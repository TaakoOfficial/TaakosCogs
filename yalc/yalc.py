"""
YALC - Yet Another Logging Cog for Red-DiscordBot.
A comprehensive logging solution with both classic and slash commands.
"""

from __future__ import annotations

import asyncio
import datetime
import logging
import time
from typing import TYPE_CHECKING

import discord
from redbot.core import Config, app_commands, commands, modlog

from .dashboard_integration import DashboardIntegration

if TYPE_CHECKING:
    from redbot.core.bot import Red


class YALC(DashboardIntegration, commands.Cog):
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

    SETUP_LOG_CHANNELS = [
        (
            "application",
            "🤖 | application-logs",
            "YALC: Prefix command, slash command, application permission, and integration logs",
        ),
        (
            "channel",
            "🤖 | channel-logs",
            "YALC: Server channel creation, deletion, and update logs",
        ),
        (
            "discord_automod",
            "🤖 | discord-automod-logs",
            "YALC: Discord AutoMod rule and action logs",
        ),
        ("emoji", "🤖 | emoji-logs", "YALC: Server emoji logs"),
        ("event", "🤖 | event-logs", "YALC: Scheduled event logs"),
        ("invite", "🤖 | invite-logs", "YALC: Invite creation and deletion logs"),
        (
            "message",
            "🤖 | message-logs",
            "YALC: Message edit, deletion, pin, and reaction logs",
        ),
        ("role", "🤖 | role-logs", "YALC: Role creation, deletion, and update logs"),
        ("stage", "🤖 | stage-logs", "YALC: Stage instance logs"),
        ("server", "🤖 | server-logs", "YALC: Server settings and broad guild logs"),
        ("sticker", "🤖 | sticker-logs", "YALC: Server sticker logs"),
        ("soundboard", "🤖 | soundboard-logs", "YALC: Soundboard sound logs"),
        ("thread", "🤖 | thread-logs", "YALC: Thread and forum post logs"),
        ("user", "🤖 | user-logs", "YALC: Member join, leave, and profile update logs"),
        ("voice", "🤖 | voice-logs", "YALC: Voice join, leave, move, and state logs"),
        ("webhook", "🤖 | webhook-logs", "YALC: Webhook update logs"),
        (
            "moderation",
            "🤖 | moderation-logs",
            "YALC: Ban, kick, timeout, and moderation logs",
        ),
    ]

    DEFAULT_EVENT_CHANNEL_KEYS = {
        "application_cmd": "application",
        "application_cmd_permissions_update": "application",
        "command_error": "application",
        "command_use": "application",
        "integration_create": "application",
        "integration_delete": "application",
        "integration_update": "application",
        "channel_create": "channel",
        "channel_delete": "channel",
        "channel_update": "channel",
        "automod_action": "discord_automod",
        "automod_rule_create": "discord_automod",
        "automod_rule_delete": "discord_automod",
        "automod_rule_update": "discord_automod",
        "emoji_update": "emoji",
        "guild_scheduled_event_create": "event",
        "guild_scheduled_event_delete": "event",
        "guild_scheduled_event_update": "event",
        "invite_create": "invite",
        "invite_delete": "invite",
        "message_bulk_delete": "message",
        "message_delete": "message",
        "message_edit": "message",
        "message_pin": "message",
        "message_unpin": "message",
        "reaction_add": "message",
        "reaction_clear": "message",
        "reaction_remove": "message",
        "role_create": "role",
        "role_delete": "role",
        "role_update": "role",
        "stage_instance_create": "stage",
        "stage_instance_delete": "stage",
        "stage_instance_update": "stage",
        "guild_update": "server",
        "sticker_update": "sticker",
        "soundboard_sound_create": "soundboard",
        "soundboard_sound_delete": "soundboard",
        "soundboard_sound_update": "soundboard",
        "forum_post_create": "thread",
        "forum_post_delete": "thread",
        "forum_post_update": "thread",
        "thread_create": "thread",
        "thread_delete": "thread",
        "thread_member_join": "thread",
        "thread_member_leave": "thread",
        "thread_update": "thread",
        "member_join": "user",
        "member_leave": "user",
        "member_update": "user",
        "voice_state_update": "voice",
        "voice_update": "voice",
        "webhook_update": "webhook",
        "member_ban": "moderation",
        "member_kick": "moderation",
        "member_timeout": "moderation",
        "member_unban": "moderation",
    }

    def __init__(self, bot: Red):
        # Initialize the bot first
        self.bot = bot

        # Initialize config and logging before parent classes
        self.config = Config.get_conf(self, identifier=1234567890)
        self.log = logging.getLogger("red.YALC")

        # Real-time audit log entry storage for role attribution
        self.recent_audit_entries = {}
        self._recent_role_event_logs = {}

        # Ban cache to distinguish between kicks and leaves
        self._ban_cache = {}

        # Enhanced audit log caching system
        self._audit_cache = {}
        self._cache_cleanup_task = None

        # Settings cache for performance optimization
        self._settings_cache = {}
        self._settings_cache_timeout = 300  # 5 minutes

        # Background task queue system for async performance
        self._log_queue = asyncio.Queue(maxsize=1000)  # Prevent memory issues
        self._background_worker_task = None
        self._processing_shutdown = False

        # Smart audit log debouncing system
        self._audit_debounce_cache = {}
        self._debounce_timeout = 30  # 30 seconds

        # Object pooling for memory efficiency and consistent performance
        self._embed_pool = []
        self._embed_pool_size = 50
        self._embed_pool_lock = asyncio.Lock()

        # Connection and batch optimization
        self._batch_operations = {}
        self._batch_timeout = 2.0  # 2 seconds
        self._max_batch_size = 10

        # Performance metrics tracking
        self._performance_metrics = {
            "events_processed": 0,
            "cache_hits": 0,
            "cache_misses": 0,
            "api_calls_saved": 0,
            "background_queue_size": 0,
            "last_reset": time.time(),
        }

        # Enhanced audit log caching system
        self._audit_cache = {}
        self._cache_cleanup_task = None

        # Settings cache for performance optimization
        self._settings_cache = {}
        self._settings_cache_timeout = 300  # 5 minutes

        # Event descriptions for logging and dashboard - MUST be set before DashboardIntegration.__init__
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
            "application_cmd_permissions_update": (
                "⚙️",
                "Application Command Permission Updates",
            ),
            # Reaction events
            "reaction_add": ("👍", "Reaction Additions"),
            "reaction_remove": ("👎", "Reaction Removals"),
            "reaction_clear": ("🧹", "Reaction Clears"),
            # Integration events
            "integration_create": ("🔗", "Integration Creation"),
            "integration_update": ("🔄", "Integration Updates"),
            "integration_delete": ("🗑️", "Integration Deletion"),
            # Soundboard events
            "soundboard_sound_create": ("🔉", "Soundboard Sound Creation"),
            "soundboard_sound_update": ("🔊", "Soundboard Sound Updates"),
            "soundboard_sound_delete": ("🔇", "Soundboard Sound Deletion"),
            # Webhook/AutoMod
            "webhook_update": ("🪝", "Webhook Updates"),
            "automod_rule_create": ("🛡️", "AutoMod Rule Creation"),
            "automod_rule_update": ("🔄", "AutoMod Rule Updates"),
            "automod_rule_delete": ("🗑️", "AutoMod Rule Deletion"),
            "automod_action": ("⚔️", "AutoMod Actions"),
        }

        # Initialize both parent classes after setting up all required attributes
        commands.Cog.__init__(self)
        DashboardIntegration.__init__(self, bot)

        self.log.info("YALC initialized with DashboardIntegration")

        # Dashboard integration is handled by the DashboardIntegration mixin class
        # The on_dashboard_cog_add listener is inherited from DashboardIntegration

        # Configuration defaults
        default_guild = {
            "events": dict.fromkeys(self.event_descriptions.keys(), False),
            "event_channels": dict.fromkeys(self.event_descriptions.keys()),
            "ignored_users": [],
            "ignored_roles": [],
            "ignored_channels": [],
            "ignored_categories": [],
            "granular_ignores": [],  # New granular ignore rules
            "ignore_bots": False,
            "ignore_webhooks": False,
            "ignore_tupperbox": True,
            "ignore_apps": True,
            "tupperbox_ids": ["239232811662311425"],  # Default Tupperbox bot ID
            "include_thumbnails": True,
            "detect_proxy_deletes": True,
            "message_prefix_filter": [],
            "webhook_name_filter": [],
            # --- Dashboard example config fields ---
            "enable_feature": False,
            "custom_message": "",
            "log_retention_days": 7,
            # Voice session tracking
            "voice_sessions": {},  # Active sessions: user_id -> {"channel_id": int, "start_time": float}
            "voice_events": [],  # Recent events history: max 50 entries
        }

        self.config.register_guild(**default_guild)

        # Dashboard integration is handled via inheritance and decorators in dashboard_integration.py

    async def _get_audit_log_entry_with_retry(
        self,
        guild,
        action,
        target=None,
        timeout_seconds=30,
        retries=3,
    ):
        """
        Helper function to get recent audit log entries with retry logic and improved reliability.

        Args:
            guild: The guild to search audit logs in
            action: The AuditLogAction to search for
            target: Optional target to match against (user, channel, role, etc.)
            timeout_seconds: How recent the entry should be (default 30 seconds)
            retries: Number of retry attempts for failed requests

        Returns:
            AuditLogEntry or None if not found/no permission

        Matching order:
        1. Exact object match (entry.target == target)
        2. Fallback: match by .id if both entry.target and target have .id
        3. Fallback: most recent entry in window
        """
        if not guild.me.guild_permissions.view_audit_log:
            return None

        for attempt in range(retries):
            try:
                await asyncio.sleep(2 + (attempt * 0.5))  # Progressive delay

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

                # If no entries found, don't retry
                return None

            except discord.HTTPException as e:
                if attempt < retries - 1:
                    self.log.debug(
                        f"Audit log fetch failed (attempt {attempt + 1}/{retries}): {e}",
                    )
                    await asyncio.sleep(2**attempt)  # Exponential backoff
                    continue
                self.log.warning(
                    f"Audit log fetch failed after {retries} attempts: {e}",
                )
            except (discord.Forbidden, asyncio.TimeoutError):
                # Don't retry for permission or timeout errors
                break
            except Exception as e:
                self.log.error(f"Unexpected error in audit log fetch: {e}")
                break

        return None

    async def _get_audit_log_entry(
        self,
        guild,
        action,
        target=None,
        timeout_seconds=30,
    ):
        """Legacy method for backward compatibility - redirects to retry version."""
        return await self._get_audit_log_entry_with_retry(
            guild,
            action,
            target,
            timeout_seconds,
        )

    async def _get_cached_settings(self, guild: discord.Guild) -> dict:
        """Get guild settings with caching for performance optimization."""
        guild_id = guild.id
        cache_key = f"settings_{guild_id}"
        current_time = time.time()

        # Check if we have cached settings that haven't expired
        if cache_key in self._settings_cache:
            cached_data = self._settings_cache[cache_key]
            if current_time - cached_data["timestamp"] < self._settings_cache_timeout:
                return cached_data["settings"]

        # Cache miss or expired - fetch from database
        settings = await self.config.guild(guild).all()
        self._settings_cache[cache_key] = {
            "settings": settings,
            "timestamp": current_time,
        }

        # Clean up old cache entries (keep cache size reasonable)
        if len(self._settings_cache) > 100:
            oldest_key = min(
                self._settings_cache.keys(),
                key=lambda k: self._settings_cache[k]["timestamp"],
            )
            del self._settings_cache[oldest_key]

        return settings

    def _invalidate_settings_cache(self, guild: discord.Guild) -> None:
        """Clear cached settings for a guild after configuration changes."""
        if guild:
            self._settings_cache.pop(f"settings_{guild.id}", None)

    def _get_default_event_channel_key(self, event_type: str) -> str:
        """Return the closest setup log channel key for an event type."""
        if event_type in self.DEFAULT_EVENT_CHANNEL_KEYS:
            return self.DEFAULT_EVENT_CHANNEL_KEYS[event_type]

        prefix_map = {
            "application": "application",
            "automod": "discord_automod",
            "channel": "channel",
            "command": "application",
            "emoji": "emoji",
            "forum": "thread",
            "guild": "server",
            "integration": "application",
            "invite": "invite",
            "member": "user",
            "message": "message",
            "reaction": "message",
            "role": "role",
            "soundboard": "soundboard",
            "stage": "stage",
            "sticker": "sticker",
            "thread": "thread",
            "voice": "voice",
            "webhook": "webhook",
        }
        return prefix_map.get(event_type.split("_", 1)[0], "server")

    def _is_forum_thread(self, thread: discord.Thread) -> bool:
        """Check whether a thread represents a forum post."""
        parent = getattr(thread, "parent", None)
        forum_channel_cls = getattr(discord, "ForumChannel", None)
        if forum_channel_cls and isinstance(parent, forum_channel_cls):
            return True
        return str(getattr(parent, "type", "")).lower() == "forum"

    def _get_audit_action(self, action_name: str):
        """Get an audit log action if the installed discord.py version exposes it."""
        return getattr(discord.AuditLogAction, action_name, None)

    @staticmethod
    def _role_has_permission(role: discord.Role, permission_name: str) -> bool:
        """Return whether a role has a permission, tolerating older discord.py fields."""
        permissions = getattr(role, "permissions", None)
        return bool(getattr(permissions, permission_name, False))

    @staticmethod
    def _role_is_premium_subscriber(role: discord.Role) -> bool:
        """Return whether a role is Discord's booster role across discord.py variants."""
        checker = getattr(role, "is_premium_subscriber", None)
        if callable(checker):
            try:
                return bool(checker())
            except Exception:
                return False
        return bool(getattr(role, "premium_subscriber", False))

    @staticmethod
    def _attachment_is_image(attachment: discord.Attachment) -> bool:
        """Return whether an attachment looks like an image."""
        content_type = getattr(attachment, "content_type", None)
        if content_type and content_type.lower().startswith("image/"):
            return True

        filename = getattr(attachment, "filename", "").lower()
        return filename.endswith(
            (
                ".apng",
                ".avif",
                ".bmp",
                ".gif",
                ".jpeg",
                ".jpg",
                ".png",
                ".tif",
                ".tiff",
                ".webp",
            ),
        )

    @staticmethod
    def _format_file_size(size: int | None) -> str:
        if not size:
            return "unknown size"

        units = ["B", "KB", "MB", "GB"]
        value = float(size)
        unit = units[0]
        for unit in units:
            if value < 1024 or unit == units[-1]:
                break
            value /= 1024

        if unit == "B":
            return f"{int(value)} {unit}"
        return f"{value:.1f} {unit}"

    @staticmethod
    def _reset_send_files(kwargs: dict) -> None:
        """Reset discord.File objects before retrying a send."""
        send_files = []
        if kwargs.get("file"):
            send_files.append(kwargs["file"])
        send_files.extend(kwargs.get("files") or [])

        for send_file in send_files:
            reset = getattr(send_file, "reset", None)
            if callable(reset):
                try:
                    reset(seek=True)
                except TypeError:
                    reset()
                except Exception:
                    continue

    async def _copy_deleted_image_attachments(
        self,
        attachments: list[discord.Attachment],
        log_channel: discord.TextChannel,
    ) -> tuple:
        """Create discord.File copies for deleted-message image attachments."""
        copied_files = []
        copy_notes = []
        if not attachments:
            return copied_files, copy_notes

        file_size_limit = getattr(
            getattr(log_channel, "guild", None),
            "filesize_limit",
            None,
        )

        for attachment in attachments:
            if not self._attachment_is_image(attachment):
                continue

            filename = getattr(attachment, "filename", "image")
            size = getattr(attachment, "size", None)
            if file_size_limit and size and size > file_size_limit:
                copy_notes.append(
                    f"`{filename}` was too large to copy ({self._format_file_size(size)}).",
                )
                continue

            try:
                try:
                    file_copy = await attachment.to_file(use_cached=True)
                except TypeError:
                    file_copy = await attachment.to_file()
                copied_files.append(file_copy)
            except (discord.Forbidden, discord.NotFound, discord.HTTPException) as e:
                copy_notes.append(
                    f"`{filename}` could not be copied ({e.__class__.__name__}).",
                )
            except Exception as e:
                self.log.debug(
                    f"Could not copy deleted image attachment {filename}: {e}",
                    exc_info=True,
                )
                copy_notes.append(f"`{filename}` could not be copied.")

        if copied_files:
            copy_notes.insert(0, f"Copied {len(copied_files)} deleted image(s) below.")

        return copied_files, copy_notes

    @staticmethod
    def _close_send_files(files: list[discord.File]) -> None:
        for send_file in files:
            close = getattr(send_file, "close", None)
            if callable(close):
                try:
                    close()
                except Exception:
                    continue

    def _prune_recent_role_event_logs(self) -> None:
        """Remove old role log markers used to prevent gateway/audit duplicates."""
        current_time = time.time()
        expired_keys = [
            key
            for key, timestamp in self._recent_role_event_logs.items()
            if current_time - timestamp > 30
        ]
        for key in expired_keys:
            del self._recent_role_event_logs[key]

    def _role_event_log_key(self, guild_id: int, event_type: str, role_key) -> tuple:
        return (guild_id, event_type, str(role_key))

    def _mark_role_event_logged(self, guild_id: int, event_type: str, role_key) -> None:
        if guild_id is None or role_key is None:
            return
        self._prune_recent_role_event_logs()
        self._recent_role_event_logs[
            self._role_event_log_key(guild_id, event_type, role_key)
        ] = time.time()

    def _was_role_event_logged(self, guild_id: int, event_type: str, role_key) -> bool:
        if guild_id is None or role_key is None:
            return False
        self._prune_recent_role_event_logs()
        return (
            self._role_event_log_key(guild_id, event_type, role_key)
            in self._recent_role_event_logs
        )

    def _get_audit_role_name(self, entry) -> str | None:
        target = getattr(entry, "target", None)
        for source in (
            target,
            getattr(entry, "before", None),
            getattr(entry, "after", None),
        ):
            name = getattr(source, "name", None)
            if name:
                return name
        return None

    def _get_audit_role_key(self, entry):
        target = getattr(entry, "target", None)
        target_id = getattr(target, "id", None)
        if target_id is not None:
            return target_id
        return self._get_audit_role_name(entry)

    async def _log_role_audit_fallback(self, entry, event_type: str) -> None:
        """Log role create/delete from audit logs when the gateway role event is missed."""
        try:
            await asyncio.sleep(2)
            guild = getattr(entry, "guild", None)
            if not guild:
                return

            role_key = self._get_audit_role_key(entry)
            if self._was_role_event_logged(guild.id, event_type, role_key):
                return

            if not await self.should_log_event(guild, event_type):
                return

            channel = await self.get_log_channel(guild, event_type)
            if not channel:
                self.log.warning(f"No log channel set for {event_type}.")
                return

            target = getattr(entry, "target", None)
            role_name = self._get_audit_role_name(entry) or "Unknown role"
            role_id = getattr(target, "id", None)
            actor = getattr(entry, "user", None)
            reason = getattr(entry, "reason", None)

            if event_type == "role_create":
                role_display = getattr(target, "mention", f"**{role_name}**")
                description = f"✨ Role created: {role_display}"
                actor_field = "Created By"
                footer_label = "YALC Logger • Role Created"
            else:
                description = f"🗑️ Role deleted: **{role_name}**"
                actor_field = "Deleted By"
                footer_label = "YALC Logger • Role Deleted"

            if actor:
                description += f" by {actor.mention}"
            description += "\n\u200b"

            embed = self.create_embed(event_type, description)
            role_value = f"**{role_name}**"
            if role_id is not None:
                role_value += f" (ID: `{role_id}`)"
            embed.add_field(name="Role", value=role_value, inline=True)

            if actor:
                embed.add_field(
                    name=actor_field,
                    value=f"{actor.mention} (`{actor}`, ID: `{actor.id}`)",
                    inline=True,
                )
            else:
                embed.add_field(
                    name=actor_field,
                    value="Unknown (audit log unavailable)",
                    inline=True,
                )

            if reason:
                embed.add_field(name="Reason", value=reason, inline=False)

            event_time = datetime.datetime.now(datetime.UTC)
            self.set_embed_footer(embed, event_time=event_time, label=footer_label)

            sent_message = await self.safe_send(channel, embed=embed)
            if sent_message:
                self._mark_role_event_logged(guild.id, event_type, role_key)
        except Exception as e:
            self.log.error(
                f"Failed to log {event_type} from audit log fallback: {e}",
                exc_info=True,
            )

    async def should_log_event(
        self,
        guild: discord.Guild,
        event_type: str,
        channel: discord.abc.GuildChannel | None = None,
        user: discord.Member | discord.User | None = None,
        message: discord.Message | None = None,
    ) -> bool:
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

            # Get cached settings to minimize database calls
            settings = await self._get_cached_settings(guild)

            # 1. Check if this event type is enabled at all
            if not settings["events"].get(event_type, False):
                self.log.debug(f"Event type {event_type} is disabled in settings")
                return False

            # 2. Channel-based ignore checks
            if channel:
                # Direct channel ignore
                if channel.id in settings["ignored_channels"]:
                    self.log.debug(
                        f"Channel {channel.id} is in the ignored channels list",
                    )
                    return False

                # Category ignore
                channel_category = getattr(channel, "category", None)
                if channel_category:
                    ignored_categories = settings.get("ignored_categories", [])
                    if channel_category.id in ignored_categories:
                        self.log.debug(
                            f"Category {channel_category.id} is in the ignored categories list",
                        )
                        return False

                # Thread parent ignore (if this is a thread and parent is ignored)
                if isinstance(channel, discord.Thread) and channel.parent:
                    if channel.parent.id in settings["ignored_channels"]:
                        self.log.debug(
                            f"Thread parent {channel.parent.id} is in the ignored channels list",
                        )
                        return False
                    parent_category = getattr(channel.parent, "category", None)
                    ignored_categories = settings.get("ignored_categories", [])
                    if parent_category and parent_category.id in ignored_categories:
                        self.log.debug(
                            f"Thread parent category {parent_category.id} is in the ignored categories list",
                        )
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
                        self.log.debug(
                            f"User {user.id} has a role that is in the ignored roles list",
                        )
                        return False

                # Bot ignore (optionally ignore all bot users)
                if getattr(user, "bot", False) and settings.get("ignore_bots", False):
                    self.log.debug(
                        f"User {user.id} is a bot and bot messages are ignored",
                    )
                    return False

            # 4. Message-specific ignore checks
            if isinstance(message, discord.Message):
                # Tupperbox ignore
                if settings.get("ignore_tupperbox", True):
                    tupperbox_ids = settings.get(
                        "tupperbox_ids",
                        ["239232811662311425"],
                    )
                    if await self.is_tupperbox_message(message, tupperbox_ids):
                        self.log.debug(
                            f"Message {message.id} detected as Tupperbox message",
                        )
                        return False

                # Webhook ignore
                if settings.get("ignore_webhooks", False) and getattr(
                    message,
                    "webhook_id",
                    None,
                ):
                    self.log.debug(
                        f"Message {message.id} is from webhook {message.webhook_id} and webhooks are ignored",
                    )
                    return False

                # App message ignore
                if settings.get("ignore_apps", True) and getattr(
                    message,
                    "application",
                    None,
                ):
                    self.log.debug(
                        f"Message {message.id} is from app {message.application.id} and apps are ignored",
                    )
                    return False

            # 5. Granular ignore checks - check for specific event+user+channel combinations
            granular_ignores = settings.get("granular_ignores", [])
            if granular_ignores and user and channel:
                # Thread-specific logic: check if this is a thread and parent channel is granularly ignored
                if isinstance(channel, discord.Thread) and channel.parent:
                    for rule in granular_ignores:
                        if (
                            rule["event_type"] == event_type
                            and rule["user_id"] == user.id
                            and rule["channel_id"] == channel.parent.id
                        ):
                            self.log.debug(
                                f"Event {event_type} from user {user.id} in thread {channel.id} (parent channel {channel.parent.id} granularly ignored)",
                            )
                            return False

                # Regular granular ignore checks
                for rule in granular_ignores:
                    if (
                        rule["event_type"] == event_type
                        and rule["user_id"] == user.id
                        and rule["channel_id"] == channel.id
                    ):
                        self.log.debug(
                            f"Event {event_type} from user {user.id} in channel {channel.id} is granularly ignored",
                        )
                        return False

            # If we've passed all ignore checks, we should log this event
            return True

        except Exception as e:
            self.log.error(f"Error in should_log_event: {e}", exc_info=True)
            # Default to True if an error occurred (better to log in case of doubt)
            return True

    # Removed setup_dashboard; dashboard pages are now registered via inheritance and decorators in dashboard_integration.py

    async def get_log_channel(
        self,
        guild: discord.Guild,
        event_type: str,
    ) -> discord.TextChannel | None:
        """Get the appropriate logging channel for an event. Only event_channels is used."""
        settings = await self._get_cached_settings(guild)
        self.log.debug(
            f"[get_log_channel] Guild: {guild.id}, Event: {event_type}, Settings: {settings}",
        )
        channel_id = settings["event_channels"].get(event_type)
        self.log.debug(f"[get_log_channel] Selected channel_id: {channel_id}")
        if not channel_id:
            return None
        channel = guild.get_channel(channel_id)
        self.log.debug(f"[get_log_channel] Resolved channel: {channel}")
        return channel if isinstance(channel, discord.TextChannel) else None

    def _calculate_embed_size(
        self,
        embed: discord.Embed,
        additional_fields: list[tuple] = None,
    ) -> int:
        """
        Calculate the total character count of an embed including all fields.

        Parameters
        ----------
        embed: discord.Embed
            The embed to calculate size for
        additional_fields: List[tuple], optional
            Additional fields to include in the calculation (name, value)

        Returns
        -------
        int
            Total character count of the embed
        """
        total_chars = 0

        # Title (max 256 chars)
        if embed.title:
            total_chars += min(len(embed.title), 256)

        # Description (max 4096 chars)
        if embed.description:
            total_chars += min(len(embed.description), 4096)

        # Author name (max 256 chars)
        if embed.author and embed.author.name:
            total_chars += min(len(embed.author.name), 256)

        # Footer text (max 2048 chars)
        if embed.footer and embed.footer.text:
            total_chars += min(len(embed.footer.text), 2048)

        # Add any additional fields
        if additional_fields:
            for name, value in additional_fields:
                # Field name (max 256 chars)
                total_chars += min(len(str(name)), 256)
                # Field value (max 1024 chars)
                total_chars += min(len(str(value)), 1024)

        return total_chars

    def _smart_truncate(self, text: str, max_length: int, suffix: str = "...") -> str:
        """
        Truncate text at word boundaries while respecting the maximum length.

        Parameters
        ----------
        text: str
            The text to truncate
        max_length: int
            Maximum length including suffix
        suffix: str
            Suffix to add when text is truncated

        Returns
        -------
        str
            Truncated text with suffix if applicable
        """
        if len(text) <= max_length:
            return text

        # Reserve space for suffix
        available_length = max_length - len(suffix)

        # Find the last space before the limit
        truncated = text[:available_length]
        last_space = truncated.rfind(" ")

        if last_space > 0:
            return text[:last_space] + suffix
        # No spaces found, truncate at exact limit
        return text[:available_length] + suffix

    def _format_embed_field_name(self, field_name: str) -> str:
        """Make generated embed field names readable for server staff."""
        readable = str(field_name).replace("_", " ").strip().title()
        acronym_fixes = {
            "Id": "ID",
            "Ids": "IDs",
            "Url": "URL",
            "Urls": "URLs",
            "Nsfw": "NSFW",
            "Rtc": "RTC",
            "Afk": "AFK",
            "Automod": "AutoMod",
        }
        for old, new in acronym_fixes.items():
            readable = readable.replace(old, new)
        return readable[:256] or "Details"

    def _format_embed_field_value(self, field_name: str, field_value) -> str:
        """Normalize field values before Discord embed size handling."""
        if field_value is None:
            return "None"
        if isinstance(field_value, bool):
            return "Yes" if field_value else "No"

        field_value_str = str(field_value).strip()
        if not field_value_str:
            return "None"

        field_name_lower = str(field_name).lower()
        if field_name_lower in {"content", "message_content", "flagged_content"}:
            return field_value_str

        return field_value_str

    def _should_inline_embed_field(self, field_name: str, field_value: str) -> bool:
        """Choose inline fields only for short metadata, not narrative content."""
        field_name_lower = str(field_name).lower()
        block_fields = {
            "changes",
            "content",
            "message_content",
            "flagged_content",
            "reason",
            "description",
            "actions",
            "action_details",
            "error_message",
            "command",
            "options",
        }
        if field_name_lower in block_fields:
            return False
        return len(field_value) < 90 and "\n" not in field_value

    def _get_embed_title(self, event_type: str) -> str:
        """Return a concise, human-readable title for an event embed."""
        emoji, description = self.event_descriptions.get(
            event_type,
            ("📝", event_type.replace("_", " ").title()),
        )
        return f"{emoji} {description}"[:256]

    def _try_single_embed(
        self,
        event_type: str,
        description: str,
        **kwargs,
    ) -> discord.Embed:
        """
        Try to create a single embed with all fields, checking Discord limits.

        This method creates an embed with all the provided fields and checks if it exceeds
        Discord's character limits. If it does, it will truncate fields intelligently
        to fit within the limits.

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
            An embed that fits within Discord's character limits
        """
        # Create the base embed
        embed = discord.Embed(
            title=self._get_embed_title(event_type),
            description=description,
            color=self._get_event_color(event_type),
            timestamp=datetime.datetime.now(datetime.UTC),
        )

        # Add all fields from kwargs with truncation
        for field_name, field_value in kwargs.items():
            if field_value is not None:
                # Convert to string and apply smart truncation to field values
                field_value_str = self._format_embed_field_value(
                    field_name,
                    field_value,
                )

                # Check individual field limits
                if len(field_value_str) > 1024:
                    field_value_str = (
                        self._smart_truncate(field_value_str, 1021) + "..."
                    )
                elif (
                    str(field_name).lower() in ["content", "message_content"]
                    and len(field_value_str) > 512
                ):
                    # Be more conservative with content fields
                    field_value_str = self._smart_truncate(field_value_str, 509) + "..."

                embed.add_field(
                    name=self._format_embed_field_name(field_name),
                    value=field_value_str,
                    inline=self._should_inline_embed_field(field_name, field_value_str),
                )

        return embed

    def _get_event_color(self, event_type: str) -> int:
        """
        Get the appropriate color for an event type.

        Parameters
        ----------
        event_type: str
            The type of event

        Returns
        -------
        int
            Discord color value
        """
        color_map = {
            # Message events
            "message_delete": 0xE74C3C,  # Red
            "message_edit": 0xF39C12,  # Orange
            "message_bulk_delete": 0x9B59B6,  # Purple
            "message_pin": 0x3498DB,  # Blue
            "message_unpin": 0x3498DB,  # Blue
            # Member events
            "member_join": 0x2ECC71,  # Green
            "member_leave": 0xE67E22,  # Dark orange
            "member_ban": 0xC0392B,  # Dark red
            "member_unban": 0x27AE60,  # Dark green
            "member_update": 0x3498DB,  # Blue
            "member_kick": 0xE74C3C,  # Red
            "member_timeout": 0xF39C12,  # Orange
            # Channel events
            "channel_create": 0x2ECC71,  # Green
            "channel_delete": 0xE74C3C,  # Red
            "channel_update": 0xF39C12,  # Orange
            "thread_create": 0x2ECC71,  # Green
            "thread_delete": 0xE74C3C,  # Red
            "thread_update": 0x3498DB,  # Blue
            "thread_member_join": 0x2ECC71,  # Green
            "thread_member_leave": 0xE67E22,  # Dark orange
            "forum_post_create": 0x2ECC71,  # Green
            "forum_post_delete": 0xE74C3C,  # Red
            "forum_post_update": 0x3498DB,  # Blue
            # Role events
            "role_create": 0x9B59B6,  # Purple
            "role_delete": 0xE74C3C,  # Red
            "role_update": 0xF39C12,  # Orange
            # Guild events
            "guild_update": 0x3498DB,  # Blue
            "emoji_update": 0xF39C12,  # Orange
            "sticker_update": 0x9B59B6,  # Purple
            "invite_create": 0x2ECC71,  # Green
            "invite_delete": 0xE74C3C,  # Red
            "guild_scheduled_event_create": 0x2ECC71,  # Green
            "guild_scheduled_event_update": 0x3498DB,  # Blue
            "guild_scheduled_event_delete": 0xE74C3C,  # Red
            "stage_instance_create": 0x2ECC71,  # Green
            "stage_instance_update": 0x3498DB,  # Blue
            "stage_instance_delete": 0xE74C3C,  # Red
            # Command events
            "command_use": 0x2ECC71,  # Green
            "command_error": 0xE74C3C,  # Red
            "application_cmd": 0x3498DB,  # Blue
            "application_cmd_permissions_update": 0xF39C12,  # Orange
            # Voice events
            "voice_state_update": 0x9B59B6,  # Purple
            "voice_update": 0x3498DB,  # Blue
            # Reaction events
            "reaction_add": 0x2ECC71,  # Green
            "reaction_remove": 0xE67E22,  # Dark orange
            "reaction_clear": 0xF39C12,  # Orange
            # Integration, webhook, AutoMod, soundboard events
            "integration_create": 0x2ECC71,
            "integration_update": 0x3498DB,
            "integration_delete": 0xE74C3C,
            "webhook_update": 0xF39C12,
            "automod_rule_create": 0x2ECC71,
            "automod_rule_update": 0xF39C12,
            "automod_rule_delete": 0xE74C3C,
            "automod_action": 0xE74C3C,
            "soundboard_sound_create": 0x2ECC71,
            "soundboard_sound_update": 0x3498DB,
            "soundboard_sound_delete": 0xE74C3C,
            # Default
            "default": 0x3498DB,  # Blue
        }

        return color_map.get(event_type, color_map["default"])

    def create_embed(
        self,
        event_type: str,
        description: str,
        **kwargs,
    ) -> discord.Embed:
        """
        Create a standardized, visually appealing embed for logging with Discord limit handling.

        This method now includes comprehensive size checking and will intelligently handle
        content that exceeds Discord's character limits by truncating fields and descriptions.

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
            A formatted embed ready for sending that fits within Discord limits
        """
        # Try to create the embed with all content first
        embed = self._try_single_embed(event_type, description, **kwargs)

        # Set the footer with the YALC branding
        self.set_embed_footer(embed)

        # Check if the embed exceeds Discord limits after footer is added
        total_size = self._calculate_embed_size(embed)
        DISCORD_EMBED_LIMIT = 6000  # Discord's total embed character limit

        if total_size <= DISCORD_EMBED_LIMIT:
            return embed

        # If we're over the limit, we need to intelligently truncate content
        self.log.warning(
            f"Embed size ({total_size}) exceeds Discord limit ({DISCORD_EMBED_LIMIT}) for event_type: {event_type}. Applying intelligent truncation.",
        )

        # Create a new embed with more aggressive truncation
        embed = discord.Embed(
            title=self._get_embed_title(event_type),
            description=self._smart_truncate(description, 3500)
            if description
            else None,  # Reserve space for fields
            color=self._get_event_color(event_type),
            timestamp=datetime.datetime.now(datetime.UTC),
        )

        # Add fields with more aggressive truncation, prioritizing important fields
        important_fields = ["user", "author", "member", "channel", "role", "reason"]
        regular_fields = []
        content_fields = []

        # Categorize fields by importance
        for field_name, field_value in kwargs.items():
            if field_value is not None:
                field_name_lower = str(field_name).lower()
                if any(important in field_name_lower for important in important_fields):
                    # Important fields get priority and moderate truncation
                    if isinstance(field_value, str) and len(field_value) > 512:
                        field_value = self._smart_truncate(field_value, 509) + "..."
                    embed.add_field(
                        name=self._format_embed_field_name(field_name),
                        value=self._format_embed_field_value(field_name, field_value)[
                            :1024
                        ],
                        inline=True,
                    )
                elif field_name_lower in ["content", "message_content", "changes"]:
                    # Content fields get saved for later with heavy truncation
                    content_fields.append((field_name, field_value))
                else:
                    # Regular fields
                    regular_fields.append((field_name, field_value))

        # Add regular fields if we have space
        current_size = self._calculate_embed_size(embed)
        DISCORD_EMBED_LIMIT - current_size - 500  # Reserve space for footer and safety

        for field_name, field_value in regular_fields:
            field_value_str = self._format_embed_field_value(field_name, field_value)
            if len(field_value_str) > 256:
                field_value_str = self._smart_truncate(field_value_str, 253) + "..."

            # Estimate field size (name + value + some overhead)
            field_name_str = self._format_embed_field_name(field_name)
            field_size = len(field_name_str) + len(field_value_str) + 10

            if current_size + field_size < DISCORD_EMBED_LIMIT - 200:  # Safety margin
                embed.add_field(
                    name=field_name_str,
                    value=field_value_str,
                    inline=self._should_inline_embed_field(field_name, field_value_str),
                )
                current_size += field_size
            else:
                break  # No more space

        # Add content fields if we still have space
        for field_name, field_value in content_fields[:1]:  # Only add one content field
            current_size = self._calculate_embed_size(embed)
            available_space = DISCORD_EMBED_LIMIT - current_size - 200  # Safety margin

            if available_space > 100:  # Only if we have reasonable space
                max_content_length = min(
                    available_space - 50,
                    800,
                )  # Cap content length
                field_value_str = self._format_embed_field_value(
                    field_name,
                    field_value,
                )
                if len(field_value_str) > max_content_length:
                    field_value_str = (
                        self._smart_truncate(field_value_str, max_content_length - 3)
                        + "..."
                    )

                embed.add_field(
                    name=self._format_embed_field_name(field_name),
                    value=field_value_str,
                    inline=False,
                )
                break

        # Add truncation notice if we had to skip fields
        total_fields_available = len(kwargs)
        fields_added = len(embed.fields)

        if fields_added < total_fields_available:
            # Try to add a notice about truncated content
            current_size = self._calculate_embed_size(embed)
            if current_size + 100 < DISCORD_EMBED_LIMIT:
                skipped_count = total_fields_available - fields_added
                embed.add_field(
                    name="⚠️ Content Truncated",
                    value=f"Some content was truncated due to Discord limits. {skipped_count} field(s) omitted.",
                    inline=False,
                )

        # Set the footer
        self.set_embed_footer(embed)

        # Final size check and emergency truncation
        final_size = self._calculate_embed_size(embed)
        if final_size > DISCORD_EMBED_LIMIT:
            # Emergency truncation - remove fields from the end until we fit
            while (
                len(embed.fields) > 0
                and self._calculate_embed_size(embed) > DISCORD_EMBED_LIMIT
            ):
                embed.remove_field(-1)

            # If we still don't fit, truncate the description more aggressively
            if (
                self._calculate_embed_size(embed) > DISCORD_EMBED_LIMIT
                and embed.description
            ):
                available_desc_space = (
                    DISCORD_EMBED_LIMIT
                    - (self._calculate_embed_size(embed) - len(embed.description))
                    - 100
                )
                if available_desc_space > 50:
                    embed.description = (
                        self._smart_truncate(
                            embed.description,
                            available_desc_space - 30,
                        )
                        + "\n*...truncated*"
                    )
                else:
                    embed.description = "*Content truncated due to size limits*"

        return embed

    def set_embed_footer(
        self,
        embed: discord.Embed,
        event_time: datetime.datetime | None = None,
        label: str = "YALC Logger",
    ) -> None:
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
        formatted_time = event_time.strftime("%B %d, %Y, %I:%M %p UTC")

        # Set footer with the existing logo URL
        embed.set_footer(
            text=f"{label} • {formatted_time}",
            icon_url="https://cdn-icons-png.flaticon.com/512/928/928797.png",  # Preserved existing logo
        )

    async def cog_unload(self) -> None:
        """Clean up when cog is unloaded."""
        try:
            dashboard_cog = self.bot.get_cog("Dashboard")
            if dashboard_cog and hasattr(dashboard_cog, "rpc"):
                dashboard_cog.rpc.third_parties_handler.remove_third_party(self)
        except Exception as e:
            self.log.error(f"Error removing dashboard integration: {e}", exc_info=True)

        # Clean up voice sessions and other resources
        try:
            # Clear active voice sessions from all guilds to prevent memory leaks
            for guild in self.bot.guilds:
                async with self.config.guild(guild).voice_sessions() as sessions:
                    sessions.clear()
        except Exception as e:
            self.log.error(
                f"Error clearing voice sessions during unload: {e}",
                exc_info=True,
            )

        # Clean up any other resources
        await super().cog_unload()

    async def cog_load(self) -> None:
        """Register all YALC events as modlog case types and dashboard third party."""
        # Register modlog case types
        case_types = []
        for event, (emoji, description) in self.event_descriptions.items():
            case_types.append(
                {
                    "name": event,
                    "default_setting": False,
                    "image": emoji,
                    "case_str": description,
                },
            )
        try:
            await modlog.register_casetypes(case_types)
            self.log.info("Registered all YALC events as modlog case types.")
        except Exception as e:
            self.log.error(f"Failed to register YALC case types: {e}")

        # Dashboard integration will be handled by the on_dashboard_cog_add listener
        # when the Dashboard cog loads
        self.log.info(
            "YALC cog loaded - dashboard integration will be registered when Dashboard cog loads.",
        )

    @commands.Cog.listener()
    async def on_voice_state_update(
        self,
        member: discord.Member,
        before: discord.VoiceState,
        after: discord.VoiceState,
    ):
        """Log voice channel join/leave/move events with comprehensive session tracking."""
        self.log.debug("Listener triggered: on_voice_state_update")

        if not member.guild:
            self.log.debug("No guild on member.")
            return

        try:
            event_channel = after.channel or before.channel
            # Check if we should log this event
            should_log = await self.should_log_event(
                member.guild,
                "voice_state_update",
                channel=event_channel,
                user=member,
            )
            if not should_log:
                self.log.debug(
                    "should_log_event returned False for voice_state_update.",
                )
                return

            # Get the log channel
            channel = await self.get_log_channel(member.guild, "voice_state_update")
            if not channel:
                self.log.warning("No log channel set for voice_state_update.")
                return

            # Skip if no meaningful change (e.g., just mute/deafen status)
            if (
                before.channel == after.channel
                and before.self_mute == after.self_mute
                and before.self_deaf == after.self_deaf
                and before.mute == after.mute
                and before.deaf == after.deaf
                and before.self_stream == after.self_stream
                and before.self_video == after.self_video
                and before.suppress == after.suppress
                and getattr(before, "requested_to_speak_at", None)
                == getattr(after, "requested_to_speak_at", None)
            ):
                return

            # Determine the type of voice state change
            actor_info = None
            session_info = {}

            if before.channel != after.channel:
                # Channel change (join/leave/move)
                if before.channel and after.channel:
                    # Moved between channels
                    action = "moved"
                    description = f"🔄 {member.mention} moved from {before.channel.mention} to {after.channel.mention}"

                    # Check for move in audit log
                    entry = await self._get_audit_log_entry(
                        member.guild,
                        discord.AuditLogAction.member_move,
                        target=member,
                        timeout_seconds=10,
                    )
                    if entry and entry.user:
                        actor_info = {
                            "actor": entry.user,
                            "reason": getattr(entry, "reason", None),
                            "action_type": "Moved by moderator",
                        }
                elif before.channel and not after.channel:
                    # Left voice
                    action = "left"
                    description = f"🚪 {member.mention} left {before.channel.mention}"

                    # Calculate session duration if we can estimate when they joined
                    if hasattr(member, "joined_at") and member.joined_at:
                        # This is a rough estimate - we can't know exactly when they joined voice
                        session_info["previous_channel"] = before.channel.name
                        session_info["channel_type"] = str(before.channel.type)

                        # Check if user was disconnected by moderator
                        entry = await self._get_audit_log_entry(
                            member.guild,
                            discord.AuditLogAction.member_disconnect,
                            target=member,
                            timeout_seconds=10,
                        )
                        if entry and entry.user:
                            actor_info = {
                                "actor": entry.user,
                                "reason": getattr(entry, "reason", None),
                                "action_type": "Disconnected by moderator",
                            }
                elif after.channel and not before.channel:
                    # Joined voice
                    action = "joined"
                    description = f"🎧 {member.mention} joined {after.channel.mention}"
                    session_info["joined_channel"] = after.channel.name
                    session_info["channel_type"] = str(after.channel.type)
            else:
                # State change within same channel (mute/deafen/stream/video)
                action = "state_changed"
                changes = []

                if before.self_mute != after.self_mute:
                    changes.append(f"Self Mute: {before.self_mute} → {after.self_mute}")
                if before.self_deaf != after.self_deaf:
                    changes.append(
                        f"Self Deafen: {before.self_deaf} → {after.self_deaf}",
                    )
                if before.mute != after.mute:
                    changes.append(f"Server Mute: {before.mute} → {after.mute}")
                if before.deaf != after.deaf:
                    changes.append(f"Server Deafen: {before.deaf} → {after.deaf}")
                if before.self_stream != after.self_stream:
                    changes.append(
                        f"Streaming: {before.self_stream} → {after.self_stream}",
                    )
                if before.self_video != after.self_video:
                    changes.append(f"Camera: {before.self_video} → {after.self_video}")
                if before.suppress != after.suppress:
                    changes.append(f"Suppressed: {before.suppress} → {after.suppress}")
                if getattr(before, "requested_to_speak_at", None) != getattr(
                    after,
                    "requested_to_speak_at",
                    None,
                ):
                    before_request = getattr(before, "requested_to_speak_at", None)
                    after_request = getattr(after, "requested_to_speak_at", None)
                    changes.append(
                        "Request to Speak: "
                        f"{discord.utils.format_dt(before_request, 'R') if before_request else 'None'} → "
                        f"{discord.utils.format_dt(after_request, 'R') if after_request else 'None'}",
                    )

                if not changes:
                    return  # No meaningful changes

                channel_mention = after.channel.mention if after.channel else "voice"
                description = (
                    f"🎛️ {member.mention} voice state updated in {channel_mention}"
                )
                session_info["state_changes"] = changes

                # Check if mute/deafen was done by moderator
                if before.mute != after.mute or before.deaf != after.deaf:
                    entry = await self._get_audit_log_entry(
                        member.guild,
                        discord.AuditLogAction.member_update,
                        target=member,
                        timeout_seconds=10,
                    )
                    if entry and entry.user != member:
                        actor_info = {
                            "actor": entry.user,
                            "reason": getattr(entry, "reason", None),
                            "action_type": "Voice state modified by moderator",
                        }

            # Create the embed
            embed = self.create_embed("voice_state_update", description)

            # Add member information
            embed.add_field(
                name="Member",
                value=f"{member.mention} (`{member}`, ID: `{member.id}`)",
                inline=True,
            )

            # Add channel information
            if action in ["joined", "left", "moved"]:
                if before.channel and after.channel:
                    embed.add_field(
                        name="Channels",
                        value=f"**From:** {before.channel.mention} (`{before.channel.name}`)\n**To:** {after.channel.mention} (`{after.channel.name}`)",
                        inline=True,
                    )
                elif before.channel:
                    embed.add_field(
                        name="Left Channel",
                        value=f"{before.channel.mention} (`{before.channel.name}`)",
                        inline=True,
                    )
                elif after.channel:
                    embed.add_field(
                        name="Joined Channel",
                        value=f"{after.channel.mention} (`{after.channel.name}`)",
                        inline=True,
                    )

            # Add voice state information
            if after.channel:
                voice_states = []
                if after.self_mute:
                    voice_states.append("🔇 Self Muted")
                if after.self_deaf:
                    voice_states.append("🔈 Self Deafened")
                if after.mute:
                    voice_states.append("🚫 Server Muted")
                if after.deaf:
                    voice_states.append("🔕 Server Deafened")
                if after.self_stream:
                    voice_states.append("📺 Streaming")
                if after.self_video:
                    voice_states.append("📹 Camera On")
                if after.suppress:
                    voice_states.append("🤐 Suppressed")
                if getattr(after, "requested_to_speak_at", None):
                    voice_states.append("🙋 Requested to Speak")

                if voice_states:
                    embed.add_field(
                        name="Voice State",
                        value=" • ".join(voice_states),
                        inline=False,
                    )

            # Add session information
            if session_info and "state_changes" in session_info:
                embed.add_field(
                    name="Changes",
                    value="\n".join(
                        f"• {change}" for change in session_info["state_changes"]
                    ),
                    inline=False,
                )

            # Add actor information if available
            if actor_info:
                embed.add_field(
                    name="Action By",
                    value=f"{actor_info['actor'].mention} (`{actor_info['actor']}`, ID: `{actor_info['actor'].id}`)",
                    inline=True,
                )

                embed.add_field(
                    name="Action Type",
                    value=actor_info["action_type"],
                    inline=True,
                )

                if actor_info.get("reason"):
                    embed.add_field(
                        name="Reason",
                        value=actor_info["reason"],
                        inline=False,
                    )
            else:
                embed.add_field(
                    name="Action Type",
                    value="User-initiated"
                    if action != "state_changed"
                    else "State change",
                    inline=True,
                )

            # Add timestamp
            embed.add_field(
                name="Timestamp",
                value=discord.utils.format_dt(
                    datetime.datetime.now(datetime.UTC),
                    style="F",
                ),
                inline=True,
            )

            # Add user thumbnail
            settings = await self.config.guild(member.guild).all()
            if settings.get("include_thumbnails", True) and member.display_avatar:
                embed.set_thumbnail(url=member.display_avatar.url)

            # Set footer
            self.set_embed_footer(embed, label="YALC Logger • Voice State Update")

            await self.safe_send(channel, embed=embed)

            # Integrated voice session tracking
            try:
                user_id = member.id
                guild = member.guild

                if action == "joined":
                    # User joined voice - start session tracking
                    if after.channel:
                        current_channel_id = after.channel.id
                        await self._start_voice_session(
                            guild,
                            user_id,
                            current_channel_id,
                        )
                        await self._log_voice_event(
                            guild,
                            user_id,
                            "session_start",
                            channel_id=current_channel_id,
                        )

                elif action == "left":
                    # User left voice - end session tracking
                    if before.channel:
                        previous_channel_id = before.channel.id
                        await self._end_voice_session(
                            guild,
                            user_id,
                            previous_channel_id,
                        )
                        # Session end logging is handled within _end_voice_session

                elif action == "moved":
                    # User moved between channels - update session tracking
                    if before.channel and after.channel:
                        old_channel_id = before.channel.id
                        new_channel_id = after.channel.id

                        # End session in old channel and start new one
                        await self._end_voice_session(guild, user_id, old_channel_id)
                        await self._start_voice_session(guild, user_id, new_channel_id)

                        # Log the channel move
                        await self._log_voice_event(
                            guild,
                            user_id,
                            "channel_move",
                            channel_id=new_channel_id,
                        )

                elif action == "state_changed":
                    # State changes within same channel - track if user is in voice
                    current_channel_id = None
                    if after.channel and after.channel.id:
                        current_channel_id = after.channel.id

                        # Check if user is actively in voice session
                        async with self.config.guild(
                            guild,
                        ).voice_sessions() as sessions:
                            session_key = str(user_id)
                            if session_key in sessions:
                                session = sessions[session_key]
                                if session.get("active", False):
                                    # Update channel if necessary
                                    if session["channel_id"] != current_channel_id:
                                        await self._log_voice_event(
                                            guild,
                                            user_id,
                                            "channel_move",
                                            channel_id=current_channel_id,
                                        )

            except Exception as e:
                self.log.error(f"Error in voice session tracking: {e}", exc_info=True)

        except Exception as e:
            self.log.error(f"Failed to log voice_state_update: {e}", exc_info=True)

    async def _log_message_pin(self, message: discord.Message) -> None:
        """Log message pin events with audit log integration."""
        if not message.guild:
            return
        try:
            should_log = await self.should_log_event(
                message.guild,
                "message_pin",
                user=message.author,
                message=message,
            )
            if not should_log:
                return
            channel = await self.get_log_channel(message.guild, "message_pin")
            if not channel:
                return

            # Try to get audit log information about who pinned the message
            entry = await self._get_audit_log_entry(
                message.guild,
                discord.AuditLogAction.message_pin,
                target=message.author,
                timeout_seconds=10,
            )

            embed = self.create_embed(
                "message_pin",
                f"📌 Message pinned in {message.channel.mention}",
                user=f"{message.author.mention} ({message.author.id})",
                content=message.content[:200] if message.content else "*No content*",
                timestamp=discord.utils.format_dt(message.created_at, "f"),
            )

            embed.add_field(
                name="Jump URL",
                value=f"[View Message]({message.jump_url})",
                inline=True,
            )

            if entry and entry.user:
                embed.add_field(
                    name="Pinned By",
                    value=f"{entry.user.mention} (`{entry.user}`, ID: `{entry.user.id}`)",
                    inline=True,
                )
                if entry.reason:
                    embed.add_field(name="Reason", value=entry.reason, inline=False)

            # Include user thumbnail
            settings = await self.config.guild(message.guild).all()
            if (
                settings.get("include_thumbnails", True)
                and message.author.display_avatar
            ):
                embed.set_thumbnail(url=message.author.display_avatar.url)

            await self.safe_send(channel, embed=embed)

        except Exception as e:
            self.log.error(f"Failed to log message_pin: {e}")

    async def _log_message_unpin(self, message: discord.Message) -> None:
        """Log message unpin events with audit log integration."""
        if not message.guild:
            return
        try:
            should_log = await self.should_log_event(
                message.guild,
                "message_unpin",
                user=message.author,
                message=message,
            )
            if not should_log:
                return
            channel = await self.get_log_channel(message.guild, "message_unpin")
            if not channel:
                return

            # Try to get audit log information about who unpinned the message
            entry = await self._get_audit_log_entry(
                message.guild,
                discord.AuditLogAction.message_unpin,
                target=message.author,
                timeout_seconds=10,
            )

            embed = self.create_embed(
                "message_unpin",
                f"📍 Message unpinned in {message.channel.mention}",
                user=f"{message.author.mention} ({message.author.id})",
                content=message.content[:200] if message.content else "*No content*",
                timestamp=discord.utils.format_dt(message.created_at, "f"),
            )

            embed.add_field(
                name="Jump URL",
                value=f"[View Message]({message.jump_url})",
                inline=True,
            )

            if entry and entry.user:
                embed.add_field(
                    name="Unpinned By",
                    value=f"{entry.user.mention} (`{entry.user}`, ID: `{entry.user.id}`)",
                    inline=True,
                )
                if entry.reason:
                    embed.add_field(name="Reason", value=entry.reason, inline=False)

            # Include user thumbnail
            settings = await self.config.guild(message.guild).all()
            if (
                settings.get("include_thumbnails", True)
                and message.author.display_avatar
            ):
                embed.set_thumbnail(url=message.author.display_avatar.url)

            await self.safe_send(channel, embed=embed)

        except Exception as e:
            self.log.error(f"Failed to log message_unpin: {e}")

    @commands.Cog.listener()
    async def on_reaction_add(
        self,
        reaction: discord.Reaction,
        user: discord.User,
    ) -> None:
        """Log reaction add events."""
        self.log.debug("Listener triggered: on_reaction_add")
        if not reaction.message.guild:
            return
        try:
            should_log = await self.should_log_event(
                reaction.message.guild,
                "reaction_add",
                user=user,
                message=reaction.message,
            )
            if not should_log:
                return
            channel = await self.get_log_channel(reaction.message.guild, "reaction_add")
            if not channel:
                return

            # Get emoji representation
            emoji_str = (
                str(reaction.emoji)
                if hasattr(reaction.emoji, "name")
                else reaction.emoji
            )
            if hasattr(reaction.emoji, "id") and reaction.emoji.id:
                emoji_str = f"<:{reaction.emoji.name}:{reaction.emoji.id}>"
            elif isinstance(reaction.emoji, str):
                emoji_str = reaction.emoji

            embed = self.create_embed(
                "reaction_add",
                f"👍 {user.mention} added reaction {emoji_str} to a message",
                user=f"{user.mention} ({user.id})",
                reaction=f"{emoji_str} ({reaction.emoji})",
                channel=f"{reaction.message.channel.mention}",
                message_content=reaction.message.content[:100]
                if reaction.message.content
                else "*No text content*",
            )

            embed.add_field(
                name="Message Link",
                value=f"[View Message]({reaction.message.jump_url})",
                inline=False,
            )

            # Include user thumbnail
            settings = await self.config.guild(reaction.message.guild).all()
            if settings.get("include_thumbnails", True) and user.display_avatar:
                embed.set_thumbnail(url=user.display_avatar.url)

            await self.safe_send(channel, embed=embed)

        except Exception as e:
            self.log.error(f"Failed to log reaction_add: {e}")

    @commands.Cog.listener()
    async def on_reaction_remove(
        self,
        reaction: discord.Reaction,
        user: discord.User,
    ) -> None:
        """Log reaction remove events."""
        self.log.debug("Listener triggered: on_reaction_remove")
        if not reaction.message.guild:
            return
        try:
            should_log = await self.should_log_event(
                reaction.message.guild,
                "reaction_remove",
                user=user,
                message=reaction.message,
            )
            if not should_log:
                return
            channel = await self.get_log_channel(
                reaction.message.guild,
                "reaction_remove",
            )
            if not channel:
                return

            # Get emoji representation
            emoji_str = (
                str(reaction.emoji)
                if hasattr(reaction.emoji, "name")
                else reaction.emoji
            )
            if hasattr(reaction.emoji, "id") and reaction.emoji.id:
                emoji_str = f"<:{reaction.emoji.name}:{reaction.emoji.id}>"
            elif isinstance(reaction.emoji, str):
                emoji_str = reaction.emoji

            embed = self.create_embed(
                "reaction_remove",
                f"👎 {user.mention} removed reaction {emoji_str} from a message",
                user=f"{user.mention} ({user.id})",
                reaction=f"{emoji_str} ({reaction.emoji})",
                channel=f"{reaction.message.channel.mention}",
                message_content=reaction.message.content[:100]
                if reaction.message.content
                else "*No text content*",
            )

            embed.add_field(
                name="Message Link",
                value=f"[View Message]({reaction.message.jump_url})",
                inline=False,
            )

            # Include user thumbnail
            settings = await self.config.guild(reaction.message.guild).all()
            if settings.get("include_thumbnails", True) and user.display_avatar:
                embed.set_thumbnail(url=user.display_avatar.url)

            await self.safe_send(channel, embed=embed)

        except Exception as e:
            self.log.error(f"Failed to log reaction_remove: {e}")

    @commands.Cog.listener()
    async def on_reaction_clear(
        self,
        message: discord.Message,
        reactions: list,
    ) -> None:
        """Log reaction clear events."""
        self.log.debug("Listener triggered: on_reaction_clear")
        if not message.guild:
            return
        try:
            should_log = await self.should_log_event(
                message.guild,
                "reaction_clear",
                message=message,
            )
            if not should_log:
                return
            channel = await self.get_log_channel(message.guild, "reaction_clear")
            if not channel:
                return

            # Analyze reactions that were cleared
            unique_emoji = {
                str(r.emoji) if hasattr(r.emoji, "name") else r.emoji for r in reactions
            }

            embed = self.create_embed(
                "reaction_clear",
                f"🧹 All reactions cleared from message in {message.channel.mention}",
                cleared_reactions=f"**{len(reactions)}** total reactions ({len(unique_emoji)} unique emojis)",
                message_content=message.content[:100]
                if message.content
                else "*No text content*",
                author=f"{message.author.mention} ({message.author.id})",
            )

            embed.add_field(
                name="Message Link",
                value=f"[View Message]({message.jump_url})",
                inline=False,
            )

            # Include user thumbnail
            settings = await self.config.guild(message.guild).all()
            if (
                settings.get("include_thumbnails", True)
                and message.author.display_avatar
            ):
                embed.set_thumbnail(url=message.author.display_avatar.url)

            await self.safe_send(channel, embed=embed)

        except Exception as e:
            self.log.error(f"Failed to log reaction_clear: {e}")

    @commands.Cog.listener()
    async def on_integration_create(self, integration: discord.Integration) -> None:
        """Log integration creation events."""
        self.log.debug("Listener triggered: on_integration_create")
        if not integration.guild:
            return
        try:
            should_log = await self.should_log_event(
                integration.guild,
                "integration_create",
            )
            if not should_log:
                return
            channel = await self.get_log_channel(
                integration.guild,
                "integration_create",
            )
            if not channel:
                return

            # Try to get audit log information
            entry = await self._get_audit_log_entry(
                integration.guild,
                discord.AuditLogAction.integration_create,
                timeout_seconds=10,
            )

            embed = self.create_embed(
                "integration_create",
                f"🔗 Integration created: **{integration.name}**",
                integration_type=getattr(
                    integration.type,
                    "name",
                    str(integration.type),
                ),
                enabled=integration.enabled,
            )

            if entry and entry.user:
                embed.add_field(
                    name="Created By",
                    value=f"{entry.user.mention} (`{entry.user}`, ID: `{entry.user.id}`)",
                    inline=True,
                )

            embed.set_footer(text=f"Integration ID: {integration.id}")

            await self.safe_send(channel, embed=embed)

        except Exception as e:
            self.log.error(f"Failed to log integration_create: {e}")

    @commands.Cog.listener()
    async def on_integration_update(self, integration: discord.Integration) -> None:
        """Log integration update events."""
        self.log.debug("Listener triggered: on_integration_update")
        if not integration.guild:
            return
        try:
            should_log = await self.should_log_event(
                integration.guild,
                "integration_update",
            )
            if not should_log:
                return
            channel = await self.get_log_channel(
                integration.guild,
                "integration_update",
            )
            if not channel:
                return

            # Try to get audit log information
            entry = await self._get_audit_log_entry(
                integration.guild,
                discord.AuditLogAction.integration_update,
                timeout_seconds=10,
            )

            embed = self.create_embed(
                "integration_update",
                f"🔄 Integration updated: **{integration.name}**",
            )
            embed.add_field(name="Type", value=str(integration.type), inline=True)
            embed.add_field(name="Enabled", value=str(integration.enabled), inline=True)

            if entry and entry.user:
                embed.add_field(
                    name="Updated By",
                    value=f"{entry.user.mention} (`{entry.user}`, ID: `{entry.user.id}`)",
                    inline=True,
                )
                if entry.reason:
                    embed.add_field(name="Reason", value=entry.reason, inline=False)

            embed.set_footer(text=f"Integration ID: {integration.id}")

            await self.safe_send(channel, embed=embed)

        except Exception as e:
            self.log.error(f"Failed to log integration_update: {e}")

    @commands.Cog.listener()
    async def on_raw_integration_delete(self, payload) -> None:
        """Log integration deletion events."""
        self.log.debug("Listener triggered: on_raw_integration_delete")
        guild = self.bot.get_guild(getattr(payload, "guild_id", 0))
        if not guild:
            return
        try:
            should_log = await self.should_log_event(guild, "integration_delete")
            if not should_log:
                return
            channel = await self.get_log_channel(guild, "integration_delete")
            if not channel:
                return

            # Try to get audit log information
            entry = await self._get_audit_log_entry(
                guild,
                discord.AuditLogAction.integration_delete,
                timeout_seconds=10,
            )
            integration_id = getattr(payload, "integration_id", None)
            integration_name = (
                f"ID `{integration_id}`" if integration_id else "Unknown integration"
            )
            if entry and entry.target:
                integration_name = (
                    getattr(entry.target, "name", None) or integration_name
                )

            embed = self.create_embed(
                "integration_delete",
                f"🗑️ Integration deleted: **{integration_name}**",
            )
            if integration_id:
                embed.add_field(
                    name="Integration ID",
                    value=f"`{integration_id}`",
                    inline=True,
                )

            if entry and entry.user:
                embed.add_field(
                    name="Deleted By",
                    value=f"{entry.user.mention} (`{entry.user}`, ID: `{entry.user.id}`)",
                    inline=True,
                )
                if entry.reason:
                    embed.add_field(name="Reason", value=entry.reason, inline=False)

            if integration_id:
                embed.set_footer(text=f"Integration ID: {integration_id}")

            await self.safe_send(channel, embed=embed)

        except Exception as e:
            self.log.error(f"Failed to log integration_delete: {e}")

    @commands.Cog.listener()
    async def on_webhooks_update(self, channel: discord.abc.GuildChannel) -> None:
        """Log webhook update events for the specified channel."""
        self.log.debug("Listener triggered: on_webhooks_update")
        if not channel.guild:
            return
        try:
            should_log = await self.should_log_event(
                channel.guild,
                "webhook_update",
                channel=channel,
            )
            if not should_log:
                return
            log_channel = await self.get_log_channel(channel.guild, "webhook_update")
            if not log_channel:
                return

            # Try to get audit log information about webhook updates
            entry = await self._get_audit_log_entry(
                channel.guild,
                discord.AuditLogAction.webhook_update,
                timeout_seconds=10,
            )

            embed = self.create_embed(
                "webhook_update",
                f"🪝 Webhooks updated in {channel.mention}",
            )

            embed.add_field(
                name="Channel",
                value=f"{channel.mention} (`{channel.name}`, ID: `{channel.id}`)",
                inline=True,
            )

            if entry and entry.user:
                embed.add_field(
                    name="Updated By",
                    value=f"{entry.user.mention} (`{entry.user}`, ID: `{entry.user.id}`)",
                    inline=True,
                )

            embed.set_footer(text=f"Channel ID: {channel.id}")

            await self.safe_send(log_channel, embed=embed)

        except Exception as e:
            self.log.error(f"Failed to log webhook_update: {e}")

    @commands.Cog.listener()
    async def on_automod_rule_create(self, rule: discord.AutoModRule) -> None:
        """Log AutoMod rule creation events."""
        self.log.debug("Listener triggered: on_automod_rule_create")
        if not rule.guild:
            return
        try:
            should_log = await self.should_log_event(rule.guild, "automod_rule_create")
            if not should_log:
                return
            channel = await self.get_log_channel(rule.guild, "automod_rule_create")
            if not channel:
                return

            # Try to get audit log information
            entry = await self._get_audit_log_entry(
                rule.guild,
                discord.AuditLogAction.automod_rule_create,
                timeout_seconds=10,
            )

            embed = self.create_embed(
                "automod_rule_create",
                f"🛡️ AutoMod rule created: **{rule.name}**",
            )

            embed.add_field(name="Rule Name", value=rule.name, inline=True)
            embed.add_field(
                name="Trigger",
                value=str(rule.trigger).replace("_", " ").title(),
                inline=True,
            )

            # Get rule actions
            actions_list = []
            for action in rule.actions:
                if hasattr(action, "type"):
                    action_type = str(action.type).replace("_", " ").title()
                    actions_list.append(f"• {action_type}")
                else:
                    actions_list.append(f"• {action}")

            if actions_list:
                embed.add_field(
                    name="Actions",
                    value="\n".join(actions_list[:5]),
                    inline=False,
                )

            if hasattr(rule, "enabled") and rule.enabled is not None:
                embed.add_field(
                    name="Enabled",
                    value="✅ Yes" if rule.enabled else "❌ No",
                    inline=True,
                )

            if entry and entry.user:
                embed.add_field(
                    name="Created By",
                    value=f"{entry.user.mention} (`{entry.user}`, ID: `{entry.user.id}`)",
                    inline=True,
                )

            embed.set_footer(text=f"Rule ID: {rule.id}")

            await self.safe_send(channel, embed=embed)

        except Exception as e:
            self.log.error(f"Failed to log automod_rule_create: {e}")

    @commands.Cog.listener()
    async def on_automod_rule_update(self, rule: discord.AutoModRule) -> None:
        """Log AutoMod rule update events."""
        self.log.debug("Listener triggered: on_automod_rule_update")
        if not rule.guild:
            return
        try:
            should_log = await self.should_log_event(rule.guild, "automod_rule_update")
            if not should_log:
                return
            channel = await self.get_log_channel(rule.guild, "automod_rule_update")
            if not channel:
                return

            # Try to get audit log information
            entry = await self._get_audit_log_entry(
                rule.guild,
                discord.AuditLogAction.automod_rule_update,
                target=rule,
                timeout_seconds=10,
            )

            embed = self.create_embed(
                "automod_rule_update",
                f"🔄 AutoMod rule updated: **{rule.name}**",
            )

            embed.add_field(name="Rule Name", value=rule.name, inline=True)
            embed.add_field(
                name="Enabled",
                value="✅ Yes" if rule.enabled else "❌ No",
                inline=True,
            )
            embed.add_field(
                name="Trigger",
                value=str(rule.trigger).replace("_", " ").title(),
                inline=True,
            )

            actions_list = []
            for action in rule.actions:
                action_type = (
                    str(getattr(action, "type", action)).replace("_", " ").title()
                )
                actions_list.append(f"• {action_type}")
            if actions_list:
                embed.add_field(
                    name="Actions",
                    value="\n".join(actions_list[:5]),
                    inline=False,
                )

            if entry and entry.user:
                embed.add_field(
                    name="Updated By",
                    value=f"{entry.user.mention} (`{entry.user}`, ID: `{entry.user.id}`)",
                    inline=True,
                )
                if entry.reason:
                    embed.add_field(name="Reason", value=entry.reason, inline=False)

            embed.set_footer(text=f"Rule ID: {rule.id}")

            await self.safe_send(channel, embed=embed)

        except Exception as e:
            self.log.error(f"Failed to log automod_rule_update: {e}")

    @commands.Cog.listener()
    async def on_automod_rule_delete(self, rule: discord.AutoModRule) -> None:
        """Log AutoMod rule deletion events."""
        self.log.debug("Listener triggered: on_automod_rule_delete")
        if not rule.guild:
            return
        try:
            should_log = await self.should_log_event(rule.guild, "automod_rule_delete")
            if not should_log:
                return
            channel = await self.get_log_channel(rule.guild, "automod_rule_delete")
            if not channel:
                return

            # Try to get audit log information
            entry = await self._get_audit_log_entry(
                rule.guild,
                discord.AuditLogAction.automod_rule_delete,
                timeout_seconds=10,
            )

            embed = self.create_embed(
                "automod_rule_delete",
                f"🗑️ AutoMod rule deleted: **{rule.name}**",
            )

            embed.add_field(name="Rule Name", value=rule.name, inline=True)
            embed.add_field(
                name="Trigger",
                value=str(rule.trigger).replace("_", " ").title(),
                inline=True,
            )

            if entry and entry.user:
                embed.add_field(
                    name="Deleted By",
                    value=f"{entry.user.mention} (`{entry.user}`, ID: `{entry.user.id}`)",
                    inline=True,
                )

            embed.set_footer(text=f"Rule ID: {rule.id}")

            await self.safe_send(channel, embed=embed)

        except Exception as e:
            self.log.error(f"Failed to log automod_rule_delete: {e}")

    @commands.Cog.listener()
    async def on_automod_action(self, execution: discord.AutoModAction) -> None:
        """Log AutoMod action execution events."""
        self.log.debug("Listener triggered: on_automod_action")
        if not execution.guild:
            return
        try:
            should_log = await self.should_log_event(
                execution.guild,
                "automod_action",
                user=execution.member,
                message=execution.content,
            )
            if not should_log:
                return
            channel = await self.get_log_channel(execution.guild, "automod_action")
            if not channel:
                return

            embed = self.create_embed(
                "automod_action",
                f"⚔️ AutoMod action triggered: **{execution.rule_trigger_type.name}**",
                rule_name=execution.rule_trigger_keyword or "N/A",
                channel=execution.channel.mention if execution.channel else "Unknown",
            )

            if execution.member:
                embed.add_field(
                    name="Targeted User",
                    value=f"{execution.member.mention} (`{execution.member}`, ID: `{execution.member.id}`)",
                    inline=True,
                )

            embed.add_field(
                name="Action Type",
                value=str(execution.action.type).replace("_", " ").title(),
                inline=True,
            )

            if execution.content and len(execution.content) > 0:
                content_preview = (
                    execution.content[:500]
                    if len(execution.content) > 500
                    else execution.content
                )
                embed.add_field(
                    name="Flagged Content",
                    value=f"```\n{content_preview}\n```",
                    inline=False,
                )

            if execution.action.metadatas:
                metadata_info = []
                for metadata in execution.action.metadatas:
                    if hasattr(metadata, "channel_id"):
                        channel_obj = execution.guild.get_channel(metadata.channel_id)
                        metadata_info.append(
                            f"• Timeout in {channel_obj.mention}"
                            if channel_obj
                            else f"• Timeout in channel {metadata.channel_id}",
                        )
                    elif hasattr(metadata, "duration"):
                        duration_str = ""
                        if metadata.duration:
                            seconds = metadata.duration.seconds
                            if seconds < 3600:
                                duration_str = f"{seconds // 60}m {seconds % 60}s"
                            else:
                                duration_str = (
                                    f"{seconds // 3600}h {(seconds % 3600) // 60}m"
                                )
                        metadata_info.append(f"• Duration: {duration_str}")

                if metadata_info:
                    embed.add_field(
                        name="Action Details",
                        value="\n".join(metadata_info),
                        inline=False,
                    )

            embed.set_footer(
                text=f"Rule ID: {execution.rule_id} • Match: {execution.matched_keyword or 'N/A'}",
            )

            # Include user thumbnail
            settings = await self.config.guild(execution.guild).all()
            if (
                execution.member
                and settings.get("include_thumbnails", True)
                and execution.member.display_avatar
            ):
                embed.set_thumbnail(url=execution.member.display_avatar.url)

            await self.safe_send(channel, embed=embed)

        except Exception as e:
            self.log.error(f"Failed to log automod_action: {e}")

    @commands.Cog.listener()
    async def on_thread_create(self, thread: discord.Thread) -> None:
        """Log thread creation events."""
        self.log.debug("Listener triggered: on_thread_create")
        if not thread.guild:
            return
        try:
            should_log = await self.should_log_event(
                thread.guild,
                "thread_create",
                channel=thread,
            )
            if not should_log:
                return
            channel = await self.get_log_channel(thread.guild, "thread_create")
            if not channel:
                return

            # Try to get audit log information
            entry = await self._get_audit_log_entry(
                thread.guild,
                discord.AuditLogAction.thread_create,
                target=thread.parent,
                timeout_seconds=10,
            )

            embed = self.create_embed(
                "thread_create",
                f"🧵 Thread created: {thread.mention}",
                thread_name=thread.name,
                parent_channel=thread.parent.mention if thread.parent else "Unknown",
                thread_type=str(thread.type).replace("_", " ").title(),
                auto_archive_duration=f"{thread.auto_archive_duration} minutes"
                if thread.auto_archive_duration
                else "Default",
            )

            if entry and entry.user:
                embed.add_field(
                    name="Created By",
                    value=f"{entry.user.mention} (`{entry.user}`, ID: `{entry.user.id}`)",
                    inline=True,
                )

            embed.set_footer(text=f"Thread ID: {thread.id}")
            await self.safe_send(channel, embed=embed)

        except Exception as e:
            self.log.error(f"Failed to log thread_create: {e}")

    @commands.Cog.listener()
    async def on_thread_delete(self, thread: discord.Thread) -> None:
        """Log thread deletion events."""
        self.log.debug("Listener triggered: on_thread_delete")
        if not thread.guild:
            return
        try:
            should_log = await self.should_log_event(
                thread.guild,
                "thread_delete",
                channel=thread,
            )
            if not should_log:
                return
            channel = await self.get_log_channel(thread.guild, "thread_delete")
            if not channel:
                return

            # Try to get audit log information
            entry = await self._get_audit_log_entry(
                thread.guild,
                discord.AuditLogAction.thread_delete,
                target=thread.parent,
                timeout_seconds=10,
            )

            embed = self.create_embed(
                "thread_delete",
                f"🗑️ Thread deleted: **{thread.name}**",
                parent_channel=thread.parent.mention if thread.parent else "Unknown",
                thread_type=str(thread.type).replace("_", " ").title(),
            )

            if entry and entry.user:
                embed.add_field(
                    name="Deleted By",
                    value=f"{entry.user.mention} (`{entry.user}`, ID: `{entry.user.id}`)",
                    inline=True,
                )

            embed.set_footer(text=f"Thread ID: {thread.id}")
            await self.safe_send(channel, embed=embed)

        except Exception as e:
            self.log.error(f"Failed to log thread_delete: {e}")

    @commands.Cog.listener()
    async def on_thread_update(
        self,
        before: discord.Thread,
        after: discord.Thread,
    ) -> None:
        """Log thread update events."""
        self.log.debug("Listener triggered: on_thread_update")
        if not before.guild:
            return
        try:
            should_log = await self.should_log_event(
                before.guild,
                "thread_update",
                channel=after,
            )
            if not should_log:
                return
            channel = await self.get_log_channel(before.guild, "thread_update")
            if not channel:
                return

            changes = []
            if before.name != after.name:
                changes.append(f"Name: `{before.name}` → `{after.name}`")
            if before.archived != after.archived:
                changes.append(f"Archived: `{before.archived}` → `{after.archived}`")
            if before.locked != after.locked:
                changes.append(f"Locked: `{before.locked}` → `{after.locked}`")
            if before.auto_archive_duration != after.auto_archive_duration:
                changes.append(
                    f"Auto Archive: `{before.auto_archive_duration}` → `{after.auto_archive_duration}` minutes",
                )

            if not changes:
                return

            # Try to get audit log information
            entry = await self._get_audit_log_entry(
                before.guild,
                discord.AuditLogAction.thread_update,
                target=after.parent,
                timeout_seconds=10,
            )

            embed = self.create_embed(
                "thread_update",
                f"🔄 Thread updated: {after.mention}",
            )

            embed.add_field(name="Changes", value="\n".join(changes), inline=False)

            if entry and entry.user:
                embed.add_field(
                    name="Updated By",
                    value=f"{entry.user.mention} (`{entry.user}`, ID: `{entry.user.id}`)",
                    inline=True,
                )

            embed.set_footer(text=f"Thread ID: {after.id}")
            await self.safe_send(channel, embed=embed)

        except Exception as e:
            self.log.error(f"Failed to log thread_update: {e}")

    @commands.Cog.listener()
    async def on_thread_member_join(self, member: discord.ThreadMember) -> None:
        """Log thread member join events."""
        self.log.debug("Listener triggered: on_thread_member_join")
        if not member.thread.guild:
            return
        try:
            should_log = await self.should_log_event(
                member.thread.guild,
                "thread_member_join",
                channel=member.thread,
            )
            if not should_log:
                return
            channel = await self.get_log_channel(
                member.thread.guild,
                "thread_member_join",
            )
            if not channel:
                return

            user = member.thread.guild.get_member(member.id)
            embed = self.create_embed(
                "thread_member_join",
                f"➡️ {user.mention if user else f'User ID: {member.id}'} joined thread {member.thread.mention}",
                thread=member.thread.name,
                user=f"{user} ({user.id})" if user else f"Unknown User ({member.id})",
            )

            await self.safe_send(channel, embed=embed)

        except Exception as e:
            self.log.error(f"Failed to log thread_member_join: {e}")

    @commands.Cog.listener()
    async def on_thread_member_remove(self, member: discord.ThreadMember) -> None:
        """Log thread member leave events."""
        self.log.debug("Listener triggered: on_thread_member_remove")
        if not member.thread.guild:
            return
        try:
            should_log = await self.should_log_event(
                member.thread.guild,
                "thread_member_leave",
                channel=member.thread,
            )
            if not should_log:
                return
            channel = await self.get_log_channel(
                member.thread.guild,
                "thread_member_leave",
            )
            if not channel:
                return

            user = member.thread.guild.get_member(member.id)
            embed = self.create_embed(
                "thread_member_leave",
                f"⬅️ {user.mention if user else f'User ID: {member.id}'} left thread {member.thread.mention}",
                thread=member.thread.name,
                user=f"{user} ({user.id})" if user else f"Unknown User ({member.id})",
            )

            await self.safe_send(channel, embed=embed)

        except Exception as e:
            self.log.error(f"Failed to log thread_member_remove: {e}")

    async def _log_voice_event(
        self,
        guild: discord.Guild,
        user_id: int,
        event_type: str,
        channel_id: int | None = None,
        duration: float | None = None,
    ):
        """Internal method to log voice session events."""
        try:
            session_data = {
                "timestamp": time.time(),
                "user_id": user_id,
                "event_type": event_type,
                "channel_id": channel_id,
                "duration": duration,
            }

            async with self.config.guild(guild).voice_events() as events:
                events.append(session_data)
                if len(events) > 50:  # Keep only last 50 events
                    events.pop(0)

        except Exception as e:
            self.log.error(f"Error logging voice event: {e}")

    async def _start_voice_session(
        self,
        guild: discord.Guild,
        user_id: int,
        channel_id: int,
    ):
        """Start a voice session for a user."""
        try:
            session_start = {
                "channel_id": channel_id,
                "start_time": time.time(),
                "active": True,
            }

            async with self.config.guild(guild).voice_sessions() as sessions:
                sessions[str(user_id)] = session_start

            self.log.debug(
                f"Started voice session for user {user_id} in channel {channel_id}",
            )

        except Exception as e:
            self.log.error(f"Error starting voice session: {e}")

    async def _end_voice_session(
        self,
        guild: discord.Guild,
        user_id: int,
        channel_id: int,
    ) -> float | None:
        """End a voice session for a user and return the duration."""
        try:
            async with self.config.guild(guild).voice_sessions() as sessions:
                if str(user_id) in sessions:
                    session = sessions[str(user_id)]
                    if session.get("active", False):
                        duration = time.time() - session["start_time"]
                        session["duration"] = duration
                        session["active"] = False
                        session["end_time"] = time.time()

                        # Log the session
                        await self._log_voice_event(
                            guild,
                            user_id,
                            "session_end",
                            channel_id=channel_id,
                            duration=duration,
                        )

                        self.log.debug(
                            f"Ended voice session for user {user_id}, duration: {duration}",
                        )
                        return duration

            return None

        except Exception as e:
            self.log.error(f"Error ending voice session: {e}")
            return None

    async def _get_voice_session_stats(self, guild: discord.Guild) -> dict:
        """Get statistics for all active voice sessions."""
        try:
            async with self.config.guild(guild).voice_sessions() as sessions:
                active_sessions = sum(
                    1 for s in sessions.values() if s.get("active", False)
                )

                stats = {
                    "active_sessions": active_sessions,
                    "total_sessions": len(sessions),
                    "sessions_by_channel": {},
                }

                # Group by channel
                for user_id, session in sessions.items():
                    if session.get("active", False):
                        channel_id = session["channel_id"]
                        if channel_id not in stats["sessions_by_channel"]:
                            stats["sessions_by_channel"][channel_id] = []
                        stats["sessions_by_channel"][channel_id].append(user_id)

                return stats

        except Exception as e:
            self.log.error(f"Error getting voice session stats: {e}")
            return {"error": str(e)}

    async def _get_recent_voice_events(
        self,
        guild: discord.Guild,
        limit: int = 10,
    ) -> list:
        """Get recent voice events."""
        try:
            async with self.config.guild(guild).voice_events() as events:
                return events[-limit:] if len(events) >= limit else events

        except Exception as e:
            self.log.error(f"Error getting recent voice events: {e}")
            return []

    async def _get_active_voice_sessions(self, guild: discord.Guild) -> list:
        """Get all currently active voice sessions."""
        try:
            async with self.config.guild(guild).voice_sessions() as sessions:
                return [
                    {
                        "user_id": int(user_id),
                        "channel_id": session["channel_id"],
                        "start_time": session["start_time"],
                        "duration": time.time() - session["start_time"],
                    }
                    for user_id, session in sessions.items()
                    if session.get("active", False)
                ]

        except Exception as e:
            self.log.error(f"Error getting active voice sessions: {e}")
            return []

    def _format_duration(self, seconds: float) -> str:
        """Format duration in seconds to a human-readable string."""
        if seconds < 60:
            return f"{int(seconds)}s"
        if seconds < 3600:
            minutes = int(seconds // 60)
            secs = int(seconds % 60)
            return f"{minutes}m {secs}s"
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        return f"{hours}h {minutes}m"

    def _format_timeout_duration(self, timeout_duration: datetime.timedelta) -> str:
        """Format timeout duration to a human-readable string."""
        seconds = timeout_duration.total_seconds()

        if seconds < 60:
            return f"{int(seconds)} second{'s' if int(seconds) != 1 else ''}"
        if seconds < 3600:
            minutes = int(seconds // 60)
            secs = int(seconds % 60)
            sec_part = f" {secs} second{'s' if secs != 1 else ''}" if secs > 0 else ""
            return f"{minutes} minute{'s' if minutes != 1 else ''}{sec_part}"
        if seconds < 86400:
            hours = int(seconds // 3600)
            minutes = int((seconds % 3600) // 60)
            min_part = (
                f" {minutes} minute{'s' if minutes != 1 else ''}" if minutes > 0 else ""
            )
            return f"{hours} hour{'s' if hours != 1 else ''}{min_part}"
        days = int(seconds // 86400)
        hours = int((seconds % 86400) // 3600)
        hour_part = f" {hours} hour{'s' if hours != 1 else ''}" if hours > 0 else ""
        return f"{days} day{'s' if days != 1 else ''}{hour_part}"

    @commands.Cog.listener()
    async def on_presence_update(self, before: discord.Member, after: discord.Member):
        """Log presence/status updates."""
        try:
            channel = await self.get_log_channel(after.guild, "presence_update")
            if not channel:
                return
            desc = (
                f"🟢 {after.mention} presence changed: {before.status} → {after.status}"
            )
            # Presence updates are user-driven, so actor is the user themselves
            embed = self.create_embed(
                "presence_update",
                desc + f" (by {after.mention} ({after}))",
            )
            await self.safe_send(channel, embed=embed)
        except Exception as e:
            self.log.error(f"Failed to log presence_update: {e}")

    @commands.Cog.listener()
    async def on_guild_integrations_update(self, guild: discord.Guild):
        """Log integration updates/removals - now using the new integration listeners for detailed logging."""
        # This listener is kept for backward compatibility, but the detailed logging
        # is now handled by the specific integration event listeners (integration_create/update/delete)
        try:
            channel = await self.get_log_channel(guild, "integration_update")
            if not channel:
                return
            desc = f"🔗 Integrations updated for {guild.name}"
            # Try to get actor from audit log
            entry = await self._get_audit_log_entry(
                guild,
                discord.AuditLogAction.integration_update,
                timeout_seconds=10,
            )
            if entry and entry.user:
                desc += f" by {entry.user.mention} ({entry.user})"
            embed = self.create_embed("integration_update", desc)
            embed.set_footer(
                text="Note: Detailed integration changes are logged separately",
            )
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
                entry = await self._get_audit_log_entry(
                    invite.guild,
                    discord.AuditLogAction.invite_create,
                    timeout_seconds=10,
                )
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
            entry = await self._get_audit_log_entry(
                invite.guild,
                discord.AuditLogAction.invite_delete,
                timeout_seconds=10,
            )
            if entry and entry.user:
                desc += f" by {entry.user.mention} ({entry.user})"
            embed = self.create_embed("invite_delete", desc)
            await self.safe_send(channel, embed=embed)
        except Exception as e:
            self.log.error(f"Failed to log invite_delete: {e}")

    @commands.Cog.listener()
    async def on_raw_app_command_permissions_update(self, payload):
        """Log application command permission changes, showing who did it if possible."""
        try:
            guild = self.bot.get_guild(getattr(payload, "guild_id", 0))
            if not guild:
                return
            if not await self.should_log_event(
                guild,
                "application_cmd_permissions_update",
            ):
                return
            channel = await self.get_log_channel(
                guild,
                "application_cmd_permissions_update",
            )
            if not channel:
                return
            command_id = getattr(payload, "command_id", None)
            desc = "⚙️ Application command permissions updated."
            if command_id:
                desc += f"\nCommand ID: `{command_id}`"
            # Try audit log for actor
            entry = await self._get_audit_log_entry(
                guild,
                discord.AuditLogAction.app_command_permission_update,
                timeout_seconds=10,
            )
            if entry and entry.user:
                desc += f" by {entry.user.mention} ({entry.user})"
            embed = self.create_embed("application_cmd_permissions_update", desc)
            await self.safe_send(channel, embed=embed)
        except Exception as e:
            self.log.error(f"Failed to log application_command_permissions_update: {e}")

    @commands.Cog.listener()
    async def on_audit_log_entry_create(self, entry):
        """Handle audit log entries for role attribution and gateway fallbacks."""
        try:
            role_create_action = self._get_audit_action("role_create")
            role_delete_action = self._get_audit_action("role_delete")
            role_update_action = self._get_audit_action("role_update")

            if role_create_action and entry.action == role_create_action:
                await self._log_role_audit_fallback(entry, "role_create")
                return

            if role_delete_action and entry.action == role_delete_action:
                await self._log_role_audit_fallback(entry, "role_delete")
                return

            # Capture role_update audit entries for real-time role logging.
            if role_update_action and entry.action == role_update_action:
                # Store audit entry temporarily with timestamp for role attribution
                role_id = entry.target.id if entry.target else None
                if role_id:
                    self.recent_audit_entries[role_id] = {
                        "entry": entry,
                        "timestamp": time.time(),
                    }

                    # Clean up old entries (older than 30 seconds) to prevent memory leaks
                    current_time = time.time()
                    expired_keys = [
                        key
                        for key, data in self.recent_audit_entries.items()
                        if current_time - data["timestamp"] > 30
                    ]
                    for key in expired_keys:
                        del self.recent_audit_entries[key]

        except Exception as e:
            self.log.error(
                f"Failed to handle audit_log_entry_create: {e}",
                exc_info=True,
            )

    # --- Event Listeners ---

    # Dashboard integration is handled by the DashboardIntegration class
    # The on_dashboard_cog_add method is inherited from DashboardIntegration

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
                    self.log.debug(
                        "Skipping Tupperbox message_delete event - direct detection.",
                    )
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
                        if any(
                            content.startswith(prefix) for prefix in custom_prefixes
                        ):
                            self.log.debug(
                                "Skipping deletion due to custom prefix match.",
                            )
                            return

            # 3. Check webhook ignore setting
            if settings.get("ignore_webhooks", False) and getattr(
                message,
                "webhook_id",
                None,
            ):
                # Additional filtering for specific webhook names
                webhook_name_filters = settings.get("webhook_name_filter", [])
                webhook = getattr(message, "webhook", None)

                if webhook and webhook_name_filters:
                    webhook_name = getattr(webhook, "name", "").lower()
                    if any(
                        filter_term.lower() in webhook_name
                        for filter_term in webhook_name_filters
                    ):
                        self.log.debug(
                            f"Skipping webhook message from filtered name: {webhook_name}",
                        )
                        return
                else:
                    self.log.debug("Skipping webhook message (all webhooks ignored).")
                    return

            # 4. Check app message ignore setting
            if settings.get("ignore_apps", True) and getattr(
                message,
                "application",
                None,
            ):
                self.log.debug("Skipping application message deletion.")
                return

            # 5. Check if we should ignore based on channel, user, or roles
            if not await self.should_log_event(
                message.guild,
                "message_delete",
                channel=message.channel,
                user=message.author,
                message=message,
            ):
                self.log.debug(
                    "should_log_event returned False - channel/user/role is ignored.",
                )
                return

            # 6. Get the appropriate log channel
            channel = await self.get_log_channel(message.guild, "message_delete")
            if not channel:
                self.log.warning("No log channel set for message_delete.")
                return

        except Exception as e:
            self.log.error(
                f"Error in pre-processing message_delete event: {e}",
                exc_info=True,
            )
            return

        # Process and log the event
        try:
            author = getattr(message, "author", None)
            content = getattr(message, "content", "")
            attachment_objects = list(getattr(message, "attachments", []) or [])
            (
                deleted_image_files,
                image_copy_notes,
            ) = await self._copy_deleted_image_attachments(
                attachment_objects,
                channel,
            )
            embeds = getattr(message, "embeds", [])
            channel_name = getattr(
                message.channel,
                "name",
                str(message.channel) if message.channel else "Unknown",
            )

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
                        timeout_seconds=10,
                    )

                    if audit_entry:
                        deletion_info = {
                            "deleted_by": audit_entry.user,
                            "reason": getattr(audit_entry, "reason", None),
                        }
                except Exception as e:
                    self.log.debug(
                        f"Could not fetch audit log for message deletion: {e}",
                    )

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
                metadata["Deleted By"] = (
                    f"{deleter.mention} (`{deleter}`, ID: `{deleter.id}`)"
                )

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
                **metadata,
            )

            # Format content with proper code blocks for different content types
            if content:
                # Use syntax highlighting for code blocks if detected
                if content.startswith("```") and content.endswith("```"):
                    # Preserve the code block as-is
                    embed.add_field(
                        name="Content",
                        value=content[:1024]
                        if len(content) <= 1024
                        else content[:1021] + "...",
                        inline=False,
                    )
                else:
                    # Format regular text with multi-line support and proper escaping
                    formatted_content = content
                    if len(formatted_content) > 1024:
                        formatted_content = formatted_content[:1021] + "..."

                    embed.add_field(
                        name="Content",
                        value=f"```\n{formatted_content}\n```",
                        inline=False,
                    )
            else:
                embed.add_field(name="Content", value="*No text content*", inline=False)

            # Handle attachments with better formatting
            if attachment_objects:
                attachment_list = []
                for attachment in attachment_objects:
                    file_name = getattr(attachment, "filename", None) or "Attachment"
                    url = getattr(attachment, "url", None)
                    size = getattr(attachment, "size", None)
                    file_label = file_name
                    if size:
                        file_label += f" ({self._format_file_size(size)})"
                    if url:
                        attachment_list.append(f"[{file_label}]({url})")
                    else:
                        attachment_list.append(f"`{file_label}`")

                embed.add_field(
                    name=f"Attachments ({len(attachment_objects)})",
                    value="\n".join(attachment_list)
                    if len(attachment_list) <= 5
                    else "\n".join(attachment_list[:5])
                    + f"\n*...and {len(attachment_list) - 5} more*",
                    inline=False,
                )

            if image_copy_notes:
                embed.add_field(
                    name="Deleted Image Copy",
                    value="\n".join(image_copy_notes[:5])
                    + (
                        f"\n*...and {len(image_copy_notes) - 5} more notes*"
                        if len(image_copy_notes) > 5
                        else ""
                    ),
                    inline=False,
                )

            # Add embed information if message contained embeds
            if embeds:
                embed_info = []
                for i, msg_embed in enumerate(
                    embeds[:3],
                ):  # Show details for first 3 embeds
                    # Get the embed title with proper formatting
                    embed_title = getattr(msg_embed, "title", "*No title*")
                    if embed_title and len(embed_title) > 80:
                        embed_title = embed_title[:77] + "..."

                    # Format the embed details with a divider for better readability
                    embed_details = [f"**Embed {i + 1}**: {embed_title}"]
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
                                embed_details.append(
                                    f"**Author**: [{author_name}]({author_url})",
                                )
                            else:
                                embed_details.append(f"**Author**: {author_name}")

                            if author_icon:
                                embed_details.append(
                                    f"**Author Icon**: [View]({author_icon})",
                                )

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
                            embed_details.append(
                                f"• **{field_name}**{inline_status}: {field_value}",
                            )

                        # Show if there are more fields
                        if len(embed_fields) > 3:
                            embed_details.append(
                                f"*...and {len(embed_fields) - 3} more fields*",
                            )

                    # Enhanced media display
                    if getattr(msg_embed, "image", None) and getattr(
                        msg_embed.image,
                        "url",
                        None,
                    ):
                        embed_details.append(
                            f"**Image**: [View]({msg_embed.image.url})",
                        )

                    if getattr(msg_embed, "thumbnail", None) and getattr(
                        msg_embed.thumbnail,
                        "url",
                        None,
                    ):
                        embed_details.append(
                            f"**Thumbnail**: [View]({msg_embed.thumbnail.url})",
                        )

                    # Add timestamp if present
                    if getattr(msg_embed, "timestamp", None):
                        formatted_time = discord.utils.format_dt(
                            msg_embed.timestamp,
                            style="f",
                        )
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
                            embed_details.append(
                                f"**Footer Icon**: [View]({footer_icon})",
                            )

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

                        embed_details.append(
                            f"**Color**: {color_indicator} {color_hex}",
                        )

                    # Join all details together with empty line for readability
                    embed_info.append("\n".join(embed_details))

                # Show info about additional embeds
                if len(embeds) > 3:
                    embed_info.append(f"*...and {len(embeds) - 3} more embeds*")

                # Add all embed info to the logging embed
                embed.add_field(
                    name=f"Embeds ({len(embeds)})",
                    value="\n".join(embed_info),
                    inline=False,
                )

            # Channel information
            embed.add_field(
                name="Channel",
                value=f"{getattr(message.channel, 'mention', '#' + channel_name)} (`{channel_name}`)",
                inline=True,
            )

            # Include user thumbnail for better visual identification
            if (
                settings.get("include_thumbnails", True)
                and author
                and hasattr(author, "display_avatar")
                and author.display_avatar
            ):
                embed.set_thumbnail(url=author.display_avatar.url)

            # Send the log message to the configured channel
            try:
                if deleted_image_files:
                    await self.safe_send(
                        channel,
                        embed=embed,
                        files=deleted_image_files,
                    )
                else:
                    await self.safe_send(channel, embed=embed)
            finally:
                self._close_send_files(deleted_image_files)

        except Exception as e:
            self.log.error(f"Failed to log message_delete: {e}", exc_info=True)

    @commands.Cog.listener()
    async def on_message_edit(
        self,
        before: discord.Message,
        after: discord.Message,
    ) -> None:
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

            if before.pinned != after.pinned:
                if after.pinned:
                    await self._log_message_pin(after)
                else:
                    await self._log_message_unpin(after)
                return

            # 1. Check if the message_edit event is enabled
            if not settings["events"].get("message_edit", False):
                self.log.debug("message_edit event is disabled in settings.")
                return

            # 2. Enhanced Tupperbot filtering
            tupperbox_ids = settings.get("tupperbox_ids", ["239232811662311425"])
            ignore_tupperbox = settings.get("ignore_tupperbox", True)

            if ignore_tupperbox:
                # Check both the before and after states of the message
                is_before_tupperbox = await self.is_tupperbox_message(
                    before,
                    tupperbox_ids,
                )
                is_after_tupperbox = await self.is_tupperbox_message(
                    after,
                    tupperbox_ids,
                )

                if is_before_tupperbox or is_after_tupperbox:
                    self.log.debug(
                        f"Skipping Tupperbox message_edit event - Before:{is_before_tupperbox}, After:{is_after_tupperbox}",
                    )
                    return

            # 3. Check ignore lists (channel, user, role)
            if not await self.should_log_event(
                before.guild,
                "message_edit",
                channel=before.channel,
                user=before.author,
            ):
                self.log.debug(
                    "should_log_event returned False - channel/user/role is ignored.",
                )
                return

            # Check if content actually changed
            if before.content == after.content:
                # If content is the same, check if this is just an auto-embed conversion
                # Auto-embeds typically happen when Discord processes links into embeds
                # without the user actually editing the message
                if (
                    len(before.embeds) != len(after.embeds)
                    or before.embeds != after.embeds
                ):
                    # This is likely an auto-embed conversion, skip logging
                    self.log.debug(
                        "Skipping auto-embed conversion - content unchanged, only embeds different",
                    )
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
            self.log.error(
                f"Error in pre-processing message_edit event: {e}",
                exc_info=True,
            )
            return

        # Process and log the event
        try:
            # Gather comprehensive message metadata
            author = getattr(before, "author", None)
            attachments = [a.url for a in getattr(after, "attachments", [])]
            embeds = getattr(after, "embeds", [])
            channel_name = getattr(
                before.channel,
                "name",
                str(before.channel) if before.channel else "Unknown",
            )

            # Additional context for debugging
            self.log.debug(f"Logging message_edit in #{channel_name} by {author}")

            # Prepare user identification with link
            user_link = (
                f"[{author}](https://discord.com/users/{author.id})"
                if author and hasattr(author, "id")
                else "Unknown"
            )

            # Include jump URL if available
            jump_url = getattr(after, "jump_url", None)

            # Rich message metadata for comprehensive logging
            metadata = {
                "Author": f"{user_link} ({author.id})"
                if author and hasattr(author, "id")
                else "Unknown",
                "Channel": f"#{channel_name}",
            }

            # Add creation and edit timestamps if available
            if hasattr(after, "created_at") and after.created_at:
                metadata["Created"] = discord.utils.format_dt(
                    after.created_at,
                    style="F",
                )
            if hasattr(after, "edited_at") and after.edited_at:
                metadata["Edited"] = discord.utils.format_dt(after.edited_at, style="R")

            # Create a visually appealing and comprehensive embed
            embed = self.create_embed(
                "message_edit",
                f"✏️ Message edited in {getattr(before.channel, 'mention', str(before.channel))}\n\u200b",
            )

            # Add fields for metadata
            for key, value in metadata.items():
                embed.add_field(name=key, value=value, inline=True)

            # Add message content comparison (before/after)
            before_text = before.content or "No content"
            after_text = after.content or "No content"

            # Format content with proper quoting for better readability
            if len(before_text) > 1024:
                before_text = before_text[:1021] + "..."
            if len(after_text) > 1024:
                after_text = after_text[:1021] + "..."

            embed.add_field(
                name="Before",
                value=f"```\n{before_text}\n```",
                inline=False,
            )
            embed.add_field(name="After", value=f"```\n{after_text}\n```", inline=False)

            # Add jump link to original message
            if jump_url:
                embed.add_field(
                    name="Jump to Message",
                    value=f"[Click here to view the message]({jump_url})",
                    inline=False,
                )

            # Add attachment and embed information
            if attachments:
                attachment_text = "\n".join(
                    [
                        f"[Attachment {i + 1}]({url})"
                        for i, url in enumerate(attachments)
                    ],
                )
                embed.add_field(name="Attachments", value=attachment_text, inline=False)

            if embeds:
                embed_info = []
                for i, msg_embed in enumerate(
                    embeds[:3],
                ):  # Show details for first 3 embeds
                    # Get the embed title with proper formatting
                    embed_title = getattr(msg_embed, "title", "*No title*")
                    if embed_title and len(embed_title) > 80:
                        embed_title = embed_title[:77] + "..."

                    # Format the embed details with a divider for better readability
                    embed_details = [f"**Embed {i + 1}**: {embed_title}"]
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
                                embed_details.append(
                                    f"**Author**: [{author_name}]({author_url})",
                                )
                            else:
                                embed_details.append(f"**Author**: {author_name}")

                            if author_icon:
                                embed_details.append(
                                    f"**Author Icon**: [View]({author_icon})",
                                )

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
                            embed_details.append(
                                f"• **{field_name}**{inline_status}: {field_value}",
                            )

                        # Show if there are more fields
                        if len(embed_fields) > 3:
                            embed_details.append(
                                f"*...and {len(embed_fields) - 3} more fields*",
                            )

                    # Enhanced media display
                    if getattr(msg_embed, "image", None) and getattr(
                        msg_embed.image,
                        "url",
                        None,
                    ):
                        embed_details.append(
                            f"**Image**: [View]({msg_embed.image.url})",
                        )

                    if getattr(msg_embed, "thumbnail", None) and getattr(
                        msg_embed.thumbnail,
                        "url",
                        None,
                    ):
                        embed_details.append(
                            f"**Thumbnail**: [View]({msg_embed.thumbnail.url})",
                        )

                    # Add timestamp if present
                    if getattr(msg_embed, "timestamp", None):
                        formatted_time = discord.utils.format_dt(
                            msg_embed.timestamp,
                            style="f",
                        )
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
                            embed_details.append(
                                f"**Footer Icon**: [View]({footer_icon})",
                            )

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
                        elif (
                            msg_embed.color.value < 0x000080
                            or msg_embed.color.value < 0x800080
                        ):  # Teal/Cyan
                            color_indicator = "🟦"
                        else:  # Purple/Pink
                            color_indicator = "🟪"

                        embed_details.append(
                            f"**Color**: {color_indicator} {color_hex}",
                        )

                    # Join all details together with empty line for readability
                    embed_info.append("\n".join(embed_details))

                # Show info about additional embeds
                if len(embeds) > 3:
                    embed_info.append(f"*...and {len(embeds) - 3} more embeds*")

                # Add all embed info to the logging embed
                embed.add_field(
                    name=f"Embeds ({len(embeds)})",
                    value="\n".join(embed_info),
                    inline=False,
                )

            # Include user thumbnail for better visual identification
            if author and hasattr(author, "display_avatar") and author.display_avatar:
                embed.set_thumbnail(url=author.display_avatar.url)

            # Set appropriate footer with timestamp
            edit_time = (
                after.edited_at
                or after.created_at
                or datetime.datetime.now(datetime.UTC)
            )
            self.set_embed_footer(
                embed,
                event_time=edit_time,
                label="YALC Logger • Message Edit",
            )

            # Send the log embed
            await self.safe_send(channel, embed=embed)

        except Exception as e:
            self.log.error(f"Failed to log message_edit: {e}", exc_info=True)

    @commands.Cog.listener()
    async def on_bulk_message_delete(self, messages: list[discord.Message]) -> None:
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
                    self.log.debug(
                        f"Category {channel.category.id} is in the ignored categories list.",
                    )
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
                    msg
                    for msg in filtered_messages
                    if not getattr(msg, "webhook_id", None)
                ]
                filtered_out_count += original_count - len(filtered_messages)

            # Filter out app messages if configured
            if settings.get("ignore_apps", True):
                original_count = len(filtered_messages)
                filtered_messages = [
                    msg
                    for msg in filtered_messages
                    if not getattr(msg, "application", None)
                ]
                filtered_out_count += original_count - len(filtered_messages)

            # Skip logging if all messages were filtered out
            if len(filtered_messages) == 0:
                self.log.debug(
                    f"All {len(messages)} bulk deleted messages were filtered out.",
                )
                return

            # Sort messages by timestamp for chronological order
            filtered_messages.sort(key=lambda m: m.created_at)

            # Create a comprehensive log embed
            embed = self.create_embed(
                "message_bulk_delete",
                f"♻️ **{len(filtered_messages)}** messages were bulk deleted in {channel.mention}\n\u200b",
            )

            # Add metadata about the deletion
            embed.add_field(
                name="Channel",
                value=f"{channel.mention} (`{channel.name}`, ID: {channel.id})",
                inline=True,
            )

            # Add thread info if applicable
            if isinstance(channel, discord.Thread):
                parent_channel = getattr(channel, "parent", None)
                if parent_channel:
                    embed.add_field(
                        name="Parent Channel",
                        value=f"{parent_channel.mention} (`{parent_channel.name}`)",
                        inline=True,
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
                    timeout_seconds=10,
                )
            except Exception as e:
                self.log.debug(
                    f"Could not fetch audit log for bulk message delete: {e}",
                )

            if audit_entry:
                embed.add_field(
                    name="Deleted By",
                    value=f"{audit_entry.user.mention} (`{audit_entry.user}`, ID: `{audit_entry.user.id}`)",
                    inline=True,
                )

                if hasattr(audit_entry, "reason") and audit_entry.reason:
                    embed.add_field(
                        name="Reason",
                        value=audit_entry.reason,
                        inline=True,
                    )
            else:
                # If no audit log info available, indicate unknown
                embed.add_field(
                    name="Deleted By",
                    value="Unknown (audit log unavailable)",
                    inline=True,
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
                            "avatar": getattr(msg.author, "display_avatar", None),
                        }

            if authors:
                # Sort by message count (most active users first)
                sorted_authors = sorted(
                    authors.items(),
                    key=lambda x: x[1]["count"],
                    reverse=True,
                )

                authors_text = []
                for author_id, data in sorted_authors[:10]:  # Limit to top 10 authors
                    authors_text.append(
                        f"• {data['mention']} (`{data['name']}`, ID: `{data['id']}`): **{data['count']} message(s)**",
                    )

                if len(sorted_authors) > 10:
                    authors_text.append(
                        f"*...and {len(sorted_authors) - 10} more users*",
                    )

                embed.add_field(
                    name="Message Authors",
                    value="\n".join(authors_text),
                    inline=False,
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
                    name=f"First {preview_count} Messages"
                    if len(filtered_messages) > preview_count
                    else "Messages",
                    value="\n".join(preview_text) or "*No preview available*",
                    inline=False,
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
                        preview_text.append(
                            f"• **{author_name}** ({timestamp}): {content}",
                        )

                    embed.add_field(
                        name=f"Last {preview_count} Messages",
                        value="\n".join(preview_text) or "*No preview available*",
                        inline=False,
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
                user=f"{member} ({member.id})",
            )
            await self.safe_send(channel, embed=embed)
        except Exception as e:
            self.log.error(f"Failed to log member_join: {e}")

    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member) -> None:
        """Log member leave/kick events with proper kick detection."""
        self.log.debug("Listener triggered: on_member_remove")
        if not member.guild:
            self.log.debug("No guild on member.")
            return

        guild = member.guild

        # Wait a moment for audit logs to be available
        await asyncio.sleep(5)

        # Check if this was a ban (if so, we already logged it in on_member_ban)
        if guild.id in self._ban_cache and member.id in self._ban_cache[guild.id]:
            self.log.debug("Member was banned, not logging as leave/kick")
            # Clean up the ban cache entry
            self._ban_cache[guild.id].remove(member.id)
            if not self._ban_cache[guild.id]:  # Remove empty list
                del self._ban_cache[guild.id]
            return

        # Check if this was a kick by looking at audit logs
        kick_entry = None
        if guild.me.guild_permissions.view_audit_log:
            try:
                kick_entry = await self._get_audit_log_entry(
                    guild,
                    discord.AuditLogAction.kick,
                    target=member,
                    timeout_seconds=10,
                )
            except Exception as e:
                self.log.debug(f"Could not fetch audit log for kick: {e}")

        if kick_entry:
            # This was a kick
            await self._log_member_kick(member, kick_entry)
        else:
            # This was a regular leave
            await self._log_member_leave(member)

    @commands.Cog.listener()
    async def on_member_ban(self, guild: discord.Guild, user: discord.User) -> None:
        """Log member ban events and track them in ban cache."""
        self.log.debug("Listener triggered: on_member_ban")

        # Track the ban in our cache to distinguish from kicks
        if guild.id not in self._ban_cache:
            self._ban_cache[guild.id] = [user.id]
        else:
            self._ban_cache[guild.id].append(user.id)

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
            channel_name=guild.name if guild else "Unknown",
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
            channel_name=guild.name if guild else "Unknown",
        )
        await self.safe_send(channel, embed=embed)

    async def _get_audit_log_entry(
        self,
        guild: discord.Guild,
        action,
        target=None,
        timeout_seconds: int = 10,
    ):
        """Get a recent audit log entry, optionally matching by target object or ID."""
        guild_me = getattr(guild, "me", None)
        if (
            action is None
            or not guild_me
            or not guild_me.guild_permissions.view_audit_log
        ):
            return None

        cutoff = datetime.datetime.now(datetime.UTC) - datetime.timedelta(
            seconds=timeout_seconds,
        )
        recent_entries = []

        try:
            await asyncio.sleep(1)
            async for entry in guild.audit_logs(action=action, limit=50):
                if entry.created_at < cutoff:
                    break

                recent_entries.append(entry)
                if target is not None:
                    if entry.target == target:
                        return entry
                    if (
                        hasattr(entry.target, "id")
                        and hasattr(target, "id")
                        and entry.target.id == target.id
                    ):
                        return entry

            if target is None and recent_entries:
                return recent_entries[0]
            if recent_entries:
                return recent_entries[0]
        except discord.Forbidden:
            self.log.debug("No permission to view audit logs")
        except Exception as e:
            self.log.debug(f"Error fetching audit logs: {e}")

        return None

    async def _log_member_kick(self, member: discord.Member, kick_entry):
        """Log a member kick event."""
        self.log.debug("Logging member kick")
        if not await self.should_log_event(member.guild, "member_kick"):
            return

        channel = await self.get_log_channel(member.guild, "member_kick")
        if not channel:
            return

        # Create kick-specific embed
        embed = discord.Embed(
            title="👢 Member Kicked",
            description=f"{member.mention} has been kicked from the server.\n\u200b",
            color=discord.Color(0xE74C3C),  # Red color for kicks
            timestamp=datetime.datetime.now(datetime.UTC),
        )

        # Add user information
        embed.add_field(
            name="User",
            value=f"{member} ({member.id})",
            inline=True,
        )

        # Add moderator information if available
        if kick_entry and kick_entry.user:
            embed.add_field(
                name="👮 Kicked by",
                value=f"{kick_entry.user} ({kick_entry.user.id})",
                inline=True,
            )

        # Add reason if available
        if kick_entry and kick_entry.reason:
            embed.add_field(
                name="📝 Reason",
                value=kick_entry.reason,
                inline=False,
            )

        # Add join date information
        if member.joined_at:
            join_date_formatted = member.joined_at.strftime("%B %d, %Y at %I:%M %p")
            embed.add_field(
                name="📅 Originally Joined",
                value=join_date_formatted,
                inline=True,
            )

            # Calculate how long they were in the server
            time_in_server = datetime.datetime.now(datetime.UTC) - member.joined_at
            days = time_in_server.days
            if days > 0:
                embed.add_field(
                    name="⏱️ Time in Server",
                    value=f"{days} day{'s' if days != 1 else ''}",
                    inline=True,
                )

        # Add server information
        embed.add_field(name="🏠 Server", value=member.guild.name, inline=True)
        embed.add_field(
            name="👥 Members",
            value=str(member.guild.member_count),
            inline=True,
        )

        # Add user thumbnail if available
        settings = await self.config.guild(member.guild).all()
        if settings.get("include_thumbnails", True) and member.display_avatar:
            embed.set_thumbnail(url=member.display_avatar.url)

        # Set footer
        self.set_embed_footer(embed, label="YALC Logger • Member Kick")

        await self.safe_send(channel, embed=embed)

    async def _log_member_leave(self, member: discord.Member):
        """Log a regular member leave event."""
        self.log.debug("Logging member leave")
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
                timestamp=datetime.datetime.now(datetime.UTC),
            )

            # Add user information
            embed.add_field(
                name="User",
                value=f"{member} ({member.id})",
                inline=True,
            )

            # Add join date information - this is what was requested
            if member.joined_at:
                join_date_formatted = member.joined_at.strftime("%B %d, %Y at %I:%M %p")
                embed.add_field(
                    name="📅 Originally Joined",
                    value=join_date_formatted,
                    inline=True,
                )

                # Calculate how long they were in the server
                time_in_server = datetime.datetime.now(datetime.UTC) - member.joined_at
                days = time_in_server.days
                if days > 0:
                    embed.add_field(
                        name="⏱️ Time in Server",
                        value=f"{days} day{'s' if days != 1 else ''}",
                        inline=True,
                    )

            # Add server information
            embed.add_field(name="🏠 Server", value=member.guild.name, inline=True)
            embed.add_field(
                name="👥 Members",
                value=str(member.guild.member_count),
                inline=True,
            )

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
    async def on_member_update(
        self,
        before: discord.Member,
        after: discord.Member,
    ) -> None:
        """Log member update events with audit log integration to show who made changes."""
        self.log.debug("Listener triggered: on_member_update")
        if not before.guild:
            self.log.debug("No guild on member.")
            return
        event_type = (
            "member_timeout"
            if getattr(before, "communication_disabled_until", None)
            != getattr(after, "communication_disabled_until", None)
            else "member_update"
        )
        try:
            should_log = await self.should_log_event(
                before.guild,
                event_type,
                user=after,
            )
        except Exception as e:
            self.log.error(f"Error in should_log_event: {e}")
            return
        if not should_log:
            self.log.debug(f"should_log_event returned False for {event_type}.")
            return
        try:
            channel = await self.get_log_channel(before.guild, event_type)
        except Exception as e:
            self.log.error(f"Error in get_log_channel: {e}")
            return
        self.log.debug(f"About to send to channel: {channel}")
        if not channel:
            self.log.warning(f"No log channel set for {event_type}.")
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
                        timeout_seconds=10,
                    )

                    if audit_entry and audit_entry.user != after:
                        moderator_info = {
                            "moderator": audit_entry.user,
                            "reason": getattr(audit_entry, "reason", None),
                        }
                except Exception as e:
                    self.log.debug(
                        f"Could not fetch audit log for member role update: {e}",
                    )

                # Add role changes to the changes list
                for role in added_roles:
                    changes.append(f"➕ Added {role.mention}")
                for role in removed_roles:
                    changes.append(f"➖ Removed {role.mention}")

            # Check for timeout/communication restriction changes
            before_timeout = getattr(before, "communication_disabled_until", None)
            after_timeout = getattr(after, "communication_disabled_until", None)

            if before_timeout != after_timeout:
                try:
                    # Look for member timeout in audit logs
                    timeout_action = discord.AuditLogAction.member_update
                    audit_entry = await self._get_audit_log_entry(
                        before.guild,
                        timeout_action,
                        target=after,
                        timeout_seconds=10,
                    )

                    if audit_entry and audit_entry.user != after and not moderator_info:
                        moderator_info = {
                            "moderator": audit_entry.user,
                            "reason": getattr(audit_entry, "reason", None),
                        }
                except Exception as e:
                    self.log.debug(
                        f"Could not fetch audit log for member timeout update: {e}",
                    )

                # Format timeout change message
                if after_timeout:
                    if before_timeout:
                        # Timeout duration changed
                        after_timeout - datetime.datetime.now(datetime.UTC)
                        changes.append(
                            f"⏰ Timeout updated: expires {discord.utils.format_dt(after_timeout, 'R')}",
                        )
                    else:
                        # New timeout applied
                        after_timeout - datetime.datetime.now(datetime.UTC)
                        changes.append(
                            f"⏰ Timeout applied: expires {discord.utils.format_dt(after_timeout, 'R')}",
                        )
                else:
                    # Timeout removed
                    changes.append("✅ Timeout removed")

            # Check for nickname changes
            if before.nick != after.nick:
                try:
                    # Look for member update in audit logs (covers nickname changes)
                    audit_entry = await self._get_audit_log_entry(
                        before.guild,
                        discord.AuditLogAction.member_update,
                        target=after,
                        timeout_seconds=10,
                    )

                    if audit_entry and audit_entry.user != after and not moderator_info:
                        moderator_info = {
                            "moderator": audit_entry.user,
                            "reason": getattr(audit_entry, "reason", None),
                        }
                except Exception as e:
                    self.log.debug(
                        f"Could not fetch audit log for member nickname update: {e}",
                    )

                changes.append(
                    f"📝 Nickname changed: '{before.nick or before.display_name}' → '{after.nick or after.display_name}'",
                )

            # Skip if no changes detected
            if not changes:
                return

            # Create the embed with enhanced information
            if moderator_info:
                description = f"👤 {after.mention} ({after.display_name})'s profile was updated by {moderator_info['moderator'].mention}"
            else:
                description = (
                    f"👤 {after.mention} ({after.display_name})'s profile was updated"
                )

            embed = self.create_embed(
                event_type,
                description + "\n\u200b",
            )

            # Add user information
            embed.add_field(
                name="Member",
                value=f"{after.mention} (`{after}`, ID: `{after.id}`)",
                inline=True,
            )

            # Add moderator information if available
            if moderator_info:
                embed.add_field(
                    name="Updated By",
                    value=f"{moderator_info['moderator'].mention} (`{moderator_info['moderator']}`, ID: `{moderator_info['moderator'].id}`)",
                    inline=True,
                )

                # Add reason if provided
                if moderator_info["reason"]:
                    embed.add_field(
                        name="Reason",
                        value=moderator_info["reason"],
                        inline=False,
                    )

                # Indicate if it was self-updated vs moderated
                if moderator_info["moderator"] == after:
                    embed.add_field(
                        name="Update Type",
                        value="Self-updated",
                        inline=True,
                    )
                else:
                    embed.add_field(
                        name="Update Type",
                        value="Moderated update",
                        inline=True,
                    )
            else:
                # If no audit log info available, indicate unknown
                embed.add_field(
                    name="Updated By",
                    value="Unknown (audit log unavailable or self-updated)",
                    inline=True,
                )

            # Add the changes
            embed.add_field(
                name="Changes",
                value="\n".join(changes),
                inline=False,
            )

            # Add user thumbnail for better visual identification
            settings = await self.config.guild(before.guild).all()
            if settings.get("include_thumbnails", True) and after.display_avatar:
                embed.set_thumbnail(url=after.display_avatar.url)

            # Set footer
            event_time = datetime.datetime.now(datetime.UTC)
            footer_label = (
                "YALC Logger • Member Timeout"
                if event_type == "member_timeout"
                else "YALC Logger • Member Update"
            )
            self.set_embed_footer(embed, event_time=event_time, label=footer_label)

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
            should_log = await self.should_log_event(
                channel.guild,
                "channel_create",
                channel,
            )
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
                    timeout_seconds=10,
                )

                if audit_entry:
                    creator_info = {
                        "creator": audit_entry.user,
                        "reason": getattr(audit_entry, "reason", None),
                    }
            except Exception as e:
                self.log.debug(f"Could not fetch audit log for channel creation: {e}")

            # Create the embed with enhanced information
            if creator_info:
                description = f"📝 Channel created: {getattr(channel, 'mention', str(channel))} by {creator_info['creator'].mention}"
            else:
                description = (
                    f"📝 Channel created: {getattr(channel, 'mention', str(channel))}"
                )

            description += "\n\u200b"

            embed = self.create_embed(
                "channel_create",
                description,
            )

            # Add channel information
            embed.add_field(
                name="Channel",
                value=f"{getattr(channel, 'mention', str(channel))} (`{channel.name}`, ID: `{channel.id}`)",
                inline=True,
            )

            embed.add_field(
                name="Type",
                value=type(channel).__name__,
                inline=True,
            )

            # Add creator information if available
            if creator_info:
                embed.add_field(
                    name="Created By",
                    value=f"{creator_info['creator'].mention} (`{creator_info['creator']}`, ID: `{creator_info['creator'].id}`)",
                    inline=True,
                )

                # Add reason if provided
                if creator_info["reason"]:
                    embed.add_field(
                        name="Reason",
                        value=creator_info["reason"],
                        inline=False,
                    )
            else:
                # If no audit log info available, indicate unknown
                embed.add_field(
                    name="Created By",
                    value="Unknown (audit log unavailable)",
                    inline=True,
                )

            # Add category info if applicable
            if hasattr(channel, "category") and channel.category:
                embed.add_field(
                    name="Category",
                    value=f"{channel.category.name} (`{channel.category.id}`)",
                    inline=True,
                )

            # Add channel-specific information
            if isinstance(channel, discord.TextChannel):
                if channel.topic:
                    embed.add_field(
                        name="Topic",
                        value=channel.topic[:1024]
                        if len(channel.topic) <= 1024
                        else channel.topic[:1021] + "...",
                        inline=False,
                    )
                embed.add_field(
                    name="NSFW",
                    value="Yes" if channel.nsfw else "No",
                    inline=True,
                )
                if channel.slowmode_delay > 0:
                    embed.add_field(
                        name="Slowmode",
                        value=f"{channel.slowmode_delay} seconds",
                        inline=True,
                    )
            elif isinstance(channel, discord.VoiceChannel):
                embed.add_field(
                    name="Bitrate",
                    value=f"{channel.bitrate} bps",
                    inline=True,
                )
                if channel.user_limit > 0:
                    embed.add_field(
                        name="User Limit",
                        value=str(channel.user_limit),
                        inline=True,
                    )

            # Add creator thumbnail for better visual identification
            settings = await self.config.guild(channel.guild).all()
            if (
                creator_info
                and settings.get("include_thumbnails", True)
                and hasattr(creator_info["creator"], "display_avatar")
            ):
                embed.set_thumbnail(url=creator_info["creator"].display_avatar.url)

            # Set footer
            event_time = datetime.datetime.now(datetime.UTC)
            self.set_embed_footer(
                embed,
                event_time=event_time,
                label="YALC Logger • Channel Created",
            )

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
            should_log = await self.should_log_event(
                channel.guild,
                "channel_delete",
                channel,
            )
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
                    timeout_seconds=10,
                )

                if audit_entry:
                    deleter_info = {
                        "deleter": audit_entry.user,
                        "reason": getattr(audit_entry, "reason", None),
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
                description,
            )

            # Add channel information
            embed.add_field(
                name="Channel",
                value=f"**{channel.name}** (ID: `{channel.id}`)",
                inline=True,
            )

            embed.add_field(
                name="Type",
                value=type(channel).__name__,
                inline=True,
            )

            # Add deleter information if available
            if deleter_info:
                embed.add_field(
                    name="Deleted By",
                    value=f"{deleter_info['deleter'].mention} (`{deleter_info['deleter']}`, ID: `{deleter_info['deleter'].id}`)",
                    inline=True,
                )

                # Add reason if provided
                if deleter_info["reason"]:
                    embed.add_field(
                        name="Reason",
                        value=deleter_info["reason"],
                        inline=False,
                    )
            else:
                # If no audit log info available, indicate unknown
                embed.add_field(
                    name="Deleted By",
                    value="Unknown (audit log unavailable)",
                    inline=True,
                )

            # Add category info if applicable
            if hasattr(channel, "category") and channel.category:
                embed.add_field(
                    name="Category",
                    value=f"{channel.category.name} (`{channel.category.id}`)",
                    inline=True,
                )

            # Add channel-specific information that was preserved before deletion
            if isinstance(channel, discord.TextChannel):
                if hasattr(channel, "topic") and channel.topic:
                    embed.add_field(
                        name="Topic",
                        value=channel.topic[:1024]
                        if len(channel.topic) <= 1024
                        else channel.topic[:1021] + "...",
                        inline=False,
                    )
                if hasattr(channel, "nsfw"):
                    embed.add_field(
                        name="NSFW",
                        value="Yes" if channel.nsfw else "No",
                        inline=True,
                    )
                if hasattr(channel, "slowmode_delay") and channel.slowmode_delay > 0:
                    embed.add_field(
                        name="Slowmode",
                        value=f"{channel.slowmode_delay} seconds",
                        inline=True,
                    )
            elif isinstance(channel, discord.VoiceChannel):
                if hasattr(channel, "bitrate"):
                    embed.add_field(
                        name="Bitrate",
                        value=f"{channel.bitrate} bps",
                        inline=True,
                    )
                if hasattr(channel, "user_limit") and channel.user_limit > 0:
                    embed.add_field(
                        name="User Limit",
                        value=str(channel.user_limit),
                        inline=True,
                    )

            # Add deleter thumbnail for better visual identification
            settings = await self.config.guild(channel.guild).all()
            if (
                deleter_info
                and settings.get("include_thumbnails", True)
                and hasattr(deleter_info["deleter"], "display_avatar")
            ):
                embed.set_thumbnail(url=deleter_info["deleter"].display_avatar.url)

            # Set footer
            event_time = datetime.datetime.now(datetime.UTC)
            self.set_embed_footer(
                embed,
                event_time=event_time,
                label="YALC Logger • Channel Deleted",
            )

            await self.safe_send(log_channel, embed=embed)
        except Exception as e:
            self.log.error(f"Failed to log channel_delete: {e}")

    @commands.Cog.listener()
    async def on_guild_channel_update(
        self,
        before: discord.abc.GuildChannel,
        after: discord.abc.GuildChannel,
    ) -> None:
        self.log.debug("Listener triggered: on_guild_channel_update")
        if not before.guild:
            self.log.debug("No guild on channel.")
            return
        stage_channel_cls = getattr(discord, "StageChannel", None)
        voice_like_channel = isinstance(before, discord.VoiceChannel) or isinstance(
            after,
            discord.VoiceChannel,
        )
        if stage_channel_cls:
            voice_like_channel = (
                voice_like_channel
                or isinstance(before, stage_channel_cls)
                or isinstance(after, stage_channel_cls)
            )
        event_type = "voice_update" if voice_like_channel else "channel_update"
        try:
            should_log = await self.should_log_event(before.guild, event_type, after)
        except Exception as e:
            self.log.error(f"Error in should_log_event: {e}")
            return
        if not should_log:
            self.log.debug(f"should_log_event returned False for {event_type}.")
            return
        try:
            log_channel = await self.get_log_channel(before.guild, event_type)
        except Exception as e:
            self.log.error(f"Error in get_log_channel: {e}")
            return
        self.log.debug(f"About to send to channel: {log_channel}")
        if not log_channel:
            self.log.warning(f"No log channel set for {event_type}.")
            return
        try:
            changes = []
            if hasattr(before, "name") and before.name != getattr(after, "name", None):
                changes.append(f"Name: {before.name} → {after.name}")
            if isinstance(before, discord.TextChannel) and isinstance(
                after,
                discord.TextChannel,
            ):
                if before.topic != after.topic:
                    changes.append(f"Topic: {before.topic} → {after.topic}")
                if before.nsfw != after.nsfw:
                    changes.append(f"NSFW: {before.nsfw} → {after.nsfw}")
                if before.slowmode_delay != after.slowmode_delay:
                    changes.append(
                        f"Slowmode: {before.slowmode_delay}s → {after.slowmode_delay}s",
                    )
            if isinstance(before, discord.VoiceChannel) and isinstance(
                after,
                discord.VoiceChannel,
            ):
                if before.bitrate != after.bitrate:
                    changes.append(f"Bitrate: {before.bitrate} → {after.bitrate}")
                if before.user_limit != after.user_limit:
                    changes.append(
                        f"User limit: {before.user_limit} → {after.user_limit}",
                    )
            if voice_like_channel:
                if getattr(before, "rtc_region", None) != getattr(
                    after,
                    "rtc_region",
                    None,
                ):
                    changes.append(
                        f"RTC region: {getattr(before, 'rtc_region', None)} → {getattr(after, 'rtc_region', None)}",
                    )
                if getattr(before, "video_quality_mode", None) != getattr(
                    after,
                    "video_quality_mode",
                    None,
                ):
                    changes.append(
                        f"Video quality: {getattr(before, 'video_quality_mode', None)} → {getattr(after, 'video_quality_mode', None)}",
                    )
            if not changes:
                return

            # Try to get audit log information about who updated the channel
            updater_info = None
            try:
                audit_entry = await self._get_audit_log_entry(
                    before.guild,
                    discord.AuditLogAction.channel_update,
                    target=after,
                    timeout_seconds=10,
                )
                if audit_entry:
                    updater_info = {
                        "updater": audit_entry.user,
                        "reason": getattr(audit_entry, "reason", None),
                    }
            except Exception as e:
                self.log.debug(f"Could not fetch audit log for channel update: {e}")

            # Build description with updater if available
            if updater_info:
                description = f"🔄 Channel updated: {getattr(after, 'mention', str(after))} by {updater_info['updater'].mention}\n\u200b"
            else:
                description = f"🔄 Channel updated: {getattr(after, 'mention', str(after))}\n\u200b"

            embed = self.create_embed(
                event_type,
                description,
                changes="\n".join(changes),
                channel_name=after.name,
            )

            # Add updater info if available
            if updater_info:
                embed.add_field(
                    name="Updated By",
                    value=f"{updater_info['updater'].mention} (`{updater_info['updater']}`, ID: `{updater_info['updater'].id}`)",
                    inline=True,
                )
                if updater_info["reason"]:
                    embed.add_field(
                        name="Reason",
                        value=updater_info["reason"],
                        inline=False,
                    )
            else:
                embed.add_field(
                    name="Updated By",
                    value="Unknown (audit log unavailable or self-updated)",
                    inline=True,
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
        event_type = (
            "forum_post_create" if self._is_forum_thread(thread) else "thread_create"
        )
        try:
            should_log = await self.should_log_event(
                thread.guild,
                event_type,
                channel=thread,
            )
        except Exception as e:
            self.log.error(f"Error in should_log_event: {e}")
            return
        if not should_log:
            self.log.debug(f"should_log_event returned False for {event_type}.")
            return
        try:
            log_channel = await self.get_log_channel(thread.guild, event_type)
        except Exception as e:
            self.log.error(f"Error in get_log_channel: {e}")
            return
        self.log.debug(f"About to send to channel: {log_channel}")
        if not log_channel:
            self.log.warning(f"No log channel set for {event_type}.")
            return
        try:
            # Try to get audit log information about who created the thread
            creator_info = None
            try:
                audit_entry = await self._get_audit_log_entry(
                    thread.guild,
                    discord.AuditLogAction.thread_create,
                    target=thread,
                    timeout_seconds=10,
                )
                if audit_entry:
                    creator_info = {
                        "creator": audit_entry.user,
                        "reason": getattr(audit_entry, "reason", None),
                    }
            except Exception as e:
                self.log.debug(f"Could not fetch audit log for thread creation: {e}")

            item_label = "Forum post" if event_type == "forum_post_create" else "Thread"
            item_emoji = "📋" if event_type == "forum_post_create" else "🧵"
            if creator_info:
                description = f"{item_emoji} {item_label} created in {getattr(thread.parent, 'mention', None)} by {creator_info['creator'].mention}\n\u200b"
            else:
                description = f"{item_emoji} {item_label} created in {getattr(thread.parent, 'mention', None)}\n\u200b"

            embed = self.create_embed(
                event_type,
                description,
                thread=thread.mention,
                name=thread.name,
                creator=f"{thread.owner} ({thread.owner_id})"
                if thread.owner
                else f"ID: {thread.owner_id}",
                type=str(thread.type),
                slowmode=f"{thread.slowmode_delay}s"
                if thread.slowmode_delay
                else "None",
            )

            if creator_info:
                embed.add_field(
                    name="Created By",
                    value=f"{creator_info['creator'].mention} (`{creator_info['creator']}`, ID: `{creator_info['creator'].id}`)",
                    inline=True,
                )
                if creator_info["reason"]:
                    embed.add_field(
                        name="Reason",
                        value=creator_info["reason"],
                        inline=False,
                    )
            else:
                embed.add_field(
                    name="Created By",
                    value="Unknown (audit log unavailable)",
                    inline=True,
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
        event_type = (
            "forum_post_delete" if self._is_forum_thread(thread) else "thread_delete"
        )
        try:
            should_log = await self.should_log_event(
                thread.guild,
                event_type,
                channel=thread,
            )
        except Exception as e:
            self.log.error(f"Error in should_log_event: {e}")
            return
        if not should_log:
            self.log.debug(f"should_log_event returned False for {event_type}.")
            return
        try:
            log_channel = await self.get_log_channel(thread.guild, event_type)
        except Exception as e:
            self.log.error(f"Error in get_log_channel: {e}")
            return
        self.log.debug(f"About to send to channel: {log_channel}")
        if not log_channel:
            self.log.warning(f"No log channel set for {event_type}.")
            return
        try:
            # Try to get audit log information about who deleted the thread
            deleter_info = None
            try:
                audit_entry = await self._get_audit_log_entry(
                    thread.guild,
                    discord.AuditLogAction.thread_delete,
                    target=thread,
                    timeout_seconds=10,
                )
                if audit_entry:
                    deleter_info = {
                        "deleter": audit_entry.user,
                        "reason": getattr(audit_entry, "reason", None),
                    }
            except Exception as e:
                self.log.debug(f"Could not fetch audit log for thread deletion: {e}")

            item_label = "forum post" if event_type == "forum_post_delete" else "thread"
            if deleter_info:
                description = f"🗑️ {item_label.title()} deleted from {getattr(thread.parent, 'mention', None)} by {deleter_info['deleter'].mention}\n\u200b"
            else:
                description = f"🗑️ {item_label.title()} deleted from {getattr(thread.parent, 'mention', None)}\n\u200b"

            embed = self.create_embed(
                event_type,
                description,
                name=thread.name,
                archived=thread.archived,
                locked=thread.locked,
                type=str(thread.type),
            )

            if deleter_info:
                embed.add_field(
                    name="Deleted By",
                    value=f"{deleter_info['deleter'].mention} (`{deleter_info['deleter']}`, ID: `{deleter_info['deleter'].id}`)",
                    inline=True,
                )
                if deleter_info["reason"]:
                    embed.add_field(
                        name="Reason",
                        value=deleter_info["reason"],
                        inline=False,
                    )
            else:
                embed.add_field(
                    name="Deleted By",
                    value="Unknown (audit log unavailable)",
                    inline=True,
                )

            await self.safe_send(log_channel, embed=embed)
        except Exception as e:
            self.log.error(f"Failed to log thread_delete: {e}")

    @commands.Cog.listener()
    async def on_thread_update(
        self,
        before: discord.Thread,
        after: discord.Thread,
    ) -> None:
        self.log.debug("Listener triggered: on_thread_update")
        if not before.guild:
            self.log.debug("No guild on thread.")
            return
        event_type = (
            "forum_post_update" if self._is_forum_thread(after) else "thread_update"
        )
        try:
            should_log = await self.should_log_event(
                before.guild,
                event_type,
                channel=after,
            )
        except Exception as e:
            self.log.error(f"Error in should_log_event: {e}")
            return
        if not should_log:
            self.log.debug(f"should_log_event returned False for {event_type}.")
            return
        try:
            log_channel = await self.get_log_channel(before.guild, event_type)
        except Exception as e:
            self.log.error(f"Error in get_log_channel: {e}")
            return
        self.log.debug(f"About to send to channel: {log_channel}")
        if not log_channel:
            self.log.warning(f"No log channel set for {event_type}.")
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
                changes.append(
                    f"Slowmode: {before.slowmode_delay}s → {after.slowmode_delay}s",
                )
            if before.auto_archive_duration != after.auto_archive_duration:
                changes.append(
                    f"Auto Archive: {before.auto_archive_duration} minutes → {after.auto_archive_duration} minutes",
                )
            if not changes:
                return
            item_label = "Forum post" if event_type == "forum_post_update" else "Thread"
            embed = self.create_embed(
                event_type,
                f"🔄 {item_label} updated in {getattr(after.parent, 'mention', None)}\n\u200b",
                thread=after.mention,
                changes="\n".join(changes),
            )
            await self.safe_send(log_channel, embed=embed)
        except Exception as e:
            self.log.error(f"Failed to log thread_update: {e}")

    @commands.Cog.listener()
    async def on_thread_member_join(self, member: discord.ThreadMember) -> None:
        self.log.debug("Listener triggered: on_thread_member_join")
        try:
            should_log = await self.should_log_event(
                member.thread.guild,
                "thread_member_join",
            )
        except Exception as e:
            self.log.error(f"Error in should_log_event: {e}")
            return
        if not should_log:
            self.log.debug("should_log_event returned False for thread_member_join.")
            return
        try:
            log_channel = await self.get_log_channel(
                member.thread.guild,
                "thread_member_join",
            )
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
            member_display = (
                resolved_member.mention if resolved_member else f"ID: {member.id}"
            )
            embed = self.create_embed(
                "thread_member_join",
                f"➡️ Member joined thread {member.thread.mention}",
                member=f"{member_display} ({member.id})",
                thread=member.thread.name,
            )
            await self.safe_send(log_channel, embed=embed)
        except Exception as e:
            self.log.error(f"Failed to log thread_member_join: {e}")

    @commands.Cog.listener()
    async def on_thread_member_remove(self, member: discord.ThreadMember) -> None:
        self.log.debug("Listener triggered: on_thread_member_remove")
        try:
            should_log = await self.should_log_event(
                member.thread.guild,
                "thread_member_leave",
            )
        except Exception as e:
            self.log.error(f"Error in should_log_event: {e}")
            return
        if not should_log:
            self.log.debug("should_log_event returned False for thread_member_leave.")
            return
        try:
            log_channel = await self.get_log_channel(
                member.thread.guild,
                "thread_member_leave",
            )
        except Exception as e:
            self.log.error(f"Error in get_log_channel: {e}")
            return
        self.log.debug(f"About to send to channel: {log_channel}")
        if not log_channel:
            self.log.warning("No log channel set for thread_member_leave.")
            return
        try:
            resolved_member = member.thread.guild.get_member(member.id)
            member_display = (
                resolved_member.mention if resolved_member else f"ID: {member.id}"
            )
            embed = self.create_embed(
                "thread_member_leave",
                f"⬅️ Member left thread {member.thread.mention}",
                member=f"{member_display} ({member.id})",
                thread=member.thread.name,
            )
            await self.safe_send(log_channel, embed=embed)
        except Exception as e:
            self.log.error(f"Failed to log thread_member_leave: {e}")

    @commands.Cog.listener()
    async def on_guild_role_create(self, role: discord.Role) -> None:
        """Log role creation events with audit log integration to show who created roles."""
        self.log.debug("Listener triggered: on_guild_role_create")
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
                    timeout_seconds=10,
                )

                if audit_entry:
                    creator_info = {
                        "creator": audit_entry.user,
                        "reason": getattr(audit_entry, "reason", None),
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
                description,
            )

            # Add role information
            embed.add_field(
                name="Role",
                value=f"{role.mention} (`{role.name}`, ID: `{role.id}`)",
                inline=True,
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
                elif (
                    role.color.value < 0x000080 or role.color.value < 0x800080
                ):  # Teal/Cyan
                    color_indicator = "🟦"
                else:  # Purple/Pink
                    color_indicator = "🟪"

                embed.add_field(
                    name="Color",
                    value=f"{color_indicator} {color_hex}",
                    inline=True,
                )

            # Add role position
            embed.add_field(
                name="Position",
                value=str(role.position),
                inline=True,
            )

            # Add creator information if available
            if creator_info:
                embed.add_field(
                    name="Created By",
                    value=f"{creator_info['creator'].mention} (`{creator_info['creator']}`, ID: `{creator_info['creator'].id}`)",
                    inline=True,
                )

                # Add reason if provided
                if creator_info["reason"]:
                    embed.add_field(
                        name="Reason",
                        value=creator_info["reason"],
                        inline=False,
                    )
            else:
                # If no audit log info available, indicate unknown
                embed.add_field(
                    name="Created By",
                    value="Unknown (audit log unavailable)",
                    inline=True,
                )

            # Add role properties
            role_properties = []
            if getattr(role, "mentionable", False):
                role_properties.append("📢 Mentionable")
            if getattr(role, "hoist", False):
                role_properties.append("📌 Hoisted (displays separately)")
            if getattr(role, "managed", False):
                role_properties.append("🤖 Managed by integration")
            if self._role_is_premium_subscriber(role):
                role_properties.append("💎 Premium subscriber role")

            if role_properties:
                embed.add_field(
                    name="Properties",
                    value="\n".join(role_properties),
                    inline=False,
                )

            # Add permission summary if role has elevated permissions
            dangerous_perms = []
            if self._role_has_permission(role, "administrator"):
                dangerous_perms.append("🔧 Administrator")
            if self._role_has_permission(role, "manage_guild"):
                dangerous_perms.append("⚙️ Manage Server")
            if self._role_has_permission(role, "manage_roles"):
                dangerous_perms.append("👥 Manage Roles")
            if self._role_has_permission(role, "manage_channels"):
                dangerous_perms.append("📝 Manage Channels")
            if self._role_has_permission(role, "kick_members"):
                dangerous_perms.append("👢 Kick Members")
            if self._role_has_permission(role, "ban_members"):
                dangerous_perms.append("🔨 Ban Members")
            if self._role_has_permission(role, "moderate_members"):
                dangerous_perms.append("⏰ Timeout Members")

            if dangerous_perms:
                embed.add_field(
                    name="Key Permissions",
                    value="\n".join(dangerous_perms),
                    inline=False,
                )

            # Add creator thumbnail for better visual identification
            settings = await self.config.guild(role.guild).all()
            if (
                creator_info
                and settings.get("include_thumbnails", True)
                and hasattr(creator_info["creator"], "display_avatar")
            ):
                embed.set_thumbnail(url=creator_info["creator"].display_avatar.url)

            # Set footer
            event_time = datetime.datetime.now(datetime.UTC)
            self.set_embed_footer(
                embed,
                event_time=event_time,
                label="YALC Logger • Role Created",
            )

            sent_message = await self.safe_send(channel, embed=embed)
            if sent_message:
                self._mark_role_event_logged(role.guild.id, "role_create", role.id)
        except Exception as e:
            self.log.error(f"Failed to log role_create: {e}", exc_info=True)

    @commands.Cog.listener()
    async def on_guild_role_delete(self, role: discord.Role) -> None:
        """Log role deletion events with audit log integration to show who deleted roles."""
        self.log.debug("Listener triggered: on_guild_role_delete")
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
                    timeout_seconds=10,
                )

                if audit_entry:
                    deleter_info = {
                        "deleter": audit_entry.user,
                        "reason": getattr(audit_entry, "reason", None),
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
                description,
            )

            # Add role information
            embed.add_field(
                name="Role",
                value=f"**{role.name}** (ID: `{role.id}`)",
                inline=True,
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
                elif (
                    role.color.value < 0x000080 or role.color.value < 0x800080
                ):  # Teal/Cyan
                    color_indicator = "🟦"
                else:  # Purple/Pink
                    color_indicator = "🟪"

                embed.add_field(
                    name="Color",
                    value=f"{color_indicator} {color_hex}",
                    inline=True,
                )

            # Add role position
            embed.add_field(
                name="Position",
                value=str(role.position),
                inline=True,
            )

            # Add deleter information if available
            if deleter_info:
                embed.add_field(
                    name="Deleted By",
                    value=f"{deleter_info['deleter'].mention} (`{deleter_info['deleter']}`, ID: `{deleter_info['deleter'].id}`)",
                    inline=True,
                )

                # Add reason if provided
                if deleter_info["reason"]:
                    embed.add_field(
                        name="Reason",
                        value=deleter_info["reason"],
                        inline=False,
                    )
            else:
                # If no audit log info available, indicate unknown
                embed.add_field(
                    name="Deleted By",
                    value="Unknown (audit log unavailable)",
                    inline=True,
                )

            # Add role properties that were preserved before deletion
            role_properties = []
            if getattr(role, "mentionable", False):
                role_properties.append("📢 Was mentionable")
            if getattr(role, "hoist", False):
                role_properties.append("📌 Was hoisted (displayed separately)")
            if getattr(role, "managed", False):
                role_properties.append("🤖 Was managed by integration")
            if self._role_is_premium_subscriber(role):
                role_properties.append("💎 Was premium subscriber role")

            if role_properties:
                embed.add_field(
                    name="Properties",
                    value="\n".join(role_properties),
                    inline=False,
                )

            # Add permission summary if role had elevated permissions
            dangerous_perms = []
            if self._role_has_permission(role, "administrator"):
                dangerous_perms.append("🔧 Had Administrator")
            if self._role_has_permission(role, "manage_guild"):
                dangerous_perms.append("⚙️ Had Manage Server")
            if self._role_has_permission(role, "manage_roles"):
                dangerous_perms.append("👥 Had Manage Roles")
            if self._role_has_permission(role, "manage_channels"):
                dangerous_perms.append("📝 Had Manage Channels")
            if self._role_has_permission(role, "kick_members"):
                dangerous_perms.append("👢 Had Kick Members")
            if self._role_has_permission(role, "ban_members"):
                dangerous_perms.append("🔨 Had Ban Members")
            if self._role_has_permission(role, "moderate_members"):
                dangerous_perms.append("⏰ Had Timeout Members")

            if dangerous_perms:
                embed.add_field(
                    name="Key Permissions",
                    value="\n".join(dangerous_perms),
                    inline=False,
                )

            # Add deleter thumbnail for better visual identification
            settings = await self.config.guild(role.guild).all()
            if (
                deleter_info
                and settings.get("include_thumbnails", True)
                and hasattr(deleter_info["deleter"], "display_avatar")
            ):
                embed.set_thumbnail(url=deleter_info["deleter"].display_avatar.url)

            # Set footer
            event_time = datetime.datetime.now(datetime.UTC)
            self.set_embed_footer(
                embed,
                event_time=event_time,
                label="YALC Logger • Role Deleted",
            )

            sent_message = await self.safe_send(channel, embed=embed)
            if sent_message:
                self._mark_role_event_logged(role.guild.id, "role_delete", role.id)
        except Exception as e:
            self.log.error(f"Failed to log role_delete: {e}", exc_info=True)

    @commands.Cog.listener()
    async def on_guild_role_update(
        self,
        before: discord.Role,
        after: discord.Role,
    ) -> None:
        """Log role update events with real-time audit log attribution."""
        self.log.debug("Listener triggered: on_guild_role_update")
        self.log.debug(
            f"Role before: name={before.name}, color={before.color}, permissions={before.permissions}",
        )
        self.log.debug(
            f"Role after:  name={after.name}, color={after.color}, permissions={after.permissions}",
        )
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
                self.log.debug(
                    f"Role permissions changed: {before.permissions} -> {after.permissions}",
                )
                changes.append("**Permissions:** Changed")
            if position_changed:
                self.log.debug(
                    f"Role position changed: {before.position} -> {after.position}",
                )
                changes.append(
                    f"**Position:** `{before.position}` → `{after.position}`",
                )
            if before.mentionable != after.mentionable:
                changes.append(
                    f"**Mentionable:** `{before.mentionable}` → `{after.mentionable}`",
                )
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
                if time.time() - audit_data["timestamp"] <= 5:
                    audit_entry = audit_data["entry"]
                    user_who_changed = audit_entry.user
                    audit_reason = getattr(audit_entry, "reason", None)
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
                        timeout_seconds=10,
                    )
                    if audit_entry:
                        user_who_changed = audit_entry.user
                        audit_reason = getattr(audit_entry, "reason", None)
                        self.log.debug(f"Using API audit data for role {after.id}")
                except Exception as e:
                    self.log.debug(f"Could not fetch audit log for role update: {e}")

            # Create enhanced embed with attribution
            if user_who_changed:
                description = (
                    f"🔄 Role updated: {after.mention} by {user_who_changed.mention}"
                )
            else:
                description = f"🔄 Role updated: {after.mention}"

            description += "\n\u200b"

            embed = self.create_embed("role_update", description)

            # Add role information
            embed.add_field(
                name="Role",
                value=f"{after.mention} (`{after.name}`, ID: `{after.id}`)",
                inline=True,
            )

            # Add who changed it
            if user_who_changed:
                embed.add_field(
                    name="Changed By",
                    value=f"{user_who_changed.mention} (`{user_who_changed.id}`)",
                    inline=True,
                )

                # Add reason if provided
                if audit_reason:
                    embed.add_field(
                        name="Reason",
                        value=audit_reason,
                        inline=False,
                    )
            else:
                embed.add_field(
                    name="Changed By",
                    value="Unknown (audit log unavailable)",
                    inline=True,
                )

            # Add timestamp
            embed.add_field(
                name="When",
                value=f"<t:{int(time.time())}:R>",
                inline=True,
            )

            # Add changes
            if changes:
                embed.add_field(
                    name="Changes",
                    value="\n".join(changes),
                    inline=False,
                )

            # Add color change if applicable
            if color_changed:
                before_hex = f"#{before.color.value:06x}"
                after_hex = f"#{after.color.value:06x}"
                before_emoji = (
                    "🟪"
                    if before.color.value >= 0x800080
                    else (
                        "🟦"
                        if before.color.value >= 0x000080
                        else (
                            "🟩"
                            if before.color.value >= 0x008000
                            else (
                                "🟨"
                                if before.color.value >= 0x008080
                                else (
                                    "🟧" if before.color.value >= 0x808000 else ("🟥")
                                )
                            )
                        )
                    )
                )
                after_emoji = (
                    "🟪"
                    if after.color.value >= 0x800080
                    else (
                        "🟦"
                        if after.color.value >= 0x000080
                        else (
                            "🟩"
                            if after.color.value >= 0x008000
                            else (
                                "🟨"
                                if after.color.value >= 0x008080
                                else ("🟧" if after.color.value >= 0x808000 else ("🟥"))
                            )
                        )
                    )
                )
                embed.add_field(
                    name="Color Change",
                    value=f"{before_emoji} {before_hex} → {after_emoji} {after_hex}",
                    inline=True,
                )

            # Add user thumbnail for better visual identification
            settings = await self.config.guild(before.guild).all()
            if (
                user_who_changed
                and settings.get("include_thumbnails", True)
                and hasattr(user_who_changed, "display_avatar")
            ):
                embed.set_thumbnail(url=user_who_changed.display_avatar.url)

            # Set footer
            event_time = datetime.datetime.now(datetime.UTC)
            self.set_embed_footer(
                embed,
                event_time=event_time,
                label="YALC Logger • Role Update",
            )

            await self.safe_send(channel, embed=embed)
        except Exception as e:
            self.log.error(f"Failed to log role_update: {e}", exc_info=True)

    @commands.Cog.listener()
    async def on_guild_update(
        self,
        before: discord.Guild,
        after: discord.Guild,
    ) -> None:
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
            if getattr(before, "banner", None) != getattr(after, "banner", None):
                changes.append("Banner changed")
            if getattr(before, "splash", None) != getattr(after, "splash", None):
                changes.append("Splash image changed")
            if getattr(before, "description", None) != getattr(
                after,
                "description",
                None,
            ):
                changes.append(
                    f"Description: {getattr(before, 'description', None)} → {getattr(after, 'description', None)}",
                )
            if getattr(before, "vanity_url_code", None) != getattr(
                after,
                "vanity_url_code",
                None,
            ):
                changes.append(
                    f"Vanity URL: {getattr(before, 'vanity_url_code', None)} → {getattr(after, 'vanity_url_code', None)}",
                )
            if getattr(before, "afk_channel", None) != getattr(
                after,
                "afk_channel",
                None,
            ):
                changes.append(
                    f"AFK Channel: {getattr(before.afk_channel, 'name', None)} → {getattr(after.afk_channel, 'name', None)}",
                )
            if getattr(before, "afk_timeout", None) != getattr(
                after,
                "afk_timeout",
                None,
            ):
                changes.append(
                    f"AFK Timeout: {getattr(before, 'afk_timeout', None)} → {getattr(after, 'afk_timeout', None)}",
                )
            if not changes:
                return

            # Try to get audit log information about who updated the guild
            updater_info = None
            try:
                audit_entry = await self._get_audit_log_entry(
                    before,
                    discord.AuditLogAction.guild_update,
                    timeout_seconds=10,
                )
                if audit_entry:
                    updater_info = {
                        "updater": audit_entry.user,
                        "reason": getattr(audit_entry, "reason", None),
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
                changes="\n".join(changes),
            )

            # Add updater info if available
            if updater_info:
                embed.add_field(
                    name="Updated By",
                    value=f"{updater_info['updater'].mention} (`{updater_info['updater']}`, ID: `{updater_info['updater'].id}`)",
                    inline=True,
                )
                if updater_info["reason"]:
                    embed.add_field(
                        name="Reason",
                        value=updater_info["reason"],
                        inline=False,
                    )
            else:
                embed.add_field(
                    name="Updated By",
                    value="Unknown (audit log unavailable or self-updated)",
                    inline=True,
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
                "😀 Emoji updated",
                changes="\n".join(changes),
            )
            await self.safe_send(channel, embed=embed)
        except Exception as e:
            self.log.error(f"Failed to log emoji_update: {e}")

    @commands.Cog.listener()
    async def on_guild_stickers_update(
        self,
        guild: discord.Guild,
        before,
        after,
    ) -> None:
        """Log server sticker creation, deletion, and update events."""
        self.log.debug("Listener triggered: on_guild_stickers_update")
        try:
            should_log = await self.should_log_event(guild, "sticker_update")
            if not should_log:
                return

            channel = await self.get_log_channel(guild, "sticker_update")
            if not channel:
                return

            before_by_id = {sticker.id: sticker for sticker in before}
            after_by_id = {sticker.id: sticker for sticker in after}
            added = [
                after_by_id[sticker_id]
                for sticker_id in after_by_id.keys() - before_by_id.keys()
            ]
            removed = [
                before_by_id[sticker_id]
                for sticker_id in before_by_id.keys() - after_by_id.keys()
            ]
            updated = [
                after_by_id[sticker_id]
                for sticker_id in before_by_id.keys() & after_by_id.keys()
                if before_by_id[sticker_id].name != after_by_id[sticker_id].name
                or getattr(before_by_id[sticker_id], "description", None)
                != getattr(after_by_id[sticker_id], "description", None)
                or getattr(before_by_id[sticker_id], "emoji", None)
                != getattr(after_by_id[sticker_id], "emoji", None)
            ]

            if not added and not removed and not updated:
                return

            changes = []
            if added:
                changes.append(
                    "Added: "
                    + ", ".join(f"`{sticker.name}`" for sticker in added[:10]),
                )
            if removed:
                changes.append(
                    "Removed: "
                    + ", ".join(f"`{sticker.name}`" for sticker in removed[:10]),
                )
            if updated:
                changes.append(
                    "Updated: "
                    + ", ".join(f"`{sticker.name}`" for sticker in updated[:10]),
                )

            action_name = (
                "sticker_create"
                if added
                else "sticker_delete"
                if removed
                else "sticker_update"
            )
            entry = await self._get_audit_log_entry(
                guild,
                self._get_audit_action(action_name),
                timeout_seconds=10,
            )

            embed = self.create_embed(
                "sticker_update",
                "🏷️ Server stickers updated",
                changes="\n".join(changes),
            )
            if entry and entry.user:
                embed.add_field(
                    name="Updated By",
                    value=f"{entry.user.mention} (`{entry.user}`, ID: `{entry.user.id}`)",
                    inline=True,
                )
                if entry.reason:
                    embed.add_field(name="Reason", value=entry.reason, inline=False)

            await self.safe_send(channel, embed=embed)
        except Exception as e:
            self.log.error(f"Failed to log sticker_update: {e}", exc_info=True)

    @commands.Cog.listener()
    async def on_command(self, ctx: commands.Context) -> None:
        """Log successful prefix command usage."""
        if not ctx.guild:
            return

        try:
            if not await self.should_log_event(
                ctx.guild,
                "command_use",
                channel=ctx.channel,
                user=ctx.author,
                message=ctx.message,
            ):
                return

            channel = await self.get_log_channel(ctx.guild, "command_use")
            if not channel:
                return

            command_name = (
                ctx.command.qualified_name if ctx.command else "Unknown command"
            )
            content = ctx.message.content if ctx.message else ""
            if len(content) > 1000:
                content = content[:997] + "..."

            embed = self.create_embed(
                "command_use",
                f"⚡ Prefix command used: `{command_name}`",
            )
            embed.add_field(
                name="User",
                value=f"{ctx.author.mention} (`{ctx.author}`, ID: `{ctx.author.id}`)",
                inline=True,
            )
            embed.add_field(
                name="Channel",
                value=f"{ctx.channel.mention} (`{ctx.channel.name}`)",
                inline=True,
            )
            embed.add_field(
                name="Command",
                value=f"`{content}`" if content else "`N/A`",
                inline=False,
            )

            settings = await self.config.guild(ctx.guild).all()
            if settings.get("include_thumbnails", True) and hasattr(
                ctx.author,
                "display_avatar",
            ):
                embed.set_thumbnail(url=ctx.author.display_avatar.url)

            self.set_embed_footer(embed, label="YALC Logger • Command Use")
            await self.safe_send(channel, embed=embed)
        except Exception as e:
            self.log.error(f"Failed to log command_use: {e}", exc_info=True)

    @commands.Cog.listener()
    async def on_app_command_completion(
        self,
        interaction: discord.Interaction,
        command,
    ) -> None:
        """Log successful slash/application command usage."""
        if not interaction.guild:
            return

        try:
            event_channel = (
                interaction.channel
                if isinstance(interaction.channel, discord.abc.GuildChannel)
                else None
            )
            if not await self.should_log_event(
                interaction.guild,
                "application_cmd",
                channel=event_channel,
                user=interaction.user,
            ):
                return

            channel = await self.get_log_channel(interaction.guild, "application_cmd")
            if not channel:
                return

            command_name = getattr(command, "qualified_name", None) or getattr(
                command,
                "name",
                "Unknown command",
            )
            namespace = getattr(interaction, "namespace", None)

            embed = self.create_embed(
                "application_cmd",
                f"🤖 Application command used: `/{command_name}`",
            )
            embed.add_field(
                name="User",
                value=f"{interaction.user.mention} (`{interaction.user}`, ID: `{interaction.user.id}`)",
                inline=True,
            )
            if event_channel:
                embed.add_field(
                    name="Channel",
                    value=f"{event_channel.mention} (`{event_channel.name}`)",
                    inline=True,
                )
            if namespace:
                namespace_text = str(namespace)
                if len(namespace_text) > 1000:
                    namespace_text = namespace_text[:997] + "..."
                embed.add_field(
                    name="Options",
                    value=f"`{namespace_text}`",
                    inline=False,
                )

            settings = await self.config.guild(interaction.guild).all()
            if settings.get("include_thumbnails", True) and hasattr(
                interaction.user,
                "display_avatar",
            ):
                embed.set_thumbnail(url=interaction.user.display_avatar.url)

            self.set_embed_footer(embed, label="YALC Logger • Application Command")
            await self.safe_send(channel, embed=embed)
        except Exception as e:
            self.log.error(f"Failed to log application_cmd: {e}", exc_info=True)

    @commands.Cog.listener()
    async def on_app_command_error(
        self,
        interaction: discord.Interaction,
        error,
    ) -> None:
        """Log slash/application command errors."""
        if not interaction.guild:
            return

        try:
            event_channel = (
                interaction.channel
                if isinstance(interaction.channel, discord.abc.GuildChannel)
                else None
            )
            if not await self.should_log_event(
                interaction.guild,
                "command_error",
                channel=event_channel,
                user=interaction.user,
            ):
                return

            channel = await self.get_log_channel(interaction.guild, "command_error")
            if not channel:
                return

            command = getattr(interaction, "command", None)
            command_name = getattr(command, "qualified_name", None) or getattr(
                command,
                "name",
                "Unknown command",
            )
            error_message = str(error)
            if len(error_message) > 1000:
                error_message = error_message[:997] + "..."

            embed = self.create_embed(
                "command_error",
                f"❌ Application command error: `/{command_name}`",
            )
            embed.add_field(
                name="User",
                value=f"{interaction.user.mention} (`{interaction.user}`, ID: `{interaction.user.id}`)",
                inline=True,
            )
            if event_channel:
                embed.add_field(
                    name="Channel",
                    value=f"{event_channel.mention} (`{event_channel.name}`)",
                    inline=True,
                )
            embed.add_field(
                name="Error Type",
                value=f"`{type(error).__name__}`",
                inline=True,
            )
            embed.add_field(
                name="Error Message",
                value=f"```\n{error_message}\n```",
                inline=False,
            )

            self.set_embed_footer(
                embed,
                label="YALC Logger • Application Command Error",
            )
            await self.safe_send(channel, embed=embed)
        except Exception as e:
            self.log.error(
                f"Failed to log application command error: {e}",
                exc_info=True,
            )

    @commands.Cog.listener()
    async def on_command_error(
        self,
        ctx: commands.Context,
        error: commands.CommandError,
    ) -> None:
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
            if not await self.should_log_event(
                ctx.guild,
                "command_error",
                channel=ctx.channel,
                user=ctx.author,
            ):
                return

            # Get the log channel
            log_channel = await self.get_log_channel(ctx.guild, "command_error")
            if not log_channel:
                return

            # Create the log embed
            command_name = (
                ctx.command.qualified_name if ctx.command else "Unknown command"
            )

            # Create embed description
            description = f"⚠️ Error occurred while executing command `{command_name}`"

            # Create embed with proper metadata
            embed = self.create_embed(
                "command_error",
                description,
            )

            # Add user info
            embed.add_field(
                name="User",
                value=f"{ctx.author.mention} (`{ctx.author}`, ID: `{ctx.author.id}`)",
                inline=True,
            )

            # Add command info
            embed.add_field(
                name="Command",
                value=f"`{ctx.message.content[:1000]}`"
                if len(ctx.message.content) <= 1000
                else f"`{ctx.message.content[:997]}...`",
                inline=False,
            )

            # Add channel info
            embed.add_field(
                name="Channel",
                value=f"{ctx.channel.mention} (`{ctx.channel.name}`)",
                inline=True,
            )

            # Add error info
            embed.add_field(
                name="Error Type",
                value=f"`{type(error).__name__}`",
                inline=True,
            )

            # Format error message
            error_message = str(error)
            if len(error_message) > 1024:
                error_message = error_message[:1021] + "..."

            embed.add_field(
                name="Error Message",
                value=f"```\n{error_message}\n```",
                inline=False,
            )

            # Add timestamp
            embed.add_field(
                name="Timestamp",
                value=discord.utils.format_dt(
                    datetime.datetime.now(datetime.UTC),
                    style="F",
                ),
                inline=True,
            )

            # Set thumbnail if appropriate
            if settings.get("include_thumbnails", True) and hasattr(
                ctx.author,
                "display_avatar",
            ):
                embed.set_thumbnail(url=ctx.author.display_avatar.url)

            # Set footer
            self.set_embed_footer(embed, label="YALC Logger • Command Error")

            # Send the log
            await self.safe_send(log_channel, embed=embed)

        except Exception as e:
            self.log.error(f"Error logging command_error: {e}", exc_info=True)

    @commands.Cog.listener()
    async def on_scheduled_event_create(self, event: discord.ScheduledEvent) -> None:
        """
        Log guild scheduled event creation.

        Parameters
        ----------
        event: discord.ScheduledEvent
            The scheduled event that was created
        """
        self.log.debug("Listener triggered: on_scheduled_event_create")

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
            log_channel = await self.get_log_channel(
                guild,
                "guild_scheduled_event_create",
            )
            if not log_channel:
                return

            # Get creator if available
            creator = None
            try:
                if event.creator_id:
                    creator = guild.get_member(
                        event.creator_id,
                    ) or await self.bot.fetch_user(event.creator_id)
            except Exception:
                pass

            # Create the log embed
            description = f"📅 Server event created: **{event.name}**"

            embed = self.create_embed(
                "guild_scheduled_event_create",
                description,
            )

            # Add event details
            embed.add_field(name="Name", value=event.name, inline=True)

            if event.description:
                embed.add_field(
                    name="Description",
                    value=event.description
                    if len(event.description) <= 1024
                    else f"{event.description[:1021]}...",
                    inline=False,
                )

            # Add location info
            if hasattr(event, "location") and event.location:
                embed.add_field(name="Location", value=event.location, inline=True)
            elif hasattr(event, "channel") and event.channel:
                embed.add_field(
                    name="Channel",
                    value=event.channel.mention,
                    inline=True,
                )

            # Add timing info
            if hasattr(event, "start_time") and event.start_time:
                embed.add_field(
                    name="Start Time",
                    value=discord.utils.format_dt(event.start_time, "F"),
                    inline=True,
                )

            if hasattr(event, "end_time") and event.end_time:
                embed.add_field(
                    name="End Time",
                    value=discord.utils.format_dt(event.end_time, "F"),
                    inline=True,
                )

            # Add creator info
            if creator:
                embed.add_field(
                    name="Created By",
                    value=f"{creator.mention} (`{creator}`, ID: `{creator.id}`)",
                    inline=True,
                )

                # Set thumbnail to creator's avatar
                if settings.get("include_thumbnails", True) and hasattr(
                    creator,
                    "display_avatar",
                ):
                    embed.set_thumbnail(url=creator.display_avatar.url)

            # Add event URL
            if hasattr(event, "url") and event.url:
                embed.add_field(
                    name="Event Link",
                    value=f"[Click to view]({event.url})",
                    inline=False,
                )

            # Set event image if available
            if hasattr(event, "image") and event.image:
                embed.set_image(url=event.image.url)

            # Set footer
            self.set_embed_footer(embed, label="YALC Logger • Event Created")

            # Send the log
            await self.safe_send(log_channel, embed=embed)

        except Exception as e:
            self.log.error(
                f"Error logging guild_scheduled_event_create: {e}",
                exc_info=True,
            )

    @commands.Cog.listener()
    async def on_scheduled_event_update(
        self,
        before: discord.ScheduledEvent,
        after: discord.ScheduledEvent,
    ) -> None:
        """
        Log guild scheduled event updates.

        Parameters
        ----------
        before: discord.ScheduledEvent
            The scheduled event before the update
        after: discord.ScheduledEvent
            The scheduled event after the update
        """
        self.log.debug("Listener triggered: on_scheduled_event_update")

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
            log_channel = await self.get_log_channel(
                guild,
                "guild_scheduled_event_update",
            )
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
                changes.append("**Description:** Changed")

            if (
                hasattr(before, "location")
                and hasattr(after, "location")
                and before.location != after.location
            ):
                changes.append(
                    f"**Location:** `{before.location or 'None'}` → `{after.location or 'None'}`",
                )

            if (
                hasattr(before, "channel_id")
                and hasattr(after, "channel_id")
                and before.channel_id != after.channel_id
            ):
                changes.append(
                    f"**Channel:** <#{before.channel_id or 'None'}> → <#{after.channel_id or 'None'}>",
                )

            if before.start_time != after.start_time:
                before_time = (
                    discord.utils.format_dt(before.start_time, "F")
                    if before.start_time
                    else "None"
                )
                after_time = (
                    discord.utils.format_dt(after.start_time, "F")
                    if after.start_time
                    else "None"
                )
                changes.append(f"**Start Time:** {before_time} → {after_time}")

            if (
                hasattr(before, "end_time")
                and hasattr(after, "end_time")
                and before.end_time != after.end_time
            ):
                before_time = (
                    discord.utils.format_dt(before.end_time, "F")
                    if before.end_time
                    else "None"
                )
                after_time = (
                    discord.utils.format_dt(after.end_time, "F")
                    if after.end_time
                    else "None"
                )
                changes.append(f"**End Time:** {before_time} → {after_time}")

            if (
                hasattr(before, "status")
                and hasattr(after, "status")
                and before.status != after.status
            ):
                changes.append(f"**Status:** `{before.status}` → `{after.status}`")

            # Skip if no changes (shouldn't happen, but just in case)
            if not changes:
                return

            # Create the log embed
            description = f"🔄 Server event updated: **{after.name}**"

            embed = self.create_embed(
                "guild_scheduled_event_update",
                description,
            )

            # Add changes
            embed.add_field(
                name="Changes",
                value="\n".join(changes),
                inline=False,
            )

            # Add event details
            embed.add_field(name="Event ID", value=f"`{after.id}`", inline=True)

            # Add event URL
            if hasattr(after, "url") and after.url:
                embed.add_field(
                    name="Event Link",
                    value=f"[Click to view]({after.url})",
                    inline=False,
                )

            # Set event image if available
            if hasattr(after, "image") and after.image:
                embed.set_image(url=after.image.url)

            # Set footer
            self.set_embed_footer(embed, label="YALC Logger • Event Updated")

            # Send the log
            await self.safe_send(log_channel, embed=embed)

        except Exception as e:
            self.log.error(
                f"Error logging guild_scheduled_event_update: {e}",
                exc_info=True,
            )

    @commands.Cog.listener()
    async def on_scheduled_event_delete(self, event: discord.ScheduledEvent) -> None:
        """
        Log guild scheduled event deletion.

        Parameters
        ----------
        event: discord.ScheduledEvent
            The scheduled event that was deleted
        """
        self.log.debug("Listener triggered: on_scheduled_event_delete")

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
            log_channel = await self.get_log_channel(
                guild,
                "guild_scheduled_event_delete",
            )
            if not log_channel:
                return

            # Get creator if available
            creator = None
            try:
                if event.creator_id:
                    creator = guild.get_member(
                        event.creator_id,
                    ) or await self.bot.fetch_user(event.creator_id)
            except Exception:
                pass

            # Create the log embed
            description = f"🗑️ Server event deleted: **{event.name}**"

            embed = self.create_embed(
                "guild_scheduled_event_delete",
                description,
            )

            # Add event details
            embed.add_field(name="Name", value=event.name, inline=True)
            embed.add_field(name="Event ID", value=f"`{event.id}`", inline=True)

            if event.description:
                embed.add_field(
                    name="Description",
                    value=event.description
                    if len(event.description) <= 1024
                    else f"{event.description[:1021]}...",
                    inline=False,
                )

            # Add location info
            if hasattr(event, "location") and event.location:
                embed.add_field(name="Location", value=event.location, inline=True)
            elif hasattr(event, "channel") and event.channel:
                embed.add_field(
                    name="Channel",
                    value=event.channel.mention,
                    inline=True,
                )

            # Add timing info
            if hasattr(event, "start_time") and event.start_time:
                embed.add_field(
                    name="Scheduled Start",
                    value=discord.utils.format_dt(event.start_time, "F"),
                    inline=True,
                )

            # Add creator info
            if creator:
                embed.add_field(
                    name="Created By",
                    value=f"{creator.mention} (`{creator}`, ID: `{creator.id}`)",
                    inline=True,
                )

                # Set thumbnail to creator's avatar
                if settings.get("include_thumbnails", True) and hasattr(
                    creator,
                    "display_avatar",
                ):
                    embed.set_thumbnail(url=creator.display_avatar.url)

            # Set event image if available
            if hasattr(event, "image") and event.image:
                embed.set_image(url=event.image.url)

            # Set footer
            self.set_embed_footer(embed, label="YALC Logger • Event Deleted")

            # Send the log
            await self.safe_send(log_channel, embed=embed)

        except Exception as e:
            self.log.error(
                f"Error logging guild_scheduled_event_delete: {e}",
                exc_info=True,
            )

    @commands.Cog.listener()
    async def on_stage_instance_create(self, stage_instance) -> None:
        """Log stage instance creation."""
        stage_channel = getattr(stage_instance, "channel", None)
        guild = getattr(stage_instance, "guild", None) or getattr(
            stage_channel,
            "guild",
            None,
        )
        if not guild:
            return

        try:
            if not await self.should_log_event(
                guild,
                "stage_instance_create",
                channel=getattr(stage_instance, "channel", None),
            ):
                return

            channel = await self.get_log_channel(guild, "stage_instance_create")
            if not channel:
                return

            audit_entry = await self._get_audit_log_entry(
                guild,
                self._get_audit_action("stage_instance_create"),
                target=stage_instance,
                timeout_seconds=10,
            )

            topic = getattr(stage_instance, "topic", "Unknown topic")
            embed = self.create_embed(
                "stage_instance_create",
                f"🎤 Stage instance created: **{topic}**",
            )
            if stage_channel:
                embed.add_field(
                    name="Stage Channel",
                    value=f"{stage_channel.mention} (`{stage_channel.name}`, ID: `{stage_channel.id}`)",
                    inline=True,
                )
            if audit_entry and audit_entry.user:
                embed.add_field(
                    name="Created By",
                    value=f"{audit_entry.user.mention} (`{audit_entry.user}`, ID: `{audit_entry.user.id}`)",
                    inline=True,
                )
                if audit_entry.reason:
                    embed.add_field(
                        name="Reason",
                        value=audit_entry.reason,
                        inline=False,
                    )

            self.set_embed_footer(embed, label="YALC Logger • Stage Created")
            await self.safe_send(channel, embed=embed)
        except Exception as e:
            self.log.error(f"Failed to log stage_instance_create: {e}", exc_info=True)

    @commands.Cog.listener()
    async def on_stage_instance_update(self, before, after) -> None:
        """Log stage instance updates."""
        stage_channel = getattr(after, "channel", None)
        guild = getattr(after, "guild", None) or getattr(stage_channel, "guild", None)
        if not guild:
            return

        try:
            if not await self.should_log_event(
                guild,
                "stage_instance_update",
                channel=getattr(after, "channel", None),
            ):
                return

            channel = await self.get_log_channel(guild, "stage_instance_update")
            if not channel:
                return

            changes = []
            if getattr(before, "topic", None) != getattr(after, "topic", None):
                changes.append(
                    f"Topic: `{getattr(before, 'topic', None)}` → `{getattr(after, 'topic', None)}`",
                )
            if getattr(before, "privacy_level", None) != getattr(
                after,
                "privacy_level",
                None,
            ):
                changes.append(
                    f"Privacy: `{getattr(before, 'privacy_level', None)}` → `{getattr(after, 'privacy_level', None)}`",
                )

            if not changes:
                return

            audit_entry = await self._get_audit_log_entry(
                guild,
                self._get_audit_action("stage_instance_update"),
                target=after,
                timeout_seconds=10,
            )

            embed = self.create_embed(
                "stage_instance_update",
                f"🔄 Stage instance updated: **{getattr(after, 'topic', 'Unknown topic')}**",
                changes="\n".join(changes),
            )
            if stage_channel:
                embed.add_field(
                    name="Stage Channel",
                    value=stage_channel.mention,
                    inline=True,
                )
            if audit_entry and audit_entry.user:
                embed.add_field(
                    name="Updated By",
                    value=f"{audit_entry.user.mention} (`{audit_entry.user}`, ID: `{audit_entry.user.id}`)",
                    inline=True,
                )
                if audit_entry.reason:
                    embed.add_field(
                        name="Reason",
                        value=audit_entry.reason,
                        inline=False,
                    )

            self.set_embed_footer(embed, label="YALC Logger • Stage Updated")
            await self.safe_send(channel, embed=embed)
        except Exception as e:
            self.log.error(f"Failed to log stage_instance_update: {e}", exc_info=True)

    @commands.Cog.listener()
    async def on_stage_instance_delete(self, stage_instance) -> None:
        """Log stage instance deletion."""
        stage_channel = getattr(stage_instance, "channel", None)
        guild = getattr(stage_instance, "guild", None) or getattr(
            stage_channel,
            "guild",
            None,
        )
        if not guild:
            return

        try:
            if not await self.should_log_event(
                guild,
                "stage_instance_delete",
                channel=getattr(stage_instance, "channel", None),
            ):
                return

            channel = await self.get_log_channel(guild, "stage_instance_delete")
            if not channel:
                return

            audit_entry = await self._get_audit_log_entry(
                guild,
                self._get_audit_action("stage_instance_delete"),
                target=stage_instance,
                timeout_seconds=10,
            )

            embed = self.create_embed(
                "stage_instance_delete",
                f"🗑️ Stage instance deleted: **{getattr(stage_instance, 'topic', 'Unknown topic')}**",
            )
            if stage_channel:
                embed.add_field(
                    name="Stage Channel",
                    value=stage_channel.mention,
                    inline=True,
                )
            if audit_entry and audit_entry.user:
                embed.add_field(
                    name="Deleted By",
                    value=f"{audit_entry.user.mention} (`{audit_entry.user}`, ID: `{audit_entry.user.id}`)",
                    inline=True,
                )
                if audit_entry.reason:
                    embed.add_field(
                        name="Reason",
                        value=audit_entry.reason,
                        inline=False,
                    )

            self.set_embed_footer(embed, label="YALC Logger • Stage Deleted")
            await self.safe_send(channel, embed=embed)
        except Exception as e:
            self.log.error(f"Failed to log stage_instance_delete: {e}", exc_info=True)

    @commands.Cog.listener()
    async def on_soundboard_sound_create(self, sound) -> None:
        """Log soundboard sound creation."""
        guild = getattr(sound, "guild", None) or self.bot.get_guild(
            getattr(sound, "guild_id", 0),
        )
        if not guild:
            return

        try:
            if not await self.should_log_event(
                guild,
                "soundboard_sound_create",
                user=getattr(sound, "user", None),
            ):
                return

            channel = await self.get_log_channel(guild, "soundboard_sound_create")
            if not channel:
                return

            audit_entry = await self._get_audit_log_entry(
                guild,
                self._get_audit_action("soundboard_sound_create"),
                target=sound,
                timeout_seconds=10,
            )

            embed = self.create_embed(
                "soundboard_sound_create",
                f"🔉 Soundboard sound created: **{getattr(sound, 'name', 'Unknown sound')}**",
            )
            embed.add_field(
                name="Sound ID",
                value=f"`{getattr(sound, 'id', 'Unknown')}`",
                inline=True,
            )
            emoji = getattr(sound, "emoji", None)
            if emoji:
                embed.add_field(name="Emoji", value=str(emoji), inline=True)
            if audit_entry and audit_entry.user:
                embed.add_field(
                    name="Created By",
                    value=f"{audit_entry.user.mention} (`{audit_entry.user}`, ID: `{audit_entry.user.id}`)",
                    inline=True,
                )

            self.set_embed_footer(embed, label="YALC Logger • Soundboard Sound Created")
            await self.safe_send(channel, embed=embed)
        except Exception as e:
            self.log.error(f"Failed to log soundboard_sound_create: {e}", exc_info=True)

    @commands.Cog.listener()
    async def on_soundboard_sound_update(self, before, after) -> None:
        """Log soundboard sound updates."""
        guild = getattr(after, "guild", None) or self.bot.get_guild(
            getattr(after, "guild_id", 0),
        )
        if not guild:
            return

        try:
            if not await self.should_log_event(
                guild,
                "soundboard_sound_update",
                user=getattr(after, "user", None),
            ):
                return

            channel = await self.get_log_channel(guild, "soundboard_sound_update")
            if not channel:
                return

            changes = []
            if getattr(before, "name", None) != getattr(after, "name", None):
                changes.append(
                    f"Name: `{getattr(before, 'name', None)}` → `{getattr(after, 'name', None)}`",
                )
            if getattr(before, "volume", None) != getattr(after, "volume", None):
                changes.append(
                    f"Volume: `{getattr(before, 'volume', None)}` → `{getattr(after, 'volume', None)}`",
                )
            if getattr(before, "emoji", None) != getattr(after, "emoji", None):
                changes.append(
                    f"Emoji: `{getattr(before, 'emoji', None)}` → `{getattr(after, 'emoji', None)}`",
                )

            if not changes:
                return

            audit_entry = await self._get_audit_log_entry(
                guild,
                self._get_audit_action("soundboard_sound_update"),
                target=after,
                timeout_seconds=10,
            )

            embed = self.create_embed(
                "soundboard_sound_update",
                f"🔊 Soundboard sound updated: **{getattr(after, 'name', 'Unknown sound')}**",
                changes="\n".join(changes),
            )
            if audit_entry and audit_entry.user:
                embed.add_field(
                    name="Updated By",
                    value=f"{audit_entry.user.mention} (`{audit_entry.user}`, ID: `{audit_entry.user.id}`)",
                    inline=True,
                )

            self.set_embed_footer(embed, label="YALC Logger • Soundboard Sound Updated")
            await self.safe_send(channel, embed=embed)
        except Exception as e:
            self.log.error(f"Failed to log soundboard_sound_update: {e}", exc_info=True)

    @commands.Cog.listener()
    async def on_soundboard_sound_delete(self, sound) -> None:
        """Log soundboard sound deletion."""
        guild = getattr(sound, "guild", None) or self.bot.get_guild(
            getattr(sound, "guild_id", 0),
        )
        if not guild:
            return

        try:
            if not await self.should_log_event(
                guild,
                "soundboard_sound_delete",
                user=getattr(sound, "user", None),
            ):
                return

            channel = await self.get_log_channel(guild, "soundboard_sound_delete")
            if not channel:
                return

            audit_entry = await self._get_audit_log_entry(
                guild,
                self._get_audit_action("soundboard_sound_delete"),
                target=sound,
                timeout_seconds=10,
            )

            embed = self.create_embed(
                "soundboard_sound_delete",
                f"🔇 Soundboard sound deleted: **{getattr(sound, 'name', 'Unknown sound')}**",
            )
            embed.add_field(
                name="Sound ID",
                value=f"`{getattr(sound, 'id', 'Unknown')}`",
                inline=True,
            )
            if audit_entry and audit_entry.user:
                embed.add_field(
                    name="Deleted By",
                    value=f"{audit_entry.user.mention} (`{audit_entry.user}`, ID: `{audit_entry.user.id}`)",
                    inline=True,
                )

            self.set_embed_footer(embed, label="YALC Logger • Soundboard Sound Deleted")
            await self.safe_send(channel, embed=embed)
        except Exception as e:
            self.log.error(f"Failed to log soundboard_sound_delete: {e}", exc_info=True)

    @commands.hybrid_group(name="yalc", aliases=["logger"], invoke_without_command=True)
    @commands.guild_only()
    async def yalc_group(self, ctx: commands.Context):
        """
        Yet Another Logging Cog - Main commands.

        This command group provides access to all YALC logging configuration commands.
        Run a subcommand to perform a specific action.
        """
        await ctx.send_help(ctx.command)

    @yalc_group.command(name="test", aliases=["diagnostics", "debug"])
    @commands.guild_only()
    async def yalc_test(self, ctx: commands.Context):
        """Test YALC voice logging functionality and show comprehensive diagnostic information."""
        try:
            # Create main diagnostic embed
            embed = discord.Embed(
                title="🔍 YALC System Diagnostics",
                description="Comprehensive system health check and voice session analysis",
                color=discord.Color.blue(),
                timestamp=datetime.datetime.now(datetime.UTC),
            )

            # System Status Section
            embed.add_field(
                name="🤖 System Status",
                value="✅ YALC Cog loaded\n"
                f"✅ Guild: {ctx.guild.name}\n"
                f"✅ Bot latency: {self.bot.latency * 1000:.1f}ms\n"
                f"✅ Guild members: {ctx.guild.member_count}",
                inline=False,
            )

            # Voice Session Statistics
            session_stats = await self._get_voice_session_stats(ctx.guild)

            embed.add_field(
                name="🎧 Voice Session Statistics",
                value="### Current Status\n"
                f"• Active sessions: **{session_stats['active_sessions']}**\n"
                f"• Total sessions tracked: **{session_stats['total_sessions']}**\n"
                f"• Channels with activity: **{len(session_stats['sessions_by_channel'])}**",
                inline=False,
            )

            # Active Voice Sessions
            active_sessions = await self._get_active_voice_sessions(ctx.guild)

            if active_sessions:
                session_info = []
                for session in active_sessions[:5]:  # Show first 5
                    try:
                        member = ctx.guild.get_member(session["user_id"])
                        member_display = (
                            member.mention if member else f"ID: {session['user_id']}"
                        )

                        channel = ctx.guild.get_channel(session["channel_id"])
                        channel_name = (
                            channel.name if channel else f"ID: {session['channel_id']}"
                        )

                        duration = self._format_duration(session["duration"])
                        session_info.append(
                            f"• {member_display} in **#{channel_name}** ({duration})",
                        )
                    except Exception:
                        session_info.append(
                            f"• Unknown user in unknown channel ({self._format_duration(session['duration'])})",
                        )

                if len(active_sessions) > 5:
                    session_info.append(
                        f"• ...and {len(active_sessions) - 5} more sessions",
                    )

                embed.add_field(
                    name="🔊 Active Sessions",
                    value="\n".join(session_info),
                    inline=False,
                )
            else:
                embed.add_field(
                    name="🔊 Active Sessions",
                    value="*No active voice sessions*",
                    inline=False,
                )

            # Recent Voice Events
            recent_events = await self._get_recent_voice_events(ctx.guild, limit=5)

            if recent_events:
                event_info = []
                for event in recent_events:
                    try:
                        member = ctx.guild.get_member(
                            event["user_id"],
                        ) or await self.bot.fetch_user(event["user_id"])
                        member_display = (
                            member.mention
                            if hasattr(member, "mention")
                            else str(member)
                        )

                        channel = ctx.guild.get_channel(event["channel_id"])
                        channel_name = (
                            f"#{channel.name}"
                            if channel
                            else f"ID: {event['channel_id']}"
                        )

                        event_time = datetime.datetime.fromtimestamp(
                            event["timestamp"],
                            tz=datetime.timezone.utc,
                        )
                        relative_time = discord.utils.format_dt(event_time, style="R")

                        duration_text = ""
                        if event.get("duration") and event["duration"] > 0:
                            duration_text = (
                                f" ({self._format_duration(event['duration'])})"
                            )

                        event_info.append(
                            f"• **{event['event_type']}** - {member_display} {channel_name}{duration_text}",
                        )
                        event_info.append(f"  {relative_time}")  # No emoji, clean
                        event_info.append("")  # Empty line for spacing

                    except Exception as e:
                        self.log.debug(f"Error processing event: {e}")
                        continue

                embed.add_field(
                    name="📜 Recent Voice Events",
                    value="\n".join(event_info)[:1024],  # Discord embed field limit
                    inline=False,
                )
            else:
                embed.add_field(
                    name="📜 Recent Voice Events",
                    value="*No recent voice events*",
                    inline=False,
                )

            # Voice Channels Monitoring
            voice_channels = [
                vc for vc in ctx.guild.channels if isinstance(vc, discord.VoiceChannel)
            ]
            voice_stats = []

            for vc in voice_channels:
                member_count = len(vc.members) if vc.members else 0
                if (
                    member_count > 0 or len(voice_channels) <= 10
                ):  # Show active channels or if we have few channels
                    voice_stats.append(
                        f"• **#{vc.name}**: {member_count} members ({'active' if member_count > 0 else 'empty'})",
                    )

            if voice_stats:
                embed.add_field(
                    name="🔊 Voice Channels Status",
                    value="\n".join(voice_stats[:10])
                    + (
                        f"\n*...and {len(voice_channels) - 10} more*"
                        if len(voice_channels) > 10
                        else ""
                    ),
                    inline=False,
                )
            else:
                embed.add_field(
                    name="🔊 Voice Channels Status",
                    value=f"Found {len(voice_channels)} voice channels, all currently empty",
                    inline=False,
                )

            # Configuration Check
            settings = await self.config.guild(ctx.guild).all()
            enabled_voice_events = [
                event
                for event in self.event_descriptions
                if event.startswith("voice_") and settings["events"].get(event, False)
            ]

            embed.add_field(
                name="⚙️ Voice Configuration",
                value=f"• Voice state update event: {'✅ Enabled' if settings['events'].get('voice_state_update', False) else '❌ Disabled'}\n"
                f"• Log channel configured: {'✅ Yes' if settings['event_channels'].get('voice_state_update') else '❌ No'}\n"
                f"• Voice events enabled: **{len(enabled_voice_events)}**\n"
                f"• Ignore bots: {'✅ Yes' if settings.get('ignore_bots', False) else '❌ No'}",
                inline=False,
            )

            # Performance Info
            embed.add_field(
                name="⚡ Performance",
                value="• Voice session tracking: ✅ Active\n"
                "• Real-time updates: ✅ Enabled\n"
                "• Database persistence: ✅ Config-based\n"
                "• Event logging: ✅ Last 50 events stored",
                inline=False,
            )

            # Add footer
            embed.set_footer(
                text="YALC Diagnostic Report",
                icon_url="https://cdn-icons-png.flaticon.com/512/928/928797.png",
            )

            await ctx.send(embed=embed)

            # Send summary message
            await ctx.send(
                "✅ **YALC Diagnostics Complete!**\n"
                f"🎧 Found {session_stats['active_sessions']} active voice sessions\n"
                f"📊 Tracked {len(recent_events)} recent voice events\n"
                f"🔊 Monitoring {len(voice_channels)} voice channels",
            )

        except Exception as e:
            error_embed = discord.Embed(
                title="❌ Diagnostic Error",
                description=f"An error occurred during diagnostics:\n```{e}```",
                color=discord.Color.red(),
                timestamp=datetime.datetime.now(datetime.UTC),
            )
            await ctx.send(embed=error_embed)
            self.log.error(f"Error in YALC test command: {e}", exc_info=True)

    @yalc_group.command(name="enable")
    @commands.admin_or_permissions(manage_guild=True)
    async def yalc_enable(self, ctx: commands.Context, event_type: str | None = None):
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
                color=discord.Color.blue(),
            )

            # Group events by category
            categories = {
                "Message Events": [
                    k for k in self.event_descriptions if k.startswith("message_")
                ],
                "Member Events": [
                    k for k in self.event_descriptions if k.startswith("member_")
                ],
                "Channel Events": [
                    k
                    for k in self.event_descriptions
                    if k.startswith(("channel_", "thread_", "forum_"))
                ],
                "Role Events": [
                    k for k in self.event_descriptions if k.startswith("role_")
                ],
                "Guild Events": [
                    k
                    for k in self.event_descriptions
                    if k.startswith(("guild_", "emoji_", "sticker_", "invite_"))
                ],
                "Voice/Stage Events": [
                    k
                    for k in self.event_descriptions
                    if k.startswith(("voice_", "stage_"))
                ],
                "Application Events": [
                    k
                    for k in self.event_descriptions
                    if k.startswith(
                        (
                            "command_",
                            "application_",
                            "integration_",
                            "webhook_",
                            "automod_",
                            "soundboard_",
                        ),
                    )
                ],
                "Other Events": [
                    k
                    for k in self.event_descriptions
                    if not any(
                        k.startswith(p)
                        for p in [
                            "message_",
                            "member_",
                            "channel_",
                            "thread_",
                            "forum_",
                            "role_",
                            "guild_",
                            "emoji_",
                            "sticker_",
                            "invite_",
                            "voice_",
                            "stage_",
                            "command_",
                            "application_",
                            "integration_",
                            "webhook_",
                            "automod_",
                            "soundboard_",
                        ]
                    )
                ],
            }

            # Add fields for each category
            for category, events in categories.items():
                if events:
                    event_list = "\n".join(
                        [
                            f"{self.event_descriptions[e][0]} `{e}` - {self.event_descriptions[e][1]}"
                            for e in events
                        ],
                    )
                    embed.add_field(name=category, value=event_list, inline=False)

            embed.set_footer(
                text=f"Use {ctx.prefix}yalc enable <event_type> to enable a specific event type",
            )
            await ctx.send(embed=embed)
            return

        # Check if the event type exists
        if event_type not in self.event_descriptions:
            await ctx.send(
                f"❌ Unknown event type: `{event_type}`. Use `{ctx.prefix}yalc enable` to see all available event types.",
            )
            return

        # Enable the event
        async with self.config.guild(ctx.guild).events() as events:
            events[event_type] = True
        self._invalidate_settings_cache(ctx.guild)

        # Get description for confirmation message
        emoji, description = self.event_descriptions[event_type]
        await ctx.send(
            f"✅ {emoji} Enabled logging for **{description}** (`{event_type}`).",
        )

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
            await ctx.send(
                f"❌ Unknown event type: `{event_type}`. Use `{ctx.prefix}yalc enable` to see all available event types.",
            )
            return

        # Disable the event
        async with self.config.guild(ctx.guild).events() as events:
            events[event_type] = False
        self._invalidate_settings_cache(ctx.guild)

        # Get description for confirmation message
        emoji, description = self.event_descriptions[event_type]
        await ctx.send(
            f"✅ {emoji} Disabled logging for **{description}** (`{event_type}`).",
        )

    @yalc_group.command(name="setchannel")
    @commands.admin_or_permissions(manage_guild=True)
    async def yalc_setchannel(
        self,
        ctx: commands.Context,
        event_type: str,
        channel: discord.TextChannel = None,
    ):
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
            await ctx.send(
                f"❌ Unknown event type: `{event_type}`. Use `{ctx.prefix}yalc enable` to see all available event types.",
            )
            return

        # Set the channel
        if event_type == "all":
            # Set for all event types
            async with self.config.guild(ctx.guild).event_channels() as event_channels:
                for et in self.event_descriptions:
                    event_channels[et] = channel.id
            self._invalidate_settings_cache(ctx.guild)
            await ctx.send(
                f"✅ Set {channel.mention} as the logging channel for **all** event types.",
            )
        else:
            # Set for a specific event type
            async with self.config.guild(ctx.guild).event_channels() as event_channels:
                event_channels[event_type] = channel.id
            self._invalidate_settings_cache(ctx.guild)

            # Get description for confirmation message
            emoji, description = self.event_descriptions[event_type]
            await ctx.send(
                f"✅ {emoji} Set {channel.mention} as the logging channel for **{description}** (`{event_type}`).",
            )

    @yalc_group.command(name="settings")
    @commands.guild_only()
    async def yalc_settings(self, ctx: commands.Context):
        """View the current YALC settings for this server, paginated if too long."""
        settings = await self.config.guild(ctx.guild).all()

        embeds = []

        # Page 1: Enabled Events with Channel Info
        enabled_events_with_channels = []
        for event, enabled in settings["events"].items():
            if enabled:
                channel_id = settings["event_channels"].get(event)
                channel_info = ""
                if channel_id:
                    channel = ctx.guild.get_channel(channel_id)
                    if channel:
                        channel_info = f" → {channel.mention}"
                    else:
                        channel_info = " → *Channel not found*"
                else:
                    channel_info = " → *No channel set*"

                emoji, description = self.event_descriptions[event]
                enabled_events_with_channels.append(
                    f"{emoji} `{event}` - {description}{channel_info}",
                )

        embed_events = discord.Embed(
            title="YALC Logger Settings",
            description="Enabled Events with Channel Configuration",
            color=discord.Color.blue(),
        )
        if enabled_events_with_channels:
            for i in range(0, len(enabled_events_with_channels), 10):
                embed_events.add_field(
                    name=f"📋 Enabled Events {i + 1}-{min(i + 10, len(enabled_events_with_channels))}",
                    value="\n".join(enabled_events_with_channels[i : i + 10]),
                    inline=False,
                )
        else:
            embed_events.add_field(
                name="📋 Enabled Events",
                value="No events enabled",
                inline=False,
            )
        embeds.append(embed_events)

        # Page 2: Event Channels
        channel_mappings = []
        for event, channel_id in settings["event_channels"].items():
            if channel_id:
                channel = ctx.guild.get_channel(channel_id)
                if channel and event in self.event_descriptions:
                    channel_mappings.append(
                        f"{self.event_descriptions[event][0]} `{event}` → {channel.mention}",
                    )
        embed_channels = discord.Embed(
            title="YALC Logger Settings",
            description="Event Channels",
            color=discord.Color.blue(),
        )
        if channel_mappings:
            for i in range(0, len(channel_mappings), 10):
                embed_channels.add_field(
                    name=f"📢 Event Channels {i + 1}-{min(i + 10, len(channel_mappings))}",
                    value="\n".join(channel_mappings[i : i + 10]),
                    inline=False,
                )
        else:
            embed_channels.add_field(
                name="📢 Event Channels",
                value="No channels configured",
                inline=False,
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
            ignore_settings.append(
                f"🚫 Ignored Roles: {', '.join(role_names)}"
                + (
                    f" *and {len(ignored_roles) - 3} more*"
                    if len(ignored_roles) > 3
                    else ""
                ),
            )
        ignored_users = settings.get("ignored_users", [])
        if ignored_users:
            ignore_settings.append(f"🚫 Ignored Users: {len(ignored_users)}")
        ignored_channels = settings.get("ignored_channels", [])
        if ignored_channels:
            channel_names = [f"<#{channel_id}>" for channel_id in ignored_channels[:3]]
            ignore_settings.append(
                f"🚫 Ignored Channels: {', '.join(channel_names)}"
                + (
                    f" *and {len(ignored_channels) - 3} more*"
                    if len(ignored_channels) > 3
                    else ""
                ),
            )
        embed_ignore = discord.Embed(
            title="YALC Logger Settings",
            description="Ignore Settings",
            color=discord.Color.blue(),
        )
        if ignore_settings:
            embed_ignore.add_field(
                name="⚙️ Broad Ignore Settings",
                value="\n".join(ignore_settings),
                inline=False,
            )
        else:
            embed_ignore.add_field(
                name="⚙️ Broad Ignore Settings",
                value="No broad ignore settings configured",
                inline=False,
            )

        # Add granular ignore rules
        granular_ignores = settings.get("granular_ignores", [])
        if granular_ignores:
            granular_rules = []
            for rule in granular_ignores[:5]:  # Show first 5
                # Get user
                user = ctx.guild.get_member(rule["user_id"])
                user_display = user.mention if user else f"ID: {rule['user_id']}"

                # Get channel
                channel = ctx.guild.get_channel(rule["channel_id"])
                channel_display = (
                    channel.mention if channel else f"ID: {rule['channel_id']}"
                )

                # Get event info
                event_type = rule["event_type"]
                emoji, description = self.event_descriptions.get(
                    event_type,
                    ("📝", event_type),
                )

                # Format rule
                rule_text = (
                    f"{emoji} **{event_type}** from {user_display} in {channel_display}"
                )
                if rule.get("reason"):
                    rule_text += f" *(Reason: {rule['reason']})*"

                granular_rules.append(rule_text)

            if len(granular_ignores) > 5:
                granular_rules.append(
                    f"*...and {len(granular_ignores) - 5} more rules*",
                )

            embed_ignore.add_field(
                name=f"🎯 Granular Ignore Rules ({len(granular_ignores)})",
                value="\n".join(granular_rules),
                inline=False,
            )
        else:
            embed_ignore.add_field(
                name="🎯 Granular Ignore Rules",
                value="*No granular ignore rules set*",
                inline=False,
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
        self._invalidate_settings_cache(ctx.guild)

        await ctx.send(f"✅ Now ignoring events from user {user.mention}.")

    @yalc_ignore.command(name="channel")
    async def yalc_ignore_channel(
        self,
        ctx: commands.Context,
        channel: discord.TextChannel,
    ):
        """
        Ignore a channel from logging events.

        Parameters
        ----------
        channel: discord.TextChannel
            The channel to ignore
        """
        async with self.config.guild(ctx.guild).ignored_channels() as ignored_channels:
            if channel.id in ignored_channels:
                await ctx.send(
                    f"❌ Channel {channel.mention} is already being ignored.",
                )
                return

            ignored_channels.append(channel.id)
        self._invalidate_settings_cache(ctx.guild)

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
        self._invalidate_settings_cache(ctx.guild)

        await ctx.send(
            f"✅ Now ignoring events from users with the role {role.mention}.",
        )

    @yalc_ignore.command(name="category")
    async def yalc_ignore_category(
        self,
        ctx: commands.Context,
        category: discord.CategoryChannel,
    ):
        """
        Ignore an entire category from logging events.

        Parameters
        ----------
        category: discord.CategoryChannel
            The category to ignore
        """
        async with self.config.guild(
            ctx.guild,
        ).ignored_categories() as ignored_categories:
            if category.id in ignored_categories:
                await ctx.send(
                    f"❌ Category '{category.name}' is already being ignored.",
                )
                return

            ignored_categories.append(category.id)
        self._invalidate_settings_cache(ctx.guild)

        await ctx.send(
            f"✅ Now ignoring events from all channels in the '{category.name}' category.",
        )

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
        self._invalidate_settings_cache(ctx.guild)

        await ctx.send(f"✅ No longer ignoring events from user {user.mention}.")

    @yalc_unignore.command(name="channel")
    async def yalc_unignore_channel(
        self,
        ctx: commands.Context,
        channel: discord.TextChannel,
    ):
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
        self._invalidate_settings_cache(ctx.guild)

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
        self._invalidate_settings_cache(ctx.guild)

        await ctx.send(
            f"✅ No longer ignoring events from users with the role {role.mention}.",
        )

    @yalc_unignore.command(name="category")
    async def yalc_unignore_category(
        self,
        ctx: commands.Context,
        category: discord.CategoryChannel,
    ):
        """
        Unignore a previously ignored category.

        Parameters
        ----------
        category: discord.CategoryChannel
            The category to stop ignoring
        """
        async with self.config.guild(
            ctx.guild,
        ).ignored_categories() as ignored_categories:
            if category.id not in ignored_categories:
                await ctx.send(f"❌ Category '{category.name}' is not being ignored.")
                return

            ignored_categories.remove(category.id)
        self._invalidate_settings_cache(ctx.guild)

        await ctx.send(
            f"✅ No longer ignoring events from channels in the '{category.name}' category.",
        )

    @yalc_ignore.command(name="specific")
    async def yalc_ignore_specific(
        self,
        ctx: commands.Context,
        event_type: str,
        user: discord.Member,
        channel: discord.TextChannel,
        *,
        reason: str | None = None,
    ):
        """
        Ignore a specific event type from a specific user in a specific channel.

        This allows granular control - for example, ignoring message edits from a particular
        user in a particular channel while still logging their other events.

        Parameters
        ----------
        event_type: str
            The event type to ignore (e.g., message_edit, message_delete)
        user: discord.Member
            The user to ignore for this event type in this channel
        channel: discord.TextChannel
            The channel where this user's events of this type should be ignored
        reason: str, optional
            Optional reason for this ignore rule
        """
        # Check if the event type exists
        if event_type not in self.event_descriptions:
            await ctx.send(
                f"❌ Unknown event type: `{event_type}`. Use `{ctx.prefix}yalc enable` to see all available event types.",
            )
            return

        # Check if this rule already exists
        async with self.config.guild(ctx.guild).granular_ignores() as granular_ignores:
            existing_rule = None
            for rule in granular_ignores:
                if (
                    rule["event_type"] == event_type
                    and rule["user_id"] == user.id
                    and rule["channel_id"] == channel.id
                ):
                    existing_rule = rule
                    break

            if existing_rule:
                await ctx.send(
                    f"❌ Already ignoring `{event_type}` events from {user.mention} in {channel.mention}.",
                )
                return

            # Create the new rule
            new_rule = {
                "event_type": event_type,
                "user_id": user.id,
                "channel_id": channel.id,
                "created_by": ctx.author.id,
                "created_at": datetime.datetime.now(datetime.UTC).isoformat(),
                "reason": reason,
            }

            granular_ignores.append(new_rule)
        self._invalidate_settings_cache(ctx.guild)

        # Get description for confirmation message
        emoji, description = self.event_descriptions[event_type]
        reason_text = f" (Reason: {reason})" if reason else ""
        await ctx.send(
            f"✅ {emoji} Now ignoring **{description}** events from {user.mention} in {channel.mention}.{reason_text}",
        )

    @yalc_unignore.command(name="specific")
    async def yalc_unignore_specific(
        self,
        ctx: commands.Context,
        event_type: str,
        user: discord.Member,
        channel: discord.TextChannel,
    ):
        """
        Remove a specific granular ignore rule.

        Parameters
        ----------
        event_type: str
            The event type to stop ignoring
        user: discord.Member
            The user to stop ignoring for this event type in this channel
        channel: discord.TextChannel
            The channel where this user's events should no longer be ignored
        """
        # Check if the event type exists
        if event_type not in self.event_descriptions:
            await ctx.send(
                f"❌ Unknown event type: `{event_type}`. Use `{ctx.prefix}yalc enable` to see all available event types.",
            )
            return

        # Find and remove the rule
        async with self.config.guild(ctx.guild).granular_ignores() as granular_ignores:
            rule_found = False
            for i, rule in enumerate(granular_ignores):
                if (
                    rule["event_type"] == event_type
                    and rule["user_id"] == user.id
                    and rule["channel_id"] == channel.id
                ):
                    granular_ignores.pop(i)
                    rule_found = True
                    break

            if not rule_found:
                await ctx.send(
                    f"❌ No granular ignore rule found for `{event_type}` events from {user.mention} in {channel.mention}.",
                )
                return

        # Get description for confirmation message
        emoji, description = self.event_descriptions[event_type]
        self._invalidate_settings_cache(ctx.guild)
        await ctx.send(
            f"✅ {emoji} No longer ignoring **{description}** events from {user.mention} in {channel.mention}.",
        )

    @yalc_ignore.command(name="thread")
    async def yalc_ignore_thread(
        self,
        ctx: commands.Context,
        event_type: str,
        user: discord.Member,
        thread: discord.Thread,
        *,
        reason: str | None = None,
    ):
        """
        Ignore a specific event type from a specific user in a specific thread.

        This allows granular control for threads - for example, ignoring message edits from a particular
        user in a particular thread while still logging their events in other threads or channels.

        Parameters
        ----------
        event_type: str
            The event type to ignore (e.g., message_edit, message_delete)
        user: discord.Member
            The user to ignore for this event type in this thread
        thread: discord.Thread
            The thread where this user's events of this type should be ignored
        reason: str, optional
            Optional reason for this ignore rule
        """
        # Check if the event type exists
        if event_type not in self.event_descriptions:
            await ctx.send(
                f"❌ Unknown event type: `{event_type}`. Use `{ctx.prefix}yalc enable` to see all available event types.",
            )
            return

        # Validate that the thread exists and is accessible
        if not isinstance(thread, discord.Thread):
            await ctx.send("❌ The specified thread is not a valid thread.")
            return

        # Check if this rule already exists
        async with self.config.guild(ctx.guild).granular_ignores() as granular_ignores:
            existing_rule = None
            for rule in granular_ignores:
                if (
                    rule["event_type"] == event_type
                    and rule["user_id"] == user.id
                    and rule.get("thread_id") == thread.id
                ):
                    existing_rule = rule
                    break

            if existing_rule:
                await ctx.send(
                    f"❌ Already ignoring `{event_type}` events from {user.mention} in {thread.mention}.",
                )
                return

            # Create the new rule
            new_rule = {
                "event_type": event_type,
                "user_id": user.id,
                "thread_id": thread.id,
                "parent_channel_id": thread.parent_id,
                "created_by": ctx.author.id,
                "created_at": datetime.datetime.now(datetime.UTC).isoformat(),
                "reason": reason,
            }

            granular_ignores.append(new_rule)
        self._invalidate_settings_cache(ctx.guild)

        # Get description for confirmation message
        emoji, description = self.event_descriptions[event_type]
        reason_text = f" (Reason: {reason})" if reason else ""
        await ctx.send(
            f"✅ {emoji} Now ignoring **{description}** events from {user.mention} in {thread.mention}.{reason_text}",
        )

    @yalc_unignore.command(name="thread")
    async def yalc_unignore_thread(
        self,
        ctx: commands.Context,
        event_type: str,
        user: discord.Member,
        thread: discord.Thread,
    ):
        """
        Remove a specific granular ignore rule for a thread.

        Parameters
        ----------
        event_type: str
            The event type to stop ignoring
        user: discord.Member
            The user to stop ignoring for this event type in this thread
        thread: discord.Thread
            The thread where this user's events should no longer be ignored
        """
        # Check if the event type exists
        if event_type not in self.event_descriptions:
            await ctx.send(
                f"❌ Unknown event type: `{event_type}`. Use `{ctx.prefix}yalc enable` to see all available event types.",
            )
            return

        # Validate that the thread exists and is accessible
        if not isinstance(thread, discord.Thread):
            await ctx.send("❌ The specified thread is not a valid thread.")
            return

        # Find and remove the rule
        async with self.config.guild(ctx.guild).granular_ignores() as granular_ignores:
            rule_found = False
            for i, rule in enumerate(granular_ignores):
                if (
                    rule["event_type"] == event_type
                    and rule["user_id"] == user.id
                    and rule.get("thread_id") == thread.id
                ):
                    granular_ignores.pop(i)
                    rule_found = True
                    break

            if not rule_found:
                await ctx.send(
                    f"❌ No granular ignore rule found for `{event_type}` events from {user.mention} in {thread.mention}.",
                )
                return

        # Get description for confirmation message
        emoji, description = self.event_descriptions[event_type]
        self._invalidate_settings_cache(ctx.guild)
        await ctx.send(
            f"✅ {emoji} No longer ignoring **{description}** events from {user.mention} in {thread.mention}.",
        )

    @yalc_ignore.command(name="list")
    async def yalc_ignore_list(self, ctx: commands.Context, list_type: str = "all"):
        """
        List all ignore rules (broad and granular).

        Parameters
        ----------
        list_type: str
            Type of ignore rules to show: 'all', 'broad', 'specific', or 'granular'
        """
        settings = await self.config.guild(ctx.guild).all()

        embed = discord.Embed(
            title="🚫 YALC Ignore Rules",
            description=f"All ignore rules for {ctx.guild.name}",
            color=discord.Color.orange(),
        )

        if list_type in ["all", "broad"]:
            # Show broad ignore rules
            broad_rules = []

            # Ignored users
            ignored_users = settings.get("ignored_users", [])
            if ignored_users:
                user_mentions = []
                for user_id in ignored_users[:5]:  # Show first 5
                    user = ctx.guild.get_member(user_id)
                    if user:
                        user_mentions.append(user.mention)
                    else:
                        user_mentions.append(f"ID: {user_id}")
                broad_rules.append(
                    f"**👤 Ignored Users ({len(ignored_users)}):** {', '.join(user_mentions)}"
                    + (
                        f" *and {len(ignored_users) - 5} more*"
                        if len(ignored_users) > 5
                        else ""
                    ),
                )

            # Ignored channels
            ignored_channels = settings.get("ignored_channels", [])
            if ignored_channels:
                channel_mentions = []
                for channel_id in ignored_channels[:5]:  # Show first 5
                    channel = ctx.guild.get_channel(channel_id)
                    if channel:
                        channel_mentions.append(channel.mention)
                    else:
                        channel_mentions.append(f"ID: {channel_id}")
                broad_rules.append(
                    f"**📢 Ignored Channels ({len(ignored_channels)}):** {', '.join(channel_mentions)}"
                    + (
                        f" *and {len(ignored_channels) - 5} more*"
                        if len(ignored_channels) > 5
                        else ""
                    ),
                )

            # Ignored roles
            ignored_roles = settings.get("ignored_roles", [])
            if ignored_roles:
                role_mentions = []
                for role_id in ignored_roles[:5]:  # Show first 5
                    role = ctx.guild.get_role(role_id)
                    if role:
                        role_mentions.append(role.mention)
                    else:
                        role_mentions.append(f"ID: {role_id}")
                broad_rules.append(
                    f"**🎭 Ignored Roles ({len(ignored_roles)}):** {', '.join(role_mentions)}"
                    + (
                        f" *and {len(ignored_roles) - 5} more*"
                        if len(ignored_roles) > 5
                        else ""
                    ),
                )

            # Other ignore settings
            other_ignores = []
            if settings.get("ignore_bots", False):
                other_ignores.append("🤖 All bots")
            if settings.get("ignore_webhooks", False):
                other_ignores.append("🔗 All webhooks")
            if settings.get("ignore_tupperbox", True):
                other_ignores.append("👥 Tupperbox/proxy messages")
            if settings.get("ignore_apps", True):
                other_ignores.append("📱 Application messages")

            if other_ignores:
                broad_rules.append(f"**⚙️ System Ignores:** {', '.join(other_ignores)}")

            if broad_rules:
                embed.add_field(
                    name="📋 Broad Ignore Rules",
                    value="\n".join(broad_rules),
                    inline=False,
                )
            else:
                embed.add_field(
                    name="📋 Broad Ignore Rules",
                    value="*No broad ignore rules set*",
                    inline=False,
                )

        if list_type in ["all", "specific", "granular"]:
            # Show granular ignore rules
            granular_ignores = settings.get("granular_ignores", [])

            if granular_ignores:
                granular_rules = []
                for rule in granular_ignores[:10]:  # Show first 10
                    # Get user
                    user = ctx.guild.get_member(rule["user_id"])
                    user_display = user.mention if user else f"ID: {rule['user_id']}"

                    # Get channel
                    channel = ctx.guild.get_channel(rule["channel_id"])
                    channel_display = (
                        channel.mention if channel else f"ID: {rule['channel_id']}"
                    )

                    # Get event info
                    event_type = rule["event_type"]
                    emoji, description = self.event_descriptions.get(
                        event_type,
                        ("📝", event_type),
                    )

                    # Format rule
                    rule_text = f"{emoji} **{event_type}** from {user_display} in {channel_display}"
                    if rule.get("reason"):
                        rule_text += f" *(Reason: {rule['reason']})*"

                    granular_rules.append(rule_text)

                if len(granular_ignores) > 10:
                    granular_rules.append(
                        f"*...and {len(granular_ignores) - 10} more rules*",
                    )

                embed.add_field(
                    name=f"🎯 Granular Ignore Rules ({len(granular_ignores)})",
                    value="\n".join(granular_rules),
                    inline=False,
                )
            else:
                embed.add_field(
                    name="🎯 Granular Ignore Rules",
                    value="*No granular ignore rules set*",
                    inline=False,
                )

        # Add summary
        total_broad = (
            len(settings.get("ignored_users", []))
            + len(settings.get("ignored_channels", []))
            + len(settings.get("ignored_roles", []))
            + len(settings.get("ignored_categories", []))
        )
        total_granular = len(settings.get("granular_ignores", []))

        embed.add_field(
            name="📊 Summary",
            value=f"• **Broad rules:** {total_broad}\n• **Granular rules:** {total_granular}\n• **Total:** {total_broad + total_granular}",
            inline=False,
        )

        embed.set_footer(
            text=f"Use '{ctx.prefix}yalc ignore list specific' to see only granular rules",
        )

        await ctx.send(embed=embed)

    @yalc_group.command(name="bulk_enable")
    @commands.admin_or_permissions(manage_guild=True)
    async def yalc_bulk_enable(
        self,
        ctx: commands.Context,
        category: str | None = None,
    ):
        """
        Enable multiple events at once by category.

        Parameters
        ----------
        category: str, optional
            Category to enable: 'message', 'member', 'channel', 'role', 'voice', 'guild', 'all'
        """
        if category is None:
            await ctx.send(
                "❌ Please specify a category: `message`, `member`, `channel`, `role`, `voice`, `guild`, `application`, `automod`, `stage`, `soundboard`, `webhook`, `invite`, or `all`",
            )
            return

        category = category.lower()

        # Define event categories
        categories = {
            "message": [k for k in self.event_descriptions if k.startswith("message_")],
            "member": [k for k in self.event_descriptions if k.startswith("member_")],
            "channel": [
                k
                for k in self.event_descriptions
                if k.startswith(("channel_", "thread_", "forum_"))
            ],
            "role": [k for k in self.event_descriptions if k.startswith("role_")],
            "guild": [
                k
                for k in self.event_descriptions
                if k.startswith(("guild_", "emoji_", "sticker_", "invite_"))
            ],
            "voice": [k for k in self.event_descriptions if k.startswith("voice_")],
            "application": [
                k
                for k in self.event_descriptions
                if k.startswith(("command_", "application_", "integration_"))
            ],
            "automod": [k for k in self.event_descriptions if k.startswith("automod_")],
            "stage": [k for k in self.event_descriptions if k.startswith("stage_")],
            "soundboard": [
                k for k in self.event_descriptions if k.startswith("soundboard_")
            ],
            "webhook": [k for k in self.event_descriptions if k.startswith("webhook_")],
            "invite": [k for k in self.event_descriptions if k.startswith("invite_")],
            "all": list(self.event_descriptions.keys()),
        }

        if category not in categories:
            await ctx.send(
                f"❌ Unknown category: `{category}`. Available categories: {', '.join(categories.keys())}",
            )
            return

        events_to_enable = categories[category]

        # Enable all events in the category
        async with self.config.guild(ctx.guild).events() as events:
            for event_type in events_to_enable:
                events[event_type] = True
        self._invalidate_settings_cache(ctx.guild)

        await ctx.send(
            f"✅ Enabled {len(events_to_enable)} events in the **{category}** category.",
        )

    @yalc_group.command(name="bulk_disable")
    @commands.admin_or_permissions(manage_guild=True)
    async def yalc_bulk_disable(
        self,
        ctx: commands.Context,
        category: str | None = None,
    ):
        """
        Disable multiple events at once by category.

        Parameters
        ----------
        category: str, optional
            Category to disable: 'message', 'member', 'channel', 'role', 'voice', 'guild', 'all'
        """
        if category is None:
            await ctx.send(
                "❌ Please specify a category: `message`, `member`, `channel`, `role`, `voice`, `guild`, `application`, `automod`, `stage`, `soundboard`, `webhook`, `invite`, or `all`",
            )
            return

        category = category.lower()

        # Define event categories
        categories = {
            "message": [k for k in self.event_descriptions if k.startswith("message_")],
            "member": [k for k in self.event_descriptions if k.startswith("member_")],
            "channel": [
                k
                for k in self.event_descriptions
                if k.startswith(("channel_", "thread_", "forum_"))
            ],
            "role": [k for k in self.event_descriptions if k.startswith("role_")],
            "guild": [
                k
                for k in self.event_descriptions
                if k.startswith(("guild_", "emoji_", "sticker_", "invite_"))
            ],
            "voice": [k for k in self.event_descriptions if k.startswith("voice_")],
            "application": [
                k
                for k in self.event_descriptions
                if k.startswith(("command_", "application_", "integration_"))
            ],
            "automod": [k for k in self.event_descriptions if k.startswith("automod_")],
            "stage": [k for k in self.event_descriptions if k.startswith("stage_")],
            "soundboard": [
                k for k in self.event_descriptions if k.startswith("soundboard_")
            ],
            "webhook": [k for k in self.event_descriptions if k.startswith("webhook_")],
            "invite": [k for k in self.event_descriptions if k.startswith("invite_")],
            "all": list(self.event_descriptions.keys()),
        }

        if category not in categories:
            await ctx.send(
                f"❌ Unknown category: `{category}`. Available categories: {', '.join(categories.keys())}",
            )
            return

        events_to_disable = categories[category]

        # Disable all events in the category
        async with self.config.guild(ctx.guild).events() as events:
            for event_type in events_to_disable:
                events[event_type] = False
        self._invalidate_settings_cache(ctx.guild)

        await ctx.send(
            f"✅ Disabled {len(events_to_disable)} events in the **{category}** category.",
        )

    @yalc_group.command(name="reset")
    @commands.admin_or_permissions(manage_guild=True)
    async def yalc_reset(self, ctx: commands.Context, confirm: str | None = None):
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
                color=discord.Color.orange(),
            )
            embed.add_field(
                name="What will be reset:",
                value="• All event logging settings\n"
                "• All channel configurations\n"
                "• All ignore lists\n"
                "• All advanced settings",
                inline=False,
            )
            embed.add_field(
                name="To confirm:",
                value=f"Run `{ctx.prefix}yalc reset CONFIRM`",
                inline=False,
            )
            await ctx.send(embed=embed)
            return

        try:
            await self.config.guild(ctx.guild).clear()
            self._invalidate_settings_cache(ctx.guild)
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
            enabled_events = [
                event for event, enabled in settings["events"].items() if enabled
            ]
            for event in enabled_events:
                channel_id = settings["event_channels"].get(event)
                if not channel_id:
                    warnings.append(
                        f"Event `{event}` is enabled but has no log channel configured",
                    )
                else:
                    channel = ctx.guild.get_channel(channel_id)
                    if not channel:
                        issues.append(
                            f"Event `{event}` is configured to log to channel ID {channel_id} but the channel doesn't exist",
                        )

            # Check for configured channels without enabled events
            configured_channels = {
                event: channel_id
                for event, channel_id in settings["event_channels"].items()
                if channel_id
            }
            for event, channel_id in configured_channels.items():
                if not settings["events"].get(event, False):
                    warnings.append(
                        f"Event `{event}` has a log channel configured but is not enabled",
                    )

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
                    warnings.append(
                        f"Ignored channel ID {channel_id} not found in server",
                    )

            # Check granular ignore rules
            granular_ignores = settings.get("granular_ignores", [])
            for i, rule in enumerate(granular_ignores):
                # Check if rule has required fields
                required_fields = ["event_type", "user_id", "channel_id"]
                missing_fields = [
                    field for field in required_fields if field not in rule
                ]
                if missing_fields:
                    issues.append(
                        f"Granular ignore rule #{i + 1} is missing required fields: {', '.join(missing_fields)}",
                    )
                    continue

                # Check if event type is valid
                event_type = rule.get("event_type")
                if event_type and event_type not in self.event_descriptions:
                    issues.append(
                        f"Granular ignore rule #{i + 1} has invalid event type: `{event_type}`",
                    )

                # Check if user exists
                user_id = rule.get("user_id")
                if user_id:
                    user = ctx.guild.get_member(user_id)
                    if not user:
                        # Try to fetch user from API as fallback
                        try:
                            fetched_user = await self.bot.fetch_user(user_id)
                            if not fetched_user:
                                warnings.append(
                                    f"Granular ignore rule #{i + 1} references unknown user ID {user_id}",
                                )
                        except Exception:
                            warnings.append(
                                f"Granular ignore rule #{i + 1} references unknown user ID {user_id}",
                            )

                # Check if channel exists
                channel_id = rule.get("channel_id")
                if channel_id:
                    channel = ctx.guild.get_channel(channel_id)
                    if not channel:
                        warnings.append(
                            f"Granular ignore rule #{i + 1} references unknown channel ID {channel_id}",
                        )

                # Check rule structure integrity
                if rule.get("created_at"):
                    try:
                        datetime.datetime.fromisoformat(
                            rule["created_at"].replace("Z", "+00:00"),
                        )
                    except (ValueError, TypeError):
                        warnings.append(
                            f"Granular ignore rule #{i + 1} has invalid created_at timestamp",
                        )

            # Create validation report
            embed = discord.Embed(
                title="🔍 YALC Configuration Validation",
                color=discord.Color.green() if not issues else discord.Color.red(),
            )

            if not issues and not warnings:
                embed.description = "✅ Configuration is valid with no issues found!"
            else:
                embed.description = (
                    f"Found {len(issues)} issues and {len(warnings)} warnings"
                )

            if issues:
                embed.add_field(
                    name="❌ Issues (require attention)",
                    value="\n".join(f"• {issue}" for issue in issues[:10])
                    + (
                        f"\n• ...and {len(issues) - 10} more"
                        if len(issues) > 10
                        else ""
                    ),
                    inline=False,
                )

            if warnings:
                embed.add_field(
                    name="⚠️ Warnings (recommended fixes)",
                    value="\n".join(f"• {warning}" for warning in warnings[:10])
                    + (
                        f"\n• ...and {len(warnings) - 10} more"
                        if len(warnings) > 10
                        else ""
                    ),
                    inline=False,
                )

            # Add summary stats
            embed.add_field(
                name="📊 Summary",
                value=f"• Enabled events: {len(enabled_events)}\n"
                f"• Configured channels: {len(configured_channels)}\n"
                f"• Ignored users: {len(settings.get('ignored_users', []))}\n"
                f"• Ignored roles: {len(settings.get('ignored_roles', []))}\n"
                f"• Ignored channels: {len(settings.get('ignored_channels', []))}\n"
                f"• Granular ignore rules: {len(settings.get('granular_ignores', []))}",
                inline=False,
            )

            await ctx.send(embed=embed)

        except Exception as e:
            await ctx.send(f"❌ Error validating configuration: {e}")

    @yalc_group.command(name="setup")
    @commands.admin_or_permissions(manage_guild=True)
    async def yalc_setup(self, ctx: commands.Context, confirm: str | None = None):
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
                description="This will create a complete logging category and route supported YALC events to dedicated log channels.",
                color=discord.Color.blue(),
            )
            channel_lines = [f"• **#{name}**" for _, name, _ in self.SETUP_LOG_CHANNELS]
            embed.add_field(
                name="Created Category",
                value="• **YALC Logs**",
                inline=False,
            )
            for index in range(0, len(channel_lines), 9):
                embed.add_field(
                    name=f"Created Channels {index + 1}-{min(index + 9, len(channel_lines))}",
                    value="\n".join(channel_lines[index : index + 9]),
                    inline=False,
                )
            embed.add_field(
                name="Events to be enabled:",
                value="• All supported YALC event types\n"
                "• Voice join, leave, move, mute/deafen, stream, camera, and suppress changes\n"
                "• Stage, sticker, soundboard, AutoMod, webhook, invite, and application command logs\n"
                "• Events are routed to the closest matching channel when no exact one exists",
                inline=False,
            )
            embed.add_field(
                name="To confirm:",
                value=f"Run `{ctx.prefix}yalc setup CONFIRM`",
                inline=False,
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
                        send_messages=False,
                    ),
                    ctx.guild.me: discord.PermissionOverwrite(
                        read_messages=True,
                        send_messages=True,
                        manage_messages=True,
                    ),
                },
                reason="YALC logging setup",
            )

            # Create logging channels
            channels = {}
            for key, name, topic in self.SETUP_LOG_CHANNELS:
                channels[key] = await ctx.guild.create_text_channel(
                    name,
                    category=category,
                    topic=topic,
                    reason="YALC logging setup",
                )

            # Configure event mappings
            event_mappings = {}
            for event_type in self.event_descriptions:
                channel_key = self._get_default_event_channel_key(event_type)
                channel = channels.get(channel_key) or channels["server"]
                event_mappings[event_type] = channel.id

            # Apply configuration
            async with self.config.guild(ctx.guild).events() as events:
                async with self.config.guild(
                    ctx.guild,
                ).event_channels() as event_channels:
                    for event_type, channel_id in event_mappings.items():
                        events[event_type] = True
                        event_channels[event_type] = channel_id

            # Set up default ignore settings
            await self.config.guild(ctx.guild).ignore_tupperbox.set(True)
            await self.config.guild(ctx.guild).ignore_apps.set(True)
            await self.config.guild(ctx.guild).include_thumbnails.set(True)
            await self.config.guild(ctx.guild).detect_proxy_deletes.set(True)
            self._invalidate_settings_cache(ctx.guild)

            # Send success message
            embed = discord.Embed(
                title="✅ YALC Setup Complete!",
                description=f"Successfully created logging infrastructure for {ctx.guild.name}",
                color=discord.Color.green(),
            )

            embed.add_field(
                name="📁 Created Category",
                value=f"**{category.name}** - {category.mention}",
                inline=False,
            )

            embed.add_field(
                name="📢 Created Channels",
                value="\n".join(
                    f"• {channels[key].mention} - {topic.removeprefix('YALC: ')}"
                    for key, _, topic in self.SETUP_LOG_CHANNELS[:8]
                ),
                inline=False,
            )

            embed.add_field(
                name="📢 Created Channels Continued",
                value="\n".join(
                    f"• {channels[key].mention} - {topic.removeprefix('YALC: ')}"
                    for key, _, topic in self.SETUP_LOG_CHANNELS[8:]
                ),
                inline=False,
            )

            embed.add_field(
                name="⚙️ Configuration",
                value=f"• **{len(event_mappings)}** events enabled\n"
                "• Ignoring Tupperbox/proxy messages\n"
                "• Ignoring application messages\n"
                "• Including user thumbnails\n"
                "• Detecting proxy deletions",
                inline=False,
            )

            embed.add_field(
                name="🎯 Next Steps",
                value=f"• Use `{ctx.prefix}yalc settings` to view configuration\n"
                f"• Use `{ctx.prefix}yalc enable/disable` to adjust events\n"
                "• Use the web dashboard for advanced configuration\n"
                f"• Use `{ctx.prefix}yalc validate` to check for issues",
                inline=False,
            )

            await ctx.send(embed=embed)

        except discord.Forbidden:
            await ctx.send(
                "❌ I don't have permission to create channels and categories. Please ensure I have `Manage Channels` permission.",
            )
        except Exception as e:
            await ctx.send(f"❌ Error during setup: {e}")

    @yalc_group.command(name="autodetect", aliases=["smartsetup", "autosetup"])
    @commands.admin_or_permissions(manage_guild=True)
    async def yalc_autodetect(self, ctx: commands.Context, confirm: str | None = None):
        """
        Automatically detect log channels based on naming patterns and configure logging.

        Smart channel detection looks for channels with common naming patterns:
        • thread-logs → Thread events
        • user-logs → Member events
        • message-logs → Message events
        • channel-logs → Channel events
        • role-logs → Role events
        • voice-logs → Voice events
        • moderation-logs → Moderation events
        • command-logs → Command events
        • bot-logs → Bot/integration events
        • system-logs → Guild events
        • general-logs → All events
        • mod-logs → Moderation events (alternative)

        Parameters
        ----------
        confirm : str, optional
            Must be "CONFIRM" to apply the detected configuration
        """
        if confirm != "CONFIRM":
            # Scan channels for patterns and generate preview
            detected_config = await self._scan_for_log_channels(ctx.guild)

            if not detected_config:
                embed = discord.Embed(
                    title="🔍 Log Channel Auto-Detection",
                    description="No log channels were found with common naming patterns.",
                    color=discord.Color.red(),
                )

                embed.add_field(
                    name="Expected Patterns",
                    value="• `thread-logs` for thread events\n"
                    "• `user-logs` for member events\n"
                    "• `message-logs` for message events\n"
                    "• `channel-logs` for channel events\n"
                    "• `role-logs` for role events\n"
                    "And many more...",
                    inline=False,
                )

                embed.add_field(
                    name="🛠️ Action Required",
                    value="Create channels with these naming patterns and run this command again.\n\n"
                    f"**or**\n\n"
                    f"Use `{ctx.prefix}yalc setup CONFIRM` to automatically create organized log channels.",
                    inline=False,
                )

                await ctx.send(embed=embed)
                return

            # Send summary embed first
            summary_embed = discord.Embed(
                title="🔍 Log Channel Auto-Detection Summary",
                description=f"Found {len(detected_config)} potential log channels with {sum(len(data['events']) for data in detected_config.values())} total events.",
                color=discord.Color.blue(),
            )

            summary_embed.add_field(
                name="📊 Quick Stats",
                value=f"• **Channels Found**: {len(detected_config)}\n"
                f"• **Total Events**: {sum(len(data['events']) for data in detected_config.values())}\n"
                f"• **Channels Ignored**: {len(ctx.guild.channels) - len(detected_config)}",
                inline=False,
            )

            summary_embed.add_field(
                name="⚠️ Safety Notice",
                value="Review the channel listings below before confirming.\n"
                "**This action will:**\n"
                "• Enable events for each detected channel\n"
                "• Set appropriate channel mappings\n"
                "• Configure default ignore settings",
                inline=False,
            )

            summary_embed.add_field(
                name="🎯 Next Step",
                value=f"To apply this configuration:\n`{ctx.prefix}yalc autodetect CONFIRM`",
                inline=False,
            )

            summary_embed.set_footer(
                text=f"Auto-detected {len(detected_config)} channels • YALC Logger",
            )
            await ctx.send(embed=summary_embed)

            # Send channel details in multiple embeds (max 10 channels per embed)
            if detected_config:
                sorted_channels = sorted(detected_config.keys())
                channels_per_embed = 10

                for i in range(0, len(sorted_channels), channels_per_embed):
                    chunk = sorted_channels[i : i + channels_per_embed]
                    page_num = (i // channels_per_embed) + 1
                    total_pages = (
                        len(sorted_channels) + channels_per_embed - 1
                    ) // channels_per_embed

                    embed = discord.Embed(
                        title=f"📂 Detected Channels (Page {page_num}/{total_pages})",
                        description=f"Channels {i + 1} to {min(i + len(chunk), len(sorted_channels))} of {len(sorted_channels)}",
                        color=discord.Color.green(),
                    )

                    channel_lines = []
                    for ch_name in chunk:
                        events_data = detected_config[ch_name]
                        channel = events_data["channel"]
                        events = events_data["events"]

                        # Use compact emoji representation to save characters
                        if len(events) <= 5:
                            event_emojis = [
                                self.event_descriptions[e][0]
                                for e in events[:5]
                                if e in self.event_descriptions
                            ]
                            event_text = "".join(event_emojis) if event_emojis else "📝"
                        else:
                            event_emojis = [
                                self.event_descriptions[e][0]
                                for e in events[:3]
                                if e in self.event_descriptions
                            ]
                            event_text = "".join(event_emojis) + f"+{len(events) - 3}"

                        channel_lines.append(
                            f"📂 **{ch_name}** → {event_text} ({len(events)} events)",
                        )

                    embed.add_field(
                        name="Detected Channels",
                        value="\n".join(channel_lines),
                        inline=False,
                    )

                    embed.set_footer(
                        text=f"Page {page_num}/{total_pages} • Use CONFIRM when ready",
                    )
                    await ctx.send(embed=embed)
            return

        # Apply the detected configuration
        detected_config = await self._scan_for_log_channels(ctx.guild)

        if not detected_config:
            await ctx.send("❌ No log channels found with expected patterns.")
            return

        # Apply configuration
        channels_configured = 0
        events_enabled = 0

        async with ctx.typing():
            # Set up events and channels
            async with self.config.guild(ctx.guild).events() as events_setting:
                async with self.config.guild(
                    ctx.guild,
                ).event_channels() as channels_setting:
                    for channel_name_key, config_data in detected_config.items():
                        channel = config_data["channel"]
                        events_list = config_data["events"]

                        for event_type in events_list:
                            # Enable the event
                            events_setting[event_type] = True
                            # Set the channel
                            channels_setting[event_type] = channel.id
                            events_enabled += 1

                channels_configured = len(detected_config)

            # Apply default ignore settings for better experience
            await self.config.guild(ctx.guild).ignore_tupperbox.set(True)
            await self.config.guild(ctx.guild).ignore_apps.set(True)
            await self.config.guild(ctx.guild).include_thumbnails.set(True)
            await self.config.guild(ctx.guild).detect_proxy_deletes.set(True)
            self._invalidate_settings_cache(ctx.guild)

        # Success message
        embed = discord.Embed(
            title="✅ YALC Auto-Detection Complete!",
            description=f"Successfully configured {events_enabled} events across {channels_configured} channels.",
            color=discord.Color.green(),
        )

        # Show what was configured
        channel_summary = []
        for ch_name, config_data in detected_config.items():
            channel = config_data["channel"]
            events = config_data["events"]
            channel_summary.append(
                f"• **{ch_name}** ({channel.mention}) → {len(events)} events",
            )

        embed.add_field(
            name="📢 Configured Channels",
            value="\n".join(channel_summary),
            inline=False,
        )

        embed.add_field(
            name="⚙️ Default Settings Applied",
            value="• Ignore Tupperbox/proxy messages\n"
            "• Ignore application messages\n"
            "• Include user thumbnails\n"
            "• Detect proxy deletions",
            inline=False,
        )

        embed.add_field(
            name="🔧 Next Steps",
            value=f"• View your settings: `{ctx.prefix}yalc settings`\n"
            f"• Test logging: `{ctx.prefix}yalc validate`\n"
            f"• Fine-tune: `{ctx.prefix}yalc enable/disable`",
            inline=False,
        )

        await ctx.send(embed=embed)

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
                color=discord.Color.blue(),
            )

            if not dashboard_cog:
                embed.add_field(
                    name="❌ Dashboard Cog",
                    value="Dashboard cog is not loaded",
                    inline=False,
                )
            else:
                embed.add_field(
                    name="✅ Dashboard Cog",
                    value="Dashboard cog is loaded",
                    inline=True,
                )

                if hasattr(dashboard_cog, "rpc"):
                    embed.add_field(
                        name="✅ Dashboard RPC",
                        value="RPC interface is available",
                        inline=True,
                    )

                    if hasattr(dashboard_cog.rpc, "third_parties_handler"):
                        embed.add_field(
                            name="✅ Third Party Handler",
                            value="Third party handler is available",
                            inline=True,
                        )

                        # Check if YALC is registered
                        try:
                            third_parties = getattr(
                                dashboard_cog.rpc.third_parties_handler,
                                "third_parties",
                                {},
                            )
                            yalc_registered = self.qualified_name in third_parties

                            if yalc_registered:
                                pages = third_parties.get(self.qualified_name, {})
                                embed.add_field(
                                    name="✅ YALC Registration",
                                    value=f"YALC is registered as a third party with {len(pages)} page(s)",
                                    inline=False,
                                )
                            else:
                                embed.add_field(
                                    name="❌ YALC Registration",
                                    value="YALC is NOT registered as a third party",
                                    inline=False,
                                )

                            registered_names = list(third_parties.keys())
                            embed.add_field(
                                name="📊 Registered Third Parties",
                                value=f"Total: {len(registered_names)}\n"
                                + "\n".join(
                                    [f"• {name}" for name in registered_names[:5]],
                                )
                                + (
                                    f"\n• ...and {len(registered_names) - 5} more"
                                    if len(registered_names) > 5
                                    else ""
                                ),
                                inline=False,
                            )
                        except Exception as e:
                            embed.add_field(
                                name="❌ Registration Check",
                                value=f"Error checking registration: {e}",
                                inline=False,
                            )
                    else:
                        embed.add_field(
                            name="❌ Third Party Handler",
                            value="Third party handler not available",
                            inline=True,
                        )
                else:
                    embed.add_field(
                        name="❌ Dashboard RPC",
                        value="RPC interface not available",
                        inline=True,
                    )

            # Add integration object status
            embed.add_field(
                name="🔧 Integration Object",
                value=f"Dashboard integration: {self is not None}\n"
                f"Has dashboard_page: {hasattr(self, 'dashboard_page')}\n"
                f"Has dashboard listener: {hasattr(self, 'on_dashboard_cog_add')}",
                inline=False,
            )

            await ctx.send(embed=embed)

        elif action == "register":
            # Attempt to register YALC with dashboard
            dashboard_cog = self.bot.get_cog("Dashboard")

            if not dashboard_cog:
                await ctx.send("❌ Dashboard cog is not loaded.")
                return

            if not hasattr(dashboard_cog, "rpc") or not hasattr(
                dashboard_cog.rpc,
                "third_parties_handler",
            ):
                await ctx.send("❌ Dashboard third party handler not available.")
                return

            try:
                handler = dashboard_cog.rpc.third_parties_handler
                try:
                    handler.add_third_party(self, overwrite=True)
                except TypeError:
                    handler.add_third_party(self)
                await ctx.send(
                    "✅ Successfully registered YALC as a dashboard third party.",
                )

                # Verify registration
                third_parties = getattr(handler, "third_parties", {})
                yalc_registered = self.qualified_name in third_parties

                if yalc_registered:
                    await ctx.send("✅ Registration verified - YALC is now registered.")
                else:
                    await ctx.send("⚠️ Registration completed but verification failed.")

            except Exception as e:
                await ctx.send(f"❌ Failed to register YALC: {e}")

        else:
            await ctx.send(
                f"❌ Unknown action: `{action}`. Use 'status' or 'register'.",
            )

    # --- Slash Commands ---

    @app_commands.command(
        name="yalc_enable",
        description="Enable logging for a specific event type",
    )
    @app_commands.describe(event_type="The event type to enable logging for")
    @app_commands.guild_only()
    async def slash_yalc_enable(
        self,
        interaction: discord.Interaction,
        event_type: str,
    ):
        """Enable logging for a specific event type via slash command."""
        # Check permissions
        if not interaction.user.guild_permissions.manage_guild:
            await interaction.response.send_message(
                "❌ You need the `Manage Server` permission to use this command.",
                ephemeral=True,
            )
            return

        # Check if the event type exists
        if event_type not in self.event_descriptions:
            available_events = ", ".join(list(self.event_descriptions.keys())[:10])
            await interaction.response.send_message(
                f"❌ Unknown event type: `{event_type}`.\n"
                f"Available events: {available_events}{'...' if len(self.event_descriptions) > 10 else ''}",
                ephemeral=True,
            )
            return

        # Enable the event
        async with self.config.guild(interaction.guild).events() as events:
            events[event_type] = True
        self._invalidate_settings_cache(interaction.guild)

        # Get description for confirmation message
        emoji, description = self.event_descriptions[event_type]
        await interaction.response.send_message(
            f"✅ {emoji} Enabled logging for **{description}** (`{event_type}`).",
        )

    @app_commands.command(
        name="yalc_disable",
        description="Disable logging for a specific event type",
    )
    @app_commands.describe(event_type="The event type to disable logging for")
    @app_commands.guild_only()
    async def slash_yalc_disable(
        self,
        interaction: discord.Interaction,
        event_type: str,
    ):
        """Disable logging for a specific event type via slash command."""
        # Check permissions
        if not interaction.user.guild_permissions.manage_guild:
            await interaction.response.send_message(
                "❌ You need the `Manage Server` permission to use this command.",
                ephemeral=True,
            )
            return

        # Check if the event type exists
        if event_type not in self.event_descriptions:
            available_events = ", ".join(list(self.event_descriptions.keys())[:10])
            await interaction.response.send_message(
                f"❌ Unknown event type: `{event_type}`.\n"
                f"Available events: {available_events}{'...' if len(self.event_descriptions) > 10 else ''}",
                ephemeral=True,
            )
            return

        # Disable the event
        async with self.config.guild(interaction.guild).events() as events:
            events[event_type] = False
        self._invalidate_settings_cache(interaction.guild)

        # Get description for confirmation message
        emoji, description = self.event_descriptions[event_type]
        await interaction.response.send_message(
            f"✅ {emoji} Disabled logging for **{description}** (`{event_type}`).",
        )

    @app_commands.command(
        name="yalc_setchannel",
        description="Set the logging channel for a specific event type",
    )
    @app_commands.describe(
        event_type="The event type to set the channel for",
        channel="The channel to log the events to",
    )
    @app_commands.guild_only()
    async def slash_yalc_setchannel(
        self,
        interaction: discord.Interaction,
        event_type: str,
        channel: discord.TextChannel,
    ):
        """Set the logging channel for a specific event type via slash command."""
        # Check permissions
        if not interaction.user.guild_permissions.manage_guild:
            await interaction.response.send_message(
                "❌ You need the `Manage Server` permission to use this command.",
                ephemeral=True,
            )
            return

        # Check if the event type exists
        if event_type not in self.event_descriptions and event_type != "all":
            available_events = ", ".join(list(self.event_descriptions.keys())[:10])
            await interaction.response.send_message(
                f"❌ Unknown event type: `{event_type}`.\n"
                f"Available events: {available_events}{'...' if len(self.event_descriptions) > 10 else ''}\n"
                f"Use `all` to set for all event types.",
                ephemeral=True,
            )
            return

        # Set the channel
        if event_type == "all":
            # Set for all event types
            async with self.config.guild(
                interaction.guild,
            ).event_channels() as event_channels:
                for et in self.event_descriptions:
                    event_channels[et] = channel.id
            self._invalidate_settings_cache(interaction.guild)
            await interaction.response.send_message(
                f"✅ Set {channel.mention} as the logging channel for **all** event types.",
            )
        else:
            # Set for a specific event type
            async with self.config.guild(
                interaction.guild,
            ).event_channels() as event_channels:
                event_channels[event_type] = channel.id
            self._invalidate_settings_cache(interaction.guild)

            # Get description for confirmation message
            emoji, description = self.event_descriptions[event_type]
            await interaction.response.send_message(
                f"✅ {emoji} Set {channel.mention} as the logging channel for **{description}** (`{event_type}`).",
            )

    async def _scan_for_log_channels(self, guild: discord.Guild) -> dict:
        """
        Scan guild text channels for common logging patterns and map them to events.

        Returns a dictionary mapping detected channel patterns to their configuration.
        """
        # Define patterns and their associated events
        patterns = {
            "application": [
                "command_use",
                "command_error",
                "application_cmd",
                "application_cmd_permissions_update",
                "integration_create",
                "integration_update",
                "integration_delete",
            ],
            "thread": [
                "thread_create",
                "thread_delete",
                "thread_update",
                "thread_member_join",
                "thread_member_leave",
                "forum_post_create",
                "forum_post_delete",
                "forum_post_update",
            ],
            "user": [
                "member_join",
                "member_leave",
                "member_update",
            ],
            "member": [
                "member_join",
                "member_leave",
                "member_update",
            ],
            "message": [
                "message_delete",
                "message_edit",
                "message_bulk_delete",
                "message_pin",
                "message_unpin",
                "reaction_add",
                "reaction_remove",
                "reaction_clear",
            ],
            "channel": [
                "channel_create",
                "channel_delete",
                "channel_update",
            ],
            "role": [
                "role_create",
                "role_delete",
                "role_update",
            ],
            "voice": [
                "voice_state_update",
                "voice_update",
            ],
            "discord-automod": [
                "automod_action",
                "automod_rule_create",
                "automod_rule_update",
                "automod_rule_delete",
            ],
            "auto-mod": [
                "automod_action",
                "automod_rule_create",
                "automod_rule_update",
                "automod_rule_delete",
            ],
            "automod": [
                "automod_action",
                "automod_rule_create",
                "automod_rule_update",
                "automod_rule_delete",
            ],
            "moderation": [
                "member_ban",
                "member_unban",
                "member_kick",
                "member_timeout",
                "automod_action",
                "automod_rule_create",
                "automod_rule_update",
                "automod_rule_delete",
            ],
            "mod": [
                "member_ban",
                "member_unban",
                "member_kick",
                "member_timeout",
                "automod_action",
                "automod_rule_create",
                "automod_rule_update",
                "automod_rule_delete",
            ],
            "command": [
                "command_use",
                "command_error",
                "application_cmd",
                "application_cmd_permissions_update",
            ],
            "emoji": [
                "emoji_update",
            ],
            "event": [
                "guild_scheduled_event_create",
                "guild_scheduled_event_update",
                "guild_scheduled_event_delete",
            ],
            "invite": [
                "invite_create",
                "invite_delete",
            ],
            "server": [
                "guild_update",
            ],
            "stage": [
                "stage_instance_create",
                "stage_instance_update",
                "stage_instance_delete",
            ],
            "sticker": [
                "sticker_update",
            ],
            "soundboard": [
                "soundboard_sound_create",
                "soundboard_sound_update",
                "soundboard_sound_delete",
            ],
            "sound": [
                "soundboard_sound_create",
                "soundboard_sound_update",
                "soundboard_sound_delete",
            ],
            "webhook": [
                "webhook_update",
            ],
            "integration": [
                "integration_create",
                "integration_update",
                "integration_delete",
            ],
            "bot": [
                "webhook_update",
                "integration_create",
                "integration_update",
                "integration_delete",
                "application_cmd",
                "application_cmd_permissions_update",
            ],
            "system": [
                "guild_update",
                "emoji_update",
                "sticker_update",
            ],
            "guild": [
                "guild_update",
                "emoji_update",
                "sticker_update",
                "invite_create",
                "invite_delete",
            ],
            "general": list(self.event_descriptions.keys()),  # All events
            "log": [],
            "logs": [],
        }

        detected_config = {}
        text_channels = [
            ch for ch in guild.channels if isinstance(ch, discord.TextChannel)
        ]

        for channel in text_channels:
            channel_name_lower = channel.name.lower()

            # Check for various naming patterns
            found_match = False
            for pattern, events in patterns.items():
                # Check different common log channel naming formats
                if any(
                    indicator in channel_name_lower
                    for indicator in [
                        pattern,
                        f"{pattern}s",
                        f"{pattern}-",
                        f"{pattern}_",
                    ]
                ):
                    # Skip if this looks like a general "log" or "logs" channel without being more specific
                    if pattern in ["log", "logs"] and channel_name_lower.strip() in [
                        "log",
                        "logs",
                    ]:
                        continue

                    # Filter events to only include ones that exist in our descriptions
                    valid_events = [e for e in events if e in self.event_descriptions]

                    if valid_events:
                        detected_config[channel.name] = {
                            "channel": channel,
                            "events": valid_events,
                        }
                        found_match = True
                        break

            # If no specific pattern match, check for broader patterns like numbering or log indicators
            if not found_match:
                # Look for patterns like "mod-log-1", "message-logs-2", etc.
                if "log" in channel_name_lower:
                    for pattern, events in patterns.items():
                        if (
                            pattern in channel_name_lower and len(pattern) > 2
                        ):  # Avoid matching just "log"
                            valid_events = [
                                e for e in events if e in self.event_descriptions
                            ]
                            if valid_events:
                                detected_config[channel.name] = {
                                    "channel": channel,
                                    "events": valid_events,
                                }
                                break

        return detected_config

    @app_commands.command(
        name="yalc_settings",
        description="View current YALC settings for this server",
    )
    @app_commands.guild_only()
    async def slash_yalc_settings(self, interaction: discord.Interaction):
        """View the current YALC settings for this server via slash command."""
        settings = await self.config.guild(interaction.guild).all()

        embed = discord.Embed(
            title="YALC Logger Settings",
            description="Current logging configuration for this server",
            color=discord.Color.blue(),
        )

        # Add enabled events with channel info
        enabled_events_with_channels = []
        for event, enabled in settings["events"].items():
            if enabled:
                channel_id = settings["event_channels"].get(event)
                channel_info = ""
                if channel_id:
                    channel = interaction.guild.get_channel(channel_id)
                    if channel:
                        channel_info = f" → {channel.mention}"
                    else:
                        channel_info = " → *Channel not found*"
                else:
                    channel_info = " → *No channel set*"

                emoji, description = self.event_descriptions[event]
                enabled_events_with_channels.append(
                    f"{emoji} `{event}` - {description}{channel_info}",
                )

        if enabled_events_with_channels:
            embed.add_field(
                name="📋 Enabled Events with Channels",
                value="\n".join(enabled_events_with_channels[:12])
                + (
                    f"\n*...and {len(enabled_events_with_channels) - 12} more*"
                    if len(enabled_events_with_channels) > 12
                    else ""
                ),
                inline=False,
            )
        else:
            embed.add_field(
                name="📋 Enabled Events",
                value="No events enabled",
                inline=False,
            )

        # Add channel mappings
        channel_mappings = []
        for event, channel_id in settings["event_channels"].items():
            if channel_id:
                channel = interaction.guild.get_channel(channel_id)
                if channel and event in self.event_descriptions:
                    channel_mappings.append(
                        f"{self.event_descriptions[event][0]} `{event}` → {channel.mention}",
                    )

        if channel_mappings:
            embed.add_field(
                name="📢 Event Channels",
                value="\n".join(channel_mappings[:10])
                + (
                    f"\n*...and {len(channel_mappings) - 10} more*"
                    if len(channel_mappings) > 10
                    else ""
                ),
                inline=False,
            )
        else:
            embed.add_field(
                name="📢 Event Channels",
                value="No channels configured",
                inline=False,
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
            ignore_settings.append(
                f"🚫 Ignored Roles: {', '.join(role_names)}"
                + (
                    f" *and {len(ignored_roles) - 3} more*"
                    if len(ignored_roles) > 3
                    else ""
                ),
            )

        ignored_users = settings.get("ignored_users", [])
        if ignored_users:
            ignore_settings.append(f"🚫 Ignored Users: {len(ignored_users)}")

        ignored_channels = settings.get("ignored_channels", [])
        if ignored_channels:
            channel_names = [f"<#{channel_id}>" for channel_id in ignored_channels[:3]]
            ignore_settings.append(
                f"🚫 Ignored Channels: {', '.join(channel_names)}"
                + (
                    f" *and {len(ignored_channels) - 3} more*"
                    if len(ignored_channels) > 3
                    else ""
                ),
            )

        if ignore_settings:
            embed.add_field(
                name="⚙️ Ignore Settings",
                value="\n".join(ignore_settings),
                inline=False,
            )

        embed.set_footer(text=f"YALC • Server ID: {interaction.guild.id}")
        await interaction.response.send_message(embed=embed)

    @app_commands.command(
        name="yalc_quicksetup",
        description="Quick setup wizard for YALC logging",
    )
    @app_commands.describe(
        log_channel="Channel to use for all logging",
        enable_basic_events="Enable basic message and member events",
    )
    @app_commands.guild_only()
    async def slash_yalc_quicksetup(
        self,
        interaction: discord.Interaction,
        log_channel: discord.TextChannel,
        enable_basic_events: bool = True,
    ):
        """Quick setup wizard for YALC logging via slash command."""
        # Check permissions
        if not interaction.user.guild_permissions.manage_guild:
            await interaction.response.send_message(
                "❌ You need the `Manage Server` permission to use this command.",
                ephemeral=True,
            )
            return

        try:
            # Set up basic events if requested
            if enable_basic_events:
                basic_events = [
                    "message_delete",
                    "message_edit",
                    "message_bulk_delete",
                    "member_join",
                    "member_leave",
                    "member_ban",
                    "member_unban",
                    "channel_create",
                    "channel_delete",
                    "role_create",
                    "role_delete",
                ]

                async with self.config.guild(interaction.guild).events() as events:
                    for event in basic_events:
                        if event in self.event_descriptions:
                            events[event] = True

                # Set the log channel for enabled events
                async with self.config.guild(
                    interaction.guild,
                ).event_channels() as event_channels:
                    for event in basic_events:
                        if event in self.event_descriptions:
                            event_channels[event] = log_channel.id

            # Enable some useful default settings
            await self.config.guild(interaction.guild).ignore_tupperbox.set(True)
            await self.config.guild(interaction.guild).ignore_apps.set(True)
            await self.config.guild(interaction.guild).include_thumbnails.set(True)
            await self.config.guild(interaction.guild).detect_proxy_deletes.set(True)
            self._invalidate_settings_cache(interaction.guild)

            embed = discord.Embed(
                title="✅ YALC Quick Setup Complete",
                description=f"YALC has been configured for {interaction.guild.name}",
                color=discord.Color.green(),
            )

            if enable_basic_events:
                embed.add_field(
                    name="📋 Enabled Events",
                    value="• Message deletions, edits, and bulk deletions\n"
                    "• Member joins, leaves, bans, and unbans\n"
                    "• Channel and role creation/deletion",
                    inline=False,
                )

            embed.add_field(
                name="📢 Log Channel",
                value=f"All events will be logged to {log_channel.mention}",
                inline=False,
            )

            embed.add_field(
                name="⚙️ Default Settings",
                value="• Ignoring Tupperbox/proxy messages\n"
                "• Ignoring application messages\n"
                "• Including user thumbnails\n"
                "• Detecting proxy deletions",
                inline=False,
            )

            embed.add_field(
                name="🔧 Next Steps",
                value="Use `/yalc_settings` to view your configuration\n"
                "Use `/yalc_enable` or `/yalc_disable` to adjust events\n"
                "Use the web dashboard for advanced configuration",
                inline=False,
            )

            await interaction.response.send_message(embed=embed)

        except Exception as e:
            await interaction.response.send_message(
                f"❌ Error during quick setup: {e}",
                ephemeral=True,
            )

    async def is_tupperbox_message(
        self,
        message: discord.Message,
        tupperbox_ids: list,
    ) -> bool:
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
            if (
                "tupperbox" in webhook_name.lower()
                or "tupperhook" in webhook_name.lower()
            ):
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
                    referenced_message = await message.channel.fetch_message(
                        message.reference.message_id,
                    )
                    if (
                        referenced_message
                        and referenced_message.author.id in tupperbox_ids
                    ):
                        return True
                except discord.NotFound:
                    pass  # Referenced message not found, ignore
                except Exception as e:
                    self.log.debug(f"Error checking referenced message: {e}")

        return False

    async def safe_send(
        self,
        channel: discord.TextChannel,
        **kwargs,
    ) -> discord.Message | None:
        """
        Enhanced safe send with comprehensive error recovery and fallback mechanisms.

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

        max_retries = 3
        base_delay = 1

        for attempt in range(max_retries):
            try:
                self._reset_send_files(kwargs)
                return await channel.send(**kwargs)

            except discord.Forbidden:
                self.log.warning(
                    f"Missing permissions to send message to channel {channel.id} in guild {channel.guild.id}",
                )
                # Try fallback: send to a default log channel if configured
                if attempt == 0:
                    fallback_channel = await self._get_fallback_log_channel(
                        channel.guild,
                    )
                    if fallback_channel and fallback_channel != channel:
                        self.log.info(f"Attempting fallback to {fallback_channel.name}")
                        try:
                            fallback_embed = kwargs.get("embed")
                            if fallback_embed:
                                fallback_embed.add_field(
                                    name="⚠️ Fallback Channel",
                                    value=f"Original destination: {channel.mention} (no permission)",
                                    inline=False,
                                )
                            self._reset_send_files(kwargs)
                            return await fallback_channel.send(**kwargs)
                        except Exception as fallback_e:
                            self.log.error(f"Fallback send also failed: {fallback_e}")
                break  # Don't retry permission errors

            except discord.HTTPException as e:
                if e.status == 429:  # Rate limited
                    retry_after = getattr(e, "retry_after", base_delay * (2**attempt))
                    self.log.warning(
                        f"Rate limited when sending to channel {channel.id}, retrying after {retry_after}s",
                    )
                    await asyncio.sleep(retry_after)
                elif e.code == 50013:  # Missing permissions
                    self.log.warning(f"Missing permissions for channel {channel.id}")
                    break
                elif e.code == 50001:  # Missing access
                    self.log.warning(f"Missing access to channel {channel.id}")
                    break
                else:
                    if attempt < max_retries - 1:
                        delay = base_delay * (2**attempt)
                        self.log.warning(
                            f"HTTP error when sending to channel {channel.id}: {e}, retrying in {delay}s",
                        )
                        await asyncio.sleep(delay)
                    else:
                        self.log.error(
                            f"Failed to send message to channel {channel.id} after {max_retries} attempts: {e}",
                        )

            except Exception as e:
                if attempt < max_retries - 1:
                    delay = base_delay * (2**attempt)
                    self.log.warning(
                        f"Unexpected error when sending to channel {channel.id}: {e}, retrying in {delay}s",
                    )
                    await asyncio.sleep(delay)
                else:
                    self.log.error(
                        f"Unexpected error when sending to channel {channel.id} after {max_retries} attempts: {e}",
                        exc_info=True,
                    )

        return None

    async def _get_fallback_log_channel(
        self,
        guild: discord.Guild,
    ) -> discord.TextChannel | None:
        """Get a fallback log channel when the primary channel is unavailable."""
        try:
            settings = await self._get_cached_settings(guild)

            # Try to find any configured log channel that we can send to
            for event_type, channel_id in settings.get("event_channels", {}).items():
                if channel_id:
                    channel = guild.get_channel(channel_id)
                    if isinstance(channel, discord.TextChannel):
                        # Test if we can send to this channel
                        try:
                            if channel.permissions_for(guild.me).send_messages:
                                return channel
                        except Exception:
                            continue

            # Fallback to the first text channel we can send to
            for channel in guild.text_channels:
                try:
                    if channel.permissions_for(guild.me).send_messages:
                        return channel
                except Exception:
                    continue

        except Exception as e:
            self.log.error(f"Error finding fallback log channel: {e}")

        return None

    async def _handle_bulk_changes(
        self,
        guild: discord.Guild,
        change_type: str,
        targets: list,
        moderator=None,
        reason=None,
    ):
        """Handle bulk operations with intelligent batching and rate limiting."""
        if not targets:
            return

        batch_size = 10  # Process in batches to avoid overwhelming logs
        total_batches = (len(targets) + batch_size - 1) // batch_size

        try:
            should_log = await self.should_log_event(guild, f"bulk_{change_type}")
            if not should_log:
                return

            channel = await self.get_log_channel(guild, f"bulk_{change_type}")
            if not channel:
                # Try to log to a general bulk changes channel
                channel = await self.get_log_channel(guild, "bulk_changes")
            if not channel:
                return

            # Create summary embed for bulk operation
            embed = self.create_embed(
                f"bulk_{change_type}",
                f"🔄 Bulk {change_type} operation detected",
                affected_count=len(targets),
                batches=total_batches,
                moderator=f"{moderator.mention} ({moderator.id})"
                if moderator
                else "Unknown",
            )

            if reason:
                embed.add_field(name="Reason", value=reason, inline=False)

            # Add sample of affected targets
            sample_size = min(10, len(targets))
            sample_targets = targets[:sample_size]
            target_names = []

            for target in sample_targets:
                if hasattr(target, "mention"):
                    target_names.append(target.mention)
                elif hasattr(target, "name"):
                    target_names.append(f"`{target.name}`")
                else:
                    target_names.append(f"`{str(target)}`")

            embed.add_field(
                name=f"Sample Targets ({sample_size}/{len(targets)})",
                value="\n".join(target_names),
                inline=False,
            )

            if len(targets) > sample_size:
                embed.add_field(
                    name="Additional Info",
                    value=f"...and {len(targets) - sample_size} more targets",
                    inline=False,
                )

            await self.safe_send(channel, embed=embed)

        except Exception as e:
            self.log.error(f"Error handling bulk {change_type} operation: {e}")

    async def _background_log_worker(self):
        """Background worker task to process log queue asynchronously."""
        self.log.info("Background log worker started")

        while not self._processing_shutdown:
            try:
                # Wait for items with timeout to allow periodic cleanup
                log_item = await asyncio.wait_for(self._log_queue.get(), timeout=30.0)
                await self._process_log_item(log_item)
                self._log_queue.task_done()

            except asyncio.TimeoutError:
                # Periodic cleanup of caches during quiet periods
                await self._cleanup_expired_caches()
                continue

            except asyncio.CancelledError:
                self.log.info("Background log worker cancelled")
                break

            except Exception as e:
                self.log.error(f"Error in background log worker: {e}", exc_info=True)
                await asyncio.sleep(1)  # Prevent rapid error loops

        self.log.info("Background log worker stopped")

    async def _process_log_item(self, log_item):
        """Process a single log item from the queue."""
        try:
            event_type, guild_id, event_data = log_item
            guild = self.bot.get_guild(guild_id)

            if not guild:
                self.log.warning(
                    f"Guild {guild_id} not found for background log processing",
                )
                return

            # Route to appropriate handler based on event type
            handler_map = {
                "member_update_bg": self._process_member_update_background,
                "voice_state_bg": self._process_voice_state_background,
                "bulk_operation_bg": self._process_bulk_operation_background,
            }

            handler = handler_map.get(event_type)
            if handler:
                await handler(guild, event_data)
            else:
                self.log.warning(f"Unknown background event type: {event_type}")

        except Exception as e:
            self.log.error(f"Error processing background log item: {e}", exc_info=True)

    async def _cleanup_expired_caches(self):
        """Clean up expired cache entries."""
        current_time = time.time()

        # Clean up audit debounce cache
        expired_debounce = [
            key
            for key, timestamp in self._audit_debounce_cache.items()
            if current_time - timestamp > self._debounce_timeout
        ]
        for key in expired_debounce:
            del self._audit_debounce_cache[key]

        # Clean up settings cache
        expired_settings = [
            key
            for key, data in self._settings_cache.items()
            if current_time - data["timestamp"] > self._settings_cache_timeout
        ]
        for key in expired_settings:
            del self._settings_cache[key]

        if expired_debounce or expired_settings:
            self.log.debug(
                f"Cleaned up {len(expired_debounce)} debounce entries and {len(expired_settings)} settings cache entries",
            )

    async def _should_debounce_audit_fetch(
        self,
        guild_id: int,
        action: discord.AuditLogAction,
        target_id: int = None,
    ) -> bool:
        """Check if we should skip audit log fetch due to recent similar fetch."""
        cache_key = f"{guild_id}_{action.name}_{target_id or 'none'}"
        current_time = time.time()

        if cache_key in self._audit_debounce_cache:
            last_fetch = self._audit_debounce_cache[cache_key]
            if current_time - last_fetch < self._debounce_timeout:
                return True  # Should debounce (skip fetch)

        # Record this fetch attempt
        self._audit_debounce_cache[cache_key] = current_time
        return False  # Should not debounce (proceed with fetch)

    async def _get_audit_log_entry_debounced(
        self,
        guild: discord.Guild,
        action: discord.AuditLogAction,
        target=None,
        timeout_seconds=30,
    ):
        """Get audit log entry with smart debouncing to reduce API calls."""
        target_id = target.id if target and hasattr(target, "id") else None

        # Check if we should skip this fetch due to recent similar request
        if await self._should_debounce_audit_fetch(guild.id, action, target_id):
            self.log.debug(
                f"Debouncing audit log fetch for {action.name} in guild {guild.id}",
            )
            # Try to get from cache instead
            if target_id:
                cached_entry = await self._get_cached_audit_entry(
                    guild,
                    action,
                    target_id,
                )
                if cached_entry:
                    return cached_entry
            return None

        # Proceed with actual API fetch
        return await self._get_audit_log_entry_with_retry(
            guild,
            action,
            target,
            timeout_seconds,
        )

    async def _queue_background_log(
        self,
        event_type: str,
        guild: discord.Guild,
        event_data: dict,
        priority: bool = False,
    ):
        """Queue a log item for background processing."""
        log_item = (event_type, guild.id, event_data)

        try:
            if priority:
                # For high-priority items, add to front of queue if possible
                temp_items = [log_item]
                while not self._log_queue.empty():
                    temp_items.append(self._log_queue.get_nowait())

                for item in temp_items:
                    await self._log_queue.put(item)
            else:
                await self._log_queue.put(log_item)

        except asyncio.QueueFull:
            self.log.warning(
                f"Log queue full, dropping {event_type} event for guild {guild.id}",
            )

    async def _process_member_update_background(
        self,
        guild: discord.Guild,
        event_data: dict,
    ):
        """Process member update in background for non-critical updates."""
        # This would handle things like nickname changes that aren't urgent
        pass  # Implementation would depend on specific needs

    async def _process_voice_state_background(
        self,
        guild: discord.Guild,
        event_data: dict,
    ):
        """Process voice state changes in background."""
        # This could handle voice session analytics and summaries
        pass  # Implementation would depend on specific needs

    async def _process_bulk_operation_background(
        self,
        guild: discord.Guild,
        event_data: dict,
    ):
        """Process bulk operations in background."""
        # This could handle summarizing large role changes, etc.
        pass  # Implementation would depend on specific needs


async def setup(bot: Red) -> None:
    """Load YALC cog."""
    await bot.add_cog(YALC(bot))
