"""Tests for etl.extract. Real-network tests are marked and skipped by default."""

import pytest

from etl.extract import EXPECTED_COLUMNS, extract


def test_expected_columns_is_non_empty_tuple():
    assert isinstance(EXPECTED_COLUMNS, tuple)
    assert len(EXPECTED_COLUMNS) >= 10


@pytest.mark.network
def test_extract_live(tmp_path):
    """Hits the real OLCC endpoint. Run with: pytest -m network"""
    result = extract(snapshot_dir=tmp_path)
    assert result.path.exists()
    assert result.row_count > 1_000
    assert result.source_checksum
