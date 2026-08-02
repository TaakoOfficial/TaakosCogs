"""Focused regression tests for DeepDelve's solo chronicle expansion."""

from __future__ import annotations

import random
from datetime import date

from deepdelve.deepdelve import DeepDelve
from deepdelve.expansion_content import CAMPAIGN_CHAPTERS, PUZZLES
from deepdelve.systems.campaign import advance_campaign, campaign_bonuses, campaign_scene
from deepdelve.systems.companions import companion_bonuses, grant_companion_xp, unlock_companions
from deepdelve.systems.migrations import PROFILE_SCHEMA_VERSION, migrate_profile
from deepdelve.systems.professions import gather
from deepdelve.systems.puzzles import puzzle_for_floor, resolve_puzzle
from deepdelve.systems.world import active_world_event, town_bonuses, upgrade_building


def profile() -> dict:
    """Return the minimal state consumed by pure expansion systems."""
    data = {
        "created": True,
        "deepest_floor": 25,
        "floor": 12,
        "gold": 0,
        "xp": 0,
        "hp": 100,
        "potions": 0,
        "rooms_cleared": 0,
        "arcane_shards": 0,
        "materials": {"iron": 0, "silk": 0, "ember": 0, "essence": 0, "voidglass": 0},
    }
    migrate_profile(data)
    return data


def test_profile_migration_is_idempotent() -> None:
    data = {"created": True, "campaign": {"chapter": 0}, "profession": {"key": ""}}
    assert migrate_profile(data)
    assert data["schema_version"] == PROFILE_SCHEMA_VERSION
    assert data["campaign"]["choices"] == {}
    assert data["profession"]["level"] == 1
    assert not migrate_profile(data)


def test_campaign_advances_and_records_permanent_choice() -> None:
    data = profile()
    first = CAMPAIGN_CHAPTERS[0]
    for _scene in first["scenes"]:
        assert advance_campaign(data)["ok"]
    assert campaign_scene(data)["at_choice"]
    result = advance_campaign(data, "power")
    assert result["resolved"]
    assert data["campaign"]["choices"][first["key"]] == "power"
    assert data["campaign"]["chapter"] == 1
    assert campaign_bonuses(data)["attack"] == 2
    while not campaign_scene(data)["at_choice"]:
        advance_campaign(data)
    assert "requires" in advance_campaign(data, "not-a-choice")["message"]


def test_puzzle_success_and_failure_paths() -> None:
    data = profile()
    data["active_puzzle"] = puzzle_for_floor(12, [], random.Random(7))
    correct = data["active_puzzle"]["answer"]
    result = resolve_puzzle(data, correct)
    assert result["solved"]
    assert data["rooms_cleared"] == 1
    assert data["arcane_shards"] >= 1

    data["active_puzzle"] = puzzle_for_floor(12, [], random.Random(8))
    wrong = next(answer for answer in data["active_puzzle"]["options"] if answer != data["active_puzzle"]["answer"])
    first_failure = resolve_puzzle(data, wrong)
    second_failure = resolve_puzzle(data, wrong)
    assert not first_failure["solved"]
    assert not second_failure["solved"]
    assert not data["active_puzzle"]


def test_puzzle_embed_never_repeats_the_riddle_narrative() -> None:
    data = profile()
    data["active_puzzle"] = puzzle_for_floor(12, [], random.Random(7))
    riddle = data["active_puzzle"]["text"]
    cog = object.__new__(DeepDelve)
    embed = cog._puzzle_embed(data, riddle)
    assert embed.description.count(riddle) == 1


def test_every_floor_band_has_a_varied_valid_puzzle_pool() -> None:
    assert len(PUZZLES) >= 50
    assert len({puzzle["key"] for puzzle in PUZZLES}) == len(PUZZLES)
    for floor in (3, 8, 13, 18, 25):
        pool = [puzzle for puzzle in PUZZLES if puzzle["min_floor"] <= floor <= puzzle["max_floor"]]
        assert len(pool) >= 10
        for puzzle in pool:
            assert puzzle["answer"] in puzzle["options"]
            assert len(puzzle["options"]) >= 3
            assert puzzle["text"]
            assert puzzle["hint"]
            assert puzzle["success"]


def test_exhausted_puzzle_pool_does_not_immediately_repeat() -> None:
    floor = 8
    solved = [puzzle["key"] for puzzle in PUZZLES if puzzle["min_floor"] <= floor <= puzzle["max_floor"]]
    latest = solved[-1]

    for seed in range(10):
        assert puzzle_for_floor(floor, solved, random.Random(seed))["key"] != latest


def test_repeated_puzzle_solution_becomes_the_most_recent_without_duplication() -> None:
    data = profile()
    puzzle = puzzle_for_floor(12, [], random.Random(3))
    data["solved_puzzles"] = [puzzle["key"], "older_puzzle"]
    data["active_puzzle"] = puzzle

    assert resolve_puzzle(data, puzzle["answer"])["solved"]
    assert data["solved_puzzles"][-1] == puzzle["key"]
    assert data["solved_puzzles"].count(puzzle["key"]) == 1


def test_companions_unlock_level_and_contribute_stats() -> None:
    data = profile()
    unlocked = unlock_companions(data)
    assert len(unlocked) == 5
    data["active_companion"] = "brindle"
    messages = grant_companion_xp(data, 1000)
    assert messages
    assert data["companions"]["brindle"]["level"] > 1
    assert companion_bonuses(data)["attack"] >= 3


def test_profession_gathering_progresses_and_awards_materials() -> None:
    data = profile()
    data["profession"] = {"key": "cartographer", "level": 1, "xp": 0}
    result = gather(data, random.Random(2))
    assert result["amount"] >= 1
    assert data["materials"]["ember"] >= 1
    assert data["profession"]["xp"] > 0


def test_world_event_is_deterministic_per_server_day() -> None:
    day = date(2026, 7, 28)
    assert active_world_event(1234, day) == active_world_event(1234, day)
    event = active_world_event(1234, day)
    assert {"combat", "reward", "puzzle"} <= event.keys()


def test_town_upgrades_spend_treasury_and_grant_bonuses() -> None:
    town = {
        "level": 1,
        "treasury": 10_000,
        "buildings": {"forge": 0, "infirmary": 0, "archive": 0, "watch": 0},
    }
    result = upgrade_building(town, "forge")
    assert result["ok"]
    assert town["buildings"]["forge"] == 1
    assert town_bonuses(town)["craft_discount"] > 0
