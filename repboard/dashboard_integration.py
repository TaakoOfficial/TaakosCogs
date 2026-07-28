# ruff: noqa: E501
"""Purpose-built dashboard for RepBoard."""

from __future__ import annotations

import html
import logging
from typing import TYPE_CHECKING, Any, Callable

from redbot.core import commands

if TYPE_CHECKING:
    import discord

log = logging.getLogger("red.taakoscogs.repboard.dashboard")


def dashboard_page(*args, **kwargs):
    def decorator(func: Callable):
        func.__dashboard_decorator_params__ = (args, kwargs)
        return func

    return decorator


class DashboardIntegration:
    """RepBoard policy, channel, and limit controls."""

    @commands.Cog.listener()
    async def on_dashboard_cog_add(self, dashboard_cog: commands.Cog) -> None:
        handler = dashboard_cog.rpc.third_parties_handler
        try:
            handler.add_third_party(self, overwrite=True)
        except TypeError:
            handler.add_third_party(self)

    @dashboard_page(name=None, description="Configure reputation rules and channels.", methods=("GET", "POST"))
    async def dashboard_page(self, user: discord.User, guild: discord.Guild, **kwargs: Any):
        if not await self._rep_can_manage(user, guild):
            return {"status": 1, "error_title": "Insufficient Permissions", "error_message": "Manage Server is required."}
        notices = []
        if kwargs.get("method", "GET").upper() == "POST":
            form = self._rep_form(kwargs)
            try:
                await self._rep_save(guild, form)
            except (commands.CommandError, ValueError) as error:
                notices.append({"message": str(error), "category": "error"})
            else:
                notices.append({"message": "RepBoard settings saved.", "category": "success"})
        settings = await self.config.guild(guild).all()
        source = self._rep_source(guild, settings, self._rep_csrf(kwargs))
        return {"status": 0, "notifications": notices, "web_content": {"source": source, "expanded": True}}

    async def _rep_save(self, guild, form):
        board_id = self._rep_channel(guild, form, "board_channel_id")
        log_id = self._rep_channel(guild, form, "log_channel_id")
        cooldown_minutes = self._rep_int(form, "cooldown_minutes", 0, 1440)
        daily_limit = self._rep_int(form, "daily_limit", 0, 100)
        minimum = self._rep_int(form, "min_reason_length", 0, 200)
        maximum = self._rep_int(form, "max_reason_length", 1, self.MAX_REASON_LENGTH)
        if minimum > maximum:
            raise commands.BadArgument("Minimum reason length cannot exceed the maximum.")
        conf = self.config.guild(guild)
        await conf.enabled.set(self._rep_checked(form, "enabled"))
        await conf.board_channel_id.set(board_id)
        await conf.log_channel_id.set(log_id)
        await conf.cooldown_seconds.set(cooldown_minutes * 60)
        await conf.daily_limit.set(daily_limit)
        await conf.require_reason.set(self._rep_checked(form, "require_reason"))
        await conf.min_reason_length.set(minimum)
        await conf.max_reason_length.set(maximum)
        await conf.allow_bots.set(self._rep_checked(form, "allow_bots"))
        await conf.allow_self_rep.set(self._rep_checked(form, "allow_self_rep"))

    def _rep_source(self, guild, settings, csrf):
        board = self._rep_channel_options(guild, settings.get("board_channel_id"))
        logs = self._rep_channel_options(guild, settings.get("log_channel_id"))
        active_records = sum(1 for item in settings.get("records", {}).values() if item.get("active", True))
        members = len(settings.get("stats", {}))
        return f"""
<section class="rep-dash"><style>
.rep-dash .card{{border:1px solid rgba(127,127,127,.3);border-radius:.65rem;padding:1rem;margin-bottom:1rem}}
.rep-dash .grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:1rem}}
.rep-dash label{{display:flex;flex-direction:column;gap:.3rem}}.rep-dash .check{{flex-direction:row;align-items:center}}
.rep-dash input,.rep-dash select{{padding:.55rem;border:1px solid rgba(127,127,127,.35);border-radius:.35rem;background:var(--background,#202225);color:var(--text,#fff)}}
.rep-dash .check input{{width:auto}}.rep-dash .stat{{font-size:1.4rem;font-weight:700}}
</style><h2>RepBoard</h2><p>Shape how members recognize each other in <strong>{html.escape(guild.name)}</strong>.</p>
<div class="grid"><div class="card"><span class="stat">{active_records:,}</span><br>active reputation records</div>
<div class="card"><span class="stat">{members:,}</span><br>members with reputation</div></div>
<form method="POST" class="card">{csrf}<div class="grid">
<label class="check"><input type="checkbox" name="enabled"{self._rep_mark(settings.get("enabled"))}> Enable reputation giving</label>
<label>Public board channel<select name="board_channel_id">{board}</select></label>
<label>Staff log channel<select name="log_channel_id">{logs}</select></label>
<label>Cooldown (minutes)<input type="number" name="cooldown_minutes" min="0" max="1440" value="{int(settings.get("cooldown_seconds", 0)) // 60}"></label>
<label>Daily limit (0 = unlimited)<input type="number" name="daily_limit" min="0" max="100" value="{int(settings.get("daily_limit", 5))}"></label>
<label class="check"><input type="checkbox" name="require_reason"{self._rep_mark(settings.get("require_reason"))}> Require a reason</label>
<label>Minimum reason length<input type="number" name="min_reason_length" min="0" max="200" value="{int(settings.get("min_reason_length", 0))}"></label>
<label>Maximum reason length<input type="number" name="max_reason_length" min="1" max="{self.MAX_REASON_LENGTH}" value="{int(settings.get("max_reason_length", self.MAX_REASON_LENGTH))}"></label>
<label class="check"><input type="checkbox" name="allow_bots"{self._rep_mark(settings.get("allow_bots"))}> Allow reputation for bots</label>
<label class="check"><input type="checkbox" name="allow_self_rep"{self._rep_mark(settings.get("allow_self_rep"))}> Allow self-reputation</label>
</div><button class="btn btn-primary">Save RepBoard Settings</button></form></section>"""

    async def _rep_can_manage(self, user, guild):
        member = guild.get_member(user.id)
        return bool(
            user.id in getattr(self.bot, "owner_ids", set())
            or (member and await self.bot.is_admin(member))
            or (member and member.guild_permissions.manage_guild),
        )

    @staticmethod
    def _rep_form(kwargs):
        data = kwargs.get("data") or {}
        return (data.get("form") or data.get("json") or {}) if isinstance(data, dict) else data

    @staticmethod
    def _rep_value(form, key, default=""):
        value = form.get(key, default) if hasattr(form, "get") else default
        if isinstance(value, (list, tuple)):
            value = value[0] if value else default
        return default if value is None else str(value)

    @classmethod
    def _rep_checked(cls, form, key):
        return cls._rep_value(form, key).lower() in {"1", "true", "on", "yes"}

    @classmethod
    def _rep_int(cls, form, key, minimum, maximum):
        try:
            value = int(cls._rep_value(form, key))
        except ValueError as error:
            raise commands.BadArgument(f"{key.replace('_', ' ')} must be a number.") from error
        if not minimum <= value <= maximum:
            raise commands.BadArgument(f"{key.replace('_', ' ')} must be {minimum}–{maximum}.")
        return value

    @classmethod
    def _rep_channel(cls, guild, form, key):
        raw = cls._rep_value(form, key)
        if not raw:
            return None
        try:
            channel_id = int(raw)
        except ValueError as error:
            raise commands.BadArgument("Choose a valid text channel.") from error
        if guild.get_channel(channel_id) not in guild.text_channels:
            raise commands.BadArgument("Choose a valid text channel.")
        return channel_id

    @staticmethod
    def _rep_channel_options(guild, selected):
        return '<option value="">Not configured</option>' + "".join(
            f'<option value="{channel.id}"{" selected" if channel.id == selected else ""}>#{html.escape(channel.name)}</option>'
            for channel in guild.text_channels
        )

    @staticmethod
    def _rep_mark(value):
        return " checked" if value else ""

    @staticmethod
    def _rep_csrf(kwargs):
        token = kwargs.get("csrf_token")
        if not isinstance(token, (tuple, list)) or len(token) != 2:
            return ""
        return f'<input type="hidden" name="csrf_token" value="{html.escape(str(token[1]), quote=True)}">'
