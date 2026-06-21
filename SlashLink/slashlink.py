"""Expose prefix-only cogs through Red's native application-command manager."""

from __future__ import annotations

import asyncio
import contextlib
import difflib
import logging
import re
from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional

import discord
from discord.ext.commands.view import StringView
from redbot.core import app_commands, commands
from redbot.core.bot import Red

log = logging.getLogger("red.taakoscogs.slashlink")


@dataclass(frozen=True)
class ProxyRecord:
    """One generated application command and the cog it represents."""

    cog_name: str
    command_name: str


class SlashLink(commands.Cog):
    """Add Red-managed application-command gateways for prefix-only cogs."""

    def __init__(self, bot: Red) -> None:
        self.bot = bot
        self._proxies: Dict[str, ProxyRecord] = {}
        self._lock = asyncio.Lock()

    async def cog_load(self) -> None:
        async with self._lock:
            for cog in tuple(self.bot.cogs.values()):
                await self._add_proxy(cog)
            await self.bot.tree.red_check_enabled()

    async def cog_unload(self) -> None:
        async with self._lock:
            for cog_name in tuple(self._proxies):
                self._remove_proxy(cog_name)

    @commands.Cog.listener()
    async def on_cog_add(self, cog: commands.Cog) -> None:
        async with self._lock:
            if await self._add_proxy(cog):
                await self.bot.tree.red_check_enabled()

    @commands.Cog.listener()
    async def on_cog_remove(self, cog: commands.Cog) -> None:
        if cog is self:
            return
        async with self._lock:
            if self._remove_proxy(cog.qualified_name):
                await self.bot.tree.red_check_enabled()

    async def red_delete_data_for_user(self, *, requester: str, user_id: int) -> None:
        """SlashLink does not persistently store user data."""

    async def _add_proxy(self, cog: commands.Cog) -> bool:
        cog_name = cog.qualified_name
        if cog is self or cog_name in self._proxies:
            return False
        if self._has_application_commands(cog):
            return False
        if not self._prefix_commands(cog):
            return False

        command_name = self._available_name(cog_name)
        if command_name is None:
            log.warning("No available application-command name for prefix-only cog %s.", cog_name)
            return False

        callback = self._make_callback(cog_name, command_name)
        callback.__module__ = cog_name
        callback = app_commands.describe(
            command="Prefix command to run",
            arguments="Arguments written as they would be after the prefix command",
            attachment="Optional attachment supplied as the command message attachment",
        )(callback)
        proxy = app_commands.Command(
            name=command_name,
            description=f"Run a {cog_name[:70]} text command.",
            callback=callback,
            extras={"slashlink_proxy": True, "slashlink_cog": cog_name},
        )

        autocomplete = self._make_autocomplete(cog_name)
        autocomplete.__module__ = cog_name
        proxy.autocomplete("command")(autocomplete)

        try:
            self.bot.tree.add_command(proxy)
        except app_commands.CommandAlreadyRegistered:
            log.warning(
                "Could not create /%s for %s because that application-command name is in use.",
                command_name,
                cog_name,
            )
            return False

        self._proxies[cog_name] = ProxyRecord(cog_name, command_name)
        log.info("Registered Red-managed proxy /%s for %s.", command_name, cog_name)
        return True

    def _remove_proxy(self, cog_name: str) -> bool:
        record = self._proxies.pop(cog_name, None)
        if record is None:
            return False
        existing = self.bot.tree._global_commands.get(record.command_name)
        if existing is None:
            existing = self.bot.tree._disabled_global_commands.get(record.command_name)
        if existing is None or existing.extras.get("slashlink_cog") != cog_name:
            log.warning(
                "Did not remove /%s for %s because the tree entry is no longer its proxy.",
                record.command_name,
                cog_name,
            )
            return False
        self.bot.tree.remove_command(record.command_name)
        log.info("Removed application-command proxy /%s for %s.", record.command_name, cog_name)
        return True

    def _has_application_commands(self, cog: commands.Cog) -> bool:
        get_app_commands = getattr(cog, "get_app_commands", None)
        if get_app_commands is not None and get_app_commands():
            return True

        module_root = cog.__module__.split(".", 1)[0]
        tree_commands = list(self.bot.tree._global_commands.values())
        tree_commands.extend(self.bot.tree._disabled_global_commands.values())
        for command in tree_commands:
            if command.extras.get("slashlink_proxy", False):
                continue
            if command.module.split(".", 1)[0] == module_root:
                return True
        return False

    @staticmethod
    def _prefix_commands(cog: commands.Cog) -> List[commands.Command]:
        return [
            command
            for command in cog.walk_commands()
            if command.enabled and not getattr(command, "__commands_is_hybrid__", False)
        ]

    def _available_name(self, cog_name: str) -> Optional[str]:
        base = self._valid_name(cog_name)
        if not base:
            return None
        occupied = set(self.bot.tree._global_commands)
        occupied.update(self.bot.tree._disabled_global_commands)
        if base not in occupied:
            return base

        suffix = "-commands"
        shortened = base[: 32 - len(suffix)].rstrip("-_")
        fallback = f"{shortened}{suffix}"
        if fallback not in occupied:
            return fallback

        for index in range(2, 100):
            suffix = f"-{index}"
            candidate = f"{base[: 32 - len(suffix)].rstrip('-_')}{suffix}"
            if candidate not in occupied:
                return candidate
        return None

    @staticmethod
    def _valid_name(value: str) -> str:
        name = re.sub(r"[^a-z0-9_-]+", "-", value.lower()).strip("-_")
        name = re.sub(r"[-_]{2,}", "-", name)
        return name[:32].rstrip("-_")

    def _make_callback(self, cog_name: str, proxy_name: str):
        async def proxy_callback(
            interaction: discord.Interaction,
            command: str,
            arguments: Optional[str] = None,
            attachment: Optional[discord.Attachment] = None,
        ) -> None:
            await self._invoke(interaction, cog_name, proxy_name, command, arguments, attachment)

        return proxy_callback

    def _make_autocomplete(self, cog_name: str):
        async def command_autocomplete(
            interaction: discord.Interaction,
            current: str,
        ) -> List[app_commands.Choice[str]]:
            cog = self.bot.get_cog(cog_name)
            if cog is None:
                return []
            if not await self.bot.allowed_by_whitelist_blacklist(interaction.user):
                return []

            try:
                ctx = await commands.Context.from_interaction(interaction)
            except (TypeError, ValueError):
                return []

            visible: List[str] = []
            for command in self._prefix_commands(cog):
                name = command.qualified_name
                if len(name) > 100:
                    continue
                try:
                    if await command.can_see(ctx):
                        visible.append(name)
                except commands.CommandError:
                    continue

            return [
                app_commands.Choice(name=name, value=name)
                for name in self._rank_matches(visible, current)[:25]
            ]

        return command_autocomplete

    @staticmethod
    def _rank_matches(names: Iterable[str], current: str) -> List[str]:
        unique = sorted(set(names))
        needle = current.casefold().strip()
        if not needle:
            return unique

        def score(name: str) -> tuple:
            folded = name.casefold()
            if folded.startswith(needle):
                rank = 0
            elif needle in folded:
                rank = 1
            else:
                rank = 2
            similarity = difflib.SequenceMatcher(None, needle, folded).ratio()
            return rank, -similarity, folded

        return sorted(unique, key=score)

    async def _invoke(
        self,
        interaction: discord.Interaction,
        cog_name: str,
        proxy_name: str,
        command_name: str,
        arguments: Optional[str],
        attachment: Optional[discord.Attachment],
    ) -> None:
        cog = self.bot.get_cog(cog_name)
        command = self.bot.get_command(command_name)
        if cog is None or command is None or command.cog is not cog:
            await interaction.response.send_message(
                f"`{command_name}` is not an available command from `{cog_name}`.",
                ephemeral=True,
            )
            return

        if getattr(command, "__commands_is_hybrid__", False):
            await interaction.response.send_message(
                "That command already has native application-command support.",
                ephemeral=True,
            )
            return

        prefix = f"/{proxy_name} "
        content = f"{prefix}{command_name}"
        if arguments:
            content = f"{content} {arguments.strip()}"

        ctx = await commands.Context.from_interaction(interaction)
        ctx.message.content = content
        ctx.message.attachments = [attachment] if attachment is not None else []
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

        auto_deferred = False

        async def defer_after_delay() -> None:
            nonlocal auto_deferred
            await asyncio.sleep(2)
            if not interaction.response.is_done():
                with contextlib.suppress(discord.InteractionResponded, discord.HTTPException):
                    await interaction.response.defer()
                    auto_deferred = True

        defer_task = asyncio.create_task(defer_after_delay())
        try:
            await self.bot.invoke(ctx)
        finally:
            defer_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await defer_task

        if auto_deferred:
            with contextlib.suppress(discord.HTTPException):
                await interaction.delete_original_response()
        elif not interaction.response.is_done():
            await interaction.response.send_message("Command invoked.", ephemeral=True)
