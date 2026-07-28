"""Discord-independent helpers for identifying proxy-system messages."""

from __future__ import annotations

from typing import Any

# Official Discord application IDs for the two proxy systems YALC supports out
# of the box. Guilds can add other proxy applications from the dashboard.
TUPPERBOX_APPLICATION_ID = 431544605209788416
PLURALKIT_APPLICATION_ID = 466378653216014359
KNOWN_PROXY_APPLICATION_IDS = frozenset(
    {TUPPERBOX_APPLICATION_ID, PLURALKIT_APPLICATION_ID},
)
PROXY_NAME_MARKERS = ("tupperbox", "tupperhook", "pluralkit", "plural kit")


def normalize_proxy_ids(values: Any) -> set[int]:
    """Return valid positive Discord IDs from mixed string/integer settings."""
    normalized: set[int] = set()
    for value in values or ():
        try:
            item = int(value)
        except (TypeError, ValueError):
            continue
        if item > 0:
            normalized.add(item)
    return normalized


def proxy_metadata_matches(
    *,
    configured_ids: Any,
    webhook_id: Any = None,
    application_id: Any = None,
    author_id: Any = None,
    author_is_bot: bool = False,
    author_name: str = "",
    webhook_owner_id: Any = None,
    webhook_name: str = "",
) -> bool:
    """Identify proxy metadata without relying on persona names or content."""
    proxy_ids = KNOWN_PROXY_APPLICATION_IDS | normalize_proxy_ids(configured_ids)

    direct_ids = normalize_proxy_ids((application_id, webhook_owner_id))
    if proxy_ids & direct_ids:
        return True

    if not webhook_id and author_is_bot and normalize_proxy_ids((author_id,)) & proxy_ids:
        return True

    if webhook_id:
        names = f"{author_name} {webhook_name}".casefold()
        return any(marker in names for marker in PROXY_NAME_MARKERS)
    return False
