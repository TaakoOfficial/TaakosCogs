"""
YALC - Yet Another Logging Cog for Red-DiscordBot.
A comprehensive logging solution with both classic and slash commands.
"""
import discord
from redbot.core import Config, commands, app_commands
from redbot.core.bot import Red
from typing import Dict, List, Optional, Union, cast
import datetime
import asyncio

class YALC(commands.Cog):
    """📝 Yet Another Logging Cog - Log all the things!
    
    A powerful Discord server logging solution that supports both classic and slash commands.
    Features include:
    - Customizable event logging
    - Per-channel configurations
    - Ignore lists for users, roles, and channels
    - Log retention management
    - Rich embed formatting
    """

    def __init__(self, bot: Red) -> None:
        """Initialize YALC cog.
        
        Parameters
        ----------
        bot: Red
            The Red Discord Bot instance.
        """
        self.bot = bot
        self.config = Config.get_conf(
            self, identifier=2025041601, force_registration=True
        )
        # Initialize default settings
        default_guild = {
            "log_channel": None,
            "ignored_users": [],
            "ignored_channels": [],
            "ignored_categories": [],
            "event_channels": {},  # Channel overrides for specific events
            "events": {
                "message_delete": False,
                "message_edit": False,
                "member_join": False,
                "member_leave": False,
                "member_ban": False,
                "member_unban": False,
                "member_update": False,
                "channel_create": False,
                "channel_delete": False,
                "channel_update": False,
                "role_create": False,
                "role_delete": False,
                "role_update": False,
                "emoji_update": False,
                "guild_update": False,
                "voice_update": False,
                "member_kick": False
            },
            "retention_days": 30
        }
        
        self.config.register_guild(**default_guild)
        self._cached_deletes: Dict[int, discord.Message] = {}
        self._cached_edits: Dict[int, discord.Message] = {}

    # Hybrid Commands - work as both classic and slash commands
    @commands.hybrid_group(name="yalc")
    @commands.guild_only()
    @commands.admin_or_permissions(manage_guild=True)
    async def yalc(self, ctx: commands.Context) -> None:
        """Manage YALC logging configuration."""
        if ctx.invoked_subcommand is None:
            await ctx.send_help()

    @yalc.command(name="info")
    @commands.guild_only()
    @commands.admin_or_permissions(manage_guild=True)
    async def yalc_info(self, ctx: commands.Context) -> None:
        """Show enabled events and their log channels."""
        try:
            settings = await self.config.guild(ctx.guild).all()
            log_events = settings["events"]
            event_channels = settings.get("event_channels", {})
            log_channel_id = settings["log_channel"]
            lines = []
            for event, enabled in log_events.items():
                channel_id = event_channels.get(event, log_channel_id)
                channel = ctx.guild.get_channel(channel_id) if channel_id else None
                emoji = "✅" if enabled else "❌"
                channel_str = channel.mention if channel else "*Not set*"
                lines.append(f"{emoji} `{event}` → {channel_str}")
            embed = discord.Embed(
                title="📝 YALC Logging Status",
                description="\n".join(lines) or "No events configured.",
                color=discord.Color.blurple()
            )
            self.set_embed_footer(embed)
            await ctx.send(embed=embed, ephemeral=True)
        except Exception as e:
            await ctx.send(f"❌ Error: {e}")

    @yalc.command(name="channel")
    async def yalc_channel(self, ctx: commands.Context, *, channel: Optional[discord.TextChannel] = None) -> None:
        """Set the channel for server logs."""
        channel = channel or ctx.channel
        if not isinstance(channel, discord.TextChannel):
            await ctx.send("❌ That's not a valid text channel!")
            return
        await self.config.guild(ctx.guild).log_channel.set(channel.id)
        await ctx.send(f"✅ Log channel set to {channel.mention}")

    @yalc.command(name="toggle")
    async def yalc_toggle(self, ctx: commands.Context, *, event: Optional[str] = None) -> None:
        """Toggle logging for a specific event."""
        events = await self.config.guild(ctx.guild).events()
        
        if not event:
            msg = "Available events:\n"
            msg += "\n".join(f"`{k}`: {'✅' if v else '❌'}" for k, v in events.items())
            await ctx.send(msg)
            return
            
        if event not in events:
            await ctx.send(f"❌ Unknown event. Available events: {', '.join(events.keys())}")
            return

        events[event] = not events[event]
        await self.config.guild(ctx.guild).events.set(events)
        status = "enabled" if events[event] else "disabled"
        await ctx.send(f"✅ Logging for `{event}` is now {status}")

    @yalc.group(name="ignore")
    async def yalc_ignore(self, ctx: commands.Context) -> None:
        """Manage ignored users, channels, and categories."""
        if ctx.invoked_subcommand is None:
            await ctx.send_help()

    @yalc_ignore.command(name="user")
    async def yalc_ignore_user(self, ctx: commands.Context, user: discord.Member) -> None:
        """Ignore a user from being logged."""
        async with self.config.guild(ctx.guild).ignored_users() as ignored:
            if user.id in ignored:
                await ctx.send(f"❌ {user.mention} is already ignored")
                return
            ignored.append(user.id)
        await ctx.send(f"✅ Now ignoring {user.mention}")

    @yalc_ignore.command(name="channel")
    async def yalc_ignore_channel(self, ctx: commands.Context, channel: discord.TextChannel) -> None:
        """Ignore a channel from being logged."""
        async with self.config.guild(ctx.guild).ignored_channels() as ignored:
            if channel.id in ignored:
                await ctx.send(f"❌ {channel.mention} is already ignored")
                return
            ignored.append(channel.id)
        await ctx.send(f"✅ Now ignoring {channel.mention}")

    @yalc_ignore.command(name="category")
    async def yalc_ignore_category(self, ctx: commands.Context, category: discord.CategoryChannel) -> None:
        """Ignore an entire category from being logged."""
        async with self.config.guild(ctx.guild).ignored_categories() as ignored:
            if category.id in ignored:
                await ctx.send(f"❌ Category {category.name} is already ignored")
                return
            ignored.append(category.id)
        await ctx.send(f"✅ Now ignoring category {category.name}")

    @yalc.group(name="unignore")
    async def yalc_unignore(self, ctx: commands.Context) -> None:
        """Remove users, channels, or categories from ignore list."""
        if ctx.invoked_subcommand is None:
            await ctx.send_help()

    @yalc_unignore.command(name="user")
    async def yalc_unignore_user(self, ctx: commands.Context, user: discord.Member) -> None:
        """Stop ignoring a user."""
        async with self.config.guild(ctx.guild).ignored_users() as ignored:
            if user.id not in ignored:
                await ctx.send(f"❌ {user.mention} is not ignored")
                return
            ignored.remove(user.id)
        await ctx.send(f"✅ No longer ignoring {user.mention}")

    @yalc_unignore.command(name="channel")
    async def yalc_unignore_channel(self, ctx: commands.Context, channel: discord.TextChannel) -> None:
        """Stop ignoring a channel."""
        async with self.config.guild(ctx.guild).ignored_channels() as ignored:
            if channel.id not in ignored:
                await ctx.send(f"❌ {channel.mention} is not ignored")
                return
            ignored.remove(channel.id)
        await ctx.send(f"✅ No longer ignoring {channel.mention}")

    @yalc_unignore.command(name="category")
    async def yalc_unignore_category(self, ctx: commands.Context, category: discord.CategoryChannel) -> None:
        """Stop ignoring a category."""
        async with self.config.guild(ctx.guild).ignored_categories() as ignored:
            if category.id not in ignored:
                await ctx.send(f"❌ Category {category.name} is not ignored")
                return
            ignored.remove(category.id)
        await ctx.send(f"✅ No longer ignoring category {category.name}")

    @yalc.group(name="template")
    async def yalc_template(self, ctx: commands.Context) -> None:
        """Manage log message templates for events."""
        if ctx.invoked_subcommand is None:
            await ctx.send_help()

    @yalc_template.command(name="set")
    async def yalc_template_set(self, ctx: commands.Context, event: str, *, template: str) -> None:
        """Set a custom log message template for an event.
        
        Use placeholders like {user}, {moderator}, {reason}.
        """
        events = await self.config.guild(ctx.guild).events()
        if event not in events:
            await ctx.send(f"❌ Invalid event type. Valid events: {', '.join(events.keys())}")
            return
        await self.config.guild(ctx.guild).set_raw(f"template_{event}", value=template)
        await ctx.send(f"✅ Template for `{event}` set!")

    @yalc_template.command(name="clear")
    async def yalc_template_clear(self, ctx: commands.Context, event: str) -> None:
        """Clear the custom template for an event (revert to default)."""
        events = await self.config.guild(ctx.guild).events()
        if event not in events:
            await ctx.send(f"❌ Invalid event type. Valid events: {', '.join(events.keys())}")
            return
        await self.config.guild(ctx.guild).clear_raw(f"template_{event}")
        await ctx.send(f"✅ Template for `{event}` cleared (using default).")

    @yalc.group(name="retention")
    async def yalc_retention(self, ctx: commands.Context) -> None:
        """Configure log retention settings."""
        if ctx.invoked_subcommand is None:
            await ctx.send_help()

    @yalc_retention.command(name="set")
    async def yalc_retention_set(self, ctx: commands.Context, days: int) -> None:
        """Set the log retention period in days (1-365)."""
        if not self.validate_retention_days(days):
            await ctx.send("❌ Please provide a value between 1 and 365 days.")
            return
        await self.config.guild(ctx.guild).retention_days.set(days)
        await ctx.send(f"✅ Log retention set to {days} days.")

    @yalc_retention.command(name="show")
    async def yalc_retention_show(self, ctx: commands.Context) -> None:
        """Show the current log retention period."""
        days = await self.config.guild(ctx.guild).retention_days()
        await ctx.send(f"📝 Current log retention period: {days} days")

    @yalc.group(name="filter")
    async def yalc_filter(self, ctx: commands.Context) -> None:
        """Manage event filters."""
        if ctx.invoked_subcommand is None:
            await ctx.send_help()

    @yalc_filter.command(name="add")
    async def yalc_filter_add(self, ctx: commands.Context, event: str, *, filter_str: str) -> None:
        """Add a filter for an event.
        
        Filters can target specific users, roles, channels, or keywords.
        """
        events = await self.config.guild(ctx.guild).events()
        if event not in events:
            await ctx.send(f"❌ Invalid event type. Valid events: {', '.join(events.keys())}")
            return
        async with self.config.guild(ctx.guild).all() as settings:
            filters = settings.get(f"filters_{event}", [])
            if filter_str in filters:
                await ctx.send("❌ This filter already exists.")
                return
            filters.append(filter_str)
            settings[f"filters_{event}"] = filters
        await ctx.send(f"✅ Filter added for `{event}`")

    @yalc_filter.command(name="remove")
    async def yalc_filter_remove(self, ctx: commands.Context, event: str, *, filter_str: str) -> None:
        """Remove a filter from an event."""
        events = await self.config.guild(ctx.guild).events()
        if event not in events:
            await ctx.send(f"❌ Invalid event type. Valid events: {', '.join(events.keys())}")
            return
        async with self.config.guild(ctx.guild).all() as settings:
            filters = settings.get(f"filters_{event}", [])
            if filter_str not in filters:
                await ctx.send("❌ This filter does not exist.")
                return
            filters.remove(filter_str)
            settings[f"filters_{event}"] = filters
        await ctx.send(f"✅ Filter removed from `{event}`")

    @yalc_filter.command(name="list")
    async def yalc_filter_list(self, ctx: commands.Context, event: str) -> None:
        """List all filters for an event."""
        events = await self.config.guild(ctx.guild).events()
        if event not in events:
            await ctx.send(f"❌ Invalid event type. Valid events: {', '.join(events.keys())}")
            return
        filters = await self.config.guild(ctx.guild).get_raw(f"filters_{event}", default=[])
        embed = discord.Embed(
            title=f"Filters for {event}",
            description="\n".join(filters) or "No filters set.",
            color=discord.Color.blurple()
        )
        self.set_embed_footer(embed)
        await ctx.send(embed=embed)

    @yalc.command(name="listevents")
    async def yalc_listevents(self, ctx: commands.Context) -> None:
        """List all available log event types."""
        events = await self.config.guild(ctx.guild).events()
        embed = discord.Embed(
            title="Available Log Event Types",
            description="\n".join(f"`{e}`" for e in events.keys()),
            color=discord.Color.blurple()
        )
        self.set_embed_footer(embed)
        await ctx.send(embed=embed)

    @yalc.command(name="setchannel")
    async def yalc_set_event_channel(self, ctx: commands.Context, event: str, channel: discord.TextChannel) -> None:
        """Set a specific channel for an event type.
        
        This overrides the default log channel for the specified event.
        """
        events = await self.config.guild(ctx.guild).events()
        if event not in events:
            await ctx.send(f"❌ Invalid event type. Valid events: {', '.join(events.keys())}")
            return
            
        async with self.config.guild(ctx.guild).event_channels() as channels:
            channels[event] = channel.id
        await ctx.send(f"✅ Channel for `{event}` set to {channel.mention}")

    @yalc.command(name="resetchannel")
    async def yalc_reset_event_channel(self, ctx: commands.Context, event: str) -> None:
        """Reset an event to use the default log channel.
        
        Removes the event-specific channel override.
        """
        events = await self.config.guild(ctx.guild).events()
        if event not in events:
            await ctx.send(f"❌ Invalid event type. Valid events: {', '.join(events.keys())}")
            return
            
        async with self.config.guild(ctx.guild).event_channels() as channels:
            if event not in channels:
                await ctx.send(f"❌ No custom channel set for `{event}`")
                return
            del channels[event]
        await ctx.send(f"✅ Channel for `{event}` reset to default log channel")

    __version__ = "2.0.0"
    
    def set_embed_footer(self, embed: discord.Embed) -> None:
        """Set consistent footer for YALC embeds.
        
        Parameters
        ----------
        embed: discord.Embed
            The embed to set the footer on
        """
        embed.set_footer(text=f"YALC v{self.__version__}")

    async def check_manage_guild(self, ctx: Union[commands.Context, discord.Interaction]) -> bool:
        """Check if user has manage guild permission.
        
        Parameters
        ----------
        ctx: Union[commands.Context, discord.Interaction]
            The context or interaction to check permissions for
            
        Returns
        -------
        bool
            True if user has permission, False otherwise
        
        Raises
        ------
        commands.CheckFailure
            If the user lacks required permissions
        """
        if isinstance(ctx, discord.Interaction):
            if not ctx.guild or not ctx.user:
                return False
            member = cast(discord.Member, ctx.user)
            return member.guild_permissions.manage_guild
        return ctx.author.guild_permissions.manage_guild

    def validate_retention_days(self, days: int) -> bool:
        """Validate log retention period is within acceptable range.
        
        Parameters
        ----------
        days: int
            Number of days to validate
            
        Returns
        -------
        bool
            True if days is within valid range (1-365)
        """
        return 1 <= days <= 365

    async def safe_send(
        self,
        channel: discord.TextChannel,
        content: Optional[str] = None,
        *,
        embed: Optional[discord.Embed] = None,
        **kwargs
    ) -> Optional[discord.Message]:
        """Safely send a message to a channel with error handling.
        
        Parameters
        ----------
        channel: discord.TextChannel
            The channel to send the message to
        content: Optional[str]
            The message content to send
        embed: Optional[discord.Embed]
            The embed to send
        **kwargs
            Additional kwargs to pass to send()
            
        Returns
        -------
        Optional[discord.Message]
            The sent message if successful, None otherwise
        """
        try:
            if embed:
                kwargs['embed'] = embed
            return await channel.send(content=content, **kwargs)
        except (discord.Forbidden, discord.HTTPException):
            return None

    async def cog_unload(self) -> None:
        """Clean up when cog is unloaded."""
        # Clear any cached messages
        self._cached_deletes.clear()
        self._cached_edits.clear()

async def setup(bot: Red) -> None:
    """Set up the YALC cog."""
    cog = YALC(bot)
    await bot.add_cog(cog)
    # Sync hybrid commands
    if bot.owner_ids:
        for owner_id in bot.owner_ids:
            owner = bot.get_user(owner_id)
            if owner:
                await cog.yalc.sync(guild=None)  # Global sync
                break
