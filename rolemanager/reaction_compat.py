"""Discord-independent compatibility helpers for imported reaction roles."""

from __future__ import annotations

import re
from typing import Any

CUSTOM_EMOJI_RE = re.compile(r"^<a?:[^:]+:(?P<id>[0-9]+)>$")
VARIATION_SELECTOR_16 = "\N{VARIATION SELECTOR-16}"


def canonical_emoji_key(emoji: Any) -> str:
    """Return the gateway-compatible key for unicode or custom emoji values."""
    emoji_id = getattr(emoji, "id", None)
    if emoji_id:
        return str(emoji_id)
    value = getattr(emoji, "name", emoji)
    text = str(value or "").strip().replace(VARIATION_SELECTOR_16, "")
    match = CUSTOM_EMOJI_RE.fullmatch(text)
    return match.group("id") if match else text


def normalize_reaction_bindings(bindings: Any) -> tuple[dict[str, dict[str, Any]], int]:
    """Normalize imported binding keys while preserving their display emoji."""
    if not isinstance(bindings, dict):
        return {}, 1
    normalized: dict[str, dict[str, Any]] = {}
    changes = 0
    for stored_key, raw_binding in bindings.items():
        if not isinstance(raw_binding, dict):
            changes += 1
            continue
        try:
            role_id = int(raw_binding.get("role_id", 0))
        except (TypeError, ValueError):
            changes += 1
            continue
        if role_id <= 0:
            changes += 1
            continue
        display_emoji = raw_binding.get("emoji") or stored_key
        key = canonical_emoji_key(display_emoji)
        if not key:
            changes += 1
            continue
        binding = dict(raw_binding)
        binding["role_id"] = role_id
        binding["emoji"] = str(display_emoji)
        binding["remove_on_unreact"] = bool(binding.get("remove_on_unreact", True))
        if str(stored_key) != key or binding != raw_binding or key in normalized:
            changes += 1
        normalized[key] = binding
    return normalized, changes
