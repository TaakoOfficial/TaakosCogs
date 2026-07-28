# ruff: noqa: E501
"""Purpose-built dashboard for Toolz role messages."""

from __future__ import annotations

import html
import logging
from typing import TYPE_CHECKING, Any, Callable

from redbot.core import commands

if TYPE_CHECKING:
    import discord

log = logging.getLogger("red.taakoscogs.toolz.dashboard")


def dashboard_page(*args, **kwargs):
    def decorator(func: Callable):
        func.__dashboard_decorator_params__ = (args, kwargs)
        return func

    return decorator


class DashboardIntegration:
    """Role-triggered message editor and server utility overview."""

    @commands.Cog.listener()
    async def on_dashboard_cog_add(self, dashboard_cog: commands.Cog) -> None:
        handler = dashboard_cog.rpc.third_parties_handler
        try:
            handler.add_third_party(self, overwrite=True)
        except TypeError:
            handler.add_third_party(self)

    @dashboard_page(name=None, description="Create and manage role-triggered messages.", methods=("GET", "POST"))
    async def dashboard_page(self, user: discord.User, guild: discord.Guild, **kwargs: Any):
        if not await self._toolz_can_manage(user, guild):
            return {"status": 1, "error_title": "Insufficient Permissions", "error_message": "Manage Roles is required."}
        notices = []
        selected = self._toolz_value(self._toolz_form(kwargs), "role_id")
        if kwargs.get("method", "GET").upper() == "POST":
            form = self._toolz_form(kwargs)
            action = self._toolz_value(form, "action", "save")
            try:
                if action == "load":
                    selected = str(self._toolz_role(guild, form).id)
                else:
                    selected = await self._toolz_save(guild, form)
            except (commands.CommandError, ValueError) as error:
                notices.append({"message": str(error), "category": "error"})
            except Exception:
                log.exception("Toolz dashboard save failed in guild %s", guild.id)
                notices.append({"message": "Role message settings could not be saved.", "category": "error"})
            else:
                if action == "load":
                    message = "Loaded that role's saved message configuration."
                elif action == "delete":
                    message = "Role message configuration removed."
                else:
                    message = "Role message configuration saved."
                notices.append(
                    {
                        "message": message,
                        "category": "success",
                    },
                )
        entries = await self.config.guild(guild).role_messages()
        return {
            "status": 0,
            "notifications": notices,
            "web_content": {"source": self._toolz_source(guild, entries, selected, self._toolz_csrf(kwargs)), "expanded": True},
        }

    async def _toolz_save(self, guild, form):
        role = self._toolz_role(guild, form)
        key = str(role.id)
        action = self._toolz_value(form, "action", "save")
        async with self.config.guild(guild).role_messages() as entries:
            if action == "delete":
                if entries.pop(key, None) is None:
                    raise commands.BadArgument("That role has no configured messages.")
                return ""
            channel = self._toolz_channel(guild, form)
            mode = self._toolz_value(form, "mode", "all").lower()
            if mode not in {"all", "random"}:
                raise commands.BadArgument("Delivery mode must be all or random.")
            messages = [line.strip() for line in self._toolz_value(form, "messages").splitlines() if line.strip()]
            if not 1 <= len(messages) <= 10:
                raise commands.BadArgument("Add 1–10 message templates, one per line.")
            if any(len(message) > 1800 for message in messages):
                raise commands.BadArgument("Each message template must be 1,800 characters or shorter.")
            entries[key] = {
                "channel_id": channel.id,
                "messages": messages,
                "enabled": self._toolz_checked(form, "enabled"),
                "mode": mode,
            }
        return key

    def _toolz_source(self, guild, entries, selected, csrf):
        entry = entries.get(str(selected), {})
        role_options = '<option value="">Choose a role…</option>' + "".join(
            f'<option value="{role.id}"{" selected" if str(role.id) == str(selected) else ""}>{html.escape(role.name)}</option>'
            for role in reversed(guild.roles)
            if not role.is_default()
        )
        channel_options = '<option value="">Choose a channel…</option>' + "".join(
            f'<option value="{channel.id}"{" selected" if channel.id == entry.get("channel_id") else ""}>#{html.escape(channel.name)}</option>'
            for channel in guild.text_channels
        )
        messages = html.escape("\n".join(entry.get("messages", [])))
        enabled = " checked" if entry.get("enabled", True) else ""
        all_selected = " selected" if entry.get("mode", "all") == "all" else ""
        random_selected = " selected" if entry.get("mode") == "random" else ""
        configured = []
        for role_id, item in entries.items():
            role = guild.get_role(int(role_id)) if str(role_id).isdigit() else None
            channel = guild.get_channel(item.get("channel_id") or 0)
            configured.append(
                f"<tr><td>{html.escape(role.name) if role else 'Deleted role'}</td><td>{'#' + html.escape(channel.name) if channel else 'Not set'}</td><td>{len(item.get('messages', []))}</td><td>{html.escape(str(item.get('mode', 'all')).title())}</td><td>{'On' if item.get('enabled', True) else 'Off'}</td></tr>",
            )
        rows = "".join(configured) or '<tr><td colspan="5">No role messages are configured yet.</td></tr>'
        return f"""
<section class="toolz-dash"><style>
.toolz-dash .card{{border:1px solid rgba(127,127,127,.3);border-radius:.7rem;padding:1rem;margin-bottom:1rem}}.toolz-dash .grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:1rem}}.toolz-dash label{{display:flex;flex-direction:column;gap:.3rem}}.toolz-dash .check{{flex-direction:row;align-items:center}}.toolz-dash input,.toolz-dash select,.toolz-dash textarea{{padding:.6rem;border:1px solid rgba(127,127,127,.35);border-radius:.4rem;background:var(--background,#202225);color:var(--text,#fff)}}.toolz-dash textarea{{min-height:12rem;resize:vertical}}.toolz-dash table{{width:100%;border-collapse:collapse}}.toolz-dash td,.toolz-dash th{{padding:.55rem;border-bottom:1px solid rgba(127,127,127,.25);text-align:left}}.toolz-dash .actions{{display:flex;gap:.6rem;flex-wrap:wrap}}
</style><h2>Toolz Role Messages</h2><p>Welcome members when roles are assigned in <strong>{html.escape(guild.name)}</strong>.</p><div class="card"><h3>Configured roles</h3><div style="overflow:auto"><table><thead><tr><th>Role</th><th>Channel</th><th>Messages</th><th>Mode</th><th>Status</th></tr></thead><tbody>{rows}</tbody></table></div></div>
<form method="POST" class="card">{csrf}<h3>Add or edit a role</h3><p>Choose a role and load it before editing an existing configuration.</p><div class="grid"><label>Role<select name="role_id" required>{role_options}</select></label><label>Destination channel<select name="channel_id" required>{channel_options}</select></label><label>Delivery mode<select name="mode"><option value="all"{all_selected}>Post every message</option><option value="random"{random_selected}>Post one at random</option></select></label><label class="check"><input type="checkbox" name="enabled"{enabled}> Enabled</label></div><label>Message templates <small>One message per line; up to 10. Placeholders: {{user}}, {{username}}, {{display_name}}, {{role}}, {{role_name}}, {{server}}.</small><textarea name="messages" maxlength="18010">{messages}</textarea></label><div class="actions"><button class="btn btn-secondary" name="action" value="load" formnovalidate>Load This Role</button><button class="btn btn-primary" name="action" value="save">Save Role Messages</button><button class="btn btn-danger" name="action" value="delete" formnovalidate>Delete This Role</button></div></form></section>"""

    async def _toolz_can_manage(self, user, guild):
        member = guild.get_member(user.id)
        return bool(
            user.id in getattr(self.bot, "owner_ids", set())
            or (member and await self.bot.is_admin(member))
            or (member and member.guild_permissions.manage_roles),
        )

    @staticmethod
    def _toolz_form(kwargs):
        data = kwargs.get("data") or {}
        return (data.get("form") or data.get("json") or {}) if isinstance(data, dict) else data

    @staticmethod
    def _toolz_value(form, key, default=""):
        value = form.get(key, default) if hasattr(form, "get") else default
        if isinstance(value, (list, tuple)):
            value = value[0] if value else default
        return default if value is None else str(value)

    @classmethod
    def _toolz_checked(cls, form, key):
        return cls._toolz_value(form, key).lower() in {"1", "true", "on", "yes"}

    @classmethod
    def _toolz_role(cls, guild, form):
        try:
            role = guild.get_role(int(cls._toolz_value(form, "role_id")))
        except ValueError as error:
            raise commands.BadArgument("Choose a valid role.") from error
        if role is None or role.is_default():
            raise commands.BadArgument("Choose a valid role.")
        return role

    @classmethod
    def _toolz_channel(cls, guild, form):
        try:
            channel = guild.get_channel(int(cls._toolz_value(form, "channel_id")))
        except ValueError as error:
            raise commands.BadArgument("Choose a valid text channel.") from error
        if channel not in guild.text_channels:
            raise commands.BadArgument("Choose a valid text channel.")
        return channel

    @staticmethod
    def _toolz_csrf(kwargs):
        token = kwargs.get("csrf_token")
        if not isinstance(token, (tuple, list)) or len(token) != 2:
            return ""
        return f'<input type="hidden" name="csrf_token" value="{html.escape(str(token[1]), quote=True)}">'
