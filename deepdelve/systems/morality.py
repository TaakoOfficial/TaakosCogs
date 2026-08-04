"""Living morality, convictions, deeds, reactions, and moral combat powers."""

from __future__ import annotations

from typing import Any

CONVICTIONS = ("mercy", "honesty", "ambition", "ruthlessness")

CAMPAIGN_DEEDS: dict[tuple[str, str], dict[str, Any]] = {
    ("lantern_below", "truth"): {
        "name": "Told Lastlight the whole truth",
        "morality": 8,
        "convictions": {"honesty": 5},
    },
    ("lantern_below", "mercy"): {
        "name": "Carried a terrible secret to protect Lastlight",
        "morality": 7,
        "convictions": {"mercy": 5, "honesty": -1},
    },
    ("lantern_below", "power"): {
        "name": "Claimed the whispering lantern",
        "morality": -8,
        "convictions": {"ambition": 5, "ruthlessness": 1},
    },
    ("silken_sky", "free"): {
        "name": "Freed the dreaming star",
        "morality": 12,
        "convictions": {"mercy": 6},
    },
    ("silken_sky", "seal"): {
        "name": "Sealed the dreaming star away",
        "morality": 2,
        "convictions": {"mercy": -1, "ambition": 2},
    },
    ("silken_sky", "harvest"): {
        "name": "Harvested a living star",
        "morality": -12,
        "convictions": {"ambition": 6, "ruthlessness": 3},
    },
    ("iron_dream", "destroy"): {
        "name": "Destroyed the memory press",
        "morality": 5,
        "convictions": {"mercy": 3, "ruthlessness": 2},
    },
    ("iron_dream", "preserve"): {
        "name": "Preserved the forbidden archive",
        "morality": 4,
        "convictions": {"honesty": 5},
    },
    ("iron_dream", "ignite"): {
        "name": "Restarted the identity forge",
        "morality": -9,
        "convictions": {"ambition": 5, "ruthlessness": 2},
    },
    ("hollow_name", "speak"): {
        "name": "Restored the Hollow King's true name",
        "morality": 7,
        "convictions": {"honesty": 6},
    },
    ("hollow_name", "erase"): {
        "name": "Erased a kingdom to end its curse",
        "morality": 0,
        "convictions": {"mercy": 2, "ruthlessness": 4},
    },
    ("hollow_name", "inherit"): {
        "name": "Inherited the Hollow Crown",
        "morality": -12,
        "convictions": {"ambition": 7, "ruthlessness": 2},
    },
    ("fifth_bell", "descend"): {
        "name": "Chose to become the Last Delver",
        "morality": 0,
        "convictions": {"ambition": 6},
    },
    ("fifth_bell", "seal"): {
        "name": "Accepted the burden of Warden",
        "morality": 10,
        "convictions": {"mercy": 5, "ambition": 2},
    },
    ("fifth_bell", "reveal"): {
        "name": "Opened the truth to the world",
        "morality": 10,
        "convictions": {"honesty": 6, "mercy": 2},
    },
}

CHOICE_DEEDS: dict[tuple[str, str], dict[str, Any]] = {
    ("sealed_door", "force"): {
        "name": "Answered a sealed warning with force",
        "morality": 0,
        "convictions": {"ambition": 1},
    },
    ("sealed_door", "study"): {
        "name": "Listened to the sealed door's warning",
        "morality": 1,
        "convictions": {"honesty": 1},
    },
    ("dark_altar", "offer"): {
        "name": "Fed the dark altar",
        "morality": -5,
        "convictions": {"ambition": 3},
    },
    ("dark_altar", "destroy"): {
        "name": "Broke a dark altar",
        "morality": 4,
        "convictions": {"ruthlessness": 2},
    },
    ("lost_delver", "aid"): {
        "name": "Gave medicine to a lost delver",
        "morality": 7,
        "convictions": {"mercy": 4},
    },
    ("lost_delver", "escort"): {
        "name": "Escorted a lost delver to safety",
        "morality": 5,
        "convictions": {"mercy": 3},
    },
    ("weeping_sword", "study"): {
        "name": "Heard the weeping sword's final memory",
        "morality": 2,
        "convictions": {"mercy": 2, "honesty": 1},
    },
    ("weeping_sword", "force"): {
        "name": "Tried to take the weeping sword by force",
        "morality": -2,
        "convictions": {"ambition": 2},
    },
    ("fungal_feast", "destroy"): {
        "name": "Burned the breathing feast",
        "morality": 0,
        "convictions": {"ruthlessness": 2},
    },
    ("clockwork_child", "aid"): {
        "name": "Gave the clockwork child a heartbeat",
        "morality": 8,
        "convictions": {"mercy": 5},
    },
    ("clockwork_child", "study"): {
        "name": "Preserved the clockwork child's sleeping memory",
        "morality": 2,
        "convictions": {"honesty": 2},
    },
    ("empty_throne", "offer"): {
        "name": "Knelt before an empty throne",
        "morality": -4,
        "convictions": {"ambition": 3},
    },
    ("empty_throne", "destroy"): {
        "name": "Freed the court from its empty throne",
        "morality": 4,
        "convictions": {"mercy": 2, "ruthlessness": 2},
    },
    ("future_grave", "study"): {
        "name": "Read the truth written on a future grave",
        "morality": 1,
        "convictions": {"honesty": 2},
    },
    ("future_grave", "destroy"): {
        "name": "Shattered a future bearing their own name",
        "morality": 0,
        "convictions": {"ruthlessness": 2, "ambition": 1},
    },
    ("judgment_mirror", "absolve"): {
        "name": "Released the sins imprisoned in the judgment mirror",
        "morality": 6,
        "convictions": {"mercy": 4},
    },
    ("judgment_mirror", "bargain"): {
        "name": "Bargained honestly with the judgment mirror",
        "morality": 0,
        "convictions": {"honesty": 2, "ambition": 2},
    },
    ("judgment_mirror", "consume"): {
        "name": "Consumed the judgment mirror's imprisoned sins",
        "morality": -6,
        "convictions": {"ambition": 4, "ruthlessness": 2},
    },
}


