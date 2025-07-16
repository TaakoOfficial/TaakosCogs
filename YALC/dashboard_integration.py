import typing
import discord
import logging
from typing import Optional, Dict, Any, List


class DashboardIntegration:
    """Dashboard integration for YALC."""

    def __init__(self, cog):
        self.cog = cog
        self.bot = cog.bot

    @property
    def name(self) -> str:
        """The name of the third party."""
        return "YALC"

    @property
    def description(self) -> str:
        """The description of the third party."""
        return "Yet Another Logging Cog - Advanced server logging and moderation event tracking"

    @property
    def version(self) -> str:
        """The version of the third party."""
        return "3.1.1"

    @property
    def author(self) -> str:
        """The author of the third party."""
        return "Taako"

    @property
    def repo(self) -> str:
        """The repository URL of the third party."""
        return "https://github.com/TaakoTaco/Taako-Cogs"

    @property
    def support(self) -> str:
        """The support URL of the third party."""
        return "https://github.com/TaakoTaco/Taako-Cogs/issues"

    @property
    def icon(self) -> str:
        """The icon URL of the third party."""
        return "https://cdn-icons-png.flaticon.com/512/928/928797.png"

    def pages(self) -> List[Dict[str, Any]]:
        """Return the pages for the dashboard."""
        return [
            {
                "name": "overview",
                "title": "YALC Overview",
                "description": "View YALC features and capabilities",
                "icon": "📝",
                "methods": ["GET"],
                "function": self.dashboard_overview,
            },
            {
                "name": "settings",
                "title": "YALC Settings",
                "description": "Configure YALC logging settings",
                "icon": "⚙️",
                "methods": ["GET", "POST"],
                "function": self.dashboard_settings,
            },
            {
                "name": "about",
                "title": "About YALC",
                "description": "Information about YALC functionality",
                "icon": "ℹ️",
                "methods": ["GET"],
                "function": self.dashboard_about,
            },
            {
                "name": "test",
                "title": "Test Page",
                "description": "Test YALC dashboard integration",
                "icon": "🧪",
                "methods": ["GET"],
                "function": self.dashboard_test,
            },
        ]

    async def dashboard_overview(self, request, guild: Optional[discord.Guild] = None) -> Dict[str, Any]:
        """Overview page for YALC in the dashboard."""
        html = self._render_overview()
        return {"status": 200, "web_content": {"source": html}}

    async def dashboard_settings(self, request, guild: Optional[discord.Guild] = None) -> Dict[str, Any]:
        """Settings page for YALC in the dashboard."""
        if not guild:
            return {"status": 400, "message": "This page requires a guild to be selected."}
        
        if request.method == "POST":
            try:
                data = await request.post()
                await self._handle_settings_post(guild, data)
                return {"status": 200, "message": "Settings updated successfully!", "force_refresh": True}
            except Exception as e:
                logging.exception("Failed to update YALC settings via dashboard.")
                return {"status": 500, "message": f"Failed to update settings: {e}"}
        
        try:
            settings = await self.cog.config.guild(guild).all()
            text_channels = [
                (c.id, c.name) for c in guild.text_channels
                if c.permissions_for(guild.me).send_messages
            ]
            html = self._render_settings_form(settings, text_channels)
            return {"status": 200, "web_content": {"source": html}}
        except Exception as e:
            logging.exception("Failed to load YALC settings for dashboard.")
            return {"status": 500, "message": f"Failed to load settings: {e}"}

    async def dashboard_about(self, request, guild: Optional[discord.Guild] = None) -> Dict[str, Any]:
        """About page for YALC in the dashboard."""
        html = (
            "<h2>About YALC</h2>"
            "<p>YALC (Yet Another Logging Cog) is a comprehensive logging solution for Red-DiscordBot servers. "
            "It provides advanced event logging, moderation tracking, and a user-friendly dashboard for configuration.</p>"
            "<ul>"
            "<li>Supports both classic and slash commands</li>"
            "<li>Customizable event and channel settings</li>"
            "<li>Integration with Red Web Dashboard</li>"
            "<li>Easy to use and extend</li>"
            "</ul>"
            "<h3>Features</h3>"
            "<ul>"
            "<li>Message logging (delete, edit, bulk delete)</li>"
            "<li>Member events (join, leave, ban, unban, kick, timeout)</li>"
            "<li>Channel events (create, delete, update, threads)</li>"
            "<li>Role events (create, delete, update)</li>"
            "<li>Guild events (scheduled events, emoji updates)</li>"
            "<li>Advanced Tupperbox/proxy message filtering</li>"
            "<li>Comprehensive ignore lists</li>"
            "<li>Rich embed formatting</li>"
            "</ul>"
        )
        return {"status": 200, "web_content": {"source": html}}

    async def dashboard_test(self, request, guild: Optional[discord.Guild] = None) -> Dict[str, Any]:
        """A simple test page to verify dashboard integration."""
        html = (
            "<h2>YALC Test Page</h2>"
            "<p>If you see this, the integration is working correctly!</p>"
            "<div class='alert alert-success'>"
            "<strong>Success!</strong> YALC dashboard integration is functional."
            "</div>"
        )
        return {"status": 200, "web_content": {"source": html}}

    def _render_overview(self) -> str:
        """Render the overview HTML."""
        return (
            "<h2>📝 YALC - Yet Another Logging Cog</h2>"
            "<p>This cog provides advanced server logging and moderation event tracking for your Discord server.</p>"
            "<div class='row'>"
            "<div class='col-md-6'>"
            "<h3>Core Features</h3>"
            "<ul>"
            "<li>✅ Customizable event logging</li>"
            "<li>✅ Per-channel configurations</li>"
            "<li>✅ Ignore lists for users, roles, and channels</li>"
            "<li>✅ Log retention management</li>"
            "<li>✅ Rich embed formatting</li>"
            "<li>✅ Tupperbox/proxy message filtering</li>"
            "</ul>"
            "</div>"
            "<div class='col-md-6'>"
            "<h3>Supported Events</h3>"
            "<ul>"
            "<li>📝 Message events (delete, edit, bulk delete)</li>"
            "<li>👥 Member events (join, leave, ban, unban)</li>"
            "<li>📢 Channel events (create, delete, update)</li>"
            "<li>🎭 Role events (create, delete, update)</li>"
            "<li>⚙️ Guild events (settings, scheduled events)</li>"
            "<li>🧵 Thread events (create, delete, update)</li>"
            "</ul>"
            "</div>"
            "</div>"
            "<p>Visit the <a href='settings'>settings page</a> to configure logging options, or use <code>/yalc</code> commands in Discord.</p>"
        )

    def _render_settings_form(self, settings: dict, text_channels: List[tuple[int, str]]) -> str:
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
