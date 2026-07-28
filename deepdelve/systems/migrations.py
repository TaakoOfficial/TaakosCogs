"""Idempotent schema migrations for persistent DeepDelve data."""

from __future__ import annotations

from typing import Any

from deepdelve.loot_content import STORY_RELICS
from deepdelve.systems.morality import origin_morality, record_campaign_deed

PROFILE_SCHEMA_VERSION = 6
GUILD_SCHEMA_VERSION = 4


def migrate_profile(profile: dict[str, Any]) -> bool:
    """Upgrade a profile in place and report whether it changed."""
    changed = False
    defaults: dict[str, Any] = {
        "schema_version": PROFILE_SCHEMA_VERSION,
        "tutorial_step": 0,
        "tutorial_complete": False,
        "campaign": {"chapter": 0, "scene": 0, "choices": {}, "completed": [], "ending": ""},
        "active_puzzle": {},
        "solved_puzzles": [],
        "puzzle_streak": 0,
        "companions": {},
        "active_companion": "",
        "profession": {"key": "", "level": 1, "xp": 0},
        "profession_mastery": {},
        "event_tokens": 0,
        "world_events_seen": [],
        "world_event": {},
        "town_contribution": 0,
        "gather_date": "",
        "gather_actions": 0,
        "origin_complete": bool(profile.get("created", False)),
        "starter_choice": "",
        "stash": [],
        "loadouts": {},
        "favorite_items": [],
        "auto_dismantle": -1,
        "consumables": {},
        "recipes": [],
        "bestiary": {},
        "active_rumor": {},
        "rumors_completed": 0,
        "story_relics": [],
        "run_history": [],
        "floor_mutator": {},
        "boss_relic_pity": 0,
        "loot_pity": 0,
        "camp_choices": 0,
        "secret_rooms": 0,
        "morality": origin_morality(profile.get("alignment", "")),
        "convictions": {"mercy": 0, "honesty": 0, "ambition": 0, "ruthlessness": 0},
        "moral_deeds": [],
        "deed_counts": {},
    }
    for key, value in defaults.items():
        if key not in profile:
            profile[key] = value
            changed = True
    campaign = profile["campaign"]
    for key, value in defaults["campaign"].items():
        if key not in campaign:
            campaign[key] = value
            changed = True
    recovered_relics = [choice for choice in campaign.get("choices", {}).values() if choice in STORY_RELICS]
    merged_relics = list(dict.fromkeys([*profile.get("story_relics", []), *recovered_relics]))
    if merged_relics != profile.get("story_relics", []):
        profile["story_relics"] = merged_relics
        changed = True
    for chapter_key, choice in campaign.get("choices", {}).items():
        if record_campaign_deed(profile, chapter_key, choice):
            changed = True
    for conviction in ("mercy", "honesty", "ambition", "ruthlessness"):
        if conviction not in profile["convictions"]:
            profile["convictions"][conviction] = 0
            changed = True
    profession = profile["profession"]
    for key, value in defaults["profession"].items():
        if key not in profession:
            profession[key] = value
            changed = True
    if int(profile.get("schema_version", 0)) != PROFILE_SCHEMA_VERSION:
        profile["schema_version"] = PROFILE_SCHEMA_VERSION
        changed = True
    return changed


def migrate_guild(data: dict[str, Any]) -> bool:
    """Upgrade guild state in place and report whether it changed."""
    changed = False
    defaults: dict[str, Any] = {
        "schema_version": GUILD_SCHEMA_VERSION,
        "town": {
            "level": 1,
            "treasury": 0,
            "buildings": {"forge": 0, "infirmary": 0, "archive": 0, "watch": 0},
            "contributors": {},
        },
        "event_announcement_channel": 0,
        "content_multiplier": 1.0,
    }
    for key, value in defaults.items():
        if key not in data:
            data[key] = value
            changed = True
    town = data["town"]
    for key, value in defaults["town"].items():
        if key not in town:
            town[key] = value
            changed = True
    buildings = town["buildings"]
    for key, value in defaults["town"]["buildings"].items():
        if key not in buildings:
            buildings[key] = value
            changed = True
    if int(data.get("schema_version", 0)) != GUILD_SCHEMA_VERSION:
        data["schema_version"] = GUILD_SCHEMA_VERSION
        changed = True
    return changed
