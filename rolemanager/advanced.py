"""Discord-independent helpers for RoleManager's advanced workflows."""

from __future__ import annotations

import shlex
from dataclasses import dataclass
from typing import Any

BUTTON_MODES = frozenset({"toggle", "add", "remove"})
SELECT_MODES = frozenset({"toggle", "sync", "exclusive", "add"})
TARGET_KEYS = frozenset(
    {
        "type",
        "status",
        "has",
        "any",
        "none",
        "channel",
        "voice",
        "thread",
        "joined_days",
        "account_days",
    },
)


@dataclass(frozen=True)
class TargetQuery:
    """A parsed advanced member-target query."""

    values: dict[str, tuple[str, ...]]

    def get(self, key: str) -> tuple[str, ...]:
        return self.values.get(key, ())


def normalize_component_policy(data: Any, *, select: bool = False) -> dict[str, Any]:
    """Return a complete, backward-compatible component policy record."""
    source = dict(data) if isinstance(data, dict) else {}
    allowed_modes = SELECT_MODES if select else BUTTON_MODES
    # Older select menus toggled individual options. Keep that behavior unless
    # an administrator explicitly opts into synchronization or exclusivity.
    default_mode = "toggle"
    mode = str(source.get("mode", default_mode)).lower()
    if mode not in allowed_modes:
        mode = default_mode

    def ids(key: str) -> list[int]:
        output: list[int] = []
        for value in source.get(key, []) or []:
            try:
                item = int(value)
            except (TypeError, ValueError):
                continue
            if item > 0 and item not in output:
                output.append(item)
        return output

    def number(key: str, maximum: int) -> int:
        try:
            value = int(source.get(key, 0) or 0)
        except (TypeError, ValueError):
            return 0
        return max(0, min(value, maximum))

    source.update(
        {
            "mode": mode,
            "required_role_ids": ids("required_role_ids"),
            "blocked_role_ids": ids("blocked_role_ids"),
            "cooldown_seconds": number("cooldown_seconds", 86_400),
            "max_holders": number("max_holders", 1_000_000),
            "temp_seconds": number("temp_seconds", 31_536_000),
        },
    )
    return source


def parse_target_query(argument: str) -> TargetQuery:
    """Parse `key=value` filters, supporting quoted and repeated values."""
    parsed: dict[str, list[str]] = {}
    for token in shlex.split(argument):
        if "=" not in token:
            raise ValueError(f"Target filter `{token}` must use key=value.")
        key, raw_value = token.split("=", 1)
        key = key.strip().lower()
        if key not in TARGET_KEYS:
            raise ValueError(f"Unknown target filter `{key}`.")
        values = [value.strip() for value in raw_value.split(",") if value.strip()]
        if not values:
            raise ValueError(f"Target filter `{key}` has no value.")
        parsed.setdefault(key, []).extend(values)
    if not parsed:
        raise ValueError("Provide at least one target filter.")
    return TargetQuery({key: tuple(dict.fromkeys(values)) for key, values in parsed.items()})


def trim_history(entries: list[dict[str, Any]], *, maximum: int = 250) -> list[dict[str, Any]]:
    """Keep only the newest bounded audit/job records."""
    if maximum <= 0:
        return []
    return list(entries[-maximum:])


def reaction_record_issues(
    records: Any,
    *,
    channel_ids: set[int],
    role_ids: set[int],
) -> list[str]:
    """Validate imported reaction records without Discord or config access."""
    issues: list[str] = []
    if not isinstance(records, dict):
        return ["Reaction-role data is not a mapping."]
    for message_id, record in records.items():
        if not str(message_id).isdigit():
            issues.append(f"Invalid message ID: {message_id}")
        if not isinstance(record, dict):
            issues.append(f"Message {message_id} has an invalid record.")
            continue
        try:
            channel_id = int(record.get("channel_id", 0))
        except (TypeError, ValueError):
            channel_id = 0
        if channel_id not in channel_ids:
            issues.append(f"Message {message_id} references missing channel {channel_id}.")
        binds = record.get("binds", {})
        if not isinstance(binds, dict) or not binds:
            issues.append(f"Message {message_id} has no bindings.")
            continue
        for emoji, bind in binds.items():
            try:
                role_id = int(bind.get("role_id", 0))
            except (AttributeError, TypeError, ValueError):
                role_id = 0
            if role_id not in role_ids:
                issues.append(f"Message {message_id} emoji {emoji} references missing role {role_id}.")
    return issues


def plan_reaction_role_changes(
    current_by_member: dict[int, set[int]],
    desired_by_member: dict[int, set[int]],
    managed_role_ids: set[int],
    *,
    remove_missing: bool,
) -> dict[int, dict[str, set[int]]]:
    """Plan reconciliation between imported panels, live reactions, and member roles."""
    plan: dict[int, dict[str, set[int]]] = {}
    member_ids = set(current_by_member) | set(desired_by_member)
    for member_id in member_ids:
        current = current_by_member.get(member_id, set()) & managed_role_ids
        desired = desired_by_member.get(member_id, set()) & managed_role_ids
        additions = desired - current
        removals = current - desired if remove_missing else set()
        if additions or removals:
            plan[int(member_id)] = {"add": additions, "remove": removals}
    return plan
