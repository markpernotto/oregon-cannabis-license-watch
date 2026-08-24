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
from itertools import pairwise
from pathlib import Path

import psycopg
from psycopg.rows import dict_row

from etl import __version__
from etl.extract import SOURCE_LANDING_URL

DEFAULT_OUT_DIR = Path("public")
# 180-day window so the UI can offer 30/90/180 client-side without refetching.
# JSON size at full saturation is roughly 320 KB, comfortably under any
# bandwidth threshold worth caring about.
DEFAULT_WINDOW_DAYS = 180

PROJECT_URL = "https://github.com/markpernotto/oregon-cannabis-license-watch"
SOURCE_NAME = "OLCC Cannabis Business Licenses & Endorsements (Oregon Open Data Portal)"
SOURCE_URL = SOURCE_LANDING_URL

_SNAPSHOT_DATES_QUERY = """
SELECT DISTINCT snapshot_date FROM licensees_snapshots ORDER BY snapshot_date
"""

_QUERY = """
SELECT lc.change_id, lc.observed_at, lc.license_number, lc.change_type,
       lc.field_name, lc.prev_value, lc.new_value, lc.diff_summary,
       lc.source_snapshot_date,
       ls.legal_name, ls.trade_name, ls.license_type, ls.county
FROM license_changes lc
LEFT JOIN LATERAL (
    SELECT legal_name, trade_name, license_type, county
    FROM licensees_snapshots
    WHERE license_number = lc.license_number
    ORDER BY snapshot_date DESC
    LIMIT 1
) ls ON TRUE
WHERE lc.observed_at >= %s
ORDER BY lc.observed_at DESC, lc.change_id DESC
"""


def _coverage(dates: list[date]) -> dict:
    """Describe what the series actually covers.

    `first_snapshot_date` is the true start of history. `consecutive_since`
    is the start of the current unbroken daily run — those two diverge once
    there is a gap, and conflating them would have let the 2026-08 source
    migration erase four months of real history from the site's own
    description of itself.
    """
    if not dates:
        return {
            "first_snapshot_date": None,
            "latest_snapshot_date": None,
            "consecutive_since": None,
            "coverage_gaps": [],
        }

    gaps = []
    for prev, nxt in pairwise(dates):
        missing = (nxt - prev).days - 1
        if missing > 0:
            gaps.append(
                {
                    "start": (prev + timedelta(days=1)).isoformat(),
                    "end": (nxt - timedelta(days=1)).isoformat(),
                    "days": missing,
                }
            )

    consecutive_since = dates[0]
    for prev, nxt in reversed(list(pairwise(dates))):
        if (nxt - prev).days != 1:
            consecutive_since = nxt
            break

    return {
        "first_snapshot_date": dates[0].isoformat(),
        "latest_snapshot_date": dates[-1].isoformat(),
        "consecutive_since": consecutive_since.isoformat(),
        "coverage_gaps": gaps,
    }


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
        "license_type": row.get("license_type"),
        "legal_name": row.get("legal_name"),
        "trade_name": row.get("trade_name"),
        "county": row.get("county"),
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
        "Daily change feed derived from OLCC cannabis license data "
        "published on the Oregon Open Data Portal."
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
        cur.execute(_SNAPSHOT_DATES_QUERY)
        coverage = _coverage([r["snapshot_date"] for r in cur.fetchall()])

    changes = [_to_change_dict(r) for r in rows]

    payload = {
        "generated_at": generated_at.isoformat(),
        "source": SOURCE_NAME,
        "source_url": SOURCE_URL,
        "window_days": window_days,
        "total_changes": len(changes),
        "freshness_sla_hours": 26,
        **coverage,
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
