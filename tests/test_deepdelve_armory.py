"""Coverage for the DeepDelve Origins & Armory expansion."""

from __future__ import annotations

import random

from deepdelve.loot_content import CONSUMABLES, RECIPES, REGIONAL_BASES, STARTER_WEAPONS
from deepdelve.systems.armory import (
    boss_relic_for,
    create_starter_item,
    should_auto_dismantle,
    use_consumable,
)
from deepdelve.systems.campaign import advance_campaign
from deepdelve.systems.dungeon_depth import (
    apply_miniboss,
    create_rumor,
    floor_mutator,
    progress_rumor,
    record_bestiary_kill,
)
from deepdelve.systems.migrations import PROFILE_SCHEMA_VERSION, migrate_profile


def test_authored_loot_breadth_and_starter_identity() -> None:
    assert sum(len(options) for options in STARTER_WEAPONS.values()) == 9
    assert sum(len(slots) for region in REGIONAL_BASES for slots in region.values()) == 45
    assert len(CONSUMABLES) == 15
    assert len(RECIPES) == 5
    item = create_starter_item("shadow", "serpent_dirk", random.Random(7))
    assert item["origin"] and item["bound"]
    assert item["upgrade_cap"] == 3
    assert item["unique_effect"] == "origin_dirk"


def test_auto_dismantle_never_destroys_special_or_favorite_items() -> None:
    profile = {"auto_dismantle": 2, "favorite_items": ["safe"]}
    ordinary = {"id": "drop", "rarity_index": 2}
    assert should_auto_dismantle(profile, ordinary)
    assert not should_auto_dismantle(profile, ordinary | {"id": "safe"})
    assert not should_auto_dismantle(profile, ordinary | {"legendary": True})
    assert not should_auto_dismantle(profile, ordinary | {"origin": True})
    assert not should_auto_dismantle(profile, ordinary | {"set": "citadel"})


def test_consumables_are_atomic_and_context_aware() -> None:
    profile = {
        "level": 5,
        "floor": 4,
        "hp": 20,
        "mana": 4,
        "consumables": {"lantern_tonic": 1, "iron_oil": 1},
        "combat_flags": {},
        "encounter": {},
        "_calculated_stats": {"max_hp": 100, "max_mana": 30},
        "status": {},
    }
    result = use_consumable(profile, "iron_oil")
    assert not result["ok"]
    assert profile["consumables"]["iron_oil"] == 1
    result = use_consumable(profile, "lantern_tonic")
    assert result["ok"] and profile["hp"] > 20
    assert profile["consumables"]["lantern_tonic"] == 0


def test_boss_relics_match_sources_and_minibosses_are_rewarding() -> None:
    relic = boss_relic_for("Ascended The Bellower", 35, random.Random(3))
    assert relic and relic["legendary"] and relic["source"] == "Ascended The Bellower"
    enemy = {"name": "Rat", "hp": 20, "attack": 5, "defense": 1, "gold": 4, "xp": 5}
    promoted = apply_miniboss(enemy, 1, random.Random(3))
    assert promoted["miniboss"]
    assert promoted["gold"] == 8
    assert promoted["hp"] > 20


def test_rumor_unlocks_recipe_and_bestiary_has_mastery() -> None:
    profile = {
        "floor": 1,
        "gold": 0,
        "arcane_shards": 0,
        "recipes": [],
        "bestiary": {},
        "rumors_completed": 0,
    }
    rumor = create_rumor(profile, random.Random(2))
    rumor["target"] = 1
    profile["active_rumor"] = rumor
    enemy = {"name": "Rat", "floor": 1}
    lines = progress_rumor(profile, enemy)
    assert lines and profile["recipes"] == ["lanternsteel"]
    for _ in range(5):
        record_bestiary_kill(profile, enemy)
    entry = next(iter(profile["bestiary"].values()))
    assert entry["mastery"] == 1


def test_story_choices_create_non_power_collection_relics() -> None:
    profile = {
        "deepest_floor": 5,
        "gold": 0,
        "xp": 0,
        "event_tokens": 0,
        "titles": [],
        "story_relics": [],
        "campaign": {"chapter": 0, "scene": 3, "choices": {}, "completed": [], "ending": ""},
    }
    result = advance_campaign(profile, "mercy")
    assert result["ok"] and result["resolved"]
    assert profile["story_relics"] == ["mercy"]


def test_floor_mutators_are_deterministic_and_migration_is_safe() -> None:
    assert floor_mutator(12, 2) == floor_mutator(12, 2)
    assert floor_mutator(12, 2)["key"] in {"darkness", "flooded", "unstable", "hunted", "hollow"}
    old = {"created": True}
    assert migrate_profile(old)
    assert old["schema_version"] == PROFILE_SCHEMA_VERSION
    assert old["origin_complete"] is True
    assert old["stash"] == [] and old["bestiary"] == {}
