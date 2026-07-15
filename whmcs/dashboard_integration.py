# ruff: noqa: E501
"""Purpose-built dashboard for WHMCS."""

from __future__ import annotations

import html
import logging
from typing import TYPE_CHECKING, Any, Callable
from urllib.parse import urlparse

from redbot.core import commands

if TYPE_CHECKING:
    import discord

log = logging.getLogger("red.taakoscogs.whmcs.dashboard")


def dashboard_page(*args, **kwargs):
    def decorator(func: Callable):
        func.__dashboard_decorator_params__ = (args, kwargs)
        return func

    return decorator


class DashboardIntegration:
    """WHMCS API, access policy, and ticket-channel controls."""

    @commands.Cog.listener()
    async def on_dashboard_cog_add(self, dashboard_cog: commands.Cog) -> None:
        handler = dashboard_cog.rpc.third_parties_handler
        try:
            handler.add_third_party(self, overwrite=True)
        except TypeError:
            handler.add_third_party(self)

    @dashboard_page(name=None, description="Configure WHMCS API access and ticket channels.", methods=("GET", "POST"))
    async def dashboard_page(self, user: discord.User, guild: discord.Guild, **kwargs: Any):
        if not await self._whmcs_can_manage(user, guild):
            return {"status": 1, "error_title": "Insufficient Permissions", "error_message": "Manage Server is required."}
        notices = []
        if kwargs.get("method", "GET").upper() == "POST":
            try:
                await self._whmcs_save(guild, self._whmcs_form(kwargs))
            except (commands.CommandError, ValueError) as error:
                notices.append({"message": str(error), "category": "error"})
            except Exception:
                log.exception("WHMCS dashboard save failed in guild %s", guild.id)
                notices.append({"message": "WHMCS settings could not be saved.", "category": "error"})
            else:
                notices.append(
                    {
                        "message": "WHMCS settings saved. Blank secret fields retained their previous values.",
                        "category": "success",
                    },
                )
        data = await self.config.guild(guild).all()
        return {
            "status": 0,
            "notifications": notices,
            "web_content": {"source": self._whmcs_source(guild, data, self._whmcs_csrf(kwargs)), "expanded": True},
        }

    async def _whmcs_save(self, guild, form):
        current_api = await self.config.guild(guild).api_config()
        url = self._whmcs_value(form, "url").strip().rstrip("/")
        if url:
            parsed = urlparse(url)
            if parsed.scheme not in {"http", "https"} or not parsed.netloc:
                raise commands.BadArgument("WHMCS URL must be a complete http:// or https:// address.")
        identifier = self._whmcs_value(form, "identifier").strip()
        secret = self._whmcs_value(form, "secret").strip()
        access_key = self._whmcs_value(form, "access_key").strip()
        api = {
            "url": url or None,
            "identifier": identifier or None,
            "secret": secret or current_api.get("secret"),
            "access_key": access_key or current_api.get("access_key"),
        }
        rate_limit = self._whmcs_int(form, "rate_limit", 1, 1000)
        color_text = self._whmcs_value(form, "embed_color", "#7289DA").lstrip("#")
        try:
            color = int(color_text, 16)
        except ValueError as error:
            raise commands.BadArgument("Choose a valid embed color.") from error
        prefix = self._whmcs_value(form, "channel_prefix", "whmcs-ticket-").strip().lower()
        if (
            not prefix
            or len(prefix) > 40
            or any(character not in "abcdefghijklmnopqrstuvwxyz0123456789-_" for character in prefix)
        ):
            raise commands.BadArgument("Channel prefix may contain lowercase letters, numbers, hyphens, and underscores only.")
        permissions = {}
        for key in ("admin_roles", "billing_roles", "support_roles", "readonly_roles"):
            permissions[key] = self._whmcs_roles(guild, form, key)
        settings = {
            "rate_limit": rate_limit,
            "embed_color": color,
            "show_sensitive": self._whmcs_checked(form, "show_sensitive"),
            "auto_sync": self._whmcs_checked(form, "auto_sync"),
        }
        ticket_channels = {
            "enabled": self._whmcs_checked(form, "ticket_enabled"),
            "category_id": self._whmcs_category(guild, form, "category_id"),
            "archive_category_id": self._whmcs_category(guild, form, "archive_category_id"),
            "channel_prefix": prefix,
            "auto_archive": self._whmcs_checked(form, "auto_archive"),
        }
        conf = self.config.guild(guild)
        await conf.api_config.set(api)
        await conf.permissions.set(permissions)
        await conf.settings.set(settings)
        await conf.ticket_channels.set(ticket_channels)

    def _whmcs_source(self, guild, data, csrf):
        api = data.get("api_config", {})
        permissions = data.get("permissions", {})
        settings = data.get("settings", {})
        tickets = data.get("ticket_channels", {})
        mappings = data.get("ticket_mappings", {})

        def value(raw):
            return html.escape(str(raw or ""), quote=True)

        def checked(raw):
            return " checked" if raw else ""

        def role_select(name):
            return self._whmcs_role_options(guild, permissions.get(name, []))

        categories = self._whmcs_category_options(guild, tickets.get("category_id"))
        archive_categories = self._whmcs_category_options(guild, tickets.get("archive_category_id"))
        configured = bool(api.get("url") and api.get("identifier") and api.get("secret"))
        return f"""
<section class="whmcs-dash"><style>
.whmcs-dash .card{{border:1px solid rgba(127,127,127,.3);border-radius:.7rem;padding:1rem;margin-bottom:1rem}}.whmcs-dash .grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(230px,1fr));gap:1rem}}.whmcs-dash label{{display:flex;flex-direction:column;gap:.3rem}}.whmcs-dash .check{{flex-direction:row;align-items:center}}.whmcs-dash input,.whmcs-dash select{{padding:.58rem;border:1px solid rgba(127,127,127,.35);border-radius:.4rem;background:var(--background,#202225);color:var(--text,#fff)}}.whmcs-dash select[multiple]{{min-height:10rem}}.whmcs-dash .status{{font-weight:700;color:{"#3ba55c" if configured else "#faa61a"}}}.whmcs-dash small{{opacity:.75}}
</style><h2>WHMCS Integration</h2><p>Connection status: <span class="status">{"Configured" if configured else "Needs credentials"}</span> · {len(mappings):,} ticket channel mappings.</p><form method="POST">{csrf}
<div class="card"><h3>API connection</h3><div class="grid"><label>WHMCS URL<input type="url" name="url" placeholder="https://billing.example.com" value="{value(api.get("url"))}"></label><label>API identifier<input name="identifier" autocomplete="off" value="{value(api.get("identifier"))}"></label><label>API secret <small>Leave blank to keep the current secret ({"set" if api.get("secret") else "not set"}).</small><input type="password" name="secret" autocomplete="new-password"></label><label>Access key <small>Leave blank to keep the current key ({"set" if api.get("access_key") else "not set"}).</small><input type="password" name="access_key" autocomplete="new-password"></label></div></div>
<div class="card"><h3>Access roles</h3><p>Use Ctrl/Cmd-click to select more than one role. Bot owners and the server owner retain access.</p><div class="grid"><label>Administrators<select name="admin_roles" multiple>{role_select("admin_roles")}</select></label><label>Billing staff<select name="billing_roles" multiple>{role_select("billing_roles")}</select></label><label>Support staff<select name="support_roles" multiple>{role_select("support_roles")}</select></label><label>Read-only staff<select name="readonly_roles" multiple>{role_select("readonly_roles")}</select></label></div></div>
<div class="card"><h3>API behavior</h3><div class="grid"><label>Requests per minute<input type="number" name="rate_limit" min="1" max="1000" value="{int(settings.get("rate_limit", 60))}"></label><label>Embed color<input type="color" name="embed_color" value="#{int(settings.get("embed_color", 0x7289DA)):06X}"></label><label class="check"><input type="checkbox" name="show_sensitive"{checked(settings.get("show_sensitive"))}> Show sensitive fields in command results</label><label class="check"><input type="checkbox" name="auto_sync"{checked(settings.get("auto_sync"))}> Enable automatic synchronization</label></div></div>
<div class="card"><h3>Discord ticket channels</h3><div class="grid"><label class="check"><input type="checkbox" name="ticket_enabled"{checked(tickets.get("enabled"))}> Create ticket channels</label><label>Open-ticket category<select name="category_id">{categories}</select></label><label>Archive category<select name="archive_category_id">{archive_categories}</select></label><label>Channel prefix<input name="channel_prefix" maxlength="40" value="{value(tickets.get("channel_prefix", "whmcs-ticket-"))}"></label><label class="check"><input type="checkbox" name="auto_archive"{checked(tickets.get("auto_archive", True))}> Archive channels when tickets close</label></div></div><button class="btn btn-primary">Save WHMCS Settings</button></form></section>"""

    async def _whmcs_can_manage(self, user, guild):
        member = guild.get_member(user.id)
        return bool(
            user.id in getattr(self.bot, "owner_ids", set())
            or user.id == guild.owner_id
            or (member and await self.bot.is_admin(member))
            or (member and member.guild_permissions.manage_guild),
        )

    @staticmethod
    def _whmcs_form(kwargs):
        data = kwargs.get("data") or {}
        return (data.get("form") or data.get("json") or {}) if isinstance(data, dict) else data

    @staticmethod
    def _whmcs_value(form, key, default=""):
        value = form.get(key, default) if hasattr(form, "get") else default
        if isinstance(value, (list, tuple)):
            value = value[0] if value else default
        return default if value is None else str(value)

    @classmethod
    def _whmcs_values(cls, form, key):
        if hasattr(form, "getlist"):
            return [str(value) for value in form.getlist(key)]
        value = form.get(key, []) if hasattr(form, "get") else []
        if isinstance(value, (list, tuple)):
            return [str(item) for item in value]
        return [str(value)] if value not in {None, ""} else []

    @classmethod
    def _whmcs_checked(cls, form, key):
        return cls._whmcs_value(form, key).lower() in {"1", "true", "on", "yes"}

    @classmethod
    def _whmcs_int(cls, form, key, minimum, maximum):
        try:
            value = int(cls._whmcs_value(form, key))
        except ValueError as error:
            raise commands.BadArgument("Rate limit must be a number.") from error
        if not minimum <= value <= maximum:
            raise commands.BadArgument(f"Rate limit must be {minimum}–{maximum}.")
        return value

    @classmethod
    def _whmcs_roles(cls, guild, form, key):
        roles = []
        for raw in cls._whmcs_values(form, key):
            try:
                role = guild.get_role(int(raw))
            except ValueError as error:
                raise commands.BadArgument("Choose valid access roles.") from error
            if role is None or role.is_default():
                raise commands.BadArgument("Choose valid access roles.")
            roles.append(role.id)
        return list(dict.fromkeys(roles))

    @classmethod
    def _whmcs_category(cls, guild, form, key):
        raw = cls._whmcs_value(form, key)
        if not raw:
            return None
        try:
            category = guild.get_channel(int(raw))
        except ValueError as error:
            raise commands.BadArgument("Choose a valid category.") from error
        if category not in guild.categories:
            raise commands.BadArgument("Choose a valid category.")
        return category.id

    @staticmethod
    def _whmcs_role_options(guild, selected):
        chosen = {int(role_id) for role_id in selected}
        return "".join(
            f'<option value="{role.id}"{" selected" if role.id in chosen else ""}>{html.escape(role.name)}</option>'
            for role in reversed(guild.roles)
            if not role.is_default()
        )

    @staticmethod
    def _whmcs_category_options(guild, selected):
        return '<option value="">Not configured</option>' + "".join(
            f'<option value="{category.id}"{" selected" if category.id == selected else ""}>{html.escape(category.name)}</option>'
            for category in guild.categories
        )

    @staticmethod
    def _whmcs_csrf(kwargs):
        token = kwargs.get("csrf_token")
        if not isinstance(token, (tuple, list)) or len(token) != 2:
            return ""
        return f'<input type="hidden" name="csrf_token" value="{html.escape(str(token[1]), quote=True)}">'
