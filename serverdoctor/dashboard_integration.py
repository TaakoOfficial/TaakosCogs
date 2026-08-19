# ruff: noqa: E501
"""Purpose-built dashboard for ServerDoctor."""

from __future__ import annotations

import html
from typing import TYPE_CHECKING, Any, Callable

from redbot.core import commands

if TYPE_CHECKING:
    import discord


def dashboard_page(*args, **kwargs):
    def decorator(func: Callable):
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

    @dashboard_page(name=None, description="Inspect ServerDoctor results and scheduled change reporting.", methods=("GET",))
    async def dashboard_page(self, user: discord.User, guild: discord.Guild, **kwargs: Any):
        member = guild.get_member(user.id)
        if not (
            user.id in getattr(self.bot, "owner_ids", set())
            or (member and await self.bot.is_admin(member))
            or (member and member.guild_permissions.manage_guild)
        ):
            return {"status": 1, "error_title": "Insufficient Permissions", "error_message": "Manage Server is required."}
        data = await self.config.guild(guild).all()
        summary = data["last_summary"]
        counts = " · ".join(f"{html.escape(key)}: {value}" for key, value in sorted(summary.items())) or "No recorded findings"
        ignored = ", ".join(f"<code>{html.escape(code)}</code>" for code in data["ignored_codes"]) or "None"
        last_scan = f"<t:{data['last_scan_at']}:R>" if data["last_scan_at"] else "Never"
        schedule = (
            f"every {data['schedule_hours']} hour(s) in <#{data['report_channel_id']}>"
            if data["schedule_hours"] and data["report_channel_id"]
            else "disabled"
        )
        source = f'<section><h2>ServerDoctor</h2><p>Run scans from Discord so permission calculations use current guild state.</p><div class="card"><b>Last scan:</b> {last_scan}<br><b>Summary:</b> {counts}<br><b>Ignored codes:</b> {ignored}<br><b>Change reports:</b> {schedule}</div></section>'
        return {"status": 0, "web_content": {"source": source, "expanded": True}}
