# ruff: noqa: E501
"""Purpose-built dashboard for RandomWeather."""

from __future__ import annotations

import html
import logging
from typing import TYPE_CHECKING, Any, Callable

import pytz
from redbot.core import commands

if TYPE_CHECKING:
    import discord

log = logging.getLogger("red.taakoscogs.randomweather.dashboard")


def dashboard_page(*args, **kwargs):
    def decorator(func: Callable):
        func.__dashboard_decorator_params__ = (args, kwargs)
        return func

    return decorator


class DashboardIntegration:
    """Random-weather schedule, presentation, and posting controls."""

    @commands.Cog.listener()
    async def on_dashboard_cog_add(self, dashboard_cog: commands.Cog) -> None:
        handler = dashboard_cog.rpc.third_parties_handler
        try:
            handler.add_third_party(self, overwrite=True)
        except TypeError:
            handler.add_third_party(self)

    @dashboard_page(
        name=None,
        description="Configure scheduled RP weather and post forecasts.",
        methods=("GET", "POST"),
    )
    async def dashboard_page(self, user: discord.User, guild: discord.Guild, **kwargs: Any):
        if not await self._rw_can_manage(user, guild):
            return {"status": 1, "error_title": "Insufficient Permissions", "error_message": "Manage Server is required."}
        notices = []
        if kwargs.get("method", "GET").upper() == "POST":
            form = self._rw_form(kwargs)
            try:
                message = await self._rw_action(guild, self._rw_value(form, "action"), form)
            except (commands.CommandError, ValueError) as error:
                notices.append({"message": str(error), "category": "error"})
            except Exception as error:
                log.exception("RandomWeather dashboard action failed")
                notices.append({"message": f"Action failed: {error}", "category": "error"})
            else:
                notices.append({"message": message, "category": "success"})
        settings = await self.config.guild(guild).all()
        source = self._rw_source(guild, settings, self._rw_csrf(kwargs))
        return {"status": 0, "notifications": notices, "web_content": {"source": source, "expanded": True}}

    async def _rw_action(self, guild, action, form):
        if action == "save":
            await self._rw_save(guild, form)
            return "RandomWeather settings saved."
        settings = await self.config.guild(guild).all()
        if not settings.get("channel_id"):
            raise commands.BadArgument("Choose a weather channel first.")
        if action == "post":
            await self._post_weather_update(guild.id, settings, is_forced=True)
            return "Weather update posted."
        if action == "extreme":
            await self._post_extreme_weather_update(guild.id, settings)
            return "Extreme-weather alert posted."
        raise commands.BadArgument("Choose a valid dashboard action.")

    async def _rw_save(self, guild, form):
        channel_id = self._rw_optional_id(guild, form, "channel_id", "channel")
        role_id = self._rw_optional_id(guild, form, "role_id", "role")
        timezone_name = self._rw_value(form, "time_zone")
        if timezone_name not in pytz.all_timezones:
            raise commands.BadArgument("Choose a valid IANA timezone.")
        schedule_mode = self._rw_value(form, "schedule_mode")
        refresh_time = None
        refresh_interval = None
        if schedule_mode == "daily":
            raw_time = self._rw_value(form, "refresh_time")
            if len(raw_time) != 5 or raw_time[2] != ":":
                raise commands.BadArgument("Choose a valid daily update time.")
            refresh_time = raw_time.replace(":", "")
        elif schedule_mode == "interval":
            try:
                minutes = int(self._rw_value(form, "refresh_minutes"))
            except ValueError as error:
                raise commands.BadArgument("Update interval must be a whole number of minutes.") from error
            if not 1 <= minutes <= 10080:
                raise commands.BadArgument("Update interval must be between 1 and 10,080 minutes.")
            refresh_interval = minutes * 60
        elif schedule_mode != "manual":
            raise commands.BadArgument("Choose a valid update schedule.")
        raw_color = self._rw_value(form, "embed_color").lstrip("#")
        try:
            color = int(raw_color, 16)
        except ValueError as error:
            raise commands.BadArgument("Choose a valid embed color.") from error
        conf = self.config.guild(guild)
        await conf.channel_id.set(channel_id)
        await conf.role_id.set(role_id)
        await conf.tag_role.set(self._rw_checked(form, "tag_role"))
        await conf.show_footer.set(self._rw_checked(form, "show_footer"))
        await conf.time_zone.set(timezone_name)
        await conf.refresh_time.set(refresh_time)
        await conf.refresh_interval.set(refresh_interval)
        await conf.embed_color.set(color)
        await conf.last_refresh.set(0)

    def _rw_source(self, guild, settings, csrf):
        channel_options = self._rw_options(guild.text_channels, settings.get("channel_id"), "Not configured", "#")
        roles = [role for role in reversed(guild.roles) if not role.is_default()]
        role_options = self._rw_options(roles, settings.get("role_id"), "No role", "")
        zones = "".join(
            f'<option value="{html.escape(zone, quote=True)}"'
            f"{' selected' if zone == settings.get('time_zone') else ''}>{html.escape(zone)}</option>"
            for zone in pytz.common_timezones
        )
        if settings.get("refresh_time"):
            mode = "daily"
        elif settings.get("refresh_interval"):
            mode = "interval"
        else:
            mode = "manual"
        raw_time = str(settings.get("refresh_time") or "0900").zfill(4)
        daily_time = f"{raw_time[:2]}:{raw_time[2:]}"
        minutes = int(settings.get("refresh_interval") or 3600) // 60
        color = f"#{int(settings.get('embed_color', 0xFF0000)):06x}"
        return f"""
<section class="rw-dash"><style>
.rw-dash .card{{border:1px solid rgba(127,127,127,.3);border-radius:.65rem;padding:1rem;margin-bottom:1rem}}
.rw-dash .grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:1rem}}
.rw-dash label{{display:flex;flex-direction:column;gap:.3rem}}.rw-dash .check{{flex-direction:row;align-items:center}}
.rw-dash input,.rw-dash select{{padding:.55rem;border:1px solid rgba(127,127,127,.35);border-radius:.35rem;background:var(--background,#202225);color:var(--text,#fff)}}
.rw-dash .check input{{width:auto}}.rw-dash .actions{{display:flex;gap:.6rem;flex-wrap:wrap}}
</style><h2>RandomWeather</h2><p>Schedule immersive RP forecasts for <strong>{html.escape(guild.name)}</strong>.</p>
<form method="POST" class="card">{csrf}<input type="hidden" name="action" value="save"><div class="grid">
<label>Weather channel<select name="channel_id">{channel_options}</select></label>
<label>Notification role<select name="role_id">{role_options}</select></label>
<label class="check"><input type="checkbox" name="tag_role"{self._rw_mark(settings.get("tag_role"))}> Tag the role</label>
<label class="check"><input type="checkbox" name="show_footer"{self._rw_mark(settings.get("show_footer"))}> Show embed footer</label>
<label>Timezone<select name="time_zone">{zones}</select></label>
<label>Schedule<select name="schedule_mode">
<option value="manual"{self._rw_selected(mode, "manual")}>Manual only</option>
<option value="daily"{self._rw_selected(mode, "daily")}>Daily at a fixed time</option>
<option value="interval"{self._rw_selected(mode, "interval")}>Repeating interval</option></select></label>
<label>Daily update time<input type="time" name="refresh_time" value="{daily_time}"></label>
<label>Interval (minutes)<input type="number" name="refresh_minutes" min="1" max="10080" value="{minutes}"></label>
<label>Embed color<input type="color" name="embed_color" value="{color}"></label>
</div><button class="btn btn-primary">Save Weather Settings</button></form>
<section class="card"><h3>Post now</h3><div class="actions">
{self._rw_button(csrf, "post", "Post Forecast")}{self._rw_button(csrf, "extreme", "Post Extreme Alert")}
</div><p>Last refresh timestamp: <code>{html.escape(str(settings.get("last_refresh") or "Never"))}</code></p></section>
</section>"""

    async def _rw_can_manage(self, user, guild):
        member = guild.get_member(user.id)
        return bool(
            user.id in getattr(self.bot, "owner_ids", set())
            or (member and await self.bot.is_admin(member))
            or (member and member.guild_permissions.manage_guild),
        )

    @staticmethod
    def _rw_form(kwargs):
        data = kwargs.get("data") or {}
        return (data.get("form") or data.get("json") or {}) if isinstance(data, dict) else data

    @staticmethod
    def _rw_value(form, key, default=""):
        value = form.get(key, default) if hasattr(form, "get") else default
        if isinstance(value, (list, tuple)):
            value = value[0] if value else default
        return default if value is None else str(value)

    @classmethod
    def _rw_checked(cls, form, key):
        return cls._rw_value(form, key).lower() in {"1", "true", "yes", "on"}

    @classmethod
    def _rw_optional_id(cls, guild, form, key, kind):
        raw = cls._rw_value(form, key)
        if not raw:
            return None
        try:
            item_id = int(raw)
        except ValueError as error:
            raise commands.BadArgument(f"Choose a valid {kind}.") from error
        item = guild.get_channel(item_id) if kind == "channel" else guild.get_role(item_id)
        if kind == "channel" and item not in guild.text_channels:
            raise commands.BadArgument("Choose a valid text channel.")
        if kind == "role" and (item is None or item.is_default()):
            raise commands.BadArgument(f"Choose a valid {kind}.")
        return item_id

    @staticmethod
    def _rw_options(items, selected, empty, prefix):
        return f'<option value="">{empty}</option>' + "".join(
            f'<option value="{item.id}"{" selected" if item.id == selected else ""}>{prefix}{html.escape(item.name)}</option>'
            for item in items
        )

    @staticmethod
    def _rw_mark(value):
        return " checked" if value else ""

    @staticmethod
    def _rw_selected(value, expected):
        return " selected" if value == expected else ""

    @staticmethod
    def _rw_button(csrf, action, label):
        return f'<form method="POST">{csrf}<input type="hidden" name="action" value="{action}"><button class="btn btn-secondary">{label}</button></form>'

    @staticmethod
    def _rw_csrf(kwargs):
        token = kwargs.get("csrf_token")
        if not isinstance(token, (tuple, list)) or len(token) != 2:
            return ""
        return f'<input type="hidden" name="csrf_token" value="{html.escape(str(token[1]), quote=True)}">'
