"""Party, player-guild, auction, and arena helpers."""

from __future__ import annotations

import random
import string
from typing import Any


def short_code(prefix: str, existing: dict[str, Any]) -> str:
    """Generate a compact human-readable unique record ID."""
    alphabet = string.ascii_uppercase + string.digits
    for _ in range(100):
        code = prefix + "".join(random.choice(alphabet) for _ in range(5))
        if code not in existing:
            return code
    return prefix + str(random.randrange(100000, 999999))


def party_bonus(member_count: int) -> dict[str, int]:
    """Return modest cooperative bonuses without invalidating solo play."""
    count = max(1, min(4, member_count))
    return {
        "hp": (count - 1) * 5,
        "attack": count - 1,
        "luck": (count - 1) * 2,
    }


def guild_perks(guild_record: dict[str, Any]) -> list[str]:
    """Return unlocked player-guild perks."""
    level = int(guild_record.get("level", 1))
    perks = ["Shared identity and guild leaderboard"]
    if level >= 2:
        perks.append("+2% expedition currency")
    if level >= 3:
        perks.append("+2 party Luck")
    if level >= 4:
        perks.append("One additional daily turn")
    if level >= 5:
        perks.append("+5% world-boss damage")
    return perks


def arena_power(profile: dict[str, Any], stats: dict[str, int]) -> int:
    """Estimate matchmaking strength from progression and equipment."""
    return (
        int(profile.get("level", 1)) * 12
        + stats["attack"] * 3
        + stats["defense"] * 2
        + stats["max_hp"] // 5
        + stats["luck"]
        + int(profile.get("prestige", 0)) * 25
    )
