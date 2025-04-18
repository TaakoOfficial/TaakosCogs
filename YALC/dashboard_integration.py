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
            logging.warning(
                "[YALC] WARNING: dashboard_page decorator fallback is being used. "
                "Dashboard integration will NOT work. Make sure the Dashboard cog is loaded before YALC."
            )
            return func
        return decorator

class DashboardIntegration:
    """Dashboard integration for YALC."""

    def __init__(self, cog):
        """Initialize dashboard integration with reference to main cog."""
        self.cog = cog
        self.bot = cog.bot

    @commands.Cog.listener()
    async def on_dashboard_cog_add(self, dashboard_cog: commands.Cog) -> None:
        """Register YALC as a third party with the dashboard when Dashboard cog loads."""
        if hasattr(dashboard_cog, "rpc") and hasattr(dashboard_cog.rpc, "third_parties_handler"):
            dashboard_cog.rpc.third_parties_handler.add_third_party(self)

    @dashboard_page(name="overview", description="YALC Overview", methods=("GET",))
    async def dashboard_overview(
        self,
        user: typing.Optional[discord.User] = None,
        guild: typing.Optional[discord.Guild] = None,
        **kwargs
    ) -> typing.Dict[str, typing.Any]:
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
        <p>Visit the settings page to configure logging options, or use <b>/yalc</b> commands in Discord.</p>
        """
        return {
            "status": 0,
            "web_content": {"source": html}
        }

    @dashboard_page(name="settings", description="YALC Settings", methods=("GET", "POST"))
    async def dashboard_settings(
        self,
        guild: typing.Optional[discord.Guild] = None,
        data: typing.Optional[dict] = None,
        **kwargs
    ) -> typing.Dict[str, typing.Any]:
        """Settings management page for YALC."""
        if not guild:
            return {"status": 1, "message": "This page requires a guild to be selected."}

        # Handle POST request to update settings
        if data:
            try:
                # Update events
                events_config = await self.cog.config.guild(guild).events()
                for event in self.cog.event_descriptions:
                    events_config[event] = data.get(f"event_{event}", False)
                await self.cog.config.guild(guild).events.set(events_config)

                # Update channel mappings
                channel_config = {}
                for event in self.cog.event_descriptions:
                    channel_id = data.get(f"channel_{event}")
                    if channel_id and channel_id.isdigit():
                        channel_config[event] = int(channel_id)
                await self.cog.config.guild(guild).event_channels.set(channel_config)

                # Update Tupperbox settings
                await self.cog.config.guild(guild).ignore_tupperbox.set(
                    data.get("ignore_tupperbox", True)
                )
                tupperbox_ids = [
                    id.strip() for id in data.get("tupperbox_ids", "").split(",")
                    if id.strip().isdigit()
                ]
                await self.cog.config.guild(guild).tupperbox_ids.set(tupperbox_ids)

                return {
                    "status": 0,
                    "message": "Settings updated successfully!",
                    "force_refresh": True
                }
            except Exception as e:
                return {"status": 1, "message": f"Failed to update settings: {str(e)}"}

        # Handle GET request to display settings
        try:
            settings = await self.cog.config.guild(guild).all()
            text_channels = [
                (c.id, c.name) for c in guild.text_channels
                if c.permissions_for(guild.me).send_messages
            ]

            html = """
            <h2>📝 YALC Settings</h2>
            <form method="POST" class="form-horizontal">
                <div class="row">
                    <div class="col-md-6">
                        <h3>Event Settings</h3>
                        <div class="card">
                            <div class="card-body">
            """

            # Add event toggles and channel selects
            for event, (emoji, desc) in self.cog.event_descriptions.items():
                current_channel = settings["event_channels"].get(event, "")
                is_enabled = settings["events"].get(event, False)
                html += f"""
                <div class="form-group">
                    <label>
                        <input type="checkbox" name="event_{event}" value="true"
                               {"checked" if is_enabled else ""}>
                        {emoji} {desc}
                    </label>
                    <select name="channel_{event}" class="form-control">
                        <option value="">Select Channel</option>
                """
                for cid, cname in text_channels:
                    html += f"""
                        <option value="{cid}" {"selected" if str(cid) == str(current_channel) else ""}>
                            #{cname}
                        </option>
                    """
                html += """
                    </select>
                </div>
                """

            html += """
                            </div>
                        </div>
                    </div>
                    <div class="col-md-6">
                        <h3>Tupperbox Settings</h3>
                        <div class="card">
                            <div class="card-body">
                                <div class="form-group">
                                    <label>
                                        <input type="checkbox" name="ignore_tupperbox" value="true"
                                               {"checked" if settings["ignore_tupperbox"] else ""}>
                                        Ignore Tupperbox Messages
                                    </label>
                                </div>
                                <div class="form-group">
                                    <label>Tupperbox Bot IDs (comma-separated)</label>
                                    <input type="text" class="form-control" name="tupperbox_ids"
                                           value="{','.join(settings['tupperbox_ids'])}">
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
                <div class="form-group mt-3">
                    <button type="submit" class="btn btn-primary">Save Settings</button>
                </div>
            </form>
            """

            return {
                "status": 0,
                "web_content": {"source": html}
            }

        except Exception as e:
            return {"status": 1, "message": f"Failed to load settings: {str(e)}"}

    @dashboard_page(name="guild", description="YALC Guild Settings", methods=("GET",))
    async def dashboard_guild(
        self,
        guild: typing.Optional[discord.Guild] = None,
        **kwargs
    ) -> typing.Dict[str, typing.Any]:
        """Show basic YALC settings for a guild."""
        html = f"""
        <h3>YALC Settings for: {guild.name if guild else 'Unknown Guild'}</h3>
        <p>Use <b>/yalc setup</b> in Discord to configure logging channels and events.</p>
        <p>For advanced options, use the Discord bot commands or contact your server admin.</p>
        """
        return {
            "status": 0,
            "web_content": {"source": html}
        }
