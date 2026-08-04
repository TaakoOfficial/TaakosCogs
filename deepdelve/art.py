"""Bestiary artwork lookup helpers."""

from __future__ import annotations

import re
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Mapping

BESTIARY_ASSET_DIR = Path(__file__).resolve().parent / "assets" / "bestiary"


def bestiary_slug(name: str) -> str:
    """Return the stable filename slug used by bestiary portraits."""
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


def combat_art_path(enemy: Mapping[str, Any]) -> Path | None:
    """Resolve an encounter to its portrait, including modified variants."""
    name = str(enemy.get("art_name") or enemy.get("base_name") or enemy.get("name") or "")
    if not name:
        return None
    path = BESTIARY_ASSET_DIR / f"{bestiary_slug(name)}.webp"
    return path if path.is_file() else None
