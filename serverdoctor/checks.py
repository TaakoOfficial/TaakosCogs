"""Pure server-health checks."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class Finding:
    code: str
    severity: str
    title: str
    detail: str


def analyze_snapshot(snapshot: dict[str, Any]) -> list[Finding]:
    findings: list[Finding] = []
    missing = sorted(set(snapshot.get("required_bot_permissions", ())) - set(snapshot.get("bot_permissions", ())))
    if missing:
        findings.append(Finding("BOT_PERMISSIONS", "high", "Bot permissions are missing", ", ".join(missing)))
    dangerous = sorted(snapshot.get("everyone_dangerous_permissions", ()))
    if dangerous:
        findings.append(Finding("EVERYONE_DANGEROUS", "critical", "@everyone has dangerous permissions", ", ".join(dangerous)))
    admin_roles = list(snapshot.get("administrator_roles", ()))
    if admin_roles:
        findings.append(Finding("ADMIN_ROLES", "medium", "Roles grant Administrator", ", ".join(admin_roles[:20])))
    role_count = int(snapshot.get("role_count", 0))
    if role_count >= 225:
        findings.append(Finding("ROLE_LIMIT", "high", "Role limit is close", f"{role_count}/250 roles are in use."))
    channel_count = int(snapshot.get("channel_count", 0))
    if channel_count >= 450:
        findings.append(Finding("CHANNEL_LIMIT", "high", "Channel limit is close", f"{channel_count}/500 channels are in use."))
    if snapshot.get("bot_role_low"):
        findings.append(
            Finding(
                "BOT_ROLE_LOW",
                "high",
                "Bot role cannot manage elevated roles",
                "Move the bot role above roles it must assign or moderate.",
            )
        )
    blocked = list(snapshot.get("blocked_text_channels", ()))
    if blocked:
        findings.append(Finding("CHANNEL_ACCESS", "medium", "Bot cannot send in text channels", ", ".join(blocked[:20])))
    empty_roles = int(snapshot.get("empty_unmanaged_roles", 0))
    if empty_roles >= 10:
        findings.append(Finding("EMPTY_ROLES", "low", "Many roles have no members", f"{empty_roles} unmanaged roles are empty."))
    duplicate_names = list(snapshot.get("duplicate_role_names", ()))
    if duplicate_names:
        findings.append(Finding("DUPLICATE_ROLE_NAMES", "low", "Role names are duplicated", ", ".join(duplicate_names[:20])))
    return findings


def finding_changes(previous_codes: list[str], findings: list[Finding]) -> tuple[list[Finding], list[str]]:
    """Return new findings and codes that disappeared since the prior scan."""
    previous = set(previous_codes)
    current = {item.code for item in findings}
    return [item for item in findings if item.code not in previous], sorted(previous - current)
