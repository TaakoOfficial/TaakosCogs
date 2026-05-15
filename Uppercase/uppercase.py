"""Uppercase channel-name tools for Red-DiscordBot."""

from __future__ import annotations

import re

import discord
from redbot.core import app_commands, commands
from redbot.core.bot import Red

__red_end_user_data_statement__ = "This cog does not persistently store any end user data."


class Uppercase(commands.Cog):
    """Create and rename text channels with uppercase names."""

    MAX_CHANNEL_NAME_LENGTH = 100
    SEPARATOR_RE = re.compile(r"[\s_]+")
    REPEATED_DASH_RE = re.compile(r"-{2,}")

    def __init__(self, bot: Red) -> None:
        self.bot = bot

    @classmethod
    def format_channel_name(cls, name: str) -> str:
        """Return a Discord-safe uppercase name for a text channel."""
        normalized = cls.SEPARATOR_RE.sub("-", name.strip())
        converted = normalized.upper()
        collapsed = cls.REPEATED_DASH_RE.sub("-", converted).strip("-")
        trimmed = collapsed[: cls.MAX_CHANNEL_NAME_LENGTH].strip("-")
        if trimmed:
            return trimmed
        return "UNNAMED"

    @staticmethod
    def _audit_reason(ctx: commands.Context) -> str:
        return f"Uppercase command used by {ctx.author} ({ctx.author.id})"

    async def _send_result(
        self,
        ctx: commands.Context,
        action: str,
        channel: discord.TextChannel,
        formatted_name: str,
    ) -> None:
        await ctx.send(f"{action} {channel.mention} as `{formatted_name}`.")

    @commands.hybrid_command(
        name="create-channel",
        description="Create a text channel with an uppercase name.",
    )
    @app_commands.describe(
        category="The category where the new text channel should be created.",
        name="The channel name to convert to uppercase.",
    )
    @commands.guild_only()
    @commands.admin_or_permissions(manage_channels=True)
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def create_channel(
        self,
        ctx: commands.Context,
        category: discord.CategoryChannel,
        *,
        name: str,
    ) -> None:
        """Create a text channel in a category with an uppercase name."""
        guild = ctx.guild
        if guild is None:
            return

        me = guild.me
        if me is None or not me.guild_permissions.manage_channels:
            await ctx.send("I need the Manage Channels permission to create channels.")
            return
        if not category.permissions_for(me).manage_channels:
            await ctx.send(f"I need Manage Channels permission in `{category.name}`.")
            return

        formatted_name = self.format_channel_name(name)

        try:
            channel = await guild.create_text_channel(
                formatted_name,
                category=category,
                reason=self._audit_reason(ctx),
            )
        except discord.Forbidden:
            await ctx.send("I do not have permission to create that channel.")
            return
        except discord.HTTPException as exc:
            await ctx.send(f"Discord rejected that channel name: `{exc.text}`")
            return

        await self._send_result(ctx, "Created", channel, formatted_name)

    @commands.hybrid_command(
        name="rename-channel",
        description="Rename a text channel with an uppercase name.",
    )
    @app_commands.describe(
        channel="The text channel to rename.",
        name="The new channel name to convert to uppercase.",
    )
    @commands.guild_only()
    @commands.admin_or_permissions(manage_channels=True)
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def rename_channel(
        self,
        ctx: commands.Context,
        channel: discord.TextChannel,
        *,
        name: str,
    ) -> None:
        """Rename a text channel with an uppercase name."""
        guild = ctx.guild
        if guild is None:
            return

        me = guild.me
        if me is None or not channel.permissions_for(me).manage_channels:
            await ctx.send(f"I need Manage Channels permission in {channel.mention}.")
            return

        formatted_name = self.format_channel_name(name)

        try:
            await channel.edit(name=formatted_name, reason=self._audit_reason(ctx))
        except discord.Forbidden:
            await ctx.send(f"I do not have permission to rename {channel.mention}.")
            return
        except discord.HTTPException as exc:
            await ctx.send(f"Discord rejected that channel name: `{exc.text}`")
            return

        await self._send_result(ctx, "Renamed", channel, formatted_name)
