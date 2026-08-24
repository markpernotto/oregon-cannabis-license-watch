"""Integration tests for etl.diff. Require a running Postgres at $DATABASE_URL."""

import csv
import io
import os
from datetime import date

import psycopg
import pytest

from etl.diff import diff
from etl.load import load
from etl.transform import SOCRATA_COLUMNS, Provenance, transform

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

# Every fixture row starts from a plausible active license and overrides only
# the fields the test cares about.
DEFAULTS = {
    "license_number": "020-AAA",
    "business_name": "Trade Name",
    "business_licenses": "ACME LLC",
    "license_type": "RECREATIONAL PRODUCER",
    "license_expired": "No",
    "effective_date": "2029-01-01",
    "expiration_date": "2030-01-01",
    "inactive_date": "",
    "sos_registration_number": "",
    "physical_address": "Exempt from Public Disclosure",
    "county": "Lane",
    "tier": "Tier I",
    "canopy_type": "Indoor",
    "endorsement": "",
}


@pytest.fixture
def clean_db():
    """Wipe both tables for the test license-numbers we use.

    Test dates are pre-1970 so MAX(snapshot_date < d1) is deterministically
    NULL even when real-data snapshots are present in the shared local DB.
    """
    test_dates = [date(1900, 1, 1), date(1900, 1, 2), date(1900, 1, 3)]
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
    """Build a valid Socrata-shaped CSV from a list of partial dicts."""
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=SOCRATA_COLUMNS)
    writer.writeheader()
    for row in rows:
        writer.writerow({**DEFAULTS, **row})
    return buf.getvalue().encode()


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


ACME = {"license_number": "020-AAA", "business_licenses": "ACME LLC"}
RETAIL = {
    "license_number": "050-BBB",
    "license_type": "RECREATIONAL RETAILER",
    "business_licenses": "RETAIL CO",
    "tier": "",
    "canopy_type": "",
}


@skip_if_no_db
def test_diff_returns_zero_with_no_prior_snapshot(clean_db):
    d1 = clean_db[0]
    _load_snapshot(d1, [ACME])
    assert diff(DATABASE_URL, d1) == 0
    assert _change_rows(d1) == []


@skip_if_no_db
def test_diff_emits_new_for_added_license(clean_db):
    d1, d2 = clean_db[0], clean_db[1]
    _load_snapshot(d1, [ACME])
    _load_snapshot(d2, [ACME, {**RETAIL, "business_licenses": "NEW CO"}])
    assert diff(DATABASE_URL, d2) == 1
    rows = _change_rows(d2)
    assert len(rows) == 1
    assert rows[0]["change_type"] == "NEW"
    assert rows[0]["license_number"] == "050-BBB"


@skip_if_no_db
def test_diff_suppresses_new_for_license_first_seen_inactive(clean_db):
    """The source carries closed licenses; arriving closed is not news.

    Without this the 2026-08 migration would have announced ~1,000 openings.
    """
    d1, d2 = clean_db[0], clean_db[1]
    _load_snapshot(d1, [ACME])
    _load_snapshot(d2, [
        ACME,
        {**RETAIL, "license_expired": "Yes", "inactive_date": "2029-06-01"},
    ])
    assert diff(DATABASE_URL, d2) == 0
    assert _change_rows(d2) == []


# A real snapshot always carries some already-closed licenses, so inactive_date
# is never universally NULL. Fixtures that exercise de-activation include one,
# otherwise the newly-published-field rule correctly ignores the column.
CLOSED = {
    "license_number": "040-CLOSED",
    "license_type": "RECREATIONAL WHOLESALER",
    "business_licenses": "SHUT CO",
    "license_expired": "Yes",
    "inactive_date": "2028-01-01",
    "tier": "",
    "canopy_type": "",
}


@skip_if_no_db
def test_diff_emits_status_field_change_on_deactivation(clean_db):
    """De-activation is a status FIELD_CHANGE now, not a REMOVED."""
    d1, d2 = clean_db[0], clean_db[1]
    _load_snapshot(d1, [ACME, CLOSED])
    _load_snapshot(d2, [
        {**ACME, "license_expired": "Yes", "inactive_date": "2029-06-01"},
        CLOSED,
    ])

    diff(DATABASE_URL, d2)
    rows = _change_rows(d2)

    assert not any(r["change_type"] == "REMOVED" for r in rows)
    status = next(r for r in rows if r["field_name"] == "status")
    assert status["change_type"] == "FIELD_CHANGE"
    assert status["prev_value"] == "ACTIVE"
    assert status["new_value"] == "INACTIVE"
    assert any(r["field_name"] == "inactive_date" for r in rows)


