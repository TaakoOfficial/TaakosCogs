"""
YALC - Yet Another Logging Cog for Red-DiscordBot.
A comprehensive logging solution with both classic and slash commands.
"""
import discord
from redbot.core import Config, commands
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
        
        default_guild = {
            "log_channel": None,
            "ignored_users": [],
            "ignored_channels": [],
            "ignored_categories": [],
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

    async def _is_guild_message(self, message: discord.Message) -> bool:
        """Check if a message is from a guild and in a text channel.
        
        Parameters
        ----------
        message: discord.Message
            The message to check.
            
        Returns
        -------
        bool
            True if the message is from a guild text channel, False otherwise.
        """
        return (
            message.guild is not None 
            and isinstance(message.channel, discord.TextChannel)
            and isinstance(message.author, discord.Member)
        )

    async def _get_log_channel(self, guild: discord.Guild) -> Optional[discord.TextChannel]:
        """Get the log channel for a guild.
        
        Parameters
        ----------
        guild: discord.Guild
            The guild to get the log channel for.
            
        Returns
        -------
        Optional[discord.TextChannel]
            The text channel set for logging, or None if not set.
        """
        if not guild:
            return None
        channel_id = await self.config.guild(guild).log_channel()
        if not channel_id:
            return None
        channel = guild.get_channel(channel_id)
        return cast(discord.TextChannel, channel) if isinstance(channel, discord.TextChannel) else None

    async def _should_log(
        self,
        guild: discord.Guild,
        event: str,
        channel: Optional[discord.abc.GuildChannel] = None,
        user: Optional[discord.Member] = None
    ) -> bool:
        """Check if an event should be logged based on guild settings.
        
        Parameters
        ----------
        guild: discord.Guild
            The guild where the event occurred.
        event: str
            The event type as a string.
        channel: Optional[discord.abc.GuildChannel]
            The channel where the event occurred, if applicable.
        user: Optional[discord.Member]
            The user associated with the event, if applicable.
            
        Returns
        -------
        bool
            True if the event should be logged, False otherwise.
        """
        if not guild:
            return False
            
        data = await self.config.guild(guild).all()
        
        # Check if logging is enabled and channel exists
        if not data["log_channel"]:
            return False
            
        # Check if event is enabled
        if not data["events"].get(event, False):
            return False
            
        # Check ignore lists
        if channel:
            if channel.id in data["ignored_channels"]:
                return False
            if (
                isinstance(channel, discord.TextChannel)
                and channel.category
                and channel.category.id in data["ignored_categories"]
            ):
                return False
                
        if user and user.id in data["ignored_users"]:
            return False
            
        return True

    @commands.group(name="log")
    @commands.guild_only()
    @commands.admin_or_permissions(manage_guild=True)
    async def _log(self, ctx: commands.Context) -> None:
        """Configure server logging settings."""
        if ctx.invoked_subcommand is None:
            await ctx.send_help()

    @_log.command(name="channel")
    async def set_log_channel(self, ctx: commands.Context, *, channel: Optional[discord.TextChannel] = None) -> None:
        """Set the channel for server logs."""
        channel = channel or ctx.channel
        if not isinstance(channel, discord.TextChannel):
            await ctx.send("❌ That's not a valid text channel!")
            return
            
        await self.config.guild(ctx.guild).log_channel.set(channel.id)
        await ctx.send(f"✅ Log channel set to {channel.mention}")

    @_log.command(name="toggle")
    async def toggle_event(self, ctx: commands.Context, *, event: Optional[str] = None) -> None:
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

    @_log.group(name="ignore")
    async def _ignore(self, ctx: commands.Context) -> None:
        """Manage ignored users, channels, and categories."""
        if ctx.invoked_subcommand is None:
            await ctx.send_help()

    @_ignore.command(name="user")
    async def ignore_user(self, ctx: commands.Context, user: discord.Member) -> None:
        """Ignore a user from being logged."""
        async with self.config.guild(ctx.guild).ignored_users() as ignored:
            if user.id in ignored:
                await ctx.send(f"❌ {user.mention} is already ignored")
                return
            ignored.append(user.id)
        await ctx.send(f"✅ Now ignoring {user.mention}")

    @_ignore.command(name="channel")
    async def ignore_channel(self, ctx: commands.Context, channel: discord.TextChannel) -> None:
        """Ignore a channel from being logged."""
        async with self.config.guild(ctx.guild).ignored_channels() as ignored:
            if channel.id in ignored:
                await ctx.send(f"❌ {channel.mention} is already ignored")
                return
            ignored.append(channel.id)
        await ctx.send(f"✅ Now ignoring {channel.mention}")

    @_ignore.command(name="category")
    async def ignore_category(self, ctx: commands.Context, category: discord.CategoryChannel) -> None:
        """Ignore an entire category from being logged."""
        async with self.config.guild(ctx.guild).ignored_categories() as ignored:
            if category.id in ignored:
                await ctx.send(f"❌ Category {category.name} is already ignored")
                return
            ignored.append(category.id)
        await ctx.send(f"✅ Now ignoring category {category.name}")

    @_log.group(name="unignore")
    async def _unignore(self, ctx: commands.Context) -> None:
        """Remove users, channels, or categories from ignore list."""
        if ctx.invoked_subcommand is None:
            await ctx.send_help()

    @_unignore.command(name="user")
    async def unignore_user(self, ctx: commands.Context, user: discord.Member) -> None:
        """Stop ignoring a user."""
        async with self.config.guild(ctx.guild).ignored_users() as ignored:
            if user.id not in ignored:
                await ctx.send(f"❌ {user.mention} is not ignored")
                return
            ignored.remove(user.id)
        await ctx.send(f"✅ No longer ignoring {user.mention}")

    @_unignore.command(name="channel")
    async def unignore_channel(self, ctx: commands.Context, channel: discord.TextChannel) -> None:
        """Stop ignoring a channel."""
        async with self.config.guild(ctx.guild).ignored_channels() as ignored:
            if channel.id not in ignored:
                await ctx.send(f"❌ {channel.mention} is not ignored")
                return
            ignored.remove(channel.id)
        await ctx.send(f"✅ No longer ignoring {channel.mention}")

    @_unignore.command(name="category")
    async def unignore_category(self, ctx: commands.Context, category: discord.CategoryChannel) -> None:
        """Stop ignoring a category."""
        async with self.config.guild(ctx.guild).ignored_categories() as ignored:
            if category.id not in ignored:
                await ctx.send(f"❌ Category {category.name} is not ignored")
                return
            ignored.remove(category.id)
        await ctx.send(f"✅ No longer ignoring category {category.name}")

    @_log.command(name="show")
    async def show_settings(self, ctx: commands.Context) -> None:
        """Show current logging settings."""
        settings = await self.config.guild(ctx.guild).all()
        
        log_channel = ctx.guild.get_channel(settings["log_channel"]) if settings["log_channel"] else None
        
        embed = discord.Embed(
            title="📝 Logging Settings",
            color=discord.Color.blue(),
            timestamp=discord.utils.utcnow()
        )
        
        embed.add_field(
            name="Log Channel",
            value=log_channel.mention if log_channel else "*Not set*",
            inline=False
        )
        
        # Show enabled events
        enabled = [k for k, v in settings["events"].items() if v]
        if enabled:
            embed.add_field(
                name="Enabled Events",
                value="\n".join(f"✅ {e}" for e in enabled),
                inline=False
            )
        
        # Show ignored entities
        ignored_users = []
        for uid in settings["ignored_users"]:
            user = ctx.guild.get_member(uid)
            if user:
                ignored_users.append(user.mention)
        
        ignored_channels = []
        for cid in settings["ignored_channels"]:
            channel = ctx.guild.get_channel(cid)
            if channel:
                ignored_channels.append(channel.mention)
                
        ignored_categories = []
        for cid in settings["ignored_categories"]:
            category = ctx.guild.get_channel(cid)
            if category:
                ignored_categories.append(category.name)
                
        if ignored_users:
            embed.add_field(name="Ignored Users", value="\n".join(ignored_users), inline=False)
        if ignored_channels:
            embed.add_field(name="Ignored Channels", value="\n".join(ignored_channels), inline=False)
        if ignored_categories:
            embed.add_field(name="Ignored Categories", value="\n".join(ignored_categories), inline=False)
            
        await ctx.send(embed=embed)

    @commands.Cog.listener()
    async def on_message_delete(self, message: discord.Message) -> None:
        """Log message deletions."""
        if not await self._is_guild_message(message):
            return
            
        guild = cast(discord.Guild, message.guild)
        channel = cast(discord.TextChannel, message.channel)
        author = cast(discord.Member, message.author)
            
        if not await self._should_log(guild, "message_delete", channel, author):
            return
            
        log_channel = await self._get_log_channel(guild)
        if not log_channel:
            return
            
        embed = discord.Embed(
            description=f"**Message sent by {author.mention} deleted in {channel.mention}**\n{message.content}",
            color=discord.Color.red(),
            timestamp=discord.utils.utcnow()
        )
        embed.set_author(name=str(author), icon_url=author.display_avatar.url)
        
        if message.attachments:
            embed.add_field(
                name="Attachments",
                value="\n".join(a.filename for a in message.attachments),
                inline=False
            )
            
        await log_channel.send(embed=embed)

    @commands.Cog.listener()
    async def on_message_edit(self, before: discord.Message, after: discord.Message) -> None:
        """Log message edits."""
        if not all([
            await self._is_guild_message(before),
            before.content != after.content  # Only log if content changed
        ]):
            return
            
        guild = cast(discord.Guild, before.guild)
        channel = cast(discord.TextChannel, before.channel)
        author = cast(discord.Member, before.author)
            
        if not await self._should_log(guild, "message_edit", channel, author):
            return
            
        log_channel = await self._get_log_channel(guild)
        if not log_channel:
            return
            
        embed = discord.Embed(
            description=f"**Message edited in {channel.mention}**",
            color=discord.Color.blue(),
            timestamp=discord.utils.utcnow()
        )
        embed.set_author(name=str(author), icon_url=author.display_avatar.url)
        embed.add_field(name="Before", value=before.content[:1024] or "*Empty message*", inline=False)
        embed.add_field(name="After", value=after.content[:1024] or "*Empty message*", inline=False)
        embed.add_field(name="Jump to", value=f"[Message]({after.jump_url})", inline=False)
        
        await log_channel.send(embed=embed)

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member) -> None:
        """Log member joins."""
        if not await self._should_log(member.guild, "member_join"):
            return
            
        log_channel = await self._get_log_channel(member.guild)
        if not log_channel:
            return
            
        embed = discord.Embed(
            description=f"👋 {member.mention} joined the server",
            color=discord.Color.green(),
            timestamp=discord.utils.utcnow()
        )
        embed.set_author(name=str(member), icon_url=member.display_avatar.url)
        embed.add_field(name="Account created", value=discord.utils.format_dt(member.created_at, "R"))
        
        await log_channel.send(embed=embed)

    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member) -> None:
        """Log member leaves."""
        if not await self._should_log(member.guild, "member_leave"):
            return
            
        log_channel = await self._get_log_channel(member.guild)
        if not log_channel:
            return
            
        embed = discord.Embed(
            description=f"👋 {member.mention} left the server",
            color=discord.Color.red(),
            timestamp=discord.utils.utcnow()
        )
        embed.set_author(name=str(member), icon_url=member.display_avatar.url)
        
        # Try to get ban info to differentiate between leaves and kicks/bans
        try:
            ban = await member.guild.fetch_ban(member)
            if ban:
                embed.description = f"🔨 {member.mention} was banned\nReason: {ban.reason or 'No reason provided'}"
                embed.color = discord.Color.dark_red()
        except discord.NotFound:
            pass
            
        await log_channel.send(embed=embed)

    @commands.Cog.listener()
    async def on_member_update(self, before: discord.Member, after: discord.Member) -> None:
        """Log member updates (roles, nickname, etc)."""
        if not await self._should_log(after.guild, "member_update"):
            return
            
        log_channel = await self._get_log_channel(after.guild)
        if not log_channel:
            return
            
        embed = None
        
        # Nickname change
        if before.nick != after.nick:
            embed = discord.Embed(
                description=f"📝 Nickname changed for {after.mention}",
                color=discord.Color.blue(),
                timestamp=discord.utils.utcnow()
            )
            embed.add_field(name="Before", value=before.nick or "*No nickname*")
            embed.add_field(name="After", value=after.nick or "*No nickname*")
            
        # Role changes
        elif before.roles != after.roles:
            added = set(after.roles) - set(before.roles)
            removed = set(before.roles) - set(after.roles)
            
            if added or removed:
                embed = discord.Embed(
                    description=f"👥 Roles updated for {after.mention}",
                    color=discord.Color.blue(),
                    timestamp=discord.utils.utcnow()
                )
                if added:
                    embed.add_field(name="Added", value=" ".join(r.mention for r in added))
                if removed:
                    embed.add_field(name="Removed", value=" ".join(r.mention for r in removed))
                    
        if embed:
            embed.set_author(name=str(after), icon_url=after.display_avatar.url)
            await log_channel.send(embed=embed)

    @commands.Cog.listener()
    async def on_guild_channel_create(self, channel: discord.abc.GuildChannel) -> None:
        """Log channel creation."""
        if not await self._should_log(channel.guild, "channel_create"):
            return
            
        log_channel = await self._get_log_channel(channel.guild)
        if not log_channel:
            return
            
        embed = discord.Embed(
            description=f"📝 Channel {channel.mention} was created",
            color=discord.Color.green(),
            timestamp=discord.utils.utcnow()
        )
        
        if isinstance(channel, discord.CategoryChannel):
            embed.description = f"📝 Category **{channel.name}** was created"
        
        await log_channel.send(embed=embed)

    @commands.Cog.listener()
    async def on_guild_channel_delete(self, channel: discord.abc.GuildChannel) -> None:
        """Log channel deletion."""
        if not await self._should_log(channel.guild, "channel_delete"):
            return
            
        log_channel = await self._get_log_channel(channel.guild)
        if not log_channel:
            return
            
        embed = discord.Embed(
            description=f"🗑️ Channel **#{channel.name}** was deleted",
            color=discord.Color.red(),
            timestamp=discord.utils.utcnow()
        )
        
        if isinstance(channel, discord.CategoryChannel):
            embed.description = f"🗑️ Category **{channel.name}** was deleted"
        
        await log_channel.send(embed=embed)

    @commands.Cog.listener()
    async def on_guild_channel_update(self, before: discord.abc.GuildChannel, after: discord.abc.GuildChannel) -> None:
        """Log channel updates."""
        if not await self._should_log(after.guild, "channel_update"):
            return
            
        log_channel = await self._get_log_channel(after.guild)
        if not log_channel:
            return
        
        changes = []
        
        if isinstance(before, discord.TextChannel) and isinstance(after, discord.TextChannel):
            if before.name != after.name:
                changes.append(f"Name: {before.name} ➔ {after.name}")
            if before.topic != after.topic:
                changes.append(f"Topic: {before.topic or '*No topic*'} ➔ {after.topic or '*No topic*'}")
            if before.slowmode_delay != after.slowmode_delay:
                changes.append(f"Slowmode: {before.slowmode_delay}s ➔ {after.slowmode_delay}s")
            if before.nsfw != after.nsfw:
                changes.append(f"NSFW: {before.nsfw} ➔ {after.nsfw}")
        
        if changes:
            embed = discord.Embed(
                title="📝 Channel Updated",
                description=f"Changes in {after.mention}:\n" + "\n".join(f"• {c}" for c in changes),
                color=discord.Color.blue(),
                timestamp=discord.utils.utcnow()
            )
            await log_channel.send(embed=embed)

    @commands.Cog.listener()
    async def on_thread_create(self, thread: discord.Thread) -> None:
        """Log thread creation."""
        if not await self._should_log(thread.guild, "channel_create"):
            return
            
        log_channel = await self._get_log_channel(thread.guild)
        if not log_channel:
            return
            
        embed = discord.Embed(
            title="🧵 Thread Created",
            description=f"Thread {thread.mention} was created in {thread.parent.mention if thread.parent else 'Unknown Channel'}",
            color=discord.Color.green(),
            timestamp=discord.utils.utcnow()
        )
        
        if thread.owner:
            embed.add_field(name="Created By", value=thread.owner.mention)
            
        await log_channel.send(embed=embed)

    @commands.Cog.listener()
    async def on_thread_delete(self, thread: discord.Thread) -> None:
        """Log thread deletion."""
        if not await self._should_log(thread.guild, "channel_delete"):
            return
            
        log_channel = await self._get_log_channel(thread.guild)
        if not log_channel:
            return
            
        embed = discord.Embed(
            title="🧵 Thread Deleted",
            description=f"Thread **{thread.name}** was deleted from {thread.parent.mention if thread.parent else 'Unknown Channel'}",
            color=discord.Color.red(),
            timestamp=discord.utils.utcnow()
        )
        await log_channel.send(embed=embed)

    @commands.Cog.listener()
    async def on_thread_update(self, before: discord.Thread, after: discord.Thread) -> None:
        """Log thread updates."""
        if not await self._should_log(after.guild, "channel_update"):
            return
            
        log_channel = await self._get_log_channel(after.guild)
        if not log_channel:
            return
            
        changes = []
        
        if before.name != after.name:
            changes.append(f"Name: {before.name} ➔ {after.name}")
        if before.archived != after.archived:
            changes.append(f"{'Archived' if after.archived else 'Unarchived'}")
        if before.locked != after.locked:
            changes.append(f"{'Locked' if after.locked else 'Unlocked'}")
            
        if changes:
            embed = discord.Embed(
                title="🧵 Thread Updated",
                description=f"Changes in {after.mention}:\n" + "\n".join(f"• {c}" for c in changes),
                color=discord.Color.blue(),
                timestamp=discord.utils.utcnow()
            )
            await log_channel.send(embed=embed)

    @commands.Cog.listener()
    async def on_webhook_update(self, channel: discord.TextChannel) -> None:
        """Log webhook changes."""
        if not await self._should_log(channel.guild, "channel_update"):
            return
            
        log_channel = await self._get_log_channel(channel.guild)
        if not log_channel:
            return
            
        embed = discord.Embed(
            title="🔗 Webhook Updated",
            description=f"Webhooks were updated in {channel.mention}",
            color=discord.Color.blue(),
            timestamp=discord.utils.utcnow()
        )
        await log_channel.send(embed=embed)

    @commands.Cog.listener()
    async def on_guild_role_create(self, role: discord.Role) -> None:
        """Log role creation."""
        if not await self._should_log(role.guild, "role_create"):
            return
            
        log_channel = await self._get_log_channel(role.guild)
        if not log_channel:
            return
            
        embed = discord.Embed(
            title="👥 Role Created",
            description=f"Role {role.mention} was created",
            color=role.color,
            timestamp=discord.utils.utcnow()
        )
        
        perms = []
        for perm, value in role.permissions:
            if value:
                perms.append(perm.replace("_", " ").title())
        
        if perms:
            embed.add_field(name="Permissions", value="\n".join(f"✅ {p}" for p in perms))
            
        await log_channel.send(embed=embed)

    @commands.Cog.listener()
    async def on_guild_role_delete(self, role: discord.Role) -> None:
        """Log role deletion."""
        if not await self._should_log(role.guild, "role_delete"):
            return
            
        log_channel = await self._get_log_channel(role.guild)
        if not log_channel:
            return
            
        embed = discord.Embed(
            title="👥 Role Deleted",
            description=f"Role **{role.name}** was deleted",
            color=discord.Color.red(),
            timestamp=discord.utils.utcnow()
        )
        await log_channel.send(embed=embed)

    @commands.Cog.listener()
    async def on_guild_role_update(self, before: discord.Role, after: discord.Role) -> None:
        """Log role updates."""
        if not await self._should_log(after.guild, "role_update"):
            return
            
        log_channel = await self._get_log_channel(after.guild)
        if not log_channel:
            return
            
        changes = []
        
        if before.name != after.name:
            changes.append(f"Name: {before.name} ➔ {after.name}")
        if before.color != after.color:
            changes.append(f"Color: {before.color} ➔ {after.color}")
        if before.hoist != after.hoist:
            changes.append(f"Hoisted: {before.hoist} ➔ {after.hoist}")
        if before.mentionable != after.mentionable:
            changes.append(f"Mentionable: {before.mentionable} ➔ {after.mentionable}")
            
        # Check permission changes
        perm_changes = []
        for perm, value in after.permissions:
            if value != getattr(before.permissions, perm):
                perm_changes.append(f"{perm.replace('_', ' ').title()}: {getattr(before.permissions, perm)} ➔ {value}")
                
        if changes or perm_changes:
            embed = discord.Embed(
                title="👥 Role Updated",
                description=f"Changes in {after.mention}:",
                color=after.color,
                timestamp=discord.utils.utcnow()
            )
            
            if changes:
                embed.add_field(name="General Changes", value="\n".join(f"• {c}" for c in changes), inline=False)
            if perm_changes:
                embed.add_field(name="Permission Changes", value="\n".join(f"• {c}" for c in perm_changes), inline=False)
                
            await log_channel.send(embed=embed)

    @commands.Cog.listener()
    async def on_voice_state_update(self, member: discord.Member, before: discord.VoiceState, after: discord.VoiceState) -> None:
        """Log voice channel events."""
        if not await self._should_log(member.guild, "voice_update", user=member):
            return
            
        log_channel = await self._get_log_channel(member.guild)
        if not log_channel:
            return
            
        embed = discord.Embed(
            title="🎤 Voice Update",
            color=discord.Color.blue(),
            timestamp=discord.utils.utcnow()
        )
        embed.set_author(name=str(member), icon_url=member.display_avatar.url)
        
        # Track channel changes
        if before.channel != after.channel:
            if before.channel is None and after.channel is not None:
                embed.description = f"{member.mention} joined voice channel {after.channel.mention}"
                embed.color = discord.Color.green()
            elif before.channel is not None and after.channel is None:
                embed.description = f"{member.mention} left voice channel {before.channel.mention}"
                embed.color = discord.Color.red()
            elif before.channel is not None and after.channel is not None:
                embed.description = f"{member.mention} moved from {before.channel.mention} to {after.channel.mention}"
                
        # Track mute/deafen changes
        elif before.self_mute != after.self_mute:
            embed.description = f"{member.mention} {'muted' if after.self_mute else 'unmuted'} themselves"
        elif before.self_deaf != after.self_deaf:
            embed.description = f"{member.mention} {'deafened' if after.self_deaf else 'undeafened'} themselves"
        elif before.mute != after.mute:
            embed.description = f"{member.mention} was {'server muted' if after.mute else 'server unmuted'}"
        elif before.deaf != after.deaf:
            embed.description = f"{member.mention} was {'server deafened' if after.deaf else 'server undeafened'}"
        else:
            return  # No relevant changes
            
        await log_channel.send(embed=embed)

    @commands.Cog.listener()
    async def on_guild_emojis_update(self, guild: discord.Guild, before: tuple[discord.Emoji, ...], after: tuple[discord.Emoji, ...]) -> None:
        """Log emoji updates."""
        if not await self._should_log(guild, "emoji_update"):
            return
            
        log_channel = await self._get_log_channel(guild)
        if not log_channel:
            return
            
        # Find added and removed emojis
        before_ids = {e.id for e in before}
        after_ids = {e.id for e in after}
        
        added = [e for e in after if e.id not in before_ids]
        removed = [e for e in before if e.id not in after_ids]
        
        if added:
            embed = discord.Embed(
                title="😀 Emoji Added",
                description="\n".join(f"{str(e)} `:{e.name}:`" for e in added),
                color=discord.Color.green(),
                timestamp=discord.utils.utcnow()
            )
            await log_channel.send(embed=embed)
            
        if removed:
            embed = discord.Embed(
                title="😢 Emoji Removed",
                description="\n".join(f"`:{e.name}:`" for e in removed),
                color=discord.Color.red(),
                timestamp=discord.utils.utcnow()
            )
            await log_channel.send(embed=embed)

    @commands.Cog.listener()
    async def on_guild_update(self, before: discord.Guild, after: discord.Guild) -> None:
        """Log server setting changes."""
        if not await self._should_log(after, "guild_update"):
            return
            
        log_channel = await self._get_log_channel(after)
        if not log_channel:
            return
            
        changes = []
        
        if before.name != after.name:
            changes.append(f"Name: {before.name} ➔ {after.name}")
        if before.description != after.description:
            changes.append(f"Description: {before.description or '*None*'} ➔ {after.description or '*None*'}")
        if before.icon != after.icon:
            changes.append("Server icon was changed")
        if before.banner != after.banner:
            changes.append("Server banner was changed")
        if before.splash != after.splash:
            changes.append("Invite splash image was changed")
        if before.discovery_splash != after.discovery_splash:
            changes.append("Discovery splash image was changed")
        if before.owner_id != after.owner_id:
            changes.append(f"Owner: <@{before.owner_id}> ➔ <@{after.owner_id}>")
        if before.verification_level != after.verification_level:
            changes.append(f"Verification Level: {before.verification_level} ➔ {after.verification_level}")
        if before.explicit_content_filter != after.explicit_content_filter:
            changes.append(f"Content Filter: {before.explicit_content_filter} ➔ {after.explicit_content_filter}")
        if before.vanity_url_code != after.vanity_url_code:
            changes.append(f"Vanity URL: {before.vanity_url_code or '*None*'} ➔ {after.vanity_url_code or '*None*'}")
        
        if changes:
            embed = discord.Embed(
                title="🏰 Server Updated",
                description="\n".join(f"• {c}" for c in changes),
                color=discord.Color.blue(),
                timestamp=discord.utils.utcnow()
            )
            
            # Add new icon preview if it changed
            if before.icon != after.icon and after.icon:
                embed.set_thumbnail(url=after.icon.url)
                
            await log_channel.send(embed=embed)

    # Utility method to check audit logs
    async def get_audit_log_entry(self, guild: discord.Guild, action: discord.AuditLogAction, target_id: Optional[int] = None) -> Optional[discord.AuditLogEntry]:
        """Get the most recent audit log entry for an action."""
        try:
            async for entry in guild.audit_logs(limit=1, action=action):
                if target_id is None:
                    return entry
                if entry.target and hasattr(entry.target, 'id') and entry.target.id == target_id:
                    return entry
        except (discord.Forbidden, discord.HTTPException):
            pass
        return None
