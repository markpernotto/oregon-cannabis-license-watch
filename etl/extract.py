"""
Extract: download the OLCC Cannabis Business Licenses & Endorsements dataset
from the Oregon Open Data Portal (Socrata).

Source migrated 2026-08 — see docs/SOURCE_HISTORY.md. OLCC decommissioned its
Tableau Server at data.olcc.state.or.us; the dataset now lives on the state
Socrata portal as SODA resource `q32u-cmam`, refreshed daily.

Two consequences of the move that matter downstream:

- The dataset is **not** pre-filtered to active licenses. It carries expired
  and terminated ones too, flagged by `license_expired` / `inactive_date`.
- The grain is one row per *license term*, not per license. A license with a
  renewal already on file appears twice. `etl.transform` collapses this.
"""

from __future__ import annotations

import csv
import hashlib
import io
import os
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import requests

from etl import __version__

SOCRATA_DOMAIN = "data.oregon.gov"
DATASET_ID = "q32u-cmam"

SOURCE_CSV_URL = f"https://{SOCRATA_DOMAIN}/resource/{DATASET_ID}.csv"
SOURCE_LANDING_URL = f"https://{SOCRATA_DOMAIN}/d/{DATASET_ID}"

# SODA returns 1,000 rows unless asked otherwise. Request far more than the
# dataset holds (~3.8k) and treat a full page as truncation rather than
# silently ingesting a short snapshot.
PAGE_LIMIT = 50_000

# Socrata does not guarantee row order without an explicit $order. Sorting on
# the system :id makes the response byte-stable, so source_checksum only moves
# when the data actually moves.
SORT_KEY = ":id"

# Socrata field names (snake_case API names, not the display labels).
EXPECTED_COLUMNS = (
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

MIN_RESPONSE_BYTES = 100_000


@dataclass(frozen=True)
class ExtractResult:
    path: Path
    source_url: str
    source_retrieved_at: str
    source_checksum: str
    extraction_version: str
    row_count: int


def extract(
    snapshot_dir: Path = Path("data/snapshots"),
    *,
    url: str = SOURCE_CSV_URL,
    user_agent: str | None = None,
    app_token: str | None = None,
    timeout_s: int = 60,
) -> ExtractResult:
    ua = user_agent or os.getenv(
        "EXTRACTOR_USER_AGENT",
        f"OregonCannabisDataProject/{__version__} (+mark@pernotto.com)",
    )
    headers = {"User-Agent": ua, "Accept": "text/csv"}

    # Anonymous requests share a throttling pool. A free app token moves us
    # into a per-application quota; the job works without one.
    token = app_token or os.getenv("SOCRATA_APP_TOKEN")
    if token:
        headers["X-App-Token"] = token

    resp = requests.get(
        url,
        params={"$limit": PAGE_LIMIT, "$order": SORT_KEY},
        headers=headers,
        timeout=timeout_s,
    )
    resp.raise_for_status()
    body = resp.content

    content_type = resp.headers.get("Content-Type", "")
    if not content_type.startswith("text/csv"):
        raise RuntimeError(f"unexpected Content-Type: {content_type!r}")
    if len(body) < MIN_RESPONSE_BYTES:
        raise RuntimeError(f"response suspiciously small: {len(body)} bytes")

    reader = csv.reader(io.StringIO(body.decode("utf-8-sig")))
    header = next(reader, None)
    if header is None:
        raise RuntimeError("response has no header row")
    missing = [c for c in EXPECTED_COLUMNS if c not in header]
    if missing:
        raise RuntimeError(f"expected columns missing from source: {missing}")

    row_count = sum(1 for _ in reader)
    if row_count >= PAGE_LIMIT:
        raise RuntimeError(
            f"got {row_count} rows at $limit={PAGE_LIMIT}; response is truncated"
        )

    retrieved_at = datetime.now(UTC)
    checksum = hashlib.sha256(body).hexdigest()

    snapshot_dir.mkdir(parents=True, exist_ok=True)
    out = snapshot_dir / f"{retrieved_at.date().isoformat()}.csv"
    out.write_bytes(body)

    return ExtractResult(
        path=out,
        source_url=url,
        source_retrieved_at=retrieved_at.isoformat(),
        source_checksum=checksum,
        extraction_version=__version__,
        row_count=row_count,
    )


if __name__ == "__main__":
    result = extract()
    print(f"wrote {result.path} ({result.row_count} rows, sha256={result.source_checksum[:12]}...)")
