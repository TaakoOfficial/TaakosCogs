"""Behavioral tests for YALC audit correlation and role-delta batching."""

from __future__ import annotations

import asyncio
import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock

from yalc.audit import AuditCorrelator
from yalc.yalc import YALC

UTC = datetime.timezone.utc


def role(role_id: int) -> SimpleNamespace:
    return SimpleNamespace(id=role_id)


def entry(
    entry_id: int,
    *,
    guild_id: int = 1,
    target_id: int = 10,
    before_roles: tuple[int, ...] = (),
    after_roles: tuple[int, ...] = (),
    action: str = "member_role_update",
    age_seconds: int = 0,
    channel_id: int | None = None,
) -> SimpleNamespace:
    extra = SimpleNamespace(channel_id=channel_id) if channel_id is not None else None
    return SimpleNamespace(
        id=entry_id,
        guild=SimpleNamespace(id=guild_id),
        target=SimpleNamespace(id=target_id),
        action=action,
        created_at=datetime.datetime.now(UTC) - datetime.timedelta(seconds=age_seconds),
        before=SimpleNamespace(roles=[role(value) for value in before_roles]),
        after=SimpleNamespace(roles=[role(value) for value in after_roles]),
        extra=extra,
    )


def test_correlates_exact_role_delta_and_direction() -> None:
    correlator = AuditCorrelator()
    added = entry(1, before_roles=(100,), after_roles=(100, 200))
    removed = entry(2, before_roles=(100, 300), after_roles=(100,))
    assert correlator.record(added)
    assert correlator.record(removed)

    added_match = correlator.match(1, "member_role_update", target_id=10, added_role_ids={200})
    removed_match = correlator.match(1, "member_role_update", target_id=10, removed_role_ids={300})

    assert added_match and added_match.entry is added
    assert added_match.added_role_ids == frozenset({200})
    assert removed_match and removed_match.entry is removed
    assert removed_match.removed_role_ids == frozenset({300})
    assert correlator.stats()["role_matches"] == 2


def test_never_attributes_an_unrelated_member() -> None:
    correlator = AuditCorrelator()
    correlator.record(entry(1, target_id=99, before_roles=(), after_roles=(200,)))
    assert correlator.match(1, "member_role_update", target_id=10, added_role_ids={200}) is None
    assert correlator.stats()["misses"] == 1


def test_prefers_newest_equally_strict_match() -> None:
    correlator = AuditCorrelator()
    older = entry(1, before_roles=(), after_roles=(200,), age_seconds=8)
    newer = entry(2, before_roles=(), after_roles=(200,), age_seconds=1)
    correlator.record(older)
    correlator.record(newer)
    match = correlator.match(1, "member_role_update", target_id=10, added_role_ids={200})
    assert match and match.entry is newer


def test_rejects_stale_entries_and_duplicate_ids() -> None:
    correlator = AuditCorrelator()
    stale = entry(1, before_roles=(), after_roles=(200,), age_seconds=60)
    assert correlator.record(stale)
    assert not correlator.record(stale)
    assert (
        correlator.match(
            1,
            "member_role_update",
            target_id=10,
            added_role_ids={200},
            max_age_seconds=30,
        )
        is None
    )
    assert correlator.stats()["duplicates"] == 1


def test_channel_matches_are_strict_when_no_target_is_available() -> None:
    correlator = AuditCorrelator()
    matching = entry(1, action="message_delete", channel_id=55)
    correlator.record(matching)
    assert correlator.match(1, "message_delete", channel_id=55).entry is matching
    assert correlator.match(1, "message_delete", channel_id=56) is None


def test_changed_field_aliases_match_timeout_updates() -> None:
    correlator = AuditCorrelator()
    timeout_entry = entry(1, action="member_update")
    timeout_entry.before = SimpleNamespace(communication_disabled_until=None)
    timeout_entry.after = SimpleNamespace(communication_disabled_until=datetime.datetime.now(UTC))
    correlator.record(timeout_entry)
    match = correlator.match(1, "member_update", target_id=10, changed_keys={"timeout"})
    assert match and match.changed_keys == frozenset({"timeout"})


def test_member_role_batch_resolves_all_cached_deltas_with_one_lookup() -> None:
    correlator = AuditCorrelator()
    first = entry(1, before_roles=(), after_roles=(200,))
    second = entry(2, before_roles=(300,), after_roles=())
    correlator.record(first)
    correlator.record(second)
    lookup = AsyncMock(return_value=first)
    fake_cog = SimpleNamespace(_audit_correlator=correlator, _get_audit_log_entry=lookup)

    result = asyncio.run(
        YALC._get_member_role_audit_entries(
            fake_cog,
            SimpleNamespace(id=1),
            SimpleNamespace(id=10),
            [role(200)],
            [role(300)],
        ),
    )

    assert result == {("added", 200): first, ("removed", 300): second}
    assert lookup.await_count == 1


def test_member_role_batch_caps_late_audit_refreshes_at_two() -> None:
    correlator = AuditCorrelator()
    first = entry(1, before_roles=(), after_roles=(200,))
    late = entry(2, before_roles=(300,), after_roles=())

    async def lookup(*_args, added_role_ids=None, removed_role_ids=None, **_kwargs):
        if added_role_ids == {200}:
            correlator.record(first)
            return first
        if removed_role_ids == {300}:
            correlator.record(late)
            return late
        return None

    mocked_lookup = AsyncMock(side_effect=lookup)
    fake_cog = SimpleNamespace(_audit_correlator=correlator, _get_audit_log_entry=mocked_lookup)
    result = asyncio.run(
        YALC._get_member_role_audit_entries(
            fake_cog,
            SimpleNamespace(id=1),
            SimpleNamespace(id=10),
            [role(200)],
            [role(300)],
        ),
    )
    assert result == {("added", 200): first, ("removed", 300): late}
    assert mocked_lookup.await_count == 2


def test_safe_send_retries_recoverable_failures_without_reordering(monkeypatch) -> None:
    sent_message = object()
    channel = SimpleNamespace(
        id=50,
        guild=SimpleNamespace(id=1),
        send=AsyncMock(side_effect=[RuntimeError("one"), RuntimeError("two"), sent_message]),
    )
    bot = SimpleNamespace(cog_disabled_in_guild=AsyncMock(return_value=False))
    fake_cog = SimpleNamespace(
        bot=bot,
        log=SimpleNamespace(warning=lambda *_args: None, error=lambda *_args: None),
        _embed_event_types={},
        _delivery_stats={"sent": 0, "fallback": 0, "failed": 0, "retries": 0},
        _apply_event_style=AsyncMock(),
        _reset_send_files=lambda _kwargs: None,
        _record_delivered_event=AsyncMock(),
    )
    sleep = AsyncMock()
    monkeypatch.setattr("yalc.yalc.asyncio.sleep", sleep)

    result = asyncio.run(YALC.safe_send(fake_cog, channel, content="event"))

    assert result is sent_message
    assert channel.send.await_count == 3
    assert fake_cog._delivery_stats == {"sent": 1, "fallback": 0, "failed": 0, "retries": 2}
    assert [call.args[0] for call in sleep.await_args_list] == [1, 2]
    fake_cog._record_delivered_event.assert_awaited_once_with(None, 50)
