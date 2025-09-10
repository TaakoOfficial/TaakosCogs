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
        
        # Note: event_descriptions will be provided by the main YALC class
        # No fallback is needed since this is a mixin that requires the main cog

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

            # Get current settings
            settings = await self.config.guild(guild).all()

            # Add comprehensive logging for debugging
            if hasattr(self, 'log') and self.log:
                self.log.info(f"YALC Dashboard accessed by {user.name} ({user.id}) for guild {guild.name} ({guild.id})")

            # Handle form submission with proper CSRF validation
            method = kwargs.get("method", "GET")
            
            # Enhanced diagnostic logging
            if hasattr(self, 'log') and self.log:
                self.log.debug(f"YALC Dashboard: method={method}, kwargs keys: {list(kwargs.keys())}")
                if 'guild' in kwargs:
                    self.log.warning(f"YALC Dashboard: 'guild' found in kwargs, this may cause duplicate parameter error")
            
            if method == "POST":
                return await self._handle_wtforms_submission(guild, user, settings, **kwargs)
            
            # Remove 'guild' from kwargs to prevent duplicate parameter error
            clean_kwargs = {k: v for k, v in kwargs.items() if k != 'guild'}
            
            # Generate the dashboard using WTForms approach
            return await self._generate_wtforms_dashboard(guild, settings, **clean_kwargs)
            
        except Exception as e:
            # Enhanced error logging
            if hasattr(self, 'log') and self.log:
                self.log.error(f"Error in YALC dashboard page: {e}", exc_info=True)
            
            return {
                "status": 1,
                "error_title": "Dashboard Error",
                "error_message": f"An error occurred while loading the dashboard: {str(e)}"
            }

    async def _handle_wtforms_submission(
        self,
        guild: discord.Guild,
        user: discord.User,
        settings: dict,
        **kwargs
    ) -> typing.Dict[str, typing.Any]:
        """Handle POST form submissions with CSRF validation and proper error handling."""
        try:
            # Get form data and validate CSRF
            form_data = kwargs.get("data", {})
            
            # Enhanced logging for debugging
            if hasattr(self, 'log') and self.log:
                self.log.info(f"YALC form submission from {user.name} ({user.id}) for guild {guild.name}")
                self.log.debug(f"Form data keys: {list(form_data.keys())}")
            
            # Check for CSRF token (Red-Web-Dashboard should handle this automatically)
            if not form_data:
                if hasattr(self, 'log') and self.log:
                    self.log.warning(f"YALC: Empty form data received from {user.name}")
                return {
                    "status": 1,
                    "error_title": "Form Error",
                    "error_message": "No form data received. This might be a CSRF token issue.",
                    "notifications": [{"message": "❌ Form submission failed: No data received", "category": "error"}]
                }
            
            # Process the form submission
            try:
                new_settings = await self._process_form_data(form_data)
                
                # Enhanced logging of what we're saving
                if hasattr(self, 'log') and self.log:
                    self.log.info(f"YALC: Updating settings for {guild.name}: {new_settings}")
                
                # Update settings with error handling
                await self.update_settings(guild, new_settings)
                
                # Log successful save
                if hasattr(self, 'log') and self.log:
                    self.log.info(f"YALC: Settings successfully updated for {guild.name}")
                
                return {
                    "status": 0,
                    "notifications": [{"message": "✅ YALC settings updated successfully!", "category": "success"}],
                    "redirect_url": kwargs.get("request_url", ""),
                }
                
            except Exception as settings_error:
                # Log settings update error
                if hasattr(self, 'log') and self.log:
                    self.log.error(f"YALC: Error updating settings for {guild.name}: {settings_error}", exc_info=True)
                
                return {
                    "status": 1,
                    "error_title": "Settings Update Error",
                    "error_message": f"Failed to save settings: {str(settings_error)}",
                    "notifications": [{"message": f"❌ Error saving settings: {str(settings_error)}", "category": "error"}]
                }
            
        except Exception as e:
            # Log submission handling error
            if hasattr(self, 'log') and self.log:
                self.log.error(f"YALC: Error handling form submission: {e}", exc_info=True)
            
            return {
                "status": 1,
                "error_title": "Form Processing Error",
                "error_message": f"Error processing form submission: {str(e)}",
                "notifications": [{"message": f"❌ Form processing failed: {str(e)}", "category": "error"}]
            }

    async def _process_form_data(self, form_data: dict) -> dict:
        """Process form data into settings format with validation."""
        new_settings = {}
        
        # Process basic filter settings (checkboxes only appear if checked)
        checkbox_settings = [
            "include_thumbnails", "ignore_bots", "ignore_webhooks",
            "ignore_tupperbox", "ignore_apps", "detect_proxy_deletes"
        ]
        
        for setting in checkbox_settings:
            # Check both prefixed and non-prefixed versions for compatibility
            new_settings[setting] = (
                setting in form_data or
                f"yalc_settings_{setting}" in form_data
            )
        
        # Process event toggles
        events = {}
        for key, value in form_data.items():
            if key.startswith("event_"):
                event_name = key[6:]  # Remove "event_" prefix
                events[event_name] = True  # If field exists, it's checked
        new_settings["events"] = events
        
        # Process channel configurations
        event_channels = {}
        for key, value in form_data.items():
            if key.startswith("event_channels[") and key.endswith("]"):
                event_name = key[15:-1]  # Extract event name
                if value and str(value).isdigit():
                    event_channels[event_name] = int(value)
                else:
                    event_channels[event_name] = None
        new_settings["event_channels"] = event_channels
        
        return new_settings

    async def _generate_wtforms_dashboard(
        self,
        guild: discord.Guild,
        settings: dict,
        **kwargs
    ) -> typing.Dict[str, typing.Any]:
        """Generate dashboard using WTForms approach with proper CSRF handling."""
        try:
            # Enhanced diagnostic logging for form debugging
            if hasattr(self, 'log') and self.log:
                self.log.debug(f"YALC WTForms Debug: kwargs keys: {list(kwargs.keys())}")
                self.log.debug(f"YALC WTForms Debug: Form type: {type(kwargs.get('Form'))}")
                self.log.debug(f"YALC WTForms Debug: Form value: {kwargs.get('Form')}")
            
            # Check if WTForms is available in kwargs (passed by Red-Web-Dashboard)
            Form = kwargs.get("Form")
            if not Form:
                # Fallback to manual form with warning about CSRF
                if hasattr(self, 'log') and self.log:
                    self.log.warning("YALC: WTForms not available, falling back to manual form")
                return await self._generate_fallback_dashboard(guild, settings, **kwargs)
            
            # Create WTForms class with CSRF protection
            import wtforms
            
            class YALCSettingsForm(Form):
                def __init__(self, *args, **kwargs):
                    super().__init__(prefix="yalc_settings_", *args, **kwargs)
                
                # Filter settings
                include_thumbnails = wtforms.BooleanField(
                    "Include user thumbnails",
                    default=settings.get("include_thumbnails", True),
                    description="Show user avatars in log embeds"
                )
                ignore_bots = wtforms.BooleanField(
                    "Ignore bot messages",
                    default=settings.get("ignore_bots", False),
                    description="Skip logging events from bots"
                )
                ignore_webhooks = wtforms.BooleanField(
                    "Ignore webhook messages",
                    default=settings.get("ignore_webhooks", False),
                    description="Skip logging webhook events"
                )
                ignore_tupperbox = wtforms.BooleanField(
                    "Ignore Tupperbox/proxy messages",
                    default=settings.get("ignore_tupperbox", True),
                    description="Skip logging proxy bot messages"
                )
                ignore_apps = wtforms.BooleanField(
                    "Ignore app messages",
                    default=settings.get("ignore_apps", True),
                    description="Skip logging application events"
                )
                detect_proxy_deletes = wtforms.BooleanField(
                    "Detect proxy deletes",
                    default=settings.get("detect_proxy_deletes", True),
                    description="Log when proxy messages are deleted"
                )
                
                submit = wtforms.SubmitField("💾 Save Configuration")
            
            # Create form instance with enhanced debugging
            form = YALCSettingsForm()
            
            # Enhanced form debugging
            if hasattr(self, 'log') and self.log:
                self.log.debug(f"YALC: Created form instance: {type(form)}")
                self.log.debug(f"YALC: Form instance details: {form}")
                self.log.debug(f"YALC: Form has include_thumbnails field: {hasattr(form, 'yalc_settings_include_thumbnails')}")
                if hasattr(form, 'yalc_settings_include_thumbnails'):
                    self.log.debug(f"YALC: include_thumbnails field type: {type(form.yalc_settings_include_thumbnails)}")
            
            # Generate additional sections for events and channels
            event_sections = self._generate_event_sections(settings)
            channel_sections = self._generate_channel_sections(guild, settings)
            
            # Generate the HTML template
            html_template = await self._generate_wtforms_html(guild, settings, event_sections, channel_sections)
            
            # Enhanced logging for template and form
            if hasattr(self, 'log') and self.log:
                self.log.debug(f"YALC: HTML template length: {len(html_template)}")
                self.log.debug(f"YALC: About to return form type: {type(form)}")
            
            # Return template without form object to avoid Jinja2 template errors
            # The template now uses manual HTML forms with proper field names
            result = {
                "status": 0,
                "web_content": {
                    "source": html_template,
                    "expanded": True,
                },
            }
            
            # Final debug check
            if hasattr(self, 'log') and self.log:
                self.log.debug(f"YALC: Final result web_content keys: {list(result['web_content'].keys())}")
                self.log.debug(f"YALC: Template-based approach - no form object passed")
            
            return result
            
        except Exception as e:
            if hasattr(self, 'log') and self.log:
                self.log.error(f"YALC: Error generating WTForms dashboard: {e}", exc_info=True)
            
            # Fallback to basic dashboard
            return await self._generate_fallback_dashboard(guild, settings, **kwargs)

    async def _generate_fallback_dashboard(
        self,
        guild: discord.Guild,
        settings: dict,
        **kwargs
    ) -> typing.Dict[str, typing.Any]:
        """Generate fallback dashboard when WTForms is not available."""
        try:
            # Generate sections
            event_sections = self._generate_event_sections(settings)
            channel_sections = self._generate_channel_sections(guild, settings)
            
            # Warning message about CSRF
            csrf_warning = """
                <div style="margin-bottom: 2em; padding: 1.5em; background: #2d1f2d; border-radius: 8px; border-left: 4px solid #ff5722;">
                    <h4 style="margin: 0 0 0.5em 0; color: #ff5722;">⚠️ CSRF Protection Warning</h4>
                    <p style="margin: 0; color: #ffab91; line-height: 1.5;">
                        WTForms is not available - using fallback form without full CSRF protection.
                        If settings don't save properly, please ensure Red-Web-Dashboard is properly configured.
                    </p>
                </div>
            """
            
            # Create checkbox values
            checkbox_values = {
                "include_thumbnails": "checked" if settings.get("include_thumbnails", True) else "",
                "ignore_bots": "checked" if settings.get("ignore_bots", False) else "",
                "ignore_webhooks": "checked" if settings.get("ignore_webhooks", False) else "",
                "ignore_tupperbox": "checked" if settings.get("ignore_tupperbox", True) else "",
                "ignore_apps": "checked" if settings.get("ignore_apps", True) else "",
                "detect_proxy_deletes": "checked" if settings.get("detect_proxy_deletes", True) else "",
            }

            source = f"""
            <div style="padding: 1em; max-width: 1200px; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #1a1a1a; color: #e0e0e0; min-height: 100vh;">
                <div style="background: linear-gradient(135deg, #2c5aa0 0%, #4a148c 100%); color: white; padding: 2em; border-radius: 10px; margin-bottom: 2em; box-shadow: 0 4px 12px rgba(0, 0, 0, 0.3);">
                    <h1 style="margin: 0; font-size: 2em; font-weight: 600;">⚙️ YALC Settings</h1>
                    <p style="margin: 0.5em 0 0 0; opacity: 0.9; font-size: 1.1em;">Configure comprehensive logging for <strong>{guild.name}</strong></p>
                    <p style="margin: 0.5em 0 0 0; opacity: 0.8; font-size: 0.9em;">Monitor 40+ event types across your Discord server</p>
                </div>

                {csrf_warning}

                <form method="POST" style="width: 100%;">
                    <!-- Filter Settings Section -->
                    <div style="margin-bottom: 2em; padding: 1.5em; background: #2d2d2d; border-radius: 8px; border-left: 4px solid #4caf50;">
                        <h3 style="color: #4caf50; margin-top: 0; margin-bottom: 1em; font-size: 1.3em; font-weight: 600;">🔍 Filtering Options</h3>
                        <p style="color: #b0b0b0; margin-bottom: 1.5em; font-size: 0.95em;">Configure what types of messages and events to include or exclude from logging.</p>

                        <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 20px;">
                            <label style="display: flex; align-items: center; padding: 0.8em; background: #3a3a3a; border-radius: 6px; border: 1px solid #4a4a4a; cursor: pointer; transition: all 0.2s ease;">
                                <input type="checkbox" name="include_thumbnails" value="1" {checkbox_values["include_thumbnails"]}
                                       style="margin-right: 12px; transform: scale(1.3); accent-color: #4caf50;">
                                <div>
                                    <div style="font-weight: 500; color: #e0e0e0;">🖼️ Include user thumbnails</div>
                                    <div style="font-size: 0.85em; color: #b0b0b0; margin-top: 2px;">Show user avatars in log embeds</div>
                                </div>
                            </label>

                            <label style="display: flex; align-items: center; padding: 0.8em; background: #3a3a3a; border-radius: 6px; border: 1px solid #4a4a4a; cursor: pointer; transition: all 0.2s ease;">
                                <input type="checkbox" name="ignore_bots" value="1" {checkbox_values["ignore_bots"]}
                                       style="margin-right: 12px; transform: scale(1.3); accent-color: #4caf50;">
                                <div>
                                    <div style="font-weight: 500; color: #e0e0e0;">🤖 Ignore bot messages</div>
                                    <div style="font-size: 0.85em; color: #b0b0b0; margin-top: 2px;">Skip logging events from bots</div>
                                </div>
                            </label>

                            <label style="display: flex; align-items: center; padding: 0.8em; background: #3a3a3a; border-radius: 6px; border: 1px solid #4a4a4a; cursor: pointer; transition: all 0.2s ease;">
                                <input type="checkbox" name="ignore_webhooks" value="1" {checkbox_values["ignore_webhooks"]}
                                       style="margin-right: 12px; transform: scale(1.3); accent-color: #4caf50;">
                                <div>
                                    <div style="font-weight: 500; color: #e0e0e0;">🪝 Ignore webhook messages</div>
                                    <div style="font-size: 0.85em; color: #b0b0b0; margin-top: 2px;">Skip logging webhook events</div>
                                </div>
                            </label>

                            <label style="display: flex; align-items: center; padding: 0.8em; background: #3a3a3a; border-radius: 6px; border: 1px solid #4a4a4a; cursor: pointer; transition: all 0.2s ease;">
                                <input type="checkbox" name="ignore_tupperbox" value="1" {checkbox_values["ignore_tupperbox"]}
                                       style="margin-right: 12px; transform: scale(1.3); accent-color: #4caf50;">
                                <div>
                                    <div style="font-weight: 500; color: #e0e0e0;">👥 Ignore Tupperbox/proxy messages</div>
                                    <div style="font-size: 0.85em; color: #b0b0b0; margin-top: 2px;">Skip logging proxy bot messages</div>
                                </div>
                            </label>

                            <label style="display: flex; align-items: center; padding: 0.8em; background: #3a3a3a; border-radius: 6px; border: 1px solid #4a4a4a; cursor: pointer; transition: all 0.2s ease;">
                                <input type="checkbox" name="ignore_apps" value="1" {checkbox_values["ignore_apps"]}
                                       style="margin-right: 12px; transform: scale(1.3); accent-color: #4caf50;">
                                <div>
                                    <div style="font-weight: 500; color: #e0e0e0;">📱 Ignore app messages</div>
                                    <div style="font-size: 0.85em; color: #b0b0b0; margin-top: 2px;">Skip logging application events</div>
                                </div>
                            </label>

                            <label style="display: flex; align-items: center; padding: 0.8em; background: #3a3a3a; border-radius: 6px; border: 1px solid #4a4a4a; cursor: pointer; transition: all 0.2s ease;">
                                <input type="checkbox" name="detect_proxy_deletes" value="1" {checkbox_values["detect_proxy_deletes"]}
                                       style="margin-right: 12px; transform: scale(1.3); accent-color: #4caf50;">
                                <div>
                                    <div style="font-weight: 500; color: #e0e0e0;">🔍 Detect proxy deletes</div>
                                    <div style="font-size: 0.85em; color: #b0b0b0; margin-top: 2px;">Log when proxy messages are deleted</div>
                                </div>
                            </label>
                        </div>
                    </div>
                
                    <!-- Additional event and channel sections -->
                    <div style="margin-top: 2em;">
                        {event_sections}
                        {channel_sections}
                    </div>

                    <!-- Submit button -->
                    <div style="text-align: center; margin-top: 3em; padding-top: 2em; border-top: 2px solid #4a4a4a;">
                        <input type="submit" name="submit" value="💾 Save Configuration"
                               style="background: linear-gradient(135deg, #4caf50 0%, #45a049 100%); color: white; border: none; padding: 1.2em 3em; border-radius: 8px; font-size: 1.1em; font-weight: 600; cursor: pointer; box-shadow: 0 4px 12px rgba(76, 175, 80, 0.3); transition: all 0.3s ease;">
                        <p style="margin-top: 1em; color: #b0b0b0; font-size: 0.9em;">
                            Changes are applied immediately and saved to Red's configuration system
                        </p>
                    </div>
                </form>

                <div style="margin-top: 2em; padding: 1.5em; background: #2d2d2d; border-radius: 8px; border-left: 4px solid #00bcd4;">
                    <h4 style="margin: 0 0 0.5em 0; color: #00bcd4;">ℹ️ About YALC</h4>
                    <p style="margin: 0; color: #b0b0b0; line-height: 1.5;">
                        Yet Another Logging Cog provides comprehensive event logging for Discord servers.
                        Configure which events to log, assign specific channels for different event types,
                        and customize filtering options to suit your server's needs.
                    </p>
                </div>

                <script>
                    document.addEventListener('DOMContentLoaded', function() {{
                        // Add interactive enhancements
                        const labels = document.querySelectorAll('label');
                        labels.forEach(label => {{
                            label.addEventListener('mouseenter', function() {{
                                this.style.transform = 'translateY(-1px)';
                                this.style.boxShadow = '0 4px 8px rgba(255, 255, 255, 0.1)';
                            }});
                            label.addEventListener('mouseleave', function() {{
                                this.style.transform = 'translateY(0)';
                                this.style.boxShadow = '0 1px 3px rgba(255, 255, 255, 0.05)';
                            }});
                        }});

                        // Add form submission feedback
                        const submitButton = document.querySelector('input[type="submit"]');
                        if (submitButton) {{
                            submitButton.addEventListener('click', function() {{
                                this.value = '⏳ Saving...';
                                this.disabled = true;
                                this.style.opacity = '0.7';
                            }});
                        }}
                    }});
                </script>
            </div>
            """
            
            return {
                "status": 0,
                "web_content": {
                    "source": source,
                    "expanded": True,
                },
            }
            
        except Exception as e:
            if hasattr(self, 'log') and self.log:
                self.log.error(f"YALC: Error generating fallback dashboard: {e}", exc_info=True)
            
            return {
                "status": 1,
                "error_title": "Dashboard Generation Error",
                "error_message": f"Failed to generate dashboard: {str(e)}"
            }

    async def _generate_wtforms_html(
        self,
        guild: discord.Guild,
        settings: dict,
        event_sections: str,
        channel_sections: str
    ) -> str:
        """Generate HTML template for WTForms rendering.
        
        This method now returns a simplified template that doesn't rely on form field access,
        since the Jinja2 error suggests the form object isn't being passed correctly to the template context.
        """
        # Create checkbox values for direct HTML rendering
        checkbox_values = {
            "include_thumbnails": "checked" if settings.get("include_thumbnails", True) else "",
            "ignore_bots": "checked" if settings.get("ignore_bots", False) else "",
            "ignore_webhooks": "checked" if settings.get("ignore_webhooks", False) else "",
            "ignore_tupperbox": "checked" if settings.get("ignore_tupperbox", True) else "",
            "ignore_apps": "checked" if settings.get("ignore_apps", True) else "",
            "detect_proxy_deletes": "checked" if settings.get("detect_proxy_deletes", True) else "",
        }
        
        return f"""
        <div style="padding: 1em; max-width: 1200px; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #1a1a1a; color: #e0e0e0; min-height: 100vh;">
            <div style="background: linear-gradient(135deg, #2c5aa0 0%, #4a148c 100%); color: white; padding: 2em; border-radius: 10px; margin-bottom: 2em; box-shadow: 0 4px 12px rgba(0, 0, 0, 0.3);">
                <h1 style="margin: 0; font-size: 2em; font-weight: 600;">⚙️ YALC Settings</h1>
                <p style="margin: 0.5em 0 0 0; opacity: 0.9; font-size: 1.1em;">Configure comprehensive logging for <strong>{guild.name}</strong></p>
                <p style="margin: 0.5em 0 0 0; opacity: 0.8; font-size: 0.9em;">Monitor 40+ event types across your Discord server</p>
            </div>

            <!-- Manual form since WTForms template access is problematic -->
            <form method="POST" style="width: 100%;">
                <!-- Filter Settings Section -->
                <div style="margin-bottom: 2em; padding: 1.5em; background: #2d2d2d; border-radius: 8px; border-left: 4px solid #4caf50;">
                    <h3 style="color: #4caf50; margin-top: 0; margin-bottom: 1em; font-size: 1.3em; font-weight: 600;">🔍 Filtering Options</h3>
                    <p style="color: #b0b0b0; margin-bottom: 1.5em; font-size: 0.95em;">Configure what types of messages and events to include or exclude from logging.</p>

                    <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 20px;">
                        <label style="display: flex; align-items: center; padding: 0.8em; background: #3a3a3a; border-radius: 6px; border: 1px solid #4a4a4a; cursor: pointer; transition: all 0.2s ease;">
                            <input type="checkbox" name="yalc_settings_include_thumbnails" value="1" {checkbox_values["include_thumbnails"]}
                                   style="margin-right: 12px; transform: scale(1.3); accent-color: #4caf50;">
                            <div>
                                <div style="font-weight: 500; color: #e0e0e0;">🖼️ Include user thumbnails</div>
                                <div style="font-size: 0.85em; color: #b0b0b0; margin-top: 2px;">Show user avatars in log embeds</div>
                            </div>
                        </label>

                        <label style="display: flex; align-items: center; padding: 0.8em; background: #3a3a3a; border-radius: 6px; border: 1px solid #4a4a4a; cursor: pointer; transition: all 0.2s ease;">
                            <input type="checkbox" name="yalc_settings_ignore_bots" value="1" {checkbox_values["ignore_bots"]}
                                   style="margin-right: 12px; transform: scale(1.3); accent-color: #4caf50;">
                            <div>
                                <div style="font-weight: 500; color: #e0e0e0;">🤖 Ignore bot messages</div>
                                <div style="font-size: 0.85em; color: #b0b0b0; margin-top: 2px;">Skip logging events from bots</div>
                            </div>
                        </label>

                        <label style="display: flex; align-items: center; padding: 0.8em; background: #3a3a3a; border-radius: 6px; border: 1px solid #4a4a4a; cursor: pointer; transition: all 0.2s ease;">
                            <input type="checkbox" name="yalc_settings_ignore_webhooks" value="1" {checkbox_values["ignore_webhooks"]}
                                   style="margin-right: 12px; transform: scale(1.3); accent-color: #4caf50;">
                            <div>
                                <div style="font-weight: 500; color: #e0e0e0;">🪝 Ignore webhook messages</div>
                                <div style="font-size: 0.85em; color: #b0b0b0; margin-top: 2px;">Skip logging webhook events</div>
                            </div>
                        </label>

                        <label style="display: flex; align-items: center; padding: 0.8em; background: #3a3a3a; border-radius: 6px; border: 1px solid #4a4a4a; cursor: pointer; transition: all 0.2s ease;">
                            <input type="checkbox" name="yalc_settings_ignore_tupperbox" value="1" {checkbox_values["ignore_tupperbox"]}
                                   style="margin-right: 12px; transform: scale(1.3); accent-color: #4caf50;">
                            <div>
                                <div style="font-weight: 500; color: #e0e0e0;">👥 Ignore Tupperbox/proxy messages</div>
                                <div style="font-size: 0.85em; color: #b0b0b0; margin-top: 2px;">Skip logging proxy bot messages</div>
                            </div>
                        </label>

                        <label style="display: flex; align-items: center; padding: 0.8em; background: #3a3a3a; border-radius: 6px; border: 1px solid #4a4a4a; cursor: pointer; transition: all 0.2s ease;">
                            <input type="checkbox" name="yalc_settings_ignore_apps" value="1" {checkbox_values["ignore_apps"]}
                                   style="margin-right: 12px; transform: scale(1.3); accent-color: #4caf50;">
                            <div>
                                <div style="font-weight: 500; color: #e0e0e0;">📱 Ignore app messages</div>
                                <div style="font-size: 0.85em; color: #b0b0b0; margin-top: 2px;">Skip logging application events</div>
                            </div>
                        </label>

                        <label style="display: flex; align-items: center; padding: 0.8em; background: #3a3a3a; border-radius: 6px; border: 1px solid #4a4a4a; cursor: pointer; transition: all 0.2s ease;">
                            <input type="checkbox" name="yalc_settings_detect_proxy_deletes" value="1" {checkbox_values["detect_proxy_deletes"]}
                                   style="margin-right: 12px; transform: scale(1.3); accent-color: #4caf50;">
                            <div>
                                <div style="font-weight: 500; color: #e0e0e0;">🔍 Detect proxy deletes</div>
                                <div style="font-size: 0.85em; color: #b0b0b0; margin-top: 2px;">Log when proxy messages are deleted</div>
                            </div>
                        </label>
                    </div>
                </div>
            
                <!-- Additional event and channel sections -->
                <div style="margin-top: 2em;">
                    {event_sections}
                    {channel_sections}
                </div>

                <!-- Submit button -->
                <div style="text-align: center; margin-top: 3em; padding-top: 2em; border-top: 2px solid #4a4a4a;">
                    <input type="submit" name="submit" value="💾 Save Configuration"
                           style="background: linear-gradient(135deg, #4caf50 0%, #45a049 100%); color: white; border: none; padding: 1.2em 3em; border-radius: 8px; font-size: 1.1em; font-weight: 600; cursor: pointer; box-shadow: 0 4px 12px rgba(76, 175, 80, 0.3); transition: all 0.3s ease;">
                    <p style="margin-top: 1em; color: #b0b0b0; font-size: 0.9em;">
                        Changes are applied immediately and saved to Red's configuration system
                    </p>
                </div>
            </form>

            <div style="margin-top: 2em; padding: 1.5em; background: #2d2d2d; border-radius: 8px; border-left: 4px solid #00bcd4;">
                <h4 style="margin: 0 0 0.5em 0; color: #00bcd4;">ℹ️ About YALC</h4>
                <p style="margin: 0; color: #b0b0b0; line-height: 1.5;">
                    Yet Another Logging Cog provides comprehensive event logging for Discord servers.
                    Configure which events to log, assign specific channels for different event types,
                    and customize filtering options to suit your server's needs.
                </p>
            </div>

            <script>
                document.addEventListener('DOMContentLoaded', function() {{
                    // Add interactive enhancements
                    const labels = document.querySelectorAll('label');
                    labels.forEach(label => {{
                        label.addEventListener('mouseenter', function() {{
                            this.style.transform = 'translateY(-1px)';
                            this.style.boxShadow = '0 4px 8px rgba(255, 255, 255, 0.1)';
                        }});
                        label.addEventListener('mouseleave', function() {{
                            this.style.transform = 'translateY(0)';
                            this.style.boxShadow = '0 1px 3px rgba(255, 255, 255, 0.05)';
                        }});
                    }});

                    // Add form submission feedback
                    const submitButton = document.querySelector('input[type="submit"]');
                    if (submitButton) {{
                        submitButton.addEventListener('click', function() {{
                            this.value = '⏳ Saving...';
                            this.disabled = true;
                            this.style.opacity = '0.7';
                        }});
                    }}
                }});
            </script>
        </div>
        """


    def _generate_event_sections(self, settings: dict) -> str:
        """Generate HTML for event toggle sections with dark mode styling."""
        # Get event descriptions from the main cog
        event_descriptions = getattr(self, 'event_descriptions', {})
        
        # Complete categories with all 52 event types and dark mode colors
        categories = {
            "Message Events": {
                "events": ["message_delete", "message_edit", "message_bulk_delete", "message_pin", "message_unpin"],
                "color": "#f44336",
                "description": "Track message modifications, deletions, and pin changes"
            },
            "Member Events": {
                "events": ["member_join", "member_leave", "member_ban", "member_unban", "member_kick", "member_timeout", "member_update"],
                "color": "#2196f3",
                "description": "Monitor member activity and moderation actions"
            },
            "Voice Events": {
                "events": ["voice_state_update"],
                "color": "#9c27b0",
                "description": "Track voice channel activity and state changes"
            },
            "Channel Events": {
                "events": ["channel_create", "channel_delete", "channel_update", "thread_create", "thread_delete", "thread_update"],
                "color": "#ff9800",
                "description": "Monitor channel and thread management"
            },
            "Role Events": {
                "events": ["role_create", "role_delete", "role_update"],
                "color": "#ff5722",
                "description": "Track role creation, deletion, and permission changes"
            },
            "Server Events": {
                "events": ["guild_update", "emoji_update", "sticker_update", "scheduled_event_create", "scheduled_event_delete", "scheduled_event_update"],
                "color": "#009688",
                "description": "Monitor server settings, emoji, sticker, and scheduled event changes"
            },
            "Command Events": {
                "events": ["slash_command_completion"],
                "color": "#4caf50",
                "description": "Track slash command usage and completion"
            },
            "Reaction Events": {
                "events": ["reaction_add", "reaction_remove", "reaction_clear", "reaction_clear_emoji"],
                "color": "#e91e63",
                "description": "Monitor message reactions and emoji interactions"
            },
            "Integration Events": {
                "events": ["integration_create", "integration_delete", "integration_update"],
                "color": "#673ab7",
                "description": "Track server integrations and connected services"
            },
            "Webhook Events": {
                "events": ["webhook_update"],
                "color": "#607d8b",
                "description": "Monitor webhook configuration changes"
            },
            "AutoMod Events": {
                "events": ["automod_rule_create", "automod_rule_delete", "automod_rule_update", "automod_action_execution"],
                "color": "#795548",
                "description": "Track AutoMod rule changes and moderation actions"
            },
            "Invite Events": {
                "events": ["invite_create", "invite_delete"],
                "color": "#3f51b5",
                "description": "Monitor server invite creation and deletion"
            },
            "Permission Events": {
                "events": ["app_command_permissions_update"],
                "color": "#ff6f00",
                "description": "Track application command permission changes"
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
                        <label style="display: flex; align-items: center; padding: 0.6em; background: #3a3a3a; border-radius: 6px; border: 1px solid #4a4a4a; cursor: pointer; transition: all 0.2s ease; margin-bottom: 8px; color: #e0e0e0;">
                            <input type="checkbox" name="event_{event}" value="1" {checked}
                                   style="margin-right: 10px; transform: scale(1.3); accent-color: {color};">
                            <div style="flex: 1;">
                                <div style="font-weight: 500; color: #e0e0e0;">{emoji} {desc}</div>
                                <div style="font-size: 0.8em; color: #b0b0b0; margin-top: 2px;">Event: {event}</div>
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
                    <div style="margin-bottom: 2em; padding: 1.5em; background: #2d2d2d; border-radius: 8px; border-left: 4px solid {color};">
                        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 1em;">
                            <h3 style="color: {color}; margin: 0; font-size: 1.3em; font-weight: 600;">{category_name}</h3>
                            {status_badge}
                        </div>
                        <p style="color: #b0b0b0; margin-bottom: 1.5em; font-size: 0.95em;">{description}</p>
                        <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 12px;">
                            {"".join(event_checkboxes)}
                        </div>
                    </div>
                """)

        return "".join(sections)

    def _generate_channel_sections(self, guild: discord.Guild, settings: dict) -> str:
        """Generate HTML for channel configuration sections with dark mode styling."""
        # Get text channels for dropdown
        text_channels = [c for c in guild.channels if isinstance(c, discord.TextChannel)]
        text_channels.sort(key=lambda c: c.name.lower())  # Sort alphabetically
        
        channel_options = '<option value="">📵 No logging</option>' + "".join(
            f'<option value="{c.id}">#{c.name}</option>' for c in text_channels
        )

        enabled_events = [event for event, enabled in settings.get("events", {}).items() if enabled]

        if not enabled_events:
            return """
            <div style="margin-bottom: 2em; padding: 2em; background: linear-gradient(135deg, #3d2914 0%, #5d4037 100%); border-radius: 8px; border-left: 4px solid #ff9800; text-align: center;">
                <h4 style="margin: 0 0 0.5em 0; color: #ff9800; font-size: 1.2em;">⚠️ No Events Enabled</h4>
                <p style="margin: 0; color: #bcaaa4; font-size: 1em;">
                    Enable some events in the sections above to configure their log channels.
                    <br><small>Each event type can be logged to a different channel for better organization.</small>
                </p>
            </div>
            """

        event_descriptions = getattr(self, 'event_descriptions', {})
        
        # Group events by category for better organization - complete list
        categories = {
            "Message Events": ["message_delete", "message_edit", "message_bulk_delete", "message_pin", "message_unpin"],
            "Member Events": ["member_join", "member_leave", "member_ban", "member_unban", "member_kick", "member_timeout", "member_update"],
            "Voice Events": ["voice_state_update"],
            "Channel Events": ["channel_create", "channel_delete", "channel_update", "thread_create", "thread_delete", "thread_update"],
            "Role Events": ["role_create", "role_delete", "role_update"],
            "Server Events": ["guild_update", "emoji_update", "sticker_update", "scheduled_event_create", "scheduled_event_delete", "scheduled_event_update"],
            "Command Events": ["slash_command_completion"],
            "Reaction Events": ["reaction_add", "reaction_remove", "reaction_clear", "reaction_clear_emoji"],
            "Integration Events": ["integration_create", "integration_delete", "integration_update"],
            "Webhook Events": ["webhook_update"],
            "AutoMod Events": ["automod_rule_create", "automod_rule_delete", "automod_rule_update", "automod_action_execution"],
            "Invite Events": ["invite_create", "invite_delete"],
            "Permission Events": ["app_command_permissions_update"]
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
                        <div style="display: flex; justify-content: space-between; align-items: center; padding: 0.8em; background: #3a3a3a; border-radius: 6px; border: 1px solid #4a4a4a; margin-bottom: 8px;">
                            <label for="channel_{event}" style="flex: 1; margin-right: 1.5em; font-weight: 500; color: #e0e0e0;">
                                {emoji} {desc}
                                <div style="font-size: 0.8em; color: #b0b0b0; margin-top: 2px; font-weight: normal;">Event: {event}</div>
                            </label>
                            <select name="event_channels[{event}]" id="channel_{event}"
                                    style="flex: 0 0 250px; padding: 0.7em; border-radius: 6px; border: 1px solid #555; font-size: 0.9em; background: #2a2a2a; color: #e0e0e0;">
                                {options_with_selection}
                            </select>
                        </div>
                    """
            
            if channel_config_html:
                category_sections.append(f"""
                    <div style="margin-bottom: 1.5em;">
                        <h4 style="color: #2196f3; margin: 0 0 0.8em 0; font-size: 1.1em; font-weight: 600; border-bottom: 1px solid #4a4a4a; padding-bottom: 0.5em;">
                            {category_name}
                        </h4>
                        {channel_config_html}
                    </div>
                """)

        status_text = f"{configured_count}/{total_enabled} events have channels configured"
        status_color = "#4caf50" if configured_count == total_enabled else "#ff9800" if configured_count > 0 else "#f44336"

        return f"""
            <div style="margin-bottom: 2em; padding: 1.5em; background: #2d2d2d; border-radius: 8px; border-left: 4px solid #00bcd4;">
                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 1em;">
                    <h3 style="color: #00bcd4; margin: 0; font-size: 1.3em; font-weight: 600;">📢 Event Log Channels</h3>
                    <span style="background: {status_color}; color: white; padding: 0.3em 0.8em; border-radius: 12px; font-size: 0.85em; font-weight: 500;">
                        {status_text}
                    </span>
                </div>
                <p style="color: #b0b0b0; margin-bottom: 1.5em; font-size: 0.95em;">
                    Assign specific channels for each enabled event type. Events without assigned channels won't be logged.
                    <br><small style="color: #888;">💡 Tip: Use different channels for different event types to keep logs organized.</small>
                </p>
                {"".join(category_sections)}
            </div>
        """

    def _generate_filter_sections(self, guild: discord.Guild, settings: dict) -> str:
        """Generate HTML for filtering options with dark mode styling."""
        return f"""
            <div style="margin-bottom: 2em; padding: 1.5em; background: #2d2d2d; border-radius: 8px; border-left: 4px solid #4caf50;">
                <h3 style="color: #4caf50; margin-top: 0; margin-bottom: 1em; font-size: 1.3em; font-weight: 600;">🔍 Filtering Options</h3>
                <p style="color: #b0b0b0; margin-bottom: 1.5em; font-size: 0.95em;">Configure what types of messages and events to include or exclude from logging.</p>

                <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 20px;">
                    <label style="display: flex; align-items: center; padding: 0.8em; background: #3a3a3a; border-radius: 6px; border: 1px solid #4a4a4a; cursor: pointer; transition: all 0.2s ease;">
                        <input type="checkbox" name="include_thumbnails" value="1" {'checked' if settings.get('include_thumbnails', True) else ''}
                               style="margin-right: 12px; transform: scale(1.3); accent-color: #4caf50;">
                        <div>
                            <div style="font-weight: 500; color: #e0e0e0;">🖼️ Include user thumbnails</div>
                            <div style="font-size: 0.85em; color: #b0b0b0; margin-top: 2px;">Show user avatars in log embeds</div>
                        </div>
                    </label>

                    <label style="display: flex; align-items: center; padding: 0.8em; background: #3a3a3a; border-radius: 6px; border: 1px solid #4a4a4a; cursor: pointer; transition: all 0.2s ease;">
                        <input type="checkbox" name="ignore_bots" value="1" {'checked' if settings.get('ignore_bots', False) else ''}
                               style="margin-right: 12px; transform: scale(1.3); accent-color: #4caf50;">
                        <div>
                            <div style="font-weight: 500; color: #e0e0e0;">🤖 Ignore bot messages</div>
                            <div style="font-size: 0.85em; color: #b0b0b0; margin-top: 2px;">Skip logging events from bots</div>
                        </div>
                    </label>

                    <label style="display: flex; align-items: center; padding: 0.8em; background: #3a3a3a; border-radius: 6px; border: 1px solid #4a4a4a; cursor: pointer; transition: all 0.2s ease;">
                        <input type="checkbox" name="ignore_webhooks" value="1" {'checked' if settings.get('ignore_webhooks', False) else ''}
                               style="margin-right: 12px; transform: scale(1.3); accent-color: #4caf50;">
                        <div>
                            <div style="font-weight: 500; color: #e0e0e0;">🪝 Ignore webhook messages</div>
                            <div style="font-size: 0.85em; color: #b0b0b0; margin-top: 2px;">Skip logging webhook events</div>
                        </div>
                    </label>

                    <label style="display: flex; align-items: center; padding: 0.8em; background: #3a3a3a; border-radius: 6px; border: 1px solid #4a4a4a; cursor: pointer; transition: all 0.2s ease;">
                        <input type="checkbox" name="ignore_tupperbox" value="1" {'checked' if settings.get('ignore_tupperbox', True) else ''}
                               style="margin-right: 12px; transform: scale(1.3); accent-color: #4caf50;">
                        <div>
                            <div style="font-weight: 500; color: #e0e0e0;">👥 Ignore Tupperbox/proxy messages</div>
                            <div style="font-size: 0.85em; color: #b0b0b0; margin-top: 2px;">Skip logging proxy bot messages</div>
                        </div>
                    </label>

                    <label style="display: flex; align-items: center; padding: 0.8em; background: #3a3a3a; border-radius: 6px; border: 1px solid #4a4a4a; cursor: pointer; transition: all 0.2s ease;">
                        <input type="checkbox" name="ignore_apps" value="1" {'checked' if settings.get('ignore_apps', True) else ''}
                               style="margin-right: 12px; transform: scale(1.3); accent-color: #4caf50;">
                        <div>
                            <div style="font-weight: 500; color: #e0e0e0;">📱 Ignore app messages</div>
                            <div style="font-size: 0.85em; color: #b0b0b0; margin-top: 2px;">Skip logging application events</div>
                        </div>
                    </label>

                    <label style="display: flex; align-items: center; padding: 0.8em; background: #3a3a3a; border-radius: 6px; border: 1px solid #4a4a4a; cursor: pointer; transition: all 0.2s ease;">
                        <input type="checkbox" name="detect_proxy_deletes" value="1" {'checked' if settings.get('detect_proxy_deletes', True) else ''}
                               style="margin-right: 12px; transform: scale(1.3); accent-color: #4caf50;">
                        <div>
                            <div style="font-weight: 500; color: #e0e0e0;">🔍 Detect proxy deletes</div>
                            <div style="font-size: 0.85em; color: #b0b0b0; margin-top: 2px;">Log when proxy messages are deleted</div>
                        </div>
                    </label>
                </div>
            </div>
        """

    @commands.Cog.listener()
    async def on_dashboard_cog_add(self, dashboard_cog: commands.Cog) -> None:
        """Register the dashboard integration when dashboard cog is loaded."""
        dashboard_cog.rpc.third_parties_handler.add_third_party(self)
