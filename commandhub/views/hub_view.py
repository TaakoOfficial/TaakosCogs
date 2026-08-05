"""Paginated hub browser session."""

from __future__ import annotations

import contextlib
from typing import TYPE_CHECKING, Any

import discord

from commandhub.utils import paginate, rank_commands

from .argument_modal import ArgumentModal
from .command_select import CommandSelect
from .confirmation_view import ConfirmationView
from .search_modal import SearchModal

if TYPE_CHECKING:
    from commandhub.models import CommandAssignment, Hub, HubCommand


class CategorySelect(discord.ui.Select):
    def __init__(self, categories: list[str], current: str) -> None:
        super().__init__(
            placeholder="Choose a category",
            options=[
                discord.SelectOption(label=name[:100], value=str(index), default=name == current)
                for index, name in enumerate(categories[:25])
            ],
            row=0,
        )
        self.categories = categories[:25]

    async def callback(self, interaction: discord.Interaction) -> None:
        view = self.view
        if view is not None:
            await view.set_category(interaction, self.categories[int(self.values[0])])


class HubView(discord.ui.View):
    PAGE_SIZE = 25

    def __init__(
        self,
        cog: Any,
        hub: Hub,
        guild_id: int,
        owner_id: int,
        commands_by_category: dict[str, list[HubCommand]],
        assignments: dict[str, CommandAssignment],
    ) -> None:
        super().__init__(timeout=600)
        self.cog = cog
        self.hub = hub
        self.guild_id = guild_id
        self.owner_id = owner_id
        self.commands_by_category = commands_by_category
        self.assignments = assignments
        self.categories = list(commands_by_category) or ["General"]
        self.category = self.categories[0]
        self.category_offset = 0
        self.page = hub.default_page
        self.search_query: str | None = None
        self.search_results: list[HubCommand] = []
        self.message: discord.InteractionMessage | None = None
        self.rebuild()

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if self.hub.ephemeral or interaction.user.id == self.owner_id:
            if interaction.user.id == self.owner_id:
                return True
            await interaction.response.send_message("This CommandHub session belongs to another user.", ephemeral=True)
            return False
        return True

    def current_commands(self) -> list[HubCommand]:
        return self.search_results if self.search_query is not None else self.commands_by_category.get(self.category, [])

    def rebuild(self) -> None:
        self.clear_items()
        if self.search_query is None and len(self.categories) > 1:
            category_page = self.categories[self.category_offset : self.category_offset + 25]
            self.add_item(CategorySelect(category_page, self.category))
        items, self.page, pages = paginate(self.current_commands(), self.page, self.PAGE_SIZE)
        self.add_item(CommandSelect(items, row=1))

        previous = discord.ui.Button(label="Previous", style=discord.ButtonStyle.secondary, disabled=self.page == 0, row=2)
        previous.callback = self.previous_page
        self.add_item(previous)
        next_button = discord.ui.Button(label="Next", style=discord.ButtonStyle.secondary, disabled=self.page >= pages - 1, row=2)
        next_button.callback = self.next_page
        self.add_item(next_button)
        if self.hub.search_enabled:
            search = discord.ui.Button(label="Search", emoji="🔎", style=discord.ButtonStyle.primary, row=2)
            search.callback = self.open_search
            self.add_item(search)
        if self.search_query is not None:
            clear = discord.ui.Button(label="Clear search", style=discord.ButtonStyle.secondary, row=3)
            clear.callback = self.clear_search
            self.add_item(clear)
        if self.hub.repeat_enabled:
            repeat = discord.ui.Button(label="Repeat", emoji="↻", style=discord.ButtonStyle.secondary, row=3)
            repeat.callback = self.repeat_last
            self.add_item(repeat)
        close = discord.ui.Button(label="Close", style=discord.ButtonStyle.danger, row=3)
        close.callback = self.close
        self.add_item(close)
        if self.search_query is None and len(self.categories) > 25:
            category_previous = discord.ui.Button(
                label="Previous categories",
                style=discord.ButtonStyle.secondary,
                disabled=self.category_offset == 0,
                row=4,
            )
            category_previous.callback = self.previous_categories
            self.add_item(category_previous)
            category_next = discord.ui.Button(
                label="Next categories",
                style=discord.ButtonStyle.secondary,
                disabled=self.category_offset + 25 >= len(self.categories),
                row=4,
            )
            category_next.callback = self.next_categories
            self.add_item(category_next)

    def embed(self) -> discord.Embed:
        items = self.current_commands()
        _, current, pages = paginate(items, self.page, self.PAGE_SIZE)
        title = f"{self.hub.emoji} {self.hub.title}" if self.hub.emoji else self.hub.title
        embed = discord.Embed(title=title[:256], description=self.hub.description[:4096], colour=discord.Colour.blurple())
        context = f"Search: {self.search_query}" if self.search_query is not None else f"Category: {self.category}"
        embed.set_footer(text=f"{context} • Page {current + 1}/{pages} • {len(items)} command(s)")
        if not items:
            embed.add_field(name="Nothing to show", value="Try another category or search.", inline=False)
        return embed

    async def update(self, interaction: discord.Interaction) -> None:
        self.rebuild()
        await interaction.response.edit_message(embed=self.embed(), view=self)

    async def set_category(self, interaction: discord.Interaction, category: str) -> None:
        self.category, self.page, self.search_query = category, 0, None
        await self.update(interaction)

    async def previous_categories(self, interaction: discord.Interaction) -> None:
        self.category_offset = max(0, self.category_offset - 25)
        self.category = self.categories[self.category_offset]
        self.page = 0
        await self.update(interaction)

    async def next_categories(self, interaction: discord.Interaction) -> None:
        self.category_offset = min(len(self.categories) - 1, self.category_offset + 25)
        self.category = self.categories[self.category_offset]
        self.page = 0
        await self.update(interaction)

    async def previous_page(self, interaction: discord.Interaction) -> None:
        self.page -= 1
        await self.update(interaction)

    async def next_page(self, interaction: discord.Interaction) -> None:
        self.page += 1
        await self.update(interaction)

    async def open_search(self, interaction: discord.Interaction) -> None:
        await interaction.response.send_modal(SearchModal(self))

    async def apply_search(self, interaction: discord.Interaction, query: str) -> None:
        all_commands = [item for values in self.commands_by_category.values() for item in values]
        self.search_query = query.strip()
        self.search_results = rank_commands(all_commands, self.search_query)
        self.page = 0
        await self.update(interaction)

    async def clear_search(self, interaction: discord.Interaction) -> None:
        self.search_query, self.search_results, self.page = None, [], 0
        await self.update(interaction)

    async def select_command(self, interaction: discord.Interaction, key: str) -> None:
        command = next((item for item in self.current_commands() if item.key == key), None)
        if command is None:
            await interaction.response.send_message("That command is no longer available. Refresh the hub.", ephemeral=True)
            return
        allowed, reason = await self.cog.invocation.can_display(interaction, command)
        if not allowed:
            await interaction.response.send_message(f"`{command.qualified_name}` is unavailable: {reason}", ephemeral=True)
            return
        if command.parameters:
            await interaction.response.send_modal(ArgumentModal(self, command))
        else:
            await self.arguments_ready(interaction, command, {})

    async def arguments_ready(self, interaction: discord.Interaction, command: HubCommand, arguments: dict[str, Any]) -> None:
        assignment = self.assignments.get(command.key)
        if assignment and assignment.confirmation_required:
            summary = self.cog.safe_argument_summary(command, arguments)
            await interaction.response.send_message(
                f"Confirm `{command.qualified_name}`?\n{summary}\nThis action was marked as requiring confirmation.",
                view=ConfirmationView(self, command, arguments),
                ephemeral=True,
            )
            return
        await self.execute(interaction, command, arguments)

    async def execute(self, interaction: discord.Interaction, command: HubCommand, arguments: dict[str, Any]) -> None:
        await self.cog.invocation.invoke(interaction, self.hub, command, arguments)

    async def repeat_last(self, interaction: discord.Interaction) -> None:
        await self.cog.repeat_last(interaction, self.hub, self)

    async def close(self, interaction: discord.Interaction) -> None:
        self.stop()
        self.cog.release_view(self)
        await interaction.response.edit_message(content="CommandHub closed.", embed=None, view=None)

    async def on_timeout(self) -> None:
        self.cog.release_view(self)
        for item in self.children:
            item.disabled = True
        if self.message is not None:
            with contextlib.suppress(discord.HTTPException):
                await self.message.edit(view=self)
