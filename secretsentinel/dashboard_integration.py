# ruff: noqa: E501
"""Purpose-built dashboard for SecretSentinel."""

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

    @dashboard_page(name=None, description="Configure secret detection without exposing matched values.", methods=("GET", "POST"))
    async def dashboard_page(self, user: discord.User, guild: discord.Guild, **kwargs: Any):
        member = guild.get_member(user.id)
        if not (
            user.id in getattr(self.bot, "owner_ids", set())
            or (member and await self.bot.is_admin(member))
            or (member and member.guild_permissions.manage_guild)
        ):
            return {"status": 1, "error_title": "Insufficient Permissions", "error_message": "Manage Server is required."}
        notices = []
        conf = self.config.guild(guild)
        if kwargs.get("method", "GET").upper() == "POST":
            data = kwargs.get("data") or {}
            form = (data.get("form") or data.get("json") or {}) if isinstance(data, dict) else data

            def value(key):
                raw_value = form.get(key, "")
                if isinstance(raw_value, (list, tuple)):
                    return (raw_value or [""])[0]
                return str(raw_value or "")

            await conf.enabled.set(value("enabled") in {"1", "true", "on", "yes"})
            await conf.scan_attachments.set(value("scan_attachments") in {"1", "true", "on", "yes"})
            await conf.create_opsroom_incidents.set(value("create_opsroom_incidents") in {"1", "true", "on", "yes"})
            await conf.action.set("report" if value("action") == "report" else "delete")
            try:
                cooldown = max(0, min(3600, int(value("alert_cooldown_seconds") or 60)))
            except ValueError:
                cooldown = 60
                notices.append({"message": "Invalid cooldown; using 60 seconds.", "category": "warning"})
            await conf.alert_cooldown_seconds.set(cooldown)
            raw = value("log_channel_id")
            channel_id = int(raw) if raw else None
            if channel_id and guild.get_channel(channel_id) not in guild.text_channels:
                notices.append({"message": "Choose a valid log channel.", "category": "error"})
            else:
                await conf.log_channel_id.set(channel_id)
                notices.append({"message": "SecretSentinel settings saved.", "category": "success"})
        settings = await conf.all()
        options = '<option value="">Disabled</option>' + "".join(
            f'<option value="{c.id}"{" selected" if c.id == settings["log_channel_id"] else ""}>#{html.escape(c.name)}</option>'
            for c in guild.text_channels
        )
        csrf = kwargs.get("csrf_token")
        csrf_html = (
            ""
            if not isinstance(csrf, (tuple, list)) or len(csrf) != 2
            else f'<input type="hidden" name="csrf_token" value="{html.escape(str(csrf[1]), quote=True)}">'
        )

        def checked(key):
            return " checked" if settings[key] else ""

        source = f'<section><h2>SecretSentinel</h2><p>Matched credential values are never displayed or stored.</p><p><b>{len(settings["disabled_kinds"])}</b> disabled detector(s) · <b>{len(settings["monitored_bot_ids"])}</b> explicitly monitored bot(s)</p><form method="POST">{csrf_html}<p><label><input type="checkbox" name="enabled" value="1"{checked("enabled")}> Enable scanning</label></p><p><label><input type="checkbox" name="scan_attachments" value="1"{checked("scan_attachments")}> Scan small text attachments</label></p><p><label><input type="checkbox" name="create_opsroom_incidents" value="1"{checked("create_opsroom_incidents")}> Open rate-limited OpsRoom incidents</label></p><p><label>Duplicate alert cooldown <input type="number" min="0" max="3600" name="alert_cooldown_seconds" value="{settings["alert_cooldown_seconds"]}"> seconds</label></p><p><label>Action <select name="action"><option value="delete"{" selected" if settings["action"] == "delete" else ""}>Delete and report</option><option value="report"{" selected" if settings["action"] == "report" else ""}>Report only</option></select></label></p><p><label>Alert channel <select name="log_channel_id">{options}</select></label></p><button class="btn btn-primary">Save SecretSentinel Settings</button></form></section>'
        return {"status": 0, "notifications": notices, "web_content": {"source": source, "expanded": True}}
