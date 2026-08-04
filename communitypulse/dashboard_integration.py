# ruff: noqa: E501
"""Purpose-built dashboard for CommunityPulse."""

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

    @dashboard_page(name=None, description="Configure content-free community health tracking.", methods=("GET", "POST"))
    async def dashboard_page(self, user: discord.User, guild: discord.Guild, **kwargs: Any):
        if not await self._cp_can_manage(user, guild):
            return {"status": 1, "error_title": "Insufficient Permissions", "error_message": "Manage Server is required."}
        notices = []
        if kwargs.get("method", "GET").upper() == "POST":
            form = self._cp_form(kwargs)
            try:
                await self._cp_save(guild, form)
            except (commands.CommandError, ValueError) as error:
                notices.append({"message": str(error), "category": "error"})
            else:
                notices.append({"message": "CommunityPulse settings saved.", "category": "success"})
        settings = await self.config.guild(guild).all()
        current = [item for item in settings["members"].values() if not item.get("left_at")]
        activated = sum(int(item.get("message_count") or 0) >= settings["activation_messages"] for item in current)
        rate = activated / len(current) * 100 if current else 0
        source = f"""<section class="cp"><style>{self._cp_css()}</style><h2>CommunityPulse</h2><p>Content-free community health for <strong>{html.escape(guild.name)}</strong>. The cog stores counts and timestamps, never message text.</p><div class="grid"><div class="card"><b>{len(current)}</b><br>tracked current members</div><div class="card"><b>{rate:.1f}%</b><br>activation rate</div><div class="card"><b>{settings["total_leaves"]}</b><br>observed leaves</div></div><form method="POST" class="card">{self._cp_csrf(kwargs)}<div class="grid"><label class="check"><input type="checkbox" name="enabled"{self._cp_mark(settings["enabled"])}> Enable activity tracking</label><label>Activation messages<input type="number" min="1" max="1000" name="activation_messages" value="{settings["activation_messages"]}"></label><label>Inactive after days<input type="number" min="1" max="3650" name="inactive_days" value="{settings["inactive_days"]}"></label></div><button class="btn btn-primary">Save CommunityPulse Settings</button></form></section>"""
        return {"status": 0, "notifications": notices, "web_content": {"source": source, "expanded": True}}

    async def _cp_save(self, guild, form):
        conf = self.config.guild(guild)
        enabled = self._cp_checked(form, "enabled")
        await conf.enabled.set(enabled)
        if enabled and not await conf.tracking_started_at():
            await conf.tracking_started_at.set(self._now())
        if enabled:
            await self._seed_members(guild)
        await conf.activation_messages.set(self._cp_int(form, "activation_messages", 1, 1000))
        await conf.inactive_days.set(self._cp_int(form, "inactive_days", 1, 3650))

    async def _cp_can_manage(self, user, guild):
        member = guild.get_member(user.id)
        return bool(
            user.id in getattr(self.bot, "owner_ids", set())
            or (member and await self.bot.is_admin(member))
            or (member and member.guild_permissions.manage_guild)
        )

    @staticmethod
    def _cp_form(kwargs):
        data = kwargs.get("data") or {}
        return (data.get("form") or data.get("json") or {}) if isinstance(data, dict) else data

    @staticmethod
    def _cp_value(form, key):
        value = form.get(key, "") if hasattr(form, "get") else ""
        return (value[0] if value else "") if isinstance(value, (list, tuple)) else str(value or "")

    @classmethod
    def _cp_checked(cls, form, key):
        return cls._cp_value(form, key).lower() in {"1", "true", "on", "yes"}

    @classmethod
    def _cp_int(cls, form, key, minimum, maximum):
        try:
            value = int(cls._cp_value(form, key))
        except ValueError as error:
            raise commands.BadArgument(f"{key.replace('_', ' ')} must be a number.") from error
        if not minimum <= value <= maximum:
            raise commands.BadArgument(f"{key.replace('_', ' ')} must be {minimum}–{maximum}.")
        return value

    @staticmethod
    def _cp_mark(value):
        return " checked" if value else ""

    @staticmethod
    def _cp_csrf(kwargs):
        token = kwargs.get("csrf_token")
        return (
            ""
            if not isinstance(token, (tuple, list)) or len(token) != 2
            else f'<input type="hidden" name="csrf_token" value="{html.escape(str(token[1]), quote=True)}">'
        )

    @staticmethod
    def _cp_css():
        return ".cp .card{border:1px solid rgba(127,127,127,.3);border-radius:.65rem;padding:1rem;margin-bottom:1rem}.cp .grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(210px,1fr));gap:1rem}.cp label{display:flex;flex-direction:column;gap:.3rem}.cp .check{flex-direction:row;align-items:center}.cp input{padding:.55rem;background:var(--background,#202225);color:var(--text,#fff);border:1px solid rgba(127,127,127,.35);border-radius:.35rem}"
