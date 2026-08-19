"""Decision state rules."""

from __future__ import annotations

VALID_STATUSES = {"proposed", "accepted", "rejected", "implemented", "superseded"}
TRANSITIONS = {
    "proposed": {"accepted", "rejected"},
    "accepted": {"implemented", "superseded"},
    "rejected": {"proposed"},
    "implemented": {"superseded"},
    "superseded": set(),
}


def validate_transition(current: str, target: str) -> None:
    if target not in VALID_STATUSES:
        raise ValueError(f"Unknown decision status: {target}")
    if target not in TRANSITIONS.get(current, set()):
        raise ValueError(f"A decision cannot move from {current} to {target}.")


def compact_title(value: str) -> str:
    title = " ".join(value.split())
    if not title:
        raise ValueError("A decision title is required.")
    return title[:200]
