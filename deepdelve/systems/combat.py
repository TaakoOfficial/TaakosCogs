"""Enemy intention and tactical-combat helpers."""

from __future__ import annotations

import random
from typing import Any

INTENTS: tuple[dict[str, Any], ...] = (
    {
        "key": "strike",
        "name": "Measured Strike",
        "emoji": "⚔️",
        "power": 1.0,
        "weight": 38,
        "description": "A standard attack.",
    },
    {
        "key": "heavy",
        "name": "Crushing Blow",
        "emoji": "💥",
        "power": 1.65,
        "weight": 18,
        "description": "Heavy damage; guarding is strongly advised.",
    },
    {
        "key": "flurry",
        "name": "Savage Flurry",
        "emoji": "🗡️",
        "power": 0.62,
        "hits": 2,
        "weight": 15,
        "description": "Two attacks that punish low defense.",
    },
    {
        "key": "guard",
        "name": "Defensive Stance",
        "emoji": "🛡️",
        "power": 0.65,
        "weight": 12,
        "description": "Attack lightly, then gain armor.",
    },
    {
        "key": "hex",
        "name": "Withering Hex",
        "emoji": "🕸️",
        "power": 0.75,
        "weight": 9,
        "description": "Damage with a chance to inflict Curse.",
    },
    {
        "key": "recover",
        "name": "Dark Renewal",
        "emoji": "🩸",
        "power": 0.55,
        "weight": 8,
        "description": "Attack and restore health.",
    },
)


def roll_enemy_intent(
    enemy: dict[str, Any],
    rng: random.Random = random,
) -> dict[str, Any]:
    """Roll a visible enemy action, adjusted for bosses and low health."""
    choices = list(INTENTS)
    weights = [intent["weight"] for intent in choices]
    if enemy.get("boss"):
        for index, intent in enumerate(choices):
            if intent["key"] in {"heavy", "hex", "recover"}:
                weights[index] += 8
    if enemy.get("hp", 1) < enemy.get("max_hp", 1) * 0.3:
        for index, intent in enumerate(choices):
            if intent["key"] == "recover":
                weights[index] += 15
    return dict(rng.choices(choices, weights=weights, k=1)[0])


def ensure_enemy_intent(enemy: dict[str, Any]) -> dict[str, Any]:
    """Ensure old or newly generated encounters have tactical state."""
    enemy.setdefault("status", {})
    enemy.setdefault("guarded", 0)
    enemy.setdefault("intent", roll_enemy_intent(enemy))
    return enemy


def intent_description(enemy: dict[str, Any]) -> str:
    """Format an enemy's telegraphed next action."""
    intent = ensure_enemy_intent(enemy)["intent"]
    return f"{intent['emoji']} **{intent['name']}** — {intent['description']}"
