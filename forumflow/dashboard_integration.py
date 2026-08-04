# ruff: noqa: E501
"""Purpose-built dashboard for ForumFlow."""

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

    @dashboard_page(name=None, description="Configure forum workflow policy and view queues.", methods=("GET", "POST"))
    async def dashboard_page(self, user: discord.User, guild: discord.Guild, **kwargs: Any):
        if not await self._dash_can_manage(user, guild):
            return {"status": 1, "error_title": "Insufficient Permissions", "error_message": "Manage Server is required."}
        notices = []
        if kwargs.get("method", "GET").upper() == "POST":
            form = self._dash_form(kwargs)
            try:
                await self._dash_save(guild, form)
            except (commands.CommandError, ValueError) as error:
                notices.append({"message": str(error), "category": "error"})
            else:
                notices.append({"message": "ForumFlow settings saved.", "category": "success"})
        settings = await self.config.guild(guild).all()
        states = {}
        for record in settings["records"].values():
            state = record.get("state", "unknown")
            states[state] = states.get(state, 0) + 1
        source = f"""
<section class="ff-dash"><style>{self._dash_css()}</style><h2>ForumFlow</h2><p>Workflow policy for <strong>{html.escape(guild.name)}</strong>.</p>
<div class="grid"><div class="card"><b>{len(settings["forum_ids"])}</b><br>managed forums</div><div class="card"><b>{len(settings["records"])}</b><br>tracked posts</div><div class="card"><b>{html.escape(", ".join(f"{k}: {v}" for k, v in sorted(states.items())) or "No activity")}</b><br>queue states</div></div>
<form method="POST" class="card">{self._dash_csrf(kwargs)}<div class="grid">
<label>Staff role<select name="staff_role_id">{self._dash_options(guild.roles, settings["staff_role_id"], "Manage Threads only")}</select></label>
<label>Log channel<select name="log_channel_id">{self._dash_options(guild.text_channels, settings["log_channel_id"], "Disabled", "#")}</select></label>
<label>Stale after (hours)<input type="number" min="1" max="8760" name="stale_hours" value="{settings["stale_hours"]}"></label>
<label class="check"><input type="checkbox" name="auto_controls"{self._dash_mark(settings["auto_controls"])}> Post persistent controls</label>
</div><button class="btn btn-primary">Save ForumFlow Settings</button></form><div class="card"><p>Add or remove managed forums from Discord with <code>[p]forumflow addforum</code> and <code>[p]forumflow removeforum</code>.</p></div></section>"""
        return {"status": 0, "notifications": notices, "web_content": {"source": source, "expanded": True}}

    async def _dash_save(self, guild, form):
        conf = self.config.guild(guild)
        await conf.staff_role_id.set(self._dash_id(guild, form, "staff_role_id", "role"))
        await conf.log_channel_id.set(self._dash_id(guild, form, "log_channel_id", "text"))
        await conf.stale_hours.set(self._dash_int(form, "stale_hours", 1, 8760))
        await conf.auto_controls.set(self._dash_checked(form, "auto_controls"))

    async def _dash_can_manage(self, user, guild):
        member = guild.get_member(user.id)
        return bool(
            user.id in getattr(self.bot, "owner_ids", set())
            or (member and await self.bot.is_admin(member))
            or (member and member.guild_permissions.manage_guild)
        )

    @staticmethod
    def _dash_form(kwargs):
        data = kwargs.get("data") or {}
        return (data.get("form") or data.get("json") or {}) if isinstance(data, dict) else data

    @staticmethod
    def _dash_value(form, key, default=""):
        value = form.get(key, default) if hasattr(form, "get") else default
        return (value[0] if value else default) if isinstance(value, (list, tuple)) else default if value is None else str(value)

    @classmethod
    def _dash_checked(cls, form, key):
        return cls._dash_value(form, key).lower() in {"1", "true", "on", "yes"}

    @classmethod
    def _dash_int(cls, form, key, minimum, maximum):
        try:
            value = int(cls._dash_value(form, key))
        except ValueError as error:
            raise commands.BadArgument(f"{key.replace('_', ' ')} must be a number.") from error
        if not minimum <= value <= maximum:
            raise commands.BadArgument(f"{key.replace('_', ' ')} must be {minimum}–{maximum}.")
        return value

    @classmethod
    def _dash_id(cls, guild, form, key, kind):
        raw = cls._dash_value(form, key)
        if not raw:
            return None
        try:
            item_id = int(raw)
        except ValueError as error:
            raise commands.BadArgument(f"Choose a valid {kind}.") from error
        item = guild.get_role(item_id) if kind == "role" else guild.get_channel(item_id)
        valid = item in guild.roles if kind == "role" else item in guild.text_channels
        if not valid:
            raise commands.BadArgument(f"Choose a valid {kind}.")
        return item_id

    @staticmethod
    def _dash_options(items, selected, empty, prefix="@"):
        return f'<option value="">{empty}</option>' + "".join(
            f'<option value="{item.id}"{" selected" if item.id == selected else ""}>{prefix}{html.escape(item.name)}</option>'
            for item in items
            if getattr(item, "name", None)
        )

    @staticmethod
    def _dash_mark(value):
        return " checked" if value else ""

    @staticmethod
    def _dash_csrf(kwargs):
        token = kwargs.get("csrf_token")
        return (
            ""
            if not isinstance(token, (tuple, list)) or len(token) != 2
            else f'<input type="hidden" name="csrf_token" value="{html.escape(str(token[1]), quote=True)}">'
        )

    @staticmethod
    def _dash_css():
        return ".ff-dash .card{border:1px solid rgba(127,127,127,.3);border-radius:.65rem;padding:1rem;margin-bottom:1rem}.ff-dash .grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(210px,1fr));gap:1rem}.ff-dash label{display:flex;flex-direction:column;gap:.3rem}.ff-dash .check{flex-direction:row;align-items:center}.ff-dash input,.ff-dash select{padding:.55rem;border:1px solid rgba(127,127,127,.35);border-radius:.35rem;background:var(--background,#202225);color:var(--text,#fff)}"
