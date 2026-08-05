"""CommandHub: configurable application-command browsers for Red."""

from __future__ import annotations

import asyncio
import contextlib
import logging
from collections import OrderedDict
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any

import discord
from redbot.core import app_commands, commands

from .config import HubConfigStore
from .dashboard_integration import DashboardIntegration
from .integrations import SlashLinkAdapter
from .invocation import InvocationEngine
from .models import CommandAssignment, CommandSource, Hub, HubCategory, HubCommand, RepeatRecord
from .registry import CommandRegistry
from .utils import Debouncer, ValidationError, is_potentially_destructive, validate_category_name, validate_hub_name
from .views import HubView
from .views.confirmation_view import ConfirmationView

if TYPE_CHECKING:
    from redbot.core.bot import Red

log = logging.getLogger("red.taakoscogs.commandhub")


class CommandHub(DashboardIntegration, commands.Cog):
    """Group loaded commands into discoverable, guild-scoped slash hubs."""

    def __init__(self, bot: Red) -> None:
        self.bot = bot
        self.store = HubConfigStore(self)
        self.slashlink = SlashLinkAdapter(bot)
        self.registry = CommandRegistry(bot, self.slashlink)
        self.invocation = InvocationEngine(self, self.slashlink)
        self._registered: dict[tuple[int, str], app_commands.Command[Any, ..., Any]] = {}
        self._sync_locks: dict[int, asyncio.Lock] = {}
        self._debouncers: dict[int, Debouncer] = {}
        self._active_views: set[HubView] = set()
        self._last_commands: OrderedDict[tuple[int, int], RepeatRecord] = OrderedDict()

    async def cog_load(self) -> None:
        old, new = await self.store.migrate()
        if old != new:
            log.info("Migrated CommandHub configuration schema from %d to %d.", old, new)
        await self.registry.refresh()
        for guild_id in await self.store.all_guild_ids():
            await self._reconcile_tree(guild_id)
        log.info("CommandHub loaded with %d configured guild(s).", len(await self.store.all_guild_ids()))

    def cog_unload(self) -> None:
        for debouncer in self._debouncers.values():
            debouncer.cancel()
        for guild_id, name in tuple(self._registered):
            self.bot.tree.remove_command(name, guild=discord.Object(id=guild_id))
        self._registered.clear()
        for view in tuple(self._active_views):
            view.stop()
        log.info("CommandHub unloaded.")

    async def red_delete_data_for_user(self, *, requester: str, user_id: int) -> None:
        self._last_commands = OrderedDict((key, value) for key, value in self._last_commands.items() if key[1] != user_id)
        for guild_id in await self.store.all_guild_ids():
            await self.store.config.member_from_ids(guild_id, user_id).clear()

    @commands.Cog.listener()
    async def on_cog_add(self, cog: commands.Cog) -> None:
        if cog is not self:
            await self.registry.refresh()

    @commands.Cog.listener()
    async def on_cog_remove(self, cog: commands.Cog) -> None:
        if cog is not self:
            await self.registry.refresh()

    async def send_interaction(self, interaction: discord.Interaction, message: str, *, ephemeral: bool) -> None:
        if interaction.response.is_done():
            await interaction.followup.send(message, ephemeral=ephemeral)
        else:
            await interaction.response.send_message(message, ephemeral=ephemeral)

    async def list_hubs_service(self, guild_id: int) -> list[Hub]:
        return await self.store.list_hubs(guild_id)

    async def create_hub_service(self, guild_id: int, name: str, **updates: Any) -> Hub:
        name = validate_hub_name(name)
        if await self.store.get_hub(guild_id, name):
            raise ValidationError(f"Hub `{name}` already exists.")
        if self._tree_name_conflict(guild_id, name):
            raise ValidationError(f"`/{name}` conflicts with an existing application command.")
        hub = Hub.create(name)
        await self.update_hub_model(hub, updates)
        await self.store.save_hub(guild_id, hub)
        await self._reconcile_tree(guild_id)
        await self.schedule_sync(guild_id)
        return hub

    async def update_hub_model(self, hub: Hub, updates: dict[str, Any]) -> Hub:
        allowed = {
            "title",
            "description",
            "emoji",
            "enabled",
            "ephemeral",
            "search_enabled",
            "repeat_enabled",
            "allowed_roles",
            "blocked_roles",
            "allowed_channels",
            "blocked_channels",
            "required_user_permissions",
            "required_bot_permissions",
            "default_page",
            "unavailable_behavior",
        }
        unknown = set(updates) - allowed
        if unknown:
            raise ValidationError(f"Unknown hub fields: {', '.join(sorted(unknown))}")
        for key, value in updates.items():
            if key == "title" and not (1 <= len(str(value)) <= 256):
                raise ValidationError("Titles must contain 1-256 characters.")
            if key == "description" and not (1 <= len(str(value)) <= 100):
                raise ValidationError("Slash-command descriptions must contain 1-100 characters.")
            if key == "unavailable_behavior" and value not in {"hide", "show"}:
                raise ValidationError("unavailable_behavior must be `hide` or `show`.")
            setattr(hub, key, value)
        return hub

    async def update_hub_service(self, guild_id: int, name: str, updates: dict[str, Any]) -> Hub:
        hub = await self.require_hub(guild_id, name)
        await self.update_hub_model(hub, updates)
        await self.store.save_hub(guild_id, hub)
        await self._reconcile_tree(guild_id)
        await self.schedule_sync(guild_id)
        return hub

    async def delete_hub_service(self, guild_id: int, name: str) -> bool:
        deleted = await self.store.delete_hub(guild_id, name)
        if deleted:
            await self._reconcile_tree(guild_id)
            await self.schedule_sync(guild_id)
        return deleted

    async def require_hub(self, guild_id: int, name: str) -> Hub:
        hub = await self.store.get_hub(guild_id, name.casefold())
        if hub is None:
            raise ValidationError(f"Hub `{name}` was not found.")
        return hub

    async def discoverable_commands_service(self) -> list[HubCommand]:
        return list(self.registry.commands.values())

    async def assign_command_service(
        self, guild_id: int, hub_name: str, reference: str, category: str = "General"
    ) -> CommandAssignment:
        hub = await self.require_hub(guild_id, hub_name)
        matches = self.registry.resolve(reference)
        if not matches:
            raise ValidationError(f"Command `{reference}` was not found in the registry.")
        if len(matches) > 1:
            sources = ", ".join(item.source.value for item in matches)
            raise ValidationError(f"Command reference is ambiguous ({sources}); use `source:{reference}`.")
        command = matches[0]
        if hub.find_assignment(command.qualified_name, command.source):
            raise ValidationError("That command is already assigned to this hub.")
        category = validate_category_name(category)
        target = hub.categories.get(category)
        if target is None:
            target = HubCategory(category, position=len(hub.categories))
            hub.categories[category] = target
        assignment = CommandAssignment(
            command.qualified_name,
            command.source,
            position=len(target.commands),
            confirmation_required=is_potentially_destructive(command.qualified_name),
        )
        target.commands.append(assignment)
        await self.store.save_hub(guild_id, hub)
        return assignment

    async def remove_command_service(self, guild_id: int, hub_name: str, reference: str) -> bool:
        hub = await self.require_hub(guild_id, hub_name)
        needle = reference.casefold()
        for category in hub.categories.values():
            for item in tuple(category.commands):
                if item.qualified_name.casefold() == needle or f"{item.source.value}:{item.qualified_name.casefold()}" == needle:
                    category.commands.remove(item)
                    for index, remaining in enumerate(category.commands):
                        remaining.position = index
                    await self.store.save_hub(guild_id, hub)
                    return True
        return False

    async def update_assignment_service(
        self,
        guild_id: int,
        hub_name: str,
        reference: str,
        updates: dict[str, bool],
    ) -> CommandAssignment:
        allowed = {"confirmation_required", "hidden", "disabled"}
        if set(updates) - allowed or not all(isinstance(value, bool) for value in updates.values()):
            raise ValidationError("Assignment updates must be boolean confirmation_required, hidden, or disabled fields.")
        hub = await self.require_hub(guild_id, hub_name)
        found = hub.find_assignment(reference)
        if found is None and ":" in reference:
            source_name, qualified_name = reference.split(":", 1)
            with contextlib.suppress(ValueError):
                found = hub.find_assignment(qualified_name, CommandSource(source_name))
        if found is None:
            raise ValidationError("That command assignment was not found.")
        assignment = found[1]
        for field, value in updates.items():
            setattr(assignment, field, value)
        await self.store.save_hub(guild_id, hub)
        return assignment

    async def reorder_commands_service(
        self,
        guild_id: int,
        hub_name: str,
        category_name: str,
        ordered_references: list[str],
    ) -> Hub:
        hub = await self.require_hub(guild_id, hub_name)
        category = hub.categories.get(category_name)
        if category is None:
            raise ValidationError("That category was not found.")
        existing = {f"{item.source.value}:{item.qualified_name.casefold()}": item for item in category.commands}
        requested = [reference.casefold() for reference in ordered_references]
        if len(requested) != len(set(requested)) or set(requested) != set(existing):
            raise ValidationError(
                "The ordered command list must contain every category assignment exactly once using source:name."
            )
        category.commands = [existing[reference] for reference in requested]
        for position, assignment in enumerate(category.commands):
            assignment.position = position
        await self.store.save_hub(guild_id, hub)
        return hub

    async def reorder_categories_service(self, guild_id: int, hub_name: str, ordered_names: list[str]) -> Hub:
        hub = await self.require_hub(guild_id, hub_name)
        if len(ordered_names) != len(set(ordered_names)) or set(ordered_names) != set(hub.categories):
            raise ValidationError("The ordered category list must contain every category exactly once.")
        for position, name in enumerate(ordered_names):
            hub.categories[name].position = position
        await self.store.save_hub(guild_id, hub)
        return hub

    async def update_permissions_service(
        self,
        guild_id: int,
        hub_name: str,
        *,
        allowed_roles: list[int],
        blocked_roles: list[int],
        allowed_channels: list[int],
        blocked_channels: list[int],
        required_user_permissions: int,
        required_bot_permissions: int,
    ) -> Hub:
        return await self.update_hub_service(
            guild_id,
            hub_name,
            {
                "allowed_roles": list(dict.fromkeys(allowed_roles)),
                "blocked_roles": list(dict.fromkeys(blocked_roles)),
                "allowed_channels": list(dict.fromkeys(allowed_channels)),
                "blocked_channels": list(dict.fromkeys(blocked_channels)),
                "required_user_permissions": required_user_permissions,
                "required_bot_permissions": required_bot_permissions,
            },
        )

    async def sync_status_service(self, guild_id: int) -> dict[str, Any]:
        return await self.store.config.guild_from_id(guild_id).sync_state()

    async def schedule_sync(self, guild_id: int) -> None:
        settings = await self.store.settings(guild_id)
        await self.store.set_sync_state(guild_id, pending=True)
        debouncer = self._debouncers.get(guild_id)
        if debouncer is None:

            async def callback() -> None:
                await self.sync_guild(guild_id)

            debouncer = self._debouncers[guild_id] = Debouncer(callback)
        debouncer.schedule(float(settings.get("sync_debounce_seconds", 10)))

    def _tree_name_conflict(self, guild_id: int, name: str, *, allow_owned: bool = False) -> bool:
        global_command = self.bot.tree.get_command(name)
        guild_command = self.bot.tree.get_command(name, guild=discord.Object(id=guild_id))
        found = guild_command or global_command
        if found is None:
            return False
        return not (allow_owned and found.extras.get("commandhub") and found.extras.get("commandhub_guild") == guild_id)

    async def _reconcile_tree(self, guild_id: int) -> None:
        hubs = {hub.name: hub for hub in await self.store.list_hubs(guild_id) if hub.enabled}
        existing = {name for (registered_guild, name) in self._registered if registered_guild == guild_id}
        guild = discord.Object(id=guild_id)
        for name in existing - set(hubs):
            self.bot.tree.remove_command(name, guild=guild)
            self._registered.pop((guild_id, name), None)
            log.info("Removed CommandHub tree entry /%s for guild %d.", name, guild_id)
        for name, hub in hubs.items():
            current = self._registered.get((guild_id, name))
            if current and current.description == hub.description:
                continue
            if current:
                self.bot.tree.remove_command(name, guild=guild)
                self._registered.pop((guild_id, name), None)
            if self._tree_name_conflict(guild_id, name):
                log.error("Cannot register CommandHub /%s in guild %d: name conflict.", name, guild_id)
                continue

            callback = self._make_hub_callback(guild_id, name)
            callback.__module__ = self.__module__
            command = app_commands.Command(
                name=name,
                description=hub.description[:100],
                callback=callback,
                extras={"commandhub": True, "commandhub_guild": guild_id},
            )
            try:
                self.bot.tree.add_command(command, guild=guild)
            except app_commands.CommandAlreadyRegistered:
                log.error("Could not register CommandHub /%s in guild %d: already registered.", name, guild_id)
                continue
            self._registered[(guild_id, name)] = command
            log.info("Registered CommandHub tree entry /%s for guild %d.", name, guild_id)

    def _make_hub_callback(self, guild_id: int, name: str) -> Any:
        async def callback(interaction: discord.Interaction) -> None:
            await self.open_hub(interaction, guild_id, name)

        return callback

    async def sync_guild(self, guild_id: int) -> None:
        lock = self._sync_locks.setdefault(guild_id, asyncio.Lock())
        async with lock:
            await self._reconcile_tree(guild_id)
            try:
                await self.bot.tree.sync(guild=discord.Object(id=guild_id))
            except Exception as exc:
                message = f"{type(exc).__name__}: {exc}"[:500]
                await self.store.set_sync_state(guild_id, error=message)
                log.exception("CommandHub tree sync failed for guild %d.", guild_id)
                raise
            timestamp = datetime.now(timezone.utc).isoformat()
            await self.store.set_sync_state(guild_id, success=timestamp)
            log.info("CommandHub tree sync completed for guild %d.", guild_id)

    async def open_hub(self, interaction: discord.Interaction, guild_id: int, name: str) -> None:
        if interaction.guild_id != guild_id:
            await self.send_interaction(interaction, "This hub belongs to another server.", ephemeral=True)
            return
        hub = await self.store.get_hub(guild_id, name)
        if hub is None or not hub.enabled:
            await self.send_interaction(interaction, "This hub is disabled or no longer exists.", ephemeral=True)
            return
        allowed, reason = await self.invocation.can_access_hub(interaction, hub)
        if not allowed:
            await self.send_interaction(interaction, reason or "You cannot access this hub.", ephemeral=True)
            return
        commands_by_category: dict[str, list[HubCommand]] = {}
        assignments: dict[str, CommandAssignment] = {}
        for category, assignment in hub.assignments():
            if assignment.hidden or assignment.disabled:
                continue
            command = self.registry.get(assignment.source, assignment.qualified_name)
            if command is None:
                if hub.unavailable_behavior == "hide":
                    continue
                command = HubCommand(
                    assignment.source,
                    assignment.qualified_name,
                    assignment.qualified_name,
                    "Unavailable (cog unloaded or command renamed)",
                    None,
                    category,
                    enabled=False,
                )
            can_run, unavailable_reason = await self.invocation.can_display(interaction, command)
            if not can_run and hub.unavailable_behavior == "hide":
                continue
            if not can_run:
                command = HubCommand(
                    command.source,
                    command.qualified_name,
                    command.display_name,
                    f"Unavailable: {unavailable_reason}",
                    command.cog_name,
                    category,
                    command.parameters,
                    command.checks,
                    command.required_user_permissions,
                    command.required_bot_permissions,
                    command.nsfw,
                    False,
                    command.callback,
                    unavailable_reason,
                )
            commands_by_category.setdefault(category, []).append(command)
            assignments[command.key] = assignment
        for current_view in tuple(self._active_views):
            if current_view.guild_id == guild_id and current_view.owner_id == interaction.user.id:
                current_view.stop()
                self.release_view(current_view)
        while len(self._active_views) >= 1000:
            stale_view = self._active_views.pop()
            stale_view.stop()
        view = HubView(self, hub, guild_id, interaction.user.id, commands_by_category, assignments)
        self._active_views.add(view)
        await interaction.response.send_message(embed=view.embed(), view=view, ephemeral=hub.ephemeral)
        with contextlib.suppress(discord.HTTPException):
            view.message = await interaction.original_response()

    def release_view(self, view: HubView) -> None:
        self._active_views.discard(view)

    async def remember_success(
        self,
        interaction: discord.Interaction,
        record: RepeatRecord,
        *,
        persist_allowed: bool = True,
    ) -> None:
        if interaction.guild_id is None:
            return
        key = (interaction.guild_id, interaction.user.id)
        self._last_commands[key] = record
        self._last_commands.move_to_end(key)
        while len(self._last_commands) > 1000:
            self._last_commands.popitem(last=False)
        settings = await self.store.settings(interaction.guild_id)
        if persist_allowed and settings.get("persist_last_command") and self._repeat_is_serializable(record):
            await self.store.config.member(interaction.user).last_command.set(record.to_dict())

    @staticmethod
    def _repeat_is_serializable(record: RepeatRecord) -> bool:
        return all(value is None or isinstance(value, str | int | float | bool) for value in record.arguments.values())

    @staticmethod
    def safe_argument_summary(command: HubCommand, arguments: dict[str, Any]) -> str:
        lines = []
        for parameter in command.parameters:
            if parameter.name not in arguments:
                continue
            value = "[hidden]" if parameter.sensitive else str(arguments[parameter.name])
            lines.append(f"• {parameter.name}: {value[:200]}")
        return "\n".join(lines) or "No arguments."

    async def repeat_last(self, interaction: discord.Interaction, hub: Hub, view: HubView) -> None:
        if interaction.guild_id is None:
            return
        record = self._last_commands.get((interaction.guild_id, interaction.user.id))
        if record is None:
            raw = await self.store.config.member(interaction.user).last_command()
            if raw:
                record = RepeatRecord(
                    raw["hub"], raw["qualified_name"], CommandSource(raw["source"]), raw.get("arguments", {}), raw["executed_at"]
                )
        if record is None or record.hub != hub.name:
            await interaction.response.send_message("There is no repeatable command for this hub.", ephemeral=True)
            return
        command = self.registry.get(record.source, record.qualified_name)
        assignment_match = hub.find_assignment(record.qualified_name, record.source)
        if command is None or assignment_match is None or assignment_match[1].disabled or assignment_match[1].hidden:
            await interaction.response.send_message("The previous command is no longer available in this hub.", ephemeral=True)
            return
        if any(parameter.sensitive for parameter in command.parameters):
            await interaction.response.send_message("Commands with sensitive arguments cannot be repeated.", ephemeral=True)
            return
        if assignment_match[1].confirmation_required:
            await interaction.response.send_message(
                f"Repeat `{command.qualified_name}`?\n{self.safe_argument_summary(command, record.arguments)}",
                view=ConfirmationView(view, command, record.arguments),
                ephemeral=True,
            )
            return
        await self.invocation.invoke(interaction, hub, command, record.arguments)

    @commands.hybrid_group(name="commandhub", aliases=["chub"], invoke_without_command=True)
    @commands.guild_only()
    @commands.admin_or_permissions(manage_guild=True)
    async def commandhub_group(self, ctx: commands.GuildContext) -> None:
        """Create and manage interactive command hubs."""
        await ctx.send_help()

    @commandhub_group.command(name="create")
    async def commandhub_create(self, ctx: commands.GuildContext, name: str) -> None:
        try:
            hub = await self.create_hub_service(ctx.guild.id, name)
        except ValidationError as exc:
            await ctx.send(str(exc))
            return
        await ctx.send(f"Created `/{hub.name}`. A debounced guild sync is pending.")

    @commandhub_group.command(name="delete")
    async def commandhub_delete(self, ctx: commands.GuildContext, name: str) -> None:
        await ctx.send(
            f"Deleted `{name}`." if await self.delete_hub_service(ctx.guild.id, name) else f"Hub `{name}` was not found."
        )

    @commandhub_group.command(name="rename")
    async def commandhub_rename(self, ctx: commands.GuildContext, old_name: str, new_name: str) -> None:
        try:
            hub = await self.require_hub(ctx.guild.id, old_name)
            new_name = validate_hub_name(new_name)
            if await self.store.get_hub(ctx.guild.id, new_name) or self._tree_name_conflict(ctx.guild.id, new_name):
                raise ValidationError(f"`/{new_name}` is already in use.")
            await self.store.delete_hub(ctx.guild.id, hub.name)
            hub.name = new_name
            await self.store.save_hub(ctx.guild.id, hub)
            await self._reconcile_tree(ctx.guild.id)
            await self.schedule_sync(ctx.guild.id)
        except ValidationError as exc:
            await ctx.send(str(exc))
            return
        await ctx.send(f"Renamed `/{old_name}` to `/{new_name}`.")

    @commandhub_group.command(name="list")
    async def commandhub_list(self, ctx: commands.GuildContext) -> None:
        hubs = await self.store.list_hubs(ctx.guild.id)
        await ctx.send(
            "\n".join(
                f"`/{hub.name}` — {'enabled' if hub.enabled else 'disabled'} — {len(hub.assignments())} commands" for hub in hubs
            )
            or "No hubs configured."
        )

    @commandhub_group.command(name="info")
    async def commandhub_info(self, ctx: commands.GuildContext, name: str) -> None:
        try:
            hub = await self.require_hub(ctx.guild.id, name)
        except ValidationError as exc:
            await ctx.send(str(exc))
            return
        unavailable = sum(self.registry.get(item.source, item.qualified_name) is None for _, item in hub.assignments())
        await ctx.send(
            f"**{hub.title}** (`/{hub.name}`)\n{hub.description}\n"
            f"Enabled: {hub.enabled} | Ephemeral: {hub.ephemeral}\n"
            f"Categories: {len(hub.categories)} | Commands: {len(hub.assignments())} | "
            f"Unavailable: {unavailable}"
        )

    @commandhub_group.command(name="enable")
    async def commandhub_enable(self, ctx: commands.GuildContext, name: str) -> None:
        await self._toggle_hub(ctx, name, True)

    @commandhub_group.command(name="disable")
    async def commandhub_disable(self, ctx: commands.GuildContext, name: str) -> None:
        await self._toggle_hub(ctx, name, False)

    async def _toggle_hub(self, ctx: commands.GuildContext, name: str, enabled: bool) -> None:
        try:
            await self.update_hub_service(ctx.guild.id, name, {"enabled": enabled})
        except ValidationError as exc:
            await ctx.send(str(exc))
            return
        await ctx.send(f"Hub `{name}` {'enabled' if enabled else 'disabled'}.")

    @commandhub_group.command(name="set")
    async def commandhub_set(self, ctx: commands.GuildContext, name: str, field: str, *, value: str) -> None:
        """Set title, description, emoji, ephemeral, search_enabled, or repeat_enabled."""
        booleans = {"ephemeral", "search_enabled", "repeat_enabled"}
        field = field.casefold()
        if field not in {"title", "description", "emoji", *booleans}:
            await ctx.send("Supported fields: title, description, emoji, ephemeral, search_enabled, repeat_enabled.")
            return
        parsed: Any = value
        if field in booleans:
            if value.casefold() not in {"true", "false", "yes", "no", "on", "off"}:
                await ctx.send("Boolean values must be true/false, yes/no, or on/off.")
                return
            parsed = value.casefold() in {"true", "yes", "on"}
        if field == "emoji" and value.casefold() in {"none", "clear"}:
            parsed = None
        try:
            await self.update_hub_service(ctx.guild.id, name, {field: parsed})
        except ValidationError as exc:
            await ctx.send(str(exc))
            return
        await ctx.send(f"Updated `{field}` for `/{name}`.")

    @commandhub_group.command(name="add")
    async def commandhub_add(self, ctx: commands.GuildContext, hub: str, *, command_reference: str) -> None:
        try:
            assignment = await self.assign_command_service(ctx.guild.id, hub, command_reference)
        except ValidationError as exc:
            await ctx.send(str(exc))
            return
        await ctx.send(f"Added `{assignment.qualified_name}` ({assignment.source.value}) to `{hub}`.")

    @commandhub_group.command(name="remove")
    async def commandhub_remove(self, ctx: commands.GuildContext, hub: str, *, command_reference: str) -> None:
        removed = await self.remove_command_service(ctx.guild.id, hub, command_reference)
        await ctx.send("Command removed." if removed else "That assignment was not found.")

    @commandhub_group.command(name="move")
    async def commandhub_move(
        self, ctx: commands.GuildContext, source_hub: str, destination_hub: str, *, command_reference: str
    ) -> None:
        try:
            source = await self.require_hub(ctx.guild.id, source_hub)
            found = source.find_assignment(command_reference)
            if found is None:
                raise ValidationError("That command is not assigned to the source hub.")
            assignment = found[1]
            await self.assign_command_service(
                ctx.guild.id, destination_hub, f"{assignment.source.value}:{assignment.qualified_name}"
            )
            await self.remove_command_service(ctx.guild.id, source_hub, f"{assignment.source.value}:{assignment.qualified_name}")
        except ValidationError as exc:
            await ctx.send(str(exc))
            return
        await ctx.send("Command moved.")

    @commandhub_group.command(name="commands")
    async def commandhub_commands(self, ctx: commands.GuildContext, hub_name: str) -> None:
        try:
            hub = await self.require_hub(ctx.guild.id, hub_name)
        except ValidationError as exc:
            await ctx.send(str(exc))
            return
        lines = [f"**{category}** — `{item.qualified_name}` ({item.source.value})" for category, item in hub.assignments()]
        await ctx.send("\n".join(lines) or "No commands assigned.")

    @commandhub_group.command(name="commandset")
    async def commandhub_commandset(
        self,
        ctx: commands.GuildContext,
        hub_name: str,
        field: str,
        value: bool,
        *,
        command_reference: str,
    ) -> None:
        """Set confirmation_required, hidden, or disabled on one assignment."""
        try:
            assignment = await self.update_assignment_service(
                ctx.guild.id,
                hub_name,
                command_reference,
                {field.casefold(): value},
            )
        except ValidationError as exc:
            await ctx.send(str(exc))
            return
        await ctx.send(f"Set `{field}` to `{value}` for `{assignment.qualified_name}`.")

    @commandhub_group.group(name="category", invoke_without_command=True)
    async def commandhub_category(self, ctx: commands.GuildContext) -> None:
        await ctx.send_help()

    @commandhub_category.command(name="create")
    async def category_create(self, ctx: commands.GuildContext, hub_name: str, *, category: str) -> None:
        try:
            hub = await self.require_hub(ctx.guild.id, hub_name)
            category = validate_category_name(category)
            if category in hub.categories:
                raise ValidationError("That category already exists.")
            hub.categories[category] = HubCategory(category, len(hub.categories))
            await self.store.save_hub(ctx.guild.id, hub)
        except ValidationError as exc:
            await ctx.send(str(exc))
            return
        await ctx.send(f"Created category `{category}`.")

    @commandhub_category.command(name="delete")
    async def category_delete(self, ctx: commands.GuildContext, hub_name: str, *, category: str) -> None:
        try:
            hub = await self.require_hub(ctx.guild.id, hub_name)
            target = hub.categories.get(category)
            if target is None:
                raise ValidationError("That category was not found.")
            if target.commands:
                raise ValidationError("Move or remove the category's commands first.")
            del hub.categories[category]
            await self.store.save_hub(ctx.guild.id, hub)
        except ValidationError as exc:
            await ctx.send(str(exc))
            return
        await ctx.send(f"Deleted category `{category}`.")

    @commandhub_category.command(name="move")
    async def category_move(self, ctx: commands.GuildContext, hub_name: str, category: str, *, command_reference: str) -> None:
        try:
            hub = await self.require_hub(ctx.guild.id, hub_name)
            if category not in hub.categories:
                raise ValidationError("Destination category was not found.")
            found = hub.find_assignment(command_reference)
            if found is None:
                raise ValidationError("That assignment was not found.")
            old_category, assignment = found
            hub.categories[old_category].commands.remove(assignment)
            assignment.position = len(hub.categories[category].commands)
            hub.categories[category].commands.append(assignment)
            await self.store.save_hub(ctx.guild.id, hub)
        except ValidationError as exc:
            await ctx.send(str(exc))
            return
        await ctx.send(f"Moved `{command_reference}` to `{category}`.")

    @commandhub_group.command(name="refresh")
    @commands.is_owner()
    async def commandhub_refresh(self, ctx: commands.GuildContext) -> None:
        await self.registry.refresh()
        await ctx.send(f"Registry refreshed: {len(self.registry.commands)} commands.")

    @commandhub_group.command(name="registry")
    async def commandhub_registry(self, ctx: commands.GuildContext) -> None:
        counts = self.registry.counts
        await ctx.send(" | ".join(f"{source.value}: {counts[source]}" for source in CommandSource))

    @commandhub_group.command(name="sync")
    @commands.is_owner()
    async def commandhub_sync(self, ctx: commands.GuildContext) -> None:
        try:
            await self.sync_guild(ctx.guild.id)
        except Exception:  # noqa: BLE001 - sync_guild records and logs every framework/network failure.
            await ctx.send("Sync failed. Check `[p]commandhub syncstatus` and the bot logs.")
            return
        await ctx.send("CommandHub guild commands synchronized.")

    @commandhub_group.command(name="syncstatus")
    async def commandhub_syncstatus(self, ctx: commands.GuildContext) -> None:
        state = await self.store.config.guild(ctx.guild).sync_state()
        await ctx.send(
            f"Pending: {state['pending']}\n"
            f"Last success: {state['last_success'] or 'never'}\n"
            f"Last error: {state['last_error'] or 'none'}"
        )

    @commandhub_group.command(name="unsupported")
    async def commandhub_unsupported(self, ctx: commands.GuildContext) -> None:
        items = [item for item in self.registry.commands.values() if item.unsupported_reason]
        await ctx.send(
            "\n".join(f"`{item.qualified_name}`: {item.unsupported_reason}" for item in items[:25])
            or "No unsupported commands discovered."
        )

    @commandhub_group.command(name="diagnose")
    @commands.is_owner()
    async def commandhub_diagnose(self, ctx: commands.GuildContext) -> None:
        hubs = await self.store.list_hubs(ctx.guild.id)
        unavailable = sum(
            self.registry.get(item.source, item.qualified_name) is None for hub in hubs for _, item in hub.assignments()
        )
        state = await self.store.config.guild(ctx.guild).sync_state()
        age = "never"
        if self.registry.refreshed_at:
            age = f"{(datetime.now(timezone.utc) - self.registry.refreshed_at).total_seconds():.1f}s"
        counts = self.registry.counts
        await ctx.send(
            f"Hubs: {len(hubs)} | Registered: {sum(guild_id == ctx.guild.id for guild_id, _ in self._registered)}\n"
            f"Prefix: {counts[CommandSource.PREFIX]} | Hybrid: {counts[CommandSource.HYBRID]} | "
            f"Native: {counts[CommandSource.APPLICATION]} | SlashLink: {counts[CommandSource.SLASHLINK]}\n"
            f"Unavailable configured: {unavailable} | Active views: {len(self._active_views)}\n"
            f"Registry age: {age} | Unsupported types: {', '.join(sorted(self.registry.unsupported_types)) or 'none'}\n"
            f"Last sync: {state['last_success'] or 'never'} | Last error: {state['last_error'] or 'none'}",
        )

    async def _hub_choices(self, interaction: discord.Interaction, current: str) -> list[app_commands.Choice[str]]:
        if interaction.guild_id is None:
            return []
        needle = current.casefold().strip()
        names = [hub.name for hub in await self.store.list_hubs(interaction.guild_id)]
        names.sort(key=lambda name: (not name.casefold().startswith(needle), needle not in name.casefold(), name))
        return [app_commands.Choice(name=name, value=name) for name in names if not needle or needle in name.casefold()][:25]

    @commandhub_delete.autocomplete("name")
    @commandhub_info.autocomplete("name")
    @commandhub_enable.autocomplete("name")
    @commandhub_disable.autocomplete("name")
    @commandhub_set.autocomplete("name")
    @commandhub_rename.autocomplete("old_name")
    async def hub_name_autocomplete(
        self,
        interaction: discord.Interaction,
        current: str,
    ) -> list[app_commands.Choice[str]]:
        return await self._hub_choices(interaction, current)

    @commandhub_add.autocomplete("hub")
    @commandhub_remove.autocomplete("hub")
    async def hub_parameter_autocomplete(
        self,
        interaction: discord.Interaction,
        current: str,
    ) -> list[app_commands.Choice[str]]:
        return await self._hub_choices(interaction, current)

    @commandhub_add.autocomplete("command_reference")
    async def command_reference_autocomplete(
        self,
        interaction: discord.Interaction,
        current: str,
    ) -> list[app_commands.Choice[str]]:
        del interaction
        choices: list[app_commands.Choice[str]] = []
        for command in self.registry.search(current):
            value = command.qualified_name
            if len(value) <= 100:
                choices.append(app_commands.Choice(name=value[:100], value=value))
            if len(choices) == 25:
                break
        return choices
