"""Advanced equipment generation and manipulation."""

from __future__ import annotations

import random
from typing import Any

from deepdelve.advanced_content import ITEM_PREFIXES, ITEM_SETS, ITEM_SUFFIXES, LEGENDARIES
from deepdelve.content import RARITIES, item_stat_line


def apply_advanced_itemization(
    item: dict[str, Any],
    floor: int,
    class_key: str,
    rng: random.Random = random,
) -> dict[str, Any]:
    """Add affixes, sets, legendary identities, and upgrade metadata."""
    item.setdefault("upgrade", 0)
    item.setdefault("enchant", "")
    item.setdefault("identified", True)
    item.setdefault("bound", False)
    item.setdefault("set", "")
    item.setdefault("unique_effect", "")
    rarity = int(item.get("rarity_index", 0))

    if rarity >= 1:
        prefix = dict(rng.choice(ITEM_PREFIXES))
        item["prefix"] = prefix["name"]
        item["name"] = f"{prefix['name']} {item['name']}"
        for stat in ("attack", "defense", "hp", "luck"):
            multiplier = prefix.get(stat, prefix.get("all", 1.0))
            if item.get(stat):
                item[stat] = max(1, round(item[stat] * multiplier))

    if rarity >= 2:
        suffix = dict(rng.choice(ITEM_SUFFIXES))
        item["suffix"] = suffix["name"]
        item["name"] = f"{item['name']} {suffix['name']}"
        item["unique_effect"] = suffix["effect"]
        item["effect_description"] = suffix["description"]

    if rarity >= 3 and rng.random() < 0.35:
        valid_sets = [(key, details) for key, details in ITEM_SETS.items() if class_key in details["classes"]]
        if valid_sets:
            set_key, details = rng.choice(valid_sets)
            item["set"] = set_key
            item["name"] = f"{details['name']} {item['name'].split()[-1]}"

    legendary_chance = 0.08 + min(0.12, floor * 0.002)
    if rarity == 4 and rng.random() < legendary_chance:
        choices = [legendary for legendary in LEGENDARIES if legendary["slot"] == item["slot"]]
        if choices:
            legendary = dict(rng.choice(choices))
            item["name"] = legendary["name"]
            item["unique_effect"] = legendary["effect"]
            item["effect_description"] = legendary["description"]
            item["legendary"] = True
            item["bound"] = True
            for stat in ("attack", "defense", "hp", "luck"):
                if item.get(stat):
                    item[stat] = round(item[stat] * 1.35)
    if rarity >= 2 and not item.get("legendary") and rng.random() < 0.08:
        item["hidden_name"] = item["name"]
        item["name"] = f"Unidentified {item['slot'].title()} Relic"
        item["identified"] = False
    if rarity >= 2 and rng.random() < 0.06:
        item["cursed"] = True
        item["bound"] = True
        for stat in ("attack", "defense", "hp", "luck"):
            if item.get(stat):
                item[stat] = max(1, round(item[stat] * 1.15))
    item["codex_key"] = item["name"].lower().replace(" ", "_")
    return item


def equipment_set_bonuses(equipment: dict[str, Any]) -> tuple[dict[str, int], list[str]]:
    """Calculate numeric bonuses and effect descriptions from equipped sets."""
    counts: dict[str, int] = {}
    for item in equipment.values():
        if item and item.get("set"):
            counts[item["set"]] = counts.get(item["set"], 0) + 1
    bonuses = {"attack": 0, "defense": 0, "hp": 0, "luck": 0, "mana": 0}
    effects = []
    for set_key, count in counts.items():
        details = ITEM_SETS.get(set_key)
        if not details:
            continue
        if count >= 2:
            if set_key == "bulwark":
                bonuses["defense"] += 8
            elif set_key == "nightstalker":
                bonuses["luck"] += 6
            else:
                bonuses["mana"] += 18
            effects.append(f"{details['name']} (2): {details['two']}")
        if count >= 3:
            effects.append(f"{details['name']} (3): {details['three']}")
    return bonuses, effects


def upgrade_cost(item: dict[str, Any]) -> tuple[int, int]:
    """Return currency and shard costs for the next equipment upgrade."""
    level = int(item.get("upgrade", 0))
    rarity = int(item.get("rarity_index", 0))
    return 40 + (level + 1) * 35 + rarity * 25, 2 + level + rarity


def dismantle_rewards(item: dict[str, Any]) -> tuple[int, int]:
    """Return currency and arcane-shard yields from dismantling."""
    rarity = int(item.get("rarity_index", 0))
    return max(1, int(item.get("value", 1)) // 4), 1 + rarity * 2 + int(item.get("upgrade", 0))


def item_detail(item: dict[str, Any]) -> str:
    """Return a rich, mobile-friendly item inspection block."""
    rarity = RARITIES[int(item.get("rarity_index", 0))]
    if not item.get("identified", True):
        return (
            f"{rarity['emoji']} **{item['name']}**\n"
            "*Its identity, attributes, and powers are concealed. "
            "Use the item-identification command to reveal it.*"
        )
    lines = [
        f"{rarity['emoji']} **{item['name']}**",
        f"*{item['rarity']} {item['slot'].title()} • Floor {item.get('floor', 1)} • Upgrade +{item.get('upgrade', 0)}*",
        item_stat_line(item),
    ]
    if item.get("effect_description"):
        lines.append(f"✨ {item['effect_description']}")
    if item.get("set"):
        details = ITEM_SETS.get(item["set"])
        if details:
            lines.append(f"🧩 **Set: {details['name']}**")
    if item.get("enchant"):
        lines.append(f"🔯 Enchantment: **{item['enchant']}**")
    if item.get("bound"):
        lines.append("🔒 Bound")
    if item.get("cursed"):
        lines.append("🩸 Cursed — cannot be unequipped once worn until cleansed")
    return "\n".join(lines)
