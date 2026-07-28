"""Companion collection, bonding, and passive bonuses."""

from __future__ import annotations

from typing import Any

from deepdelve.expansion_content import COMPANIONS


def unlock_companions(profile: dict[str, Any]) -> list[str]:
    """Unlock companions earned by depth and return newly unlocked keys."""
    owned = profile.setdefault("companions", {})
    deepest = int(profile.get("deepest_floor", 1))
    unlocked = []
    for key, companion in COMPANIONS.items():
        if deepest >= companion["unlock_floor"] and key not in owned:
            owned[key] = {"level": 1, "xp": 0, "bond": 0}
            unlocked.append(key)
    return unlocked


def active_companion(profile: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]] | None:
    """Return active companion definition and progression."""
    key = profile.get("active_companion", "")
    if key not in COMPANIONS or key not in profile.get("companions", {}):
        return None
    return COMPANIONS[key], profile["companions"][key]


def companion_bonuses(profile: dict[str, Any]) -> dict[str, int]:
    """Return scaled passive statistics from the active companion."""
    active = active_companion(profile)
    if not active:
        return {"attack": 0, "defense": 0, "luck": 0}
    definition, progress = active
    level = int(progress.get("level", 1))
    bond_tier = int(progress.get("bond", 0)) // 25
    scale = 1 + (level - 1) * 0.18
    return {stat: round(int(definition[stat]) * scale) + bond_tier for stat in ("attack", "defense", "luck")}


def grant_companion_xp(profile: dict[str, Any], amount: int) -> list[str]:
    """Award XP/bond to the active companion and return level-up messages."""
    active = active_companion(profile)
    if not active:
        return []
    definition, progress = active
    progress["xp"] = int(progress.get("xp", 0)) + max(0, amount)
    progress["bond"] = min(100, int(progress.get("bond", 0)) + 1)
    messages = []
    while progress["level"] < 10:
        needed = 40 + int(progress["level"]) * 30
        if progress["xp"] < needed:
            break
        progress["xp"] -= needed
        progress["level"] += 1
        messages.append(f"{definition['emoji']} **{definition['name']} reached level {progress['level']}!**")
    return messages
