"""Profession commissions and recipe research for the Living World."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from deepdelve.living_content import LIVING_RECIPES


def ensure_commissions(profile: dict[str, Any]) -> dict[str, Any]:
    """Normalize profession commission state."""
    state = profile.setdefault(
        "commissions",
        {"week": "", "offers": [], "active": {}, "completed": 0},
    )
    state.setdefault("week", "")
    state.setdefault("offers", [])
    state.setdefault("active", {})
    state.setdefault("completed", 0)
    return state


def commission_board(profile: dict[str, Any]) -> list[dict[str, Any]]:
    """Return three deterministic weekly profession offers."""
    state = ensure_commissions(profile)
    today = datetime.now(timezone.utc).date()
    week = f"{today.isocalendar().year}-w{today.isocalendar().week:02d}"
    if state["week"] == week and state["offers"]:
        return state["offers"]
    profession = profile.get("profession", {}).get("key", "")
    seed = today.isocalendar().week + sum(ord(char) for char in profession)
    objectives = ("gather", "craft", "defeat")
    state["week"] = week
    state["offers"] = [
        {
            "key": f"commission:{week}:{profession or 'delver'}:{index}",
            "name": f"{(profession or 'Delver').replace('_', ' ').title()} Commission {index}",
            "objective": objectives[(seed + index) % len(objectives)],
            "target": 2 + index,
            "progress": 0,
            "reward": {"gold": 90 + index * 45, "xp": 70 + index * 35, "mastery": 12 + index * 4},
        }
        for index in range(1, 4)
    ]
    return state["offers"]


def accept_commission(profile: dict[str, Any], index: int) -> tuple[bool, str]:
    """Accept one weekly commission."""
    state = ensure_commissions(profile)
    offers = commission_board(profile)
    if state["active"]:
        return False, "Finish the active commission first."
    if not 1 <= int(index) <= len(offers):
        return False, "Choose commission 1, 2, or 3."
    state["active"] = dict(offers[int(index) - 1])
    offer = state["active"]
    return True, f"Accepted **{offer['name']}** — {offer['objective']} {offer['target']} time(s)."


def progress_commission(profile: dict[str, Any], objective: str, amount: int = 1) -> list[str]:
    """Advance and automatically reward a matching commission."""
    state = ensure_commissions(profile)
    active = state.get("active") or {}
    if not active or active["objective"] != objective:
        return []
    active["progress"] = min(active["target"], int(active["progress"]) + max(0, int(amount)))
    if active["progress"] < active["target"]:
        return [f"⚒️ Commission progress: **{active['progress']}/{active['target']}**."]
    reward = active["reward"]
    profile["gold"] = int(profile.get("gold", 0)) + int(reward["gold"])
    profile["xp"] = int(profile.get("xp", 0)) + int(reward["xp"])
    profile.setdefault("profession_mastery_points", 0)
    profile["profession_mastery_points"] += int(reward["mastery"])
    state["completed"] += 1
    name = active["name"]
    state["active"] = {}
    return [f"⚒️ **Commission complete: {name}** — +{reward['gold']} currency, +{reward['xp']} XP, +{reward['mastery']} mastery."]


def research_recipe(profile: dict[str, Any], key: str) -> tuple[bool, str]:
    """Research a gated recipe using currency and regional materials."""
    recipe = LIVING_RECIPES.get(key)
    if not recipe:
        return False, "Unknown Living World recipe."
    if key in profile.setdefault("recipes", []):
        return False, "That recipe is already known."
    mastery = int(profile.get("profession_mastery_points", 0))
    if mastery < int(recipe["mastery"]):
        return False, f"Research requires {recipe['mastery']} profession mastery."
    if int(profile.get("gold", 0)) < int(recipe["gold_cost"]):
        return False, f"Research requires {recipe['gold_cost']} currency."
    for material, amount in recipe["materials"].items():
        if int(profile.get("materials", {}).get(material, 0)) < int(amount):
            return False, f"Research requires {amount} {material}."
    profile["gold"] -= int(recipe["gold_cost"])
    for material, amount in recipe["materials"].items():
        profile["materials"][material] -= int(amount)
    profile["recipes"].append(key)
    return True, f"📖 Researched **{recipe['name']}**. It is now recorded in your crafting collection."
