"""NPC relationship and story-quest helpers."""

from __future__ import annotations

from typing import Any

from deepdelve.advanced_content import NPCS


def npc_progress(profile: dict[str, Any], npc_key: str) -> dict[str, Any]:
    """Return relationship and quest-state details for an NPC."""
    npc = NPCS[npc_key]
    reputation = int(profile.get("npc_reputation", {}).get(npc_key, 0))
    completed = set(profile.get("story_flags", []))
    quests = []
    for index, (name, requirement, description) in enumerate(npc["quests"], start=1):
        flag = f"{npc_key}:{index}"
        eligible = _quest_condition(profile, npc_key, index, requirement)
        quests.append(
            {
                "flag": flag,
                "name": name,
                "description": description,
                "completed": flag in completed,
                "eligible": eligible,
                "requirement": requirement,
            },
        )
    relationship = "Stranger"
    if reputation >= 20:
        relationship = "Confidant"
    elif reputation >= 10:
        relationship = "Trusted"
    elif reputation >= 4:
        relationship = "Acquaintance"
    return {
        "npc": npc,
        "reputation": reputation,
        "relationship": relationship,
        "quests": quests,
    }


def _quest_condition(
    profile: dict[str, Any],
    npc_key: str,
    index: int,
    requirement: int,
) -> bool:
    if npc_key == "orra":
        if index == 1:
            return profile.get("crafted", 0) >= requirement
        if index == 2:
            return sum(profile.get("materials", {}).values()) >= requirement
        return profile.get("deepest_floor", 0) >= requirement
    if npc_key == "mara":
        if index == 1:
            return profile.get("kills", 0) >= requirement
        if index == 2:
            return profile.get("contracts_completed", 0) >= 3
        return profile.get("bosses", 0) >= 4
    if npc_key == "vesper":
        return profile.get("deepest_floor", 0) >= requirement if index == 3 else len(profile.get("lore", [])) >= requirement
    return profile.get("deepest_floor", 0) >= requirement if index != 2 else profile.get("kills", 0) >= requirement
