"""Staff scheduling, time tracking, leave, and handoff workflows."""

from __future__ import annotations

import csv
import io
import time
from contextlib import suppress
from typing import TYPE_CHECKING

import discord
from redbot.core import Config, commands

from .dashboard_integration import DashboardIntegration

if TYPE_CHECKING:
    from redbot.core.bot import Red


class StaffOps(DashboardIntegration, commands.Cog):
    """Coordinate staff and volunteer coverage without external scheduling software."""

    CONFIG_IDENTIFIER = 2026080302
    COLOR = 0x57F287

    def __init__(self, bot: Red) -> None:
        self.bot = bot
        self.config = Config.get_conf(self, identifier=self.CONFIG_IDENTIFIER, force_registration=True)
        self.config.register_guild(
            staff_role_id=None,
            log_channel_id=None,
            max_shift_hours=16,
            next_shift_id=1,
            next_leave_id=1,
            shifts={},
            active_shifts={},
            availability={},
            leave_requests={},
            on_call=[],
            handoffs=[],
        )

    @staticmethod
    def _now() -> int:
        return int(time.time())

    async def _is_staff(self, member: discord.Member) -> bool:
        if member.id in getattr(self.bot, "owner_ids", set()) or member.guild_permissions.manage_guild:
            return True
        role_id = await self.config.guild(member.guild).staff_role_id()
        return bool(role_id and member.get_role(role_id))

    async def _require_staff(self, member: discord.Member) -> None:
        if not await self._is_staff(member):
            raise commands.CheckFailure("You are not in the configured staff team.")

    async def get_member_context(self, guild: discord.Guild, user_id: int) -> dict[str, object] | None:
        """Return bounded scheduling context for optional TaakosCogs integrations."""
        member = guild.get_member(user_id)
        if member is None or not await self._is_staff(member):
            return None
        conf = self.config.guild(guild)
        active = await conf.active_shifts()
        availability = await conf.availability()
        rota = await conf.on_call()
        leaves = await conf.leave_requests()
        on_call_position = next(
            (index for index, record in enumerate(rota, start=1) if record.get("user_id") == user_id),
            None,
        )
        approved_leave = next(
            (
                record.get("until")
                for record in reversed(list(leaves.values()))
                if record.get("user_id") == user_id and record.get("status") == "approved"
            ),
            None,
        )
        return {
            "active_shift": str(user_id) in active,
            "availability": (availability.get(str(user_id)) or {}).get("text"),
            "on_call_position": on_call_position,
            "approved_leave": approved_leave,
        }

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

    async def red_delete_data_for_user(self, *, requester: str, user_id: int) -> None:
        user_key = str(user_id)
        for guild_id in await self.config.all_guilds():
            conf = self.config.guild_from_id(guild_id)
            data = await conf.all()
            data["active_shifts"].pop(user_key, None)
            data["availability"].pop(user_key, None)
            data["on_call"] = [item for item in data["on_call"] if item.get("user_id") != user_id]
            for collection in (data["shifts"], data["leave_requests"]):
                for record in collection.values():
                    if record.get("user_id") == user_id:
                        record["user_id"] = None
                        record["note"] = "[deleted by data request]"
                    if record.get("reviewer_id") == user_id:
                        record["reviewer_id"] = None
            for handoff in data["handoffs"]:
                if handoff.get("from_id") == user_id:
                    handoff["from_id"] = None
                if handoff.get("to_id") == user_id:
                    handoff["to_id"] = None
                if handoff.get("from_id") is None:
                    handoff["note"] = "[deleted by data request]"
            for key, value in data.items():
                await conf.set_raw(key, value=value)

    @commands.hybrid_group(name="staffops", aliases=["staff"], invoke_without_command=True)
    @commands.guild_only()
    async def staffops(self, ctx: commands.Context) -> None:
        """Coordinate staff coverage and availability."""
        await ctx.send_help()

    @staffops.command(name="staffrole")
    @commands.admin_or_permissions(manage_guild=True)
    async def staff_role(self, ctx: commands.Context, role: discord.Role | None = None) -> None:
        """Set the role whose members may use staff workflows."""
        await self.config.guild(ctx.guild).staff_role_id.set(role.id if role else None)
        await ctx.send(f"Staff role set to {role.mention}." if role else "Staff role cleared.")

    @staffops.command(name="logchannel")
    @commands.admin_or_permissions(manage_guild=True)
    async def log_channel(self, ctx: commands.Context, channel: discord.TextChannel | None = None) -> None:
        """Set the private staff operations log channel."""
        await self.config.guild(ctx.guild).log_channel_id.set(channel.id if channel else None)
        await ctx.send(f"Staff logs will be sent to {channel.mention}." if channel else "Staff logging disabled.")

    @staffops.command(name="clockin")
    async def clock_in(self, ctx: commands.Context, *, note: str = "") -> None:
        """Start a staff shift."""
        await self._require_staff(ctx.author)
        conf = self.config.guild(ctx.guild)
        active = await conf.active_shifts()
        key = str(ctx.author.id)
        if key in active:
            raise commands.BadArgument("You already have an active shift.")
        active[key] = {"started_at": self._now(), "note": note[:500], "channel_id": ctx.channel.id}
        await conf.active_shifts.set(active)
        await self._log(ctx.guild, "Shift started", f"{ctx.author.mention} clocked in.\n{note}".strip())
        await ctx.send(f"{ctx.author.mention} clocked in at <t:{active[key]['started_at']}:t>.")

    @staffops.command(name="clockout")
    async def clock_out(self, ctx: commands.Context, *, note: str = "") -> None:
        """End your active shift and optionally leave a closing note."""
        await self._require_staff(ctx.author)
        conf = self.config.guild(ctx.guild)
        active = await conf.active_shifts()
        key = str(ctx.author.id)
        current = active.pop(key, None)
        if not current:
            raise commands.BadArgument("You do not have an active shift.")
        ended = self._now()
        shift_id = await conf.next_shift_id()
        record = {
            "shift_id": shift_id,
            "user_id": ctx.author.id,
            "started_at": current["started_at"],
            "ended_at": ended,
            "seconds": max(0, ended - current["started_at"]),
            "note": current.get("note", ""),
            "closing_note": note[:500],
        }
        async with conf.shifts() as shifts:
            shifts[str(shift_id)] = record
        await conf.next_shift_id.set(shift_id + 1)
        await conf.active_shifts.set(active)
        await self._log(
            ctx.guild,
            "Shift ended",
            f"{ctx.author.mention} clocked out after **{self._duration(record['seconds'])}**.\n{note}".strip(),
        )
        await ctx.send(f"Clocked out. Shift length: **{self._duration(record['seconds'])}**.")

    @staffops.command(name="active")
    async def active(self, ctx: commands.Context) -> None:
        """Show currently active staff shifts."""
        conf = self.config.guild(ctx.guild)
        active = await conf.active_shifts()
        maximum = int(await conf.max_shift_hours()) * 3600
        now = self._now()
        lines = [
            f"• {'⚠️ ' if now - record['started_at'] > maximum else ''}<@{user_id}> — "
            f"since <t:{record['started_at']}:R>{' · ' + record['note'] if record.get('note') else ''}"
            for user_id, record in active.items()
        ]
        await ctx.send(
            embed=discord.Embed(title="Active Staff", description="\n".join(lines) or "No active shifts.", color=self.COLOR)
        )

    @staffops.command(name="availability")
    async def availability(self, ctx: commands.Context, *, availability: str) -> None:
        """Set your normal availability in plain language."""
        await self._require_staff(ctx.author)
        clean = " ".join(availability.split())[:500]
        async with self.config.guild(ctx.guild).availability() as records:
            records[str(ctx.author.id)] = {"text": clean, "updated_at": self._now()}
        await ctx.send("Availability updated.")

    @staffops.command(name="roster")
    async def roster(self, ctx: commands.Context) -> None:
        """Show staff availability and current on-call order."""
        conf = self.config.guild(ctx.guild)
        availability = await conf.availability()
        on_call = await conf.on_call()
        available_lines = [f"• <@{user_id}> — {record['text']}" for user_id, record in availability.items()]
        rota_lines = [f"{index}. <@{record['user_id']}>" for index, record in enumerate(on_call, start=1)]
        embed = discord.Embed(title="Staff Roster", color=self.COLOR)
        embed.add_field(name="Availability", value="\n".join(available_lines)[:1024] or "Not provided", inline=False)
        embed.add_field(name="On-call rotation", value="\n".join(rota_lines)[:1024] or "Not configured", inline=False)
        await ctx.send(embed=embed)

    @staffops.command(name="leave")
    async def request_leave(self, ctx: commands.Context, until: str, *, reason: str = "") -> None:
        """Request leave. The until value is kept as the staff member entered it."""
        await self._require_staff(ctx.author)
        conf = self.config.guild(ctx.guild)
        leave_id = await conf.next_leave_id()
        record = {
            "leave_id": leave_id,
            "user_id": ctx.author.id,
            "until": until[:100],
            "reason": reason[:500],
            "status": "pending",
            "created_at": self._now(),
            "reviewer_id": None,
            "reviewed_at": None,
        }
        async with conf.leave_requests() as requests:
            requests[str(leave_id)] = record
        await conf.next_leave_id.set(leave_id + 1)
        await self._log(
            ctx.guild, f"Leave request #{leave_id}", f"{ctx.author.mention} requested leave until **{until}**.\n{reason}".strip()
        )
        await ctx.send(f"Leave request **#{leave_id}** submitted.")

    @staffops.command(name="reviewleave")
    @commands.admin_or_permissions(manage_guild=True)
    async def review_leave(self, ctx: commands.Context, leave_id: int, decision: str, *, note: str = "") -> None:
        """Approve or deny a pending leave request."""
        decision = decision.casefold()
        if decision not in {"approve", "approved", "deny", "denied"}:
            raise commands.BadArgument("Decision must be approve or deny.")
        status = "approved" if decision.startswith("approv") else "denied"
        async with self.config.guild(ctx.guild).leave_requests() as requests:
            record = requests.get(str(leave_id))
            if not record:
                raise commands.BadArgument("That leave request does not exist.")
            record.update(status=status, reviewer_id=ctx.author.id, reviewed_at=self._now(), review_note=note[:500])
        await self._log(ctx.guild, f"Leave request #{leave_id} {status}", f"Reviewed by {ctx.author.mention}.\n{note}".strip())
        await ctx.send(f"Leave request **#{leave_id}** {status}.")

    @staffops.group(name="oncall", invoke_without_command=True)
    async def on_call(self, ctx: commands.Context) -> None:
        """Manage the ordered on-call rotation."""
        rota = await self.config.guild(ctx.guild).on_call()
        lines = [f"{index}. <@{item['user_id']}>" for index, item in enumerate(rota, start=1)]
        await ctx.send("\n".join(lines) or "The on-call rotation is empty.")

    @on_call.command(name="add")
    @commands.admin_or_permissions(manage_guild=True)
    async def on_call_add(self, ctx: commands.Context, member: discord.Member) -> None:
        """Add a member to the end of the rotation."""
        async with self.config.guild(ctx.guild).on_call() as rota:
            if member.id not in {item["user_id"] for item in rota}:
                rota.append({"user_id": member.id, "added_at": self._now()})
        await ctx.send(f"Added {member.mention} to the on-call rotation.")

    @on_call.command(name="remove")
    @commands.admin_or_permissions(manage_guild=True)
    async def on_call_remove(self, ctx: commands.Context, member: discord.Member) -> None:
        """Remove a member from the rotation."""
        async with self.config.guild(ctx.guild).on_call() as rota:
            rota[:] = [item for item in rota if item["user_id"] != member.id]
        await ctx.send(f"Removed {member.mention} from the on-call rotation.")

    @on_call.command(name="rotate")
    @commands.admin_or_permissions(manage_guild=True)
    async def on_call_rotate(self, ctx: commands.Context) -> None:
        """Move the current on-call member to the end."""
        async with self.config.guild(ctx.guild).on_call() as rota:
            if not rota:
                raise commands.BadArgument("The on-call rotation is empty.")
            rota.append(rota.pop(0))
            current_id = rota[0]["user_id"]
        await self._log(ctx.guild, "On-call rotation advanced", f"<@{current_id}> is now first on call.")
        await ctx.send(f"<@{current_id}> is now first on call.")

    @staffops.command(name="handoff")
    async def handoff(self, ctx: commands.Context, member: discord.Member | None = None, *, note: str) -> None:
        """Leave a timestamped handoff note, optionally for another staff member."""
        await self._require_staff(ctx.author)
        record = {
            "from_id": ctx.author.id,
            "to_id": member.id if member else None,
            "note": note[:1000],
            "created_at": self._now(),
        }
        async with self.config.guild(ctx.guild).handoffs() as handoffs:
            handoffs.append(record)
            del handoffs[:-100]
        target = member.mention if member else "the team"
        await self._log(ctx.guild, "Staff handoff", f"{ctx.author.mention} → {target}\n{record['note']}")
        await ctx.send(f"Handoff recorded for {target}.")

    @staffops.command(name="report")
    @commands.admin_or_permissions(manage_guild=True)
    async def report(self, ctx: commands.Context, days: commands.Range[int, 1, 365] = 30) -> None:
        """Show shift totals for the previous number of days."""
        cutoff = self._now() - int(days) * 86400
        shifts = await self.config.guild(ctx.guild).shifts()
        totals: dict[int, int] = {}
        for record in shifts.values():
            if record.get("ended_at", 0) >= cutoff and record.get("user_id"):
                totals[record["user_id"]] = totals.get(record["user_id"], 0) + int(record.get("seconds", 0))
        ranking = sorted(totals.items(), key=lambda item: item[1], reverse=True)
        lines = [f"• <@{user_id}> — **{self._duration(seconds)}**" for user_id, seconds in ranking]
        await ctx.send(
            embed=discord.Embed(
                title=f"Staff hours · {days} days", description="\n".join(lines) or "No completed shifts.", color=self.COLOR
            )
        )

    @staffops.command(name="export")
    @commands.admin_or_permissions(manage_guild=True)
    async def export(self, ctx: commands.Context) -> None:
        """Export completed shifts as CSV."""
        shifts = await self.config.guild(ctx.guild).shifts()
        output = io.StringIO()
        fields = ["shift_id", "user_id", "started_at", "ended_at", "seconds", "note", "closing_note"]
        writer = csv.DictWriter(output, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(shifts.values())
        await ctx.send(file=discord.File(io.BytesIO(output.getvalue().encode()), filename="staffops-shifts.csv"))

    @staticmethod
    def _duration(seconds: int) -> str:
        hours, remainder = divmod(max(0, int(seconds)), 3600)
        minutes = remainder // 60
        return f"{hours}h {minutes}m"
