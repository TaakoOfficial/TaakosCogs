"""Repeatable Monte Carlo smoke test for DeepDelve's solo combat bands.

Run directly from the repository root:
    python tests/simulate_deepdelve_balance.py
"""

from __future__ import annotations

import argparse
import random
import sys
from pathlib import Path
from statistics import mean

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from deepdelve.advanced_content import ABILITIES, SUBCLASSES
from deepdelve.content import AFFIXES, GAME_CLASSES, RARITIES, boss_for_floor, enemy_for_floor
from deepdelve.deepdelve import DeepDelve
from deepdelve.systems.combat import ensure_enemy_intent
from deepdelve.systems.dungeon_depth import apply_miniboss
from deepdelve.systems.legacy import tenet_effects
from deepdelve.systems.morality import moral_power, use_moral_power

LEVELS = {5: 4, 10: 7, 20: 16, 30: 24, 40: 31}
MORAL_PATHS = {
    "radiant": (70, {"mercy": 25, "honesty": 25, "ambition": 0, "ruthlessness": 0}),
    "pragmatic": (0, {"mercy": 0, "honesty": 25, "ambition": 25, "ruthlessness": 0}),
    "umbral": (-70, {"mercy": 0, "honesty": 0, "ambition": 25, "ruthlessness": 25}),
}
TENET_LOADOUTS = {
    "radiant": ["sheltering_flame", "mercy_repaid", "last_lantern"],
    "pragmatic": ["measured_breath", "even_edge", "balanced_guard"],
    "umbral": ["predators_patience", "borrowed_vigor", "unyielding_claim"],
}
TURN_BANDS = {
    "normal": (3, 6),
    "elite": (5, 9),
    "miniboss": (7, 12),
    "boss": (10, 16),
}
WIN_BANDS = {
    "normal": (90, 98),
    "elite": (80, 92),
    "miniboss": (70, 85),
    "boss": (60, 78),
}
COG = object.__new__(DeepDelve)


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


def profile_for(class_key: str, floor: int, subclass: str, moral_path: str) -> dict:
    level = max(10, LEVELS[floor]) if subclass else LEVELS[floor]
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
        "subclass": subclass,
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
        "morality": MORAL_PATHS[moral_path][0],
        "convictions": dict(MORAL_PATHS[moral_path][1]),
        "moral_deeds": [{"key": "simulation"}] * 12,
        "deed_counts": {},
        "conviction_fatigue": 0,
        "legacy": {
            "resolve": 0,
            "resolve_earned": 0,
            "unlocked_tenets": list(TENET_LOADOUTS[moral_path]),
            "active_tenets": list(TENET_LOADOUTS[moral_path]),
            "faction_reputation": {"lantern": 0, "concord": 0, "court": 0},
            "oath": "",
            "oath_board_date": "",
            "oath_board": [],
            "redemption": {},
            "consequence_flags": [],
            "resolve_sources": [],
            "service_dates": {},
        },
    }
    stats = COG._stats(profile)
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
        if key == "last_stand" and profile["hp"] > COG._stats(profile)["max_hp"] * 0.5:
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


def enemy_for_kind(floor: int, kind: str) -> dict:
    """Create each encounter tier without relying on the live elite roll chance."""
    if kind == "boss":
        return boss_for_floor(floor)
    enemy = enemy_for_floor(floor)
    if kind == "elite":
        affix = dict(random.choice(AFFIXES))
        enemy["name"] = f"{affix['name']} {enemy['name']}"
        enemy["affix"] = affix
        for field in ("hp", "attack", "defense"):
            endurance = max(1.25, 1.65 - max(0, floor - 1) * 0.015) if field == "hp" else 1.0
            enemy[field] = max(1, round(enemy[field] * affix[field] * endurance))
        enemy["max_hp"] = enemy["hp"]
        enemy["threat_multiplier"] = 1.25
    elif kind == "miniboss":
        enemy = apply_miniboss(enemy, floor)
    return enemy


