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
        
        
        # Comprehensive event descriptions with emojis
        self.event_descriptions = {
            # Message events
            "message_delete": ("🗑️", "Message deletions"),
            "message_edit": ("📝", "Message edits"),
            "message_bulk_delete": ("♻️", "Bulk message deletions"),
            "message_pin": ("📌", "Message pins"),
            "message_unpin": ("📍", "Message unpins"),
            
            # Member events
            "member_join": ("🚪", "Member joins"),
            "member_leave": ("👋", "Member leaves"),
            "member_ban": ("🔨", "Member bans"),
            "member_unban": ("🔓", "Member unbans"),
            "member_kick": ("👢", "Member kicks"),
            "member_update": ("👤", "Member updates (roles, nickname)"),
            "member_timeout": ("⏱️", "Member timeout (added/removed)"),
            
            # Channel events
            "channel_create": ("🆕", "Channel creations"),
            "channel_delete": ("🗑️", "Channel deletions"),
            "channel_update": ("🔄", "Channel updates"),
            "thread_create": ("🧵", "Thread creations"),
            "thread_delete": ("🗑️", "Thread deletions"),
            "thread_update": ("🔄", "Thread updates"),
            "thread_member_join": ("➡️", "Thread member joins"),
            "thread_member_leave": ("⬅️", "Thread member leaves"),
            "forum_post_create": ("📰", "Forum post creations"),
            "forum_post_delete": ("🗑️", "Forum post deletions"),
            "forum_post_update": ("🔄", "Forum post updates"),
            
            # Role events
            "role_create": ("✨", "Role creations"),
            "role_delete": ("🗑️", "Role deletions"),
            "role_update": ("🔄", "Role updates"),
            
            # Guild events
            "guild_update": ("⚙️", "Server setting updates"),
            "emoji_update": ("😀", "Emoji updates"),
            "sticker_update": ("🏷️", "Sticker updates"),
            "invite_create": ("📨", "Invite creations"),
            "invite_delete": ("🗑️", "Invite deletions"),
            "guild_scheduled_event_create": ("📅", "Server event creations"),
            "guild_scheduled_event_update": ("🔄", "Server event updates"),
            "guild_scheduled_event_delete": ("🗑️", "Server event deletions"),
            "stage_instance_create": ("🎭", "Stage instance creations"),
            "stage_instance_delete": ("🗑️", "Stage instance deletions"),
            "stage_instance_update": ("🔄", "Stage instance updates"),
            
            # Voice events
            "voice_update": ("🎤", "Voice channel updates"),
            "voice_state_update": ("🔊", "Voice state changes"),
            
            # Command and interaction events
            "command_use": ("⌨️", "Command usage"),
            "command_error": ("⚠️", "Command errors"),
            "application_cmd": ("🔷", "Application command usage"),
            
            # Reaction events
            "reaction_add": ("👍", "Reaction additions"),
            "reaction_remove": ("👎", "Reaction removals"),
            "reaction_clear": ("🧹", "Reaction clears"),
            
            # Integration events
            "integration_create": ("🔌", "Integration creations"),
            "integration_update": ("🔄", "Integration updates"),
            "integration_delete": ("🗑️", "Integration deletions"),
            
            # Webhook events
            "webhook_update": ("🪝", "Webhook updates"),
            
            # AutoMod events
            "automod_rule_create": ("🛡️", "AutoMod rule creations"),
            "automod_rule_update": ("🔄", "AutoMod rule updates"),
            "automod_rule_delete": ("🗑️", "AutoMod rule deletions"),
            "automod_action": ("🚫", "AutoMod actions executed")
        }

        # Initialize Config with comprehensive defaults
        default_guild = {
            # Event enablement status - all disabled by default
            "events": {event: False for event in self.event_descriptions},
            
            # Channel mapping for each event type
            "event_channels": {},
            
            # Tupperbox and Discord app filtering settings
            "ignore_tupperbox": True,
            "tupperbox_ids": [
                "239232811662311425",  # Default Tupperbox bot ID
                "431544605209788416",  # Tupper.io
                "508808937294331904",  # PluralKit
                "466378653216014359",  # Tupperbox fork
                "798482360910127104",  # PluralKit webhook service
                "782749873194696734",  # Another proxy bot
                "689490322539159592",  # Yet another proxy bot
                "765338157961879563"   # TupperBox Beta
            ],
            
            # Advanced filtering options
            "ignore_apps": True,           # Ignore all Discord app messages
            "ignore_webhooks": False,      # Option to ignore webhook messages
            "detect_proxy_deletes": True,  # Detect and ignore Tupperbox proxy message patterns
            "ignore_proxy_patterns": True, # Detect proxy message patterns in normal messages
            "webhook_name_filter": [],     # Custom webhook names to ignore
            "message_prefix_filter": [],   # Custom message prefixes to ignore
            
            # Log management
            "retention_days": 30,         # How long to keep logs
            "log_by_category": False,     # Option to organize logs by category
            "auto_archive_threads": True, # Auto-archive log threads after retention period
            "max_embed_count": 25,        # Maximum number of embeds per log entry
            
            # Ignore lists
            "ignored_channels": [],       # Channels to ignore for all events
            "ignored_users": [],          # Users to ignore for all events
            "ignored_roles": [],          # Roles to ignore for all events
            "ignored_categories": [],     # Channel categories to ignore
            
            # Appearance settings
            "use_embeds": True,           # Use rich embeds (vs. plain text)
            "embed_color": None,          # Custom embed color override
            "include_timestamps": True,   # Include timestamps in logs
            "include_thumbnails": True,   # Include user avatars as thumbnails
            "use_markdown": True,         # Format text with markdown
            "compact_mode": False         # Use more compact embed layouts for busier servers
        }
        self.config = Config.get_conf(self, identifier=2394567890, force_registration=True)
        self.config.register_guild(**default_guild)


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
            
            # Initialize the embed with base information
            description = f"🗑️ Message deleted in {getattr(message.channel, 'mention', str(message.channel))}\n\u200b"
            
            # Add jump URL if available (useful for context)
            message_id = getattr(message, "id", None)
            channel_id = getattr(message.channel, "id", None)
            if message_id and channel_id:
                description += f"\nMessage ID: `{message_id}`"
            
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
            
            # Add moderation data if available
            audit_entry = None
            try:
                if guild.me.guild_permissions.view_audit_log:
                    async for entry in guild.audit_logs(limit=5, action=discord.AuditLogAction.message_bulk_delete):
                        # Match the entry with our channel
                        target_channel = getattr(entry, "target", None)
                        if target_channel and target_channel.id == channel.id:
                            audit_entry = entry
                            break
            except Exception as e:
                self.log.debug(f"Could not fetch audit logs: {e}")
                
            if audit_entry:
                embed.add_field(
                    name="Deleted By",
                    value=f"{audit_entry.user.mention} ({audit_entry.user})",
                    inline=True
                )
                
                if hasattr(audit_entry, "reason") and audit_entry.reason:
                    embed.add_field(name="Reason", value=audit_entry.reason, inline=True)
            
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
        """View the current YALC settings for this server."""
        settings = await self.config.guild(ctx.guild).all()
        
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
                channel = ctx.guild.get_channel(channel_id)
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
        
        embed.set_footer(text=f"YALC • Server ID: {ctx.guild.id}")
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
    
    async def is_tupperbox_message(self, message: discord.Message, tupperbox_ids: list) -> bool:
        """Check if a message is from Tupperbox or a configured proxy bot.
        
        This method checks if a message is from the Tupperbox bot or any other bot
        configured as a Tupperbox proxy in the guild settings.
        
        Parameters
        ----------
        message: discord.Message
            The message to check
        tupperbox_ids: list
            List of Tupperbox bot IDs configured for the guild
            
        Returns
        -------
        bool
            True if the message is from Tupperbox or a proxy bot, False otherwise
        """
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