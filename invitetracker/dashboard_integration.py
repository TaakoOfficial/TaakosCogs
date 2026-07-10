"""Red-Web-Dashboard integration for InviteTracker."""

from __future__ import annotations

import html
import logging
import typing
from datetime import datetime, timezone

import discord
from redbot.core import commands

log = logging.getLogger("red.taakoscogs.invitetracker.dashboard")


def dashboard_page(*args, **kwargs):
    """Dashboard page decorator compatible with Red-Web-Dashboard."""

    def decorator(func: typing.Callable):
        func.__dashboard_decorator_params__ = (args, kwargs)
        return func

    return decorator


class DashboardIntegration:
    """Dashboard integration mixin for InviteTracker."""

    @commands.Cog.listener()
    async def on_dashboard_cog_add(self, dashboard_cog: commands.Cog) -> None:
        """Register InviteTracker as a Red-Web-Dashboard third party."""
        handler = dashboard_cog.rpc.third_parties_handler
        try:
            handler.add_third_party(self, overwrite=True)
        except TypeError:
            handler.add_third_party(self)

    @dashboard_page(
        name=None,
        description="Configure invite tracking, refresh cache, reset stats, and view summaries.",
        methods=("GET", "POST"),
    )
    async def dashboard_page(
        self,
        user: discord.User,
        guild: discord.Guild,
        **kwargs,
    ) -> dict[str, typing.Any]:
        """Render and process the InviteTracker dashboard page."""
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
                messages = await self._dashboard_handle_action(guild, action, form_data)
            except commands.CommandError as error:
                notifications.append(
                    {"message": str(error), "category": "error"})
            except Exception as error:
                log.exception("InviteTracker dashboard action failed.")
                notifications.append(
                    {
                        "message": f"InviteTracker dashboard action failed: {error}",
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
    ) -> int:
        value = self._dash_value(form_data, key).strip()
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
        action: str,
        form_data: typing.Any,
    ) -> list[dict[str, str]]:
        if action == "save_settings":
            cache_size = await self._dashboard_save_settings(guild, form_data)
            message = "InviteTracker settings saved."
            if cache_size is not None:
                message += f" Cached {self._count(cache_size)} invite(s)."
            return [{"message": message, "category": "success"}]

        if action == "refresh_cache":
            invite_cache = await self._refresh_invite_cache(guild)
            return [
                {
                    "message": (
                        f"Invite cache refreshed. Cached "
                        f"{self._count(len(invite_cache))} invite(s)."
                    ),
                    "category": "success",
                },
            ]

        if action == "reset_stats":
            return await self._dashboard_reset_stats(guild, form_data)

        if action:
            raise commands.BadArgument(
                "Unknown InviteTracker dashboard action.")
        return []

    async def _dashboard_save_settings(
        self,
        guild: discord.Guild,
        form_data: typing.Any,
    ) -> int | None:
        enabled = self._dash_bool(form_data, "enabled")
        include_bots = self._dash_bool(form_data, "include_bots")
        log_channel_id = self._dash_optional_id(form_data, "log_channel_id")
        fake_age_hours = self._dash_int(
            form_data,
            "fake_age_hours",
            default=24,
            minimum=0,
            maximum=8760,
        )

        if log_channel_id is not None:
            channel = guild.get_channel(log_channel_id)
            if not isinstance(channel, discord.TextChannel):
                raise commands.BadArgument(
                    "The invite log channel must be a text channel.",
                )
            me = guild.me
            if me is None:
                raise commands.CommandError(
                    "I could not check my channel permissions.")
            permissions = channel.permissions_for(me)
            if not permissions.send_messages or not permissions.embed_links:
                raise commands.CommandError(
                    f"I need Send Messages and Embed Links in #{channel.name}.",
                )

        guild_conf = self.config.guild(guild)
        await guild_conf.log_channel_id.set(log_channel_id)
        await guild_conf.include_bots.set(include_bots)
        await guild_conf.fake_age_hours.set(fake_age_hours)

        cache_size = None
        if enabled:
            invite_cache = await self._refresh_invite_cache(guild)
            cache_size = len(invite_cache)
        await guild_conf.enabled.set(enabled)
        return cache_size

    async def _dashboard_reset_stats(
        self,
        guild: discord.Guild,
        form_data: typing.Any,
    ) -> list[dict[str, str]]:
        confirmation = self._dash_value(
            form_data, "reset_confirm").strip().lower()
        if confirmation != "confirm":
            raise commands.BadArgument(
                "Type `confirm` to reset all InviteTracker stats.",
            )

        await self.config.guild(guild).inviters.set({})
        await self.config.guild(guild).members.set({})
        await self.config.guild(guild).unknown_joins.set(0)
        try:
            invite_cache = await self._refresh_invite_cache(guild)
        except commands.CommandError as error:
            return [
                {
                    "message": (
                        "InviteTracker stats were reset, but the invite cache could "
                        f"not be refreshed: {error}"
                    ),
                    "category": "warning",
                },
            ]
        return [
            {
                "message": (
                    "InviteTracker stats reset. Cached "
                    f"{self._count(len(invite_cache))} invite(s)."
                ),
                "category": "success",
            },
        ]

    async def _dashboard_source(
        self,
        guild: discord.Guild,
        kwargs: dict[str, typing.Any],
    ) -> str:
        settings = await self.config.guild(guild).all()
        invite_cache = settings.get("invite_cache") or {}
        inviters = settings.get("inviters") or {}
        members = settings.get("members") or {}
        csrf = self._dash_csrf(kwargs)

        total_joins = sum(int(stats.get("joins", 0))
                          for stats in inviters.values())
        total_leaves = sum(int(stats.get("leaves", 0))
                           for stats in inviters.values())
        total_fake = sum(int(stats.get("fake", 0))
                         for stats in inviters.values())
        active_members = sum(
            1 for record in members.values() if not record.get("left_at")
        )
        leaderboard = self._leaderboard_rows(guild, inviters)
        recent_members = self._recent_member_rows(guild, members)
        active_tab = self._dashboard_active_tab(
            kwargs,
            {
                "save_settings": "settings",
                "refresh_cache": "maintenance",
                "reset_stats": "maintenance",
            },
            "reports",
        )

        return f"""
<style>
.it-dash {{
  --bg: #101318; --panel: #171b22; --line: #2a303a; --text: #eef1f5;
  --muted: #aab2bf; --accent: #8ab4ff; --danger: #ff6b6b;
  color: var(--text); display: grid; gap: 16px;
}}
.it-dash * {{ box-sizing: border-box; }}
.it-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 16px; }}
.it-card {{ background: var(--panel); border: 1px solid var(--line); border-radius: 8px; padding: 16px; }}
.it-card h2 {{ margin: 0 0 12px; font-size: 18px; }}
.it-stats {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(145px, 1fr)); gap: 10px; }}
.it-stat {{ border: 1px solid var(--line); border-radius: 8px; padding: 12px; }}
.it-stat strong {{ display: block; font-size: 22px; }}
.it-stat span, .it-muted {{ color: var(--muted); }}
.it-field {{ display: grid; gap: 6px; margin-bottom: 10px; }}
.it-field label {{ color: var(--muted); font-size: 13px; }}
.it-field input, .it-field select {{
  width: 100%; background: #0c0f14; color: var(--text); border: 1px solid var(--line);
  border-radius: 6px; padding: 9px 10px;
}}
.it-check {{ display: flex; align-items: center; gap: 8px; margin-bottom: 10px; color: var(--muted); }}
.it-check input {{ width: auto; }}
.it-actions {{ display: flex; flex-wrap: wrap; gap: 8px; margin-top: 12px; }}
.it-actions button {{
  background: var(--accent); color: #07111f; border: 0; border-radius: 6px;
  padding: 9px 12px; font-weight: 700; cursor: pointer;
}}
.it-actions button.danger {{ background: var(--danger); color: #210909; }}
.it-table {{ width: 100%; border-collapse: collapse; font-size: 14px; }}
.it-table th, .it-table td {{ border-bottom: 1px solid var(--line); padding: 8px; text-align: left; vertical-align: top;
 }}
.it-table th {{ color: var(--muted); font-weight: 600; }}
.dash-tabs {{ display: flex; gap: 4px; overflow-x: auto; position: sticky; top: 0; z-index: 10; padding: 5px;
background: #0c0f14; border: 1px solid var(--line); border-radius: 8px; }}
.dash-tab {{ flex: 0 0 auto; border: 0; border-radius: 6px; padding: 9px 13px; background: transparent; color:
var(--muted); cursor: pointer; font-weight: 700; white-space: nowrap; }}
.dash-tab:hover {{ background: var(--panel); color: var(--text); }} .dash-tab.active {{ background: var(--accent);
color: #07111f; }}
.dash-panel {{ display: none; }} .dash-panel.active {{ display: block; }}
</style>
<div class="it-dash" data-dashboard-tabs="1">
  <div class="it-stats">
    <div class="it-stat"><strong>{self._h("Enabled" if settings.get("enabled") else
    "Disabled")}</strong><span>Status</span></div>
    <div class="it-stat"><strong>{self._count(total_joins)}</strong><span>joins</span></div>
    <div class="it-stat"><strong>{self._count(total_leaves)}</strong><span>leaves</span></div>
    <div class="it-stat"><strong>{self._count(total_fake)}</strong><span>fake joins</span></div>
    <div class="it-stat"><strong>{self._count(active_members)}</strong><span>active tracked</span></div>
    <div class="it-stat"><strong>{self._count(len(invite_cache))}</strong><span>cached invites</span></div>
  </div>
  <div class="dash-tabs" role="tablist" aria-label="InviteTracker sections">
    {self._dashboard_tab_button("reports", "Reports", active_tab)}
    {self._dashboard_tab_button("settings", "Settings", active_tab)}
    {self._dashboard_tab_button("maintenance", "Maintenance", active_tab)}
  </div>
  <section class="dash-panel{" active" if active_tab == "settings" else ""}" data-tab-panel="settings"><div
  class="it-grid">
    <form class="it-card" method="post">
      {csrf}
      <input type="hidden" name="action" value="save_settings">
      <h2>Settings</h2>
      {self._checkbox("enabled", "Enable invite tracking", settings.get("enabled"))}
      {self._select("log_channel_id", "Invite log channel", self._text_options(guild), settings.get("log_channel_id"),
      "No log channel")}
      {self._input("fake_age_hours", "Fake join threshold hours", settings.get("fake_age_hours") or 0, "number", 0,
      8760)}
      {self._checkbox("include_bots", "Track bot joins", settings.get("include_bots"))}
      <div class="it-actions"><button type="submit">Save settings</button></div>
    </form>
  </div></section>
  <section class="dash-panel{" active" if active_tab == "maintenance" else ""}" data-tab-panel="maintenance"><div
  class="it-grid">
    <div class="it-card">
      <h2>Maintenance</h2>
      <form method="post" class="it-actions">
        {csrf}
        <input type="hidden" name="action" value="refresh_cache">
        <button type="submit">Refresh invite cache</button>
      </form>
      <form method="post" class="it-actions">
        {csrf}
        <input type="hidden" name="action" value="reset_stats">
        <input name="reset_confirm" placeholder="type confirm">
        <button class="danger" type="submit">Reset stats</button>
      </form>
      <p class="it-muted">Reset clears inviter totals, tracked member sources, and unknown join count.</p>
    </div>
  </div></section>
  <section class="dash-panel{" active" if active_tab == "reports" else ""}" data-tab-panel="reports"><div
  class="it-grid">
    <div class="it-card">
      <h2>Top Inviters</h2>
      {leaderboard}
    </div>
    <div class="it-card">
      <h2>Recent Tracked Members</h2>
      {recent_members}
    </div>
  </div></section>
  {self._dashboard_tabs_script()}
</div>
"""

    def _leaderboard_rows(
        self,
        guild: discord.Guild,
        inviters: dict[str, typing.Any],
    ) -> str:
        if not inviters:
            return '<p class="it-muted">No invite stats have been tracked yet.</p>'
        ranked = sorted(
            inviters.items(),
            key=lambda item: (
                self._net_joins(item[1]),
                int(item[1].get("joins", 0)),
                -int(item[1].get("leaves", 0)),
            ),
            reverse=True,
        )
        rows = []
        for index, (user_id, stats) in enumerate(ranked[:10], start=1):
            rows.append(
                "<tr>"
                f"<td>{index}</td>"
                f"<td>{self._h(self._member_label(guild, user_id))}</td>"
                f"<td>{self._count(self._net_joins(stats))}</td>"
                f"<td>{self._count(int(stats.get('joins', 0)))}</td>"
                f"<td>{self._count(int(stats.get('leaves', 0)))}</td>"
                f"<td>{self._count(int(stats.get('fake', 0)))}</td>"
                "</tr>",
            )
        return (
            '<table class="it-table"><thead><tr><th>#</th><th>Inviter</th>'
            "<th>Net</th><th>Joins</th><th>Leaves</th><th>Fake</th></tr></thead><tbody>"
            + "".join(rows)
            + "</tbody></table>"
        )

    def _recent_member_rows(
        self,
        guild: discord.Guild,
        members: dict[str, typing.Any],
    ) -> str:
        if not members:
            return (
                '<p class="it-muted">No member join sources have been tracked yet.</p>'
            )
        records = sorted(
            members.values(),
            key=lambda record: float(record.get("joined_at") or 0),
            reverse=True,
        )
        rows = []
        for record in records[:10]:
            member_id = record.get("member_id")
            inviter_id = record.get("inviter_id")
            left = "Yes" if record.get("left_at") else "No"
            fake = "Yes" if record.get("fake") else "No"
            rows.append(
                "<tr>"
                f"<td>{self._h(self._member_label(guild, member_id))}</td>"
                f"<td>{self._h(self._member_label(guild, inviter_id))}</td>"
                f"<td>{self._h(record.get('invite_code') or 'Unknown')}</td>"
                f"<td>{self._h(self._format_dashboard_time(record.get('joined_at')))}</td>"
                f"<td>{self._h(left)}</td>"
                f"<td>{self._h(fake)}</td>"
                "</tr>",
            )
        return (
            '<table class="it-table"><thead><tr><th>Member</th><th>Inviter</th>'
            "<th>Invite</th><th>Joined</th><th>Left</th><th>Fake</th></tr></thead><tbody>"
            + "".join(rows)
            + "</tbody></table>"
        )

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
            f'<div class="it-field"><label>{self._h(label)}</label>'
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
            f'<div class="it-field"><label>{self._h(label)}</label>'
            f'<input type="{self._h(input_type)}" name="{self._h(name)}" '
            f'value="{self._h(value)}" {" ".join(attrs)}></div>'
        )

    def _checkbox(self, name: str, label: str, checked: typing.Any) -> str:
        checked_attr = "checked" if checked else ""
        return (
            '<label class="it-check">'
            f'<input type="checkbox" name="{self._h(name)}" value="1" {checked_attr}>'
            f"{self._h(label)}</label>"
        )

    def _member_label(self, guild: discord.Guild, user_id: typing.Any) -> str:
        if user_id in (None, ""):
            return "Unknown"
        try:
            user_int = int(user_id)
        except (TypeError, ValueError):
            return "Unknown"
        member = guild.get_member(user_int)
        return str(member) if member else f"User {user_int}"

    def _selected(self, value: typing.Any, selected: typing.Any) -> str:
        return "selected" if str(value) == str(selected) else ""

    def _format_dashboard_time(self, value: typing.Any) -> str:
        if value in (None, ""):
            return "Unknown"
        try:
            timestamp = float(value)
        except (TypeError, ValueError):
            return "Unknown"
        return datetime.fromtimestamp(timestamp, tz=timezone.utc).strftime(
            "%Y-%m-%d %H:%M UTC",
        )

    def _h(self, value: typing.Any) -> str:
        return html.escape("" if value is None else str(value), quote=True)