@skip_if_no_db
def test_diff_ignores_a_field_the_prior_snapshot_never_published(clean_db):
    """The Tableau view carried no effective_date; the portal does.

    Without this the migration night would have emitted one NULL -> date
    event per continuing license (~2,600 of them) and buried the real news.
    """
    d1, d2 = clean_db[0], clean_db[1]
    _load_snapshot(d1, [
        {**ACME, "effective_date": ""},
        {**RETAIL, "effective_date": ""},
    ])
    _load_snapshot(d2, [
        {**ACME, "effective_date": "2029-01-01"},
        {**RETAIL, "effective_date": "2029-02-01"},
    ])

    diff(DATABASE_URL, d2)
    assert not any(r["field_name"] == "effective_date" for r in _change_rows(d2))


@skip_if_no_db
def test_diff_still_reports_a_field_that_was_only_partly_populated(clean_db):
    """The rule keys on "nobody had one", not "this license didn't"."""
    d1, d2 = clean_db[0], clean_db[1]
    _load_snapshot(d1, [
        {**ACME, "sos_registration_number": ""},
        {**RETAIL, "sos_registration_number": "123456-99"},
    ])
    _load_snapshot(d2, [
        {**ACME, "sos_registration_number": "654321-11"},
        {**RETAIL, "sos_registration_number": "123456-99"},
    ])

    diff(DATABASE_URL, d2)
    rows = _change_rows(d2)
    sos = next(r for r in rows if r["field_name"] == "sos_registration")
    assert sos["license_number"] == "020-AAA"
    assert sos["prev_value"] is None
    assert sos["new_value"] == "654321-11"


@skip_if_no_db
def test_diff_emits_removed_for_disappearing_license(clean_db):
    d1, d2 = clean_db[0], clean_db[1]
    _load_snapshot(d1, [ACME, {**RETAIL, "business_licenses": "GONE CO"}])
    _load_snapshot(d2, [ACME])
    assert diff(DATABASE_URL, d2) == 1
    rows = _change_rows(d2)
    assert rows[0]["change_type"] == "REMOVED"
    assert rows[0]["license_number"] == "050-BBB"


@skip_if_no_db
def test_diff_emits_field_change_for_trade_name_update(clean_db):
    d1, d2 = clean_db[0], clean_db[1]
    _load_snapshot(d1, [{**RETAIL, "business_name": "Old Name"}])
    _load_snapshot(d2, [{**RETAIL, "business_name": "New Name"}])
    assert diff(DATABASE_URL, d2) == 1
    rows = _change_rows(d2)
    assert rows[0]["change_type"] == "FIELD_CHANGE"
    assert rows[0]["field_name"] == "trade_name"
    assert rows[0]["prev_value"] == "Old Name"
    assert rows[0]["new_value"] == "New Name"


@skip_if_no_db
def test_diff_emits_field_change_for_endorsement_array(clean_db):
    d1, d2 = clean_db[0], clean_db[1]
    _load_snapshot(d1, [{**RETAIL, "endorsement": "Marijuana Home Delivery"}])
    _load_snapshot(d2, [{
        **RETAIL,
        "endorsement": "Marijuana Home Delivery, Medical Marijuana Retailer",
    }])
    assert diff(DATABASE_URL, d2) == 1
    rows = _change_rows(d2)
    assert rows[0]["field_name"] == "endorsements"
    assert rows[0]["prev_value"] == ["Marijuana Home Delivery"]
    assert rows[0]["new_value"] == ["Marijuana Home Delivery", "Medical Marijuana Retailer"]


@skip_if_no_db
def test_diff_emits_field_change_for_renewal(clean_db):
    """A renewal moves the term boundaries; that is the signal for 'renewed'."""
    d1, d2 = clean_db[0], clean_db[1]
    _load_snapshot(d1, [ACME])
    _load_snapshot(d2, [{**ACME, "effective_date": "2030-01-02", "expiration_date": "2031-01-01"}])

    diff(DATABASE_URL, d2)
    fields = {r["field_name"] for r in _change_rows(d2)}
    assert {"effective_date", "expiration_date"} <= fields


@skip_if_no_db
def test_diff_is_idempotent(clean_db):
    d1, d2 = clean_db[0], clean_db[1]
    _load_snapshot(d1, [ACME])
    _load_snapshot(d2, [ACME, {**RETAIL, "business_licenses": "NEW CO"}])

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
    _load_snapshot(d1, [{**ACME, "business_licenses": "ORIGINAL"}])
    _load_snapshot(d2, [{**ACME, "business_licenses": "MIDDLE"}])
    _load_snapshot(d3, [{**ACME, "business_licenses": "LATEST"}])
    assert diff(DATABASE_URL, d3) == 1
    rows = _change_rows(d3)
    assert rows[0]["field_name"] == "legal_name"
    assert rows[0]["prev_value"] == "MIDDLE"  # not "ORIGINAL"
    assert rows[0]["new_value"] == "LATEST"
