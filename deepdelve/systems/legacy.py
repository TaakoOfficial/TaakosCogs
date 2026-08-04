"""Morality paths, Resolve, Tenets, factions, oaths, and consequences."""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from typing import Any

from deepdelve.living_content import FACTION_QUESTS, FACTIONS, TENETS
from deepdelve.systems.morality import CONVICTIONS, ensure_morality, morality_path, record_deed

MAX_ACTIVE_TENETS = 3
TENET_UNLOCK_COST = 2
FACTION_REPUTATION_CAP = 100


def ensure_legacy(profile: dict[str, Any]) -> dict[str, Any]:
    """Normalize and return version-5 legacy state."""
    ensure_morality(profile)
    state = profile.setdefault(
        "legacy",
        {
            "resolve": 0,
            "resolve_earned": 0,
            "unlocked_tenets": [],
            "active_tenets": [],
            "faction_reputation": dict.fromkeys(FACTIONS, 0),
            "oath": "",
            "oath_board_date": "",
            "oath_board": [],
            "redemption": {},
            "consequence_flags": [],
            "resolve_sources": [],
            "service_dates": {},
        },
    )
    state.setdefault("resolve", 0)
    state.setdefault("resolve_earned", 0)
    state.setdefault("unlocked_tenets", [])
    state.setdefault("active_tenets", [])
    state.setdefault("faction_reputation", {})
    for key in FACTIONS:
        state["faction_reputation"].setdefault(key, 0)
    state.setdefault("oath", "")
    state.setdefault("oath_board_date", "")
    state.setdefault("oath_board", [])
    state.setdefault("redemption", {})
    state.setdefault("consequence_flags", [])
    state.setdefault("resolve_sources", [])
    state.setdefault("service_dates", {})
    return state


def grant_resolve(profile: dict[str, Any], amount: int, source: str) -> int:
    """Grant non-tradable Resolve once for a unique source."""
    state = ensure_legacy(profile)
    amount = max(0, int(amount))
    if not amount or source in state["resolve_sources"]:
        return 0
    state["resolve_sources"].append(source)
    state["resolve"] += amount
    state["resolve_earned"] += amount
    return amount


def backfill_historical_resolve(profile: dict[str, Any]) -> int:
    """Credit recognized unique deeds without rewarding repeatable farming."""
    granted = 0
    for deed in profile.get("moral_deeds", []):
        key = str(deed.get("key", ""))
        if key.startswith("campaign:"):
            granted += grant_resolve(profile, 1, f"history:{key}")
    return granted


def tenet_available(profile: dict[str, Any], key: str) -> tuple[bool, str]:
    """Return whether a Tenet matches the player's established path."""
    definition = TENETS.get(key)
    if not definition:
        return False, "Unknown Tenet."
    path = morality_path(profile)["key"]
    broad_path = "radiant" if path in {"radiant", "beacon"} else "umbral" if path in {"umbral", "dreadbound"} else "pragmatic"
    if definition["path"] != broad_path:
        return False, f"This Tenet answers the {definition['path'].title()} path."
    return True, ""


def unlock_tenet(profile: dict[str, Any], key: str) -> tuple[bool, str]:
    """Spend Resolve to permanently learn a path-appropriate Tenet."""
    state = ensure_legacy(profile)
    if key in state["unlocked_tenets"]:
        return False, "That Tenet is already learned."
    available, reason = tenet_available(profile, key)
    if not available:
        return False, reason
    if state["resolve"] < TENET_UNLOCK_COST:
        return False, f"Learning a Tenet requires {TENET_UNLOCK_COST} Resolve."
    state["resolve"] -= TENET_UNLOCK_COST
    state["unlocked_tenets"].append(key)
    return True, f"Learned **{TENETS[key]['name']}**."


def equip_tenets(profile: dict[str, Any], keys: list[str]) -> tuple[bool, str]:
    """Equip up to three unique learned Tenets."""
    state = ensure_legacy(profile)
    normalized = list(dict.fromkeys(keys))
    if len(normalized) > MAX_ACTIVE_TENETS:
        return False, f"Equip no more than {MAX_ACTIVE_TENETS} Tenets."
    unknown = [key for key in normalized if key not in state["unlocked_tenets"]]
    if unknown:
        return False, f"Unlearned Tenet: {unknown[0]}."
    state["active_tenets"] = normalized
    return True, "Active Tenets updated."


