# ruff: noqa: E501
"""Purpose-built dashboard for Uppercase channel tools."""

from __future__ import annotations

import html
import logging
from typing import Any, Callable

import discord
from redbot.core import commands

log = logging.getLogger("red.taakoscogs.uppercase.dashboard")


def dashboard_page(*args, **kwargs):
    def decorator(func: Callable):
        func.__dashboard_decorator_params__ = (args, kwargs)
        return func

    return decorator


class DashboardIntegration:
    """Create and rename visibly-uppercase Discord channels."""

    @commands.Cog.listener()
    async def on_dashboard_cog_add(self, dashboard_cog: commands.Cog) -> None:
        handler = dashboard_cog.rpc.third_parties_handler
        try:
            handler.add_third_party(self, overwrite=True)
        except TypeError:
            handler.add_third_party(self)

    @dashboard_page(name=None, description="Create or rename visibly-uppercase channels.", methods=("GET", "POST"))
    async def dashboard_page(self, user: discord.User, guild: discord.Guild, **kwargs: Any):
        if not await self._upper_can_manage(user, guild):
            return {"status": 1, "error_title": "Insufficient Permissions", "error_message": "Manage Channels is required."}
        notices = []
        preview = ""
        form = self._upper_form(kwargs)
        raw_name = self._upper_value(form, "name")
        if raw_name:
            preview = self.format_channel_name(raw_name)
        if kwargs.get("method", "GET").upper() == "POST":
            try:
                message = await self._upper_apply(guild, user, form)
            except (commands.CommandError, ValueError) as error:
                notices.append({"message": str(error), "category": "error"})
            except discord.Forbidden:
                notices.append(
                    {
                        "message": "Discord denied the channel change. Check the bot's role and category permissions.",
                        "category": "error",
                    },
                )
            except discord.HTTPException as error:
                notices.append({"message": f"Discord rejected the channel change: {error.text}", "category": "error"})
            except Exception:
                log.exception("Uppercase dashboard operation failed in guild %s", guild.id)
                notices.append({"message": "The channel operation failed.", "category": "error"})
            else:
                notices.append({"message": message, "category": "success"})
        source = self._upper_source(guild, preview, self._upper_csrf(kwargs))
        return {"status": 0, "notifications": notices, "web_content": {"source": source, "expanded": True}}

    async def _upper_apply(self, guild, user, form):
        action = self._upper_value(form, "action", "preview")
        name = self._upper_value(form, "name").strip()
        if not name:
            raise commands.BadArgument("Enter a channel name.")
        formatted = self.format_channel_name(name)
        if action == "preview":
            return f"Preview: {formatted}"
        reason = f"Uppercase dashboard used by {user} ({user.id})"
        if action == "create":
            category = self._upper_category(guild, form)
            me = guild.me
            if me is None or not me.guild_permissions.manage_channels or not category.permissions_for(me).manage_channels:
                raise commands.BotMissingPermissions(["manage_channels"])
            channel = await guild.create_text_channel(formatted, category=category, reason=reason)
            return f"Created #{channel.name}."
        if action == "rename":
            channel = self._upper_channel(guild, form)
            me = guild.me
            if me is None or not channel.permissions_for(me).manage_channels:
                raise commands.BotMissingPermissions(["manage_channels"])
            await channel.edit(name=formatted, reason=reason)
            return f"Renamed the channel to #{formatted}."
        raise commands.BadArgument("Choose a valid channel action.")

    def _upper_source(self, guild, preview, csrf):
        categories = '<option value="">Choose a category…</option>' + "".join(
            f'<option value="{category.id}">{html.escape(category.name)}</option>' for category in guild.categories
        )
        channels = '<option value="">Choose a text channel…</option>' + "".join(
            f'<option value="{channel.id}">#{html.escape(channel.name)}</option>' for channel in guild.text_channels
        )
        rendered = html.escape(preview or "Your formatted channel name appears here")
        return f"""<section class="upper-dash"><style>.upper-dash .card{{border:1px solid rgba(127,127,127,.3);border-radius:.75rem;padding:1rem;margin-bottom:1rem}}.upper-dash .grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(230px,1fr));gap:1rem}}.upper-dash label{{display:flex;flex-direction:column;gap:.3rem}}.upper-dash input,.upper-dash select{{padding:.6rem;border:1px solid rgba(127,127,127,.35);border-radius:.4rem;background:var(--background,#202225);color:var(--text,#fff)}}.upper-dash .preview{{font-size:1.35rem;padding:1rem;background:rgba(127,127,127,.1);border-radius:.5rem;overflow-wrap:anywhere}}.upper-dash .actions{{display:flex;gap:.6rem;flex-wrap:wrap}}</style><h2>Uppercase Channels</h2><p>Create Discord-safe, visibly uppercase channel names in <strong>{html.escape(guild.name)}</strong>.</p><form method="POST" class="card">{csrf}<label>Channel name<input name="name" maxlength="100" required placeholder="community updates"></label><p class="preview">{rendered}</p><div class="grid"><label>Category for a new channel<select name="category_id">{categories}</select></label><label>Existing channel to rename<select name="channel_id">{channels}</select></label></div><div class="actions"><button class="btn btn-secondary" name="action" value="preview">Preview</button><button class="btn btn-primary" name="action" value="create">Create Channel</button><button class="btn btn-warning" name="action" value="rename">Rename Channel</button></div></form></section>"""

    async def _upper_can_manage(self, user, guild):
        member = guild.get_member(user.id)
        return bool(
            user.id in getattr(self.bot, "owner_ids", set())
            or (member and await self.bot.is_admin(member))
            or (member and member.guild_permissions.manage_channels),
        )

    @staticmethod
    def _upper_form(kwargs):
        data = kwargs.get("data") or {}
        return (data.get("form") or data.get("json") or {}) if isinstance(data, dict) else data

    @staticmethod
    def _upper_value(form, key, default=""):
        value = form.get(key, default) if hasattr(form, "get") else default
        if isinstance(value, (list, tuple)):
            value = value[0] if value else default
        return default if value is None else str(value)

    @classmethod
    def _upper_category(cls, guild, form):
        try:
            category = guild.get_channel(int(cls._upper_value(form, "category_id")))
        except ValueError as error:
            raise commands.BadArgument("Choose a category for the new channel.") from error
        if category not in guild.categories:
            raise commands.BadArgument("Choose a category for the new channel.")
        return category

    @classmethod
    def _upper_channel(cls, guild, form):
        try:
            channel = guild.get_channel(int(cls._upper_value(form, "channel_id")))
        except ValueError as error:
            raise commands.BadArgument("Choose a text channel to rename.") from error
        if channel not in guild.text_channels:
            raise commands.BadArgument("Choose a text channel to rename.")
        return channel

    @staticmethod
    def _upper_csrf(kwargs):
        token = kwargs.get("csrf_token")
        if not isinstance(token, (tuple, list)) or len(token) != 2:
            return ""
        return f'<input type="hidden" name="csrf_token" value="{html.escape(str(token[1]), quote=True)}">'
