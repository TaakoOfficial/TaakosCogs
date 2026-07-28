"""Idempotent schema migrations for persistent DeepDelve data."""

from __future__ import annotations

from typing import Any

from deepdelve.advanced_content import ITEM_SUFFIXES, LEGENDARIES
from deepdelve.content import AFFIXES
from deepdelve.loot_content import RECIPES, STARTER_WEAPONS, STORY_RELICS
from deepdelve.systems.atlas import ensure_atlas
from deepdelve.systems.commissions import ensure_commissions
from deepdelve.systems.legacy import backfill_historical_resolve, ensure_legacy
from deepdelve.systems.living_campaign import ensure_living_campaign
from deepdelve.systems.morality import origin_morality, record_campaign_deed
from deepdelve.systems.nemesis import ensure_nemeses
from deepdelve.systems.quests import ensure_quests
from deepdelve.systems.relationships import ensure_relationships
from deepdelve.systems.sanctum import ensure_sanctum
from deepdelve.systems.season_archive import ensure_season_story

PROFILE_SCHEMA_VERSION = 8
GUILD_SCHEMA_VERSION = 6


def _migrate_item_enchantment(item: dict[str, Any] | None) -> bool:
    """Separate legacy enchantments from the item's recoverable native identity."""
    if not item or not item.get("enchant") or item.get("enchant_effect"):
        return False
    item["enchant_effect"] = item.get("unique_effect", "")
    item["enchant_description"] = item.get("effect_description", "")
    native_effect = ""
    native_description = ""
    native_definitions = [definition for options in STARTER_WEAPONS.values() for definition in options.values()] + list(
        LEGENDARIES,
    )
    native = next(
        (definition for definition in native_definitions if definition["name"] == item.get("name")),
        None,
    )
    if native:
        native_effect = native["effect"]
        native_description = native["description"]
    elif item.get("source"):
        recipe = next(
            (definition for definition in RECIPES.values() if definition["name"] == item.get("source")),
            None,
        )
        if recipe:
            native_effect = recipe["effect"]
            native_description = f"Pattern effect: {recipe['name']}."
    elif item.get("suffix"):
        suffix = next(
            (definition for definition in ITEM_SUFFIXES if definition["name"] == item.get("suffix")),
            None,
        )
        if suffix:
            native_effect = suffix["effect"]
            native_description = suffix["description"]
    item["unique_effect"] = native_effect
    item["effect_description"] = native_description
    return True


def _migrate_bestiary(profile: dict[str, Any]) -> bool:
    """Merge legacy affixed creatures and add variant/floor metadata."""
    old = profile.get("bestiary", {})
    normalized: dict[str, dict[str, Any]] = {}
    changed = False
    affix_names = tuple(affix["name"] for affix in AFFIXES)
    for old_key, raw in old.items():
        entry = dict(raw)
        name = str(entry.get("name") or old_key)
        matched_affix = next((affix for affix in affix_names if name.startswith(f"{affix} ")), "")
        base_name = name.removeprefix(f"{matched_affix} ") if matched_affix else name
        key = old_key
        if matched_affix:
            key = f"creature:{base_name.lower().replace(' ', '_')}"
            changed = True
        target = normalized.setdefault(
            key,
            {
                "name": base_name,
                "kills": 0,
                "mastery": 0,
                "affixes": {},
                "min_floor": int(profile.get("floor", 1)),
                "max_floor": int(profile.get("floor", 1)),
                "kind": entry.get("kind", "creature"),
            },
        )
        target["kills"] += int(entry.get("kills", 0))
        target["mastery"] = max(int(target["mastery"]), int(entry.get("mastery", 0)))
        target["min_floor"] = min(int(target["min_floor"]), int(entry.get("min_floor", profile.get("floor", 1))))
        target["max_floor"] = max(int(target["max_floor"]), int(entry.get("max_floor", profile.get("floor", 1))))
        for affix, count in entry.get("affixes", {}).items():
            target["affixes"][affix] = int(target["affixes"].get(affix, 0)) + int(count)
        if matched_affix:
            target["affixes"][matched_affix] = int(target["affixes"].get(matched_affix, 0)) + int(
                entry.get("kills", 0),
            )
        if any(field not in entry for field in ("affixes", "min_floor", "max_floor", "kind")):
            changed = True
    if normalized != old:
        profile["bestiary"] = normalized
        changed = True
    return changed


