# ruff: noqa: E501
"""Purpose-built dashboard for EmojiPorter."""

from __future__ import annotations

import asyncio
import html
import logging
from typing import TYPE_CHECKING, Any, Callable

from redbot.core import commands

if TYPE_CHECKING:
    import discord

log = logging.getLogger("red.taakoscogs.emojiporter.dashboard")


def dashboard_page(*args, **kwargs):
    def decorator(func: Callable):
        func.__dashboard_decorator_params__ = (args, kwargs)
        return func

    return decorator


class DashboardIntegration:
    """Browse and copy emoji or sticker assets between mutual servers."""

    @commands.Cog.listener()
    async def on_dashboard_cog_add(self, dashboard_cog: commands.Cog) -> None:
        handler = dashboard_cog.rpc.third_parties_handler
        try:
            handler.add_third_party(self, overwrite=True)
        except TypeError:
            handler.add_third_party(self)

    @dashboard_page(name=None, description="Browse and copy emojis or stickers between servers.", methods=("GET", "POST"))
    async def dashboard_page(self, user: discord.User, guild: discord.Guild, **kwargs: Any):
        if not await self._porter_can_manage(user, guild):
            return {"status": 1, "error_title": "Insufficient Permissions", "error_message": "Manage Expressions is required."}
        form = self._porter_form(kwargs)
        source_id = self._porter_value(form, "source_guild_id")
        source_guild = self.bot.get_guild(int(source_id)) if source_id.isdigit() else None
        notices = []
        if kwargs.get("method", "GET").upper() == "POST" and self._porter_value(form, "action") in {
            "copy_emojis",
            "copy_stickers",
        }:
            try:
                message = await self._porter_copy(user, guild, form)
            except (commands.CommandError, ValueError) as error:
                notices.append({"message": str(error), "category": "error"})
            except Exception:
                log.exception("EmojiPorter dashboard operation failed in guild %s", guild.id)
                notices.append({"message": "The asset copy operation failed.", "category": "error"})
            else:
                notices.append({"message": message, "category": "success"})
        source = self._porter_source(user, guild, source_guild, self._porter_csrf(kwargs))
        return {"status": 0, "notifications": notices, "web_content": {"source": source, "expanded": True}}

    async def _porter_copy(self, user, target, form):
        source = self._porter_source_guild(user, form)
        action = self._porter_value(form, "action")
        requested = [name.strip() for name in self._porter_value(form, "asset_names").split(",") if name.strip()]
        assets = list(source.emojis if action == "copy_emojis" else source.stickers)
        if requested:
            requested_set = set(requested)
            assets = [asset for asset in assets if asset.name in requested_set]
            missing = sorted(requested_set - {asset.name for asset in assets})
            if missing:
                raise commands.BadArgument(f"Not found in the source server: {', '.join(missing[:10])}.")
        if not assets:
            raise commands.BadArgument("The source server has no matching assets.")
        if len(assets) > 50:
            raise commands.BadArgument("Copy at most 50 assets at once; enter specific comma-separated names.")
        copied, skipped, failed = 0, 0, []
        existing_names = {asset.name for asset in (target.emojis if action == "copy_emojis" else target.stickers)}
        for asset in assets:
            if asset.name in existing_names:
                skipped += 1
                continue
            try:
                if action == "copy_emojis":
                    await self._copy_emoji(asset, target)
                else:
                    await self._copy_sticker(asset, target)
                copied += 1
                existing_names.add(asset.name)
            except commands.CommandError as error:
                failed.append(f"{asset.name}: {error}")
            await asyncio.sleep(0.35)
        kind = "emoji" if action == "copy_emojis" else "sticker"
        detail = f" Copied {copied}, skipped {skipped}, failed {len(failed)}."
        if failed:
            detail += " " + "; ".join(failed[:3])
        return f"Finished {kind} import.{detail}"

    def _porter_source(self, user, target, source, csrf):
        sources = self._porter_sources(user, target)
        source_options = '<option value="">Choose a source server…</option>' + "".join(
            f'<option value="{item.id}"{" selected" if source and item.id == source.id else ""}>{html.escape(item.name)} · {len(item.emojis)} emoji · {len(item.stickers)} stickers</option>'
            for item in sources
        )
        if source and source in sources:
            emojis = (
                "".join(
                    f'<span class="asset"><img src="{html.escape(str(emoji.url), quote=True)}" alt="">{html.escape(emoji.name)}</span>'
                    for emoji in source.emojis[:100]
                )
                or "<em>No custom emojis.</em>"
            )
            stickers = (
                "".join(
                    f'<span class="asset"><img src="{html.escape(str(sticker.url), quote=True)}" alt="">{html.escape(sticker.name)}</span>'
                    for sticker in source.stickers[:50]
                )
                or "<em>No custom stickers.</em>"
            )
            inventory = f'<div class="card"><h3>Source inventory: {html.escape(source.name)}</h3><h4>Emojis ({len(source.emojis)})</h4><div class="assets">{emojis}</div><h4>Stickers ({len(source.stickers)})</h4><div class="assets">{stickers}</div></div>'
        else:
            inventory = '<div class="card"><p>Select a mutual server and press <strong>Browse Inventory</strong>.</p></div>'
        return f"""<section class="porter-dash"><style>.porter-dash .card{{border:1px solid rgba(127,127,127,.3);border-radius:.75rem;padding:1rem;margin-bottom:1rem}}.porter-dash label{{display:flex;flex-direction:column;gap:.3rem}}.porter-dash input,.porter-dash select{{padding:.6rem;border:1px solid rgba(127,127,127,.35);border-radius:.4rem;background:var(--background,#202225);color:var(--text,#fff)}}.porter-dash .assets{{display:flex;flex-wrap:wrap;gap:.45rem;max-height:18rem;overflow:auto}}.porter-dash .asset{{display:flex;align-items:center;gap:.35rem;padding:.35rem .55rem;border-radius:.4rem;background:rgba(127,127,127,.12)}}.porter-dash .asset img{{width:30px;height:30px;object-fit:contain}}.porter-dash .actions{{display:flex;gap:.6rem;flex-wrap:wrap}}</style><h2>EmojiPorter</h2><p>Copy expressions into <strong>{html.escape(target.name)}</strong>. Only servers where you and the bot are both members are shown.</p><form method="POST" class="card">{csrf}<label>Source server<select name="source_guild_id" required>{source_options}</select></label><label>Specific asset names <small>Optional comma-separated list. Leave blank to copy every asset, up to 50 at once.</small><input name="asset_names" placeholder="party_blob, wave, approved"></label><div class="actions"><button class="btn btn-secondary" name="action" value="browse">Browse Inventory</button><button class="btn btn-primary" name="action" value="copy_emojis">Copy Emojis</button><button class="btn btn-success" name="action" value="copy_stickers">Copy Stickers</button></div></form>{inventory}</section>"""

    def _porter_sources(self, user, target):
        return sorted(
            (guild for guild in self.bot.guilds if guild.id != target.id and guild.get_member(user.id) is not None),
            key=lambda guild: guild.name.casefold(),
        )

    def _porter_source_guild(self, user, form):
        raw = self._porter_value(form, "source_guild_id")
        try:
            source = self.bot.get_guild(int(raw))
        except ValueError as error:
            raise commands.BadArgument("Choose a source server.") from error
        if source is None or source.get_member(user.id) is None:
            raise commands.BadArgument("Choose a mutual source server.")
        return source

    async def _porter_can_manage(self, user, guild):
        member = guild.get_member(user.id)
        expression_permission = member and getattr(member.guild_permissions, "manage_emojis_and_stickers", False)
        return bool(
            user.id in getattr(self.bot, "owner_ids", set())
            or (member and await self.bot.is_admin(member))
            or expression_permission,
        )

    @staticmethod
    def _porter_form(kwargs):
        data = kwargs.get("data") or {}
        return (data.get("form") or data.get("json") or {}) if isinstance(data, dict) else data

    @staticmethod
    def _porter_value(form, key, default=""):
        value = form.get(key, default) if hasattr(form, "get") else default
        if isinstance(value, (list, tuple)):
            value = value[0] if value else default
        return default if value is None else str(value)

    @staticmethod
    def _porter_csrf(kwargs):
        token = kwargs.get("csrf_token")
        if not isinstance(token, (tuple, list)) or len(token) != 2:
            return ""
        return f'<input type="hidden" name="csrf_token" value="{html.escape(str(token[1]), quote=True)}">'
