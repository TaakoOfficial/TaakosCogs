"""Profession progression and gathering helpers."""

from __future__ import annotations

import random
from typing import Any

from deepdelve.content import MATERIALS, region_for_floor
from deepdelve.expansion_content import PROFESSIONS

RANKS = ("Apprentice", "Journeyman", "Expert", "Master", "Grandmaster")


def profession_level(profile: dict[str, Any]) -> int:
    """Return the current profession level."""
    return int(profile.get("profession", {}).get("level", 1))


def profession_rank(level: int) -> str:
    """Return the rank title for a profession level."""
    return RANKS[min(len(RANKS) - 1, max(0, (level - 1) // 5))]


def grant_profession_xp(profile: dict[str, Any], amount: int) -> list[str]:
    """Award profession XP and handle level-ups."""
    profession = profile.setdefault("profession", {"key": "", "level": 1, "xp": 0})
    if profession.get("key") not in PROFESSIONS:
        return []
    profession["xp"] = int(profession.get("xp", 0)) + max(0, amount)
    messages = []
    while profession["level"] < 25:
        needed = 50 + int(profession["level"]) * 25
        if profession["xp"] < needed:
            break
        profession["xp"] -= needed
        profession["level"] += 1
        rank = profession_rank(profession["level"])
        messages.append(
            f"{PROFESSIONS[profession['key']]['emoji']} Profession advanced to **level {profession['level']} — {rank}**!",
        )
    return messages


def gather(profile: dict[str, Any], rng: random.Random = random) -> dict[str, Any]:
    """Gather region materials with profession-specific benefits."""
    region = region_for_floor(int(profile.get("floor", 1)))
    key = region["material"]
    level = profession_level(profile)
    amount = 1 + level // 8
    if profile.get("profession", {}).get("key") == "cartographer" and rng.random() < 0.25:
        amount += 1
    if profile.get("active_companion") == "brindle" and rng.random() < 0.3:
        amount += 1
    profile["materials"][key] = int(profile["materials"].get(key, 0)) + amount
    messages = grant_profession_xp(profile, 12 + int(profile.get("floor", 1)))
    potion = False
    if profile.get("profession", {}).get("key") == "alchemist" and rng.random() < min(0.5, 0.15 + level * 0.015):
        profile["potions"] += 1
        potion = True
    return {
        "material": key,
        "name": MATERIALS[key]["name"],
        "emoji": MATERIALS[key]["emoji"],
        "amount": amount,
        "potion": potion,
        "messages": messages,
    }
