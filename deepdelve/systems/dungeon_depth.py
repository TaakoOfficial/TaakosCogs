"""Bestiary, miniboss, rumor, mutator, and run-history helpers."""

from __future__ import annotations

import hashlib
import random
from typing import Any

from deepdelve.loot_content import FLOOR_MUTATORS, MINIBOSSES
from deepdelve.systems.morality import morality_path


def region_index(floor: int) -> int:
    """Return the authored region index for a floor."""
    return min(4, max(0, (max(1, int(floor)) - 1) // 5))


def floor_mutator(floor: int, ascensions: int = 0) -> dict[str, Any]:
    """Return a deterministic modifier for a floor and incarnation."""
    digest = hashlib.sha256(f"{max(1, floor)}:{max(0, ascensions)}".encode()).digest()
    return dict(FLOOR_MUTATORS[digest[0] % len(FLOOR_MUTATORS)])


def apply_miniboss(enemy: dict[str, Any], floor: int, rng: random.Random = random) -> dict[str, Any]:
    """Promote a normal enemy into the current region's named miniboss."""
    definition = MINIBOSSES[region_index(floor)]
    enemy["original_name"] = enemy["name"]
    enemy["name"] = definition["name"]
    enemy["base_name"] = definition["name"]
    enemy["emoji"] = definition["emoji"]
    for stat in ("hp", "attack", "defense"):
        if stat == "hp" and 6 <= floor <= 9:
            endurance = 1.15 + (floor - 6) * 0.03125
        elif stat == "hp" and floor <= 10:
            endurance = max(1.15, 1.5 - max(0, floor - 1) * 0.025)
        else:
            endurance = 1.15 if stat == "hp" else 1.0
        enemy[stat] = max(1, round(int(enemy[stat]) * float(definition[stat]) * endurance))
    enemy["max_hp"] = enemy["hp"]
    enemy["gold"] = round(int(enemy["gold"]) * 2)
    enemy["xp"] = round(int(enemy["xp"]) * 1.8)
    enemy["miniboss"] = True
    enemy["threat_multiplier"] = 1.20
    enemy["codex_key"] = f"miniboss:{region_index(floor)}"
    enemy["affix"] = enemy.get("affix") or {}
    return enemy


def record_bestiary_kill(profile: dict[str, Any], enemy: dict[str, Any]) -> list[str]:
    """Record kills and announce non-power mastery milestones."""
    key = str(enemy.get("codex_key") or enemy.get("base_name") or enemy.get("original_name") or enemy["name"]).lower()
    display_name = enemy.get("base_name") or enemy.get("original_name") or enemy["name"]
    entry = profile.setdefault("bestiary", {}).setdefault(
        key,
        {
            "name": display_name,
            "kills": 0,
            "mastery": 0,
            "affixes": {},
            "min_floor": int(enemy.get("floor", profile.get("floor", 1))),
            "max_floor": int(enemy.get("floor", profile.get("floor", 1))),
            "kind": "boss" if enemy.get("boss") else "miniboss" if enemy.get("miniboss") else "creature",
        },
    )
    entry.setdefault("affixes", {})
    floor = int(enemy.get("floor", profile.get("floor", 1)))
    entry["min_floor"] = min(floor, int(entry.get("min_floor", floor)))
    entry["max_floor"] = max(floor, int(entry.get("max_floor", floor)))
    affix_name = (enemy.get("affix") or {}).get("name")
    if affix_name:
        entry["affixes"][affix_name] = int(entry["affixes"].get(affix_name, 0)) + 1
    entry["kills"] = int(entry.get("kills", 0)) + 1
    milestones = (5, 15, 30)
    lines = []
    for rank, needed in enumerate(milestones, start=1):
        if entry["kills"] >= needed and int(entry.get("mastery", 0)) < rank:
            entry["mastery"] = rank
            labels = ("Observed", "Understood", "Mastered")
            lines.append(
                f"📖 **Bestiary {labels[rank - 1]}:** {entry['name']} — {entry['kills']} defeated; tactical notes updated.",
            )
    return lines


def create_rumor(profile: dict[str, Any], rng: random.Random = random) -> dict[str, Any]:
    """Create a personal hunt tied to the current region."""
    region = region_index(int(profile.get("floor", 1)))
    targets = (4, 5, 6)
    target = rng.choice(targets)
    return {
        "name": ("The Lantern Ledger", "Spores in the Blood", "A Debt of Iron", "Court Without Guests", "Red Ink")[region],
        "description": (
            "Defeat creatures in the Warrens and recover the missing survey marks.",
            "Cull the Crypt's infected dead before the dreaming spores flower.",
            "Break the Foundry's collectors and settle a debt written in brass.",
            "Hunt the nameless courtiers still answering a dead sovereign.",
            "Erase the Unwritten predators named in the cartographer's margin.",
        )[region],
        "region": region,
        "target": target,
        "progress": 0,
        "reward_gold": 80 + int(profile.get("floor", 1)) * 12,
        "reward_shards": 2 + region,
    }


def progress_rumor(profile: dict[str, Any], enemy: dict[str, Any]) -> list[str]:
    """Advance a matching hunt and unlock its regional recipe."""
    rumor = profile.get("active_rumor") or {}
    if not rumor or region_index(int(enemy.get("floor", profile.get("floor", 1)))) != int(rumor["region"]):
        return []
    rumor["progress"] = min(int(rumor["target"]), int(rumor.get("progress", 0)) + 1)
    if rumor["progress"] < rumor["target"]:
        return [f"🗺️ Rumor progress: **{rumor['progress']}/{rumor['target']}**."]
    from deepdelve.systems.armory import recipe_for_region

    recipe_key, recipe = recipe_for_region(int(rumor["region"]))
    profile["gold"] += int(rumor["reward_gold"])
    profile["arcane_shards"] += int(rumor["reward_shards"])
    newly_unlocked = recipe_key not in profile.setdefault("recipes", [])
    if newly_unlocked:
        profile["recipes"].append(recipe_key)
    profile["rumors_completed"] = int(profile.get("rumors_completed", 0)) + 1
    profile["active_rumor"] = {}
    return [
        f"🗺️ **Rumor resolved: {rumor['name']}** — {rumor['reward_gold']} gold, "
        f"{rumor['reward_shards']} shards" + (f", and recipe **{recipe['name']}**." if newly_unlocked else "."),
    ]


def ending_recap(profile: dict[str, Any]) -> list[str]:
    """Summarize the authored history of a completed or ongoing character."""
    campaign = profile.get("campaign", {})
    companions = profile.get("companions", {})
    closest = max(companions.items(), key=lambda pair: int(pair[1].get("bond", 0)), default=None)
    legendary_count = sum(
        1
        for item in [*profile.get("inventory", []), *profile.get("stash", []), *profile.get("equipment", {}).values()]
        if item and item.get("legendary")
    )
    lines = [
        (
            f"**Depth:** Floor {profile.get('deepest_floor', 1)} • "
            f"{profile.get('bosses', 0)} bosses • {profile.get('deaths', 0)} deaths"
        ),
        f"**Legacy:** {profile.get('ascensions', 0)} ascensions • {legendary_count} legendary relics",
        f"**Knowledge:** {len(profile.get('bestiary', {}))} creatures • {len(profile.get('lore', []))} lore fragments",
        f"**Ending:** {str(campaign.get('ending') or 'Still being written').title()}",
        (
            f"**Moral Legacy:** {morality_path(profile)['name']} "
            f"({int(profile.get('morality', 0)):+d}) • {len(profile.get('moral_deeds', []))} remembered deeds"
        ),
    ]
    if closest:
        lines.append(
            f"**Closest Companion:** {closest[0].title()} • Bond {int(closest[1].get('bond', 0))}/100",
        )
    return lines
