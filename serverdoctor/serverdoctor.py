"""Read-only Discord server health diagnostics."""

from __future__ import annotations

import io
import time
from collections import Counter
from typing import TYPE_CHECKING, Any, ClassVar

import discord
from discord.ext import tasks
from redbot.core import Config, commands

from .checks import Finding, analyze_snapshot, finding_changes
from .dashboard_integration import DashboardIntegration

if TYPE_CHECKING:
    from redbot.core.bot import Red


class ServerDoctor(DashboardIntegration, commands.Cog):
    """Find configuration trouble without changing the server."""

    CONFIG_IDENTIFIER = 2026081802
    SCHEMA_VERSION = 2
    REQUIRED_BOT_PERMISSIONS: ClassVar[set[str]] = {
        "view_channel",
        "send_messages",
        "embed_links",
        "read_message_history",
    }
    DANGEROUS: ClassVar[set[str]] = {
        "administrator",
        "manage_guild",
        "manage_roles",
        "manage_channels",
        "manage_webhooks",
        "mention_everyone",
    }

    def __init__(self, bot: Red) -> None:
        self.bot = bot
        self.config = Config.get_conf(self, identifier=self.CONFIG_IDENTIFIER, force_registration=True)
        self.config.register_guild(
            schema_version=self.SCHEMA_VERSION,
            ignored_codes=[],
            last_scan_at=None,
            last_summary={},
            schedule_hours=0,
            report_channel_id=None,
            last_scheduled_at=0,
            last_finding_codes=[],
        )

    async def cog_load(self) -> None:
        for guild_id in await self.config.all_guilds():
            await self.config.guild_from_id(guild_id).schema_version.set(self.SCHEMA_VERSION)
        self.doctor_loop.start()

    def cog_unload(self) -> None:
        self.doctor_loop.cancel()

    async def red_delete_data_for_user(self, *, requester: str, user_id: int) -> None:
        return

    def _snapshot(self, guild: discord.Guild) -> dict[str, Any]:
        me = guild.me
        guild_perms = me.guild_permissions if me else discord.Permissions.none()
        names = Counter(role.name.casefold() for role in guild.roles if not role.is_default())
        assignable = [role for role in guild.roles if not role.managed and not role.is_default()]
        bot_role_low = bool(me and any(role >= me.top_role for role in assignable if role.members))
        blocked = []
        for channel in guild.text_channels:
            permissions = channel.permissions_for(me) if me else discord.Permissions.none()
            if not permissions.view_channel or not permissions.send_messages:
                blocked.append(f"#{channel.name}")
        return {
            "required_bot_permissions": self.REQUIRED_BOT_PERMISSIONS,
            "bot_permissions": {name for name, value in guild_perms if value},
            "everyone_dangerous_permissions": {
                name for name in self.DANGEROUS if getattr(guild.default_role.permissions, name, False)
            },
            "administrator_roles": [
                role.name for role in guild.roles if not role.is_default() and role.permissions.administrator
            ],
            "role_count": len(guild.roles),
            "channel_count": len(guild.channels),
            "bot_role_low": bot_role_low,
            "blocked_text_channels": blocked,
            "empty_unmanaged_roles": sum(not role.members and not role.managed and not role.is_default() for role in guild.roles),
            "duplicate_role_names": [name for name, count in names.items() if count > 1],
        }

    async def diagnose(self, guild: discord.Guild) -> list[Finding]:
        ignored = set(await self.config.guild(guild).ignored_codes())
        findings = analyze_snapshot(self._snapshot(guild))
        findings.extend(await self._cog_findings(guild))
        return [finding for finding in findings if finding.code not in ignored]

    async def _audit(self, guild: discord.Guild, action: str, status: str, detail: str = "") -> None:
        operations = self.bot.get_cog("OperationsCenter")
        if operations and hasattr(operations, "record_audit"):
            await operations.record_audit(guild, "ServerDoctor", action, status, detail)

    @tasks.loop(minutes=30)
    async def doctor_loop(self) -> None:
        now = int(time.time())
        for guild in self.bot.guilds:
            conf = self.config.guild(guild)
            settings = await conf.all()
            hours = int(settings["schedule_hours"])
            if not hours or now - int(settings["last_scheduled_at"]) < hours * 3600:
                continue
            channel = guild.get_channel(settings["report_channel_id"])
            if not isinstance(channel, discord.TextChannel):
                continue
            findings = await self.diagnose(guild)
            added, resolved = finding_changes(settings["last_finding_codes"], findings)
            if added or resolved:
                embed = discord.Embed(
                    title="ServerDoctor changes", color=discord.Color.orange() if added else discord.Color.green()
                )
                if added:
                    embed.add_field(
                        name="New findings",
                        value="\n".join(f"`{item.code}` [{item.severity}] {item.title}" for item in added)[:1024],
                        inline=False,
                    )
                if resolved:
                    embed.add_field(name="Resolved", value="\n".join(f"`{code}`" for code in resolved)[:1024], inline=False)
                try:
                    await channel.send(embed=embed, allowed_mentions=discord.AllowedMentions.none())
                except (discord.Forbidden, discord.HTTPException) as error:
                    await self._audit(guild, "scheduled scan", "failed", str(error))
                else:
                    await self._audit(guild, "scheduled scan", "completed", f"{len(added)} new, {len(resolved)} resolved")
            await conf.last_finding_codes.set([item.code for item in findings])
            await conf.last_scheduled_at.set(now)
            await conf.last_scan_at.set(now)
            await conf.last_summary.set(dict(Counter(item.severity for item in findings)))

    @doctor_loop.before_loop
    async def before_doctor_loop(self) -> None:
        await self.bot.wait_until_red_ready()

    async def _cog_findings(self, guild: discord.Guild) -> list[Finding]:
        """Inspect known cog configuration only when that cog is loaded."""
        findings: list[Finding] = []
        me = guild.me

        def channel_usable(channel_id: int | None) -> bool:
            channel = guild.get_channel(channel_id) if channel_id else None
            if not isinstance(channel, discord.TextChannel) or me is None:
                return False
            permissions = channel.permissions_for(me)
            return permissions.view_channel and permissions.send_messages and permissions.embed_links

        secret = self.bot.get_cog("SecretSentinel")
        if secret is not None:
            settings = await secret.config.guild(guild).all()
            if settings.get("enabled") and not settings.get("log_channel_id"):
                findings.append(
                    Finding("SECRET_LOG_MISSING", "high", "SecretSentinel has no alert channel", "Detections cannot reach staff.")
                )
            if settings.get("enabled") and settings.get("action") == "delete" and me and not me.guild_permissions.manage_messages:
                findings.append(
                    Finding(
                        "SECRET_DELETE_PERMISSION",
                        "high",
                        "SecretSentinel cannot delete leaks",
                        "Grant Manage Messages or use report mode.",
                    )
                )
            if settings.get("create_opsroom_incidents") and self.bot.get_cog("OpsRoom") is None:
                findings.append(
                    Finding(
                        "SECRET_OPSROOM_MISSING",
                        "medium",
                        "SecretSentinel incident creation has no OpsRoom",
                        "Load OpsRoom or disable credential-response incidents.",
                    )
                )
            elif settings.get("create_opsroom_incidents"):
                opsroom = self.bot.get_cog("OpsRoom")
                role_id = await opsroom.config.guild(guild).response_role_id()
                if not role_id or not guild.get_role(role_id):
                    findings.append(
                        Finding(
                            "SECRET_OPSROOM_ROLE",
                            "high",
                            "Credential incidents have no private response role",
                            "Configure a valid OpsRoom response role or disable credential incidents.",
                        )
                    )

        knowledge = self.bot.get_cog("KnowledgeGarden")
        if knowledge is not None:
            auto = await knowledge.config.guild(guild).auto_capture_forumflow()
            if auto and self.bot.get_cog("ForumFlow") is None:
                findings.append(
                    Finding(
                        "KNOWLEDGE_SOURCE_MISSING",
                        "medium",
                        "KnowledgeGarden automation has no ForumFlow",
                        "Load ForumFlow or disable automatic capture.",
                    )
                )
            review_channel_id = await knowledge.config.guild(guild).review_channel_id()
            if review_channel_id and not channel_usable(review_channel_id):
                findings.append(
                    Finding(
                        "KNOWLEDGE_REVIEW_CHANNEL",
                        "high",
                        "KnowledgeGarden cannot send review notices",
                        "Choose a channel where the bot can send messages and embeds.",
                    )
                )

        ledger = self.bot.get_cog("DecisionLedger")
        if ledger is not None:
            settings = await ledger.config.guild(guild).all()
            if settings.get("auto_import_suggestions") and self.bot.get_cog("SuggestionBox") is None:
                findings.append(
                    Finding(
                        "DECISION_SUGGESTIONS_MISSING",
                        "medium",
                        "Suggestion auto-import has no SuggestionBox",
                        "Load SuggestionBox or disable that integration.",
                    )
                )
            if settings.get("auto_import_incident_actions") and self.bot.get_cog("OpsRoom") is None:
                findings.append(
                    Finding(
                        "DECISION_INCIDENTS_MISSING",
                        "medium",
                        "Incident auto-import has no OpsRoom",
                        "Load OpsRoom or disable that integration.",
                    )
                )
            if settings.get("reminder_channel_id") and not channel_usable(settings["reminder_channel_id"]):
                findings.append(
                    Finding(
                        "DECISION_REMINDER_CHANNEL",
                        "high",
                        "DecisionLedger cannot send reminders",
                        "Choose a channel where the bot can send messages and embeds.",
                    )
                )

        suggestions = self.bot.get_cog("SuggestionBox")
        if suggestions is not None:
            settings = await suggestions.config.guild(guild).all()
            if settings.get("enabled") and not guild.get_channel(settings.get("suggestion_channel_id")):
                findings.append(
                    Finding(
                        "SUGGESTION_CHANNEL_MISSING",
                        "high",
                        "SuggestionBox channel is unavailable",
                        "Choose an existing suggestion channel.",
                    )
                )

        events = self.bot.get_cog("EventCheckin")
        if events is not None:
            records = await events.config.guild(guild).events()
            broken = sum(
                event.get("status") == "open" and (not event.get("message_id") or not guild.get_channel(event.get("channel_id")))
                for event in records.values()
            )
            if broken:
                findings.append(
                    Finding(
                        "EVENT_PANELS_MISSING",
                        "high",
                        "Open EventCheckin panels are unavailable",
                        f"{broken} open event(s) have no usable panel channel or message ID.",
                    )
                )

        forumflow = self.bot.get_cog("ForumFlow")
        if forumflow is not None:
            forum_ids = await forumflow.config.guild(guild).forum_ids()
            missing = sum(not isinstance(guild.get_channel(item), discord.ForumChannel) for item in forum_ids)
            if missing:
                findings.append(
                    Finding(
                        "FORUMFLOW_FORUM_MISSING",
                        "medium",
                        "ForumFlow references missing forums",
                        f"{missing} configured forum ID(s) are unavailable.",
                    )
                )
        operations = self.bot.get_cog("OperationsCenter")
        if operations is not None:
            settings = await operations.config.guild(guild).all()
            if settings.get("audit_channel_id") and not channel_usable(settings["audit_channel_id"]):
                findings.append(
                    Finding(
                        "OPERATIONS_ALERT_CHANNEL",
                        "high",
                        "OperationsCenter cannot send failure alerts",
                        "Choose a channel where the bot can send messages and embeds.",
                    )
                )
        return findings

    @commands.hybrid_group(name="serverdoctor", aliases=["serverhealth"], invoke_without_command=True)
    @commands.guild_only()
    @commands.admin_or_permissions(manage_guild=True)
    async def server_doctor(self, ctx: commands.Context) -> None:
        """Run read-only server configuration checks."""
        await ctx.send_help()

    @server_doctor.command(name="scan")
    async def scan(self, ctx: commands.Context) -> None:
        """Run health checks and show the current findings."""
        findings = await self.diagnose(ctx.guild)
        counts = Counter(item.severity for item in findings)
        await self.config.guild(ctx.guild).last_scan_at.set(int(time.time()))
        await self.config.guild(ctx.guild).last_summary.set(dict(counts))
        if not findings:
            await ctx.send(
                embed=discord.Embed(title="ServerDoctor", description="No active findings.", color=discord.Color.green())
            )
            return
        pages: list[discord.Embed] = []
        for offset in range(0, len(findings), 8):
            embed = discord.Embed(title="ServerDoctor findings", color=discord.Color.orange())
            for finding in findings[offset : offset + 8]:
                embed.add_field(
                    name=f"[{finding.severity.upper()}] {finding.code}",
                    value=f"**{finding.title}**\n{finding.detail}"[:1024],
                    inline=False,
                )
            embed.set_footer(text="Read-only report; no settings were changed.")
            pages.append(embed)
        for embed in pages:
            await ctx.send(embed=embed)

    @server_doctor.command(name="export")
    async def export(self, ctx: commands.Context) -> None:
        """Export current findings as a text report."""
        findings = await self.diagnose(ctx.guild)
        lines = [f"ServerDoctor report for {ctx.guild.name}", ""]
        lines.extend(f"[{item.severity.upper()}] {item.code}: {item.title}\n{item.detail}\n" for item in findings)
        if not findings:
            lines.append("No active findings.")
        await ctx.send(file=discord.File(io.BytesIO("\n".join(lines).encode()), filename="serverdoctor-report.txt"))

    @server_doctor.command(name="ignore")
    async def ignore(self, ctx: commands.Context, code: str) -> None:
        """Suppress a finding code after staff review."""
        code = code.upper()
        known = {item.code for item in analyze_snapshot(self._snapshot(ctx.guild))}
        known.update(item.code for item in await self._cog_findings(ctx.guild))
        if code not in known:
            raise commands.BadArgument("That code is not present in the current unfiltered report.")
        async with self.config.guild(ctx.guild).ignored_codes() as codes:
            if code not in codes:
                codes.append(code)
        await ctx.send(f"Ignored `{code}`. ServerDoctor did not change the underlying server setting.")

    @server_doctor.command(name="unignore")
    async def unignore(self, ctx: commands.Context, code: str) -> None:
        """Restore a suppressed finding code."""
        code = code.upper()
        async with self.config.guild(ctx.guild).ignored_codes() as codes:
            if code in codes:
                codes.remove(code)
        await ctx.send(f"Restored `{code}`.")

    @server_doctor.command(name="ignored")
    async def ignored(self, ctx: commands.Context) -> None:
        """List suppressed finding codes."""
        codes = await self.config.guild(ctx.guild).ignored_codes()
        await ctx.send(", ".join(f"`{code}`" for code in codes) if codes else "No finding codes are suppressed.")

    @server_doctor.command(name="cogs")
    async def cogs(self, ctx: commands.Context) -> None:
        """Show which optional TaakosCogs checks are active."""
        names = ("SecretSentinel", "KnowledgeGarden", "DecisionLedger", "SuggestionBox", "EventCheckin", "ForumFlow")
        await ctx.send("\n".join(f"{name}: **{'checked' if self.bot.get_cog(name) else 'not loaded'}**" for name in names))

    @server_doctor.command(name="schedule")
    async def schedule(
        self,
        ctx: commands.Context,
        hours: commands.Range[int, 0, 168],
        channel: discord.TextChannel | None = None,
    ) -> None:
        """Schedule change-only health reports; use zero hours to disable them."""
        conf = self.config.guild(ctx.guild)
        if int(hours) == 0:
            await conf.schedule_hours.set(0)
            await ctx.send("Scheduled ServerDoctor reports disabled.")
            return
        destination = channel or ctx.channel
        if not isinstance(destination, discord.TextChannel):
            raise commands.BadArgument("Choose a text channel for scheduled reports.")
        permissions = destination.permissions_for(ctx.guild.me)
        if not permissions.send_messages or not permissions.embed_links:
            raise commands.BadArgument("I need Send Messages and Embed Links in the report channel.")
        findings = await self.diagnose(ctx.guild)
        await conf.report_channel_id.set(destination.id)
        await conf.schedule_hours.set(int(hours))
        await conf.last_finding_codes.set([item.code for item in findings])
        await conf.last_scheduled_at.set(int(time.time()))
        await ctx.send(f"ServerDoctor will check every {int(hours)} hour(s) and report only changes in {destination.mention}.")