def fight(profile: dict, enemy: dict) -> tuple[bool, int, float, int]:
    """Resolve one fight while preserving expedition health, mana, and potions."""
    cog = COG
    enemy = ensure_enemy_intent(enemy)
    profile["combat_flags"] = {}
    turns = 0
    starting_potions = profile["potions"]
    while profile["hp"] > 0 and enemy["hp"] > 0 and turns < 60:
        turns += 1
        stats = cog._stats(profile)
        legacy_effects = tenet_effects(profile)
        if (
            legacy_effects.get("blood_mana")
            and not profile["combat_flags"].get("tenet_blood_price")
            and profile["mana"] <= stats["max_mana"] - int(legacy_effects["blood_mana"])
        ):
            cost = max(1, round(stats["max_hp"] * int(legacy_effects["blood_cost_percent"]) / 100))
            if profile["hp"] > cost:
                profile["combat_flags"]["tenet_blood_price"] = True
                profile["hp"] -= cost
                profile["mana"] = min(stats["max_mana"], profile["mana"] + int(legacy_effects["blood_mana"]))
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
        conviction = moral_power(profile)
        if conviction["available"] and turns >= 4 and (enemy.get("boss") or enemy.get("miniboss")):
            use_moral_power(profile, enemy, stats)
        elif profile["hp"] < stats["max_hp"] * 0.45 and profile["potions"]:
            profile["potions"] -= 1
            profile["hp"] = min(stats["max_hp"], profile["hp"] + 35 + profile["level"] * 5)
        elif enemy.get("intent", {}).get("key") == "heavy" and profile["combat_flags"].get("tenet_last_action") != "defend":
            guard = 0.55 + min(0.2, stats["defense"] * 0.008)
            if profile["hp"] <= stats["max_hp"] / 2:
                guard += float(legacy_effects.get("guard_bonus", 0))
            profile["combat_flags"]["guard"] = guard
            profile["combat_flags"]["tenet_last_action"] = "defend"
            profile["mana"] = min(stats["max_mana"], profile["mana"] + 2)
        elif ability := _choose_ability(profile, enemy):
            cast_key = ability["key"]
            profile["mana"] -= ability["mana"]
            damage, _lines = cog._ability_damage(profile, enemy, stats, cast_key)
            if (
                profile["combat_flags"].get("tenet_last_action") == "defend"
                and legacy_effects.get("post_defend_damage_percent")
            ):
                damage = round(damage * (1 + int(legacy_effects["post_defend_damage_percent"]) / 100))
            if (
                enemy.get("boss")
                and enemy["hp"] <= enemy["max_hp"] * 0.3
                and legacy_effects.get("execute_percent")
            ):
                damage = round(damage * (1 + int(legacy_effects["execute_percent"]) / 100))
            enemy["hp"] -= damage
            profile["combat_flags"]["tenet_last_action"] = "ability"
            profile["skill_cooldowns"][cast_key] = ability["cooldown"]
        else:
            damage, _critical = cog._player_damage(stats, enemy["defense"])
            previous = profile["combat_flags"].get("tenet_last_action")
            if not profile.get("status") and not enemy.get("status") and legacy_effects.get("clean_attack_percent"):
                damage = round(damage * (1 + int(legacy_effects["clean_attack_percent"]) / 100))
            if previous == "defend" and legacy_effects.get("post_defend_damage_percent"):
                damage = round(damage * (1 + int(legacy_effects["post_defend_damage_percent"]) / 100))
            if (
                enemy.get("boss")
                and enemy["hp"] <= enemy["max_hp"] * 0.3
                and legacy_effects.get("execute_percent")
            ):
                damage = round(damage * (1 + int(legacy_effects["execute_percent"]) / 100))
            if previous == "ability" and legacy_effects.get("alternating_guard"):
                profile["combat_flags"]["guard"] = max(
                    float(profile["combat_flags"].get("guard", 0)),
                    float(legacy_effects["alternating_guard"]),
                )
            enemy["hp"] -= damage
            profile["combat_flags"]["tenet_last_action"] = "basic"
        if enemy["hp"] > 0:
            cog._resolve_enemy_intent(profile, enemy, stats)
        cog._advance_cooldowns(profile, exclude=cast_key)
    stats = cog._stats(profile)
    won = enemy["hp"] <= 0 and profile["hp"] > 0
    if won:
        if enemy.get("boss"):
            profile["conviction_fatigue"] = 0
        elif not profile["combat_flags"].get("moral_power_used") and profile["conviction_fatigue"] > 0:
            profile["conviction_fatigue"] -= 1
    return (
        won,
        turns,
        max(0, profile["hp"]) / stats["max_hp"] * 100,
        starting_potions - profile["potions"],
    )


