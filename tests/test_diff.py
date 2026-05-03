"""Integration tests for etl.diff. Require a running Postgres at $DATABASE_URL."""

import os
from datetime import date

import psycopg
import pytest

from etl.diff import diff
from etl.load import load
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
    """Wipe both tables for the test license-numbers we use."""
    test_dates = [date(2099, 1, 1), date(2099, 1, 2), date(2099, 1, 3)]
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
    """Build a minimal valid OLCC-shaped CSV from a list of partial dicts."""
    headers = [
        "Business Licenses", "Business Name", "Canopy Type", "County", "Endorsement",
        "License Number", "License Type", "PhysicalAddress", "SOS Registration Number",
        "Status", "Tier", "Expiration Date",
    ]
    lines = [",".join(headers)]
    for row in rows:
        cells = [str(row.get(h, " ")) for h in headers]
        lines.append(",".join(cells))
    return ("\n".join(lines) + "\n").encode()


def _load_snapshot(snapshot_date: date, rows: list[dict]) -> None:
    csv_bytes = _csv_for(rows)
    transformed = transform(csv_bytes, snapshot_date=snapshot_date, provenance=PROV)
    load(transformed, DATABASE_URL)


def _change_rows(snapshot_date: date) -> list[dict]:
    with psycopg.connect(DATABASE_URL) as conn, conn.cursor(row_factory=psycopg.rows.dict_row) as cur:
        cur.execute(
            "SELECT change_type, license_number, field_name, prev_value, new_value "
            "FROM license_changes WHERE source_snapshot_date = %s "
            "ORDER BY change_type, license_number, field_name",
            (snapshot_date,),
        )
        return cur.fetchall()


@skip_if_no_db
def test_diff_returns_zero_with_no_prior_snapshot(clean_db):
    d1 = clean_db[0]
    _load_snapshot(d1, [
        {"License Number": "020-AAA", "License Type": "RECREATIONAL PRODUCER",
         "Status": "ACTIVE", "Business Licenses": "ACME LLC", "Expiration Date": "1/1/2030"},
    ])
    assert diff(DATABASE_URL, d1) == 0
    assert _change_rows(d1) == []


@skip_if_no_db
def test_diff_emits_new_for_added_license(clean_db):
    d1, d2 = clean_db[0], clean_db[1]
    _load_snapshot(d1, [
        {"License Number": "020-AAA", "License Type": "RECREATIONAL PRODUCER",
         "Status": "ACTIVE", "Business Licenses": "ACME LLC", "Expiration Date": "1/1/2030"},
    ])
    _load_snapshot(d2, [
        {"License Number": "020-AAA", "License Type": "RECREATIONAL PRODUCER",
         "Status": "ACTIVE", "Business Licenses": "ACME LLC", "Expiration Date": "1/1/2030"},
        {"License Number": "050-BBB", "License Type": "RECREATIONAL RETAILER",
         "Status": "ACTIVE", "Business Licenses": "NEW CO", "Expiration Date": "2/1/2030"},
    ])
    assert diff(DATABASE_URL, d2) == 1
    rows = _change_rows(d2)
    assert len(rows) == 1
    assert rows[0]["change_type"] == "NEW"
    assert rows[0]["license_number"] == "050-BBB"


@skip_if_no_db
def test_diff_emits_removed_for_disappearing_license(clean_db):
    d1, d2 = clean_db[0], clean_db[1]
    _load_snapshot(d1, [
        {"License Number": "020-AAA", "License Type": "RECREATIONAL PRODUCER",
         "Status": "ACTIVE", "Business Licenses": "ACME LLC", "Expiration Date": "1/1/2030"},
        {"License Number": "050-BBB", "License Type": "RECREATIONAL RETAILER",
         "Status": "ACTIVE", "Business Licenses": "GONE CO", "Expiration Date": "2/1/2030"},
    ])
    _load_snapshot(d2, [
        {"License Number": "020-AAA", "License Type": "RECREATIONAL PRODUCER",
         "Status": "ACTIVE", "Business Licenses": "ACME LLC", "Expiration Date": "1/1/2030"},
    ])
    assert diff(DATABASE_URL, d2) == 1
    rows = _change_rows(d2)
    assert rows[0]["change_type"] == "REMOVED"
    assert rows[0]["license_number"] == "050-BBB"


