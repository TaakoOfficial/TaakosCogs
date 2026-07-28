"""Persistent UI components for RoleManager."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import discord

if TYPE_CHECKING:
    from collections.abc import Iterable

    from .rolemanager import RoleManager


class RoleManagerView(discord.ui.View):
    """Persistent view containing RoleManager buttons and select menus."""

    def __init__(self, cog: RoleManager, *, timeout: float | None = None) -> None:
        super().__init__(timeout=timeout)
        self.cog = cog


class RoleButton(discord.ui.Button):
    """A button that toggles one role for the clicking member."""

    def __init__(
        self,
        *,
        name: str,
        role_id: int,
        label: str,
        emoji: str | None,
        style: int,
        guild_id: int,
    ) -> None:
        self.name = name
        self.role_id = int(role_id)
        self._label_template = label or ""
        super().__init__(
            label=label or None,
            emoji=discord.PartialEmoji.from_str(emoji) if emoji else None,
            style=discord.ButtonStyle(style),
            custom_id=f"taakoscogs:rolemanager:button:{guild_id}:{name}",
        )

    def refresh_label(self, guild: discord.Guild) -> None:
        """Refresh dynamic label placeholders."""
        role = guild.get_role(self.role_id)
        if role is None:
            return
        if self._label_template:
            self.label = self._label_template.replace(
                "{count}",
                f"{len(role.members):,}",
            )
        elif self.label is None:
            self.label = f"@{role.name}"

    async def callback(self, interaction: discord.Interaction) -> None:
        view = self.view
        if not isinstance(view, RoleManagerView):
            return
        await view.cog.handle_button_interaction(interaction, self)


class RoleSelect(discord.ui.Select):
    """A select menu that toggles selected roles for the clicking member."""

    def __init__(
        self,
        *,
        name: str,
        guild_id: int,
        placeholder: str | None,
        min_values: int,
        max_values: int,
        options: Iterable[dict[str, Any]],
    ) -> None:
        self.name = name
        self._option_templates: dict[str, dict[str, str]] = {}
        built_options: list[discord.SelectOption] = []
        for option in options:
            role_id = int(option["role_id"])
            value = str(role_id)
            label = str(option.get("label") or "")
            description = str(option.get("description") or "")
            emoji = option.get("emoji") or None
            built = discord.SelectOption(
                label=label or "Role",
                value=value,
                description=description or None,
                emoji=discord.PartialEmoji.from_str(emoji) if emoji else None,
            )
            built_options.append(built)
            self._option_templates[value] = {
                "label": label,
                "description": description,
            }

        max_values = max(1, min(max_values, len(built_options) or 1))
        min_values = max(0, min(min_values, max_values))
        super().__init__(
            custom_id=f"taakoscogs:rolemanager:select:{guild_id}:{name}",
            placeholder=placeholder or None,
            min_values=min_values,
            max_values=max_values,
            options=built_options[:25],
        )

    def refresh_options(self, guild: discord.Guild) -> None:
        """Refresh dynamic option placeholders."""
        for option in self.options:
            role = guild.get_role(int(option.value))
            if role is None:
                continue
            template = self._option_templates.get(option.value, {})
            label = template.get("label") or f"@{role.name}"
            description = template.get("description") or None
            option.label = label.replace("{count}", f"{len(role.members):,}")[:100]
            if description:
                option.description = description.replace(
                    "{count}",
                    f"{len(role.members):,}",
                )[:100]

    async def callback(self, interaction: discord.Interaction) -> None:
        view = self.view
        if not isinstance(view, RoleManagerView):
            return
        await view.cog.handle_select_interaction(interaction, self)
