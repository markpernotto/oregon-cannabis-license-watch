"""
Transform source CSV bytes into rows matching the licensees_snapshots schema.

Two source formats are supported, detected from the header row:

- **socrata** (current) — the Oregon Open Data Portal export, snake_case API
  field names. See docs/SOURCE_HISTORY.md.
- **legacy** (2026-04 .. 2026-08) — the retired OLCC Tableau Server export,
  display-name headers. Retained so `etl.backfill` can still replay every
  CSV committed under data/snapshots/.

Both formats produce identical output rows, so everything downstream of this
module is format-agnostic.

Source quirks handled:
- Legacy blank cells arrive as a single space " ", not as empty string.
- Endorsements are a comma-separated list inside one quoted CSV field.
- "Exempt from Public Disclosure" is meaningful for producer/processor/
  wholesaler addresses and is preserved verbatim, not nulled.
- Legacy dates are M/D/YYYY (no leading zeros); Socrata dates are ISO.
- Socrata publishes one row per *license term*, so a license with a renewal
  already on file appears twice. We collapse to the term in effect on the
  snapshot date; the uncollapsed rows stay in the committed snapshot CSV.
"""

from __future__ import annotations

import csv
import io
import logging
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime

from etl.vocab import normalize

LOG = logging.getLogger(__name__)

# Current source: Socrata API field names.
SOCRATA_COLUMNS = (
    "license_number",
    "business_name",
    "business_licenses",
    "license_type",
    "license_expired",
    "effective_date",
    "expiration_date",
    "inactive_date",
    "sos_registration_number",
    "physical_address",
    "county",
    "tier",
    "canopy_type",
    "endorsement",
)

# Retired source: OLCC Tableau Server display headers.
LEGACY_COLUMNS = (
    "Business Licenses",
    "Business Name",
    "Canopy Type",
    "County",
    "Endorsement",
    "License Number",
    "License Type",
    "PhysicalAddress",
    "SOS Registration Number",
    "Status",
    "Tier",
    "Expiration Date",
)

# Back-compat alias: tests and docs referred to the legacy set by this name
# when it was the only set.
REQUIRED_COLUMNS = SOCRATA_COLUMNS

_DATE_FORMATS = ("%Y-%m-%d", "%m/%d/%Y")


@dataclass(frozen=True)
class Provenance:
    source_url: str
    source_retrieved_at: str
    source_checksum: str
    extraction_version: str


def _optional(value: str | None) -> str | None:
    if value is None:
        return None
    stripped = value.strip()
    return stripped or None


def _required(value: str | None, field: str) -> str:
    cleaned = _optional(value)
    if cleaned is None:
        raise ValueError(f"required field {field!r} is empty")
    return cleaned


def _endorsements(value: str | None) -> list[str]:
    cleaned = _optional(value)
    if cleaned is None:
        return []
    return [piece.strip() for piece in cleaned.split(",") if piece.strip()]


def _parse_date(value: str | None, field: str = "date") -> date | None:
    cleaned = _optional(value)
    if cleaned is None:
        return None
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(cleaned, fmt).date()
        except ValueError:
            continue
    # The source occasionally carries sentinels like "*" for irregular records.
    # Don't fail; the original stays in raw_row and the column goes NULL.
    LOG.warning("unparseable %s %r; storing NULL", field, cleaned)
    return None


def _derive_status(expired_flag: str | None, inactive_date: date | None) -> str:
    """Map the Socrata `license_expired` flag + `inactive_date` onto our
    status vocabulary.

    The portal publishes no status column. It publishes a curated
    `license_expired` Yes/No flag (authoritative — 177 currently-active
    licenses sit past their printed expiration date while in renewal) plus an
    `inactive_date` that is set when a license ended before its term ran out.
    Most inactive_date values precede expiration_date, i.e. the license was
    surrendered or revoked rather than allowed to lapse, so INACTIVE and
    EXPIRED are meaningfully different outcomes here.
    """
    flag = (_optional(expired_flag) or "").casefold()
    if flag == "no":
        return "ACTIVE"
    if flag == "yes":
        return "INACTIVE" if inactive_date is not None else "EXPIRED"
    LOG.warning("unexpected license_expired value %r; deriving from inactive_date", expired_flag)
    return "INACTIVE" if inactive_date is not None else "ACTIVE"


def _covers(term: dict, as_of: date) -> bool:
    """True if this license term is in effect on `as_of`."""
    effective = _parse_date(term.get("effective_date"))
    expiration = _parse_date(term.get("expiration_date"))
    if effective is not None and effective > as_of:
        return False  # term has not started yet
    return expiration is None or expiration >= as_of


def _select_term(terms: list[dict], license_number: str, as_of: date) -> dict:
    """Pick the license term to represent a license number on `as_of`.

    Prefer a term in effect on the snapshot date. Failing that (every term
    lapsed, or every term still in the future) take the most recently
    effective one, which is the closest thing to the license's current state.

    Exactly one term is live per license in the source as observed
    (2026-08-24: 92 of 94 multi-term licenses, the other two closed). Nothing
    upstream guarantees that, though, and if it stops being true the choice
    below turns arbitrary and the row could flap between snapshots — so say
    so out loud rather than picking silently.
    """
    if len(terms) == 1:
        return terms[0]
    live = [t for t in terms if _covers(t, as_of)]
    if len(live) > 1:
        LOG.warning(
            "license %s has %d terms in effect on %s; picking the most recently "
            "effective one. Diffs for this license may be unstable.",
            license_number,
            len(live),
            as_of,
        )
    pool = live or terms
    return max(pool, key=lambda t: (_parse_date(t.get("effective_date")) or date.min))


