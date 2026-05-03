"""
Extract: download the OLCC Cannabis Licensee CSV from Tableau Server.

Endpoint verified 2026-04-24 (see docs/TABLEAU_RESEARCH.md). The direct
`.csv` URL returns Content-Type: text/csv with ~2,600 active-license rows.
"""

from __future__ import annotations

import hashlib
import os
import tempfile
from dataclasses import dataclass
from datetime import UTC, datetime
from functools import lru_cache
from pathlib import Path

import certifi
import requests

from etl import __version__

OLCC_INTERMEDIATE = (
    Path(__file__).resolve().parent / "certs" / "sectigo_public_server_auth_ov_r36.pem"
)


@lru_cache(maxsize=1)
def _ca_bundle() -> str:
    """Return a path to a CA bundle that includes the Sectigo intermediate
    that data.olcc.state.or.us fails to serve. See etl/certs/README.md."""
    merged = Path(tempfile.gettempdir()) / "oc_data_ca_bundle.pem"
    body = Path(certifi.where()).read_bytes() + b"\n" + OLCC_INTERMEDIATE.read_bytes()
    merged.write_bytes(body)
    return str(merged)

OLCC_LICENSEE_URL = (
    "https://data.olcc.state.or.us/t/OLCCPublic/views/"
    "CannabisBusinessLicensesEndorsements/CannabisLicensesEndorsements.csv"
)

EXPECTED_COLUMNS = (
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
    url: str = OLCC_LICENSEE_URL,
    user_agent: str | None = None,
    timeout_s: int = 60,
) -> ExtractResult:
    ua = user_agent or os.getenv(
        "EXTRACTOR_USER_AGENT",
        f"OregonCannabisDataProject/{__version__} (+mark@pernotto.com)",
    )
    resp = requests.get(
        url,
        headers={"User-Agent": ua, "Accept": "text/csv"},
        timeout=timeout_s,
        verify=_ca_bundle(),
    )
    resp.raise_for_status()
    body = resp.content

    content_type = resp.headers.get("Content-Type", "")
    if not content_type.startswith("text/csv"):
        raise RuntimeError(f"unexpected Content-Type: {content_type!r}")
    if len(body) < 100_000:
        raise RuntimeError(f"response suspiciously small: {len(body)} bytes")

    header = body.split(b"\n", 1)[0].decode("utf-8", errors="replace")
    missing = [c for c in EXPECTED_COLUMNS if c not in header]
    if missing:
        raise RuntimeError(f"expected columns missing from source: {missing}")

    row_count = body.count(b"\n")  # header + data rows; minus 1 for true data count
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
        row_count=row_count - 1,
    )


if __name__ == "__main__":
    result = extract()
    print(f"wrote {result.path} ({result.row_count} rows, sha256={result.source_checksum[:12]}...)")
