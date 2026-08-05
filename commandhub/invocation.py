"""Permission-aware command invocation adapters."""

from __future__ import annotations

import asyncio
import contextlib
import logging
import secrets
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any

import discord
from discord.ext.commands.view import StringView
from redbot.core import app_commands, commands

from .converters import serialize_prefix_argument
from .models import CommandSource, Hub, HubCommand, RepeatRecord
from .utils import hub_scope_allows

if TYPE_CHECKING:
    from .integrations import SlashLinkAdapter

log = logging.getLogger("red.taakoscogs.commandhub.invocation")


class InvocationError(RuntimeError):
    pass


class InvocationEngine:
    def __init__(self, cog: Any, slashlink: SlashLinkAdapter) -> None:
        self.cog = cog
        self.bot = cog.bot
        self.slashlink = slashlink

    async def can_access_hub(self, interaction: discord.Interaction, hub: Hub) -> tuple[bool, str | None]:
        if interaction.guild is None or not isinstance(interaction.user, discord.Member):
            return False, "Hubs can only be used in a server."
        member = interaction.user
        role_ids = {role.id for role in member.roles}
        channel_id = interaction.channel_id
        me = interaction.guild.me
        if me is None:
            return False, "I could not resolve my server member."
        allowed, reason = hub_scope_allows(
            hub,
            role_ids,
            channel_id,
            member.guild_permissions.value,
            me.guild_permissions.value,
        )
        if not allowed:
            return False, reason
        if not await self.bot.allowed_by_whitelist_blacklist(member):
            return False, "You are not permitted to use this bot."
        return True, None

    async def can_run(self, interaction: discord.Interaction, command: HubCommand) -> tuple[bool, str | None]:
        if not command.enabled:
            return False, "Command disabled."
        if command.unsupported_reason:
            return False, command.unsupported_reason
        if command.source in {CommandSource.PREFIX, CommandSource.HYBRID}:
            try:
                ctx = await commands.Context.from_interaction(interaction)
                if not await command.callback.can_see(ctx):
                    return False, "You cannot run this command here."
                return True, None
            except commands.CommandError as exc:
                return False, str(exc) or "A command check failed."
        if command.source is CommandSource.APPLICATION:
            checker = getattr(command.callback, "_check_can_run", None)
            if checker is None:
                return False, "This application command cannot be safely routed on this Discord.py version."
            try:
                if not await checker(interaction):
                    return False, "A command check failed."
            except app_commands.AppCommandError as exc:
                return False, str(exc) or "An application-command check failed."
            return True, None
        if command.source is CommandSource.SLASHLINK and not self.slashlink.available:
            return False, "SlashLink is unavailable or incompatible."
        return True, None

    async def can_display(self, interaction: discord.Interaction, command: HubCommand) -> tuple[bool, str | None]:
        """Run visibility checks that cannot consume cooldowns or mutate concurrency state."""
        if not command.enabled:
            return False, "Command disabled."
        if command.unsupported_reason:
            return False, command.unsupported_reason
        if command.source in {CommandSource.PREFIX, CommandSource.HYBRID}:
            try:
                ctx = await commands.Context.from_interaction(interaction)
                if not await command.callback.can_see(ctx):
                    return False, "You cannot run this command here."
            except commands.CommandError as exc:
                return False, str(exc) or "A visibility check failed."
        if command.source is CommandSource.SLASHLINK and not self.slashlink.available:
            return False, "SlashLink is unavailable or incompatible."
        return True, None

    async def invoke(
        self,
        interaction: discord.Interaction,
        hub: Hub,
        command: HubCommand,
        arguments: dict[str, Any],
    ) -> bool:
        allowed, reason = await self.can_access_hub(interaction, hub)
        if allowed:
            allowed, reason = await self.can_run(interaction, command)
        if not allowed:
            await self.cog.send_interaction(interaction, f"Cannot run `{command.qualified_name}`: {reason}", ephemeral=True)
            return False
        try:
            if command.source in {CommandSource.PREFIX, CommandSource.HYBRID}:
                if not await self._invoke_prefix(interaction, hub, command, arguments):
                    return False
            elif command.source is CommandSource.APPLICATION:
                if not await self._invoke_application(interaction, command, arguments):
                    return False
            else:
                await self.slashlink.invoke(interaction, command.qualified_name, arguments)
        except (commands.CommandError, app_commands.AppCommandError) as exc:
            # Framework errors are intentionally concise; their handlers have already had an opportunity to run.
            await self.cog.send_interaction(interaction, f"Command failed: {exc}", ephemeral=True)
            return False
        except Exception:
            error_id = secrets.token_hex(3)
            log.exception("CommandHub invocation failed (error %s, command %s).", error_id, command.qualified_name)
            await self.cog.send_interaction(interaction, f"Invocation failed. Error ID: `{error_id}`", ephemeral=True)
            return False
        await self.cog.remember_success(
            interaction,
            RepeatRecord(
                hub=hub.name,
                qualified_name=command.qualified_name,
                source=command.source,
                arguments=dict(arguments),
                executed_at=datetime.now(timezone.utc).isoformat(),
            ),
            persist_allowed=not any(parameter.sensitive for parameter in command.parameters),
        )
        return True

    async def _invoke_prefix(
        self, interaction: discord.Interaction, hub: Hub, command: HubCommand, arguments: dict[str, Any]
    ) -> bool:
        prefix = f"/{hub.name} "
        values = [
            serialize_prefix_argument(arguments[item.name])
            for item in command.parameters
            if item.name in arguments and arguments[item.name] is not None
        ]
        content = f"{prefix}{command.qualified_name}"
        if values:
            content += " " + " ".join(values)
        ctx = await commands.Context.from_interaction(interaction)
        ctx.message.content = content
        ctx.message.attachments = []
        ctx.prefix = prefix
        ctx.view = StringView(content)
        ctx.view.skip_string(prefix)
        ctx.invoked_with = ctx.view.get_word()
        ctx.command = self.bot.get_command(ctx.invoked_with)
        ctx.invoked_parents = []
        ctx.invoked_subcommand = None
        ctx.subcommand_passed = None
        ctx.args = []
        ctx.kwargs = {}
        if ctx.command is None:
            raise InvocationError("The prefix command was unloaded.")

        async def defer_later() -> None:
            await asyncio.sleep(2)
            if not interaction.response.is_done():
                with contextlib.suppress(discord.HTTPException, discord.InteractionResponded):
                    await interaction.response.defer(ephemeral=hub.ephemeral)

        task = asyncio.create_task(defer_later())
        try:
            await self.bot.invoke(ctx)
        finally:
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task
        succeeded = not ctx.command_failed
        if not interaction.response.is_done():
            message = (
                "Command completed." if succeeded else "Command did not complete; a command check or error handler stopped it."
            )
            await interaction.response.send_message(message, ephemeral=hub.ephemeral)
        return succeeded

    async def _invoke_application(
        self,
        interaction: discord.Interaction,
        command: HubCommand,
        arguments: dict[str, Any],
    ) -> bool:
        target = command.callback
        callback = getattr(target, "callback", None)
        error_handler = getattr(target, "_invoke_error_handlers", None)
        if callback is None or error_handler is None:
            raise InvocationError("This application command cannot be safely invoked on this Discord.py version.")
        previous = getattr(interaction, "command", None)
        interaction.command = target
        try:
            binding = getattr(target, "binding", None)
            if binding is None:
                await callback(interaction, **arguments)
            else:
                await callback(binding, interaction, **arguments)
        except app_commands.AppCommandError as exc:
            interaction.command_failed = True
            await error_handler(interaction, exc)
            await self.bot.tree.on_error(interaction, exc)
            return False
        except Exception as exc:  # noqa: BLE001 - callback failures must enter Discord's application-command handlers.
            interaction.command_failed = True
            error_id = secrets.token_hex(3)
            wrapped = app_commands.CommandInvokeError(target, exc)
            log.exception("Native CommandHub callback failed (error %s, command %s).", error_id, command.qualified_name)
            await error_handler(interaction, wrapped)
            await self.bot.tree.on_error(interaction, wrapped)
            if not interaction.response.is_done():
                await interaction.response.send_message(f"Invocation failed. Error ID: `{error_id}`", ephemeral=True)
            return False
        finally:
            interaction.command = previous
        if not interaction.response.is_done():
            await interaction.response.send_message("Command completed.", ephemeral=True)
        return True
