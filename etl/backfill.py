"""
Backfill: load every CSV in data/snapshots/ into the database, then run
diff for each snapshot date in chronological order, then publish.

Idempotent — every step uses ON CONFLICT-style upserts, so running this
multiple times is safe. Intended to be run once when bringing up a new
production DB so it inherits the history that's already committed to the
repo.

Usage:
    DATABASE_URL=... python -m etl.backfill
"""

from __future__ import annotations

import hashlib
import os
import sys
from datetime import UTC, date, datetime
from pathlib import Path

from etl import __version__
from etl.diff import diff
from etl.load import load
from etl.publish import publish
from etl.transform import Provenance, transform

SNAPSHOTS_DIR = Path("data/snapshots")
SEED_DATE = date(2026, 4, 24)


def _snapshot_date_from_filename(path: Path) -> date | None:
    if path.name == "seed.csv":
        return SEED_DATE
    try:
        return date.fromisoformat(path.stem)
    except ValueError:
        return None


def _provenance_for(path: Path) -> Provenance:
    body = path.read_bytes()
    return Provenance(
        source_url=f"file://{path.resolve()}",
        source_retrieved_at=datetime.now(UTC).isoformat(),
        source_checksum=hashlib.sha256(body).hexdigest(),
        extraction_version=f"backfill-{__version__}",
    )


def backfill(database_url: str, snapshots_dir: Path = SNAPSHOTS_DIR) -> dict:
    csvs = sorted(snapshots_dir.glob("*.csv"))
    dated: list[tuple[date, Path]] = []
    for csv_path in csvs:
        sd = _snapshot_date_from_filename(csv_path)
        if sd is None:
            print(f"  skipping (no date): {csv_path.name}")
            continue
        dated.append((sd, csv_path))
    dated.sort(key=lambda p: p[0])

    print(f"backfilling {len(dated)} snapshot(s):")
    for sd, csv_path in dated:
        prov = _provenance_for(csv_path)
        rows = transform(csv_path.read_bytes(), snapshot_date=sd, provenance=prov)
        n_loaded = load(rows, database_url)
        print(f"  loaded {sd}: {n_loaded} rows from {csv_path.name}")

    print("running diff for each snapshot date:")
    total_changes = 0
    for sd, _ in dated:
        n = diff(database_url, sd)
        total_changes += n
        print(f"  diff {sd}: {n} change rows")

    print("publishing artifacts:")
    pub = publish(database_url)
    print(f"  wrote {pub['json_path']} ({pub['total_changes']} changes)")
    print(f"  wrote {pub['rss_path']}")

    return {
        "snapshots_loaded": len(dated),
        "total_changes_emitted": total_changes,
        "json_path": pub["json_path"],
        "rss_path": pub["rss_path"],
    }


def main() -> int:
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        print("error: DATABASE_URL is not set", file=sys.stderr)
        return 2
    backfill(database_url)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
