"""Red-Web-Dashboard integration."""

from __future__ import annotations

import html
import json
import logging
from typing import TYPE_CHECKING, Any, Callable

from redbot.core import commands

if TYPE_CHECKING:
    import discord

log = logging.getLogger("red.taakoscogs.flipper.dashboard")


def dashboard_page(*args, **kwargs):
    """Dashboard page decorator compatible with Red-Web-Dashboard."""

    def decorator(func: Callable):
        func.__dashboard_decorator_params__ = (args, kwargs)
        return func

    return decorator


class DashboardIntegration:
    """Conservative dashboard integration for cogs without custom web controls."""

    @commands.Cog.listener()
    async def on_dashboard_cog_add(self, dashboard_cog: commands.Cog) -> None:
        """Register the cog as a Red-Web-Dashboard third party."""
        handler = dashboard_cog.rpc.third_parties_handler
        try:
            handler.add_third_party(self, overwrite=True)
        except TypeError:
            handler.add_third_party(self)

    @dashboard_page(
        name=None,
        description="View this cog's current server configuration and commands.",
        methods=("GET",),
    )
    async def dashboard_page(
        self,
        user: discord.User,
        guild: discord.Guild,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Render a read-only dashboard page."""
        if not await self._dashboard_can_manage(user, guild):
            return {
                "status": 1,
                "error_title": "Insufficient Permissions",
                "error_message": (
                    "You need Manage Server, Red admin, or bot owner access."
                ),
            }

        try:
            source = await self._dashboard_source(guild)
        except Exception as error:
            log.exception("Dashboard render failed for %s.",
                          self.qualified_name)
            return {
                "status": 1,
                "error_title": "Dashboard Error",
                "error_message": f"Could not render dashboard page: {error}",
            }

        return {
            "status": 0,
            "web_content": {
                "source": source,
                "expanded": True,
            },
        }

    async def _dashboard_can_manage(
        self,
        user: discord.User,
        guild: discord.Guild,
    ) -> bool:
        member = guild.get_member(user.id)
        is_owner = user.id in getattr(self.bot, "owner_ids", set())
        is_admin = member is not None and await self.bot.is_admin(member)
        return bool(
            is_owner
            or is_admin
            or (member is not None and member.guild_permissions.manage_guild),
        )

    async def _dashboard_source(self, guild: discord.Guild) -> str:
        cog_name = html.escape(self.qualified_name)
        config = await self._dashboard_guild_config(guild)
        commands_html = self._dashboard_commands_html()
        config_html = self._dashboard_config_html(config)

        return f"""
<section class="third-party-dashboard">
  <h2>{cog_name}</h2>
  <p>This dashboard page confirms the cog is registered with Red-Web-Dashboard.</p>
  <h3>Commands</h3>
  {commands_html}
  <h3>Current Server Config</h3>
  {config_html}
</section>
"""

    async def _dashboard_guild_config(
        self,
        guild: discord.Guild,
    ) -> dict[str, Any] | None:
        config = getattr(self, "config", None) or getattr(
            self, "_config", None)
        if config is None:
            return None
        guild_config = getattr(config, "guild", None)
        if guild_config is None:
            return None
        return await guild_config(guild).all()

    def _dashboard_commands_html(self) -> str:
        commands_list = sorted(
            command.qualified_name
            for command in self.walk_commands()
            if not command.hidden
        )
        if not commands_list:
            return "<p>No visible commands were found for this cog.</p>"
        items = "\n".join(
            f"<li><code>{html.escape(command)}</code></li>" for command in commands_list
        )
        return f"<ul>{items}</ul>"

    @staticmethod
    def _dashboard_config_html(config: dict[str, Any] | None) -> str:
        if config is None:
            return "<p>This cog does not store per-server config.</p>"
        dumped = json.dumps(config, indent=2, sort_keys=True, default=str)
        return f"<pre><code>{html.escape(dumped)}</code></pre>"
