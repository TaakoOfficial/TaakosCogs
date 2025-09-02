import typing
import discord
from redbot.core import commands, Config
from redbot.core.bot import Red

# Import dashboard decorators
try:
    from dashboard.rpc.third_parties import dashboard_page
except ImportError:
    # Graceful fallback if dashboard isn't installed
    def dashboard_page(*args, **kwargs):
        def decorator(func):
            return func
        return decorator

# Optional: AAA3A_utils (for CFS tokens or other fixes)
try:
    import AAA3A_utils
except ImportError:
    AAA3A_utils = None

import logging


class DashboardIntegration:
    """
    Dashboard integration for YALC (Yet Another Logging Cog).
    Allows users to view info and configure the cog through Red-Web-Dashboard.
    """

    # Metadata for dashboard
    name = "YALC"
    description = "Yet Another Logging Cog - Comprehensive Discord event logging with dashboard integration"
    version = "3.0.0"
    author = "YALC Team"
    repo = "https://github.com/TaakoOfficial/TaakosCogs"
    support = "https://discord.gg/your-support"
    icon = "https://cdn-icons-png.flaticon.com/512/928/928797.png"

    bot: Red

    def __init__(self, bot: Red) -> None:
        self.bot = bot

        # Set up logging
        self.log = logging.getLogger("red.YALC")

        # Event descriptions for logging and dashboard (must be set up before config)
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

        # Use YALC's actual config identifier
        self.config = Config.get_conf(
            self, identifier=1234567875, force_registration=True
        )

        # YALC's comprehensive default guild settings
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
            "webhook_name_filter": [],

            # Dashboard example config fields merged
            "enable_feature": False,
            "custom_message": "",
            "log_retention_days": 7,

            # Voice session tracking
            "voice_sessions": {},  # Active sessions: user_id -> {"channel_id": int, "start_time": float}
            "voice_events": []  # Recent events history: max 50 entries
        }

        self.config.register_guild(**default_guild)

        # Real-time audit log entry storage for role attribution (shared with YALC)
        self.recent_audit_entries = {}

    @commands.Cog.listener()
    async def on_dashboard_cog_add(self, dashboard_cog) -> None:
        """
        Register this cog as a dashboard third party when the dashboard cog is loaded.
        This listener will be active through inheritance by the main YALC cog.
        """
        try:
            dashboard_cog.rpc.third_parties_handler.add_third_party(self)
        except Exception as e:
            # Graceful fallback if registration fails - log to console if available
            print(f"[YALC Dashboard] Failed to register as third party: {e}")
            pass

    # ABOUT PAGE
    @dashboard_page(
        name="about",
        description="Information about the YALC cog.",
        methods=("GET",),
        is_owner=False,
    )
    # SETTINGS PAGE
    @dashboard_page(
        name="settings",
        description="Configure YALC settings.",
        methods=("GET", "POST"),
        is_owner=False,  # Allow server admins to configure
    )
    async def dashboard_settings(
        self, user: discord.User, guild_id: int, **kwargs
    ) -> typing.Dict[str, typing.Any]:
        """Settings page for YALC dashboard."""
        guild = self.bot.get_guild(guild_id)
        if not guild:
            return {"status": 1, "web_content": {"error": "Invalid guild."}}

        # Check user permissions
        member = guild.get_member(user.id)
        if not member or not member.guild_permissions.manage_guild:
            return {"status": 1, "web_content": {"error": "You need `Manage Server` permission to view this page."}}

        # Handle POST (update settings)
        if kwargs.get("method") == "POST":
            data = kwargs.get("data", {})
            await self._update_settings_from_post(guild, data)

        # GET (fetch current settings)
        settings = await self.config.guild(guild).all()

        html_content = await self._generate_settings_html(guild, settings)
        return {
            "status": 0,
            "web_content": {
                "source": html_content,
                "settings": settings,
            },
        }

    async def _update_settings_from_post(self, guild: discord.Guild, data: dict):
        """Update settings from POST data."""
        try:
            # Basic settings
            if "include_thumbnails" in data:
                await self.config.guild(guild).include_thumbnails.set(bool(data.get("include_thumbnails")))
            if "ignore_bots" in data:
                await self.config.guild(guild).ignore_bots.set(bool(data.get("ignore_bots")))
            if "ignore_webhooks" in data:
                await self.config.guild(guild).ignore_webhooks.set(bool(data.get("ignore_webhooks")))
            if "ignore_tupperbox" in data:
                await self.config.guild(guild).ignore_tupperbox.set(bool(data.get("ignore_tupperbox")))
            if "ignore_apps" in data:
                await self.config.guild(guild).ignore_apps.set(bool(data.get("ignore_apps")))

            # Event toggles
            events_data = {}
            for event in self.event_descriptions.keys():
                if f"event_{event}" in data:
                    events_data[event] = bool(data.get(f"event_{event}"))
                elif event in data.get("events", {}):
                    events_data[event] = data["events"][event]

            if events_data:
                await self.config.guild(guild).events.set(events_data)

            # Channel configurations
            if "event_channels" in data:
                event_channels = data["event_channels"]
                if isinstance(event_channels, dict):
                    # Convert string IDs to ints
                    cleaned_channels = {}
                    for event, channel_id in event_channels.items():
                        if channel_id and str(channel_id).isdigit():
                            cleaned_channels[event] = int(channel_id)
                        else:
                            cleaned_channels[event] = None
                    await self.config.guild(guild).event_channels.set(cleaned_channels)

        except Exception as e:
            # Log error but don't crash the request
            pass

    async def _generate_settings_html(self, guild: discord.Guild, settings: dict) -> str:
        """Generate the settings page HTML."""
        # Generate event toggle sections
        event_sections = self._generate_event_sections(settings)
        channel_sections = self._generate_channel_sections(guild, settings)
        filter_sections = self._generate_filter_sections(guild, settings)

        html_content = f"""
        <div style="padding: 1em; max-width: 1200px;">
            <div style="background: linear-gradient(135deg, #3949ab 0%, #5e35b1 100%); color: white; padding: 2em; border-radius: 10px; margin-bottom: 2em;">
                <h1 style="margin: 0; font-size: 2em;">⚙️ YALC Settings</h1>
                <p style="margin: 0.5em 0 0 0; opacity: 0.9;">Configure logging for {guild.name}</p>
            </div>

            <form method="POST" style="background: white; border-radius: 10px; padding: 2em; box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);">
                {event_sections}
                {channel_sections}
                {filter_sections}

                <div style="text-align: center; margin-top: 2em; padding-top: 2em; border-top: 1px solid #e0e0e0;">
                    <button type="submit" style="background: #4caf50; color: white; border: none; padding: 1em 2em; border-radius: 5px; font-size: 1.1em; cursor: pointer;">Save Settings</button>
                </div>
            </form>

            <div style="margin-top: 2em; text-align: center; color: #666;">
                <p>Changes are saved automatically to Red's configuration system.</p>
            </div>
        </div>
        """
        return html_content

    def _generate_event_sections(self, settings: dict) -> str:
        """Generate HTML for event toggle sections."""
        categories = {
            "Message Events": ["message_delete", "message_edit", "message_bulk_delete", "message_pin", "message_unpin"],
            "Member Events": ["member_join", "member_leave", "member_ban", "member_unban", "member_kick", "member_timeout"],
            "Voice Events": ["voice_state_update", "voice_update"],
            "Channel Events": ["channel_create", "channel_delete", "channel_update", "thread_create", "thread_delete", "thread_update"],
            "Role Events": ["role_create", "role_delete", "role_update"],
            "Server Events": ["guild_update", "emoji_update", "sticker_update", "invite_create", "invite_delete"],
            "Moderation Events": ["automod_rule_create", "automod_rule_update", "automod_rule_delete", "automod_action"]
        }

        sections = []

        for category_name, events in categories.items():
            event_checkboxes = []
            for event in events:
                if event in self.event_descriptions:
                    emoji, desc = self.event_descriptions[event]
                    checked = "checked" if settings.get("events", {}).get(event, False) else ""
                    event_checkboxes.append(f"""
                        <label style="display: inline-block; margin-right: 15px; margin-bottom: 8px;">
                            <input type="checkbox" name="event_{event}" value="1" {checked}
                                   style="margin-right: 5px; transform: scale(1.2);">
                            {emoji} {desc}
                        </label>
                    """)

            if event_checkboxes:
                sections.append(f"""
                    <div style="margin-bottom: 2em; padding: 1.5em; background: #f8f9fa; border-radius: 8px;">
                        <h3 style="color: #3949ab; margin-top: 0; border-bottom: 2px solid #3949ab; padding-bottom: 0.5em;">{category_name}</h3>
                        <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(250px, 1fr)); gap: 10px;">
                            {"".join(event_checkboxes)}
                        </div>
                    </div>
                """)

        return "".join(sections)

    def _generate_channel_sections(self, guild: discord.Guild, settings: dict) -> str:
        """Generate HTML for channel configuration sections."""
        # Get text channels for dropdown
        text_channels = [c for c in guild.channels if isinstance(c, discord.TextChannel)]
        channel_options = '<option value="">None</option>' + "".join(
            f'<option value="{c.id}">{c.name}</option>' for c in text_channels
        )

        enabled_events = [event for event, enabled in settings.get("events", {}).items() if enabled]

        if not enabled_events:
            return '<div style="margin-bottom: 2em; padding: 1.5em; background: #fff3cd; border-radius: 8px; border-left: 4px solid #ffc107;"><p>⚠️ Enable some events above to configure their log channels.</p></div>'

        channel_config_html = ""
        for event in enabled_events:
            if event in self.event_descriptions:
                emoji, desc = self.event_descriptions[event]
                current_channel_id = settings.get("event_channels", {}).get(event)
                selected_value = current_channel_id if current_channel_id else ""

                channel_config_html += f"""
                    <div style="display: flex; justify-content: space-between; align-items: center; padding: 0.5em 0; border-bottom: 1px solid #eee;">
                        <label for="channel_{event}" style="flex: 1; margin-right: 1em;">
                            {emoji} {desc}
                        </label>
                        <select name="event_channels[{event}]" id="channel_{event}" style="flex: 0 0 200px; padding: 0.5em; border-radius: 4px; border: 1px solid #ccc;">
                            {channel_options.replace(f'value="{selected_value}"', f'value="{selected_value}" selected')}
                        </select>
                    </div>
                """

        return f"""
            <div style="margin-bottom: 2em; padding: 1.5em; background: #f8f9fa; border-radius: 8px;">
                <h3 style="color: #3949ab; margin-top: 0; border-bottom: 2px solid #3949ab; padding-bottom: 0.5em;">📢 Event Log Channels</h3>
                <p style="color: #666; margin-bottom: 1em;">Select which channel each event should be logged to.</p>
                {channel_config_html}
            </div>
        """

    def _generate_filter_sections(self, guild: discord.Guild, settings: dict) -> str:
        """Generate HTML for filtering options."""
        return f"""
            <div style="margin-bottom: 2em; padding: 1.5em; background: #f8f9fa; border-radius: 8px;">
                <h3 style="color: #3949ab; margin-top: 0; border-bottom: 2px solid #3949ab; padding-bottom: 0.5em;">🔍 Filtering Options</h3>

                <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(250px, 1fr)); gap: 15px;">
                    <label style="display: flex; align-items: center;">
                        <input type="checkbox" name="include_thumbnails" value="1" {'checked' if settings.get('include_thumbnails', True) else ''}
                               style="margin-right: 10px; transform: scale(1.2);">
                        🖼️ Include user thumbnails
                    </label>

                    <label style="display: flex; align-items: center;">
                        <input type="checkbox" name="ignore_bots" value="1" {'checked' if settings.get('ignore_bots', False) else ''}
                               style="margin-right: 10px; transform: scale(1.2);">
                        🤖 Ignore bot messages
                    </label>

                    <label style="display: flex; align-items: center;">
                        <input type="checkbox" name="ignore_webhooks" value="1" {'checked' if settings.get('ignore_webhooks', False) else ''}
                               style="margin-right: 10px; transform: scale(1.2);">
                        🪝 Ignore webhook messages
                    </label>

                    <label style="display: flex; align-items: center;">
                        <input type="checkbox" name="ignore_tupperbox" value="1" {'checked' if settings.get('ignore_tupperbox', True) else ''}
                               style="margin-right: 10px; transform: scale(1.2);">
                        👥 Ignore Tupperbox/proxy messages
                    </label>

                    <label style="display: flex; align-items: center;">
                        <input type="checkbox" name="ignore_apps" value="1" {'checked' if settings.get('ignore_apps', True) else ''}
                               style="margin-right: 10px; transform: scale(1.2);">
                        📱 Ignore app messages
                    </label>
                </div>
            </div>
        """

    def yalcdash_settings(self) -> typing.Dict[str, typing.Any]:
        """
        Expose YALC config fields as dashboard widgets.
        This schema helps the dashboard auto-render inputs.
        """
        # Base configuration schema
        schema = {
            # Basic toggles
            "include_thumbnails": {
                "type": "boolean",
                "label": "Include Thumbnails",
                "description": "Include user avatars in log embeds",
                "default": True,
            },
            "ignore_bots": {
                "type": "boolean",
                "label": "Ignore Bots",
                "description": "Don't log messages from bot users",
                "default": False,
            },
            "ignore_webhooks": {
                "type": "boolean",
                "label": "Ignore Webhooks",
                "description": "Don't log messages from webhooks",
                "default": False,
            },
            "ignore_tupperbox": {
                "type": "boolean",
                "label": "Ignore Tupperbox",
                "description": "Don't log Tupperbox/proxy messages",
                "default": True,
            },
            "ignore_apps": {
                "type": "boolean",
                "label": "Ignore Apps",
                "description": "Don't log messages from applications",
                "default": True,
            },
        }

        # Add event toggles
        for event_type, (emoji, description) in self.event_descriptions.items():
            schema[f"event_{event_type}"] = {
                "type": "boolean",
                "label": f"{emoji} {description}",
                "description": f"Log {description.lower()}",
                "default": False,
            }

        return schema

    async def dashboard_about(
        self, user: discord.User, **kwargs
    ) -> typing.Dict[str, typing.Any]:
        """About page for YALC dashboard."""
        features_html = """
        <ul style="list-style-type: none; padding: 0;">
            <li>✅ Comprehensive event logging with 35+ events</li>
            <li>✅ Per-channel configurations</li>
            <li>✅ Advanced filtering (users, roles, channels)</li>
            <li>✅ Message content tracking with Tupperbox support</li>
            <li>✅ Voice session logging and analytics</li>
            <li>✅ Audit log integration for attribution</li>
            <li>✅ Rich embed formatting with thumbnails</li>
            <li>✅ Dashboard integration for easy configuration</li>
        </ul>
        """

        html_content = f"""
        <div style="padding: 1em; max-width: 800px;">
            <div style="text-align: center; margin-bottom: 2em;">
                <img src="{self.icon}" width="96" height="96" style="border-radius: 15px; box-shadow: 0 4px 8px rgba(0,0,0,0.1);"/>
                <h1 style="color: #3949ab; margin: 0.5em 0;">{self.name}</h1>
                <p style="color: #666; margin: 0; font-style: italic;">{self.description}</p>
            </div>

            <div style="background: #f8f9fa; border-radius: 10px; padding: 1.5em; margin-bottom: 1.5em;">
                <h3 style="color: #3949ab; margin-top: 0;">Features & Capabilities</h3>
                {features_html}
            </div>

            <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 1em;">
                <div style="background: #e8f5e8; border-radius: 8px; padding: 1em;">
                    <h4 style="color: #2e7d32; margin-top: 0;">Supported Events</h4>
                    <p style="margin: 0;"><strong>35+ event types</strong> including message actions, member events, channel management, role changes, voice activity, and moderation events.</p>
                </div>
                <div style="background: #e3f2fd; border-radius: 8px; padding: 1em;">
                    <h4 style="color: #1976d2; margin-top: 0;">Filtering Options</h4>
                    <p style="margin: 0;">Advanced filtering by users, roles, channels, bot messages, webhooks, and custom proxy detection.</p>
                </div>
            </div>

            <div style="margin-top: 2em; text-align: center; color: #666;">
                <p><strong>Version {self.version}</strong> | Created by {self.author}</p>
                <p><a href="{self.repo}" target="_blank">View on GitHub</a> | <a href="{self.support}" target="_blank">Support Server</a></p>
            </div>
        </div>
        """
        return {"status": 0, "web_content": {"source": html_content}}