def tenet_effects(profile: dict[str, Any]) -> dict[str, float]:
    """Combine the capped effects of equipped Tenets."""
    state = ensure_legacy(profile)
    effects: dict[str, float] = {}
    for key in state["active_tenets"][:MAX_ACTIVE_TENETS]:
        for effect, value in TENETS.get(key, {}).get("effect", {}).items():
            if isinstance(value, (int, float)):
                effects[effect] = effects.get(effect, 0) + value
    return effects


def change_faction_reputation(profile: dict[str, Any], faction: str, amount: int) -> int:
    """Adjust bounded faction reputation and return the applied delta."""
    state = ensure_legacy(profile)
    if faction not in FACTIONS:
        return 0
    old = int(state["faction_reputation"][faction])
    new = max(0, min(FACTION_REPUTATION_CAP, old + int(amount)))
    state["faction_reputation"][faction] = new
    return new - old


def oath_board(profile: dict[str, Any], today: date | None = None) -> list[dict[str, Any]]:
    """Return a deterministic daily board with equal-value faction assignments."""
    state = ensure_legacy(profile)
    today = today or datetime.now(timezone.utc).date()
    day_key = today.isoformat()
    if state["oath_board_date"] == day_key and state["oath_board"]:
        return state["oath_board"]
    ordinal = today.toordinal()
    entries = []
    for offset, faction in enumerate(FACTIONS):
        arc = FACTION_QUESTS[faction]
        source = arc[(ordinal + offset * 3) % len(arc)]
        entries.append(
            {
                "key": f"oath:{day_key}:{faction}",
                "faction": faction,
                "name": source["name"],
                "objective": source["objective"],
                "target": min(6, source["target"]),
                "progress": 0,
                "expires": (today + timedelta(days=1)).isoformat(),
                "reward": {"gold": 90, "xp": 110, "faction_reputation": 3},
            },
        )
    state["oath_board_date"] = day_key
    state["oath_board"] = entries
    return entries


def accept_oath(profile: dict[str, Any], faction: str, today: date | None = None) -> tuple[bool, str]:
    """Accept one current Oath Board assignment."""
    state = ensure_legacy(profile)
    entries = oath_board(profile, today)
    entry = next((item for item in entries if item["faction"] == faction), None)
    if not entry:
        return False, "Choose lantern, concord, or court."
    if state.get("oath"):
        current = next((item for item in entries if item["key"] == state["oath"]), None)
        if current:
            return False, f"**{current['name']}** is already your active oath."
        state["oath"] = ""
    state["oath"] = entry["key"]
    return True, (
        f"Accepted **{entry['name']}** for the {FACTIONS[faction]['name']} — {entry['objective']} {entry['target']} time(s)."
    )


def progress_oath(profile: dict[str, Any], objective: str, amount: int = 1) -> list[str]:
    """Advance and reward the active daily oath exactly once."""
    state = ensure_legacy(profile)
    if not state.get("oath"):
        return []
    entry = next((item for item in state.get("oath_board", []) if item["key"] == state["oath"]), None)
    if not entry or entry.get("claimed") or entry["objective"] != objective:
        return []
    entry["progress"] = min(int(entry["target"]), int(entry.get("progress", 0)) + max(0, int(amount)))
    if entry["progress"] < entry["target"]:
        return [f"📜 Oath progress: **{entry['progress']}/{entry['target']}**."]
    reward = entry["reward"]
    profile["gold"] = int(profile.get("gold", 0)) + int(reward["gold"])
    profile["xp"] = int(profile.get("xp", 0)) + int(reward["xp"])
    change_faction_reputation(profile, entry["faction"], int(reward["faction_reputation"]))
    entry["claimed"] = True
    state["oath"] = ""
    return [
        (
            f"📜 **Oath fulfilled: {entry['name']}** — +{reward['gold']} currency, "
            f"+{reward['xp']} XP, +{reward['faction_reputation']} faction reputation."
        ),
    ]


