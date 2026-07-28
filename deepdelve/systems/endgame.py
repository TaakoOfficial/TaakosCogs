"""Season, daily dungeon, and rift helpers."""

from __future__ import annotations

import hashlib
from datetime import date, datetime, timezone
from typing import Any

from deepdelve.advanced_content import SEASON_NAMES


def current_season(now: datetime | None = None) -> dict[str, Any]:
    """Return a deterministic three-month season descriptor."""
    now = now or datetime.now(timezone.utc)
    quarter = (now.month - 1) // 3
    season_id = f"{now.year}-q{quarter + 1}"
    return {
        "id": season_id,
        "name": SEASON_NAMES[(now.year * 4 + quarter) % len(SEASON_NAMES)],
        "year": now.year,
        "quarter": quarter + 1,
    }


def daily_dungeon(day: date | None = None) -> dict[str, Any]:
    """Create a server-independent daily challenge from the UTC date."""
    day = day or datetime.now(timezone.utc).date()
    digest = hashlib.sha256(day.isoformat().encode()).digest()
    modifiers = (
        ("Blood Moon", "Enemies deal 25% more damage.", 1.35),
        ("Fool's Gold", "Currency is doubled, but fleeing is harder.", 1.5),
        ("Glass Labyrinth", "Everyone deals 40% more damage.", 1.4),
        ("Starvation", "Potions cannot be used.", 1.55),
        ("Royal Hunt", "Every enemy is elite.", 1.65),
    )
    name, description, multiplier = modifiers[digest[0] % len(modifiers)]
    return {
        "date": day.isoformat(),
        "name": name,
        "description": description,
        "reward_multiplier": multiplier,
        "floor": 5 + digest[1] % 21,
        "seed": int.from_bytes(digest[:8], "big"),
    }
