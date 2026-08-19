# ruff: noqa: E501
"""Purpose-built dashboard for OperationsCenter."""

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

    @dashboard_page(name=None, description="Inspect operations integrations, audits, and retries.", methods=("GET", "POST"))
    async def dashboard_page(self, user: discord.User, guild: discord.Guild, **kwargs: Any):
        member = guild.get_member(user.id)
        if not (
            user.id in getattr(self.bot, "owner_ids", set())
            or (member and await self.bot.is_admin(member))
            or (member and member.guild_permissions.manage_guild)
        ):
            return {"status": 1, "error_title": "Insufficient Permissions", "error_message": "Manage Server is required."}
        conf = self.config.guild(guild)
        notices = []
        if kwargs.get("method", "GET").upper() == "POST":
            data = kwargs.get("data") or {}
            form = (data.get("form") or data.get("json") or {}) if isinstance(data, dict) else data
            raw = form.get("notify_failures", "") if hasattr(form, "get") else ""
            raw = raw[0] if isinstance(raw, (list, tuple)) and raw else raw
            await conf.notify_failures.set(str(raw).casefold() in {"1", "true", "on", "yes"})
            notices.append({"message": "OperationsCenter settings saved.", "category": "success"})
        settings = await conf.all()
        checked = " checked" if settings["notify_failures"] else ""
        loaded = ", ".join(html.escape(name) for name in self.MANAGED_COGS if self.bot.get_cog(name)) or "None"
        csrf = kwargs.get("csrf_token")
        csrf_html = (
            ""
            if not isinstance(csrf, (tuple, list)) or len(csrf) != 2
            else f'<input type="hidden" name="csrf_token" value="{html.escape(str(csrf[1]), quote=True)}">'
        )
        muted = ", ".join(html.escape(name) for name in settings["muted_sources"]) or "None"
        source = f'<section><h2>OperationsCenter</h2><p><b>Loaded:</b> {loaded}</p><p><b>{len(settings["audit_events"])}</b> retained audit events · <b>{len(settings["retry_queue"])}</b> queued retries · <b>{len(settings["notification_channels"])}</b> custom routes</p><p><b>Quiet integrations:</b> {muted}</p><form method="POST">{csrf_html}<label><input type="checkbox" name="notify_failures" value="1"{checked}> Notify configured operations channels when integrations fail</label><br><button class="btn btn-primary">Save Operations Settings</button></form><p>Use <code>operationscenter setup</code> in Discord to validate channel permissions and see guided partner-cog setup.</p></section>'
        return {"status": 0, "notifications": notices, "web_content": {"source": source, "expanded": True}}
