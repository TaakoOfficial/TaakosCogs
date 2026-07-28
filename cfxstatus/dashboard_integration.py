# ruff: noqa: E501
"""Purpose-built Red-Web-Dashboard integration for CfxStatus."""

from __future__ import annotations

import html
import logging
from typing import TYPE_CHECKING, Any, Callable

from redbot.core import commands

if TYPE_CHECKING:
    import discord

log = logging.getLogger("red.taakoscogs.cfxstatus.dashboard")


def dashboard_page(*args, **kwargs):
    def decorator(func: Callable):
        func.__dashboard_decorator_params__ = (args, kwargs)
        return func

    return decorator


class DashboardIntegration:
    """Cfx.re status-panel settings and operational controls."""

    @commands.Cog.listener()
    async def on_dashboard_cog_add(self, dashboard_cog: commands.Cog) -> None:
        handler = dashboard_cog.rpc.third_parties_handler
        try:
            handler.add_third_party(self, overwrite=True)
        except TypeError:
            handler.add_third_party(self)

    @dashboard_page(
        name=None,
        description="Configure and operate the auto-updating Cfx.re status panel.",
        methods=("GET", "POST"),
    )
    async def dashboard_page(
        self,
        user: discord.User,
        guild: discord.Guild,
        **kwargs: Any,
    ) -> dict[str, Any]:
        if not await self._dash_can_manage(user, guild):
            return {
                "status": 1,
                "error_title": "Insufficient Permissions",
                "error_message": "Manage Server is required.",
            }
        notices = []
        if kwargs.get("method", "GET").upper() == "POST":
            form = self._dash_form(kwargs)
            try:
                message = await self._dash_action(guild, self._dash_value(form, "action"), form)
            except (commands.CommandError, ValueError) as error:
                notices.append({"message": str(error), "category": "error"})
            except Exception as error:
                log.exception("CfxStatus dashboard action failed")
                notices.append({"message": f"Action failed: {error}", "category": "error"})
            else:
                notices.append({"message": message, "category": "success"})
        settings = await self.config.guild(guild).all()
        source = self._dash_source(guild, settings, self._dash_csrf(kwargs))
        return {
            "status": 0,
            "notifications": notices,
            "web_content": {"source": source, "expanded": True},
        }

    async def _dash_action(self, guild, action: str, form: Any) -> str:
        conf = self.config.guild(guild)
        if action == "save":
            channel_id = self._dash_optional_channel(guild, form, "status_channel_id")
            enabled = self._dash_checked(form, "enabled")
            if enabled and channel_id is None:
                raise commands.BadArgument("Choose a status channel before enabling updates.")
            try:
                interval = int(self._dash_value(form, "poll_interval_minutes"))
            except ValueError as error:
                raise commands.BadArgument("Refresh interval must be a whole number.") from error
            if not self.MIN_POLL_INTERVAL_MINUTES <= interval <= self.MAX_POLL_INTERVAL_MINUTES:
                raise commands.BadArgument(
                    f"Refresh interval must be {self.MIN_POLL_INTERVAL_MINUTES}–{self.MAX_POLL_INTERVAL_MINUTES} minutes.",
                )
            old_channel = await conf.status_channel_id()
            await conf.enabled.set(enabled)
            await conf.status_channel_id.set(channel_id)
            await conf.poll_interval_minutes.set(interval)
            if channel_id != old_channel:
                await conf.status_message_id.set(None)
            return "Cfx.re status settings saved."
        if action in {"post", "refresh"}:
            message = await self._update_status_message(
                guild,
                force_post=action == "post",
                allow_error_embed=True,
            )
            if action == "post":
                await conf.enabled.set(True)
            verb = "posted" if action == "post" else "refreshed"
            return f"Status panel {verb}: {message.jump_url}"
        raise commands.BadArgument("Choose a valid action.")

    def _dash_source(self, guild, settings, csrf: str) -> str:
        channels = ['<option value="">Not configured</option>']
        channels.extend(
            f'<option value="{channel.id}"'
            f"{' selected' if channel.id == settings.get('status_channel_id') else ''}>"
            f"#{html.escape(channel.name)}</option>"
            for channel in guild.text_channels
        )
        enabled = " checked" if settings.get("enabled") else ""
        message_id = html.escape(str(settings.get("status_message_id") or "Not posted"))
        last_poll = html.escape(str(settings.get("last_poll_at") or "Never"))
        return f"""
<section class="cfx-dash"><style>
.cfx-dash .card{{border:1px solid rgba(127,127,127,.3);border-radius:.65rem;padding:1rem;margin-bottom:1rem}}
.cfx-dash .grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:1rem}}
.cfx-dash label{{display:flex;flex-direction:column;gap:.3rem}}.cfx-dash .check{{flex-direction:row;align-items:center}}
.cfx-dash input,.cfx-dash select{{padding:.55rem;border:1px solid rgba(127,127,127,.35);border-radius:.35rem;background:var(--background,#202225);color:var(--text,#fff)}}
.cfx-dash .check input{{width:auto}}.cfx-dash .actions{{display:flex;gap:.6rem;flex-wrap:wrap}}
</style><h2>Cfx.re Service Status</h2>
<p>Configure and operate the auto-updating service-status panel for <strong>{html.escape(guild.name)}</strong>.</p>
<form method="POST" class="card">{csrf}<input type="hidden" name="action" value="save"><div class="grid">
<label class="check"><input type="checkbox" name="enabled"{enabled}> Automatic updates</label>
<label>Status channel<select name="status_channel_id">{"".join(channels)}</select></label>
<label>Refresh interval (minutes)<input type="number" name="poll_interval_minutes"
min="{self.MIN_POLL_INTERVAL_MINUTES}" max="{self.MAX_POLL_INTERVAL_MINUTES}"
value="{int(settings.get("poll_interval_minutes", self.DEFAULT_POLL_INTERVAL_MINUTES))}" required></label>
</div><button class="btn btn-primary" type="submit">Save Status Settings</button></form>
<section class="card"><h3>Panel operations</h3><div class="actions">
{self._dash_button(csrf, "post", "Post Fresh Panel")}{self._dash_button(csrf, "refresh", "Refresh Now")}
</div><p>Panel message ID: <code>{message_id}</code><br>Last poll timestamp: <code>{last_poll}</code></p></section>
</section>"""

    async def _dash_can_manage(self, user, guild) -> bool:
        member = guild.get_member(user.id)
        return bool(
            user.id in getattr(self.bot, "owner_ids", set())
            or (member is not None and await self.bot.is_admin(member))
            or (member is not None and member.guild_permissions.manage_guild),
        )

    @staticmethod
    def _dash_form(kwargs):
        data = kwargs.get("data") or {}
        return (data.get("form") or data.get("json") or {}) if isinstance(data, dict) else data

    @staticmethod
    def _dash_value(form, key, default=""):
        value = form.get(key, default) if hasattr(form, "get") else default
        if isinstance(value, (list, tuple)):
            value = value[0] if value else default
        return default if value is None else str(value)

    @classmethod
    def _dash_checked(cls, form, key):
        return cls._dash_value(form, key).lower() in {"1", "true", "yes", "on"}

    @classmethod
    def _dash_optional_channel(cls, guild, form, key):
        raw = cls._dash_value(form, key).strip()
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
    def _dash_csrf(kwargs):
        token = kwargs.get("csrf_token")
        if not isinstance(token, (tuple, list)) or len(token) != 2:
            return ""
        return f'<input type="hidden" name="csrf_token" value="{html.escape(str(token[1]), quote=True)}">'

    @staticmethod
    def _dash_button(csrf, action, label):
        return (
            f'<form method="POST">{csrf}<input type="hidden" name="action" value="{action}">'
            f'<button class="btn btn-secondary">{label}</button></form>'
        )
