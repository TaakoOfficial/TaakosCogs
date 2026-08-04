"""Persistent event registration, waitlists, check-ins, and attendance."""

from __future__ import annotations

import csv
import io
import time
from contextlib import suppress
from typing import TYPE_CHECKING, Any

import discord
from discord.ext import tasks
from redbot.core import Config, commands

from .dashboard_integration import DashboardIntegration

if TYPE_CHECKING:
    from redbot.core.bot import Red


class EventControls(discord.ui.View):
    """Persistent controls shared by all EventCheckin panels."""

    def __init__(self, cog: EventCheckin) -> None:
        super().__init__(timeout=None)
        self.cog = cog

    @discord.ui.button(label="RSVP", emoji="✅", style=discord.ButtonStyle.success, custom_id="eventcheckin:rsvp")
    async def rsvp(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        await self.cog.handle_button(interaction, "rsvp")

    @discord.ui.button(label="Withdraw", emoji="↩️", style=discord.ButtonStyle.secondary, custom_id="eventcheckin:withdraw")
    async def withdraw(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        await self.cog.handle_button(interaction, "withdraw")

    @discord.ui.button(label="Check in", emoji="📍", style=discord.ButtonStyle.primary, custom_id="eventcheckin:checkin")
    async def checkin(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        await self.cog.handle_button(interaction, "checkin")


class EventCheckin(DashboardIntegration, commands.Cog):
    """Know who intended to attend, who arrived, and who missed out."""

    CONFIG_IDENTIFIER = 2026080310
    COLOR = 0x5865F2

    def __init__(self, bot: Red) -> None:
        self.bot = bot
        self.config = Config.get_conf(self, identifier=self.CONFIG_IDENTIFIER, force_registration=True)
        self.config.register_guild(
            next_event_id=1,
            reminder_minutes=60,
            checkin_early_minutes=120,
            checkin_late_minutes=720,
            log_channel_id=None,
            events={},
        )

    async def cog_load(self) -> None:
        self.bot.add_view(EventControls(self))
        self.event_loop.start()

    def cog_unload(self) -> None:
        self.event_loop.cancel()

    @staticmethod
    def _now() -> int:
        return int(time.time())

    async def _event(self, guild: discord.Guild, event_id: int) -> tuple[dict[str, Any], dict[str, Any]]:
        events = await self.config.guild(guild).events()
        event = events.get(str(event_id))
        if not event:
            raise commands.BadArgument("Event not found.")
        return events, event

    async def _event_for_message(
        self, guild: discord.Guild, message_id: int
    ) -> tuple[dict[str, Any], dict[str, Any]] | tuple[None, None]:
        events = await self.config.guild(guild).events()
        event = next((item for item in events.values() if item.get("message_id") == message_id), None)
        return (events, event) if event else (None, None)

    async def _save(self, guild: discord.Guild, events: dict[str, Any], event: dict[str, Any]) -> None:
        event["updated_at"] = self._now()
        events[str(event["event_id"])] = event
        await self.config.guild(guild).events.set(events)

    @staticmethod
    def _counts(event: dict[str, Any]) -> dict[str, int]:
        counts = {"going": 0, "waitlist": 0, "checked_in": 0, "no_show": 0}
        for record in event.get("attendees", {}).values():
            status = record.get("status")
            if status in counts:
                counts[status] += 1
            if record.get("checked_in_at"):
                counts["checked_in"] += status != "checked_in"
        return counts

    def _embed(self, event: dict[str, Any]) -> discord.Embed:
        counts = self._counts(event)
        capacity = "Unlimited" if not event["capacity"] else str(event["capacity"])
        embed = discord.Embed(
            title=event["title"],
            description=event.get("description") or "Use the buttons below to register and check in.",
            color=self.COLOR if event["status"] == "open" else 0x95A5A6,
        )
        embed.add_field(name="Starts", value=f"<t:{event['starts_at']}:F>\n<t:{event['starts_at']}:R>")
        embed.add_field(name="Capacity", value=capacity)
        embed.add_field(name="RSVPs", value=f"{counts['going']} going\n{counts['waitlist']} waiting")
        embed.add_field(name="Status", value=event["status"].title())
        if event.get("location"):
            embed.add_field(name="Location", value=event["location"], inline=False)
        embed.set_footer(text=f"Event #{event['event_id']} · {counts['checked_in']} checked in")
        return embed

    async def _refresh(self, guild: discord.Guild, event: dict[str, Any]) -> None:
        channel = guild.get_channel(event.get("channel_id"))
        if not isinstance(channel, discord.TextChannel) or not event.get("message_id"):
            return
        try:
            message = await channel.fetch_message(event["message_id"])
            await message.edit(embed=self._embed(event), view=EventControls(self) if event["status"] == "open" else None)
        except (discord.NotFound, discord.Forbidden, discord.HTTPException):
            pass

    async def _log(self, guild: discord.Guild, text: str) -> None:
        channel_id = await self.config.guild(guild).log_channel_id()
        channel = guild.get_channel(channel_id) if channel_id else None
        if isinstance(channel, discord.TextChannel):
            with suppress(discord.HTTPException):
                await channel.send(embed=discord.Embed(description=text, color=self.COLOR, timestamp=discord.utils.utcnow()))

    def _promote(self, event: dict[str, Any]) -> int | None:
        capacity = int(event.get("capacity") or 0)
        attendees = event.setdefault("attendees", {})
        going = sum(record.get("status") in {"going", "checked_in"} for record in attendees.values())
        if capacity and going >= capacity:
            return None
        waiting = sorted(
            (record for record in attendees.values() if record.get("status") == "waitlist"),
            key=lambda record: record.get("registered_at", 0),
        )
        if not waiting:
            return None
        waiting[0]["status"] = "going"
        waiting[0]["promoted_at"] = self._now()
        return waiting[0]["user_id"]

    async def handle_button(self, interaction: discord.Interaction, action: str) -> None:
        if not interaction.guild or not interaction.message or not isinstance(interaction.user, discord.Member):
            await interaction.response.send_message("This event control only works in a server.", ephemeral=True)
            return
        events, event = await self._event_for_message(interaction.guild, interaction.message.id)
        if not event or events is None:
            await interaction.response.send_message("This event is no longer tracked.", ephemeral=True)
            return
        if event["status"] != "open":
            await interaction.response.send_message("Registration for this event is closed.", ephemeral=True)
            return
        attendees = event.setdefault("attendees", {})
        key = str(interaction.user.id)
        current = attendees.get(key)
        response = ""
        promoted_id = None
        if action == "rsvp":
            if current and current.get("status") == "checked_in":
                await interaction.response.send_message("You are already checked in.", ephemeral=True)
                return
            going = sum(record.get("status") in {"going", "checked_in"} for record in attendees.values())
            capacity = int(event.get("capacity") or 0)
            status = (
                "waitlist" if capacity and going >= capacity and (not current or current.get("status") != "going") else "going"
            )
            attendees[key] = {
                "user_id": interaction.user.id,
                "status": status,
                "registered_at": current.get("registered_at", self._now()) if current else self._now(),
                "checked_in_at": current.get("checked_in_at") if current else None,
                "promoted_at": current.get("promoted_at") if current else None,
                "staff_actor_id": None,
            }
            response = "You are registered." if status == "going" else "The event is full; you joined the waitlist."
        elif action == "withdraw":
            if not current or current.get("status") not in {"going", "waitlist"}:
                response = "You do not have an active RSVP."
            else:
                was_going = current.get("status") == "going"
                current["status"] = "withdrawn"
                current["withdrawn_at"] = self._now()
                promoted_id = self._promote(event) if was_going else None
                response = "Your RSVP was withdrawn."
        else:
            early = event["starts_at"] - int(await self.config.guild(interaction.guild).checkin_early_minutes()) * 60
            late = event["starts_at"] + int(await self.config.guild(interaction.guild).checkin_late_minutes()) * 60
            if not current or current.get("status") != "going":
                response = "You must have a confirmed RSVP before checking in."
            elif not early <= self._now() <= late:
                response = f"Check-in is available from <t:{early}:F> through <t:{late}:F>."
            else:
                current["checked_in_at"] = self._now()
                current["status"] = "checked_in"
                response = "You are checked in."
        await self._save(interaction.guild, events, event)
        await interaction.response.send_message(
            response + (f" <@{promoted_id}> was promoted from the waitlist." if promoted_id else ""), ephemeral=True
        )
        await self._refresh(interaction.guild, event)

    async def red_delete_data_for_user(self, *, requester: str, user_id: int) -> None:
        for guild_id in await self.config.all_guilds():
            conf = self.config.guild_from_id(guild_id)
            events = await conf.events()
            changed = False
            for event in events.values():
                if event.get("created_by") == user_id:
                    event["created_by"] = None
                    changed = True
                if event.get("finalized_by") == user_id:
                    event["finalized_by"] = None
                    changed = True
                if event.get("attendees", {}).pop(str(user_id), None):
                    self._promote(event)
                    changed = True
                for attendee in event.get("attendees", {}).values():
                    if attendee.get("staff_actor_id") == user_id:
                        attendee["staff_actor_id"] = None
                        changed = True
            if changed:
                await conf.events.set(events)

    @tasks.loop(minutes=5)
    async def event_loop(self) -> None:
        now = self._now()
        for guild in self.bot.guilds:
            conf = self.config.guild(guild)
            events = await conf.events()
            changed = False
            reminder_minutes = int(await conf.reminder_minutes())
            for event in events.values():
                if event["status"] != "open" or event.get("reminder_sent_at"):
                    continue
                if now >= event["starts_at"] - reminder_minutes * 60:
                    channel = guild.get_channel(event.get("channel_id"))
                    going_ids = [
                        record["user_id"] for record in event.get("attendees", {}).values() if record.get("status") == "going"
                    ]
                    if isinstance(channel, discord.TextChannel):
                        mentions = " ".join(f"<@{user_id}>" for user_id in going_ids[:50])
                        with suppress(discord.HTTPException):
                            await channel.send(
                                (
                                    f"{mentions}\n**{event['title']}** starts "
                                    f"<t:{event['starts_at']}:R>. Check in from the event panel."
                                ).strip()
                            )
                    event["reminder_sent_at"] = now
                    changed = True
            if changed:
                await conf.events.set(events)

    @event_loop.before_loop
    async def before_event_loop(self) -> None:
        await self.bot.wait_until_red_ready()

    @commands.hybrid_group(name="eventcheckin", aliases=["checkinevent"], invoke_without_command=True)
    @commands.guild_only()
    async def event_checkin(self, ctx: commands.Context) -> None:
        """Create event panels and manage attendance."""
        await ctx.send_help()

    @event_checkin.command(name="create")
    @commands.admin_or_permissions(manage_events=True)
    async def create(
        self,
        ctx: commands.Context,
        starts_at: int,
        capacity: commands.Range[int, 0, 10000],
        title: str,
        *,
        description: str = "",
    ) -> None:
        """Create an event using a Unix timestamp and capacity (0 = unlimited)."""
        if starts_at <= self._now():
            raise commands.BadArgument("The event start timestamp must be in the future.")
        conf = self.config.guild(ctx.guild)
        event_id = await conf.next_event_id()
        now = self._now()
        event = {
            "event_id": event_id,
            "title": title[:200],
            "description": description[:2000],
            "location": "",
            "starts_at": starts_at,
            "capacity": int(capacity),
            "status": "draft",
            "created_by": ctx.author.id,
            "created_at": now,
            "updated_at": now,
            "channel_id": None,
            "message_id": None,
            "reminder_sent_at": None,
            "finalized_at": None,
            "finalized_by": None,
            "reward_role_id": None,
            "attendees": {},
        }
        async with conf.events() as events:
            events[str(event_id)] = event
        await conf.next_event_id.set(event_id + 1)
        await ctx.send(
            f"Created draft event **#{event_id} {event['title']}** for <t:{starts_at}:F>. "
            f"Use `{ctx.clean_prefix}eventcheckin post {event_id}`."
        )

    @event_checkin.command(name="post")
    @commands.admin_or_permissions(manage_events=True)
    async def post(self, ctx: commands.Context, event_id: int, channel: discord.TextChannel | None = None) -> None:
        """Post or move an event registration panel."""
        destination = channel or ctx.channel
        if not isinstance(destination, discord.TextChannel):
            raise commands.BadArgument("Choose a text channel.")
        events, event = await self._event(ctx.guild, event_id)
        event["status"] = "open"
        message = await destination.send(embed=self._embed(event), view=EventControls(self))
        event["channel_id"] = destination.id
        event["message_id"] = message.id
        await self._save(ctx.guild, events, event)
        await ctx.send(f"Event panel posted: {message.jump_url}")

    @event_checkin.command(name="location")
    @commands.admin_or_permissions(manage_events=True)
    async def location(self, ctx: commands.Context, event_id: int, *, location: str) -> None:
        """Set an event location or joining instruction."""
        events, event = await self._event(ctx.guild, event_id)
        event["location"] = location[:500]
        await self._save(ctx.guild, events, event)
        await self._refresh(ctx.guild, event)
        await ctx.send("Event location updated.")

    @event_checkin.command(name="rewardrole")
    @commands.admin_or_permissions(manage_roles=True)
    async def reward_role(self, ctx: commands.Context, event_id: int, role: discord.Role | None = None) -> None:
        """Set a role awarded to checked-in attendees when finalized."""
        if role and (role.managed or role >= ctx.guild.me.top_role):
            raise commands.BadArgument("Choose a role the bot can manage.")
        events, event = await self._event(ctx.guild, event_id)
        event["reward_role_id"] = role.id if role else None
        await self._save(ctx.guild, events, event)
        await ctx.send(f"Reward role set to {role.mention}." if role else "Reward role cleared.")

    @event_checkin.command(name="checkin")
    @commands.admin_or_permissions(manage_events=True)
    async def staff_checkin(self, ctx: commands.Context, event_id: int, member: discord.Member) -> None:
        """Check in an attendee manually."""
        events, event = await self._event(ctx.guild, event_id)
        record = event.setdefault("attendees", {}).setdefault(
            str(member.id),
            {"user_id": member.id, "registered_at": self._now(), "promoted_at": None},
        )
        record.update(status="checked_in", checked_in_at=self._now(), staff_actor_id=ctx.author.id)
        await self._save(ctx.guild, events, event)
        await self._refresh(ctx.guild, event)
        await ctx.send(f"Checked in {member.mention}.")

    @event_checkin.command(name="attendees")
    async def attendees(self, ctx: commands.Context, event_id: int, status: str = "going") -> None:
        """List attendees in a registration state."""
        _events, event = await self._event(ctx.guild, event_id)
        rows = [record for record in event.get("attendees", {}).values() if status == "all" or record.get("status") == status]
        rows.sort(key=lambda record: record.get("registered_at", 0))
        lines = [f"• <@{record['user_id']}> · {record['status']}" for record in rows[:50]]
        await ctx.send(
            embed=discord.Embed(
                title=f"{event['title']} · {status}", description="\n".join(lines) or "No attendees.", color=self.COLOR
            )
        )

    @event_checkin.command(name="finalize")
    @commands.admin_or_permissions(manage_events=True)
    async def finalize(self, ctx: commands.Context, event_id: int) -> None:
        """Close registration, mark unarrived RSVPs as no-shows, and award a role."""
        events, event = await self._event(ctx.guild, event_id)
        checked = no_shows = rewards = errors = 0
        role = ctx.guild.get_role(event.get("reward_role_id")) if event.get("reward_role_id") else None
        for record in event.get("attendees", {}).values():
            if record.get("checked_in_at"):
                record["status"] = "checked_in"
                checked += 1
                member = ctx.guild.get_member(record["user_id"])
                if member and role and role not in member.roles:
                    try:
                        await member.add_roles(role, reason=f"EventCheckin event #{event_id} attendance")
                        rewards += 1
                    except discord.HTTPException:
                        errors += 1
            elif record.get("status") == "going":
                record["status"] = "no_show"
                no_shows += 1
        event.update(status="finalized", finalized_at=self._now(), finalized_by=ctx.author.id)
        await self._save(ctx.guild, events, event)
        await self._refresh(ctx.guild, event)
        await self._log(
            ctx.guild,
            f"Event **#{event_id} {event['title']}** finalized: {checked} checked in, "
            f"{no_shows} no-show(s), {rewards} reward(s), {errors} error(s).",
        )
        await ctx.send(
            f"Finalized: **{checked}** checked in, **{no_shows}** no-show(s), "
            f"**{rewards}** reward role(s), **{errors}** error(s)."
        )

    @event_checkin.command(name="cancel")
    @commands.admin_or_permissions(manage_events=True)
    async def cancel(self, ctx: commands.Context, event_id: int, *, reason: str = "") -> None:
        """Cancel an event without deleting its attendance record."""
        events, event = await self._event(ctx.guild, event_id)
        event.update(status="cancelled", cancel_reason=reason[:500], finalized_at=self._now(), finalized_by=ctx.author.id)
        await self._save(ctx.guild, events, event)
        await self._refresh(ctx.guild, event)
        await ctx.send(f"Event **#{event_id}** cancelled.")

    @event_checkin.command(name="list")
    async def list_events(self, ctx: commands.Context, status: str = "open") -> None:
        """List events by status, or use all."""
        events = await self.config.guild(ctx.guild).events()
        rows = [event for event in events.values() if status == "all" or event.get("status") == status]
        rows.sort(key=lambda event: event["starts_at"])
        lines = [
            f"• **#{event['event_id']} {event['title']}** · {event['status']} · <t:{event['starts_at']}:R>" for event in rows[:25]
        ]
        await ctx.send(embed=discord.Embed(title="Events", description="\n".join(lines) or "No events.", color=self.COLOR))

    @event_checkin.command(name="export")
    @commands.admin_or_permissions(manage_events=True)
    async def export(self, ctx: commands.Context, event_id: int) -> None:
        """Export event registration and attendance as CSV."""
        _events, event = await self._event(ctx.guild, event_id)
        output = io.StringIO()
        fields = [
            "event_id",
            "event_title",
            "user_id",
            "status",
            "registered_at",
            "promoted_at",
            "checked_in_at",
            "withdrawn_at",
            "staff_actor_id",
        ]
        writer = csv.DictWriter(output, fieldnames=fields)
        writer.writeheader()
        for record in event.get("attendees", {}).values():
            writer.writerow({"event_id": event_id, "event_title": event["title"], **{key: record.get(key) for key in fields[2:]}})
        await ctx.send(file=discord.File(io.BytesIO(output.getvalue().encode()), filename=f"event-{event_id}-attendance.csv"))
