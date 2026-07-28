# ruff: noqa: E501
"""Purpose-built dashboard for FiveMStatus."""

from __future__ import annotations

import html
import logging
from typing import TYPE_CHECKING, Any, Callable
from zoneinfo import available_timezones

from redbot.core import commands

if TYPE_CHECKING:
    import discord

log = logging.getLogger("red.taakoscogs.fivemstatus.dashboard")


def dashboard_page(*args, **kwargs):
    def decorator(func: Callable):
        func.__dashboard_decorator_params__ = (args, kwargs)
        return func

    return decorator


class DashboardIntegration:
    """FiveM endpoint, panel presentation, links, and restart controls."""

    @commands.Cog.listener()
    async def on_dashboard_cog_add(self, dashboard_cog: commands.Cog) -> None:
        handler = dashboard_cog.rpc.third_parties_handler
        try:
            handler.add_third_party(self, overwrite=True)
        except TypeError:
            handler.add_third_party(self)

    @dashboard_page(name=None, description="Configure and operate the FiveM status panel.", methods=("GET", "POST"))
    async def dashboard_page(self, user: discord.User, guild: discord.Guild, **kwargs: Any):
        if not await self._fm_can_manage(user, guild):
            return {"status": 1, "error_title": "Insufficient Permissions", "error_message": "Manage Server is required."}
        notices = []
        if kwargs.get("method", "GET").upper() == "POST":
            form = self._fm_form(kwargs)
            try:
                message = await self._fm_action(guild, self._fm_value(form, "action"), form)
            except (commands.CommandError, ValueError) as error:
                notices.append({"message": str(error), "category": "error"})
            except Exception as error:
                log.exception("FiveMStatus dashboard action failed")
                notices.append({"message": f"Action failed: {error}", "category": "error"})
            else:
                notices.append({"message": message, "category": "success"})
        settings = await self.config.guild(guild).all()
        source = self._fm_source(guild, settings, self._fm_csrf(kwargs))
        return {"status": 0, "notifications": notices, "web_content": {"source": source, "expanded": True}}

    async def _fm_action(self, guild, action, form):
        if action == "save":
            await self._fm_save(guild, form)
            return "FiveM status settings saved."
        if action in {"post", "refresh"}:
            message = await self._update_status_message(guild, force_post=action == "post")
            if action == "post":
                await self.config.guild(guild).enabled.set(True)
            return f"Status panel {'posted' if action == 'post' else 'refreshed'}: {message.jump_url}"
        raise commands.BadArgument("Choose a valid dashboard action.")

    async def _fm_save(self, guild, form):
        server = self._normalize_server_address(self._fm_value(form, "server_address"))
        channel_id = self._fm_channel(guild, form)
        timezone_name = self._fm_value(form, "timezone")
        if timezone_name not in available_timezones():
            raise commands.BadArgument("Choose a valid IANA timezone.")
        restart_times = []
        for line in self._fm_value(form, "restart_times").splitlines():
            if line.strip():
                parsed = self._parse_restart_time(line)
                if parsed not in restart_times:
                    restart_times.append(parsed)
        restart_times.sort()
        color_raw = self._fm_value(form, "embed_color").lstrip("#")
        try:
            color = int(color_raw, 16)
        except ValueError as error:
            raise commands.BadArgument("Choose a valid embed color.") from error
        conf = self.config.guild(guild)
        previous_server = await conf.server_address()
        await conf.enabled.set(self._fm_checked(form, "enabled"))
        await conf.server_address.set(server)
        await conf.status_channel_id.set(channel_id)
        await conf.display_name.set(self._clean_optional_text(self._fm_value(form, "display_name"), 120))
        await conf.status_message.set(self._clean_optional_text(self._fm_value(form, "status_message"), 300))
        for key in ("logo_url", "image_url", "connect_url", "discord_url", "hosting_url"):
            await getattr(conf, key).set(self._clean_optional_url(self._fm_value(form, key) or None))
        await conf.embed_color.set(color)
        await conf.restart_times.set(restart_times)
        await conf.timezone.set(timezone_name)
        if server != previous_server:
            await conf.online_since.set(None)
            await conf.last_seen_online.set(False)

    def _fm_source(self, guild, settings, csrf):
        channels = self._fm_options(guild.text_channels, settings.get("status_channel_id"), "Not configured")
        zones = "".join(
            f'<option value="{html.escape(z, quote=True)}"{" selected" if z == settings.get("timezone") else ""}>{html.escape(z)}</option>'
            for z in sorted(available_timezones())
        )
        restarts = "\n".join(settings.get("restart_times") or [])

        def val(key):
            return html.escape(str(settings.get(key) or ""), quote=True)

        return f"""
<section class="fm-dash"><style>
.fm-dash .card{{border:1px solid rgba(127,127,127,.3);border-radius:.65rem;padding:1rem;margin-bottom:1rem}}.fm-dash .grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(230px,1fr));gap:1rem}}
.fm-dash label{{display:flex;flex-direction:column;gap:.3rem}}.fm-dash .wide{{grid-column:1/-1}}.fm-dash .check{{flex-direction:row;align-items:center}}.fm-dash .check input{{width:auto}}
.fm-dash input,.fm-dash select,.fm-dash textarea{{padding:.55rem;border:1px solid rgba(127,127,127,.35);border-radius:.35rem;background:var(--background,#202225);color:var(--text,#fff)}}.fm-dash textarea{{min-height:6rem}}.fm-dash .actions{{display:flex;gap:.6rem;flex-wrap:wrap}}
</style><h2>FiveM Status</h2><p>Manage the live server panel for <strong>{html.escape(guild.name)}</strong>.</p>
<form method="POST" class="card">{csrf}<input type="hidden" name="action" value="save"><div class="grid">
<label class="check"><input type="checkbox" name="enabled"{self._fm_mark(settings.get("enabled"))}> Automatic refreshes</label>
<label>Server endpoint or CFX code<input name="server_address" value="{val("server_address")}" required></label>
<label>Status channel<select name="status_channel_id" required>{channels}</select></label>
<label>Display name<input name="display_name" maxlength="120" value="{val("display_name")}"></label>
<label class="wide">Status message<input name="status_message" maxlength="300" value="{val("status_message")}"></label>
<label>Embed color<input type="color" name="embed_color" value="#{int(settings.get("embed_color", self.DEFAULT_COLOR)):06x}"></label>
<label>Logo URL<input type="url" name="logo_url" value="{val("logo_url")}"></label><label>Large image URL<input type="url" name="image_url" value="{val("image_url")}"></label>
<label>Join button URL<input type="url" name="connect_url" value="{val("connect_url")}"></label><label>Discord URL<input type="url" name="discord_url" value="{val("discord_url")}"></label>
<label>Hosting URL<input type="url" name="hosting_url" value="{val("hosting_url")}"></label><label>Restart timezone<select name="timezone">{zones}</select></label>
<label class="wide">Daily restart times (one HH:MM per line)<textarea name="restart_times">{html.escape(restarts)}</textarea></label>
</div><button class="btn btn-primary">Save FiveM Settings</button></form>
<section class="card"><h3>Panel operations</h3><div class="actions">{self._fm_button(csrf, "post", "Post Fresh Panel")}{self._fm_button(csrf, "refresh", "Refresh Now")}</div>
<p>Message ID: <code>{html.escape(str(settings.get("status_message_id") or "Not posted"))}</code> · Online since: <code>{html.escape(str(settings.get("online_since") or "Offline"))}</code></p></section></section>"""

    async def _fm_can_manage(self, user, guild):
        member = guild.get_member(user.id)
        return bool(
            user.id in getattr(self.bot, "owner_ids", set())
            or (member and await self.bot.is_admin(member))
            or (member and member.guild_permissions.manage_guild),
        )

    @staticmethod
    def _fm_form(kwargs):
        data = kwargs.get("data") or {}
        return (data.get("form") or data.get("json") or {}) if isinstance(data, dict) else data

    @staticmethod
    def _fm_value(form, key, default=""):
        value = form.get(key, default) if hasattr(form, "get") else default
        if isinstance(value, (list, tuple)):
            value = value[0] if value else default
        return default if value is None else str(value)

    @classmethod
    def _fm_checked(cls, form, key):
        return cls._fm_value(form, key).lower() in {"1", "true", "on", "yes"}

    @classmethod
    def _fm_channel(cls, guild, form):
        try:
            channel_id = int(cls._fm_value(form, "status_channel_id"))
        except ValueError as error:
            raise commands.BadArgument("Choose a status channel.") from error
        if guild.get_channel(channel_id) not in guild.text_channels:
            raise commands.BadArgument("Choose a valid text channel.")
        return channel_id

    @staticmethod
    def _fm_options(items, selected, empty):
        return f'<option value="">{empty}</option>' + "".join(
            f'<option value="{x.id}"{" selected" if x.id == selected else ""}>#{html.escape(x.name)}</option>' for x in items
        )

    @staticmethod
    def _fm_mark(value):
        return " checked" if value else ""

    @staticmethod
    def _fm_button(csrf, action, label):
        return f'<form method="POST">{csrf}<input type="hidden" name="action" value="{action}"><button class="btn btn-secondary">{label}</button></form>'

    @staticmethod
    def _fm_csrf(kwargs):
        token = kwargs.get("csrf_token")
        return (
            ""
            if not isinstance(token, (tuple, list)) or len(token) != 2
            else f'<input type="hidden" name="csrf_token" value="{html.escape(str(token[1]), quote=True)}">'
        )
