"""
Publish: regenerate public/rss.xml and public/changes.json from license_changes.

Day-6 work — stubbed for now.
"""

from __future__ import annotations

from pathlib import Path


def publish(database_url: str, out_dir: Path = Path("public")) -> None:
    """Regenerate RSS + JSON artifacts.

    Not implemented yet.
    """
    raise NotImplementedError("publish: implement in Day 6 of Phase 1")
