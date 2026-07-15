"""Red-Web-Dashboard integration for TempVoice."""

from __future__ import annotations

import html
import logging
import typing
from datetime import datetime, timezone

import discord
from redbot.core import commands

log = logging.getLogger("red.taakoscogs.tempvoice.dashboard")


def dashboard_page(*args, **kwargs):
    """Dashboard page decorator compatible with Red-Web-Dashboard."""

    def decorator(func: typing.Callable):
        func.__dashboard_decorator_params__ = (args, kwargs)
        return func

    return decorator


class DashboardIntegration:
    """Dashboard integration mixin for TempVoice."""

    @commands.Cog.listener()
    async def on_dashboard_cog_add(self, dashboard_cog: commands.Cog) -> None:
        """Register TempVoice as a Red-Web-Dashboard third party."""
        handler = dashboard_cog.rpc.third_parties_handler
        try:
            handler.add_third_party(self, overwrite=True)
        except TypeError:
            handler.add_third_party(self)

    @dashboard_page(
        name=None,
        description="Configure TempVoice settings and manage active temporary channels.",
        methods=("GET", "POST"),
    )
    async def dashboard_page(
        self,
        user: discord.User,
        guild: discord.Guild,
        **kwargs,
    ) -> dict[str, typing.Any]:
        """Render and process the TempVoice dashboard page."""
        _member, can_manage = await self._dashboard_member_can_manage(user, guild)
        if not can_manage:
            return {
                "status": 1,
                "error_title": "Insufficient Permissions",
                "error_message": "You need Manage Server, Red admin, or bot owner access.",
            }

        notifications = []
        form_data = self._dashboard_form_data(kwargs)

        if kwargs.get("method", "GET") == "POST":
            action = self._dash_value(form_data, "action")
            try:
                messages = await self._dashboard_handle_action(
                    guild,
                    user,
                    action,
                    form_data,
                )
            except commands.CommandError as error:
                notifications.append(
                    {"message": str(error), "category": "error"})
            except Exception as error:
                log.exception("TempVoice dashboard action failed.")
                notifications.append(
                    {
                        "message": f"TempVoice dashboard action failed: {error}",
                        "category": "error",
                    },
                )
            else:
                notifications.extend(messages)

        source = await self._dashboard_source(guild, kwargs)
        return {
            "status": 0,
            "notifications": notifications,
            "web_content": {
                "source": source,
                "expanded": True,
            },
        }

    async def _dashboard_member_can_manage(
        self,
        user: discord.User,
        guild: discord.Guild,
    ) -> tuple[discord.Member | None, bool]:
        member = guild.get_member(user.id)
        is_owner = user.id in getattr(self.bot, "owner_ids", set())
        is_admin = member is not None and await self.bot.is_admin(member)
        can_manage = (
            is_owner
            or is_admin
            or (member is not None and member.guild_permissions.manage_guild)
        )
        return member, can_manage

    def _dashboard_form_data(self, kwargs: dict[str, typing.Any]) -> typing.Any:
        data = kwargs.get("data") or {}
        if isinstance(data, dict) and ("form" in data or "json" in data):
            return data.get("form") or data.get("json") or {}
        return data

    def _dashboard_active_tab(self, kwargs, action_tabs, default):
        form_data = self._dashboard_form_data(kwargs)
        selected = self._dash_value(form_data, "active_tab").lower()
        valid = set(action_tabs.values()) | {default}
        return (
            selected
            if selected in valid
            else action_tabs.get(self._dash_value(form_data, "action").lower(), default)
        )

    def _dashboard_tab_button(self, name: str, label: str, active: str) -> str:
        selected = name == active
        active_class = " active" if selected else ""
        aria_selected = str(selected).lower()
        tabindex = 0 if selected else -1
        return (
            f'<button type="button" class="dash-tab{active_class}" '
            f'data-tab="{self._h(name)}" role="tab" '
            f'aria-selected="{aria_selected}" tabindex="{tabindex}">'
            f"{self._h(label)}</button>"
        )

    @staticmethod
    def _dashboard_tabs_script() -> str:
        return """
<script>
(() => {
  const root = document.currentScript.closest("[data-dashboard-tabs]");
  if (!root) return;

  const tabs = Array.from(root.querySelectorAll("[data-tab]"));
  const panels = Array.from(root.querySelectorAll("[data-tab-panel]"));
  const names = new Set(tabs.map((tab) => tab.dataset.tab));

  const activate = (name, hash = false) => {
    if (!names.has(name)) return;
    tabs.forEach((tab) => {
      const on = tab.dataset.tab === name;
      tab.classList.toggle("active", on);
      tab.setAttribute("aria-selected", on ? "true" : "false");
      tab.tabIndex = on ? 0 : -1;
    });
    panels.forEach((panel) => {
      const on = panel.dataset.tabPanel === name;
      panel.classList.toggle("active", on);
      panel.hidden = !on;
    });
    if (hash) history.replaceState(null, "", `#tab-${name}`);
  };

  const fromHash = () => {
    const hash = location.hash.slice(1);
    if (hash.startsWith("tab-") && names.has(hash.slice(4))) return hash.slice(4);
    const section = document.getElementById(hash);
    const panel = section ? section.closest("[data-tab-panel]") : null;
    return panel ? panel.dataset.tabPanel : null;
  };

  tabs.forEach((tab, index) => {
    tab.addEventListener("click", () => activate(tab.dataset.tab, true));
    tab.addEventListener("keydown", (event) => {
      const move = event.key === "ArrowRight" ? 1 : event.key === "ArrowLeft" ? -1 : 0;
      if (!move) return;
      event.preventDefault();
      const next = tabs[(index + move + tabs.length) % tabs.length];
      next.focus();
      activate(next.dataset.tab, true);
    });
  });

  root.querySelectorAll("form").forEach((form) => {
    form.addEventListener("submit", () => {
      let input = form.querySelector('input[name="active_tab"]');
      if (!input) {
        input = document.createElement("input");
        input.type = "hidden";
        input.name = "active_tab";
        form.appendChild(input);
      }
      input.value = root.querySelector("[data-tab].active").dataset.tab;
    });
  });

  activate(fromHash() || root.querySelector("[data-tab].active").dataset.tab);
})();
</script>
"""

    def _dash_value(
        self,
        form_data: typing.Any,
        key: str,
        default: str = "",
    ) -> str:
        if hasattr(form_data, "get"):
            value = form_data.get(key, default)
        else:
            return default
        if isinstance(value, (list, tuple)):
            value = value[0] if value else default
        if value is None:
            return default
        return str(value)

    def _dash_bool(self, form_data: typing.Any, key: str) -> bool:
        if hasattr(form_data, "__contains__") and key in form_data:
            value = self._dash_value(form_data, key, "on").lower()
            return value not in {"0", "false", "off", "no", ""}
        return False

    def _dash_int(
        self,
        form_data: typing.Any,
        key: str,
        *,
        default: int | None = None,
        minimum: int | None = None,
        maximum: int | None = None,
        optional: bool = False,
    ) -> int | None:
        value = self._dash_value(form_data, key).strip()
        if optional and value == "":
            return None
        try:
            number = int(value)
        except (TypeError, ValueError):
            if default is not None:
                number = default
            else:
                raise commands.BadArgument(f"`{key}` must be a whole number.")
        if minimum is not None:
            number = max(minimum, number)
        if maximum is not None:
            number = min(maximum, number)
        return number

    def _dash_optional_id(self, form_data: typing.Any, key: str) -> int | None:
        value = self._dash_value(form_data, key).strip()
        if not value:
            return None
        try:
            return int(value)
        except (TypeError, ValueError) as exc:
            raise commands.BadArgument(
                f"`{key}` must be a Discord ID.") from exc

    def _dash_required_id(self, form_data: typing.Any, key: str) -> int:
        value = self._dash_optional_id(form_data, key)
        if value is None:
            raise commands.BadArgument(f"`{key}` is required.")
        return value

    def _dash_csrf(self, kwargs: dict[str, typing.Any]) -> str:
        csrf_token = kwargs.get("csrf_token")
        if not isinstance(csrf_token, (tuple, list)) or len(csrf_token) != 2:
            return ""
        return (
            '<input type="hidden" name="csrf_token" value="'
            f'{html.escape(str(csrf_token[1]), quote=True)}">'
        )

    async def _dashboard_handle_action(
        self,
        guild: discord.Guild,
        user: discord.User,
        action: str,
        form_data: typing.Any,
    ) -> list[dict[str, str]]:
        if action == "save_settings":
            await self._dashboard_save_settings(guild, form_data)
            return [{"message": "TempVoice settings saved.", "category": "success"}]

        if action == "cleanup_empty":
            deleted, stale = await self._dashboard_cleanup(guild, user)
            return [
                {
                    "message": (
                        f"Deleted {deleted} empty channel(s) and removed "
                        f"{stale} stale record(s)."
                    ),
                    "category": "success",
                },
            ]

        if action == "resend_panel":
            message = await self._dashboard_resend_panel(guild, form_data)
            return [
                {
                    "message": f"Control panel sent in #{message.channel.name}.",
                    "category": "success",
                },
            ]

        if action == "delete_temp":
            channel_id = await self._dashboard_delete_temp(guild, user, form_data)
            return [
                {
                    "message": f"Temporary channel `{channel_id}` deleted or cleaned up.",
                    "category": "success",
                },
            ]

        if action:
            raise commands.BadArgument("Unknown TempVoice dashboard action.")
        return []

    async def _dashboard_save_settings(
        self,
        guild: discord.Guild,
        form_data: typing.Any,
    ) -> None:
        enabled = self._dash_bool(form_data, "enabled")
        join_channel_id = self._dash_optional_id(form_data, "join_channel_id")
        category_id = self._dash_optional_id(form_data, "category_id")
        panel_channel_id = self._dash_optional_id(
            form_data, "panel_channel_id")
        default_limit = self._dash_int(
            form_data,
            "default_user_limit",
            default=0,
            minimum=0,
            maximum=99,
        )
        auto_delete_delay = self._dash_int(
            form_data,
            "auto_delete_delay",
            default=3,
            minimum=0,
            maximum=self.MAX_DELETE_DELAY,
        )
        template = self._clean_channel_name(
            self._dash_value(form_data, "channel_name_template",
                             self.DEFAULT_TEMPLATE),
        )
        clone_permissions = self._dash_bool(
            form_data, "clone_trigger_permissions")

        if enabled and join_channel_id is None:
            raise commands.BadArgument(
                "Set a join-to-create voice channel before enabling.",
            )
        if join_channel_id is not None and not isinstance(
            guild.get_channel(join_channel_id),
            discord.VoiceChannel,
        ):
            raise commands.BadArgument(
                "The join-to-create channel must be a voice channel.",
            )
        if category_id is not None and not isinstance(
            guild.get_channel(category_id),
            discord.CategoryChannel,
        ):
            raise commands.BadArgument(
                "The temporary channel category must be a category.",
            )
        if panel_channel_id is not None:
            panel_channel = guild.get_channel(panel_channel_id)
            if not isinstance(panel_channel, discord.TextChannel):
                raise commands.BadArgument(
                    "The control panel channel must be a text channel.",
                )
            me = guild.me
            if me is None:
                raise commands.CommandError(
                    "I could not check my channel permissions.")
            permissions = panel_channel.permissions_for(me)
            if not permissions.send_messages or not permissions.embed_links:
                raise commands.CommandError(
                    f"I need Send Messages and Embed Links in #{panel_channel.name}.",
                )

        guild_conf = self.config.guild(guild)
        await guild_conf.enabled.set(enabled)
        await guild_conf.join_channel_id.set(join_channel_id)
        await guild_conf.category_id.set(category_id)
        await guild_conf.panel_channel_id.set(panel_channel_id)
        await guild_conf.default_user_limit.set(default_limit)
        await guild_conf.auto_delete_delay.set(auto_delete_delay)
        await guild_conf.channel_name_template.set(template)
        await guild_conf.clone_trigger_permissions.set(clone_permissions)

    async def _dashboard_cleanup(
        self,
        guild: discord.Guild,
        user: discord.User,
    ) -> tuple[int, int]:
        records = await self.config.guild(guild).temp_channels()
        stale_ids = []
        empty_ids = []

        for channel_id in records:
            try:
                channel = guild.get_channel(int(channel_id))
            except (TypeError, ValueError):
                stale_ids.append(channel_id)
                continue
            if not isinstance(channel, discord.VoiceChannel):
                stale_ids.append(channel_id)
                continue
            if not self._human_members(channel):
                empty_ids.append(channel.id)

        deleted = 0
        for channel_id in empty_ids:
            await self._delete_temp_channel(
                guild,
                channel_id,
                reason=f"TempVoice dashboard cleanup by {user} ({user.id}).",
            )
            deleted += 1

        if stale_ids:
            async with self.config.guild(guild).temp_channels() as stored:
                for channel_id in stale_ids:
                    stored.pop(channel_id, None)
        return deleted, len(stale_ids)

    async def _dashboard_resend_panel(
        self,
        guild: discord.Guild,
        form_data: typing.Any,
    ) -> discord.Message:
        channel_id = self._dash_required_id(form_data, "channel_id")
        record = await self._get_temp_record(guild, channel_id)
        channel = guild.get_channel(channel_id)
        if not record or not isinstance(channel, discord.VoiceChannel):
            raise commands.BadArgument(
                "That is not an active TempVoice channel.")
        settings = await self.config.guild(guild).all()
        message = await self._send_control_panel(guild, channel, record, settings)
        if message is None:
            raise commands.CommandError(
                "I could not send a control panel for that channel.",
            )
        await self._update_record(
            guild,
            channel.id,
            panel_channel_id=message.channel.id,
            panel_message_id=message.id,
        )
        return message

    async def _dashboard_delete_temp(
        self,
        guild: discord.Guild,
        user: discord.User,
        form_data: typing.Any,
    ) -> int:
        channel_id = self._dash_required_id(form_data, "channel_id")
        confirmation = self._dash_value(
            form_data, "delete_confirm").strip().lower()
        if confirmation != "delete":
            raise commands.BadArgument(
                "Type `delete` to confirm channel cleanup.")

        record = await self._get_temp_record(guild, channel_id)
        if not record:
            raise commands.BadArgument(
                "That channel is not tracked by TempVoice.")
        channel = guild.get_channel(channel_id)
        if not isinstance(channel, discord.VoiceChannel):
            await self._remove_temp_record(guild, channel_id)
            return channel_id
        if self._human_members(channel):
            raise commands.BadArgument(
                "Only empty temporary channels can be deleted here.",
            )

        await self._delete_temp_channel(
            guild,
            channel.id,
            reason=f"TempVoice dashboard delete by {user} ({user.id}).",
        )
        return channel_id

    async def _dashboard_source(
        self,
        guild: discord.Guild,
        kwargs: dict[str, typing.Any],
    ) -> str:
        settings = await self.config.guild(guild).all()
        records = settings.get("temp_channels") or {}
        csrf = self._dash_csrf(kwargs)
        active_rows, active_count, stale_count = self._active_channel_rows(
            guild,
            records,
            csrf,
        )
        active_tab = self._dashboard_active_tab(
            kwargs,
            {
                "save_settings": "settings",
                "cleanup_empty": "maintenance",
                "resend_panel": "channels",
                "delete_temp": "channels",
            },
            "channels",
        )

        return f"""
<style>
.tv-dash {{
  --bg: #101318; --panel: #171b22; --line: #2a303a; --text: #eef1f5;
  --muted: #aab2bf; --accent: #8ab4ff; --danger: #ff6b6b;
  color: var(--text); display: grid; gap: 16px;
}}
.tv-dash * {{ box-sizing: border-box; }}
.tv-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 16px; }}
.tv-card {{ background: var(--panel); border: 1px solid var(--line); border-radius: 8px; padding: 16px; }}
.tv-card h2 {{ margin: 0 0 12px; font-size: 18px; }}
.tv-stats {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(145px, 1fr)); gap: 10px; }}
.tv-stat {{ border: 1px solid var(--line); border-radius: 8px; padding: 12px; }}
.tv-stat strong {{ display: block; font-size: 22px; }}
.tv-stat span, .tv-muted {{ color: var(--muted); }}
.tv-field {{ display: grid; gap: 6px; margin-bottom: 10px; }}
.tv-field label {{ color: var(--muted); font-size: 13px; }}
.tv-field input, .tv-field select {{
  width: 100%; min-width: 0; max-width: 100%; box-sizing: border-box; background: #0c0f14; color: var(--text);
  border: 1px solid var(--line);
  border-radius: 6px; padding: 9px 10px;
}}
.tv-check {{ display: flex; align-items: center; gap: 8px; margin-bottom: 10px; color: var(--muted); }}
.tv-check input {{ width: auto; }}
.tv-actions {{ display: flex; flex-wrap: wrap; gap: 8px; margin-top: 12px; }}
.tv-actions button {{
  background: var(--accent); color: #07111f; border: 0; border-radius: 6px;
  padding: 9px 12px; font-weight: 700; cursor: pointer;
}}
.tv-actions button.danger {{ background: var(--danger); color: #210909; }}
.tv-table {{ width: 100%; border-collapse: collapse; font-size: 14px; }}
.tv-table th, .tv-table td {{ border-bottom: 1px solid var(--line); padding: 8px; text-align: left; vertical-align: top;
 }}
.tv-table th {{ color: var(--muted); font-weight: 600; }}
.dash-tabs {{ display: flex; gap: 4px; overflow-x: auto; position: sticky; top: 0; z-index: 10; padding: 5px;
background: #0c0f14; border: 1px solid var(--line); border-radius: 8px; }}
.dash-tab {{ flex: 0 0 auto; border: 0; border-radius: 6px; padding: 9px 13px; background: transparent; color:
var(--muted); cursor: pointer; font-weight: 700; white-space: nowrap; }}
.dash-tab:hover {{ background: var(--panel); color: var(--text); }} .dash-tab.active {{ background: var(--accent);
color: #07111f; }}
.dash-panel {{ display: none; }} .dash-panel.active {{ display: block; }}
</style>
<div class="tv-dash" data-dashboard-tabs="1">
  <div class="tv-stats">
    <div class="tv-stat"><strong>{self._h("Enabled" if settings.get("enabled") else
    "Disabled")}</strong><span>Status</span></div>
    <div class="tv-stat"><strong>{active_count}</strong><span>active records</span></div>
    <div class="tv-stat"><strong>{stale_count}</strong><span>stale records</span></div>
    <div class="tv-stat"><strong>{self._h(settings.get("auto_delete_delay") or 0)}s</strong><span>empty cleanup
    delay</span></div>
  </div>
  <div class="dash-tabs" role="tablist" aria-label="TempVoice sections">
    {self._dashboard_tab_button("channels", "Active Channels", active_tab)}
    {self._dashboard_tab_button("settings", "Settings", active_tab)}
    {self._dashboard_tab_button("maintenance", "Maintenance", active_tab)}
  </div>
  <section class="dash-panel{" active" if active_tab == "settings" else ""}" data-tab-panel="settings"><div
  class="tv-grid">
    <form class="tv-card" method="post">
      {csrf}
      <input type="hidden" name="action" value="save_settings">
      <h2>Settings</h2>
      {self._checkbox("enabled", "Enable join-to-create", settings.get("enabled"))}
      {self._select("join_channel_id", "Join-to-create voice channel", self._voice_options(guild),
      settings.get("join_channel_id"))}
      {self._select("category_id", "Temporary channel category", self._category_options(guild),
      settings.get("category_id"), "Use trigger category")}
      {self._select("panel_channel_id", "Control panel text channel", self._text_options(guild),
      settings.get("panel_channel_id"), "Use voice channel chat")}
      {self._input("default_user_limit", "Default user limit", settings.get("default_user_limit") or 0, "number", 0,
      99)}
      {self._input("auto_delete_delay", "Auto delete delay seconds", settings.get("auto_delete_delay") or 0, "number",
      0, self.MAX_DELETE_DELAY)}
      {self._input("channel_name_template", "Channel name template", settings.get("channel_name_template") or
      self.DEFAULT_TEMPLATE)}
      {self._checkbox("clone_trigger_permissions", "Clone trigger channel permissions",
      settings.get("clone_trigger_permissions", True))}
      <div class="tv-actions"><button type="submit">Save settings</button></div>
    </form>
  </div></section>
  <section class="dash-panel{" active" if active_tab == "maintenance" else ""}" data-tab-panel="maintenance"><div
  class="tv-grid">
    <form class="tv-card" method="post">
      {csrf}
      <input type="hidden" name="action" value="cleanup_empty">
      <h2>Cleanup</h2>
      <p class="tv-muted">Delete empty TempVoice channels and remove records for missing channels.</p>
      <div class="tv-actions"><button class="danger" type="submit">Clean up empty channels</button></div>
    </form>
  </div></section>
  <section class="dash-panel{" active" if active_tab == "channels" else ""}" data-tab-panel="channels"><div
  class="tv-card" id="active-channels">
    <h2>Active Temporary Channels</h2>
    {active_rows}
  </div></section>
  {self._dashboard_tabs_script()}
</div>
"""

    def _active_channel_rows(
        self,
        guild: discord.Guild,
        records: dict[str, typing.Any],
        csrf: str,
    ) -> tuple[str, int, int]:
        if not records:
            return '<p class="tv-muted">No temporary channels are active.</p>', 0, 0

        rows = []
        active = 0
        stale = 0
        for raw_channel_id, record in sorted(records.items()):
            try:
                channel_id = int(raw_channel_id)
            except (TypeError, ValueError):
                stale += 1
                continue
            channel = guild.get_channel(channel_id)
            if not isinstance(channel, discord.VoiceChannel):
                stale += 1
                channel_name = "Missing channel"
                members = "0"
            else:
                active += 1
                channel_name = channel.name
                members = str(len(self._human_members(channel)))
            owner_id = record.get("owner_id") if isinstance(
                record, dict) else None
            owner = self._member_label(guild, owner_id)
            created = self._format_dashboard_time(record.get("created_at"))
            locked = "Locked" if record.get("locked") else "Unlocked"
            user_limit = self._limit_text(record.get("user_limit"))
            rows.append(
                "<tr>"
                f'<td>{self._h(channel_name)}<br><span class="tv-muted">{channel_id}</span></td>'
                f"<td>{self._h(owner)}</td>"
                f"<td>{self._h(members)}</td>"
                f"<td>{self._h(locked)}<br>{self._h(user_limit)}</td>"
                f"<td>{self._h(created)}</td>"
                "<td>"
                '<form method="post" class="tv-actions">'
                f"{csrf}"
                '<input type="hidden" name="action" value="resend_panel">'
                f'<input type="hidden" name="channel_id" value="{self._h(channel_id)}">'
                '<button type="submit">Send panel</button>'
                "</form>"
                '<form method="post" class="tv-actions">'
                f"{csrf}"
                '<input type="hidden" name="action" value="delete_temp">'
                f'<input type="hidden" name="channel_id" value="{self._h(channel_id)}">'
                '<input name="delete_confirm" placeholder="type delete">'
                '<button class="danger" type="submit">Delete empty</button>'
                "</form>"
                "</td>"
                "</tr>",
            )
        table = (
            '<table class="tv-table"><thead><tr><th>Channel</th><th>Owner</th>'
            "<th>Members</th><th>Status</th><th>Created</th><th>Actions</th></tr>"
            "</thead><tbody>" + "".join(rows) + "</tbody></table>"
        )
        return table, active, stale

    def _voice_options(self, guild: discord.Guild) -> list[tuple[int, str]]:
        return [(channel.id, channel.name) for channel in guild.voice_channels]

    def _category_options(self, guild: discord.Guild) -> list[tuple[int, str]]:
        return [(category.id, category.name) for category in guild.categories]

    def _text_options(self, guild: discord.Guild) -> list[tuple[int, str]]:
        return [(channel.id, f"#{channel.name}") for channel in guild.text_channels]

    def _select(
        self,
        name: str,
        label: str,
        options: list[tuple[typing.Any, str]],
        selected: typing.Any = "",
        empty_label: str = "Select...",
    ) -> str:
        option_html = [f'<option value="">{self._h(empty_label)}</option>']
        for value, text in options:
            option_html.append(
                f'<option value="{self._h(value)}" {self._selected(value, selected)}>'
                f"{self._h(text)}</option>",
            )
        return (
            f'<div class="tv-field"><label>{self._h(label)}</label>'
            f'<select name="{self._h(name)}">{"".join(option_html)}</select></div>'
        )

    def _input(
        self,
        name: str,
        label: str,
        value: typing.Any,
        input_type: str = "text",
        min_value: int | None = None,
        max_value: int | None = None,
    ) -> str:
        attrs = []
        if min_value is not None:
            attrs.append(f'min="{min_value}"')
        if max_value is not None:
            attrs.append(f'max="{max_value}"')
        return (
            f'<div class="tv-field"><label>{self._h(label)}</label>'
            f'<input type="{self._h(input_type)}" name="{self._h(name)}" '
            f'value="{self._h(value)}" {" ".join(attrs)}></div>'
        )

    def _checkbox(self, name: str, label: str, checked: typing.Any) -> str:
        checked_attr = "checked" if checked else ""
        return (
            '<label class="tv-check">'
            f'<input type="checkbox" name="{self._h(name)}" value="1" {checked_attr}>'
            f"{self._h(label)}</label>"
        )

    def _member_label(self, guild: discord.Guild, user_id: typing.Any) -> str:
        if user_id in (None, ""):
            return "Unclaimed"
        try:
            member = guild.get_member(int(user_id))
        except (TypeError, ValueError):
            return "Unknown"
        return str(member) if member else f"User {user_id}"

    def _selected(self, value: typing.Any, selected: typing.Any) -> str:
        return "selected" if str(value) == str(selected) else ""

    def _format_dashboard_time(self, value: typing.Any) -> str:
        try:
            timestamp = float(value)
        except (TypeError, ValueError):
            return "Unknown"
        return datetime.fromtimestamp(timestamp, tz=timezone.utc).strftime(
            "%Y-%m-%d %H:%M UTC",
        )

    def _h(self, value: typing.Any) -> str:
        return html.escape("" if value is None else str(value), quote=True)