def origin_morality(alignment: str) -> int:
    """Return the small starting bias provided by an origin philosophy."""
    return {"Radiant": 15, "Pragmatic": 0, "Umbral": -15}.get(alignment, 0)


def ensure_morality(profile: dict[str, Any]) -> None:
    """Normalize morality state without applying historical deeds."""
    profile.setdefault("morality", origin_morality(profile.get("alignment", "")))
    convictions = profile.setdefault("convictions", {})
    for conviction in CONVICTIONS:
        convictions.setdefault(conviction, 0)
    profile.setdefault("moral_deeds", [])
    profile.setdefault("deed_counts", {})
    profile.setdefault("conviction_fatigue", 0)


def morality_path(profile: dict[str, Any]) -> dict[str, Any]:
    """Describe the visible moral transformation caused by a score."""
    ensure_morality(profile)
    score = max(-100, min(100, int(profile["morality"])))
    if score >= 70:
        return {
            "key": "beacon",
            "name": "Beacon",
            "emoji": "☀️",
            "color": 0xF1C40F,
            "appearance": "Golden light gathers in your eyes, and your shadow points toward danger.",
        }
    if score >= 30:
        return {
            "key": "radiant",
            "name": "Radiant",
            "emoji": "✨",
            "color": 0xF5B041,
            "appearance": "Your lantern burns warmly in the presence of frightened souls.",
        }
    if score <= -70:
        return {
            "key": "dreadbound",
            "name": "Dreadbound",
            "emoji": "👁️",
            "color": 0x641E16,
            "appearance": "Your reflection smiles late, and nearby flames lean away from you.",
        }
    if score <= -30:
        return {
            "key": "umbral",
            "name": "Umbral",
            "emoji": "🌑",
            "color": 0x512E5F,
            "appearance": "A second shadow follows your movements and whispers before you speak.",
        }
    return {
        "key": "pragmatic",
        "name": "Uncommitted",
        "emoji": "⚖️",
        "color": 0x7F8C8D,
        "appearance": "The Deep finds no simple answer in you; both lanterns and shadows remain watchful.",
    }


def dominant_conviction(profile: dict[str, Any]) -> str:
    """Return the strongest recorded motive, resolving untouched ties neutrally."""
    ensure_morality(profile)
    convictions = profile["convictions"]
    highest = max((int(convictions.get(key, 0)) for key in CONVICTIONS), default=0)
    if highest <= 0:
        return "unproven"
    return next(key for key in CONVICTIONS if int(convictions.get(key, 0)) == highest)


