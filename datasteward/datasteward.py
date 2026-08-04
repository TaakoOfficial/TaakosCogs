"""Dry-run-first retention and privacy request operations."""

from __future__ import annotations

import time
from contextlib import suppress
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any

import discord
from discord.ext import tasks
from redbot.core import Config, commands

from .dashboard_integration import DashboardIntegration

if TYPE_CHECKING:
    from redbot.core.bot import Red


class DataSteward(DashboardIntegration, commands.Cog):
    """Make message retention deliberate, bounded, and observable."""

    CONFIG_IDENTIFIER = 2026080309
    COLOR = 0x1ABC9C
    MAX_PER_CHANNEL_RUN = 250

    def __init__(self, bot: Red) -> None:
        self.bot = bot
        self.config = Config.get_conf(self, identifier=self.CONFIG_IDENTIFIER, force_registration=True)
        self.config.register_guild(
            policies={},
            enabled=False,
            dry_run=True,
            log_channel_id=None,
            last_run_at=0,
            last_result={},
            next_request_id=1,
            requests={},
        )

    async def cog_load(self) -> None:
        self.retention_loop.start()

    def cog_unload(self) -> None:
        self.retention_loop.cancel()

    @staticmethod
    def _now() -> int:
        return int(time.time())

    async def _log(self, guild: discord.Guild, title: str, description: str, color: int | None = None) -> None:
        channel_id = await self.config.guild(guild).log_channel_id()
        channel = guild.get_channel(channel_id) if channel_id else None
        if isinstance(channel, discord.TextChannel):
            with suppress(discord.HTTPException):
                await channel.send(
                    embed=discord.Embed(
                        title=title,
                        description=description,
                        color=color or self.COLOR,
                        timestamp=discord.utils.utcnow(),
                    ),
                )

    async def _apply_policy(
        self,
        channel: discord.TextChannel,
        days: int,
        *,
        enforce: bool,
        limit: int = MAX_PER_CHANNEL_RUN,
    ) -> dict[str, int]:
        cutoff = datetime.fromtimestamp(self._now() - days * 86400, tz=timezone.utc)
        result = {"candidates": 0, "deleted": 0, "pinned": 0, "errors": 0}
        try:
            async for message in channel.history(before=cutoff, limit=limit, oldest_first=True):
                if message.pinned:
                    result["pinned"] += 1
                    continue
                result["candidates"] += 1
                if not enforce:
                    continue
                try:
                    await message.delete(reason=f"DataSteward {days}-day retention policy")
                except (discord.Forbidden, discord.HTTPException):
                    result["errors"] += 1
                else:
                    result["deleted"] += 1
        except (discord.Forbidden, discord.HTTPException):
            result["errors"] += 1
        return result

    async def _run_guild(self, guild: discord.Guild, *, force_dry_run: bool | None = None) -> dict[str, Any]:
        conf = self.config.guild(guild)
        settings = await conf.all()
        enforce = settings["enabled"] and not settings["dry_run"]
        if force_dry_run is True:
            enforce = False
        totals = {"channels": 0, "candidates": 0, "deleted": 0, "pinned": 0, "errors": 0, "enforced": enforce}
        details = []
        for channel_key, policy in settings["policies"].items():
            if not policy.get("enabled", True):
                continue
            channel = guild.get_channel(int(channel_key))
            if not isinstance(channel, discord.TextChannel):
                totals["errors"] += 1
                continue
            result = await self._apply_policy(channel, int(policy["days"]), enforce=enforce)
            totals["channels"] += 1
            for key in ("candidates", "deleted", "pinned", "errors"):
                totals[key] += result[key]
            details.append({"channel_id": channel.id, "days": policy["days"], **result})
        totals["details"] = details
        totals["ran_at"] = self._now()
        await conf.last_run_at.set(totals["ran_at"])
        await conf.last_result.set(totals)
        return totals

    async def red_delete_data_for_user(self, *, requester: str, user_id: int) -> None:
        for guild_id in await self.config.all_guilds():
            conf = self.config.guild_from_id(guild_id)
            async with conf.policies() as policies:
                for policy in policies.values():
                    if policy.get("created_by") == user_id:
                        policy["created_by"] = None
            async with conf.requests() as requests:
                for request in requests.values():
                    if request.get("user_id") == user_id:
                        request["user_id"] = None
                        request["details"] = "[deleted by data request]"
                    if request.get("reviewer_id") == user_id:
                        request["reviewer_id"] = None

    @tasks.loop(hours=6)
    async def retention_loop(self) -> None:
        for guild in self.bot.guilds:
            settings = await self.config.guild(guild).all()
            if not settings["enabled"] or settings["dry_run"] or not settings["policies"]:
                continue
            result = await self._run_guild(guild)
            await self._log(
                guild,
                "DataSteward scheduled retention run",
                f"Checked {result['channels']} channel(s); deleted {result['deleted']} message(s); "
                f"protected {result['pinned']} pinned message(s); {result['errors']} error(s).",
            )

    @retention_loop.before_loop
    async def before_retention_loop(self) -> None:
        await self.bot.wait_until_red_ready()

    @commands.hybrid_group(name="datasteward", aliases=["retention"], invoke_without_command=True)
    @commands.guild_only()
    async def data_steward(self, ctx: commands.Context) -> None:
        """Manage channel retention and privacy requests."""
        await ctx.send_help()

    @data_steward.group(name="policy", invoke_without_command=True)
    @commands.admin_or_permissions(manage_messages=True)
    async def policy(self, ctx: commands.Context) -> None:
        """Manage per-channel retention policies."""
        policies = await self.config.guild(ctx.guild).policies()
        lines = [
            f"• <#{channel_id}> — **{record['days']} days** · {'enabled' if record.get('enabled', True) else 'paused'}"
            for channel_id, record in policies.items()
        ]
        await ctx.send("\n".join(lines) or "No retention policies configured.")

    @policy.command(name="set")
    async def policy_set(self, ctx: commands.Context, channel: discord.TextChannel, days: commands.Range[int, 1, 3650]) -> None:
        """Set a retention window. New policies do not enable enforcement."""
        async with self.config.guild(ctx.guild).policies() as policies:
            policies[str(channel.id)] = {
                "days": int(days),
                "enabled": True,
                "created_by": ctx.author.id,
                "updated_at": self._now(),
            }
        await ctx.send(
            f"Policy set: keep messages in {channel.mention} for **{days} days**. DataSteward remains in its current mode."
        )

    @policy.command(name="remove")
    async def policy_remove(self, ctx: commands.Context, channel: discord.TextChannel) -> None:
        """Remove a retention policy without deleting anything."""
        async with self.config.guild(ctx.guild).policies() as policies:
            removed = policies.pop(str(channel.id), None)
        if not removed:
            raise commands.BadArgument("That channel has no policy.")
        await ctx.send(f"Removed the policy for {channel.mention}.")

    @data_steward.command(name="logchannel")
    @commands.admin_or_permissions(manage_guild=True)
    async def log_channel(self, ctx: commands.Context, channel: discord.TextChannel | None = None) -> None:
        """Set the private retention and privacy request audit channel."""
        await self.config.guild(ctx.guild).log_channel_id.set(channel.id if channel else None)
        await ctx.send(f"DataSteward logs will go to {channel.mention}." if channel else "DataSteward logging disabled.")

    @data_steward.command(name="preview")
    @commands.admin_or_permissions(manage_messages=True)
    async def preview(self, ctx: commands.Context) -> None:
        """Run every policy without deleting messages."""
        async with ctx.typing():
            result = await self._run_guild(ctx.guild, force_dry_run=True)
        await ctx.send(
            f"Previewed **{result['channels']}** channel(s): **{result['candidates']}** deletion candidate(s), "
            f"**{result['pinned']}** pinned message(s) protected, **{result['errors']}** error(s).",
        )

    @data_steward.command(name="mode")
    @commands.admin_or_permissions(manage_guild=True)
    async def mode(self, ctx: commands.Context, mode: str, confirmation: str = "") -> None:
        """Set disabled, dry-run, or enforce mode. Enforce requires `ENFORCE`."""
        mode = mode.casefold()
        conf = self.config.guild(ctx.guild)
        if mode == "disabled":
            await conf.enabled.set(False)
            await conf.dry_run.set(True)
        elif mode in {"dry", "dry-run", "preview"}:
            await conf.enabled.set(True)
            await conf.dry_run.set(True)
            mode = "dry-run"
        elif mode == "enforce":
            if confirmation != "ENFORCE":
                raise commands.BadArgument("Enforcement deletes messages. Re-run with the exact confirmation `ENFORCE`.")
            await conf.enabled.set(True)
            await conf.dry_run.set(False)
        else:
            raise commands.BadArgument("Mode must be disabled, dry-run, or enforce.")
        await self._log(ctx.guild, "DataSteward mode changed", f"{ctx.author.mention} set mode to **{mode}**.")
        await ctx.send(f"DataSteward mode: **{mode}**.")

    @data_steward.command(name="run")
    @commands.admin_or_permissions(manage_messages=True)
    async def run(self, ctx: commands.Context, confirmation: str = "") -> None:
        """Run now. Enforce mode requires `DELETE` on every manual run."""
        conf = self.config.guild(ctx.guild)
        settings = await conf.all()
        enforcing = settings["enabled"] and not settings["dry_run"]
        if enforcing and confirmation != "DELETE":
            raise commands.BadArgument("This run will delete messages. Re-run with the exact confirmation `DELETE`.")
        async with ctx.typing():
            result = await self._run_guild(ctx.guild)
        await self._log(
            ctx.guild,
            "DataSteward manual run",
            f"Run by {ctx.author.mention}: {result['candidates']} candidate(s), "
            f"{result['deleted']} deleted, {result['errors']} error(s).",
        )
        await ctx.send(
            f"Run complete: **{result['candidates']}** candidate(s), **{result['deleted']}** deleted, "
            f"**{result['pinned']}** pinned protected, **{result['errors']}** error(s).",
        )

    @data_steward.command(name="settings")
    async def settings(self, ctx: commands.Context) -> None:
        """Show current safety mode and last run summary."""
        data = await self.config.guild(ctx.guild).all()
        mode = "disabled" if not data["enabled"] else "dry-run" if data["dry_run"] else "ENFORCE"
        last = data["last_result"]
        embed = discord.Embed(title="DataSteward", color=self.COLOR)
        embed.add_field(name="Mode", value=mode)
        embed.add_field(name="Policies", value=str(len(data["policies"])))
        embed.add_field(name="Per-channel cap", value=str(self.MAX_PER_CHANNEL_RUN))
        embed.add_field(name="Last run", value=f"<t:{data['last_run_at']}:R>" if data["last_run_at"] else "Never", inline=False)
        if last:
            embed.add_field(
                name="Last result",
                value=(
                    f"{last.get('candidates', 0)} candidates · {last.get('deleted', 0)} deleted · {last.get('errors', 0)} errors"
                ),
                inline=False,
            )
        await ctx.send(embed=embed)

    @data_steward.command(name="request")
    async def request(self, ctx: commands.Context, request_type: str, *, details: str = "") -> None:
        """Open a data access, correction, or deletion request for server staff."""
        request_type = request_type.casefold()
        if request_type not in {"access", "correction", "deletion"}:
            raise commands.BadArgument("Request type must be access, correction, or deletion.")
        conf = self.config.guild(ctx.guild)
        request_id = await conf.next_request_id()
        record = {
            "request_id": request_id,
            "user_id": ctx.author.id,
            "type": request_type,
            "details": details[:1000],
            "status": "open",
            "created_at": self._now(),
            "reviewer_id": None,
            "reviewed_at": None,
            "review_note": "",
        }
        async with conf.requests() as requests:
            requests[str(request_id)] = record
        await conf.next_request_id.set(request_id + 1)
        await self._log(
            ctx.guild,
            f"Privacy request #{request_id}",
            f"{ctx.author.mention} opened a **{request_type}** request.\n{details}".strip(),
        )
        await ctx.send(
            f"Privacy request **#{request_id}** opened. This records a workflow request; "
            "it does not automatically invoke other cogs' deletion handlers."
        )

    @data_steward.command(name="review")
    @commands.admin_or_permissions(manage_guild=True)
    async def review(self, ctx: commands.Context, request_id: int, status: str, *, note: str = "") -> None:
        """Set a privacy request to in-progress, completed, or denied."""
        status = status.casefold()
        if status not in {"in-progress", "completed", "denied"}:
            raise commands.BadArgument("Status must be in-progress, completed, or denied.")
        async with self.config.guild(ctx.guild).requests() as requests:
            record = requests.get(str(request_id))
            if not record:
                raise commands.BadArgument("Request not found.")
            record.update(status=status, reviewer_id=ctx.author.id, reviewed_at=self._now(), review_note=note[:1000])
        await self._log(
            ctx.guild, f"Privacy request #{request_id} {status}", f"Reviewed by {ctx.author.mention}.\n{note}".strip()
        )
        await ctx.send(f"Privacy request **#{request_id}** marked **{status}**.")

    @data_steward.command(name="requests")
    @commands.admin_or_permissions(manage_guild=True)
    async def requests(self, ctx: commands.Context, status: str = "open") -> None:
        """List privacy workflow requests by status, or use all."""
        records = await self.config.guild(ctx.guild).requests()
        rows = [record for record in records.values() if status == "all" or record.get("status") == status]
        lines = [
            f"• **#{record['request_id']} {record['type']}** · {record['status']} · "
            f"<@{record['user_id']}> · <t:{record['created_at']}:R>"
            for record in rows[:25]
        ]
        await ctx.send(
            embed=discord.Embed(title="Privacy Requests", description="\n".join(lines) or "No requests.", color=self.COLOR)
        )
