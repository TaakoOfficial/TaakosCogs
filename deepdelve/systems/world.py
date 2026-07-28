"""Server town progression and deterministic rotating world events."""

from __future__ import annotations

import hashlib
from datetime import date, datetime, timezone
from typing import Any

from deepdelve.expansion_content import TOWN_BUILDINGS, WORLD_EVENTS


def active_world_event(guild_id: int, day: date | None = None) -> dict[str, Any]:
    """Return the deterministic daily event for a server."""
    day = day or datetime.now(timezone.utc).date()
    digest = hashlib.sha256(f"{guild_id}:{day.isoformat()}:deepdelve".encode()).digest()
    event = dict(WORLD_EVENTS[digest[0] % len(WORLD_EVENTS)])
    event["date"] = day.isoformat()
    return event


def town_bonuses(town: dict[str, Any]) -> dict[str, float]:
    """Calculate effects from server town building levels."""
    buildings = town.get("buildings", {})
    return {
        "craft_discount": min(0.28, int(buildings.get("forge", 0)) * 0.07),
        "crafted_bonus": int(buildings.get("forge", 0)),
        "service_discount": min(0.28, int(buildings.get("infirmary", 0)) * 0.07),
        "potion_bonus": int(buildings.get("infirmary", 0)) * 0.05,
        "knowledge_bonus": int(buildings.get("archive", 0)) * 0.08,
        "daily_turns": int(buildings.get("watch", 0)),
        "event_safety": int(buildings.get("watch", 0)) * 0.04,
    }


def upgrade_building(town: dict[str, Any], building_key: str) -> dict[str, Any]:
    """Spend treasury funds to upgrade one town building."""
    if building_key not in TOWN_BUILDINGS:
        return {"ok": False, "message": "Unknown town building."}
    buildings = town.setdefault("buildings", dict.fromkeys(TOWN_BUILDINGS, 0))
    level = int(buildings.get(building_key, 0))
    if level >= 4:
        return {"ok": False, "message": "That building is already fully upgraded."}
    cost = int(TOWN_BUILDINGS[building_key]["costs"][level])
    if int(town.get("treasury", 0)) < cost:
        return {"ok": False, "message": f"The town treasury needs **{cost} gold** for that upgrade."}
    town["treasury"] -= cost
    buildings[building_key] = level + 1
    town["level"] = 1 + sum(int(value) for value in buildings.values())
    return {
        "ok": True,
        "cost": cost,
        "level": level + 1,
        "building": TOWN_BUILDINGS[building_key],
    }
