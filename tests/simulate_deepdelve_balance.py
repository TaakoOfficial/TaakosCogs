"""Repeatable Monte Carlo smoke test for DeepDelve's solo combat bands.

Run directly from the repository root:
    python tests/simulate_deepdelve_balance.py
"""

from __future__ import annotations

import random
import sys
from pathlib import Path
from statistics import mean

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from deepdelve.advanced_content import ABILITIES
from deepdelve.content import GAME_CLASSES, RARITIES, boss_for_floor, enemy_for_floor
from deepdelve.deepdelve import DeepDelve
from deepdelve.systems.combat import ensure_enemy_intent

LEVELS = {5: 4, 10: 7, 20: 16, 30: 24, 40: 31}
SUBCLASSES = {"vanguard": "guardian", "shadow": "assassin", "arcanist": "elementalist"}


def _equipment(floor: int) -> dict:
    rarity_index = 0 if floor < 5 else 1 if floor < 15 else 2 if floor < 30 else 3
    multiplier = float(RARITIES[rarity_index]["multiplier"])
    upgrade = min(4, floor // 10)
    primary = round((2 + floor * 0.65) * multiplier * 1.12**upgrade)
    return {
        "weapon": {"attack": primary, "defense": 0, "hp": 0, "luck": rarity_index // 2},
        "armor": {"attack": 0, "defense": primary, "hp": round(primary * 2.5), "luck": 0},
        "charm": {
            "attack": round(primary * 0.55),
            "defense": 0,
            "hp": 0,
            "luck": max(1, round(primary * 0.6)),
        },
    }


def _allocate(total: int, weights: dict[str, float]) -> dict[str, int]:
    result = {key: int(total * weight) for key, weight in weights.items()}
    result[next(iter(weights))] += total - sum(result.values())
    return result


def profile_for(class_key: str, floor: int) -> dict:
    level = LEVELS[floor]
    weights = {
        "vanguard": {"might": 0.35, "vitality": 0.45, "finesse": 0.1, "fortune": 0.1},
        "shadow": {"might": 0.4, "finesse": 0.3, "fortune": 0.2, "vitality": 0.1},
        "arcanist": {"might": 0.4, "insight": 0.35, "vitality": 0.15, "fortune": 0.1},
    }[class_key]
    talent_points = 1 + (level - 1) // 2
    talent_order = {
        "vanguard": ("unyielding", "retaliation", "weapon_mastery", "second_wind"),
        "shadow": ("precision", "evasion", "toxicology", "opportunist"),
        "arcanist": ("spellpower", "mana_shield", "deep_reserves", "overchannel"),
    }[class_key]
    caps = {
        "unyielding": 5,
        "retaliation": 3,
        "weapon_mastery": 5,
        "second_wind": 1,
        "precision": 5,
        "evasion": 3,
        "toxicology": 5,
        "opportunist": 1,
        "spellpower": 5,
        "mana_shield": 3,
        "deep_reserves": 5,
        "overchannel": 1,
    }
    talents: dict[str, int] = {}
    for key in talent_order:
        rank = min(caps[key], talent_points)
        talents[key] = rank
        talent_points -= rank
    profile = {
        "created": True,
        "class_key": class_key,
        "level": level,
        "floor": floor,
        "equipment": _equipment(floor),
        "attributes": _allocate(5 + (level - 1) * 2, weights),
        "talents": talents,
        "subclass": SUBCLASSES[class_key],
        "prestige": 0,
        "blessings": [],
        "scars": [],
        "party_bonus": {},
        "party_role": "",
        "party_id": "",
        "guild_bonus": {},
        "town_bonus": {},
        "campaign": {"choices": {}},
        "companions": {},
        "active_companion": "",
        "status": {},
        "combat_flags": {},
        "skill_cooldowns": {},
        "ability_casts": 0,
        "potions": 2,
    }
    stats = DeepDelve._stats(DeepDelve.__new__(DeepDelve), profile)
    profile["hp"] = stats["max_hp"]
    profile["mana"] = stats["max_mana"]
    return profile


def _available(profile: dict, key: str) -> dict | None:
    return next(
        (
            ability
            for ability in ABILITIES[profile["class_key"]]
            if ability["key"] == key
            and profile["level"] >= ability["level"]
            and not profile["skill_cooldowns"].get(key)
            and profile["mana"] >= ability["mana"]
        ),
        None,
    )


def _choose_ability(profile: dict, enemy: dict) -> dict | None:
    intent = enemy["intent"]["key"]
    defensive = {
        "vanguard": "iron_wall",
        "shadow": "smoke_bomb",
        "arcanist": "frost_ward",
    }[profile["class_key"]]
    if intent == "heavy" and (ability := _available(profile, defensive)):
        return ability
    priorities = {
        "vanguard": ("last_stand", "sunder", "shield_bash"),
        "shadow": ("execution", "venom_edge", "twin_fang"),
        "arcanist": ("starfire", "arcane_lance", "time_fracture"),
    }[profile["class_key"]]
    for key in priorities:
        if key == "last_stand" and profile["hp"] > DeepDelve._stats(DeepDelve.__new__(DeepDelve), profile)["max_hp"] * 0.5:
            continue
        if key == "execution" and enemy["hp"] > enemy["max_hp"] * 0.5:
            continue
        if key == "venom_edge" and enemy["status"].get("poison"):
            continue
        if key == "starfire" and enemy["status"].get("burn"):
            continue
        if ability := _available(profile, key):
            return ability
    return None


def battle(class_key: str, floor: int, boss: bool) -> tuple[bool, int, float, int]:
    cog = DeepDelve.__new__(DeepDelve)
    profile = profile_for(class_key, floor)
    enemy = ensure_enemy_intent(boss_for_floor(floor) if boss else enemy_for_floor(floor))
    turns = 0
    starting_potions = profile["potions"]
    while profile["hp"] > 0 and enemy["hp"] > 0 and turns < 50:
        turns += 1
        stats = cog._stats(profile)
        for condition in ("poison", "burn"):
            if enemy["status"].get(condition):
                damage = 4 + profile["level"]
                if condition == "poison":
                    damage += profile["talents"].get("toxicology", 0) * 2
                elif profile["subclass"] == "elementalist":
                    damage = round(damage * 1.5)
                enemy["hp"] -= damage
                enemy["status"][condition] -= 1
        if enemy["hp"] <= 0:
            break
        cast_key = ""
        if profile["hp"] < stats["max_hp"] * 0.32 and profile["potions"]:
            profile["potions"] -= 1
            profile["hp"] = min(stats["max_hp"], profile["hp"] + 35 + profile["level"] * 5)
        elif ability := _choose_ability(profile, enemy):
            cast_key = ability["key"]
            profile["mana"] -= ability["mana"]
            damage, _lines = cog._ability_damage(profile, enemy, stats, cast_key)
            enemy["hp"] -= damage
            profile["skill_cooldowns"][cast_key] = ability["cooldown"]
        else:
            damage, _critical = cog._player_damage(stats, enemy["defense"])
            enemy["hp"] -= damage
        if enemy["hp"] > 0:
            cog._resolve_enemy_intent(profile, enemy, stats)
        cog._advance_cooldowns(profile, exclude=cast_key)
    stats = cog._stats(profile)
    return (
        enemy["hp"] <= 0 and profile["hp"] > 0,
        turns,
        max(0, profile["hp"]) / stats["max_hp"] * 100,
        starting_potions - profile["potions"],
    )


def run(samples: int = 10) -> None:
    random.seed(7331)
    print("floor class     fight  win% turns hp% pots")
    for floor in LEVELS:
        for class_key in GAME_CLASSES:
            for boss in (False, True):
                results = [battle(class_key, floor, boss) for _ in range(samples)]
                print(
                    f"{floor:>5} {class_key:<9} {'boss' if boss else 'normal':<6} "
                    f"{mean(row[0] for row in results) * 100:>5.1f} "
                    f"{mean(row[1] for row in results):>5.2f} "
                    f"{mean(row[2] for row in results):>5.1f} "
                    f"{mean(row[3] for row in results):>4.2f}",
                )


if __name__ == "__main__":
    run()