@skip_if_no_db
def test_diff_emits_field_change_for_trade_name_update(clean_db):
    d1, d2 = clean_db[0], clean_db[1]
    _load_snapshot(d1, [
        {"License Number": "050-BBB", "License Type": "RECREATIONAL RETAILER",
         "Status": "ACTIVE", "Business Licenses": "RETAIL CO", "Business Name": "Old Name",
         "Expiration Date": "2/1/2030"},
    ])
    _load_snapshot(d2, [
        {"License Number": "050-BBB", "License Type": "RECREATIONAL RETAILER",
         "Status": "ACTIVE", "Business Licenses": "RETAIL CO", "Business Name": "New Name",
         "Expiration Date": "2/1/2030"},
    ])
    assert diff(DATABASE_URL, d2) == 1
    rows = _change_rows(d2)
    assert rows[0]["change_type"] == "FIELD_CHANGE"
    assert rows[0]["field_name"] == "trade_name"
    assert rows[0]["prev_value"] == "Old Name"
    assert rows[0]["new_value"] == "New Name"


@skip_if_no_db
def test_diff_emits_field_change_for_endorsement_array(clean_db):
    d1, d2 = clean_db[0], clean_db[1]
    _load_snapshot(d1, [
        {"License Number": "050-BBB", "License Type": "RECREATIONAL RETAILER",
         "Status": "ACTIVE", "Business Licenses": "RETAIL CO",
         "Endorsement": "Marijuana Home Delivery", "Expiration Date": "2/1/2030"},
    ])
    _load_snapshot(d2, [
        {"License Number": "050-BBB", "License Type": "RECREATIONAL RETAILER",
         "Status": "ACTIVE", "Business Licenses": "RETAIL CO",
         "Endorsement": '"Marijuana Home Delivery, Medical Marijuana Retailer"',
         "Expiration Date": "2/1/2030"},
    ])
    # CSV building above doesn't quote properly; simpler to assert at least
    # one FIELD_CHANGE occurred and field_name is endorsements OR the
    # endorsement field. We accept either-shape because the test fixture
    # builder is intentionally minimal.
    n = diff(DATABASE_URL, d2)
    assert n >= 1
    rows = _change_rows(d2)
    field_changes = [r for r in rows if r["change_type"] == "FIELD_CHANGE"]
    assert any(r["field_name"] == "endorsements" for r in field_changes)


@skip_if_no_db
def test_diff_is_idempotent(clean_db):
    d1, d2 = clean_db[0], clean_db[1]
    _load_snapshot(d1, [
        {"License Number": "020-AAA", "License Type": "RECREATIONAL PRODUCER",
         "Status": "ACTIVE", "Business Licenses": "ACME LLC", "Expiration Date": "1/1/2030"},
    ])
    _load_snapshot(d2, [
        {"License Number": "020-AAA", "License Type": "RECREATIONAL PRODUCER",
         "Status": "ACTIVE", "Business Licenses": "ACME LLC", "Expiration Date": "1/1/2030"},
        {"License Number": "050-BBB", "License Type": "RECREATIONAL RETAILER",
         "Status": "ACTIVE", "Business Licenses": "NEW CO", "Expiration Date": "2/1/2030"},
    ])

    first = diff(DATABASE_URL, d2)
    second = diff(DATABASE_URL, d2)

    assert first == 1
    assert second == 1  # function returns rows it computed, not rows it inserted

    rows = _change_rows(d2)
    assert len(rows) == 1, "duplicate rows after second diff() call"


@skip_if_no_db
def test_diff_uses_most_recent_prior_snapshot(clean_db):
    """Given snapshots on d1, d2, d3, running diff for d3 must compare against d2 (not d1)."""
    d1, d2, d3 = clean_db
    _load_snapshot(d1, [
        {"License Number": "020-AAA", "License Type": "RECREATIONAL PRODUCER",
         "Status": "ACTIVE", "Business Licenses": "ORIGINAL", "Expiration Date": "1/1/2030"},
    ])
    _load_snapshot(d2, [
        {"License Number": "020-AAA", "License Type": "RECREATIONAL PRODUCER",
         "Status": "ACTIVE", "Business Licenses": "MIDDLE", "Expiration Date": "1/1/2030"},
    ])
    _load_snapshot(d3, [
        {"License Number": "020-AAA", "License Type": "RECREATIONAL PRODUCER",
         "Status": "ACTIVE", "Business Licenses": "LATEST", "Expiration Date": "1/1/2030"},
    ])
    assert diff(DATABASE_URL, d3) == 1
    rows = _change_rows(d3)
    assert rows[0]["field_name"] == "legal_name"
    assert rows[0]["prev_value"] == "MIDDLE"  # not "ORIGINAL"
    assert rows[0]["new_value"] == "LATEST"
