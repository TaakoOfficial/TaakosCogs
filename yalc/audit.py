"""Strict, bounded correlation for Discord audit-log entries."""

from __future__ import annotations

import datetime
import time
from collections import defaultdict, deque
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class AuditMatch:
    """A correlated audit entry and how certain the match is."""

    entry: Any
    confidence: str


@dataclass(slots=True)
class _CachedEntry:
    entry: Any
    received_at: float


class AuditCorrelator:
    """Keep a short-lived audit stream and perform strict target-aware matches."""

    def __init__(self, *, max_entries_per_guild: int = 500, ttl_seconds: int = 90):
        self.max_entries_per_guild = max_entries_per_guild
        self.ttl_seconds = ttl_seconds
        self._entries: dict[int, deque[_CachedEntry]] = defaultdict(
            lambda: deque(maxlen=self.max_entries_per_guild),
        )
        self._seen: dict[int, float] = {}
        self.matches = 0
        self.misses = 0
        self.duplicates = 0

    @staticmethod
    def _action_key(action: Any) -> str:
        return str(getattr(action, "name", action))

    @staticmethod
    def _target_id(entry: Any) -> int | None:
        target = getattr(entry, "target", None)
        value = getattr(target, "id", None)
        if value is None:
            value = getattr(entry, "target_id", None)
        try:
            return int(value) if value is not None else None
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _channel_id(entry: Any) -> int | None:
        extra = getattr(entry, "extra", None)
        value = getattr(extra, "channel_id", None)
        if value is None:
            value = getattr(getattr(extra, "channel", None), "id", None)
        try:
            return int(value) if value is not None else None
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _entry_age(entry: Any, now: datetime.datetime) -> float:
        created_at = getattr(entry, "created_at", None)
        if not isinstance(created_at, datetime.datetime):
            return 0.0
        if created_at.tzinfo is None:
            created_at = created_at.replace(tzinfo=datetime.timezone.utc)
        return max(0.0, (now - created_at).total_seconds())

    def _prune(self) -> None:
        cutoff = time.monotonic() - self.ttl_seconds
        for guild_id, entries in tuple(self._entries.items()):
            while entries and entries[0].received_at < cutoff:
                entries.popleft()
            if not entries:
                self._entries.pop(guild_id, None)
        for entry_id, timestamp in tuple(self._seen.items()):
            if timestamp < cutoff:
                self._seen.pop(entry_id, None)

    def record(self, entry: Any) -> bool:
        """Record an entry, returning False when its audit ID was already seen."""
        self._prune()
        entry_id = getattr(entry, "id", None)
        if entry_id is not None:
            try:
                numeric_id = int(entry_id)
            except (TypeError, ValueError):
                numeric_id = None
            if numeric_id is not None and numeric_id in self._seen:
                self.duplicates += 1
                return False
            if numeric_id is not None:
                self._seen[numeric_id] = time.monotonic()

        guild = getattr(entry, "guild", None)
        guild_id = getattr(guild, "id", None)
        if guild_id is None:
            return False
        self._entries[int(guild_id)].append(_CachedEntry(entry, time.monotonic()))
        return True

    def match(
        self,
        guild_id: int,
        action: Any,
        *,
        target_id: int | None = None,
        channel_id: int | None = None,
        max_age_seconds: int = 30,
    ) -> AuditMatch | None:
        """Return a strict recent match; never substitute an unrelated target."""
        self._prune()
        action_key = self._action_key(action)
        now = datetime.datetime.now(datetime.timezone.utc)
        candidates: list[tuple[int, float, Any]] = []

        for cached in reversed(self._entries.get(int(guild_id), ())):
            entry = cached.entry
            if self._action_key(getattr(entry, "action", None)) != action_key:
                continue
            age = self._entry_age(entry, now)
            if age > max_age_seconds:
                continue

            entry_target_id = self._target_id(entry)
            entry_channel_id = self._channel_id(entry)
            if target_id is not None and entry_target_id != int(target_id):
                continue
            if channel_id is not None and entry_channel_id is not None and entry_channel_id != int(channel_id):
                continue
            if channel_id is not None and target_id is None and entry_channel_id is None:
                continue

            score = 1
            if target_id is not None:
                score += 4
            if channel_id is not None and entry_channel_id == int(channel_id):
                score += 3
            candidates.append((score, -age, entry))

        if not candidates:
            self.misses += 1
            return None

        score, _age, entry = max(candidates, key=lambda item: (item[0], item[1]))
        self.matches += 1
        confidence = "confirmed" if score >= 5 else "probable"
        return AuditMatch(entry=entry, confidence=confidence)

    def stats(self) -> dict[str, int]:
        self._prune()
        return {
            "cached_entries": sum(len(entries) for entries in self._entries.values()),
            "matches": self.matches,
            "misses": self.misses,
            "duplicates": self.duplicates,
        }
