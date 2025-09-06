import discord
from redbot.core import commands
import typing
import logging

# Dashboard integration decorator - compatible with Red-Web-Dashboard
def dashboard_page(*args, **kwargs):
    """Dashboard page decorator that stores parameters for later registration."""
    def decorator(func: typing.Callable):
        func.__dashboard_decorator_params__ = (args, kwargs)
        return func
    return decorator


class DashboardIntegration(object):
    """Dashboard integration for YALC (Yet Another Logging Cog)."""

    def __init__(self, bot, *args, **kwargs) -> None:
        # This is a mixin class, so initialization is handled by the main cog
        # Don't call super().__init__() as this could interfere with multiple inheritance
        self.bot = bot
        
        # Initialize event descriptions if not already set by main cog
        if not hasattr(self, 'event_descriptions'):
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
                
                # Role events
                "role_create": ("✨", "Role Creation"),
                "role_delete": ("🗑️", "Role Deletion"),
                "role_update": ("🔄", "Role Updates"),
                
                # Guild events
                "guild_update": ("⚙️", "Server Updates"),
                "emoji_update": ("😀", "Emoji Updates"),
                "voice_state_update": ("🎧", "Voice State Changes"),
            }

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

    @dashboard_page(name=None, methods=("GET", "POST"))
    async def dashboard_page(
        self,
        user: discord.User,
        guild_id: int,
        **kwargs,
    ) -> typing.Dict[str, typing.Any]:
        """Main dashboard page for YALC."""
        try:
            # Check if we have access to the required attributes
            if not hasattr(self, 'config') or not self.config:
                return {
                    "status": 1,
                    "error_title": "Configuration Error",
                    "error_message": "Dashboard integration is not properly initialized. Please reload the cog."
                }
            
            guild = self.bot.get_guild(guild_id)
            if not guild:
                return {"status": 1, "error_title": "Invalid Guild", "error_message": "The specified guild could not be found."}

            # Check permissions
            member = guild.get_member(user.id)
            if not member or not member.guild_permissions.manage_guild:
                return {"status": 1, "error_title": "Insufficient Permissions", "error_message": "You need `Manage Server` permission to view this page."}

            # Handle form submission for POST requests
            method = kwargs.get("method", "GET")
            if method == "POST":
                return await self._handle_form_submission(guild, user, **kwargs)

            # Get current settings
            settings = await self.config.guild(guild).all()
            
            # Generate HTML content with form
            # Only pass specific kwargs to avoid parameter conflicts
            html_kwargs = {
                "csrf_token": kwargs.get("csrf_token"),
                "request_url": kwargs.get("request_url"),
                "method": kwargs.get("method")
            }
            html_content = await self._generate_dashboard_html(guild, settings, **html_kwargs)
            
            return {
                "status": 0,
                "web_content": {
                    "source": html_content,
                    "expanded": True,  # Use template without guild profile for more space
                },
            }
            
        except Exception as e:
            # Log the error if we have access to the logger
            if hasattr(self, 'log') and self.log:
                self.log.error(f"Error in YALC dashboard page: {e}", exc_info=True)
            
            return {
                "status": 1,
                "error_title": "Dashboard Error",
                "error_message": f"An error occurred while loading the dashboard: {str(e)}"
            }

    async def _handle_form_submission(
        self,
        guild: discord.Guild,
        user: discord.User,
        **kwargs
    ) -> typing.Dict[str, typing.Any]:
        """Handle POST form submissions."""
        try:
            # Get form data
            data = kwargs.get("data", {})
            form_data = data.get("form", {})
            
            # Process form data into settings format
            new_settings = {}
            
            # Process filter settings
            new_settings["include_thumbnails"] = "include_thumbnails" in form_data
            new_settings["ignore_bots"] = "ignore_bots" in form_data
            new_settings["ignore_webhooks"] = "ignore_webhooks" in form_data
            new_settings["ignore_tupperbox"] = "ignore_tupperbox" in form_data
            new_settings["ignore_apps"] = "ignore_apps" in form_data
            new_settings["detect_proxy_deletes"] = "detect_proxy_deletes" in form_data
            
            # Process event toggles
            events = {}
            for key in form_data:
                if key.startswith("event_"):
                    event_name = key[6:]  # Remove "event_" prefix
                    events[event_name] = True
            new_settings["events"] = events
            
            # Process channel configurations
            event_channels = {}
            for key in form_data:
                if key.startswith("event_channels[") and key.endswith("]"):
                    event_name = key[15:-1]  # Extract event name from event_channels[event_name]
                    channel_id = form_data[key]
                    if channel_id and channel_id.isdigit():
                        event_channels[event_name] = int(channel_id)
                    else:
                        event_channels[event_name] = None
            new_settings["event_channels"] = event_channels
            
            # Update settings
            await self.update_settings(guild, new_settings)
            
            return {
                "status": 0,
                "notifications": [{"message": "Settings updated successfully!", "category": "success"}],
                "redirect_url": kwargs.get("request_url", ""),
            }
            
        except Exception as e:
            if hasattr(self, 'log') and self.log:
                self.log.error(f"Error handling form submission: {e}")
            return {
                "status": 1,
                "notifications": [{"message": f"Error updating settings: {str(e)}", "category": "error"}],
            }

    async def _generate_dashboard_html(self, guild: discord.Guild, settings: dict, **kwargs) -> str:
        """Generate the main dashboard HTML."""
        # Get CSRF token if available
        csrf_token = kwargs.get("csrf_token", ("", ""))
        csrf_field = f'<input type="hidden" name="csrf_token" value="{csrf_token[0]}">' if csrf_token[0] else ""
        
        # Generate event toggle sections
        event_sections = self._generate_event_sections(settings)
        channel_sections = self._generate_channel_sections(guild, settings)
        filter_sections = self._generate_filter_sections(guild, settings)

        html_content = f"""
        <div style="padding: 1em; max-width: 1200px; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;">
            <div style="background: linear-gradient(135deg, #3949ab 0%, #5e35b1 100%); color: white; padding: 2em; border-radius: 10px; margin-bottom: 2em; box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);">
                <h1 style="margin: 0; font-size: 2em; font-weight: 600;">⚙️ YALC Settings</h1>
                <p style="margin: 0.5em 0 0 0; opacity: 0.9; font-size: 1.1em;">Configure comprehensive logging for <strong>{guild.name}</strong></p>
                <p style="margin: 0.5em 0 0 0; opacity: 0.8; font-size: 0.9em;">Monitor 40+ event types across your Discord server</p>
            </div>

            <form method="POST" style="background: white; border-radius: 10px; padding: 2em; box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1); border: 1px solid #e1e5e9;" id="yalc-settings-form">
                {csrf_field}
                {filter_sections}
                {event_sections}
                {channel_sections}

                <div style="text-align: center; margin-top: 3em; padding-top: 2em; border-top: 2px solid #f0f2f5;">
                    <button type="submit" style="background: linear-gradient(135deg, #4caf50 0%, #45a049 100%); color: white; border: none; padding: 1.2em 3em; border-radius: 8px; font-size: 1.1em; font-weight: 600; cursor: pointer; box-shadow: 0 4px 12px rgba(76, 175, 80, 0.3); transition: all 0.3s ease;" id="save-button">
                        💾 Save Configuration
                    </button>
                    <p style="margin-top: 1em; color: #666; font-size: 0.9em;">
                        Changes are applied immediately and saved to Red's configuration system
                    </p>
                </div>
            </form>

            <div style="margin-top: 2em; padding: 1.5em; background: #f8f9fa; border-radius: 8px; border-left: 4px solid #17a2b8;">
                <h4 style="margin: 0 0 0.5em 0; color: #17a2b8;">ℹ️ About YALC</h4>
                <p style="margin: 0; color: #666; line-height: 1.5;">
                    Yet Another Logging Cog provides comprehensive event logging for Discord servers.
                    Configure which events to log, assign specific channels for different event types,
                    and customize filtering options to suit your server's needs.
                </p>
            </div>

            <script>
                // Add interactive enhancements
                document.addEventListener('DOMContentLoaded', function() {{
                    // Add hover effects to checkboxes
                    const labels = document.querySelectorAll('label');
                    labels.forEach(label => {{
                        label.addEventListener('mouseenter', function() {{
                            this.style.transform = 'translateY(-1px)';
                            this.style.boxShadow = '0 4px 8px rgba(0, 0, 0, 0.1)';
                        }});
                        label.addEventListener('mouseleave', function() {{
                            this.style.transform = 'translateY(0)';
                            this.style.boxShadow = '0 1px 3px rgba(0, 0, 0, 0.05)';
                        }});
                    }});

                    // Add form submission feedback
                    const form = document.getElementById('yalc-settings-form');
                    const saveButton = document.getElementById('save-button');
                    
                    if (form && saveButton) {{
                        form.addEventListener('submit', function() {{
                            saveButton.innerHTML = '⏳ Saving...';
                            saveButton.disabled = true;
                            saveButton.style.opacity = '0.7';
                        }});
                    }}

                    // Count enabled events and update display
                    function updateEventCounts() {{
                        const eventCheckboxes = document.querySelectorAll('input[name^="event_"]');
                        let totalEnabled = 0;
                        eventCheckboxes.forEach(checkbox => {{
                            if (checkbox.checked) totalEnabled++;
                        }});
                        
                        // Update any event counter displays
                        const counters = document.querySelectorAll('.event-counter');
                        counters.forEach(counter => {{
                            counter.textContent = totalEnabled;
                        }});
                    }}

                    // Add event listeners to checkboxes
                    const eventCheckboxes = document.querySelectorAll('input[name^="event_"]');
                    eventCheckboxes.forEach(checkbox => {{
                        checkbox.addEventListener('change', updateEventCounts);
                    }});
                    
                    // Initial count
                    updateEventCounts();
                }});
            </script>
        </div>
        """
        return html_content

    def _generate_event_sections(self, settings: dict) -> str:
        """Generate HTML for event toggle sections."""
        # Get event descriptions from the main cog
        event_descriptions = getattr(self, 'event_descriptions', {})
        
        # Expanded categories with more complete event coverage
        categories = {
            "Message Events": {
                "events": ["message_delete", "message_edit", "message_bulk_delete", "message_pin", "message_unpin"],
                "color": "#e74c3c",
                "description": "Track message modifications, deletions, and pin changes"
            },
            "Member Events": {
                "events": ["member_join", "member_leave", "member_ban", "member_unban", "member_kick", "member_timeout", "member_update"],
                "color": "#3498db",
                "description": "Monitor member activity and moderation actions"
            },
            "Voice Events": {
                "events": ["voice_state_update"],
                "color": "#9b59b6",
                "description": "Track voice channel activity and state changes"
            },
            "Channel Events": {
                "events": ["channel_create", "channel_delete", "channel_update", "thread_create", "thread_delete", "thread_update"],
                "color": "#f39c12",
                "description": "Monitor channel and thread management"
            },
            "Role Events": {
                "events": ["role_create", "role_delete", "role_update"],
                "color": "#e67e22",
                "description": "Track role creation, deletion, and permission changes"
            },
            "Server Events": {
                "events": ["guild_update", "emoji_update"],
                "color": "#1abc9c",
                "description": "Monitor server settings and emoji changes"
            }
        }

        sections = []

        for category_name, category_info in categories.items():
            events = category_info["events"]
            color = category_info["color"]
            description = category_info["description"]
            
            event_checkboxes = []
            enabled_count = 0
            
            for event in events:
                if event in event_descriptions:
                    emoji, desc = event_descriptions[event]
                    is_checked = settings.get("events", {}).get(event, False)
                    if is_checked:
                        enabled_count += 1
                    
                    checked = "checked" if is_checked else ""
                    event_checkboxes.append(f"""
                        <label style="display: flex; align-items: center; padding: 0.6em; background: white; border-radius: 6px; border: 1px solid #e1e5e9; cursor: pointer; transition: all 0.2s ease; margin-bottom: 8px;">
                            <input type="checkbox" name="event_{event}" value="1" {checked}
                                   style="margin-right: 10px; transform: scale(1.3); accent-color: {color};">
                            <div style="flex: 1;">
                                <div style="font-weight: 500; color: #2c3e50;">{emoji} {desc}</div>
                                <div style="font-size: 0.8em; color: #7f8c8d; margin-top: 2px;">Event: {event}</div>
                            </div>
                        </label>
                    """)

            if event_checkboxes:
                status_badge = f"""
                    <span style="background: {color}; color: white; padding: 0.3em 0.8em; border-radius: 12px; font-size: 0.85em; font-weight: 500;">
                        {enabled_count}/{len(events)} enabled
                    </span>
                """
                
                sections.append(f"""
                    <div style="margin-bottom: 2em; padding: 1.5em; background: #f8f9fa; border-radius: 8px; border-left: 4px solid {color};">
                        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 1em;">
                            <h3 style="color: {color}; margin: 0; font-size: 1.3em; font-weight: 600;">{category_name}</h3>
                            {status_badge}
                        </div>
                        <p style="color: #666; margin-bottom: 1.5em; font-size: 0.95em;">{description}</p>
                        <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 12px;">
                            {"".join(event_checkboxes)}
                        </div>
                    </div>
                """)

        return "".join(sections)

    def _generate_channel_sections(self, guild: discord.Guild, settings: dict) -> str:
        """Generate HTML for channel configuration sections."""
        # Get text channels for dropdown
        text_channels = [c for c in guild.channels if isinstance(c, discord.TextChannel)]
        text_channels.sort(key=lambda c: c.name.lower())  # Sort alphabetically
        
        channel_options = '<option value="">📵 No logging</option>' + "".join(
            f'<option value="{c.id}">#{c.name}</option>' for c in text_channels
        )

        enabled_events = [event for event, enabled in settings.get("events", {}).items() if enabled]

        if not enabled_events:
            return """
            <div style="margin-bottom: 2em; padding: 2em; background: linear-gradient(135deg, #fff3cd 0%, #ffeaa7 100%); border-radius: 8px; border-left: 4px solid #f39c12; text-align: center;">
                <h4 style="margin: 0 0 0.5em 0; color: #f39c12; font-size: 1.2em;">⚠️ No Events Enabled</h4>
                <p style="margin: 0; color: #856404; font-size: 1em;">
                    Enable some events in the sections above to configure their log channels.
                    <br><small>Each event type can be logged to a different channel for better organization.</small>
                </p>
            </div>
            """

        event_descriptions = getattr(self, 'event_descriptions', {})
        
        # Group events by category for better organization
        categories = {
            "Message Events": ["message_delete", "message_edit", "message_bulk_delete", "message_pin", "message_unpin"],
            "Member Events": ["member_join", "member_leave", "member_ban", "member_unban", "member_kick", "member_timeout", "member_update"],
            "Voice Events": ["voice_state_update"],
            "Channel Events": ["channel_create", "channel_delete", "channel_update", "thread_create", "thread_delete", "thread_update"],
            "Role Events": ["role_create", "role_delete", "role_update"],
            "Server Events": ["guild_update", "emoji_update"]
        }
        
        category_sections = []
        configured_count = 0
        total_enabled = len(enabled_events)
        
        for category_name, category_events in categories.items():
            category_enabled = [event for event in category_events if event in enabled_events]
            if not category_enabled:
                continue
                
            channel_config_html = ""
            for event in category_enabled:
                if event in event_descriptions:
                    emoji, desc = event_descriptions[event]
                    current_channel_id = settings.get("event_channels", {}).get(event)
                    if current_channel_id:
                        configured_count += 1
                    
                    # Create options with current selection
                    options_with_selection = channel_options
                    if current_channel_id:
                        options_with_selection = options_with_selection.replace(
                            f'value="{current_channel_id}"',
                            f'value="{current_channel_id}" selected'
                        )

                    channel_config_html += f"""
                        <div style="display: flex; justify-content: space-between; align-items: center; padding: 0.8em; background: white; border-radius: 6px; border: 1px solid #e1e5e9; margin-bottom: 8px;">
                            <label for="channel_{event}" style="flex: 1; margin-right: 1.5em; font-weight: 500; color: #2c3e50;">
                                {emoji} {desc}
                                <div style="font-size: 0.8em; color: #7f8c8d; margin-top: 2px; font-weight: normal;">Event: {event}</div>
                            </label>
                            <select name="event_channels[{event}]" id="channel_{event}"
                                    style="flex: 0 0 250px; padding: 0.7em; border-radius: 6px; border: 1px solid #ddd; font-size: 0.9em; background: white;">
                                {options_with_selection}
                            </select>
                        </div>
                    """
            
            if channel_config_html:
                category_sections.append(f"""
                    <div style="margin-bottom: 1.5em;">
                        <h4 style="color: #3949ab; margin: 0 0 0.8em 0; font-size: 1.1em; font-weight: 600; border-bottom: 1px solid #e1e5e9; padding-bottom: 0.5em;">
                            {category_name}
                        </h4>
                        {channel_config_html}
                    </div>
                """)

        status_text = f"{configured_count}/{total_enabled} events have channels configured"
        status_color = "#28a745" if configured_count == total_enabled else "#ffc107" if configured_count > 0 else "#dc3545"

        return f"""
            <div style="margin-bottom: 2em; padding: 1.5em; background: #f8f9fa; border-radius: 8px; border-left: 4px solid #17a2b8;">
                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 1em;">
                    <h3 style="color: #17a2b8; margin: 0; font-size: 1.3em; font-weight: 600;">📢 Event Log Channels</h3>
                    <span style="background: {status_color}; color: white; padding: 0.3em 0.8em; border-radius: 12px; font-size: 0.85em; font-weight: 500;">
                        {status_text}
                    </span>
                </div>
                <p style="color: #666; margin-bottom: 1.5em; font-size: 0.95em;">
                    Assign specific channels for each enabled event type. Events without assigned channels won't be logged.
                    <br><small style="color: #888;">💡 Tip: Use different channels for different event types to keep logs organized.</small>
                </p>
                {"".join(category_sections)}
            </div>
        """

    def _generate_filter_sections(self, guild: discord.Guild, settings: dict) -> str:
        """Generate HTML for filtering options."""
        return f"""
            <div style="margin-bottom: 2em; padding: 1.5em; background: #f8f9fa; border-radius: 8px; border-left: 4px solid #28a745;">
                <h3 style="color: #28a745; margin-top: 0; margin-bottom: 1em; font-size: 1.3em; font-weight: 600;">🔍 Filtering Options</h3>
                <p style="color: #666; margin-bottom: 1.5em; font-size: 0.95em;">Configure what types of messages and events to include or exclude from logging.</p>

                <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 20px;">
                    <label style="display: flex; align-items: center; padding: 0.8em; background: white; border-radius: 6px; border: 1px solid #e1e5e9; cursor: pointer; transition: all 0.2s ease;">
                        <input type="checkbox" name="include_thumbnails" value="1" {'checked' if settings.get('include_thumbnails', True) else ''}
                               style="margin-right: 12px; transform: scale(1.3); accent-color: #28a745;">
                        <div>
                            <div style="font-weight: 500;">🖼️ Include user thumbnails</div>
                            <div style="font-size: 0.85em; color: #666; margin-top: 2px;">Show user avatars in log embeds</div>
                        </div>
                    </label>

                    <label style="display: flex; align-items: center; padding: 0.8em; background: white; border-radius: 6px; border: 1px solid #e1e5e9; cursor: pointer; transition: all 0.2s ease;">
                        <input type="checkbox" name="ignore_bots" value="1" {'checked' if settings.get('ignore_bots', False) else ''}
                               style="margin-right: 12px; transform: scale(1.3); accent-color: #28a745;">
                        <div>
                            <div style="font-weight: 500;">🤖 Ignore bot messages</div>
                            <div style="font-size: 0.85em; color: #666; margin-top: 2px;">Skip logging events from bots</div>
                        </div>
                    </label>

                    <label style="display: flex; align-items: center; padding: 0.8em; background: white; border-radius: 6px; border: 1px solid #e1e5e9; cursor: pointer; transition: all 0.2s ease;">
                        <input type="checkbox" name="ignore_webhooks" value="1" {'checked' if settings.get('ignore_webhooks', False) else ''}
                               style="margin-right: 12px; transform: scale(1.3); accent-color: #28a745;">
                        <div>
                            <div style="font-weight: 500;">🪝 Ignore webhook messages</div>
                            <div style="font-size: 0.85em; color: #666; margin-top: 2px;">Skip logging webhook events</div>
                        </div>
                    </label>

                    <label style="display: flex; align-items: center; padding: 0.8em; background: white; border-radius: 6px; border: 1px solid #e1e5e9; cursor: pointer; transition: all 0.2s ease;">
                        <input type="checkbox" name="ignore_tupperbox" value="1" {'checked' if settings.get('ignore_tupperbox', True) else ''}
                               style="margin-right: 12px; transform: scale(1.3); accent-color: #28a745;">
                        <div>
                            <div style="font-weight: 500;">👥 Ignore Tupperbox/proxy messages</div>
                            <div style="font-size: 0.85em; color: #666; margin-top: 2px;">Skip logging proxy bot messages</div>
                        </div>
                    </label>

                    <label style="display: flex; align-items: center; padding: 0.8em; background: white; border-radius: 6px; border: 1px solid #e1e5e9; cursor: pointer; transition: all 0.2s ease;">
                        <input type="checkbox" name="ignore_apps" value="1" {'checked' if settings.get('ignore_apps', True) else ''}
                               style="margin-right: 12px; transform: scale(1.3); accent-color: #28a745;">
                        <div>
                            <div style="font-weight: 500;">📱 Ignore app messages</div>
                            <div style="font-size: 0.85em; color: #666; margin-top: 2px;">Skip logging application events</div>
                        </div>
                    </label>

                    <label style="display: flex; align-items: center; padding: 0.8em; background: white; border-radius: 6px; border: 1px solid #e1e5e9; cursor: pointer; transition: all 0.2s ease;">
                        <input type="checkbox" name="detect_proxy_deletes" value="1" {'checked' if settings.get('detect_proxy_deletes', True) else ''}
                               style="margin-right: 12px; transform: scale(1.3); accent-color: #28a745;">
                        <div>
                            <div style="font-weight: 500;">🔍 Detect proxy deletes</div>
                            <div style="font-size: 0.85em; color: #666; margin-top: 2px;">Log when proxy messages are deleted</div>
                        </div>
                    </label>
                </div>
            </div>
        """

    @commands.Cog.listener()
    async def on_dashboard_cog_add(self, dashboard_cog: commands.Cog) -> None:
        """Register the dashboard integration when dashboard cog is loaded."""
        dashboard_cog.rpc.third_parties_handler.add_third_party(self)
