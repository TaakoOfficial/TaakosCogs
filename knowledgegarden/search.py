"""Provider-free knowledge search."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Iterable

WORD_RE = re.compile(r"[a-z\d]{2,}")


def tokens(value: str) -> set[str]:
    return set(WORD_RE.findall(value.casefold()))


def rank_entries(
    entries: Iterable[dict[str, Any]], query: str, *, published_only: bool = True
) -> list[tuple[int, dict[str, Any]]]:
    query_words = tokens(query)
    if not query_words:
        return []
    ranked = []
    for entry in entries:
        if published_only and entry.get("status") != "published":
            continue
        title = tokens(str(entry.get("title", "")))
        tags = tokens(" ".join(entry.get("tags", [])))
        aliases = tokens(" ".join(entry.get("aliases", [])))
        body = tokens(str(entry.get("body", "")))
        score = 6 * len(query_words & title) + 5 * len(query_words & aliases) + 4 * len(query_words & tags)
        score += len(query_words & body)
        if query.casefold() in str(entry.get("title", "")).casefold():
            score += 8
        if score:
            ranked.append((score, entry))
    return sorted(ranked, key=lambda item: (-item[0], -int(item[1].get("updated_at", 0)), int(item[1].get("entry_id", 0))))
