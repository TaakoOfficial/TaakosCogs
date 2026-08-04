# ruff: noqa: E501
"""Purpose-built dashboard for DataSteward."""

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

    @dashboard_page(name=None, description="Inspect retention policy and choose only safe modes.", methods=("GET", "POST"))
    async def dashboard_page(self, user: discord.User, guild: discord.Guild, **kwargs: Any):
        if not await self._ds_can_manage(user, guild):
            return {"status": 1, "error_title": "Insufficient Permissions", "error_message": "Manage Server is required."}
        notices = []
        if kwargs.get("method", "GET").upper() == "POST":
            form = self._ds_form(kwargs)
            try:
                await self._ds_save(guild, form)
            except (commands.CommandError, ValueError) as error:
                notices.append({"message": str(error), "category": "error"})
            else:
                notices.append({"message": "DataSteward safe settings saved.", "category": "success"})
        settings = await self.config.guild(guild).all()
        mode = "disabled" if not settings["enabled"] else "dry-run" if settings["dry_run"] else "ENFORCE"
        policy_rows = (
            "".join(f"<li>&lt;#{channel_id}&gt; — {item['days']} days</li>" for channel_id, item in settings["policies"].items())
            or "<li>No policies configured.</li>"
        )
        source = f"""<section class="ds"><style>{self._ds_css()}</style><h2>DataSteward</h2><p>Retention and privacy workflows for <strong>{html.escape(guild.name)}</strong>.</p><div class="grid"><div class="card"><b>{html.escape(mode)}</b><br>current mode</div><div class="card"><b>{len(settings["policies"])}</b><br>channel policies</div><div class="card"><b>{sum(item.get("status") == "open" for item in settings["requests"].values())}</b><br>open privacy requests</div></div><form method="POST" class="card">{self._ds_csrf(kwargs)}<div class="grid"><label>Safe mode<select name="mode"><option value="disabled"{" selected" if mode == "disabled" else ""}>Disabled</option><option value="dry-run"{" selected" if mode == "dry-run" else ""}>Dry-run</option></select></label><label>Audit log channel<select name="log_channel_id">{self._ds_options(guild.text_channels, settings["log_channel_id"])}</select></label></div><button class="btn btn-primary">Save Safe Settings</button></form><div class="card"><h3>Retention policies</h3><ul>{policy_rows}</ul><p>The dashboard cannot enable enforcement or delete messages. Use the explicit command confirmations after reviewing a dry-run preview.</p></div></section>"""
        return {"status": 0, "notifications": notices, "web_content": {"source": source, "expanded": True}}

    async def _ds_save(self, guild, form):
        conf = self.config.guild(guild)
        mode = self._ds_value(form, "mode")
        if mode not in {"disabled", "dry-run"}:
            raise commands.BadArgument("The dashboard only permits disabled or dry-run modes.")
        await conf.enabled.set(mode == "dry-run")
        await conf.dry_run.set(True)
        raw = self._ds_value(form, "log_channel_id")
        channel_id = int(raw) if raw else None
        if channel_id and guild.get_channel(channel_id) not in guild.text_channels:
            raise commands.BadArgument("Choose a valid log channel.")
        await conf.log_channel_id.set(channel_id)

    async def _ds_can_manage(self, user, guild):
        member = guild.get_member(user.id)
        return bool(
            user.id in getattr(self.bot, "owner_ids", set())
            or (member and await self.bot.is_admin(member))
            or (member and member.guild_permissions.manage_guild)
        )

    @staticmethod
    def _ds_form(kwargs):
        data = kwargs.get("data") or {}
        return (data.get("form") or data.get("json") or {}) if isinstance(data, dict) else data

    @staticmethod
    def _ds_value(form, key):
        value = form.get(key, "") if hasattr(form, "get") else ""
        return (value[0] if value else "") if isinstance(value, (list, tuple)) else str(value or "")

    @staticmethod
    def _ds_options(items, selected):
        return '<option value="">Disabled</option>' + "".join(
            f'<option value="{item.id}"{" selected" if item.id == selected else ""}>#{html.escape(item.name)}</option>'
            for item in items
        )

    @staticmethod
    def _ds_csrf(kwargs):
        token = kwargs.get("csrf_token")
        return (
            ""
            if not isinstance(token, (tuple, list)) or len(token) != 2
            else f'<input type="hidden" name="csrf_token" value="{html.escape(str(token[1]), quote=True)}">'
        )

    @staticmethod
    def _ds_css():
        return ".ds .card{border:1px solid rgba(127,127,127,.3);border-radius:.65rem;padding:1rem;margin-bottom:1rem}.ds .grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(210px,1fr));gap:1rem}.ds label{display:flex;flex-direction:column;gap:.3rem}.ds select{padding:.55rem;background:var(--background,#202225);color:var(--text,#fff);border:1px solid rgba(127,127,127,.35);border-radius:.35rem}"
