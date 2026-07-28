"""Cross-reference and balance validation for DeepDelve 5.0 content."""

from __future__ import annotations

from collections import Counter

from deepdelve.living_content import (
    CHARACTER_ARCS,
    CONTRACT_TEMPLATES,
    DUNGEON_EVENTS,
    FACTION_QUESTS,
    LIVING_BOSSES,
    LIVING_CONSUMABLES,
    LIVING_ENEMIES,
    LIVING_ITEM_SETS,
    LIVING_MINIBOSSES,
    LIVING_PUZZLES,
    LIVING_RECIPES,
    LIVING_RELICS,
    MAIN_CAMPAIGN_ACTS,
    NAMED_DUNGEONS,
    SEASON_CHAPTERS,
    TENETS,
)
from deepdelve.systems.economy import reward_budget

CONTENT_MINIMUMS = {
    "campaign_scenes": 36,
    "campaign_decisions": 18,
    "faction_quests": 24,
    "character_quests": 27,
    "dungeons": 10,
    "events": 60,
    "moral_events": 30,
    "puzzles": 15,
    "enemies": 45,
    "minibosses": 15,
    "bosses": 10,
    "sets": 12,
    "relics": 30,
    "consumables": 24,
    "recipes": 30,
    "contracts": 36,
    "seasons": 12,
    "tenets": 18,
}


def content_counts() -> dict[str, int]:
    """Return measurable release-package counts."""
    return {
        "campaign_scenes": sum(len(act["scenes"]) for act in MAIN_CAMPAIGN_ACTS),
        "campaign_decisions": sum(len(act["decisions"]) for act in MAIN_CAMPAIGN_ACTS),
        "faction_quests": sum(len(arc) for arc in FACTION_QUESTS.values()),
        "character_quests": sum(len(arc) for arc in CHARACTER_ARCS.values()),
        "dungeons": len(NAMED_DUNGEONS),
        "events": len(DUNGEON_EVENTS),
        "moral_events": sum(bool(event["moral_choice"]) for event in DUNGEON_EVENTS.values()),
        "puzzles": len(LIVING_PUZZLES),
        "enemies": len(LIVING_ENEMIES),
        "minibosses": len(LIVING_MINIBOSSES),
        "bosses": len(LIVING_BOSSES),
        "sets": len(LIVING_ITEM_SETS),
        "relics": len(LIVING_RELICS),
        "consumables": len(LIVING_CONSUMABLES),
        "recipes": len(LIVING_RECIPES),
        "contracts": len(CONTRACT_TEMPLATES),
        "seasons": len(SEASON_CHAPTERS),
        "tenets": len(TENETS),
    }


def validate_content() -> list[str]:
    """Return every content-registry violation."""
    errors = []
    counts = content_counts()
    for key, minimum in CONTENT_MINIMUMS.items():
        if counts[key] < minimum:
            errors.append(f"{key}: expected at least {minimum}, found {counts[key]}")
    paths = Counter(tenet["path"] for tenet in TENETS.values())
    if paths != {"radiant": 6, "pragmatic": 6, "umbral": 6}:
        errors.append(f"tenet path distribution is not 6/6/6: {dict(paths)}")
    for key, dungeon in NAMED_DUNGEONS.items():
        if dungeon["miniboss"] not in LIVING_MINIBOSSES:
            errors.append(f"{key}: unknown miniboss {dungeon['miniboss']}")
        if dungeon["boss"] not in LIVING_BOSSES:
            errors.append(f"{key}: unknown boss {dungeon['boss']}")
        elif LIVING_BOSSES[dungeon["boss"]]["dungeon"] != key:
            errors.append(f"{key}: boss backlink does not match")
        if int(dungeon["rooms"]) < 5 or not dungeon["checkpoints"]:
            errors.append(f"{key}: dungeon lacks a meaningful route/checkpoint structure")
    for faction, arc in FACTION_QUESTS.items():
        budgets = [reward_budget(quest["reward"]) for quest in arc]
        if any(value <= 0 for value in budgets):
            errors.append(f"{faction}: non-positive quest reward budget")
        if [quest["stage"] for quest in arc] != list(range(1, 9)):
            errors.append(f"{faction}: faction quest transitions are not sequential")
    for character, arc in CHARACTER_ARCS.items():
        if [quest["stage"] for quest in arc] != [1, 2, 3]:
            errors.append(f"{character}: character quest transitions are not sequential")
    for act in MAIN_CAMPAIGN_ACTS:
        if len(act["scenes"]) != 6 or len(act["decisions"]) != 3:
            errors.append(f"{act['key']}: campaign act must contain six scenes and three decisions")
        for decision in act["decisions"]:
            if set(decision["options"]) != {"mercy", "honesty", "ambition", "ruthlessness"}:
                errors.append(f"{decision['key']}: incomplete conviction routes")
    for key, event in DUNGEON_EVENTS.items():
        if not event.get("text") or not event.get("purpose"):
            errors.append(f"{key}: event has no narrative/build purpose")
        if event["moral_choice"] and set(event["options"]) != {"mercy", "honesty", "ambition", "ruthlessness"}:
            errors.append(f"{key}: moral event lacks equivalent conviction routes")
    for key, puzzle in LIVING_PUZZLES.items():
        if len(puzzle.get("solutions", ())) < 2:
            errors.append(f"{key}: puzzle needs multiple valid solutions")
    for key, enemy in LIVING_ENEMIES.items():
        if not enemy.get("tactic") or not enemy.get("counter") or not enemy.get("codex_unlocks"):
            errors.append(f"{key}: enemy is only a renamed stat block")
    for key, details in LIVING_ITEM_SETS.items():
        slots = {piece["slot"] for piece in details.get("pieces", ())}
        if slots != {"weapon", "armor", "charm"} or not details.get("identity"):
            errors.append(f"{key}: equipment set lacks three purposeful pieces")
    for key, relic in LIVING_RELICS.items():
        if not relic.get("bound") or not relic.get("description") or not relic.get("effect"):
            errors.append(f"{key}: relic lacks a bound tactical identity")
    supported_consumable_effects = {"guard", "reroll", "cleanse", "mana", "escape"}
    for key, consumable in LIVING_CONSUMABLES.items():
        if consumable.get("effect") not in supported_consumable_effects or int(consumable.get("power", 0)) <= 0:
            errors.append(f"{key}: unsupported consumable effect")
    for key, recipe in LIVING_RECIPES.items():
        if int(recipe.get("gold_cost", 0)) <= 0 or not recipe.get("materials") or not recipe.get("output"):
            errors.append(f"{key}: incomplete recipe cost or output")
    for key, contract in CONTRACT_TEMPLATES.items():
        if int(contract["energy_budget"]) > 12 or int(contract["target"]) <= 0:
            errors.append(f"{key}: contract exceeds daily objective energy budget")
    for chapter in SEASON_CHAPTERS:
        if not chapter["permanent"] or int(chapter["energy_budget"]) > 12:
            errors.append(f"{chapter['key']}: season is not permanent or exceeds daily energy budget")
    all_keys = [
        *TENETS,
        *NAMED_DUNGEONS,
        *DUNGEON_EVENTS,
        *LIVING_PUZZLES,
        *LIVING_ENEMIES,
        *LIVING_MINIBOSSES,
        *LIVING_BOSSES,
        *LIVING_ITEM_SETS,
        *LIVING_RELICS,
        *LIVING_CONSUMABLES,
        *LIVING_RECIPES,
        *CONTRACT_TEMPLATES,
    ]
    if len(all_keys) != len(set(all_keys)):
        errors.append("content keys collide across registries")
    return errors
