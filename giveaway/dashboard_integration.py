"""Red-Web-Dashboard integration for Giveaway."""

from __future__ import annotations

import html
import logging
import typing
from datetime import datetime, timezone

import discord
from redbot.core import commands

log = logging.getLogger("red.taakoscogs.giveaway.dashboard")


def dashboard_page(*args, **kwargs):
    """Dashboard page decorator compatible with Red-Web-Dashboard."""

    def decorator(func: typing.Callable):
        func.__dashboard_decorator_params__ = (args, kwargs)
        return func

    return decorator


class DashboardIntegration:
    """Dashboard integration mixin for Giveaway."""

    @commands.Cog.listener()
    async def on_dashboard_cog_add(self, dashboard_cog: commands.Cog) -> None:
        """Register Giveaway as a Red-Web-Dashboard third party."""
        handler = dashboard_cog.rpc.third_parties_handler
        try:
            handler.add_third_party(self, overwrite=True)
        except TypeError:
            handler.add_third_party(self)

    @dashboard_page(
        name=None,
        description="Start, attach, end, cancel, reroll, and inspect giveaways.",
        methods=("GET", "POST"),
    )
    async def dashboard_page(
        self,
        user: discord.User,
        guild: discord.Guild,
        **kwargs,
    ) -> dict[str, typing.Any]:
        """Render and process the Giveaway dashboard page."""
        member, can_manage = await self._dashboard_member_can_manage(user, guild)
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
                    member,
                    action,
                    form_data,
                )
            except commands.CommandError as error:
                notifications.append(
                    {"message": str(error), "category": "error"})
            except Exception as error:
                log.exception("Giveaway dashboard action failed.")
                notifications.append(
                    {
                        "message": f"Giveaway dashboard action failed: {error}",
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

    def _dashboard_active_tab(
        self,
        kwargs: dict[str, typing.Any],
        action_tabs: dict[str, str],
        default: str,
    ) -> str:
        form_data = self._dashboard_form_data(kwargs)
        selected = self._dash_value(form_data, "active_tab").lower()
        valid = set(action_tabs.values()) | {default}
        if selected in valid:
            return selected
        return action_tabs.get(self._dash_value(form_data, "action").lower(), default)

    def _dashboard_tab_button(self, name: str, label: str, active: str) -> str:
        selected = name == active
        return (
            f'<button type="button" class="dash-tab{" active" if selected else ""}" '
            f'data-tab="{self._h(name)}" role="tab" aria-selected="{str(selected).lower()}" '
            f'tabindex="{0 if selected else -1}">{self._h(label)}</button>'
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
            const activate = (name, updateHash = false) => {
                if (!names.has(name)) return;
                tabs.forEach((tab) => {
                    const selected = tab.dataset.tab === name;
                    tab.classList.toggle("active", selected);
                    tab.setAttribute("aria-selected", selected ? "true" : "false");
                    tab.tabIndex = selected ? 0 : -1;
                });
                panels.forEach((panel) => {
                    const selected = panel.dataset.tabPanel === name;
                    panel.classList.toggle("active", selected);
                    panel.hidden = !selected;
                });
                if (updateHash) history.replaceState(null, "", `#tab-${name}`);
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
                    const offset = event.key === "ArrowRight" ? 1 : event.key === "ArrowLeft" ? -1 : 0;
                    if (!offset) return;
                    event.preventDefault();
                    const next = tabs[(index + offset + tabs.length) % tabs.length];
                    next.focus();
                    activate(next.dataset.tab, true);
                });
            });
            root.querySelectorAll("form").forEach((form) => form.addEventListener("submit", () => {
                let input = form.querySelector('input[name="active_tab"]');
                if (!input) {
                    input = document.createElement("input");
                    input.type = "hidden";
                    input.name = "active_tab";
                    form.appendChild(input);
                }
                input.value = root.querySelector("[data-tab].active").dataset.tab;
            }));
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
        member: discord.Member | None,
        action: str,
        form_data: typing.Any,
    ) -> list[dict[str, str]]:
        messages: list[dict[str, str]] = []

        if action == "start_giveaway":
            record, message, duration_text = await self._dashboard_start_giveaway(
                guild,
                user,
                member,
                form_data,
            )
            jump_url = self._build_jump_url(
                guild.id,
                int(record["channel_id"]),
                int(message.id),
            )
            messages.append(
                {
                    "message": f"Giveaway started. It ends in {duration_text}: {jump_url}",
                    "category": "success",
                },
            )

        elif action == "attach_giveaway":
            (
                record,
                entry_message,
                status_message,
                duration_text,
            ) = await self._dashboard_attach_giveaway(guild, user, member, form_data)
            entry_url = self._build_jump_url(
                guild.id,
                int(record["channel_id"]),
                int(entry_message.id),
            )
            status_url = self._build_jump_url(
                guild.id,
                int(record["channel_id"]),
                int(status_message.id),
            )
            messages.append(
                {
                    "message": (
                        f"Giveaway attached. It ends in {duration_text}. "
                        f"Entry: {entry_url} Status: {status_url}"
                    ),
                    "category": "success",
                },
            )

        elif action == "end_giveaway":
            record, winners = await self._dashboard_end_giveaway(guild, form_data)
            winner_text = (
                ", ".join(str(winner)
                          for winner in winners) or "No valid entries"
            )
            messages.append(
                {
                    "message": f"Giveaway `{record['message_id']}` ended. Winner(s): {winner_text}",
                    "category": "success",
                },
            )

        elif action == "cancel_giveaway":
            record = await self._dashboard_cancel_giveaway(guild, form_data)
            messages.append(
                {
                    "message": f"Giveaway `{record['message_id']}` cancelled.",
                    "category": "success",
                },
            )

        elif action == "reroll_giveaway":
            record, winners = await self._dashboard_reroll_giveaway(guild, form_data)
            await self._announce_reroll(guild, record, winners)
            winner_text = ", ".join(str(winner) for winner in winners)
            messages.append(
                {
                    "message": f"Giveaway `{record['message_id']}` rerolled. Winner(s): {winner_text}",
                    "category": "success",
                },
            )

        elif action == "refresh_giveaway":
            record = await self._dashboard_refresh_giveaway(guild, form_data)
            messages.append(
                {
                    "message": f"Giveaway `{record['message_id']}` message refreshed.",
                    "category": "success",
                },
            )

        elif action:
            raise commands.BadArgument("Unknown Giveaway dashboard action.")

        return messages

    async def _dashboard_start_giveaway(
        self,
        guild: discord.Guild,
        user: discord.User,
        member: discord.Member | None,
        form_data: typing.Any,
    ) -> tuple[dict[str, typing.Any], discord.Message, str]:
        channel = self._dashboard_required_text_channel(
            guild,
            self._dash_optional_id(form_data, "start_channel_id"),
            "Choose a text channel for the giveaway.",
        )
        duration = self._dash_value(form_data, "start_duration").strip()
        winner_count = self._dash_int(
            form_data,
            "start_winner_count",
            default=1,
            minimum=1,
            maximum=self.MAX_WINNERS,
        )
        prize = self._dash_value(form_data, "start_prize").strip()
        host_id = (
            self._dash_optional_id(
                form_data, "start_host_id") or (member or user).id
        )
        return await self._create_giveaway(
            guild,
            channel,
            host_id,
            duration,
            winner_count,
            prize,
        )

    async def _dashboard_attach_giveaway(
        self,
        guild: discord.Guild,
        user: discord.User,
        member: discord.Member | None,
        form_data: typing.Any,
    ) -> tuple[dict[str, typing.Any], discord.Message, discord.Message, str]:
        current_channel_id = self._dash_optional_id(
            form_data, "attach_channel_id")
        current_channel = (
            guild.get_channel(
                current_channel_id) if current_channel_id else None
        )
        if current_channel_id and not isinstance(current_channel, discord.TextChannel):
            raise commands.BadArgument(
                "Attach channel must be a text channel.")
        reference = self._dash_value(form_data, "attach_reference").strip()
        duration = self._dash_value(form_data, "attach_duration").strip()
        winner_count = self._dash_int(
            form_data,
            "attach_winner_count",
            default=1,
            minimum=1,
            maximum=self.MAX_WINNERS,
        )
        prize = self._dash_value(form_data, "attach_prize").strip() or None
        host_id = (
            self._dash_optional_id(
                form_data, "attach_host_id") or (member or user).id
        )
        return await self._attach_giveaway(
            guild,
            current_channel
            if isinstance(current_channel, discord.TextChannel)
            else None,
            host_id,
            reference,
            duration,
            winner_count,
            prize,
        )

    async def _dashboard_end_giveaway(
        self,
        guild: discord.Guild,
        form_data: typing.Any,
    ) -> tuple[dict[str, typing.Any], list[discord.Member]]:
        reference = self._dash_value(form_data, "manage_reference").strip()
        key, _record = await self._get_record_from_reference(guild, reference)
        return await self._end_giveaway(guild, int(key))

    async def _dashboard_cancel_giveaway(
        self,
        guild: discord.Guild,
        form_data: typing.Any,
    ) -> dict[str, typing.Any]:
        reference = self._dash_value(form_data, "manage_reference").strip()
        key, _record = await self._get_record_from_reference(guild, reference)
        return await self._cancel_giveaway(guild, int(key))

    async def _dashboard_reroll_giveaway(
        self,
        guild: discord.Guild,
        form_data: typing.Any,
    ) -> tuple[dict[str, typing.Any], list[discord.Member]]:
        reference = self._dash_value(form_data, "reroll_reference").strip()
        key, record = await self._get_record_from_reference(guild, reference)
        winner_count = self._dash_int(
            form_data,
            "reroll_winner_count",
            default=int(record.get("winner_count", 1)),
            minimum=1,
            maximum=self.MAX_WINNERS,
        )
        self._ensure_winner_count(winner_count)
        return await self._reroll_giveaway(guild, int(key), winner_count)

    async def _dashboard_refresh_giveaway(
        self,
        guild: discord.Guild,
        form_data: typing.Any,
    ) -> dict[str, typing.Any]:
        reference = self._dash_value(form_data, "refresh_reference").strip()
        _key, record = await self._get_record_from_reference(guild, reference)
        await self._edit_giveaway_message(guild, record)
        return record

    async def _dashboard_source(
        self,
        guild: discord.Guild,
        kwargs: dict[str, typing.Any],
    ) -> str:
        giveaways = await self.config.guild(guild).giveaways()
        csrf = self._dash_csrf(kwargs)
        records = sorted(
            giveaways.values(),
            key=lambda record: float(record.get("ends_at") or 0),
            reverse=True,
        )
        active_count = sum(
            1 for record in records if record.get("status") == "active")
        ended_count = sum(
            1 for record in records if record.get("status") == "ended")
        cancelled_count = sum(
            1 for record in records if record.get("status") == "cancelled"
        )
        active_tab = self._dashboard_active_tab(
            kwargs,
            {
                "start_giveaway": "create",
                "attach_giveaway": "create",
                "end_giveaway": "manage",
                "cancel_giveaway": "manage",
                "refresh_giveaway": "manage",
                "reroll_giveaway": "manage",
            },
            "overview",
        )

        return f"""
        <style>
            .gw-wrap {{ max-width: 1180px; margin: 0 auto; color: #e5e7eb; }}
            .gw-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(260px, 1fr)); gap: 16px; }}
            .gw-row {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 12px;
            margin-bottom: 12px; }}
            .gw-card {{ background: #1f2937; border: 1px solid #374151; border-radius: 8px; padding: 16px;
            margin-bottom: 16px; }}
            .gw-card h2, .gw-card h3 {{ margin: 0 0 12px 0; color: #f9fafb; }}
            .gw-muted {{ color: #9ca3af; }}
            .gw-stat {{ font-size: 1.5rem; font-weight: 700; color: #f9fafb; }}
            .gw-field label {{ display: block; font-weight: 600; margin-bottom: 4px; color: #d1d5db; }}
            .gw-field input, .gw-field select, .gw-field textarea {{
                width: 100%; box-sizing: border-box; border: 1px solid #4b5563; border-radius: 6px;
                background: #111827; color: #f9fafb; padding: 8px; min-height: 38px;
            }}
            .gw-field textarea {{ min-height: 82px; font-family: ui-monospace, SFMono-Regular, Menlo, monospace; }}
            .gw-btn {{ background: #2563eb; color: white; border: 0; border-radius: 6px; padding: 9px 14px; cursor:
            pointer; font-weight: 700; }}
            .gw-btn.secondary {{ background: #4b5563; }}
            .gw-btn.danger {{ background: #dc2626; }}
            .dash-tabs {{ display: flex; gap: 4px; overflow-x: auto; position: sticky; top: 0; z-index: 10; margin: 0 0
            16px; padding: 5px; background: #111827; border: 1px solid #374151; border-radius: 8px; }}
            .dash-tab {{ flex: 0 0 auto; border: 0; border-radius: 6px; padding: 9px 13px; background: transparent;
            color: #9ca3af; cursor: pointer; font-weight: 700; white-space: nowrap; }}
            .dash-tab:hover {{ background: #1f2937; color: #f9fafb; }}
            .dash-tab.active {{ background: #2563eb; color: white; }}
            .dash-panel {{ display: none; }}
            .dash-panel.active {{ display: block; }}
            .gw-table {{ width: 100%; border-collapse: collapse; font-size: 0.92rem; }}
            .gw-table th, .gw-table td {{ border-bottom: 1px solid #374151; padding: 8px; text-align: left;
            vertical-align: top; }}
            .gw-table th {{ color: #d1d5db; }}
        </style>
        <div class="gw-wrap" data-dashboard-tabs="1">
            <div class="gw-card">
                <h2>Giveaway Dashboard</h2>
                <div class="gw-grid">
                    <div><div class="gw-muted">Total</div><div class="gw-stat">{len(records)}</div></div>
                    <div><div class="gw-muted">Active</div><div class="gw-stat">{active_count}</div></div>
                    <div><div class="gw-muted">Ended</div><div class="gw-stat">{ended_count}</div></div>
                    <div><div class="gw-muted">Cancelled</div><div class="gw-stat">{cancelled_count}</div></div>
                </div>
            </div>
            <div class="dash-tabs" role="tablist" aria-label="Giveaway sections">
                {self._dashboard_tab_button("overview", "Overview", active_tab)}
                {self._dashboard_tab_button("create", "Create", active_tab)}
                {self._dashboard_tab_button("manage", "Manage", active_tab)}
            </div>
            <section class="dash-panel{" active" if active_tab == "overview" else ""}"
            data-tab-panel="overview">{self._dashboard_records_section(guild, records)}</section>
            <section class="dash-panel{" active" if active_tab == "create" else ""}"
            data-tab-panel="create">{self._dashboard_start_section(guild, csrf)}{self._dashboard_attach_section(guild,
            csrf)}</section>
            <section class="dash-panel{" active" if active_tab == "manage" else ""}"
            data-tab-panel="manage">{self._dashboard_manage_section(giveaways,
            csrf)}{self._dashboard_reroll_section(giveaways, csrf)}</section>
            {self._dashboard_tabs_script()}
        </div>
        """

    def _dashboard_records_section(
        self,
        guild: discord.Guild,
        records: typing.Sequence[dict[str, typing.Any]],
    ) -> str:
        rows = []
        for record in records[:100]:
            channel = self._get_text_channel(
                guild, int(record.get("channel_id") or 0))
            jump_url = self._build_jump_url(
                guild.id,
                int(record.get("channel_id") or 0),
                int(record.get("message_id") or 0),
            )
            rows.append(
                "<tr>"
                f"<td>{self._h(record.get('message_id'))}</td>"
                f"<td>{self._h(record.get('status') or 'active')}</td>"
                f"<td>{self._h(record.get('source') or 'created')}</td>"
                f"<td>{self._h(channel.name if channel else record.get('channel_id') or 'missing')}</td>"
                f"<td>{self._h(self._shorten(str(record.get('prize') or ''), 120))}</td>"
                f"<td>{self._h(record.get('winner_count') or 1)}</td>"
                f"<td>{self._h(record.get('entry_count') or 0)}</td>"
                f"<td>{self._h(self._format_dashboard_time(record.get('ends_at')))}</td>"
                f'<td><a href="{self._h(jump_url)}">Jump</a></td>'
                "</tr>",
            )
        table = "".join(rows) or (
            '<tr><td colspan="9" class="gw-muted">No giveaways are tracked.</td></tr>'
        )
        return f"""
        <div id="giveaways" class="gw-card">
            <h3>Tracked Giveaways</h3>
            <table class="gw-table">
                <thead><tr><th>Message
                ID</th><th>Status</th><th>Source</th><th>Channel</th><th>Prize</th><th>Winners</th><th>Entries</th><th>Ends</th><th>Link</th></tr></thead>
                <tbody>{table}</tbody>
            </table>
        </div>
        """

    def _dashboard_start_section(self, guild: discord.Guild, csrf: str) -> str:
        return f"""
        <div id="start" class="gw-card">
            <h3>Start Giveaway</h3>
            <form method="POST">
                {csrf}
                <input type="hidden" name="action" value="start_giveaway">
                <div class="gw-row">
                    {self._channel_select(guild, "start_channel_id", "Channel", None)}
                    {self._input("start_duration", "Duration", "1h")}
                    {self._input("start_winner_count", "Winner Count", 1, "number", min_value=1,
                    max_value=self.MAX_WINNERS)}
                    {self._input("start_host_id", "Host User ID", "")}
                </div>
                {self._textarea("start_prize", "Prize", "", rows=3)}
                <button class="gw-btn" type="submit">Start Giveaway</button>
            </form>
        </div>
        """

    def _dashboard_attach_section(self, guild: discord.Guild, csrf: str) -> str:
        return f"""
        <div id="attach" class="gw-card">
            <h3>Attach Giveaway</h3>
            <form method="POST">
                {csrf}
                <input type="hidden" name="action" value="attach_giveaway">
                <div class="gw-row">
                    {self._channel_select(guild, "attach_channel_id", "Message Channel", None)}
                    {self._input("attach_reference", "Message ID or Link", "")}
                    {self._input("attach_duration", "Duration", "1h")}
                    {self._input("attach_winner_count", "Winner Count", 1, "number", min_value=1,
                    max_value=self.MAX_WINNERS)}
                    {self._input("attach_host_id", "Host User ID", "")}
                </div>
                {self._textarea("attach_prize", "Prize Override", "", rows=3)}
                <button class="gw-btn" type="submit">Attach Giveaway</button>
            </form>
        </div>
        """

    def _dashboard_manage_section(
        self,
        giveaways: dict[str, dict[str, typing.Any]],
        csrf: str,
    ) -> str:
        options = self._record_options(giveaways, status_filter={"active"})
        all_options = self._record_options(giveaways)
        return f"""
        <div id="manage" class="gw-card">
            <h3>Manage Active Giveaway</h3>
            <div class="gw-grid">
                <form method="POST">
                    {csrf}
                    <input type="hidden" name="action" value="end_giveaway">
                    <div class="gw-field"><label>Active Giveaway</label><select
                    name="manage_reference">{options}</select></div>
                    <button class="gw-btn" type="submit">End Now</button>
                </form>
                <form method="POST">
                    {csrf}
                    <input type="hidden" name="action" value="cancel_giveaway">
                    <div class="gw-field"><label>Active Giveaway</label><select
                    name="manage_reference">{options}</select></div>
                    <button class="gw-btn danger" type="submit">Cancel</button>
                </form>
                <form method="POST">
                    {csrf}
                    <input type="hidden" name="action" value="refresh_giveaway">
                    <div class="gw-field"><label>Giveaway</label><select
                    name="refresh_reference">{all_options}</select></div>
                    <button class="gw-btn secondary" type="submit">Refresh Message</button>
                </form>
            </div>
        </div>
        """

    def _dashboard_reroll_section(
        self,
        giveaways: dict[str, dict[str, typing.Any]],
        csrf: str,
    ) -> str:
        options = self._record_options(giveaways, status_filter={"ended"})
        return f"""
        <div id="reroll" class="gw-card">
            <h3>Reroll Ended Giveaway</h3>
            <form method="POST">
                {csrf}
                <input type="hidden" name="action" value="reroll_giveaway">
                <div class="gw-row">
                    <div class="gw-field"><label>Ended Giveaway</label><select
                    name="reroll_reference">{options}</select></div>
                    {self._input("reroll_winner_count", "Winner Count", "", "number", min_value=1,
                    max_value=self.MAX_WINNERS)}
                </div>
                <button class="gw-btn secondary" type="submit">Reroll Winners</button>
            </form>
        </div>
        """

    def _record_options(
        self,
        giveaways: dict[str, dict[str, typing.Any]],
        *,
        status_filter: set[str] | None = None,
    ) -> str:
        records = []
        for key, record in giveaways.items():
            if status_filter is not None and record.get("status") not in status_filter:
                continue
            records.append((key, record))
        if not records:
            return '<option value="">No matching giveaways</option>'
        records.sort(key=lambda item: float(
            item[1].get("ends_at") or 0), reverse=True)
        options = []
        for key, record in records[:100]:
            label = (
                f"{record.get('message_id') or key} - "
                f"{record.get('status') or 'active'} - "
                f"{self._shorten(str(record.get('prize') or ''), 70)}"
            )
            options.append(
                f'<option value="{self._h(key)}">{self._h(label)}</option>')
        return "".join(options)

    def _dashboard_required_text_channel(
        self,
        guild: discord.Guild,
        channel_id: int | None,
        error_message: str,
    ) -> discord.TextChannel:
        channel = guild.get_channel(channel_id) if channel_id else None
        if not isinstance(channel, discord.TextChannel):
            raise commands.BadArgument(error_message)
        return channel

    def _channel_select(
        self,
        guild: discord.Guild,
        name: str,
        label: str,
        selected: typing.Any,
    ) -> str:
        options = ['<option value="">None</option>']
        for channel in sorted(guild.text_channels, key=lambda item: item.name.lower()):
            options.append(
                f'<option value="{channel.id}" {self._selected(channel.id, selected)}>#{self._h(channel.name)}</option>',
            )
        return (
            f'<div class="gw-field"><label>{self._h(label)}</label>'
            f'<select name="{self._h(name)}">{"".join(options)}</select></div>'
        )

    def _input(
        self,
        name: str,
        label: str,
        value: typing.Any,
        input_type: str = "text",
        *,
        min_value: int | None = None,
        max_value: int | None = None,
    ) -> str:
        attrs = []
        if min_value is not None:
            attrs.append(f'min="{min_value}"')
        if max_value is not None:
            attrs.append(f'max="{max_value}"')
        return (
            f'<div class="gw-field"><label>{self._h(label)}</label>'
            f'<input type="{self._h(input_type)}" name="{self._h(name)}" '
            f'value="{self._h(value)}" {" ".join(attrs)}></div>'
        )

    def _textarea(
        self,
        name: str,
        label: str,
        value: typing.Any,
        *,
        rows: int = 4,
    ) -> str:
        return (
            f'<div class="gw-field"><label>{self._h(label)}</label>'
            f'<textarea name="{self._h(name)}" rows="{rows}">{self._h(value)}</textarea></div>'
        )

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
