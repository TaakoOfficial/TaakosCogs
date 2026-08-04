# ruff: noqa: E501
"""Purpose-built dashboard for EventCheckin."""

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

    @dashboard_page(name=None, description="Configure attendance windows and inspect events.", methods=("GET", "POST"))
    async def dashboard_page(self, user: discord.User, guild: discord.Guild, **kwargs: Any):
        if not await self._ec_can_manage(user, guild):
            return {"status": 1, "error_title": "Insufficient Permissions", "error_message": "Manage Server is required."}
        notices = []
        if kwargs.get("method", "GET").upper() == "POST":
            form = self._ec_form(kwargs)
            try:
                await self._ec_save(guild, form)
            except (commands.CommandError, ValueError) as error:
                notices.append({"message": str(error), "category": "error"})
            else:
                notices.append({"message": "EventCheckin settings saved.", "category": "success"})
        settings = await self.config.guild(guild).all()
        open_count = sum(item.get("status") == "open" for item in settings["events"].values())
        checkins = sum(
            sum(bool(record.get("checked_in_at")) for record in item.get("attendees", {}).values())
            for item in settings["events"].values()
        )
        source = f"""<section class="ec"><style>{self._ec_css()}</style><h2>EventCheckin</h2><p>Registration and attendance policy for <strong>{html.escape(guild.name)}</strong>.</p><div class="grid"><div class="card"><b>{open_count}</b><br>open events</div><div class="card"><b>{len(settings["events"])}</b><br>events retained</div><div class="card"><b>{checkins}</b><br>recorded check-ins</div></div><form method="POST" class="card">{self._ec_csrf(kwargs)}<div class="grid"><label>Reminder minutes before<input type="number" min="0" max="10080" name="reminder_minutes" value="{settings["reminder_minutes"]}"></label><label>Check-in opens minutes before<input type="number" min="0" max="10080" name="checkin_early_minutes" value="{settings["checkin_early_minutes"]}"></label><label>Check-in closes minutes after<input type="number" min="0" max="10080" name="checkin_late_minutes" value="{settings["checkin_late_minutes"]}"></label><label>Attendance log channel<select name="log_channel_id">{self._ec_options(guild.text_channels, settings["log_channel_id"])}</select></label></div><button class="btn btn-primary">Save EventCheckin Settings</button></form></section>"""
        return {"status": 0, "notifications": notices, "web_content": {"source": source, "expanded": True}}

    async def _ec_save(self, guild, form):
        conf = self.config.guild(guild)
        await conf.reminder_minutes.set(self._ec_int(form, "reminder_minutes", 0, 10080))
        await conf.checkin_early_minutes.set(self._ec_int(form, "checkin_early_minutes", 0, 10080))
        await conf.checkin_late_minutes.set(self._ec_int(form, "checkin_late_minutes", 0, 10080))
        raw = self._ec_value(form, "log_channel_id")
        channel_id = int(raw) if raw else None
        if channel_id and guild.get_channel(channel_id) not in guild.text_channels:
            raise commands.BadArgument("Choose a valid log channel.")
        await conf.log_channel_id.set(channel_id)

    async def _ec_can_manage(self, user, guild):
        member = guild.get_member(user.id)
        return bool(
            user.id in getattr(self.bot, "owner_ids", set())
            or (member and await self.bot.is_admin(member))
            or (member and member.guild_permissions.manage_guild)
        )

    @staticmethod
    def _ec_form(kwargs):
        data = kwargs.get("data") or {}
        return (data.get("form") or data.get("json") or {}) if isinstance(data, dict) else data

    @staticmethod
    def _ec_value(form, key):
        value = form.get(key, "") if hasattr(form, "get") else ""
        return (value[0] if value else "") if isinstance(value, (list, tuple)) else str(value or "")

    @classmethod
    def _ec_int(cls, form, key, minimum, maximum):
        try:
            value = int(cls._ec_value(form, key))
        except ValueError as error:
            raise commands.BadArgument(f"{key.replace('_', ' ')} must be a number.") from error
        if not minimum <= value <= maximum:
            raise commands.BadArgument(f"{key.replace('_', ' ')} must be {minimum}–{maximum}.")
        return value

    @staticmethod
    def _ec_options(items, selected):
        return '<option value="">Disabled</option>' + "".join(
            f'<option value="{item.id}"{" selected" if item.id == selected else ""}>#{html.escape(item.name)}</option>'
            for item in items
        )

    @staticmethod
    def _ec_csrf(kwargs):
        token = kwargs.get("csrf_token")
        return (
            ""
            if not isinstance(token, (tuple, list)) or len(token) != 2
            else f'<input type="hidden" name="csrf_token" value="{html.escape(str(token[1]), quote=True)}">'
        )

    @staticmethod
    def _ec_css():
        return ".ec .card{border:1px solid rgba(127,127,127,.3);border-radius:.65rem;padding:1rem;margin-bottom:1rem}.ec .grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(210px,1fr));gap:1rem}.ec label{display:flex;flex-direction:column;gap:.3rem}.ec input,.ec select{padding:.55rem;background:var(--background,#202225);color:var(--text,#fff);border:1px solid rgba(127,127,127,.35);border-radius:.35rem}"
