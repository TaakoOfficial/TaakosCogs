"""Strict, bounded correlation for Discord audit-log entries."""

from __future__ import annotations

import datetime
import time
from collections import defaultdict, deque
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Collection


@dataclass(frozen=True, slots=True)
class AuditMatch:
    """A correlated audit entry and how certain the match is."""

    entry: Any
    confidence: str
    added_role_ids: frozenset[int] = frozenset()
    removed_role_ids: frozenset[int] = frozenset()
    changed_keys: frozenset[str] = frozenset()


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
        self.role_matches = 0
        self.field_matches = 0

    @staticmethod
    def _action_key(action: Any) -> str:
        return str(getattr(action, "name", action))

    @staticmethod
    def _target_id(entry: Any) -> int | str | None:
        target = getattr(entry, "target", None)
        value = target if isinstance(target, int | str) else getattr(target, "id", None)
        if value is None:
            value = getattr(entry, "target_id", None)
        if value is None:
            value = getattr(target, "code", None)
        try:
            return int(value) if value is not None else None
        except (TypeError, ValueError):
            return str(value) if value is not None else None

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

    @staticmethod
    def _role_ids(value: Any) -> frozenset[int]:
        role_ids = set()
        for role in value or ():
            role_id = getattr(role, "id", role)
            try:
                role_ids.add(int(role_id))
            except (TypeError, ValueError):
                continue
        return frozenset(role_ids)

    @classmethod
    def _role_delta(cls, entry: Any) -> tuple[frozenset[int], frozenset[int], bool]:
        before = getattr(entry, "before", None)
        after = getattr(entry, "after", None)
        before_roles = getattr(before, "roles", None)
        after_roles = getattr(after, "roles", None)
        available = before_roles is not None or after_roles is not None
        if not available:
            return frozenset(), frozenset(), False
        before_ids = cls._role_ids(before_roles)
        after_ids = cls._role_ids(after_roles)
        return after_ids - before_ids, before_ids - after_ids, True

    @staticmethod
    def _canonical_key(name: str) -> str:
        aliases = {
            "communication_disabled_until": "timeout",
            "timed_out_until": "timeout",
            "timeout": "timeout",
        }
        return aliases.get(name, name)

    @staticmethod
    def _changed_keys(entry: Any) -> frozenset[str]:
        before = getattr(entry, "before", None)
        after = getattr(entry, "after", None)
        attributes: set[str] = set()
        for diff in (before, after):
            if diff is None:
                continue
            try:
                attributes.update(str(name) for name, _value in diff)
            except (TypeError, ValueError):
                attributes.update(str(name) for name in vars(diff) if not str(name).startswith("_"))
        return frozenset(
            AuditCorrelator._canonical_key(name)
            for name in attributes
            if getattr(before, name, None) != getattr(after, name, None)
        )

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
        target_id: int | str | None = None,
        channel_id: int | None = None,
        max_age_seconds: int = 30,
        added_role_ids: Collection[int] | None = None,
        removed_role_ids: Collection[int] | None = None,
        changed_keys: Collection[str] | None = None,
    ) -> AuditMatch | None:
        """Return a strict recent match; never substitute an unrelated target."""
        self._prune()
        action_key = self._action_key(action)
        now = datetime.datetime.now(datetime.timezone.utc)
        expected_added = self._role_ids(added_role_ids)
        expected_removed = self._role_ids(removed_role_ids)
        expected_keys = frozenset(self._canonical_key(str(key)) for key in (changed_keys or ()))
        expects_roles = bool(expected_added or expected_removed)
        candidates: list[tuple[int, float, Any, frozenset[int], frozenset[int], frozenset[str]]] = []

        for cached in reversed(self._entries.get(int(guild_id), ())):
            entry = cached.entry
            if self._action_key(getattr(entry, "action", None)) != action_key:
                continue
            age = self._entry_age(entry, now)
            if age > max_age_seconds:
                continue

            entry_target_id = self._target_id(entry)
            entry_channel_id = self._channel_id(entry)
            expected_target = target_id
            try:
                expected_target = int(target_id) if target_id is not None else None
            except (TypeError, ValueError):
                expected_target = str(target_id)
            if expected_target is not None and entry_target_id != expected_target:
                continue
            if channel_id is not None and entry_channel_id is not None and entry_channel_id != int(channel_id):
                continue
            if channel_id is not None and target_id is None and entry_channel_id is None:
                continue

            candidate_added, candidate_removed, role_delta_available = self._role_delta(entry)
            if expects_roles:
                if not role_delta_available:
                    continue
                if expected_added and not expected_added.issubset(candidate_added):
                    continue
                if expected_removed and not expected_removed.issubset(candidate_removed):
                    continue

            candidate_keys = self._changed_keys(entry)
            if expected_keys and not expected_keys.issubset(candidate_keys):
                continue

            score = 1
            if target_id is not None:
                score += 4
            if channel_id is not None and entry_channel_id == int(channel_id):
                score += 3
            if expects_roles:
                exact_delta = expected_added == candidate_added and expected_removed == candidate_removed
                score += 8 if exact_delta else 6
            if expected_keys:
                score += 5 if expected_keys == candidate_keys else 3
            candidates.append((score, -age, entry, candidate_added, candidate_removed, candidate_keys))

        if not candidates:
            self.misses += 1
            return None

        score, _age, entry, candidate_added, candidate_removed, candidate_keys = max(
            candidates,
            key=lambda item: (item[0], item[1]),
        )
        self.matches += 1
        if expects_roles:
            self.role_matches += 1
        if expected_keys:
            self.field_matches += 1
        confidence = "confirmed" if score >= 5 else "probable"
        return AuditMatch(
            entry=entry,
            confidence=confidence,
            added_role_ids=candidate_added,
            removed_role_ids=candidate_removed,
            changed_keys=candidate_keys,
        )

    def stats(self) -> dict[str, int]:
        self._prune()
        return {
            "cached_entries": sum(len(entries) for entries in self._entries.values()),
            "matches": self.matches,
            "misses": self.misses,
            "duplicates": self.duplicates,
            "role_matches": self.role_matches,
            "field_matches": self.field_matches,
        }
