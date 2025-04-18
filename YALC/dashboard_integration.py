from redbot.core import commands
from redbot.core.bot import Red
import discord
import typing
import logging

try:
    from dashboard.rpc.thirdparties import dashboard_page
except ImportError:
    def dashboard_page(*args, **kwargs):
        def decorator(func):
            logging.warning("[YALC] WARNING: dashboard_page decorator fallback is being used. Dashboard integration will NOT work. Make sure the Dashboard cog is loaded before YALC.")
            return func
        return decorator

class DashboardIntegration:
    """Dashboard integration for YALC."""
    bot: Red

    @commands.Cog.listener()
    async def on_dashboard_cog_add(self, dashboard_cog: commands.Cog) -> None:
        """Register YALC as a third party with the dashboard when Dashboard cog loads."""
        if hasattr(dashboard_cog, "rpc") and hasattr(dashboard_cog.rpc, "third_parties_handler"):
            dashboard_cog.rpc.third_parties_handler.add_third_party(self)

    @dashboard_page(name=None, description="YALC Overview", methods=("GET",))
    async def dashboard_overview(self, user: discord.User = None, guild: discord.Guild = None, **kwargs) -> typing.Dict[str, typing.Any]:
        """Overview page for YALC in the dashboard."""
        html = """
        <h2>📝 YALC - Yet Another Logging Cog</h2>
        <p>This cog provides advanced server logging and moderation event tracking for your Discord server.</p>
        <ul>
            <li>Customizable event logging</li>
            <li>Per-channel configurations</li>
            <li>Ignore lists for users, roles, and channels</li>
            <li>Log retention management</li>
            <li>Rich embed formatting</li>
        </ul>
        <p>Use the <b>/yalc</b> commands in Discord to configure logging, or visit the server settings for more options.</p>
        """
        return {
            "status": 0,
            "web_content": {"source": html}
        }

    @dashboard_page(name="guild", description="YALC Guild Settings", methods=("GET",))
    async def dashboard_guild(self, guild: discord.Guild, **kwargs) -> typing.Dict[str, typing.Any]:
        """Show basic YALC settings for a guild."""
        html = f"""
        <h3>YALC Settings for: {guild.name}</h3>
        <p>Use <b>/yalc setup</b> in Discord to configure logging channels and events.</p>
        <p>For advanced options, use the Discord bot commands or contact your server admin.</p>
        """
        return {
            "status": 0,
            "web_content": {"source": html}
        }
