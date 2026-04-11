"""Giveaway cog for Red-DiscordBot."""

from __future__ import annotations

import asyncio
import logging
import random
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

import discord
from discord.ext import tasks
from redbot.core import Config, commands
from redbot.core.bot import Red
from redbot.core.utils.chat_formatting import humanize_timedelta, pagify

log = logging.getLogger("red.taakoscogs.giveaway")


class Giveaway(commands.Cog):
    """Run timed reaction-based giveaways."""

    REACTION_EMOJI = "\N{PARTY POPPER}"
    MIN_DURATION_SECONDS = 30
    MAX_DURATION_SECONDS = 60 * 60 * 24 * 365
    MAX_WINNERS = 25
    DURATION_RE = re.compile(r"(\d+)([smhdw])", re.IGNORECASE)
    MESSAGE_LINK_RE = re.compile(
        r"https?://(?:ptb\.|canary\.)?discord(?:app)?\.com/channels/"
        r"(?P<guild_id>\d+)/(?P<channel_id>\d+)/(?P<message_id>\d+)"
    )

    def __init__(self, bot: Red) -> None:
        self.bot = bot
        self.config = Config.get_conf(self, identifier=2026041101, force_registration=True)
        self.config.register_guild(giveaways={})
        self._giveaway_locks: Dict[Tuple[int, int], asyncio.Lock] = {}
        self._task = self.giveaway_loop.start()

    async def cog_unload(self) -> None:
        """Cancel the giveaway watcher when the cog unloads."""
        if self._task:
            self._task.cancel()

    async def red_delete_data_for_user(self, *, requester: str, user_id: int) -> None:
        """Remove stored host and winner references for a deleted user."""
        all_guilds = await self.config.all_guilds()
        for guild_id in all_guilds:
            async with self.config.guild_from_id(guild_id).giveaways() as giveaways:
                for record in giveaways.values():
                    if record.get("host_id") == user_id:
                        record["host_id"] = None
                    winner_ids = [winner_id for winner_id in record.get("winner_ids", []) if winner_id != user_id]
                    if winner_ids != record.get("winner_ids", []):
                        record["winner_ids"] = winner_ids

    @tasks.loop(seconds=30)
    async def giveaway_loop(self) -> None:
        """End active giveaways whose timers have elapsed."""
        now = self._now_ts()
        all_guilds = await self.config.all_guilds()
        for guild_id, guild_data in all_guilds.items():
            guild = self.bot.get_guild(guild_id)
            if guild is None:
                continue

            for message_id, record in guild_data.get("giveaways", {}).items():
                if record.get("status") != "active":
                    continue
                if float(record.get("ends_at", 0)) > now:
                    continue

                try:
                    await self._end_giveaway(guild, int(message_id))
                except Exception:
                    log.exception(
                        "Failed to auto-end giveaway %s in guild %s",
                        message_id,
                        guild_id,
                    )

    @giveaway_loop.before_loop
    async def before_giveaway_loop(self) -> None:
        """Wait until the bot is ready before checking giveaways."""
        await self.bot.wait_until_ready()

    @staticmethod
    def _now_ts() -> float:
        return datetime.now(timezone.utc).timestamp()

    @staticmethod
    def _shorten(text: str, limit: int) -> str:
        if len(text) <= limit:
            return text
        return f"{text[: limit - 3].rstrip()}..."

    @classmethod
    def _parse_duration(cls, raw_duration: str) -> int:
        compact = raw_duration.strip().lower().replace(" ", "")
        if not compact:
            raise commands.BadArgument(
                "Provide a duration like `30m`, `2h`, `1d12h`, or `1w`."
            )

        matches = list(cls.DURATION_RE.finditer(compact))
        if not matches or "".join(match.group(0) for match in matches) != compact:
            raise commands.BadArgument(
                "Invalid duration. Use values like `30m`, `2h`, `3d`, or `1w2d6h`."
            )

        unit_seconds = {
            "s": 1,
            "m": 60,
            "h": 60 * 60,
            "d": 60 * 60 * 24,
            "w": 60 * 60 * 24 * 7,
        }
        total_seconds = sum(
            int(match.group(1)) * unit_seconds[match.group(2).lower()] for match in matches
        )

        if total_seconds < cls.MIN_DURATION_SECONDS:
            raise commands.BadArgument("Giveaways must run for at least 30 seconds.")
        if total_seconds > cls.MAX_DURATION_SECONDS:
            raise commands.BadArgument("Giveaways cannot run longer than 1 year.")

        return total_seconds

    def _get_lock(self, guild_id: int, message_id: int) -> asyncio.Lock:
        key = (guild_id, message_id)
        if key not in self._giveaway_locks:
            self._giveaway_locks[key] = asyncio.Lock()
        return self._giveaway_locks[key]

    def _get_text_channel(self, guild: discord.Guild, channel_id: int) -> Optional[discord.TextChannel]:
        channel = guild.get_channel(channel_id)
        if isinstance(channel, discord.TextChannel):
            return channel
        return None

    def _format_user(self, user_id: Optional[int]) -> str:
        if not user_id:
            return "Unknown user"
        return f"<@{user_id}>"

    def _build_jump_url(self, guild_id: int, channel_id: int, message_id: int) -> str:
        return f"https://discord.com/channels/{guild_id}/{channel_id}/{message_id}"

    def _build_giveaway_embed(self, record: Dict[str, Any]) -> discord.Embed:
        status = record.get("status", "active")
        if status == "cancelled":
            color = discord.Color.red()
            status_label = "Cancelled"
            description = (
                f"**Prize:** {self._shorten(record['prize'], 3800)}\n\n"
                "This giveaway has been cancelled."
            )
        elif status == "ended":
            color = discord.Color.green()
            status_label = "Ended"
            description = (
                f"**Prize:** {self._shorten(record['prize'], 3800)}\n\n"
                "This giveaway has ended."
            )
        else:
            color = discord.Color.blurple()
            status_label = "Active"
            description = (
                f"**Prize:** {self._shorten(record['prize'], 3800)}\n\n"
                f"React with {self.REACTION_EMOJI} to enter."
            )

        embed = discord.Embed(title="Giveaway", description=description, color=color)

        end_time = datetime.fromtimestamp(float(record["ends_at"]), tz=timezone.utc)
        embed.add_field(
            name="Ends",
            value=f"{discord.utils.format_dt(end_time, 'F')}\n{discord.utils.format_dt(end_time, 'R')}",
            inline=False,
        )
        embed.add_field(
            name="Hosted By",
            value=self._format_user(record.get("host_id")),
            inline=True,
        )
        embed.add_field(
            name="Winners",
            value=str(int(record.get("winner_count", 1))),
            inline=True,
        )
        embed.add_field(name="Status", value=status_label, inline=True)

        entry_count = int(record.get("entry_count", 0))
        if status != "active":
            embed.add_field(name="Entries", value=str(entry_count), inline=True)

        winner_ids = [winner_id for winner_id in record.get("winner_ids", []) if winner_id]
        if status == "ended":
            winner_value = ", ".join(f"<@{winner_id}>" for winner_id in winner_ids) if winner_ids else "No valid entries"
            embed.add_field(name="Winner(s)", value=self._shorten(winner_value, 1024), inline=False)

        ended_at = record.get("ended_at")
        if ended_at:
            ended_time = datetime.fromtimestamp(float(ended_at), tz=timezone.utc)
            embed.add_field(
                name="Closed",
                value=f"{discord.utils.format_dt(ended_time, 'F')}\n{discord.utils.format_dt(ended_time, 'R')}",
                inline=False,
            )

        if record.get("message_id"):
            embed.set_footer(text=f"Message ID: {record['message_id']}")

        return embed

    def _ensure_winner_count(self, winner_count: int) -> None:
        if winner_count < 1:
            raise commands.BadArgument("Winner count must be at least 1.")
        if winner_count > self.MAX_WINNERS:
            raise commands.BadArgument(f"Winner count cannot exceed {self.MAX_WINNERS}.")

    def _validate_channel_permissions(
        self, channel: discord.TextChannel, me: Optional[discord.Member]
    ) -> None:
        if me is None:
            raise commands.CommandError("I couldn't resolve my own member record in this server.")

        permissions = channel.permissions_for(me)
        missing = []
        required = {
            "view_channel": "View Channel",
            "send_messages": "Send Messages",
            "embed_links": "Embed Links",
            "add_reactions": "Add Reactions",
            "read_message_history": "Read Message History",
        }
        for perm_name, label in required.items():
            if not getattr(permissions, perm_name, False):
                missing.append(label)

        if missing:
            missing_text = ", ".join(missing)
            raise commands.CommandError(
                f"I am missing required permissions in {channel.mention}: {missing_text}."
            )

    async def _fetch_giveaway_message(
        self, guild: discord.Guild, record: Dict[str, Any]
    ) -> Optional[discord.Message]:
        channel = self._get_text_channel(guild, int(record["channel_id"]))
        if channel is None:
            return None

        try:
            return await channel.fetch_message(int(record["message_id"]))
        except (discord.NotFound, discord.Forbidden, discord.HTTPException):
            return None

    async def _get_entrants(self, message: discord.Message) -> List[discord.Member]:
        reaction = discord.utils.get(message.reactions, emoji=self.REACTION_EMOJI)
        if reaction is None:
            return []

        entrants: List[discord.Member] = []
        async for user in reaction.users():
            if user.bot:
                continue

            member = user if isinstance(user, discord.Member) else message.guild.get_member(user.id)
            if member is None:
                try:
                    member = await message.guild.fetch_member(user.id)
                except (discord.NotFound, discord.Forbidden, discord.HTTPException):
                    continue

            if member.bot:
                continue

            entrants.append(member)

        return entrants

    @staticmethod
    def _pick_winners(
        entrants: List[discord.Member], winner_count: int, excluded_ids: Optional[set[int]] = None
    ) -> List[discord.Member]:
        excluded_ids = excluded_ids or set()
        pool = [entrant for entrant in entrants if entrant.id not in excluded_ids]
        if not pool:
            return []
        return random.sample(pool, k=min(winner_count, len(pool)))

    @classmethod
    def _parse_reference(cls, guild: discord.Guild, raw_reference: str) -> Tuple[Optional[int], int]:
        reference = raw_reference.strip().strip("<>")
        if reference.isdigit():
            return None, int(reference)

        match = cls.MESSAGE_LINK_RE.fullmatch(reference)
        if not match:
            raise commands.BadArgument("Provide a giveaway message ID or a Discord message link.")

        guild_id = int(match.group("guild_id"))
        if guild_id != guild.id:
            raise commands.BadArgument("That message link does not belong to this server.")

        return int(match.group("channel_id")), int(match.group("message_id"))

    async def _get_record_from_reference(
        self, guild: discord.Guild, reference: str
    ) -> Tuple[str, Dict[str, Any]]:
        channel_id_hint, message_id = self._parse_reference(guild, reference)
        giveaways = await self.config.guild(guild).giveaways()
        key = str(message_id)
        record = giveaways.get(key)
        if record is None:
            raise commands.BadArgument("No giveaway with that message ID was found in this server.")
        if channel_id_hint is not None and int(record.get("channel_id", 0)) != channel_id_hint:
            raise commands.BadArgument("That message link does not match the stored giveaway record.")
        return key, record

    async def _edit_giveaway_message(
        self, guild: discord.Guild, record: Dict[str, Any]
    ) -> Optional[discord.Message]:
        message = await self._fetch_giveaway_message(guild, record)
        if message is None:
            return None

        try:
            await message.edit(embed=self._build_giveaway_embed(record))
        except (discord.Forbidden, discord.HTTPException):
            log.warning(
                "Failed to edit giveaway message %s in guild %s",
                record.get("message_id"),
                guild.id,
            )
        return message

    async def _end_giveaway(
        self, guild: discord.Guild, message_id: int, announce: bool = True
    ) -> Tuple[Dict[str, Any], List[discord.Member]]:
        lock = self._get_lock(guild.id, message_id)
        async with lock:
            giveaways = await self.config.guild(guild).giveaways()
            key = str(message_id)
            record = giveaways.get(key)
            if record is None:
                raise commands.BadArgument("No giveaway with that message ID was found in this server.")
            if record.get("status") != "active":
                raise commands.CommandError("That giveaway is not active.")

            message = await self._fetch_giveaway_message(guild, record)
            entrants = await self._get_entrants(message) if message is not None else []
            winners = self._pick_winners(entrants, int(record.get("winner_count", 1)))

            record["status"] = "ended"
            record["ended_at"] = self._now_ts()
            record["entry_count"] = len(entrants)
            record["winner_ids"] = [winner.id for winner in winners]

            async with self.config.guild(guild).giveaways() as stored_giveaways:
                stored_giveaways[key] = record

            await self._edit_giveaway_message(guild, record)

            channel = self._get_text_channel(guild, int(record["channel_id"]))
            if announce and channel is not None:
                allowed_mentions = discord.AllowedMentions(users=True, roles=False, everyone=False)
                if winners:
                    mentions = ", ".join(winner.mention for winner in winners)
                    await channel.send(
                        f"Congratulations {mentions}! You won **{record['prize']}**.",
                        allowed_mentions=allowed_mentions,
                    )
                else:
                    await channel.send(
                        f"The giveaway for **{record['prize']}** ended with no valid entries."
                    )

            return record, winners

    async def _cancel_giveaway(self, guild: discord.Guild, message_id: int) -> Dict[str, Any]:
        lock = self._get_lock(guild.id, message_id)
        async with lock:
            giveaways = await self.config.guild(guild).giveaways()
            key = str(message_id)
            record = giveaways.get(key)
            if record is None:
                raise commands.BadArgument("No giveaway with that message ID was found in this server.")
            if record.get("status") != "active":
                raise commands.CommandError("Only active giveaways can be cancelled.")

            message = await self._fetch_giveaway_message(guild, record)
            entrants = await self._get_entrants(message) if message is not None else []

            record["status"] = "cancelled"
            record["ended_at"] = self._now_ts()
            record["entry_count"] = len(entrants)
            record["winner_ids"] = []

            async with self.config.guild(guild).giveaways() as stored_giveaways:
                stored_giveaways[key] = record

            await self._edit_giveaway_message(guild, record)
            return record

    async def _reroll_giveaway(
        self, guild: discord.Guild, message_id: int, winner_count: int
    ) -> Tuple[Dict[str, Any], List[discord.Member]]:
        lock = self._get_lock(guild.id, message_id)
        async with lock:
            giveaways = await self.config.guild(guild).giveaways()
            key = str(message_id)
            record = giveaways.get(key)
            if record is None:
                raise commands.BadArgument("No giveaway with that message ID was found in this server.")
            if record.get("status") != "ended":
                raise commands.CommandError("Only ended giveaways can be rerolled.")

            message = await self._fetch_giveaway_message(guild, record)
            if message is None:
                raise commands.CommandError(
                    "I couldn't fetch the giveaway message, so I can't reroll the entrants."
                )

            entrants = await self._get_entrants(message)
            winners = self._pick_winners(
                entrants,
                winner_count,
                excluded_ids=set(record.get("winner_ids", [])),
            )
            if not winners:
                raise commands.CommandError("No new eligible entrants are available for a reroll.")

            record["winner_count"] = winner_count
            record["winner_ids"] = [winner.id for winner in winners]
            record["entry_count"] = len(entrants)
            record["ended_at"] = self._now_ts()

            async with self.config.guild(guild).giveaways() as stored_giveaways:
                stored_giveaways[key] = record

            await self._edit_giveaway_message(guild, record)
            return record, winners

    @commands.group(name="giveaway", aliases=["gaw"], invoke_without_command=True)
    @commands.guild_only()
    async def giveaway(self, ctx: commands.Context) -> None:
        """Create and manage giveaways."""
        await ctx.send_help(ctx.command)

    @giveaway.command(name="start")
    @commands.guild_only()
    @commands.admin_or_permissions(manage_guild=True)
    async def giveaway_start(
        self,
        ctx: commands.Context,
        duration: str,
        winner_count: int,
        *,
        prize: str,
    ) -> None:
        """Start a giveaway in the current channel."""
        if not isinstance(ctx.channel, discord.TextChannel):
            raise commands.CommandError("Giveaways can only be started in standard text channels.")

        self._ensure_winner_count(winner_count)
        duration_seconds = self._parse_duration(duration)
        prize = prize.strip()
        if not prize:
            raise commands.BadArgument("Prize text cannot be empty.")

        me = ctx.guild.me or ctx.guild.get_member(self.bot.user.id)
        self._validate_channel_permissions(ctx.channel, me)

        ends_at = self._now_ts() + duration_seconds
        record: Dict[str, Any] = {
            "message_id": 0,
            "channel_id": ctx.channel.id,
            "prize": prize,
            "winner_count": winner_count,
            "host_id": ctx.author.id,
            "ends_at": ends_at,
            "status": "active",
            "winner_ids": [],
            "ended_at": None,
            "entry_count": 0,
        }

        giveaway_message = await ctx.channel.send(
            embed=self._build_giveaway_embed(record),
            allowed_mentions=discord.AllowedMentions.none(),
        )
        try:
            await giveaway_message.add_reaction(self.REACTION_EMOJI)
        except discord.HTTPException as exc:
            try:
                await giveaway_message.delete()
            except discord.HTTPException:
                pass
            raise commands.CommandError(
                "I couldn't add the giveaway reaction. Check my `Add Reactions` permission."
            ) from exc

        record["message_id"] = giveaway_message.id
        async with self.config.guild(ctx.guild).giveaways() as giveaways:
            giveaways[str(giveaway_message.id)] = record

        duration_text = humanize_timedelta(seconds=duration_seconds) or f"{duration_seconds} seconds"
        await ctx.send(
            f"Giveaway started in {ctx.channel.mention} for **{prize}**. "
            f"It ends in {duration_text}. Message ID: `{giveaway_message.id}`"
        )

    @giveaway.command(name="startin")
    @commands.guild_only()
    @commands.admin_or_permissions(manage_guild=True)
    async def giveaway_start_in(
        self,
        ctx: commands.Context,
        channel: discord.TextChannel,
        duration: str,
        winner_count: int,
        *,
        prize: str,
    ) -> None:
        """Start a giveaway in a specific text channel."""
        self._ensure_winner_count(winner_count)
        duration_seconds = self._parse_duration(duration)
        prize = prize.strip()
        if not prize:
            raise commands.BadArgument("Prize text cannot be empty.")

        me = ctx.guild.me or ctx.guild.get_member(self.bot.user.id)
        self._validate_channel_permissions(channel, me)

        ends_at = self._now_ts() + duration_seconds
        record: Dict[str, Any] = {
            "message_id": 0,
            "channel_id": channel.id,
            "prize": prize,
            "winner_count": winner_count,
            "host_id": ctx.author.id,
            "ends_at": ends_at,
            "status": "active",
            "winner_ids": [],
            "ended_at": None,
            "entry_count": 0,
        }

        giveaway_message = await channel.send(
            embed=self._build_giveaway_embed(record),
            allowed_mentions=discord.AllowedMentions.none(),
        )
        try:
            await giveaway_message.add_reaction(self.REACTION_EMOJI)
        except discord.HTTPException as exc:
            try:
                await giveaway_message.delete()
            except discord.HTTPException:
                pass
            raise commands.CommandError(
                "I couldn't add the giveaway reaction. Check my `Add Reactions` permission."
            ) from exc

        record["message_id"] = giveaway_message.id
        async with self.config.guild(ctx.guild).giveaways() as giveaways:
            giveaways[str(giveaway_message.id)] = record

        duration_text = humanize_timedelta(seconds=duration_seconds) or f"{duration_seconds} seconds"
        await ctx.send(
            f"Giveaway started in {channel.mention} for **{prize}**. "
            f"It ends in {duration_text}. Message ID: `{giveaway_message.id}`"
        )

    @giveaway.command(name="end")
    @commands.guild_only()
    @commands.admin_or_permissions(manage_guild=True)
    async def giveaway_end(self, ctx: commands.Context, reference: str) -> None:
        """End an active giveaway immediately."""
        key, _record = await self._get_record_from_reference(ctx.guild, reference)
        record, winners = await self._end_giveaway(ctx.guild, int(key))
        if winners:
            winner_text = ", ".join(winner.mention for winner in winners)
            await ctx.send(f"Giveaway ended. Winner(s): {winner_text}")
        else:
            await ctx.send("Giveaway ended. No valid entries were found.")

        jump_url = self._build_jump_url(ctx.guild.id, int(record["channel_id"]), int(record["message_id"]))
        await ctx.send(f"Updated giveaway message: {jump_url}")

    @giveaway.command(name="cancel")
    @commands.guild_only()
    @commands.admin_or_permissions(manage_guild=True)
    async def giveaway_cancel(self, ctx: commands.Context, reference: str) -> None:
        """Cancel an active giveaway without picking winners."""
        key, _record = await self._get_record_from_reference(ctx.guild, reference)
        record = await self._cancel_giveaway(ctx.guild, int(key))
        jump_url = self._build_jump_url(ctx.guild.id, int(record["channel_id"]), int(record["message_id"]))
        await ctx.send(f"Giveaway cancelled. Updated message: {jump_url}")

    @giveaway.command(name="reroll")
    @commands.guild_only()
    @commands.admin_or_permissions(manage_guild=True)
    async def giveaway_reroll(
        self, ctx: commands.Context, reference: str, winner_count: Optional[int] = None
    ) -> None:
        """Pick a new winner from an ended giveaway."""
        key, record = await self._get_record_from_reference(ctx.guild, reference)
        winner_count = winner_count or int(record.get("winner_count", 1))
        self._ensure_winner_count(winner_count)

        updated_record, winners = await self._reroll_giveaway(ctx.guild, int(key), winner_count)
        channel = self._get_text_channel(ctx.guild, int(updated_record["channel_id"]))
        winner_text = ", ".join(winner.mention for winner in winners)
        if channel is not None:
            await channel.send(
                f"Reroll result for **{updated_record['prize']}**: {winner_text}",
                allowed_mentions=discord.AllowedMentions(users=True, roles=False, everyone=False),
            )

        await ctx.send(f"Rerolled winner(s): {winner_text}")

    @giveaway.command(name="list")
    @commands.guild_only()
    async def giveaway_list(self, ctx: commands.Context) -> None:
        """List all active giveaways in this server."""
        giveaways = await self.config.guild(ctx.guild).giveaways()
        active_records = [
            record for record in giveaways.values() if record.get("status") == "active"
        ]
        if not active_records:
            await ctx.send("There are no active giveaways in this server.")
            return

        active_records.sort(key=lambda record: float(record.get("ends_at", 0)))
        lines = []
        for record in active_records:
            channel = self._get_text_channel(ctx.guild, int(record["channel_id"]))
            channel_text = channel.mention if channel is not None else f"<#{record['channel_id']}>"
            end_time = datetime.fromtimestamp(float(record["ends_at"]), tz=timezone.utc)
            jump_url = self._build_jump_url(
                ctx.guild.id, int(record["channel_id"]), int(record["message_id"])
            )
            lines.append(
                f"`{record['message_id']}` | {self._shorten(record['prize'], 80)} | "
                f"{channel_text} | ends {discord.utils.format_dt(end_time, 'R')} | {jump_url}"
            )

        for page in pagify("\n".join(lines), page_length=1800):
            await ctx.send(page)