def _detect_format(fieldnames: list[str]) -> str:
    if all(c in fieldnames for c in SOCRATA_COLUMNS):
        return "socrata"
    if all(c in fieldnames for c in LEGACY_COLUMNS):
        return "legacy"
    missing = [c for c in SOCRATA_COLUMNS if c not in fieldnames]
    raise ValueError(f"required columns missing from CSV: {missing}")


def _row_socrata(src: dict, *, snapshot_date: date, provenance: Provenance) -> dict:
    inactive_date = _parse_date(src.get("inactive_date"), "inactive_date")
    return {
        "snapshot_date": snapshot_date,
        "license_number": _required(src.get("license_number"), "license_number"),
        "license_type": normalize(
            "license_type",
            _required(src.get("license_type"), "license_type"),
        ),
        "status": normalize(
            "status",
            _derive_status(src.get("license_expired"), inactive_date),
        ),
        "legal_name": _optional(src.get("business_licenses")),
        "trade_name": _optional(src.get("business_name")),
        "endorsements": _endorsements(src.get("endorsement")),
        "county": _optional(src.get("county")),
        "physical_address": _optional(src.get("physical_address")),
        "tier": _optional(src.get("tier")),
        "canopy_type": _optional(src.get("canopy_type")),
        "sos_registration": _optional(src.get("sos_registration_number")),
        "effective_date": _parse_date(src.get("effective_date"), "effective_date"),
        "expiration_date": _parse_date(src.get("expiration_date"), "expiration_date"),
        "inactive_date": inactive_date,
        "raw_row": dict(src),
        "source_url": provenance.source_url,
        "source_retrieved_at": provenance.source_retrieved_at,
        "source_checksum": provenance.source_checksum,
        "extraction_version": provenance.extraction_version,
    }


def _row_legacy(src: dict, *, snapshot_date: date, provenance: Provenance) -> dict:
    return {
        "snapshot_date": snapshot_date,
        "license_number": _required(src.get("License Number"), "License Number"),
        "license_type": normalize(
            "license_type",
            _required(src.get("License Type"), "License Type"),
        ),
        "status": normalize("status", _required(src.get("Status"), "Status")),
        "legal_name": _optional(src.get("Business Licenses")),
        "trade_name": _optional(src.get("Business Name")),
        "endorsements": _endorsements(src.get("Endorsement")),
        "county": _optional(src.get("County")),
        "physical_address": _optional(src.get("PhysicalAddress")),
        "tier": _optional(src.get("Tier")),
        "canopy_type": _optional(src.get("Canopy Type")),
        "sos_registration": _optional(src.get("SOS Registration Number")),
        # The Tableau view published neither of these.
        "effective_date": None,
        "expiration_date": _parse_date(src.get("Expiration Date"), "expiration date"),
        "inactive_date": None,
        "raw_row": dict(src),
        "source_url": provenance.source_url,
        "source_retrieved_at": provenance.source_retrieved_at,
        "source_checksum": provenance.source_checksum,
        "extraction_version": provenance.extraction_version,
    }


def _assert_unique_license_numbers(rows: list[dict]) -> None:
    """Enforce the licensees_snapshots primary key before we reach the database.

    (snapshot_date, license_number) is the PK, and the source's grain is the
    license *term*, so collapsing correctly is load-bearing. Checking here
    turns a future upstream change into one clear error naming the offending
    licenses, instead of a psycopg unique-violation partway through a
    3,700-row executemany.
    """
    seen: set[str] = set()
    dupes: set[str] = set()
    for row in rows:
        number = row["license_number"]
        if number in seen:
            dupes.add(number)
        seen.add(number)
    if dupes:
        listed = ", ".join(sorted(dupes)[:5])
        more = f" (and {len(dupes) - 5} more)" if len(dupes) > 5 else ""
        raise ValueError(
            f"term collapsing left {len(dupes)} duplicate license number(s): {listed}{more}"
        )


def transform(
    csv_bytes: bytes,
    *,
    snapshot_date: date,
    provenance: Provenance,
) -> list[dict]:
    text = csv_bytes.decode("utf-8-sig")
    reader = csv.DictReader(io.StringIO(text))

    if reader.fieldnames is None:
        raise ValueError("CSV has no header row")
    source_format = _detect_format(reader.fieldnames)
    src_rows = list(reader)

    if source_format == "legacy":
        return [
            _row_legacy(src, snapshot_date=snapshot_date, provenance=provenance)
            for src in src_rows
        ]

    by_license: dict[str, list[dict]] = defaultdict(list)
    for src in src_rows:
        by_license[_required(src.get("license_number"), "license_number")].append(src)

    collapsed = sum(1 for terms in by_license.values() if len(terms) > 1)
    if collapsed:
        LOG.info(
            "%d license(s) published multiple terms; kept the term in effect on %s",
            collapsed,
            snapshot_date,
        )

    rows = [
        _row_socrata(
            _select_term(terms, number, snapshot_date),
            snapshot_date=snapshot_date,
            provenance=provenance,
        )
        for number, terms in sorted(by_license.items())
    ]
    _assert_unique_license_numbers(rows)
    return rows
