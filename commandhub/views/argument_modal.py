"""Multi-step argument collection modal."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import discord

from commandhub.converters import ConversionError, convert_argument

if TYPE_CHECKING:
    from commandhub.models import CommandParameter, HubCommand


class ArgumentModal(discord.ui.Modal):
    def __init__(
        self,
        hub_view: Any,
        command: HubCommand,
        *,
        offset: int = 0,
        arguments: dict[str, Any] | None = None,
    ) -> None:
        end = min(offset + 5, len(command.parameters))
        super().__init__(title=f"Arguments {offset + 1}-{end} of {len(command.parameters)}", timeout=300)
        self.hub_view = hub_view
        self.command = command
        self.offset = offset
        self.arguments = arguments or {}
        self.inputs: list[tuple[CommandParameter, discord.ui.TextInput]] = []
        for parameter in command.parameters[offset:end]:
            choice_hint = ", ".join(parameter.choices) if parameter.choices else parameter.kind.value.replace("_", " ")
            is_text = parameter.kind.value == "string"
            minimum_length = int(parameter.minimum) if is_text and parameter.minimum is not None else None
            maximum_length = min(4000, int(parameter.maximum)) if is_text and parameter.maximum is not None else 4000
            component = discord.ui.TextInput(
                label=parameter.name[:45],
                placeholder=(parameter.description or choice_hint)[:100],
                required=parameter.required,
                style=discord.TextStyle.paragraph if parameter.remainder else discord.TextStyle.short,
                min_length=minimum_length,
                max_length=maximum_length,
            )
            self.inputs.append((parameter, component))
            self.add_item(component)

    async def on_submit(self, interaction: discord.Interaction) -> None:
        converted = dict(self.arguments)
        try:
            for parameter, component in self.inputs:
                converted[parameter.name] = await convert_argument(interaction, parameter, str(component))
        except ConversionError as exc:
            await interaction.response.send_message(
                f"Invalid argument: {exc}\nSelect the command again to retry.", ephemeral=True
            )
            return
        next_offset = self.offset + len(self.inputs)
        if next_offset < len(self.command.parameters):
            await interaction.response.send_modal(
                ArgumentModal(self.hub_view, self.command, offset=next_offset, arguments=converted),
            )
            return
        await self.hub_view.arguments_ready(interaction, self.command, converted)
