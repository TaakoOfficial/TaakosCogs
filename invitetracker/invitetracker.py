"""Invite tracking cog for Red-DiscordBot."""

from __future__ import annotations

import asyncio
import csv
import io
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

import discord
from redbot.core import Config, commands
from redbot.core.bot import Red
from redbot.core.utils.chat_formatting import box, pagify

log = logging.getLogger("red.taakoscogs.invitetracker")


InviteCache = Dict[str, Dict[str, Any]]
MemberRecord = Dict[str, Any]
StatsRecord = Dict[str, int]


class InviteTracker(commands.Cog):
    """Track Discord invite usage, joins, leaves, fake joins, and leaderboards."""

    DEFAULT_COLOR = 0x5865F2
    JOIN_COLOR = 0x3BA55D
    LEAVE_COLOR = 0xED4245
    FAKE_COLOR = 0xFEE75C

    def __init__(self, bot: Red) -> None:
        self.bot = bot
        self.config = Config.get_conf(self, identifier=2026051302, force_registration=True)
        self.config.register_guild(
            enabled=False,
            log_channel_id=None,
            include_bots=False,
            fake_age_hours=24,
            invite_cache={},
            inviters={},
            members={},
            unknown_joins=0,
        )
        self._locks: Dict[int, asyncio.Lock] = {}
        self._startup_task = asyncio.create_task(self._refresh_enabled_guilds())

    async def cog_unload(self) -> None:
        """Cancel startup work when the cog unloads."""
        if self._startup_task and not self._startup_task.done():
            self._startup_task.cancel()

    async def red_delete_data_for_user(self, *, requester: str, user_id: int) -> None:
        """Delete stored invite records and stats for a Discord user ID."""
        user_key = str(user_id)
        all_guilds = await self.config.all_guilds()
        for guild_id in all_guilds:
            guild_conf = self.config.guild_from_id(guild_id)
            async with guild_conf.inviters() as inviters:
                inviters.pop(user_key, None)

            async with guild_conf.members() as members:
                members.pop(user_key, None)
                for record in members.values():
                    if str(record.get("inviter_id")) == user_key:
                        record["inviter_id"] = None

            async with guild_conf.invite_cache() as invite_cache:
                for record in invite_cache.values():
                    if str(record.get("inviter_id")) == user_key:
                        record["inviter_id"] = None

    def _guild_lock(self, guild_id: int) -> asyncio.Lock:
        return self._locks.setdefault(guild_id, asyncio.Lock())

    async def _refresh_enabled_guilds(self) -> None:
        await self.bot.wait_until_ready()
        all_guilds = await self.config.all_guilds()
        for guild_id, settings in all_guilds.items():
            if not settings.get("enabled"):
                continue
            guild = self.bot.get_guild(guild_id)
            if guild is None:
                continue
            try:
                await self._refresh_invite_cache(guild)
            except Exception:
                log.exception("Failed to refresh invite cache for guild %s", guild_id)

    @staticmethod
    def _now() -> datetime:
        return datetime.now(timezone.utc)

    @classmethod
    def _now_ts(cls) -> float:
        return cls._now().timestamp()

    @staticmethod
    def _count(value: int) -> str:
        return f"{value:,}"

    @staticmethod
    def _format_ts(value: Any, style: str = "F") -> str:
        if value in (None, ""):
            return "Unknown"
        try:
            timestamp = int(float(value))
        except (TypeError, ValueError):
            return "Unknown"
        return f"<t:{timestamp}:{style}>"

    @staticmethod
    def _user_ref(user_id: Any) -> str:
        if user_id in (None, ""):
            return "Unknown"
        try:
            return f"<@{int(user_id)}>"
        except (TypeError, ValueError):
            return "Unknown"

    @staticmethod
    def _invite_url(code: Optional[str]) -> str:
        if not code:
            return "Unknown"
        return f"https://discord.gg/{code}"

    @staticmethod
    def _net_joins(stats: Dict[str, Any]) -> int:
        joins = int(stats.get("joins", 0))
        leaves = int(stats.get("leaves", 0))
        fake = int(stats.get("fake", 0))
        return max(joins - leaves - fake, 0)

    @classmethod
    def _stats_line(cls, stats: Dict[str, Any]) -> str:
        joins = int(stats.get("joins", 0))
        leaves = int(stats.get("leaves", 0))
        fake = int(stats.get("fake", 0))
        net = cls._net_joins(stats)
        return (
            f"Total joins: **{cls._count(joins)}**\n"
            f"Left: **{cls._count(leaves)}**\n"
            f"Fake joins: **{cls._count(fake)}**\n"
            f"Net valid joins: **{cls._count(net)}**"
        )

    @staticmethod
    def _invite_to_record(invite: discord.Invite) -> Dict[str, Any]:
        channel = invite.channel
        inviter = invite.inviter
        created_at = invite.created_at
        return {
            "code": invite.code,
            "uses": int(invite.uses or 0),
            "inviter_id": inviter.id if inviter else None,
            "channel_id": channel.id if channel else None,
            "created_at": created_at.timestamp() if created_at else None,
            "max_age": invite.max_age,
            "max_uses": invite.max_uses,
            "temporary": bool(invite.temporary),
        }

    @staticmethod
    def _find_used_invite(
        before_cache: InviteCache,
        after_cache: InviteCache,
    ) -> Tuple[Optional[str], Optional[Dict[str, Any]]]:
        candidates: List[Tuple[int, int, str, Dict[str, Any]]] = []

        for code, after_record in after_cache.items():
            before_record = before_cache.get(code, {})
            before_uses = int(before_record.get("uses") or 0)
            after_uses = int(after_record.get("uses") or 0)
            if after_uses > before_uses:
                candidates.append((after_uses - before_uses, before_uses, code, after_record))

        if not candidates:
            return None, None

        candidates.sort(key=lambda item: (item[0], int(item[3].get("uses") or 0)), reverse=True)
        _delta, before_uses, code, record = candidates[0]
        # Consume one observed use so burst joins can be attributed across member join events.
        record["uses"] = before_uses + 1
        return code, record

    async def _fetch_invite_cache(self, guild: discord.Guild) -> InviteCache:
        try:
            invites = await guild.invites()
        except discord.Forbidden as exc:
            raise commands.CommandError(
                "I cannot read server invites. Give the bot `Manage Server` permission, "
                "then run `[p]invitetracker refresh`."
            ) from exc
        except discord.HTTPException as exc:
            raise commands.CommandError("Discord did not return the server invite list.") from exc

        return {invite.code: self._invite_to_record(invite) for invite in invites}

    async def _refresh_invite_cache(self, guild: discord.Guild) -> InviteCache:
        async with self._guild_lock(guild.id):
            invite_cache = await self._fetch_invite_cache(guild)
            await self.config.guild(guild).invite_cache.set(invite_cache)
            return invite_cache

    @classmethod
    def _is_fake_join(cls, member: discord.Member, fake_age_hours: int) -> bool:
        if fake_age_hours <= 0:
            return False
        account_age_seconds = cls._now_ts() - member.created_at.timestamp()
        return account_age_seconds < fake_age_hours * 3600

    @staticmethod
    def _empty_stats() -> StatsRecord:
        return {"joins": 0, "leaves": 0, "fake": 0}

    @classmethod
    def _ensure_stats(cls, inviters: Dict[str, StatsRecord], inviter_id: Any) -> StatsRecord:
        key = str(inviter_id)
        stats = inviters.setdefault(key, cls._empty_stats())
        stats.setdefault("joins", 0)
        stats.setdefault("leaves", 0)
        stats.setdefault("fake", 0)
        return stats

    async def _increment_unknown_joins(self, guild: discord.Guild) -> None:
        current = await self.config.guild(guild).unknown_joins()
        await self.config.guild(guild).unknown_joins.set(int(current or 0) + 1)

    async def _send_log(self, guild: discord.Guild, embed: discord.Embed) -> None:
        channel_id = await self.config.guild(guild).log_channel_id()
        if not channel_id:
            return

        channel = guild.get_channel(int(channel_id))
        if not isinstance(channel, discord.TextChannel):
            return

        me = guild.me
        if me is None:
            return
        permissions = channel.permissions_for(me)
        if not permissions.send_messages or not permissions.embed_links:
            return

        try:
            await channel.send(embed=embed, allowed_mentions=discord.AllowedMentions.none())
        except discord.HTTPException:
            log.exception("Failed to send InviteTracker log in guild %s", guild.id)

    def _join_embed(
        self,
        member: discord.Member,
        invite_code: Optional[str],
        invite_record: Optional[Dict[str, Any]],
        is_fake: bool,
    ) -> discord.Embed:
        color = self.FAKE_COLOR if is_fake else self.JOIN_COLOR
        embed = discord.Embed(
            title="Member Joined",
            description=f"{member.mention} joined the server.",
            color=color,
            timestamp=self._now(),
        )
        embed.set_thumbnail(url=member.display_avatar.url)

        inviter_id = invite_record.get("inviter_id") if invite_record else None
        invite_text = "Unknown"
        if invite_code:
            invite_text = f"`{invite_code}`\n{self._invite_url(invite_code)}"
        embed.add_field(name="Invite", value=invite_text, inline=True)
        embed.add_field(name="Inviter", value=self._user_ref(inviter_id), inline=True)
        embed.add_field(
            name="Account Created",
            value=self._format_ts(member.created_at.timestamp(), "R"),
            inline=True,
        )

        if invite_record:
            channel_id = invite_record.get("channel_id")
            channel_text = f"<#{channel_id}>" if channel_id else "Unknown"
            uses = int(invite_record.get("uses") or 0)
            embed.add_field(name="Invite Channel", value=channel_text, inline=True)
            embed.add_field(name="Invite Uses", value=self._count(uses), inline=True)

        embed.add_field(name="Fake Join", value="Yes" if is_fake else "No", inline=True)
        embed.set_footer(text=f"User ID: {member.id}")
        return embed

    def _leave_embed(self, member: discord.Member, record: MemberRecord) -> discord.Embed:
        embed = discord.Embed(
            title="Member Left",
            description=f"{member} left the server.",
            color=self.LEAVE_COLOR,
            timestamp=self._now(),
        )
        embed.set_thumbnail(url=member.display_avatar.url)
        embed.add_field(name="Invited By", value=self._user_ref(record.get("inviter_id")), inline=True)

        invite_code = record.get("invite_code")
        invite_text = "Unknown"
        if invite_code:
            invite_text = f"`{invite_code}`\n{self._invite_url(invite_code)}"
        embed.add_field(name="Invite", value=invite_text, inline=True)
        embed.add_field(name="Joined", value=self._format_ts(record.get("joined_at"), "R"), inline=True)
        embed.add_field(name="Fake Join", value="Yes" if record.get("fake") else "No", inline=True)
        embed.set_footer(text=f"User ID: {member.id}")
        return embed

    async def _record_join(self, member: discord.Member) -> None:
        guild = member.guild
        settings = await self.config.guild(guild).all()
        if not settings.get("enabled"):
            return
        if member.bot and not settings.get("include_bots"):
            return

        invite_code: Optional[str] = None
        invite_record: Optional[Dict[str, Any]] = None

        async with self._guild_lock(guild.id):
            before_cache = await self.config.guild(guild).invite_cache()
            try:
                after_cache = await self._fetch_invite_cache(guild)
            except commands.CommandError:
                await self._increment_unknown_joins(guild)
                log.warning("Invite lookup failed for member join in guild %s", guild.id)
            else:
                invite_code, invite_record = self._find_used_invite(before_cache, after_cache)
                await self.config.guild(guild).invite_cache.set(after_cache)
                if invite_record is None:
                    await self._increment_unknown_joins(guild)

        fake_age_hours = int(settings.get("fake_age_hours") or 0)
        is_fake = self._is_fake_join(member, fake_age_hours)
        inviter_id = invite_record.get("inviter_id") if invite_record else None

        member_record: MemberRecord = {
            "member_id": member.id,
            "inviter_id": inviter_id,
            "invite_code": invite_code,
            "joined_at": self._now_ts(),
            "left_at": None,
            "fake": is_fake,
        }

        async with self.config.guild(guild).members() as members:
            members[str(member.id)] = member_record

        if inviter_id:
            async with self.config.guild(guild).inviters() as inviters:
                stats = self._ensure_stats(inviters, inviter_id)
                stats["joins"] += 1
                if is_fake:
                    stats["fake"] += 1

        await self._send_log(guild, self._join_embed(member, invite_code, invite_record, is_fake))

    async def _record_leave(self, member: discord.Member) -> None:
        guild = member.guild
        settings = await self.config.guild(guild).all()
        if not settings.get("enabled"):
            return
        if member.bot and not settings.get("include_bots"):
            return

        member_key = str(member.id)
        record: Optional[MemberRecord] = None
        async with self.config.guild(guild).members() as members:
            raw_record = members.get(member_key)
            if raw_record:
                raw_record["left_at"] = self._now_ts()
                record = dict(raw_record)

        if not record:
            return

        inviter_id = record.get("inviter_id")
        if inviter_id:
            async with self.config.guild(guild).inviters() as inviters:
                stats = self._ensure_stats(inviters, inviter_id)
                stats["leaves"] += 1

        await self._send_log(guild, self._leave_embed(member, record))

    @commands.Cog.listener()
    async def on_invite_create(self, invite: discord.Invite) -> None:
        guild = invite.guild
        if guild is None:
            return
        if not await self.config.guild(guild).enabled():
            return

        async with self._guild_lock(guild.id):
            async with self.config.guild(guild).invite_cache() as invite_cache:
                invite_cache[invite.code] = self._invite_to_record(invite)

    @commands.Cog.listener()
    async def on_invite_delete(self, invite: discord.Invite) -> None:
        guild = invite.guild
        if guild is None:
            return
        if not await self.config.guild(guild).enabled():
            return

        async with self._guild_lock(guild.id):
            async with self.config.guild(guild).invite_cache() as invite_cache:
                invite_cache.pop(invite.code, None)

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member) -> None:
        try:
            await self._record_join(member)
        except Exception:
            log.exception("Failed to record invite join for guild %s", member.guild.id)

    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member) -> None:
        try:
            await self._record_leave(member)
        except Exception:
            log.exception("Failed to record invite leave for guild %s", member.guild.id)

    async def _send_settings(self, ctx: commands.Context) -> None:
        assert ctx.guild is not None
        settings = await self.config.guild(ctx.guild).all()
        channel_id = settings.get("log_channel_id")
        channel_text = f"<#{channel_id}>" if channel_id else "Not set"
        invite_cache = settings.get("invite_cache") or {}
        inviters = settings.get("inviters") or {}
        members = settings.get("members") or {}

        total_joins = sum(int(stats.get("joins", 0)) for stats in inviters.values())
        total_leaves = sum(int(stats.get("leaves", 0)) for stats in inviters.values())
        total_fake = sum(int(stats.get("fake", 0)) for stats in inviters.values())
        active_tracked = sum(1 for record in members.values() if not record.get("left_at"))

        embed = discord.Embed(
            title="InviteTracker Settings",
            color=self.DEFAULT_COLOR,
            timestamp=self._now(),
        )
        prefix = ctx.clean_prefix
        setup_command = f"{prefix}invitetracker setup #join-logs"
        embed.add_field(
            name="Status",
            value=(
                f"Enabled: **{'Yes' if settings.get('enabled') else 'No'}**\n"
                f"Log channel: {channel_text}\n"
                f"Include bots: **{'Yes' if settings.get('include_bots') else 'No'}**\n"
                f"Fake threshold: **{int(settings.get('fake_age_hours') or 0)} hour(s)**"
            ),
            inline=False,
        )
        if not settings.get("enabled") or not channel_id:
            embed.add_field(
                name="Start Here",
                value=(
                    f"1. Create or choose a join log channel.\n"
                    f"2. Run `{setup_command}`.\n"
                    f"3. Make sure I have `Manage Server` so I can read invites.\n"
                    f"4. Enable Server Members intent for reliable join/leave tracking."
                ),
                inline=False,
            )
        else:
            embed.add_field(
                name="Useful Commands",
                value=(
                    f"`{prefix}invites top 10` - show the leaderboard\n"
                    f"`{prefix}invites @member` - show someone's invite stats\n"
                    f"`{prefix}invites source @member` - show how a member joined\n"
                    f"`{prefix}invitetracker refresh` - recache current invites"
                ),
                inline=False,
            )
        embed.add_field(
            name="Tracked Data",
            value=(
                f"Cached invites: **{self._count(len(invite_cache))}**\n"
                f"Inviters: **{self._count(len(inviters))}**\n"
                f"Active tracked members: **{self._count(active_tracked)}**"
            ),
            inline=True,
        )
        embed.add_field(
            name="Totals",
            value=(
                f"Joins: **{self._count(total_joins)}**\n"
                f"Leaves: **{self._count(total_leaves)}**\n"
                f"Fake joins: **{self._count(total_fake)}**\n"
                f"Unknown joins: **{self._count(int(settings.get('unknown_joins') or 0))}**"
            ),
            inline=True,
        )
        embed.add_field(
            name="How It Works",
            value=(
                "Discord does not tell bots the exact invite used on join. "
                "InviteTracker compares invite use counts before and after a member joins."
            ),
            inline=False,
        )
        await ctx.send(embed=embed)

    @commands.group(name="invitetracker", invoke_without_command=True)
    @commands.guild_only()
    @commands.bot_has_permissions(embed_links=True)
    async def invitetracker(self, ctx: commands.Context) -> None:
        """Configure invite tracking for this server."""
        await self._send_settings(ctx)

    @invitetracker.command(name="setup")
    @commands.admin_or_permissions(manage_guild=True)
    async def invitetracker_setup(
        self,
        ctx: commands.Context,
        channel: Optional[discord.TextChannel] = None,
    ) -> None:
        """Enable invite tracking, set a log channel, and cache current invites."""
        assert ctx.guild is not None
        if channel is None:
            if not isinstance(ctx.channel, discord.TextChannel):
                await ctx.send("Run this in a text channel or provide a channel.")
                return
            channel = ctx.channel

        try:
            invite_cache = await self._refresh_invite_cache(ctx.guild)
        except commands.CommandError as error:
            await ctx.send(str(error))
            return

        await self.config.guild(ctx.guild).log_channel_id.set(channel.id)
        await self.config.guild(ctx.guild).enabled.set(True)
        await ctx.send(
            f"InviteTracker is enabled. Logs will post in {channel.mention}. "
            f"Cached **{self._count(len(invite_cache))}** invite(s)."
        )

    @invitetracker.command(name="enable")
    @commands.admin_or_permissions(manage_guild=True)
    async def invitetracker_enable(self, ctx: commands.Context, enabled: bool = True) -> None:
        """Enable or disable invite tracking."""
        assert ctx.guild is not None
        if enabled:
            try:
                await self._refresh_invite_cache(ctx.guild)
            except commands.CommandError as error:
                await ctx.send(str(error))
                return
        await self.config.guild(ctx.guild).enabled.set(enabled)
        await ctx.send(f"Invite tracking is now {'enabled' if enabled else 'disabled'}.")

    @invitetracker.command(name="disable")
    @commands.admin_or_permissions(manage_guild=True)
    async def invitetracker_disable(self, ctx: commands.Context) -> None:
        """Disable invite tracking."""
        assert ctx.guild is not None
        await self.config.guild(ctx.guild).enabled.set(False)
        await ctx.send("Invite tracking is now disabled.")

    @invitetracker.command(name="channel")
    @commands.admin_or_permissions(manage_guild=True)
    async def invitetracker_channel(
        self,
        ctx: commands.Context,
        channel: Optional[discord.TextChannel] = None,
    ) -> None:
        """Set the invite log channel. Omit the channel to use the current channel."""
        assert ctx.guild is not None
        if channel is None:
            if not isinstance(ctx.channel, discord.TextChannel):
                await ctx.send("Run this in a text channel or provide a channel.")
                return
            channel = ctx.channel
        await self.config.guild(ctx.guild).log_channel_id.set(channel.id)
        await ctx.send(f"Invite logs will post in {channel.mention}.")

    @invitetracker.command(name="clearchannel")
    @commands.admin_or_permissions(manage_guild=True)
    async def invitetracker_clear_channel(self, ctx: commands.Context) -> None:
        """Clear the invite log channel."""
        assert ctx.guild is not None
        await self.config.guild(ctx.guild).log_channel_id.set(None)
        await ctx.send("Invite log channel cleared.")

    @invitetracker.command(name="fakeage")
    @commands.admin_or_permissions(manage_guild=True)
    async def invitetracker_fake_age(self, ctx: commands.Context, hours: int) -> None:
        """Set the account-age threshold for fake joins in hours. Use 0 to disable."""
        assert ctx.guild is not None
        if hours < 0:
            await ctx.send("Fake join age must be 0 or greater.")
            return
        await self.config.guild(ctx.guild).fake_age_hours.set(min(hours, 8760))
        await ctx.send(f"Fake join threshold set to **{min(hours, 8760)}** hour(s).")

    @invitetracker.command(name="includebots")
    @commands.admin_or_permissions(manage_guild=True)
    async def invitetracker_include_bots(self, ctx: commands.Context, include_bots: bool) -> None:
        """Choose whether bot joins should be tracked."""
        assert ctx.guild is not None
        await self.config.guild(ctx.guild).include_bots.set(include_bots)
        await ctx.send(f"Bot joins are now {'tracked' if include_bots else 'ignored'}.")

    @invitetracker.command(name="refresh")
    @commands.admin_or_permissions(manage_guild=True)
    async def invitetracker_refresh(self, ctx: commands.Context) -> None:
        """Refresh the cached invite list from Discord."""
        assert ctx.guild is not None
        try:
            invite_cache = await self._refresh_invite_cache(ctx.guild)
        except commands.CommandError as error:
            await ctx.send(str(error))
            return
        await ctx.send(f"Invite cache refreshed. Cached **{self._count(len(invite_cache))}** invite(s).")

    @invitetracker.command(name="resetstats")
    @commands.admin_or_permissions(manage_guild=True)
    async def invitetracker_reset_stats(self, ctx: commands.Context, confirmation: str = "") -> None:
        """Reset all InviteTracker stats. Use `confirm` to proceed."""
        assert ctx.guild is not None
        if confirmation.lower() != "confirm":
            await ctx.send("This clears all invite stats for this server. Run the command again with `confirm`.")
            return

        await self.config.guild(ctx.guild).inviters.set({})
        await self.config.guild(ctx.guild).members.set({})
        await self.config.guild(ctx.guild).unknown_joins.set(0)
        try:
            await self._refresh_invite_cache(ctx.guild)
        except commands.CommandError as error:
            await ctx.send(f"Stats were reset, but the invite cache could not be refreshed: {error}")
            return
        await ctx.send("InviteTracker stats have been reset.")

    @invitetracker.command(name="settings")
    @commands.bot_has_permissions(embed_links=True)
    async def invitetracker_settings(self, ctx: commands.Context) -> None:
        """Show current InviteTracker settings."""
        await self._send_settings(ctx)

    @commands.group(name="invites", aliases=["inv"], invoke_without_command=True)
    @commands.guild_only()
    @commands.bot_has_permissions(embed_links=True)
    async def invites(
        self,
        ctx: commands.Context,
        member: Optional[discord.Member] = None,
    ) -> None:
        """Show invite stats for yourself or another member."""
        assert ctx.guild is not None
        member = member or ctx.author
        inviters = await self.config.guild(ctx.guild).inviters()
        stats = inviters.get(str(member.id), self._empty_stats())

        embed = discord.Embed(
            title=f"Invite Stats: {member.display_name}",
            description=member.mention,
            color=member.color if member.color.value else self.DEFAULT_COLOR,
            timestamp=self._now(),
        )
        embed.set_thumbnail(url=member.display_avatar.url)
        embed.add_field(name="Stats", value=self._stats_line(stats), inline=False)

        members = await self.config.guild(ctx.guild).members()
        active = sum(
            1
            for record in members.values()
            if str(record.get("inviter_id")) == str(member.id) and not record.get("left_at")
        )
        embed.add_field(name="Currently Tracked Members", value=self._count(active), inline=True)
        embed.set_footer(text=f"User ID: {member.id}")
        await ctx.send(embed=embed)

    @invites.command(name="top", aliases=["leaderboard", "lb"])
    @commands.guild_only()
    @commands.bot_has_permissions(embed_links=True)
    async def invites_top(self, ctx: commands.Context, limit: int = 10) -> None:
        """Show the invite leaderboard."""
        assert ctx.guild is not None
        limit = max(1, min(limit, 25))
        inviters = await self.config.guild(ctx.guild).inviters()
        if not inviters:
            await ctx.send("No invite stats have been tracked yet.")
            return

        ranked = sorted(
            inviters.items(),
            key=lambda item: (
                self._net_joins(item[1]),
                int(item[1].get("joins", 0)),
                -int(item[1].get("leaves", 0)),
            ),
            reverse=True,
        )
        lines = []
        for index, (user_id, stats) in enumerate(ranked[:limit], start=1):
            lines.append(
                f"**{index}.** {self._user_ref(user_id)} - "
                f"**{self._count(self._net_joins(stats))}** net "
                f"({self._count(int(stats.get('joins', 0)))} joins, "
                f"{self._count(int(stats.get('leaves', 0)))} left, "
                f"{self._count(int(stats.get('fake', 0)))} fake)"
            )

        embed = discord.Embed(
            title="Invite Leaderboard",
            description="\n".join(lines),
            color=self.DEFAULT_COLOR,
            timestamp=self._now(),
        )
        await ctx.send(embed=embed)

    @invites.command(name="source", aliases=["joined"])
    @commands.guild_only()
    @commands.bot_has_permissions(embed_links=True)
    async def invites_source(self, ctx: commands.Context, member: discord.Member) -> None:
        """Show which invite a member joined with."""
        assert ctx.guild is not None
        members = await self.config.guild(ctx.guild).members()
        record = members.get(str(member.id))
        if not record:
            await ctx.send("I do not have a tracked invite source for that member.")
            return

        invite_code = record.get("invite_code")
        invite_text = "Unknown"
        if invite_code:
            invite_text = f"`{invite_code}`\n{self._invite_url(invite_code)}"

        embed = discord.Embed(
            title=f"Invite Source: {member.display_name}",
            description=member.mention,
            color=member.color if member.color.value else self.DEFAULT_COLOR,
            timestamp=self._now(),
        )
        embed.set_thumbnail(url=member.display_avatar.url)
        embed.add_field(name="Invited By", value=self._user_ref(record.get("inviter_id")), inline=True)
        embed.add_field(name="Invite", value=invite_text, inline=True)
        embed.add_field(name="Joined", value=self._format_ts(record.get("joined_at"), "F"), inline=True)
        embed.add_field(name="Left", value=self._format_ts(record.get("left_at"), "R"), inline=True)
        embed.add_field(name="Fake Join", value="Yes" if record.get("fake") else "No", inline=True)
        embed.set_footer(text=f"User ID: {member.id}")
        await ctx.send(embed=embed)

    @invites.command(name="joinedby")
    @commands.guild_only()
    async def invites_joined_by(
        self,
        ctx: commands.Context,
        inviter: discord.Member,
        limit: int = 20,
    ) -> None:
        """List tracked current members invited by a member."""
        assert ctx.guild is not None
        limit = max(1, min(limit, 50))
        members = await self.config.guild(ctx.guild).members()
        records = [
            record
            for record in members.values()
            if str(record.get("inviter_id")) == str(inviter.id) and not record.get("left_at")
        ]
        records.sort(key=lambda record: float(record.get("joined_at") or 0), reverse=True)
        if not records:
            await ctx.send(f"No currently tracked members were invited by {inviter.mention}.")
            return

        lines = []
        for record in records[:limit]:
            member_id = record.get("member_id")
            invite_code = record.get("invite_code") or "unknown"
            fake_text = " fake" if record.get("fake") else ""
            lines.append(
                f"{self._user_ref(member_id)} - `{invite_code}` - "
                f"{self._format_ts(record.get('joined_at'), 'R')}{fake_text}"
            )

        header = f"Current tracked members invited by {inviter} ({len(records)} total):"
        pages = list(pagify("\n".join(lines), page_length=1800))
        for page in pages:
            await ctx.send(box(f"{header}\n\n{page}"))

    @invites.command(name="export")
    @commands.guild_only()
    @commands.admin_or_permissions(manage_guild=True)
    @commands.bot_has_permissions(attach_files=True)
    async def invites_export(self, ctx: commands.Context) -> None:
        """Export tracked invite member records as CSV."""
        assert ctx.guild is not None
        members = await self.config.guild(ctx.guild).members()
        if not members:
            await ctx.send("No invite member records have been tracked yet.")
            return

        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["member_id", "inviter_id", "invite_code", "joined_at", "left_at", "fake"])
        for record in members.values():
            writer.writerow(
                [
                    record.get("member_id"),
                    record.get("inviter_id"),
                    record.get("invite_code"),
                    self._format_export_time(record.get("joined_at")),
                    self._format_export_time(record.get("left_at")),
                    "yes" if record.get("fake") else "no",
                ]
            )

        data = output.getvalue().encode("utf-8")
        file = discord.File(io.BytesIO(data), filename=f"invites-{ctx.guild.id}.csv")
        await ctx.send("Invite member records export:", file=file)

    @staticmethod
    def _format_export_time(value: Any) -> str:
        if value in (None, ""):
            return ""
        try:
            return datetime.fromtimestamp(float(value), tz=timezone.utc).isoformat()
        except (TypeError, ValueError, OSError):
            return ""