def battle(class_key: str, subclass: str, moral_path: str, floor: int, kind: str) -> tuple[bool, int, float, int]:
    return fight(profile_for(class_key, floor, subclass, moral_path), enemy_for_kind(floor, kind))


def expedition(class_key: str, subclass: str, moral_path: str, floor: int) -> tuple[bool, int, float, int, int]:
    """Run a five-encounter boss-floor gauntlet with real resource attrition."""
    profile = profile_for(class_key, floor, subclass, moral_path)
    profile["potions"] = 5
    total_turns = 0
    cleared = 0
    starting_potions = profile["potions"]
    for kind in ("normal", "normal", "elite", "miniboss", "boss"):
        won, turns, _hp, _potions = fight(profile, enemy_for_kind(floor, kind))
        total_turns += turns
        if not won:
            break
        cleared += 1
        if kind != "boss":
            stats = COG._stats(profile)
            profile["mana"] = min(
                stats["max_mana"],
                profile["mana"] + max(1, round(stats["max_mana"] * 0.04)),
            )
    stats = COG._stats(profile)
    return (
        cleared == 5,
        cleared,
        max(0, profile["hp"]) / stats["max_hp"] * 100,
        starting_potions - profile["potions"],
        total_turns,
    )


def run(samples: int = 3, *, full_matrix: bool = False) -> None:
    random.seed(7331)
    print("SINGLE ENCOUNTERS")
    print("floor class     subclass     morality  fight     win% turns target  hp% pots")
    for floor in LEVELS:
        for class_key in GAME_CLASSES:
            subclasses = (
                tuple(SUBCLASSES[class_key])
                if full_matrix and floor >= 10
                else ("",)
                if floor < 10
                else (next(iter(SUBCLASSES[class_key])),)
            )
            paths = tuple(MORAL_PATHS) if full_matrix else ("pragmatic",)
            for subclass in subclasses:
                for moral_path in paths:
                    for kind in ("normal", "elite", "miniboss", "boss"):
                        results = [battle(class_key, subclass, moral_path, floor, kind) for _ in range(samples)]
                        average_turns = mean(row[1] for row in results)
                        low, high = TURN_BANDS[kind]
                        target = "OK" if low <= average_turns <= high else "FAST" if average_turns < low else "SLOW"
                        print(
                            f"{floor:>5} {class_key:<9} {subclass:<12} {moral_path:<9} {kind:<8} "
                            f"{mean(row[0] for row in results) * 100:>5.1f} "
                            f"{average_turns:>5.2f} {target:>6} "
                            f"{mean(row[2] for row in results):>5.1f} "
                            f"{mean(row[3] for row in results):>4.2f}",
                        )
    print("\nPREPARED FIVE-COMBAT ATTRITION STRESS TEST")
    print("floor class     subclass     morality  clear% rooms  hp% pots turns")
    for floor in LEVELS:
        for class_key in GAME_CLASSES:
            subclasses = (
                tuple(SUBCLASSES[class_key])
                if full_matrix and floor >= 10
                else ("",)
                if floor < 10
                else (next(iter(SUBCLASSES[class_key])),)
            )
            paths = tuple(MORAL_PATHS) if full_matrix else ("pragmatic",)
            for subclass in subclasses:
                for moral_path in paths:
                    results = [expedition(class_key, subclass, moral_path, floor) for _ in range(samples)]
                    print(
                        f"{floor:>5} {class_key:<9} {subclass:<12} {moral_path:<9} "
                        f"{mean(row[0] for row in results) * 100:>6.1f} "
                        f"{mean(row[1] for row in results):>5.2f} "
                        f"{mean(row[2] for row in results):>4.1f} "
                        f"{mean(row[3] for row in results):>4.2f} "
                        f"{mean(row[4] for row in results):>5.1f}",
                    )


