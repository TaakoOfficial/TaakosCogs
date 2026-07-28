"""Origins, loot comparison, collections, consumables, and storage helpers."""

from __future__ import annotations

import random
from typing import Any

from deepdelve.content import RARITIES
from deepdelve.loot_content import (
    BOSS_RELICS,
    CONSUMABLES,
    RECIPES,
    REGIONAL_BASES,
    STARTER_WEAPONS,
)


def starter_options(class_key: str) -> dict[str, dict[str, Any]]:
    """Return the three origin weapons available to a class."""
    return STARTER_WEAPONS.get(class_key, {})


def create_starter_item(class_key: str, choice: str, rng: random.Random = random) -> dict[str, Any]:
    """Create a bound, non-tradeable floor-one origin weapon."""
    definition = starter_options(class_key)[choice]
    return {
        "id": f"{rng.randrange(16**8):08x}",
        "name": definition["name"],
        "slot": "weapon",
        "rarity": "Origin",
        "rarity_index": 0,
        "attack": int(definition.get("attack", 0)),
        "defense": int(definition.get("defense", 0)),
        "hp": int(definition.get("hp", 0)),
        "luck": int(definition.get("luck", 0)),
        "value": 0,
        "floor": 1,
        "upgrade": 0,
        "upgrade_cap": 3,
        "identified": True,
        "bound": True,
        "origin": True,
        "unique_effect": definition["effect"],
        "effect_description": definition["description"],
        "codex_key": f"origin:{class_key}:{choice}",
    }


