"""
Transform OLCC CSV bytes into rows matching the licensees_snapshots schema.

Source quirks handled:
- Blank cells appear as a single space " " in the CSV, not as empty string.
- Endorsements are a comma-separated list inside one quoted CSV field.
- "Exempt from Public Disclosure" is meaningful for producer/processor/
  wholesaler addresses and is preserved verbatim, not nulled.
- Dates are M/D/YYYY (no leading zeros).
"""

from __future__ import annotations

import csv
import io
import logging
from dataclasses import dataclass
from datetime import date, datetime

from etl.vocab import normalize

LOG = logging.getLogger(__name__)

REQUIRED_COLUMNS = (
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
class Provenance:
    source_url: str
    source_retrieved_at: str
    source_checksum: str
    extraction_version: str


def _optional(value: str | None) -> str | None:
    if value is None:
        return None
    stripped = value.strip()
    return stripped or None


def _required(value: str | None, field: str) -> str:
    cleaned = _optional(value)
    if cleaned is None:
        raise ValueError(f"required field {field!r} is empty")
    return cleaned


def _endorsements(value: str | None) -> list[str]:
    cleaned = _optional(value)
    if cleaned is None:
        return []
    return [piece.strip() for piece in cleaned.split(",") if piece.strip()]


def _expiration_date(value: str | None) -> date | None:
    cleaned = _optional(value)
    if cleaned is None:
        return None
    try:
        return datetime.strptime(cleaned, "%m/%d/%Y").date()
    except ValueError:
        # OLCC occasionally uses sentinels like "*" for irregular records.
        # Don't fail; preserve the original in raw_row and null the date.
        LOG.warning("unparseable expiration date %r; storing NULL", cleaned)
        return None


def transform(
    csv_bytes: bytes,
    *,
    snapshot_date: date,
    provenance: Provenance,
) -> list[dict]:
    text = csv_bytes.decode("utf-8-sig")
    reader = csv.DictReader(io.StringIO(text))

    if reader.fieldnames is None:
        raise ValueError("CSV has no header row")
    missing = [c for c in REQUIRED_COLUMNS if c not in reader.fieldnames]
    if missing:
        raise ValueError(f"required columns missing from CSV: {missing}")

    rows: list[dict] = []
    for src in reader:
        rows.append(
            {
                "snapshot_date": snapshot_date,
                "license_number": _required(src.get("License Number"), "License Number"),
                "license_type": normalize(
                    "license_type",
                    _required(src.get("License Type"), "License Type"),
                ),
                "status": normalize(
                    "status",
                    _required(src.get("Status"), "Status"),
                ),
                "legal_name": _optional(src.get("Business Licenses")),
                "trade_name": _optional(src.get("Business Name")),
                "endorsements": _endorsements(src.get("Endorsement")),
                "county": _optional(src.get("County")),
                "physical_address": _optional(src.get("PhysicalAddress")),
                "tier": _optional(src.get("Tier")),
                "canopy_type": _optional(src.get("Canopy Type")),
                "sos_registration": _optional(src.get("SOS Registration Number")),
                "expiration_date": _expiration_date(src.get("Expiration Date")),
                "raw_row": dict(src),
                "source_url": provenance.source_url,
                "source_retrieved_at": provenance.source_retrieved_at,
                "source_checksum": provenance.source_checksum,
                "extraction_version": provenance.extraction_version,
            }
        )
    return rows