def release_gate(samples: int = 500) -> list[str]:
    """Run the high-sample aggregate gate with common seeds across moral paths."""
    buckets = {
        (kind, path): []
        for kind in TURN_BANDS
        for path in MORAL_PATHS
    }
    for floor_index, floor in enumerate(LEVELS):
        for class_index, class_key in enumerate(GAME_CLASSES):
            subclasses = ("",) if floor < 10 else tuple(SUBCLASSES[class_key])
            for subclass_index, subclass in enumerate(subclasses):
                for kind_index, kind in enumerate(TURN_BANDS):
                    for path in MORAL_PATHS:
                        for trial in range(samples):
                            random.seed(
                                880_000
                                + floor_index * 100_000
                                + class_index * 10_000
                                + subclass_index * 1_000
                                + kind_index * samples
                                + trial,
                            )
                            buckets[(kind, path)].append(
                                battle(class_key, subclass, path, floor, kind),
                            )

    violations = []
    print("DEEPDELVE 5.0 HIGH-SAMPLE RELEASE GATE")
    print("fight      morality   win%   turns   win target  turn target")
    for kind in TURN_BANDS:
        path_metrics = {}
        for path in MORAL_PATHS:
            results = buckets[(kind, path)]
            win_rate = mean(row[0] for row in results) * 100
            turns = mean(row[1] for row in results)
            path_metrics[path] = (win_rate, turns)
            win_ok = WIN_BANDS[kind][0] <= win_rate <= WIN_BANDS[kind][1]
            turns_ok = TURN_BANDS[kind][0] <= turns <= TURN_BANDS[kind][1]
            print(
                f"{kind:<10} {path:<10} {win_rate:>5.2f} {turns:>7.3f} "
                f"{'OK' if win_ok else 'FAIL':>10} {'OK' if turns_ok else 'FAIL':>12}",
            )
            if not win_ok:
                violations.append(f"{kind}/{path} win rate {win_rate:.2f}%")
            if not turns_ok:
                violations.append(f"{kind}/{path} duration {turns:.3f}")
        win_values = [metric[0] for metric in path_metrics.values()]
        turn_values = [metric[1] for metric in path_metrics.values()]
        win_spread = max(win_values) - min(win_values)
        turn_spread = max(turn_values) - min(turn_values)
        if win_spread > 3:
            violations.append(f"{kind} moral win spread {win_spread:.2f}pp")
        if turn_spread > 0.5:
            violations.append(f"{kind} moral duration spread {turn_spread:.3f}")
        print(f"{'':<10} {'path spread':<10} {win_spread:>5.2f} {turn_spread:>7.3f}")
    return violations


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--samples", type=int, default=3, help="Trials per class, floor, and encounter.")
    parser.add_argument("--full-matrix", action="store_true", help="Run all 9 subclasses across all 3 moral paths.")
    parser.add_argument(
        "--release-gate",
        action="store_true",
        help="Run the concise high-sample release gate instead of the detailed report.",
    )
    arguments = parser.parse_args()
    if arguments.release_gate:
        failures = release_gate(max(1, arguments.samples))
        if failures:
            print("\nFAILURES")
            for failure in failures:
                print(f"- {failure}")
            raise SystemExit(1)
        print("\nPASS — encounter, duration, and moral-equivalence targets satisfied.")
    else:
        run(max(1, arguments.samples), full_matrix=arguments.full_matrix)
