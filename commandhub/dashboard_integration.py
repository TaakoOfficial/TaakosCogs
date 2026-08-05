"""Dashboard scaffold that delegates all mutations to CommandHub services."""

from __future__ import annotations

import html
from typing import TYPE_CHECKING, Any, Callable

from redbot.core import commands

if TYPE_CHECKING:
    import discord


def dashboard_page(*args: Any, **kwargs: Any) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        func.__dashboard_decorator_params__ = (args, kwargs)
        return func

    return decorator


class DashboardIntegration:
    @commands.Cog.listener()
    async def on_dashboard_cog_add(self, dashboard_cog: commands.Cog) -> None:
        handler = dashboard_cog.rpc.third_parties_handler
        try:
            handler.add_third_party(self, overwrite=True)
        except TypeError:
            handler.add_third_party(self)

    @dashboard_page(name=None, description="Configure command hubs.", methods=("GET",))
    async def dashboard_page(self, user: discord.User, guild: discord.Guild, **kwargs: Any) -> dict[str, Any]:
        member = guild.get_member(user.id)
        if not member or not (member.guild_permissions.manage_guild or user.id in self.bot.owner_ids):
            return {
                "status": 1,
                "error_title": "Insufficient Permissions",
                "error_message": "Manage Server is required.",
            }
        hubs = await self.list_hubs_service(guild.id)
        rows = (
            "".join(
                f"<tr><td><code>/{html.escape(hub.name)}</code></td><td>{html.escape(hub.title)}</td>"
                f"<td>{sum(len(category.commands) for category in hub.categories.values())}</td>"
                f"<td>{'Enabled' if hub.enabled else 'Disabled'}</td></tr>"
                for hub in hubs
            )
            or '<tr><td colspan="4">No hubs configured.</td></tr>'
        )
        source = (
            "<h2>CommandHub</h2><p>Hub inventory and sync state. Mutating dashboard routes can call the public "
            "CommandHub service methods documented in the cog README.</p><table class='table'><thead><tr>"
            f"<th>Command</th><th>Title</th><th>Commands</th><th>State</th></tr></thead><tbody>{rows}</tbody></table>"
        )
        return {"status": 0, "web_content": {"source": source, "expanded": True}}
