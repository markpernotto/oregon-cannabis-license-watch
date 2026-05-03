"""
Diff: compare the latest licensees_snapshots snapshot against the prior one
and emit license_changes rows.

Emits NEW, REMOVED, and one FIELD_CHANGE row per changed field. The source
view is filtered to ACTIVE-only, so de-activations manifest as REMOVED — we
don't emit STATUS_CHANGE because we'd never see the alternative.

Idempotent: a unique index on
(source_snapshot_date, license_number, change_type, field_name) backs an
INSERT ... ON CONFLICT DO NOTHING, so re-running diff on the same pair of
snapshots produces no duplicates.

Graceful first-run: if there is no prior snapshot, returns 0 (no error).
"""

from __future__ import annotations

from datetime import UTC, date, datetime

import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

# Fields compared for FIELD_CHANGE detection. Provenance and snapshot_date
# are intentionally excluded; raw_row is excluded because it duplicates these.
COMPARED_FIELDS = (
    "license_type",
    "status",
    "legal_name",
    "trade_name",
    "endorsements",
    "county",
    "physical_address",
    "tier",
    "canopy_type",
    "sos_registration",
    "expiration_date",
)

_SNAPSHOT_FIELDS = (
    "license_number",
    *COMPARED_FIELDS,
)

_SELECT_SNAPSHOT_SQL = f"""
SELECT {", ".join(_SNAPSHOT_FIELDS)}
FROM licensees_snapshots
WHERE snapshot_date = %s
"""

_INSERT_CHANGE_SQL = """
INSERT INTO license_changes (
    observed_at, license_number, change_type, field_name,
    prev_value, new_value, diff_summary, source_snapshot_date
) VALUES (
    %(observed_at)s, %(license_number)s, %(change_type)s, %(field_name)s,
    %(prev_value)s, %(new_value)s, %(diff_summary)s, %(source_snapshot_date)s
)
ON CONFLICT (source_snapshot_date, license_number, change_type, field_name)
DO NOTHING
"""


def _summary_new(row: dict) -> str:
    name = row.get("trade_name") or row.get("legal_name") or row["license_number"]
    return f"NEW {row['license_type']}: {name} ({row['license_number']})"


def _summary_removed(row: dict) -> str:
    name = row.get("trade_name") or row.get("legal_name") or row["license_number"]
    return f"REMOVED: {name} ({row['license_number']})"


def _summary_field_change(license_number: str, field: str, prev, new) -> str:
    return f"{license_number} {field}: {prev!r} -> {new!r}"


def diff(database_url: str, snapshot_date: date) -> int:
    observed_at = datetime.now(UTC)
    with psycopg.connect(database_url) as conn, conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            "SELECT MAX(snapshot_date) AS prior FROM licensees_snapshots "
            "WHERE snapshot_date < %s",
            (snapshot_date,),
        )
        prior_row = cur.fetchone()
        prior_date = prior_row["prior"] if prior_row else None
        if prior_date is None:
            return 0

        cur.execute(_SELECT_SNAPSHOT_SQL, (snapshot_date,))
        today = {r["license_number"]: r for r in cur.fetchall()}
        cur.execute(_SELECT_SNAPSHOT_SQL, (prior_date,))
        prior = {r["license_number"]: r for r in cur.fetchall()}

        today_keys = set(today)
        prior_keys = set(prior)

        changes: list[dict] = []

        for lic in sorted(today_keys - prior_keys):
            row = today[lic]
            changes.append(
                {
                    "observed_at": observed_at,
                    "license_number": lic,
                    "change_type": "NEW",
                    "field_name": None,
                    "prev_value": None,
                    "new_value": Jsonb({k: _jsonable(v) for k, v in row.items()}),
                    "diff_summary": _summary_new(row),
                    "source_snapshot_date": snapshot_date,
                }
            )

        for lic in sorted(prior_keys - today_keys):
            row = prior[lic]
            changes.append(
                {
                    "observed_at": observed_at,
                    "license_number": lic,
                    "change_type": "REMOVED",
                    "field_name": None,
                    "prev_value": Jsonb({k: _jsonable(v) for k, v in row.items()}),
                    "new_value": None,
                    "diff_summary": _summary_removed(row),
                    "source_snapshot_date": snapshot_date,
                }
            )

        for lic in sorted(today_keys & prior_keys):
            t = today[lic]
            p = prior[lic]
            for field in COMPARED_FIELDS:
                if t[field] != p[field]:
                    changes.append(
                        {
                            "observed_at": observed_at,
                            "license_number": lic,
                            "change_type": "FIELD_CHANGE",
                            "field_name": field,
                            "prev_value": Jsonb(_jsonable(p[field])),
                            "new_value": Jsonb(_jsonable(t[field])),
                            "diff_summary": _summary_field_change(lic, field, p[field], t[field]),
                            "source_snapshot_date": snapshot_date,
                        }
                    )

        if changes:
            cur.executemany(_INSERT_CHANGE_SQL, changes)
            conn.commit()

        return len(changes)


def _jsonable(value):
    """Coerce date/datetime to ISO strings; everything else passes through."""
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    return value
