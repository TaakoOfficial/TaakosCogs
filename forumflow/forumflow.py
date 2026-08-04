"""Managed help workflows for Discord forum channels."""

from __future__ import annotations

import csv
import io
import time
from contextlib import suppress
from typing import TYPE_CHECKING, Any

import discord
from redbot.core import Config, commands

from .dashboard_integration import DashboardIntegration

if TYPE_CHECKING:
    from redbot.core.bot import Red


WORKFLOW_TAGS = {"open", "claimed", "waiting", "solved", "stale"}


class ForumFlowControls(discord.ui.View):
    """Persistent controls shared by every tracked forum post."""

    def __init__(self, cog: ForumFlow) -> None:
        super().__init__(timeout=None)
        self.cog = cog

    @discord.ui.button(label="Claim", style=discord.ButtonStyle.primary, custom_id="forumflow:claim")
    async def claim(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        await self.cog.handle_control(interaction, "claimed")

    @discord.ui.button(label="Waiting", style=discord.ButtonStyle.secondary, custom_id="forumflow:waiting")
    async def waiting(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        await self.cog.handle_control(interaction, "waiting")

    @discord.ui.button(label="Solve", style=discord.ButtonStyle.success, custom_id="forumflow:solve")
    async def solve(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        await self.cog.handle_control(interaction, "solved")

    @discord.ui.button(label="Reopen", style=discord.ButtonStyle.danger, custom_id="forumflow:reopen")
    async def reopen(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        await self.cog.handle_control(interaction, "open")


class ForumFlow(DashboardIntegration, commands.Cog):
    """Turn forum channels into measurable support and knowledge workflows."""

    CONFIG_IDENTIFIER = 2026080301
    COLOR = 0x5865F2

    def __init__(self, bot: Red) -> None:
        self.bot = bot
        self.config = Config.get_conf(self, identifier=self.CONFIG_IDENTIFIER, force_registration=True)
        self.config.register_guild(
            forum_ids=[],
            staff_role_id=None,
            log_channel_id=None,
            stale_hours=72,
            auto_controls=True,
            records={},
        )

    async def cog_load(self) -> None:
        self.bot.add_view(ForumFlowControls(self))

    async def red_delete_data_for_user(self, *, requester: str, user_id: int) -> None:
        for guild_id in await self.config.all_guilds():
            conf = self.config.guild_from_id(guild_id)
            records = await conf.records()
            changed = False
            for record in records.values():
                for key in ("author_id", "assignee_id", "accepted_author_id", "last_actor_id"):
                    if record.get(key) == user_id:
                        record[key] = None
                        changed = True
            if changed:
                await conf.records.set(records)

    @staticmethod
    def _now() -> int:
        return int(time.time())

    async def _is_staff(self, member: discord.Member) -> bool:
        if member.id in getattr(self.bot, "owner_ids", set()) or member.guild_permissions.manage_threads:
            return True
        role_id = await self.config.guild(member.guild).staff_role_id()
        return bool(role_id and member.get_role(role_id))

    async def _record_for(self, thread: discord.Thread) -> tuple[dict[str, Any], dict[str, Any]]:
        conf = self.config.guild(thread.guild)
        records = await conf.records()
        key = str(thread.id)
        record = records.setdefault(
            key,
            {
                "thread_id": thread.id,
                "forum_id": thread.parent_id,
                "author_id": thread.owner_id,
                "assignee_id": None,
                "state": "open",
                "created_at": int(thread.created_at.timestamp()) if thread.created_at else self._now(),
                "updated_at": self._now(),
                "resolved_at": None,
                "accepted_message_id": None,
                "accepted_author_id": None,
                "control_message_id": None,
                "last_actor_id": None,
            },
        )
        return records, record

    async def _save_record(self, thread: discord.Thread, records: dict[str, Any], record: dict[str, Any]) -> None:
        records[str(thread.id)] = record
        await self.config.guild(thread.guild).records.set(records)

    async def _apply_state_tag(self, thread: discord.Thread, state: str) -> None:
        parent = thread.parent
        if not isinstance(parent, discord.ForumChannel):
            return
        desired = next((tag for tag in parent.available_tags if tag.name.casefold() == state), None)
        retained = [tag for tag in thread.applied_tags if tag.name.casefold() not in WORKFLOW_TAGS]
        if desired:
            retained.append(desired)
        with suppress(discord.HTTPException):
            await thread.edit(applied_tags=retained, reason=f"ForumFlow state: {state}")

    async def _set_state(self, thread: discord.Thread, actor: discord.Member, state: str) -> dict[str, Any]:
        records, record = await self._record_for(thread)
        record["state"] = state
        record["updated_at"] = self._now()
        record["last_actor_id"] = actor.id
        if state == "claimed":
            record["assignee_id"] = actor.id
        if state == "solved":
            record["resolved_at"] = self._now()
        elif record.get("resolved_at"):
            record["resolved_at"] = None
        await self._save_record(thread, records, record)
        await self._apply_state_tag(thread, state)
        await self._log(thread.guild, f"**{thread.name}** changed to **{state}** by {actor.mention}.", thread.jump_url)
        return record

    async def _log(self, guild: discord.Guild, text: str, url: str | None = None) -> None:
        channel_id = await self.config.guild(guild).log_channel_id()
        channel = guild.get_channel(channel_id) if channel_id else None
        if isinstance(channel, discord.TextChannel):
            embed = discord.Embed(description=text, color=self.COLOR, timestamp=discord.utils.utcnow())
            if url:
                embed.add_field(name="Post", value=f"[Open thread]({url})")
            with suppress(discord.HTTPException):
                await channel.send(embed=embed)

    async def handle_control(self, interaction: discord.Interaction, state: str) -> None:
        if not interaction.guild or not isinstance(interaction.user, discord.Member):
            await interaction.response.send_message("This control only works in a server.", ephemeral=True)
            return
        channel = interaction.channel
        if not isinstance(channel, discord.Thread):
            await interaction.response.send_message("This control belongs in a forum post.", ephemeral=True)
            return
        if state != "solved" and not await self._is_staff(interaction.user):
            await interaction.response.send_message("Only configured staff can use that control.", ephemeral=True)
            return
        if state == "solved":
            _records, record = await self._record_for(channel)
            if interaction.user.id not in {record.get("author_id"), record.get("assignee_id")} and not await self._is_staff(
                interaction.user,
            ):
                await interaction.response.send_message(
                    "Only the author, assignee, or staff can solve this post.", ephemeral=True
                )
                return
        await interaction.response.defer(ephemeral=True)
        await self._set_state(channel, interaction.user, state)
        await interaction.followup.send(f"Post marked **{state}**.", ephemeral=True)

    @commands.Cog.listener()
    async def on_thread_create(self, thread: discord.Thread) -> None:
        if not thread.guild or thread.parent_id not in await self.config.guild(thread.guild).forum_ids():
            return
        records, record = await self._record_for(thread)
        await self._apply_state_tag(thread, "open")
        if await self.config.guild(thread.guild).auto_controls():
            try:
                message = await thread.send(
                    embed=discord.Embed(
                        title="ForumFlow",
                        description="Staff can claim or change this post's state. The author or staff can mark it solved.",
                        color=self.COLOR,
                    ),
                    view=ForumFlowControls(self),
                )
            except discord.HTTPException:
                message = None
            if message:
                record["control_message_id"] = message.id
        await self._save_record(thread, records, record)

    @commands.hybrid_group(name="forumflow", aliases=["ff"], invoke_without_command=True)
    @commands.guild_only()
    async def forumflow(self, ctx: commands.Context) -> None:
        """Manage forum support workflows."""
        await ctx.send_help()

    @forumflow.command(name="addforum")
    @commands.admin_or_permissions(manage_guild=True)
    async def add_forum(self, ctx: commands.Context, forum: discord.ForumChannel | None = None) -> None:
        """Enable ForumFlow for a forum channel."""
        current_forum = ctx.channel.parent if isinstance(ctx.channel, discord.Thread) else ctx.channel
        selected = forum or (current_forum if isinstance(current_forum, discord.ForumChannel) else None)
        if not selected:
            raise commands.BadArgument("Run this in a forum channel or provide one.")
        async with self.config.guild(ctx.guild).forum_ids() as forum_ids:
            if selected.id not in forum_ids:
                forum_ids.append(selected.id)
        await ctx.send(f"ForumFlow enabled for {selected.mention}.")

    @forumflow.command(name="removeforum")
    @commands.admin_or_permissions(manage_guild=True)
    async def remove_forum(self, ctx: commands.Context, forum: discord.ForumChannel) -> None:
        """Disable ForumFlow for a forum channel."""
        async with self.config.guild(ctx.guild).forum_ids() as forum_ids:
            if forum.id in forum_ids:
                forum_ids.remove(forum.id)
        await ctx.send(f"ForumFlow disabled for {forum.mention}.")

    @forumflow.command(name="staffrole")
    @commands.admin_or_permissions(manage_guild=True)
    async def staff_role(self, ctx: commands.Context, role: discord.Role | None = None) -> None:
        """Set the staff role; omit it to clear the setting."""
        await self.config.guild(ctx.guild).staff_role_id.set(role.id if role else None)
        await ctx.send(f"Staff role set to {role.mention}." if role else "Staff role cleared.")

    @forumflow.command(name="logchannel")
    @commands.admin_or_permissions(manage_guild=True)
    async def log_channel(self, ctx: commands.Context, channel: discord.TextChannel | None = None) -> None:
        """Set the workflow log channel; omit it to clear it."""
        await self.config.guild(ctx.guild).log_channel_id.set(channel.id if channel else None)
        await ctx.send(f"Log channel set to {channel.mention}." if channel else "Log channel cleared.")

    @forumflow.command(name="claim")
    async def claim_command(self, ctx: commands.Context) -> None:
        """Claim the current tracked forum post."""
        if not isinstance(ctx.channel, discord.Thread) or not isinstance(ctx.author, discord.Member):
            raise commands.BadArgument("Run this inside a forum post.")
        if not await self._is_staff(ctx.author):
            raise commands.CheckFailure("Only configured staff can claim posts.")
        await self._set_state(ctx.channel, ctx.author, "claimed")
        await ctx.send(f"Claimed by {ctx.author.mention}.")

    @forumflow.command(name="state")
    async def state_command(self, ctx: commands.Context, state: str) -> None:
        """Set the current post to open, claimed, waiting, solved, or stale."""
        if not isinstance(ctx.channel, discord.Thread) or not isinstance(ctx.author, discord.Member):
            raise commands.BadArgument("Run this inside a forum post.")
        state = state.casefold()
        if state not in WORKFLOW_TAGS:
            raise commands.BadArgument("State must be open, claimed, waiting, solved, or stale.")
        if not await self._is_staff(ctx.author):
            raise commands.CheckFailure("Only configured staff can change workflow state.")
        await self._set_state(ctx.channel, ctx.author, state)
        await ctx.send(f"Post marked **{state}**.")

    @forumflow.command(name="accept")
    async def accept_answer(self, ctx: commands.Context, message: discord.Message) -> None:
        """Mark a message in the current post as its accepted answer."""
        if not isinstance(ctx.channel, discord.Thread) or message.channel.id != ctx.channel.id:
            raise commands.BadArgument("Choose a message from this forum post.")
        records, record = await self._record_for(ctx.channel)
        if ctx.author.id != record.get("author_id") and not (
            isinstance(ctx.author, discord.Member) and await self._is_staff(ctx.author)
        ):
            raise commands.CheckFailure("Only the post author or staff can accept an answer.")
        record["accepted_message_id"] = message.id
        record["accepted_author_id"] = message.author.id
        record["updated_at"] = self._now()
        await self._save_record(ctx.channel, records, record)
        if isinstance(ctx.author, discord.Member):
            await self._set_state(ctx.channel, ctx.author, "solved")
        await ctx.send(f"Accepted {message.jump_url} as the answer.")

    @forumflow.command(name="queue")
    async def queue(self, ctx: commands.Context, state: str = "open") -> None:
        """List tracked posts in a workflow state."""
        state = state.casefold()
        records = await self.config.guild(ctx.guild).records()
        matches = [record for record in records.values() if record.get("state") == state]
        matches.sort(key=lambda item: item.get("updated_at", 0))
        lines = []
        for record in matches[:25]:
            thread = ctx.guild.get_thread(record["thread_id"])
            if thread:
                lines.append(f"• {thread.mention} — updated <t:{record['updated_at']}:R>")
        await ctx.send(
            embed=discord.Embed(
                title=f"ForumFlow · {state.title()}", description="\n".join(lines) or "No posts.", color=self.COLOR
            )
        )

    @forumflow.command(name="markstale")
    @commands.admin_or_permissions(manage_threads=True)
    async def mark_stale(self, ctx: commands.Context) -> None:
        """Mark inactive open, claimed, or waiting posts as stale."""
        conf = self.config.guild(ctx.guild)
        records = await conf.records()
        cutoff = self._now() - int(await conf.stale_hours()) * 3600
        changed = 0
        for record in records.values():
            if record.get("state") in {"open", "claimed", "waiting"} and record.get("updated_at", 0) < cutoff:
                record["state"] = "stale"
                record["updated_at"] = self._now()
                thread = ctx.guild.get_thread(record["thread_id"])
                if thread:
                    await self._apply_state_tag(thread, "stale")
                changed += 1
        await conf.records.set(records)
        await ctx.send(f"Marked {changed} post(s) stale.")

    @forumflow.command(name="settings")
    async def settings(self, ctx: commands.Context) -> None:
        """Show ForumFlow configuration and metrics."""
        data = await self.config.guild(ctx.guild).all()
        states: dict[str, int] = {}
        resolved_seconds = []
        for record in data["records"].values():
            states[record.get("state", "unknown")] = states.get(record.get("state", "unknown"), 0) + 1
            if record.get("resolved_at") and record.get("created_at"):
                resolved_seconds.append(record["resolved_at"] - record["created_at"])
        average = int(sum(resolved_seconds) / len(resolved_seconds)) if resolved_seconds else 0
        forums = [f"<#{channel_id}>" for channel_id in data["forum_ids"]]
        embed = discord.Embed(title="ForumFlow Settings", color=self.COLOR)
        embed.add_field(name="Forums", value=", ".join(forums) or "None", inline=False)
        embed.add_field(name="States", value="\n".join(f"{key}: {value}" for key, value in sorted(states.items())) or "No posts")
        embed.add_field(
            name="Average resolution", value=f"{average // 3600}h {(average % 3600) // 60}m" if average else "No data"
        )
        embed.add_field(name="Stale after", value=f"{data['stale_hours']} hours")
        await ctx.send(embed=embed)

    @forumflow.command(name="export")
    @commands.admin_or_permissions(manage_guild=True)
    async def export(self, ctx: commands.Context) -> None:
        """Export tracked forum records as CSV."""
        records = await self.config.guild(ctx.guild).records()
        output = io.StringIO()
        fields = [
            "thread_id",
            "forum_id",
            "author_id",
            "assignee_id",
            "state",
            "created_at",
            "updated_at",
            "resolved_at",
            "accepted_message_id",
        ]
        writer = csv.DictWriter(output, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(records.values())
        await ctx.send(file=discord.File(io.BytesIO(output.getvalue().encode()), filename="forumflow.csv"))
