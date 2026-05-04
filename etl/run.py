"""
End-to-end pipeline runner: extract -> transform -> load -> diff.

Usage:
    python -m etl.run                              # full pipeline against live OLCC
    python -m etl.run --seed data/snapshots/seed.csv --as-of 2026-04-24
                                                   # load a local CSV as a backfilled snapshot
"""

from __future__ import annotations

import argparse
import hashlib
import os
import sys
from datetime import UTC, date, datetime
from pathlib import Path

from dotenv import load_dotenv

from etl import __version__
from etl.diff import diff
from etl.extract import OLCC_LICENSEE_URL, extract
from etl.load import load
from etl.publish import publish
from etl.transform import Provenance, transform


def _provenance_for_seed(path: Path, as_of: date) -> Provenance:
    body = path.read_bytes()
    return Provenance(
        source_url=f"file://{path.resolve()}",
        source_retrieved_at=datetime.combine(as_of, datetime.min.time(), tzinfo=UTC).isoformat(),
        source_checksum=hashlib.sha256(body).hexdigest(),
        extraction_version=__version__,
    )


def _live_pipeline(database_url: str) -> None:
    print(f"[1/5] extracting from {OLCC_LICENSEE_URL}")
    result = extract()
    print(f"      wrote {result.path} ({result.row_count} rows)")
    print(f"      sha256: {result.source_checksum}")

    print("[2/5] transforming")
    csv_bytes = result.path.read_bytes()
    snapshot_date = date.fromisoformat(result.path.stem)
    prov = Provenance(
        source_url=result.source_url,
        source_retrieved_at=result.source_retrieved_at,
        source_checksum=result.source_checksum,
        extraction_version=result.extraction_version,
    )
    rows = transform(csv_bytes, snapshot_date=snapshot_date, provenance=prov)
    print(f"      transformed {len(rows)} rows")

    print(f"[3/5] loading to Postgres ({_safe_url(database_url)})")
    loaded = load(rows, database_url)
    print(f"      upserted {loaded} rows for snapshot_date={snapshot_date}")

    print("[4/5] diff against prior snapshot")
    n = diff(database_url, snapshot_date)
    print(f"      emitted {n} change rows")

    print("[5/5] publishing public/changes.json + public/rss.xml")
    pub = publish(database_url)
    print(f"      wrote {pub['json_path']} ({pub['total_changes']} changes)")
    print(f"      wrote {pub['rss_path']}")


def _seed_pipeline(database_url: str, seed_path: Path, as_of: date) -> None:
    print(f"[1/3] reading seed {seed_path} as of {as_of}")
    csv_bytes = seed_path.read_bytes()
    prov = _provenance_for_seed(seed_path, as_of)

    print("[2/3] transforming")
    rows = transform(csv_bytes, snapshot_date=as_of, provenance=prov)
    print(f"      transformed {len(rows)} rows")

    print(f"[3/3] loading to Postgres ({_safe_url(database_url)})")
    loaded = load(rows, database_url)
    print(f"      upserted {loaded} rows for snapshot_date={as_of}")


def _safe_url(url: str) -> str:
    """Strip the password from a database URL for display."""
    if "://" not in url or "@" not in url:
        return url
    scheme, rest = url.split("://", 1)
    if "@" in rest:
        creds, host = rest.rsplit("@", 1)
        if ":" in creds:
            user = creds.split(":", 1)[0]
            return f"{scheme}://{user}:***@{host}"
    return url


def main(argv: list[str] | None = None) -> int:
    load_dotenv()

    parser = argparse.ArgumentParser(description="OC Data pipeline runner")
    parser.add_argument(
        "--seed",
        type=Path,
        help="Path to a CSV to load as a backfilled snapshot (skips extract+diff)",
    )
    parser.add_argument(
        "--as-of",
        type=date.fromisoformat,
        help="Snapshot date to assign to the seed CSV (YYYY-MM-DD)",
    )
    args = parser.parse_args(argv)

    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        print("error: DATABASE_URL is not set", file=sys.stderr)
        return 2

    if args.seed:
        if not args.as_of:
            print("error: --seed requires --as-of YYYY-MM-DD", file=sys.stderr)
            return 2
        _seed_pipeline(database_url, args.seed, args.as_of)
    else:
        _live_pipeline(database_url)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
