from redbot.core import commands, Config
from redbot.core.bot import Red
import discord
import typing
import logging
from typing import TYPE_CHECKING

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

# Local dashboard_page decorator for Red-Web-Dashboard compatibility
def dashboard_page(*args, **kwargs):
    def decorator(func):
        func.__dashboard_decorator_params__ = (args, kwargs)
        return func
    return decorator

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
    
    # Type annotations for attributes provided by the inheriting class
    if TYPE_CHECKING:
        config: Config
        log: logging.Logger
        bot: Red
    description = "Yet Another Logging Cog - Comprehensive Discord event logging with dashboard integration"
    version = "3.0.0"
    author = "YALC Team"
    repo = "https://github.com/your-repo/YALC"
    support = "https://discord.gg/your-support"
    icon = "https://cdn-icons-png.flaticon.com/512/928/928797.png"

    # Required bot attribute for Red-Web-Dashboard
    bot: Red

    # Dashboard page decorator is defined at module level
    
    # Pages are automatically detected by dashboard_page decorators

    @commands.Cog.listener()
    async def on_dashboard_cog_add(self, dashboard_cog: commands.Cog) -> None:
        """Register this cog as a third party with the Dashboard when dashboard cog is loaded."""
        dashboard_cog.rpc.third_parties_handler.add_third_party(self)
    # Add an about page method that might be expected
    @dashboard_page(name="stats", description="YALC Statistics: View logging statistics and activity.", methods=("GET",), is_owner=False)
    async def dashboard_stats(self, user: discord.User, guild: discord.Guild, **kwargs) -> typing.Dict[str, typing.Any]:
        """Statistics page for YALC dashboard."""
        # Get stats from config if available
        stats = {}
        if hasattr(self, 'config') and hasattr(self.config, 'guild'):
            try:
                stats = await self.config.guild(guild).stats.get_raw() or {}
            except Exception:
                stats = {}
        
        # Mock stats for demonstration
        total_events = stats.get("total_events", 0)
        events_today = stats.get("events_today", 0)
        most_active_channel = stats.get("most_active_channel", "N/A")
        
        source = f"""
        <div class="stats-dashboard">
            <h2>📊 YALC Statistics for {guild.name}</h2>
            
            <div class="stats-grid">
                <div class="stat-card">
                    <h3>Total Events Logged</h3>
                    <p class="stat-number">{total_events:,}</p>
                </div>
                
                <div class="stat-card">
                    <h3>Events Today</h3>
                    <p class="stat-number">{events_today}</p>
                </div>
                
                <div class="stat-card">
                    <h3>Most Active Channel</h3>
                    <p class="stat-text">{most_active_channel}</p>
                </div>
                
                <div class="stat-card">
                    <h3>Status</h3>
                    <p class="stat-status">{'✅ Active' if hasattr(self, 'config') else '❌ Inactive'}</p>
                </div>
            </div>
            
            <div class="chart-section">
                <h3>Event Activity</h3>
                <p>📈 Event logging is {'enabled' if hasattr(self, 'config') else 'disabled'} for this server.</p>
            </div>
        </div>
        
        <style>
        .stats-dashboard {{
            padding: 1rem;
        }}
        .stats-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 1rem;
            margin: 1rem 0;
        }}
        .stat-card {{
            background: #f8f9fa;
            padding: 1rem;
            border-radius: 8px;
            text-align: center;
            border-left: 4px solid #007bff;
        }}
        .stat-number {{
            font-size: 2rem;
            font-weight: bold;
            color: #007bff;
            margin: 0.5rem 0;
        }}
        .stat-text {{
            font-size: 1.1rem;
            color: #495057;
            margin: 0.5rem 0;
        }}
        .stat-status {{
            font-size: 1.1rem;
            margin: 0.5rem 0;
        }}
        .chart-section {{
            background: white;
            padding: 1rem;
            border-radius: 8px;
            margin-top: 1rem;
            border: 1px solid #dee2e6;
        }}
        </style>
        """
        return {
            "status": 0,
            "web_content": {"source": source},
        }

    @dashboard_page(name="events", description="YALC Event Configuration: Configure which events to log.", methods=("GET", "POST"), is_owner=False)
    async def dashboard_events(self, user: discord.User, guild: discord.Guild, **kwargs) -> typing.Dict[str, typing.Any]:
        """Event configuration page for YALC dashboard."""
        import wtforms
        
        # Get current event settings
        current_events = {}
        if hasattr(self, 'config') and hasattr(self.config, 'guild'):
            try:
                current_events = await self.config.guild(guild).events.get_raw() or {}
            except Exception:
                current_events = {}
        
        # Get available events from the main cog
        available_events = getattr(self, 'event_descriptions', {
            'message_delete': ('🗑️', 'Message Deletions'),
            'message_edit': ('✏️', 'Message Edits'),
            'member_join': ('👋', 'Member Joins'),
            'member_leave': ('👋', 'Member Leaves'),
            'voice_join': ('🔊', 'Voice Channel Joins'),
            'voice_leave': ('🔇', 'Voice Channel Leaves'),
            'role_create': ('➕', 'Role Creation'),
            'role_delete': ('➖', 'Role Deletion'),
            'channel_create': ('📝', 'Channel Creation'),
            'channel_delete': ('🗑️', 'Channel Deletion'),
        })
        
        class EventForm(kwargs["Form"]):
            def __init__(self):
                super().__init__(prefix="yalc_events_form_")
                
                # Create checkboxes for each event type
                for event_key, (emoji, description) in available_events.items():
                    field_name = f"event_{event_key}"
                    current_value = current_events.get(event_key, False)
                    setattr(self, field_name, wtforms.BooleanField(
                        f"{emoji} {description}",
                        default=current_value
                    ))
                
                self.submit = wtforms.SubmitField("Save Event Settings")

        form = EventForm()
        
        if form.validate_on_submit():
            try:
                # Save event settings
                new_events = {}
                for event_key in available_events.keys():
                    field_name = f"event_{event_key}"
                    if hasattr(form, field_name):
                        new_events[event_key] = getattr(form, field_name).data
                
                if hasattr(self, 'config') and hasattr(self.config, 'guild'):
                    await self.config.guild(guild).events.set(new_events)
                
                return {
                    "status": 0,
                    "notifications": [{"message": "Event settings saved successfully!", "category": "success"}],
                    "redirect_url": kwargs["request_url"],
                }
            except Exception as e:
                return {
                    "status": 0,
                    "notifications": [{"message": f"Error saving settings: {e}", "category": "error"}],
                }
        
        # Render form HTML
        form_html = """
        <div class="events-config">
            <h2>🎯 Event Logging Configuration</h2>
            <p>Select which events you want YALC to log in this server.</p>
            
            <form method="POST" class="event-form">
        """
        
        for field_name, field in form._fields.items():
            if field.type == 'BooleanField' and not field_name.startswith('csrf') and field_name != 'submit':
                checked = ' checked="checked"' if field.data else ''
                form_html += f"""
                <div class="event-option">
                    <label class="event-label">
                        <input type="checkbox" name="{field_name}" value="y"{checked}>
                        <span class="event-text">{field.label.text}</span>
                    </label>
                </div>
                """
        
        form_html += """
                <div class="form-actions">
                    <input type="submit" value="Save Event Settings" class="btn btn-primary">
                </div>
            </form>
        </div>
        
        <style>
        .events-config {
            padding: 1rem;
        }
        .event-form {
            background: white;
            padding: 1.5rem;
            border-radius: 8px;
            border: 1px solid #dee2e6;
        }
        .event-option {
            margin-bottom: 1rem;
            padding: 0.75rem;
            background: #f8f9fa;
            border-radius: 6px;
            border-left: 3px solid #007bff;
        }
        .event-label {
            display: flex;
            align-items: center;
            cursor: pointer;
            font-weight: 500;
        }
        .event-label input {
            margin-right: 0.75rem;
            transform: scale(1.2);
        }
        .event-text {
            font-size: 1rem;
        }
        .form-actions {
            margin-top: 1.5rem;
            text-align: center;
        }
        .btn {
            padding: 0.75rem 1.5rem;
            border: none;
            border-radius: 6px;
            cursor: pointer;
            font-size: 1rem;
            font-weight: 500;
        }
        .btn-primary {
            background: #007bff;
            color: white;
        }
        .btn-primary:hover {
            background: #0056b3;
        }
        </style>
        """
        
        return {
            "status": 0,
            "web_content": {"source": form_html, "form": form},
        }

    @dashboard_page(name="about", description="YALC About: Information about the cog.", methods=("GET",), is_owner=False)
    async def dashboard_about(self, user: discord.User, **kwargs) -> typing.Dict[str, typing.Any]:
        """About page for YALC dashboard."""
        source = f"""
        <div class="about-section">
            <h2>About YALC</h2>
            <p><strong>Version:</strong> {self.version}</p>
            <p><strong>Author:</strong> {self.author}</p>
            <p><strong>Description:</strong> {self.description}</p>
            <p><strong>Repository:</strong> <a href="{self.repo}" target="_blank">{self.repo}</a></p>
            <p><strong>Support:</strong> <a href="{self.support}" target="_blank">{self.support}</a></p>
        </div>
        <style>
        .about-section {{
            padding: 2rem;
            background: #f8f9fa;
            border-radius: 8px;
            margin: 1rem 0;
        }}
        .about-section h2 {{
            color: #495057;
            margin-bottom: 1rem;
        }}
        .about-section p {{
            margin-bottom: 0.5rem;
        }}
        .about-section a {{
            color: #007bff;
            text-decoration: none;
        }}
        .about-section a:hover {{
            text-decoration: underline;
        }}
        </style>
        """
        return {
            "status": 0,
            "web_content": {"source": source},
        }


    # Dashboard page methods with proper decorator parameters
    @dashboard_page(name=None, description="YALC Dashboard: Manage and view YALC features.", methods=("GET", "POST"), is_owner=True)
    async def dashboard_home(self, user: discord.User, **kwargs) -> typing.Dict[str, typing.Any]:
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

    @dashboard_page()
    async def dashboard_guild(self, user: discord.User, guild: discord.Guild, **kwargs) -> typing.Dict[str, typing.Any]:
        """Guild-specific YALC dashboard page."""
        return {
            "status": 0,
            "web_content": {
                "source": '<h4>YALC Dashboard: Guild "{{ guild.name }}" ({{ guild.id }})</h4>',
                "guild": guild,
            },
        }

    @dashboard_page()
    async def dashboard_settings(self, user: discord.User, guild: discord.Guild, **kwargs) -> typing.Dict[str, typing.Any]:
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