def regional_base_name(floor: int, slot: str, rng: random.Random = random) -> str:
    """Choose an authored equipment base from the item's region."""
    index = min(len(REGIONAL_BASES) - 1, max(0, (max(1, floor) - 1) // 5))
    return rng.choice(REGIONAL_BASES[index][slot])


def item_power(item: dict[str, Any]) -> int:
    """Estimate comparable item power without treating utility as free raw stats."""
    raw = int(item.get("attack", 0)) * 4 + int(item.get("defense", 0)) * 4 + int(item.get("hp", 0)) + int(item.get("luck", 0)) * 3
    effect = 8 + int(item.get("floor", 1)) // 2 if item.get("unique_effect") else 0
    enchant = 4 + int(item.get("floor", 1)) // 4 if item.get("enchant_effect") else 0
    set_value = 6 + int(item.get("floor", 1)) // 3 if item.get("set") else 0
    return max(1, raw + effect + enchant + set_value)


def comparison_line(item: dict[str, Any], equipped: dict[str, Any] | None) -> str:
    """Format a concise power comparison against the equipped item."""
    current = item_power(equipped) if equipped else 0
    difference = item_power(item) - current
    if not equipped:
        return f"🆕 **Power {item_power(item)}** — empty {item['slot']} slot"
    marker = "▲" if difference > 0 else "▼" if difference < 0 else "◆"
    sign = "+" if difference > 0 else ""
    return f"{marker} **Power {item_power(item)}** ({sign}{difference} vs {equipped['name']})"


def should_auto_dismantle(profile: dict[str, Any], item: dict[str, Any]) -> bool:
    """Honor a player's rarity threshold without destroying special equipment."""
    threshold = int(profile.get("auto_dismantle", -1))
    return (
        threshold >= 0
        and int(item.get("rarity_index", 0)) <= threshold
        and not item.get("legendary")
        and not item.get("set")
        and not item.get("origin")
        and str(item.get("id")) not in profile.get("favorite_items", [])
    )


def boss_relic_for(
    enemy_name: str,
    floor: int,
    rng: random.Random = random,
) -> dict[str, Any] | None:
    """Create a source-matched boss relic with floor-scaled, budgeted stats."""
    choices = [relic for relic in BOSS_RELICS if relic["source"].lower() in enemy_name.lower()]
    if not choices:
        return None
    relic = rng.choice(choices)
    primary = max(3, round((2 + floor * 0.65) * 2.25))
    item = {
        "id": f"{rng.randrange(16**8):08x}",
        "name": relic["name"],
        "slot": relic["slot"],
        "rarity": "Legendary",
        "rarity_index": 4,
        "attack": 0,
        "defense": 0,
        "hp": 0,
        "luck": 0,
        "value": round((12 + floor * 7) * RARITIES[4]["multiplier"]),
        "floor": floor,
        "upgrade": 0,
        "identified": True,
        "bound": True,
        "legendary": True,
        "boss_relic": True,
        "source": enemy_name,
        "unique_effect": relic["effect"],
        "effect_description": relic["description"],
        "codex_key": f"boss:{relic['name'].lower().replace(' ', '_')}",
    }
    if relic["slot"] == "weapon":
        item["attack"] = primary
        item["luck"] = 2
    elif relic["slot"] == "armor":
        item["defense"] = primary
        item["hp"] = round(primary * 2.4)
    else:
        item["luck"] = max(3, round(primary * 0.55))
        item["attack"] = round(primary * 0.5)
    return item


def roll_consumable(floor: int, rng: random.Random = random) -> tuple[str, dict[str, Any]]:
    """Roll a consumable from the current or immediately previous region."""
    region = min(4, max(0, (max(1, floor) - 1) // 5))
    choices = [(key, item) for key, item in CONSUMABLES.items() if item["region"] in {region, max(0, region - 1)}]
    return rng.choice(choices)


def use_consumable(profile: dict[str, Any], key: str) -> dict[str, Any]:
    """Apply one consumable to current character or combat state."""
    definition = CONSUMABLES.get(key)
    owned = int(profile.get("consumables", {}).get(key, 0))
    if not definition or owned < 1:
        return {"ok": False, "message": "You do not carry that consumable."}
    enemy = profile.get("encounter") or {}
    effect = definition["effect"]
    power = int(definition["power"])
    stats = profile.get("_calculated_stats", {})
    if effect in {"damage", "burn", "sunder", "reroll", "evade", "guard", "attack", "luck", "cooldown", "escape"} and not enemy:
        return {"ok": False, "message": "That item can only be used during combat."}
    if effect == "escape" and enemy.get("boss"):
        return {"ok": False, "message": "The Margin Scroll cannot escape a sealed boss chamber."}
    if effect == "heal" and int(profile["hp"]) >= int(stats.get("max_hp", profile["hp"])):
        return {"ok": False, "message": "You are already at full health."}
    if effect == "mana" and int(profile["mana"]) >= int(stats.get("max_mana", profile["mana"])):
        return {"ok": False, "message": "Your mana is already full."}
    if effect == "cleanse" and not profile.get("status"):
        return {"ok": False, "message": "You have no condition to cleanse."}
    profile["consumables"][key] = owned - 1
    flags = profile.setdefault("combat_flags", {})
    if effect == "heal":
        maximum = int(stats.get("max_hp", profile.get("hp", 1)))
        amount = min(maximum - int(profile["hp"]), power + int(profile.get("level", 1)) * 2)
        profile["hp"] += amount
        message = f"Restore **{amount} health**."
    elif effect == "mana":
        maximum = int(stats.get("max_mana", profile.get("mana", 0)))
        amount = min(maximum - int(profile["mana"]), power)
        profile["mana"] += amount
        message = f"Restore **{amount} mana**."
    elif effect == "cleanse":
        profile["status"] = {}
        message = "Poison and Curse are cleansed."
    elif effect == "damage":
        enemy["hp"] -= power + int(profile.get("floor", 1))
        message = f"The enemy suffers **{power + int(profile.get('floor', 1))} damage**."
    elif effect == "burn":
        enemy.setdefault("status", {})["burn"] = max(enemy.get("status", {}).get("burn", 0), power)
        message = f"The enemy Burns for **{power} turns**."
    elif effect == "sunder":
        enemy["hp"] -= power
        removed = max(1, round(int(enemy.get("defense", 0)) * 0.25))
        enemy["defense"] = max(0, int(enemy.get("defense", 0)) - removed)
        message = f"Deal **{power} damage** and destroy **{removed} armor**."
    elif effect == "reroll":
        flags["reroll_intent"] = True
        message = "The enemy's intention fractures."
    elif effect == "evade":
        flags["evade"] = True
        message = "The next enemy attack will miss."
    elif effect == "guard":
        flags["guard"] = power / 100
        message = f"Gain **{power}% guard** against the next attack."
    elif effect in {"attack", "luck"}:
        flags[f"consumable_{effect}"] = max(int(flags.get(f"consumable_{effect}", 0)), power)
        message = f"Gain **{power} {effect.upper()}** for this battle."
    elif effect == "cooldown":
        if not any(int(remaining) > 0 for remaining in profile.get("skill_cooldowns", {}).values()):
            profile["consumables"][key] = owned
            return {"ok": False, "message": "No ability is currently cooling down."}
        for ability, remaining in list(profile.get("skill_cooldowns", {}).items()):
            profile["skill_cooldowns"][ability] = max(0, int(remaining) - power)
        message = f"All cooldowns advance by **{power}**."
    else:
        profile["encounter"] = {}
        message = "The page folds around you. You escape safely."
    return {"ok": True, "message": f"{definition['emoji']} **{definition['name']}** — {message}"}


def recipe_for_region(region: int) -> tuple[str, dict[str, Any]]:
    """Return the unique recipe associated with a region."""
    return next((key, recipe) for key, recipe in RECIPES.items() if int(recipe["region"]) == int(region))
