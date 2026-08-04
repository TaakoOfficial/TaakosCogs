# ruff: noqa: E501
"""Purpose-built dashboard for CommunityDigest."""

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

    @dashboard_page(name=None, description="Configure digest schedule and privacy settings.", methods=("GET", "POST"))
    async def dashboard_page(self, user: discord.User, guild: discord.Guild, **kwargs: Any):
        if not await self._cd_can_manage(user, guild):
            return {"status": 1, "error_title": "Insufficient Permissions", "error_message": "Manage Server is required."}
        notices = []
        if kwargs.get("method", "GET").upper() == "POST":
            form = self._cd_form(kwargs)
            try:
                await self._cd_save(guild, form)
            except (commands.CommandError, ValueError) as error:
                notices.append({"message": str(error), "category": "error"})
            else:
                notices.append({"message": "CommunityDigest settings saved.", "category": "success"})
        settings = await self.config.guild(guild).all()
        source = f"""<section class="cd"><style>{self._cd_css()}</style><h2>CommunityDigest</h2><p>Provider-free recaps for <strong>{html.escape(guild.name)}</strong>. Message content is read only while generating a digest and is not retained.</p><div class="grid"><div class="card"><b>{len(settings["source_ids"])}</b><br>sources</div><div class="card"><b>{settings["run_count"]}</b><br>digests published</div><div class="card"><b>{"Enabled" if settings["enabled"] else "Paused"}</b><br>scheduler</div></div><form method="POST" class="card">{self._cd_csrf(kwargs)}<div class="grid"><label class="check"><input type="checkbox" name="enabled"{self._cd_mark(settings["enabled"])}> Automatic posting</label><label>Destination<select name="destination_id">{self._cd_options(guild.text_channels, settings["destination_id"])}</select></label><label>Interval hours<input type="number" min="1" max="720" name="interval_hours" value="{settings["interval_hours"]}"></label><label>Lookback hours<input type="number" min="1" max="720" name="lookback_hours" value="{settings["lookback_hours"]}"></label><label>Minimum activity<input type="number" min="1" max="10000" name="min_messages" value="{settings["min_messages"]}"></label><label class="check"><input type="checkbox" name="include_bots"{self._cd_mark(settings["include_bots"])}> Include bot messages</label></div><button class="btn btn-primary">Save Digest Settings</button></form><div class="card"><p>Manage source channels and run previews from Discord with <code>[p]communitydigest source</code> and <code>[p]communitydigest preview</code>.</p></div></section>"""
        return {"status": 0, "notifications": notices, "web_content": {"source": source, "expanded": True}}

    async def _cd_save(self, guild, form):
        conf = self.config.guild(guild)
        raw = self._cd_value(form, "destination_id")
        channel_id = int(raw) if raw else None
        if channel_id and guild.get_channel(channel_id) not in guild.text_channels:
            raise commands.BadArgument("Choose a valid destination.")
        await conf.destination_id.set(channel_id)
        await conf.enabled.set(self._cd_checked(form, "enabled"))
        await conf.include_bots.set(self._cd_checked(form, "include_bots"))
        await conf.interval_hours.set(self._cd_int(form, "interval_hours", 1, 720))
        await conf.lookback_hours.set(self._cd_int(form, "lookback_hours", 1, 720))
        await conf.min_messages.set(self._cd_int(form, "min_messages", 1, 10000))

    async def _cd_can_manage(self, user, guild):
        member = guild.get_member(user.id)
        return bool(
            user.id in getattr(self.bot, "owner_ids", set())
            or (member and await self.bot.is_admin(member))
            or (member and member.guild_permissions.manage_guild)
        )

    @staticmethod
    def _cd_form(kwargs):
        data = kwargs.get("data") or {}
        return (data.get("form") or data.get("json") or {}) if isinstance(data, dict) else data

    @staticmethod
    def _cd_value(form, key):
        value = form.get(key, "") if hasattr(form, "get") else ""
        return (value[0] if value else "") if isinstance(value, (list, tuple)) else str(value or "")

    @classmethod
    def _cd_checked(cls, form, key):
        return cls._cd_value(form, key).lower() in {"1", "true", "on", "yes"}

    @classmethod
    def _cd_int(cls, form, key, minimum, maximum):
        try:
            value = int(cls._cd_value(form, key))
        except ValueError as error:
            raise commands.BadArgument(f"{key.replace('_', ' ')} must be a number.") from error
        if not minimum <= value <= maximum:
            raise commands.BadArgument(f"{key.replace('_', ' ')} must be {minimum}–{maximum}.")
        return value

    @staticmethod
    def _cd_options(items, selected):
        return '<option value="">Not configured</option>' + "".join(
            f'<option value="{item.id}"{" selected" if item.id == selected else ""}>#{html.escape(item.name)}</option>'
            for item in items
        )

    @staticmethod
    def _cd_mark(value):
        return " checked" if value else ""

    @staticmethod
    def _cd_csrf(kwargs):
        token = kwargs.get("csrf_token")
        return (
            ""
            if not isinstance(token, (tuple, list)) or len(token) != 2
            else f'<input type="hidden" name="csrf_token" value="{html.escape(str(token[1]), quote=True)}">'
        )

    @staticmethod
    def _cd_css():
        return ".cd .card{border:1px solid rgba(127,127,127,.3);border-radius:.65rem;padding:1rem;margin-bottom:1rem}.cd .grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(210px,1fr));gap:1rem}.cd label{display:flex;flex-direction:column;gap:.3rem}.cd .check{flex-direction:row;align-items:center}.cd input,.cd select{padding:.55rem;background:var(--background,#202225);color:var(--text,#fff);border:1px solid rgba(127,127,127,.35);border-radius:.35rem}"
