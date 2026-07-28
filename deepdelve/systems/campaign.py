"""Branching campaign state and reward helpers."""

from __future__ import annotations

from typing import Any

from deepdelve.expansion_content import CAMPAIGN_CHAPTERS
from deepdelve.loot_content import STORY_RELICS
from deepdelve.systems.morality import record_campaign_deed


def campaign_state(profile: dict[str, Any]) -> dict[str, Any]:
    """Normalize and return a character's campaign state."""
    state = profile.setdefault(
        "campaign",
        {"chapter": 0, "scene": 0, "choices": {}, "completed": [], "ending": ""},
    )
    state.setdefault("chapter", 0)
    state.setdefault("scene", 0)
    state.setdefault("choices", {})
    state.setdefault("completed", [])
    state.setdefault("ending", "")
    return state


def current_chapter(profile: dict[str, Any]) -> dict[str, Any] | None:
    """Return the current chapter or ``None`` when the chronicle is complete."""
    state = campaign_state(profile)
    index = int(state["chapter"])
    return CAMPAIGN_CHAPTERS[index] if 0 <= index < len(CAMPAIGN_CHAPTERS) else None


def chapter_available(profile: dict[str, Any]) -> bool:
    """Whether the character has reached the current chapter's required floor."""
    chapter = current_chapter(profile)
    return bool(chapter and int(profile.get("deepest_floor", 1)) >= int(chapter["floor"]))


def campaign_scene(profile: dict[str, Any]) -> dict[str, Any]:
    """Describe the current campaign scene without mutating it."""
    state = campaign_state(profile)
    chapter = current_chapter(profile)
    if not chapter:
        return {"complete": True, "state": state}
    scene = min(int(state["scene"]), len(chapter["scenes"]))
    return {
        "complete": False,
        "available": chapter_available(profile),
        "chapter": chapter,
        "scene": scene,
        "text": chapter["scenes"][scene] if scene < len(chapter["scenes"]) else "",
        "at_choice": scene >= len(chapter["scenes"]),
        "state": state,
    }


def advance_campaign(profile: dict[str, Any], choice: str | None = None) -> dict[str, Any]:
    """Advance one scene or resolve a chapter choice."""
    view = campaign_scene(profile)
    if view["complete"]:
        return {"ok": False, "message": "Your first chronicle is already complete."}
    if not view["available"]:
        floor = view["chapter"]["floor"]
        return {"ok": False, "message": f"This chapter awakens after you reach floor **{floor}**."}
    state = view["state"]
    chapter = view["chapter"]
    if not view["at_choice"]:
        state["scene"] += 1
        next_view = campaign_scene(profile)
        return {
            "ok": True,
            "resolved": False,
            "message": view["text"],
            "at_choice": next_view.get("at_choice", False),
        }
    options = chapter["choice"]["options"]
    if choice not in options:
        return {
            "ok": False,
            "needs_choice": True,
            "options": options,
            "message": "This moment requires one of the permanent decisions shown below.",
        }
    state["choices"][chapter["key"]] = choice
    state["completed"].append(chapter["key"])
    reward = chapter["reward"]
    knowledge_bonus = float(profile.get("town_bonus", {}).get("knowledge_bonus", 0))
    gold_reward = round(int(reward["gold"]) * (1 + knowledge_bonus))
    xp_reward = round(int(reward["xp"]) * (1 + knowledge_bonus))
    profile["gold"] += gold_reward
    profile["xp"] += xp_reward
    profile["event_tokens"] = int(profile.get("event_tokens", 0)) + int(reward["tokens"])
    if choice in STORY_RELICS and choice not in profile.setdefault("story_relics", []):
        profile["story_relics"].append(choice)
    state["chapter"] += 1
    state["scene"] = 0
    if state["chapter"] >= len(CAMPAIGN_CHAPTERS):
        state["ending"] = choice
        profile["titles"] = list(dict.fromkeys([*profile.get("titles", []), "chronicler"]))
    label, consequence = options[choice]
    deed_lines = record_campaign_deed(profile, chapter["key"], choice)
    relic_line = ""
    if choice in STORY_RELICS:
        relic = STORY_RELICS[choice]
        relic_line = f"\n🏺 Story relic recovered: **{relic['name']}**."
    return {
        "ok": True,
        "resolved": True,
        "message": (
            f"**{label}.** {consequence}\n\n"
            f"Chapter complete: **+{gold_reward} gold**, **+{xp_reward} XP**, "
            f"**+{reward['tokens']} Chronicle Token(s)**.{relic_line}" + (f"\n{deed_lines[0]}" if deed_lines else "")
        ),
    }


def campaign_bonuses(profile: dict[str, Any]) -> dict[str, int]:
    """Translate permanent story decisions into modest build bonuses."""
    bonuses = {"attack": 0, "defense": 0, "luck": 0, "hp": 0, "mana": 0}
    effects = {
        "truth": ("luck", 2),
        "mercy": ("hp", 12),
        "power": ("attack", 2),
        "free": ("mana", 12),
        "seal": ("defense", 2),
        "harvest": ("attack", 3),
        "destroy": ("defense", 2),
        "preserve": ("luck", 3),
        "ignite": ("attack", 2),
        "speak": ("luck", 3),
        "erase": ("defense", 3),
        "inherit": ("attack", 4),
        "descend": ("attack", 5),
        "reveal": ("luck", 5),
    }
    choices = profile.get("campaign", {}).get("choices", {})
    for choice in choices.values():
        if choice in effects:
            stat, amount = effects[choice]
            bonuses[stat] += amount
    if profile.get("campaign", {}).get("ending") == "seal":
        bonuses["hp"] += 25
        bonuses["defense"] += 3
    return bonuses
