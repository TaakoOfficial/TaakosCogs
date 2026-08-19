# ruff: noqa: E501
"""Purpose-built dashboard for KnowledgeGarden."""

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

    @dashboard_page(name=None, description="Inspect knowledge status and configure review separation.", methods=("GET", "POST"))
    async def dashboard_page(self, user: discord.User, guild: discord.Guild, **kwargs: Any):
        member = guild.get_member(user.id)
        if not (
            user.id in getattr(self.bot, "owner_ids", set())
            or (member and await self.bot.is_admin(member))
            or (member and member.guild_permissions.manage_guild)
        ):
            return {"status": 1, "error_title": "Insufficient Permissions", "error_message": "Manage Server is required."}
        conf = self.config.guild(guild)
        notices = []
        if kwargs.get("method", "GET").upper() == "POST":
            data = kwargs.get("data") or {}
            form = (data.get("form") or data.get("json") or {}) if isinstance(data, dict) else data
            raw = form.get("require_separate_publisher", "") if hasattr(form, "get") else ""
            raw = raw[0] if isinstance(raw, (list, tuple)) and raw else raw
            await conf.require_separate_publisher.set(str(raw).casefold() in {"1", "true", "on", "yes"})
            auto_raw = form.get("auto_capture_forumflow", "") if hasattr(form, "get") else ""
            auto_raw = auto_raw[0] if isinstance(auto_raw, (list, tuple)) and auto_raw else auto_raw
            await conf.auto_capture_forumflow.set(str(auto_raw).casefold() in {"1", "true", "on", "yes"})
            notices.append({"message": "KnowledgeGarden settings saved.", "category": "success"})
        settings = await conf.all()
        counts = {"draft": 0, "published": 0, "retired": 0}
        for item in settings["entries"].values():
            counts[item["status"]] += 1
        feedback_count = sum(len(item.get("feedback", {})) for item in settings["entries"].values())
        csrf = kwargs.get("csrf_token")
        csrf_html = (
            ""
            if not isinstance(csrf, (tuple, list)) or len(csrf) != 2
            else f'<input type="hidden" name="csrf_token" value="{html.escape(str(csrf[1]), quote=True)}">'
        )
        checked = " checked" if settings["require_separate_publisher"] else ""
        auto_checked = " checked" if settings["auto_capture_forumflow"] else ""
        forumflow = "loaded" if self.bot.get_cog("ForumFlow") else "not loaded"
        reviews = (
            f"after {settings['stale_days']} days in <#{settings['review_channel_id']}>"
            if settings["review_channel_id"]
            else "disabled"
        )
        source = f'<section><h2>KnowledgeGarden</h2><p><b>{counts["published"]}</b> published · <b>{counts["draft"]}</b> drafts · <b>{counts["retired"]}</b> retired</p><p><b>{feedback_count}</b> feedback ratings · <b>{len(settings["missed_searches"])}</b> unanswered phrases · stale reviews <b>{reviews}</b></p><p>ForumFlow is <b>{forumflow}</b>.</p><form method="POST">{csrf_html}<label><input type="checkbox" name="require_separate_publisher" value="1"{checked}> Require a different staff member to publish a draft</label><br><label><input type="checkbox" name="auto_capture_forumflow" value="1"{auto_checked}> Automatically draft accepted ForumFlow answers</label><br><button class="btn btn-primary">Save KnowledgeGarden Settings</button></form><p>Draft creation, review, editing, search, and export remain Discord commands so permissions and source-message access are checked live.</p></section>'
        return {"status": 0, "notifications": notices, "web_content": {"source": source, "expanded": True}}
