"""Reputation board cog for Red-DiscordBot."""

from __future__ import annotations

import asyncio
import csv
import io
import logging
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any

import discord
from redbot.core import Config, commands
from redbot.core.utils.chat_formatting import box, pagify

if TYPE_CHECKING:
    from redbot.core.bot import Red

log = logging.getLogger("red.taakoscogs.repboard")


RepRecord = dict[str, Any]
StatsRecord = dict[str, Any]


class RepBoard(commands.Cog):
    """Community reputation, kudos, public rep boards, and leaderboards."""

    CONFIG_IDENTIFIER = 2026051501
    DEFAULT_COLOR = 0x5865F2
    REP_COLOR = 0x57F287
    REMOVED_COLOR = 0xED4245
    PROFILE_COLOR = 0xFEE75C
    MAX_REASON_LENGTH = 500

    def __init__(self, bot: Red) -> None:
        self.bot = bot
        self.config = Config.get_conf(
            self,
            identifier=self.CONFIG_IDENTIFIER,
            force_registration=True,
        )
        self.config.register_guild(
            enabled=False,
            board_channel_id=None,
            log_channel_id=None,
            allow_bots=False,
            allow_self_rep=False,
            require_reason=False,
            cooldown_seconds=3600,
            daily_limit=5,
            min_reason_length=0,
            max_reason_length=self.MAX_REASON_LENGTH,
            next_rep_id=1,
            records={},
            stats={},
        )
        self._locks: dict[int, asyncio.Lock] = {}

    async def red_delete_data_for_user(self, *, requester: str, user_id: int) -> None:
        """Remove stored reputation references for a Discord user ID."""
        user_key = str(user_id)
        all_guilds = await self.config.all_guilds()
        for guild_id in all_guilds:
            guild_conf = self.config.guild_from_id(guild_id)
            stats = await guild_conf.stats()
            records = await guild_conf.records()
            stats.pop(user_key, None)
            for record in records.values():
                touched = False
                giver_id = record.get("giver_id")
                receiver_id = record.get("receiver_id")
                was_active = bool(record.get("active", True))
                if str(giver_id) == user_key:
                    record["giver_id"] = None
                    record["giver_removed"] = True
                    touched = True
                if str(receiver_id) == user_key:
                    record["receiver_id"] = None
                    record["receiver_removed"] = True
                    touched = True
                if str(record.get("removed_by")) == user_key:
                    record["removed_by"] = None
                if touched:
                    if was_active and giver_id and str(giver_id) != user_key:
                        giver_stats = self._ensure_stats(stats, giver_id)
                        giver_stats["given"] = max(
                            0,
                            int(giver_stats.get("given") or 0) - 1,
                        )
                    if was_active and receiver_id and str(receiver_id) != user_key:
                        receiver_stats = self._ensure_stats(stats, receiver_id)
                        receiver_stats["received"] = max(
                            0,
                            int(receiver_stats.get("received") or 0) - 1,
                        )
                    record["reason"] = "[deleted by data request]"
                    record["active"] = False
                    record["removed_at"] = record.get("removed_at") or self._now_ts()
                    record["remove_reason"] = "Deleted by data request."
            await guild_conf.stats.set(stats)
            await guild_conf.records.set(records)

    def _guild_lock(self, guild_id: int) -> asyncio.Lock:
        return self._locks.setdefault(guild_id, asyncio.Lock())

    @staticmethod
    def _now() -> datetime:
        return datetime.now(timezone.utc)

    @classmethod
    def _now_ts(cls) -> float:
        return cls._now().timestamp()

    @classmethod
    def _daily_key(cls) -> str:
        return cls._now().strftime("%Y-%m-%d")

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
    def _format_export_time(value: Any) -> str:
        if value in (None, ""):
            return ""
        try:
            return datetime.fromtimestamp(float(value), tz=timezone.utc).isoformat()
        except (TypeError, ValueError, OSError):
            return ""

    @staticmethod
    def _user_ref(user_id: Any) -> str:
        if user_id in (None, ""):
            return "Unknown"
        try:
            return f"<@{int(user_id)}>"
        except (TypeError, ValueError):
            return "Unknown"

    @staticmethod
    def _record_key(rep_id: int) -> str:
        return str(int(rep_id))

    @staticmethod
    def _empty_stats() -> StatsRecord:
        return {
            "received": 0,
            "given": 0,
            "last_given_at": None,
            "daily_key": None,
            "daily_given": 0,
        }

    @classmethod
    def _ensure_stats(cls, stats: dict[str, StatsRecord], user_id: Any) -> StatsRecord:
        key = str(user_id)
        record = stats.setdefault(key, cls._empty_stats())
        record.setdefault("received", 0)
        record.setdefault("given", 0)
        record.setdefault("last_given_at", None)
        record.setdefault("daily_key", None)
        record.setdefault("daily_given", 0)
        return record

    @staticmethod
    def _channel_from_id(
        guild: discord.Guild,
        channel_id: Any,
    ) -> discord.TextChannel | None:
        if not channel_id:
            return None
        try:
            channel = guild.get_channel(int(channel_id))
        except (TypeError, ValueError):
            return None
        return channel if isinstance(channel, discord.TextChannel) else None

    async def _get_board_channel(
        self,
        guild: discord.Guild,
        settings: dict[str, Any] | None = None,
    ) -> discord.TextChannel | None:
        settings = settings or await self.config.guild(guild).all()
        return self._channel_from_id(guild, settings.get("board_channel_id"))

    async def _get_log_channel(
        self,
        guild: discord.Guild,
        settings: dict[str, Any] | None = None,
    ) -> discord.TextChannel | None:
        settings = settings or await self.config.guild(guild).all()
        return self._channel_from_id(guild, settings.get("log_channel_id"))

    @staticmethod
    def _can_send_embed(channel: discord.TextChannel, member: discord.Member) -> bool:
        permissions = channel.permissions_for(member)
        return bool(permissions.send_messages and permissions.embed_links)

    @classmethod
    def _clean_reason(cls, reason: str | None, settings: dict[str, Any]) -> str:
        cleaned = " ".join((reason or "").strip().split())
        require_reason = bool(settings.get("require_reason"))
        min_length = int(settings.get("min_reason_length") or 0)
        max_length = int(settings.get("max_reason_length") or cls.MAX_REASON_LENGTH)
        max_length = max(1, min(max_length, cls.MAX_REASON_LENGTH))

        if not cleaned and require_reason:
            raise commands.BadArgument("A reason is required here.")
        if cleaned and len(cleaned) < min_length:
            raise commands.BadArgument(
                f"Reason must be at least {min_length} characters.",
            )
        if min_length > 0 and not cleaned:
            raise commands.BadArgument(
                f"Reason must be at least {min_length} characters.",
            )
        if len(cleaned) > max_length:
            raise commands.BadArgument(
                f"Reason must be {max_length} characters or fewer.",
            )
        return cleaned

    @classmethod
    def _normalise_leaderboard_mode(cls, mode: str) -> str:
        lowered = mode.strip().lower()
        aliases = {
            "score": "received",
            "rep": "received",
            "reps": "received",
            "top": "received",
            "received": "received",
            "recv": "received",
            "given": "given",
            "sent": "given",
            "gave": "given",
        }
        if lowered not in aliases:
            raise commands.BadArgument("Mode must be `received` or `given`.")
        return aliases[lowered]

    @staticmethod
    def _active_records(records: dict[str, RepRecord]) -> list[RepRecord]:
        return [record for record in records.values() if record.get("active", True)]

    @classmethod
    def _rankings(
        cls,
        stats: dict[str, StatsRecord],
        mode: str = "received",
    ) -> list[tuple[int, int]]:
        rows: list[tuple[int, int]] = []
        for user_id, record in stats.items():
            try:
                member_id = int(user_id)
            except (TypeError, ValueError):
                continue
            value = int(record.get(mode) or 0)
            if value > 0:
                rows.append((value, member_id))
        rows.sort(key=lambda item: (item[0], -item[1]), reverse=True)
        return rows

    @classmethod
    def _rank_for_member(
        cls,
        stats: dict[str, StatsRecord],
        member_id: int,
        mode: str = "received",
    ) -> int | None:
        for index, (_value, ranked_id) in enumerate(
            cls._rankings(stats, mode),
            start=1,
        ):
            if ranked_id == member_id:
                return index
        return None

    def _rep_embed(
        self,
        guild: discord.Guild,
        record: RepRecord,
        *,
        receiver_total: int | None = None,
    ) -> discord.Embed:
        active = bool(record.get("active", True))
        rep_id = int(record.get("id") or 0)
        reason = str(record.get("reason") or "No reason provided.")
        embed = discord.Embed(
            title=f"Rep #{rep_id}",
            description=reason,
            color=self.REP_COLOR if active else self.REMOVED_COLOR,
            timestamp=self._now(),
        )
        if guild.icon:
            embed.set_author(name=guild.name, icon_url=guild.icon.url)
        else:
            embed.set_author(name=guild.name)
        embed.add_field(
            name="From",
            value=self._user_ref(record.get("giver_id")),
            inline=True,
        )
        embed.add_field(
            name="To",
            value=self._user_ref(record.get("receiver_id")),
            inline=True,
        )
        embed.add_field(
            name="Given",
            value=self._format_ts(record.get("created_at"), "R"),
            inline=True,
        )
        if receiver_total is not None:
            embed.add_field(
                name="Receiver Total",
                value=self._count(receiver_total),
                inline=True,
            )
        if not active:
            embed.add_field(name="Status", value="Removed", inline=True)
            embed.add_field(
                name="Removed By",
                value=self._user_ref(record.get("removed_by")),
                inline=True,
            )
            if record.get("remove_reason"):
                embed.add_field(
                    name="Removal Reason",
                    value=str(record["remove_reason"])[:1024],
                    inline=False,
                )
        embed.set_footer(text=f"Rep ID: {rep_id}")
        return embed

    def _profile_embed(
        self,
        guild: discord.Guild,
        member: discord.Member,
        stats: dict[str, StatsRecord],
        records: dict[str, RepRecord],
    ) -> discord.Embed:
        member_stats = self._ensure_stats(stats, member.id)
        received = int(member_stats.get("received") or 0)
        given = int(member_stats.get("given") or 0)
        rank = self._rank_for_member(stats, member.id, "received")
        recent = [
            record
            for record in self._active_records(records)
            if str(record.get("receiver_id")) == str(member.id)
        ]
        recent.sort(key=lambda item: float(item.get("created_at") or 0), reverse=True)

        embed = discord.Embed(
            title=f"{member.display_name}'s Reputation",
            color=self.PROFILE_COLOR,
            timestamp=self._now(),
        )
        embed.set_thumbnail(url=member.display_avatar.url)
        embed.add_field(name="Received", value=self._count(received), inline=True)
        embed.add_field(name="Given", value=self._count(given), inline=True)
        embed.add_field(
            name="Rank",
            value=f"#{rank}" if rank else "Unranked",
            inline=True,
        )
        if recent:
            lines = []
            for record in recent[:5]:
                giver = self._user_ref(record.get("giver_id"))
                reason = str(record.get("reason") or "No reason provided.")
                lines.append(f"#{record.get('id')} from {giver}: {reason[:90]}")
            embed.add_field(
                name="Recent Rep",
                value="\n".join(lines)[:1024],
                inline=False,
            )
        else:
            embed.add_field(
                name="Recent Rep",
                value="No reputation received yet.",
                inline=False,
            )
        return embed

    async def _send_log(
        self,
        guild: discord.Guild,
        settings: dict[str, Any],
        title: str,
        description: str,
        *,
        color: int | None = None,
    ) -> None:
        channel = await self._get_log_channel(guild, settings)
        if channel is None:
            return
        me = guild.me
        if me is None or not self._can_send_embed(channel, me):
            return
        embed = discord.Embed(
            title=title,
            description=description,
            color=color or self.DEFAULT_COLOR,
            timestamp=self._now(),
        )
        try:
            await channel.send(
                embed=embed,
                allowed_mentions=discord.AllowedMentions.none(),
            )
        except discord.HTTPException:
            log.exception("Failed to send RepBoard log in guild %s", guild.id)

    async def _send_rep_announcement(
        self,
        ctx: commands.Context,
        record: RepRecord,
        settings: dict[str, Any],
        *,
        receiver_total: int,
    ) -> discord.Message | None:
        assert ctx.guild is not None
        me = ctx.guild.me
        if me is None:
            return None

        embed = self._rep_embed(ctx.guild, record, receiver_total=receiver_total)
        board_channel = await self._get_board_channel(ctx.guild, settings)
        fallback_channel = (
            ctx.channel if isinstance(ctx.channel, discord.TextChannel) else None
        )

        channels: list[discord.TextChannel] = []
        if board_channel is not None:
            channels.append(board_channel)
        if fallback_channel is not None and fallback_channel not in channels:
            channels.append(fallback_channel)

        for channel in channels:
            if not self._can_send_embed(channel, me):
                continue
            try:
                return await channel.send(
                    embed=embed,
                    allowed_mentions=discord.AllowedMentions.none(),
                )
            except discord.HTTPException:
                log.exception(
                    "Failed to send RepBoard announcement in guild %s",
                    ctx.guild.id,
                )
        return None

    async def _store_announcement_message(
        self,
        guild: discord.Guild,
        record: RepRecord,
        message: discord.Message | None,
    ) -> None:
        if message is None:
            return
        async with self.config.guild(guild).records() as records:
            stored = records.get(self._record_key(int(record["id"])))
            if not stored:
                return
            stored["message_id"] = message.id
            stored["channel_id"] = message.channel.id
            if isinstance(message.channel, discord.TextChannel):
                stored["message_jump_url"] = message.jump_url
            records[self._record_key(int(record["id"]))] = stored

    async def _sync_record_message(
        self,
        guild: discord.Guild,
        record: RepRecord,
    ) -> None:
        channel = self._channel_from_id(guild, record.get("channel_id"))
        message_id = record.get("message_id")
        if channel is None or not message_id:
            return
        try:
            message = await channel.fetch_message(int(message_id))
            await message.edit(embed=self._rep_embed(guild, record))
        except (discord.NotFound, discord.Forbidden, discord.HTTPException):
            return

    async def _give_rep(
        self,
        guild: discord.Guild,
        giver: discord.Member,
        receiver: discord.Member,
        reason: str | None,
    ) -> tuple[RepRecord, dict[str, Any], int]:
        async with self._guild_lock(guild.id):
            guild_conf = self.config.guild(guild)
            settings = await guild_conf.all()
            if not settings.get("enabled"):
                raise commands.CommandError(
                    "RepBoard is not enabled yet. Ask staff to run `[p]repboard setup`.",
                )
            if receiver.bot and not settings.get("allow_bots"):
                raise commands.CommandError("Reputation for bots is disabled here.")
            if giver.id == receiver.id and not settings.get("allow_self_rep"):
                raise commands.CommandError("You cannot give reputation to yourself.")

            cleaned_reason = self._clean_reason(reason, settings)
            stats: dict[str, StatsRecord] = settings.get("stats") or {}
            records: dict[str, RepRecord] = settings.get("records") or {}
            giver_stats = self._ensure_stats(stats, giver.id)
            receiver_stats = self._ensure_stats(stats, receiver.id)

            now = self._now_ts()
            cooldown_seconds = int(settings.get("cooldown_seconds") or 0)
            last_given_at = giver_stats.get("last_given_at")
            if cooldown_seconds > 0 and last_given_at:
                elapsed = now - float(last_given_at)
                if elapsed < cooldown_seconds:
                    remaining = int(cooldown_seconds - elapsed)
                    raise commands.CommandError(
                        f"Wait {remaining // 60}m {remaining % 60}s before giving reputation again.",
                    )

            daily_limit = int(settings.get("daily_limit") or 0)
            today = self._daily_key()
            if giver_stats.get("daily_key") != today:
                giver_stats["daily_key"] = today
                giver_stats["daily_given"] = 0
            if (
                daily_limit > 0
                and int(giver_stats.get("daily_given") or 0) >= daily_limit
            ):
                raise commands.CommandError(
                    f"You have reached the daily reputation limit of {daily_limit}.",
                )

            rep_id = int(settings.get("next_rep_id") or 1)
            record: RepRecord = {
                "id": rep_id,
                "giver_id": giver.id,
                "receiver_id": receiver.id,
                "reason": cleaned_reason,
                "created_at": now,
                "active": True,
                "removed_at": None,
                "removed_by": None,
                "remove_reason": None,
                "channel_id": None,
                "message_id": None,
                "message_jump_url": None,
            }

            giver_stats["given"] = int(giver_stats.get("given") or 0) + 1
            giver_stats["last_given_at"] = now
            giver_stats["daily_given"] = int(giver_stats.get("daily_given") or 0) + 1
            receiver_stats["received"] = int(receiver_stats.get("received") or 0) + 1
            receiver_total = int(receiver_stats.get("received") or 0)

            records[self._record_key(rep_id)] = record
            await guild_conf.records.set(records)
            await guild_conf.stats.set(stats)
            await guild_conf.next_rep_id.set(rep_id + 1)
            settings["records"] = records
            settings["stats"] = stats
            settings["next_rep_id"] = rep_id + 1
            return record, settings, receiver_total

    async def _remove_rep(
        self,
        guild: discord.Guild,
        rep_id: int,
        moderator: discord.Member,
        reason: str | None,
    ) -> tuple[RepRecord, dict[str, Any]]:
        async with self._guild_lock(guild.id):
            guild_conf = self.config.guild(guild)
            settings = await guild_conf.all()
            records: dict[str, RepRecord] = settings.get("records") or {}
            stats: dict[str, StatsRecord] = settings.get("stats") or {}
            record = records.get(self._record_key(rep_id))
            if not record:
                raise commands.BadArgument(
                    f"No reputation entry with ID `{rep_id}` was found.",
                )
            if not record.get("active", True):
                raise commands.BadArgument(
                    f"Reputation entry `{rep_id}` is already removed.",
                )

            record["active"] = False
            record["removed_at"] = self._now_ts()
            record["removed_by"] = moderator.id
            record["remove_reason"] = (reason or "No reason provided.")[:300]

            giver_id = record.get("giver_id")
            receiver_id = record.get("receiver_id")
            if giver_id:
                giver_stats = self._ensure_stats(stats, giver_id)
                giver_stats["given"] = max(0, int(giver_stats.get("given") or 0) - 1)
            if receiver_id:
                receiver_stats = self._ensure_stats(stats, receiver_id)
                receiver_stats["received"] = max(
                    0,
                    int(receiver_stats.get("received") or 0) - 1,
                )

            records[self._record_key(rep_id)] = record
            await guild_conf.records.set(records)
            await guild_conf.stats.set(stats)
            settings["records"] = records
            settings["stats"] = stats
            return record, settings

    async def _send_settings(self, ctx: commands.Context) -> None:
        assert ctx.guild is not None
        settings = await self.config.guild(ctx.guild).all()
        stats = settings.get("stats") or {}
        records = settings.get("records") or {}
        active_count = len(self._active_records(records))
        board_channel = await self._get_board_channel(ctx.guild, settings)
        log_channel = await self._get_log_channel(ctx.guild, settings)
        prefix = ctx.clean_prefix
        embed = discord.Embed(
            title="RepBoard",
            color=self.DEFAULT_COLOR,
            timestamp=self._now(),
        )
        embed.add_field(
            name="Status",
            value=(
                f"Enabled: **{'Yes' if settings.get('enabled') else 'No'}**\n"
                f"Active rep entries: **{self._count(active_count)}**\n"
                f"Tracked members: **{self._count(len(stats))}**"
            ),
            inline=True,
        )
        embed.add_field(
            name="Channels",
            value=(
                f"Board: {board_channel.mention if board_channel else 'not set'}\n"
                f"Logs: {log_channel.mention if log_channel else 'not set'}"
            ),
            inline=True,
        )
        cooldown = int(settings.get("cooldown_seconds") or 0)
        daily_limit = int(settings.get("daily_limit") or 0)
        embed.add_field(
            name="Limits",
            value=(
                f"Cooldown: **{cooldown // 60} minute(s)**\n"
                f"Daily limit: **{daily_limit if daily_limit else 'Unlimited'}**\n"
                f"Reason required: **{'Yes' if settings.get('require_reason') else 'No'}**"
            ),
            inline=False,
        )
        embed.add_field(
            name="Start Here",
            value=(
                f"`{prefix}repboard walkthrough`\n"
                f"`{prefix}repboard setup #rep-board #staff-logs`\n"
                f"`{prefix}repboard give @member thank you for helping`"
            ),
            inline=False,
        )
        await ctx.send(embed=embed)

    async def _wait_for_setup_reply(
        self,
        ctx: commands.Context,
        prompt: str,
        timeout: int = 120,
    ) -> str:
        await ctx.send(prompt)

        def check(message: discord.Message) -> bool:
            return (
                message.author.id == ctx.author.id
                and message.channel.id == ctx.channel.id
                and message.guild == ctx.guild
            )

        try:
            message = await self.bot.wait_for("message", check=check, timeout=timeout)
        except asyncio.TimeoutError as exc:
            raise commands.CommandError("RepBoard walkthrough timed out.") from exc

        answer = message.content.strip()
        if answer.lower() in {"cancel", "stop", "quit"}:
            raise commands.CommandError("RepBoard walkthrough cancelled.")
        return answer

    async def _prompt_text_channel(
        self,
        ctx: commands.Context,
        prompt: str,
        *,
        allow_none: bool = False,
    ) -> discord.TextChannel | None:
        while True:
            answer = await self._wait_for_setup_reply(ctx, prompt)
            lowered = answer.lower()
            if lowered in {"here", "current"} and isinstance(
                ctx.channel,
                discord.TextChannel,
            ):
                return ctx.channel
            if allow_none and lowered in {"none", "no", "skip", "off"}:
                return None
            try:
                return await commands.TextChannelConverter().convert(ctx, answer)
            except commands.BadArgument:
                await ctx.send(
                    "Reply with a text channel mention, channel ID, `here`, or `none` when allowed.",
                )

    @staticmethod
    def _parse_bool_answer(answer: str, *, default: bool | None = None) -> bool:
        lowered = answer.strip().lower()
        if default is not None and lowered in {"", "skip", "default"}:
            return default
        if lowered in {"yes", "y", "true", "on", "enable", "enabled", "1"}:
            return True
        if lowered in {"no", "n", "false", "off", "disable", "disabled", "0"}:
            return False
        raise commands.BadArgument("Reply with `yes` or `no`.")

    async def _prompt_bool(
        self,
        ctx: commands.Context,
        prompt: str,
        *,
        default: bool | None = None,
    ) -> bool:
        while True:
            answer = await self._wait_for_setup_reply(ctx, prompt)
            try:
                return self._parse_bool_answer(answer, default=default)
            except commands.BadArgument as error:
                await ctx.send(str(error))

    async def _prompt_int(
        self,
        ctx: commands.Context,
        prompt: str,
        *,
        minimum: int,
        maximum: int,
        default: int | None = None,
    ) -> int:
        while True:
            answer = await self._wait_for_setup_reply(ctx, prompt)
            lowered = answer.lower()
            if default is not None and lowered in {"skip", "default"}:
                return default
            try:
                value = int(answer)
            except ValueError:
                await ctx.send(
                    f"Reply with a whole number between {minimum} and {maximum}.",
                )
                continue
            if value < minimum or value > maximum:
                await ctx.send(f"Reply with a number between {minimum} and {maximum}.")
                continue
            return value

    @commands.hybrid_group(name="repboard", invoke_without_command=True)
    @commands.guild_only()
    @commands.bot_has_permissions(embed_links=True)
    async def repboard(self, ctx: commands.Context) -> None:
        """Configure and use RepBoard."""
        await self._send_settings(ctx)

    @repboard.command(name="setup")
    @commands.admin_or_permissions(manage_guild=True)
    async def repboard_setup(
        self,
        ctx: commands.Context,
        board_channel: discord.TextChannel | None = None,
        log_channel: discord.TextChannel | None = None,
    ) -> None:
        """Quick setup for RepBoard."""
        assert ctx.guild is not None
        if board_channel is None:
            if not isinstance(ctx.channel, discord.TextChannel):
                await ctx.send("Run this in a text channel or provide a board channel.")
                return
            board_channel = ctx.channel
        guild_conf = self.config.guild(ctx.guild)
        await guild_conf.enabled.set(True)
        await guild_conf.board_channel_id.set(board_channel.id)
        if log_channel is not None:
            await guild_conf.log_channel_id.set(log_channel.id)
        await ctx.send(
            f"RepBoard is enabled. Board: {board_channel.mention}. "
            f"Logs: {log_channel.mention if log_channel else 'unchanged/not set'}.",
        )

    @repboard.command(name="walkthrough", aliases=["wizard"])
    @commands.admin_or_permissions(manage_guild=True)
    async def repboard_walkthrough(self, ctx: commands.Context) -> None:
        """Walk through RepBoard setup."""
        assert ctx.guild is not None
        await ctx.send(
            "RepBoard setup walkthrough started. Reply `cancel` at any step to stop.",
        )
        try:
            board_channel = await self._prompt_text_channel(
                ctx,
                "Step 1/5: Which channel should public reputation posts go to? Reply with a channel, `here`, or `none`.",
                allow_none=True,
            )
            log_channel = await self._prompt_text_channel(
                ctx,
                "Step 2/5: Which channel should staff logs go to? Reply with a channel, `here`, or `none`.",
                allow_none=True,
            )
            require_reason = await self._prompt_bool(
                ctx,
                "Step 3/5: Should members be required to include a reason? Reply `yes` or `no`.",
                default=False,
            )
            cooldown_minutes = await self._prompt_int(
                ctx,
                "Step 4/5: How many minutes should members wait between giving rep? Use `0` to disable.",
                minimum=0,
                maximum=1440,
                default=60,
            )
            daily_limit = await self._prompt_int(
                ctx,
                "Step 5/5: How many reps can each member give per UTC day? Use `0` for unlimited.",
                minimum=0,
                maximum=100,
                default=5,
            )
        except commands.CommandError as error:
            await ctx.send(str(error))
            return

        guild_conf = self.config.guild(ctx.guild)
        await guild_conf.enabled.set(True)
        await guild_conf.board_channel_id.set(
            board_channel.id if board_channel else None,
        )
        await guild_conf.log_channel_id.set(log_channel.id if log_channel else None)
        await guild_conf.require_reason.set(require_reason)
        await guild_conf.cooldown_seconds.set(cooldown_minutes * 60)
        await guild_conf.daily_limit.set(daily_limit)

        await ctx.send(
            "RepBoard setup complete.\n"
            f"Board: {board_channel.mention if board_channel else 'command channel fallback'}\n"
            f"Logs: {log_channel.mention if log_channel else 'none'}\n"
            f"Members can now use `{ctx.clean_prefix}repboard give @member reason`.",
        )

    @repboard.command(name="enable")
    @commands.admin_or_permissions(manage_guild=True)
    async def repboard_enable(
        self,
        ctx: commands.Context,
        enabled: bool = True,
    ) -> None:
        """Enable or disable reputation giving."""
        assert ctx.guild is not None
        await self.config.guild(ctx.guild).enabled.set(enabled)
        await ctx.send(f"RepBoard is now {'enabled' if enabled else 'disabled'}.")

    @repboard.command(name="boardchannel")
    @commands.admin_or_permissions(manage_guild=True)
    async def repboard_board_channel(
        self,
        ctx: commands.Context,
        channel: discord.TextChannel | None = None,
    ) -> None:
        """Set or clear the public rep board channel."""
        assert ctx.guild is not None
        await self.config.guild(ctx.guild).board_channel_id.set(
            channel.id if channel else None,
        )
        await ctx.send(
            f"Rep board channel set to {channel.mention if channel else 'none'}.",
        )

    @repboard.command(name="logchannel")
    @commands.admin_or_permissions(manage_guild=True)
    async def repboard_log_channel(
        self,
        ctx: commands.Context,
        channel: discord.TextChannel | None = None,
    ) -> None:
        """Set or clear the staff log channel."""
        assert ctx.guild is not None
        await self.config.guild(ctx.guild).log_channel_id.set(
            channel.id if channel else None,
        )
        await ctx.send(
            f"RepBoard log channel set to {channel.mention if channel else 'none'}.",
        )

    @repboard.command(name="cooldown")
    @commands.admin_or_permissions(manage_guild=True)
    async def repboard_cooldown(self, ctx: commands.Context, minutes: int) -> None:
        """Set cooldown minutes between giving reputation."""
        assert ctx.guild is not None
        minutes = max(0, min(minutes, 1440))
        await self.config.guild(ctx.guild).cooldown_seconds.set(minutes * 60)
        await ctx.send(f"Rep giving cooldown set to **{minutes}** minute(s).")

    @repboard.command(name="dailylimit")
    @commands.admin_or_permissions(manage_guild=True)
    async def repboard_daily_limit(self, ctx: commands.Context, amount: int) -> None:
        """Set daily reputation giving limit. Use 0 for unlimited."""
        assert ctx.guild is not None
        amount = max(0, min(amount, 100))
        await self.config.guild(ctx.guild).daily_limit.set(amount)
        await ctx.send(
            f"Daily rep giving limit set to **{amount if amount else 'unlimited'}**.",
        )

    @repboard.command(name="requirereason")
    @commands.admin_or_permissions(manage_guild=True)
    async def repboard_require_reason(
        self,
        ctx: commands.Context,
        enabled: bool,
    ) -> None:
        """Require or allow empty reputation reasons."""
        assert ctx.guild is not None
        await self.config.guild(ctx.guild).require_reason.set(enabled)
        await ctx.send(f"Rep reasons are now {'required' if enabled else 'optional'}.")

    @repboard.command(name="minreason")
    @commands.admin_or_permissions(manage_guild=True)
    async def repboard_min_reason(self, ctx: commands.Context, length: int) -> None:
        """Set minimum reason length."""
        assert ctx.guild is not None
        length = max(0, min(length, 200))
        await self.config.guild(ctx.guild).min_reason_length.set(length)
        await ctx.send(f"Minimum rep reason length set to **{length}**.")

    @repboard.command(name="allowbots")
    @commands.admin_or_permissions(manage_guild=True)
    async def repboard_allow_bots(self, ctx: commands.Context, enabled: bool) -> None:
        """Allow or block reputation for bots."""
        assert ctx.guild is not None
        await self.config.guild(ctx.guild).allow_bots.set(enabled)
        await ctx.send(f"Bot reputation is now {'allowed' if enabled else 'blocked'}.")

    @repboard.command(name="allowself")
    @commands.admin_or_permissions(manage_guild=True)
    async def repboard_allow_self(self, ctx: commands.Context, enabled: bool) -> None:
        """Allow or block self-reputation."""
        assert ctx.guild is not None
        await self.config.guild(ctx.guild).allow_self_rep.set(enabled)
        await ctx.send(f"Self-reputation is now {'allowed' if enabled else 'blocked'}.")

    @repboard.command(name="give", aliases=["kudos", "thank", "thanks"])
    @commands.guild_only()
    async def repboard_give(
        self,
        ctx: commands.Context,
        member: discord.Member,
        *,
        reason: str | None = None,
    ) -> None:
        """Give reputation to a member."""
        assert ctx.guild is not None
        if not isinstance(ctx.author, discord.Member):
            await ctx.send("This command only works in a server.")
            return
        try:
            record, settings, receiver_total = await self._give_rep(
                ctx.guild,
                ctx.author,
                member,
                reason,
            )
        except commands.CommandError as error:
            await ctx.send(str(error))
            return

        message = await self._send_rep_announcement(
            ctx,
            record,
            settings,
            receiver_total=receiver_total,
        )
        await self._store_announcement_message(ctx.guild, record, message)
        await self._send_log(
            ctx.guild,
            settings,
            "Reputation Given",
            f"Rep #{record['id']} from {ctx.author.mention} to {member.mention}.",
            color=self.REP_COLOR,
        )

        if message is None:
            await ctx.send(
                f"Rep #{record['id']} recorded for {member.mention}, but I could not post an embed.",
            )
        elif (
            isinstance(ctx.channel, discord.TextChannel)
            and message.channel.id != ctx.channel.id
        ):
            await ctx.send(f"Rep #{record['id']} posted to {message.channel.mention}.")

    @repboard.command(name="profile")
    @commands.guild_only()
    async def repboard_profile(
        self,
        ctx: commands.Context,
        member: discord.Member | None = None,
    ) -> None:
        """Show a member's reputation profile."""
        assert ctx.guild is not None
        if member is None:
            if not isinstance(ctx.author, discord.Member):
                await ctx.send("Provide a member.")
                return
            member = ctx.author
        settings = await self.config.guild(ctx.guild).all()
        stats = settings.get("stats") or {}
        records = settings.get("records") or {}
        await ctx.send(embed=self._profile_embed(ctx.guild, member, stats, records))

    @repboard.command(name="leaderboard", aliases=["top"])
    @commands.guild_only()
    async def repboard_leaderboard(
        self,
        ctx: commands.Context,
        mode: str = "received",
        limit: int = 10,
    ) -> None:
        """Show the reputation leaderboard."""
        assert ctx.guild is not None
        if mode.isdigit() and limit == 10:
            limit = int(mode)
            mode = "received"
        try:
            mode = self._normalise_leaderboard_mode(mode)
        except commands.BadArgument as error:
            await ctx.send(str(error))
            return
        limit = max(1, min(limit, 25))
        stats = await self.config.guild(ctx.guild).stats()
        rows = self._rankings(stats, mode)[:limit]
        if not rows:
            await ctx.send("No reputation has been recorded yet.")
            return

        title = "Received Reputation" if mode == "received" else "Given Reputation"
        lines = []
        for index, (value, member_id) in enumerate(rows, start=1):
            lines.append(
                f"{index}. {self._user_ref(member_id)} - **{self._count(value)}**",
            )
        embed = discord.Embed(
            title=f"RepBoard Leaderboard - {title}",
            description="\n".join(lines),
            color=self.DEFAULT_COLOR,
            timestamp=self._now(),
        )
        await ctx.send(embed=embed)

    @repboard.command(name="history")
    @commands.guild_only()
    async def repboard_history(
        self,
        ctx: commands.Context,
        member: discord.Member | None = None,
        limit: int = 10,
    ) -> None:
        """Show recent reputation received by a member."""
        assert ctx.guild is not None
        if member is None:
            if not isinstance(ctx.author, discord.Member):
                await ctx.send("Provide a member.")
                return
            member = ctx.author
        limit = max(1, min(limit, 25))
        records = await self.config.guild(ctx.guild).records()
        history = [
            record
            for record in self._active_records(records)
            if str(record.get("receiver_id")) == str(member.id)
        ]
        history.sort(key=lambda item: float(item.get("created_at") or 0), reverse=True)
        if not history:
            await ctx.send(f"{member.mention} has not received reputation yet.")
            return
        lines = []
        for record in history[:limit]:
            reason = str(record.get("reason") or "No reason provided.")
            lines.append(
                f"#{record.get('id')} | {self._format_ts(record.get('created_at'), 'R')} "
                f"| from {self._user_ref(record.get('giver_id'))} | {reason}",
            )
        for page in pagify("\n".join(lines), page_length=1800):
            await ctx.send(box(page))

    @repboard.command(name="remove", aliases=["delete"])
    @commands.guild_only()
    @commands.admin_or_permissions(manage_messages=True)
    async def repboard_remove(
        self,
        ctx: commands.Context,
        rep_id: int,
        *,
        reason: str | None = None,
    ) -> None:
        """Remove a reputation entry from active counts."""
        assert ctx.guild is not None
        if not isinstance(ctx.author, discord.Member):
            return
        try:
            record, settings = await self._remove_rep(
                ctx.guild,
                rep_id,
                ctx.author,
                reason,
            )
        except commands.CommandError as error:
            await ctx.send(str(error))
            return
        await self._sync_record_message(ctx.guild, record)
        await self._send_log(
            ctx.guild,
            settings,
            "Reputation Removed",
            f"Rep #{rep_id} removed by {ctx.author.mention}. Reason: {record.get('remove_reason')}",
            color=self.REMOVED_COLOR,
        )
        await ctx.send(f"Rep #{rep_id} removed from active counts.")

    @repboard.command(name="export")
    @commands.admin_or_permissions(manage_guild=True)
    @commands.bot_has_permissions(attach_files=True)
    async def repboard_export(self, ctx: commands.Context) -> None:
        """Export reputation records as CSV."""
        assert ctx.guild is not None
        records = await self.config.guild(ctx.guild).records()
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(
            [
                "id",
                "active",
                "giver_id",
                "receiver_id",
                "reason",
                "created_at",
                "removed_at",
                "removed_by",
                "remove_reason",
                "channel_id",
                "message_id",
                "message_jump_url",
            ],
        )
        for record in sorted(
            records.values(),
            key=lambda item: int(item.get("id") or 0),
        ):
            writer.writerow(
                [
                    record.get("id"),
                    bool(record.get("active", True)),
                    record.get("giver_id"),
                    record.get("receiver_id"),
                    record.get("reason"),
                    self._format_export_time(record.get("created_at")),
                    self._format_export_time(record.get("removed_at")),
                    record.get("removed_by"),
                    record.get("remove_reason"),
                    record.get("channel_id"),
                    record.get("message_id"),
                    record.get("message_jump_url"),
                ],
            )
        file = discord.File(
            io.BytesIO(output.getvalue().encode("utf-8")),
            filename=f"repboard-{ctx.guild.id}.csv",
        )
        await ctx.send("RepBoard export:", file=file)
