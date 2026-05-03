"""Integration tests for etl.load. Require a Postgres at $DATABASE_URL."""

import os
from datetime import date
from pathlib import Path

import psycopg
import pytest

from etl.load import load
from etl.transform import Provenance, transform

DATABASE_URL = os.getenv("DATABASE_URL")

pytestmark = pytest.mark.integration

skip_if_no_db = pytest.mark.skipif(
    not DATABASE_URL,
    reason="DATABASE_URL not set; integration tests skipped",
)


@pytest.fixture
def schema_applied():
    """Apply schema.sql against the configured database."""
    schema_path = Path(__file__).resolve().parent.parent / "etl" / "schema.sql"
    with psycopg.connect(DATABASE_URL) as conn, conn.cursor() as cur:
        cur.execute(schema_path.read_text())
        conn.commit()
    yield
    # Don't drop — re-runs are idempotent and we want to keep state visible.


@pytest.fixture
def cleanup_snapshot():
    """Remove rows for the test snapshot_date before/after each test."""
    test_date = date(2099, 1, 1)
    with psycopg.connect(DATABASE_URL) as conn, conn.cursor() as cur:
        cur.execute("DELETE FROM licensees_snapshots WHERE snapshot_date = %s", (test_date,))
        conn.commit()
    yield test_date
    with psycopg.connect(DATABASE_URL) as conn, conn.cursor() as cur:
        cur.execute("DELETE FROM licensees_snapshots WHERE snapshot_date = %s", (test_date,))
        conn.commit()


@skip_if_no_db
def test_load_inserts_all_rows(fixtures_dir, schema_applied, cleanup_snapshot):
    test_date = cleanup_snapshot
    csv_bytes = (fixtures_dir / "sample.csv").read_bytes()
    prov = Provenance(
        source_url="https://example.test/source.csv",
        source_retrieved_at="2099-01-01T00:00:00+00:00",
        source_checksum="x" * 64,
        extraction_version="0.1.0",
    )
    rows = transform(csv_bytes, snapshot_date=test_date, provenance=prov)

    count = load(rows, DATABASE_URL)
    assert count == 5

    with psycopg.connect(DATABASE_URL) as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT COUNT(*) FROM licensees_snapshots WHERE snapshot_date = %s",
            (test_date,),
        )
        assert cur.fetchone()[0] == 5


@skip_if_no_db
def test_load_is_idempotent(fixtures_dir, schema_applied, cleanup_snapshot):
    test_date = cleanup_snapshot
    csv_bytes = (fixtures_dir / "sample.csv").read_bytes()
    prov = Provenance(
        source_url="https://example.test/source.csv",
        source_retrieved_at="2099-01-01T00:00:00+00:00",
        source_checksum="x" * 64,
        extraction_version="0.1.0",
    )
    rows = transform(csv_bytes, snapshot_date=test_date, provenance=prov)

    load(rows, DATABASE_URL)
    load(rows, DATABASE_URL)  # second load must not duplicate

    with psycopg.connect(DATABASE_URL) as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT COUNT(*) FROM licensees_snapshots WHERE snapshot_date = %s",
            (test_date,),
        )
        assert cur.fetchone()[0] == 5


@skip_if_no_db
def test_load_preserves_endorsements_array(fixtures_dir, schema_applied, cleanup_snapshot):
    test_date = cleanup_snapshot
    csv_bytes = (fixtures_dir / "sample.csv").read_bytes()
    prov = Provenance(
        source_url="https://example.test/source.csv",
        source_retrieved_at="2099-01-01T00:00:00+00:00",
        source_checksum="x" * 64,
        extraction_version="0.1.0",
    )
    rows = transform(csv_bytes, snapshot_date=test_date, provenance=prov)
    load(rows, DATABASE_URL)

    with psycopg.connect(DATABASE_URL) as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT endorsements FROM licensees_snapshots "
            "WHERE snapshot_date = %s AND license_number = %s",
            (test_date, "050-10157025C26"),
        )
        endorsements = cur.fetchone()[0]
        assert endorsements == ["Marijuana Home Delivery", "Medical Marijuana Retailer"]
