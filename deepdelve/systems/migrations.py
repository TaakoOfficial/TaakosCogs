"""Idempotent schema migrations for persistent DeepDelve data."""

from __future__ import annotations

from typing import Any

PROFILE_SCHEMA_VERSION = 4
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
