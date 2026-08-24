"""Tests for etl.transform, across both supported source formats."""

from datetime import date

import pytest

from etl.transform import LEGACY_COLUMNS, SOCRATA_COLUMNS, Provenance, transform

SNAPSHOT = date(2026, 4, 27)


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


@pytest.fixture
def legacy_bytes(fixtures_dir) -> bytes:
    return (fixtures_dir / "sample_legacy.csv").read_bytes()


@pytest.fixture
def terms_bytes(fixtures_dir) -> bytes:
    return (fixtures_dir / "sample_socrata_terms.csv").read_bytes()


def _by_license(rows: list[dict]) -> dict[str, dict]:
    return {r["license_number"]: r for r in rows}


# --- current (Socrata) format ------------------------------------------


def test_socrata_columns_match_fixture(fixture_bytes):
    header = fixture_bytes.split(b"\n", 1)[0].decode()
    for col in SOCRATA_COLUMNS:
        assert col in header, f"missing {col!r} in fixture header"


def test_transform_row_count(fixture_bytes, provenance):
    rows = transform(fixture_bytes, snapshot_date=SNAPSHOT, provenance=provenance)
    assert len(rows) == 5


def test_transform_carries_provenance(fixture_bytes, provenance):
    rows = transform(fixture_bytes, snapshot_date=SNAPSHOT, provenance=provenance)
    for row in rows:
        assert row["source_url"] == provenance.source_url
        assert row["source_retrieved_at"] == provenance.source_retrieved_at
        assert row["source_checksum"] == provenance.source_checksum
        assert row["extraction_version"] == provenance.extraction_version


def test_transform_blank_field_becomes_none(fixture_bytes, provenance):
    producer = _by_license(
        transform(fixture_bytes, snapshot_date=SNAPSHOT, provenance=provenance)
    )["020-1001842C5BE"]
    assert producer["endorsements"] == []
    assert producer["sos_registration"] is None
    assert producer["inactive_date"] is None
    assert producer["canopy_type"] == "Indoor"


def test_transform_endorsements_parsed_to_list(fixture_bytes, provenance):
    retailer = _by_license(
        transform(fixture_bytes, snapshot_date=SNAPSHOT, provenance=provenance)
    )["050-10157025C26"]
    assert retailer["endorsements"] == ["Marijuana Home Delivery", "Medical Marijuana Retailer"]


def test_transform_preserves_exempt_address_verbatim(fixture_bytes, provenance):
    producer = _by_license(
        transform(fixture_bytes, snapshot_date=SNAPSHOT, provenance=provenance)
    )["020-1001842C5BE"]
    assert producer["physical_address"] == "Exempt from Public Disclosure"


def test_transform_quoted_legal_name_with_comma(fixture_bytes, provenance):
    rows = transform(fixture_bytes, snapshot_date=SNAPSHOT, provenance=provenance)
    bizs = {r["legal_name"] for r in rows}
    assert "3 D BLUEBERRY FARMS, INC." in bizs
    assert "3B ANALYTICAL, LLC" in bizs


def test_transform_iso_dates_parsed(fixture_bytes, provenance):
    producer = _by_license(
        transform(fixture_bytes, snapshot_date=SNAPSHOT, provenance=provenance)
    )["020-1001842C5BE"]
    assert producer["effective_date"] == date(2025, 12, 23)
    assert producer["expiration_date"] == date(2026, 12, 22)


def test_transform_license_type_normalized(fixture_bytes, provenance):
    rows = transform(fixture_bytes, snapshot_date=SNAPSHOT, provenance=provenance)
    types = {r["license_type"] for r in rows}
    assert "RECREATIONAL_PRODUCER" in types
    assert "RECREATIONAL_RETAILER" in types
    assert "LABORATORY" in types


def test_transform_raw_row_preserved(fixture_bytes, provenance):
    raw = _by_license(
        transform(fixture_bytes, snapshot_date=SNAPSHOT, provenance=provenance)
    )["020-1001842C5BE"]["raw_row"]
    assert raw["license_type"] == "RECREATIONAL PRODUCER"  # source casing preserved
    assert raw["license_number"] == "020-1001842C5BE"


def test_transform_missing_required_columns_raises(provenance):
    bad = b"license_number,license_type\n020-X,RECREATIONAL PRODUCER\n"
    with pytest.raises(ValueError, match="required columns missing"):
        transform(bad, snapshot_date=SNAPSHOT, provenance=provenance)


# --- status derivation --------------------------------------------------


def test_status_active_when_not_expired(fixture_bytes, provenance):
    rows = transform(fixture_bytes, snapshot_date=SNAPSHOT, provenance=provenance)
    assert all(r["status"] == "ACTIVE" for r in rows)


def test_status_expired_when_flagged_without_inactive_date(terms_bytes, provenance):
    row = _by_license(
        transform(terms_bytes, snapshot_date=SNAPSHOT, provenance=provenance)
    )["050-LAPSED"]
    assert row["status"] == "EXPIRED"
    assert row["inactive_date"] is None


def test_status_inactive_when_inactive_date_present(terms_bytes, provenance):
    row = _by_license(
        transform(terms_bytes, snapshot_date=SNAPSHOT, provenance=provenance)
    )["050-ENDED"]
    assert row["status"] == "INACTIVE"
    assert row["inactive_date"] == date(2024, 9, 15)


def test_sampling_laboratory_is_in_vocabulary(terms_bytes, provenance):
    row = _by_license(
        transform(terms_bytes, snapshot_date=SNAPSHOT, provenance=provenance)
    )["010-SAMPLER"]
    assert row["license_type"] == "SAMPLING_LABORATORY"


# --- license-term collapsing -------------------------------------------


