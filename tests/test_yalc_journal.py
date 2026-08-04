"""Behavioral tests for YALC's privacy-aware event journal."""

from __future__ import annotations

import asyncio
import datetime
import json
from typing import TYPE_CHECKING

from yalc.models import LogEvent
from yalc.storage import EventJournal

if TYPE_CHECKING:
    from pathlib import Path

UTC = datetime.timezone.utc


def test_log_event_removes_message_content_by_default() -> None:
    event = LogEvent(
        guild_id=1,
        event_type="message_edit",
        summary="message edited",
        details={"content": "secret", "before_content": "old", "after_content": "new", "message_id": 10},
    )
    payload = event.journal_payload(include_content=False)
    assert payload["details"] == {"message_id": 10}
    assert event.details["content"] == "secret"


def test_journal_deduplicates_audit_event_identity(tmp_path: Path) -> None:
    async def scenario() -> dict:
        journal = EventJournal(tmp_path / "events.sqlite3")
        await journal.initialize()
        event = LogEvent(
            guild_id=1,
            event_type="member_ban",
            summary="member banned",
            target_id=10,
            audit_entry_id=99,
        )
        await journal.add(event, include_content=False)
        await journal.add(event, include_content=False)
        return await journal.stats(1)

    assert asyncio.run(scenario())["count"] == 1


def test_journal_search_is_scoped_by_guild_and_event(tmp_path: Path) -> None:
    async def scenario() -> list[dict]:
        journal = EventJournal(tmp_path / "events.sqlite3")
        await journal.initialize()
        await journal.add(LogEvent(1, "member_ban", "matched moderator action"), include_content=False)
        await journal.add(LogEvent(1, "message_edit", "matched message"), include_content=False)
        await journal.add(LogEvent(2, "member_ban", "matched other guild"), include_content=False)
        return await journal.search(1, query="matched", event_type="member_ban")

    rows = asyncio.run(scenario())
    assert len(rows) == 1
    assert rows[0]["event_type"] == "member_ban"


def test_delete_user_removes_nested_privacy_references(tmp_path: Path) -> None:
    async def scenario() -> tuple[int, int]:
        journal = EventJournal(tmp_path / "events.sqlite3")
        await journal.initialize()
        event = LogEvent(
            guild_id=1,
            event_type="member_update",
            summary="roles changed",
            details={"moderator": {"id": "42"}},
        )
        await journal.add(event, include_content=False)
        deleted = await journal.delete_user(42)
        stats = await journal.stats(1)
        return deleted, stats["count"]

    assert asyncio.run(scenario()) == (1, 0)


def test_prune_removes_only_expired_guild_events(tmp_path: Path) -> None:
    async def scenario() -> tuple[int, int, int]:
        journal = EventJournal(tmp_path / "events.sqlite3")
        await journal.initialize()
        old = LogEvent(
            1,
            "member_join",
            "old",
            occurred_at=datetime.datetime.now(UTC) - datetime.timedelta(days=40),
        )
        current = LogEvent(1, "member_join", "current")
        other_guild = LogEvent(
            2,
            "member_join",
            "other",
            occurred_at=datetime.datetime.now(UTC) - datetime.timedelta(days=40),
        )
        for event in (old, current, other_guild):
            await journal.add(event, include_content=False)
        removed = await journal.prune(1, 30)
        return removed, (await journal.stats(1))["count"], (await journal.stats(2))["count"]

    assert asyncio.run(scenario()) == (1, 1, 1)


def test_stored_payload_never_contains_content_when_disabled(tmp_path: Path) -> None:
    async def scenario() -> dict:
        journal = EventJournal(tmp_path / "events.sqlite3")
        await journal.initialize()
        await journal.add(
            LogEvent(1, "message_delete", "deleted", details={"content": "private", "message_id": 7}),
            include_content=False,
        )
        rows = await journal.search(1)
        return json.loads(rows[0]["payload_json"])

    assert asyncio.run(scenario())["details"] == {"message_id": 7}
