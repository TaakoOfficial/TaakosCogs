"""Dungeon puzzle generation and resolution."""

from __future__ import annotations

import random
from typing import Any

from deepdelve.expansion_content import PUZZLES


def puzzle_for_floor(floor: int, solved: list[str], rng: random.Random = random) -> dict[str, Any]:
    """Choose a serializable puzzle suitable for a floor."""
    choices = [
        puzzle for puzzle in PUZZLES if puzzle["min_floor"] <= floor <= puzzle["max_floor"] and puzzle["key"] not in solved
    ]
    if not choices:
        choices = [puzzle for puzzle in PUZZLES if puzzle["min_floor"] <= floor <= puzzle["max_floor"]]
    puzzle = dict(rng.choice(choices))
    puzzle["options"] = dict(puzzle["options"])
    puzzle["attempts"] = 0
    return puzzle


def resolve_puzzle(
    profile: dict[str, Any],
    answer: str,
    *,
    reward_multiplier: float = 1.0,
) -> dict[str, Any]:
    """Resolve an active puzzle and apply its consequences."""
    puzzle = profile.get("active_puzzle") or {}
    if not puzzle:
        return {"ok": False, "message": "No puzzle is currently waiting for an answer."}
    if answer not in puzzle.get("options", {}):
        return {"ok": False, "message": "That is not one of the puzzle's possible answers."}
    if answer == puzzle["answer"]:
        streak = int(profile.get("puzzle_streak", 0)) + 1
        base = 30 + int(profile.get("floor", 1)) * 8 + streak * 5
        profession = profile.get("profession", {}).get("key")
        if profession == "cartographer":
            reward_multiplier *= 1.2
        companion = profile.get("active_companion")
        if companion == "mote":
            reward_multiplier *= 1.15
        reward = round(base * reward_multiplier)
        shards = 1 + int(profile.get("floor", 1)) // 10
        profile["gold"] += reward
        profile["arcane_shards"] = int(profile.get("arcane_shards", 0)) + shards
        profile["puzzle_streak"] = streak
        if puzzle["key"] not in profile["solved_puzzles"]:
            profile["solved_puzzles"].append(puzzle["key"])
        profile["active_puzzle"] = {}
        profile["rooms_cleared"] += 1
        return {
            "ok": True,
            "solved": True,
            "message": (
                f"**Correct: {puzzle['success']}.** Stone yields to insight. "
                f"You recover **{reward} gold** and **{shards} arcane shard(s)**. "
                f"Puzzle streak: **{streak}**."
            ),
        }
    puzzle["attempts"] = int(puzzle.get("attempts", 0)) + 1
    profile["puzzle_streak"] = 0
    damage = 5 + int(profile.get("floor", 1)) * 2
    profile["hp"] -= damage
    if puzzle["attempts"] >= 2:
        profile["active_puzzle"] = {}
        profile["rooms_cleared"] += 1
        return {
            "ok": True,
            "solved": False,
            "message": (
                f"The mechanism rejects your answer and seals forever. You suffer **{damage} damage**.\n"
                f"Lost solution: **{puzzle['success']}**."
            ),
        }
    return {
        "ok": True,
        "solved": False,
        "message": f"The chamber answers with pain: **{damage} damage**. Hint: *{puzzle['hint']}*",
    }
