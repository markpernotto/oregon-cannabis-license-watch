"""
Load: UPSERT transformed rows into Postgres licensees_snapshots.

Idempotent on (snapshot_date, license_number). Re-running the same load is
safe and produces the same final state.
"""

from __future__ import annotations

from collections.abc import Iterable

import psycopg
from psycopg.types.json import Jsonb

UPSERT_SQL = """
INSERT INTO licensees_snapshots (
    snapshot_date, license_number, license_type, status,
    legal_name, trade_name, endorsements, county,
    physical_address, tier, canopy_type, sos_registration,
    expiration_date, raw_row,
    source_url, source_retrieved_at, source_checksum, extraction_version
) VALUES (
    %(snapshot_date)s, %(license_number)s, %(license_type)s, %(status)s,
    %(legal_name)s, %(trade_name)s, %(endorsements)s, %(county)s,
    %(physical_address)s, %(tier)s, %(canopy_type)s, %(sos_registration)s,
    %(expiration_date)s, %(raw_row)s,
    %(source_url)s, %(source_retrieved_at)s, %(source_checksum)s, %(extraction_version)s
)
ON CONFLICT (snapshot_date, license_number) DO UPDATE SET
    license_type        = EXCLUDED.license_type,
    status              = EXCLUDED.status,
    legal_name          = EXCLUDED.legal_name,
    trade_name          = EXCLUDED.trade_name,
    endorsements        = EXCLUDED.endorsements,
    county              = EXCLUDED.county,
    physical_address    = EXCLUDED.physical_address,
    tier                = EXCLUDED.tier,
    canopy_type         = EXCLUDED.canopy_type,
    sos_registration    = EXCLUDED.sos_registration,
    expiration_date     = EXCLUDED.expiration_date,
    raw_row             = EXCLUDED.raw_row,
    source_url          = EXCLUDED.source_url,
    source_retrieved_at = EXCLUDED.source_retrieved_at,
    source_checksum     = EXCLUDED.source_checksum,
    extraction_version  = EXCLUDED.extraction_version
"""


def _prepare(row: dict) -> dict:
    out = dict(row)
    out["raw_row"] = Jsonb(out["raw_row"])
    return out


def load(rows: Iterable[dict], database_url: str) -> int:
    prepared = [_prepare(r) for r in rows]
    with psycopg.connect(database_url) as conn, conn.cursor() as cur:
        cur.executemany(UPSERT_SQL, prepared)
        conn.commit()
        return len(prepared)
