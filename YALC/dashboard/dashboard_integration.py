from redbot.core import commands
from redbot.core.bot import Red
import discord
import typing

# Dashboard page decorator for Red-Web-Dashboard third-party integration
def dashboard_page(*args, **kwargs):
    def decorator(func: typing.Callable):
        func.__dashboard_decorator_params__ = (args, kwargs)
        return func
    return decorator

class DashboardIntegration:
    """Dashboard integration mixin for YALC cog.
    
    This class provides the required interface for Red-Web-Dashboard
    third-party integrations. It's designed to be inherited from
    by the main cog class.
    """
    
    # Required attributes for Red-Web-Dashboard third-party integration
    name = "YALC"
    description = "Yet Another Logging Cog - Comprehensive Discord event logging with dashboard integration"
    version = "3.0.0"
    author = "YALC Team"
    repo = "https://github.com/your-repo/YALC"
    support = "https://discord.gg/your-support"
    icon = "https://cdn-icons-png.flaticon.com/512/928/928797.png"
    
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
            # Check if the dashboard cog has the required attributes
            if hasattr(dashboard_cog, 'rpc') and hasattr(dashboard_cog.rpc, 'third_parties_handler'):
                dashboard_cog.rpc.third_parties_handler.add_third_party(self)
                # Access log through the main cog instance
                if hasattr(self, 'log'):
                    self.log.info("Successfully registered YALC as a dashboard third party.")
                else:
                    print("YALC: Successfully registered as a dashboard third party.")
            else:
                if hasattr(self, 'log'):
                    self.log.warning("Dashboard cog found but missing required attributes for third-party integration.")
                else:
                    print("YALC: Dashboard cog found but missing required attributes for third-party integration.")
        except Exception as e:
            if hasattr(self, 'log'):
                self.log.error(f"Dashboard integration setup failed: {e}")
            else:
                print(f"YALC: Dashboard integration setup failed: {e}")

    @dashboard_page(
        name=None,
        description="YALC Dashboard: Manage and view YALC features.",
        methods=("GET", "POST"),
        is_owner=True
    )
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

        source = "{{ form|safe }}"

        return {
            "status": 0,
            "web_content": {"source": source, "form": form},
        }

    @dashboard_page(
        name="guild",
        description="YALC Guild Dashboard: View guild details.",
        methods=("GET",),
    )
    async def yalcdash_guild(self, user: discord.User, guild: discord.Guild, **kwargs) -> typing.Dict[str, typing.Any]:
        """Guild-specific YALC dashboard page."""
        return {
            "status": 0,
            "web_content": {
                "source": '<h4>YALC Dashboard: Guild "{{ guild.name }}" ({{ guild.id }})</h4>',
                "guild": guild,
            },
        }

    @dashboard_page(
        name="settings",
        description="YALC Settings Dashboard: Configure logging settings.",
        methods=("GET", "POST"),
        is_owner=False
    )
    async def yalcdash_settings(self, user: discord.User, guild: discord.Guild, **kwargs) -> typing.Dict[str, typing.Any]:
        """Settings configuration page for YALC."""
        import wtforms

        # Get current settings for this guild - access config through the main cog instance
        if hasattr(self, 'config'):
            current_settings = await self.config.guild(guild).all()
        else:
            current_settings = {}

        class SettingsForm(kwargs["Form"]):
            def __init__(self):
                super().__init__(prefix="yalc_settings_form_")
            
            # Create form fields based on available events
            # Note: event_descriptions is defined in the main cog class
            # We'll create a basic form for now, can be enhanced later
            submit: wtforms.SubmitField = wtforms.SubmitField("Save Settings")

        form: SettingsForm = SettingsForm()
        
        if form.validate_on_submit():
            # Update settings based on form submission
            try:
                # For now, just return success since we don't have dynamic form fields
                # This can be enhanced later to work with the actual event descriptions
                return {
                    "status": 0,
                    "notifications": [{"message": "Settings form submitted! (Enhanced form coming soon)", "category": "info"}],
                    "redirect_url": kwargs["request_url"],
                }
            except Exception as e:
                return {
                    "status": 0,
                    "notifications": [{"message": f"Error processing form: {e}", "category": "error"}],
                }

        source = """
        <h3>YALC Settings for {{ guild.name }}</h3>
        <p>Configure which events to log in this server.</p>
        {{ form|safe }}
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