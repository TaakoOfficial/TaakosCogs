"""Regression coverage for DeepDelve administrator utilities."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

from deepdelve.deepdelve import DeepDelve


def test_grant_turns_updates_an_existing_character_immediately() -> None:
    async def check() -> None:
        profile = {"created": True, "gold": 204, "turns": 4}
        member = SimpleNamespace(id=22, mention="<@22>")
        ctx = SimpleNamespace(guild=SimpleNamespace(id=11), send=AsyncMock())
        cog = object.__new__(DeepDelve)
        cog._lock_for = lambda _guild_id, _user_id: asyncio.Lock()
        cog._get_profile = AsyncMock(return_value=profile)
        cog._save_profile = AsyncMock(return_value=profile)

        await DeepDelve.grant_turns.callback(cog, ctx, member, 20)

        assert profile["turns"] == 24
        cog._save_profile.assert_awaited_once_with(11, 22, profile, 204)
        ctx.send.assert_awaited_once_with(
            "Granted **20 turns** to <@22>. They now have **24 turns**.",
        )

    asyncio.run(check())


def test_grant_turns_rejects_invalid_amounts_without_loading_a_profile() -> None:
    async def check() -> None:
        member = SimpleNamespace(id=22, mention="<@22>")
        ctx = SimpleNamespace(guild=SimpleNamespace(id=11), send=AsyncMock())
        cog = object.__new__(DeepDelve)
        cog._get_profile = AsyncMock()

        await DeepDelve.grant_turns.callback(cog, ctx, member, 0)

        cog._get_profile.assert_not_awaited()
        ctx.send.assert_awaited_once_with("Granted turns must be between 1 and 100.")

    asyncio.run(check())


def test_grant_turns_rejects_members_without_characters() -> None:
    async def check() -> None:
        profile = {"created": False, "gold": 40, "turns": 0}
        member = SimpleNamespace(id=22, mention="<@22>")
        ctx = SimpleNamespace(guild=SimpleNamespace(id=11), send=AsyncMock())
        cog = object.__new__(DeepDelve)
        cog._lock_for = lambda _guild_id, _user_id: asyncio.Lock()
        cog._get_profile = AsyncMock(return_value=profile)
        cog._save_profile = AsyncMock()

        await DeepDelve.grant_turns.callback(cog, ctx, member, 20)

        cog._save_profile.assert_not_awaited()
        ctx.send.assert_awaited_once_with("<@22> does not have a DeepDelve character.")

    asyncio.run(check())
