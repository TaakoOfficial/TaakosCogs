# ruff: noqa: E501
"""Purpose-built dashboard for LinkSentinel."""

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

    @dashboard_page(name=None, description="Configure link checks and inspect failures.", methods=("GET", "POST"))
    async def dashboard_page(self, user: discord.User, guild: discord.Guild, **kwargs: Any):
        if not await self._ls_can_manage(user, guild):
            return {"status": 1, "error_title": "Insufficient Permissions", "error_message": "Manage Server is required."}
        notices = []
        if kwargs.get("method", "GET").upper() == "POST":
            form = self._ls_form(kwargs)
            try:
                await self._ls_save(guild, form)
            except (commands.CommandError, ValueError) as error:
                notices.append({"message": str(error), "category": "error"})
            else:
                notices.append({"message": "LinkSentinel settings saved.", "category": "success"})
        settings = await self.config.guild(guild).all()
        failed = sum(item.get("status") == "failed" for item in settings["links"].values())
        last_scan = f"<t:{settings['last_scan_at']}:R>" if settings["last_scan_at"] else "Never"
        source = f"""<section class="ls"><style>{self._ls_css()}</style><h2>LinkSentinel</h2><p>Resource health for <strong>{html.escape(guild.name)}</strong>.</p><div class="grid"><div class="card"><b>{len(settings["links"])}</b><br>monitored links</div><div class="card"><b>{failed}</b><br>failing links</div><div class="card"><b>{last_scan}</b><br>last scan</div></div><form method="POST" class="card">{self._ls_csrf(kwargs)}<div class="grid"><label>Alert channel<select name="alert_channel_id">{self._ls_options(guild.text_channels, settings["alert_channel_id"])}</select></label><label>Interval hours<input type="number" min="1" max="168" name="interval_hours" value="{settings["interval_hours"]}"></label><label>HTTP timeout seconds<input type="number" min="3" max="60" name="timeout_seconds" value="{settings["timeout_seconds"]}"></label><label>TLS warning days<input type="number" min="1" max="365" name="tls_warning_days" value="{settings["tls_warning_days"]}"></label></div><button class="btn btn-primary">Save LinkSentinel Settings</button></form><div class="card"><p>Add, discover, remove, or scan links from Discord commands. Network scans are intentionally not triggered by loading this page.</p></div></section>"""
        return {"status": 0, "notifications": notices, "web_content": {"source": source, "expanded": True}}

    async def _ls_save(self, guild, form):
        conf = self.config.guild(guild)
        raw = self._ls_value(form, "alert_channel_id")
        channel_id = int(raw) if raw else None
        if channel_id and guild.get_channel(channel_id) not in guild.text_channels:
            raise commands.BadArgument("Choose a valid alert channel.")
        await conf.alert_channel_id.set(channel_id)
        await conf.interval_hours.set(self._ls_int(form, "interval_hours", 1, 168))
        await conf.timeout_seconds.set(self._ls_int(form, "timeout_seconds", 3, 60))
        await conf.tls_warning_days.set(self._ls_int(form, "tls_warning_days", 1, 365))

    async def _ls_can_manage(self, user, guild):
        member = guild.get_member(user.id)
        return bool(
            user.id in getattr(self.bot, "owner_ids", set())
            or (member and await self.bot.is_admin(member))
            or (member and member.guild_permissions.manage_guild)
        )

    @staticmethod
    def _ls_form(kwargs):
        data = kwargs.get("data") or {}
        return (data.get("form") or data.get("json") or {}) if isinstance(data, dict) else data

    @staticmethod
    def _ls_value(form, key):
        value = form.get(key, "") if hasattr(form, "get") else ""
        return (value[0] if value else "") if isinstance(value, (list, tuple)) else str(value or "")

    @classmethod
    def _ls_int(cls, form, key, minimum, maximum):
        try:
            value = int(cls._ls_value(form, key))
        except ValueError as error:
            raise commands.BadArgument(f"{key.replace('_', ' ')} must be a number.") from error
        if not minimum <= value <= maximum:
            raise commands.BadArgument(f"{key.replace('_', ' ')} must be {minimum}–{maximum}.")
        return value

    @staticmethod
    def _ls_options(items, selected):
        return '<option value="">Disabled</option>' + "".join(
            f'<option value="{item.id}"{" selected" if item.id == selected else ""}>#{html.escape(item.name)}</option>'
            for item in items
        )

    @staticmethod
    def _ls_csrf(kwargs):
        token = kwargs.get("csrf_token")
        return (
            ""
            if not isinstance(token, (tuple, list)) or len(token) != 2
            else f'<input type="hidden" name="csrf_token" value="{html.escape(str(token[1]), quote=True)}">'
        )

    @staticmethod
    def _ls_css():
        return ".ls .card{border:1px solid rgba(127,127,127,.3);border-radius:.65rem;padding:1rem;margin-bottom:1rem}.ls .grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(210px,1fr));gap:1rem}.ls label{display:flex;flex-direction:column;gap:.3rem}.ls input,.ls select{padding:.55rem;background:var(--background,#202225);color:var(--text,#fff);border:1px solid rgba(127,127,127,.35);border-radius:.35rem}"
