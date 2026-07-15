# ruff: noqa: E501
"""Purpose-built dashboard for ReviewHub."""

from __future__ import annotations

import html
import logging
from typing import TYPE_CHECKING, Any, Callable

from redbot.core import commands

if TYPE_CHECKING:
    import discord

log = logging.getLogger("red.taakoscogs.reviewhub.dashboard")


def dashboard_page(*args, **kwargs):
    def decorator(func: Callable):
        func.__dashboard_decorator_params__ = (args, kwargs)
        return func

    return decorator


class DashboardIntegration:
    """Review publishing, moderation, and presentation controls."""

    @commands.Cog.listener()
    async def on_dashboard_cog_add(self, dashboard_cog: commands.Cog) -> None:
        handler = dashboard_cog.rpc.third_parties_handler
        try:
            handler.add_third_party(self, overwrite=True)
        except TypeError:
            handler.add_third_party(self)

    @dashboard_page(name=None, description="Configure reviews, vouches, and moderation.", methods=("GET", "POST"))
    async def dashboard_page(self, user: discord.User, guild: discord.Guild, **kwargs: Any):
        if not await self._rh_can_manage(user, guild):
            return {"status": 1, "error_title": "Insufficient Permissions", "error_message": "Manage Server is required."}
        notices = []
        if kwargs.get("method", "GET").upper() == "POST":
            try:
                await self._rh_save(guild, self._rh_form(kwargs))
            except (commands.CommandError, ValueError) as error:
                notices.append({"message": str(error), "category": "error"})
            except Exception:
                log.exception("ReviewHub dashboard save failed in guild %s", guild.id)
                notices.append({"message": "ReviewHub settings could not be saved.", "category": "error"})
            else:
                notices.append({"message": "ReviewHub settings saved.", "category": "success"})
        settings = await self.config.guild(guild).all()
        return {
            "status": 0,
            "notifications": notices,
            "web_content": {"source": self._rh_source(guild, settings, self._rh_csrf(kwargs)), "expanded": True},
        }

    async def _rh_save(self, guild, form):
        template = self._rh_value(form, "review_template", "classic").lower()
        if template not in {"classic", "detailed"}:
            raise commands.BadArgument("Review template must be classic or detailed.")
        command_name = self._rh_value(form, "review_command_name", "review").strip().lower()
        if not command_name or not command_name.replace("-", "").replace("_", "").isalnum() or len(command_name) > 32:
            raise commands.BadArgument("Command name must be 1–32 letters, numbers, hyphens, or underscores.")
        color_text = self._rh_value(form, "review_embed_color", "#5865F2").lstrip("#")
        try:
            color = int(color_text, 16)
        except ValueError as error:
            raise commands.BadArgument("Choose a valid embed color.") from error
        if not 0 <= color <= 0xFFFFFF:
            raise commands.BadArgument("Choose a valid embed color.")
        daily_limit = self._rh_int(form, "daily_limit", 1, 100)
        values = {
            "review_channel_id": self._rh_channel(guild, form, "review_channel_id"),
            "report_channel_id": self._rh_channel(guild, form, "report_channel_id"),
            "rateme_role_id": self._rh_role(guild, form, "rateme_role_id"),
            "review_command_role_id": self._rh_role(guild, form, "review_command_role_id"),
            "review_template": template,
            "review_embed_color": color,
            "daily_limit": daily_limit,
            "review_command_name": command_name,
        }
        for key in (
            "review_title",
            "thread_title",
            "rateme_message",
            "review_request_title",
            "rate_experience_title",
            "review_button_label",
            "review_author_text",
            "star_emoji",
            "report_button_emoji",
            "submit_review_emoji",
            "useful_button_emoji",
        ):
            value = self._rh_value(form, key).strip()
            if not value:
                raise commands.BadArgument(f"{key.replace('_', ' ').title()} cannot be empty.")
            values[key] = value[:1000]
        for key in (
            "review_button_show",
            "report_button_show",
            "useful_button_show",
            "auto_thread",
            "review_command_enabled",
            "delete_review_requests",
            "vouch_mode",
            "review_targets_enabled",
        ):
            values[key] = self._rh_checked(form, key)
        conf = self.config.guild(guild)
        for key, value in values.items():
            await getattr(conf, key).set(value)

    def _rh_source(self, guild, settings, csrf):
        reviews = settings.get("reviews", {})
        requests = settings.get("requests", {})
        active = sum(1 for record in reviews.values() if record.get("active", True))
        pending = sum(1 for request in requests.values() if request.get("status", "pending") == "pending")
        channel_options = self._rh_channel_options(guild, settings.get("review_channel_id"))
        report_options = self._rh_channel_options(guild, settings.get("report_channel_id"))
        rate_roles = self._rh_role_options(guild, settings.get("rateme_role_id"))
        command_roles = self._rh_role_options(guild, settings.get("review_command_role_id"))

        def value(key, default=""):
            return html.escape(str(settings.get(key, default)), quote=True)

        def check(key):
            return " checked" if settings.get(key) else ""

        def selected(option):
            return " selected" if settings.get("review_template", "classic") == option else ""

        color = f"#{int(settings.get('review_embed_color', 0x5865F2)):06X}"
        return f"""
<section class="rh-dash"><style>
.rh-dash .card{{border:1px solid rgba(127,127,127,.3);border-radius:.7rem;padding:1rem;margin-bottom:1rem}}.rh-dash .grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(230px,1fr));gap:1rem}}.rh-dash label{{display:flex;flex-direction:column;gap:.3rem}}.rh-dash .check{{flex-direction:row;align-items:center}}.rh-dash input,.rh-dash select{{padding:.55rem;border:1px solid rgba(127,127,127,.35);border-radius:.35rem;background:var(--background,#202225);color:var(--text,#fff)}}.rh-dash .stat{{font-size:1.5rem;font-weight:700}}
</style><h2>ReviewHub</h2><p>Run reviews or vouches for <strong>{html.escape(guild.name)}</strong>.</p>
<div class="grid"><div class="card"><span class="stat">{active:,}</span><br>active reviews</div><div class="card"><span class="stat">{pending:,}</span><br>pending requests</div><div class="card"><span class="stat">{int(settings.get("daily_count", 0))}</span><br>submitted today</div></div>
<form method="POST">{csrf}<div class="card"><h3>Destinations & access</h3><div class="grid">
<label>Review channel<select name="review_channel_id">{channel_options}</select></label><label>Report channel<select name="report_channel_id">{report_options}</select></label><label>/rateme role<select name="rateme_role_id">{rate_roles}</select></label><label>Review command role<select name="review_command_role_id">{command_roles}</select></label><label>Daily review limit<input type="number" name="daily_limit" min="1" max="100" value="{value("daily_limit", 5)}"></label><label>Command name<input name="review_command_name" maxlength="32" value="{value("review_command_name", "review")}"></label>
<label class="check"><input type="checkbox" name="review_command_enabled"{check("review_command_enabled")}> Enable review command</label><label class="check"><input type="checkbox" name="delete_review_requests"{check("delete_review_requests")}> Delete completed request messages</label></div></div>
<div class="card"><h3>Experience</h3><div class="grid"><label>Mode<select name="review_template"><option value="classic"{selected("classic")}>Classic</option><option value="detailed"{selected("detailed")}>Detailed</option></select></label><label>Embed color<input type="color" name="review_embed_color" value="{color}"></label><label>Review title<input name="review_title" value="{value("review_title", "New Review")}"></label><label>Button label<input name="review_button_label" value="{value("review_button_label", "Submit Review")}"></label><label>Request title<input name="review_request_title" value="{value("review_request_title", "Review Request")}"></label><label>Rating title<input name="rate_experience_title" value="{value("rate_experience_title", "Rate your experience")}"></label><label>Thread title<input name="thread_title" value="{value("thread_title", "Review {id} discussion")}"></label><label>Author text<input name="review_author_text" value="{value("review_author_text", "{user} submitted a review")}"></label><label>Request message<input name="rateme_message" value="{value("rateme_message", "{reviewer}, {requester} requested a review from you.")}"></label><label>Star emoji<input name="star_emoji" value="{value("star_emoji", "⭐")}"></label><label>Report emoji<input name="report_button_emoji" value="{value("report_button_emoji", "⚠️")}"></label><label>Submit emoji<input name="submit_review_emoji" value="{value("submit_review_emoji", "📝")}"></label><label>Useful emoji<input name="useful_button_emoji" value="{value("useful_button_emoji", "👍")}"></label></div>
<div class="grid"><label class="check"><input type="checkbox" name="review_button_show"{check("review_button_show")}> Show review button</label><label class="check"><input type="checkbox" name="report_button_show"{check("report_button_show")}> Show report button</label><label class="check"><input type="checkbox" name="useful_button_show"{check("useful_button_show")}> Show useful button</label><label class="check"><input type="checkbox" name="auto_thread"{check("auto_thread")}> Create discussion threads</label><label class="check"><input type="checkbox" name="vouch_mode"{check("vouch_mode")}> Use vouch mode</label><label class="check"><input type="checkbox" name="review_targets_enabled"{check("review_targets_enabled")}> Allow review targets</label></div></div><button class="btn btn-primary">Save ReviewHub Settings</button></form></section>"""

    async def _rh_can_manage(self, user, guild):
        member = guild.get_member(user.id)
        return bool(
            user.id in getattr(self.bot, "owner_ids", set())
            or (member and await self.bot.is_admin(member))
            or (member and member.guild_permissions.manage_guild),
        )

    @staticmethod
    def _rh_form(kwargs):
        data = kwargs.get("data") or {}
        return (data.get("form") or data.get("json") or {}) if isinstance(data, dict) else data

    @staticmethod
    def _rh_value(form, key, default=""):
        value = form.get(key, default) if hasattr(form, "get") else default
        if isinstance(value, (list, tuple)):
            value = value[0] if value else default
        return default if value is None else str(value)

    @classmethod
    def _rh_checked(cls, form, key):
        return cls._rh_value(form, key).lower() in {"1", "true", "on", "yes"}

    @classmethod
    def _rh_int(cls, form, key, minimum, maximum):
        try:
            value = int(cls._rh_value(form, key))
        except ValueError as error:
            raise commands.BadArgument(f"{key.replace('_', ' ')} must be a number.") from error
        if not minimum <= value <= maximum:
            raise commands.BadArgument(f"{key.replace('_', ' ')} must be {minimum}–{maximum}.")
        return value

    @classmethod
    def _rh_channel(cls, guild, form, key):
        raw = cls._rh_value(form, key)
        if not raw:
            return None
        try:
            channel = guild.get_channel(int(raw))
        except ValueError as error:
            raise commands.BadArgument("Choose a valid text channel.") from error
        if channel not in guild.text_channels:
            raise commands.BadArgument("Choose a valid text channel.")
        return channel.id

    @classmethod
    def _rh_role(cls, guild, form, key):
        raw = cls._rh_value(form, key)
        if not raw:
            return None
        try:
            role = guild.get_role(int(raw))
        except ValueError as error:
            raise commands.BadArgument("Choose a valid role.") from error
        if role is None or role.is_default():
            raise commands.BadArgument("Choose a valid role.")
        return role.id

    @staticmethod
    def _rh_channel_options(guild, selected):
        return '<option value="">Not configured</option>' + "".join(
            f'<option value="{channel.id}"{" selected" if channel.id == selected else ""}>#{html.escape(channel.name)}</option>'
            for channel in guild.text_channels
        )

    @staticmethod
    def _rh_role_options(guild, selected):
        return '<option value="">Everyone / unrestricted</option>' + "".join(
            f'<option value="{role.id}"{" selected" if role.id == selected else ""}>{html.escape(role.name)}</option>'
            for role in reversed(guild.roles)
            if not role.is_default()
        )

    @staticmethod
    def _rh_csrf(kwargs):
        token = kwargs.get("csrf_token")
        if not isinstance(token, (tuple, list)) or len(token) != 2:
            return ""
        return f'<input type="hidden" name="csrf_token" value="{html.escape(str(token[1]), quote=True)}">'
