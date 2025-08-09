"""
YALC - Yet Another Logging Cog for Red-DiscordBot.
A comprehensive logging solution with both classic and slash commands.
"""
import discord
from redbot.core import Config, commands, app_commands
from redbot.core.bot import Red
# Import dashboard integration from local module
from .dashboard.dashboard_integration import DashboardIntegration, dashboard_page
_dashboard_available = True
from typing import Dict, List, Optional, Union, cast
import datetime
import asyncio
import logging
import time
from datetime import timedelta
from redbot.core import modlog
import typing

class YALC(commands.Cog, DashboardIntegration):
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

    def __init__(self, bot: Red):
        self.bot = bot
        self.config = Config.get_conf(self, identifier=1234567875)
        self.log = logging.getLogger("red.YALC")
        
        # Dashboard integration attributes - required for Red Web Dashboard
        self.name = "YALC"
        self.description = "Yet Another Logging Cog - Comprehensive Discord event logging with dashboard integration"
        self.version = "3.0.0"
        self.author = "YALC Team"
        self.repo = "https://github.com/your-repo/YALC"
        self.support = "https://discord.gg/your-support"
        self.icon = "https://cdn-icons-png.flaticon.com/512/928/928797.png"
        
        # Real-time audit log entry storage for role attribution
        self.recent_audit_entries = {}
        
        # Event descriptions for logging and dashboard
        self.event_descriptions = {
            # Message events
            "message_delete": ("🗑️", "Message Deletions"),
            "message_edit": ("✏️", "Message Edits"),
            "message_bulk_delete": ("♻️", "Bulk Message Deletions"),
            "message_pin": ("📌", "Message Pins"),
            "message_unpin": ("📍", "Message Unpins"),
            
            # Member events
            "member_join": ("👋", "Member Joins"),
            "member_leave": ("🚪", "Member Leaves"),
            "member_ban": ("🔨", "Member Bans"),
            "member_unban": ("🔓", "Member Unbans"),
            "member_update": ("👤", "Member Updates"),
            "member_kick": ("👢", "Member Kicks"),
            "member_timeout": ("⏰", "Member Timeouts"),
            
            # Channel events
            "channel_create": ("📝", "Channel Creation"),
            "channel_delete": ("🗑️", "Channel Deletion"),
            "channel_update": ("🔄", "Channel Updates"),
            "thread_create": ("🧵", "Thread Creation"),
            "thread_delete": ("🗑️", "Thread Deletion"),
            "thread_update": ("🔄", "Thread Updates"),
            "thread_member_join": ("➡️", "Thread Member Joins"),
            "thread_member_leave": ("⬅️", "Thread Member Leaves"),
            "forum_post_create": ("📋", "Forum Post Creation"),
            "forum_post_delete": ("🗑️", "Forum Post Deletion"),
            "forum_post_update": ("🔄", "Forum Post Updates"),
            
            # Role events
            "role_create": ("✨", "Role Creation"),
            "role_delete": ("🗑️", "Role Deletion"),
            "role_update": ("🔄", "Role Updates"),
            
            # Guild events
            "guild_update": ("⚙️", "Server Updates"),
            "emoji_update": ("😀", "Emoji Updates"),
            "sticker_update": ("🏷️", "Sticker Updates"),
            "invite_create": ("📨", "Invite Creation"),
            "invite_delete": ("📪", "Invite Deletion"),
            
            # Event management
            "guild_scheduled_event_create": ("📅", "Event Creation"),
            "guild_scheduled_event_update": ("🔄", "Event Updates"),
            "guild_scheduled_event_delete": ("🗑️", "Event Deletion"),
            "stage_instance_create": ("🎤", "Stage Instance Creation"),
            "stage_instance_update": ("🔄", "Stage Instance Updates"),
            "stage_instance_delete": ("🗑️", "Stage Instance Deletion"),
            
            # Voice events
            "voice_update": ("🔊", "Voice Updates"),
            "voice_state_update": ("🎧", "Voice State Changes"),
            
            # Command events
            "command_use": ("⚡", "Command Usage"),
            "command_error": ("❌", "Command Errors"),
            "application_cmd": ("🤖", "Application Commands"),
            
            # Reaction events
            "reaction_add": ("👍", "Reaction Additions"),
            "reaction_remove": ("👎", "Reaction Removals"),
            "reaction_clear": ("🧹", "Reaction Clears"),
            
            # Integration events
            "integration_create": ("🔗", "Integration Creation"),
            "integration_update": ("🔄", "Integration Updates"),
            "integration_delete": ("🗑️", "Integration Deletion"),
            
            # Webhook/AutoMod
            "webhook_update": ("🪝", "Webhook Updates"),
            "automod_rule_create": ("🛡️", "AutoMod Rule Creation"),
            "automod_rule_update": ("🔄", "AutoMod Rule Updates"),
            "automod_rule_delete": ("🗑️", "AutoMod Rule Deletion"),
            "automod_action": ("⚔️", "AutoMod Actions"),
        }
        
        # Configuration defaults
        default_guild = {
            "events": {event: False for event in self.event_descriptions.keys()},
            "event_channels": {event: None for event in self.event_descriptions.keys()},
            "ignored_users": [],
            "ignored_roles": [],
            "ignored_channels": [],
            "ignored_categories": [],
            "ignore_bots": False,
            "ignore_webhooks": False,
            "ignore_tupperbox": True,
            "ignore_apps": True,
            "tupperbox_ids": ["239232811662311425"],  # Default Tupperbox bot ID
            "include_thumbnails": True,
            "detect_proxy_deletes": True,
            "message_prefix_filter": [],
            "webhook_name_filter": []
        }
        
        self.config.register_guild(**default_guild)
        
        # Dashboard integration is handled via inheritance and decorators in dashboard_integration.py

    async def _get_audit_log_entry(self, guild, action, target=None, timeout_seconds=30):
        """
        Helper function to get recent audit log entries with improved reliability and generalized fallback matching.

        Args:
            guild: The guild to search audit logs in
            action: The AuditLogAction to search for
            target: Optional target to match against (user, channel, role, etc.)
            timeout_seconds: How recent the entry should be (default 30 seconds)

        Returns:
            AuditLogEntry or None if not found/no permission

        Matching order:
        1. Exact object match (entry.target == target)
        2. Fallback: match by .id if both entry.target and target have .id
        3. Fallback: most recent entry in window
        """
        if not guild.me.guild_permissions.view_audit_log:
            return None

        await asyncio.sleep(2)

        try:
            now = datetime.datetime.now(datetime.UTC)
            entries = []
            async for entry in guild.audit_logs(action=action, limit=15):
                age = (now - entry.created_at).total_seconds()
                if age > timeout_seconds * 2:
                    break
                if age <= timeout_seconds:
                    entries.append(entry)
                    # First, try exact match
                    if target is not None and entry.target == target:
                        return entry
            # Fallback: try matching by .id for any target type
            if target is not None and hasattr(target, "id"):
                for entry in entries:
                    if hasattr(entry.target, "id") and entry.target.id == target.id:
                        return entry
            # Fallback: return most recent entry in window if any
            if entries:
                return entries[0]
        except (discord.Forbidden, discord.HTTPException, asyncio.TimeoutError):
            pass

        return None

    async def should_log_event(self, guild: discord.Guild, event_type: str,
                         channel: Optional[discord.abc.GuildChannel] = None,
                         user: Optional[Union[discord.Member, discord.User]] = None,
                         message: Optional[discord.Message] = None) -> bool:
        """
        Check if an event should be logged based on settings and ignore lists.
        
        Parameters
        ----------
        guild: discord.Guild
            The guild where the event occurred
        event_type: str
            The type of event being checked
        channel: Optional[discord.abc.GuildChannel]
            The channel where the event occurred, if applicable
        user: Optional[Union[discord.Member, discord.User]]
            The user who triggered the event, if applicable
        message: Optional[discord.Message]
            The message involved in the event, if applicable
            
        Returns
        -------
        bool
            True if the event should be logged, False if it should be ignored
        """
        try:
            # If no guild, we can't get settings, so don't log
            if not guild:
                return False
                
            # Get all settings at once to minimize database calls
            settings = await self.config.guild(guild).all()
            
            # 1. Check if this event type is enabled at all
            if not settings["events"].get(event_type, False):
                self.log.debug(f"Event type {event_type} is disabled in settings")
                return False
                
            # 2. Channel-based ignore checks
            if channel:
                # Direct channel ignore
                if channel.id in settings["ignored_channels"]:
                    self.log.debug(f"Channel {channel.id} is in the ignored channels list")
                    return False
                
                # Category ignore
                if isinstance(channel, discord.TextChannel) and channel.category:
                    ignored_categories = settings.get("ignored_categories", [])
                    if channel.category.id in ignored_categories:
                        self.log.debug(f"Category {channel.category.id} is in the ignored categories list")
                        return False
                        
                # Thread parent ignore (if this is a thread and parent is ignored)
                if isinstance(channel, discord.Thread) and channel.parent:
                    if channel.parent.id in settings["ignored_channels"]:
                        self.log.debug(f"Thread parent {channel.parent.id} is in the ignored channels list")
                        return False
            
            # 3. User-based ignore checks
            if user:
                # Direct user ignore
                if user.id in settings["ignored_users"]:
                    self.log.debug(f"User {user.id} is in the ignored users list")
                    return False
                
                # Role-based ignore (only for Members)
                if isinstance(user, discord.Member):
                    ignored_roles = settings["ignored_roles"]
                    if any(r.id in ignored_roles for r in user.roles):
                        self.log.debug(f"User {user.id} has a role that is in the ignored roles list")
                        return False
                        
                # Bot ignore (optionally ignore all bot users)
                if getattr(user, "bot", False) and settings.get("ignore_bots", False):
                    self.log.debug(f"User {user.id} is a bot and bot messages are ignored")
                    return False
            
            # 4. Message-specific ignore checks
            if message:
                # Tupperbox ignore
                if settings.get("ignore_tupperbox", True):
                    tupperbox_ids = settings.get("tupperbox_ids", ["239232811662311425"])
                    if await self.is_tupperbox_message(message, tupperbox_ids):
                        self.log.debug(f"Message {message.id} detected as Tupperbox message")
                        return False
                
                # Webhook ignore
                if settings.get("ignore_webhooks", False) and getattr(message, "webhook_id", None):
                    self.log.debug(f"Message {message.id} is from webhook {message.webhook_id} and webhooks are ignored")
                    return False
                    
                # App message ignore
                if settings.get("ignore_apps", True) and getattr(message, "application", None):
                    self.log.debug(f"Message {message.id} is from app {message.application.id} and apps are ignored")
                    return False
            
            # If we've passed all ignore checks, we should log this event
            return True
            
        except Exception as e:
            self.log.error(f"Error in should_log_event: {e}", exc_info=True)
            # Default to True if an error occurred (better to log in case of doubt)
            return True


    # Removed setup_dashboard; dashboard pages are now registered via inheritance and decorators in dashboard_integration.py

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
        """
        Create a standardized, visually appealing embed for logging.
        
        Parameters
        ----------
        event_type: str
            The type of event being logged
        description: str
            Primary description for the embed
        **kwargs
            Additional fields to include in the embed
            
        Returns
        -------
        discord.Embed
            A formatted embed ready for sending
        """
        # Comprehensive color coding for visual differentiation of event types
        color_map = {
            # Message events - Blues
            "message_delete": discord.Color(0xE74C3C),      # Red
            "message_edit": discord.Color(0x3498DB),        # Blue
            "message_bulk_delete": discord.Color(0xC0392B), # Dark Red
            "message_pin": discord.Color(0x1ABC9C),         # Teal
            "message_unpin": discord.Color(0x16A085),       # Dark Teal
            
            # Member events - Greens and oranges
            "member_join": discord.Color(0x2ECC71),         # Green
            "member_leave": discord.Color(0xF39C12),        # Orange
            "member_ban": discord.Color(0xC0392B),          # Dark Red
            "member_unban": discord.Color(0x27AE60),        # Dark Green
            "member_update": discord.Color(0x3498DB),       # Blue
            "member_kick": discord.Color(0xE67E22),         # Dark Orange
            "member_timeout": discord.Color(0xD35400),      # Very Dark Orange
            
            # Channel events - Purples
            "channel_create": discord.Color(0x9B59B6),      # Purple
            "channel_delete": discord.Color(0x8E44AD),      # Dark Purple
            "channel_update": discord.Color(0x9B59B6),      # Purple
            "thread_create": discord.Color(0x9B59B6),       # Purple
            "thread_delete": discord.Color(0x8E44AD),       # Dark Purple
            "thread_update": discord.Color(0x9B59B6),       # Purple
            "thread_member_join": discord.Color(0xAF7AC5),  # Light Purple
            "thread_member_leave": discord.Color(0x884EA0), # Medium Purple
            "forum_post_create": discord.Color(0x9B59B6),   # Purple
            "forum_post_delete": discord.Color(0x8E44AD),   # Dark Purple
            "forum_post_update": discord.Color(0x9B59B6),   # Purple
            
            # Role events - Yellows
            "role_create": discord.Color(0xF1C40F),         # Yellow
            "role_delete": discord.Color(0xF39C12),         # Orange
            "role_update": discord.Color(0xF1C40F),         # Yellow
            
            # Guild events - Blues
            "guild_update": discord.Color(0x3498DB),        # Blue
            "emoji_update": discord.Color(0xF1C40F),        # Yellow
            "sticker_update": discord.Color(0xF1C40F),      # Yellow
            "invite_create": discord.Color(0x2ECC71),       # Green
            "invite_delete": discord.Color(0xE74C3C),       # Red
            
            # Event management - Teals
            "guild_scheduled_event_create": discord.Color(0x1ABC9C),  # Teal
            "guild_scheduled_event_update": discord.Color(0x16A085),  # Dark Teal
            "guild_scheduled_event_delete": discord.Color(0xE74C3C),  # Red
            "stage_instance_create": discord.Color(0x1ABC9C),         # Teal
            "stage_instance_update": discord.Color(0x16A085),         # Dark Teal
            "stage_instance_delete": discord.Color(0xE74C3C),         # Red
            
            # Voice events - Blues
            "voice_update": discord.Color(0x3498DB),        # Blue
            "voice_state_update": discord.Color(0x2980B9),  # Dark Blue
            
            # Command events - Grays
            "command_use": discord.Color(0x95A5A6),         # Light Gray
            "command_error": discord.Color(0xE74C3C),       # Red
            "application_cmd": discord.Color(0x7F8C8D),     # Gray
            
            # Reaction events - Yellows
            "reaction_add": discord.Color(0xF1C40F),        # Yellow
            "reaction_remove": discord.Color(0xF39C12),     # Orange
            "reaction_clear": discord.Color(0xE67E22),      # Dark Orange
            
            # Integration events - Teals
            "integration_create": discord.Color(0x1ABC9C),  # Teal
            "integration_update": discord.Color(0x16A085),  # Dark Teal
            "integration_delete": discord.Color(0xE74C3C),  # Red
            
            # Webhook/AutoMod - Grays and Reds
            "webhook_update": discord.Color(0x7F8C8D),      # Gray
            "automod_rule_create": discord.Color(0x2ECC71), # Green
            "automod_rule_update": discord.Color(0x27AE60), # Dark Green
            "automod_rule_delete": discord.Color(0xE74C3C), # Red
            "automod_action": discord.Color(0xE67E22),      # Dark Orange
        }
        
        # Get appropriate emoji for the event type
        emoji, _ = self.event_descriptions.get(event_type, ("📝", "Event"))
        
        # Format the title with a cleaner presentation
        title = f"{emoji} {event_type.replace('_', ' ').title()}"
        
        # Create the base embed with appropriate styling
        embed = discord.Embed(
            title=title,
            description=description + "\n\u200b",  # Add spacing after description
            color=color_map.get(event_type, discord.Color.blurple()),
            timestamp=datetime.datetime.now(datetime.UTC)
        )
        
        # Add fields with improved formatting for better readability
        for key, value in kwargs.items():
            if value is None:
                continue
                
            field_name = key.replace('_', ' ').title()
            
            # Format field values based on content type
            if isinstance(value, list):
                # Format lists as bulleted items
                if not value:  # Empty list
                    continue
                if len(value) == 1:
                    formatted_value = value[0]
                else:
                    formatted_value = "\n".join(f"• {v}" for v in value)
                    
            elif isinstance(value, (int, float, bool)):
                # Simple representation for primitives
                formatted_value = str(value)
                
            elif isinstance(value, str):
                if not value.strip():  # Empty or whitespace-only string
                    continue
                    
                # Format long or multi-line strings appropriately
                if "\n" in value or len(value) > 60:
                    # For code blocks or already formatted text, preserve formatting
                    if value.startswith("```") and value.endswith("```"):
                        formatted_value = value
                    # For long text that isn't a code block, use blockquotes for readability
                    else:
                        formatted_value = value.replace("\n", "\n> ")
                        formatted_value = f"> {formatted_value}"
                else:
                    formatted_value = value
            else:
                # For any other types, convert to string
                formatted_value = str(value)
                
            # Truncate extremely long values to avoid hitting Discord limits
            if isinstance(formatted_value, str) and len(formatted_value) > 1024:
                formatted_value = formatted_value[:1021] + "..."
                
            # Add the formatted field to the embed
            embed.add_field(name=field_name, value=formatted_value, inline=False)
            
        # Set the footer with the YALC branding
        self.set_embed_footer(embed)
        
        return embed

    def set_embed_footer(self, embed: discord.Embed, event_time: Optional[datetime.datetime] = None, label: str = "YALC Logger") -> None:
        """
        Set a standard footer for all log embeds, including a formatted time and logo.
        
        Parameters
        ----------
        embed: discord.Embed
            The embed to modify
        event_time: Optional[datetime.datetime]
            The timestamp to show in the footer
        label: str
            Text label to show in the footer
            
        Notes
        -----
        This preserves the existing embed logo URL as requested.
        """
        # Use current time if not specified
        if event_time is None:
            event_time = datetime.datetime.now(datetime.UTC)
            
        # Format time in a readable manner
        formatted_time = event_time.strftime('%B %d, %Y, %I:%M %p UTC')
        
        # Set footer with the existing logo URL
        embed.set_footer(
            text=f"{label} • {formatted_time}",
            icon_url="https://cdn-icons-png.flaticon.com/512/928/928797.png"  # Preserved existing logo
        )

    async def cog_unload(self) -> None:
        """Clean up when cog is unloaded."""
        try:
            dashboard_cog = self.bot.get_cog("Dashboard")
            if dashboard_cog and hasattr(dashboard_cog, "rpc"):
                dashboard_cog.rpc.third_parties_handler.remove_third_party(self)
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
        
        # Dashboard integration will be handled by the on_dashboard_cog_add listener
        # when the Dashboard cog loads
        self.log.info("YALC cog loaded - dashboard integration will be registered when Dashboard cog loads.")
    @commands.Cog.listener()
    async def on_voice_state_update(self, member: discord.Member, before: discord.VoiceState, after: discord.VoiceState):
        """Log voice channel join/leave/move events, including who moved the user if possible."""
        try:
            channel = await self.get_log_channel(member.guild, "voice_state_update")
            if not channel:
                return
            desc = f"🎧 {member.mention} voice state changed: "
            actor_info = ""
            if before.channel != after.channel:
                # Try to get who moved the user from audit log if moved/kicked
                actor = None
                if before.channel and after.channel:
                    desc += f"moved from {before.channel.mention} to {after.channel.mention}"
                    # Check for move in audit log
                    entry = await self._get_audit_log_entry(member.guild, discord.AuditLogAction.member_move, target=member, timeout_seconds=10)
                    if entry and entry.user:
                        actor_info = f" by {entry.user.mention} ({entry.user})"
                elif before.channel and not after.channel:
                    desc += f"left {before.channel.mention}"
                    entry = await self._get_audit_log_entry(member.guild, discord.AuditLogAction.member_disconnect, target=member, timeout_seconds=10)
                    if entry and entry.user:
                        actor_info = f" by {entry.user.mention} ({entry.user})"
                elif after.channel and not before.channel:
                    desc += f"joined {after.channel.mention}"
            else:
                desc += "state updated"
            embed = self.create_embed("voice_state_update", desc + actor_info)
            await self.safe_send(channel, embed=embed)
        except Exception as e:
            self.log.error(f"Failed to log voice_state_update: {e}")

    @commands.Cog.listener()
    async def on_presence_update(self, before: discord.Member, after: discord.Member):
        """Log presence/status updates."""
        try:
            channel = await self.get_log_channel(after.guild, "presence_update")
            if not channel:
                return
            desc = f"🟢 {after.mention} presence changed: {before.status} → {after.status}"
            # Presence updates are user-driven, so actor is the user themselves
            embed = self.create_embed("presence_update", desc + f" (by {after.mention} ({after}))")
            await self.safe_send(channel, embed=embed)
        except Exception as e:
            self.log.error(f"Failed to log presence_update: {e}")

    @commands.Cog.listener()
    async def on_guild_integrations_update(self, guild: discord.Guild):
        """Log integration updates/removals, showing who did it if possible."""
        try:
            channel = await self.get_log_channel(guild, "integration_update")
            if not channel:
                return
            desc = f"🔗 Integrations updated for {guild.name}"
            # Try to get actor from audit log
            entry = await self._get_audit_log_entry(guild, discord.AuditLogAction.integration_update, timeout_seconds=10)
            if entry and entry.user:
                desc += f" by {entry.user.mention} ({entry.user})"
            embed = self.create_embed("integration_update", desc)
            await self.safe_send(channel, embed=embed)
        except Exception as e:
            self.log.error(f"Failed to log guild_integrations_update: {e}")

    @commands.Cog.listener()
    async def on_invite_create(self, invite: discord.Invite):
        """Log invite creation, showing who did it."""
        try:
            channel = await self.get_log_channel(invite.guild, "invite_create")
            if not channel:
                return
            desc = f"📨 Invite created: {invite.url}"
            if invite.inviter:
                desc += f" by {invite.inviter.mention} ({invite.inviter})"
            else:
                # Try audit log fallback
                entry = await self._get_audit_log_entry(invite.guild, discord.AuditLogAction.invite_create, timeout_seconds=10)
                if entry and entry.user:
                    desc += f" by {entry.user.mention} ({entry.user})"
            embed = self.create_embed("invite_create", desc)
            await self.safe_send(channel, embed=embed)
        except Exception as e:
            self.log.error(f"Failed to log invite_create: {e}")

    @commands.Cog.listener()
    async def on_invite_delete(self, invite: discord.Invite):
        """Log invite deletion/expiration, showing who did it if possible."""
        try:
            channel = await self.get_log_channel(invite.guild, "invite_delete")
            if not channel:
                return
            desc = f"📪 Invite deleted/expired: {invite.url}"
            # Try audit log for deleter
            entry = await self._get_audit_log_entry(invite.guild, discord.AuditLogAction.invite_delete, timeout_seconds=10)
            if entry and entry.user:
                desc += f" by {entry.user.mention} ({entry.user})"
            embed = self.create_embed("invite_delete", desc)
            await self.safe_send(channel, embed=embed)
        except Exception as e:
            self.log.error(f"Failed to log invite_delete: {e}")

    @commands.Cog.listener()
    async def on_application_command_permissions_update(self, guild: discord.Guild, permissions):
        """Log application command permission changes, showing who did it if possible."""
        try:
            channel = await self.get_log_channel(guild, "application_cmd_permissions_update")
            if not channel:
                return
            desc = f"⚙️ Application command permissions updated."
            # Try audit log for actor
            entry = await self._get_audit_log_entry(guild, discord.AuditLogAction.application_command_permission_update, timeout_seconds=10)
            if entry and entry.user:
                desc += f" by {entry.user.mention} ({entry.user})"
            embed = self.create_embed("application_cmd_permissions_update", desc)
            await self.safe_send(channel, embed=embed)
        except Exception as e:
            self.log.error(f"Failed to log application_command_permissions_update: {e}")

    @commands.Cog.listener()
    async def on_audit_log_entry_create(self, entry):
        """Handle audit log entries for role updates and store them temporarily for real-time attribution."""
        try:
            # Only capture role_update audit entries for real-time role logging
            if entry.action == discord.AuditLogAction.role_update:
                # Store audit entry temporarily with timestamp for role attribution
                role_id = entry.target.id if entry.target else None
                if role_id:
                    self.recent_audit_entries[role_id] = {
                        'entry': entry,
                        'timestamp': time.time()
                    }
                    
                    # Clean up old entries (older than 30 seconds) to prevent memory leaks
                    current_time = time.time()
                    expired_keys = [
                        key for key, data in self.recent_audit_entries.items()
                        if current_time - data['timestamp'] > 30
                    ]
                    for key in expired_keys:
                        del self.recent_audit_entries[key]
                        
        except Exception as e:
            self.log.error(f"Failed to handle audit_log_entry_create: {e}", exc_info=True)


    # --- Event Listeners ---

    @commands.Cog.listener()
    async def on_dashboard_cog_add(self, dashboard_cog: commands.Cog) -> None:
        """Register YALC as a dashboard third party when dashboard cog is loaded."""
        try:
            dashboard_cog.rpc.third_parties_handler.add_third_party(self)
            self.log.info("Successfully registered YALC as a dashboard third party.")
        except Exception as e:
            self.log.error(f"Dashboard integration setup failed: {e}")


    @commands.Cog.listener()
    async def on_message_delete(self, message: discord.Message) -> None:
        """Log message deletion events, with enhanced Tupperbot filtering."""
        self.log.debug("Listener triggered: on_message_delete")
        
        # Skip processing if message has no guild or is in DM
        if not message.guild:
            self.log.debug("No guild on message.")
            return
            
        # Check early if we should process this message
        try:
            # Fetch settings first to avoid redundant DB calls
            settings = await self.config.guild(message.guild).all()
            
            # 1. Check if the event type is enabled at all
            if not settings["events"].get("message_delete", False):
                self.log.debug("message_delete event is disabled in settings.")
                return
            
            # 2. Enhanced Tupperbox message detection
            tupperbox_ids = settings.get("tupperbox_ids", ["239232811662311425"])
            ignore_tupperbox = settings.get("ignore_tupperbox", True)
            
            if ignore_tupperbox:
                # Check if this specific message is a Tupperbox message
                if await self.is_tupperbox_message(message, tupperbox_ids):
                    self.log.debug("Skipping Tupperbox message_delete event - direct detection.")
                    return
                
                # Check for proxy deletion patterns
                if settings.get("detect_proxy_deletes", True):
                    # Time-based proxy deletion detection
                    # (Tupperbox often deletes the original command message after proxying)
                    now = datetime.datetime.now(datetime.UTC)
                    msg_age = now - message.created_at
                    
                    # Check if message is very new (typical for proxy command deletion)
                    if msg_age.total_seconds() < 3.0:
                        content = getattr(message, "content", "").lower()
                        
                        # Common proxy message command patterns
                        proxy_commands = [";", "!", "//", "pk;", "tb:", "$", "t!"]
                        
                        if any(content.startswith(cmd) for cmd in proxy_commands):
                            self.log.debug("Skipping likely proxy command deletion.")
                            return
                        
                        # Check for message prefix patterns from settings
                        custom_prefixes = settings.get("message_prefix_filter", [])
                        if any(content.startswith(prefix) for prefix in custom_prefixes):
                            self.log.debug("Skipping deletion due to custom prefix match.")
                            return
                
            # 3. Check webhook ignore setting
            if settings.get("ignore_webhooks", False) and getattr(message, "webhook_id", None):
                # Additional filtering for specific webhook names
                webhook_name_filters = settings.get("webhook_name_filter", [])
                webhook = getattr(message, "webhook", None)
                
                if webhook and webhook_name_filters:
                    webhook_name = getattr(webhook, "name", "").lower()
                    if any(filter_term.lower() in webhook_name for filter_term in webhook_name_filters):
                        self.log.debug(f"Skipping webhook message from filtered name: {webhook_name}")
                        return
                else:
                    self.log.debug("Skipping webhook message (all webhooks ignored).")
                    return
                
            # 4. Check app message ignore setting
            if settings.get("ignore_apps", True) and getattr(message, "application", None):
                self.log.debug("Skipping application message deletion.")
                return
                
            # 5. Check if we should ignore based on channel, user, or roles
            if not await self.should_log_event(message.guild, "message_delete", 
                                              channel=message.channel, 
                                              user=message.author,
                                              message=message):
                self.log.debug("should_log_event returned False - channel/user/role is ignored.")
                return
                
            # 6. Get the appropriate log channel
            channel = await self.get_log_channel(message.guild, "message_delete")
            if not channel:
                self.log.warning("No log channel set for message_delete.")
                return
                
        except Exception as e:
            self.log.error(f"Error in pre-processing message_delete event: {e}", exc_info=True)
            return
            
        # Process and log the event
        try:
            author = getattr(message, "author", None)
            content = getattr(message, "content", "")
            attachments = [a.url for a in getattr(message, "attachments", [])]
            embeds = getattr(message, "embeds", [])
            channel_name = getattr(message.channel, "name", str(message.channel) if message.channel else "Unknown")
            
            # Additional context for debugging
            self.log.debug(f"Logging message_delete: {author} in #{channel_name}")
            
            # Rich message metadata for comprehensive logging
            metadata = {}
            
            # Format timestamps consistently with Discord native formatting
            if hasattr(message, "created_at") and message.created_at:
                formatted_time = discord.utils.format_dt(message.created_at, style="F")
                relative_time = discord.utils.format_dt(message.created_at, style="R")
                metadata["Created"] = f"{formatted_time} ({relative_time})"
            
            # User information with clickable link
            if author and hasattr(author, "id"):
                user_link = f"[{author}](https://discord.com/users/{author.id})"
                metadata["Author"] = f"{user_link} ({author.id})"
                
                # Add role info if author is a member (not a webhook or system user)
                if isinstance(author, discord.Member) and author.roles:
                    top_role = author.roles[-1] if len(author.roles) > 1 else None
                    if top_role and top_role.name != "@everyone":
                        metadata["Top Role"] = f"{top_role.mention} ({top_role.id})"
            else:
                metadata["Author"] = "Unknown User"
            
            # Try to get audit log information about who deleted the message
            deletion_info = None
            if message.guild and message.guild.me.guild_permissions.view_audit_log:
                try:
                    # Look for message delete audit log entries
                    audit_entry = await self._get_audit_log_entry(
                        message.guild,
                        discord.AuditLogAction.message_delete,
                        target=message.author,
                        timeout_seconds=10
                    )
                    
                    if audit_entry:
                        deletion_info = {
                            "deleted_by": audit_entry.user,
                            "reason": getattr(audit_entry, "reason", None)
                        }
                except Exception as e:
                    self.log.debug(f"Could not fetch audit log for message deletion: {e}")
            
            # Initialize the embed with base information
            description = f"🗑️ Message deleted in {getattr(message.channel, 'mention', str(message.channel))}"
            
            # Add deletion information if available
            if deletion_info:
                deleter = deletion_info["deleted_by"]
                if deleter != message.author:  # Only show if deleted by someone else
                    description += f" by {deleter.mention}"
            
            description += "\n\u200b"
            
            # Add jump URL if available (useful for context)
            message_id = getattr(message, "id", None)
            channel_id = getattr(message.channel, "id", None)
            if message_id and channel_id:
                description += f"\nMessage ID: `{message_id}`"
            
            # Add deletion metadata
            if deletion_info:
                deleter = deletion_info["deleted_by"]
                metadata["Deleted By"] = f"{deleter.mention} (`{deleter}`, ID: `{deleter.id}`)"
                
                # Add reason if provided
                if deletion_info["reason"]:
                    metadata["Deletion Reason"] = deletion_info["reason"]
                    
                # Indicate if it was self-deleted vs moderated
                if deleter == message.author:
                    metadata["Deletion Type"] = "Self-deleted"
                else:
                    metadata["Deletion Type"] = "Moderated deletion"
            else:
                # If no audit log info available, indicate unknown
                metadata["Deleted By"] = "Unknown (audit log unavailable)"
            
            # Build a comprehensive and visually appealing embed
            embed = self.create_embed(
                "message_delete",
                description,
                **metadata
            )
            
            # Format content with proper code blocks for different content types
            if content:
                # Use syntax highlighting for code blocks if detected
                if content.startswith("```") and content.endswith("```"):
                    # Preserve the code block as-is
                    embed.add_field(name="Content", value=content[:1024] if len(content) <= 1024 
                                   else content[:1021] + "...", inline=False)
                else:
                    # Format regular text with multi-line support and proper escaping
                    formatted_content = content
                    if len(formatted_content) > 1024:
                        formatted_content = formatted_content[:1021] + "..."
                    
                    embed.add_field(name="Content", value=f"```\n{formatted_content}\n```", inline=False)
            else:
                embed.add_field(name="Content", value="*No text content*", inline=False)
            
            # Handle attachments with better formatting
            if attachments:
                attachment_list = []
                for i, url in enumerate(attachments):
                    file_name = url.split("/")[-1]
                    attachment_list.append(f"[{file_name}]({url})")
                
                embed.add_field(
                    name=f"Attachments ({len(attachments)})",
                    value="\n".join(attachment_list) if len(attachment_list) <= 5 
                          else "\n".join(attachment_list[:5]) + f"\n*...and {len(attachment_list) - 5} more*",
                    inline=False
                )
            
            # Add embed information if message contained embeds
            if embeds:
                embed_info = []
                for i, msg_embed in enumerate(embeds[:3]):  # Show details for first 3 embeds
                    # Get the embed title with proper formatting
                    embed_title = getattr(msg_embed, "title", "*No title*")
                    if embed_title and len(embed_title) > 80:
                        embed_title = embed_title[:77] + "..."
                    
                    # Format the embed details with a divider for better readability
                    embed_details = [f"**Embed {i+1}**: {embed_title}"]
                    embed_details.append("───────────────")  # Divider
                    
                    # Add description with proper truncation and formatting
                    embed_desc = getattr(msg_embed, "description", None)
                    if embed_desc:
                        if len(embed_desc) > 200:  # Increased character limit
                            embed_desc = embed_desc[:197] + "..."
                        embed_details.append(f"**Description**: {embed_desc}")
                    
                    # Add URL if present
                    embed_url = getattr(msg_embed, "url", None)
                    if embed_url:
                        embed_details.append(f"**URL**: [Link]({embed_url})")
                    
                    # Enhanced author display with URL if available
                    embed_author = getattr(msg_embed, "author", None)
                    if embed_author:
                        author_name = getattr(embed_author, "name", None)
                        author_url = getattr(embed_author, "url", None)
                        author_icon = getattr(embed_author, "icon_url", None)
                        
                        if author_name:
                            if author_url:
                                embed_details.append(f"**Author**: [{author_name}]({author_url})")
                            else:
                                embed_details.append(f"**Author**: {author_name}")
                            
                            if author_icon:
                                embed_details.append(f"**Author Icon**: [View]({author_icon})")
                    
                    # Add fields with improved formatting (up to 3)
                    embed_fields = getattr(msg_embed, "fields", [])
                    if embed_fields:
                        embed_details.append("**Fields**:")
                        for j, field in enumerate(embed_fields[:3]):
                            field_name = getattr(field, "name", "Unnamed Field")
                            field_value = getattr(field, "value", "")
                            field_inline = getattr(field, "inline", False)
                            
                            # Format field values with truncation
                            if field_value and len(field_value) > 100:
                                field_value = field_value[:97] + "..."
                            
                            # Show field name and value with inline status
                            inline_status = " (Inline)" if field_inline else ""
                            embed_details.append(f"• **{field_name}**{inline_status}: {field_value}")
                        
                        # Show if there are more fields
                        if len(embed_fields) > 3:
                            embed_details.append(f"*...and {len(embed_fields) - 3} more fields*")
                    
                    # Enhanced media display
                    if getattr(msg_embed, "image", None) and getattr(msg_embed.image, "url", None):
                        embed_details.append(f"**Image**: [View]({msg_embed.image.url})")
                    
                    if getattr(msg_embed, "thumbnail", None) and getattr(msg_embed.thumbnail, "url", None):
                        embed_details.append(f"**Thumbnail**: [View]({msg_embed.thumbnail.url})")
                    
                    # Add timestamp if present
                    if getattr(msg_embed, "timestamp", None):
                        formatted_time = discord.utils.format_dt(msg_embed.timestamp, style="f")
                        embed_details.append(f"**Timestamp**: {formatted_time}")
                    
                    # Footer with enhanced formatting
                    embed_footer = getattr(msg_embed, "footer", None)
                    if embed_footer:
                        footer_text = getattr(embed_footer, "text", None)
                        footer_icon = getattr(embed_footer, "icon_url", None)
                        
                        if footer_text:
                            if len(footer_text) > 100:
                                footer_text = footer_text[:97] + "..."
                            embed_details.append(f"**Footer**: {footer_text}")
                        
                        if footer_icon:
                            embed_details.append(f"**Footer Icon**: [View]({footer_icon})")
                    
                    # Add color with a visual indicator
                    if getattr(msg_embed, "color", None):
                        color_hex = f"#{msg_embed.color.value:06x}"
                        # Add a colored square emoji based on general color
                        if msg_embed.color.value < 0x800000:  # Dark/Red
                            color_indicator = "🟥"
                        elif msg_embed.color.value < 0x808000:  # Orange/Brown
                            color_indicator = "🟧"
                        elif msg_embed.color.value < 0x008000:  # Yellow/Gold
                            color_indicator = "🟨"
                        elif msg_embed.color.value < 0x008080:  # Green
                            color_indicator = "🟩"
                        elif msg_embed.color.value < 0x000080:  # Teal/Cyan
                            color_indicator = "🟦"
                        elif msg_embed.color.value < 0x800080:  # Blue/Indigo
                            color_indicator = "🟪"
                        else:  # Purple/Pink
                            color_indicator = "🟪"
                        
                        embed_details.append(f"**Color**: {color_indicator} {color_hex}")
                    
                    # Join all details together with empty line for readability
                    embed_info.append("\n".join(embed_details))
                
                # Show info about additional embeds
                if len(embeds) > 3:
                    embed_info.append(f"*...and {len(embeds) - 3} more embeds*")
                
                # Add all embed info to the logging embed
                embed.add_field(
                    name=f"Embeds ({len(embeds)})",
                    value="\n".join(embed_info),
                    inline=False
                )
            
            # Channel information
            embed.add_field(
                name="Channel",
                value=f"{getattr(message.channel, 'mention', '#' + channel_name)} (`{channel_name}`)",
                inline=True
            )
            
            # Include user thumbnail for better visual identification
            if settings.get("include_thumbnails", True) and author and hasattr(author, "display_avatar") and author.display_avatar:
                embed.set_thumbnail(url=author.display_avatar.url)
            
            # Send the log message to the configured channel
            await self.safe_send(channel, embed=embed)
            
        except Exception as e:
            self.log.error(f"Failed to log message_delete: {e}", exc_info=True)

    @commands.Cog.listener()
    async def on_message_edit(self, before: discord.Message, after: discord.Message) -> None:
        """Log message edit events, with enhanced Tupperbot filtering."""
        self.log.debug("Listener triggered: on_message_edit")
        
        # Skip processing if no guild (DM message or other non-guild context)
        if not before.guild:
            self.log.debug("No guild on message.")
            return
            
        # Early processing checks
        try:
            # Get settings once to avoid redundant database calls
            settings = await self.config.guild(before.guild).all()
            
            # 1. Check if the message_edit event is enabled
            if not settings["events"].get("message_edit", False):
                self.log.debug("message_edit event is disabled in settings.")
                return
                
            # 2. Enhanced Tupperbot filtering
            tupperbox_ids = settings.get("tupperbox_ids", ["239232811662311425"])
            ignore_tupperbox = settings.get("ignore_tupperbox", True)
            
            if ignore_tupperbox:
                # Check both the before and after states of the message
                is_before_tupperbox = await self.is_tupperbox_message(before, tupperbox_ids)
                is_after_tupperbox = await self.is_tupperbox_message(after, tupperbox_ids)
                
                if is_before_tupperbox or is_after_tupperbox:
                    self.log.debug(
                        f"Skipping Tupperbox message_edit event - Before:{is_before_tupperbox}, After:{is_after_tupperbox}"
                    )
                    return
                    
            # 3. Check ignore lists (channel, user, role)
            if not await self.should_log_event(before.guild, "message_edit", 
                                              channel=before.channel, 
                                              user=before.author):
                self.log.debug("should_log_event returned False - channel/user/role is ignored.")
                return
                
            # Check if content actually changed
            if before.content == after.content:
                # If content is the same, check if this is just an auto-embed conversion
                # Auto-embeds typically happen when Discord processes links into embeds
                # without the user actually editing the message
                if (len(before.embeds) != len(after.embeds) or
                    before.embeds != after.embeds):
                    # This is likely an auto-embed conversion, skip logging
                    self.log.debug("Skipping auto-embed conversion - content unchanged, only embeds different")
                    return
                # If content and embeds are the same, nothing meaningful changed
                self.log.debug("Skipping message edit - no meaningful changes detected")
                return
                
            # 4. Get the appropriate log channel
            channel = await self.get_log_channel(before.guild, "message_edit")
            if not channel:
                self.log.warning("No log channel set for message_edit.")
                return
                
        except Exception as e:
            self.log.error(f"Error in pre-processing message_edit event: {e}", exc_info=True)
            return
        
        # Process and log the event
        try:
            # Gather comprehensive message metadata
            author = getattr(before, "author", None)
            attachments = [a.url for a in getattr(after, "attachments", [])]
            embeds = getattr(after, "embeds", [])
            channel_name = getattr(before.channel, "name", str(before.channel) if before.channel else "Unknown")
            
            # Additional context for debugging
            self.log.debug(f"Logging message_edit in #{channel_name} by {author}")
            
            # Prepare user identification with link
            user_link = f"[{author}](https://discord.com/users/{author.id})" if author and hasattr(author, "id") else "Unknown"
            
            # Include jump URL if available
            jump_url = getattr(after, "jump_url", None)
            
            # Rich message metadata for comprehensive logging
            metadata = {
                "Author": f"{user_link} ({author.id})" if author and hasattr(author, "id") else "Unknown",
                "Channel": f"#{channel_name}"
            }
            
            # Add creation and edit timestamps if available
            if hasattr(after, "created_at") and after.created_at:
                metadata["Created"] = discord.utils.format_dt(after.created_at, style="F")
            if hasattr(after, "edited_at") and after.edited_at:
                metadata["Edited"] = discord.utils.format_dt(after.edited_at, style="R")
            
            # Create a visually appealing and comprehensive embed
            embed = self.create_embed(
                "message_edit",
                f"✏️ Message edited in {getattr(before.channel, 'mention', str(before.channel))}\n\u200b"
            )
            
            # Add fields for metadata
            for key, value in metadata.items():
                embed.add_field(name=key, value=value, inline=True)
            
            # Add message content comparison (before/after)
            before_text = before.content or 'No content'
            after_text = after.content or 'No content'
            
            # Format content with proper quoting for better readability
            if len(before_text) > 1024:
                before_text = before_text[:1021] + "..."
            if len(after_text) > 1024:
                after_text = after_text[:1021] + "..."
                
            embed.add_field(name="Before", value=f"```\n{before_text}\n```", inline=False)
            embed.add_field(name="After", value=f"```\n{after_text}\n```", inline=False)
            
            # Add jump link to original message
            if jump_url:
                embed.add_field(
                    name="Jump to Message", 
                    value=f"[Click here to view the message]({jump_url})", 
                    inline=False
                )
                
            # Add attachment and embed information
            if attachments:
                attachment_text = "\n".join([f"[Attachment {i+1}]({url})" for i, url in enumerate(attachments)])
                embed.add_field(name="Attachments", value=attachment_text, inline=False)
                
            if embeds:
                embed_info = []
                for i, msg_embed in enumerate(embeds[:3]):  # Show details for first 3 embeds
                    # Get the embed title with proper formatting
                    embed_title = getattr(msg_embed, "title", "*No title*")
                    if embed_title and len(embed_title) > 80:
                        embed_title = embed_title[:77] + "..."
                    
                    # Format the embed details with a divider for better readability
                    embed_details = [f"**Embed {i+1}**: {embed_title}"]
                    embed_details.append("───────────────")  # Divider
                    
                    # Add description with proper truncation and formatting
                    embed_desc = getattr(msg_embed, "description", None)
                    if embed_desc:
                        if len(embed_desc) > 200:  # Increased character limit
                            embed_desc = embed_desc[:197] + "..."
                        embed_details.append(f"**Description**: {embed_desc}")
                    
                    # Add URL if present
                    embed_url = getattr(msg_embed, "url", None)
                    if embed_url:
                        embed_details.append(f"**URL**: [Link]({embed_url})")
                    
                    # Enhanced author display with URL if available
                    embed_author = getattr(msg_embed, "author", None)
                    if embed_author:
                        author_name = getattr(embed_author, "name", None)
                        author_url = getattr(embed_author, "url", None)
                        author_icon = getattr(embed_author, "icon_url", None)
                        
                        if author_name:
                            if author_url:
                                embed_details.append(f"**Author**: [{author_name}]({author_url})")
                            else:
                                embed_details.append(f"**Author**: {author_name}")
                            
                            if author_icon:
                                embed_details.append(f"**Author Icon**: [View]({author_icon})")
                    
                    # Add fields with improved formatting (up to 3)
                    embed_fields = getattr(msg_embed, "fields", [])
                    if embed_fields:
                        embed_details.append("**Fields**:")
                        for j, field in enumerate(embed_fields[:3]):
                            field_name = getattr(field, "name", "Unnamed Field")
                            field_value = getattr(field, "value", "")
                            field_inline = getattr(field, "inline", False)
                            
                            # Format field values with truncation
                            if field_value and len(field_value) > 100:
                                field_value = field_value[:97] + "..."
                            
                            # Show field name and value with inline status
                            inline_status = " (Inline)" if field_inline else ""
                            embed_details.append(f"• **{field_name}**{inline_status}: {field_value}")
                        
                        # Show if there are more fields
                        if len(embed_fields) > 3:
                            embed_details.append(f"*...and {len(embed_fields) - 3} more fields*")
                    
                    # Enhanced media display
                    if getattr(msg_embed, "image", None) and getattr(msg_embed.image, "url", None):
                        embed_details.append(f"**Image**: [View]({msg_embed.image.url})")
                    
                    if getattr(msg_embed, "thumbnail", None) and getattr(msg_embed.thumbnail, "url", None):
                        embed_details.append(f"**Thumbnail**: [View]({msg_embed.thumbnail.url})")
                    
                    # Add timestamp if present
                    if getattr(msg_embed, "timestamp", None):
                        formatted_time = discord.utils.format_dt(msg_embed.timestamp, style="f")
                        embed_details.append(f"**Timestamp**: {formatted_time}")
                    
                    # Footer with enhanced formatting
                    embed_footer = getattr(msg_embed, "footer", None)
                    if embed_footer:
                        footer_text = getattr(embed_footer, "text", None)
                        footer_icon = getattr(embed_footer, "icon_url", None)
                        
                        if footer_text:
                            if len(footer_text) > 100:
                                footer_text = footer_text[:97] + "..."
                            embed_details.append(f"**Footer**: {footer_text}")
                        
                        if footer_icon:
                            embed_details.append(f"**Footer Icon**: [View]({footer_icon})")
                    
                    # Add color with a visual indicator
                    if getattr(msg_embed, "color", None):
                        color_hex = f"#{msg_embed.color.value:06x}"
                        # Add a colored square emoji based on general color
                        if msg_embed.color.value < 0x800000:  # Dark/Red
                            color_indicator = "🟥"
                        elif msg_embed.color.value < 0x808000:  # Orange/Brown
                            color_indicator = "🟧"
                        elif msg_embed.color.value < 0x008000:  # Yellow/Gold
                            color_indicator = "🟨"
                        elif msg_embed.color.value < 0x008080:  # Green
                            color_indicator = "🟩"
                        elif msg_embed.color.value < 0x000080:  # Teal/Cyan
                            color_indicator = "🟦"
                        elif msg_embed.color.value < 0x800080:  # Blue/Indigo
                            color_indicator = "🟦"
                        else:  # Purple/Pink
                            color_indicator = "🟪"
                        
                        embed_details.append(f"**Color**: {color_indicator} {color_hex}")
                    
                    # Join all details together with empty line for readability
                    embed_info.append("\n".join(embed_details))
                
                # Show info about additional embeds
                if len(embeds) > 3:
                    embed_info.append(f"*...and {len(embeds) - 3} more embeds*")
                
                # Add all embed info to the logging embed
                embed.add_field(
                    name=f"Embeds ({len(embeds)})",
                    value="\n".join(embed_info),
                    inline=False
                )
                
            # Include user thumbnail for better visual identification
            if author and hasattr(author, "display_avatar") and author.display_avatar:
                embed.set_thumbnail(url=author.display_avatar.url)
                
            # Set appropriate footer with timestamp
            edit_time = after.edited_at or after.created_at or datetime.datetime.now(datetime.UTC)
            self.set_embed_footer(embed, event_time=edit_time, label="YALC Logger • Message Edit")
            
            # Send the log embed
            await self.safe_send(channel, embed=embed)
            
        except Exception as e:
            self.log.error(f"Failed to log message_edit: {e}", exc_info=True)

    @commands.Cog.listener()
    async def on_bulk_message_delete(self, messages: List[discord.Message]) -> None:
        """
        Log bulk message deletion events with enhanced Tupperbot filtering.
        
        This handler processes bulk message deletions (purges) and generates
        a comprehensive log entry with user statistics and message samples.
        
        Parameters
        ----------
        messages: List[discord.Message]
            The list of deleted messages
        """
        # Skip if no messages were provided
        if not messages:
            self.log.debug("Empty message list for bulk_message_delete.")
            return
            
        # Use the first message to get guild and channel info
        first_msg = messages[0]
        guild = first_msg.guild
        channel = first_msg.channel
        
        if not guild:
            self.log.debug("No guild on bulk message delete.")
            return
            
        # Check if we should log this event
        try:
            settings = await self.config.guild(guild).all()
            
            # Skip if event is disabled
            if not settings["events"].get("message_bulk_delete", False):
                self.log.debug("message_bulk_delete event is disabled.")
                return
                
            # Check if channel is in ignore list
            if channel.id in settings.get("ignored_channels", []):
                self.log.debug(f"Channel {channel.id} is in the ignored channels list.")
                return
                
            # Check if channel category is ignored
            if isinstance(channel, discord.TextChannel) and channel.category:
                if channel.category.id in settings.get("ignored_categories", []):
                    self.log.debug(f"Category {channel.category.id} is in the ignored categories list.")
                    return
                
            # Get the appropriate log channel
            log_channel = await self.get_log_channel(guild, "message_bulk_delete")
            if not log_channel:
                self.log.debug("No log channel configured for message_bulk_delete.")
                return
                
            # Apply enhanced filtering
            filtered_messages = messages
            filtered_out_count = 0
            
            # Filter out Tupperbot messages if configured
            if settings.get("ignore_tupperbox", True):
                tupperbox_ids = settings.get("tupperbox_ids", ["239232811662311425"])
                
                original_count = len(filtered_messages)
                
                # We need to use a loop instead of a list comprehension for async calls
                new_filtered_messages = []
                for msg in filtered_messages:
                    if not await self.is_tupperbox_message(msg, tupperbox_ids):
                        new_filtered_messages.append(msg)
                
                filtered_messages = new_filtered_messages
                filtered_out_count += original_count - len(filtered_messages)
                
            # Filter out webhook messages if configured
            if settings.get("ignore_webhooks", False):
                original_count = len(filtered_messages)
                filtered_messages = [
                    msg for msg in filtered_messages 
                    if not getattr(msg, "webhook_id", None)
                ]
                filtered_out_count += original_count - len(filtered_messages)
                
            # Filter out app messages if configured
            if settings.get("ignore_apps", True):
                original_count = len(filtered_messages)
                filtered_messages = [
                    msg for msg in filtered_messages 
                    if not getattr(msg, "application", None)
                ]
                filtered_out_count += original_count - len(filtered_messages)
            
            # Skip logging if all messages were filtered out
            if len(filtered_messages) == 0:
                self.log.debug(f"All {len(messages)} bulk deleted messages were filtered out.")
                return
            
            # Sort messages by timestamp for chronological order
            filtered_messages.sort(key=lambda m: m.created_at)
            
            # Create a comprehensive log embed
            embed = self.create_embed(
                "message_bulk_delete",
                f"♻️ **{len(filtered_messages)}** messages were bulk deleted in {channel.mention}\n\u200b"
            )
            
            # Add metadata about the deletion
            embed.add_field(
                name="Channel", 
                value=f"{channel.mention} (`{channel.name}`, ID: {channel.id})",
                inline=True
            )
            
            # Add thread info if applicable
            if isinstance(channel, discord.Thread):
                parent_channel = getattr(channel, "parent", None)
                if parent_channel:
                    embed.add_field(
                        name="Parent Channel",
                        value=f"{parent_channel.mention} (`{parent_channel.name}`)",
                        inline=True
                    )
            
            # Add time range info
            oldest_msg = filtered_messages[0]
            newest_msg = filtered_messages[-1]
            
            time_range = (
                f"From {discord.utils.format_dt(oldest_msg.created_at, 'F')} "
                f"to {discord.utils.format_dt(newest_msg.created_at, 'F')}"
            )
            embed.add_field(name="Time Range", value=time_range, inline=False)
            
            # Add message count information with filter details
            message_count_text = f"{len(filtered_messages)} messages deleted"
            if filtered_out_count > 0:
                message_count_text += f" ({filtered_out_count} filtered out)"
                
            embed.add_field(name="Message Count", value=message_count_text, inline=True)
            
            # Add moderation data if available using centralized audit log helper
            audit_entry = None
            try:
                # Look for bulk message delete audit log entries using our centralized helper
                audit_entry = await self._get_audit_log_entry(
                    guild,
                    discord.AuditLogAction.message_bulk_delete,
                    target=channel,
                    timeout_seconds=10
                )
            except Exception as e:
                self.log.debug(f"Could not fetch audit log for bulk message delete: {e}")
                
            if audit_entry:
                embed.add_field(
                    name="Deleted By",
                    value=f"{audit_entry.user.mention} (`{audit_entry.user}`, ID: `{audit_entry.user.id}`)",
                    inline=True
                )
                
                if hasattr(audit_entry, "reason") and audit_entry.reason:
                    embed.add_field(name="Reason", value=audit_entry.reason, inline=True)
            else:
                # If no audit log info available, indicate unknown
                embed.add_field(
                    name="Deleted By",
                    value="Unknown (audit log unavailable)",
                    inline=True
                )
            
            # Add authors summary (who sent the deleted messages)
            authors = {}
            for msg in filtered_messages:
                if msg.author:
                    author_id = msg.author.id
                    if author_id in authors:
                        authors[author_id]["count"] += 1
                    else:
                        authors[author_id] = {
                            "name": str(msg.author),
                            "id": author_id,
                            "count": 1,
                            "mention": msg.author.mention,
                            "avatar": getattr(msg.author, "display_avatar", None)
                        }
            
            if authors:
                # Sort by message count (most active users first)
                sorted_authors = sorted(
                    authors.items(), 
                    key=lambda x: x[1]["count"],
                    reverse=True
                )
                
                authors_text = []
                for author_id, data in sorted_authors[:10]:  # Limit to top 10 authors
                    authors_text.append(
                        f"• {data['mention']} (`{data['name']}`, ID: `{data['id']}`): **{data['count']} message(s)**"
                    )
                    
                if len(sorted_authors) > 10:
                    authors_text.append(f"*...and {len(sorted_authors) - 10} more users*")
                    
                embed.add_field(
                    name="Message Authors", 
                    value="\n".join(authors_text), 
                    inline=False
                )
                
                # Set thumbnail to the user with most messages
                if sorted_authors and settings.get("include_thumbnails", True):
                    top_author = sorted_authors[0][1]
                    if "avatar" in top_author and top_author["avatar"]:
                        embed.set_thumbnail(url=top_author["avatar"].url)
                
            # Add content preview (first few and last few messages)
            preview_count = min(5, len(filtered_messages))
            if preview_count > 0:
                # First messages
                first_msgs = filtered_messages[:preview_count]
                
                preview_text = []
                for msg in first_msgs:
                    author_name = str(msg.author) if msg.author else "Unknown"
                    content = msg.content if msg.content else "[No text content]"
                    if len(content) > 60:
                        content = content[:57] + "..."
                    timestamp = discord.utils.format_dt(msg.created_at, style="R")
                    preview_text.append(f"• **{author_name}** ({timestamp}): {content}")
                    
                embed.add_field(
                    name=f"First {preview_count} Messages" if len(filtered_messages) > preview_count 
                         else "Messages",
                    value="\n".join(preview_text) or "*No preview available*",
                    inline=False
                )
                
                # Last messages (if we have more than 2*preview_count)
                if len(filtered_messages) > preview_count * 2:
                    last_msgs = filtered_messages[-preview_count:]
                    
                    preview_text = []
                    for msg in last_msgs:
                        author_name = str(msg.author) if msg.author else "Unknown"
                        content = msg.content if msg.content else "[No text content]"
                        if len(content) > 60:
                            content = content[:57] + "..."
                        timestamp = discord.utils.format_dt(msg.created_at, style="R")
                        preview_text.append(f"• **{author_name}** ({timestamp}): {content}")
                        
                    embed.add_field(
                        name=f"Last {preview_count} Messages",
                        value="\n".join(preview_text) or "*No preview available*",
                        inline=False
                    )
            
            # Add timestamp for when deletion occurred
            self.set_embed_footer(embed, label="YALC Logger • Bulk Message Delete")
            
            # Send the log entry
            await self.safe_send(log_channel, embed=embed)
            
        except Exception as e:
            self.log.error(f"Error logging bulk message delete: {e}", exc_info=True)
    
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
            # Create enhanced embed with join date information
            embed = discord.Embed(
                title="👋 Member Leave",
                description=f"{member.mention} has left the server.\n\u200b",
                color=discord.Color(0xF39C12),  # Orange color for leave events
                timestamp=datetime.datetime.now(datetime.UTC)
            )
            
            # Add user information
            embed.add_field(
                name="User",
                value=f"{member} ({member.id})",
                inline=True
            )
            
            # Add join date information - this is what was requested
            if member.joined_at:
                join_date_formatted = member.joined_at.strftime('%B %d, %Y at %I:%M %p')
                embed.add_field(
                    name="📅 Originally Joined",
                    value=join_date_formatted,
                    inline=True
                )
                
                # Calculate how long they were in the server
                time_in_server = datetime.datetime.now(datetime.UTC) - member.joined_at
                days = time_in_server.days
                if days > 0:
                    embed.add_field(
                        name="⏱️ Time in Server",
                        value=f"{days} day{'s' if days != 1 else ''}",
                        inline=True
                    )
            
            # Add server information
            embed.add_field(name="🏠 Server", value=member.guild.name, inline=True)
            embed.add_field(name="👥 Members", value=str(member.guild.member_count), inline=True)
            
            # Add user thumbnail if available
            settings = await self.config.guild(member.guild).all()
            if settings.get("include_thumbnails", True) and member.display_avatar:
                embed.set_thumbnail(url=member.display_avatar.url)
            
            # Set footer
            self.set_embed_footer(embed, label="YALC Logger • Member Leave")
            
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
        """Log member update events with audit log integration to show who made changes."""
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
            moderator_info = None
            
            # Check for role changes
            added_roles = [r for r in after.roles if r not in before.roles]
            removed_roles = [r for r in before.roles if r not in after.roles]
            
            # Try to get audit log information for role changes
            if added_roles or removed_roles:
                try:
                    # Look for member role update in audit logs
                    audit_entry = await self._get_audit_log_entry(
                        before.guild,
                        discord.AuditLogAction.member_role_update,
                        target=after,
                        timeout_seconds=10
                    )
                    
                    if audit_entry and audit_entry.user != after:
                        moderator_info = {
                            "moderator": audit_entry.user,
                            "reason": getattr(audit_entry, "reason", None)
                        }
                except Exception as e:
                    self.log.debug(f"Could not fetch audit log for member role update: {e}")
                
                # Add role changes to the changes list
                for role in added_roles:
                    changes.append(f"➕ Added {role.mention}")
                for role in removed_roles:
                    changes.append(f"➖ Removed {role.mention}")
            
            # Check for nickname changes
            if before.nick != after.nick:
                try:
                    # Look for member update in audit logs (covers nickname changes)
                    audit_entry = await self._get_audit_log_entry(
                        before.guild,
                        discord.AuditLogAction.member_update,
                        target=after,
                        timeout_seconds=10
                    )
                    
                    if audit_entry and audit_entry.user != after and not moderator_info:
                        moderator_info = {
                            "moderator": audit_entry.user,
                            "reason": getattr(audit_entry, "reason", None)
                        }
                except Exception as e:
                    self.log.debug(f"Could not fetch audit log for member nickname update: {e}")
                
                changes.append(f"📝 Nickname changed: '{before.nick or before.display_name}' → '{after.nick or after.display_name}'")
            
            # Skip if no changes detected
            if not changes:
                return
            
            # Create the embed with enhanced information
            if moderator_info:
                description = f"👤 {after.mention} ({after.display_name})'s profile was updated by {moderator_info['moderator'].mention}"
            else:
                description = f"👤 {after.mention} ({after.display_name})'s profile was updated"
            
            embed = self.create_embed(
                "member_update",
                description + "\n\u200b"
            )
            
            # Add user information
            embed.add_field(
                name="Member",
                value=f"{after.mention} (`{after}`, ID: `{after.id}`)",
                inline=True
            )
            
            # Add moderator information if available
            if moderator_info:
                embed.add_field(
                    name="Updated By",
                    value=f"{moderator_info['moderator'].mention} (`{moderator_info['moderator']}`, ID: `{moderator_info['moderator'].id}`)",
                    inline=True
                )
                
                # Add reason if provided
                if moderator_info["reason"]:
                    embed.add_field(
                        name="Reason",
                        value=moderator_info["reason"],
                        inline=False
                    )
                    
                # Indicate if it was self-updated vs moderated
                if moderator_info["moderator"] == after:
                    embed.add_field(
                        name="Update Type",
                        value="Self-updated",
                        inline=True
                    )
                else:
                    embed.add_field(
                        name="Update Type",
                        value="Moderated update",
                        inline=True
                    )
            else:
                # If no audit log info available, indicate unknown
                embed.add_field(
                    name="Updated By",
                    value="Unknown (audit log unavailable or self-updated)",
                    inline=True
                )
            
            # Add the changes
            embed.add_field(
                name="Changes",
                value="\n".join(changes),
                inline=False
            )
            
            # Add user thumbnail for better visual identification
            settings = await self.config.guild(before.guild).all()
            if settings.get("include_thumbnails", True) and after.display_avatar:
                embed.set_thumbnail(url=after.display_avatar.url)
            
            # Set footer
            event_time = datetime.datetime.now(datetime.UTC)
            self.set_embed_footer(embed, event_time=event_time, label="YALC Logger • Member Update")
            
            # Send the log message
            await self.safe_send(channel, embed=embed)
            
        except Exception as e:
            self.log.error(f"Failed to log member_update: {e}")

    @commands.Cog.listener()
    async def on_guild_channel_create(self, channel: discord.abc.GuildChannel) -> None:
        """Log channel creation events with audit log integration to show who created channels."""
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
            # Try to get audit log information about who created the channel
            creator_info = None
            try:
                # Look for channel create audit log entries
                audit_entry = await self._get_audit_log_entry(
                    channel.guild,
                    discord.AuditLogAction.channel_create,
                    target=channel,
                    timeout_seconds=10
                )
                
                if audit_entry:
                    creator_info = {
                        "creator": audit_entry.user,
                        "reason": getattr(audit_entry, "reason", None)
                    }
            except Exception as e:
                self.log.debug(f"Could not fetch audit log for channel creation: {e}")
            
            # Create the embed with enhanced information
            if creator_info:
                description = f"📝 Channel created: {getattr(channel, 'mention', str(channel))} by {creator_info['creator'].mention}"
            else:
                description = f"📝 Channel created: {getattr(channel, 'mention', str(channel))}"
            
            description += "\n\u200b"
            
            embed = self.create_embed(
                "channel_create",
                description
            )
            
            # Add channel information
            embed.add_field(
                name="Channel",
                value=f"{getattr(channel, 'mention', str(channel))} (`{channel.name}`, ID: `{channel.id}`)",
                inline=True
            )
            
            embed.add_field(
                name="Type",
                value=type(channel).__name__,
                inline=True
            )
            
            # Add creator information if available
            if creator_info:
                embed.add_field(
                    name="Created By",
                    value=f"{creator_info['creator'].mention} (`{creator_info['creator']}`, ID: `{creator_info['creator'].id}`)",
                    inline=True
                )
                
                # Add reason if provided
                if creator_info["reason"]:
                    embed.add_field(
                        name="Reason",
                        value=creator_info["reason"],
                        inline=False
                    )
            else:
                # If no audit log info available, indicate unknown
                embed.add_field(
                    name="Created By",
                    value="Unknown (audit log unavailable)",
                    inline=True
                )
            
            # Add category info if applicable
            if hasattr(channel, 'category') and channel.category:
                embed.add_field(
                    name="Category",
                    value=f"{channel.category.name} (`{channel.category.id}`)",
                    inline=True
                )
            
            # Add channel-specific information
            if isinstance(channel, discord.TextChannel):
                if channel.topic:
                    embed.add_field(
                        name="Topic",
                        value=channel.topic[:1024] if len(channel.topic) <= 1024 else channel.topic[:1021] + "...",
                        inline=False
                    )
                embed.add_field(
                    name="NSFW",
                    value="Yes" if channel.nsfw else "No",
                    inline=True
                )
                if channel.slowmode_delay > 0:
                    embed.add_field(
                        name="Slowmode",
                        value=f"{channel.slowmode_delay} seconds",
                        inline=True
                    )
            elif isinstance(channel, discord.VoiceChannel):
                embed.add_field(
                    name="Bitrate",
                    value=f"{channel.bitrate} bps",
                    inline=True
                )
                if channel.user_limit > 0:
                    embed.add_field(
                        name="User Limit",
                        value=str(channel.user_limit),
                        inline=True
                    )
            
            # Add creator thumbnail for better visual identification
            settings = await self.config.guild(channel.guild).all()
            if creator_info and settings.get("include_thumbnails", True) and hasattr(creator_info["creator"], "display_avatar"):
                embed.set_thumbnail(url=creator_info["creator"].display_avatar.url)
            
            # Set footer
            event_time = datetime.datetime.now(datetime.UTC)
            self.set_embed_footer(embed, event_time=event_time, label="YALC Logger • Channel Created")
            
            await self.safe_send(log_channel, embed=embed)
        except Exception as e:
            self.log.error(f"Failed to log channel_create: {e}")

    @commands.Cog.listener()
    async def on_guild_channel_delete(self, channel: discord.abc.GuildChannel) -> None:
        """Log channel deletion events with audit log integration to show who deleted channels."""
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
            # Try to get audit log information about who deleted the channel
            deleter_info = None
            try:
                # Look for channel delete audit log entries
                audit_entry = await self._get_audit_log_entry(
                    channel.guild,
                    discord.AuditLogAction.channel_delete,
                    target=channel,
                    timeout_seconds=10
                )
                
                if audit_entry:
                    deleter_info = {
                        "deleter": audit_entry.user,
                        "reason": getattr(audit_entry, "reason", None)
                    }
            except Exception as e:
                self.log.debug(f"Could not fetch audit log for channel deletion: {e}")
            
            # Create the embed with enhanced information
            if deleter_info:
                description = f"🗑️ Channel deleted: **{channel.name}** by {deleter_info['deleter'].mention}"
            else:
                description = f"🗑️ Channel deleted: **{channel.name}**"
            
            description += "\n\u200b"
            
            embed = self.create_embed(
                "channel_delete",
                description
            )
            
            # Add channel information
            embed.add_field(
                name="Channel",
                value=f"**{channel.name}** (ID: `{channel.id}`)",
                inline=True
            )
            
            embed.add_field(
                name="Type",
                value=type(channel).__name__,
                inline=True
            )
            
            # Add deleter information if available
            if deleter_info:
                embed.add_field(
                    name="Deleted By",
                    value=f"{deleter_info['deleter'].mention} (`{deleter_info['deleter']}`, ID: `{deleter_info['deleter'].id}`)",
                    inline=True
                )
                
                # Add reason if provided
                if deleter_info["reason"]:
                    embed.add_field(
                        name="Reason",
                        value=deleter_info["reason"],
                        inline=False
                    )
            else:
                # If no audit log info available, indicate unknown
                embed.add_field(
                    name="Deleted By",
                    value="Unknown (audit log unavailable)",
                    inline=True
                )
            
            # Add category info if applicable
            if hasattr(channel, 'category') and channel.category:
                embed.add_field(
                    name="Category",
                    value=f"{channel.category.name} (`{channel.category.id}`)",
                    inline=True
                )
            
            # Add channel-specific information that was preserved before deletion
            if isinstance(channel, discord.TextChannel):
                if hasattr(channel, 'topic') and channel.topic:
                    embed.add_field(
                        name="Topic",
                        value=channel.topic[:1024] if len(channel.topic) <= 1024 else channel.topic[:1021] + "...",
                        inline=False
                    )
                if hasattr(channel, 'nsfw'):
                    embed.add_field(
                        name="NSFW",
                        value="Yes" if channel.nsfw else "No",
                        inline=True
                    )
                if hasattr(channel, 'slowmode_delay') and channel.slowmode_delay > 0:
                    embed.add_field(
                        name="Slowmode",
                        value=f"{channel.slowmode_delay} seconds",
                        inline=True
                    )
            elif isinstance(channel, discord.VoiceChannel):
                if hasattr(channel, 'bitrate'):
                    embed.add_field(
                        name="Bitrate",
                        value=f"{channel.bitrate} bps",
                        inline=True
                    )
                if hasattr(channel, 'user_limit') and channel.user_limit > 0:
                    embed.add_field(
                        name="User Limit",
                        value=str(channel.user_limit),
                        inline=True
                    )
            
            # Add deleter thumbnail for better visual identification
            settings = await self.config.guild(channel.guild).all()
            if deleter_info and settings.get("include_thumbnails", True) and hasattr(deleter_info["deleter"], "display_avatar"):
                embed.set_thumbnail(url=deleter_info["deleter"].display_avatar.url)
            
            # Set footer
            event_time = datetime.datetime.now(datetime.UTC)
            self.set_embed_footer(embed, event_time=event_time, label="YALC Logger • Channel Deleted")
            
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

            # Try to get audit log information about who updated the channel
            updater_info = None
            try:
                audit_entry = await self._get_audit_log_entry(
                    before.guild,
                    discord.AuditLogAction.channel_update,
                    target=after,
                    timeout_seconds=10
                )
                if audit_entry:
                    updater_info = {
                        "updater": audit_entry.user,
                        "reason": getattr(audit_entry, "reason", None)
                    }
            except Exception as e:
                self.log.debug(f"Could not fetch audit log for channel update: {e}")

            # Build description with updater if available
            if updater_info:
                description = f"🔄 Channel updated: {getattr(after, 'mention', str(after))} by {updater_info['updater'].mention}\n\u200b"
            else:
                description = f"🔄 Channel updated: {getattr(after, 'mention', str(after))}\n\u200b"

            embed = self.create_embed(
                "channel_update",
                description,
                changes="\n".join(changes),
                channel_name=after.name
            )

            # Add updater info if available
            if updater_info:
                embed.add_field(
                    name="Updated By",
                    value=f"{updater_info['updater'].mention} (`{updater_info['updater']}`, ID: `{updater_info['updater'].id}`)",
                    inline=True
                )
                if updater_info["reason"]:
                    embed.add_field(
                        name="Reason",
                        value=updater_info["reason"],
                        inline=False
                    )
            else:
                embed.add_field(
                    name="Updated By",
                    value="Unknown (audit log unavailable or self-updated)",
                    inline=True
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
            # Try to get audit log information about who created the thread
            creator_info = None
            try:
                audit_entry = await self._get_audit_log_entry(
                    thread.guild,
                    discord.AuditLogAction.thread_create,
                    target=thread,
                    timeout_seconds=10
                )
                if audit_entry:
                    creator_info = {
                        "creator": audit_entry.user,
                        "reason": getattr(audit_entry, "reason", None)
                    }
            except Exception as e:
                self.log.debug(f"Could not fetch audit log for thread creation: {e}")

            if creator_info:
                description = f"🧵 Thread created in {getattr(thread.parent, 'mention', None)} by {creator_info['creator'].mention}\n\u200b"
            else:
                description = f"🧵 Thread created in {getattr(thread.parent, 'mention', None)}\n\u200b"

            embed = self.create_embed(
                "thread_create",
                description,
                thread=thread.mention,
                name=thread.name,
                creator=f"{thread.owner} ({thread.owner_id})" if thread.owner else f"ID: {thread.owner_id}",
                type=str(thread.type),
                slowmode=f"{thread.slowmode_delay}s" if thread.slowmode_delay else "None"
            )

            if creator_info:
                embed.add_field(
                    name="Created By",
                    value=f"{creator_info['creator'].mention} (`{creator_info['creator']}`, ID: `{creator_info['creator'].id}`)",
                    inline=True
                )
                if creator_info["reason"]:
                    embed.add_field(
                        name="Reason",
                        value=creator_info["reason"],
                        inline=False
                    )
            else:
                embed.add_field(
                    name="Created By",
                    value="Unknown (audit log unavailable)",
                    inline=True
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
            # Try to get audit log information about who deleted the thread
            deleter_info = None
            try:
                audit_entry = await self._get_audit_log_entry(
                    thread.guild,
                    discord.AuditLogAction.thread_delete,
                    target=thread,
                    timeout_seconds=10
                )
                if audit_entry:
                    deleter_info = {
                        "deleter": audit_entry.user,
                        "reason": getattr(audit_entry, "reason", None)
                    }
            except Exception as e:
                self.log.debug(f"Could not fetch audit log for thread deletion: {e}")

            if deleter_info:
                description = f"🗑️ Thread deleted from {getattr(thread.parent, 'mention', None)} by {deleter_info['deleter'].mention}\n\u200b"
            else:
                description = f"🗑️ Thread deleted from {getattr(thread.parent, 'mention', None)}\n\u200b"

            embed = self.create_embed(
                "thread_delete",
                description,
                name=thread.name,
                archived=thread.archived,
                locked=thread.locked,
                type=str(thread.type)
            )

            if deleter_info:
                embed.add_field(
                    name="Deleted By",
                    value=f"{deleter_info['deleter'].mention} (`{deleter_info['deleter']}`, ID: `{deleter_info['deleter'].id}`)",
                    inline=True
                )
                if deleter_info["reason"]:
                    embed.add_field(
                        name="Reason",
                        value=deleter_info["reason"],
                        inline=False
                    )
            else:
                embed.add_field(
                    name="Deleted By",
                    value="Unknown (audit log unavailable)",
                    inline=True
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
        """Log role creation events with audit log integration to show who created roles."""
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
            # Try to get audit log information about who created the role
            creator_info = None
            try:
                # Look for role create audit log entries
                audit_entry = await self._get_audit_log_entry(
                    role.guild,
                    discord.AuditLogAction.role_create,
                    target=role,
                    timeout_seconds=10
                )
                
                if audit_entry:
                    creator_info = {
                        "creator": audit_entry.user,
                        "reason": getattr(audit_entry, "reason", None)
                    }
            except Exception as e:
                self.log.debug(f"Could not fetch audit log for role creation: {e}")
            
            # Create the embed with enhanced information
            if creator_info:
                description = f"✨ Role created: {role.mention} by {creator_info['creator'].mention}"
            else:
                description = f"✨ Role created: {role.mention}"
            
            description += "\n\u200b"
            
            embed = self.create_embed(
                "role_create",
                description
            )
            
            # Add role information
            embed.add_field(
                name="Role",
                value=f"{role.mention} (`{role.name}`, ID: `{role.id}`)",
                inline=True
            )
            
            # Add role color if it's not default
            if role.color != discord.Color.default():
                color_hex = f"#{role.color.value:06x}"
                # Add a colored square emoji based on general color
                if role.color.value < 0x800000:  # Dark/Red
                    color_indicator = "🟥"
                elif role.color.value < 0x808000:  # Orange/Brown
                    color_indicator = "🟧"
                elif role.color.value < 0x008000:  # Yellow/Gold
                    color_indicator = "🟨"
                elif role.color.value < 0x008080:  # Green
                    color_indicator = "🟩"
                elif role.color.value < 0x000080:  # Teal/Cyan
                    color_indicator = "🟦"
                elif role.color.value < 0x800080:  # Blue/Indigo
                    color_indicator = "🟦"
                else:  # Purple/Pink
                    color_indicator = "🟪"
                
                embed.add_field(
                    name="Color",
                    value=f"{color_indicator} {color_hex}",
                    inline=True
                )
            
            # Add role position
            embed.add_field(
                name="Position",
                value=str(role.position),
                inline=True
            )
            
            # Add creator information if available
            if creator_info:
                embed.add_field(
                    name="Created By",
                    value=f"{creator_info['creator'].mention} (`{creator_info['creator']}`, ID: `{creator_info['creator'].id}`)",
                    inline=True
                )
                
                # Add reason if provided
                if creator_info["reason"]:
                    embed.add_field(
                        name="Reason",
                        value=creator_info["reason"],
                        inline=False
                    )
            else:
                # If no audit log info available, indicate unknown
                embed.add_field(
                    name="Created By",
                    value="Unknown (audit log unavailable)",
                    inline=True
                )
            
            # Add role properties
            role_properties = []
            if role.mentionable:
                role_properties.append("📢 Mentionable")
            if role.hoist:
                role_properties.append("📌 Hoisted (displays separately)")
            if role.managed:
                role_properties.append("🤖 Managed by integration")
            if role.premium_subscriber:
                role_properties.append("💎 Premium subscriber role")
            
            if role_properties:
                embed.add_field(
                    name="Properties",
                    value="\n".join(role_properties),
                    inline=False
                )
            
            # Add permission summary if role has elevated permissions
            dangerous_perms = []
            if role.permissions.administrator:
                dangerous_perms.append("🔧 Administrator")
            if role.permissions.manage_guild:
                dangerous_perms.append("⚙️ Manage Server")
            if role.permissions.manage_roles:
                dangerous_perms.append("👥 Manage Roles")
            if role.permissions.manage_channels:
                dangerous_perms.append("📝 Manage Channels")
            if role.permissions.kick_members:
                dangerous_perms.append("👢 Kick Members")
            if role.permissions.ban_members:
                dangerous_perms.append("🔨 Ban Members")
            if role.permissions.moderate_members:
                dangerous_perms.append("⏰ Timeout Members")
            
            if dangerous_perms:
                embed.add_field(
                    name="Key Permissions",
                    value="\n".join(dangerous_perms),
                    inline=False
                )
            
            # Add creator thumbnail for better visual identification
            settings = await self.config.guild(role.guild).all()
            if creator_info and settings.get("include_thumbnails", True) and hasattr(creator_info["creator"], "display_avatar"):
                embed.set_thumbnail(url=creator_info["creator"].display_avatar.url)
            
            # Set footer
            event_time = datetime.datetime.now(datetime.UTC)
            self.set_embed_footer(embed, event_time=event_time, label="YALC Logger • Role Created")
            
            await self.safe_send(channel, embed=embed)
        except Exception as e:
            self.log.error(f"Failed to log role_create: {e}")

    @commands.Cog.listener()
    async def on_role_delete(self, role: discord.Role) -> None:
        """Log role deletion events with audit log integration to show who deleted roles."""
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
            # Try to get audit log information about who deleted the role
            deleter_info = None
            try:
                # Look for role delete audit log entries
                audit_entry = await self._get_audit_log_entry(
                    role.guild,
                    discord.AuditLogAction.role_delete,
                    target=role,
                    timeout_seconds=10
                )
                
                if audit_entry:
                    deleter_info = {
                        "deleter": audit_entry.user,
                        "reason": getattr(audit_entry, "reason", None)
                    }
            except Exception as e:
                self.log.debug(f"Could not fetch audit log for role deletion: {e}")
            
            # Create the embed with enhanced information
            if deleter_info:
                description = f"🗑️ Role deleted: **{role.name}** by {deleter_info['deleter'].mention}"
            else:
                description = f"🗑️ Role deleted: **{role.name}**"
            
            description += "\n\u200b"
            
            embed = self.create_embed(
                "role_delete",
                description
            )
            
            # Add role information
            embed.add_field(
                name="Role",
                value=f"**{role.name}** (ID: `{role.id}`)",
                inline=True
            )
            
            # Add role color if it wasn't default
            if role.color != discord.Color.default():
                color_hex = f"#{role.color.value:06x}"
                # Add a colored square emoji based on general color
                if role.color.value < 0x800000:  # Dark/Red
                    color_indicator = "🟥"
                elif role.color.value < 0x808000:  # Orange/Brown
                    color_indicator = "🟧"
                elif role.color.value < 0x008000:  # Yellow/Gold
                    color_indicator = "🟨"
                elif role.color.value < 0x008080:  # Green
                    color_indicator = "🟩"
                elif role.color.value < 0x000080:  # Teal/Cyan
                    color_indicator = "🟦"
                elif role.color.value < 0x800080:  # Blue/Indigo
                    color_indicator = "🟦"
                else:  # Purple/Pink
                    color_indicator = "🟪"
                
                embed.add_field(
                    name="Color",
                    value=f"{color_indicator} {color_hex}",
                    inline=True
                )
            
            # Add role position
            embed.add_field(
                name="Position",
                value=str(role.position),
                inline=True
            )
            
            # Add deleter information if available
            if deleter_info:
                embed.add_field(
                    name="Deleted By",
                    value=f"{deleter_info['deleter'].mention} (`{deleter_info['deleter']}`, ID: `{deleter_info['deleter'].id}`)",
                    inline=True
                )
                
                # Add reason if provided
                if deleter_info["reason"]:
                    embed.add_field(
                        name="Reason",
                        value=deleter_info["reason"],
                        inline=False
                    )
            else:
                # If no audit log info available, indicate unknown
                embed.add_field(
                    name="Deleted By",
                    value="Unknown (audit log unavailable)",
                    inline=True
                )
            
            # Add role properties that were preserved before deletion
            role_properties = []
            if role.mentionable:
                role_properties.append("📢 Was mentionable")
            if role.hoist:
                role_properties.append("📌 Was hoisted (displayed separately)")
            if role.managed:
                role_properties.append("🤖 Was managed by integration")
            if role.premium_subscriber:
                role_properties.append("💎 Was premium subscriber role")
            
            if role_properties:
                embed.add_field(
                    name="Properties",
                    value="\n".join(role_properties),
                    inline=False
                )
            
            # Add permission summary if role had elevated permissions
            dangerous_perms = []
            if role.permissions.administrator:
                dangerous_perms.append("🔧 Had Administrator")
            if role.permissions.manage_guild:
                dangerous_perms.append("⚙️ Had Manage Server")
            if role.permissions.manage_roles:
                dangerous_perms.append("👥 Had Manage Roles")
            if role.permissions.manage_channels:
                dangerous_perms.append("📝 Had Manage Channels")
            if role.permissions.kick_members:
                dangerous_perms.append("👢 Had Kick Members")
            if role.permissions.ban_members:
                dangerous_perms.append("🔨 Had Ban Members")
            if role.permissions.moderate_members:
                dangerous_perms.append("⏰ Had Timeout Members")
            
            if dangerous_perms:
                embed.add_field(
                    name="Key Permissions",
                    value="\n".join(dangerous_perms),
                    inline=False
                )
            
            # Add deleter thumbnail for better visual identification
            settings = await self.config.guild(role.guild).all()
            if deleter_info and settings.get("include_thumbnails", True) and hasattr(deleter_info["deleter"], "display_avatar"):
                embed.set_thumbnail(url=deleter_info["deleter"].display_avatar.url)
            
            # Set footer
            event_time = datetime.datetime.now(datetime.UTC)
            self.set_embed_footer(embed, event_time=event_time, label="YALC Logger • Role Deleted")
            
            await self.safe_send(channel, embed=embed)
        except Exception as e:
            self.log.error(f"Failed to log role_delete: {e}")

    @commands.Cog.listener()
    async def on_role_update(self, before: discord.Role, after: discord.Role) -> None:
        """Log role update events with real-time audit log attribution."""
        self.log.debug("Listener triggered: on_role_update")
        self.log.debug(f"Role before: name={before.name}, color={before.color}, permissions={before.permissions}")
        self.log.debug(f"Role after:  name={after.name}, color={after.color}, permissions={after.permissions}")
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
            # Detect changes
            changes = []
            color_changed = before.color != after.color
            position_changed = before.position != after.position
            
            if before.name != after.name:
                self.log.debug(f"Role name changed: {before.name} -> {after.name}")
                changes.append(f"**Name:** `{before.name}` → `{after.name}`")
            if before.permissions != after.permissions:
                self.log.debug(f"Role permissions changed: {before.permissions} -> {after.permissions}")
                changes.append("**Permissions:** Changed")
            if position_changed:
                self.log.debug(f"Role position changed: {before.position} -> {after.position}")
                changes.append(f"**Position:** `{before.position}` → `{after.position}`")
            if before.mentionable != after.mentionable:
                changes.append(f"**Mentionable:** `{before.mentionable}` → `{after.mentionable}`")
            if before.hoist != after.hoist:
                changes.append(f"**Hoisted:** `{before.hoist}` → `{after.hoist}`")
            
            if color_changed:
                self.log.debug(f"Role color changed: {before.color} -> {after.color}")
            
            # Check if there are any meaningful changes
            if not changes and not color_changed:
                self.log.debug("No meaningful changes detected.")
                return
            
            # Try to get real-time audit log data first, then fall back to API query
            user_who_changed = None
            audit_reason = None
            
            # Check recent audit entries first (real-time)
            if after.id in self.recent_audit_entries:
                audit_data = self.recent_audit_entries[after.id]
                # Check if the audit entry is recent (within 5 seconds)
                if time.time() - audit_data['timestamp'] <= 5:
                    audit_entry = audit_data['entry']
                    user_who_changed = audit_entry.user
                    audit_reason = getattr(audit_entry, 'reason', None)
                    self.log.debug(f"Using real-time audit data for role {after.id}")
                    
                    # Clean up used entry
                    del self.recent_audit_entries[after.id]
            
            # Fall back to API query if no real-time data
            if not user_who_changed:
                try:
                    audit_entry = await self._get_audit_log_entry(
                        before.guild,
                        discord.AuditLogAction.role_update,
                        target=after,
                        timeout_seconds=10
                    )
                    if audit_entry:
                        user_who_changed = audit_entry.user
                        audit_reason = getattr(audit_entry, 'reason', None)
                        self.log.debug(f"Using API audit data for role {after.id}")
                except Exception as e:
                    self.log.debug(f"Could not fetch audit log for role update: {e}")
            
            # Create enhanced embed with attribution
            if user_who_changed:
                description = f"🔄 Role updated: {after.mention} by {user_who_changed.mention}"
            else:
                description = f"🔄 Role updated: {after.mention}"
            
            description += "\n\u200b"
            
            embed = self.create_embed("role_update", description)
            
            # Add role information
            embed.add_field(
                name="Role",
                value=f"{after.mention} (`{after.name}`, ID: `{after.id}`)",
                inline=True
            )
            
            # Add who changed it
            if user_who_changed:
                embed.add_field(
                    name="Changed By",
                    value=f"{user_who_changed.mention} (`{user_who_changed.id}`)",
                    inline=True
                )
                
                # Add reason if provided
                if audit_reason:
                    embed.add_field(
                        name="Reason",
                        value=audit_reason,
                        inline=False
                    )
            else:
                embed.add_field(
                    name="Changed By",
                    value="Unknown (audit log unavailable)",
                    inline=True
                )
            
            # Add timestamp
            embed.add_field(
                name="When",
                value=f"<t:{int(time.time())}:R>",
                inline=True
            )
            
            # Add changes
            if changes:
                embed.add_field(
                    name="Changes",
                    value="\n".join(changes),
                    inline=False
                )
            
            # Add color change if applicable
            if color_changed:
                before_hex = f"#{before.color.value:06x}"
                after_hex = f"#{after.color.value:06x}"
                before_emoji = "🟪" if before.color.value >= 0x800080 else (
                    "🟦" if before.color.value >= 0x000080 else (
                    "🟩" if before.color.value >= 0x008000 else (
                    "🟨" if before.color.value >= 0x008080 else (
                    "🟧" if before.color.value >= 0x808000 else (
                    "🟥")))))
                after_emoji = "🟪" if after.color.value >= 0x800080 else (
                    "🟦" if after.color.value >= 0x000080 else (
                    "🟩" if after.color.value >= 0x008000 else (
                    "🟨" if after.color.value >= 0x008080 else (
                    "🟧" if after.color.value >= 0x808000 else (
                    "🟥")))))
                embed.add_field(
                    name="Color Change",
                    value=f"{before_emoji} {before_hex} → {after_emoji} {after_hex}",
                    inline=True
                )
            
            # Add user thumbnail for better visual identification
            settings = await self.config.guild(before.guild).all()
            if user_who_changed and settings.get("include_thumbnails", True) and hasattr(user_who_changed, "display_avatar"):
                embed.set_thumbnail(url=user_who_changed.display_avatar.url)
            
            # Set footer
            event_time = datetime.datetime.now(datetime.UTC)
            self.set_embed_footer(embed, event_time=event_time, label="YALC Logger • Role Update")
            
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

            # Try to get audit log information about who updated the guild
            updater_info = None
            try:
                audit_entry = await self._get_audit_log_entry(
                    before,
                    discord.AuditLogAction.guild_update,
                    timeout_seconds=10
                )
                if audit_entry:
                    updater_info = {
                        "updater": audit_entry.user,
                        "reason": getattr(audit_entry, "reason", None)
                    }
            except Exception as e:
                self.log.debug(f"Could not fetch audit log for guild update: {e}")

            # Build description with updater if available
            if updater_info:
                description = f"⚙️ Server updated by {updater_info['updater'].mention}"
            else:
                description = "⚙️ Server updated"

            embed = self.create_embed(
                "guild_update",
                description,
                changes="\n".join(changes)
            )

            # Add updater info if available
            if updater_info:
                embed.add_field(
                    name="Updated By",
                    value=f"{updater_info['updater'].mention} (`{updater_info['updater']}`, ID: `{updater_info['updater'].id}`)",
                    inline=True
                )
                if updater_info["reason"]:
                    embed.add_field(
                        name="Reason",
                        value=updater_info["reason"],
                        inline=False
                    )
            else:
                embed.add_field(
                    name="Updated By",
                    value="Unknown (audit log unavailable or self-updated)",
                    inline=True
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
    async def on_command_error(self, ctx: commands.Context, error: commands.CommandError) -> None:
        """
        Log command error events.
        
        Parameters
        ----------
        ctx: commands.Context
            The context of the command
        error: commands.CommandError
            The error that occurred
        """
        # Skip if not in a guild
        if not ctx.guild:
            return
            
        try:
            # Get settings
            settings = await self.config.guild(ctx.guild).all()
            
            # Skip if event is disabled
            if not settings["events"].get("command_error", False):
                return
                
            # Skip if in ignored channel or category
            if not await self.should_log_event(ctx.guild, "command_error", 
                                             channel=ctx.channel, user=ctx.author):
                return
                
            # Get the log channel
            log_channel = await self.get_log_channel(ctx.guild, "command_error")
            if not log_channel:
                return
                
            # Create the log embed
            command_name = ctx.command.qualified_name if ctx.command else "Unknown command"
            
            # Create embed description
            description = f"⚠️ Error occurred while executing command `{command_name}`"
            
            # Create embed with proper metadata
            embed = self.create_embed(
                "command_error",
                description
            )
            
            # Add user info
            embed.add_field(
                name="User",
                value=f"{ctx.author.mention} (`{ctx.author}`, ID: `{ctx.author.id}`)",
                inline=True
            )
            
            # Add command info
            embed.add_field(
                name="Command",
                value=f"`{ctx.message.content[:1000]}`" if len(ctx.message.content) <= 1000 
                      else f"`{ctx.message.content[:997]}...`",
                inline=False
            )
            
            # Add channel info
            embed.add_field(
                name="Channel",
                value=f"{ctx.channel.mention} (`{ctx.channel.name}`)",
                inline=True
            )
            
            # Add error info
            embed.add_field(
                name="Error Type",
                value=f"`{type(error).__name__}`",
                inline=True
            )
            
            # Format error message
            error_message = str(error)
            if len(error_message) > 1024:
                error_message = error_message[:1021] + "..."
                
            embed.add_field(
                name="Error Message",
                value=f"```\n{error_message}\n```",
                inline=False
            )
            
            # Add timestamp
            embed.add_field(
                name="Timestamp",
                value=discord.utils.format_dt(datetime.datetime.now(datetime.UTC), style="F"),
                inline=True
            )
            
            # Set thumbnail if appropriate
            if settings.get("include_thumbnails", True) and hasattr(ctx.author, "display_avatar"):
                embed.set_thumbnail(url=ctx.author.display_avatar.url)
                
            # Set footer
            self.set_embed_footer(embed, label="YALC Logger • Command Error")
            
            # Send the log
            await self.safe_send(log_channel, embed=embed)
            
        except Exception as e:
            self.log.error(f"Error logging command_error: {e}", exc_info=True)

    @commands.Cog.listener()
    async def on_guild_scheduled_event_create(self, event: discord.ScheduledEvent) -> None:
        """
        Log guild scheduled event creation.
        
        Parameters
        ----------
        event: discord.ScheduledEvent
            The scheduled event that was created
        """
        self.log.debug("Listener triggered: on_guild_scheduled_event_create")
        
        # Skip if event has no guild
        guild = event.guild
        if not guild:
            return
            
        try:
            # Get settings
            settings = await self.config.guild(guild).all()
            
            # Skip if event is disabled
            if not settings["events"].get("guild_scheduled_event_create", False):
                return
                
            # Skip if we should ignore based on channel, user, or roles
            if not await self.should_log_event(guild, "guild_scheduled_event_create"):
                return
                
            # Get the log channel
            log_channel = await self.get_log_channel(guild, "guild_scheduled_event_create")
            if not log_channel:
                return
                
            # Get creator if available
            creator = None
            try:
                if event.creator_id:
                    creator = guild.get_member(event.creator_id) or await self.bot.fetch_user(event.creator_id)
            except Exception:
                pass
                
            # Create the log embed
            description = f"📅 Server event created: **{event.name}**"
            
            embed = self.create_embed(
                "guild_scheduled_event_create",
                description
            )
            
            # Add event details
            embed.add_field(name="Name", value=event.name, inline=True)
            
            if event.description:
                embed.add_field(
                    name="Description", 
                    value=event.description if len(event.description) <= 1024 
                          else f"{event.description[:1021]}...",
                    inline=False
                )
                
            # Add location info
            if hasattr(event, "location") and event.location:
                embed.add_field(name="Location", value=event.location, inline=True)
            elif hasattr(event, "channel") and event.channel:
                embed.add_field(name="Channel", value=event.channel.mention, inline=True)
                
            # Add timing info
            if hasattr(event, "start_time") and event.start_time:
                embed.add_field(
                    name="Start Time",
                    value=discord.utils.format_dt(event.start_time, "F"),
                    inline=True
                )
                
            if hasattr(event, "end_time") and event.end_time:
                embed.add_field(
                    name="End Time",
                    value=discord.utils.format_dt(event.end_time, "F"),
                    inline=True
                )
                
            # Add creator info
            if creator:
                embed.add_field(
                    name="Created By",
                    value=f"{creator.mention} (`{creator}`, ID: `{creator.id}`)",
                    inline=True
                )
                
                # Set thumbnail to creator's avatar
                if settings.get("include_thumbnails", True) and hasattr(creator, "display_avatar"):
                    embed.set_thumbnail(url=creator.display_avatar.url)
            
            # Add event URL
            if hasattr(event, "url") and event.url:
                embed.add_field(
                    name="Event Link",
                    value=f"[Click to view]({event.url})",
                    inline=False
                )
                
            # Set event image if available
            if hasattr(event, "image") and event.image:
                embed.set_image(url=event.image.url)
                
            # Set footer
            self.set_embed_footer(embed, label="YALC Logger • Event Created")
            
            # Send the log
            await self.safe_send(log_channel, embed=embed)
            
        except Exception as e:
            self.log.error(f"Error logging guild_scheduled_event_create: {e}", exc_info=True)
            
    @commands.Cog.listener()
    async def on_guild_scheduled_event_update(self, before: discord.ScheduledEvent, after: discord.ScheduledEvent) -> None:
        """
        Log guild scheduled event updates.
        
        Parameters
        ----------
        before: discord.ScheduledEvent
            The scheduled event before the update
        after: discord.ScheduledEvent
            The scheduled event after the update
        """
        self.log.debug("Listener triggered: on_guild_scheduled_event_update")
        
        # Skip if event has no guild
        guild = after.guild
        if not guild:
            return
            
        try:
            # Get settings
            settings = await self.config.guild(guild).all()
            
            # Skip if event is disabled
            if not settings["events"].get("guild_scheduled_event_update", False):
                return
                
            # Skip if we should ignore based on channel, user, or roles
            if not await self.should_log_event(guild, "guild_scheduled_event_update"):
                return
                
            # Get the log channel
            log_channel = await self.get_log_channel(guild, "guild_scheduled_event_update")
            if not log_channel:
                return
                
            # Collect all the changes
            changes = []
            
            if before.name != after.name:
                changes.append(f"**Name:** `{before.name}` → `{after.name}`")
                
            if before.description != after.description:
                before_desc = before.description or "None"
                after_desc = after.description or "None"
                if len(before_desc) > 100:
                    before_desc = before_desc[:97] + "..."
                if len(after_desc) > 100:
                    after_desc = after_desc[:97] + "..."
                changes.append(f"**Description:** Changed")
                
            if hasattr(before, "location") and hasattr(after, "location") and before.location != after.location:
                changes.append(f"**Location:** `{before.location or 'None'}` → `{after.location or 'None'}`")
                
            if hasattr(before, "channel_id") and hasattr(after, "channel_id") and before.channel_id != after.channel_id:
                changes.append(f"**Channel:** <#{before.channel_id or 'None'}> → <#{after.channel_id or 'None'}>")
                
            if before.start_time != after.start_time:
                before_time = discord.utils.format_dt(before.start_time, "F") if before.start_time else "None"
                after_time = discord.utils.format_dt(after.start_time, "F") if after.start_time else "None"
                changes.append(f"**Start Time:** {before_time} → {after_time}")
                
            if hasattr(before, "end_time") and hasattr(after, "end_time") and before.end_time != after.end_time:
                before_time = discord.utils.format_dt(before.end_time, "F") if before.end_time else "None"
                after_time = discord.utils.format_dt(after.end_time, "F") if after.end_time else "None"
                changes.append(f"**End Time:** {before_time} → {after_time}")
                
            if hasattr(before, "status") and hasattr(after, "status") and before.status != after.status:
                changes.append(f"**Status:** `{before.status}` → `{after.status}`")
                
            # Skip if no changes (shouldn't happen, but just in case)
            if not changes:
                return
                
            # Create the log embed
            description = f"🔄 Server event updated: **{after.name}**"
            
            embed = self.create_embed(
                "guild_scheduled_event_update",
                description
            )
            
            # Add changes
            embed.add_field(
                name="Changes",
                value="\n".join(changes),
                inline=False
            )
            
            # Add event details
            embed.add_field(name="Event ID", value=f"`{after.id}`", inline=True)
            
            # Add event URL
            if hasattr(after, "url") and after.url:
                embed.add_field(
                    name="Event Link",
                    value=f"[Click to view]({after.url})",
                    inline=False
                )
                
            # Set event image if available
            if hasattr(after, "image") and after.image:
                embed.set_image(url=after.image.url)
                
            # Set footer
            self.set_embed_footer(embed, label="YALC Logger • Event Updated")
            
            # Send the log
            await self.safe_send(log_channel, embed=embed)
            
        except Exception as e:
            self.log.error(f"Error logging guild_scheduled_event_update: {e}", exc_info=True)
            
    @commands.Cog.listener()
    async def on_guild_scheduled_event_delete(self, event: discord.ScheduledEvent) -> None:
        """
        Log guild scheduled event deletion.
        
        Parameters
        ----------
        event: discord.ScheduledEvent
            The scheduled event that was deleted
        """
        self.log.debug("Listener triggered: on_guild_scheduled_event_delete")
        
        # Skip if event has no guild
        guild = event.guild
        if not guild:
            return
            
        try:
            # Get settings
            settings = await self.config.guild(guild).all()
            
            # Skip if event is disabled
            if not settings["events"].get("guild_scheduled_event_delete", False):
                return
                
            # Skip if we should ignore based on channel, user, or roles
            if not await self.should_log_event(guild, "guild_scheduled_event_delete"):
                return
                
            # Get the log channel
            log_channel = await self.get_log_channel(guild, "guild_scheduled_event_delete")
            if not log_channel:
                return
                
            # Get creator if available
            creator = None
            try:
                if event.creator_id:
                    creator = guild.get_member(event.creator_id) or await self.bot.fetch_user(event.creator_id)
            except Exception:
                pass
                
            # Create the log embed
            description = f"🗑️ Server event deleted: **{event.name}**"
            
            embed = self.create_embed(
                "guild_scheduled_event_delete",
                description
            )
            
            # Add event details
            embed.add_field(name="Name", value=event.name, inline=True)
            embed.add_field(name="Event ID", value=f"`{event.id}`", inline=True)
            
            if event.description:
                embed.add_field(
                    name="Description", 
                    value=event.description if len(event.description) <= 1024 
                          else f"{event.description[:1021]}...",
                    inline=False
                )
                
            # Add location info
            if hasattr(event, "location") and event.location:
                embed.add_field(name="Location", value=event.location, inline=True)
            elif hasattr(event, "channel") and event.channel:
                embed.add_field(name="Channel", value=event.channel.mention, inline=True)
                
            # Add timing info
            if hasattr(event, "start_time") and event.start_time:
                embed.add_field(
                    name="Scheduled Start",
                    value=discord.utils.format_dt(event.start_time, "F"),
                    inline=True
                )
                
            # Add creator info
            if creator:
                embed.add_field(
                    name="Created By",
                    value=f"{creator.mention} (`{creator}`, ID: `{creator.id}`)",
                    inline=True
                )
                
                # Set thumbnail to creator's avatar
                if settings.get("include_thumbnails", True) and hasattr(creator, "display_avatar"):
                    embed.set_thumbnail(url=creator.display_avatar.url)
            
            # Set event image if available
            if hasattr(event, "image") and event.image:
                embed.set_image(url=event.image.url)
                
            # Set footer
            self.set_embed_footer(embed, label="YALC Logger • Event Deleted")
            
            # Send the log
            await self.safe_send(log_channel, embed=embed)
            
        except Exception as e:
            self.log.error(f"Error logging guild_scheduled_event_delete: {e}", exc_info=True)

    @commands.group(name="yalc", aliases=["logger"], invoke_without_command=True)
    @commands.guild_only()
    async def yalc_group(self, ctx: commands.Context):
        """
        Yet Another Logging Cog - Main commands.
        
        This command group provides access to all YALC logging configuration commands.
        Run a subcommand to perform a specific action.
        """
        await ctx.send_help(ctx.command)

    @yalc_group.command(name="enable")
    @commands.admin_or_permissions(manage_guild=True)
    async def yalc_enable(self, ctx: commands.Context, event_type: Optional[str] = None):
        """
        Enable logging for a specific event type.
        
        If no event type is specified, lists all available event types.
        
        Parameters
        ----------
        event_type: str, optional
            The event type to enable logging for
        """
        if event_type is None:
            # List all available event types
            embed = discord.Embed(
                title="YALC Available Event Types",
                description="Here are all the event types you can enable:",
                color=discord.Color.blue()
            )
            
            # Group events by category
            categories = {
                "Message Events": [k for k in self.event_descriptions.keys() if k.startswith("message_")],
                "Member Events": [k for k in self.event_descriptions.keys() if k.startswith("member_")],
                "Channel Events": [k for k in self.event_descriptions.keys() if k.startswith(("channel_", "thread_", "forum_"))],
                "Role Events": [k for k in self.event_descriptions.keys() if k.startswith("role_")],
                "Guild Events": [k for k in self.event_descriptions.keys() if k.startswith(("guild_", "emoji_"))],
                "Other Events": [k for k in self.event_descriptions.keys() if not any(k.startswith(p) for p in 
                                 ["message_", "member_", "channel_", "thread_", "forum_", "role_", "guild_", "emoji_"])]
            }
            
            # Add fields for each category
            for category, events in categories.items():
                if events:
                    event_list = "\n".join([f"{self.event_descriptions[e][0]} `{e}` - {self.event_descriptions[e][1]}" 
                                          for e in events])
                    embed.add_field(name=category, value=event_list, inline=False)
            
            embed.set_footer(text=f"Use {ctx.prefix}yalc enable <event_type> to enable a specific event type")
            await ctx.send(embed=embed)
            return
            
        # Check if the event type exists
        if event_type not in self.event_descriptions:
            await ctx.send(f"❌ Unknown event type: `{event_type}`. Use `{ctx.prefix}yalc enable` to see all available event types.")
            return
            
        # Enable the event
        async with self.config.guild(ctx.guild).events() as events:
            events[event_type] = True
            
        # Get description for confirmation message
        emoji, description = self.event_descriptions[event_type]
        await ctx.send(f"✅ {emoji} Enabled logging for **{description}** (`{event_type}`).")

    @yalc_group.command(name="disable")
    @commands.admin_or_permissions(manage_guild=True)
    async def yalc_disable(self, ctx: commands.Context, event_type: str):
        """
        Disable logging for a specific event type.
        
        Parameters
        ----------
        event_type: str
            The event type to disable logging for
        """
        # Check if the event type exists
        if event_type not in self.event_descriptions:
            await ctx.send(f"❌ Unknown event type: `{event_type}`. Use `{ctx.prefix}yalc enable` to see all available event types.")
            return
            
        # Disable the event
        async with self.config.guild(ctx.guild).events() as events:
            events[event_type] = False
            
        # Get description for confirmation message
        emoji, description = self.event_descriptions[event_type]
        await ctx.send(f"✅ {emoji} Disabled logging for **{description}** (`{event_type}`).")

    @yalc_group.command(name="setchannel")
    @commands.admin_or_permissions(manage_guild=True)
    async def yalc_setchannel(self, ctx: commands.Context, event_type: str, channel: discord.TextChannel = None):
        """
        Set the logging channel for a specific event type.
        
        Parameters
        ----------
        event_type: str
            The event type to set the channel for
        channel: discord.TextChannel, optional
            The channel to log the events to. If not specified, uses the current channel.
        """
        # Use current channel if none specified
        if channel is None:
            channel = ctx.channel
            
        # Check if the event type exists
        if event_type not in self.event_descriptions and event_type != "all":
            await ctx.send(f"❌ Unknown event type: `{event_type}`. Use `{ctx.prefix}yalc enable` to see all available event types.")
            return
            
        # Set the channel
        if event_type == "all":
            # Set for all event types
            async with self.config.guild(ctx.guild).event_channels() as event_channels:
                for et in self.event_descriptions.keys():
                    event_channels[et] = channel.id
            await ctx.send(f"✅ Set {channel.mention} as the logging channel for **all** event types.")
        else:
            # Set for a specific event type
            async with self.config.guild(ctx.guild).event_channels() as event_channels:
                event_channels[event_type] = channel.id
                
            # Get description for confirmation message
            emoji, description = self.event_descriptions[event_type]
            await ctx.send(f"✅ {emoji} Set {channel.mention} as the logging channel for **{description}** (`{event_type}`).")

    @yalc_group.command(name="settings")
    @commands.guild_only()
    async def yalc_settings(self, ctx: commands.Context):
        """View the current YALC settings for this server, paginated if too long."""
        settings = await self.config.guild(ctx.guild).all()

        embeds = []

        # Page 1: Enabled Events
        enabled_events = [f"{self.event_descriptions[event][0]} `{event}` - {self.event_descriptions[event][1]}"
                          for event, enabled in settings["events"].items() if enabled]
        embed_events = discord.Embed(
            title="YALC Logger Settings",
            description="Enabled Events",
            color=discord.Color.blue()
        )
        if enabled_events:
            for i in range(0, len(enabled_events), 15):
                embed_events.add_field(
                    name=f"📋 Enabled Events {i+1}-{min(i+15, len(enabled_events))}",
                    value="\n".join(enabled_events[i:i+15]),
                    inline=False
                )
        else:
            embed_events.add_field(
                name="📋 Enabled Events",
                value="No events enabled",
                inline=False
            )
        embeds.append(embed_events)

        # Page 2: Event Channels
        channel_mappings = []
        for event, channel_id in settings["event_channels"].items():
            if channel_id:
                channel = ctx.guild.get_channel(channel_id)
                if channel and event in self.event_descriptions:
                    channel_mappings.append(f"{self.event_descriptions[event][0]} `{event}` → {channel.mention}")
        embed_channels = discord.Embed(
            title="YALC Logger Settings",
            description="Event Channels",
            color=discord.Color.blue()
        )
        if channel_mappings:
            for i in range(0, len(channel_mappings), 10):
                embed_channels.add_field(
                    name=f"📢 Event Channels {i+1}-{min(i+10, len(channel_mappings))}",
                    value="\n".join(channel_mappings[i:i+10]),
                    inline=False
                )
        else:
            embed_channels.add_field(
                name="📢 Event Channels",
                value="No channels configured",
                inline=False
            )
        embeds.append(embed_channels)

        # Page 3: Ignore Settings
        ignore_settings = []
        if settings.get("ignore_bots", False):
            ignore_settings.append("🤖 Ignoring bot messages")
        if settings.get("ignore_webhooks", False):
            ignore_settings.append("🔗 Ignoring webhook messages")
        if settings.get("ignore_tupperbox", True):
            ignore_settings.append("👥 Ignoring Tupperbox/proxy messages")
        ignored_roles = settings.get("ignored_roles", [])
        if ignored_roles:
            role_names = [f"<@&{role_id}>" for role_id in ignored_roles[:3]]
            ignore_settings.append(f"🚫 Ignored Roles: {', '.join(role_names)}" +
                                  (f" *and {len(ignored_roles) - 3} more*" if len(ignored_roles) > 3 else ""))
        ignored_users = settings.get("ignored_users", [])
        if ignored_users:
            ignore_settings.append(f"🚫 Ignored Users: {len(ignored_users)}")
        ignored_channels = settings.get("ignored_channels", [])
        if ignored_channels:
            channel_names = [f"<#{channel_id}>" for channel_id in ignored_channels[:3]]
            ignore_settings.append(f"🚫 Ignored Channels: {', '.join(channel_names)}" +
                                  (f" *and {len(ignored_channels) - 3} more*" if len(ignored_channels) > 3 else ""))
        embed_ignore = discord.Embed(
            title="YALC Logger Settings",
            description="Ignore Settings",
            color=discord.Color.blue()
        )
        if ignore_settings:
            embed_ignore.add_field(
                name="⚙️ Ignore Settings",
                value="\n".join(ignore_settings),
                inline=False
            )
        else:
            embed_ignore.add_field(
                name="⚙️ Ignore Settings",
                value="No ignore settings configured",
                inline=False
            )
        embeds.append(embed_ignore)

        # Add footer to all embeds
        for embed in embeds:
            embed.set_footer(text=f"YALC • Server ID: {ctx.guild.id}")

        # Send paginated embeds (simple implementation: send all embeds in order)
        for embed in embeds:
            await ctx.send(embed=embed)

    @yalc_group.group(name="ignore", invoke_without_command=True)
    @commands.admin_or_permissions(manage_guild=True)
    async def yalc_ignore(self, ctx: commands.Context):
        """
        Ignore a user, channel, role, or category from logging.
        
        Use subcommands to specify what type of entity to ignore.
        """
        await ctx.send_help(ctx.command)

    @yalc_ignore.command(name="user")
    async def yalc_ignore_user(self, ctx: commands.Context, user: discord.Member):
        """
        Ignore a user from logging events.
        
        Parameters
        ----------
        user: discord.Member
            The user to ignore
        """
        async with self.config.guild(ctx.guild).ignored_users() as ignored_users:
            if user.id in ignored_users:
                await ctx.send(f"❌ User {user.mention} is already being ignored.")
                return
                
            ignored_users.append(user.id)
            
        await ctx.send(f"✅ Now ignoring events from user {user.mention}.")

    @yalc_ignore.command(name="channel")
    async def yalc_ignore_channel(self, ctx: commands.Context, channel: discord.TextChannel):
        """
        Ignore a channel from logging events.
        
        Parameters
        ----------
        channel: discord.TextChannel
            The channel to ignore
        """
        async with self.config.guild(ctx.guild).ignored_channels() as ignored_channels:
            if channel.id in ignored_channels:
                await ctx.send(f"❌ Channel {channel.mention} is already being ignored.")
                return
                
            ignored_channels.append(channel.id)
            
        await ctx.send(f"✅ Now ignoring events from channel {channel.mention}.")

    @yalc_ignore.command(name="role")
    async def yalc_ignore_role(self, ctx: commands.Context, role: discord.Role):
        """
        Ignore users with a specific role from logging events.
        
        Parameters
        ----------
        role: discord.Role
            The role to ignore
        """
        async with self.config.guild(ctx.guild).ignored_roles() as ignored_roles:
            if role.id in ignored_roles:
                await ctx.send(f"❌ Role {role.mention} is already being ignored.")
                return
                
            ignored_roles.append(role.id)
            
        await ctx.send(f"✅ Now ignoring events from users with the role {role.mention}.")

    @yalc_ignore.command(name="category")
    async def yalc_ignore_category(self, ctx: commands.Context, category: discord.CategoryChannel):
        """
        Ignore an entire category from logging events.
        
        Parameters
        ----------
        category: discord.CategoryChannel
            The category to ignore
        """
        async with self.config.guild(ctx.guild).ignored_categories() as ignored_categories:
            if category.id in ignored_categories:
                await ctx.send(f"❌ Category '{category.name}' is already being ignored.")
                return
                
            ignored_categories.append(category.id)
            
        await ctx.send(f"✅ Now ignoring events from all channels in the '{category.name}' category.")

    @yalc_group.group(name="unignore", invoke_without_command=True)
    @commands.admin_or_permissions(manage_guild=True)
    async def yalc_unignore(self, ctx: commands.Context):
        """
        Unignore a previously ignored user, channel, role, or category.
        
        Use subcommands to specify what type of entity to unignore.
        """
        await ctx.send_help(ctx.command)

    @yalc_unignore.command(name="user")
    async def yalc_unignore_user(self, ctx: commands.Context, user: discord.Member):
        """
        Unignore a previously ignored user.
        
        Parameters
        ----------
        user: discord.Member
            The user to stop ignoring
        """
        async with self.config.guild(ctx.guild).ignored_users() as ignored_users:
            if user.id not in ignored_users:
                await ctx.send(f"❌ User {user.mention} is not being ignored.")
                return
                
            ignored_users.remove(user.id)
            
        await ctx.send(f"✅ No longer ignoring events from user {user.mention}.")

    @yalc_unignore.command(name="channel")
    async def yalc_unignore_channel(self, ctx: commands.Context, channel: discord.TextChannel):
        """
        Unignore a previously ignored channel.
        
        Parameters
        ----------
        channel: discord.TextChannel
            The channel to stop ignoring
        """
        async with self.config.guild(ctx.guild).ignored_channels() as ignored_channels:
            if channel.id not in ignored_channels:
                await ctx.send(f"❌ Channel {channel.mention} is not being ignored.")
                return
                
            ignored_channels.remove(channel.id)
            
        await ctx.send(f"✅ No longer ignoring events from channel {channel.mention}.")

    @yalc_unignore.command(name="role")
    async def yalc_unignore_role(self, ctx: commands.Context, role: discord.Role):
        """
        Unignore a previously ignored role.
        
        Parameters
        ----------
        role: discord.Role
            The role to stop ignoring
        """
        async with self.config.guild(ctx.guild).ignored_roles() as ignored_roles:
            if role.id not in ignored_roles:
                await ctx.send(f"❌ Role {role.mention} is not being ignored.")
                return
                
            ignored_roles.remove(role.id)
            
        await ctx.send(f"✅ No longer ignoring events from users with the role {role.mention}.")

    @yalc_unignore.command(name="category")
    async def yalc_unignore_category(self, ctx: commands.Context, category: discord.CategoryChannel):
        """
        Unignore a previously ignored category.
        
        Parameters
        ----------
        category: discord.CategoryChannel
            The category to stop ignoring
        """
        async with self.config.guild(ctx.guild).ignored_categories() as ignored_categories:
            if category.id not in ignored_categories:
                await ctx.send(f"❌ Category '{category.name}' is not being ignored.")
                return
                
            ignored_categories.remove(category.id)
            
        await ctx.send(f"✅ No longer ignoring events from channels in the '{category.name}' category.")

    @yalc_group.command(name="bulk_enable")
    @commands.admin_or_permissions(manage_guild=True)
    async def yalc_bulk_enable(self, ctx: commands.Context, category: str = None):
        """
        Enable multiple events at once by category.
        
        Parameters
        ----------
        category: str, optional
            Category to enable: 'message', 'member', 'channel', 'role', 'guild', 'all'
        """
        if category is None:
            await ctx.send("❌ Please specify a category: `message`, `member`, `channel`, `role`, `guild`, or `all`")
            return
            
        category = category.lower()
        
        # Define event categories
        categories = {
            "message": [k for k in self.event_descriptions.keys() if k.startswith("message_")],
            "member": [k for k in self.event_descriptions.keys() if k.startswith("member_")],
            "channel": [k for k in self.event_descriptions.keys() if k.startswith(("channel_", "thread_", "forum_"))],
            "role": [k for k in self.event_descriptions.keys() if k.startswith("role_")],
            "guild": [k for k in self.event_descriptions.keys() if k.startswith(("guild_", "emoji_", "sticker_"))],
            "all": list(self.event_descriptions.keys())
        }
        
        if category not in categories:
            await ctx.send(f"❌ Unknown category: `{category}`. Available categories: {', '.join(categories.keys())}")
            return
            
        events_to_enable = categories[category]
        
        # Enable all events in the category
        async with self.config.guild(ctx.guild).events() as events:
            for event_type in events_to_enable:
                events[event_type] = True
                
        await ctx.send(f"✅ Enabled {len(events_to_enable)} events in the **{category}** category.")

    @yalc_group.command(name="bulk_disable")
    @commands.admin_or_permissions(manage_guild=True)
    async def yalc_bulk_disable(self, ctx: commands.Context, category: str = None):
        """
        Disable multiple events at once by category.
        
        Parameters
        ----------
        category: str, optional
            Category to disable: 'message', 'member', 'channel', 'role', 'guild', 'all'
        """
        if category is None:
            await ctx.send("❌ Please specify a category: `message`, `member`, `channel`, `role`, `guild`, or `all`")
            return
            
        category = category.lower()
        
        # Define event categories
        categories = {
            "message": [k for k in self.event_descriptions.keys() if k.startswith("message_")],
            "member": [k for k in self.event_descriptions.keys() if k.startswith("member_")],
            "channel": [k for k in self.event_descriptions.keys() if k.startswith(("channel_", "thread_", "forum_"))],
            "role": [k for k in self.event_descriptions.keys() if k.startswith("role_")],
            "guild": [k for k in self.event_descriptions.keys() if k.startswith(("guild_", "emoji_", "sticker_"))],
            "all": list(self.event_descriptions.keys())
        }
        
        if category not in categories:
            await ctx.send(f"❌ Unknown category: `{category}`. Available categories: {', '.join(categories.keys())}")
            return
            
        events_to_disable = categories[category]
        
        # Disable all events in the category
        async with self.config.guild(ctx.guild).events() as events:
            for event_type in events_to_disable:
                events[event_type] = False
                
        await ctx.send(f"✅ Disabled {len(events_to_disable)} events in the **{category}** category.")

    @yalc_group.command(name="reset")
    @commands.admin_or_permissions(manage_guild=True)
    async def yalc_reset(self, ctx: commands.Context, confirm: str = None):
        """
        Reset all YALC settings to defaults.
        
        Parameters
        ----------
        confirm: str, optional
            Must be "CONFIRM" to proceed with reset
        """
        if confirm != "CONFIRM":
            embed = discord.Embed(
                title="⚠️ Reset YALC Configuration",
                description="This will reset **ALL** YALC settings to their default values.",
                color=discord.Color.orange()
            )
            embed.add_field(
                name="What will be reset:",
                value="• All event logging settings\n"
                      "• All channel configurations\n"
                      "• All ignore lists\n"
                      "• All advanced settings",
                inline=False
            )
            embed.add_field(
                name="To confirm:",
                value=f"Run `{ctx.prefix}yalc reset CONFIRM`",
                inline=False
            )
            await ctx.send(embed=embed)
            return
            
        try:
            await self.config.guild(ctx.guild).clear()
            await ctx.send("✅ All YALC settings have been reset to defaults.")
        except Exception as e:
            await ctx.send(f"❌ Error resetting configuration: {e}")

    @yalc_group.command(name="validate")
    @commands.admin_or_permissions(manage_guild=True)
    async def yalc_validate(self, ctx: commands.Context):
        """Validate the current YALC configuration and report any issues."""
        try:
            settings = await self.config.guild(ctx.guild).all()
            issues = []
            warnings = []
            
            # Check for enabled events without channels
            enabled_events = [event for event, enabled in settings["events"].items() if enabled]
            for event in enabled_events:
                channel_id = settings["event_channels"].get(event)
                if not channel_id:
                    warnings.append(f"Event `{event}` is enabled but has no log channel configured")
                else:
                    channel = ctx.guild.get_channel(channel_id)
                    if not channel:
                        issues.append(f"Event `{event}` is configured to log to channel ID {channel_id} but the channel doesn't exist")
            
            # Check for configured channels without enabled events
            configured_channels = {event: channel_id for event, channel_id in settings["event_channels"].items() if channel_id}
            for event, channel_id in configured_channels.items():
                if not settings["events"].get(event, False):
                    warnings.append(f"Event `{event}` has a log channel configured but is not enabled")
            
            # Check for invalid ignored users/roles/channels
            for user_id in settings.get("ignored_users", []):
                user = ctx.guild.get_member(user_id)
                username_info = None
                if not user:
                    # Try to fetch user from API as fallback
                    try:
                        fetched_user = await self.bot.fetch_user(user_id)
                        if fetched_user:
                            username_info = f"{fetched_user} (ID: {user_id})"
                        else:
                            username_info = f"ID: {user_id}"
                    except Exception:
                        username_info = f"ID: {user_id}"
                    warnings.append(f"Ignored user {username_info} not found in server")
                else:
                    username_info = f"{user} (ID: {user_id})"
                    warnings.append(f"Ignored user {username_info} not found in server")
            
            for role_id in settings.get("ignored_roles", []):
                role = ctx.guild.get_role(role_id)
                if not role:
                    warnings.append(f"Ignored role ID {role_id} not found in server")
            
            for channel_id in settings.get("ignored_channels", []):
                channel = ctx.guild.get_channel(channel_id)
                if not channel:
                    warnings.append(f"Ignored channel ID {channel_id} not found in server")
            
            # Create validation report
            embed = discord.Embed(
                title="🔍 YALC Configuration Validation",
                color=discord.Color.green() if not issues else discord.Color.red()
            )
            
            if not issues and not warnings:
                embed.description = "✅ Configuration is valid with no issues found!"
            else:
                embed.description = f"Found {len(issues)} issues and {len(warnings)} warnings"
            
            if issues:
                embed.add_field(
                    name="❌ Issues (require attention)",
                    value="\n".join(f"• {issue}" for issue in issues[:10]) +
                          (f"\n• ...and {len(issues) - 10} more" if len(issues) > 10 else ""),
                    inline=False
                )
            
            if warnings:
                embed.add_field(
                    name="⚠️ Warnings (recommended fixes)",
                    value="\n".join(f"• {warning}" for warning in warnings[:10]) +
                          (f"\n• ...and {len(warnings) - 10} more" if len(warnings) > 10 else ""),
                    inline=False
                )
            
            # Add summary stats
            embed.add_field(
                name="📊 Summary",
                value=f"• Enabled events: {len(enabled_events)}\n"
                      f"• Configured channels: {len(configured_channels)}\n"
                      f"• Ignored users: {len(settings.get('ignored_users', []))}\n"
                      f"• Ignored roles: {len(settings.get('ignored_roles', []))}\n"
                      f"• Ignored channels: {len(settings.get('ignored_channels', []))}",
                inline=False
            )
            
            await ctx.send(embed=embed)
            
        except Exception as e:
            await ctx.send(f"❌ Error validating configuration: {e}")

    @yalc_group.command(name="setup")
    @commands.admin_or_permissions(manage_guild=True)
    async def yalc_setup(self, ctx: commands.Context, confirm: str = None):
        """
        Full YALC setup - creates logging channels and category automatically.
        
        Parameters
        ----------
        confirm: str, optional
            Must be "CONFIRM" to proceed with setup
        """
        if confirm != "CONFIRM":
            embed = discord.Embed(
                title="🏗️ YALC Full Setup",
                description="This will create a complete logging infrastructure for your server.",
                color=discord.Color.blue()
            )
            embed.add_field(
                name="What will be created:",
                value="• **YALC Logs** category\n"
                      "• **#yalc-messages** - Message events (edits, deletions)\n"
                      "• **#yalc-members** - Member events (joins, leaves, bans)\n"
                      "• **#yalc-channels** - Channel/role events\n"
                      "• **#yalc-moderation** - Moderation events\n"
                      "• **#yalc-general** - Other server events",
                inline=False
            )
            embed.add_field(
                name="Events to be enabled:",
                value="• Message deletions, edits, bulk deletions\n"
                      "• Member joins, leaves, bans, unbans\n"
                      "• Channel and role management\n"
                      "• Guild events and moderation",
                inline=False
            )
            embed.add_field(
                name="To confirm:",
                value=f"Run `{ctx.prefix}yalc setup CONFIRM`",
                inline=False
            )
            await ctx.send(embed=embed)
            return
            
        try:
            # Create the YALC Logs category
            category = await ctx.guild.create_category_channel(
                "YALC Logs",
                overwrites={
                    ctx.guild.default_role: discord.PermissionOverwrite(
                        read_messages=False,
                        send_messages=False
                    ),
                    ctx.guild.me: discord.PermissionOverwrite(
                        read_messages=True,
                        send_messages=True,
                        manage_messages=True
                    )
                },
                reason="YALC logging setup"
            )
            
            # Create logging channels
            channels = {}
            
            # Messages channel
            channels["messages"] = await ctx.guild.create_text_channel(
                "yalc-messages",
                category=category,
                topic="YALC: Message events (edits, deletions, bulk deletions)",
                reason="YALC logging setup"
            )
            
            # Members channel
            channels["members"] = await ctx.guild.create_text_channel(
                "yalc-members",
                category=category,
                topic="YALC: Member events (joins, leaves, bans, role changes)",
                reason="YALC logging setup"
            )
            
            # Channels/Roles channel
            channels["channels"] = await ctx.guild.create_text_channel(
                "yalc-channels",
                category=category,
                topic="YALC: Channel and role management events",
                reason="YALC logging setup"
            )
            
            # Moderation channel
            channels["moderation"] = await ctx.guild.create_text_channel(
                "yalc-moderation",
                category=category,
                topic="YALC: Moderation events (bans, kicks, timeouts)",
                reason="YALC logging setup"
            )
            
            # General events channel
            channels["general"] = await ctx.guild.create_text_channel(
                "yalc-general",
                category=category,
                topic="YALC: Server events (guild updates, integrations, etc.)",
                reason="YALC logging setup"
            )
            
            # Configure event mappings
            event_mappings = {
                # Message events -> messages channel
                "message_delete": channels["messages"].id,
                "message_edit": channels["messages"].id,
                "message_bulk_delete": channels["messages"].id,
                "message_pin": channels["messages"].id,
                "message_unpin": channels["messages"].id,
                
                # Member events -> members channel
                "member_join": channels["members"].id,
                "member_leave": channels["members"].id,
                "member_update": channels["members"].id,
                
                # Moderation events -> moderation channel
                "member_ban": channels["moderation"].id,
                "member_unban": channels["moderation"].id,
                "member_kick": channels["moderation"].id,
                "member_timeout": channels["moderation"].id,
                
                # Channel/Role events -> channels channel
                "channel_create": channels["channels"].id,
                "channel_delete": channels["channels"].id,
                "channel_update": channels["channels"].id,
                "thread_create": channels["channels"].id,
                "thread_delete": channels["channels"].id,
                "thread_update": channels["channels"].id,
                "thread_member_join": channels["channels"].id,
                "thread_member_leave": channels["channels"].id,
                "role_create": channels["channels"].id,
                "role_delete": channels["channels"].id,
                "role_update": channels["channels"].id,
                
                # Guild events -> general channel
                "guild_update": channels["general"].id,
                "emoji_update": channels["general"].id,
                "sticker_update": channels["general"].id,
                "invite_create": channels["general"].id,
                "invite_delete": channels["general"].id,
                "guild_scheduled_event_create": channels["general"].id,
                "guild_scheduled_event_update": channels["general"].id,
                "guild_scheduled_event_delete": channels["general"].id,
                "command_error": channels["general"].id,
            }
            
            # Apply configuration
            async with self.config.guild(ctx.guild).events() as events:
                async with self.config.guild(ctx.guild).event_channels() as event_channels:
                    for event_type, channel_id in event_mappings.items():
                        events[event_type] = True
                        event_channels[event_type] = channel_id
            
            # Set up default ignore settings
            await self.config.guild(ctx.guild).ignore_tupperbox.set(True)
            await self.config.guild(ctx.guild).ignore_apps.set(True)
            await self.config.guild(ctx.guild).include_thumbnails.set(True)
            await self.config.guild(ctx.guild).detect_proxy_deletes.set(True)
            
            # Send success message
            embed = discord.Embed(
                title="✅ YALC Setup Complete!",
                description=f"Successfully created logging infrastructure for {ctx.guild.name}",
                color=discord.Color.green()
            )
            
            embed.add_field(
                name="📁 Created Category",
                value=f"**{category.name}** - {category.mention}",
                inline=False
            )
            
            embed.add_field(
                name="📢 Created Channels",
                value=f"• {channels['messages'].mention} - Message events\n"
                      f"• {channels['members'].mention} - Member events\n"
                      f"• {channels['channels'].mention} - Channel/Role events\n"
                      f"• {channels['moderation'].mention} - Moderation events\n"
                      f"• {channels['general'].mention} - Server events",
                inline=False
            )
            
            embed.add_field(
                name="⚙️ Configuration",
                value=f"• **{len(event_mappings)}** events enabled\n"
                      "• Ignoring Tupperbox/proxy messages\n"
                      "• Ignoring application messages\n"
                      "• Including user thumbnails\n"
                      "• Detecting proxy deletions",
                inline=False
            )
            
            embed.add_field(
                name="🎯 Next Steps",
                value=f"• Use `{ctx.prefix}yalc settings` to view configuration\n"
                      f"• Use `{ctx.prefix}yalc enable/disable` to adjust events\n"
                      "• Use the web dashboard for advanced configuration\n"
                      f"• Use `{ctx.prefix}yalc validate` to check for issues",
                inline=False
            )
            
            await ctx.send(embed=embed)
            
        except discord.Forbidden:
            await ctx.send("❌ I don't have permission to create channels and categories. Please ensure I have `Manage Channels` permission.")
        except Exception as e:
            await ctx.send(f"❌ Error during setup: {e}")

    @yalc_group.command(name="dashboard")
    @commands.admin_or_permissions(manage_guild=True)
    async def yalc_dashboard(self, ctx: commands.Context, action: str = "status"):
        """
        Check or manage dashboard integration status.
        
        Parameters
        ----------
        action: str
            Action to perform: 'status' (default) or 'register'
        """
        if action == "status":
            # Check dashboard integration status
            dashboard_cog = self.bot.get_cog("Dashboard")
            
            embed = discord.Embed(
                title="🪃 YALC Dashboard Integration Status",
                color=discord.Color.blue()
            )
            
            if not dashboard_cog:
                embed.add_field(
                    name="❌ Dashboard Cog",
                    value="Dashboard cog is not loaded",
                    inline=False
                )
            else:
                embed.add_field(
                    name="✅ Dashboard Cog",
                    value="Dashboard cog is loaded",
                    inline=True
                )
                
                if hasattr(dashboard_cog, "rpc"):
                    embed.add_field(
                        name="✅ Dashboard RPC",
                        value="RPC interface is available",
                        inline=True
                    )
                    
                    if hasattr(dashboard_cog.rpc, "third_parties_handler"):
                        embed.add_field(
                            name="✅ Third Party Handler",
                            value="Third party handler is available",
                            inline=True
                        )
                        
                        # Check if YALC is registered
                        try:
                            third_parties = getattr(dashboard_cog.rpc.third_parties_handler, 'third_parties', [])
                            yalc_registered = any(getattr(tp, 'name', None) == 'YALC' for tp in third_parties)
                            
                            if yalc_registered:
                                embed.add_field(
                                    name="✅ YALC Registration",
                                    value="YALC is registered as a third party",
                                    inline=False
                                )
                            else:
                                embed.add_field(
                                    name="❌ YALC Registration",
                                    value="YALC is NOT registered as a third party",
                                    inline=False
                                )
                                
                            embed.add_field(
                                name="📊 Registered Third Parties",
                                value=f"Total: {len(third_parties)}\n" +
                                      "\n".join([f"• {getattr(tp, 'name', 'Unknown')}" for tp in third_parties[:5]]) +
                                      (f"\n• ...and {len(third_parties) - 5} more" if len(third_parties) > 5 else ""),
                                inline=False
                            )
                        except Exception as e:
                            embed.add_field(
                                name="❌ Registration Check",
                                value=f"Error checking registration: {e}",
                                inline=False
                            )
                    else:
                        embed.add_field(
                            name="❌ Third Party Handler",
                            value="Third party handler not available",
                            inline=True
                        )
                else:
                    embed.add_field(
                        name="❌ Dashboard RPC",
                        value="RPC interface not available",
                        inline=True
                    )
            
            # Add integration object status
            embed.add_field(
                name="🔧 Integration Object",
                value=f"Dashboard integration: {self is not None}\n" +
                      f"Has dashboard_home: {hasattr(self, 'dashboard_home')}\n" +
                      f"Has dashboard_settings: {hasattr(self, 'dashboard_settings')}\n" +
                      f"Has dashboard_about: {hasattr(self, 'dashboard_about')}",
                inline=False
            )
            
            await ctx.send(embed=embed)
            
        elif action == "register":
            # Attempt to register YALC with dashboard
            dashboard_cog = self.bot.get_cog("Dashboard")
            
            if not dashboard_cog:
                await ctx.send("❌ Dashboard cog is not loaded.")
                return
                
            if not hasattr(dashboard_cog, "rpc") or not hasattr(dashboard_cog.rpc, "third_parties_handler"):
                await ctx.send("❌ Dashboard third party handler not available.")
                return
                
            try:
                dashboard_cog.rpc.third_parties_handler.add_third_party(self)
                await ctx.send("✅ Successfully registered YALC as a dashboard third party.")
                
                # Verify registration
                third_parties = getattr(dashboard_cog.rpc.third_parties_handler, 'third_parties', [])
                yalc_registered = any(getattr(tp, 'name', None) == 'YALC' for tp in third_parties)
                
                if yalc_registered:
                    await ctx.send("✅ Registration verified - YALC is now registered.")
                else:
                    await ctx.send("⚠️ Registration completed but verification failed.")
                    
            except Exception as e:
                await ctx.send(f"❌ Failed to register YALC: {e}")
                
        else:
            await ctx.send(f"❌ Unknown action: `{action}`. Use 'status' or 'register'.")

    # --- Slash Commands ---
    
    @app_commands.command(name="yalc_enable", description="Enable logging for a specific event type")
    @app_commands.describe(event_type="The event type to enable logging for")
    @app_commands.guild_only()
    async def slash_yalc_enable(self, interaction: discord.Interaction, event_type: str):
        """Enable logging for a specific event type via slash command."""
        # Check permissions
        if not interaction.user.guild_permissions.manage_guild:
            await interaction.response.send_message("❌ You need the `Manage Server` permission to use this command.", ephemeral=True)
            return
            
        # Check if the event type exists
        if event_type not in self.event_descriptions:
            available_events = ", ".join(list(self.event_descriptions.keys())[:10])
            await interaction.response.send_message(
                f"❌ Unknown event type: `{event_type}`.\n"
                f"Available events: {available_events}{'...' if len(self.event_descriptions) > 10 else ''}",
                ephemeral=True
            )
            return
            
        # Enable the event
        async with self.config.guild(interaction.guild).events() as events:
            events[event_type] = True
            
        # Get description for confirmation message
        emoji, description = self.event_descriptions[event_type]
        await interaction.response.send_message(f"✅ {emoji} Enabled logging for **{description}** (`{event_type}`).")

    @app_commands.command(name="yalc_disable", description="Disable logging for a specific event type")
    @app_commands.describe(event_type="The event type to disable logging for")
    @app_commands.guild_only()
    async def slash_yalc_disable(self, interaction: discord.Interaction, event_type: str):
        """Disable logging for a specific event type via slash command."""
        # Check permissions
        if not interaction.user.guild_permissions.manage_guild:
            await interaction.response.send_message("❌ You need the `Manage Server` permission to use this command.", ephemeral=True)
            return
            
        # Check if the event type exists
        if event_type not in self.event_descriptions:
            available_events = ", ".join(list(self.event_descriptions.keys())[:10])
            await interaction.response.send_message(
                f"❌ Unknown event type: `{event_type}`.\n"
                f"Available events: {available_events}{'...' if len(self.event_descriptions) > 10 else ''}",
                ephemeral=True
            )
            return
            
        # Disable the event
        async with self.config.guild(interaction.guild).events() as events:
            events[event_type] = False
            
        # Get description for confirmation message
        emoji, description = self.event_descriptions[event_type]
        await interaction.response.send_message(f"✅ {emoji} Disabled logging for **{description}** (`{event_type}`).")

    @app_commands.command(name="yalc_setchannel", description="Set the logging channel for a specific event type")
    @app_commands.describe(
        event_type="The event type to set the channel for",
        channel="The channel to log the events to"
    )
    @app_commands.guild_only()
    async def slash_yalc_setchannel(self, interaction: discord.Interaction, event_type: str, channel: discord.TextChannel):
        """Set the logging channel for a specific event type via slash command."""
        # Check permissions
        if not interaction.user.guild_permissions.manage_guild:
            await interaction.response.send_message("❌ You need the `Manage Server` permission to use this command.", ephemeral=True)
            return
            
        # Check if the event type exists
        if event_type not in self.event_descriptions and event_type != "all":
            available_events = ", ".join(list(self.event_descriptions.keys())[:10])
            await interaction.response.send_message(
                f"❌ Unknown event type: `{event_type}`.\n"
                f"Available events: {available_events}{'...' if len(self.event_descriptions) > 10 else ''}\n"
                f"Use `all` to set for all event types.",
                ephemeral=True
            )
            return
            
        # Set the channel
        if event_type == "all":
            # Set for all event types
            async with self.config.guild(interaction.guild).event_channels() as event_channels:
                for et in self.event_descriptions.keys():
                    event_channels[et] = channel.id
            await interaction.response.send_message(f"✅ Set {channel.mention} as the logging channel for **all** event types.")
        else:
            # Set for a specific event type
            async with self.config.guild(interaction.guild).event_channels() as event_channels:
                event_channels[event_type] = channel.id
                
            # Get description for confirmation message
            emoji, description = self.event_descriptions[event_type]
            await interaction.response.send_message(f"✅ {emoji} Set {channel.mention} as the logging channel for **{description}** (`{event_type}`).")

    @app_commands.command(name="yalc_settings", description="View current YALC settings for this server")
    @app_commands.guild_only()
    async def slash_yalc_settings(self, interaction: discord.Interaction):
        """View the current YALC settings for this server via slash command."""
        settings = await self.config.guild(interaction.guild).all()
        
        embed = discord.Embed(
            title="YALC Logger Settings",
            description="Current logging configuration for this server",
            color=discord.Color.blue()
        )
        
        # Add enabled events
        enabled_events = [f"{self.event_descriptions[event][0]} `{event}` - {self.event_descriptions[event][1]}"
                         for event, enabled in settings["events"].items() if enabled]
        
        if enabled_events:
            embed.add_field(
                name="📋 Enabled Events",
                value="\n".join(enabled_events[:15]) +
                      (f"\n*...and {len(enabled_events) - 15} more*" if len(enabled_events) > 15 else ""),
                inline=False
            )
        else:
            embed.add_field(
                name="📋 Enabled Events",
                value="No events enabled",
                inline=False
            )
            
        # Add channel mappings
        channel_mappings = []
        for event, channel_id in settings["event_channels"].items():
            if channel_id:
                channel = interaction.guild.get_channel(channel_id)
                if channel and event in self.event_descriptions:
                    channel_mappings.append(f"{self.event_descriptions[event][0]} `{event}` → {channel.mention}")
        
        if channel_mappings:
            embed.add_field(
                name="📢 Event Channels",
                value="\n".join(channel_mappings[:10]) +
                      (f"\n*...and {len(channel_mappings) - 10} more*" if len(channel_mappings) > 10 else ""),
                inline=False
            )
        else:
            embed.add_field(
                name="📢 Event Channels",
                value="No channels configured",
                inline=False
            )
            
        # Add ignore settings
        ignore_settings = []
        
        if settings.get("ignore_bots", False):
            ignore_settings.append("🤖 Ignoring bot messages")
        
        if settings.get("ignore_webhooks", False):
            ignore_settings.append("🔗 Ignoring webhook messages")
            
        if settings.get("ignore_tupperbox", True):
            ignore_settings.append("👥 Ignoring Tupperbox/proxy messages")
            
        # Add ignored roles, users, channels counts
        ignored_roles = settings.get("ignored_roles", [])
        if ignored_roles:
            role_names = [f"<@&{role_id}>" for role_id in ignored_roles[:3]]
            ignore_settings.append(f"🚫 Ignored Roles: {', '.join(role_names)}" +
                                 (f" *and {len(ignored_roles) - 3} more*" if len(ignored_roles) > 3 else ""))
            
        ignored_users = settings.get("ignored_users", [])
        if ignored_users:
            ignore_settings.append(f"🚫 Ignored Users: {len(ignored_users)}")
            
        ignored_channels = settings.get("ignored_channels", [])
        if ignored_channels:
            channel_names = [f"<#{channel_id}>" for channel_id in ignored_channels[:3]]
            ignore_settings.append(f"🚫 Ignored Channels: {', '.join(channel_names)}" +
                                 (f" *and {len(ignored_channels) - 3} more*" if len(ignored_channels) > 3 else ""))
            
        if ignore_settings:
            embed.add_field(
                name="⚙️ Ignore Settings",
                value="\n".join(ignore_settings),
                inline=False
            )
        
        embed.set_footer(text=f"YALC • Server ID: {interaction.guild.id}")
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="yalc_quicksetup", description="Quick setup wizard for YALC logging")
    @app_commands.describe(
        log_channel="Channel to use for all logging",
        enable_basic_events="Enable basic message and member events"
    )
    @app_commands.guild_only()
    async def slash_yalc_quicksetup(self, interaction: discord.Interaction,
                                    log_channel: discord.TextChannel,
                                    enable_basic_events: bool = True):
        """Quick setup wizard for YALC logging via slash command."""
        # Check permissions
        if not interaction.user.guild_permissions.manage_guild:
            await interaction.response.send_message("❌ You need the `Manage Server` permission to use this command.", ephemeral=True)
            return
            
        try:
            # Set up basic events if requested
            if enable_basic_events:
                basic_events = [
                    "message_delete", "message_edit", "message_bulk_delete",
                    "member_join", "member_leave", "member_ban", "member_unban",
                    "channel_create", "channel_delete", "role_create", "role_delete"
                ]
                
                async with self.config.guild(interaction.guild).events() as events:
                    for event in basic_events:
                        if event in self.event_descriptions:
                            events[event] = True
                
                # Set the log channel for enabled events
                async with self.config.guild(interaction.guild).event_channels() as event_channels:
                    for event in basic_events:
                        if event in self.event_descriptions:
                            event_channels[event] = log_channel.id
                            
            # Enable some useful default settings
            await self.config.guild(interaction.guild).ignore_tupperbox.set(True)
            await self.config.guild(interaction.guild).ignore_apps.set(True)
            await self.config.guild(interaction.guild).include_thumbnails.set(True)
            await self.config.guild(interaction.guild).detect_proxy_deletes.set(True)
            
            embed = discord.Embed(
                title="✅ YALC Quick Setup Complete",
                description=f"YALC has been configured for {interaction.guild.name}",
                color=discord.Color.green()
            )
            
            if enable_basic_events:
                embed.add_field(
                    name="📋 Enabled Events",
                    value="• Message deletions, edits, and bulk deletions\n"
                          "• Member joins, leaves, bans, and unbans\n"
                          "• Channel and role creation/deletion",
                    inline=False
                )
            
            embed.add_field(
                name="📢 Log Channel",
                value=f"All events will be logged to {log_channel.mention}",
                inline=False
            )
            
            embed.add_field(
                name="⚙️ Default Settings",
                value="• Ignoring Tupperbox/proxy messages\n"
                      "• Ignoring application messages\n"
                      "• Including user thumbnails\n"
                      "• Detecting proxy deletions",
                inline=False
            )
            
            embed.add_field(
                name="🔧 Next Steps",
                value="Use `/yalc_settings` to view your configuration\n"
                      "Use `/yalc_enable` or `/yalc_disable` to adjust events\n"
                      "Use the web dashboard for advanced configuration",
                inline=False
            )
            
            await interaction.response.send_message(embed=embed)
            
        except Exception as e:
            await interaction.response.send_message(f"❌ Error during quick setup: {e}", ephemeral=True)

    async def is_tupperbox_message(self, message: discord.Message, tupperbox_ids: list) -> bool:
        """Check if a message is from Tupperbox, Tupperhook, or a configured proxy bot.
        
        This method checks if a message is from the Tupperbox bot, a webhook named "Tupperhook"/"Tupperbox",
        or any other bot configured as a Tupperbox proxy in the guild settings.
        
        Parameters
        ----------
        message: discord.Message
            The message to check
        tupperbox_ids: list
            List of Tupperbox bot IDs configured for the guild
            
        Returns
        -------
        bool
            True if the message is from Tupperbox, Tupperhook, or a proxy bot, False otherwise
        """
        # Webhook name detection for Tupperbox/Tupperhook
        if getattr(message, "webhook_id", None):
            webhook_name = getattr(message.author, "name", "") or ""
            if "tupperbox" in webhook_name.lower() or "tupperhook" in webhook_name.lower():
                return True

        if message.author.bot:
            # Check if the bot is in the configured Tupperbox IDs
            if message.author.id in tupperbox_ids:
                return True
            
            # Check for common proxy patterns in the message content
            content = message.content or ""
            if any(pattern in content for pattern in ["|", "‖", "⧸", "⧹"]):
                return True
            
            # Check if the message is a reply to a Tupperbox message
            if message.reference and message.reference.message_id:
                try:
                    referenced_message = await message.channel.fetch_message(message.reference.message_id)
                    if referenced_message and referenced_message.author.id in tupperbox_ids:
                        return True
                except discord.NotFound:
                    pass  # Referenced message not found, ignore
                except Exception as e:
                    self.log.debug(f"Error checking referenced message: {e}")
                
        return False
        
    async def safe_send(self, channel: discord.TextChannel, **kwargs) -> Optional[discord.Message]:
        """
        Send a message to a channel safely, handling common exceptions.
        
        This method attempts to send a message to a channel and handles common exceptions
        such as missing permissions, invalid channel state, etc.
        
        Parameters
        ----------
        channel : discord.TextChannel
            The channel to send the message to
        **kwargs
            Additional arguments to pass to channel.send()
            
        Returns
        -------
        Optional[discord.Message]
            The sent message if successful, None otherwise
        """
        if not channel:
            self.log.warning("Attempted to send a message to a nonexistent channel")
            return None
            
        try:
            return await channel.send(**kwargs)
        except discord.Forbidden:
            self.log.warning(f"Missing permissions to send message to channel {channel.id} in guild {channel.guild.id}")
        except discord.HTTPException as e:
            self.log.error(f"Failed to send message to channel {channel.id}: {e}")
        except Exception as e:
            self.log.error(f"Unexpected error when sending to channel {channel.id}: {e}", exc_info=True)
        return None
