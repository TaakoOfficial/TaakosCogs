# ruff: noqa: E501
"""Purpose-built dashboard for Fable."""

from __future__ import annotations

import html
import logging
from typing import TYPE_CHECKING, Any, Callable

from redbot.core import commands

if TYPE_CHECKING:
    import discord

log = logging.getLogger("red.taakoscogs.fable.dashboard")


def dashboard_page(*args, **kwargs):
    def decorator(func: Callable):
        func.__dashboard_decorator_params__ = (args, kwargs)
        return func

    return decorator


class DashboardIntegration:
    """Fable world overview and campaign policy controls."""

    @commands.Cog.listener()
    async def on_dashboard_cog_add(self, dashboard_cog: commands.Cog) -> None:
        handler = dashboard_cog.rpc.third_parties_handler
        try:
            handler.add_third_party(self, overwrite=True)
        except TypeError:
            handler.add_third_party(self)

    @dashboard_page(name=None, description="Manage Fable campaign categories and mail retention.", methods=("GET", "POST"))
    async def dashboard_page(self, user: discord.User, guild: discord.Guild, **kwargs: Any):
        if not await self._fable_can_manage(user, guild):
            return {"status": 1, "error_title": "Insufficient Permissions", "error_message": "Manage Server is required."}
        notices = []
        if kwargs.get("method", "GET").upper() == "POST":
            try:
                await self._fable_save(guild, self._fable_form(kwargs))
            except (commands.CommandError, ValueError) as error:
                notices.append({"message": str(error), "category": "error"})
            except Exception:
                log.exception("Fable dashboard save failed in guild %s", guild.id)
                notices.append({"message": "Fable settings could not be saved.", "category": "error"})
            else:
                notices.append({"message": "Fable campaign settings saved.", "category": "success"})
        settings = await self.config.guild(guild).all()
        return {
            "status": 0,
            "notifications": notices,
            "web_content": {"source": self._fable_source(guild, settings, self._fable_csrf(kwargs)), "expanded": True},
        }

    async def _fable_save(self, guild, form):
        expiry = self._fable_int(form, "mail_expiry_days", 1, 3650)
        intensity = self._fable_lines(form, "relationship_intensity_levels", 2, 20)
        categories = self._fable_lines(form, "milestone_categories", 1, 30)
        if len({item.casefold() for item in intensity}) != len(intensity):
            raise commands.BadArgument("Relationship levels must be unique.")
        if len({item.casefold() for item in categories}) != len(categories):
            raise commands.BadArgument("Milestone categories must be unique.")
        conf = self.config.guild(guild)
        await conf.mail_expiry_days.set(expiry)
        current = await conf.settings()
        current["relationship_intensity_levels"] = intensity
        current["milestone_categories"] = categories
        await conf.settings.set(current)

    def _fable_source(self, guild, data, csrf):
        settings = data.get("settings", {})
        intensity = html.escape("\n".join(settings.get("relationship_intensity_levels", [])))
        categories = html.escape("\n".join(settings.get("milestone_categories", [])))
        stats = (
            ("Characters", len(data.get("characters", {}))),
            ("Relationships", len(data.get("relationships", {}))),
            ("Story arcs", len(data.get("story_arcs", {}))),
            ("Locations", len(data.get("locations", {}))),
            ("Lore entries", len(data.get("lore", {}))),
            ("Milestones", len(data.get("milestones", {}))),
            ("RP logs", len(data.get("logs", []))),
            ("Mail", len(data.get("mail", {}))),
        )
        cards = "".join(f'<div class="stat"><strong>{count:,}</strong><span>{label}</span></div>' for label, count in stats)
        return f"""
<section class="fable-dash"><style>
.fable-dash .card{{border:1px solid rgba(127,127,127,.3);border-radius:.75rem;padding:1rem;margin-bottom:1rem}}.fable-dash .stats{{display:grid;grid-template-columns:repeat(auto-fit,minmax(125px,1fr));gap:.7rem;margin:1rem 0}}.fable-dash .stat{{padding:.8rem;border-radius:.6rem;background:rgba(127,127,127,.1);display:flex;flex-direction:column}}.fable-dash .stat strong{{font-size:1.45rem}}.fable-dash .grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(270px,1fr));gap:1rem}}.fable-dash label{{display:flex;flex-direction:column;gap:.35rem}}.fable-dash textarea,.fable-dash input{{padding:.6rem;border:1px solid rgba(127,127,127,.35);border-radius:.4rem;background:var(--background,#202225);color:var(--text,#fff)}}.fable-dash textarea{{min-height:13rem;resize:vertical}}
</style><h2>Fable World</h2><p>A campaign overview for <strong>{html.escape(guild.name)}</strong>. Story records remain managed through Fable commands so this page cannot accidentally overwrite your world.</p><div class="stats">{cards}</div>
<form method="POST" class="card">{csrf}<h3>Campaign settings</h3><div class="grid"><label>Relationship progression <small>One level per line, weakest to strongest.</small><textarea name="relationship_intensity_levels" maxlength="1200">{intensity}</textarea></label><label>Milestone categories <small>One category per line.</small><textarea name="milestone_categories" maxlength="1800">{categories}</textarea></label></div><label>Mail expiry (days)<input type="number" name="mail_expiry_days" min="1" max="3650" value="{int(data.get("mail_expiry_days", 30))}"></label><br><button class="btn btn-primary">Save Fable Settings</button></form></section>"""

    async def _fable_can_manage(self, user, guild):
        member = guild.get_member(user.id)
        return bool(
            user.id in getattr(self.bot, "owner_ids", set())
            or (member and await self.bot.is_admin(member))
            or (member and member.guild_permissions.manage_guild),
        )

    @staticmethod
    def _fable_form(kwargs):
        data = kwargs.get("data") or {}
        return (data.get("form") or data.get("json") or {}) if isinstance(data, dict) else data

    @staticmethod
    def _fable_value(form, key, default=""):
        value = form.get(key, default) if hasattr(form, "get") else default
        if isinstance(value, (list, tuple)):
            value = value[0] if value else default
        return default if value is None else str(value)

    @classmethod
    def _fable_int(cls, form, key, minimum, maximum):
        try:
            value = int(cls._fable_value(form, key))
        except ValueError as error:
            raise commands.BadArgument("Mail expiry must be a number.") from error
        if not minimum <= value <= maximum:
            raise commands.BadArgument(f"Mail expiry must be {minimum}–{maximum} days.")
        return value

    @classmethod
    def _fable_lines(cls, form, key, minimum, maximum):
        values = [line.strip() for line in cls._fable_value(form, key).splitlines() if line.strip()]
        if not minimum <= len(values) <= maximum:
            raise commands.BadArgument(f"{key.replace('_', ' ').title()} requires {minimum}–{maximum} entries.")
        if any(len(item) > 80 for item in values):
            raise commands.BadArgument("Each category or level must be 80 characters or shorter.")
        return values

    @staticmethod
    def _fable_csrf(kwargs):
        token = kwargs.get("csrf_token")
        if not isinstance(token, (tuple, list)) or len(token) != 2:
            return ""
        return f'<input type="hidden" name="csrf_token" value="{html.escape(str(token[1]), quote=True)}">'
