"""Persistent quest journal, branching resolutions, skill checks, and rewards."""

from __future__ import annotations

import random
from datetime import datetime, timezone
from typing import Any

from deepdelve.living_content import (
    CHARACTER_ARCS,
    CONTRACT_TEMPLATES,
    FACTION_QUESTS,
    MAIN_CAMPAIGN_ACTS,
    SEASON_CHAPTERS,
)
from deepdelve.systems.legacy import advance_redemption, change_faction_reputation, grant_resolve
from deepdelve.systems.morality import record_deed

QUEST_CATEGORIES = ("main", "faction", "character", "side", "bounty", "profession", "moral", "seasonal")


def quest_registry() -> dict[str, dict[str, Any]]:
    """Return the unified immutable quest definition registry."""
    registry: dict[str, dict[str, Any]] = {}
    for act in MAIN_CAMPAIGN_ACTS:
        registry[f"main:{act['key']}"] = {
            "key": f"main:{act['key']}",
            "name": act["name"],
            "category": "main",
            "requirement": {"deepest_floor": act["floor"]},
            "objective": "decision",
            "target": len(act["decisions"]),
            "energy": len(act["scenes"]),
            "reward": act["reward"],
            "outcomes": ("mercy", "honesty", "ambition", "ruthlessness"),
            # Campaign acts appear in the journal, while living_campaign owns
            # their progress and rewards so the same act cannot pay out twice.
            "managed": True,
            "campaign_act": act["key"],
            "managed_message": "Main acts advance through Activities → Living Saga.",
        }
    for arcs in FACTION_QUESTS.values():
        previous = ""
        for quest in arcs:
            registry[quest["key"]] = {**quest, "prerequisite": previous}
            previous = quest["key"]
    for arcs in CHARACTER_ARCS.values():
        previous = ""
        for quest in arcs:
            registry[quest["key"]] = {**quest, "prerequisite": previous}
            previous = quest["key"]
    for chapter in SEASON_CHAPTERS:
        key = f"seasonal:{chapter['key']}"
        registry[key] = {
            "key": key,
            "name": chapter["name"],
            "category": "seasonal",
            "requirement": {"deepest_floor": max(1, chapter["index"] * 2)},
            "objective": "explore",
            "target": chapter["scenes"],
            "energy": chapter["energy_budget"],
            "reward": chapter["reward"],
            "outcomes": ("mercy", "honesty", "ambition", "ruthlessness"),
            "managed": True,
            "managed_message": "Seasonal chapters advance through Activities → Season Archive.",
        }
    contract_categories = ("side", "bounty", "profession", "moral")
    objective_aliases = {
        "hunt": "defeat",
        "study": "study",
        "recover": "recover",
        "survive": "defeat",
        "resolve": "resolve",
        "delve": "delve",
    }
    for index, (contract_key, contract) in enumerate(CONTRACT_TEMPLATES.items()):
        category = contract_categories[index % len(contract_categories)]
        key = f"{category}:{contract_key}"
        registry[key] = {
            "key": key,
            "name": contract["name"],
            "description": contract["description"],
            "category": category,
            "requirement": {"deepest_floor": contract["tier"] * 3},
            "objective": objective_aliases[contract["objective"]],
            "target": contract["target"],
            "energy": contract["energy_budget"],
            "reward": contract["reward"],
            "outcomes": ("mercy", "honesty", "ambition", "ruthlessness"),
            "time_limit_hours": 48 if category == "bounty" else 0,
        }
    return registry


QUESTS = quest_registry()


def ensure_quests(profile: dict[str, Any]) -> dict[str, Any]:
    """Normalize and return persistent quest state."""
    state = profile.setdefault(
        "quests_v2",
        {
            "active": {},
            "completed": {},
            "failed": {},
            "choice_flags": [],
            "counters": {},
            "claim_tokens": [],
        },
    )
    state.setdefault("active", {})
    state.setdefault("completed", {})
    state.setdefault("failed", {})
    state.setdefault("choice_flags", [])
    state.setdefault("counters", {})
    state.setdefault("claim_tokens", [])
    return state


