"""Atlas discovery, named dungeons, routes, and checkpoints."""

from __future__ import annotations

from typing import Any

from deepdelve.content import boss_for_floor, enemy_for_floor
from deepdelve.living_content import (
    DUNGEON_EVENTS,
    LIVING_BOSSES,
    LIVING_ENEMIES,
    LIVING_MINIBOSSES,
    LIVING_PUZZLES,
    NAMED_DUNGEONS,
)
from deepdelve.systems.dungeon_depth import apply_miniboss
from deepdelve.systems.morality import record_deed


def ensure_atlas(profile: dict[str, Any]) -> dict[str, Any]:
    """Normalize and return persistent Atlas state."""
    state = profile.setdefault(
        "atlas",
        {"discovered": [], "completed": [], "shortcuts": [], "active_dungeon": {}, "clues": {}},
    )
    state.setdefault("discovered", [])
    state.setdefault("completed", [])
    state.setdefault("shortcuts", [])
    state.setdefault("active_dungeon", {})
    state.setdefault("clues", {})
    for key, dungeon in NAMED_DUNGEONS.items():
        if int(profile.get("deepest_floor", 1)) >= int(dungeon["floor"]) and key not in state["discovered"]:
            state["discovered"].append(key)
    return state


def atlas_locations(profile: dict[str, Any]) -> list[dict[str, Any]]:
    """Return all locations with explicit lock reasons."""
    state = ensure_atlas(profile)
    return [
        {
            "key": key,
            **dungeon,
            "discovered": key in state["discovered"],
            "completed": key in state["completed"],
            "locked_reason": "" if key in state["discovered"] else f"Reach floor {dungeon['floor']}.",
        }
        for key, dungeon in NAMED_DUNGEONS.items()
    ]


def enter_dungeon(profile: dict[str, Any], key: str) -> tuple[bool, str]:
    """Enter a discovered named dungeon."""
    state = ensure_atlas(profile)
    dungeon = NAMED_DUNGEONS.get(key)
    if not dungeon:
        return False, "Unknown named dungeon."
    if key not in state["discovered"]:
        return False, f"Reach floor {dungeon['floor']} to discover this route."
    if state["active_dungeon"]:
        return False, "Finish or abandon the current named dungeon first."
    state["active_dungeon"] = {
        "key": key,
        "room": 0,
        "checkpoint": 0,
        "flags": [],
        "energy_spent": 0,
        "pending": {},
        "awaiting_combat": False,
        "combat_cleared": 0,
    }
    if "shadow_cache" in profile.get("legacy", {}).get("active_tenets", []):
        state["clues"][key] = max(1, int(state["clues"].get(key, 0)))
    profile.setdefault("quests_v2", {}).setdefault("counters", {})["second_answer_used"] = 0
    return True, f"Entered **{dungeon['name']}**. Each of its {dungeon['rooms']} rooms costs 1 energy."


