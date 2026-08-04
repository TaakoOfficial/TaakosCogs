# ruff: noqa: E501
"""Purpose-built dashboard for SponsorSync."""

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

    @dashboard_page(
        name=None, description="Inspect membership tiers and configure reconciliation policy.", methods=("GET", "POST")
    )
    async def dashboard_page(self, user: discord.User, guild: discord.Guild, **kwargs: Any):
        if not await self._ss_can_manage(user, guild):
            return {"status": 1, "error_title": "Insufficient Permissions", "error_message": "Manage Server is required."}
        notices = []
        if kwargs.get("method", "GET").upper() == "POST":
            form = self._ss_form(kwargs)
            try:
                await self._ss_save(guild, form)
            except (commands.CommandError, ValueError) as error:
                notices.append({"message": str(error), "category": "error"})
            else:
                notices.append({"message": "SponsorSync settings saved.", "category": "success"})
        settings = await self.config.guild(guild).all()
        active = sum(item.get("status") == "active" for item in settings["subscribers"].values())
        tiers = (
            "".join(
                f"<li><strong>{html.escape(key)}</strong> → &lt;@&amp;{item['role_id']}&gt;</li>"
                for key, item in settings["tiers"].items()
            )
            or "<li>No tiers configured.</li>"
        )
        source = f"""<section class="ss"><style>{self._ss_css()}</style><h2>SponsorSync</h2><p>Membership-role reconciliation for <strong>{html.escape(guild.name)}</strong>.</p><div class="grid"><div class="card"><b>{len(settings["tiers"])}</b><br>tiers</div><div class="card"><b>{active}</b><br>active subscribers</div><div class="card"><b>{settings["sync_count"]}</b><br>sync runs</div></div><form method="POST" class="card">{self._ss_csrf(kwargs)}<div class="grid"><label>Grace period days<input type="number" min="0" max="90" name="grace_days" value="{settings["grace_days"]}"></label><label>Audit alert channel<select name="alert_channel_id">{self._ss_options(guild.text_channels, settings["alert_channel_id"])}</select></label></div><button class="btn btn-primary">Save SponsorSync Settings</button></form><div class="card"><h3>Tier mappings</h3><ul>{tiers}</ul><p>Tier and subscriber changes remain command-controlled because they alter member access.</p></div></section>"""
        return {"status": 0, "notifications": notices, "web_content": {"source": source, "expanded": True}}

    async def _ss_save(self, guild, form):
        conf = self.config.guild(guild)
        await conf.grace_days.set(self._ss_int(form, "grace_days", 0, 90))
        raw = self._ss_value(form, "alert_channel_id")
        channel_id = int(raw) if raw else None
        if channel_id and guild.get_channel(channel_id) not in guild.text_channels:
            raise commands.BadArgument("Choose a valid alert channel.")
        await conf.alert_channel_id.set(channel_id)

    async def _ss_can_manage(self, user, guild):
        member = guild.get_member(user.id)
        return bool(
            user.id in getattr(self.bot, "owner_ids", set())
            or (member and await self.bot.is_admin(member))
            or (member and member.guild_permissions.manage_guild)
        )

    @staticmethod
    def _ss_form(kwargs):
        data = kwargs.get("data") or {}
        return (data.get("form") or data.get("json") or {}) if isinstance(data, dict) else data

    @staticmethod
    def _ss_value(form, key):
        value = form.get(key, "") if hasattr(form, "get") else ""
        return (value[0] if value else "") if isinstance(value, (list, tuple)) else str(value or "")

    @classmethod
    def _ss_int(cls, form, key, minimum, maximum):
        try:
            value = int(cls._ss_value(form, key))
        except ValueError as error:
            raise commands.BadArgument(f"{key.replace('_', ' ')} must be a number.") from error
        if not minimum <= value <= maximum:
            raise commands.BadArgument(f"{key.replace('_', ' ')} must be {minimum}–{maximum}.")
        return value

    @staticmethod
    def _ss_options(items, selected):
        return '<option value="">Disabled</option>' + "".join(
            f'<option value="{item.id}"{" selected" if item.id == selected else ""}>#{html.escape(item.name)}</option>'
            for item in items
        )

    @staticmethod
    def _ss_csrf(kwargs):
        token = kwargs.get("csrf_token")
        return (
            ""
            if not isinstance(token, (tuple, list)) or len(token) != 2
            else f'<input type="hidden" name="csrf_token" value="{html.escape(str(token[1]), quote=True)}">'
        )

    @staticmethod
    def _ss_css():
        return ".ss .card{border:1px solid rgba(127,127,127,.3);border-radius:.65rem;padding:1rem;margin-bottom:1rem}.ss .grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(210px,1fr));gap:1rem}.ss label{display:flex;flex-direction:column;gap:.3rem}.ss input,.ss select{padding:.55rem;background:var(--background,#202225);color:var(--text,#fff);border:1px solid rgba(127,127,127,.35);border-radius:.35rem}"