def record_deed(
    profile: dict[str, Any],
    key: str,
    name: str,
    morality: int,
    convictions: dict[str, int] | None = None,
    *,
    repeatable: bool = False,
) -> list[str]:
    """Record a deed, applying capped diminishing returns to repeatable actions."""
    ensure_morality(profile)
    count = int(profile["deed_counts"].get(key, 0))
    if (not repeatable and count) or (repeatable and count >= 3):
        return []
    scale = (1.0, 0.5, 0.25)[count] if repeatable else 1.0
    moral_delta = round(morality * scale)
    applied_convictions: dict[str, int] = {}
    for conviction, amount in (convictions or {}).items():
        if conviction not in CONVICTIONS:
            continue
        delta = round(int(amount) * scale)
        if not delta:
            continue
        old = int(profile["convictions"].get(conviction, 0))
        profile["convictions"][conviction] = max(-100, min(100, old + delta))
        applied_convictions[conviction] = delta
    old_score = int(profile["morality"])
    profile["morality"] = max(-100, min(100, old_score + moral_delta))
    profile["deed_counts"][key] = count + 1
    profile["moral_deeds"] = (
        profile["moral_deeds"]
        + [
            {
                "key": key,
                "name": name,
                "morality": moral_delta,
                "convictions": applied_convictions,
                "floor": int(profile.get("floor", 1)),
            },
        ]
    )[-40:]
    direction = "toward the Light" if moral_delta > 0 else "toward Shadow" if moral_delta < 0 else "without easy judgment"
    details = []
    if moral_delta:
        details.append(f"{moral_delta:+d} Morality")
    details.extend(f"{amount:+d} {key.title()}" for key, amount in applied_convictions.items())
    suffix = f" ({' • '.join(details)})" if details else ""
    return [f"⚖️ **Deed Remembered:** {name} — {direction}.{suffix}"]


def record_campaign_deed(profile: dict[str, Any], chapter_key: str, choice: str) -> list[str]:
    """Record one permanent campaign decision."""
    deed = CAMPAIGN_DEEDS.get((chapter_key, choice))
    if not deed:
        return []
    return record_deed(
        profile,
        f"campaign:{chapter_key}:{choice}",
        deed["name"],
        deed["morality"],
        deed["convictions"],
    )


def record_choice_deed(profile: dict[str, Any], choice_key: str, action: str, *, performed: bool = True) -> list[str]:
    """Record one dungeon decision with lifetime anti-farming limits."""
    if not performed:
        return []
    deed = CHOICE_DEEDS.get((choice_key, action))
    if not deed:
        return []
    return record_deed(
        profile,
        f"event:{choice_key}:{action}",
        deed["name"],
        deed["morality"],
        deed["convictions"],
        repeatable=True,
    )


def moral_power(profile: dict[str, Any]) -> dict[str, Any]:
    """Return the once-per-battle power earned by an established moral identity."""
    path = morality_path(profile)
    score = int(profile["morality"])
    motive = dominant_conviction(profile)
    fatigue = max(0, int(profile.get("conviction_fatigue", 0)))
    if score >= 30:
        power = {
            "unlocked": True,
            "key": "grace",
            "name": "Lantern Grace",
            "emoji": "☀️",
            "description": f"Heal, cleanse conditions, and gain guard once per battle. Strongest motive: {motive.title()}.",
            "greater": score >= 70,
        }
    elif score <= -30:
        power = {
            "unlocked": True,
            "key": "claim",
            "name": "Dread Claim",
            "emoji": "🌑",
            "description": f"Wound through armor and steal part of the damage. Strongest motive: {motive.title()}.",
            "greater": score <= -70,
        }
    else:
        established = len(profile.get("moral_deeds", [])) >= 3
        power = {
            "unlocked": established,
            "key": "gambit",
            "name": "Measured Gambit",
            "emoji": path["emoji"],
            "description": f"Rewrite an intention, recover mana, and gain guard. Strongest motive: {motive.title()}.",
            "greater": len(profile.get("moral_deeds", [])) >= 12,
        }
    power["fatigue"] = fatigue
    power["available"] = bool(power["unlocked"] and fatigue <= 0)
    return power


