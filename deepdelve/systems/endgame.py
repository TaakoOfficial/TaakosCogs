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


def scaled_daily_floor(challenge_floor: int, deepest_floor: int) -> int:
    """Keep the shared daily dangerous without placing players in impossible brackets."""
    return max(5, min(int(challenge_floor), max(5, int(deepest_floor) + 2)))


def restore_challenge_origin(profile: dict[str, Any]) -> bool:
    """Leave a rift cleanly and restore the adventure state it temporarily replaced."""
    rift = profile.get("rift_state") or {}
    if not rift:
        return False
    profile["floor"] = max(1, int(rift.get("original_floor", profile.get("floor", 1))))
    profile["rooms_cleared"] = max(0, int(rift.get("original_rooms", 0)))
    profile["rift_state"] = {}
    return True
