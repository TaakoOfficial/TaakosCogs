"""Privacy-safe credential leak detection for Discord messages."""

from __future__ import annotations

import time
from contextlib import suppress
from typing import TYPE_CHECKING, ClassVar

import discord
from redbot.core import Config, commands

from .dashboard_integration import DashboardIntegration
from .detection import PATTERNS, find_secrets

if TYPE_CHECKING:
    from redbot.core.bot import Red


class SecretSentinel(DashboardIntegration, commands.Cog):
    """Find exposed credentials without retaining the credential value."""

    CONFIG_IDENTIFIER = 2026081801
    SCHEMA_VERSION = 2
    TEXT_EXTENSIONS: ClassVar[set[str]] = {
        ".txt",
        ".log",
        ".env",
        ".json",
        ".yaml",
        ".yml",
        ".ini",
        ".cfg",
        ".py",
        ".js",
        ".ts",
        ".md",
    }

    def __init__(self, bot: Red) -> None:
        self.bot = bot
        self.config = Config.get_conf(self, identifier=self.CONFIG_IDENTIFIER, force_registration=True)
        self.config.register_guild(
            schema_version=self.SCHEMA_VERSION,
            enabled=False,
            action="delete",
            log_channel_id=None,
            scan_attachments=True,
            disabled_kinds=[],
            monitored_bot_ids=[],
            alert_cooldown_seconds=60,
            create_opsroom_incidents=False,
            ignored_channel_ids=[],
            ignored_role_ids=[],
        )
        self._handled: set[int] = set()
        self._last_alert: dict[tuple[int, int, str], int] = {}
        self._last_incident: dict[int, int] = {}

    async def cog_load(self) -> None:
        for guild_id in await self.config.all_guilds():
            await self.config.guild_from_id(guild_id).schema_version.set(self.SCHEMA_VERSION)

    @staticmethod
    def _now() -> int:
        return int(time.time())

    async def _audit(self, guild: discord.Guild, action: str, status: str, detail: str = "") -> None:
        operations = self.bot.get_cog("OperationsCenter")
        if operations and hasattr(operations, "record_audit"):
            await operations.record_audit(guild, "SecretSentinel", action, status, detail)

    async def retry_integration_event(self, guild: discord.Guild, event: str, payload: dict[str, object]) -> None:
        """Replay supported durable OperationsCenter work."""
        if event != "open_opsroom_incident":
            raise RuntimeError("Unsupported SecretSentinel retry event.")
        opsroom = self.bot.get_cog("OpsRoom")
        creator = getattr(opsroom, "create_incident_service", None) if opsroom else None
        if creator is None:
            raise RuntimeError("OpsRoom is not loaded or needs an update.")
        await creator(
            guild,
            "sev2",
            "Possible credential exposure",
            int(payload["actor_id"]),
            summary=(
                f"SecretSentinel detected {payload['kinds']} in channel {payload['channel_id']}, "
                f"message {payload['message_id']}. No matched value was retained. Rotate or revoke the credential."
            ),
            source_type="secretsentinel",
        )
        self._last_incident[guild.id] = self._now()
        await self._audit(guild, "OpsRoom incident retry", "completed", "Credential-response incident opened")

    async def red_delete_data_for_user(self, *, requester: str, user_id: int) -> None:
        return

    async def _attachment_text(self, attachment: discord.Attachment) -> str:
        suffix = "." + attachment.filename.rsplit(".", 1)[-1].casefold() if "." in attachment.filename else ""
        if attachment.size > 65536 or suffix not in self.TEXT_EXTENSIONS:
            return ""
        try:
            payload = await attachment.read()
        except (discord.HTTPException, discord.NotFound, discord.Forbidden):
            return ""
        return payload.decode("utf-8", errors="ignore")

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message) -> None:
        if not message.guild or message.id in self._handled:
            return
        settings = await self.config.guild(message.guild).all()
        if message.author.bot and message.author.id not in settings["monitored_bot_ids"]:
            return
        if not settings["enabled"] or message.channel.id in settings["ignored_channel_ids"]:
            return
        author_roles = {role.id for role in getattr(message.author, "roles", [])}
        if author_roles.intersection(settings["ignored_role_ids"]):
            return
        kinds = {match.kind for match in find_secrets(message.content)}
        if settings["scan_attachments"]:
            for attachment in message.attachments:
                kinds.update(match.kind for match in find_secrets(await self._attachment_text(attachment)))
        kinds.difference_update(settings["disabled_kinds"])
        if not kinds:
            return
        self._handled.add(message.id)
        if len(self._handled) > 5000:
            self._handled.clear()
            self._handled.add(message.id)
        deleted = False
        if settings["action"] == "delete":
            with suppress(discord.Forbidden, discord.NotFound, discord.HTTPException):
                await message.delete()
                deleted = True
        kind_key = ",".join(sorted(kinds))
        alert_key = (message.guild.id, message.author.id, kind_key)
        now = self._now()
        alert_allowed = now - self._last_alert.get(alert_key, 0) >= int(settings["alert_cooldown_seconds"])
        if alert_allowed:
            self._last_alert[alert_key] = now
            if len(self._last_alert) > 5000:
                cutoff = now - max(3600, int(settings["alert_cooldown_seconds"]))
                self._last_alert = {key: timestamp for key, timestamp in self._last_alert.items() if timestamp >= cutoff}
        log_channel = message.guild.get_channel(settings["log_channel_id"]) if settings["log_channel_id"] else None
        if alert_allowed and isinstance(log_channel, discord.TextChannel):
            embed = discord.Embed(title="Possible secret exposed", color=discord.Color.red())
            embed.add_field(name="Types", value="\n".join(f"• {kind}" for kind in sorted(kinds)), inline=False)
            embed.add_field(name="Location", value=f"<#{message.channel.id}> · message `{message.id}`", inline=False)
            embed.add_field(name="Author", value=f"<@{message.author.id}> (`{message.author.id}`)", inline=False)
            embed.set_footer(text="Message deleted" if deleted else "Report-only mode; message retained")
            with suppress(discord.HTTPException):
                await log_channel.send(embed=embed, allowed_mentions=discord.AllowedMentions.none())
        if alert_allowed:
            with suppress(discord.Forbidden, discord.HTTPException):
                await message.author.send(
                    f"SecretSentinel detected a possible {', '.join(sorted(kinds))} in **{message.guild.name}**. "
                    + (
                        "The message was deleted. Rotate or revoke the exposed credential now."
                        if deleted
                        else "Staff were notified. Rotate or revoke the credential now."
                    )
                )
            await self._audit(message.guild, "credential detection", "completed", f"{kind_key}; deleted={deleted}")
        if alert_allowed and settings["create_opsroom_incidents"] and now - self._last_incident.get(message.guild.id, 0) >= 900:
            opsroom = self.bot.get_cog("OpsRoom")
            creator = getattr(opsroom, "create_incident_service", None) if opsroom else None
            if creator:
                try:
                    await creator(
                        message.guild,
                        "sev2",
                        "Possible credential exposure",
                        message.author.id,
                        summary=(
                            f"SecretSentinel detected {kind_key} in channel {message.channel.id}, message {message.id}. "
                            "No matched value was retained. Rotate or revoke the credential."
                        ),
                        source_type="secretsentinel",
                    )
                except (discord.Forbidden, discord.HTTPException, commands.CommandError) as error:
                    await self._audit(message.guild, "OpsRoom incident", "failed", str(error))
                    operations = self.bot.get_cog("OperationsCenter")
                    if operations and hasattr(operations, "enqueue_retry"):
                        await operations.enqueue_retry(
                            message.guild,
                            "SecretSentinel",
                            "open_opsroom_incident",
                            {
                                "actor_id": message.author.id,
                                "kinds": kind_key,
                                "channel_id": message.channel.id,
                                "message_id": message.id,
                            },
                            str(error),
                        )
                else:
                    self._last_incident[message.guild.id] = now
                    await self._audit(message.guild, "OpsRoom incident", "completed", "Credential-response incident opened")

    @commands.hybrid_group(name="secretsentinel", aliases=["ssentinel"], invoke_without_command=True)
    @commands.guild_only()
    @commands.admin_or_permissions(manage_guild=True)
    async def secret_sentinel(self, ctx: commands.Context) -> None:
        """Configure credential leak detection."""
        await ctx.send_help()

    @secret_sentinel.command(name="enable")
    async def enable(self, ctx: commands.Context, enabled: bool) -> None:
        """Enable or disable message scanning."""
        await self.config.guild(ctx.guild).enabled.set(enabled)
        await ctx.send(f"SecretSentinel is now {'enabled' if enabled else 'disabled'}.")

    @secret_sentinel.command(name="setup")
    @commands.bot_has_permissions(send_messages=True, embed_links=True)
    async def setup_command(self, ctx: commands.Context, channel: discord.TextChannel | None = None) -> None:
        """Configure safe defaults and use the selected channel for alerts."""
        destination = channel or ctx.channel
        if not isinstance(destination, discord.TextChannel):
            raise commands.BadArgument("Choose a text channel for private staff alerts.")
        permissions = destination.permissions_for(ctx.guild.me)
        if not permissions.send_messages or not permissions.embed_links:
            raise commands.BadArgument("I need Send Messages and Embed Links in the alert channel.")
        can_delete = ctx.guild.me.guild_permissions.manage_messages
        conf = self.config.guild(ctx.guild)
        await conf.log_channel_id.set(destination.id)
        await conf.action.set("delete" if can_delete else "report")
        await conf.enabled.set(True)
        await ctx.send(
            f"SecretSentinel enabled with alerts in {destination.mention}. "
            f"Action: **{'delete and report' if can_delete else 'report only'}**."
        )

    @secret_sentinel.command(name="status")
    async def status(self, ctx: commands.Context) -> None:
        """Show configuration, exclusions, and permission warnings."""
        settings = await self.config.guild(ctx.guild).all()
        channel = ctx.guild.get_channel(settings["log_channel_id"]) if settings["log_channel_id"] else None
        warnings = []
        if settings["enabled"] and channel is None:
            warnings.append("No usable alert channel is configured.")
        if settings["action"] == "delete" and not ctx.guild.me.guild_permissions.manage_messages:
            warnings.append("Delete mode needs Manage Messages.")
        embed = discord.Embed(
            title="SecretSentinel status", color=discord.Color.green() if not warnings else discord.Color.orange()
        )
        embed.add_field(name="Enabled", value="Yes" if settings["enabled"] else "No")
        embed.add_field(name="Action", value=settings["action"].title())
        embed.add_field(name="Alerts", value=channel.mention if channel else "Not configured")
        embed.add_field(name="Attachment scanning", value="On" if settings["scan_attachments"] else "Off")
        embed.add_field(name="Alert cooldown", value=f"{settings['alert_cooldown_seconds']} seconds")
        embed.add_field(name="OpsRoom incidents", value="On" if settings["create_opsroom_incidents"] else "Off")
        embed.add_field(name="Disabled detectors", value=str(len(settings["disabled_kinds"])))
        embed.add_field(name="Monitored bots", value=str(len(settings["monitored_bot_ids"])))
        embed.add_field(name="Excluded channels", value=str(len(settings["ignored_channel_ids"])))
        embed.add_field(name="Excluded roles", value=str(len(settings["ignored_role_ids"])))
        if warnings:
            embed.add_field(name="Warnings", value="\n".join(f"• {item}" for item in warnings), inline=False)
        await ctx.send(embed=embed)

    @secret_sentinel.command(name="action")
    async def action(self, ctx: commands.Context, action: str) -> None:
        """Choose delete or report-only behavior."""
        action = action.casefold().replace("-", "")
        if action not in {"delete", "report", "reportonly"}:
            raise commands.BadArgument("Action must be `delete` or `report`.")
        stored = "report" if action.startswith("report") else "delete"
        await self.config.guild(ctx.guild).action.set(stored)
        await ctx.send(f"SecretSentinel action set to `{stored}`.")

    @secret_sentinel.command(name="attachments")
    async def attachments(self, ctx: commands.Context, enabled: bool) -> None:
        """Enable or disable scanning of small text attachments."""
        await self.config.guild(ctx.guild).scan_attachments.set(enabled)
        await ctx.send(f"Text attachment scanning is now {'enabled' if enabled else 'disabled'}.")

    @secret_sentinel.command(name="cooldown")
    async def cooldown(self, ctx: commands.Context, seconds: commands.Range[int, 0, 3600]) -> None:
        """Set duplicate alert suppression for the same author and detector types."""
        await self.config.guild(ctx.guild).alert_cooldown_seconds.set(int(seconds))
        await ctx.send(f"Duplicate alert cooldown set to {int(seconds)} second(s). Message actions still run every time.")

    @secret_sentinel.command(name="detector")
    async def detector(self, ctx: commands.Context, *, kind: str) -> None:
        """Toggle a detector type shown by the synthetic self-test or alerts."""
        known = {kind for kind, _pattern in PATTERNS}
        selected = next((item for item in known if item.casefold() == kind.casefold()), None)
        if not selected:
            raise commands.BadArgument("Unknown detector type: " + ", ".join(sorted(known)))
        async with self.config.guild(ctx.guild).disabled_kinds() as disabled:
            if selected in disabled:
                disabled.remove(selected)
                state = "enabled"
            else:
                disabled.append(selected)
                state = "disabled"
        await ctx.send(f"Detector **{selected}** is now {state}.")

    @secret_sentinel.command(name="scanbot")
    async def scan_bot(self, ctx: commands.Context, bot_user: discord.Member) -> None:
        """Toggle scanning for one explicitly selected bot account."""
        if not bot_user.bot:
            raise commands.BadArgument("Choose a bot account.")
        async with self.config.guild(ctx.guild).monitored_bot_ids() as bot_ids:
            if bot_user.id in bot_ids:
                bot_ids.remove(bot_user.id)
                state = "ignored"
            else:
                bot_ids.append(bot_user.id)
                state = "monitored"
        await ctx.send(f"{bot_user.mention} is now {state} by SecretSentinel.")

    @secret_sentinel.command(name="opsroom")
    async def opsroom_incidents(self, ctx: commands.Context, enabled: bool) -> None:
        """Toggle rate-limited credential-response incidents when OpsRoom is loaded."""
        if enabled and not self.bot.get_cog("OpsRoom"):
            raise commands.BadArgument("OpsRoom is not loaded.")
        if enabled:
            opsroom = self.bot.get_cog("OpsRoom")
            role_id = await opsroom.config.guild(ctx.guild).response_role_id()
            if not role_id or not ctx.guild.get_role(role_id):
                raise commands.BadArgument("Configure an OpsRoom response role before enabling credential incidents.")
        await self.config.guild(ctx.guild).create_opsroom_incidents.set(enabled)
        await ctx.send(f"OpsRoom credential incidents are now {'enabled' if enabled else 'disabled'}.")

    @secret_sentinel.command(name="logchannel")
    async def log_channel(self, ctx: commands.Context, channel: discord.TextChannel | None = None) -> None:
        """Set the staff alert channel, or omit it to disable alerts."""
        await self.config.guild(ctx.guild).log_channel_id.set(channel.id if channel else None)
        await ctx.send(f"Alert channel set to {channel.mention}." if channel else "Alert channel disabled.")

    @secret_sentinel.command(name="ignorechannel")
    async def ignore_channel(self, ctx: commands.Context, channel: discord.TextChannel) -> None:
        """Toggle a channel exclusion."""
        async with self.config.guild(ctx.guild).ignored_channel_ids() as ids:
            if channel.id in ids:
                ids.remove(channel.id)
                result = "removed from"
            else:
                ids.append(channel.id)
                result = "added to"
        await ctx.send(f"{channel.mention} {result} the exclusion list.")

    @secret_sentinel.command(name="ignorerole")
    async def ignore_role(self, ctx: commands.Context, role: discord.Role) -> None:
        """Toggle a role exclusion."""
        if role.is_default() or role.permissions.administrator:
            raise commands.BadArgument("The default role and Administrator roles cannot bypass secret detection.")
        async with self.config.guild(ctx.guild).ignored_role_ids() as ids:
            if role.id in ids:
                ids.remove(role.id)
                result = "removed from"
            else:
                ids.append(role.id)
                result = "added to"
        await ctx.send(f"{role.mention} {result} the exclusion list.")

    @secret_sentinel.command(name="selftest", aliases=["scan"])
    async def self_test(self, ctx: commands.Context) -> None:
        """Test detectors with synthetic values; never paste a real credential."""
        samples = [
            "ghp_" + "A" * 36,
            "AKIA" + "B" * 16,
            "-----BEGIN " + "PRIVATE KEY-----",
        ]
        kinds = sorted({match.kind for sample in samples for match in find_secrets(sample)})
        await ctx.send("Synthetic self-test detected: " + ", ".join(kinds))
