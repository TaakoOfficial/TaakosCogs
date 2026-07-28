"""Permanent, additive seasonal story chapters with catch-up access."""

from __future__ import annotations

from typing import Any

from deepdelve.living_content import SEASON_CHAPTERS

SCENE_COSTS = (3, 3, 2)


def ensure_season_story(profile: dict[str, Any]) -> dict[str, Any]:
    """Normalize permanent archive and active seasonal story state."""
    profile.setdefault("season_archive", [])
    state = profile.setdefault("season_story", {"active": "", "scene": 0})
    state.setdefault("active", "")
    state.setdefault("scene", 0)
    return state


def season_chapter_status(profile: dict[str, Any]) -> list[dict[str, Any]]:
    """Return every permanent chapter with lock and completion information."""
    state = ensure_season_story(profile)
    archive = set(profile["season_archive"])
    return [
        {
            **chapter,
            "completed": chapter["key"] in archive,
            "active": chapter["key"] == state["active"],
            "available": int(profile.get("deepest_floor", 1)) >= max(1, int(chapter["index"]) * 2),
            "locked_reason": f"Reach floor {max(1, int(chapter['index']) * 2)}.",
        }
        for chapter in SEASON_CHAPTERS
    ]


def begin_season_chapter(profile: dict[str, Any], index: int) -> tuple[bool, str]:
    """Begin any unlocked, unarchived chapter; old chapters never expire."""
    state = ensure_season_story(profile)
    if not 1 <= int(index) <= len(SEASON_CHAPTERS):
        return False, f"Choose a chapter from 1 to {len(SEASON_CHAPTERS)}."
    chapter = SEASON_CHAPTERS[int(index) - 1]
    if chapter["key"] in profile["season_archive"]:
        return False, "That chapter is already preserved in your archive."
    if int(profile.get("deepest_floor", 1)) < max(1, int(chapter["index"]) * 2):
        return False, f"Reach floor {max(1, int(chapter['index']) * 2)}."
    if state["active"] and state["active"] != chapter["key"]:
        return False, "Finish the active seasonal chapter first."
    state["active"] = chapter["key"]
    state["scene"] = 0
    return True, f"Opened **{chapter['name']}**. Its three scenes cost 3, 3, and 2 energy."


def advance_season_chapter(profile: dict[str, Any]) -> tuple[bool, str]:
    """Spend the declared scene energy and permanently archive completion."""
    state = ensure_season_story(profile)
    chapter = next((entry for entry in SEASON_CHAPTERS if entry["key"] == state["active"]), None)
    if not chapter:
        return False, "No seasonal chapter is active."
    scene = int(state["scene"])
    cost = SCENE_COSTS[scene]
    if int(profile.get("turns", 0)) < cost:
        return False, f"This scene costs **{cost} exploration energy**; only {profile.get('turns', 0)} remains."
    profile["turns"] -= cost
    state["scene"] += 1
    if state["scene"] < 3:
        return True, (
            f"📚 **{chapter['name']} — Scene {state['scene']}/3** preserved. "
            f"The next scene costs {SCENE_COSTS[state['scene']]} energy."
        )
    reward = chapter["reward"]
    profile["gold"] = int(profile.get("gold", 0)) + int(reward["gold"])
    profile["xp"] = int(profile.get("xp", 0)) + int(reward["xp"])
    profile["season_archive"].append(chapter["key"])
    sanctum = profile.setdefault("sanctum", {})
    cosmetics = sanctum.setdefault("cosmetics", [])
    if reward["cosmetic"] not in cosmetics:
        cosmetics.append(reward["cosmetic"])
    state["active"] = ""
    state["scene"] = 0
    return True, (
        f"📚 **{chapter['name']} permanently archived.** "
        f"+{reward['gold']} currency • +{reward['xp']} XP • cosmetic `{reward['cosmetic']}`."
    )