def _living_enemy(dungeon: dict[str, Any], room: int, *, kind: str) -> dict[str, Any]:
    """Create a live combat identity backed by the normal balance engine."""
    floor = int(dungeon["floor"])
    enemy = enemy_for_floor(floor)
    if kind == "miniboss":
        enemy = apply_miniboss(enemy, floor)
        identity = LIVING_MINIBOSSES[dungeon["miniboss"]]
        enemy["miniboss"] = True
    elif kind == "boss":
        enemy = boss_for_floor(max(5, ((floor + 4) // 5) * 5))
        identity = LIVING_BOSSES[dungeon["boss"]]
        enemy["boss"] = True
    else:
        identities = [
            details
            for details in LIVING_ENEMIES.values()
            if details["region"] == dungeon["region"]
        ]
        identity = identities[room % len(identities)]
    enemy["name"] = identity["name"]
    enemy["base_name"] = identity["name"]
    enemy["codex_key"] = f"living:{dungeon['region']}:{identity['name'].lower().replace(' ', '_')}"
    enemy["status"] = {}
    enemy["guarded"] = 0
    enemy["atlas_room"] = room
    enemy["atlas_dungeon"] = next(key for key, value in NAMED_DUNGEONS.items() if value is dungeon)
    enemy["living_mechanic"] = identity.get("mechanic") or identity.get("tactic", "")
    return enemy


def advance_dungeon(profile: dict[str, Any]) -> tuple[bool, str]:
    """Spend one energy and advance a named dungeon room."""
    state = ensure_atlas(profile)
    run = state["active_dungeon"]
    if not run:
        return False, "No named dungeon is active."
    run.setdefault("pending", {})
    run.setdefault("awaiting_combat", False)
    run.setdefault("combat_cleared", 0)
    if run["pending"]:
        return False, "Resolve the current room choice before advancing."
    dungeon = NAMED_DUNGEONS[run["key"]]
    if run["awaiting_combat"]:
        if int(run["combat_cleared"]) >= int(run["room"]):
            run["awaiting_combat"] = False
            if int(run["room"]) >= int(dungeon["rooms"]):
                if run["key"] not in state["completed"]:
                    state["completed"].append(run["key"])
                name = dungeon["name"]
                state["active_dungeon"] = {}
                return True, f"🏛️ **{name} completed.** Its outcome and route are permanently recorded."
            return True, "⚔️ The room is secure. Advancing to the next room will cost **1 energy**."
        if profile.get("encounter"):
            return False, "The room's enemy still blocks the route. Use Resume and finish the battle."
        kind = "boss" if int(run["room"]) >= int(dungeon["rooms"]) else "miniboss" if int(run["room"]) == 5 else "normal"
        profile["encounter"] = _living_enemy(dungeon, int(run["room"]), kind=kind)
        return True, "⚔️ Your foe survived the failed attempt and bars the route again. The retry costs no energy."
    if int(profile.get("turns", 0)) < 1:
        return False, "You have no exploration energy remaining."
    profile["turns"] -= 1
    run["energy_spent"] += 1
    run["room"] += 1
    room = int(run["room"])
    if room in {1, 4, 6}:
        events = [event for event in DUNGEON_EVENTS.values() if event["region"] == dungeon["region"]]
        event = events[(tuple(NAMED_DUNGEONS).index(run["key"]) + room) % len(events)]
        run["pending"] = {
            "type": "moral",
            "key": event["name"].lower().replace(" ", "_"),
            "name": event["name"],
            "prompt": event["text"],
            "options": list(event["options"]),
        }
        return True, (
            f"⚖️ **Room {room}/{dungeon['rooms']} — {event['name']}**\n{event['text']}\n"
            "Choose `mercy`, `honesty`, `ambition`, or `ruthlessness` with "
            "`/deepdelve living atlas choice <approach>`."
        )
    if room == 3:
        run["checkpoint"] = run["room"]
        puzzles = [puzzle for puzzle in LIVING_PUZZLES.values() if puzzle["region"] == dungeon["region"]]
        puzzle = puzzles[tuple(NAMED_DUNGEONS).index(run["key"]) % len(puzzles)]
        run["pending"] = {
            "type": "puzzle",
            "key": puzzle["name"].lower().replace(" ", "_"),
            "name": puzzle["name"],
            "prompt": puzzle["prompt"],
            "options": list(puzzle["solutions"]),
        }
        return True, (
            f"🕯️ **Checkpoint secured — {puzzle['name']}**\n{puzzle['prompt']}\n"
            f"Valid approaches: **{', '.join(puzzle['solutions'])}**. "
            "Use `/deepdelve living atlas choice <approach>`."
        )
    if room in {2, 5, int(dungeon["rooms"])}:
        kind = "boss" if room >= int(dungeon["rooms"]) else "miniboss" if room == 5 else "normal"
        enemy = _living_enemy(dungeon, room, kind=kind)
        profile["encounter"] = enemy
        run["awaiting_combat"] = True
        return True, (
            f"⚔️ **Room {room}/{dungeon['rooms']} — {enemy['name']}**\n"
            f"*{enemy['living_mechanic']}*\nUse Resume to fight. Combat actions cost no additional energy."
        )
    return True, f"Advanced to room **{room}/{dungeon['rooms']}** — {dungeon['mechanic']}"


def resolve_dungeon_choice(profile: dict[str, Any], approach: str) -> tuple[bool, str]:
    """Resolve a pending moral room or puzzle through one valid approach."""
    run = ensure_atlas(profile).get("active_dungeon") or {}
    pending = run.get("pending") or {}
    approach = approach.lower()
    if not pending:
        return False, "The active named dungeon has no unresolved choice."
    if approach not in pending["options"]:
        return False, f"Choose one of: {', '.join(pending['options'])}."
    flag = f"{pending['type']}:{pending['key']}:{approach}"
    if flag not in run["flags"]:
        run["flags"].append(flag)
    if pending["type"] == "moral":
        delta = {"mercy": 2, "honesty": 1, "ambition": -1, "ruthlessness": -2}[approach]
        record_deed(
            profile,
            f"named_dungeon:{run['key']}:{run['room']}:{approach}",
            f"Resolved {pending['name']} through {approach}",
            delta,
            {approach: 1},
        )
        consequence = f"dungeon:{run['key']}:room_{run['room']}:{approach}"
        legacy_flags = profile.setdefault("legacy", {}).setdefault("consequence_flags", [])
        if consequence not in legacy_flags:
            legacy_flags.append(consequence)
        message = f"⚖️ **{approach.title()}** changes how this route will be remembered."
    else:
        clues = ensure_atlas(profile)["clues"]
        clues[run["key"]] = min(3, int(clues.get(run["key"], 0)) + 1)
        message = f"🧩 **{approach.title()}** solves the chamber. An Atlas clue is permanently recorded."
    run["pending"] = {}
    return True, message


def record_dungeon_victory(profile: dict[str, Any], enemy: dict[str, Any]) -> list[str]:
    """Mark an Atlas combat room cleared exactly once when its enemy is defeated."""
    key = enemy.get("atlas_dungeon")
    room = int(enemy.get("atlas_room", 0))
    run = ensure_atlas(profile).get("active_dungeon") or {}
    if not key or run.get("key") != key or room != int(run.get("room", 0)):
        return []
    run["combat_cleared"] = max(int(run.get("combat_cleared", 0)), room)
    return [f"🗺️ **Named-dungeon room {room} cleared.** Return to the Atlas route to continue."]


def abandon_dungeon(profile: dict[str, Any]) -> tuple[bool, str]:
    """Return to the last checkpoint without refunding spent energy."""
    state = ensure_atlas(profile)
    run = state["active_dungeon"]
    if not run:
        return False, "No named dungeon is active."
    encounter = profile.get("encounter") or {}
    if encounter.get("atlas_dungeon") == run["key"]:
        return False, "You cannot abandon while a named-dungeon enemy is engaged. Fight or flee first."
    if run["checkpoint"]:
        run["room"] = run["checkpoint"]
        run["pending"] = {}
        run["awaiting_combat"] = False
        run["combat_cleared"] = run["checkpoint"]
        return True, f"Returned to checkpoint **{run['checkpoint']}**. Spent energy was not refunded."
    state["active_dungeon"] = {}
    return True, "The expedition was abandoned. Spent energy was not refunded."
