"""Tests for etl.extract. Real-network tests are marked and skipped by default."""

import pytest

from etl.extract import (
    EXPECTED_COLUMNS,
    PAGE_LIMIT,
    SOURCE_CSV_URL,
    SOURCE_LANDING_URL,
    extract,
)


def test_expected_columns_is_non_empty_tuple():
    assert isinstance(EXPECTED_COLUMNS, tuple)
    assert len(EXPECTED_COLUMNS) >= 10


def test_expected_columns_are_socrata_field_names():
    """Socrata serves snake_case API names, not the portal's display labels."""
    assert all(c == c.lower() and " " not in c for c in EXPECTED_COLUMNS)


def test_source_urls_point_at_the_open_data_portal():
    assert SOURCE_CSV_URL.startswith("https://data.oregon.gov/resource/")
    assert SOURCE_CSV_URL.endswith(".csv")
    assert SOURCE_LANDING_URL.startswith("https://data.oregon.gov/d/")


def test_page_limit_leaves_headroom_over_the_dataset():
    """~3.8k rows as of 2026-08-24; the guard trips only on real truncation."""
    assert PAGE_LIMIT >= 50_000


@pytest.mark.network
def test_extract_live(tmp_path):
    """Hits the real Socrata endpoint. Run with: pytest -m network"""
    result = extract(snapshot_dir=tmp_path)
    assert result.path.exists()
    assert result.row_count > 1_000
    assert result.source_checksum


@pytest.mark.network
def test_extract_live_is_byte_stable(tmp_path):
    """$order=:id must make repeated pulls identical, or every run looks like a change."""
    first = extract(snapshot_dir=tmp_path / "a")
    second = extract(snapshot_dir=tmp_path / "b")
    assert first.source_checksum == second.source_checksum
