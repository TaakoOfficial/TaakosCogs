"""Short-lived confirmation for destructive or administrator-marked commands."""

from __future__ import annotations

from typing import Any

import discord


class ConfirmationView(discord.ui.View):
    def __init__(self, hub_view: Any, command: Any, arguments: dict[str, Any]) -> None:
        super().__init__(timeout=60)
        self.hub_view = hub_view
        self.command = command
        self.arguments = arguments

    @discord.ui.button(label="Confirm", style=discord.ButtonStyle.danger)
    async def confirm(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        self.stop()
        await self.hub_view.execute(interaction, self.command, self.arguments)

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.secondary)
    async def cancel(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        self.stop()
        await interaction.response.edit_message(content="Command cancelled.", embed=None, view=None)