def requirement_status(profile: dict[str, Any], quest: dict[str, Any]) -> tuple[bool, str]:
    """Explain the first unmet quest requirement."""
    requirement = quest.get("requirement", {})
    floor = int(requirement.get("deepest_floor", 0))
    if int(profile.get("deepest_floor", 1)) < floor:
        return False, f"Reach floor {floor}."
    campaign_act = quest.get("campaign_act")
    if campaign_act:
        campaign = profile.get("living_campaign", {})
        if campaign_act in campaign.get("completed", []):
            return False, "This act is already written in your Living Chronicle."
        current_index = int(campaign.get("act", 0))
        current_key = (
            MAIN_CAMPAIGN_ACTS[current_index]["key"]
            if 0 <= current_index < len(MAIN_CAMPAIGN_ACTS)
            else ""
        )
        if campaign_act != current_key:
            return False, "Complete the preceding Living Chronicle act."
    faction_required = int(requirement.get("faction_reputation", 0))
    faction = quest.get("faction")
    faction_rep = profile.get("legacy", {}).get("faction_reputation", {}).get(faction, 0)
    if faction and faction_rep < faction_required:
        return False, f"Earn {faction_required} reputation with this faction."
    relationship = int(requirement.get("relationship", 0))
    character = quest.get("character")
    current_relationship = profile.get("relationships", {}).get(character, {}).get("trust", 0)
    if character and current_relationship < relationship:
        return False, f"Reach {relationship} trust with {character.title()}."
    prerequisite = quest.get("prerequisite")
    if prerequisite and prerequisite not in ensure_quests(profile)["completed"]:
        previous = QUESTS.get(prerequisite, {})
        return False, f"Complete **{previous.get('name', prerequisite)}** first."
    return True, "Available."


def available_quests(profile: dict[str, Any], category: str | None = None) -> list[dict[str, Any]]:
    """Return quest definitions annotated with persistent availability."""
    state = ensure_quests(profile)
    results = []
    for key, definition in QUESTS.items():
        if category and definition["category"] != category:
            continue
        available, reason = requirement_status(profile, definition)
        results.append(
            {
                **definition,
                "available": available,
                "reason": reason,
                "active": key in state["active"],
                "completed": key in state["completed"],
                "failed": key in state["failed"],
            },
        )
    return results


def accept_quest(profile: dict[str, Any], key: str) -> tuple[bool, str]:
    """Accept an available quest without charging its displayed expedition energy."""
    definition = QUESTS.get(key)
    if not definition:
        return False, "Unknown quest."
    if definition.get("managed"):
        return False, f"{definition['managed_message']} Its reward cannot be claimed twice."
    state = ensure_quests(profile)
    if key in state["completed"]:
        return False, "That quest is already complete."
    if key in state["active"]:
        return False, "That quest is already active."
    if len(state["active"]) >= 6:
        return False, "Your active journal is full; resolve or abandon one of its six quests."
    if any(QUESTS.get(active_key, {}).get("category") == definition["category"] for active_key in state["active"]):
        return False, f"Finish the active {definition['category']} quest first."
    available, reason = requirement_status(profile, definition)
    if not available:
        return False, reason
    accepted_at = datetime.now(timezone.utc)
    time_limit = int(definition.get("time_limit_hours", 0))
    state["active"][key] = {
        "progress": 0,
        "target": int(definition["target"]),
        "accepted_at": accepted_at.isoformat(),
        "expires_at": datetime.fromtimestamp(
            accepted_at.timestamp() + time_limit * 3600,
            timezone.utc,
        ).isoformat()
        if time_limit
        else "",
        "outcome": "",
        "claim_token": f"{key}:{len(state['completed'])}:{profile.get('created_at', '')}",
    }
    return True, f"Accepted **{definition['name']}**."


def expire_quests(profile: dict[str, Any], now: datetime | None = None) -> list[str]:
    """Move elapsed timed quests into persistent failure history."""
    state = ensure_quests(profile)
    current = now or datetime.now(timezone.utc)
    lines = []
    for key, progress in list(state["active"].items()):
        expires_at = progress.get("expires_at")
        if not expires_at or datetime.fromisoformat(expires_at) > current:
            continue
        state["failed"][key] = {**progress, "reason": "Time expired.", "failed_at": current.isoformat()}
        del state["active"][key]
        lines.append(f"⌛ **{QUESTS.get(key, {}).get('name', key)}** expired; its failure is remembered.")
    return lines


def fail_quest(profile: dict[str, Any], key: str, reason: str = "Abandoned.") -> tuple[bool, str]:
    """Persist a quest failure without paying its reward."""
    state = ensure_quests(profile)
    progress = state["active"].get(key)
    if not progress:
        return False, "That quest is not active."
    state["failed"][key] = {
        **progress,
        "reason": reason,
        "failed_at": datetime.now(timezone.utc).isoformat(),
    }
    del state["active"][key]
    return True, f"📕 **{QUESTS[key]['name']}** failed — {reason}"


def progress_quests(profile: dict[str, Any], objective: str, amount: int = 1) -> list[str]:
    """Advance all active quests matching an objective."""
    state = ensure_quests(profile)
    lines = expire_quests(profile)
    for key, progress in state["active"].items():
        definition = QUESTS.get(key, {})
        if definition.get("objective") != objective:
            continue
        progress["progress"] = min(progress["target"], int(progress["progress"]) + max(0, int(amount)))
        if progress["progress"] >= progress["target"]:
            lines.append(f"📜 **{definition['name']}** is ready to resolve.")
    state["counters"][objective] = int(state["counters"].get(objective, 0)) + max(0, int(amount))
    return lines


