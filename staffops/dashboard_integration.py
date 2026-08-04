# ruff: noqa: E501
"""Purpose-built dashboard for StaffOps."""

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

    @dashboard_page(name=None, description="Configure staff operations and inspect coverage.", methods=("GET", "POST"))
    async def dashboard_page(self, user: discord.User, guild: discord.Guild, **kwargs: Any):
        if not await self._so_can_manage(user, guild):
            return {"status": 1, "error_title": "Insufficient Permissions", "error_message": "Manage Server is required."}
        notices = []
        if kwargs.get("method", "GET").upper() == "POST":
            form = self._so_form(kwargs)
            try:
                await self._so_save(guild, form)
            except (commands.CommandError, ValueError) as error:
                notices.append({"message": str(error), "category": "error"})
            else:
                notices.append({"message": "StaffOps settings saved.", "category": "success"})
        settings = await self.config.guild(guild).all()
        source = f"""<section class="so"><style>{self._so_css()}</style><h2>StaffOps</h2><p>Coverage and policy for <strong>{html.escape(guild.name)}</strong>.</p>
<div class="grid"><div class="card"><b>{len(settings["active_shifts"])}</b><br>active shifts</div><div class="card"><b>{len(settings["on_call"])}</b><br>on-call members</div><div class="card"><b>{sum(x.get("status") == "pending" for x in settings["leave_requests"].values())}</b><br>pending leave requests</div></div>
<form method="POST" class="card">{self._so_csrf(kwargs)}<div class="grid"><label>Staff role<select name="staff_role_id">{self._so_options(guild.roles, settings["staff_role_id"], "Manage Server only", "@")}</select></label><label>Log channel<select name="log_channel_id">{self._so_options(guild.text_channels, settings["log_channel_id"], "Disabled", "#")}</select></label><label>Maximum shift hours<input type="number" min="1" max="168" name="max_shift_hours" value="{settings["max_shift_hours"]}"></label></div><button class="btn btn-primary">Save StaffOps Settings</button></form></section>"""
        return {"status": 0, "notifications": notices, "web_content": {"source": source, "expanded": True}}

    async def _so_save(self, guild, form):
        conf = self.config.guild(guild)
        await conf.staff_role_id.set(self._so_id(guild, form, "staff_role_id", True))
        await conf.log_channel_id.set(self._so_id(guild, form, "log_channel_id", False))
        await conf.max_shift_hours.set(self._so_int(form, "max_shift_hours", 1, 168))

    async def _so_can_manage(self, user, guild):
        member = guild.get_member(user.id)
        return bool(
            user.id in getattr(self.bot, "owner_ids", set())
            or (member and await self.bot.is_admin(member))
            or (member and member.guild_permissions.manage_guild)
        )

    @staticmethod
    def _so_form(kwargs):
        data = kwargs.get("data") or {}
        return (data.get("form") or data.get("json") or {}) if isinstance(data, dict) else data

    @staticmethod
    def _so_value(form, key):
        value = form.get(key, "") if hasattr(form, "get") else ""
        return (value[0] if value else "") if isinstance(value, (list, tuple)) else str(value or "")

    @classmethod
    def _so_int(cls, form, key, minimum, maximum):
        try:
            value = int(cls._so_value(form, key))
        except ValueError as error:
            raise commands.BadArgument(f"{key.replace('_', ' ')} must be a number.") from error
        if not minimum <= value <= maximum:
            raise commands.BadArgument(f"{key.replace('_', ' ')} must be {minimum}–{maximum}.")
        return value

    @classmethod
    def _so_id(cls, guild, form, key, role):
        raw = cls._so_value(form, key)
        if not raw:
            return None
        try:
            item_id = int(raw)
        except ValueError as error:
            raise commands.BadArgument("Choose a valid Discord item.") from error
        item = guild.get_role(item_id) if role else guild.get_channel(item_id)
        if not item or (not role and item not in guild.text_channels):
            raise commands.BadArgument("Choose a valid Discord item.")
        return item_id

    @staticmethod
    def _so_options(items, selected, empty, prefix):
        return f'<option value="">{empty}</option>' + "".join(
            f'<option value="{item.id}"{" selected" if item.id == selected else ""}>{prefix}{html.escape(item.name)}</option>'
            for item in items
            if getattr(item, "name", None)
        )

    @staticmethod
    def _so_csrf(kwargs):
        token = kwargs.get("csrf_token")
        return (
            ""
            if not isinstance(token, (tuple, list)) or len(token) != 2
            else f'<input type="hidden" name="csrf_token" value="{html.escape(str(token[1]), quote=True)}">'
        )

    @staticmethod
    def _so_css():
        return ".so .card{border:1px solid rgba(127,127,127,.3);border-radius:.65rem;padding:1rem;margin-bottom:1rem}.so .grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(210px,1fr));gap:1rem}.so label{display:flex;flex-direction:column;gap:.3rem}.so input,.so select{padding:.55rem;background:var(--background,#202225);color:var(--text,#fff);border:1px solid rgba(127,127,127,.35);border-radius:.35rem}"