def migrate_profile(profile: dict[str, Any]) -> bool:
    """Upgrade a profile in place and report whether it changed."""
    changed = False
    previous_version = int(profile.get("schema_version", 0))
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
        "conviction_fatigue": 0,
        "set_pity": 0,
        "set_discoveries": {},
        "set_fragments": {},
        "legendary_codex": [],
        "legacy": {
            "resolve": 0,
            "resolve_earned": 0,
            "unlocked_tenets": [],
            "active_tenets": [],
            "faction_reputation": {"lantern": 0, "concord": 0, "court": 0},
            "oath": "",
            "oath_board_date": "",
            "oath_board": [],
            "redemption": {},
            "consequence_flags": [],
            "resolve_sources": [],
            "service_dates": {},
        },
        "quests_v2": {
            "active": {},
            "completed": {},
            "failed": {},
            "choice_flags": [],
            "counters": {},
            "claim_tokens": [],
        },
        "relationships": {},
        "mailbox": [],
        "mail_read": [],
        "nemeses": {"active": [], "defeated": [], "next_id": 1},
        "atlas": {"discovered": [], "completed": [], "shortcuts": [], "active_dungeon": {}, "clues": {}},
        "sanctum": {
            "rooms": {"hall": 0, "library": 0, "workshop": 0, "garden": 0, "observatory": 0},
            "spent": 0,
            "cosmetics": [],
            "active_cosmetic": "",
        },
        "season_archive": [],
        "living_campaign": {"act": 0, "scene": 0, "decision": 0, "choices": {}, "completed": [], "ending": ""},
        "season_story": {"active": "", "scene": 0},
        "commissions": {"week": "", "offers": [], "active": {}, "completed": 0},
        "profession_mastery_points": 0,
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
    ensure_legacy(profile)
    ensure_living_campaign(profile)
    ensure_quests(profile)
    ensure_relationships(profile)
    ensure_nemeses(profile)
    ensure_atlas(profile)
    ensure_sanctum(profile)
    ensure_season_story(profile)
    ensure_commissions(profile)
    if previous_version < 8 and backfill_historical_resolve(profile):
        changed = True
    owned_items = [
        *profile.get("inventory", []),
        *profile.get("stash", []),
        *(item for item in profile.get("equipment", {}).values() if item),
    ]
    for item in owned_items:
        if item.get("legendary") and item.get("name") not in profile["legendary_codex"]:
            profile["legendary_codex"].append(item["name"])
            changed = True
        set_key = item.get("set", "")
        slot = item.get("slot", "")
        if set_key and slot in {"weapon", "armor", "charm"}:
            discoveries = profile["set_discoveries"].setdefault(set_key, [])
            if slot not in discoveries:
                discoveries.append(slot)
                changed = True
    for item in owned_items:
        if _migrate_item_enchantment(item):
            changed = True
    if _migrate_bestiary(profile):
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
        "season_archive": [],
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
    stored_items = [record.get("item") for record in data.get("auctions", {}).values()]
    stored_items.extend(item for record in data.get("player_guilds", {}).values() for item in record.get("vault", []))
    for item in stored_items:
        if _migrate_item_enchantment(item):
            changed = True
    if int(data.get("schema_version", 0)) != GUILD_SCHEMA_VERSION:
        data["schema_version"] = GUILD_SCHEMA_VERSION
        changed = True
    return changed
