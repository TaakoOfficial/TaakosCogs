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
from redbot.core import modlog

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
            "thread_member_leave": ("⬅️", "Thread member leaves"),
            # Forum events
            "forum_post_create": ("📰", "Forum post created"),
            "forum_post_update": ("📰", "Forum post updated"),
            "forum_post_delete": ("📰", "Forum post deleted")
        }
        self.tupperbox_default_ids = ["272885620769161216"]  # Default Tupperbox bot user ID
        default_guild = {
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
                "thread_member_leave": False,
                # Forum events
                "forum_post_create": False,
                "forum_post_update": False,
                "forum_post_delete": False
            },
            "ignored_commands": [],
            "ignored_cogs": [],
            "ignore_tupperbox": True,
            "tupperbox_ids": self.tupperbox_default_ids.copy(),
        }
        self.config.register_guild(**default_guild)

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
        """Get the appropriate logging channel for an event. Only event_channels is used."""
        settings = await self.config.guild(guild).all()
        self.log.debug(f"[get_log_channel] Guild: {guild.id}, Event: {event_type}, Settings: {settings}")
        channel_id = settings["event_channels"].get(event_type)
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

    def set_embed_footer(self, embed: discord.Embed) -> None:
        """Set a standard footer for all log embeds."""
        embed.set_footer(
            text="YALC Logger",
            icon_url="https://cdn-icons-png.flaticon.com/512/928/928797.png"
        )

    async def cog_unload(self) -> None:
        """Cleanup tasks when the cog is unloaded."""
        pass

    async def cog_load(self) -> None:
        """Register all YALC events as modlog case types."""
        case_types = []
        for event, (emoji, description) in self.event_descriptions.items():
            case_types.append({
                "name": event,
                "default_setting": False,
                "image": emoji,
                "case_str": description
            })
        try:
            await modlog.register_casetypes(case_types)
            self.log.info("Registered all YALC events as modlog case types.")
        except Exception as e:
            self.log.error(f"Failed to register YALC case types: {e}")

    async def safe_send(
        self,
        channel: discord.TextChannel,
        *,
        content: Optional[str] = None,
        embed: Optional[discord.Embed] = None
    ) -> None:
        """Safely send a message or embed to a channel, logging any errors."""
        try:
            if embed is not None:
                await channel.send(content=content, embed=embed)
            else:
                await channel.send(content=content)
        except Exception as e:
            self.log.error(f"Failed to send message to {channel}: {e}")

    # --- Event Listeners ---

    @commands.Cog.listener()
    async def on_message_delete(self, message: discord.Message) -> None:
        """Log message deletion events."""
        self.log.debug("Listener triggered: on_message_delete")
        if not message.guild:
            self.log.debug("No guild on message.")
            return
        try:
            should_log = await self.should_log_event(message.guild, "message_delete")
        except Exception as e:
            self.log.error(f"Error in should_log_event: {e}")
            return
        if not should_log:
            self.log.debug("should_log_event returned False for message_delete.")
            return
        try:
            channel = await self.get_log_channel(message.guild, "message_delete")
        except Exception as e:
            self.log.error(f"Error in get_log_channel: {e}")
            return
        self.log.debug(f"About to send to channel: {channel}")
        if not channel:
            self.log.warning("No log channel set for message_delete.")
            return
        try:
            settings = await self.config.guild(message.guild).all()
            if settings.get("ignore_tupperbox", True) and self.is_tupperbox_message(message, settings.get("tupperbox_ids", self.tupperbox_default_ids)):
                self.log.debug("Skipping Tupperbox message_delete event.")
                return
        except Exception as e:
            self.log.error(f"Error checking Tupperbox ignore: {e}")
        try:
            author = getattr(message, "author", None)
            content = getattr(message, "content", "")
            attachments = [a.url for a in getattr(message, "attachments", [])]
            embeds = getattr(message, "embeds", [])
            channel_name = getattr(message.channel, "name", str(message.channel) if message.channel else "Unknown")
            self.log.debug(f"Logging message_delete: author={author}, content={content}, attachments={attachments}, embeds={embeds}, channel_name={channel_name}")
            embed = self.create_embed(
                "message_delete",
                f"🗑️ Message deleted in {getattr(message.channel, 'mention', str(message.channel))}",
                user=f"{author} ({getattr(author, 'id', 'N/A')})" if author else "Unknown",
                content=content,
                attachments=attachments,
                embeds=embeds,
                channel_name=channel_name
            )
            await self.safe_send(channel, embed=embed)
        except Exception as e:
            self.log.error(f"Failed to log message_delete: {e}")

    @commands.Cog.listener()
    async def on_message_edit(self, before: discord.Message, after: discord.Message) -> None:
        """Log message edit events."""
        self.log.debug("Listener triggered: on_message_edit")
        if not before.guild:
            self.log.debug("No guild on message.")
            return
        try:
            should_log = await self.should_log_event(before.guild, "message_edit")
        except Exception as e:
            self.log.error(f"Error in should_log_event: {e}")
            return
        if not should_log:
            self.log.debug("should_log_event returned False for message_edit.")
            return
        try:
            channel = await self.get_log_channel(before.guild, "message_edit")
        except Exception as e:
            self.log.error(f"Error in get_log_channel: {e}")
            return
        self.log.debug(f"About to send to channel: {channel}")
        if not channel:
            self.log.warning("No log channel set for message_edit.")
            return
        try:
            settings = await self.config.guild(before.guild).all()
            if settings.get("ignore_tupperbox", True) and self.is_tupperbox_message(before, settings.get("tupperbox_ids", self.tupperbox_default_ids)):
                self.log.debug("Skipping Tupperbox message_edit event.")
                return
        except Exception as e:
            self.log.error(f"Error checking Tupperbox ignore: {e}")
        try:
            author = getattr(before, "author", None)
            content_before = getattr(before, "content", "")
            content_after = getattr(after, "content", "")
            attachments = [a.url for a in getattr(after, "attachments", [])]
            embeds = getattr(after, "embeds", [])
            channel_name = getattr(before.channel, "name", str(before.channel) if before.channel else "Unknown")
            self.log.debug(f"Logging message_edit: author={author}, before={content_before}, after={content_after}, attachments={attachments}, embeds={embeds}, channel_name={channel_name}")
            embed = self.create_embed(
                "message_edit",
                f"✏️ Message edited in {getattr(before.channel, 'mention', str(before.channel))}",
                user=f"{author} ({getattr(author, 'id', 'N/A')})" if author else "Unknown",
                content=f"**Before:** {content_before}\n**After:** {content_after}",
                attachments=attachments,
                embeds=embeds,
                channel_name=channel_name
            )
            await self.safe_send(channel, embed=embed)
        except Exception as e:
            self.log.error(f"Failed to log message_edit: {e}")

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member) -> None:
        """Log member join events."""
        self.log.debug("Listener triggered: on_member_join")
        if not member.guild:
            self.log.debug("No guild on member.")
            return
        try:
            should_log = await self.should_log_event(member.guild, "member_join")
        except Exception as e:
            self.log.error(f"Error in should_log_event: {e}")
            return
        if not should_log:
            self.log.debug("should_log_event returned False for member_join.")
            return
        try:
            channel = await self.get_log_channel(member.guild, "member_join")
        except Exception as e:
            self.log.error(f"Error in get_log_channel: {e}")
            return
        self.log.debug(f"About to send to channel: {channel}")
        if not channel:
            self.log.warning("No log channel set for member_join.")
            return
        try:
            embed = self.create_embed(
                "member_join",
                f"👋 {member} has joined the server.",
                user=f"{member} ({member.id})"
            )
            await self.safe_send(channel, embed=embed)
        except Exception as e:
            self.log.error(f"Failed to log member_join: {e}")

    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member) -> None:
        """Log member leave events."""
        self.log.debug("Listener triggered: on_member_remove")
        if not member.guild:
            self.log.debug("No guild on member.")
            return
        try:
            should_log = await self.should_log_event(member.guild, "member_leave")
        except Exception as e:
            self.log.error(f"Error in should_log_event: {e}")
            return
        if not should_log:
            self.log.debug("should_log_event returned False for member_leave.")
            return
        try:
            channel = await self.get_log_channel(member.guild, "member_leave")
        except Exception as e:
            self.log.error(f"Error in get_log_channel: {e}")
            return
        self.log.debug(f"About to send to channel: {channel}")
        if not channel:
            self.log.warning("No log channel set for member_leave.")
            return
        try:
            embed = self.create_embed(
                "member_leave",
                f"👋 {member} has left the server.",
                user=f"{member} ({member.id})"
            )
            await self.safe_send(channel, embed=embed)
        except Exception as e:
            self.log.error(f"Failed to log member_leave: {e}")

    @commands.Cog.listener()
    async def on_member_ban(self, guild: discord.Guild, user: discord.User) -> None:
        """Log member ban events."""
        self.log.debug("Listener triggered: on_member_ban")
        if not guild or not await self.should_log_event(guild, "member_ban"):
            return
        channel = await self.get_log_channel(guild, "member_ban")
        self.log.debug(f"About to send to channel: {channel}")
        if not channel:
            return
        embed = self.create_embed(
            "member_ban",
            f"🔨 {user} has been banned.",
            user=f"{user} ({user.id})",
            channel_name=guild.name if guild else "Unknown"
        )
        await self.safe_send(channel, embed=embed)

    @commands.Cog.listener()
    async def on_member_unban(self, guild: discord.Guild, user: discord.User) -> None:
        """Log member unban events."""
        self.log.debug("Listener triggered: on_member_unban")
        if not guild or not await self.should_log_event(guild, "member_unban"):
            return
        channel = await self.get_log_channel(guild, "member_unban")
        self.log.debug(f"About to send to channel: {channel}")
        if not channel:
            return
        embed = self.create_embed(
            "member_unban",
            f"🔓 {user} has been unbanned.",
            user=f"{user} ({user.id})",
            channel_name=guild.name if guild else "Unknown"
        )
        await self.safe_send(channel, embed=embed)

    @commands.Cog.listener()
    async def on_member_update(self, before: discord.Member, after: discord.Member) -> None:
        self.log.debug("Listener triggered: on_member_update")
        if not before.guild:
            self.log.debug("No guild on member.")
            return
        try:
            should_log = await self.should_log_event(before.guild, "member_update")
        except Exception as e:
            self.log.error(f"Error in should_log_event: {e}")
            return
        if not should_log:
            self.log.debug("should_log_event returned False for member_update.")
            return
        try:
            channel = await self.get_log_channel(before.guild, "member_update")
        except Exception as e:
            self.log.error(f"Error in get_log_channel: {e}")
            return
        self.log.debug(f"About to send to channel: {channel}")
        if not channel:
            self.log.warning("No log channel set for member_update.")
            return
        try:
            changes = []
            if before.roles != after.roles:
                changes.append("roles")
            if before.nick != after.nick:
                changes.append("nickname")
            channel_name = before.guild.name if before.guild else "Unknown"
            embed = self.create_embed(
                "member_update",
                f"👤 {after}'s information has been updated: {', '.join(changes)}",
                user=f"{before} ({before.id})",
                changes=", ".join(changes),
                channel_name=channel_name
            )
            await self.safe_send(channel, embed=embed)
        except Exception as e:
            self.log.error(f"Failed to log member_update: {e}")

    @commands.Cog.listener()
    async def on_guild_channel_create(self, channel: discord.abc.GuildChannel) -> None:
        self.log.debug("Listener triggered: on_guild_channel_create")
        if not channel.guild:
            self.log.debug("No guild on channel.")
            return
        try:
            should_log = await self.should_log_event(channel.guild, "channel_create", channel)
        except Exception as e:
            self.log.error(f"Error in should_log_event: {e}")
            return
        if not should_log:
            self.log.debug("should_log_event returned False for channel_create.")
            return
        try:
            log_channel = await self.get_log_channel(channel.guild, "channel_create")
        except Exception as e:
            self.log.error(f"Error in get_log_channel: {e}")
            return
        self.log.debug(f"About to send to channel: {log_channel}")
        if not log_channel:
            self.log.warning("No log channel set for channel_create.")
            return
        try:
            embed = self.create_embed(
                "channel_create",
                f"📝 Channel created: {getattr(channel, 'mention', str(channel))}",
                name=channel.name,
                id=channel.id,
                type=type(channel).__name__,
                channel_name=channel.name
            )
            await self.safe_send(log_channel, embed=embed)
        except Exception as e:
            self.log.error(f"Failed to log channel_create: {e}")

    @commands.Cog.listener()
    async def on_guild_channel_delete(self, channel: discord.abc.GuildChannel) -> None:
        self.log.debug("Listener triggered: on_guild_channel_delete")
        if not channel.guild:
            self.log.debug("No guild on channel.")
            return
        try:
            should_log = await self.should_log_event(channel.guild, "channel_delete", channel)
        except Exception as e:
            self.log.error(f"Error in should_log_event: {e}")
            return
        if not should_log:
            self.log.debug("should_log_event returned False for channel_delete.")
            return
        try:
            log_channel = await self.get_log_channel(channel.guild, "channel_delete")
        except Exception as e:
            self.log.error(f"Error in get_log_channel: {e}")
            return
        self.log.debug(f"About to send to channel: {log_channel}")
        if not log_channel:
            self.log.warning("No log channel set for channel_delete.")
            return
        try:
            embed = self.create_embed(
                "channel_delete",
                f"🗑️ Channel deleted: {getattr(channel, 'mention', str(channel))}",
                name=channel.name,
                id=channel.id,
                type=type(channel).__name__,
                channel_name=channel.name
            )
            await self.safe_send(log_channel, embed=embed)
        except Exception as e:
            self.log.error(f"Failed to log channel_delete: {e}")

    @commands.Cog.listener()
    async def on_guild_channel_update(self, before: discord.abc.GuildChannel, after: discord.abc.GuildChannel) -> None:
        self.log.debug("Listener triggered: on_guild_channel_update")
        if not before.guild:
            self.log.debug("No guild on channel.")
            return
        try:
            should_log = await self.should_log_event(before.guild, "channel_update", after)
        except Exception as e:
            self.log.error(f"Error in should_log_event: {e}")
            return
        if not should_log:
            self.log.debug("should_log_event returned False for channel_update.")
            return
        try:
            log_channel = await self.get_log_channel(before.guild, "channel_update")
        except Exception as e:
            self.log.error(f"Error in get_log_channel: {e}")
            return
        self.log.debug(f"About to send to channel: {log_channel}")
        if not log_channel:
            self.log.warning("No log channel set for channel_update.")
            return
        try:
            changes = []
            if hasattr(before, "name") and before.name != getattr(after, "name", None):
                changes.append(f"Name: {before.name} → {after.name}")
            if isinstance(before, discord.TextChannel) and isinstance(after, discord.TextChannel):
                if before.topic != after.topic:
                    changes.append(f"Topic: {before.topic} → {after.topic}")
                if before.nsfw != after.nsfw:
                    changes.append(f"NSFW: {before.nsfw} → {after.nsfw}")
                if before.slowmode_delay != after.slowmode_delay:
                    changes.append(f"Slowmode: {before.slowmode_delay}s → {after.slowmode_delay}s")
            if isinstance(before, discord.VoiceChannel) and isinstance(after, discord.VoiceChannel):
                if before.bitrate != after.bitrate:
                    changes.append(f"Bitrate: {before.bitrate} → {after.bitrate}")
                if before.user_limit != after.user_limit:
                    changes.append(f"User limit: {before.user_limit} → {after.user_limit}")
            if not changes:
                return
            embed = self.create_embed(
                "channel_update",
                f"🔄 Channel updated: {getattr(after, 'mention', str(after))}",
                changes="\n".join(changes),
                channel_name=after.name
            )
            await self.safe_send(log_channel, embed=embed)
        except Exception as e:
            self.log.error(f"Failed to log channel_update: {e}")

    @commands.Cog.listener()
    async def on_thread_create(self, thread: discord.Thread) -> None:
        self.log.debug("Listener triggered: on_thread_create")
        if not thread.guild:
            self.log.debug("No guild on thread.")
            return
        try:
            should_log = await self.should_log_event(thread.guild, "thread_create")
        except Exception as e:
            self.log.error(f"Error in should_log_event: {e}")
            return
        if not should_log:
            self.log.debug("should_log_event returned False for thread_create.")
            return
        try:
            log_channel = await self.get_log_channel(thread.guild, "thread_create")
        except Exception as e:
            self.log.error(f"Error in get_log_channel: {e}")
            return
        self.log.debug(f"About to send to channel: {log_channel}")
        if not log_channel:
            self.log.warning("No log channel set for thread_create.")
            return
        try:
            embed = self.create_embed(
                "thread_create",
                f"🧵 Thread created in {getattr(thread.parent, 'mention', None)}",
                thread=thread.mention,
                name=thread.name,
                creator=f"{thread.owner} ({thread.owner_id})" if thread.owner else f"ID: {thread.owner_id}",
                type=str(thread.type),
                slowmode=f"{thread.slowmode_delay}s" if thread.slowmode_delay else "None"
            )
            await self.safe_send(log_channel, embed=embed)
        except Exception as e:
            self.log.error(f"Failed to log thread_create: {e}")

    @commands.Cog.listener()
    async def on_thread_delete(self, thread: discord.Thread) -> None:
        self.log.debug("Listener triggered: on_thread_delete")
        if not thread.guild:
            self.log.debug("No guild on thread.")
            return
        try:
            should_log = await self.should_log_event(thread.guild, "thread_delete")
        except Exception as e:
            self.log.error(f"Error in should_log_event: {e}")
            return
        if not should_log:
            self.log.debug("should_log_event returned False for thread_delete.")
            return
        try:
            log_channel = await self.get_log_channel(thread.guild, "thread_delete")
        except Exception as e:
            self.log.error(f"Error in get_log_channel: {e}")
            return
        self.log.debug(f"About to send to channel: {log_channel}")
        if not log_channel:
            self.log.warning("No log channel set for thread_delete.")
            return
        try:
            embed = self.create_embed(
                "thread_delete",
                f"🗑️ Thread deleted from {getattr(thread.parent, 'mention', None)}",
                name=thread.name,
                archived=thread.archived,
                locked=thread.locked,
                type=str(thread.type)
            )
            await self.safe_send(log_channel, embed=embed)
        except Exception as e:
            self.log.error(f"Failed to log thread_delete: {e}")

    @commands.Cog.listener()
    async def on_thread_update(self, before: discord.Thread, after: discord.Thread) -> None:
        self.log.debug("Listener triggered: on_thread_update")
        if not before.guild:
            self.log.debug("No guild on thread.")
            return
        try:
            should_log = await self.should_log_event(before.guild, "thread_update")
        except Exception as e:
            self.log.error(f"Error in should_log_event: {e}")
            return
        if not should_log:
            self.log.debug("should_log_event returned False for thread_update.")
            return
        try:
            log_channel = await self.get_log_channel(before.guild, "thread_update")
        except Exception as e:
            self.log.error(f"Error in get_log_channel: {e}")
            return
        self.log.debug(f"About to send to channel: {log_channel}")
        if not log_channel:
            self.log.warning("No log channel set for thread_update.")
            return
        try:
            changes = []
            if before.name != after.name:
                changes.append(f"Name: {before.name} → {after.name}")
            if before.archived != after.archived:
                changes.append(f"Archived: {before.archived} → {after.archived}")
            if before.locked != after.locked:
                changes.append(f"Locked: {before.locked} → {after.locked}")
            if before.slowmode_delay != after.slowmode_delay:
                changes.append(f"Slowmode: {before.slowmode_delay}s → {after.slowmode_delay}s")
            if before.auto_archive_duration != after.auto_archive_duration:
                changes.append(f"Auto Archive: {before.auto_archive_duration} minutes → {after.auto_archive_duration} minutes")
            if not changes:
                return
            embed = self.create_embed(
                "thread_update",
                f"🔄 Thread updated in {getattr(after.parent, 'mention', None)}",
                thread=after.mention,
                changes="\n".join(changes)
            )
            await self.safe_send(log_channel, embed=embed)
        except Exception as e:
            self.log.error(f"Failed to log thread_update: {e}")

    @commands.Cog.listener()
    async def on_thread_member_join(self, member: discord.ThreadMember) -> None:
        self.log.debug("Listener triggered: on_thread_member_join")
        try:
            should_log = await self.should_log_event(member.thread.guild, "thread_member_join")
        except Exception as e:
            self.log.error(f"Error in should_log_event: {e}")
            return
        if not should_log:
            self.log.debug("should_log_event returned False for thread_member_join.")
            return
        try:
            log_channel = await self.get_log_channel(member.thread.guild, "thread_member_join")
        except Exception as e:
            self.log.error(f"Error in get_log_channel: {e}")
            return
        self.log.debug(f"About to send to channel: {log_channel}")
        if not log_channel:
            self.log.warning("No log channel set for thread_member_join.")
            return
        try:
            # Try to resolve the member as a guild member for mention
            resolved_member = member.thread.guild.get_member(member.id)
            member_display = resolved_member.mention if resolved_member else f"ID: {member.id}"
            embed = self.create_embed(
                "thread_member_join",
                f"➡️ Member joined thread {member.thread.mention}",
                member=f"{member_display} ({member.id})",
                thread=member.thread.name
            )
            await self.safe_send(log_channel, embed=embed)
        except Exception as e:
            self.log.error(f"Failed to log thread_member_join: {e}")

    @commands.Cog.listener()
    async def on_thread_member_remove(self, member: discord.ThreadMember) -> None:
        self.log.debug("Listener triggered: on_thread_member_remove")
        try:
            should_log = await self.should_log_event(member.thread.guild, "thread_member_leave")
        except Exception as e:
            self.log.error(f"Error in should_log_event: {e}")
            return
        if not should_log:
            self.log.debug("should_log_event returned False for thread_member_leave.")
            return
        try:
            log_channel = await self.get_log_channel(member.thread.guild, "thread_member_leave")
        except Exception as e:
            self.log.error(f"Error in get_log_channel: {e}")
            return
        self.log.debug(f"About to send to channel: {log_channel}")
        if not log_channel:
            self.log.warning("No log channel set for thread_member_leave.")
            return
        try:
            resolved_member = member.thread.guild.get_member(member.id)
            member_display = resolved_member.mention if resolved_member else f"ID: {member.id}"
            embed = self.create_embed(
                "thread_member_leave",
                f"⬅️ Member left thread {member.thread.mention}",
                member=f"{member_display} ({member.id})",
                thread=member.thread.name
            )
            await self.safe_send(log_channel, embed=embed)
        except Exception as e:
            self.log.error(f"Failed to log thread_member_leave: {e}")

    @commands.Cog.listener()
    async def on_role_create(self, role: discord.Role) -> None:
        self.log.debug("Listener triggered: on_role_create")
        if not role.guild:
            self.log.debug("No guild on role.")
            return
        try:
            should_log = await self.should_log_event(role.guild, "role_create")
        except Exception as e:
            self.log.error(f"Error in should_log_event: {e}")
            return
        if not should_log:
            self.log.debug("should_log_event returned False for role_create.")
            return
        try:
            channel = await self.get_log_channel(role.guild, "role_create")
        except Exception as e:
            self.log.error(f"Error in get_log_channel: {e}")
            return
        self.log.debug(f"About to send to channel: {channel}")
        if not channel:
            self.log.warning("No log channel set for role_create.")
            return
        try:
            embed = self.create_embed(
                "role_create",
                f"✨ Role created: {role.mention}",
                name=role.name,
                id=role.id
            )
            await self.safe_send(channel, embed=embed)
        except Exception as e:
            self.log.error(f"Failed to log role_create: {e}")

    @commands.Cog.listener()
    async def on_role_delete(self, role: discord.Role) -> None:
        self.log.debug("Listener triggered: on_role_delete")
        if not role.guild:
            self.log.debug("No guild on role.")
            return
        try:
            should_log = await self.should_log_event(role.guild, "role_delete")
        except Exception as e:
            self.log.error(f"Error in should_log_event: {e}")
            return
        if not should_log:
            self.log.debug("should_log_event returned False for role_delete.")
            return
        try:
            channel = await self.get_log_channel(role.guild, "role_delete")
        except Exception as e:
            self.log.error(f"Error in get_log_channel: {e}")
            return
        self.log.debug(f"About to send to channel: {channel}")
        if not channel:
            self.log.warning("No log channel set for role_delete.")
            return
        try:
            embed = self.create_embed(
                "role_delete",
                f"🗑️ Role deleted: {role.name}",
                name=role.name,
                id=role.id
            )
            await self.safe_send(channel, embed=embed)
        except Exception as e:
            self.log.error(f"Failed to log role_delete: {e}")

    @commands.Cog.listener()
    async def on_role_update(self, before: discord.Role, after: discord.Role) -> None:
        self.log.debug("Listener triggered: on_role_update")
        if not before.guild:
            self.log.debug("No guild on role.")
            return
        try:
            should_log = await self.should_log_event(before.guild, "role_update")
        except Exception as e:
            self.log.error(f"Error in should_log_event: {e}")
            return
        if not should_log:
            self.log.debug("should_log_event returned False for role_update.")
            return
        try:
            channel = await self.get_log_channel(before.guild, "role_update")
        except Exception as e:
            self.log.error(f"Error in get_log_channel: {e}")
            return
        self.log.debug(f"About to send to channel: {channel}")
        if not channel:
            self.log.warning("No log channel set for role_update.")
            return
        try:
            changes = []
            if before.name != after.name:
                changes.append(f"Name: {before.name} → {after.name}")
            if before.color != after.color:
                changes.append(f"Color: {before.color} → {after.color}")
            if before.permissions != after.permissions:
                changes.append("Permissions changed")
            if not changes:
                return
            embed = self.create_embed(
                "role_update",
                f"🔄 Role updated: {after.mention}",
                changes="\n".join(changes)
            )
            await self.safe_send(channel, embed=embed)
        except Exception as e:
            self.log.error(f"Failed to log role_update: {e}")

    @commands.Cog.listener()
    async def on_guild_update(self, before: discord.Guild, after: discord.Guild) -> None:
        self.log.debug("Listener triggered: on_guild_update")
        try:
            should_log = await self.should_log_event(before, "guild_update")
        except Exception as e:
            self.log.error(f"Error in should_log_event: {e}")
            return
        if not should_log:
            self.log.debug("should_log_event returned False for guild_update.")
            return
        try:
            channel = await self.get_log_channel(before, "guild_update")
        except Exception as e:
            self.log.error(f"Error in get_log_channel: {e}")
            return
        self.log.debug(f"About to send to channel: {channel}")
        if not channel:
            self.log.warning("No log channel set for guild_update.")
            return
        try:
            changes = []
            if before.name != after.name:
                changes.append(f"Name: {before.name} → {after.name}")
            if before.icon != after.icon:
                changes.append("Icon changed")
            if before.owner_id != after.owner_id:
                changes.append(f"Owner: {before.owner_id} → {after.owner_id}")
            if not changes:
                return
            embed = self.create_embed(
                "guild_update",
                f"⚙️ Server updated",
                changes="\n".join(changes)
            )
            await self.safe_send(channel, embed=embed)
        except Exception as e:
            self.log.error(f"Failed to log guild_update: {e}")

    @commands.Cog.listener()
    async def on_guild_emojis_update(self, guild: discord.Guild, before, after) -> None:
        self.log.debug("Listener triggered: on_guild_emojis_update")
        try:
            should_log = await self.should_log_event(guild, "emoji_update")
        except Exception as e:
            self.log.error(f"Error in should_log_event: {e}")
            return
        if not should_log:
            self.log.debug("should_log_event returned False for emoji_update.")
            return
        try:
            channel = await self.get_log_channel(guild, "emoji_update")
        except Exception as e:
            self.log.error(f"Error in get_log_channel: {e}")
            return
        self.log.debug(f"About to send to channel: {channel}")
        if not channel:
            self.log.warning("No log channel set for emoji_update.")
            return
        try:
            before_set = set(before)
            after_set = set(after)
            added = after_set - before_set
            removed = before_set - after_set
            changes = []
            if added:
                changes.append(f"Added: {', '.join(str(e) for e in added)}")
            if removed:
                changes.append(f"Removed: {', '.join(str(e) for e in removed)}")
            if not changes:
                return
            embed = self.create_embed(
                "emoji_update",
                f"😀 Emoji updated",
                changes="\n".join(changes)
            )
            await self.safe_send(channel, embed=embed)
        except Exception as e:
            self.log.error(f"Failed to log emoji_update: {e}")

    @commands.Cog.listener()
    async def on_voice_state_update(self, member: discord.Member, before: discord.VoiceState, after: discord.VoiceState) -> None:
        self.log.debug("Listener triggered: on_voice_state_update")
        if not member.guild:
            self.log.debug("No guild on member.")
            return
        try:
            should_log = await self.should_log_event(member.guild, "voice_update")
        except Exception as e:
            self.log.error(f"Error in should_log_event: {e}")
            return
        if not should_log:
            self.log.debug("should_log_event returned False for voice_update.")
            return
        try:
            channel = await self.get_log_channel(member.guild, "voice_update")
        except Exception as e:
            self.log.error(f"Error in get_log_channel: {e}")
            return
        self.log.debug(f"About to send to channel: {channel}")
        if not channel:
            self.log.warning("No log channel set for voice_update.")
            return
        try:
            changes = []
            if before.channel != after.channel:
                changes.append(f"Channel: {getattr(before.channel, 'mention', None)} → {getattr(after.channel, 'mention', None)}")
            if before.mute != after.mute:
                changes.append(f"Muted: {before.mute} → {after.mute}")
            if before.deaf != after.deaf:
                changes.append(f"Deafened: {before.deaf} → {after.deaf}")
            if before.self_mute != after.self_mute:
                changes.append(f"Self-muted: {before.self_mute} → {after.self_mute}")
            if before.self_deaf != after.self_deaf:
                changes.append(f"Self-deafened: {before.self_deaf} → {after.self_deaf}")
            if not changes:
                return
            embed = self.create_embed(
                "voice_update",
                f"🎤 Voice state updated for {member.mention}",
                changes="\n".join(changes)
            )
            await self.safe_send(channel, embed=embed)
        except Exception as e:
            self.log.error(f"Failed to log voice_update: {e}")

    @commands.Cog.listener()
    async def on_member_kick(self, guild: discord.Guild, user: discord.User) -> None:
        self.log.debug("Listener triggered: on_member_kick")
        if not guild or not await self.should_log_event(guild, "member_kick"):
            return
        channel = await self.get_log_channel(guild, "member_kick")
        self.log.debug(f"About to send to channel: {channel}")
        if not channel:
            return
        embed = self.create_embed(
            "member_kick",
            f"👢 {user} has been kicked.",
            user=f"{user} ({user.id})"
        )
        await self.safe_send(channel, embed=embed)

    @commands.Cog.listener()
    async def on_command(self, ctx: commands.Context) -> None:
        self.log.debug("Listener triggered: on_command")
        if not ctx.guild or not await self.should_log_event(ctx.guild, "command_use"):
            return
        channel = await self.get_log_channel(ctx.guild, "command_use")
        self.log.debug(f"About to send to channel: {channel}")
        if not channel:
            return
        channel_name = getattr(ctx.channel, "name", str(ctx.channel) if ctx.channel else "Unknown")
        embed = self.create_embed(
            "command_use",
            f"⌨️ Command used: `{ctx.command}`",
            user=f"{ctx.author} ({ctx.author.id})",
            channel=channel_name
        )
        await self.safe_send(channel, embed=embed)

    @commands.Cog.listener()
    async def on_command_error(self, ctx: commands.Context, error: Exception) -> None:
        self.log.debug("Listener triggered: on_command_error")
        if not ctx.guild or not await self.should_log_event(ctx.guild, "command_error"):
            return
        channel = await self.get_log_channel(ctx.guild, "command_error")
        self.log.debug(f"About to send to channel: {channel}")
        if not channel:
            return
        channel_name = getattr(ctx.channel, "name", str(ctx.channel) if ctx.channel else "Unknown")
        embed = self.create_embed(
            "command_error",
            f"⚠️ Error in command `{ctx.command}`",
            user=f"{ctx.author} ({ctx.author.id})",
            error=str(error),
            channel=channel_name
        )
        await self.safe_send(channel, embed=embed)

    @commands.Cog.listener()
    async def on_application_command(self, interaction: discord.Interaction) -> None:
        self.log.debug("Listener triggered: on_application_command")
        if not interaction.guild or not await self.should_log_event(interaction.guild, "application_cmd"):
            return
        channel = await self.get_log_channel(interaction.guild, "application_cmd")
        self.log.debug(f"About to send to channel: {channel}")
        if not channel:
            return
        channel_name = getattr(interaction.channel, "name", str(interaction.channel) if interaction.channel else "Unknown")
        embed = self.create_embed(
            "application_cmd",
            f"🔷 Slash command used: `{interaction.command}`",
            user=f"{interaction.user} ({interaction.user.id})",
            channel=channel_name
        )
        await self.safe_send(channel, embed=embed)

    # --- Forum Event Listeners ---

    @commands.Cog.listener()
    async def on_forum_post_create(self, post) -> None:
        """Log forum post creation events."""
        self.log.debug("Listener triggered: on_forum_post_create")
        guild = getattr(post, "guild", None)
        if not guild:
            self.log.debug("No guild on forum post.")
            return
        try:
            should_log = await self.should_log_event(guild, "forum_post_create")
        except Exception as e:
            self.log.error(f"Error in should_log_event: {e}")
            return
        if not should_log:
            self.log.debug("should_log_event returned False for forum_post_create.")
            return
        try:
            channel = await self.get_log_channel(guild, "forum_post_create")
        except Exception as e:
            self.log.error(f"Error in get_log_channel: {e}")
            return
        self.log.debug(f"About to send to channel: {channel}")
        if not channel:
            self.log.warning("No log channel set for forum_post_create.")
            return
        try:
            author = getattr(post, "author", None)
            title = getattr(post, "title", "Unknown")
            content = getattr(post, "content", "")
            forum_name = getattr(getattr(post, "parent", None), "name", "Unknown Forum")
            embed = self.create_embed(
                "forum_post_create",
                f"📰 Forum post created in {forum_name}",
                user=f"{author} ({getattr(author, 'id', 'N/A')})" if author else "Unknown",
                title=title,
                content=content
            )
            await self.safe_send(channel, embed=embed)
        except Exception as e:
            self.log.error(f"Failed to log forum_post_create: {e}")

    @commands.Cog.listener()
    async def on_forum_post_update(self, before, after) -> None:
        """Log forum post update events."""
        self.log.debug("Listener triggered: on_forum_post_update")
        guild = getattr(after, "guild", None)
        if not guild:
            self.log.debug("No guild on forum post.")
            return
        try:
            should_log = await self.should_log_event(guild, "forum_post_update")
        except Exception as e:
            self.log.error(f"Error in should_log_event: {e}")
            return
        if not should_log:
            self.log.debug("should_log_event returned False for forum_post_update.")
            return
        try:
            channel = await self.get_log_channel(guild, "forum_post_update")
        except Exception as e:
            self.log.error(f"Error in get_log_channel: {e}")
            return
        self.log.debug(f"About to send to channel: {channel}")
        if not channel:
            self.log.warning("No log channel set for forum_post_update.")
            return
        try:
            author = getattr(after, "author", None)
            title_before = getattr(before, "title", "Unknown")
            title_after = getattr(after, "title", "Unknown")
            content_before = getattr(before, "content", "")
            content_after = getattr(after, "content", "")
            forum_name = getattr(getattr(after, "parent", None), "name", "Unknown Forum")
            changes = []
            if title_before != title_after:
                changes.append(f"Title: {title_before} → {title_after}")
            if content_before != content_after:
                changes.append("Content updated")
            if not changes:
                return
            embed = self.create_embed(
                "forum_post_update",
                f"📰 Forum post updated in {forum_name}",
                user=f"{author} ({getattr(author, 'id', 'N/A')})" if author else "Unknown",
                changes="\n".join(changes)
            )
            await self.safe_send(channel, embed=embed)
        except Exception as e:
            self.log.error(f"Failed to log forum_post_update: {e}")

    @commands.Cog.listener()
    async def on_forum_post_delete(self, post) -> None:
        """Log forum post deletion events."""
        self.log.debug("Listener triggered: on_forum_post_delete")
        guild = getattr(post, "guild", None)
        if not guild:
            self.log.debug("No guild on forum post.")
            return
        try:
            should_log = await self.should_log_event(guild, "forum_post_delete")
        except Exception as e:
            self.log.error(f"Error in should_log_event: {e}")
            return
        if not should_log:
            self.log.debug("should_log_event returned False for forum_post_delete.")
            return
        try:
            channel = await self.get_log_channel(guild, "forum_post_delete")
        except Exception as e:
            self.log.error(f"Error in get_log_channel: {e}")
            return
        self.log.debug(f"About to send to channel: {channel}")
        if not channel:
            self.log.warning("No log channel set for forum_post_delete.")
            return
        try:
            author = getattr(post, "author", None)
            title = getattr(post, "title", "Unknown")
            forum_name = getattr(getattr(post, "parent", None), "name", "Unknown Forum")
            embed = self.create_embed(
                "forum_post_delete",
                f"📰 Forum post deleted in {forum_name}",
                user=f"{author} ({getattr(author, 'id', 'N/A')})" if author else "Unknown",
                title=title
            )
            await self.safe_send(channel, embed=embed)
        except Exception as e:
            self.log.error(f"Failed to log forum_post_delete: {e}")

    @commands.hybrid_group(name="yalc", invoke_without_command=True, with_app_command=True)
    async def yalc_group
        """YALC logging configuration commands."""
        await ctx.send_help()

    @yalc_group.hybrid_command(name="setup", with_app_command=True)
    async def yalc_setup(self, ctx: commands.Context) -> None:
        """Simplified interactive setup for YALC logging."""
        if not ctx.guild:
            await ctx.send("This command must be used in a server.", ephemeral=True)
            return
        if not ctx.channel.permissions_for(ctx.author).manage_guild:
            await ctx.send("You need the Manage Server permission to run setup.", ephemeral=True)
            return
        await ctx.send(
            "How would you like to set up logging channels?\n"
            "1️⃣ Create a new category and channels\n"
            "2️⃣ Use existing channels\n"
            "3️⃣ Skip (I'll set channels manually)",
            ephemeral=True
        )
        setup_msg = await ctx.send("React with 1️⃣, 2️⃣, or 3️⃣.", ephemeral=True)
        for emoji in ["1️⃣", "2️⃣", "3️⃣"]:
            try:
                await setup_msg.add_reaction(emoji)
            except Exception:
                pass
        def setup_check(reaction, user):
            return user == ctx.author and reaction.message.id == setup_msg.id and str(reaction.emoji) in ["1️⃣", "2️⃣", "3️⃣"]
        try:
            reaction, _ = await ctx.bot.wait_for("reaction_add", timeout=60.0, check=setup_check)
        except Exception:
            await ctx.send("Timed out. Please run setup again.", ephemeral=True)
            return
        choice = str(reaction.emoji)
        log_channels = {}
        use_emojis = False
        channel_defs = [
            ("message", "📝 message-logs", "message logs"),
            ("member", "👤 member-logs", "member logs"),
            ("channel", "📺 channel-logs", "channel logs"),
            ("thread", "🧵 thread-logs", "thread logs"),
            ("role", "✨ role-logs", "role logs"),
            ("command", "⌨️ command-logs", "command logs"),
            ("server", "⚙️ server-logs", "server logs"),
            ("forum", "📰 forum-logs", "forum logs")
        ]
        if choice == "1️⃣":
            emoji_prompt = await ctx.send(
                "Do you want to include emojis in the category and channel names? React ✅ for yes, ❌ for no.", ephemeral=True)
            try:
                await emoji_prompt.add_reaction("✅")
                await emoji_prompt.add_reaction("❌")
            except Exception:
                pass
            def emoji_check(reaction, user):
                return user == ctx.author and reaction.message.id == emoji_prompt.id and str(reaction.emoji) in ["✅", "❌"]
            try:
                emoji_reaction, _ = await ctx.bot.wait_for("reaction_add", timeout=30.0, check=emoji_check)
                use_emojis = str(emoji_reaction.emoji) == "✅"
            except Exception:
                await ctx.send("Timed out. Using plain names.", ephemeral=True)
                use_emojis = False
            cat_name = "📝 YALC Logs" if use_emojis else "YALC Logs"
            category = await ctx.guild.create_category_channel(cat_name, reason="YALC setup")
            for key, emoji_name, plain_name in channel_defs:
                ch_name = emoji_name if use_emojis else plain_name
                ch = await ctx.guild.create_text_channel(ch_name, category=category, reason="YALC setup")
                log_channels[key] = ch.id
            await ctx.send(f"Created category and channels: {', '.join(f'<#{cid}>' for cid in log_channels.values())}", ephemeral=True)
        elif choice == "2️⃣":
            await ctx.send("Please mention the channels for: message, member, channel, thread, role, command, server, forum. Type 'skip' to leave any unset.", ephemeral=True)
            for key, _, plain_name in channel_defs:
                await ctx.send(f"Mention a channel for `{plain_name}` or type 'skip':", ephemeral=True)
                def msg_check(m):
                    return m.author == ctx.author and m.channel == ctx.channel
                try:
                    msg = await ctx.bot.wait_for("message", timeout=60.0, check=msg_check)
                except Exception:
                    await ctx.send(f"Timed out for `{plain_name}`. Skipping.", ephemeral=True)
                    continue
                if msg.content.lower() == "skip":
                    continue
                if msg.channel_mentions:
                    log_channels[key] = msg.channel_mentions[0].id
        # Step 2: Event enabling
        await ctx.send(
            "Which events do you want to enable?\n"
            "✅ All events\n"
            "🛡️ Moderation only (bans, kicks, role, channel, member updates)\n"
            "❌ None (I'll enable manually)",
            ephemeral=True
        )
        events_msg = await ctx.send("React with ✅, 🛡️, or ❌.", ephemeral=True)
        for emoji in ["✅", "🛡️", "❌"]:
            try:
                await events_msg.add_reaction(emoji)
            except Exception:
                pass
        def events_check(reaction, user):
            return user == ctx.author and reaction.message.id == events_msg.id and str(reaction.emoji) in ["✅", "🛡️", "❌"]
        try:
            reaction, _ = await ctx.bot.wait_for("reaction_add", timeout=60.0, check=events_check)
        except Exception:
            await ctx.send("Timed out. Please run setup again.", ephemeral=True)
            return
        event_choice = str(reaction.emoji)
        all_events = list(self.event_descriptions.keys())
        mod_events = [
            "member_ban", "member_unban", "member_kick", "member_update",
            "role_create", "role_delete", "role_update",
            "channel_create", "channel_delete", "channel_update",
            "message_delete", "message_edit"
        ]
        if event_choice == "✅":
            for event in all_events:
                await self.config.guild(ctx.guild).events.set_raw(event, value=True)
        elif event_choice == "🛡️":
            for event in all_events:
                await self.config.guild(ctx.guild).events.set_raw(event, value=(event in mod_events))
        else:
            for event in all_events:
                await self.config.guild(ctx.guild).events.set_raw(event, value=False)
        # Step 3: Assign log channels to events (if any set)
        if log_channels:
            event_map = {
                "message": ["message_delete", "message_edit"],
                "member": ["member_join", "member_leave", "member_ban", "member_unban", "member_kick", "member_update"],
                "channel": ["channel_create", "channel_delete", "channel_update"],
                "thread": ["thread_create", "thread_delete", "thread_update", "thread_member_join", "thread_member_leave"],
                "role": ["role_create", "role_delete", "role_update"],
                "command": ["command_use", "command_error", "application_cmd"],
                "server": ["guild_update", "emoji_update", "cog_load", "voice_update"],
                "forum": []  # Add forum-related events if/when supported
            }
            for key, events in event_map.items():
                if key in log_channels:
                    for event in events:
                        await self.config.guild(ctx.guild).event_channels.set_raw(event, value=log_channels[key])
        # --- Tupperbox Setup Step ---
        await ctx.send(
            "Do you want to ignore Tupperbox proxy messages in logs? React ✅ for yes, ❌ for no.", ephemeral=True
        )
        tupperbox_prompt = await ctx.send("React now.", ephemeral=True)
        try:
            await tupperbox_prompt.add_reaction("✅")
            await tupperbox_prompt.add_reaction("❌")
        except Exception:
            pass
        def tupperbox_check(reaction, user):
            return user == ctx.author and reaction.message.id == tupperbox_prompt.id and str(reaction.emoji) in ["✅", "❌"]
        try:
            tupperbox_reaction, _ = await ctx.bot.wait_for("reaction_add", timeout=30.0, check=tupperbox_check)
            ignore_tupperbox = str(tupperbox_reaction.emoji) == "✅"
        except Exception:
            await ctx.send("Timed out. Defaulting to ignore Tupperbox: True.", ephemeral=True)
            ignore_tupperbox = True
        await self.config.guild(ctx.guild).ignore_tupperbox.set(ignore_tupperbox)
        if ignore_tupperbox:
            await ctx.send(
                "Would you like to add additional Tupperbox bot IDs to ignore? Type each ID and send, or type 'done' to finish.",
                ephemeral=True
            )
            ids = await self.config.guild(ctx.guild).tupperbox_ids()
            while True:
                def id_check(m):
                    return m.author == ctx.author and m.channel == ctx.channel
                try:
                    msg = await ctx.bot.wait_for("message", timeout=60.0, check=id_check)
                except Exception:
                    await ctx.send("Timed out. No more IDs added.", ephemeral=True)
                    break
                user_input = msg.content.strip()
                if user_input.lower() in ("done", "skip"):
                    break
                if not user_input.isdigit() or len(user_input) < 17:
                    await ctx.send("Please enter a valid Discord user ID (17+ digits) or 'done'.", ephemeral=True)
                    continue
                if user_input not in ids:
                    ids.append(user_input)
                    await self.config.guild(ctx.guild).tupperbox_ids.set(ids)
                    await ctx.send(f"Added `{user_input}` to Tupperbox ignore list.", ephemeral=True)
                else:
                    await ctx.send(f"ID `{user_input}` is already in the ignore list.", ephemeral=True)
        await ctx.send("✅ YALC setup complete! Use `/yalc events` to review your settings.", ephemeral=True)

    @yalc_group.hybrid_command(name="events", with_app_command=True)
    async def yalc_events(self, ctx: commands.Context) -> None:
        """List all loggable events and their status."""
        settings = await self.config.guild(ctx.guild).all()
        events = settings["events"]
        lines = [f"`{k}`: {'✅' if v else '❌'}" for k, v in events.items()]
        embed = discord.Embed(
            title="YALC Events",
            description="\n".join(lines),
            color=discord.Color.blurple()
        )
        await ctx.send(embed=embed, ephemeral=True)

    @yalc_group.hybrid_command(name="enable", with_app_command=True)
    async def yalc_enable(self, ctx: commands.Context, event: str) -> None:
        """Enable logging for an event."""
        event = event.lower()
        if event not in self.event_descriptions:
            await ctx.send(f"Unknown event: `{event}`.", ephemeral=True)
            return
        await self.config.guild(ctx.guild).events.set_raw(event, value=True)
        await ctx.send(f"Enabled logging for `{event}`.", ephemeral=True)

    @yalc_group.hybrid_command(name="disable", with_app_command=True)
    async def yalc_disable(self, ctx: commands.Context, event: str) -> None:
        """Disable logging for an event."""
        event = event.lower()
        if event not in self.event_descriptions:
            await ctx.send(f"Unknown event: `{event}`.", ephemeral=True)
            return
        await self.config.guild(ctx.guild).events.set_raw(event, value=False)
        await ctx.send(f"Disabled logging for `{event}`.", ephemeral=True)

    @yalc_group.hybrid_command(name="setchannel", with_app_command=True)
    async def yalc_setchannel(self, ctx: commands.Context, event: str, channel: Optional[discord.TextChannel]) -> None:
        """Set the log channel for an event."""
        event = event.lower()
        if event not in self.event_descriptions:
            await ctx.send(f"Unknown event: `{event}`.", ephemeral=True)
            return
        if not channel:
            await ctx.send("You must mention a text channel.", ephemeral=True)
            return
        await self.config.guild(ctx.guild).event_channels.set_raw(event, value=channel.id)
        await ctx.send(f"Set log channel for `{event}` to {channel.mention}.", ephemeral=True)

    @yalc_group.hybrid_command(name="removechannel", with_app_command=True)
    async def yalc_removechannel(self, ctx: commands.Context, event: str) -> None:
        """Remove the log channel override for an event."""
        event = event.lower()
        if event not in self.event_descriptions:
            await ctx.send(f"Unknown event: `{event}`.", ephemeral=True)
            return
        await self.config.guild(ctx.guild).event_channels.clear_raw(event)
        await ctx.send(f"Removed log channel override for `{event}`.", ephemeral=True)

    def is_tupperbox_message(self, message: discord.Message, tupperbox_ids: list[str]) -> bool:
        """Check if a message is from Tupperbox or a configured proxy bot."""
        if not message.author:
            return False
        return str(message.author.id) in tupperbox_ids

    @commands.hybrid_group(name="tupperbox", invoke_without_command=True, with_app_command=True)
    async def tupperbox_group(self, ctx: commands.Context) -> None:
        """Tupperbox ignore settings."""
        await ctx.send_help()

    @tupperbox_group.hybrid_command(name="ignore", with_app_command=True)
    async def tupperbox_ignore(self, ctx: commands.Context, enabled: Optional[bool] = None) -> None:
        """Enable or disable ignoring Tupperbox messages in logs."""
        if enabled is None:
            enabled = await self.config.guild(ctx.guild).ignore_tupperbox()
            await ctx.send(f"Tupperbox ignore is currently {'enabled' if enabled else 'disabled'}.", ephemeral=True)
            return
        await self.config.guild(ctx.guild).ignore_tupperbox.set(enabled)
        await ctx.send(f"Tupperbox ignore set to {'enabled' if enabled else 'disabled'}.", ephemeral=True)

    @tupperbox_group.hybrid_command(name="addid", with_app_command=True)
    async def tupperbox_addid(self, ctx: commands.Context, bot_id: str) -> None:
        """Add a bot user ID to ignore as Tupperbox proxy."""
        ids = await self.config.guild(ctx.guild).tupperbox_ids()
        if bot_id not in ids:
            ids.append(bot_id)
            await self.config.guild(ctx.guild).tupperbox_ids.set(ids)
            await ctx.send(f"Added bot ID `{bot_id}` to Tupperbox ignore list.", ephemeral=True)
        else:
            await ctx.send(f"Bot ID `{bot_id}` is already in the ignore list.", ephemeral=True)

    @tupperbox_group.hybrid_command(name="removeid", with_app_command=True)
    async def tupperbox_removeid(self, ctx: commands.Context, bot_id: str) -> None:
        """Remove a bot user ID from the Tupperbox ignore list."""
        ids = await self.config.guild(ctx.guild).tupperbox_ids()
        if bot_id in ids:
            ids.remove(bot_id)
            await self.config.guild(ctx.guild).tupperbox_ids.set(ids)
            await ctx.send(f"Removed bot ID `{bot_id}` from Tupperbox ignore list.", ephemeral=True)
        else:
            await ctx.send(f"Bot ID `{bot_id}` is not in the ignore list.", ephemeral=True)

async def setup(bot: Red) -> None:
    """Set up the YALC cog."""
    cog = YALC(bot)
    await bot.add_cog(cog)
    # Do not add cog.listeners as a cog
    # If you have slash groups, add them here
    # bot.tree.add_command(cog.yalc)  # If you have a hybrid group
