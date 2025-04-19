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
from .dashboard_integration import DashboardIntegration

class YALC(commands.Cog):
    """Yet Another Logging Cog for Red-DiscordBot.

    A comprehensive logging solution with both classic and slash commands.
    Features include:
    - Customizable event logging
    - Per-channel configurations
    - Ignore lists for users, roles, and channels
    - Log retention management
    - Rich embed formatting
    - Dashboard integration for easy configuration
    """

    def __init__(self, bot: Red) -> None:
        """Initialize YALC."""
        self.bot = bot
        self.log = logging.getLogger("red.taako.yalc")
        
        # Initialize dashboard integration
        self.dashboard = DashboardIntegration(self)
        
        
        # Event descriptions with emojis
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
        }

        # Initialize Config
        default_guild = {
            "events": {event: False for event in self.event_descriptions},
            "event_channels": {},
            "ignore_tupperbox": True,
            "tupperbox_ids": ["239232811662311425"],  # Default Tupperbox bot ID
            "retention_days": 30,
            "ignored_channels": [],
            "ignored_users": [],
            "ignored_roles": []
        }
        self.config = Config.get_conf(self, identifier=2394567890, force_registration=True)
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
        """Create a standardized, readable embed for logging."""
        color_map = {
            "message_delete": discord.Color.red(),
            "message_edit": discord.Color.blue(),
            "member_join": discord.Color.green(),
            "member_leave": discord.Color.orange(),
            "member_ban": discord.Color.dark_red(),
            "member_unban": discord.Color.teal(),
            "member_update": discord.Color.blurple(),
            "channel_create": discord.Color.green(),
            "channel_delete": discord.Color.red(),
            "channel_update": discord.Color.blurple(),
            "role_create": discord.Color.green(),
            "role_delete": discord.Color.red(),
            "role_update": discord.Color.blurple(),
            "emoji_update": discord.Color.gold(),
            "guild_update": discord.Color.blurple(),
            "voice_update": discord.Color.purple(),
            "member_kick": discord.Color.orange(),
            "command_use": discord.Color.blurple(),
            "command_error": discord.Color.red(),
            "application_cmd": discord.Color.blurple(),
            "forum_post_create": discord.Color.green(),
            "forum_post_update": discord.Color.blurple(),
            "forum_post_delete": discord.Color.red(),
            "thread_create": discord.Color.green(),
            "thread_delete": discord.Color.red(),
            "thread_update": discord.Color.blurple(),
            "thread_member_join": discord.Color.green(),
            "thread_member_leave": discord.Color.red(),
        }
        embed = discord.Embed(
            title=f"📝 {event_type.replace('_', ' ').title()}",
            description=description + "\n\u200b",  # Add spacing after desc
            color=color_map.get(event_type, discord.Color.blurple()),
            timestamp=datetime.datetime.now(datetime.UTC)
        )
        # Add fields with better formatting
        for key, value in kwargs.items():
            if not value:
                continue
            # For multi-line or list fields, use block quotes or bullets
            if isinstance(value, list):
                value = "\n".join(f"- {v}" for v in value)
            elif isinstance(value, str) and ("\n" in value or len(value) > 60):
                value = f"> {value.replace(chr(10), '\n> ')}"
            embed.add_field(name=key.replace('_', ' ').title(), value=value, inline=False)
        self.set_embed_footer(embed)
        return embed

    def set_embed_footer(self, embed: discord.Embed, event_time: Optional[datetime.datetime] = None, label: str = "YALC Logger") -> None:
        """Set a standard footer for all log embeds, including a formatted time."""
        if event_time is None:
            event_time = datetime.datetime.now(datetime.UTC)
        formatted_time = event_time.strftime('%B %d, %Y, %I:%M %p')
        embed.set_footer(
            text=f"{label} • {formatted_time}",
            icon_url="https://cdn-icons-png.flaticon.com/512/928/928797.png"
        )

    async def cog_unload(self) -> None:
        """Clean up when cog is unloaded."""
        if hasattr(self, "dashboard"):
            try:
                dashboard_cog = self.bot.get_cog("Dashboard")
                if dashboard_cog and hasattr(dashboard_cog, "rpc"):
                    dashboard_cog.rpc.third_parties_handler.remove_third_party(self.dashboard)
            except Exception as e:
                self.log.error(f"Error removing dashboard integration: {e}", exc_info=True)

        # Clean up any other resources
        await super().cog_unload()

    async def cog_load(self) -> None:
        """Register all YALC events as modlog case types and dashboard third party."""
        # Register modlog case types
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
        # Register as dashboard third party if dashboard is loaded
        dashboard_cog = self.bot.get_cog("Dashboard")
        if dashboard_cog and hasattr(dashboard_cog, "rpc") and hasattr(dashboard_cog.rpc, "third_parties_handler"):
            try:
                dashboard_cog.rpc.third_parties_handler.add_third_party(self.dashboard)
                self.log.info("Registered YALC as a dashboard third party.")
            except Exception as e:
                self.log.error(f"Failed to register YALC as dashboard third party: {e}")

    @property
    def dashboard_third_party_name(self) -> str:
        """Name for dashboard third party integration."""
        return "YALC"

    @property
    def dashboard_third_party_description(self) -> str:
        """Description for dashboard third party integration."""
        return "Yet Another Logging Cog - advanced server logging and moderation event tracking."

    @property
    def dashboard_third_party_icon(self) -> str:
        """Icon URL for dashboard third party integration."""
        return "https://cdn-icons-png.flaticon.com/512/928/928797.png"

    @property
    def dashboard_third_party_routes(self) -> list:
        """Dashboard routes for third party integration (empty if not using custom pages)."""
        return []

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
            user_link = f"[{author}](https://discord.com/users/{author.id})" if author else "Unknown"
            embed = self.create_embed(
                "message_delete",
                f"🗑️ Message deleted in {getattr(message.channel, 'mention', str(message.channel))}\n\u200b",
                user=user_link,
                channel_name=channel_name,
                content=content if content else None,
                attachments=attachments if attachments else None,
                embeds="Yes" if embeds else None
            )
            await self.safe_send(channel, embed=embed)
        except Exception as e:
            self.log.error(f"Failed to log message_delete: {e}")

    @commands.Cog.listener()
    async def on_message_edit(self, before: discord.Message, after: discord.Message) -> None:
        """Log message edit events, skipping Tupperbox proxies if configured."""
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
            tupperbox_ids = settings.get("tupperbox_ids", getattr(self, "tupperbox_default_ids", ["239232811662311425"]))
            ignore_tupperbox = settings.get("ignore_tupperbox", True)
            if ignore_tupperbox and (
                self.is_tupperbox_message(before, tupperbox_ids) or self.is_tupperbox_message(after, tupperbox_ids)
            ):
                self.log.debug("Skipping Tupperbox message_edit event (matched before or after message).")
                return
        except Exception as e:
            self.log.error(f"Error checking Tupperbox ignore: {e}")
        try:
            author = getattr(before, "author", None)
            attachments = [a.url for a in getattr(after, "attachments", [])]
            embeds = getattr(after, "embeds", [])
            channel_name = getattr(before.channel, "name", str(before.channel) if before.channel else "Unknown")
            self.log.debug(f"Logging message_edit: author={author}, before={before.content}, after={after.content}, attachments={attachments}, embeds={embeds}, channel_name={channel_name}")
            user_link = f"[{author}](https://discord.com/users/{author.id})" if author else "Unknown"
            jump_url = getattr(after, "jump_url", None)
            embed = self.create_embed(
                "message_edit",
                f"✏️ Message edited in {getattr(before.channel, 'mention', str(before.channel))}\n\u200b",
                user=user_link,
                channel_name=channel_name
            )
            before_text = before.content or 'No content'
            after_text = after.content or 'No content'
            embed.add_field(name="Before", value=f"> {before_text}", inline=False)
            embed.add_field(name="After", value=f"> {after_text}", inline=False)
            if jump_url:
                embed.add_field(name="Jump to Message", value=f"[Click here to view the message]({jump_url})", inline=False)
            if attachments:
                embed.add_field(name="Attachments", value="\n".join(attachments), inline=False)
            if embeds:
                embed.add_field(name="Embeds", value="Yes", inline=False)
            edit_time = after.edited_at or after.created_at or discord.utils.utcnow()
            if edit_time:
                self.set_embed_footer(embed, event_time=edit_time, label="YALC Logger • Edited")
            else:
                self.set_embed_footer(embed)
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
                f"👋 {member.mention} has joined the server.\n\u200b",
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
                f"👋 {member.mention} has left the server.\n\u200b",
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
            f"🔨 {user.mention if hasattr(user, 'mention') else user} has been banned.\n\u200b",
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
            f"🔓 {user.mention if hasattr(user, 'mention') else user} has been unbanned.\n\u200b",
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
            added_roles = [r for r in after.roles if r not in before.roles]
            removed_roles = [r for r in before.roles if r not in after.roles]
            if added_roles or removed_roles:
                for role in added_roles:
                    changes.append(f"➕ Added {role.mention}")
                for role in removed_roles:
                    changes.append(f"➖ Removed {role.mention}")
            if before.nick != after.nick:
                changes.append(f"📝 Nickname changed: '{before.nick or before.display_name}' → '{after.nick or after.display_name}'")
            if not changes:
                return
            embed = discord.Embed(
                title="👤 Member Role Update",
                description=f"{after.mention} ({after.display_name})'s roles or nickname were updated.",
                color=discord.Color.blurple(),
                timestamp=datetime.datetime.now(datetime.UTC)
            )
            embed.add_field(name="Changes", value="\n".join(changes), inline=False)
            if after.display_avatar:
                embed.set_thumbnail(url=after.display_avatar.url)
            event_time = datetime.datetime.now(datetime.UTC)
            self.set_embed_footer(embed, event_time=event_time, label="YALC Logger • Role/Nick Update")
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
                f"📝 Channel created: {getattr(channel, 'mention', str(channel))}\n\u200b",
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
                f"🗑️ Channel deleted: {getattr(channel, 'mention', str(channel))}\n\u200b",
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
                f"🔄 Channel updated: {getattr(after, 'mention', str(after))}\n\u200b",
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
                f"🧵 Thread created in {getattr(thread.parent, 'mention', None)}\n\u200b",
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
                f"🗑️ Thread deleted from {getattr(thread.parent, 'mention', None)}\n\u200b",
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
                f"🔄 Thread updated in {getattr(after.parent, 'mention', None)}\n\u200b",
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
                f"✨ Role created: {role.mention}\n\u200b",
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
                f"🗑️ Role deleted: {role.name}\n\u200b",
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
                f"🔄 Role updated: {after.mention}\n\u200b",
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
            if getattr(before, 'banner', None) != getattr(after, 'banner', None):
                changes.append("Banner changed")
            if getattr(before, 'splash', None) != getattr(after, 'splash', None):
                changes.append("Splash image changed")
            if getattr(before, 'description', None) != getattr(after, 'description', None):
                changes.append(f"Description: {getattr(before, 'description', None)} → {getattr(after, 'description', None)}")
            if getattr(before, 'vanity_url_code', None) != getattr(after, 'vanity_url_code', None):
                changes.append(f"Vanity URL: {getattr(before, 'vanity_url_code', None)} → {getattr(after, 'vanity_url_code', None)}")
            if getattr(before, 'afk_channel', None) != getattr(after, 'afk_channel', None):
                changes.append(f"AFK Channel: {getattr(before.afk_channel, 'name', None)} → {getattr(after.afk_channel, 'name', None)}")
            if getattr(before, 'afk_timeout', None) != getattr(after, 'afk_timeout', None):
                changes.append(f"AFK Timeout: {getattr(before, 'afk_timeout', None)} → {getattr(after, 'afk_timeout', None)}")
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
        """Log simple, readable voice state changes."""
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
            # Only log the most relevant, simple changes
            events = []
            if before.channel != after.channel:
                if before.channel and not after.channel:
                    events.append(f"{member.mention} left {before.channel.mention}")
                elif not before.channel and after.channel:
                    events.append(f"{member.mention} joined {after.channel.mention}")
                elif before.channel and after.channel:
                    events.append(f"{member.mention} moved from {before.channel.mention} to {after.channel.mention}")
            if before.mute != after.mute:
                events.append(f"{member.mention} was {'muted' if after.mute else 'unmuted'} by server")
            if before.deaf != after.deaf:
                events.append(f"{member.mention} was {'deafened' if after.deaf else 'undeafened'} by server")
            if before.self_mute != after.self_mute:
                events.append(f"{member.mention} {'muted themselves' if after.self_mute else 'unmuted themselves'}")
            if before.self_deaf != after.self_deaf:
                events.append(f"{member.mention} {'deafened themselves' if after.self_deaf else 'undeafened themselves'}")
            if not events:
                return
            for event in events:
                embed = discord.Embed(
                    description=event,
                    color=discord.Color.purple(),
                    timestamp=datetime.datetime.now(datetime.UTC)
                )
                self.set_embed_footer(embed, label="YALC Logger • Voice")
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

    @commands.hybrid_group(name="yalc", invoke_without_command=True, with_app_command=True, description="YALC logging configuration commands.")
    async def yalc(self, ctx: commands.Context) -> None:
        """YALC logging configuration commands."""
        prefix = ctx.clean_prefix
        embed = discord.Embed(
            title="YALC Logging Commands",
            description=(
                f"`{prefix}yalc setup` - Start the setup wizard\n"
                f"`{prefix}yalc events` - Show current event logging status\n"
                f"`{prefix}yalc enable <event>` - Enable logging for an event\n"
                f"`{prefix}yalc disable <event>` - Disable logging for an event\n"
                f"`{prefix}yalc setchannel <event> <channel>` - Set log channel for an event\n"
                f"`{prefix}yalc removechannel <event>` - Remove log channel override for an event\n"
                f"`{prefix}yalc tboxignore [enabled]` - Toggle Tupperbox ignore\n"
                f"`{prefix}yalc addtbox <bot_id>` - Add Tupperbox bot ID to ignore\n"
                f"`{prefix}yalc removetbox <bot_id>` - Remove Tupperbox bot ID from ignore list"
            ),
            color=discord.Color.blurple()
        )
        await ctx.send(embed=embed, ephemeral=True)

    @yalc.command(name="events", with_app_command=True, description="List all loggable events and their status.")
    async def yalc_events_cmd(self, ctx: commands.Context) -> None:
        """List all loggable events and their status."""
        await self.yalc_events(ctx)

    @yalc.command(name="enable", with_app_command=True, description="Enable logging for an event.")
    async def yalc_enable_cmd(self, ctx: commands.Context, event: str) -> None:
        """Enable logging for an event."""
        await self.yalc_enable(ctx, event)

    @yalc.command(name="disable", with_app_command=True, description="Disable logging for an event.")
    async def yalc_disable_cmd(self, ctx: commands.Context, event: str) -> None:
        """Disable logging for an event."""
        await self.yalc_disable(ctx, event)

    @yalc.command(name="setchannel", with_app_command=True, description="Set the log channel for an event.")
    async def yalc_setchannel_cmd(self, ctx: commands.Context, event: str, channel: Optional[discord.TextChannel]) -> None:
        """Set the log channel for an event."""
        await self.yalc_setchannel(ctx, event, channel)

    @yalc.command(name="removechannel", with_app_command=True, description="Remove the log channel override for an event.")
    async def yalc_removechannel_cmd(self, ctx: commands.Context, event: str) -> None:
        """Remove the log channel override for an event."""
        await self.yalc_removechannel(ctx, event)

    @yalc.command(name="tboxignore", with_app_command=True, description="Enable or disable ignoring Tupperbox messages in logs.")
    async def yalc_tboxignore_cmd(self, ctx: commands.Context, enabled: Optional[bool] = None) -> None:
        """Enable or disable ignoring Tupperbox messages in logs."""
        try:
            if enabled is None:
                current = await self.config.guild(ctx.guild).ignore_tupperbox()
                await ctx.send(
                    f"Tupperbox ignore is currently {'enabled' if current else 'disabled'}.",
                    ephemeral=True
                )
                return
            await self.config.guild(ctx.guild).ignore_tupperbox.set(enabled)
            await ctx.send(
                f"Tupperbox ignore set to {'enabled' if enabled else 'disabled'}.",
                ephemeral=True
            )
        except Exception as e:
            self.log.error(f"Failed to set Tupperbox ignore: {e}")
            await ctx.send("Failed to update Tupperbox ignore setting.", ephemeral=True)

    @yalc.command(name="addtbox", with_app_command=True, description="Add a bot user ID to ignore as Tupperbox proxy.")
    async def yalc_tupperbox_add_cmd(self, ctx: commands.Context, bot_id: str) -> None:
        """Add a bot user ID to ignore as Tupperbox proxy."""
        await self.tupperbox_addid(ctx, bot_id)

    @yalc.command(name="removetbox", with_app_command=True, description="Remove a bot user ID from the Tupperbox ignore list.")
    async def yalc_tupperbox_remove_cmd(self, ctx: commands.Context, bot_id: str) -> None:
        """Remove a bot user ID from the Tupperbox ignore list."""
        await self.tupperbox_removeid(ctx, bot_id)

    @yalc.command(name="setup", with_app_command=True, description="Start the interactive setup wizard for YALC.")
    @commands.has_permissions(manage_guild=True)
    @commands.guild_only()
    async def yalc_setup_cmd(self, ctx: commands.Context) -> None:
        """Simplified interactive setup for YALC logging."""
        if not ctx.guild:
            await ctx.send("This command must be used in a server.", ephemeral=True)
            return
            
        if not ctx.channel.permissions_for(ctx.author).manage_guild:
            await ctx.send("You need the Manage Server permission to run setup.", ephemeral=True)
            return

        # Step 1: Channel setup
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
            return (
                user == ctx.author 
                and reaction.message.id == setup_msg.id 
                and str(reaction.emoji) in ["1️⃣", "2️⃣", "3️⃣"]
            )
        
        try:
            reaction, _ = await ctx.bot.wait_for("reaction_add", timeout=60.0, check=setup_check)
        except asyncio.TimeoutError:
            await ctx.send("Setup timed out. Please run setup again.", ephemeral=True)
            return

        choice = str(reaction.emoji)
        log_channels = {}
        use_emojis = False
        channel_defs = [
            ("member", "👤 member-logs", "member-logs"),
            ("message", "📝 message-logs", "message-logs"),
            ("channel", "📺 channel-logs", "channel-logs"),
            ("role", "✨ role-logs", "role-logs"),
            ("voice", "🎤 voice-logs", "voice-logs"),
            ("server", "⚙️ server-logs", "server-logs"),
            ("emoji", "😀 emoji-sticker-logs", "emoji-sticker-logs")
        ]

        if choice == "1️⃣":
            # Emoji preference
            emoji_prompt = await ctx.send(
                "Do you want to include emojis in the category and channel names? React ✅ for yes, ❌ for no.",
                ephemeral=True
            )
            try:
                await emoji_prompt.add_reaction("✅")
                await emoji_prompt.add_reaction("❌")
            except Exception:
                pass

            def emoji_check(reaction, user):
                return (
                    user == ctx.author 
                    and reaction.message.id == emoji_prompt.id 
                    and str(reaction.emoji) in ["✅", "❌"]
                )

            try:
                emoji_reaction, _ = await ctx.bot.wait_for("reaction_add", timeout=30.0, check=emoji_check)
                use_emojis = str(emoji_reaction.emoji) == "✅"
            except asyncio.TimeoutError:
                await ctx.send("Timed out. Using no emojis by default.", ephemeral=True)
                use_emojis = False

            # Create category and channels
            cat_name = "📝 YALC Logs" if use_emojis else "YALC Logs"
            try:
                category = await ctx.guild.create_category_channel(cat_name, reason="YALC setup")
                for key, emoji_name, plain_name in channel_defs:
                    channel = await ctx.guild.create_text_channel(
                        emoji_name if use_emojis else plain_name,
                        category=category,
                        reason=f"YALC setup - {plain_name}"
                    )
                    log_channels[key] = channel
                await ctx.send("✅ Created all log channels.", ephemeral=True)
            except Exception as e:
                self.log.error(f"Failed to create channels: {e}")
                await ctx.send("❌ Failed to create some channels. Please check permissions.", ephemeral=True)
                return

        elif choice == "2️⃣":
            for key, emoji_name, plain_name in channel_defs:
                await ctx.send(
                    f"Please mention the channel to use for {plain_name}, or type 'skip' to skip.",
                    ephemeral=True
                )

                def msg_check(m):
                    return m.author == ctx.author and m.channel == ctx.channel

                try:
                    msg = await ctx.bot.wait_for("message", timeout=30.0, check=msg_check)
                    if msg.content.lower() != "skip":
                        if not msg.channel_mentions:
                            await ctx.send(f"No channel mentioned. Skipping {plain_name}.", ephemeral=True)
                            continue
                        log_channels[key] = msg.channel_mentions[0]
                except asyncio.TimeoutError:
                    await ctx.send(f"Timed out. Skipping {plain_name}.", ephemeral=True)
                    continue
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
                return (
                    user == ctx.author 
                    and reaction.message.id == events_msg.id 
                    and str(reaction.emoji) in ["✅", "🛡️", "❌"]
                )

            try:
                event_reaction, _ = await ctx.bot.wait_for("reaction_add", timeout=30.0, check=events_check)
            except asyncio.TimeoutError:
                await ctx.send("Timed out. No events will be enabled by default.", ephemeral=True)
                event_choice = "❌"
            else:
                event_choice = str(event_reaction.emoji)

            all_events = list(self.event_descriptions.keys())
            mod_events = [
                "member_ban", "member_unban", "member_kick", "member_update",
                "role_create", "role_delete", "role_update",
                "channel_create", "channel_delete", "channel_update",
                "message_delete", "message_edit"
            ]

            if event_choice == "✅":
                # Enable all events
                events_config = {event: True for event in all_events}
                await self.config.guild(ctx.guild).events.set(events_config)
                await ctx.send("✅ Enabled all events.", ephemeral=True)
            elif event_choice == "🛡️":
                # Enable moderation events only
                events_config = {event: (event in mod_events) for event in all_events}
                await self.config.guild(ctx.guild).events.set(events_config)
                await ctx.send("✅ Enabled moderation events.", ephemeral=True)
            else:
                # Keep all events disabled
                events_config = {event: False for event in all_events}
                await self.config.guild(ctx.guild).events.set(events_config)
                await ctx.send("✅ All events will remain disabled.", ephemeral=True)

        # Step 3: Assign log channels to events (if any set)
        if log_channels:
            event_map = {
                "message": ["message_delete", "message_edit"],
                "member": [
                    "member_join", "member_leave", "member_ban",
                    "member_unban", "member_kick", "member_update"
                ],
                "channel": ["channel_create", "channel_delete", "channel_update"],
                "role": ["role_create", "role_delete", "role_update"],
                "voice": ["voice_update"],
                "server": ["guild_update", "cog_load"],
                "emoji": ["emoji_update"]
            }
            event_channels = {}
            for key, events in event_map.items():
                if key in log_channels:
                    for event in events:
                        event_channels[event] = log_channels[key].id
            await self.config.guild(ctx.guild).event_channels.set(event_channels)
            await ctx.send("✅ Configured log channels for all events.", ephemeral=True)

        # Step 4: Tupperbox Setup
        await ctx.send(
            "Do you want to ignore Tupperbox proxy messages in logs? React ✅ for yes, ❌ for no.",
            ephemeral=True
        )
        tupperbox_prompt = await ctx.send("React now.", ephemeral=True)
        try:
            await tupperbox_prompt.add_reaction("✅")
            await tupperbox_prompt.add_reaction("❌")
        except Exception:
            pass

        def tupperbox_check(reaction, user):
            return (
                user == ctx.author 
                and reaction.message.id == tupperbox_prompt.id 
                and str(reaction.emoji) in ["✅", "❌"]
            )

        try:
            tupperbox_reaction, _ = await ctx.bot.wait_for(
                "reaction_add",
                timeout=30.0,
                check=tupperbox_check
            )
            ignore_tupperbox = str(tupperbox_reaction.emoji) == "✅"
        except asyncio.TimeoutError:
            await ctx.send("Timed out. Defaulting to ignore Tupperbox: True.", ephemeral=True)
            ignore_tupperbox = True

        await self.config.guild(ctx.guild).ignore_tupperbox.set(ignore_tupperbox)

        if ignore_tupperbox:
            await ctx.send(
                "Would you like to add additional Tupperbox bot IDs to ignore? "
                "Type each ID and send, or type 'done' to finish.",
                ephemeral=True
            )
            ids = await self.config.guild(ctx.guild).tupperbox_ids()

            def id_check(m):
                return m.author == ctx.author and m.channel == ctx.channel

            while True:
                try:
                    msg = await ctx.bot.wait_for("message", timeout=30.0, check=id_check)
                    if msg.content.lower() == "done":
                        break
                    if msg.content.isdigit() and len(msg.content) >= 17:
                        if msg.content not in ids:
                            ids.append(msg.content)
                            await ctx.send(f"Added ID: {msg.content}", ephemeral=True)
                        else:
                            await ctx.send("That ID is already in the list.", ephemeral=True)
                    else:
                        await ctx.send(
                            "That doesn't look like a valid Discord user ID. "
                            "Please enter a valid ID or 'done'.",
                            ephemeral=True
                        )
                except asyncio.TimeoutError:
                    await ctx.send("Timed out. Saving current IDs.", ephemeral=True)
                    break

            await self.config.guild(ctx.guild).tupperbox_ids.set(ids)

        await ctx.send(
            "✅ YALC setup complete! Use `/yalc events` to review your settings.",
            ephemeral=True
        )

    async def yalc_events(self, ctx: commands.Context) -> None:
        """List all loggable events and their status."""
        if not ctx.guild:
            await ctx.send("This command must be used in a server.", ephemeral=True)
            return
        settings = await self.config.guild(ctx.guild).all()
        events = settings["events"]
        event_channels = settings["event_channels"]

        embed = discord.Embed(
            title="YALC Event Status",
            description="Current status of all loggable events.",
            color=discord.Color.blue()
        )
        
        for event in sorted(self.event_descriptions.keys()):
            emoji, desc = self.event_descriptions[event]
            status = "✅ Enabled" if events.get(event, False) else "❌ Disabled"
            channel = ctx.guild.get_channel(event_channels.get(event, 0))
            channel_text = f" in {channel.mention}" if channel else ""
            embed.add_field(
                name=f"{emoji} {event}",
                value=f"{status}{channel_text}\n{desc}",
                inline=True
            )
        
        await ctx.send(embed=embed, ephemeral=True)

    async def yalc_enable(self, ctx: commands.Context, event: str) -> None:
        """Enable logging for an event or all events."""
        if not ctx.guild:
            await ctx.send("This command must be used in a server.", ephemeral=True)
            return
        
        if not ctx.channel.permissions_for(ctx.author).manage_guild:
            await ctx.send("You need the Manage Server permission to enable events.", ephemeral=True)
            return

        if event.lower() == "all":
            try:
                all_events = {e: True for e in self.event_descriptions}
                await self.config.guild(ctx.guild).events.set(all_events)
                await ctx.send(
                    "✅ Enabled logging for all events.",
                    ephemeral=True
                )
            except Exception as e:
                self.log.error(f"Failed to enable all events: {e}")
                await ctx.send("Failed to enable all event logging.", ephemeral=True)
            return

        if event not in self.event_descriptions:
            await ctx.send(
                f"Invalid event. Use `/yalc events` to see available events.",
                ephemeral=True
            )
            return

        try:
            await self.config.guild(ctx.guild).events.set_raw(event, value=True)
            emoji, desc = self.event_descriptions[event]
            await ctx.send(
                f"{emoji} Enabled logging for: **{event}** ({desc})",
                ephemeral=True
            )
        except Exception as e:
            self.log.error(f"Failed to enable event {event}: {e}")
            await ctx.send("Failed to enable event logging.", ephemeral=True)

    async def yalc_disable(self, ctx: commands.Context, event: str) -> None:
        """Disable logging for an event."""
        if not ctx.guild:
            await ctx.send("This command must be used in a server.", ephemeral=True)
            return
        
        if not ctx.channel.permissions_for(ctx.author).manage_guild:
            await ctx.send("You need the Manage Server permission to disable events.", ephemeral=True)
            return

        if event not in self.event_descriptions:
            await ctx.send(
                f"Invalid event. Use `/yalc events` to see available events.",
                ephemeral=True
            )
            return

        try:
            await self.config.guild(ctx.guild).events.set_raw(event, value=False)
            emoji, desc = self.event_descriptions[event]
            await ctx.send(
                f"{emoji} Disabled logging for: **{event}** ({desc})",
                ephemeral=True
            )
        except Exception as e:
            self.log.error(f"Failed to disable event {event}: {e}")
            await ctx.send("Failed to disable event logging.", ephemeral=True)

    async def yalc_setchannel(self, ctx: commands.Context, event: str, channel: Optional[discord.TextChannel]) -> None:
        """Set the log channel for an event."""
        if not ctx.guild:
            await ctx.send("This command must be used in a server.", ephemeral=True)
            return
        
        if not ctx.channel.permissions_for(ctx.author).manage_guild:
            await ctx.send("You need the Manage Server permission to set channels.", ephemeral=True)
            return

        if event not```python
        if event not in self.event_descriptions:
            await ctx.send(
                f"Invalid event. Use `/yalc events` to see available events.",
                ephemeral=True
            )
            return

        try:
            if channel:
                await self.config.guild(ctx.guild).event_channels.set_raw(event, value=channel.id)
                emoji, desc = self.event_descriptions[event]
                await ctx.send(
                    f"{emoji} Set logging channel for **{event}** to {channel.mention}",
                    ephemeral=True
                )
            else:
                await ctx.send("Please specifya channel to set.", ephemeral=True)
        except Exception as e:
            self.log.error(f"Failed to set channel for event {event}: {e}")
            await ctx.send("Failed to set logging channel.", ephemeral=True)

    async def yalc_removechannel(self, ctx: commands.Context, event: str) -> None:
        """Remove the log channel override for an event."""
        if not ctx.guild:
            await ctx.send("This command must be used in a server.", ephemeral=True)
            return
        
        if not ctx.channel.permissions_for(ctx.author).manage_guild:
            await ctx.send("You need the Manage Server permission to remove channels.", ephemeral=True)
            return

        if event not in self.event_descriptions:
            await ctx.send(
                f"Invalid event. Use `/yalc events` to see available events.",
                ephemeral=True
            )
            return

        try:
            await self.config.guild(ctx.guild).event_channels.clear_raw(event)
            emoji, desc = self.event_descriptions[event]
            await ctx.send(
                f"{emoji} Removed channel override for **{event}**",
                ephemeral=True
            )
        except Exception as e:
            self.log.error(f"Failed to remove channel for event {event}: {e}")
            await ctx.send("Failed to remove logging channel.", ephemeral=True)

    async def tupperbox_addid(self, ctx: commands.Context, bot_id: str) -> None:
        """Add a bot user ID to ignore as Tupperbox proxy."""
        if not ctx.guild:
            await ctx.send("This command must be used in a server.", ephemeral=True)
            return
        
        if not ctx.channel.permissions_for(ctx.author).manage_guild:
            await ctx.send("You need the Manage Server permission to modify Tupperbox settings.", ephemeral=True)
            return

        if not bot_id.isdigit() or len(bot_id) < 17:
            await ctx.send("Please provide a valid Discord user ID (17+ digits).", ephemeral=True)
            return

        try:
            ids = await self.config.guild(ctx.guild).tupperbox_ids()
            if bot_id in ids:
                await ctx.send(f"ID `{bot_id}` is already in the ignore list.", ephemeral=True)
                return
            ids.append(bot_id)
            await self.config.guild(ctx.guild).tupperbox_ids.set(ids)
            await ctx.send(f"Added `{bot_id}` to Tupperbox ignore list.", ephemeral=True)
        except Exception as e:
            self.log.error(f"Failed to add Tupperbox ID {bot_id}: {e}")
            await ctx.send("Failed to add ID to ignore list.", ephemeral=True)

    async def tupperbox_removeid(self, ctx: commands.Context, bot_id: str) -> None:
        """Remove a bot user ID from the Tupperbox ignore list."""
        if not ctx.guild:
            await ctx.send("This command must be used in a server.", ephemeral=True)
            return
        
        if not ctx.channel.permissions_for(ctx.author).manage_guild:
            await ctx.send("You need the Manage Server permission to modify Tupperbox settings.", ephemeral=True)
            return

        try:
            ids = await self.config.guild(ctx.guild).tupperbox_ids()
            if bot_id not in ids:
                await ctx.send(f"ID `{bot_id}` is not in the ignore list.", ephemeral=True)
                return
            
            ids.remove(bot_id)
            await self.config.guild(ctx.guild).tupperbox_ids.set(ids)
            await ctx.send(f"Removed `{bot_id}` from Tupperbox ignore list.", ephemeral=True)
        except Exception as e:
            self.log.error(f"Failed to remove Tupperbox ID {bot_id}: {e}")
            await ctx.send("Failed to remove ID from ignore list.", ephemeral=True)

    def is_tupperbox_message(self, message: discord.Message, tupperbox_ids: list[str]) -> bool:
        """Check if a message is from Tupperbox or a configured proxy bot.
        This checks both the author's ID against the configured list and
        verifies if they have a #0000 discriminator (indicating a botaccount).
        Uses the discriminator attribute directly for robustness.
        """
        author = getattr(message, "author", None)
        if not author:
            return False
        if str(getattr(author, "id", "")) in tupperbox_ids:
            return True
        # Prefer attribute access for discriminator
        discriminator = getattr(author, "discriminator", None)
        if discriminator is not None:
            if str(discriminator) == "0" or str(discriminator) == "0000":
                self.log.debug(f"Detected potential Tupperbox message from {author} (discriminator: {discriminator})")
                return True
        # Fallback: parse from string if attribute missing
        try:
            full_tag = str(author)
            if "#" in full_tag:
                tag_disc = full_tag.split("#", 1)[1]
                if tag_disc in ("0", "0000"):
                    self.log.debug(f"Detected potential Tupperbox message from {full_tag} (string fallback)")
                    return True
        except Exception as e:
            self.log.debug(f"Failed to check discriminator robustly: {e}")
        return False

    async def safe_send(self, channel: Optional[discord.abc.Messageable], *args, **kwargs) -> None:
        """Safely send a message or embed to a channel, catching and logging exceptions."""
        if channel is None:
            self.log.warning("safe_send: Channel is None, cannot send message.")
            return
        try:
            await channel.send(*args, **kwargs)
        except Exception as e:
            self.log.error(f"safe_send: Failed to send message: {e}")

async def setup(bot: Red) -> None:
    """Set up the YALC cog."""
    cog = YALC(bot)
    await bot.add_cog(cog)

