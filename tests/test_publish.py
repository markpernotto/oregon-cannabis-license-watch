"""Integration tests for etl.publish. Require Postgres at $DATABASE_URL."""

import json
import os
import xml.etree.ElementTree as ET
from datetime import date

import psycopg
import pytest

from etl.diff import diff
from etl.load import load
from etl.publish import publish
from etl.transform import Provenance, transform

DATABASE_URL = os.getenv("DATABASE_URL")

pytestmark = pytest.mark.integration

skip_if_no_db = pytest.mark.skipif(
    not DATABASE_URL,
    reason="DATABASE_URL not set; integration tests skipped",
)

PROV = Provenance(
    source_url="https://example.test/source.csv",
    source_retrieved_at="2099-01-01T00:00:00+00:00",
    source_checksum="x" * 64,
    extraction_version="0.1.0",
)


@pytest.fixture
def clean_db():
    test_dates = [date(2099, 6, 1), date(2099, 6, 2)]
    with psycopg.connect(DATABASE_URL) as conn, conn.cursor() as cur:
        cur.execute("DELETE FROM licensees_snapshots WHERE snapshot_date = ANY(%s)", (test_dates,))
        cur.execute("DELETE FROM license_changes WHERE source_snapshot_date = ANY(%s)", (test_dates,))
        conn.commit()
    yield test_dates
    with psycopg.connect(DATABASE_URL) as conn, conn.cursor() as cur:
        cur.execute("DELETE FROM licensees_snapshots WHERE snapshot_date = ANY(%s)", (test_dates,))
        cur.execute("DELETE FROM license_changes WHERE source_snapshot_date = ANY(%s)", (test_dates,))
        conn.commit()


def _csv_for(rows: list[dict]) -> bytes:
    headers = [
        "Business Licenses", "Business Name", "Canopy Type", "County", "Endorsement",
        "License Number", "License Type", "PhysicalAddress", "SOS Registration Number",
        "Status", "Tier", "Expiration Date",
    ]
    lines = [",".join(headers)]
    for row in rows:
        lines.append(",".join(str(row.get(h, " ")) for h in headers))
    return ("\n".join(lines) + "\n").encode()


def _load(snapshot_date: date, rows: list[dict]) -> None:
    csv_bytes = _csv_for(rows)
    transformed = transform(csv_bytes, snapshot_date=snapshot_date, provenance=PROV)
    load(transformed, DATABASE_URL)


@skip_if_no_db
def test_publish_writes_artifacts(clean_db, tmp_path):
    d1, d2 = clean_db
    _load(d1, [
        {"License Number": "020-PUB1", "License Type": "RECREATIONAL PRODUCER",
         "Status": "ACTIVE", "Business Licenses": "PUB CO", "Expiration Date": "1/1/2030"},
    ])
    _load(d2, [
        {"License Number": "020-PUB1", "License Type": "RECREATIONAL PRODUCER",
         "Status": "ACTIVE", "Business Licenses": "PUB CO", "Expiration Date": "1/1/2030"},
        {"License Number": "050-PUB2", "License Type": "RECREATIONAL RETAILER",
         "Status": "ACTIVE", "Business Licenses": "RETAIL CO", "Expiration Date": "2/1/2030"},
    ])
    diff(DATABASE_URL, d2)

    result = publish(DATABASE_URL, out_dir=tmp_path, window_days=365 * 100)

    assert result["json_path"].exists()
    assert result["rss_path"].exists()

    payload = json.loads(result["json_path"].read_text())
    assert payload["source"] == "OLCC Cannabis Licensee Public Report"
    assert payload["total_changes"] >= 1
    assert payload["freshness_sla_hours"] == 26
    new_entries = [c for c in payload["changes"] if c["change_type"] == "NEW"]
    assert any(c["license_number"] == "050-PUB2" for c in new_entries)

    rss_root = ET.fromstring(result["rss_path"].read_bytes())
    assert rss_root.tag == "rss"
    items = rss_root.findall("./channel/item")
    assert len(items) >= 1
    titles = [item.findtext("title") for item in items]
    assert any("050-PUB2" in (t or "") for t in titles)


@skip_if_no_db
def test_publish_handles_no_recent_changes(clean_db, tmp_path):
    """Empty changes window must still produce valid (empty) artifacts.

    Uses an explicit far-future cutoff so the test is not state-dependent on
    whether real-data changes exist in the shared local DB.
    """
    from datetime import UTC, datetime
    result = publish(
        DATABASE_URL,
        out_dir=tmp_path,
        cutoff=datetime(2099, 12, 31, tzinfo=UTC),
    )

    payload = json.loads(result["json_path"].read_text())
    assert payload["total_changes"] == 0
    assert payload["changes"] == []

    rss_root = ET.fromstring(result["rss_path"].read_bytes())
    assert rss_root.findall("./channel/item") == []
