"""Regression tests for DeepDelve's balance and state-safety rules."""

from __future__ import annotations

from deepdelve.content import boss_for_floor
from deepdelve.deepdelve import DeepDelve
from deepdelve.systems.endgame import restore_challenge_origin, scaled_daily_floor
from deepdelve.systems.items import item_sale_value
from deepdelve.systems.progression import progression_bonuses


def test_boss_curve_never_resets_at_identity_cycles() -> None:
    bosses = [boss_for_floor(floor) for floor in range(5, 151, 5)]
    for previous, current in zip(bosses, bosses[1:], strict=False):
        for stat in ("hp", "attack", "defense", "gold", "xp"):
            assert current[stat] > previous[stat], (stat, previous, current)


def test_upgrades_cannot_increase_resale_value() -> None:
    legacy_upgraded = {
        "floor": 100,
        "rarity_index": 3,
        "value": 18_000,
        "upgrade": 10,
    }
    assert item_sale_value(legacy_upgraded) == round((12 + 100 * 7) * 2.25)

    natural_item = {"floor": 20, "rarity_index": 2, "value": 258, "upgrade": 0}
    natural_sale = item_sale_value(natural_item)
    natural_item.update({"upgrade": 10, "value": 99_999})
    assert item_sale_value(natural_item) == natural_sale


def test_challenge_exit_restores_replaced_adventure_state() -> None:
    profile = {
        "floor": 24,
        "rooms_cleared": 2,
        "rift_state": {"original_floor": 12, "original_rooms": 4},
    }
    assert restore_challenge_origin(profile)
    assert profile["floor"] == 12
    assert profile["rooms_cleared"] == 4
    assert profile["rift_state"] == {}
    assert not restore_challenge_origin(profile)


def test_daily_floor_is_bracketed_to_player_progress() -> None:
    assert scaled_daily_floor(25, 5) == 7
    assert scaled_daily_floor(5, 40) == 5
    assert scaled_daily_floor(25, 40) == 25


def test_prestige_combat_power_caps_at_ten() -> None:
    base = {
        "attributes": {},
        "class_key": "shadow",
        "subclass": "",
        "talents": {},
        "blessings": [],
        "scars": [],
        "party_bonus": {},
        "guild_bonus": {},
    }
    at_cap = progression_bonuses({**base, "prestige": 10})
    far_beyond = progression_bonuses({**base, "prestige": 100})
    assert far_beyond["attack_percent"] == at_cap["attack_percent"] == 10
    assert far_beyond["hp_percent"] == at_cap["hp_percent"] == 20


def test_scars_do_not_reward_intentional_deaths() -> None:
    base = {
        "attributes": {},
        "class_key": "shadow",
        "subclass": "",
        "talents": {},
        "prestige": 0,
        "blessings": [],
        "party_bonus": {},
        "guild_bonus": {},
    }
    clean = progression_bonuses({**base, "scars": []})
    scarred = progression_bonuses(
        {
            **base,
            "scars": [
                "Spiderbite Scar",
                "Cinderbrand",
                "Hollow King's Gaze",
                "Void-Touched Hand",
                "Bellower's Mark",
            ],
        },
    )
    assert scarred == clean


def test_cooldowns_advance_after_actions_but_not_on_the_cast_that_created_them() -> None:
    profile = {
        "subclass": "",
        "skill_cooldowns": {"just_cast": 1, "older": 2},
    }
    DeepDelve._advance_cooldowns(profile, exclude="just_cast")
    assert profile["skill_cooldowns"] == {"just_cast": 1, "older": 1}
    DeepDelve._advance_cooldowns(profile)
    assert profile["skill_cooldowns"] == {}
