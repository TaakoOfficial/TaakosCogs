"""Regression coverage for private and intentionally public gameplay responses."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

from deepdelve.deepdelve import DeepDelve


def test_personal_slash_commands_defer_ephemerally() -> None:
    async def check() -> None:
        personal_commands = (
            "deepdelve",
            "deepdelve adventure",
            "deepdelve inventory",
            "deepdelve chronicle rumor",
            "deepdelve journal",
            "deepdelve living quests",
        )
        cog = object.__new__(DeepDelve)
        for qualified_name in personal_commands:
            response = SimpleNamespace(is_done=lambda: False)
            ctx = SimpleNamespace(
                interaction=SimpleNamespace(response=response),
                command=SimpleNamespace(qualified_name=qualified_name),
                defer=AsyncMock(),
            )
            await cog.cog_before_invoke(ctx)
            ctx.defer.assert_awaited_once_with(ephemeral=True)

    asyncio.run(check())


def test_social_slash_commands_remain_public() -> None:
    async def check() -> None:
        public_commands = (
            "deepdelve party",
            "deepdelve party create",
            "deepdelve auction browse",
            "deepdelve guild leaderboard",
            "deepdelve arena challenge",
            "deepdelve endgame worldboss",
            "deepdelve leaderboard",
        )
        cog = object.__new__(DeepDelve)
        for qualified_name in public_commands:
            response = SimpleNamespace(is_done=lambda: False)
            ctx = SimpleNamespace(
                interaction=SimpleNamespace(response=response),
                command=SimpleNamespace(qualified_name=qualified_name),
                defer=AsyncMock(),
            )
            await cog.cog_before_invoke(ctx)
            ctx.defer.assert_not_awaited()

    asyncio.run(check())


def test_prefix_commands_are_not_deferred_as_interactions() -> None:
    async def check() -> None:
        cog = object.__new__(DeepDelve)
        ctx = SimpleNamespace(
            interaction=None,
            command=SimpleNamespace(qualified_name="deepdelve chronicle rumor"),
        )
        await cog.cog_before_invoke(ctx)

    asyncio.run(check())
