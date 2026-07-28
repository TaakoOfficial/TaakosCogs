"""Playable six-act Living World campaign with permanent decisions and endings."""

from __future__ import annotations

from typing import Any

from deepdelve.living_content import MAIN_CAMPAIGN_ACTS
from deepdelve.systems.legacy import grant_resolve
from deepdelve.systems.morality import record_deed

OUTCOME_DELTAS = {
    "mercy": (3, {"mercy": 2}),
    "honesty": (1, {"honesty": 2}),
    "ambition": (-1, {"ambition": 2}),
    "ruthlessness": (-3, {"ruthlessness": 2}),
}

ENDINGS = {
    "dawn": ("The Common Dawn", "Lastlight survives because power is made answerable to the people it protects."),
    "balance": ("The Honest Measure", "The Deep is bound by terms that name every cost and conceal no sacrifice."),
    "crown": ("The Crown Below", "You master the Deep's authorship and become the power every future delver must bargain with."),
    "unwritten": ("The Unwritten Door", "You refuse every offered conclusion and leave the world capable of choosing again."),
}


def ensure_living_campaign(profile: dict[str, Any]) -> dict[str, Any]:
    """Normalize persistent 5.0 campaign state."""
    state = profile.setdefault(
        "living_campaign",
        {"act": 0, "scene": 0, "decision": 0, "choices": {}, "completed": [], "ending": ""},
    )
    state.setdefault("act", 0)
    state.setdefault("scene", 0)
    state.setdefault("decision", 0)
    state.setdefault("choices", {})
    state.setdefault("completed", [])
    state.setdefault("ending", "")
    return state


def living_campaign_view(profile: dict[str, Any]) -> dict[str, Any]:
    """Return the current story state without mutating it."""
    state = ensure_living_campaign(profile)
    if state["ending"] or int(state["act"]) >= len(MAIN_CAMPAIGN_ACTS):
        return {"complete": True, "state": state, "ending": ENDINGS.get(state["ending"], ENDINGS["unwritten"])}
    act = MAIN_CAMPAIGN_ACTS[int(state["act"])]
    decision = int(state["decision"])
    scene = int(state["scene"])
    needs_choice = decision < len(act["decisions"]) and scene >= (decision + 1) * 2
    return {
        "complete": False,
        "available": int(profile.get("deepest_floor", 1)) >= int(act["floor"]),
        "act": act,
        "scene": scene,
        "decision": decision,
        "needs_choice": needs_choice,
        "energy_cost": 0 if needs_choice else 1,
        "state": state,
    }


def _campaign_ending(state: dict[str, Any]) -> str:
    counts = dict.fromkeys(OUTCOME_DELTAS, 0)
    for choice in state["choices"].values():
        counts[choice] += 1
    if counts["mercy"] >= 7:
        return "dawn"
    if counts["ambition"] + counts["ruthlessness"] >= 10:
        return "crown"
    if max(counts.values()) - min(counts.values()) <= 2:
        return "unwritten"
    return "balance"


def advance_living_campaign(profile: dict[str, Any], choice: str | None = None) -> dict[str, Any]:
    """Advance one scene or commit one permanent decision."""
    view = living_campaign_view(profile)
    if view["complete"]:
        name, text = view["ending"]
        return {"ok": False, "message": f"Your Living Chronicle is complete: **{name}** — {text}"}
    act = view["act"]
    state = view["state"]
    if not view["available"]:
        return {"ok": False, "message": f"Act {int(state['act']) + 1} unlocks at floor **{act['floor']}**."}
    if view["needs_choice"]:
        if choice not in OUTCOME_DELTAS:
            decision = act["decisions"][int(state["decision"])]
            return {
                "ok": False,
                "needs_choice": True,
                "message": f"**{decision['prompt']}** Choose mercy, honesty, ambition, or ruthlessness.",
            }
        decision = act["decisions"][int(state["decision"])]
        key = decision["key"]
        state["choices"][key] = choice
        state["decision"] += 1
        morality, convictions = OUTCOME_DELTAS[choice]
        lines = record_deed(
            profile,
            f"living_campaign:{key}:{choice}",
            f"Chose {choice} during {act['name']}",
            morality,
            convictions,
        )
        message = f"⚖️ **{choice.title()}** becomes part of the Chronicle."
        if lines:
            message += f"\n{lines[0]}"
        if state["decision"] < len(act["decisions"]):
            return {"ok": True, "resolved": True, "act_complete": False, "outcome": choice, "message": message}
    else:
        if int(profile.get("turns", 0)) < 1:
            return {"ok": False, "message": "Continuing this scene costs **1 exploration energy**, but none remains."}
        profile["turns"] -= 1
        scene_text = act["scenes"][int(state["scene"])]
        state["scene"] += 1
        return {
            "ok": True,
            "resolved": False,
            "act_complete": False,
            "message": f"📖 **{act['name']} — Scene {state['scene']}/6**\n\n{scene_text}\n\n*Cost: 1 exploration energy.*",
        }

    reward = act["reward"]
    profile["gold"] = int(profile.get("gold", 0)) + int(reward["gold"])
    profile["xp"] = int(profile.get("xp", 0)) + int(reward["xp"])
    grant_resolve(profile, int(reward["resolve"]), f"living_campaign:{act['key']}")
    state["completed"].append(act["key"])
    state["act"] += 1
    state["scene"] = 0
    state["decision"] = 0
    complete = int(state["act"]) >= len(MAIN_CAMPAIGN_ACTS)
    if complete:
        state["ending"] = _campaign_ending(state)
        name, text = ENDINGS[state["ending"]]
        message += (
            f"\n\n🏆 **The Living Chronicle is complete — {name}.**\n{text}\n"
            f"+{reward['gold']} currency • +{reward['xp']} XP • +{reward['resolve']} Resolve"
        )
    else:
        message += f"\n\n📕 **Act complete.** +{reward['gold']} currency • +{reward['xp']} XP • +{reward['resolve']} Resolve"
    return {"ok": True, "resolved": True, "act_complete": True, "complete": complete, "outcome": choice, "message": message}
