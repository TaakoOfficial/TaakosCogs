# ruff: noqa: E501
"""Purpose-built dashboard for AccessReview."""

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

    @dashboard_page(name=None, description="Configure reviewers and inspect access campaigns.", methods=("GET", "POST"))
    async def dashboard_page(self, user: discord.User, guild: discord.Guild, **kwargs: Any):
        if not await self._ar_can_manage(user, guild):
            return {"status": 1, "error_title": "Insufficient Permissions", "error_message": "Manage Server is required."}
        notices = []
        if kwargs.get("method", "GET").upper() == "POST":
            form = self._ar_form(kwargs)
            try:
                await self._ar_save(guild, form)
            except (commands.CommandError, ValueError) as error:
                notices.append({"message": str(error), "category": "error"})
            else:
                notices.append({"message": "AccessReview settings saved.", "category": "success"})
        settings = await self.config.guild(guild).all()
        open_count = sum(item.get("status") == "open" for item in settings["campaigns"].values())
        pending = sum(
            sum(entry.get("decision") == "pending" for entry in item.get("entries", {}).values())
            for item in settings["campaigns"].values()
            if item.get("status") == "open"
        )
        source = f"""<section class="ar"><style>{self._ar_css()}</style><h2>AccessReview</h2><p>Periodic role certification for <strong>{html.escape(guild.name)}</strong>.</p><div class="grid"><div class="card"><b>{open_count}</b><br>open campaigns</div><div class="card"><b>{pending}</b><br>pending decisions</div><div class="card"><b>{len(settings["campaigns"])}</b><br>campaigns retained</div></div><form method="POST" class="card">{self._ar_csrf(kwargs)}<div class="grid"><label>Reviewer role<select name="reviewer_role_id">{self._ar_options(guild.roles, settings["reviewer_role_id"], "Manage Roles only", "@")}</select></label><label>Evidence log channel<select name="log_channel_id">{self._ar_options(guild.text_channels, settings["log_channel_id"], "Disabled", "#")}</select></label></div><button class="btn btn-primary">Save AccessReview Settings</button></form><div class="card"><p>Campaign decisions and enforcement remain command-controlled. Enforcement always requires the explicit <code>REMOVE</code> confirmation.</p></div></section>"""
        return {"status": 0, "notifications": notices, "web_content": {"source": source, "expanded": True}}

    async def _ar_save(self, guild, form):
        conf = self.config.guild(guild)
        await conf.reviewer_role_id.set(self._ar_id(guild, form, "reviewer_role_id", True))
        await conf.log_channel_id.set(self._ar_id(guild, form, "log_channel_id", False))

    async def _ar_can_manage(self, user, guild):
        member = guild.get_member(user.id)
        return bool(
            user.id in getattr(self.bot, "owner_ids", set())
            or (member and await self.bot.is_admin(member))
            or (member and member.guild_permissions.manage_guild)
        )

    @staticmethod
    def _ar_form(kwargs):
        data = kwargs.get("data") or {}
        return (data.get("form") or data.get("json") or {}) if isinstance(data, dict) else data

    @staticmethod
    def _ar_value(form, key):
        value = form.get(key, "") if hasattr(form, "get") else ""
        return (value[0] if value else "") if isinstance(value, (list, tuple)) else str(value or "")

    @classmethod
    def _ar_id(cls, guild, form, key, role):
        raw = cls._ar_value(form, key)
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
    def _ar_options(items, selected, empty, prefix):
        return f'<option value="">{empty}</option>' + "".join(
            f'<option value="{item.id}"{" selected" if item.id == selected else ""}>{prefix}{html.escape(item.name)}</option>'
            for item in items
            if getattr(item, "name", None)
        )

    @staticmethod
    def _ar_csrf(kwargs):
        token = kwargs.get("csrf_token")
        return (
            ""
            if not isinstance(token, (tuple, list)) or len(token) != 2
            else f'<input type="hidden" name="csrf_token" value="{html.escape(str(token[1]), quote=True)}">'
        )

    @staticmethod
    def _ar_css():
        return ".ar .card{border:1px solid rgba(127,127,127,.3);border-radius:.65rem;padding:1rem;margin-bottom:1rem}.ar .grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(210px,1fr));gap:1rem}.ar label{display:flex;flex-direction:column;gap:.3rem}.ar select{padding:.55rem;background:var(--background,#202225);color:var(--text,#fff);border:1px solid rgba(127,127,127,.35);border-radius:.35rem}"
