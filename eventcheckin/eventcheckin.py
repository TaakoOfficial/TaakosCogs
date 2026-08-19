"""Persistent event registration, waitlists, check-ins, and attendance."""

from __future__ import annotations

import asyncio
import csv
import io
import time
from contextlib import suppress
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING, Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import discord
from discord.ext import tasks
from redbot.core import Config, commands

from .calendar_utils import build_calendar
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
    SCHEMA_VERSION = 2

    def __init__(self, bot: Red) -> None:
        self.bot = bot
        self.config = Config.get_conf(self, identifier=self.CONFIG_IDENTIFIER, force_registration=True)
        self.config.register_guild(
            schema_version=self.SCHEMA_VERSION,
            next_event_id=1,
            reminder_minutes=60,
            checkin_early_minutes=120,
            checkin_late_minutes=720,
            log_channel_id=None,
            timezone="UTC",
            templates={},
            events={},
        )
        self._locks: dict[int, asyncio.Lock] = {}

    def _lock(self, guild_id: int) -> asyncio.Lock:
        if not hasattr(self, "_locks"):
            self._locks = {}
        return self._locks.setdefault(guild_id, asyncio.Lock())

    async def cog_load(self) -> None:
        for guild_id in await self.config.all_guilds():
            conf = self.config.guild_from_id(guild_id)
            events = await conf.events()
            changed = False
            for event in events.values():
                defaults = {
                    "duration_minutes": 60,
                    "scheduled_event_id": None,
                    "recurrence_group": None,
                    "source_type": "manual",
                    "source_id": None,
                    "cancel_reason": "",
                }
                for key, value in defaults.items():
                    if key not in event:
                        event[key] = value
                        changed = True
            if changed:
                await conf.events.set(events)
            await conf.schema_version.set(self.SCHEMA_VERSION)
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

    async def _audit(self, guild: discord.Guild, action: str, status: str, detail: str = "") -> None:
        operations = self.bot.get_cog("OperationsCenter")
        if operations and hasattr(operations, "record_audit"):
            await operations.record_audit(guild, "EventCheckin", action, status, detail)

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
        embed.add_field(name="Duration", value=f"{int(event.get('duration_minutes') or 60)} minutes")
        embed.add_field(name="Capacity", value=capacity)
        embed.add_field(name="RSVPs", value=f"{counts['going']} going\n{counts['waitlist']} waiting")
        embed.add_field(name="Status", value=event["status"].title())
        if event.get("location"):
            embed.add_field(name="Location", value=event["location"], inline=False)
        if event.get("source_type") and event["source_type"] != "manual":
            source = event["source_type"].replace("_", " ").title()
            value = f"{source} #{event['source_id']}" if event.get("source_id") else source
            embed.add_field(name="Created from", value=value, inline=False)
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

    async def create_draft_service(
        self,
        guild: discord.Guild,
        *,
        actor_id: int,
        starts_at: int,
        capacity: int,
        title: str,
        description: str = "",
        duration_minutes: int = 60,
        source_type: str = "manual",
        source_id: int | None = None,
    ) -> dict[str, Any]:
        """Create a draft for commands and optional TaakosCogs integrations."""
        if starts_at <= self._now():
            raise commands.BadArgument("The event start timestamp must be in the future.")
        if not 0 <= capacity <= 10000:
            raise commands.BadArgument("Capacity must be between 0 and 10,000.")
        if not 1 <= duration_minutes <= 10080:
            raise commands.BadArgument("Duration must be between 1 and 10,080 minutes.")
        conf = self.config.guild(guild)
        async with self._lock(getattr(guild, "id", 0)):
            event_id = int(await conf.next_event_id())
            now = self._now()
            event = {
                "event_id": event_id,
                "title": title[:200],
                "description": description[:2000],
                "location": "",
                "starts_at": starts_at,
                "duration_minutes": duration_minutes,
                "capacity": capacity,
                "status": "draft",
                "created_by": actor_id,
                "created_at": now,
                "updated_at": now,
                "channel_id": None,
                "message_id": None,
                "reminder_sent_at": None,
                "finalized_at": None,
                "finalized_by": None,
                "reward_role_id": None,
                "scheduled_event_id": None,
                "recurrence_group": None,
                "source_type": source_type[:50],
                "source_id": source_id,
                "attendees": {},
            }
            events = await conf.events()
            events[str(event_id)] = event
            await conf.events.set(events)
            await conf.next_event_id.set(event_id + 1)
        return event

    @commands.hybrid_group(name="eventcheckin", aliases=["checkinevent"], invoke_without_command=True)
    @commands.guild_only()
    async def event_checkin(self, ctx: commands.Context) -> None:
        """Create event panels and manage attendance."""
        await ctx.send_help()

    @event_checkin.command(name="setup")
    @commands.admin_or_permissions(manage_events=True)
    async def setup_command(
        self,
        ctx: commands.Context,
        channel: discord.TextChannel | None = None,
        timezone_name: str = "UTC",
    ) -> None:
        """Configure the attendance log channel and calendar timezone."""
        destination = channel or ctx.channel
        if not isinstance(destination, discord.TextChannel):
            raise commands.BadArgument("Choose a text channel for attendance logs.")
        try:
            ZoneInfo(timezone_name)
        except ZoneInfoNotFoundError as error:
            raise commands.BadArgument("Unknown IANA timezone name.") from error
        permissions = destination.permissions_for(ctx.guild.me)
        if not permissions.send_messages or not permissions.embed_links:
            raise commands.BadArgument("I need Send Messages and Embed Links in that channel.")
        conf = self.config.guild(ctx.guild)
        await conf.log_channel_id.set(destination.id)
        await conf.timezone.set(timezone_name)
        await ctx.send(f"EventCheckin logs use {destination.mention}; calendar timezone is `{timezone_name}`.")

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
        event = await self.create_draft_service(
            ctx.guild,
            actor_id=ctx.author.id,
            starts_at=starts_at,
            capacity=int(capacity),
            title=title,
            description=description,
        )
        event_id = event["event_id"]
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

    @event_checkin.command(name="duration")
    @commands.admin_or_permissions(manage_events=True)
    async def duration(self, ctx: commands.Context, event_id: int, minutes: commands.Range[int, 1, 10080]) -> None:
        """Set an event duration in minutes."""
        events, event = await self._event(ctx.guild, event_id)
        event["duration_minutes"] = int(minutes)
        await self._save(ctx.guild, events, event)
        await self._refresh(ctx.guild, event)
        await ctx.send(f"Event duration set to {minutes} minutes.")

    @event_checkin.command(name="timezone")
    @commands.admin_or_permissions(manage_events=True)
    async def timezone(self, ctx: commands.Context, *, timezone_name: str) -> None:
        """Set the guild calendar timezone, such as America/Chicago."""
        try:
            ZoneInfo(timezone_name)
        except ZoneInfoNotFoundError as error:
            raise commands.BadArgument("Unknown IANA timezone name.") from error
        await self.config.guild(ctx.guild).timezone.set(timezone_name)
        await ctx.send(f"Event calendar timezone set to `{timezone_name}`.")

    @event_checkin.command(name="repeat")
    @commands.admin_or_permissions(manage_events=True)
    async def repeat(
        self, ctx: commands.Context, event_id: int, interval_days: commands.Range[int, 1, 365], count: commands.Range[int, 1, 52]
    ) -> None:
        """Create recurring draft copies of an event."""
        _events, source = await self._event(ctx.guild, event_id)
        conf = self.config.guild(ctx.guild)
        async with self._lock(ctx.guild.id):
            next_id = int(await conf.next_event_id())
            group = source.get("recurrence_group") or f"{ctx.guild.id}:{event_id}:{self._now()}"
            created: list[int] = []
            events = await conf.events()
            source["recurrence_group"] = group
            events[str(event_id)] = source
            for occurrence in range(1, int(count) + 1):
                clone = {
                    **source,
                    "event_id": next_id,
                    "starts_at": int(source["starts_at"]) + int(interval_days) * 86400 * occurrence,
                    "status": "draft",
                    "created_by": ctx.author.id,
                    "created_at": self._now(),
                    "updated_at": self._now(),
                    "channel_id": None,
                    "message_id": None,
                    "scheduled_event_id": None,
                    "reminder_sent_at": None,
                    "finalized_at": None,
                    "finalized_by": None,
                    "attendees": {},
                    "recurrence_group": group,
                }
                events[str(next_id)] = clone
                created.append(next_id)
                next_id += 1
            await conf.events.set(events)
            await conf.next_event_id.set(next_id)
        await ctx.send(f"Created {len(created)} recurring drafts: {', '.join(f'#{item}' for item in created)}.")

    @event_checkin.group(name="template", invoke_without_command=True)
    @commands.admin_or_permissions(manage_events=True)
    async def template(self, ctx: commands.Context) -> None:
        """Manage reusable event templates."""
        templates = await self.config.guild(ctx.guild).templates()
        await ctx.send(", ".join(f"`{name}`" for name in sorted(templates)) or "No event templates are configured.")

    @template.command(name="save")
    async def template_save(self, ctx: commands.Context, event_id: int, name: str) -> None:
        """Save an event's reusable fields as a named template."""
        _events, event = await self._event(ctx.guild, event_id)
        key = name.casefold()[:50]
        if not key:
            raise commands.BadArgument("A template name is required.")
        async with self.config.guild(ctx.guild).templates() as templates:
            if key not in templates and len(templates) >= 25:
                raise commands.BadArgument("A guild can retain at most 25 event templates.")
            templates[key] = {
                "title": event["title"],
                "description": event.get("description", ""),
                "location": event.get("location", ""),
                "duration_minutes": int(event.get("duration_minutes") or 60),
                "capacity": int(event.get("capacity") or 0),
                "reward_role_id": event.get("reward_role_id"),
            }
        await ctx.send(f"Saved event template `{key}`.")

    @template.command(name="remove")
    async def template_remove(self, ctx: commands.Context, name: str) -> None:
        """Remove a named event template."""
        async with self.config.guild(ctx.guild).templates() as templates:
            removed = templates.pop(name.casefold(), None)
        await ctx.send("Template removed." if removed else "Template not found.")

    @template.command(name="use")
    async def template_use(self, ctx: commands.Context, name: str, starts_at: int) -> None:
        """Create a draft from a named template."""
        template = (await self.config.guild(ctx.guild).templates()).get(name.casefold())
        if not template:
            raise commands.BadArgument("Template not found.")
        event = await self.create_draft_service(
            ctx.guild,
            actor_id=ctx.author.id,
            starts_at=starts_at,
            capacity=int(template["capacity"]),
            title=template["title"],
            description=template["description"],
            duration_minutes=int(template["duration_minutes"]),
            source_type="template",
        )
        events, stored = await self._event(ctx.guild, event["event_id"])
        stored["location"] = template.get("location", "")
        stored["reward_role_id"] = template.get("reward_role_id")
        await self._save(ctx.guild, events, stored)
        await ctx.send(f"Created EventCheckin draft **#{event['event_id']}** from `{name.casefold()}`.")

    @event_checkin.command(name="calendar")
    async def calendar(self, ctx: commands.Context, status: str = "all") -> None:
        """Export retained events as an iCalendar (.ics) file."""
        allowed = {"all", "draft", "open", "finalized", "cancelled"}
        status = status.casefold()
        if status not in allowed:
            raise commands.BadArgument(f"Status must be one of: {', '.join(sorted(allowed))}.")
        events = (await self.config.guild(ctx.guild).events()).values()
        selected = list(events) if status == "all" else [event for event in events if event.get("status") == status]
        payload = build_calendar(ctx.guild.id, ctx.guild.name, selected, self._now()).encode("utf-8")
        await ctx.send(file=discord.File(io.BytesIO(payload), filename=f"{ctx.guild.id}-events.ics"))

    @event_checkin.command(name="discordevent")
    @commands.admin_or_permissions(manage_events=True)
    @commands.bot_has_permissions(manage_events=True)
    async def discord_event(self, ctx: commands.Context, event_id: int) -> None:
        """Create a native Discord scheduled event from an EventCheckin event."""
        events, event = await self._event(ctx.guild, event_id)
        if event.get("scheduled_event_id"):
            raise commands.BadArgument("This event already has a stored Discord scheduled-event ID.")
        if not event.get("location"):
            raise commands.BadArgument("Set a location before creating an external scheduled event.")
        start = datetime.fromtimestamp(int(event["starts_at"]), timezone.utc)
        end = start + timedelta(minutes=max(1, int(event.get("duration_minutes") or 60)))
        create_options: dict[str, Any] = {}
        if event.get("description"):
            create_options["description"] = event["description"]
        scheduled = await ctx.guild.create_scheduled_event(
            name=event["title"],
            start_time=start,
            end_time=end,
            entity_type=discord.EntityType.external,
            privacy_level=discord.PrivacyLevel.guild_only,
            location=event["location"],
            reason=f"EventCheckin event #{event_id} created by {ctx.author}",
            **create_options,
        )
        event["scheduled_event_id"] = scheduled.id
        await self._save(ctx.guild, events, event)
        await ctx.send(f"Created Discord scheduled event **{scheduled.name}** (`{scheduled.id}`).")

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
        notified = 0
        for record in list(event.get("attendees", {}).values())[:100]:
            member = ctx.guild.get_member(record.get("user_id"))
            if member:
                with suppress(discord.Forbidden, discord.HTTPException):
                    await member.send(
                        f"**{event['title']}** in **{ctx.guild.name}** was cancelled."
                        + (f"\nReason: {reason[:500]}" if reason else "")
                    )
                    notified += 1
        channel = ctx.guild.get_channel(event.get("channel_id"))
        if isinstance(channel, discord.TextChannel):
            with suppress(discord.HTTPException):
                await channel.send(
                    f"**{event['title']}** was cancelled." + (f"\nReason: {reason[:500]}" if reason else ""),
                    allowed_mentions=discord.AllowedMentions.none(),
                )
        await self._audit(ctx.guild, "event cancellation", "completed", f"Event #{event_id}; {notified} DM(s)")
        await ctx.send(f"Event **#{event_id}** cancelled; notified **{notified}** reachable attendee(s).")

    @event_checkin.command(name="list")
    async def list_events(self, ctx: commands.Context, status: str = "open") -> None:
        """List events by status, or use all."""
        events = await self.config.guild(ctx.guild).events()
        timezone_name = await self.config.guild(ctx.guild).timezone()
        timezone = ZoneInfo(timezone_name)
        rows = [event for event in events.values() if status == "all" or event.get("status") == status]
        rows.sort(key=lambda event: event["starts_at"])
        lines = [
            f"• **#{event['event_id']} {event['title']}** · {event['status']} · <t:{event['starts_at']}:R> · "
            f"{datetime.fromtimestamp(event['starts_at'], timezone):%Y-%m-%d %H:%M %Z}"
            for event in rows[:25]
        ]
        await ctx.send(
            embed=discord.Embed(title=f"Events · {timezone_name}", description="\n".join(lines) or "No events.", color=self.COLOR)
        )

    @event_checkin.command(name="series")
    async def series(self, ctx: commands.Context, event_id: int) -> None:
        """List every retained event in an event's recurrence series."""
        events, source = await self._event(ctx.guild, event_id)
        group = source.get("recurrence_group")
        selected = [item for item in events.values() if group and item.get("recurrence_group") == group]
        if not group:
            selected = [source]
        selected.sort(key=lambda item: item["starts_at"])
        lines = [f"`#{item['event_id']}` {item['status']} · <t:{item['starts_at']}:F>" for item in selected[:52]]
        await ctx.send(embed=discord.Embed(title=source["title"], description="\n".join(lines), color=self.COLOR))

    @event_checkin.command(name="seriescancel")
    @commands.admin_or_permissions(manage_events=True)
    async def series_cancel(self, ctx: commands.Context, event_id: int, *, reason: str = "") -> None:
        """Cancel future draft/open occurrences in a recurrence series."""
        events, source = await self._event(ctx.guild, event_id)
        group = source.get("recurrence_group")
        if not group:
            raise commands.BadArgument("That event is not part of a recurrence series.")
        now = self._now()
        selected = [
            item
            for item in events.values()
            if item.get("recurrence_group") == group
            and item.get("status") in {"draft", "open"}
            and int(item.get("starts_at", 0)) >= now
        ]
        for item in selected:
            item.update(status="cancelled", cancel_reason=reason[:500], finalized_at=now, finalized_by=ctx.author.id)
            events[str(item["event_id"])] = item
        await self.config.guild(ctx.guild).events.set(events)
        for item in selected:
            await self._refresh(ctx.guild, item)
        await ctx.send(f"Cancelled **{len(selected)}** future occurrence(s).")

    @event_checkin.command(name="stats")
    @commands.admin_or_permissions(manage_events=True)
    async def stats(self, ctx: commands.Context, days: commands.Range[int, 1, 3650] = 90) -> None:
        """Show aggregate attendance for events started within the selected period."""
        cutoff = self._now() - int(days) * 86400
        events = [
            item
            for item in (await self.config.guild(ctx.guild).events()).values()
            if int(item.get("starts_at", 0)) >= cutoff and item.get("status") in {"finalized", "completed"}
        ]
        registrations = checked = no_shows = 0
        for item in events:
            counts = self._counts(item)
            registrations += len(item.get("attendees", {}))
            checked += counts["checked_in"]
            no_shows += counts["no_show"]
        rate = checked / registrations * 100 if registrations else 0
        embed = discord.Embed(title=f"Attendance · last {int(days)} days", color=self.COLOR)
        embed.add_field(name="Events", value=str(len(events)))
        embed.add_field(name="Registrations", value=str(registrations))
        embed.add_field(name="Checked in", value=f"{checked} ({rate:.1f}%)")
        embed.add_field(name="No-shows", value=str(no_shows))
        await ctx.send(embed=embed)

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
