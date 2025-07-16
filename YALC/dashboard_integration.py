import typing
import discord
import logging
from typing import Optional, Dict, Any, List


import typing

def setup_dashboard_pages(cog):
    dashboard_page = getattr(cog, 'dashboard_page', None)
    if dashboard_page is None:
        raise RuntimeError("dashboard_page decorator not found on cog instance!")

    @dashboard_page(name=None, description="YALC Dashboard Home", methods=("GET",), is_owner=False)
    async def dashboard_home(self, user, **kwargs) -> typing.Dict[str, typing.Any]:
        source = '<h2>Welcome to the YALC Dashboard Integration!</h2>' \
                 '<p>This page is provided by the YALC cog. Use the navigation to explore available features.</p>'
        return {
            "status": 0,
            "web_content": {"source": source},
        }

    @dashboard_page(name="settings", description="Configure YALC settings for this guild", methods=("GET", "POST"), is_owner=False)
    async def dashboard_settings(self, user, guild, request: typing.Optional[dict] = None, **kwargs) -> typing.Dict[str, typing.Any]:
        config = cog.config.guild(guild)
        retention_days = await config.retention_days()
        use_embeds = await config.use_embeds()
        auto_archive_threads = await config.auto_archive_threads()
        source = f'''
        <h3>YALC Guild Settings</h3>
        <ul>
            <li>Retention Days: {retention_days}</li>
            <li>Use Embeds: {use_embeds}</li>
            <li>Auto Archive Threads: {auto_archive_threads}</li>
        </ul>
        '''
        return {
            "status": 0,
            "web_content": {"source": source},
        }

    @dashboard_page(name="about", description="About YALC", methods=("GET",), is_owner=False)
    async def dashboard_about(self, user, **kwargs) -> typing.Dict[str, typing.Any]:
        source = (
            "<h2>About YALC</h2>"
            "<p>YALC (Yet Another Logging Cog) is a comprehensive logging solution for Red-DiscordBot servers.</p>"
        )
        return {
            "status": 0,
            "web_content": {"source": source},
        }

    cog.dashboard_home = dashboard_home.__get__(cog)
    cog.dashboard_settings = dashboard_settings.__get__(cog)
    cog.dashboard_about = dashboard_about.__get__(cog)


