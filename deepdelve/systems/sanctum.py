"""Personal Sanctum progression and capped currency sinks."""

from __future__ import annotations

from typing import Any

SANCTUM_ROOMS: dict[str, dict[str, Any]] = {
    "hall": {"name": "Hall of Echoes", "costs": (250, 750, 1800), "benefit": "Displays endings, deeds, and Nemesis trophies."},
    "library": {
        "name": "Forbidden Library",
        "costs": (300, 900, 2100),
        "benefit": "Adds collection filters and capped skill-check lore.",
    },
    "workshop": {
        "name": "Commission Workshop",
        "costs": (350, 1000, 2400),
        "benefit": "Adds recipe tracking and one weekly commission reroll.",
    },
    "garden": {"name": "Night Garden", "costs": (275, 825, 1950), "benefit": "Displays companions and unlocks cosmetic auras."},
    "observatory": {
        "name": "Subterranean Observatory",
        "costs": (400, 1200, 2800),
        "benefit": "Archives seasons and Atlas discoveries.",
    },
}


def ensure_sanctum(profile: dict[str, Any]) -> dict[str, Any]:
    """Normalize persistent Sanctum state."""
    state = profile.setdefault(
        "sanctum", {"rooms": dict.fromkeys(SANCTUM_ROOMS, 0), "spent": 0, "cosmetics": [], "active_cosmetic": ""},
    )
    state.setdefault("rooms", {})
    for key in SANCTUM_ROOMS:
        state["rooms"].setdefault(key, 0)
    state.setdefault("spent", 0)
    state.setdefault("cosmetics", [])
    state.setdefault("active_cosmetic", "")
    return state


def sanctum_upgrade_cost(profile: dict[str, Any], room: str) -> int | None:
    """Return the next fixed cost or None at maximum level."""
    state = ensure_sanctum(profile)
    definition = SANCTUM_ROOMS.get(room)
    if not definition:
        return None
    level = int(state["rooms"][room])
    return int(definition["costs"][level]) if level < len(definition["costs"]) else None


def upgrade_sanctum(profile: dict[str, Any], room: str) -> tuple[bool, str]:
    """Spend ordinary currency on a capped convenience/cosmetic room."""
    definition = SANCTUM_ROOMS.get(room)
    if not definition:
        return False, "Unknown Sanctum room."
    cost = sanctum_upgrade_cost(profile, room)
    if cost is None:
        return False, "That room is already fully restored."
    if int(profile.get("gold", 0)) < cost:
        return False, f"Restoration requires {cost} currency."
    state = ensure_sanctum(profile)
    profile["gold"] -= cost
    state["spent"] += cost
    state["rooms"][room] += 1
    return True, f"🏛️ **{definition['name']}** restored to level **{state['rooms'][room]}/3** for **{cost} currency**."
