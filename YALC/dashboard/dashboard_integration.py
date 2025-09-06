import discord
from redbot.core import commands
import typing
import logging

# Try to import dashboard utilities - fallback if not available
try:
    from AAA3A_utils import Cog
    from AAA3A_utils.dashboard import dashboard_page
    _aaa3a_available = True
except ImportError:
    _aaa3a_available = False
    Cog = object
    # Fallback decorator when AAA3A_utils is not available
    def dashboard_page():
        def decorator(func):
            return func
        return decorator


class DashboardIntegration(object):
    """Dashboard integration for YALC (Yet Another Logging Cog)."""

    def __init__(self, bot, *args, **kwargs) -> None:
        # This is a mixin class, so initialization is handled by the main cog
        pass
            
        # Store event descriptions from main cog for dashboard use
        self.event_descriptions = getattr(self, 'event_descriptions', {
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
            
            # Role events
            "role_create": ("✨", "Role Creation"),
            "role_delete": ("🗑️", "Role Deletion"),
            "role_update": ("🔄", "Role Updates"),
            
            # Guild events
            "guild_update": ("⚙️", "Server Updates"),
            "emoji_update": ("😀", "Emoji Updates"),
            "voice_state_update": ("🎧", "Voice State Changes"),
        })

    async def format_settings(
        self,
        guild: discord.Guild,
        **kwargs,
    ) -> typing.Dict[str, typing.Any]:
        """Format settings for the dashboard."""
        try:
            config = await self.config.guild(guild).all()
            
            # Format the settings data for display
            settings = {
                # Basic filter settings
                "include_thumbnails": config.get("include_thumbnails", True),
                "ignore_bots": config.get("ignore_bots", False),
                "ignore_webhooks": config.get("ignore_webhooks", False),
                "ignore_tupperbox": config.get("ignore_tupperbox", True),
                "ignore_apps": config.get("ignore_apps", True),
                "detect_proxy_deletes": config.get("detect_proxy_deletes", True),
                
                # Event toggles
                "events": config.get("events", {}),
                
                # Channel configurations
                "event_channels": config.get("event_channels", {}),
                
                # Ignore lists
                "ignored_users": config.get("ignored_users", []),
                "ignored_roles": config.get("ignored_roles", []),
                "ignored_channels": config.get("ignored_channels", []),
                "ignored_categories": config.get("ignored_categories", []),
                
                # Additional settings
                "tupperbox_ids": config.get("tupperbox_ids", ["239232811662311425"]),
                "message_prefix_filter": config.get("message_prefix_filter", []),
                "webhook_name_filter": config.get("webhook_name_filter", []),
            }
            
            return settings
        except Exception:
            return {}

    async def update_settings(
        self,
        guild: discord.Guild,
        new_settings: typing.Dict[str, typing.Any],
        **kwargs,
    ) -> None:
        """Update settings from the dashboard."""
        try:
            # Update basic filter settings
            if "include_thumbnails" in new_settings:
                await self.config.guild(guild).include_thumbnails.set(new_settings["include_thumbnails"])
            if "ignore_bots" in new_settings:
                await self.config.guild(guild).ignore_bots.set(new_settings["ignore_bots"])
            if "ignore_webhooks" in new_settings:
                await self.config.guild(guild).ignore_webhooks.set(new_settings["ignore_webhooks"])
            if "ignore_tupperbox" in new_settings:
                await self.config.guild(guild).ignore_tupperbox.set(new_settings["ignore_tupperbox"])
            if "ignore_apps" in new_settings:
                await self.config.guild(guild).ignore_apps.set(new_settings["ignore_apps"])
            if "detect_proxy_deletes" in new_settings:
                await self.config.guild(guild).detect_proxy_deletes.set(new_settings["detect_proxy_deletes"])
                
            # Update event toggles
            if "events" in new_settings:
                await self.config.guild(guild).events.set(new_settings["events"])
                
            # Update channel configurations
            if "event_channels" in new_settings:
                # Convert string IDs to ints
                cleaned_channels = {}
                for event, channel_id in new_settings["event_channels"].items():
                    if channel_id and str(channel_id).isdigit():
                        cleaned_channels[event] = int(channel_id)
                    else:
                        cleaned_channels[event] = None
                await self.config.guild(guild).event_channels.set(cleaned_channels)
                
            # Update ignore lists
            if "ignored_users" in new_settings:
                await self.config.guild(guild).ignored_users.set(new_settings["ignored_users"])
            if "ignored_roles" in new_settings:
                await self.config.guild(guild).ignored_roles.set(new_settings["ignored_roles"])
            if "ignored_channels" in new_settings:
                await self.config.guild(guild).ignored_channels.set(new_settings["ignored_channels"])
            if "ignored_categories" in new_settings:
                await self.config.guild(guild).ignored_categories.set(new_settings["ignored_categories"])
                
            # Update additional settings
            if "tupperbox_ids" in new_settings:
                await self.config.guild(guild).tupperbox_ids.set(new_settings["tupperbox_ids"])
            if "message_prefix_filter" in new_settings:
                await self.config.guild(guild).message_prefix_filter.set(new_settings["message_prefix_filter"])
            if "webhook_name_filter" in new_settings:
                await self.config.guild(guild).webhook_name_filter.set(new_settings["webhook_name_filter"])
                
        except Exception as e:
            # Use bot logger if available, otherwise just pass
            if hasattr(self, 'log') and self.log:
                self.log.error(f"Error updating YALC settings: {e}")

    @dashboard_page()
    async def dashboard_page(
        self,
        user: discord.User,
        guild_id: int,
        **kwargs,
    ) -> typing.Dict[str, typing.Any]:
        """Main dashboard page for YALC."""
        guild = self.bot.get_guild(guild_id)
        if not guild:
            return {"status": 1, "web_content": {"error": "Invalid guild."}}

        # Check permissions
        member = guild.get_member(user.id)
        if not member or not member.guild_permissions.manage_guild:
            return {"status": 1, "web_content": {"error": "You need `Manage Server` permission to view this page."}}

        # Get current settings
        settings = await self.config.guild(guild).all()
        
        # Generate HTML content
        html_content = await self._generate_dashboard_html(guild, settings)
        
        return {
            "status": 0,
            "web_content": {
                "source": html_content,
                "settings": settings,
            },
        }

    async def _generate_dashboard_html(self, guild: discord.Guild, settings: dict) -> str:
        """Generate the main dashboard HTML."""
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
        # Get event descriptions from the main cog
        event_descriptions = getattr(self, 'event_descriptions', {})
        
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
                if event in event_descriptions:
                    emoji, desc = event_descriptions[event]
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

        event_descriptions = getattr(self, 'event_descriptions', {})
        
        channel_config_html = ""
        for event in enabled_events:
            if event in event_descriptions:
                emoji, desc = event_descriptions[event]
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

    @commands.Cog.listener()
    async def on_dashboard_cog_add(self, dashboard_cog: commands.Cog) -> None:
        """Register the dashboard integration when dashboard cog is loaded."""
        dashboard_cog.rpc.third_parties_handler.add_third_party(self)
