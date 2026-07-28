"""Read-only Red-Web-Dashboard integration for DeepDelve."""

from __future__ import annotations

import html
import json
from typing import TYPE_CHECKING, Any, Callable

from redbot.core import commands

if TYPE_CHECKING:
    import discord


def dashboard_page(*args, **kwargs):
    """Provide the metadata expected by Red-Web-Dashboard."""

    def decorator(func: Callable):
        func.__dashboard_decorator_params__ = (args, kwargs)
        return func

    return decorator


class DashboardIntegration:
    """Expose settings and commands without exposing player save data."""

    @commands.Cog.listener()
    async def on_dashboard_cog_add(self, dashboard_cog: commands.Cog) -> None:
        """Register this cog with Red-Web-Dashboard."""
        handler = dashboard_cog.rpc.third_parties_handler
        try:
            handler.add_third_party(self, overwrite=True)
        except TypeError:
            handler.add_third_party(self)

    @dashboard_page(
        name=None,
        description="View DeepDelve settings and commands.",
        methods=("GET",),
    )
    async def dashboard_page(
        self,
        user: discord.User,
        guild: discord.Guild,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Render a safe, read-only server page."""
        del kwargs
        member = guild.get_member(user.id)
        permitted = bool(
            user.id in getattr(self.bot, "owner_ids", set())
            or member is not None
            and (member.guild_permissions.manage_guild or await self.bot.is_admin(member)),
        )
        if not permitted:
            return {
                "status": 1,
                "error_title": "Insufficient Permissions",
                "error_message": "You need Manage Server, Red admin, or bot owner access.",
            }
        config = await self.config.guild(guild).all()
        commands_list = sorted(command.qualified_name for command in self.walk_commands() if not command.hidden)
        command_items = "\n".join(f"<li><code>{html.escape(command)}</code></li>" for command in commands_list)
        config_text = html.escape(json.dumps(config, indent=2, sort_keys=True))
        source = f"""
<section class="third-party-dashboard">
  <h2>DeepDelve</h2>
  <p>Persistent dungeon crawler settings for {html.escape(guild.name)}.</p>
  <h3>Commands</h3>
  <ul>{command_items}</ul>
  <h3>Server Settings</h3>
  <pre><code>{config_text}</code></pre>
  <p>Player profiles are intentionally excluded from this page.</p>
</section>
"""
        return {"status": 0, "web_content": {"source": source, "expanded": True}}
