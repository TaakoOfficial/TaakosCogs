"""Unified health, audit, and retry controls for optional TaakosCogs integrations."""

from __future__ import annotations

import asyncio
import time
from contextlib import suppress
from typing import TYPE_CHECKING, Any, ClassVar

import discord
from discord.ext import tasks
from redbot.core import Config, commands

from .dashboard_integration import DashboardIntegration

if TYPE_CHECKING:
    from redbot.core.bot import Red


class OperationsCenter(DashboardIntegration, commands.Cog):
    """Show optional cog health and retain bounded integration operations history."""

    CONFIG_IDENTIFIER = 2026081805
    SCHEMA_VERSION = 1
    MANAGED_COGS: ClassVar[tuple[str, ...]] = (
        "SecretSentinel",
        "ServerDoctor",
        "DecisionLedger",
        "KnowledgeGarden",
        "EventCheckin",
        "ForumFlow",
        "SuggestionBox",
        "OpsRoom",
        "StaffOps",
    )

    def __init__(self, bot: Red) -> None:
        self.bot = bot
        self.config = Config.get_conf(self, identifier=self.CONFIG_IDENTIFIER, force_registration=True)
        self.config.register_guild(
            schema_version=self.SCHEMA_VERSION,
            audit_channel_id=None,
            notify_failures=True,
            notification_channels={},
            muted_sources=[],
            next_retry_id=1,
            audit_events=[],
            retry_queue=[],
        )
        self._locks: dict[int, asyncio.Lock] = {}

    @staticmethod
    def _now() -> int:
        return int(time.time())

    def _lock(self, guild_id: int) -> asyncio.Lock:
        return self._locks.setdefault(guild_id, asyncio.Lock())

    async def cog_load(self) -> None:
        for guild_id in await self.config.all_guilds():
            await self.config.guild_from_id(guild_id).schema_version.set(self.SCHEMA_VERSION)
        self.retry_loop.start()

    def cog_unload(self) -> None:
        self.retry_loop.cancel()

    async def red_delete_data_for_user(self, *, requester: str, user_id: int) -> None:
        return

    async def record_audit(
        self,
        guild: discord.Guild,
        source: str,
        action: str,
        status: str,
        detail: str = "",
    ) -> None:
        """Record a bounded, non-secret integration event for optional partner cogs."""
        event = {
            "at": self._now(),
            "source": source[:50],
            "action": action[:100],
            "status": status[:20],
            "detail": detail[:500],
        }
        conf = self.config.guild(guild)
        async with self._lock(guild.id):
            events = await conf.audit_events()
            events.append(event)
            await conf.audit_events.set(events[-250:])
        if status != "failed" or not await conf.notify_failures() or source in await conf.muted_sources():
            return
        routes = await conf.notification_channels()
        channel_id = routes.get(source) or await conf.audit_channel_id()
        channel = guild.get_channel(channel_id) if channel_id else None
        if isinstance(channel, discord.TextChannel):
            with suppress(discord.HTTPException):
                await channel.send(
                    embed=discord.Embed(
                        title=f"{source} integration failed",
                        description=f"**{action}**\n{detail[:1500] or 'No additional detail.'}",
                        color=discord.Color.red(),
                    ),
                    allowed_mentions=discord.AllowedMentions.none(),
                )

    async def enqueue_retry(
        self,
        guild: discord.Guild,
        target_cog: str,
        event: str,
        payload: dict[str, Any],
        detail: str = "",
    ) -> int:
        """Queue a bounded retry for a cog exposing retry_integration_event."""
        conf = self.config.guild(guild)
        async with self._lock(guild.id):
            retry_id = int(await conf.next_retry_id())
            queue = await conf.retry_queue()
            queue.append(
                {
                    "retry_id": retry_id,
                    "target_cog": target_cog[:50],
                    "event": event[:100],
                    "payload": payload,
                    "attempts": 0,
                    "next_attempt_at": self._now() + 60,
                    "last_error": detail[:500],
                    "created_at": self._now(),
                }
            )
            await conf.retry_queue.set(queue[-100:])
            await conf.next_retry_id.set(retry_id + 1)
        await self.record_audit(guild, target_cog, event, "queued", detail)
        return retry_id

    async def _process_retries(self, guild: discord.Guild, *, retry_id: int = 0) -> tuple[int, int]:
        conf = self.config.guild(guild)
        now = self._now()
        completed = 0
        failed = 0
        async with self._lock(guild.id):
            queue = await conf.retry_queue()
            retained = []
            selected = []
            for item in queue:
                if retry_id and item["retry_id"] != retry_id:
                    retained.append(item)
                    continue
                if not retry_id and int(item.get("next_attempt_at", 0)) > now:
                    retained.append(item)
                    continue
                selected.append(item)
            await conf.retry_queue.set(retained)
        for item in selected:
            target = self.bot.get_cog(item["target_cog"])
            handler = getattr(target, "retry_integration_event", None) if target else None
            try:
                if handler is None:
                    raise RuntimeError("Target cog is not loaded or does not support retries.")
                await handler(guild, item["event"], dict(item.get("payload") or {}))
            except Exception as error:  # noqa: BLE001 - retry boundary must isolate partner cogs
                item["attempts"] = int(item.get("attempts", 0)) + 1
                item["last_error"] = str(error)[:500]
                if item["attempts"] < 5:
                    item["next_attempt_at"] = now + min(3600, 60 * (2 ** item["attempts"]))
                    async with self._lock(guild.id):
                        current = await conf.retry_queue()
                        current.append(item)
                        await conf.retry_queue.set(current[-100:])
                failed += 1
            else:
                completed += 1
        return completed, failed

    @tasks.loop(minutes=1)
    async def retry_loop(self) -> None:
        for guild in self.bot.guilds:
            with suppress(Exception):
                await self._process_retries(guild)

    @retry_loop.before_loop
    async def before_retry_loop(self) -> None:
        await self.bot.wait_until_red_ready()

    @commands.hybrid_group(name="operationscenter", aliases=["opsstatus"], invoke_without_command=True)
    @commands.guild_only()
    @commands.admin_or_permissions(manage_guild=True)
    async def operations_center(self, ctx: commands.Context) -> None:
        """Inspect and configure optional TaakosCogs operations integrations."""
        await self._send_status(ctx)

    async def _send_status(self, ctx: commands.Context) -> None:
        settings = await self.config.guild(ctx.guild).all()
        loaded = [name for name in self.MANAGED_COGS if self.bot.get_cog(name)]
        missing = [name for name in self.MANAGED_COGS if name not in loaded]
        doctor = self.bot.get_cog("ServerDoctor")
        findings = await doctor.diagnose(ctx.guild) if doctor and hasattr(doctor, "diagnose") else []
        embed = discord.Embed(title="OperationsCenter", color=discord.Color.blurple())
        embed.add_field(name="Loaded", value=", ".join(loaded) or "None", inline=False)
        embed.add_field(name="Optional / absent", value=", ".join(missing) or "None", inline=False)
        embed.add_field(name="Health findings", value=str(len(findings)))
        embed.add_field(name="Queued retries", value=str(len(settings["retry_queue"])))
        embed.add_field(name="Audit events", value=str(len(settings["audit_events"])))
        embed.set_footer(text="Absent optional cogs do not prevent loaded cogs from working.")
        await ctx.send(embed=embed)

    @operations_center.command(name="status")
    async def status(self, ctx: commands.Context) -> None:
        """Show loaded capabilities, health findings, audit counts, and retries."""
        await self._send_status(ctx)

    @operations_center.command(name="setup")
    async def guided_setup(self, ctx: commands.Context, channel: discord.TextChannel | None = None) -> None:
        """Set the operations alert channel and show safe setup commands for loaded cogs."""
        destination = channel or ctx.channel
        if not isinstance(destination, discord.TextChannel):
            raise commands.BadArgument("Choose a text channel for operations alerts.")
        permissions = destination.permissions_for(ctx.guild.me)
        if not permissions.send_messages or not permissions.embed_links:
            raise commands.BadArgument("I need Send Messages and Embed Links in that channel.")
        await self.config.guild(ctx.guild).audit_channel_id.set(destination.id)
        prefix = ctx.clean_prefix
        commands_to_run = []
        if self.bot.get_cog("SecretSentinel"):
            commands_to_run.append(f"`{prefix}secretsentinel setup {destination.mention}`")
        if self.bot.get_cog("ServerDoctor"):
            commands_to_run.append(f"`{prefix}serverdoctor schedule 24 {destination.mention}`")
        if self.bot.get_cog("DecisionLedger"):
            commands_to_run.append(f"`{prefix}decision setup {destination.mention}`")
        if self.bot.get_cog("KnowledgeGarden"):
            commands_to_run.append(f"`{prefix}knowledgegarden setup {destination.mention}`")
        if self.bot.get_cog("EventCheckin"):
            commands_to_run.append(f"`{prefix}eventcheckin setup {destination.mention} UTC`")
        await ctx.send(
            f"Operations alerts will use {destination.mention}. Complete any desired optional setup:\n"
            + ("\n".join(commands_to_run) if commands_to_run else "No managed partner cogs are loaded yet.")
        )

    @operations_center.command(name="audit")
    async def audit(self, ctx: commands.Context, limit: commands.Range[int, 1, 25] = 10) -> None:
        """Show recent integration activity without stored message content."""
        events = (await self.config.guild(ctx.guild).audit_events())[-int(limit) :]
        lines = [
            f"<t:{item['at']}:R> **{item['source']}** · {item['action']} · `{item['status']}`"
            + (f" — {item['detail']}" if item.get("detail") else "")
            for item in reversed(events)
        ]
        await ctx.send("\n".join(lines)[:1900] if lines else "No integration activity has been recorded.")

    @operations_center.command(name="route")
    async def route(self, ctx: commands.Context, source: str, channel: discord.TextChannel | None = None) -> None:
        """Route one integration's failure alerts, or omit the channel to use the default."""
        canonical = next((name for name in self.MANAGED_COGS if name.casefold() == source.casefold()), None)
        if not canonical:
            raise commands.BadArgument("Unknown managed cog name.")
        if channel:
            permissions = channel.permissions_for(ctx.guild.me)
            if not permissions.send_messages or not permissions.embed_links:
                raise commands.BadArgument("I need Send Messages and Embed Links in that channel.")
        async with self.config.guild(ctx.guild).notification_channels() as routes:
            if channel:
                routes[canonical] = channel.id
            else:
                routes.pop(canonical, None)
        await ctx.send(
            f"{canonical} failures will use {channel.mention}." if channel else f"{canonical} now uses the default alert channel."
        )

    @operations_center.command(name="mute")
    async def mute(self, ctx: commands.Context, source: str) -> None:
        """Toggle quiet mode for one integration's failure notifications."""
        canonical = next((name for name in self.MANAGED_COGS if name.casefold() == source.casefold()), None)
        if not canonical:
            raise commands.BadArgument("Unknown managed cog name.")
        async with self.config.guild(ctx.guild).muted_sources() as muted:
            if canonical in muted:
                muted.remove(canonical)
                state = "unmuted"
            else:
                muted.append(canonical)
                state = "muted"
        await ctx.send(f"{canonical} failure notifications are now {state}; audit events are still retained.")

    @operations_center.command(name="retries")
    async def retries(self, ctx: commands.Context) -> None:
        """List durable integration retries."""
        queue = await self.config.guild(ctx.guild).retry_queue()
        lines = [
            f"`#{item['retry_id']}` {item['target_cog']} / {item['event']} · "
            f"{item['attempts']} attempt(s) · next <t:{item['next_attempt_at']}:R>"
            for item in queue[-20:]
        ]
        await ctx.send("\n".join(lines) if lines else "No integration retries are queued.")

    @operations_center.command(name="retry")
    async def retry(self, ctx: commands.Context, retry_id: int) -> None:
        """Run one queued integration retry immediately."""
        completed, failed = await self._process_retries(ctx.guild, retry_id=retry_id)
        if not completed and not failed:
            raise commands.BadArgument("Retry not found.")
        await ctx.send(f"Retry finished: {completed} completed, {failed} failed or rescheduled.")
