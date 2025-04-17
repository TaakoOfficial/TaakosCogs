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
import logging

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
        """Initialize YALC cog."""
        self.bot = bot
        self.config = Config.get_conf(
            self, identifier=2025041601, force_registration=True
        )
        self.log = logging.getLogger(f"red.YALC.{__name__}")

        self.event_descriptions = {
            "message_delete": ("🗑️", "Message deletions"),
            "message_edit": ("📝", "Message edits"),
            "member_join": ("👋", "Member joins"),
            "member_leave": ("👋", "Member leaves"),
            "member_ban": ("🔨", "Member bans"),
            "member_unban": ("🔓", "Member unbans"),
            "member_update": ("👤", "Member updates (roles, nickname)"),
            "channel_create": ("📝", "Channel creations"),
            "channel_delete": ("🗑️", "Channel deletions"),
            "channel_update": ("🔄", "Channel updates"),
            "role_create": ("✨", "Role creations"),
            "role_delete": ("🗑️", "Role deletions"),
            "role_update": ("🔄", "Role updates"),
            "emoji_update": ("😀", "Emoji updates"),
            "guild_update": ("⚙️", "Server setting updates"),
            "voice_update": ("🎤", "Voice channel updates"),
            "member_kick": ("👢", "Member kicks"),
            "command_use": ("⌨️", "Command usage"),
            "command_error": ("⚠️", "Command errors"),
            "cog_load": ("📦", "Cog loads/unloads"),
            "application_cmd": ("🔷", "Slash command usage"),
            "thread_create": ("🧵", "Thread creations"),
            "thread_delete": ("🗑️", "Thread deletions"),
            "thread_update": ("🔄", "Thread updates"),
            "thread_member_join": ("➡️", "Thread member joins"),
            "thread_member_leave": ("⬅️", "Thread member leaves")
        }
        
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
                "member_kick": False,
                "command_use": False,
                "command_error": False,
                "cog_load": False,
                "application_cmd": False,
                "thread_create": False,
                "thread_delete": False,
                "thread_update": False,
                "thread_member_join": False,
                "thread_member_leave": False
            },
            "ignored_commands": [],
            "ignored_cogs": []
        }
        
        self.config.register_guild(**default_guild)
        
        # Initialize listeners and slash commands
        from .listeners import Listeners
        self.listeners = Listeners(self)
        # Do not add_cog here; must be awaited in setup()

    async def should_log_event(self, guild: discord.Guild, event_type: str, channel: Optional[discord.abc.GuildChannel] = None) -> bool:
        """Check if an event should be logged based on settings."""
        if not guild:
            return False
            
        settings = await self.config.guild(guild).all()
        if not settings["events"].get(event_type, False):
            return False

        # Check channel, category, and user ignore lists
        if channel:
            if channel.id in settings["ignored_channels"]:
                return False
            if isinstance(channel, discord.TextChannel) and channel.category:
                if channel.category.id in settings["ignored_categories"]:
                    return False

        return True

    async def get_log_channel(self, guild: discord.Guild, event_type: str) -> Optional[discord.TextChannel]:
        """Get the appropriate logging channel for an event."""
        settings = await self.config.guild(guild).all()
        self.log.debug(f"[get_log_channel] Guild: {guild.id}, Event: {event_type}, Settings: {settings}")
        # Check for event-specific channel override
        channel_id = settings["event_channels"].get(event_type, settings["log_channel"])
        self.log.debug(f"[get_log_channel] Selected channel_id: {channel_id}")
        if not channel_id:
            return None
        channel = guild.get_channel(channel_id)
        self.log.debug(f"[get_log_channel] Resolved channel: {channel}")
        return channel if isinstance(channel, discord.TextChannel) else None

    def create_embed(self, event_type: str, description: str, **kwargs) -> discord.Embed:
        """Create a standardized embed for logging."""
        color_map = {
            "message_delete": discord.Color.red(),
            "message_edit": discord.Color.blue(),
            "member_join": discord.Color.green(),
            "member_leave": discord.Color.orange(),
            "member_ban": discord.Color.dark_red(),
            "member_unban": discord.Color.teal()
        }
        
        embed = discord.Embed(
            title=f"📝 {event_type.replace('_', ' ').title()}",
            description=description,
            color=color_map.get(event_type, discord.Color.blurple()),
            timestamp=datetime.datetime.now(datetime.UTC)
        )
        
        # Add any additional fields from kwargs
        for key, value in kwargs.items():
            if value:
                embed.add_field(name=key.replace('_', ' ').title(), value=str(value))
                
        self.set_embed_footer(embed)
        return embed

    async def cog_unload(self) -> None:
        """Clean up when cog is unloaded."""
        # Clear any cached messages in listeners
        if hasattr(self, "listeners"):
            self.listeners._cached_deletes.clear()
            self.listeners._cached_edits.clear()
        # No manual sync needed for hybrid commands

    # Hybrid Commands - work as both classic and slash commands
    @commands.hybrid_group(name="yalc")
    @commands.guild_only()
    @commands.admin_or_permissions(manage_guild=True)
    async def yalc(self, ctx: commands.Context) -> None:
        """Manage YALC logging configuration."""
        # Do not call ctx.send_help() here; Redbot handles help automatically for hybrid groups.
        pass

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

    @yalc.command(name="resetdefault")
    async def yalc_reset_default(self, ctx: commands.Context) -> None:
        """Reset the default log channel."""
        await self.config.guild(ctx.guild).log_channel.set(None)
        await ctx.send("✅ Default log channel has been removed.")

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
        
        # Group events by their current status
        enabled_events = []
        disabled_events = []
        
        for event_name, enabled in events.items():
            emoji, description = self.event_descriptions.get(event_name, ("❔", "Unknown event type"))
            line = f"{emoji} `{event_name}` - {description}"
            if enabled:
                enabled_events.append(line)
            else:
                disabled_events.append(line)
        
        embed = discord.Embed(
            title="📝 Available Log Event Types",
            color=discord.Color.blurple(),
            description="Use `/yalc toggle <event>` to enable or disable events."
        )
        
        if enabled_events:
            embed.add_field(
                name="✅ Enabled Events",
                value="\n".join(enabled_events),
                inline=False
            )
        
        if disabled_events:
            embed.add_field(
                name="❌ Disabled Events",
                value="\n".join(disabled_events),
                inline=False
            )
        
        self.set_embed_footer(embed)
        await ctx.send(embed=embed)

    # Removed slash command implementation as hybrid commands provide slash functionality

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

    async def _handle_setup_reaction(
        self,
        ctx: commands.Context,
        message: discord.Message,
        emoji_options: Dict[str, str],
        timeout: float = 30.0
    ) -> Optional[str]:
        """Handle reaction-based selection in setup wizard.
        
        Parameters
        ----------
        ctx: commands.Context
            The command context
        message: discord.Message
            The message to add reactions to
        emoji_options: Dict[str, str]
            Mapping of emoji to their meanings
        timeout: float
            How long to wait for a reaction
            
        Returns
        -------
        Optional[str]
            The selected option or None if timed out
        """
        for emoji in emoji_options.keys():
            await message.add_reaction(emoji)
            
        try:
            reaction, user = await self.bot.wait_for(
                "reaction_add",
                check=lambda r, u: (
                    u == ctx.author and 
                    str(r.emoji) in emoji_options and 
                    r.message.id == message.id
                ),
                timeout=timeout
            )
            return str(reaction.emoji)
        except asyncio.TimeoutError:
            return None

    @yalc.command(name="setup")
    @commands.guild_only()
    @commands.admin_or_permissions(manage_guild=True)
    async def yalc_setup(self, ctx: commands.Context) -> None:
        """Start an interactive setup wizard for YALC."""
        if not ctx.guild:
            await ctx.send("❌ This command can only be used in a server!")
            return

        # Step 1: Channel Organization
        embed = discord.Embed(
            title="📋 YALC Setup Wizard - Channel Organization",
            description=(
                "How would you like to organize your logging channels?\n\n"
                "🗂️ - Create a category with separate channels for different event types\n"
                "📜 - Use a single channel for all logs\n"
                "❌ - Cancel setup"
            ),
            color=discord.Color.blue()
        )
        self.set_embed_footer(embed)
        
        msg = await ctx.send(embed=embed)
        option = await self._handle_setup_reaction(ctx, msg, {
            "🗂️": "categories",
            "📜": "single",
            "❌": "cancel"
        })
        
        if not option or option == "❌":
            await ctx.send("Setup cancelled!")
            return
            
        # Step 2: Event Types
        event_embed = discord.Embed(
            title="🎯 Event Selection",
            description=(
                "Which events would you like to enable?\n\n"
                "✨ - Enable all events\n"
                "🎯 - Enable common events only (messages, members, moderation)\n"
                "⚙️ - Let me choose specific events"
            ),
            color=discord.Color.blue()
        )
        self.set_embed_footer(event_embed)
        
        event_msg = await ctx.send(embed=event_embed)
        event_choice = await self._handle_setup_reaction(ctx, event_msg, {
            "✨": "all",
            "🎯": "common",
            "⚙️": "custom"
        })
        
        if not event_choice:
            await ctx.send("Setup timed out!")
            return
        
        try:
            self.log.debug(f"[setup] User selected organization option: {option}")
            # Create channels based on selection
            if option == "categories":
                self.log.debug("[setup] Entering 'categories' setup path.")
                # Create category and channels
                category = await ctx.guild.create_category(
                    "📝 Server Logs",
                    reason="YALC Setup Wizard - Creating log channels"
                )
                
                channels = {
                    "messages": {
                        "name": "logs-messages",
                        "emoji": "💬",
                        "events": ["message_delete", "message_edit"]
                    },
                    "members": {
                        "name": "logs-members",
                        "emoji": "👥",
                        "events": ["member_join", "member_leave", "member_ban", "member_unban", "member_update", "member_kick"]
                    },
                    "channels": {
                        "name": "logs-channels",
                        "emoji": "📝",
                        "events": ["channel_create", "channel_delete", "channel_update", "voice_update"]
                    },
                    "threads": {
                        "name": "logs-threads",
                        "emoji": "🧵",
                        "events": ["thread_create", "thread_delete", "thread_update", "thread_member_join", "thread_member_leave"]
                    },
                    "roles": {
                        "name": "logs-roles",
                        "emoji": "🎭",
                        "events": ["role_create", "role_delete", "role_update"]
                    },
                    "commands": {
                        "name": "logs-commands",
                        "emoji": "⌨️",
                        "events": ["command_use", "command_error", "application_cmd"]
                    },
                    "server": {
                        "name": "logs-server",
                        "emoji": "⚙️",
                        "events": ["emoji_update", "guild_update", "cog_load"]
                    }
                }
                
                channel_overrides = {}
                channel_list = []
                
                for group, info in channels.items():
                    channel_name = f"{info['emoji']}-{info['name']}"
                    self.log.debug(f"[setup] Creating channel: {channel_name} for group: {group}")
                    channel = await category.create_text_channel(
                        channel_name,
                        reason=f"YALC Setup - Channel for {group} events"
                    )
                    await channel.set_permissions(
                        ctx.guild.default_role,
                        read_messages=False
                    )
                    channel_list.append(f"{info['emoji']} {channel.mention}")
                    for event in info["events"]:
                        channel_overrides[event] = channel.id
                    self.log.debug(f"[setup] Channel created: {channel_name} (ID: {channel.id})")
                # Overwrite config: reset all relevant fields
                async with self.config.guild(ctx.guild).all() as settings:
                    settings["event_channels"] = channel_overrides
                    self.log.debug(f"[setup] Saved event-to-channel mapping: {channel_overrides}")
                    settings["log_channel"] = None
                    settings["ignored_users"] = []
                    settings["ignored_channels"] = []
                    settings["ignored_categories"] = []
                    settings["ignored_commands"] = []
                    settings["ignored_cogs"] = []
                    # Remove all filters and templates
                    for k in list(settings.keys()):
                        if k.startswith("filters_") or k.startswith("template_"):
                            del settings[k]
                    # Enable events based on choice
                    if event_choice == "all":  # All events
                        for event in settings["events"]:
                            settings["events"][event] = True
                    elif event_choice == "common":  # Common events
                        common_events = [
                            "message_delete", "message_edit",
                            "member_join", "member_leave",
                            "member_ban", "member_unban",
                            "member_kick", "channel_create",
                            "channel_delete"
                        ]
                        for event in settings["events"]:
                            settings["events"][event] = event in common_events
                
                setup_embed = discord.Embed(
                    title="✅ YALC Setup Complete!",
                    description=(
                        "I've created the following structure:\n\n"
                        f"📁 **Server Logs** category with channels:\n"
                        f"{chr(10).join(channel_list)}\n\n"
                        f"🎯 Events enabled: {'All' if event_choice == 'all' else 'Common' if event_choice == 'common' else 'Custom'}\n\n"
                        "You can customize this further using `/yalc` commands!"
                    ),
                    color=discord.Color.green()
                )
            else:  # Single channel
                self.log.debug("[setup] Entering 'single' setup path.")
                log_channel = await ctx.guild.create_text_channel(
                    "📝-server-logs",
                    reason="YALC Setup Wizard - Creating log channel"
                )
                await log_channel.set_permissions(
                    ctx.guild.default_role,
                    read_messages=False
                )
                async with self.config.guild(ctx.guild).all() as settings:
                    settings["log_channel"] = log_channel.id
                    settings["event_channels"] = {}
                    self.log.debug(f"[setup] Saved single log channel ID: {log_channel.id}")
                    settings["ignored_users"] = []
                    settings["ignored_channels"] = []
                    settings["ignored_categories"] = []
                    settings["ignored_commands"] = []
                    settings["ignored_cogs"] = []
                    # Remove all filters and templates
                    for k in list(settings.keys()):
                        if k.startswith("filters_") or k.startswith("template_"):
                            del settings[k]
                    # Enable events based on choice
                    if event_choice == "all":  # All events
                        for event in settings["events"]:
                            settings["events"][event] = True
                    elif event_choice == "common":  # Common events
                        common_events = [
                            "message_delete", "message_edit",
                            "member_join", "member_leave",
                            "member_ban", "member_unban",
                            "member_kick", "channel_create",
                            "channel_delete"
                        ]
                        for event in settings["events"]:
                            settings["events"][event] = event in common_events
                
                setup_embed = discord.Embed(
                    title="✅ YALC Setup Complete!",
                    description=(
                        f"I've created {log_channel.mention} for all logs.\n\n"
                        f"🎯 Events enabled: {'All' if event_choice == 'all' else 'Common' if event_choice == 'common' else 'Custom'}\n\n"
                        "You can customize the settings using `/yalc` commands!"
                    ),
                    color=discord.Color.green()
                )
            
            self.set_embed_footer(setup_embed)
            await ctx.send(embed=setup_embed)
            # Log config after setup
            config_after = await self.config.guild(ctx.guild).all()
            self.log.info(f"[setup] Config after setup for guild {ctx.guild.id}: {config_after}")
        except discord.Forbidden:
            error_embed = discord.Embed(
                title="❌ Setup Failed",
                description=(
                    "I don't have permission to create channels or categories.\n"
                    "Please make sure I have the `Manage Channels` permission and try again."
                ),
                color=discord.Color.red()
            )
            self.set_embed_footer(error_embed)
            await ctx.send(embed=error_embed)

    __version__ = "3.0.0"
    
    def set_embed_footer(self, embed: discord.Embed) -> None:
        """Set consistent footer for YALC embeds.
        
        Parameters
        ----------
        embed: discord.Embed
            The embed to set the footer on
        """
        embed.set_footer(
            text=f"YALC v{self.__version__}",
            icon_url="https://cdn-icons-png.flaticon.com/512/928/928797.png"
        )

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

async def setup(bot: Red) -> None:
        """Set up the YALC cog."""
        cog = YALC(bot)
        await bot.add_cog(cog)
        await bot.add_cog(cog.listeners)
        # Register hybrid slash group with the application command tree
        bot.tree.add_command(cog.yalc)
        # No need to call sync() on the group; Redbot handles hybrid command registration
