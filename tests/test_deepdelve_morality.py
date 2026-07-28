"""Regression coverage for living Morality, deeds, and conviction powers."""

from __future__ import annotations

from deepdelve.systems.campaign import advance_campaign
from deepdelve.systems.migrations import PROFILE_SCHEMA_VERSION, migrate_profile
from deepdelve.systems.morality import (
    moral_power,
    morality_path,
    origin_morality,
    record_choice_deed,
    record_deed,
    use_moral_power,
)


def moral_profile(score: int = 0) -> dict:
    return {
        "alignment": "Pragmatic",
        "morality": score,
        "convictions": {"mercy": 0, "honesty": 0, "ambition": 0, "ruthlessness": 0},
        "moral_deeds": [],
        "deed_counts": {},
        "floor": 3,
        "hp": 50,
        "mana": 4,
        "status": {"curse": 2},
        "combat_flags": {},
    }


def test_origin_philosophy_is_only_a_starting_bias() -> None:
    assert origin_morality("Radiant") == 15
    assert origin_morality("Pragmatic") == 0
    assert origin_morality("Umbral") == -15


def test_repeatable_deeds_diminish_and_stop_farming() -> None:
    profile = moral_profile()
    deltas = []
    for _ in range(5):
        before = profile["morality"]
        record_deed(
            profile,
            "aid",
            "Helped a stranger",
            8,
            {"mercy": 4},
            repeatable=True,
        )
        deltas.append(profile["morality"] - before)
    assert deltas == [8, 4, 2, 0, 0]
    assert profile["convictions"]["mercy"] == 7
    assert len(profile["moral_deeds"]) == 3


def test_unique_deeds_cannot_be_replayed() -> None:
    profile = moral_profile()
    assert record_deed(profile, "unique", "Made a permanent choice", -10, {"ambition": 5})
    assert not record_deed(profile, "unique", "Made a permanent choice", -10, {"ambition": 5})
    assert profile["morality"] == -10


def test_campaign_choices_record_morality_and_convictions() -> None:
    profile = moral_profile()
    profile.update(
        {
            "deepest_floor": 5,
            "gold": 0,
            "xp": 0,
            "event_tokens": 0,
            "titles": [],
            "story_relics": [],
            "campaign": {"chapter": 0, "scene": 3, "choices": {}, "completed": [], "ending": ""},
        },
    )
    result = advance_campaign(profile, "power")
    assert result["ok"] and result["resolved"]
    assert profile["morality"] == -8
    assert profile["convictions"]["ambition"] == 5
    assert profile["moral_deeds"][0]["key"] == "campaign:lantern_below:power"


def test_moral_paths_transform_at_symmetric_thresholds() -> None:
    assert morality_path(moral_profile(70))["key"] == "beacon"
    assert morality_path(moral_profile(30))["key"] == "radiant"
    assert morality_path(moral_profile(0))["key"] == "pragmatic"
    assert morality_path(moral_profile(-30))["key"] == "umbral"
    assert morality_path(moral_profile(-70))["key"] == "dreadbound"


def test_conviction_power_is_once_per_battle() -> None:
    profile = moral_profile(70)
    enemy = {"hp": 100, "defense": 5}
    stats = {"max_hp": 100, "max_mana": 20, "attack": 15}
    power = moral_power(profile)
    assert power["available"] and power["greater"]
    first = use_moral_power(profile, enemy, stats)
    assert first["ok"]
    assert profile["hp"] > 50
    assert profile["status"] == {}
    assert not use_moral_power(profile, enemy, stats)["ok"]


def test_choice_deeds_use_the_same_anti_farming_ledger() -> None:
    profile = moral_profile()
    for _ in range(4):
        record_choice_deed(profile, "lost_delver", "aid")
    assert profile["morality"] == 13
    assert profile["deed_counts"]["event:lost_delver:aid"] == 3


def test_schema_six_backfills_completed_campaign_morality_once() -> None:
    old = {
        "created": True,
        "alignment": "Radiant",
        "campaign": {
            "chapter": 1,
            "scene": 0,
            "choices": {"lantern_below": "truth"},
            "completed": ["lantern_below"],
            "ending": "",
        },
    }
    assert migrate_profile(old)
    assert old["schema_version"] == PROFILE_SCHEMA_VERSION == 6
    assert old["morality"] == 23
    assert old["convictions"]["honesty"] == 5
    assert not migrate_profile(old)
