"""Dynamic Discord components that survive cog reloads and bot restarts."""

from __future__ import annotations

import asyncio
import logging
import re
from typing import TYPE_CHECKING, Any

import discord

if TYPE_CHECKING:
    from .deepdelve import DeepDelve

BUTTON_TEMPLATE = re.compile(r"deepdelve:b:(?P<user_id>[0-9]+):(?P<route>[a-z0-9_:-]+)")
SELECT_TEMPLATE = re.compile(r"deepdelve:s:(?P<user_id>[0-9]+):(?P<route>[a-z0-9_:-]+)")
LOGGER = logging.getLogger("red.taakoscogs.deepdelve")
LIVE_VIEW_HANDOFF_SECONDS = 0.1


def persistent_custom_id(kind: str, user_id: int, route: str) -> str:
    """Build a stable, owner-bound component identifier."""
    return f"deepdelve:{kind}:{int(user_id)}:{route}"[:100]


async def _reject(interaction: discord.Interaction, message: str) -> None:
    if interaction.response.is_done():
        await interaction.followup.send(message, ephemeral=True)
    else:
        await interaction.response.send_message(message, ephemeral=True)


def _resolve_cog(interaction: discord.Interaction) -> DeepDelve | None:
    cog = interaction.client.get_cog("DeepDelve")
    return cog if cog is not None else None


async def _handled_by_live_view(interaction: discord.Interaction) -> bool:
    """Give a message-bound view first refusal before using restart recovery.

    Discord.py schedules matching dynamic items even when the same message still has
    a live, stateful view registered. That would otherwise execute every click twice.
    Live callbacks acknowledge immediately; restored messages remain unanswered and
    fall through to the dynamic route after this short handoff.
    """
    await asyncio.sleep(LIVE_VIEW_HANDOFF_SECONDS)
    return interaction.response.is_done()


class DeepDelveDynamicButton(
    discord.ui.DynamicItem[discord.ui.Button],
    template=BUTTON_TEMPLATE,
):
    """Reconstruct an owner-bound DeepDelve button from its custom ID."""

    def __init__(self, item: discord.ui.Button, user_id: int, route: str) -> None:
        super().__init__(item)
        self.user_id = int(user_id)
        self.route = route

    @classmethod
    async def from_custom_id(
        cls,
        interaction: discord.Interaction,
        item: discord.ui.Item[Any],
        match: re.Match[str],
        /,
    ) -> DeepDelveDynamicButton:
        if not isinstance(item, discord.ui.Button):
            raise TypeError("DeepDelve dynamic button received a non-button component")
        return cls(item, int(match["user_id"]), match["route"])

    async def interaction_check(self, interaction: discord.Interaction, /) -> bool:
        if interaction.user.id == self.user_id:
            return True
        await _reject(
            interaction,
            "This adventure belongs to another delver. Use `/deepdelve adventure` to open yours.",
        )
        return False

    async def callback(self, interaction: discord.Interaction) -> None:
        if await _handled_by_live_view(interaction):
            return
        cog = _resolve_cog(interaction)
        if cog is None:
            await _reject(interaction, "DeepDelve is reloading. Try that control again in a moment.")
            return
        try:
            await cog._dispatch_persistent_button(interaction, self.route)
        except Exception as error:
            LOGGER.error(
                "Persistent DeepDelve button failed for route %s",
                self.route,
                exc_info=(type(error), error, error.__traceback__),
            )
            await _reject(
                interaction,
                "DeepDelve hit an unexpected snag. Your progress is safe; reopen the current screen and try again.",
            )


class DeepDelveDynamicSelect(
    discord.ui.DynamicItem[discord.ui.Select],
    template=SELECT_TEMPLATE,
):
    """Reconstruct a state-aware DeepDelve selector from its custom ID."""

    def __init__(self, item: discord.ui.Select, user_id: int, route: str) -> None:
        super().__init__(item)
        self.user_id = int(user_id)
        self.route = route

    @classmethod
    async def from_custom_id(
        cls,
        interaction: discord.Interaction,
        item: discord.ui.Item[Any],
        match: re.Match[str],
        /,
    ) -> DeepDelveDynamicSelect:
        if not isinstance(item, discord.ui.Select):
            raise TypeError("DeepDelve dynamic selector received a non-select component")
        return cls(item, int(match["user_id"]), match["route"])

    async def interaction_check(self, interaction: discord.Interaction, /) -> bool:
        if interaction.user.id == self.user_id:
            return True
        await _reject(
            interaction,
            "This adventure belongs to another delver. Use `/deepdelve adventure` to open yours.",
        )
        return False

    async def callback(self, interaction: discord.Interaction) -> None:
        if await _handled_by_live_view(interaction):
            return
        cog = _resolve_cog(interaction)
        if cog is None:
            await _reject(interaction, "DeepDelve is reloading. Try that control again in a moment.")
            return
        try:
            await cog._dispatch_persistent_select(interaction, self.route, list(self.item.values))
        except Exception as error:
            LOGGER.error(
                "Persistent DeepDelve selector failed for route %s",
                self.route,
                exc_info=(type(error), error, error.__traceback__),
            )
            await _reject(
                interaction,
                "DeepDelve hit an unexpected snag. Your progress is safe; reopen the current screen and try again.",
            )
