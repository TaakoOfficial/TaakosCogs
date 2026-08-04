"""Buffered, content-free Discord community health analytics."""

from __future__ import annotations

import csv
import io
import time
from collections import defaultdict
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any

import discord
from discord.ext import tasks
from redbot.core import Config, commands

from .dashboard_integration import DashboardIntegration

if TYPE_CHECKING:
    from redbot.core.bot import Red


class CommunityPulse(DashboardIntegration, commands.Cog):
    """Measure whether new members become active and stay engaged."""

    CONFIG_IDENTIFIER = 2026080307
    COLOR = 0x00A8A8

    def __init__(self, bot: Red) -> None:
        self.bot = bot
        self._pending: dict[int, dict[int, dict[str, int]]] = defaultdict(dict)
        self.config = Config.get_conf(self, identifier=self.CONFIG_IDENTIFIER, force_registration=True)
        self.config.register_guild(
            enabled=False,
            activation_messages=5,
            inactive_days=30,
            members={},
            total_joins=0,
            total_leaves=0,
            tracking_started_at=None,
            last_flush_at=0,
        )

    async def cog_load(self) -> None:
        self.flush_loop.start()

    def cog_unload(self) -> None:
        self.flush_loop.cancel()

    @staticmethod
    def _now() -> int:
        return int(time.time())

    async def _flush_guild(self, guild: discord.Guild) -> int:
        pending = self._pending.pop(guild.id, {})
        if not pending:
            return 0
        conf = self.config.guild(guild)
        records = await conf.members()
        for user_id, update in pending.items():
            member = guild.get_member(user_id)
            key = str(user_id)
            record = records.setdefault(
                key,
                {
                    "user_id": user_id,
                    "joined_at": int(member.joined_at.timestamp()) if member and member.joined_at else update["last_at"],
                    "left_at": None,
                    "first_message_at": update["first_at"],
                    "last_message_at": update["last_at"],
                    "message_count": 0,
                    "role_ids": [],
                },
            )
            record["first_message_at"] = record.get("first_message_at") or update["first_at"]
            record["last_message_at"] = max(int(record.get("last_message_at") or 0), update["last_at"])
            record["message_count"] = int(record.get("message_count") or 0) + update["count"]
            record["left_at"] = None
            if member:
                record["role_ids"] = [role.id for role in member.roles if role != guild.default_role and not role.managed]
        await conf.members.set(records)
        await conf.last_flush_at.set(self._now())
        return len(pending)

    async def _flush_all(self) -> None:
        for guild_id in list(self._pending):
            guild = self.bot.get_guild(guild_id)
            if guild:
                await self._flush_guild(guild)
            else:
                self._pending.pop(guild_id, None)

    async def red_delete_data_for_user(self, *, requester: str, user_id: int) -> None:
        for pending in self._pending.values():
            pending.pop(user_id, None)
        for guild_id in await self.config.all_guilds():
            conf = self.config.guild_from_id(guild_id)
            async with conf.members() as records:
                records.pop(str(user_id), None)

    @tasks.loop(minutes=5)
    async def flush_loop(self) -> None:
        await self._flush_all()

    @flush_loop.before_loop
    async def before_flush_loop(self) -> None:
        await self.bot.wait_until_red_ready()

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message) -> None:
        if not message.guild or message.author.bot or not isinstance(message.author, discord.Member):
            return
        if not await self.config.guild(message.guild).enabled():
            return
        now = self._now()
        pending = self._pending[message.guild.id]
        record = pending.setdefault(message.author.id, {"count": 0, "first_at": now, "last_at": now})
        record["count"] += 1
        record["last_at"] = now

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member) -> None:
        conf = self.config.guild(member.guild)
        if not await conf.enabled():
            return
        now = self._now()
        async with conf.members() as records:
            records[str(member.id)] = {
                "user_id": member.id,
                "joined_at": int(member.joined_at.timestamp()) if member.joined_at else now,
                "left_at": None,
                "first_message_at": None,
                "last_message_at": None,
                "message_count": 0,
                "role_ids": [],
            }
        await conf.total_joins.set((await conf.total_joins()) + 1)

    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member) -> None:
        conf = self.config.guild(member.guild)
        if not await conf.enabled():
            return
        await self._flush_guild(member.guild)
        async with conf.members() as records:
            record = records.setdefault(
                str(member.id),
                {
                    "user_id": member.id,
                    "joined_at": int(member.joined_at.timestamp()) if member.joined_at else self._now(),
                    "first_message_at": None,
                    "last_message_at": None,
                    "message_count": 0,
                    "role_ids": [],
                },
            )
            record["left_at"] = self._now()
        await conf.total_leaves.set((await conf.total_leaves()) + 1)

    async def _records(self, guild: discord.Guild) -> dict[str, dict[str, Any]]:
        await self._flush_guild(guild)
        return await self.config.guild(guild).members()

    async def _seed_members(self, guild: discord.Guild) -> int:
        """Create a baseline for members present when tracking is first enabled."""
        conf = self.config.guild(guild)
        now = self._now()
        added = 0
        async with conf.members() as records:
            for member in guild.members:
                if member.bot or str(member.id) in records:
                    continue
                records[str(member.id)] = {
                    "user_id": member.id,
                    "joined_at": int(member.joined_at.timestamp()) if member.joined_at else now,
                    "left_at": None,
                    "first_message_at": None,
                    "last_message_at": None,
                    "message_count": 0,
                    "role_ids": [role.id for role in member.roles if role != guild.default_role and not role.managed],
                }
                added += 1
        return added

    @commands.hybrid_group(name="communitypulse", aliases=["pulse"], invoke_without_command=True)
    @commands.guild_only()
    async def community_pulse(self, ctx: commands.Context) -> None:
        """Inspect onboarding, activation, retention, and churn."""
        await ctx.send_help()

    @community_pulse.command(name="enable")
    @commands.admin_or_permissions(manage_guild=True)
    async def enable(self, ctx: commands.Context) -> None:
        """Enable content-free member activity tracking."""
        conf = self.config.guild(ctx.guild)
        await conf.enabled.set(True)
        if not await conf.tracking_started_at():
            await conf.tracking_started_at.set(self._now())
        added = await self._seed_members(ctx.guild)
        await ctx.send(f"CommunityPulse enabled with **{added}** new baseline member(s). Message content is not stored.")

    @community_pulse.command(name="disable")
    @commands.admin_or_permissions(manage_guild=True)
    async def disable(self, ctx: commands.Context) -> None:
        """Stop collecting new activity while retaining existing metrics."""
        await self._flush_guild(ctx.guild)
        await self.config.guild(ctx.guild).enabled.set(False)
        await ctx.send("CommunityPulse disabled. Existing metrics were retained.")

    @community_pulse.command(name="thresholds")
    @commands.admin_or_permissions(manage_guild=True)
    async def thresholds(
        self,
        ctx: commands.Context,
        activation_messages: commands.Range[int, 1, 1000],
        inactive_days: commands.Range[int, 1, 3650],
    ) -> None:
        """Set activation message count and inactivity window."""
        conf = self.config.guild(ctx.guild)
        await conf.activation_messages.set(int(activation_messages))
        await conf.inactive_days.set(int(inactive_days))
        await ctx.send(f"Activation: **{activation_messages} messages**; inactive: **{inactive_days} days**.")

    @community_pulse.command(name="overview")
    @commands.admin_or_permissions(manage_guild=True)
    async def overview(self, ctx: commands.Context) -> None:
        """Show current community health totals."""
        records = await self._records(ctx.guild)
        settings = await self.config.guild(ctx.guild).all()
        now = self._now()
        active_records = [record for record in records.values() if not record.get("left_at")]
        activated = [
            record for record in active_records if int(record.get("message_count") or 0) >= settings["activation_messages"]
        ]
        inactive_cutoff = now - settings["inactive_days"] * 86400
        inactive = [record for record in active_records if int(record.get("last_message_at") or 0) < inactive_cutoff]
        embed = discord.Embed(title="CommunityPulse Overview", color=self.COLOR, timestamp=discord.utils.utcnow())
        embed.add_field(name="Tracked current members", value=f"{len(active_records):,}")
        embed.add_field(name="Activated", value=f"{len(activated):,}")
        embed.add_field(name="Inactive", value=f"{len(inactive):,}")
        embed.add_field(name="Observed joins", value=f"{settings['total_joins']:,}")
        embed.add_field(name="Observed leaves", value=f"{settings['total_leaves']:,}")
        activation_rate = len(activated) / len(active_records) * 100 if active_records else 0
        embed.add_field(name="Activation rate", value=f"{activation_rate:.1f}%")
        await ctx.send(embed=embed)

    @community_pulse.command(name="funnel")
    @commands.admin_or_permissions(manage_guild=True)
    async def funnel(self, ctx: commands.Context) -> None:
        """Show join → first message → activation → retained stages."""
        records = await self._records(ctx.guild)
        settings = await self.config.guild(ctx.guild).all()
        joined = len(records)
        spoke = sum(bool(record.get("first_message_at")) for record in records.values())
        activated = sum(int(record.get("message_count") or 0) >= settings["activation_messages"] for record in records.values())
        retained = sum(
            int(record.get("message_count") or 0) >= settings["activation_messages"] and not record.get("left_at")
            for record in records.values()
        )
        lines = [
            f"Joined/tracked        {joined:>6,}  {100 if joined else 0:>5.1f}%",
            f"Sent first message    {spoke:>6,}  {spoke / joined * 100 if joined else 0:>5.1f}%",
            f"Activated             {activated:>6,}  {activated / joined * 100 if joined else 0:>5.1f}%",
            f"Still in server       {retained:>6,}  {retained / joined * 100 if joined else 0:>5.1f}%",
        ]
        body = "\n".join(lines)
        await ctx.send(f"```text\n{body}\n```")

    @community_pulse.command(name="inactive")
    @commands.admin_or_permissions(manage_guild=True)
    async def inactive(self, ctx: commands.Context, days: commands.Range[int, 1, 3650] | None = None) -> None:
        """List tracked current members inactive for the chosen period."""
        records = await self._records(ctx.guild)
        chosen = int(days or await self.config.guild(ctx.guild).inactive_days())
        cutoff = self._now() - chosen * 86400
        rows = [
            record
            for record in records.values()
            if not record.get("left_at") and int(record.get("last_message_at") or 0) < cutoff
        ]
        rows.sort(key=lambda record: int(record.get("last_message_at") or 0))
        lines = [
            f"• <@{record['user_id']}> — "
            + (f"last active <t:{record['last_message_at']}:R>" if record.get("last_message_at") else "has not spoken")
            for record in rows[:50]
        ]
        await ctx.send(
            embed=discord.Embed(
                title=f"Inactive for {chosen}+ days", description="\n".join(lines) or "No matching members.", color=self.COLOR
            )
        )

    @community_pulse.command(name="cohorts")
    @commands.admin_or_permissions(manage_guild=True)
    async def cohorts(self, ctx: commands.Context) -> None:
        """Group tracked members by join month with activation and retention rates."""
        records = await self._records(ctx.guild)
        threshold = await self.config.guild(ctx.guild).activation_messages()
        cohorts: dict[str, dict[str, int]] = defaultdict(lambda: {"joined": 0, "activated": 0, "retained": 0})
        for record in records.values():
            joined_at = record.get("joined_at")
            if not joined_at:
                continue
            month = datetime.fromtimestamp(int(joined_at), tz=timezone.utc).strftime("%Y-%m")
            cohorts[month]["joined"] += 1
            if int(record.get("message_count") or 0) >= threshold:
                cohorts[month]["activated"] += 1
                if not record.get("left_at"):
                    cohorts[month]["retained"] += 1
        lines = []
        for month, values in sorted(cohorts.items(), reverse=True)[:18]:
            joined = values["joined"]
            activated_rate = values["activated"] / joined * 100
            retained_rate = values["retained"] / joined * 100
            lines.append(
                f"{month}  joined={joined:>4}  activated={activated_rate:>5.1f}%  retained={retained_rate:>5.1f}%",
            )
        body = "\n".join(lines) if lines else "No cohort data."
        await ctx.send(f"```text\n{body}\n```")

    @community_pulse.command(name="roles")
    @commands.admin_or_permissions(manage_guild=True)
    async def roles(self, ctx: commands.Context) -> None:
        """Show adoption of non-managed roles among tracked current members."""
        records = await self._records(ctx.guild)
        counts: dict[int, int] = defaultdict(int)
        current = [record for record in records.values() if not record.get("left_at")]
        for record in current:
            for role_id in record.get("role_ids", []):
                counts[int(role_id)] += 1
        rows = sorted(counts.items(), key=lambda item: item[1], reverse=True)
        lines = (
            [f"• <@&{role_id}> — **{count:,}** ({count / len(current) * 100:.1f}%)" for role_id, count in rows[:25]]
            if current
            else []
        )
        await ctx.send(
            embed=discord.Embed(title="Role Adoption", description="\n".join(lines) or "No role data.", color=self.COLOR)
        )

    @community_pulse.command(name="export")
    @commands.admin_or_permissions(manage_guild=True)
    async def export(self, ctx: commands.Context) -> None:
        """Export member-level metrics as CSV."""
        records = await self._records(ctx.guild)
        output = io.StringIO()
        fields = ["user_id", "joined_at", "left_at", "first_message_at", "last_message_at", "message_count", "role_ids"]
        writer = csv.DictWriter(output, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        for record in records.values():
            row = dict(record)
            row["role_ids"] = "|".join(str(role_id) for role_id in row.get("role_ids", []))
            writer.writerow(row)
        await ctx.send(file=discord.File(io.BytesIO(output.getvalue().encode()), filename="communitypulse.csv"))
