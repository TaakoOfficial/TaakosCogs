"""Command search modal."""

from __future__ import annotations

import discord


class SearchModal(discord.ui.Modal, title="Search commands"):
    query = discord.ui.TextInput(label="Command name or keywords", max_length=100)

    def __init__(self, hub_view: object) -> None:
        super().__init__(timeout=180)
        self.hub_view = hub_view

    async def on_submit(self, interaction: discord.Interaction) -> None:
        await self.hub_view.apply_search(interaction, str(self.query))