def skill_check_chance(
    profile: dict[str, Any],
    *,
    attribute: str = "",
    conviction: str = "",
    difficulty: int = 50,
) -> int:
    """Calculate a transparent, capped skill-check chance."""
    attributes = profile.get("attributes", {})
    convictions = profile.get("convictions", {})
    attribute_score = int(attributes.get(attribute, 0)) * 4
    conviction_score = min(20, max(0, int(convictions.get(conviction, 0))) // 4)
    profession_score = min(10, int(profile.get("profession", {}).get("level", 1)) // 2)
    companion_score = 5 if profile.get("active_companion") else 0
    lore_score = min(10, len(profile.get("lore", [])) // 2)
    tenet_bonus = (
        5
        if any(
            definition.get("effect", {}).get("check") == conviction
            for key in profile.get("legacy", {}).get("active_tenets", [])
            for definition in (__import__("deepdelve.living_content", fromlist=["TENETS"]).TENETS.get(key, {}),)
        )
        else 0
    )
    return max(
        15,
        min(
            90,
            55
            - int(difficulty)
            + attribute_score
            + conviction_score
            + profession_score
            + companion_score
            + lore_score
            + tenet_bonus,
        ),
    )


def perform_skill_check(
    profile: dict[str, Any],
    *,
    attribute: str = "",
    conviction: str = "",
    difficulty: int = 50,
    roll: int | None = None,
) -> dict[str, Any]:
    """Resolve a visible skill check and return its roll details."""
    chance = skill_check_chance(profile, attribute=attribute, conviction=conviction, difficulty=difficulty)
    rolled = int(roll if roll is not None else random.randint(1, 100))
    rerolled = 0
    flags = profile.setdefault("quests_v2", {}).setdefault("counters", {})
    if (
        rolled > chance
        and "second_answer" in profile.get("legacy", {}).get("active_tenets", [])
        and not flags.get("second_answer_used")
    ):
        flags["second_answer_used"] = 1
        rerolled = random.randint(1, 100)
        rolled = rerolled
    return {
        "success": rolled <= chance,
        "roll": rolled,
        "reroll": rerolled,
        "chance": chance,
        "risk": "Low" if chance >= 70 else "Even" if chance >= 45 else "High",
    }


def resolve_quest(profile: dict[str, Any], key: str, outcome: str) -> tuple[bool, str]:
    """Resolve, reward, and remember an active quest exactly once."""
    expired = expire_quests(profile)
    if expired and key not in ensure_quests(profile)["active"]:
        return False, expired[0]
    definition = QUESTS.get(key)
    state = ensure_quests(profile)
    progress = state["active"].get(key)
    if not definition or not progress:
        return False, "That quest is not active."
    if int(progress["progress"]) < int(progress["target"]):
        return False, f"Progress: {progress['progress']}/{progress['target']}."
    if outcome not in definition.get("outcomes", ()):
        return False, "Choose mercy, honesty, ambition, or ruthlessness."
    claim_token = progress["claim_token"]
    if claim_token in state["claim_tokens"]:
        return False, "That reward has already been claimed."
    reward = definition["reward"]
    profile["gold"] = int(profile.get("gold", 0)) + int(reward.get("gold", 0))
    profile["xp"] = int(profile.get("xp", 0)) + int(reward.get("xp", 0))
    if reward.get("resolve"):
        grant_resolve(profile, int(reward["resolve"]), f"quest:{key}")
    faction = definition.get("faction")
    if faction:
        change_faction_reputation(profile, faction, int(reward.get("faction_reputation", 4)))
    character = definition.get("character")
    if character:
        relationship = profile.setdefault("relationships", {}).setdefault(character, {"trust": 0, "conflict": 0, "flags": []})
        relationship["trust"] += int(reward.get("relationship", 3))
    moral_delta = {"mercy": 3, "honesty": 1, "ambition": -1, "ruthlessness": -3}[outcome]
    record_deed(profile, f"quest:{key}:{outcome}", f"Resolved {definition['name']} through {outcome}", moral_delta, {outcome: 2})
    advance_redemption(profile, outcome)
    flag = f"quest_outcome:{key}:{outcome}"
    if flag not in state["choice_flags"]:
        state["choice_flags"].append(flag)
    progress["outcome"] = outcome
    state["completed"][key] = dict(progress)
    state["claim_tokens"].append(claim_token)
    del state["active"][key]
    return True, (
        f"📜 **{definition['name']} complete** through **{outcome.title()}** — "
        f"+{int(reward.get('gold', 0))} currency, +{int(reward.get('xp', 0))} XP."
    )
