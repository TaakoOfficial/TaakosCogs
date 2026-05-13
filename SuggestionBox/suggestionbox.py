"""Suggestion box cog for Red-DiscordBot."""

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

log = logging.getLogger("red.taakoscogs.suggestionbox")


SuggestionRecord = Dict[str, Any]


class SuggestionVoteView(discord.ui.View):
    """Persistent voting buttons for suggestion messages."""

    def __init__(self, cog: "SuggestionBox") -> None:
        super().__init__(timeout=None)
        self.cog = cog

    @discord.ui.button(
        label="Upvote",
        style=discord.ButtonStyle.success,
        custom_id="taakoscogs:suggestionbox:upvote",
    )
    async def upvote(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ) -> None:
        await self.cog.handle_vote(interaction, "up")

    @discord.ui.button(
        label="Downvote",
        style=discord.ButtonStyle.danger,
        custom_id="taakoscogs:suggestionbox:downvote",
    )
    async def downvote(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ) -> None:
        await self.cog.handle_vote(interaction, "down")


class SuggestionBox(commands.Cog):
    """Collect, vote on, review, and export community suggestions."""

    CONFIG_IDENTIFIER = 2026051303
    DEFAULT_COLOR = 0x5865F2
    STATUS_COLORS = {
        "open": 0x5865F2,
        "considering": 0xFEE75C,
        "approved": 0x57F287,
        "denied": 0xED4245,
        "implemented": 0x3BA55D,
        "closed": 0x747F8D,
    }
    STATUS_LABELS = {
        "open": "Open",
        "considering": "Considering",
        "approved": "Approved",
        "denied": "Denied",
        "implemented": "Implemented",
        "closed": "Closed",
    }
    VALID_STATUSES = set(STATUS_LABELS)
    MAX_SUGGESTION_LENGTH = 1800
    MAX_REASON_LENGTH = 700
    MAX_COMMENT_LENGTH = 700

    def __init__(self, bot: Red) -> None:
        self.bot = bot
        self.config = Config.get_conf(
            self,
            identifier=self.CONFIG_IDENTIFIER,
            force_registration=True,
        )
        self.config.register_guild(
            enabled=False,
            suggestion_channel_id=None,
            review_channel_id=None,
            anonymous=False,
            allow_downvotes=True,
            allow_self_vote=False,
            embed_color=self.DEFAULT_COLOR,
            next_id=1,
            suggestions={},
        )
        self._locks: Dict[int, asyncio.Lock] = {}
        self._vote_view = SuggestionVoteView(self)

    async def cog_load(self) -> None:
        """Register persistent button callbacks."""
        self.bot.add_view(self._vote_view)

    async def red_delete_data_for_user(self, *, requester: str, user_id: int) -> None:
        """Delete stored suggestion data associated with a Discord user ID."""
        user_key = str(user_id)
        all_guilds = await self.config.all_guilds()
        for guild_id in all_guilds:
            async with self.config.guild_from_id(guild_id).suggestions() as suggestions:
                for record in suggestions.values():
                    if str(record.get("author_id")) == user_key:
                        record["author_id"] = None
                        record["author_removed"] = True
                        record["text"] = "[deleted by data request]"
                        record["status"] = "closed"
                        record["updated_at"] = self._now_ts()
                    record["upvotes"] = [
                        voter for voter in record.get("upvotes", []) if str(voter) != user_key
                    ]
                    record["downvotes"] = [
                        voter for voter in record.get("downvotes", []) if str(voter) != user_key
                    ]
                    if str(record.get("decision_by")) == user_key:
                        record["decision_by"] = None
                    record["staff_notes"] = [
                        note
                        for note in record.get("staff_notes", [])
                        if str(note.get("staff_id")) != user_key
                    ]

    def _guild_lock(self, guild_id: int) -> asyncio.Lock:
        return self._locks.setdefault(guild_id, asyncio.Lock())

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
    def _clean_text(value: str, limit: int) -> str:
        cleaned = " ".join(value.strip().split())
        if not cleaned:
            raise commands.BadArgument("Provide text.")
        if len(cleaned) > limit:
            raise commands.BadArgument(f"Text must be {limit} characters or fewer.")
        return cleaned

    @classmethod
    def _normalise_status(cls, status: str) -> str:
        normalized = status.strip().lower()
        aliases = {
            "pending": "open",
            "review": "considering",
            "accepted": "approved",
            "reject": "denied",
            "rejected": "denied",
            "done": "implemented",
            "complete": "implemented",
        }
        normalized = aliases.get(normalized, normalized)
        if normalized not in cls.VALID_STATUSES:
            raise commands.BadArgument(
                "Status must be one of: " + ", ".join(sorted(cls.VALID_STATUSES))
            )
        return normalized

    @classmethod
    def _status_label(cls, status: str) -> str:
        return cls.STATUS_LABELS.get(status, status.title())

    @staticmethod
    def _suggestion_key(suggestion_id: int) -> str:
        return str(int(suggestion_id))

    @classmethod
    def _score(cls, record: SuggestionRecord) -> int:
        return len(record.get("upvotes", [])) - len(record.get("downvotes", []))

    @classmethod
    def _vote_text(cls, record: SuggestionRecord, allow_downvotes: bool) -> str:
        upvotes = len(record.get("upvotes", []))
        downvotes = len(record.get("downvotes", [])) if allow_downvotes else 0
        if allow_downvotes:
            return (
                f"Upvotes: **{cls._count(upvotes)}**\n"
                f"Downvotes: **{cls._count(downvotes)}**\n"
                f"Score: **{cls._count(upvotes - downvotes)}**"
            )
        return f"Upvotes: **{cls._count(upvotes)}**"

    def _record_embed(
        self,
        guild: discord.Guild,
        record: SuggestionRecord,
        settings: Dict[str, Any],
    ) -> discord.Embed:
        status = str(record.get("status") or "open")
        color = self.STATUS_COLORS.get(status, int(settings.get("embed_color") or self.DEFAULT_COLOR))
        if status == "open":
            color = int(settings.get("embed_color") or self.DEFAULT_COLOR)

        suggestion_id = int(record.get("id") or 0)
        embed = discord.Embed(
            title=f"Suggestion #{suggestion_id}",
            description=str(record.get("text") or ""),
            color=color,
            timestamp=self._now(),
        )
        if guild.icon:
            embed.set_author(name=guild.name, icon_url=guild.icon.url)
        else:
            embed.set_author(name=guild.name)

        embed.add_field(name="Status", value=self._status_label(status), inline=True)
        embed.add_field(
            name="Votes",
            value=self._vote_text(record, bool(settings.get("allow_downvotes"))),
            inline=True,
        )
        if not settings.get("anonymous") or record.get("author_removed"):
            author_text = self._user_ref(record.get("author_id"))
            if record.get("author_removed"):
                author_text = "Deleted user"
            embed.add_field(name="Author", value=author_text, inline=True)
        else:
            embed.add_field(name="Author", value="Anonymous", inline=True)

        embed.add_field(name="Submitted", value=self._format_ts(record.get("created_at"), "R"), inline=True)
        updated_at = record.get("updated_at")
        if updated_at:
            embed.add_field(name="Updated", value=self._format_ts(updated_at, "R"), inline=True)

        decision_reason = record.get("decision_reason")
        if decision_reason:
            decision_by = self._user_ref(record.get("decision_by"))
            decision_at = self._format_ts(record.get("decision_at"), "R")
            embed.add_field(
                name="Staff Decision",
                value=f"{decision_reason}\nBy: {decision_by}\nWhen: {decision_at}",
                inline=False,
            )

        notes = record.get("staff_notes", [])[-3:]
        if notes:
            lines = []
            for note in notes:
                staff = self._user_ref(note.get("staff_id"))
                when = self._format_ts(note.get("created_at"), "R")
                lines.append(f"{when} by {staff}: {note.get('comment')}")
            embed.add_field(name="Staff Notes", value="\n".join(lines)[:1024], inline=False)

        embed.set_footer(text=f"Suggestion ID: {suggestion_id}")
        return embed

    async def _get_suggestion_channel(
        self,
        guild: discord.Guild,
        settings: Optional[Dict[str, Any]] = None,
    ) -> Optional[discord.TextChannel]:
        settings = settings or await self.config.guild(guild).all()
        channel_id = settings.get("suggestion_channel_id")
        if not channel_id:
            return None
        channel = guild.get_channel(int(channel_id))
        return channel if isinstance(channel, discord.TextChannel) else None

    async def _get_review_channel(
        self,
        guild: discord.Guild,
        settings: Optional[Dict[str, Any]] = None,
    ) -> Optional[discord.TextChannel]:
        settings = settings or await self.config.guild(guild).all()
        channel_id = settings.get("review_channel_id")
        if not channel_id:
            return None
        channel = guild.get_channel(int(channel_id))
        return channel if isinstance(channel, discord.TextChannel) else None

    async def _fetch_suggestion_message(
        self,
        guild: discord.Guild,
        record: SuggestionRecord,
    ) -> Optional[discord.Message]:
        channel_id = record.get("channel_id")
        message_id = record.get("message_id")
        if not channel_id or not message_id:
            return None
        channel = guild.get_channel(int(channel_id))
        if not isinstance(channel, discord.TextChannel):
            return None
        try:
            return await channel.fetch_message(int(message_id))
        except (discord.NotFound, discord.Forbidden, discord.HTTPException):
            return None

    def _view_for_record(self, record: SuggestionRecord) -> Optional[discord.ui.View]:
        if str(record.get("status") or "open") != "open":
            return None
        return self._vote_view

    async def _sync_suggestion_message(
        self,
        guild: discord.Guild,
        record: SuggestionRecord,
        settings: Optional[Dict[str, Any]] = None,
    ) -> None:
        settings = settings or await self.config.guild(guild).all()
        message = await self._fetch_suggestion_message(guild, record)
        if message is None:
            return
        embed = self._record_embed(guild, record, settings)
        try:
            await message.edit(embed=embed, view=self._view_for_record(record))
        except discord.HTTPException:
            log.exception("Failed to update suggestion %s in guild %s", record.get("id"), guild.id)

    async def _send_review_log(
        self,
        guild: discord.Guild,
        record: SuggestionRecord,
        action: str,
        actor: Optional[discord.abc.User],
        reason: Optional[str] = None,
    ) -> None:
        settings = await self.config.guild(guild).all()
        channel = await self._get_review_channel(guild, settings)
        if channel is None:
            return

        me = guild.me
        if me is None:
            return
        permissions = channel.permissions_for(me)
        if not permissions.send_messages or not permissions.embed_links:
            return

        embed = discord.Embed(
            title=f"Suggestion {action}",
            description=f"Suggestion #{record.get('id')}",
            color=self.STATUS_COLORS.get(str(record.get("status")), self.DEFAULT_COLOR),
            timestamp=self._now(),
        )
        embed.add_field(name="Status", value=self._status_label(str(record.get("status"))), inline=True)
        embed.add_field(name="Author", value=self._user_ref(record.get("author_id")), inline=True)
        embed.add_field(name="Actor", value=actor.mention if actor else "System", inline=True)
        if reason:
            embed.add_field(name="Reason", value=reason[:1024], inline=False)
        message_id = record.get("message_id")
        channel_id = record.get("channel_id")
        if message_id and channel_id:
            embed.add_field(
                name="Message",
                value=f"https://discord.com/channels/{guild.id}/{channel_id}/{message_id}",
                inline=False,
            )

        try:
            await channel.send(embed=embed, allowed_mentions=discord.AllowedMentions.none())
        except discord.HTTPException:
            log.exception("Failed to send suggestion review log in guild %s", guild.id)

    async def _get_record(self, guild: discord.Guild, suggestion_id: int) -> SuggestionRecord:
        suggestions = await self.config.guild(guild).suggestions()
        record = suggestions.get(self._suggestion_key(suggestion_id))
        if not record:
            raise commands.BadArgument(f"No suggestion with ID `{suggestion_id}` was found.")
        return record

    async def _find_record_by_message(
        self,
        guild: discord.Guild,
        message_id: int,
    ) -> Tuple[str, SuggestionRecord]:
        suggestions = await self.config.guild(guild).suggestions()
        for key, record in suggestions.items():
            if int(record.get("message_id") or 0) == int(message_id):
                return key, record
        raise commands.BadArgument("That message is not a tracked suggestion.")

    async def handle_vote(self, interaction: discord.Interaction, vote_type: str) -> None:
        """Handle a persistent button vote."""
        if not interaction.guild or not interaction.message:
            await interaction.response.send_message("This button only works in a server.", ephemeral=True)
            return

        user = interaction.user
        if user is None or user.bot:
            await interaction.response.send_message("Bot votes are ignored.", ephemeral=True)
            return

        guild = interaction.guild
        async with self._guild_lock(guild.id):
            settings = await self.config.guild(guild).all()
            if not settings.get("enabled"):
                await interaction.response.send_message("Suggestion voting is disabled.", ephemeral=True)
                return
            if vote_type == "down" and not settings.get("allow_downvotes"):
                await interaction.response.send_message("Downvotes are disabled here.", ephemeral=True)
                return

            try:
                suggestion_key, record = await self._find_record_by_message(guild, interaction.message.id)
            except commands.BadArgument:
                await interaction.response.send_message("This suggestion is no longer tracked.", ephemeral=True)
                return

            if str(record.get("status") or "open") != "open":
                await interaction.response.send_message("Voting is closed for this suggestion.", ephemeral=True)
                return
            if not settings.get("allow_self_vote") and str(record.get("author_id")) == str(user.id):
                await interaction.response.send_message("You cannot vote on your own suggestion.", ephemeral=True)
                return

            upvotes = {str(voter) for voter in record.get("upvotes", [])}
            downvotes = {str(voter) for voter in record.get("downvotes", [])}
            voter_key = str(user.id)

            if vote_type == "up":
                if voter_key in upvotes:
                    upvotes.remove(voter_key)
                    message = "Your upvote was removed."
                else:
                    upvotes.add(voter_key)
                    downvotes.discard(voter_key)
                    message = "Your upvote was counted."
            else:
                if voter_key in downvotes:
                    downvotes.remove(voter_key)
                    message = "Your downvote was removed."
                else:
                    downvotes.add(voter_key)
                    upvotes.discard(voter_key)
                    message = "Your downvote was counted."

            record["upvotes"] = sorted(upvotes)
            record["downvotes"] = sorted(downvotes)
            record["updated_at"] = self._now_ts()

            async with self.config.guild(guild).suggestions() as suggestions:
                suggestions[suggestion_key] = record

            embed = self._record_embed(guild, record, settings)
            await interaction.response.edit_message(embed=embed, view=self._vote_view)
            try:
                await interaction.followup.send(message, ephemeral=True)
            except discord.HTTPException:
                pass

    async def _submit_suggestion(
        self,
        guild: discord.Guild,
        author: discord.abc.User,
        suggestion_text: str,
    ) -> Tuple[SuggestionRecord, discord.Message]:
        settings = await self.config.guild(guild).all()
        if not settings.get("enabled"):
            raise commands.CommandError("SuggestionBox is not enabled yet.")

        channel = await self._get_suggestion_channel(guild, settings)
        if channel is None:
            raise commands.CommandError("No suggestion channel is configured.")

        me = guild.me
        if me is None:
            raise commands.CommandError("I could not inspect my server permissions.")
        permissions = channel.permissions_for(me)
        if not permissions.send_messages or not permissions.embed_links:
            raise commands.CommandError(
                f"I need `Send Messages` and `Embed Links` in {channel.mention}."
            )

        suggestion_text = self._clean_text(suggestion_text, self.MAX_SUGGESTION_LENGTH)
        async with self._guild_lock(guild.id):
            next_id = int(await self.config.guild(guild).next_id())
            record: SuggestionRecord = {
                "id": next_id,
                "author_id": author.id,
                "text": suggestion_text,
                "status": "open",
                "channel_id": channel.id,
                "message_id": None,
                "created_at": self._now_ts(),
                "updated_at": None,
                "upvotes": [],
                "downvotes": [],
                "decision_by": None,
                "decision_reason": None,
                "decision_at": None,
                "staff_notes": [],
            }

            embed = self._record_embed(guild, record, settings)
            message = await channel.send(embed=embed, view=self._vote_view)
            record["message_id"] = message.id

            async with self.config.guild(guild).suggestions() as suggestions:
                suggestions[self._suggestion_key(next_id)] = record
            await self.config.guild(guild).next_id.set(next_id + 1)

        await self._sync_suggestion_message(guild, record, settings)
        await self._send_review_log(guild, record, "Submitted", author)
        return record, message

    async def _send_settings(self, ctx: commands.Context) -> None:
        assert ctx.guild is not None
        settings = await self.config.guild(ctx.guild).all()
        suggestion_channel = await self._get_suggestion_channel(ctx.guild, settings)
        review_channel = await self._get_review_channel(ctx.guild, settings)
        suggestions = settings.get("suggestions") or {}
        status_counts = {status: 0 for status in self.VALID_STATUSES}
        for record in suggestions.values():
            status = str(record.get("status") or "open")
            status_counts[status] = status_counts.get(status, 0) + 1

        embed = discord.Embed(
            title="SuggestionBox Settings",
            color=int(settings.get("embed_color") or self.DEFAULT_COLOR),
            timestamp=self._now(),
        )
        embed.add_field(
            name="Status",
            value=(
                f"Enabled: **{'Yes' if settings.get('enabled') else 'No'}**\n"
                f"Suggestion channel: {suggestion_channel.mention if suggestion_channel else 'Not set'}\n"
                f"Review channel: {review_channel.mention if review_channel else 'Not set'}"
            ),
            inline=False,
        )
        embed.add_field(
            name="Options",
            value=(
                f"Anonymous: **{'Yes' if settings.get('anonymous') else 'No'}**\n"
                f"Downvotes: **{'Yes' if settings.get('allow_downvotes') else 'No'}**\n"
                f"Self voting: **{'Yes' if settings.get('allow_self_vote') else 'No'}**"
            ),
            inline=True,
        )
        embed.add_field(
            name="Suggestions",
            value=(
                f"Total: **{self._count(len(suggestions))}**\n"
                f"Open: **{self._count(status_counts.get('open', 0))}**\n"
                f"Approved: **{self._count(status_counts.get('approved', 0))}**\n"
                f"Implemented: **{self._count(status_counts.get('implemented', 0))}**"
            ),
            inline=True,
        )
        await ctx.send(embed=embed)

    @commands.command(name="suggest")
    @commands.guild_only()
    async def suggest(self, ctx: commands.Context, *, suggestion: str) -> None:
        """Submit a suggestion."""
        assert ctx.guild is not None
        try:
            record, message = await self._submit_suggestion(ctx.guild, ctx.author, suggestion)
        except commands.CommandError as error:
            await ctx.send(str(error))
            return

        await ctx.send(f"Suggestion #{record['id']} submitted: {message.jump_url}")

    @commands.group(name="suggestionbox", aliases=["suggestionset"], invoke_without_command=True)
    @commands.guild_only()
    @commands.bot_has_permissions(embed_links=True)
    async def suggestionbox(self, ctx: commands.Context) -> None:
        """Configure the server suggestion box."""
        await self._send_settings(ctx)

    @suggestionbox.command(name="setup")
    @commands.admin_or_permissions(manage_guild=True)
    async def suggestionbox_setup(
        self,
        ctx: commands.Context,
        suggestion_channel: Optional[discord.TextChannel] = None,
        review_channel: Optional[discord.TextChannel] = None,
    ) -> None:
        """Enable suggestions and set the suggestion and optional review channels."""
        assert ctx.guild is not None
        if suggestion_channel is None:
            if not isinstance(ctx.channel, discord.TextChannel):
                await ctx.send("Run this in a text channel or provide a suggestion channel.")
                return
            suggestion_channel = ctx.channel

        await self.config.guild(ctx.guild).suggestion_channel_id.set(suggestion_channel.id)
        await self.config.guild(ctx.guild).review_channel_id.set(review_channel.id if review_channel else None)
        await self.config.guild(ctx.guild).enabled.set(True)
        review_text = f" Review logs will post in {review_channel.mention}." if review_channel else ""
        await ctx.send(f"SuggestionBox is enabled in {suggestion_channel.mention}.{review_text}")

    @suggestionbox.command(name="enable")
    @commands.admin_or_permissions(manage_guild=True)
    async def suggestionbox_enable(self, ctx: commands.Context, enabled: bool = True) -> None:
        """Enable or disable suggestion submissions and voting."""
        assert ctx.guild is not None
        await self.config.guild(ctx.guild).enabled.set(enabled)
        await ctx.send(f"SuggestionBox is now {'enabled' if enabled else 'disabled'}.")

    @suggestionbox.command(name="disable")
    @commands.admin_or_permissions(manage_guild=True)
    async def suggestionbox_disable(self, ctx: commands.Context) -> None:
        """Disable suggestion submissions and voting."""
        assert ctx.guild is not None
        await self.config.guild(ctx.guild).enabled.set(False)
        await ctx.send("SuggestionBox is now disabled.")

    @suggestionbox.command(name="channel")
    @commands.admin_or_permissions(manage_guild=True)
    async def suggestionbox_channel(
        self,
        ctx: commands.Context,
        channel: Optional[discord.TextChannel] = None,
    ) -> None:
        """Set the suggestion channel. Omit the channel to use the current channel."""
        assert ctx.guild is not None
        if channel is None:
            if not isinstance(ctx.channel, discord.TextChannel):
                await ctx.send("Run this in a text channel or provide a suggestion channel.")
                return
            channel = ctx.channel
        await self.config.guild(ctx.guild).suggestion_channel_id.set(channel.id)
        await ctx.send(f"Suggestion channel set to {channel.mention}.")

    @suggestionbox.command(name="reviewchannel")
    @commands.admin_or_permissions(manage_guild=True)
    async def suggestionbox_review_channel(
        self,
        ctx: commands.Context,
        channel: Optional[discord.TextChannel] = None,
    ) -> None:
        """Set the staff review log channel. Omit the channel to use the current channel."""
        assert ctx.guild is not None
        if channel is None:
            if not isinstance(ctx.channel, discord.TextChannel):
                await ctx.send("Run this in a text channel or provide a review channel.")
                return
            channel = ctx.channel
        await self.config.guild(ctx.guild).review_channel_id.set(channel.id)
        await ctx.send(f"Suggestion review logs will post in {channel.mention}.")

    @suggestionbox.command(name="clearreview")
    @commands.admin_or_permissions(manage_guild=True)
    async def suggestionbox_clear_review(self, ctx: commands.Context) -> None:
        """Clear the staff review log channel."""
        assert ctx.guild is not None
        await self.config.guild(ctx.guild).review_channel_id.set(None)
        await ctx.send("Suggestion review channel cleared.")

    @suggestionbox.command(name="anonymous")
    @commands.admin_or_permissions(manage_guild=True)
    async def suggestionbox_anonymous(self, ctx: commands.Context, enabled: bool) -> None:
        """Choose whether suggestion embeds hide authors."""
        assert ctx.guild is not None
        await self.config.guild(ctx.guild).anonymous.set(enabled)
        await ctx.send(f"Anonymous suggestions are now {'enabled' if enabled else 'disabled'}.")

    @suggestionbox.command(name="downvotes")
    @commands.admin_or_permissions(manage_guild=True)
    async def suggestionbox_downvotes(self, ctx: commands.Context, enabled: bool) -> None:
        """Choose whether downvotes are allowed."""
        assert ctx.guild is not None
        await self.config.guild(ctx.guild).allow_downvotes.set(enabled)
        await ctx.send(f"Downvotes are now {'enabled' if enabled else 'disabled'}.")

    @suggestionbox.command(name="selfvote")
    @commands.admin_or_permissions(manage_guild=True)
    async def suggestionbox_self_vote(self, ctx: commands.Context, enabled: bool) -> None:
        """Choose whether authors can vote on their own suggestions."""
        assert ctx.guild is not None
        await self.config.guild(ctx.guild).allow_self_vote.set(enabled)
        await ctx.send(f"Self voting is now {'enabled' if enabled else 'disabled'}.")

    @suggestionbox.command(name="color")
    @commands.admin_or_permissions(manage_guild=True)
    async def suggestionbox_color(
        self,
        ctx: commands.Context,
        color: Optional[discord.Color] = None,
    ) -> None:
        """Set the open suggestion embed color, or omit a color to reset it."""
        assert ctx.guild is not None
        await self.config.guild(ctx.guild).embed_color.set(color.value if color else self.DEFAULT_COLOR)
        await ctx.tick()

    @suggestionbox.command(name="reset")
    @commands.admin_or_permissions(manage_guild=True)
    async def suggestionbox_reset(self, ctx: commands.Context, confirmation: str = "") -> None:
        """Clear all stored suggestion records. Use `confirm` to proceed."""
        assert ctx.guild is not None
        if confirmation.lower() != "confirm":
            await ctx.send("This clears all stored suggestion records. Run again with `confirm`.")
            return
        await self.config.guild(ctx.guild).suggestions.set({})
        await self.config.guild(ctx.guild).next_id.set(1)
        await ctx.send("SuggestionBox records have been reset.")

    @suggestionbox.command(name="refresh")
    @commands.admin_or_permissions(manage_guild=True)
    @commands.bot_has_permissions(embed_links=True)
    async def suggestionbox_refresh(self, ctx: commands.Context) -> None:
        """Refresh all tracked suggestion messages from stored records."""
        assert ctx.guild is not None
        settings = await self.config.guild(ctx.guild).all()
        suggestions = settings.get("suggestions") or {}
        count = 0
        for record in suggestions.values():
            await self._sync_suggestion_message(ctx.guild, record, settings)
            count += 1
        await ctx.send(f"Refreshed **{self._count(count)}** suggestion message(s).")

    @suggestionbox.command(name="settings")
    @commands.bot_has_permissions(embed_links=True)
    async def suggestionbox_settings(self, ctx: commands.Context) -> None:
        """Show current SuggestionBox settings."""
        await self._send_settings(ctx)

    @commands.group(name="suggestions", aliases=["sbox"], invoke_without_command=True)
    @commands.guild_only()
    async def suggestions_group(self, ctx: commands.Context) -> None:
        """View and manage suggestions."""
        await ctx.send_help(ctx.command)

    @suggestions_group.command(name="info")
    @commands.bot_has_permissions(embed_links=True)
    async def suggestions_info(self, ctx: commands.Context, suggestion_id: int) -> None:
        """Show a suggestion by ID."""
        assert ctx.guild is not None
        try:
            record = await self._get_record(ctx.guild, suggestion_id)
        except commands.BadArgument as error:
            await ctx.send(str(error))
            return
        settings = await self.config.guild(ctx.guild).all()
        await ctx.send(embed=self._record_embed(ctx.guild, record, settings))

    @suggestions_group.command(name="list")
    async def suggestions_list(
        self,
        ctx: commands.Context,
        status: Optional[str] = "open",
        limit: int = 20,
    ) -> None:
        """List suggestions by status. Use `all` to show every status."""
        assert ctx.guild is not None
        limit = max(1, min(limit, 50))
        suggestions = await self.config.guild(ctx.guild).suggestions()
        if status and status.lower() != "all":
            try:
                normalized_status = self._normalise_status(status)
            except commands.BadArgument as error:
                await ctx.send(str(error))
                return
        else:
            normalized_status = None

        records = list(suggestions.values())
        if normalized_status:
            records = [
                record
                for record in records
                if str(record.get("status") or "open") == normalized_status
            ]
        records.sort(key=lambda record: int(record.get("id") or 0), reverse=True)
        records = records[:limit]
        if not records:
            await ctx.send("No suggestions matched that filter.")
            return

        lines = []
        for record in records:
            score = self._score(record)
            text = str(record.get("text") or "")
            if len(text) > 90:
                text = text[:87] + "..."
            lines.append(
                f"#{record.get('id')} | {self._status_label(str(record.get('status') or 'open'))} "
                f"| score {score} | {text}"
            )

        for page in pagify("\n".join(lines), page_length=1800):
            await ctx.send(box(page))

    @suggestions_group.command(name="mine")
    async def suggestions_mine(self, ctx: commands.Context, limit: int = 20) -> None:
        """List your submitted suggestions."""
        assert ctx.guild is not None
        limit = max(1, min(limit, 50))
        suggestions = await self.config.guild(ctx.guild).suggestions()
        records = [
            record for record in suggestions.values() if str(record.get("author_id")) == str(ctx.author.id)
        ]
        records.sort(key=lambda record: int(record.get("id") or 0), reverse=True)
        if not records:
            await ctx.send("You do not have any tracked suggestions in this server.")
            return

        lines = []
        for record in records[:limit]:
            text = str(record.get("text") or "")
            if len(text) > 90:
                text = text[:87] + "..."
            lines.append(
                f"#{record.get('id')} | {self._status_label(str(record.get('status') or 'open'))} "
                f"| score {self._score(record)} | {text}"
            )

        for page in pagify("\n".join(lines), page_length=1800):
            await ctx.send(box(page))

    @suggestions_group.command(name="stats")
    @commands.bot_has_permissions(embed_links=True)
    async def suggestions_stats(self, ctx: commands.Context) -> None:
        """Show suggestion totals by status."""
        assert ctx.guild is not None
        suggestions = await self.config.guild(ctx.guild).suggestions()
        counts = {status: 0 for status in self.VALID_STATUSES}
        top_record: Optional[SuggestionRecord] = None
        for record in suggestions.values():
            status = str(record.get("status") or "open")
            counts[status] = counts.get(status, 0) + 1
            if top_record is None or self._score(record) > self._score(top_record):
                top_record = record

        embed = discord.Embed(title="Suggestion Stats", color=self.DEFAULT_COLOR, timestamp=self._now())
        embed.add_field(name="Total", value=self._count(len(suggestions)), inline=True)
        for status in sorted(self.VALID_STATUSES):
            embed.add_field(name=self._status_label(status), value=self._count(counts.get(status, 0)), inline=True)
        if top_record:
            embed.add_field(
                name="Top Score",
                value=f"#{top_record.get('id')} with score **{self._count(self._score(top_record))}**",
                inline=False,
            )
        await ctx.send(embed=embed)

    async def _set_status(
        self,
        ctx: commands.Context,
        suggestion_id: int,
        status: str,
        reason: Optional[str] = None,
    ) -> None:
        assert ctx.guild is not None
        reason = self._clean_text(reason, self.MAX_REASON_LENGTH) if reason else None
        async with self._guild_lock(ctx.guild.id):
            async with self.config.guild(ctx.guild).suggestions() as suggestions:
                key = self._suggestion_key(suggestion_id)
                record = suggestions.get(key)
                if not record:
                    await ctx.send(f"No suggestion with ID `{suggestion_id}` was found.")
                    return
                record["status"] = status
                record["updated_at"] = self._now_ts()
                record["decision_by"] = ctx.author.id
                record["decision_reason"] = reason
                record["decision_at"] = self._now_ts()
                suggestions[key] = record

        settings = await self.config.guild(ctx.guild).all()
        await self._sync_suggestion_message(ctx.guild, record, settings)
        await self._send_review_log(ctx.guild, record, self._status_label(status), ctx.author, reason)
        await ctx.send(f"Suggestion #{suggestion_id} marked as {self._status_label(status)}.")

    @suggestions_group.command(name="approve")
    @commands.admin_or_permissions(manage_guild=True)
    async def suggestions_approve(
        self,
        ctx: commands.Context,
        suggestion_id: int,
        *,
        reason: Optional[str] = None,
    ) -> None:
        """Mark a suggestion as approved."""
        await self._set_status(ctx, suggestion_id, "approved", reason)

    @suggestions_group.command(name="deny")
    @commands.admin_or_permissions(manage_guild=True)
    async def suggestions_deny(
        self,
        ctx: commands.Context,
        suggestion_id: int,
        *,
        reason: Optional[str] = None,
    ) -> None:
        """Mark a suggestion as denied."""
        await self._set_status(ctx, suggestion_id, "denied", reason)

    @suggestions_group.command(name="consider")
    @commands.admin_or_permissions(manage_guild=True)
    async def suggestions_consider(
        self,
        ctx: commands.Context,
        suggestion_id: int,
        *,
        reason: Optional[str] = None,
    ) -> None:
        """Mark a suggestion as under consideration."""
        await self._set_status(ctx, suggestion_id, "considering", reason)

    @suggestions_group.command(name="implement")
    @commands.admin_or_permissions(manage_guild=True)
    async def suggestions_implement(
        self,
        ctx: commands.Context,
        suggestion_id: int,
        *,
        reason: Optional[str] = None,
    ) -> None:
        """Mark a suggestion as implemented."""
        await self._set_status(ctx, suggestion_id, "implemented", reason)

    @suggestions_group.command(name="close")
    @commands.admin_or_permissions(manage_guild=True)
    async def suggestions_close(
        self,
        ctx: commands.Context,
        suggestion_id: int,
        *,
        reason: Optional[str] = None,
    ) -> None:
        """Close a suggestion without approving or denying it."""
        await self._set_status(ctx, suggestion_id, "closed", reason)

    @suggestions_group.command(name="reopen")
    @commands.admin_or_permissions(manage_guild=True)
    async def suggestions_reopen(self, ctx: commands.Context, suggestion_id: int) -> None:
        """Reopen a suggestion for voting."""
        await self._set_status(ctx, suggestion_id, "open", None)

    @suggestions_group.command(name="comment")
    @commands.admin_or_permissions(manage_guild=True)
    async def suggestions_comment(
        self,
        ctx: commands.Context,
        suggestion_id: int,
        *,
        comment: str,
    ) -> None:
        """Add a staff note to a suggestion."""
        assert ctx.guild is not None
        comment = self._clean_text(comment, self.MAX_COMMENT_LENGTH)
        async with self._guild_lock(ctx.guild.id):
            async with self.config.guild(ctx.guild).suggestions() as suggestions:
                key = self._suggestion_key(suggestion_id)
                record = suggestions.get(key)
                if not record:
                    await ctx.send(f"No suggestion with ID `{suggestion_id}` was found.")
                    return
                notes = record.setdefault("staff_notes", [])
                notes.append(
                    {
                        "staff_id": ctx.author.id,
                        "comment": comment,
                        "created_at": self._now_ts(),
                    }
                )
                record["updated_at"] = self._now_ts()
                suggestions[key] = record

        settings = await self.config.guild(ctx.guild).all()
        await self._sync_suggestion_message(ctx.guild, record, settings)
        await self._send_review_log(ctx.guild, record, "Commented", ctx.author, comment)
        await ctx.send(f"Added a staff note to suggestion #{suggestion_id}.")

    @suggestions_group.command(name="delete")
    @commands.admin_or_permissions(manage_guild=True)
    async def suggestions_delete(
        self,
        ctx: commands.Context,
        suggestion_id: int,
        *,
        reason: Optional[str] = None,
    ) -> None:
        """Delete a suggestion record and remove its message when possible."""
        assert ctx.guild is not None
        reason = self._clean_text(reason, self.MAX_REASON_LENGTH) if reason else None
        async with self._guild_lock(ctx.guild.id):
            async with self.config.guild(ctx.guild).suggestions() as suggestions:
                key = self._suggestion_key(suggestion_id)
                record = suggestions.pop(key, None)
                if not record:
                    await ctx.send(f"No suggestion with ID `{suggestion_id}` was found.")
                    return

        message = await self._fetch_suggestion_message(ctx.guild, record)
        if message is not None:
            try:
                await message.delete()
            except discord.HTTPException:
                pass
        await self._send_review_log(ctx.guild, record, "Deleted", ctx.author, reason)
        await ctx.send(f"Suggestion #{suggestion_id} was deleted.")

    @suggestions_group.command(name="export")
    @commands.admin_or_permissions(manage_guild=True)
    @commands.bot_has_permissions(attach_files=True)
    async def suggestions_export(self, ctx: commands.Context) -> None:
        """Export suggestion records as CSV."""
        assert ctx.guild is not None
        suggestions = await self.config.guild(ctx.guild).suggestions()
        if not suggestions:
            await ctx.send("No suggestion records have been stored yet.")
            return

        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(
            [
                "id",
                "author_id",
                "status",
                "score",
                "upvotes",
                "downvotes",
                "created_at",
                "updated_at",
                "decision_by",
                "decision_at",
                "suggestion",
            ]
        )
        for record in sorted(suggestions.values(), key=lambda item: int(item.get("id") or 0)):
            writer.writerow(
                [
                    record.get("id"),
                    record.get("author_id"),
                    record.get("status"),
                    self._score(record),
                    len(record.get("upvotes", [])),
                    len(record.get("downvotes", [])),
                    self._format_export_time(record.get("created_at")),
                    self._format_export_time(record.get("updated_at")),
                    record.get("decision_by"),
                    self._format_export_time(record.get("decision_at")),
                    record.get("text"),
                ]
            )

        data = output.getvalue().encode("utf-8")
        file = discord.File(io.BytesIO(data), filename=f"suggestions-{ctx.guild.id}.csv")
        await ctx.send("Suggestion records export:", file=file)

    @staticmethod
    def _format_export_time(value: Any) -> str:
        if value in (None, ""):
            return ""
        try:
            return datetime.fromtimestamp(float(value), tz=timezone.utc).isoformat()
        except (TypeError, ValueError, OSError):
            return ""
