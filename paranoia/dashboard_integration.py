# ruff: noqa: E501
"""Purpose-built dashboard for Paranoia."""

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
    """Paranoia question-bank settings and live-game overview."""

    @commands.Cog.listener()
    async def on_dashboard_cog_add(self, dashboard_cog: commands.Cog) -> None:
        handler = dashboard_cog.rpc.third_parties_handler
        try:
            handler.add_third_party(self, overwrite=True)
        except TypeError:
            handler.add_third_party(self)

    @dashboard_page(name=None, description="Manage Paranoia questions and proxy support.", methods=("GET", "POST"))
    async def dashboard_page(self, user: discord.User, guild: discord.Guild, **kwargs: Any):
        if not await self._par_can_manage(user, guild):
            return {"status": 1, "error_title": "Insufficient Permissions", "error_message": "Manage Server is required."}
        notices = []
        if kwargs.get("method", "GET").upper() == "POST":
            form = self._par_form(kwargs)
            questions = [line.strip() for line in self._par_value(form, "custom_questions").splitlines() if line.strip()]
            if len(questions) > 500:
                notices.append({"message": "The custom question bank is limited to 500 questions.", "category": "error"})
            elif any(len(question) > 300 for question in questions):
                notices.append({"message": "Each question must be 300 characters or fewer.", "category": "error"})
            else:
                conf = self.config.guild(guild)
                await conf.custom_questions.set(questions)
                await conf.tupperbox_support.set(self._par_checked(form, "tupperbox_support"))
                notices.append({"message": "Paranoia settings saved.", "category": "success"})
        settings = await self.config.guild(guild).all()
        source = self._par_source(guild, settings, self._par_csrf(kwargs))
        return {"status": 0, "notifications": notices, "web_content": {"source": source, "expanded": True}}

    def _par_source(self, guild, settings, csrf):
        custom = "\n".join(settings.get("custom_questions", []))
        games = settings.get("active_games", {})
        game_rows = []
        for channel_id, game in games.items():
            channel = guild.get_channel(int(channel_id))
            name = f"#{channel.name}" if channel else f"Deleted channel ({channel_id})"
            game_rows.append(
                f"<tr><td>{html.escape(name)}</td><td>{int(game.get('round', 0))}</td>"
                f"<td>{len(game.get('players', []))}</td><td>{len(game.get('current_answers', {}))}</td></tr>",
            )
        rows = "".join(game_rows) or '<tr><td colspan="4">No games are currently running.</td></tr>'
        enabled = " checked" if settings.get("tupperbox_support") else ""
        return f"""
<section class="par-dash"><style>
.par-dash .card{{border:1px solid rgba(127,127,127,.3);border-radius:.65rem;padding:1rem;margin-bottom:1rem}}
.par-dash textarea{{width:100%;min-height:18rem;padding:.6rem;background:var(--background,#202225);color:var(--text,#fff);border:1px solid rgba(127,127,127,.35);border-radius:.35rem}}
.par-dash .check{{display:flex;align-items:center;gap:.5rem}}.par-dash table{{width:100%}}.par-dash th,.par-dash td{{padding:.45rem;text-align:left}}
</style><h2>Paranoia</h2><p>Manage the question pool and proxy behavior for <strong>{html.escape(guild.name)}</strong>.</p>
<form method="POST" class="card">{csrf}
<label class="check"><input type="checkbox" name="tupperbox_support"{enabled}> Enable Tupperbox/proxy support</label>
<h3>Custom questions</h3><p>Enter one question per line. The built-in question bank remains available.</p>
<textarea name="custom_questions" maxlength="151000" spellcheck="true">{html.escape(custom)}</textarea>
<p>{len(settings.get("custom_questions", []))} custom · {len(self.default_questions)} built-in questions</p>
<button class="btn btn-primary">Save Question Settings</button></form>
<section class="card"><h3>Active games</h3><table><thead><tr><th>Channel</th><th>Round</th><th>Players</th><th>Answers</th></tr></thead><tbody>{rows}</tbody></table></section>
</section>"""

    async def _par_can_manage(self, user, guild):
        member = guild.get_member(user.id)
        return bool(
            user.id in getattr(self.bot, "owner_ids", set())
            or (member and await self.bot.is_admin(member))
            or (member and member.guild_permissions.manage_guild),
        )

    @staticmethod
    def _par_form(kwargs):
        data = kwargs.get("data") or {}
        return (data.get("form") or data.get("json") or {}) if isinstance(data, dict) else data

    @staticmethod
    def _par_value(form, key, default=""):
        value = form.get(key, default) if hasattr(form, "get") else default
        if isinstance(value, (list, tuple)):
            value = value[0] if value else default
        return default if value is None else str(value)

    @classmethod
    def _par_checked(cls, form, key):
        return cls._par_value(form, key).lower() in {"1", "true", "on", "yes"}

    @staticmethod
    def _par_csrf(kwargs):
        token = kwargs.get("csrf_token")
        if not isinstance(token, (tuple, list)) or len(token) != 2:
            return ""
        return f'<input type="hidden" name="csrf_token" value="{html.escape(str(token[1]), quote=True)}">'