def use_moral_power(profile: dict[str, Any], enemy: dict[str, Any], stats: dict[str, int]) -> dict[str, Any]:
    """Apply a moral power once during the current encounter."""
    power = moral_power(profile)
    flags = profile.setdefault("combat_flags", {})
    if not power["unlocked"]:
        return {"ok": False, "message": "Your convictions have not yet become strong enough to answer in battle."}
    if power["fatigue"]:
        return {
            "ok": False,
            "message": f"Conviction Fatigue remains for **{power['fatigue']} more victory/victories**.",
        }
    if flags.get("moral_power_used"):
        return {"ok": False, "message": "Your conviction has already answered once in this battle."}
    flags["moral_power_used"] = True
    profile["conviction_fatigue"] = 2
    if power["key"] == "grace":
        mercy = max(0, int(profile["convictions"].get("mercy", 0)))
        rate = (0.11 if power["greater"] else 0.09) + (0.01 if mercy >= 25 else 0)
        healing = min(stats["max_hp"] - profile["hp"], max(1, round(stats["max_hp"] * rate)))
        profile["hp"] += healing
        profile["status"] = {}
        flags["guard"] = max(float(flags.get("guard", 0)), 0.2 if power["greater"] else 0.16)
        damage = max(
            1,
            round(stats["attack"] * (1.15 if power["greater"] else 1.05)) - int(enemy.get("defense", 0)) // 4,
        )
        enemy["hp"] -= damage
        message = (
            f"☀️ **Lantern Grace** deals **{damage} damage**, restores **{healing} health**, cleanses you, and raises a ward."
        )
    elif power["key"] == "claim":
        ambition = max(0, int(profile["convictions"].get("ambition", 0)))
        multiplier = 1.15 if power["greater"] else 1.05
        damage = max(1, round(stats["attack"] * multiplier) - int(enemy.get("defense", 0)) // 4)
        enemy["hp"] -= damage
        drain_rate = (0.5 if power["greater"] else 0.4) + (0.02 if ambition >= 25 else 0)
        drain = min(
            round(damage * drain_rate),
            round(stats["max_hp"] * (0.10 if power["greater"] else 0.08)),
        )
        healing = min(stats["max_hp"] - profile["hp"], max(1, drain))
        profile["hp"] += healing
        flags["guard"] = max(float(flags.get("guard", 0)), 0.2 if power["greater"] else 0.16)
        message = f"🌑 **Dread Claim** deals **{damage} damage** and steals **{healing} health**."
    else:
        from deepdelve.systems.combat import roll_enemy_intent

        enemy["intent"] = roll_enemy_intent(enemy)
        honesty = max(0, int(profile["convictions"].get("honesty", 0)))
        ambition = max(0, int(profile["convictions"].get("ambition", 0)))
        mana_base = (6 if power["greater"] else 4) + (1 if honesty >= 25 else 0)
        mana = min(stats["max_mana"] - profile["mana"], mana_base)
        profile["mana"] += mana
        guard = (0.19 if power["greater"] else 0.15) + (0.01 if ambition >= 25 else 0)
        flags["guard"] = max(float(flags.get("guard", 0)), guard)
        healing = min(
            stats["max_hp"] - profile["hp"],
            max(1, round(stats["max_hp"] * (0.12 if power["greater"] else 0.09))),
        )
        profile["hp"] += healing
        damage = max(
            1,
            round(stats["attack"] * (1.15 if power["greater"] else 1.05)) - int(enemy.get("defense", 0)) // 4,
        )
        enemy["hp"] -= damage
        message = (
            f"⚖️ **Measured Gambit** deals **{damage} damage**, rewrites the intention, "
            f"restores **{mana} mana** and **{healing} health**, and grants guard."
        )
    return {"ok": True, "message": message}


def npc_moral_reaction(profile: dict[str, Any], npc_key: str) -> str:
    """Return authored NPC recognition of the player's visible moral path."""
    path = morality_path(profile)["key"]
    reactions = {
        "orra": {
            "beacon": "“Your steel has stopped whispering at night. It thinks you might actually save someone.”",
            "radiant": "“There is mercy in your grip. Do not confuse that with weakness.”",
            "umbral": "“The metal recoils from you now. Useful—but I noticed.”",
            "dreadbound": "“Leave the weapon on the stone. I will not take it from your hand.”",
            "pragmatic": "“Still deciding what kind of weapon you are? So is the Deep.”",
        },
        "mara": {
            "beacon": "“The Watch stands straighter when you pass. That is a responsibility, not applause.”",
            "radiant": "“People believe you will come back for them. Try to deserve it.”",
            "umbral": "“You get results. I have assigned two guards to watch how.”",
            "dreadbound": "“Lastlight needs you outside its walls more than it wants you inside them.”",
            "pragmatic": "“I can work with difficult choices. I cannot work with excuses.”",
        },
        "vesper": {
            "beacon": "“Fascinating. The manuscript has begun illuminating your name by itself.”",
            "radiant": "“History is attempting to call you kind. History is rarely so optimistic.”",
            "umbral": "“Several forbidden texts now open when you enter the room.”",
            "dreadbound": "“The page describing your death has gone missing. I suspect it is afraid.”",
            "pragmatic": "“Every edition disagrees about you. That may be the most honest biography.”",
        },
        "rook": {
            "beacon": "“If you grow a halo, I am using it to read maps in the dark.”",
            "radiant": "“You keep rescuing people. Very inconsiderate to those of us cultivating mystery.”",
            "umbral": "“That new shadow of yours cheats at cards. I respect it.”",
            "dreadbound": "“For the record, I was joking when I said you should become terrifying.”",
            "pragmatic": "“Good, evil—whichever one finds the better shortcut, let me know.”",
        },
    }
    return reactions.get(npc_key, {}).get(path, "")
