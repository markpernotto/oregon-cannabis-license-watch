"""Tests for etl.transform."""

from datetime import date

import pytest

from etl.transform import REQUIRED_COLUMNS, Provenance, transform


@pytest.fixture
def provenance() -> Provenance:
    return Provenance(
        source_url="https://example.test/source.csv",
        source_retrieved_at="2026-04-27T12:00:00+00:00",
        source_checksum="a" * 64,
        extraction_version="0.1.0",
    )


@pytest.fixture
def fixture_bytes(fixtures_dir) -> bytes:
    return (fixtures_dir / "sample.csv").read_bytes()


def test_required_columns_match_source(fixture_bytes):
    header = fixture_bytes.split(b"\n", 1)[0].decode()
    for col in REQUIRED_COLUMNS:
        assert col in header, f"missing {col!r} in fixture header"


def test_transform_row_count(fixture_bytes, provenance):
    rows = transform(fixture_bytes, snapshot_date=date(2026, 4, 27), provenance=provenance)
    assert len(rows) == 5


def test_transform_carries_provenance(fixture_bytes, provenance):
    rows = transform(fixture_bytes, snapshot_date=date(2026, 4, 27), provenance=provenance)
    for row in rows:
        assert row["source_url"] == provenance.source_url
        assert row["source_retrieved_at"] == provenance.source_retrieved_at
        assert row["source_checksum"] == provenance.source_checksum
        assert row["extraction_version"] == provenance.extraction_version


def test_transform_blank_field_becomes_none(fixture_bytes, provenance):
    """Source represents missing values as a single-space string ' '."""
    rows = transform(fixture_bytes, snapshot_date=date(2026, 4, 27), provenance=provenance)
    # First row is a producer with no endorsement; sos_registration is blank.
    producer = rows[0]
    assert producer["endorsements"] == []
    assert producer["sos_registration"] is None
    # Producers don't have a canopy_type=='Mixed' row in fixture; the producer row has Indoor.
    assert producer["canopy_type"] == "Indoor"


def test_transform_endorsements_parsed_to_list(fixture_bytes, provenance):
    rows = transform(fixture_bytes, snapshot_date=date(2026, 4, 27), provenance=provenance)
    retailer = next(r for r in rows if r["license_number"] == "050-10157025C26")
    assert retailer["endorsements"] == ["Marijuana Home Delivery", "Medical Marijuana Retailer"]


def test_transform_preserves_exempt_address_verbatim(fixture_bytes, provenance):
    rows = transform(fixture_bytes, snapshot_date=date(2026, 4, 27), provenance=provenance)
    producer = rows[0]
    assert producer["physical_address"] == "Exempt from Public Disclosure"


def test_transform_quoted_legal_name_with_comma(fixture_bytes, provenance):
    rows = transform(fixture_bytes, snapshot_date=date(2026, 4, 27), provenance=provenance)
    bizs = {r["legal_name"] for r in rows}
    assert "3 D BLUEBERRY FARMS, INC." in bizs
    assert "3B ANALYTICAL, LLC" in bizs


def test_transform_expiration_date_parsed(fixture_bytes, provenance):
    rows = transform(fixture_bytes, snapshot_date=date(2026, 4, 27), provenance=provenance)
    producer = rows[0]
    assert producer["expiration_date"] == date(2026, 12, 22)


def test_transform_license_type_normalized(fixture_bytes, provenance):
    rows = transform(fixture_bytes, snapshot_date=date(2026, 4, 27), provenance=provenance)
    types = {r["license_type"] for r in rows}
    assert "RECREATIONAL_PRODUCER" in types
    assert "RECREATIONAL_RETAILER" in types
    assert "LABORATORY" in types


def test_transform_status_normalized(fixture_bytes, provenance):
    rows = transform(fixture_bytes, snapshot_date=date(2026, 4, 27), provenance=provenance)
    assert all(r["status"] == "ACTIVE" for r in rows)


def test_transform_raw_row_preserved(fixture_bytes, provenance):
    rows = transform(fixture_bytes, snapshot_date=date(2026, 4, 27), provenance=provenance)
    raw = rows[0]["raw_row"]
    assert raw["License Type"] == "RECREATIONAL PRODUCER"  # source casing preserved
    assert raw["License Number"] == "020-1001842C5BE"


def test_transform_missing_required_columns_raises(provenance):
    bad = b"License Number,License Type\n020-X,RECREATIONAL PRODUCER\n"
    with pytest.raises(ValueError, match="required columns missing"):
        transform(bad, snapshot_date=date(2026, 4, 27), provenance=provenance)


def test_transform_malformed_expiration_date_becomes_none(provenance):
    """Real OLCC data occasionally contains sentinels like '*' for dates."""
    headers = (
        "Business Licenses,Business Name,Canopy Type,County,Endorsement,"
        "License Number,License Type,PhysicalAddress,SOS Registration Number,"
        "Status,Tier,Expiration Date"
    )
    bad_row = "QUIRKY CO, , ,Lane, ,020-XYZ,RECREATIONAL PRODUCER, , ,ACTIVE,Tier I,*"
    rows = transform(
        f"{headers}\n{bad_row}\n".encode(),
        snapshot_date=date(2026, 4, 27),
        provenance=provenance,
    )
    assert rows[0]["expiration_date"] is None
    assert rows[0]["raw_row"]["Expiration Date"] == "*"