def test_multiple_terms_collapse_to_one_row_per_license(terms_bytes, provenance):
    rows = transform(terms_bytes, snapshot_date=SNAPSHOT, provenance=provenance)
    numbers = [r["license_number"] for r in rows]
    assert len(numbers) == len(set(numbers)) == 5  # 6 source rows, 5 licenses


def test_collapse_keeps_the_term_in_effect(terms_bytes, provenance):
    """On 2026-04-27 the 2025-05-02..2026-05-01 term is live, not the renewal."""
    row = _by_license(
        transform(terms_bytes, snapshot_date=SNAPSHOT, provenance=provenance)
    )["020-RENEWED"]
    assert row["effective_date"] == date(2025, 5, 2)
    assert row["expiration_date"] == date(2026, 5, 1)
    assert row["tier"] == "Tier I"


def test_collapse_follows_the_renewal_once_it_starts(terms_bytes, provenance):
    """Same license, snapshot taken after the renewal takes effect."""
    row = _by_license(
        transform(terms_bytes, snapshot_date=date(2026, 6, 1), provenance=provenance)
    )["020-RENEWED"]
    assert row["effective_date"] == date(2026, 5, 2)
    assert row["tier"] == "Tier II"


def test_collapse_falls_back_when_no_term_is_live(terms_bytes, provenance):
    """A license whose only term starts in the future still yields a row."""
    row = _by_license(
        transform(terms_bytes, snapshot_date=SNAPSHOT, provenance=provenance)
    )["020-RENEWALONLY"]
    assert row["effective_date"] == date(2027, 1, 1)


# --- retired (Tableau) format, still replayed by etl.backfill ----------


def test_legacy_columns_match_legacy_fixture(legacy_bytes):
    header = legacy_bytes.split(b"\n", 1)[0].decode()
    for col in LEGACY_COLUMNS:
        assert col in header, f"missing {col!r} in legacy fixture header"


def test_legacy_format_still_transforms(legacy_bytes, provenance):
    rows = transform(legacy_bytes, snapshot_date=SNAPSHOT, provenance=provenance)
    assert len(rows) == 5
    assert all(r["status"] == "ACTIVE" for r in rows)


def test_legacy_slash_dates_parsed(legacy_bytes, provenance):
    row = _by_license(
        transform(legacy_bytes, snapshot_date=SNAPSHOT, provenance=provenance)
    )["020-1001842C5BE"]
    assert row["expiration_date"] == date(2026, 12, 22)
    # The Tableau view published neither term boundary.
    assert row["effective_date"] is None
    assert row["inactive_date"] is None


def test_legacy_single_space_blanks_become_none(legacy_bytes, provenance):
    row = _by_license(
        transform(legacy_bytes, snapshot_date=SNAPSHOT, provenance=provenance)
    )["020-1001842C5BE"]
    assert row["sos_registration"] is None
    assert row["endorsements"] == []


def test_malformed_date_becomes_none(provenance):
    """Both sources occasionally carry sentinels like '*' for dates."""
    header = ",".join(SOCRATA_COLUMNS)
    row = "020-XYZ,Quirky,QUIRKY CO,RECREATIONAL PRODUCER,No,*,*,,,,Lane,Tier I,,"
    rows = transform(
        f"{header}\n{row}\n".encode(),
        snapshot_date=SNAPSHOT,
        provenance=provenance,
    )
    assert rows[0]["expiration_date"] is None
    assert rows[0]["effective_date"] is None
    assert rows[0]["raw_row"]["expiration_date"] == "*"


# --- primary-key invariant ---------------------------------------------


def _socrata_csv(rows: list[dict]) -> bytes:
    import csv
    import io

    base = dict.fromkeys(SOCRATA_COLUMNS, "")
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=SOCRATA_COLUMNS)
    writer.writeheader()
    for row in rows:
        writer.writerow({**base, "license_type": "RECREATIONAL PRODUCER",
                         "license_expired": "No", **row})
    return buf.getvalue().encode()


def test_collapse_output_is_unique_per_license(terms_bytes, provenance):
    rows = transform(terms_bytes, snapshot_date=SNAPSHOT, provenance=provenance)
    numbers = [r["license_number"] for r in rows]
    assert len(numbers) == len(set(numbers))


def test_duplicate_license_numbers_raise_before_the_database(provenance, monkeypatch):
    """The PK guard must fire even if term selection is later broken."""
    import etl.transform as t

    monkeypatch.setattr(t, "_select_term", lambda terms, number, as_of: terms[0])
    monkeypatch.setattr(
        t, "_row_socrata",
        lambda src, *, snapshot_date, provenance: {"license_number": "020-DUP"},
    )
    csv_bytes = _socrata_csv([
        {"license_number": "020-DUP", "effective_date": "2026-01-01"},
        {"license_number": "020-OTHER", "effective_date": "2026-01-01"},
    ])
    with pytest.raises(ValueError, match="duplicate license number"):
        t.transform(csv_bytes, snapshot_date=SNAPSHOT, provenance=provenance)


def test_ambiguous_overlapping_terms_are_warned_about(provenance, caplog):
    """Two live terms make the pick arbitrary; that must not pass silently."""
    csv_bytes = _socrata_csv([
        {"license_number": "020-OVERLAP", "effective_date": "2026-01-01",
         "expiration_date": "2026-12-31"},
        {"license_number": "020-OVERLAP", "effective_date": "2026-03-01",
         "expiration_date": "2027-02-28"},
    ])
    with caplog.at_level("WARNING"):
        rows = transform(csv_bytes, snapshot_date=SNAPSHOT, provenance=provenance)

    assert len(rows) == 1
    assert "020-OVERLAP" in caplog.text
    assert "terms in effect" in caplog.text
    # Still deterministic: the most recently effective term wins.
    assert rows[0]["effective_date"] == date(2026, 3, 1)
