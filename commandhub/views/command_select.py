"""Command select component."""

from __future__ import annotations

from typing import TYPE_CHECKING

import discord

if TYPE_CHECKING:
    from commandhub.models import HubCommand


class CommandSelect(discord.ui.Select):
    def __init__(self, commands: list[HubCommand], *, row: int = 1) -> None:
        self.command_keys = [command.key for command in commands]
        options = [
            discord.SelectOption(
                label=command.display_name[:100],
                value=str(index),
                description=command.description[:100] if command.description else None,
            )
            for index, command in enumerate(commands)
        ] or [discord.SelectOption(label="No commands available", value="__none__")]
        super().__init__(placeholder="Choose a command", options=options, disabled=not commands, row=row)

    async def callback(self, interaction: discord.Interaction) -> None:
        view = self.view
        if view is not None and self.values[0] != "__none__":
            await view.select_command(interaction, self.command_keys[int(self.values[0])])
