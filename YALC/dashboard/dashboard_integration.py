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
        self.config = Config.get_conf(
            self, identifier=1234567890, force_registration=True
        )
        default_guild = {
            "enable_logging": True,
            "log_channel": None,
            "custom_message": "Logging enabled by YALC.",
        }
        self.config.register_guild(**default_guild)

    @commands.Cog.listener()
    async def on_dashboard_cog_add(self, dashboard_cog: commands.Cog) -> None:
        """
        Register this cog as a dashboard third party when the dashboard cog is loaded.
        """
        dashboard_cog.rpc.third_parties_handler.add_third_party(self)

    # ABOUT PAGE
    @dashboard_page(
        name="about",
        description="Information about the YALC cog.",
        methods=("GET",),
        is_owner=False,
    )
    async def dashboard_about(
        self, user: discord.User, **kwargs
    ) -> typing.Dict[str, typing.Any]:
        """About page for YALC dashboard."""
        html_content = f"""
        <div style="padding: 1em;">
            <h2>{self.name} v{self.version}</h2>
            <p>{self.description}</p>
            <p><b>Author:</b> {self.author}</p>
            <p><b>Repo:</b> <a href="{self.repo}" target="_blank">{self.repo}</a></p>
            <p><b>Support:</b> <a href="{self.support}" target="_blank">{self.support}</a></p>
            <img src="{self.icon}" width="64" height="64"/>
        </div>
        """
        return {"status": 0, "web_content": {"source": html_content}}

    # SETTINGS PAGE
    @dashboard_page(
        name="settings",
        description="Configure YALC settings.",
        methods=("GET", "POST"),
        is_owner=True,
    )
    async def dashboard_settings(
        self, user: discord.User, guild_id: int, **kwargs
    ) -> typing.Dict[str, typing.Any]:
        """Settings page for YALC dashboard."""
        guild = self.bot.get_guild(guild_id)
        if not guild:
            return {"status": 1, "web_content": {"error": "Invalid guild."}}

        # Handle POST (update settings)
        if kwargs.get("method") == "POST":
            data = kwargs.get("data", {})
            await self.config.guild(guild).enable_logging.set(
                bool(data.get("enable_logging", True))
            )
            await self.config.guild(guild).log_channel.set(data.get("log_channel"))
            await self.config.guild(guild).custom_message.set(
                data.get("custom_message", "Logging enabled by YALC.")
            )

        # GET (fetch current settings)
        enable_logging = await self.config.guild(guild).enable_logging()
        log_channel = await self.config.guild(guild).log_channel()
        custom_message = await self.config.guild(guild).custom_message()

        html_content = f"""
        <div style="padding: 1em;">
            <h2>YALC Settings for {guild.name}</h2>
            <form method="POST">
                <label>
                    Enable Logging:
                    <input type="checkbox" name="enable_logging" {'checked' if enable_logging else ''}/>
                </label><br/><br/>
                <label>
                    Log Channel ID:
                    <input type="text" name="log_channel" value="{log_channel or ''}"/>
                </label><br/><br/>
                <label>
                    Custom Message:
                    <input type="text" name="custom_message" value="{custom_message}"/>
                </label><br/><br/>
                <button type="submit">Save</button>
            </form>
        </div>
        """
        return {
            "status": 0,
            "web_content": {
                "source": html_content,
                "enable_logging": enable_logging,
                "log_channel": log_channel,
                "custom_message": custom_message,
            },
        }

    def yalcdash_settings(self) -> typing.Dict[str, typing.Any]:
        """
        Expose YALC config fields as dashboard widgets.
        This schema helps the dashboard auto-render inputs.
        """
        return {
            "enable_logging": {
                "type": "boolean",
                "label": "Enable Logging",
                "default": True,
            },
            "log_channel": {
                "type": "text",
                "label": "Log Channel ID",
                "default": None,
            },
            "custom_message": {
                "type": "text",
                "label": "Custom Message",
                "default": "Logging enabled by YALC.",
            },
        }
