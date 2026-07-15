import html
import typing

import discord
from redbot.core import commands

RECOVERABLE_EXCEPTIONS = (
    discord.DiscordException,
    OSError,
    RuntimeError,
    ValueError,
    KeyError,
    TypeError,
    AttributeError,
)


# Dashboard integration decorator - compatible with Red-Web-Dashboard
def dashboard_page(*args, **kwargs):
    """Dashboard page decorator that stores parameters for later registration."""

    def decorator(func: typing.Callable):
        func.__dashboard_decorator_params__ = (args, kwargs)
        return func

    return decorator


class DashboardIntegration:
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
    ) -> dict[str, typing.Any]:
        """Format settings for the dashboard."""
        try:
            config = await self.config.guild(guild).all()

            # Format the settings data for display
            return {
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

        except RECOVERABLE_EXCEPTIONS:
            return {}

    async def update_settings(
        self,
        guild: discord.Guild,
        new_settings: dict[str, typing.Any],
        **kwargs,
    ) -> None:
        """Update settings from the dashboard."""
        try:
            # Update basic filter settings
            if "include_thumbnails" in new_settings:
                await self.config.guild(guild).include_thumbnails.set(
                    new_settings["include_thumbnails"],
                )
            if "ignore_bots" in new_settings:
                await self.config.guild(guild).ignore_bots.set(
                    new_settings["ignore_bots"],
                )
            if "ignore_webhooks" in new_settings:
                await self.config.guild(guild).ignore_webhooks.set(
                    new_settings["ignore_webhooks"],
                )
            if "ignore_tupperbox" in new_settings:
                await self.config.guild(guild).ignore_tupperbox.set(
                    new_settings["ignore_tupperbox"],
                )
            if "ignore_apps" in new_settings:
                await self.config.guild(guild).ignore_apps.set(
                    new_settings["ignore_apps"],
                )
            if "detect_proxy_deletes" in new_settings:
                await self.config.guild(guild).detect_proxy_deletes.set(
                    new_settings["detect_proxy_deletes"],
                )

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
                await self.config.guild(guild).ignored_users.set(
                    new_settings["ignored_users"],
                )
            if "ignored_roles" in new_settings:
                await self.config.guild(guild).ignored_roles.set(
                    new_settings["ignored_roles"],
                )
            if "ignored_channels" in new_settings:
                await self.config.guild(guild).ignored_channels.set(
                    new_settings["ignored_channels"],
                )
            if "ignored_categories" in new_settings:
                await self.config.guild(guild).ignored_categories.set(
                    new_settings["ignored_categories"],
                )

            # Update additional settings
            if "tupperbox_ids" in new_settings:
                await self.config.guild(guild).tupperbox_ids.set(
                    new_settings["tupperbox_ids"],
                )
            if "message_prefix_filter" in new_settings:
                await self.config.guild(guild).message_prefix_filter.set(
                    new_settings["message_prefix_filter"],
                )
            if "webhook_name_filter" in new_settings:
                await self.config.guild(guild).webhook_name_filter.set(
                    new_settings["webhook_name_filter"],
                )
            if hasattr(self, "_invalidate_settings_cache"):
                self._invalidate_settings_cache(guild)

        except RECOVERABLE_EXCEPTIONS as e:
            # Use bot logger if available, otherwise just pass
            if hasattr(self, "log") and self.log:
                self.log.error(f"Error updating YALC settings: {e}")

    @dashboard_page(
        name=None,
        description="Configure YALC logging settings.",
        methods=("GET", "POST"),
    )
    async def dashboard_page(
        self,
        user: discord.User,
        guild: discord.Guild,
        **kwargs,
    ) -> dict[str, typing.Any]:
        """Main dashboard page for YALC."""
        try:
            # Check if we have access to the required attributes
            if not hasattr(self, "config") or not self.config:
                return {
                    "status": 1,
                    "error_title": "Configuration Error",
                    "error_message": "Dashboard integration is not properly initialized. Please reload the cog.",
                }

            # Check permissions
            member = guild.get_member(user.id)
            is_owner = user.id in getattr(self.bot, "owner_ids", set())
            is_admin = member is not None and await self.bot.is_admin(member)
            can_manage = (
                is_owner
                or is_admin
                or (member is not None and member.guild_permissions.manage_guild)
            )
            if not can_manage:
                return {
                    "status": 1,
                    "error_title": "Insufficient Permissions",
                    "error_message": "You need `Manage Server` permission to view this page.",
                }

            # Get current settings
            settings = await self.config.guild(guild).all()

            # Add comprehensive logging for debugging
            if hasattr(self, "log") and self.log:
                self.log.info(
                    f"YALC Dashboard accessed by {user.name} ({user.id}) for guild {guild.name} ({guild.id})",
                )

            # Handle form submission with proper CSRF validation
            method = kwargs.get("method", "GET")

            # Enhanced diagnostic logging
            if hasattr(self, "log") and self.log:
                self.log.debug(
                    f"YALC Dashboard: method={method}, kwargs keys: {list(kwargs.keys())}",
                )
                if "guild" in kwargs:
                    self.log.warning(
                        "YALC Dashboard: 'guild' found in kwargs, this may cause duplicate parameter error",
                    )

            if method == "POST":
                return await self._handle_wtforms_submission(
                    guild,
                    user,
                    settings,
                    **kwargs,
                )

            # Remove 'guild' from kwargs to prevent duplicate parameter error
            clean_kwargs = {k: v for k, v in kwargs.items() if k != "guild"}

            # Generate the dashboard using WTForms approach
            return await self._generate_wtforms_dashboard(
                guild,
                settings,
                **clean_kwargs,
            )

        except RECOVERABLE_EXCEPTIONS as e:
            # Enhanced error logging
            if hasattr(self, "log") and self.log:
                self.log.error(
                    f"Error in YALC dashboard page: {e}", exc_info=True)

            return {
                "status": 1,
                "error_title": "Dashboard Error",
                "error_message": f"An error occurred while loading the dashboard: {str(e)}",
            }

    async def _handle_wtforms_submission(
        self,
        guild: discord.Guild,
        user: discord.User,
        settings: dict,
        **kwargs,
    ) -> dict[str, typing.Any]:
        """Handle POST form submissions with CSRF validation and proper error handling."""
        try:
            data = kwargs.get("data") or {}
            if isinstance(data, dict) and ("form" in data or "json" in data):
                form_data = data.get("form") or data.get("json") or {}
            elif isinstance(data, dict):
                form_data = data
            else:
                form_data = data

            # Enhanced logging for debugging
            if hasattr(self, "log") and self.log:
                self.log.info(
                    f"YALC form submission from {user.name} ({user.id}) for guild {guild.name}",
                )
                self.log.debug(
                    f"Form data keys: {list(form_data.keys()) if hasattr(form_data, 'keys') else []}",
                )

            # Check for CSRF token (Red-Web-Dashboard should handle this automatically)
            if not form_data:
                if hasattr(self, "log") and self.log:
                    self.log.warning(
                        f"YALC: Empty form data received from {user.name}")
                return {
                    "status": 1,
                    "error_title": "Form Error",
                    "error_message": "No form data received. This might be a CSRF token issue.",
                    "notifications": [
                        {
                            "message": "❌ Form submission failed: No data received",
                            "category": "error",
                        },
                    ],
                }

            # Process the form submission
            try:
                new_settings = await self._process_form_data(form_data, settings)

                # Enhanced logging of what we're saving
                if hasattr(self, "log") and self.log:
                    self.log.info(
                        f"YALC: Updating settings for {guild.name}: {new_settings}",
                    )

                # Update settings with error handling
                await self.update_settings(guild, new_settings)

                # Log successful save
                if hasattr(self, "log") and self.log:
                    self.log.info(
                        f"YALC: Settings successfully updated for {guild.name}",
                    )

                return {
                    "status": 0,
                    "notifications": [
                        {
                            "message": "✅ YALC settings updated successfully!",
                            "category": "success",
                        },
                    ],
                    "redirect_url": kwargs.get("request_url", ""),
                }

            except RECOVERABLE_EXCEPTIONS as settings_error:
                # Log settings update error
                if hasattr(self, "log") and self.log:
                    self.log.error(
                        f"YALC: Error updating settings for {guild.name}: {settings_error}",
                        exc_info=True,
                    )

                return {
                    "status": 1,
                    "error_title": "Settings Update Error",
                    "error_message": f"Failed to save settings: {str(settings_error)}",
                    "notifications": [
                        {
                            "message": f"❌ Error saving settings: {str(settings_error)}",
                            "category": "error",
                        },
                    ],
                }

        except RECOVERABLE_EXCEPTIONS as e:
            # Log submission handling error
            if hasattr(self, "log") and self.log:
                self.log.error(
                    f"YALC: Error handling form submission: {e}",
                    exc_info=True,
                )

            return {
                "status": 1,
                "error_title": "Form Processing Error",
                "error_message": f"Error processing form submission: {str(e)}",
                "notifications": [
                    {
                        "message": f"❌ Form processing failed: {str(e)}",
                        "category": "error",
                    },
                ],
            }

    def _get_form_value(
        self,
        form_data: typing.Any,
        key: str,
        default: typing.Any = None,
    ) -> typing.Any:
        """Return a submitted form value from dict-like or MultiDict-like data."""
        if hasattr(form_data, "get"):
            value = form_data.get(key, default)
        else:
            return default
        if isinstance(value, (list, tuple)):
            return value[0] if value else default
        return value

    def _manual_csrf_hidden(self, kwargs: dict) -> str:
        """Build a CSRF field for the fallback form when Dashboard's Form helper is unavailable."""
        csrf_token = kwargs.get("csrf_token")
        if not isinstance(csrf_token, (tuple, list)) or len(csrf_token) != 2:
            return ""
        return (
            '<input type="hidden" name="csrf_token" value="'
            f'{html.escape(str(csrf_token[1]), quote=True)}">'
        )

    async def _process_form_data(
        self,
        form_data: typing.Any,
        current_settings: dict,
    ) -> dict:
        """Process form data into settings format with validation."""
        new_settings = {}
        event_descriptions = getattr(self, "event_descriptions", {})

        # Process basic filter settings (checkboxes only appear if checked)
        checkbox_settings = [
            "include_thumbnails",
            "ignore_bots",
            "ignore_webhooks",
            "ignore_tupperbox",
            "ignore_apps",
            "detect_proxy_deletes",
        ]

        for setting in checkbox_settings:
            # Check both prefixed and non-prefixed versions for compatibility
            new_settings[setting] = (
                setting in form_data or f"yalc_settings_{setting}" in form_data
            )

        # Process event toggles
        events = {
            event: f"event_{event}" in form_data for event in event_descriptions}
        new_settings["events"] = events

        # Process channel configurations
        existing_channels = current_settings.get("event_channels", {})
        event_channels = {
            event: existing_channels.get(event) for event in event_descriptions
        }
        for event in event_descriptions:
            value = self._get_form_value(form_data, f"event_channels[{event}]")
            if value is None:
                continue
            try:
                event_channels[event] = int(
                    value) if str(value).strip() else None
            except (TypeError, ValueError):
                event_channels[event] = None
        new_settings["event_channels"] = event_channels

        return new_settings

    async def _generate_wtforms_dashboard(
        self,
        guild: discord.Guild,
        settings: dict,
        **kwargs,
    ) -> dict[str, typing.Any]:
        """Generate dashboard using WTForms approach with proper CSRF handling."""
        try:
            # Enhanced diagnostic logging for form debugging
            if hasattr(self, "log") and self.log:
                self.log.debug(
                    f"YALC WTForms Debug: kwargs keys: {list(kwargs.keys())}",
                )
                self.log.debug(
                    f"YALC WTForms Debug: Form type: {type(kwargs.get('Form'))}",
                )
                self.log.debug(
                    f"YALC WTForms Debug: Form value: {kwargs.get('Form')}")

            # Check if WTForms is available in kwargs (passed by Red-Web-Dashboard)
            form_class = kwargs.get("Form")
            if not form_class:
                # Fallback to manual form with warning about CSRF
                if hasattr(self, "log") and self.log:
                    self.log.warning(
                        "YALC: WTForms not available, falling back to manual form",
                    )
                return await self._generate_fallback_dashboard(
                    guild,
                    settings,
                    **kwargs,
                )

            # Create WTForms class with CSRF protection
            import wtforms

            class YALCSettingsForm(form_class):
                def __init__(self, *args, **kwargs):
                    super().__init__(prefix="yalc_settings_", *args, **kwargs)

                # Filter settings
                include_thumbnails = wtforms.BooleanField(
                    "Include user thumbnails",
                    default=settings.get("include_thumbnails", True),
                    description="Show user avatars in log embeds",
                )
                ignore_bots = wtforms.BooleanField(
                    "Ignore bot messages",
                    default=settings.get("ignore_bots", False),
                    description="Skip logging events from bots",
                )
                ignore_webhooks = wtforms.BooleanField(
                    "Ignore webhook messages",
                    default=settings.get("ignore_webhooks", False),
                    description="Skip logging webhook events",
                )
                ignore_tupperbox = wtforms.BooleanField(
                    "Ignore Tupperbox/proxy messages",
                    default=settings.get("ignore_tupperbox", True),
                    description="Skip logging proxy bot messages",
                )
                ignore_apps = wtforms.BooleanField(
                    "Ignore app messages",
                    default=settings.get("ignore_apps", True),
                    description="Skip logging application events",
                )
                detect_proxy_deletes = wtforms.BooleanField(
                    "Detect proxy deletes",
                    default=settings.get("detect_proxy_deletes", True),
                    description="Log when proxy messages are deleted",
                )

                submit = wtforms.SubmitField("💾 Save Configuration")

            # Create form instance with enhanced debugging
            form = YALCSettingsForm()

            # Enhanced form debugging
            if hasattr(self, "log") and self.log:
                self.log.debug(f"YALC: Created form instance: {type(form)}")
                self.log.debug(f"YALC: form_class instance details: {form}")
                self.log.debug(
                    f"YALC: form_class has include_thumbnails field: {hasattr(form, 'yalc_settings_include_thumbnails')}",
                )
                if hasattr(form, "yalc_settings_include_thumbnails"):
                    self.log.debug(
                        f"YALC: include_thumbnails field type: {type(form.yalc_settings_include_thumbnails)}",
                    )

            # Generate additional sections for events and channels
            event_sections = self._generate_event_sections(settings)
            channel_sections = self._generate_channel_sections(guild, settings)
            csrf_hidden = str(form.hidden_tag()) if hasattr(
                form, "hidden_tag") else ""

            # Generate the HTML template
            html_template = await self._generate_wtforms_html(
                guild,
                settings,
                event_sections,
                channel_sections,
                csrf_hidden,
            )

            # Enhanced logging for template and form
            if hasattr(self, "log") and self.log:
                self.log.debug(
                    f"YALC: HTML template length: {len(html_template)}")
                self.log.debug(
                    f"YALC: About to return form type: {type(form)}")

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
            if hasattr(self, "log") and self.log:
                self.log.debug(
                    f"YALC: Final result web_content keys: {list(result['web_content'].keys())}",
                )
                self.log.debug(
                    "YALC: Template-based approach - no form object passed")

            return result

        except RECOVERABLE_EXCEPTIONS as e:
            if hasattr(self, "log") and self.log:
                self.log.error(
                    f"YALC: Error generating WTForms dashboard: {e}",
                    exc_info=True,
                )

            # Fallback to basic dashboard
            return await self._generate_fallback_dashboard(guild, settings, **kwargs)

    async def _generate_fallback_dashboard(
        self,
        guild: discord.Guild,
        settings: dict,
        **kwargs,
    ) -> dict[str, typing.Any]:
        """Generate fallback dashboard when WTForms is not available."""
        try:
            # Generate sections
            event_sections = self._generate_event_sections(settings)
            channel_sections = self._generate_channel_sections(guild, settings)
            csrf_hidden = self._manual_csrf_hidden(kwargs)

            # Warning message about CSRF
            csrf_warning = """
                <div style="margin-bottom: 2em; padding: 1.5em; background: #2d1f2d; border-radius: 8px; border-left:
                4px solid #ff5722;">
                    <h4 style="margin: 0 0 0.5em 0; color: #ff5722;">⚠️ CSRF Protection Warning</h4>
                    <p style="margin: 0; color: #ffab91; line-height: 1.5;">
                        WTForms is not available - using fallback form without full CSRF protection.
                        If settings don't save properly, please ensure Red-Web-Dashboard is properly configured.
                    </p>
                </div>
            """

            # Create checkbox values
            guild_name = html.escape(guild.name)
            checkbox_values = {
                "include_thumbnails": "checked"
                if settings.get("include_thumbnails", True)
                else "",
                "ignore_bots": "checked" if settings.get("ignore_bots", False) else "",
                "ignore_webhooks": "checked"
                if settings.get("ignore_webhooks", False)
                else "",
                "ignore_tupperbox": "checked"
                if settings.get("ignore_tupperbox", True)
                else "",
                "ignore_apps": "checked" if settings.get("ignore_apps", True) else "",
                "detect_proxy_deletes": "checked"
                if settings.get("detect_proxy_deletes", True)
                else "",
            }

            source = f"""
            <div data-yalc-tabs="1" class="yalc-shell">
                <header class="yalc-hero">
                    <h1>YALC logging</h1>
                    <p>Choose what gets logged and where for <strong>{guild_name}</strong>.</p>
                </header>

                {csrf_warning}
                {self._yalc_tabs_header()}

                <form method="POST" style="width: 100%;">
                    {csrf_hidden}
                    <!-- Filter Settings Section -->
                    <section class="yalc-tab-panel active" data-yalc-panel="filters">
                    <div style="margin-bottom: 2em; padding: 1.5em; background: #2d2d2d; border-radius: 8px;
                    border-left: 4px solid #4caf50;">
                        <h3 style="color: #4caf50; margin-top: 0; margin-bottom: 1em; font-size: 1.3em; font-weight:
                        600;">🔍 Filtering Options</h3>
                        <p style="color: #b0b0b0; margin-bottom: 1.5em; font-size: 0.95em;">Configure what types of
                        messages and events to include or exclude from logging.</p>

                        <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap:
                        20px;">
                            <label style="display: flex; align-items: center; padding: 0.8em; background: #3a3a3a;
                            border-radius: 6px; border: 1px solid #4a4a4a; cursor: pointer; transition: all 0.2s ease;">
                                <input type="checkbox" name="include_thumbnails" value="1"
                                {checkbox_values["include_thumbnails"]}
                                       style="margin-right: 12px; transform: scale(1.3); accent-color: #4caf50;">
                                <div>
                                    <div style="font-weight: 500; color: #e0e0e0;">🖼️ Include user thumbnails</div>
                                    <div style="font-size: 0.85em; color: #b0b0b0; margin-top: 2px;">Show user avatars
                                    in log embeds</div>
                                </div>
                            </label>

                            <label style="display: flex; align-items: center; padding: 0.8em; background: #3a3a3a;
                            border-radius: 6px; border: 1px solid #4a4a4a; cursor: pointer; transition: all 0.2s ease;">
                                <input type="checkbox" name="ignore_bots" value="1" {checkbox_values["ignore_bots"]}
                                       style="margin-right: 12px; transform: scale(1.3); accent-color: #4caf50;">
                                <div>
                                    <div style="font-weight: 500; color: #e0e0e0;">🤖 Ignore bot messages</div>
                                    <div style="font-size: 0.85em; color: #b0b0b0; margin-top: 2px;">Skip logging events
                                     from bots</div>
                                </div>
                            </label>

                            <label style="display: flex; align-items: center; padding: 0.8em; background: #3a3a3a;
                            border-radius: 6px; border: 1px solid #4a4a4a; cursor: pointer; transition: all 0.2s ease;">
                                <input type="checkbox" name="ignore_webhooks" value="1"
                                {checkbox_values["ignore_webhooks"]}
                                       style="margin-right: 12px; transform: scale(1.3); accent-color: #4caf50;">
                                <div>
                                    <div style="font-weight: 500; color: #e0e0e0;">🪝 Ignore webhook messages</div>
                                    <div style="font-size: 0.85em; color: #b0b0b0; margin-top: 2px;">Skip logging
                                    webhook events</div>
                                </div>
                            </label>

                            <label style="display: flex; align-items: center; padding: 0.8em; background: #3a3a3a;
                            border-radius: 6px; border: 1px solid #4a4a4a; cursor: pointer; transition: all 0.2s ease;">
                                <input type="checkbox" name="ignore_tupperbox" value="1"
                                {checkbox_values["ignore_tupperbox"]}
                                       style="margin-right: 12px; transform: scale(1.3); accent-color: #4caf50;">
                                <div>
                                    <div style="font-weight: 500; color: #e0e0e0;">👥 Ignore Tupperbox/proxy
                                    messages</div>
                                    <div style="font-size: 0.85em; color: #b0b0b0; margin-top: 2px;">Skip logging proxy
                                    bot messages</div>
                                </div>
                            </label>

                            <label style="display: flex; align-items: center; padding: 0.8em; background: #3a3a3a;
                            border-radius: 6px; border: 1px solid #4a4a4a; cursor: pointer; transition: all 0.2s ease;">
                                <input type="checkbox" name="ignore_apps" value="1" {checkbox_values["ignore_apps"]}
                                       style="margin-right: 12px; transform: scale(1.3); accent-color: #4caf50;">
                                <div>
                                    <div style="font-weight: 500; color: #e0e0e0;">📱 Ignore app messages</div>
                                    <div style="font-size: 0.85em; color: #b0b0b0; margin-top: 2px;">Skip logging
                                    application events</div>
                                </div>
                            </label>

                            <label style="display: flex; align-items: center; padding: 0.8em; background: #3a3a3a;
                            border-radius: 6px; border: 1px solid #4a4a4a; cursor: pointer; transition: all 0.2s ease;">
                                <input type="checkbox" name="detect_proxy_deletes" value="1"
                                {checkbox_values["detect_proxy_deletes"]}
                                       style="margin-right: 12px; transform: scale(1.3); accent-color: #4caf50;">
                                <div>
                                    <div style="font-weight: 500; color: #e0e0e0;">🔍 Detect proxy deletes</div>
                                    <div style="font-size: 0.85em; color: #b0b0b0; margin-top: 2px;">Log when proxy
                                    messages are deleted</div>
                                </div>
                            </label>
                        </div>
                    </div>
                    </section>

                    <!-- Additional event and channel sections -->
                    <section class="yalc-tab-panel" data-yalc-panel="events" style="margin-top: 2em;">
                        {event_sections}
                    </section>
                    <section class="yalc-tab-panel" data-yalc-panel="channels" style="margin-top: 2em;">
                        {channel_sections}
                    </section>

                    <!-- Submit button -->
                    <div class="yalc-save">
                        <p class="yalc-note">Changes take effect as soon as they are saved.</p>
                        <input type="submit" name="submit" value="Save configuration" class="yalc-submit">
                    </div>
                </form>

                <div class="yalc-about">
                    <strong>About YALC</strong>
                    Configure event logging, destination channels, and message filters for this server.
                </div>

                <script>
                    document.addEventListener('DOMContentLoaded', function() {{
                        // Add form submission feedback without disabling native submission.
                        const submitButton = document.querySelector('input[type="submit"]');
                        if (submitButton) {{
                            const form = submitButton.closest('form');
                            if (form) {{
                                form.addEventListener('submit', function() {{
                                    submitButton.value = 'Saving...';
                                    submitButton.style.opacity = '0.7';
                                    submitButton.style.pointerEvents = 'none';
                                }});
                            }}
                        }}
                    }});
                </script>
                {self._yalc_tabs_script()}
            </div>
            """

            return {
                "status": 0,
                "web_content": {
                    "source": source,
                    "expanded": True,
                },
            }

        except RECOVERABLE_EXCEPTIONS as e:
            if hasattr(self, "log") and self.log:
                self.log.error(
                    f"YALC: Error generating fallback dashboard: {e}",
                    exc_info=True,
                )

            return {
                "status": 1,
                "error_title": "Dashboard Generation Error",
                "error_message": f"Failed to generate dashboard: {str(e)}",
            }

    @staticmethod
    def _yalc_tabs_header() -> str:
        return """
        <style>
            .yalc-shell, .yalc-shell * { box-sizing: border-box; }
            .yalc-shell { width: 100%; max-width: 1120px; margin: 0 auto; padding: 20px; color: #e5e7eb;
            font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; }
            .yalc-hero { margin-bottom: 20px; padding: 4px 2px 18px; border-bottom: 1px solid #374151; }
            .yalc-hero h1 { margin: 0; color: #f9fafb; font-size: clamp(1.55rem, 4vw, 2rem); line-height: 1.2;
            letter-spacing: -0.025em; }
            .yalc-hero p { margin: 7px 0 0; color: #9ca3af; }
            .yalc-tabs { display: flex; gap: 6px; overflow-x: auto; position: sticky; top: 0; z-index: 10; margin: 0 0
            20px; padding: 5px; background: #171b22; border: 1px solid #374151; border-radius: 8px; }
            .yalc-tab { flex: 0 0 auto; border: 0; border-radius: 5px; padding: 9px 13px; background: transparent;
            color: #9ca3af; cursor: pointer; font-weight: 650; white-space: nowrap; }
            .yalc-tab:hover { background: #252b35; color: #f9fafb; }
            .yalc-tab.active { background: #374151; color: #fff; }
            .yalc-tab-panel { display: none; }
            .yalc-tab-panel.active { display: block; }
            .yalc-section { margin-bottom: 16px; padding: 18px; background: #20252d; border: 1px solid #374151;
            border-radius: 8px; }
            .yalc-section-head { display: flex; flex-wrap: wrap; align-items: center; justify-content: space-between;
            gap: 10px 16px; margin-bottom: 4px; }
            .yalc-section h3, .yalc-section h4 { margin: 0; color: #f3f4f6; font-size: 1rem; }
            .yalc-section-copy { margin: 6px 0 16px; color: #9ca3af; font-size: .9rem; line-height: 1.5; }
            .yalc-event-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(min(260px, 100%), 1fr));
            gap: 8px; }
            .yalc-event { display: flex; align-items: center; gap: 10px; min-width: 0; padding: 11px 12px;
            background: #191e25; border: 1px solid #303743; border-radius: 6px; cursor: pointer; }
            .yalc-event:hover { border-color: #4b5563; background: #1d232b; }
            .yalc-event input { flex: 0 0 auto; width: 16px; height: 16px; margin: 0; accent-color: #60a5fa; }
            .yalc-event-name { color: #e5e7eb; font-weight: 550; }
            .yalc-event-key { margin-top: 2px; color: #7f8998; font: .75rem ui-monospace, SFMono-Regular, Menlo,
            monospace; overflow-wrap: anywhere; }
            .yalc-count { flex: 0 0 auto; color: #9ca3af; font-size: .8rem; font-weight: 650; }
            .yalc-button { border: 1px solid #4b5563; border-radius: 5px; padding: 7px 10px; background: #252b35;
            color: #e5e7eb; font: inherit; font-size: .82rem; font-weight: 650; cursor: pointer; }
            .yalc-button:hover { background: #303743; border-color: #6b7280; }
            .yalc-event-toolbar { display: flex; flex-wrap: wrap; justify-content: space-between; align-items: center;
            gap: 12px; margin-bottom: 12px; }
            .yalc-channel-group + .yalc-channel-group { margin-top: 22px; }
            .yalc-channel-group h4 { margin: 0 0 8px; padding-bottom: 8px; border-bottom: 1px solid #374151; }
            .yalc-channel-row { display: grid; grid-template-columns: minmax(0, 1fr) minmax(190px, 280px);
            align-items: center; gap: 12px 20px; padding: 10px 0; border-bottom: 1px solid #303743; }
            .yalc-channel-row:last-child { border-bottom: 0; }
            .yalc-channel-label { min-width: 0; color: #e5e7eb; font-weight: 550; }
            .yalc-channel-select { display: block; width: 100%; min-width: 0; max-width: 100%; height: 40px;
            padding: 7px 34px 7px 10px; border: 1px solid #4b5563; border-radius: 6px; background: #111827;
            color: #f3f4f6; font: inherit; font-size: .9rem; white-space: nowrap; }
            .yalc-channel-select option { white-space: normal; }
            .yalc-disabled { display: inline-block; margin-left: 6px; padding: 2px 6px; border-radius: 999px;
            background: #374151; color: #cbd5e1; font-size: .7rem; font-weight: 650; }
            [data-yalc-panel="filters"] > div { margin-bottom: 16px !important; padding: 18px !important;
            background: #20252d !important; border: 1px solid #374151 !important; border-radius: 8px !important; }
            [data-yalc-panel="filters"] > div > h3 { margin: 0 0 6px !important; color: #f3f4f6 !important;
            font-size: 1rem !important; }
            [data-yalc-panel="filters"] > div > p { margin: 0 0 16px !important; color: #9ca3af !important; }
            [data-yalc-panel="filters"] > div > div { grid-template-columns:
            repeat(auto-fit, minmax(min(240px, 100%), 1fr)) !important; gap: 8px !important; }
            [data-yalc-panel="filters"] label { padding: 11px 12px !important; background: #191e25 !important;
            border-color: #303743 !important; border-radius: 6px !important; box-shadow: none !important; }
            .yalc-save { display: flex; flex-wrap: wrap; align-items: center; justify-content: space-between; gap: 12px;
            margin-top: 20px; padding-top: 18px; border-top: 1px solid #374151; }
            .yalc-submit { border: 0; border-radius: 6px; padding: 10px 16px; background: #2563eb; color: #fff;
            font: inherit; font-weight: 700; cursor: pointer; }
            .yalc-submit:hover { background: #1d4ed8; }
            .yalc-note { margin: 0; color: #9ca3af; font-size: .82rem; }
            .yalc-about { margin-top: 20px; padding: 14px 16px; color: #9ca3af; background: #191e25;
            border: 1px solid #303743; border-radius: 7px; font-size: .88rem; line-height: 1.5; }
            .yalc-about strong { display: block; margin-bottom: 3px; color: #d1d5db; }
            @media (max-width: 620px) {
                .yalc-shell { padding: 12px; }
                .yalc-section { padding: 14px; }
                .yalc-channel-row { grid-template-columns: minmax(0, 1fr); gap: 7px; }
                .yalc-channel-select { width: 100%; }
            }
        </style>
        <div class="yalc-tabs" role="tablist" aria-label="YALC sections">
            <button type="button" class="yalc-tab active" data-yalc-tab="filters" role="tab" aria-selected="true"
            tabindex="0">Filtering</button>
            <button type="button" class="yalc-tab" data-yalc-tab="events" role="tab" aria-selected="false"
            tabindex="-1">Events</button>
            <button type="button" class="yalc-tab" data-yalc-tab="channels" role="tab" aria-selected="false"
            tabindex="-1">Log Channels</button>
        </div>
        """

    @staticmethod
    def _yalc_tabs_script() -> str:
        return """
        <script>
        (() => {
            const root = document.currentScript.closest("[data-yalc-tabs]");
            if (!root) return;
            const tabs = Array.from(root.querySelectorAll("[data-yalc-tab]"));
            const panels = Array.from(root.querySelectorAll("[data-yalc-panel]"));
            const names = new Set(tabs.map((tab) => tab.dataset.yalcTab));
            const storageKey = `yalc-dashboard-tab:${location.pathname}`;
            const activate = (name, updateHash = false) => {
                if (!names.has(name)) return;
                tabs.forEach((tab) => {
                    const selected = tab.dataset.yalcTab === name;
                    tab.classList.toggle("active", selected);
                    tab.setAttribute("aria-selected", selected ? "true" : "false");
                    tab.tabIndex = selected ? 0 : -1;
                });
                panels.forEach((panel) => {
                    const selected = panel.dataset.yalcPanel === name;
                    panel.classList.toggle("active", selected);
                    panel.hidden = !selected;
                });
                sessionStorage.setItem(storageKey, name);
                if (updateHash) history.replaceState(null, "", `#tab-${name}`);
            };
            tabs.forEach((tab, index) => {
                tab.addEventListener("click", () => activate(tab.dataset.yalcTab, true));
                tab.addEventListener("keydown", (event) => {
                    const move = event.key === "ArrowRight" ? 1 : event.key === "ArrowLeft" ? -1 : 0;
                    if (!move) return;
                    event.preventDefault();
                    const next = tabs[(index + move + tabs.length) % tabs.length];
                    next.focus();
                    activate(next.dataset.yalcTab, true);
                });
            });
            const eventInputs = () => Array.from(root.querySelectorAll("[data-yalc-event]"));
            const updateEventControls = () => {
                const allInputs = eventInputs();
                root.querySelectorAll("[data-yalc-event-group]").forEach((group) => {
                    const inputs = Array.from(group.querySelectorAll("[data-yalc-event]"));
                    const enabled = inputs.filter((input) => input.checked).length;
                    const count = group.querySelector("[data-yalc-count]");
                    const button = group.querySelector("[data-yalc-toggle-group]");
                    if (count) count.textContent = `${enabled}/${inputs.length} enabled`;
                    if (button) button.textContent = enabled === inputs.length ? "Disable category" : "Enable category";
                });
                const enabled = allInputs.filter((input) => input.checked).length;
                const count = root.querySelector("[data-yalc-total-count]");
                const button = root.querySelector("[data-yalc-toggle-all]");
                if (count) count.textContent = `${enabled}/${allInputs.length} events enabled`;
                if (button) button.textContent = enabled === allInputs.length ? "Disable all events" : "Enable all events";
            };
            root.querySelectorAll("[data-yalc-toggle-group]").forEach((button) => {
                button.addEventListener("click", () => {
                    const inputs = Array.from(button.closest("[data-yalc-event-group]").querySelectorAll(
                        "[data-yalc-event]",
                    ));
                    const enable = inputs.some((input) => !input.checked);
                    inputs.forEach((input) => { input.checked = enable; });
                    updateEventControls();
                });
            });
            const toggleAll = root.querySelector("[data-yalc-toggle-all]");
            if (toggleAll) toggleAll.addEventListener("click", () => {
                const inputs = eventInputs();
                const enable = inputs.some((input) => !input.checked);
                inputs.forEach((input) => { input.checked = enable; });
                updateEventControls();
            });
            eventInputs().forEach((input) => input.addEventListener("change", updateEventControls));
            updateEventControls();
            const hash = location.hash.startsWith("#tab-") ? location.hash.slice(5) : "";
            activate(names.has(hash) ? hash : sessionStorage.getItem(storageKey) || "filters");
        })();
        </script>
        """

    async def _generate_wtforms_html(
        self,
        guild: discord.Guild,
        settings: dict,
        event_sections: str,
        channel_sections: str,
        csrf_hidden: str = "",
    ) -> str:
        """Generate HTML template for WTForms rendering.

        This method now returns a simplified template that doesn't rely on form field access,
        since the Jinja2 error suggests the form object isn't being passed correctly to the template context.
        """
        guild_name = html.escape(guild.name)
        # Create checkbox values for direct HTML rendering
        checkbox_values = {
            "include_thumbnails": "checked"
            if settings.get("include_thumbnails", True)
            else "",
            "ignore_bots": "checked" if settings.get("ignore_bots", False) else "",
            "ignore_webhooks": "checked"
            if settings.get("ignore_webhooks", False)
            else "",
            "ignore_tupperbox": "checked"
            if settings.get("ignore_tupperbox", True)
            else "",
            "ignore_apps": "checked" if settings.get("ignore_apps", True) else "",
            "detect_proxy_deletes": "checked"
            if settings.get("detect_proxy_deletes", True)
            else "",
        }

        return f"""
        <div data-yalc-tabs="1" class="yalc-shell">
            <header class="yalc-hero">
                <h1>YALC logging</h1>
                <p>Choose what gets logged and where for <strong>{guild_name}</strong>.</p>
            </header>
            {self._yalc_tabs_header()}

            <!-- Manual form since WTForms template access is problematic -->
            <form method="POST" style="width: 100%;">
                {csrf_hidden}
                <!-- Filter Settings Section -->
                <section class="yalc-tab-panel active" data-yalc-panel="filters">
                <div style="margin-bottom: 2em; padding: 1.5em; background: #2d2d2d; border-radius: 8px; border-left:
                4px solid #4caf50;">
                    <h3 style="color: #4caf50; margin-top: 0; margin-bottom: 1em; font-size: 1.3em; font-weight: 600;">🔍
                     Filtering Options</h3>
                    <p style="color: #b0b0b0; margin-bottom: 1.5em; font-size: 0.95em;">Configure what types of messages
                     and events to include or exclude from logging.</p>

                    <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 20px;">
                        <label style="display: flex; align-items: center; padding: 0.8em; background: #3a3a3a;
                        border-radius: 6px; border: 1px solid #4a4a4a; cursor: pointer; transition: all 0.2s ease;">
                            <input type="checkbox" name="yalc_settings_include_thumbnails" value="1"
                            {checkbox_values["include_thumbnails"]}
                                   style="margin-right: 12px; transform: scale(1.3); accent-color: #4caf50;">
                            <div>
                                <div style="font-weight: 500; color: #e0e0e0;">🖼️ Include user thumbnails</div>
                                <div style="font-size: 0.85em; color: #b0b0b0; margin-top: 2px;">Show user avatars in
                                log embeds</div>
                            </div>
                        </label>

                        <label style="display: flex; align-items: center; padding: 0.8em; background: #3a3a3a;
                        border-radius: 6px; border: 1px solid #4a4a4a; cursor: pointer; transition: all 0.2s ease;">
                            <input type="checkbox" name="yalc_settings_ignore_bots" value="1"
                            {checkbox_values["ignore_bots"]}
                                   style="margin-right: 12px; transform: scale(1.3); accent-color: #4caf50;">
                            <div>
                                <div style="font-weight: 500; color: #e0e0e0;">🤖 Ignore bot messages</div>
                                <div style="font-size: 0.85em; color: #b0b0b0; margin-top: 2px;">Skip logging events
                                from bots</div>
                            </div>
                        </label>

                        <label style="display: flex; align-items: center; padding: 0.8em; background: #3a3a3a;
                        border-radius: 6px; border: 1px solid #4a4a4a; cursor: pointer; transition: all 0.2s ease;">
                            <input type="checkbox" name="yalc_settings_ignore_webhooks" value="1"
                            {checkbox_values["ignore_webhooks"]}
                                   style="margin-right: 12px; transform: scale(1.3); accent-color: #4caf50;">
                            <div>
                                <div style="font-weight: 500; color: #e0e0e0;">🪝 Ignore webhook messages</div>
                                <div style="font-size: 0.85em; color: #b0b0b0; margin-top: 2px;">Skip logging webhook
                                events</div>
                            </div>
                        </label>

                        <label style="display: flex; align-items: center; padding: 0.8em; background: #3a3a3a;
                        border-radius: 6px; border: 1px solid #4a4a4a; cursor: pointer; transition: all 0.2s ease;">
                            <input type="checkbox" name="yalc_settings_ignore_tupperbox" value="1"
                            {checkbox_values["ignore_tupperbox"]}
                                   style="margin-right: 12px; transform: scale(1.3); accent-color: #4caf50;">
                            <div>
                                <div style="font-weight: 500; color: #e0e0e0;">👥 Ignore Tupperbox/proxy messages</div>
                                <div style="font-size: 0.85em; color: #b0b0b0; margin-top: 2px;">Skip logging proxy bot
                                messages</div>
                            </div>
                        </label>

                        <label style="display: flex; align-items: center; padding: 0.8em; background: #3a3a3a;
                        border-radius: 6px; border: 1px solid #4a4a4a; cursor: pointer; transition: all 0.2s ease;">
                            <input type="checkbox" name="yalc_settings_ignore_apps" value="1"
                            {checkbox_values["ignore_apps"]}
                                   style="margin-right: 12px; transform: scale(1.3); accent-color: #4caf50;">
                            <div>
                                <div style="font-weight: 500; color: #e0e0e0;">📱 Ignore app messages</div>
                                <div style="font-size: 0.85em; color: #b0b0b0; margin-top: 2px;">Skip logging
                                application events</div>
                            </div>
                        </label>

                        <label style="display: flex; align-items: center; padding: 0.8em; background: #3a3a3a;
                        border-radius: 6px; border: 1px solid #4a4a4a; cursor: pointer; transition: all 0.2s ease;">
                            <input type="checkbox" name="yalc_settings_detect_proxy_deletes" value="1"
                            {checkbox_values["detect_proxy_deletes"]}
                                   style="margin-right: 12px; transform: scale(1.3); accent-color: #4caf50;">
                            <div>
                                <div style="font-weight: 500; color: #e0e0e0;">🔍 Detect proxy deletes</div>
                                <div style="font-size: 0.85em; color: #b0b0b0; margin-top: 2px;">Log when proxy messages
                                 are deleted</div>
                            </div>
                        </label>
                    </div>
                </div>
                </section>

                <!-- Additional event and channel sections -->
                <section class="yalc-tab-panel" data-yalc-panel="events" style="margin-top: 2em;">
                    {event_sections}
                </section>
                <section class="yalc-tab-panel" data-yalc-panel="channels" style="margin-top: 2em;">
                    {channel_sections}
                </section>

                <!-- Submit button -->
                <div class="yalc-save">
                    <p class="yalc-note">Changes take effect as soon as they are saved.</p>
                    <input type="submit" name="submit" value="Save configuration" class="yalc-submit">
                </div>
            </form>

            <div class="yalc-about">
                <strong>About YALC</strong>
                Configure event logging, destination channels, and message filters for this server.
            </div>

            <script>
                document.addEventListener('DOMContentLoaded', function() {{
                    // Add form submission feedback without disabling native submission.
                    const submitButton = document.querySelector('input[type="submit"]');
                    if (submitButton) {{
                        const form = submitButton.closest('form');
                        if (form) {{
                            form.addEventListener('submit', function() {{
                                submitButton.value = 'Saving...';
                                submitButton.style.opacity = '0.7';
                                submitButton.style.pointerEvents = 'none';
                            }});
                        }}
                    }}
                }});
            </script>
            {self._yalc_tabs_script()}
        </div>
        """

    def _get_event_categories(self) -> dict[str, dict[str, typing.Any]]:
        """Return dashboard groupings for YALC's configured event keys."""
        return {
            "Message Events": {
                "events": [
                    "message_delete",
                    "message_edit",
                    "message_bulk_delete",
                    "message_pin",
                    "message_unpin",
                ],
                "color": "#f44336",
                "description": "Track message modifications, deletions, and pin changes",
            },
            "Reaction Events": {
                "events": ["reaction_add", "reaction_remove", "reaction_clear"],
                "color": "#e91e63",
                "description": "Monitor message reactions and emoji interactions",
            },
            "Member Events": {
                "events": [
                    "member_join",
                    "member_leave",
                    "member_ban",
                    "member_unban",
                    "member_kick",
                    "member_timeout",
                    "member_update",
                ],
                "color": "#2196f3",
                "description": "Monitor member activity and moderation actions",
            },
            "Voice Events": {
                "events": ["voice_state_update", "voice_update"],
                "color": "#9c27b0",
                "description": "Track voice channel activity and state changes",
            },
            "Channel Events": {
                "events": ["channel_create", "channel_delete", "channel_update"],
                "color": "#ff9800",
                "description": "Monitor channel management",
            },
            "Thread & Forum Events": {
                "events": [
                    "thread_create",
                    "thread_delete",
                    "thread_update",
                    "thread_member_join",
                    "thread_member_leave",
                    "forum_post_create",
                    "forum_post_delete",
                    "forum_post_update",
                ],
                "color": "#00bcd4",
                "description": "Monitor thread and forum post activity",
            },
            "Role Events": {
                "events": ["role_create", "role_delete", "role_update"],
                "color": "#ff5722",
                "description": "Track role creation, deletion, and permission changes",
            },
            "Server Events": {
                "events": ["guild_update", "emoji_update", "sticker_update"],
                "color": "#009688",
                "description": "Monitor server settings, emoji, and sticker changes",
            },
            "Scheduled & Stage Events": {
                "events": [
                    "guild_scheduled_event_create",
                    "guild_scheduled_event_delete",
                    "guild_scheduled_event_update",
                    "stage_instance_create",
                    "stage_instance_delete",
                    "stage_instance_update",
                ],
                "color": "#607d8b",
                "description": "Track scheduled events and stage instances",
            },
            "Command Events": {
                "events": [
                    "command_use",
                    "command_error",
                    "application_cmd",
                    "application_cmd_permissions_update",
                ],
                "color": "#4caf50",
                "description": "Track prefix commands, slash commands, and permissions",
            },
            "Integration & Webhook Events": {
                "events": [
                    "integration_create",
                    "integration_delete",
                    "integration_update",
                    "webhook_update",
                ],
                "color": "#673ab7",
                "description": "Track server integrations and webhook changes",
            },
            "Soundboard Events": {
                "events": [
                    "soundboard_sound_create",
                    "soundboard_sound_delete",
                    "soundboard_sound_update",
                ],
                "color": "#3f51b5",
                "description": "Monitor soundboard sound changes",
            },
            "AutoMod Events": {
                "events": [
                    "automod_rule_create",
                    "automod_rule_delete",
                    "automod_rule_update",
                    "automod_action",
                ],
                "color": "#795548",
                "description": "Track AutoMod rule changes and moderation actions",
            },
            "Invite Events": {
                "events": ["invite_create", "invite_delete"],
                "color": "#ff6f00",
                "description": "Monitor server invite creation and deletion",
            },
        }

    def _generate_event_sections(self, settings: dict) -> str:
        """Generate responsive event controls with global and category toggles."""
        event_descriptions = getattr(self, "event_descriptions", {})
        categories = self._get_event_categories()
        sections = []
        total_events = 0
        total_enabled = 0

        for category_index, (category_name, category_info) in enumerate(categories.items()):
            events = [
                event
                for event in category_info["events"]
                if event in event_descriptions
            ]
            if not events:
                continue
            description = html.escape(category_info["description"])
            category_name_html = html.escape(category_name)
            event_checkboxes = []
            enabled_count = 0

            for event in events:
                emoji, desc = event_descriptions[event]
                is_checked = settings.get("events", {}).get(event, False)
                if is_checked:
                    enabled_count += 1
                checked = "checked" if is_checked else ""
                event_html = html.escape(event)
                desc_html = html.escape(desc)
                emoji_html = html.escape(emoji)
                event_checkboxes.append(f"""
                    <label class="yalc-event">
                        <input type="checkbox" name="event_{event_html}" value="1" {checked} data-yalc-event>
                        <div>
                            <div class="yalc-event-name">{emoji_html} {desc_html}</div>
                            <div class="yalc-event-key">{event_html}</div>
                        </div>
                    </label>
                """)

            if event_checkboxes:
                total_events += len(events)
                total_enabled += enabled_count
                group_id = f"events-{category_index}"
                toggle_label = "Disable category" if enabled_count == len(events) else "Enable category"
                sections.append(f"""
                    <section class="yalc-section" data-yalc-event-group id="{group_id}">
                        <div class="yalc-section-head">
                            <h3>{category_name_html}</h3>
                            <div>
                                <span class="yalc-count" data-yalc-count>{enabled_count}/{len(events)} enabled</span>
                                <button type="button" class="yalc-button" data-yalc-toggle-group>{toggle_label}</button>
                            </div>
                        </div>
                        <p class="yalc-section-copy">{description}</p>
                        <div class="yalc-event-grid">
                            {"".join(event_checkboxes)}
                        </div>
                    </section>
                """)

        global_label = "Disable all events" if total_events and total_enabled == total_events else "Enable all events"
        return f"""
            <div class="yalc-event-toolbar">
                <span class="yalc-count" data-yalc-total-count>{total_enabled}/{total_events} events enabled</span>
                <button type="button" class="yalc-button" data-yalc-toggle-all>{global_label}</button>
            </div>
            {"".join(sections)}
        """

    def _generate_channel_sections(self, guild: discord.Guild, settings: dict) -> str:
        """Generate HTML for channel configuration sections with dark mode styling."""
        # Get text channels for dropdown
        text_channels = [
            c for c in guild.channels if isinstance(c, discord.TextChannel)
        ]
        text_channels.sort(key=lambda c: c.name.lower())  # Sort alphabetically

        channel_options = '<option value="">📵 No logging</option>' + "".join(
            f'<option value="{c.id}">#{html.escape(c.name)}</option>'
            for c in text_channels
        )

        event_descriptions = getattr(self, "event_descriptions", {})
        categories = self._get_event_categories()

        category_sections = []
        configured_count = 0
        total_events = sum(
            1
            for category_info in categories.values()
            for event in category_info["events"]
            if event in event_descriptions
        )

        for category_name, category_info in categories.items():
            category_events = [
                event
                for event in category_info["events"]
                if event in event_descriptions
            ]
            if not category_events:
                continue

            channel_config_html = ""
            for event in category_events:
                emoji, desc = event_descriptions[event]
                current_channel_id = settings.get(
                    "event_channels", {}).get(event)
                if current_channel_id:
                    configured_count += 1

                options_with_selection = channel_options
                if current_channel_id:
                    options_with_selection = options_with_selection.replace(
                        f'value="{current_channel_id}"',
                        f'value="{current_channel_id}" selected',
                    )

                is_enabled = settings.get("events", {}).get(event, False)
                state_badge = "" if is_enabled else '<span class="yalc-disabled">disabled</span>'
                opacity = "1" if is_enabled else "0.72"
                event_html = html.escape(event)
                desc_html = html.escape(desc)
                emoji_html = html.escape(emoji)

                channel_config_html += f"""
                    <div class="yalc-channel-row" style="opacity: {opacity};">
                        <label for="channel_{event_html}" class="yalc-channel-label">
                            {emoji_html} {desc_html}{state_badge}
                            <div class="yalc-event-key">{event_html}</div>
                        </label>
                        <select name="event_channels[{event_html}]" id="channel_{event_html}"
                                class="yalc-channel-select">
                            {options_with_selection}
                        </select>
                    </div>
                """

            if channel_config_html:
                category_sections.append(f"""
                    <section class="yalc-channel-group">
                        <h4>{html.escape(category_name)}</h4>
                        {channel_config_html}
                    </section>
                """)

        status_text = (
            f"{configured_count}/{total_events} events have channels configured"
        )
        status_color = (
            "#4caf50"
            if configured_count == total_events
            else "#ff9800"
            if configured_count > 0
            else "#f44336"
        )

        return f"""
            <div class="yalc-section">
                <div class="yalc-section-head">
                    <h3>Event log channels</h3>
                    <span class="yalc-count" style="color: {status_color};">
                        {status_text}
                    </span>
                </div>
                <p class="yalc-section-copy">
                    Assign channels for events you enable above. Events without assigned channels won't be logged.
                    You can set a channel before enabling its event.
                </p>
                {"".join(category_sections)}
            </div>
        """

    def _generate_filter_sections(self, guild: discord.Guild, settings: dict) -> str:
        """Generate HTML for filtering options with dark mode styling."""
        return f"""
            <div style="margin-bottom: 2em; padding: 1.5em; background: #2d2d2d; border-radius: 8px; border-left: 4px
            solid #4caf50;">
                <h3 style="color: #4caf50; margin-top: 0; margin-bottom: 1em; font-size: 1.3em; font-weight: 600;">🔍
                Filtering Options</h3>
                <p style="color: #b0b0b0; margin-bottom: 1.5em; font-size: 0.95em;">Configure what types of messages and
                 events to include or exclude from logging.</p>

                <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 20px;">
                    <label style="display: flex; align-items: center; padding: 0.8em; background: #3a3a3a;
                    border-radius: 6px; border: 1px solid #4a4a4a; cursor: pointer; transition: all 0.2s ease;">
                        <input type="checkbox" name="include_thumbnails" value="1" {"checked" if
                        settings.get("include_thumbnails", True) else ""}
                               style="margin-right: 12px; transform: scale(1.3); accent-color: #4caf50;">
                        <div>
                            <div style="font-weight: 500; color: #e0e0e0;">🖼️ Include user thumbnails</div>
                            <div style="font-size: 0.85em; color: #b0b0b0; margin-top: 2px;">Show user avatars in log
                            embeds</div>
                        </div>
                    </label>

                    <label style="display: flex; align-items: center; padding: 0.8em; background: #3a3a3a;
                    border-radius: 6px; border: 1px solid #4a4a4a; cursor: pointer; transition: all 0.2s ease;">
                        <input type="checkbox" name="ignore_bots" value="1" {"checked" if settings.get("ignore_bots",
                        False) else ""}
                               style="margin-right: 12px; transform: scale(1.3); accent-color: #4caf50;">
                        <div>
                            <div style="font-weight: 500; color: #e0e0e0;">🤖 Ignore bot messages</div>
                            <div style="font-size: 0.85em; color: #b0b0b0; margin-top: 2px;">Skip logging events from
                            bots</div>
                        </div>
                    </label>

                    <label style="display: flex; align-items: center; padding: 0.8em; background: #3a3a3a;
                    border-radius: 6px; border: 1px solid #4a4a4a; cursor: pointer; transition: all 0.2s ease;">
                        <input type="checkbox" name="ignore_webhooks" value="1" {"checked" if
                        settings.get("ignore_webhooks", False) else ""}
                               style="margin-right: 12px; transform: scale(1.3); accent-color: #4caf50;">
                        <div>
                            <div style="font-weight: 500; color: #e0e0e0;">🪝 Ignore webhook messages</div>
                            <div style="font-size: 0.85em; color: #b0b0b0; margin-top: 2px;">Skip logging webhook
                            events</div>
                        </div>
                    </label>

                    <label style="display: flex; align-items: center; padding: 0.8em; background: #3a3a3a;
                    border-radius: 6px; border: 1px solid #4a4a4a; cursor: pointer; transition: all 0.2s ease;">
                        <input type="checkbox" name="ignore_tupperbox" value="1" {"checked" if
                        settings.get("ignore_tupperbox", True) else ""}
                               style="margin-right: 12px; transform: scale(1.3); accent-color: #4caf50;">
                        <div>
                            <div style="font-weight: 500; color: #e0e0e0;">👥 Ignore Tupperbox/proxy messages</div>
                            <div style="font-size: 0.85em; color: #b0b0b0; margin-top: 2px;">Skip logging proxy bot
                            messages</div>
                        </div>
                    </label>

                    <label style="display: flex; align-items: center; padding: 0.8em; background: #3a3a3a;
                    border-radius: 6px; border: 1px solid #4a4a4a; cursor: pointer; transition: all 0.2s ease;">
                        <input type="checkbox" name="ignore_apps" value="1" {"checked" if settings.get("ignore_apps",
                        True) else ""}
                               style="margin-right: 12px; transform: scale(1.3); accent-color: #4caf50;">
                        <div>
                            <div style="font-weight: 500; color: #e0e0e0;">📱 Ignore app messages</div>
                            <div style="font-size: 0.85em; color: #b0b0b0; margin-top: 2px;">Skip logging application
                            events</div>
                        </div>
                    </label>

                    <label style="display: flex; align-items: center; padding: 0.8em; background: #3a3a3a;
                    border-radius: 6px; border: 1px solid #4a4a4a; cursor: pointer; transition: all 0.2s ease;">
                        <input type="checkbox" name="detect_proxy_deletes" value="1" {"checked" if
                        settings.get("detect_proxy_deletes", True) else ""}
                               style="margin-right: 12px; transform: scale(1.3); accent-color: #4caf50;">
                        <div>
                            <div style="font-weight: 500; color: #e0e0e0;">🔍 Detect proxy deletes</div>
                            <div style="font-size: 0.85em; color: #b0b0b0; margin-top: 2px;">Log when proxy messages are
                             deleted</div>
                        </div>
                    </label>
                </div>
            </div>
        """

    @commands.Cog.listener()
    async def on_dashboard_cog_add(self, dashboard_cog: commands.Cog) -> None:
        """Register the dashboard integration when dashboard cog is loaded."""
        handler = dashboard_cog.rpc.third_parties_handler
        try:
            handler.add_third_party(self, overwrite=True)
        except TypeError:
            handler.add_third_party(self)
