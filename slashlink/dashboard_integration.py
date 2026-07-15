# ruff: noqa: E501
"""Purpose-built status dashboard for SlashLink."""

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
    """Live inventory of generated prefix-command gateways."""

    @commands.Cog.listener()
    async def on_dashboard_cog_add(self, dashboard_cog: commands.Cog) -> None:
        handler = dashboard_cog.rpc.third_parties_handler
        try:
            handler.add_third_party(self, overwrite=True)
        except TypeError:
            handler.add_third_party(self)

    @dashboard_page(name=None, description="Inspect SlashLink's live command gateways.", methods=("GET", "POST"))
    async def dashboard_page(self, user: discord.User, guild: discord.Guild, **kwargs: Any):
        if not await self._slash_can_manage(user, guild):
            return {"status": 1, "error_title": "Insufficient Permissions", "error_message": "Manage Server is required."}
        notices = []
        if kwargs.get("method", "GET").upper() == "POST":
            notices.append({"message": "SlashLink inventory refreshed from the live command tree.", "category": "success"})
        rows = []
        for cog_name, record in sorted(self._proxies.items()):
            cog = self.bot.get_cog(cog_name)
            prefix_commands = self._prefix_commands(cog) if cog is not None else []
            sample = ", ".join(html.escape(command.qualified_name) for command in prefix_commands[:4])
            if len(prefix_commands) > 4:
                sample += f" +{len(prefix_commands) - 4} more"
            rows.append(
                f"<tr><td>{html.escape(cog_name)}</td><td><code>/{html.escape(record.command_name)}</code></td><td>{len(prefix_commands)}</td><td>{sample or 'None'}</td><td><span class='ok'>Live</span></td></tr>",
            )
        table_rows = "".join(rows) or '<tr><td colspan="5">No prefix-only cogs currently need a SlashLink gateway.</td></tr>'
        native_count = sum(1 for cog in self.bot.cogs.values() if cog is not self and self._has_application_commands(cog))
        prefix_only = len(self._proxies)
        csrf = self._slash_csrf(kwargs)
        source = f"""<section class="slash-dash"><style>.slash-dash .stats{{display:grid;grid-template-columns:repeat(auto-fit,minmax(160px,1fr));gap:.8rem;margin:1rem 0}}.slash-dash .card{{border:1px solid rgba(127,127,127,.3);border-radius:.7rem;padding:1rem}}.slash-dash .stat{{font-size:1.6rem;font-weight:700}}.slash-dash table{{width:100%;border-collapse:collapse}}.slash-dash th,.slash-dash td{{padding:.6rem;border-bottom:1px solid rgba(127,127,127,.25);text-align:left;vertical-align:top}}.slash-dash .ok{{color:#3ba55c;font-weight:700}}.slash-dash .note{{opacity:.8}}</style><h2>SlashLink Gateways</h2><p>Live application-command coverage for the bot. Gateways are created and removed automatically as cogs load or unload.</p><div class="stats"><div class="card"><span class="stat">{prefix_only}</span><br>generated gateways</div><div class="card"><span class="stat">{native_count}</span><br>cogs with native slash commands</div><div class="card"><span class="stat">{len(self.bot.cogs)}</span><br>loaded cogs</div></div><div class="card" style="overflow:auto"><table><thead><tr><th>Cog</th><th>Gateway</th><th>Commands</th><th>Examples</th><th>Status</th></tr></thead><tbody>{table_rows}</tbody></table></div><p class="note">SlashLink has no per-server settings: its gateways are global Red application commands, and Red's application-command manager controls whether they are enabled in this server.</p><form method="POST">{csrf}<button class="btn btn-primary">Refresh Live Inventory</button></form></section>"""
        return {"status": 0, "notifications": notices, "web_content": {"source": source, "expanded": True}}

    async def _slash_can_manage(self, user, guild):
        member = guild.get_member(user.id)
        return bool(
            user.id in getattr(self.bot, "owner_ids", set())
            or (member and await self.bot.is_admin(member))
            or (member and member.guild_permissions.manage_guild),
        )

    @staticmethod
    def _slash_csrf(kwargs):
        token = kwargs.get("csrf_token")
        if not isinstance(token, (tuple, list)) or len(token) != 2:
            return ""
        return f'<input type="hidden" name="csrf_token" value="{html.escape(str(token[1]), quote=True)}">'