def use_faction_service(profile: dict[str, Any], faction: str) -> tuple[bool, str]:
    """Use one equal-budget faction contact per UTC day as a currency sink."""
    state = ensure_legacy(profile)
    if faction not in FACTIONS:
        return False, "Choose lantern, concord, or court."
    if int(state["faction_reputation"][faction]) < 10:
        return False, f"This contact requires 10 reputation with the {FACTIONS[faction]['name']}."
    today = datetime.now(timezone.utc).date().isoformat()
    if state["service_dates"].get(faction) == today:
        return False, "You have already used this faction contact today."
    if faction == "lantern" and int(profile.get("potions", 0)) >= 10:
        return False, "Your potion satchel is full; the Lantern contact will not charge you."
    cost = 80 + int(profile.get("level", 1)) * 5
    if "known_cost" in state["active_tenets"]:
        cost = round(cost * 0.9)
    if int(profile.get("gold", 0)) < cost:
        return False, f"This service costs {cost} currency."
    profile["gold"] -= cost
    state["service_dates"][faction] = today
    if faction == "lantern":
        profile["potions"] = min(10, int(profile.get("potions", 0)) + 1)
        reward = "one bound field potion"
    elif faction == "concord":
        consumables = profile.setdefault("consumables", {})
        consumables["truth_salt_1"] = int(consumables.get("truth_salt_1", 0)) + 1
        reward = "one Truth Salt"
    else:
        profile["arcane_shards"] = int(profile.get("arcane_shards", 0)) + 2
        reward = "two bound arcane shards"
    return True, f"{FACTIONS[faction]['emoji']} The contact provides **{reward}** for **{cost} currency**."


def begin_redemption(profile: dict[str, Any], target: str) -> tuple[bool, str]:
    """Begin a slow three-stage moral journey without erasing remembered deeds."""
    state = ensure_legacy(profile)
    if target not in {"radiant", "pragmatic", "umbral"}:
        return False, "Choose radiant, pragmatic, or umbral."
    current = morality_path(profile)["key"]
    broad = "radiant" if current in {"radiant", "beacon"} else "umbral" if current in {"umbral", "dreadbound"} else "pragmatic"
    if target == broad:
        return False, "You already walk that road."
    state["redemption"] = {"target": target, "stage": 1, "progress": 0, "required": 5}
    return True, f"A three-stage journey toward **{target.title()}** has begun."


def advance_redemption(profile: dict[str, Any], conviction: str) -> list[str]:
    """Advance a journey through matching significant deeds."""
    state = ensure_legacy(profile)
    journey = state.get("redemption") or {}
    if not journey or conviction not in CONVICTIONS:
        return []
    target_convictions = {
        "radiant": {"mercy", "honesty"},
        "pragmatic": {"honesty", "ambition"},
        "umbral": {"ambition", "ruthlessness"},
    }[journey["target"]]
    if conviction not in target_convictions:
        return []
    journey["progress"] += 1
    if journey["progress"] < journey["required"]:
        return [f"🛤️ Moral journey: **{journey['progress']}/{journey['required']}**."]
    target = journey["target"]
    delta = 12 if target == "radiant" else -12 if target == "umbral" else (-8 if profile["morality"] > 0 else 8)
    record_deed(
        profile,
        f"journey:{target}:{journey['stage']}",
        f"Completed stage {journey['stage']} of the road toward {target}",
        delta,
        {conviction: 2},
    )
    journey["stage"] += 1
    journey["progress"] = 0
    journey["required"] += 2
    if journey["stage"] > 3:
        state["consequence_flags"].append(f"journey_complete:{target}")
        state["redemption"] = {}
        grant_resolve(profile, 2, f"journey:{target}")
        return [f"🛤️ Your journey toward **{target.title()}** is complete. The past remains, but it no longer commands you."]
    return [f"🛤️ Stage complete. The next stage requires **{journey['required']}** fitting deeds."]
