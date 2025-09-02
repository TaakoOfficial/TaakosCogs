from redbot.core import commands
from redbot.core.bot import Red
import discord
import typing

# --- AAA3A_utils import for CFS token/auth handling ---
import importlib
import subprocess
import sys

try:
    from AAA3A_utils import dashboard_utils
except ImportError:
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", "AAA3A_utils"])
        dashboard_utils = importlib.import_module("AAA3A_utils").dashboard_utils
    except Exception:
        dashboard_utils = None  # Fallback if AAA3A_utils is not installed

class DashboardIntegration:
    """Dashboard integration mixin for YALC cog.

    This class provides the required interface for Red-Web-Dashboard
    third-party integrations. It's designed to be inherited from
    by the main cog class.

    --- DASHBOARD HOOKS ARE ADDED HERE ---
    - on_dashboard_cog_add: Registers this cog as a dashboard third party.
    - get_pages: Exposes dashboard pages for Red-Web-Dashboard.
    - yalcdash_settings: Exposes config options as dashboard widgets.
    """

    # Required attributes for Red-Web-Dashboard third-party integration
    name = "YALC"
    description = "Yet Another Logging Cog - Comprehensive Discord event logging with dashboard integration"
    version = "3.0.0"
    author = "YALC Team"
    repo = "https://github.com/your-repo/YALC"
    support = "https://discord.gg/your-support"
    icon = "https://cdn-icons-png.flaticon.com/512/928/928797.png"

    # Required bot attribute for Red-Web-Dashboard
    bot: Red

    # Dashboard page decorator (will be set when Dashboard cog loads)
    dashboard_page = None
    
    # Required method for third-party integration
    def get_pages(self) -> typing.List[typing.Dict[str, typing.Any]]:
        """Return a list of dashboard pages for this third-party integration.
        
        This method is required by Red-Web-Dashboard to discover available pages.
        """
        pages = []
        
        # Main dashboard page
        pages.append({
            "name": None,  # Main page
            "description": "YALC Dashboard: Manage and view YALC features.",
            "methods": ("GET", "POST"),
            "is_owner": True,
            "function": self.yalcdash_main
        })
        
        # Guild-specific page
        pages.append({
            "name": "guild",
            "description": "YALC Guild Dashboard: View guild details.",
            "methods": ("GET",),
            "is_owner": False,
            "function": self.yalcdash_guild
        })
        
        # Settings page
        pages.append({
            "name": "settings",
            "description": "YALC Settings Dashboard: Configure logging settings.",
            "methods": ("GET", "POST"),
            "is_owner": False,
            "function": self.yalcdash_settings
        })
        
        return pages

    @commands.Cog.listener()
    async def on_dashboard_cog_add(self, dashboard_cog: commands.Cog) -> None:
        """Register this cog as a third party with the Dashboard when dashboard cog is loaded."""
        try:
            # Try different paths to access the third_parties_handler (robust fallback)
            third_parties_handler = None
            dashboard_page = None

            # Main path: dashboard_cog.rpc.third_parties_handler
            if hasattr(dashboard_cog, 'rpc') and hasattr(dashboard_cog.rpc, 'third_parties_handler'):
                third_parties_handler = dashboard_cog.rpc.third_parties_handler
                if hasattr(third_parties_handler, 'dashboard_page'):
                    dashboard_page = third_parties_handler.dashboard_page

            # Fallback path: dashboard_cog.third_parties_handler (if rpc is not there)
            elif hasattr(dashboard_cog, 'third_parties_handler'):
                third_parties_handler = dashboard_cog.third_parties_handler
                if hasattr(third_parties_handler, 'dashboard_page'):
                    dashboard_page = third_parties_handler.dashboard_page

            if third_parties_handler:
                # Set the dashboard_page for decoration
                self.dashboard_page = dashboard_page

                # Debug: Print available attributes
                print(f"YALC: Dashboard cog attributes: {[attr for attr in dir(dashboard_cog) if not attr.startswith('_')]}")
                if hasattr(dashboard_cog, 'rpc'):
                    print(f"YALC: Dashboard rpc attributes: {[attr for attr in dir(dashboard_cog.rpc) if not attr.startswith('_')]}")

                # Register the third party
                await third_parties_handler.add_third_party(self)

                # Dynamically apply the dashboard_page decorator to our methods if available
                if self.dashboard_page:
                    self.yalcdash_main = self.dashboard_page(self.yalcdash_main)
                    self.yalcdash_guild = self.dashboard_page(self.yalcdash_guild)
                    self.yalcdash_settings = self.dashboard_page(self.yalcdash_settings)

                # Access log through the main cog instance
                if hasattr(self, 'log'):
                    self.log.info("Successfully registered YALC as a dashboard third party.")
                else:
                    print("YALC: Successfully registered as a dashboard third party.")
            else:
                if hasattr(self, 'log'):
                    self.log.warning("Dashboard cog found but could not locate third_parties_handler.")
                else:
                    print("YALC: Dashboard cog found but could not locate third_parties_handler.")
        except Exception as e:
            if hasattr(self, 'log'):
                self.log.error(f"Dashboard integration setup failed: {e}")
            else:
                print(f"YALC: Dashboard integration setup failed: {e}")

    # Dashboard page methods without decorators - they'll be registered manually
    async def yalcdash_main(self, user: discord.User, **kwargs) -> typing.Dict[str, typing.Any]:
        """Main YALC dashboard page."""
        import wtforms

        class YALCForm(kwargs["Form"]):
            def __init__(self):
                super().__init__(prefix="yalc_dashboard_form_")
            action: wtforms.SelectField = wtforms.SelectField(
                "Action:",
                choices=[("view", "View Info"), ("update", "Update Settings")],
                validators=[wtforms.validators.InputRequired()]
            )
            message: wtforms.TextAreaField = wtforms.TextAreaField(
                "Message:",
                validators=[wtforms.validators.Optional(), wtforms.validators.Length(max=2000)],
                default=""
            )
            submit: wtforms.SubmitField = wtforms.SubmitField("Submit")

        form: YALCForm = YALCForm()
        notifications = []

        if form.validate_on_submit():
            action = form.action.data
            msg = form.message.data
            if action == "view":
                notifications.append({"message": "Viewing YALC info.", "category": "info"})
            elif action == "update":
                notifications.append({"message": f"Updated settings: {msg}", "category": "success"})
            else:
                notifications.append({"message": "Unknown action.", "category": "error"})
            return {
                "status": 0,
                "notifications": notifications,
                "redirect_url": kwargs["request_url"],
            }

        # Get some stats about YALC
        total_guilds = len(self.bot.guilds) if hasattr(self, 'bot') else 0
        event_count = len(getattr(self, 'event_descriptions', {}))

        source = f"""
        <div class="dashboard-header">
            <h2>🎯 YALC Dashboard</h2>
            <p>Yet Another Logging Cog - Comprehensive Discord event logging</p>
        </div>

        <div class="stats-grid">
            <div class="stat-card">
                <h3>📊 Statistics</h3>
                <p><strong>Total Servers:</strong> {total_guilds}</p>
                <p><strong>Event Types:</strong> {event_count}</p>
                <p><strong>Version:</strong> {self.version}</p>
            </div>

            <div class="stat-card">
                <h3>🔧 Quick Actions</h3>
                <p><a href="/dashboard/{{{{ guild.id }}}}/third-party/YALC/settings" class="btn btn-primary">Configure Logging</a></p>
                <p><a href="/dashboard/{{{{ guild.id }}}}/third-party/YALC/guild" class="btn btn-secondary">View Server Info</a></p>
            </div>
        </div>

        <div class="form-section">
            <h3>📝 Quick Actions</h3>
            {{{{ form|safe }}}}
        </div>

        <style>
        .dashboard-header {{
            text-align: center;
            margin-bottom: 2rem;
            padding: 1rem;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            border-radius: 10px;
        }}

        .stats-grid {{
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 1rem;
            margin-bottom: 2rem;
        }}

        .stat-card {{
            background: #f8f9fa;
            padding: 1rem;
            border-radius: 8px;
            border-left: 4px solid #667eea;
        }}

        .form-section {{
            background: white;
            padding: 1rem;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }}

        .btn {{
            display: inline-block;
            padding: 0.5rem 1rem;
            text-decoration: none;
            border-radius: 4px;
            margin: 0.25rem;
        }}

        .btn-primary {{
            background: #007bff;
            color: white;
        }}

        .btn-secondary {{
            background: #6c757d;
            color: white;
        }}
        </style>
        """

        return {
            "status": 0,
            "web_content": {"source": source, "form": form},
        }

    async def yalcdash_guild(self, user: discord.User, guild: discord.Guild, **kwargs) -> typing.Dict[str, typing.Any]:
        """Guild-specific YALC dashboard page."""
        return {
            "status": 0,
            "web_content": {
                "source": '<h4>YALC Dashboard: Guild "{{ guild.name }}" ({{ guild.id }})</h4>',
                "guild": guild,
            },
        }

    async def yalcdash_settings(self, user: discord.User, guild: discord.Guild, **kwargs) -> typing.Dict[str, typing.Any]:
        """Settings configuration page for YALC."""
        import wtforms

        # Get current settings for this guild - access config through the main cog instance
        current_settings = {}
        if hasattr(self, 'config') and hasattr(self.config, 'guild'):
            try:
                current_settings = await self.config.guild(guild).all()
            except Exception as e:
                if hasattr(self, 'log'):
                    self.log.debug(f"Could not get current settings: {e}")
                current_settings = {}

        # Get event descriptions from the main cog
        event_descriptions = getattr(self, 'event_descriptions', {})

        # Example config fields for dashboard widgets
        enable_feature = current_settings.get("enable_feature", False)
        custom_message = current_settings.get("custom_message", "")
        log_retention_days = current_settings.get("log_retention_days", 7)

        class SettingsForm(kwargs["Form"]):
            def __init__(self):
                super().__init__(prefix="yalc_settings_form_")

                # Example widgets for dashboard config
                self.enable_feature = wtforms.BooleanField(
                    "Enable YALC feature",
                    default=enable_feature
                )
                self.custom_message = wtforms.StringField(
                    "Custom message",
                    default=custom_message,
                    validators=[wtforms.validators.Length(max=200)]
                )
                self.log_retention_days = wtforms.IntegerField(
                    "Log retention days",
                    default=log_retention_days,
                    validators=[wtforms.validators.NumberRange(min=1, max=365)]
                )

                # Create form fields based on available events
                for event_name, (emoji, description) in event_descriptions.items():
                    field_name = f"event_{event_name}"
                    current_value = current_settings.get("events", {}).get(event_name, False)
                    setattr(self, field_name, wtforms.BooleanField(
                        f"{emoji} {description}",
                        default=current_value
                    ))

                self.submit = wtforms.SubmitField("Save Settings")

        form: SettingsForm = SettingsForm()

        if form.validate_on_submit():
            # Update settings based on form submission
            try:
                # Use AAA3A_utils for CFS token/auth if available
                if dashboard_utils and hasattr(dashboard_utils, "validate_cfs_token"):
                    cfs_token = kwargs.get("cfs_token")
                    if not dashboard_utils.validate_cfs_token(cfs_token):
                        return {
                            "status": 0,
                            "notifications": [{"message": "Invalid CFS token.", "category": "error"}],
                        }

                # Save example config fields
                if hasattr(self, 'config') and hasattr(self.config, 'guild'):
                    await self.config.guild(guild).enable_feature.set(form.enable_feature.data)
                    await self.config.guild(guild).custom_message.set(form.custom_message.data)
                    await self.config.guild(guild).log_retention_days.set(form.log_retention_days.data)

                # Save event toggles
                new_settings = {}
                for event_name in event_descriptions.keys():
                    field_name = f"event_{event_name}"
                    if hasattr(form, field_name):
                        new_settings[event_name] = getattr(form, field_name).data

                if hasattr(self, 'config') and hasattr(self.config, 'guild'):
                    await self.config.guild(guild).events.set(new_settings)

                return {
                    "status": 0,
                    "notifications": [{"message": "Settings updated successfully!", "category": "success"}],
                    "redirect_url": kwargs["request_url"],
                }
            except Exception as e:
                return {
                    "status": 0,
                    "notifications": [{"message": f"Error updating settings: {e}", "category": "error"}],
                }

        # Prepare form HTML
        form_fields_html = ""

        # Render example widgets
        form_fields_html += f"""
        <div class="form-group">
            <label for="enable_feature">{form.enable_feature.label.text}</label>
            <input type="checkbox" id="enable_feature" name="enable_feature"{' checked="checked"' if form.enable_feature.data else ''}>
        </div>
        <div class="form-group">
            <label for="custom_message">{form.custom_message.label.text}</label>
            <input type="text" id="custom_message" name="custom_message" value="{form.custom_message.data}">
        </div>
        <div class="form-group">
            <label for="log_retention_days">{form.log_retention_days.label.text}</label>
            <input type="number" id="log_retention_days" name="log_retention_days" value="{form.log_retention_days.data}" min="1" max="365">
        </div>
        """

        # Render event toggles
        for field_name, field in form._fields.items():
            if field.type == 'BooleanField' and not field_name in ['enable_feature']:
                checked_attr = ' checked="checked"' if field.data else ''
                form_fields_html += f"""
                <div class="form-group">
                    <label for="{field_name}">{field.label.text}</label>
                    <input type="checkbox" id="{field_name}" name="{field_name}"{checked_attr}>
                </div>
                """

        source = f"""
        <h3>YALC Settings for {{{{ guild.name }}}}</h3>
        <p>Configure which events to log in this server.</p>
        <form method="POST">
            {form_fields_html}
            <input type="submit" value="Save Settings" class="btn btn-primary">
        </form>
        <style>
        .form-group {{
            margin-bottom: 1rem;
        }}
        .form-group label {{
            display: block;
            margin-bottom: 0.5rem;
            font-weight: bold;
        }}
        .btn {{
            display: inline-block;
            padding: 0.5rem 1rem;
            text-decoration: none;
            border-radius: 4px;
            border: none;
            cursor: pointer;
        }}
        .btn-primary {{
            background: #007bff;
            color: white;
        }}
        </style>
        """

        return {
            "status": 0,
            "web_content": {
                "source": source,
                "form": form,
                "guild": guild,
                "current_settings": current_settings
            },
        }