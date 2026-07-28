"""Purpose-built Red-Web-Dashboard controls for RPCalander."""

from __future__ import annotations

import html
import logging
from datetime import date
from typing import Any, Callable

import discord
import pytz
from redbot.core import commands

log = logging.getLogger("red.taakoscogs.rpcalander.dashboard")


def dashboard_page(*args, **kwargs):
    def decorator(func: Callable):
        func.__dashboard_decorator_params__ = (args, kwargs)
        return func

    return decorator


class DashboardIntegration:
    """Dashboard mixin for RP calendar and moon settings."""

    @commands.Cog.listener()
    async def on_dashboard_cog_add(self, dashboard_cog: commands.Cog) -> None:
        handler = dashboard_cog.rpc.third_parties_handler
        try:
            handler.add_third_party(self, overwrite=True)
        except TypeError:
            handler.add_third_party(self)

    @dashboard_page(
        name=None,
        description="Configure the RP calendar, daily posts, and moon simulation.",
        methods=("GET", "POST"),
    )
    async def dashboard_page(
        self,
        user: discord.User,
        guild: discord.Guild,
        **kwargs: Any,
    ) -> dict[str, Any]:
        if not await self._dash_can_manage(user, guild):
            return self._dash_error("Insufficient Permissions", "You need Manage Server access.")
        notices = []
        if kwargs.get("method", "GET").upper() == "POST":
            form = self._dash_form(kwargs)
            try:
                message = await self._dash_action(guild, self._dash_value(form, "action"), form)
            except (commands.CommandError, ValueError) as error:
                notices.append({"message": str(error), "category": "error"})
            except Exception as error:
                log.exception("RPCalander dashboard action failed")
                notices.append({"message": f"Dashboard action failed: {error}", "category": "error"})
            else:
                notices.append({"message": message, "category": "success"})
        try:
            source = await self._dash_source(guild, kwargs)
        except Exception as error:
            log.exception("RPCalander dashboard render failed")
            return self._dash_error("Dashboard Error", f"Could not render the page: {error}")
        return {
            "status": 0,
            "notifications": notices,
            "web_content": {"source": source, "expanded": True},
        }

    async def _dash_can_manage(self, user: discord.User, guild: discord.Guild) -> bool:
        member = guild.get_member(user.id)
        return bool(
            user.id in getattr(self.bot, "owner_ids", set())
            or (member is not None and await self.bot.is_admin(member))
            or (member is not None and member.guild_permissions.manage_guild),
        )

    async def _dash_action(self, guild: discord.Guild, action: str, form: Any) -> str:
        if action == "save":
            await self._dash_save(guild, form)
            return "RP calendar settings saved."
        if action == "post_calendar":
            success, message = await self.force_post(guild)
            if not success:
                raise commands.CommandError(message)
            return message
        if action == "post_moon":
            settings = await self._config.guild(guild).all()
            if not settings.get("show_moon_phase"):
                raise commands.CommandError("Enable moon phases before posting a moon update.")
            if not settings.get("current_date"):
                raise commands.CommandError("Set the current RP date first.")
            await self._post_moon_update(guild)
            return "Moon phase update posted."
        raise commands.BadArgument("Choose a valid dashboard action.")

    async def _dash_save(self, guild: discord.Guild, form: Any) -> None:
        title = self._dash_value(form, "embed_title").strip()
        if not 1 <= len(title) <= 256:
            raise commands.BadArgument("Embed title must contain 1 to 256 characters.")
        timezone_name = self._dash_value(form, "time_zone")
        if timezone_name not in pytz.all_timezones:
            raise commands.BadArgument("Choose a valid IANA timezone.")
        color = self._dash_color(form, "embed_color")
        channel_id = self._dash_channel_id(guild, form, "channel_id", required=False)
        moon_channel_id = self._dash_channel_id(guild, form, "moon_channel_id", required=False)
        start_date = self._dash_date(form, "start_date")
        current_date = self._dash_date(form, "current_date")

        conf = self._config.guild(guild)
        await conf.embed_title.set(title)
        await conf.time_zone.set(timezone_name)
        await conf.embed_color.set(color)
        await conf.channel_id.set(channel_id)
        await conf.moon_channel_id.set(moon_channel_id)
        await conf.start_date.set(start_date)
        await conf.current_date.set(current_date)
        await conf.show_footer.set(self._dash_checked(form, "show_footer"))
        await conf.show_moon_phase.set(self._dash_checked(form, "show_moon_phase"))
        await conf.blood_moon_enabled.set(self._dash_checked(form, "blood_moon_enabled"))

    async def _dash_source(self, guild: discord.Guild, kwargs: dict[str, Any]) -> str:
        settings = await self._config.guild(guild).all()
        csrf = self._dash_csrf(kwargs)
        channels = self._dash_channel_options(guild, settings.get("channel_id"), optional=True)
        moon_channels = self._dash_channel_options(
            guild,
            settings.get("moon_channel_id"),
            optional=True,
            empty_label="Same as calendar channel",
        )
        timezones = "".join(
            f'<option value="{html.escape(zone, quote=True)}"'
            f"{' selected' if zone == settings.get('time_zone') else ''}>{html.escape(zone)}</option>"
            for zone in pytz.common_timezones
        )
        current = self._dash_html_date(settings.get("current_date"))
        start = self._dash_html_date(settings.get("start_date"))
        color = f"#{int(settings.get('embed_color', 0x0000FF)):06x}"
        last_posted = html.escape(str(settings.get("last_posted") or "Never"))
        return f"""
<section class="rpc-dash">
<style>
.rpc-dash .grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(230px,1fr));gap:1rem}}
.rpc-dash .card{{border:1px solid rgba(127,127,127,.3);border-radius:.65rem;padding:1rem;margin-bottom:1rem}}
.rpc-dash label{{display:flex;flex-direction:column;gap:.3rem;margin-bottom:.8rem}}
.rpc-dash input,.rpc-dash select{{width:100%;padding:.55rem;border-radius:.35rem;
border:1px solid rgba(127,127,127,.35);background:var(--background,#202225);
color:var(--text,#fff)}}
.rpc-dash .check{{display:flex;flex-direction:row;align-items:center;gap:.5rem}}.rpc-dash .check input{{width:auto}}
.rpc-dash .actions{{display:flex;gap:.6rem;flex-wrap:wrap}}.rpc-dash .muted{{opacity:.75}}
</style>
<h2>RP Calendar</h2>
<p>Configure the in-world date, daily calendar post, and moon simulation for
<strong>{html.escape(guild.name)}</strong>.</p>
<form method="POST" class="card">{csrf}<input type="hidden" name="action" value="save">
  <div class="grid">
    <section><h3>Calendar</h3>
      <label>Calendar channel<select name="channel_id">{channels}</select></label>
      <label>Timeline start date<input type="date" name="start_date" value="{start}"></label>
      <label>Current RP date<input type="date" name="current_date" value="{current}"></label>
      <label>Timezone<select name="time_zone">{timezones}</select></label>
    </section>
    <section><h3>Appearance</h3>
      <label>Embed title<input name="embed_title" maxlength="256"
      value="{html.escape(str(settings.get("embed_title") or ""), quote=True)}" required></label>
      <label>Embed color<input type="color" name="embed_color" value="{color}"></label>
      <label class="check"><input type="checkbox" name="show_footer"
      {self._dash_checked_attr(settings.get("show_footer"))}> Show calendar footer</label>
      <p class="muted">Last automatic post: {last_posted}</p>
    </section>
    <section><h3>Moon simulation</h3>
      <label class="check"><input type="checkbox" name="show_moon_phase"
      {self._dash_checked_attr(settings.get("show_moon_phase"))}> Enable moon phases</label>
      <label class="check"><input type="checkbox" name="blood_moon_enabled"
      {self._dash_checked_attr(settings.get("blood_moon_enabled"))}> Allow blood moons</label>
      <label>Moon channel<select name="moon_channel_id">{moon_channels}</select></label>
    </section>
  </div>
  <button class="btn btn-primary" type="submit">Save Calendar Settings</button>
</form>
<section class="card"><h3>Post now</h3><div class="actions">
  <form method="POST">{csrf}<input type="hidden" name="action" value="post_calendar">
  <button class="btn btn-secondary">Post Calendar Update</button></form>
  <form method="POST">{csrf}<input type="hidden" name="action" value="post_moon">
  <button class="btn btn-secondary">Post Moon Update</button></form>
</div></section>
</section>"""

    @staticmethod
    def _dash_form(kwargs: dict[str, Any]) -> Any:
        data = kwargs.get("data") or {}
        return (data.get("form") or data.get("json") or {}) if isinstance(data, dict) else data

    @staticmethod
    def _dash_value(form: Any, key: str, default: str = "") -> str:
        value = form.get(key, default) if hasattr(form, "get") else default
        if isinstance(value, (list, tuple)):
            value = value[0] if value else default
        return default if value is None else str(value)

    @classmethod
    def _dash_checked(cls, form: Any, key: str) -> bool:
        return cls._dash_value(form, key).lower() in {"1", "true", "yes", "on"}

    @staticmethod
    def _dash_checked_attr(value: Any) -> str:
        return " checked" if value else ""

    @classmethod
    def _dash_channel_id(cls, guild, form, key, *, required: bool) -> int | None:
        raw = cls._dash_value(form, key).strip()
        if not raw and not required:
            return None
        try:
            channel_id = int(raw)
        except ValueError as error:
            raise commands.BadArgument("Choose a valid channel.") from error
        if not isinstance(guild.get_channel(channel_id), discord.TextChannel):
            raise commands.BadArgument("Choose a valid text channel.")
        return channel_id

    @staticmethod
    def _dash_channel_options(guild, selected, *, optional=False, empty_label="Not configured") -> str:
        options = [f'<option value="">{html.escape(empty_label)}</option>'] if optional else []
        options.extend(
            f'<option value="{channel.id}"{" selected" if channel.id == selected else ""}>#{html.escape(channel.name)}</option>'
            for channel in guild.text_channels
        )
        return "".join(options)

    @classmethod
    def _dash_color(cls, form: Any, key: str) -> int:
        raw = cls._dash_value(form, key).strip().lstrip("#")
        try:
            value = int(raw, 16)
        except ValueError as error:
            raise commands.BadArgument("Choose a valid embed color.") from error
        if not 0 <= value <= 0xFFFFFF:
            raise commands.BadArgument("Choose a valid embed color.")
        return value

    @classmethod
    def _dash_date(cls, form: Any, key: str) -> str | None:
        raw = cls._dash_value(form, key).strip()
        if not raw:
            return None
        try:
            return date.fromisoformat(raw).strftime("%m-%d-%Y")
        except ValueError as error:
            raise commands.BadArgument("Choose a valid date.") from error

    @staticmethod
    def _dash_html_date(value: Any) -> str:
        if not value:
            return ""
        try:
            month, day, year = (int(part) for part in str(value).split("-"))
            return date(year, month, day).isoformat()
        except (TypeError, ValueError):
            return ""

    @staticmethod
    def _dash_csrf(kwargs: dict[str, Any]) -> str:
        token = kwargs.get("csrf_token")
        if not isinstance(token, (tuple, list)) or len(token) != 2:
            return ""
        return f'<input type="hidden" name="csrf_token" value="{html.escape(str(token[1]), quote=True)}">'

    @staticmethod
    def _dash_error(title: str, message: str) -> dict[str, Any]:
        return {"status": 1, "error_title": title, "error_message": message}
