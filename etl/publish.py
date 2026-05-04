"""
Publish: regenerate public/changes.json and public/rss.xml from license_changes.

Both artifacts are static files committed to the repo by the nightly Action.
The React UI reads changes.json directly; the RSS feed is consumable by any
reader. No API server required for Phase 1.
"""

from __future__ import annotations

import json
import os
import sys
import xml.etree.ElementTree as ET
from datetime import UTC, date, datetime, timedelta
from email.utils import format_datetime
from pathlib import Path

import psycopg
from psycopg.rows import dict_row

from etl import __version__

DEFAULT_OUT_DIR = Path("public")
DEFAULT_WINDOW_DAYS = 30

PROJECT_URL = "https://github.com/markpernotto/oregon-cannabis-license-watch"
SOURCE_NAME = "OLCC Cannabis Licensee Public Report"
SOURCE_URL = (
    "https://data.olcc.state.or.us/t/OLCCPublic/views/"
    "CannabisBusinessLicensesEndorsements/CannabisLicensesEndorsements"
)

_QUERY = """
SELECT change_id, observed_at, license_number, change_type, field_name,
       prev_value, new_value, diff_summary, source_snapshot_date
FROM license_changes
WHERE observed_at >= %s
ORDER BY observed_at DESC, change_id DESC
"""


def _json_default(value):
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    raise TypeError(f"not JSON-serializable: {type(value).__name__}")


def _to_change_dict(row: dict) -> dict:
    return {
        "change_id": row["change_id"],
        "observed_at": row["observed_at"].isoformat(),
        "snapshot_date": row["source_snapshot_date"].isoformat(),
        "license_number": row["license_number"],
        "change_type": row["change_type"],
        "field_name": row["field_name"],
        "prev_value": row["prev_value"],
        "new_value": row["new_value"],
        "summary": row["diff_summary"],
    }


def _build_rss(changes: list[dict], generated_at: datetime) -> bytes:
    rss = ET.Element(
        "rss",
        attrib={"version": "2.0", "xmlns:atom": "http://www.w3.org/2005/Atom"},
    )
    channel = ET.SubElement(rss, "channel")
    ET.SubElement(channel, "title").text = "Oregon Cannabis License Changes"
    ET.SubElement(channel, "link").text = PROJECT_URL
    ET.SubElement(channel, "description").text = (
        "Daily change feed derived from the OLCC Cannabis Licensee public report."
    )
    ET.SubElement(channel, "language").text = "en-us"
    ET.SubElement(channel, "pubDate").text = format_datetime(generated_at)
    ET.SubElement(channel, "generator").text = f"oregon-cannabis-license-watch {__version__}"

    for c in changes:
        item = ET.SubElement(channel, "item")
        ET.SubElement(item, "title").text = c["summary"]
        ET.SubElement(item, "link").text = PROJECT_URL
        guid = ET.SubElement(item, "guid", attrib={"isPermaLink": "false"})
        guid.text = f"change-{c['change_id']}"
        observed = datetime.fromisoformat(c["observed_at"])
        ET.SubElement(item, "pubDate").text = format_datetime(observed)
        ET.SubElement(item, "description").text = c["summary"]

    return ET.tostring(rss, encoding="utf-8", xml_declaration=True)


def publish(
    database_url: str,
    out_dir: Path = DEFAULT_OUT_DIR,
    window_days: int = DEFAULT_WINDOW_DAYS,
    *,
    cutoff: datetime | None = None,
) -> dict:
    generated_at = datetime.now(UTC)
    if cutoff is None:
        cutoff = generated_at - timedelta(days=window_days)

    with psycopg.connect(database_url) as conn, conn.cursor(row_factory=dict_row) as cur:
        cur.execute(_QUERY, (cutoff,))
        rows = cur.fetchall()

    changes = [_to_change_dict(r) for r in rows]

    payload = {
        "generated_at": generated_at.isoformat(),
        "source": SOURCE_NAME,
        "source_url": SOURCE_URL,
        "window_days": window_days,
        "total_changes": len(changes),
        "freshness_sla_hours": 26,
        "changes": changes,
    }

    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / "changes.json"
    rss_path = out_dir / "rss.xml"
    json_path.write_text(json.dumps(payload, indent=2, default=_json_default) + "\n")
    rss_path.write_bytes(_build_rss(changes, generated_at))

    return {
        "json_path": json_path,
        "rss_path": rss_path,
        "total_changes": len(changes),
        "generated_at": generated_at.isoformat(),
    }


def main(argv: list[str] | None = None) -> int:
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        print("error: DATABASE_URL is not set", file=sys.stderr)
        return 2
    result = publish(database_url)
    print(f"wrote {result['json_path']} ({result['total_changes']} changes)")
    print(f"wrote {result['rss_path']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
