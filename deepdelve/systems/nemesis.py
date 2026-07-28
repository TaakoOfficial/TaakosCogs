"""Personal Nemeses created by consequential defeats."""

from __future__ import annotations

import random
from typing import Any

NEMESIS_EPITHETS = ("the Unforgotten", "Lantern-Breaker", "the Patient", "Oath-Eater", "Scar-Collector")
NEMESIS_TRAITS = {
    "vengeful": "Deals more damage after the delver heals.",
    "studious": "Resists the delver's most-used ability.",
    "hoarder": "Carries improved bound loot.",
    "stalker": "Can interrupt ordinary exploration.",
    "scarred": "Begins wounded but gains attack.",
}


def ensure_nemeses(profile: dict[str, Any]) -> dict[str, Any]:
    """Normalize persistent Nemesis state."""
    state = profile.setdefault("nemeses", {"active": [], "defeated": [], "next_id": 1})
    state.setdefault("active", [])
    state.setdefault("defeated", [])
    state.setdefault("next_id", 1)
    return state


def create_nemesis(profile: dict[str, Any], enemy: dict[str, Any], *, force: bool = False) -> dict[str, Any] | None:
    """Promote a defeating enemy, capped to three active rivals."""
    state = ensure_nemeses(profile)
    if len(state["active"]) >= 3 or (not force and random.random() > 0.35):
        return None
    base_name = str(enemy.get("base_name") or enemy.get("name") or "Nameless Hunter")
    trait = random.choice(tuple(NEMESIS_TRAITS))
    nemesis = {
        "id": state["next_id"],
        "name": f"{base_name}, {random.choice(NEMESIS_EPITHETS)}",
        "base_name": base_name,
        "trait": trait,
        "trait_text": NEMESIS_TRAITS[trait],
        "level": 1,
        "victories": 1,
        "floor": int(profile.get("floor", 1)),
        "reward_multiplier": 1.35,
    }
    state["next_id"] += 1
    state["active"].append(nemesis)
    return nemesis


def record_nemesis_escape(profile: dict[str, Any], nemesis_id: int) -> None:
    """Improve a Nemesis that defeats the player again."""
    state = ensure_nemeses(profile)
    nemesis = next((entry for entry in state["active"] if int(entry["id"]) == int(nemesis_id)), None)
    if nemesis:
        nemesis["victories"] += 1
        nemesis["level"] = min(5, int(nemesis["level"]) + 1)
        nemesis["reward_multiplier"] = min(2.0, float(nemesis["reward_multiplier"]) + 0.15)


def defeat_nemesis(profile: dict[str, Any], nemesis_id: int) -> tuple[bool, str]:
    """Archive a Nemesis and grant a bounded non-resalable trophy."""
    state = ensure_nemeses(profile)
    nemesis = next((entry for entry in state["active"] if int(entry["id"]) == int(nemesis_id)), None)
    if not nemesis:
        return False, "That Nemesis is no longer hunting you."
    state["active"].remove(nemesis)
    state["defeated"].append({**nemesis, "trophy": f"Mark of {nemesis['name']}", "bound": True})
    return True, f"🏆 **{nemesis['name']}** is finally defeated. Its bound trophy enters your Sanctum."
