# ruff: noqa: E501
"""Purpose-built dashboard for OpsRoom."""

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

    @dashboard_page(name=None, description="Configure incident response channels and inspect status.", methods=("GET", "POST"))
    async def dashboard_page(self, user: discord.User, guild: discord.Guild, **kwargs: Any):
        if not await self._op_can_manage(user, guild):
            return {"status": 1, "error_title": "Insufficient Permissions", "error_message": "Manage Server is required."}
        notices = []
        if kwargs.get("method", "GET").upper() == "POST":
            form = self._op_form(kwargs)
            try:
                await self._op_save(guild, form)
            except (commands.CommandError, ValueError) as error:
                notices.append({"message": str(error), "category": "error"})
            else:
                notices.append({"message": "OpsRoom settings saved.", "category": "success"})
        settings = await self.config.guild(guild).all()
        active = sum(item.get("status") != "resolved" for item in settings["incidents"].values())
        source = f"""<section class="op"><style>{self._op_css()}</style><h2>OpsRoom</h2><p>Incident response for <strong>{html.escape(guild.name)}</strong>.</p><div class="grid"><div class="card"><b>{active}</b><br>active incidents</div><div class="card"><b>{len(settings["incidents"])}</b><br>total incidents</div></div><form method="POST" class="card">{self._op_csrf(kwargs)}<div class="grid"><label>Incident category<select name="category_id">{self._op_options(guild.categories, settings["category_id"], "Server root")}</select></label><label>Archive category<select name="archive_category_id">{self._op_options(guild.categories, settings["archive_category_id"], "Do not move")}</select></label><label>Response role<select name="response_role_id">{self._op_options(guild.roles, settings["response_role_id"], "Manage Channels only", "@")}</select></label><label>Stakeholder update channel<select name="update_channel_id">{self._op_options(guild.text_channels, settings["update_channel_id"], "Disabled", "#")}</select></label></div><button class="btn btn-primary">Save OpsRoom Settings</button></form></section>"""
        return {"status": 0, "notifications": notices, "web_content": {"source": source, "expanded": True}}

    async def _op_save(self, guild, form):
        conf = self.config.guild(guild)
        await conf.category_id.set(self._op_id(guild, form, "category_id", "category"))
        await conf.archive_category_id.set(self._op_id(guild, form, "archive_category_id", "category"))
        await conf.response_role_id.set(self._op_id(guild, form, "response_role_id", "role"))
        await conf.update_channel_id.set(self._op_id(guild, form, "update_channel_id", "text"))

    async def _op_can_manage(self, user, guild):
        member = guild.get_member(user.id)
        return bool(
            user.id in getattr(self.bot, "owner_ids", set())
            or (member and await self.bot.is_admin(member))
            or (member and member.guild_permissions.manage_guild)
        )

    @staticmethod
    def _op_form(kwargs):
        data = kwargs.get("data") or {}
        return (data.get("form") or data.get("json") or {}) if isinstance(data, dict) else data

    @staticmethod
    def _op_value(form, key):
        value = form.get(key, "") if hasattr(form, "get") else ""
        return (value[0] if value else "") if isinstance(value, (list, tuple)) else str(value or "")

    @classmethod
    def _op_id(cls, guild, form, key, kind):
        raw = cls._op_value(form, key)
        if not raw:
            return None
        try:
            item_id = int(raw)
        except ValueError as error:
            raise commands.BadArgument("Choose a valid Discord item.") from error
        item = guild.get_role(item_id) if kind == "role" else guild.get_channel(item_id)
        if not item:
            raise commands.BadArgument("Choose a valid Discord item.")
        return item_id

    @staticmethod
    def _op_options(items, selected, empty, prefix=""):
        return f'<option value="">{empty}</option>' + "".join(
            f'<option value="{item.id}"{" selected" if item.id == selected else ""}>{prefix}{html.escape(item.name)}</option>'
            for item in items
            if getattr(item, "name", None)
        )

    @staticmethod
    def _op_csrf(kwargs):
        token = kwargs.get("csrf_token")
        return (
            ""
            if not isinstance(token, (tuple, list)) or len(token) != 2
            else f'<input type="hidden" name="csrf_token" value="{html.escape(str(token[1]), quote=True)}">'
        )

    @staticmethod
    def _op_css():
        return ".op .card{border:1px solid rgba(127,127,127,.3);border-radius:.65rem;padding:1rem;margin-bottom:1rem}.op .grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(210px,1fr));gap:1rem}.op label{display:flex;flex-direction:column;gap:.3rem}.op select{padding:.55rem;background:var(--background,#202225);color:var(--text,#fff);border:1px solid rgba(127,127,127,.35);border-radius:.35rem}"
