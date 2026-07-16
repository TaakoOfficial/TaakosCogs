"""Optional SQLite event journal for YALC."""

from __future__ import annotations

import asyncio
import datetime
import json
import sqlite3
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from pathlib import Path

    from .models import LogEvent


class EventJournal:
    """Small asynchronous wrapper around a per-cog SQLite journal."""

    def __init__(self, path: Path):
        self.path = path
        self._lock = asyncio.Lock()

    async def initialize(self) -> None:
        await asyncio.to_thread(self._initialize_sync)

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        return connection

    def _initialize_sync(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as connection:
            connection.executescript(
                """
                PRAGMA journal_mode=WAL;
                CREATE TABLE IF NOT EXISTS events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    guild_id INTEGER NOT NULL,
                    event_type TEXT NOT NULL,
                    occurred_at TEXT NOT NULL,
                    actor_id INTEGER,
                    target_id INTEGER,
                    source_channel_id INTEGER,
                    audit_entry_id INTEGER,
                    confidence TEXT NOT NULL,
                    summary TEXT NOT NULL,
                    payload_json TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_events_guild_time
                    ON events(guild_id, occurred_at DESC);
                CREATE INDEX IF NOT EXISTS idx_events_guild_type_time
                    ON events(guild_id, event_type, occurred_at DESC);
                DROP INDEX IF EXISTS idx_events_audit_entry;
                CREATE UNIQUE INDEX IF NOT EXISTS idx_events_event_identity
                    ON events(
                        guild_id,
                        event_type,
                        audit_entry_id,
                        COALESCE(target_id, -1),
                        COALESCE(source_channel_id, -1),
                        summary
                    )
                    WHERE audit_entry_id IS NOT NULL;
                """,
            )

    async def add(self, event: LogEvent, *, include_content: bool) -> None:
        payload = event.journal_payload(include_content=include_content)
        async with self._lock:
            await asyncio.to_thread(self._add_sync, event, payload)

    def _add_sync(self, event: LogEvent, payload: dict[str, Any]) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                INSERT OR IGNORE INTO events (
                    guild_id, event_type, occurred_at, actor_id, target_id,
                    source_channel_id, audit_entry_id, confidence, summary,
                    payload_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    event.guild_id,
                    event.event_type,
                    event.occurred_at.isoformat(),
                    event.actor_id,
                    event.target_id,
                    event.source_channel_id,
                    event.audit_entry_id,
                    event.confidence,
                    event.summary[:1000],
                    json.dumps(payload, ensure_ascii=False, default=str),
                ),
            )

    async def search(
        self,
        guild_id: int,
        *,
        query: str = "",
        event_type: str | None = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        return await asyncio.to_thread(
            self._search_sync,
            guild_id,
            query,
            event_type,
            max(1, min(limit, 500)),
        )

    def _search_sync(
        self,
        guild_id: int,
        query: str,
        event_type: str | None,
        limit: int,
    ) -> list[dict[str, Any]]:
        clauses = ["guild_id = ?"]
        values: list[Any] = [guild_id]
        if event_type:
            clauses.append("event_type = ?")
            values.append(event_type)
        if query:
            clauses.append("(summary LIKE ? OR payload_json LIKE ?)")
            wildcard = f"%{query}%"
            values.extend((wildcard, wildcard))
        values.append(limit)
        sql = "SELECT * FROM events WHERE " + " AND ".join(clauses) + " ORDER BY occurred_at DESC LIMIT ?"
        with self._connect() as connection:
            return [dict(row) for row in connection.execute(sql, values).fetchall()]

    async def stats(self, guild_id: int) -> dict[str, Any]:
        return await asyncio.to_thread(self._stats_sync, guild_id)

    def _stats_sync(self, guild_id: int) -> dict[str, Any]:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT COUNT(*) AS count, MIN(occurred_at) AS oldest, MAX(occurred_at) AS newest FROM events WHERE guild_id = ?",
                (guild_id,),
            ).fetchone()
        return dict(row) if row is not None else {"count": 0, "oldest": None, "newest": None}

    async def prune(self, guild_id: int, retention_days: int) -> int:
        cutoff = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(
            days=retention_days,
        )
        async with self._lock:
            return await asyncio.to_thread(self._prune_sync, guild_id, cutoff.isoformat())

    def _prune_sync(self, guild_id: int, cutoff: str) -> int:
        with self._connect() as connection:
            cursor = connection.execute(
                "DELETE FROM events WHERE guild_id = ? AND occurred_at < ?",
                (guild_id, cutoff),
            )
            return max(cursor.rowcount, 0)

    async def clear_guild(self, guild_id: int) -> int:
        async with self._lock:
            return await asyncio.to_thread(self._clear_sync, guild_id)

    def _clear_sync(self, guild_id: int) -> int:
        with self._connect() as connection:
            cursor = connection.execute("DELETE FROM events WHERE guild_id = ?", (guild_id,))
            return max(cursor.rowcount, 0)

    async def delete_user(self, user_id: int) -> int:
        """Delete journal rows that reference a user ID."""
        async with self._lock:
            return await asyncio.to_thread(self._delete_user_sync, user_id)

    def _delete_user_sync(self, user_id: int) -> int:
        pattern = f'%"{user_id}"%'
        with self._connect() as connection:
            cursor = connection.execute(
                """
                DELETE FROM events
                WHERE actor_id = ? OR target_id = ? OR payload_json LIKE ?
                """,
                (user_id, user_id, pattern),
            )
            return max(cursor.rowcount, 0)
