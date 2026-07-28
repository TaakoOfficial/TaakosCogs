# ruff: noqa: E501
"""Interactive dashboard for Flipper."""

from __future__ import annotations

import html
import random
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
    """A dashboard-native coin toss for this stateless utility cog."""

    @commands.Cog.listener()
    async def on_dashboard_cog_add(self, dashboard_cog: commands.Cog) -> None:
        handler = dashboard_cog.rpc.third_parties_handler
        try:
            handler.add_third_party(self, overwrite=True)
        except TypeError:
            handler.add_third_party(self)

    @dashboard_page(name=None, description="Flip a coin from the dashboard.", methods=("GET", "POST"))
    async def dashboard_page(self, user: discord.User, guild: discord.Guild, **kwargs: Any):
        result = None
        notices = []
        if kwargs.get("method", "GET").upper() == "POST":
            result = random.choice(("Heads", "Tails"))
            notices.append({"message": f"The coin landed on {result}.", "category": "success"})
        side = result or "Ready"
        symbol = "🪙" if result is None else ("👑" if result == "Heads" else "🦅")
        csrf = self._flip_csrf(kwargs)
        source = f"""<section class="flip-dash"><style>.flip-dash{{text-align:center;max-width:680px;margin:auto}}.flip-dash .coin{{font-size:5rem;margin:1rem}}.flip-dash .card{{border:1px solid rgba(127,127,127,.3);border-radius:1rem;padding:2rem}}.flip-dash h3{{font-size:2rem}}</style><h2>Flipper</h2><p>A quick, fair 50/50 toss for <strong>{html.escape(guild.name)}</strong>. Flipper has no server settings or stored history.</p><div class="card"><div class="coin">{symbol}</div><h3>{side}</h3><form method="POST">{csrf}<button class="btn btn-primary btn-lg">Flip the Coin</button></form></div></section>"""
        return {"status": 0, "notifications": notices, "web_content": {"source": source, "expanded": True}}

    @staticmethod
    def _flip_csrf(kwargs):
        token = kwargs.get("csrf_token")
        if not isinstance(token, (tuple, list)) or len(token) != 2:
            return ""
        return f'<input type="hidden" name="csrf_token" value="{html.escape(str(token[1]), quote=True)}">'
