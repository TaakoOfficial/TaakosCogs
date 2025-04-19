from redbot.core import commands
import discord
import logging
from dashboard.rpc.third_parties import dashboard_page

class DashboardIntegration:
    """Dashboard integration for YALC."""

    def __init__(self, cog):
        self.cog = cog
        self.bot = cog.bot

    @dashboard_page("overview", "YALC Overview", methods=("GET", "POST"))
    async def dashboard_overview(self, request, guild):
        html = self._render_overview()
        return {"status": 0, "web_content": {"source": html}}

    @dashboard_page("settings", "YALC Settings", methods=("GET", "POST"))
    async def dashboard_settings(self, request, guild):
        if not guild:
            return {"status": 1, "message": "This page requires a guild to be selected."}
        if request.method == "POST":
            data = await request.post()
            try:
                await self._handle_settings_post(guild, data)
                return {"status": 0, "message": "Settings updated successfully!", "force_refresh": True}
            except Exception as e:
                logging.exception("Failed to update YALC settings via dashboard.")
                return {"status": 1, "message": f"Failed to update settings: {e}"}
        try:
            settings = await self.cog.config.guild(guild).all()
            text_channels = [
                (c.id, c.name) for c in guild.text_channels
                if c.permissions_for(guild.me).send_messages
            ]
            html = self._render_settings_form(settings, text_channels)
            return {"status": 0, "web_content": {"source": html}}
        except Exception as e:
            logging.exception("Failed to load YALC settings for dashboard.")
            return {"status": 1, "message": f"Failed to load settings: {e}"}

    @dashboard_page("about", "About YALC", methods=("GET", "POST") )
    async def dashboard_about(self, request, guild):
        """About page for YALC in the dashboard."""
        html = (
            "<h2>About YALC</h2>"
            "<p>YALC (Yet Another Logging Cog) is a comprehensive logging solution for Red-DiscordBot servers. "
            "It provides advanced event logging, moderation tracking, and a user-friendly dashboard for configuration.</p>"
            "<ul>"
            "<li>Supports both classic and slash commands</li>"
            "<li>Customizable event and channel settings</li>"
            "<li>Integration with AAA3A's Dashboard</li>"
            "<li>Easy to use and extend</li>"
            "</ul>"
        )
        return {"status": 0, "web_content": {"source": html}}

    def _render_overview(self) -> str:
        """Render the overview HTML."""
        return (
            "<h2>📝 YALC - Yet Another Logging Cog</h2>"
            "<p>This cog provides advanced server logging and moderation event tracking for your Discord server.</p>"
            "<ul>"
            "<li>Customizable event logging</li>"
            "<li>Per-channel configurations</li>"
            "<li>Ignore lists for users, roles, and channels</li>"
            "<li>Log retention management</li>"
            "<li>Rich embed formatting</li>"
            "</ul>"
            "<p>Visit the settings page to configure logging options, or use <b>/yalc</b> commands in Discord.</p>"
        )

    def _render_settings_form(self, settings: dict, text_channels: list[tuple[int, str]]) -> str:
        """Render the settings form HTML."""
        html = [
            '<h2>📝 YALC Settings</h2>',
            '<form method="POST" class="form-horizontal">',
            '<div class="row">',
            '<div class="col-md-6">',
            '<h3>Event Settings</h3>',
            '<div class="card"><div class="card-body">'
        ]
        for event, (emoji, desc) in self.cog.event_descriptions.items():
            current_channel = settings["event_channels"].get(event, "")
            is_enabled = settings["events"].get(event, False)
            html.append(f'<div class="form-group">')
            html.append(f'<label>')
            html.append(f'<input type="checkbox" name="event_{event}" value="true" {"checked" if is_enabled else ""}> {emoji} {desc}')
            html.append('</label>')
            html.append(f'<select name="channel_{event}" class="form-control">')
            html.append('<option value="">Select Channel</option>')
            for cid, cname in text_channels:
                selected = "selected" if str(cid) == str(current_channel) else ""
                html.append(f'<option value="{cid}" {selected}>#{cname}</option>')
            html.append('</select></div>')
        html.append('</div></div></div>')
        html.append('<div class="col-md-6">')
        html.append('<h3>Tupperbox Settings</h3>')
        html.append('<div class="card"><div class="card-body">')
        html.append('<div class="form-group">')
        html.append(f'<label><input type="checkbox" name="ignore_tupperbox" value="true" {"checked" if settings["ignore_tupperbox"] else ""}> Ignore Tupperbox Messages</label>')
        html.append('</div>')
        html.append('<div class="form-group">')
        html.append('<label>Tupperbox Bot IDs (comma-separated)</label>')
        html.append(f'<input type="text" class="form-control" name="tupperbox_ids" value="{",".join(settings["tupperbox_ids"])}">')
        html.append('</div></div></div></div></div>')
        html.append('<div class="form-group mt-3">')
        html.append('<button type="submit" class="btn btn-primary">Save Settings</button>')
        html.append('</div></form>')
        return "\n".join(html)

    async def _handle_settings_post(self, guild: discord.Guild, data: dict) -> None:
        """Handle POST data from the dashboard settings form."""
        events_config = await self.cog.config.guild(guild).events()
        for event in self.cog.event_descriptions:
            events_config[event] = data.get(f"event_{event}") == "true"
        await self.cog.config.guild(guild).events.set(events_config)
        channel_config = {}
        for event in self.cog.event_descriptions:
            channel_id = data.get(f"channel_{event}")
            if channel_id and channel_id.isdigit():
                channel_config[event] = int(channel_id)
        await self.cog.config.guild(guild).event_channels.set(channel_config)
        ignore_tupperbox = data.get("ignore_tupperbox") == "true"
        await self.cog.config.guild(guild).ignore_tupperbox.set(ignore_tupperbox)
        tupperbox_ids = [id.strip() for id in data.get("tupperbox_ids", "").split(",") if id.strip().isdigit()]
        await self.cog.config.guild(guild).tupperbox_ids.set(tupperbox_ids)

    @dashboard_page("test", "YALC Test Page", methods=("GET", "POST"))
    async def dashboard_test(self, request, guild):
        """A simple test page to verify dashboard integration."""
        return {"status": 0, "web_content": {"source": "<h2>YALC Test Page</h2><p>If you see this, the integration works!</p>"}}

    def get_dashboard_views(self) -> list:
        return [self.dashboard_overview, self.dashboard_settings, self.dashboard_about, self.dashboard_test]

    @property
    def qualified_name(self) -> str:
        return "YALC"

    def on_dashboard_cog_add(self, dashboard_cog) -> None:
        """Called when the dashboard cog is loaded and this third party is registered."""
        for view in self.get_dashboard_views():
            dashboard_cog.rpc.third_parties_handler.add_page(self, view)
