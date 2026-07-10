"""Red-Web-Dashboard integration for TicketHub."""

from __future__ import annotations

import html
import logging
import typing

import discord
from redbot.core import commands

log = logging.getLogger("red.taakoscogs.tickethub.dashboard")


def dashboard_page(*args, **kwargs):
    """Dashboard page decorator compatible with Red-Web-Dashboard."""

    def decorator(func: typing.Callable):
        func.__dashboard_decorator_params__ = (args, kwargs)
        return func

    return decorator


class DashboardIntegration:
    """Dashboard integration mixin for TicketHub."""

    @commands.Cog.listener()
    async def on_dashboard_cog_add(self, dashboard_cog: commands.Cog) -> None:
        """Register TicketHub as a Red-Web-Dashboard third party."""
        handler = dashboard_cog.rpc.third_parties_handler
        try:
            handler.add_third_party(self, overwrite=True)
        except TypeError:
            handler.add_third_party(self)

    @dashboard_page(
        name=None,
        description="Configure TicketHub profiles, panels, tickets, and imports.",
        methods=("GET", "POST"),
    )
    async def dashboard_page(
        self,
        user: discord.User,
        guild: discord.Guild,
        **kwargs,
    ) -> typing.Dict[str, typing.Any]:
        """Render and process the TicketHub dashboard page."""
        member, can_manage = await self._dashboard_member_can_manage(user, guild)
        if not can_manage:
            return {
                "status": 1,
                "error_title": "Insufficient Permissions",
                "error_message": "You need Manage Server, Red admin, or bot owner access.",
            }

        notifications = []
        form_data = self._dashboard_form_data(kwargs)
        selected_profile = self._dash_value(form_data, "selected_profile") or self._dash_value(
            form_data,
            "profile_name",
        )

        if kwargs.get("method", "GET") == "POST":
            action = self._dash_value(form_data, "action")
            try:
                selected_profile, messages = await self._dashboard_handle_action(
                    guild,
                    member,
                    action,
                    form_data,
                    selected_profile,
                )
            except commands.CommandError as error:
                notifications.append({"message": str(error), "category": "error"})
            except Exception as error:
                log.exception("TicketHub dashboard action failed.")
                notifications.append(
                    {
                        "message": f"TicketHub dashboard action failed: {error}",
                        "category": "error",
                    }
                )
            else:
                notifications.extend(messages)

        source = await self._dashboard_source(guild, selected_profile, kwargs)
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
    ) -> typing.Tuple[typing.Optional[discord.Member], bool]:
        member = guild.get_member(user.id)
        is_owner = user.id in getattr(self.bot, "owner_ids", set())
        is_admin = member is not None and await self.bot.is_admin(member)
        can_manage = (
            is_owner
            or is_admin
            or (member is not None and member.guild_permissions.manage_guild)
        )
        return member, can_manage

    def _dashboard_form_data(self, kwargs: typing.Dict[str, typing.Any]) -> typing.Any:
        data = kwargs.get("data") or {}
        if isinstance(data, dict) and ("form" in data or "json" in data):
            return data.get("form") or data.get("json") or {}
        return data

    def _dashboard_active_tab(self, kwargs, action_tabs, default):
        form_data = self._dashboard_form_data(kwargs)
        selected = self._dash_value(form_data, "active_tab").lower()
        valid = set(action_tabs.values()) | {default}
        return selected if selected in valid else action_tabs.get(self._dash_value(form_data, "action").lower(), default)

    def _dashboard_tab_button(self, name: str, label: str, active: str) -> str:
        selected = name == active
        return f'<button type="button" class="dash-tab{" active" if selected else ""}" data-tab="{self._h(name)}" role="tab" aria-selected="{str(selected).lower()}" tabindex="{0 if selected else -1}">{self._h(label)}</button>'

    @staticmethod
    def _dashboard_tabs_script() -> str:
        return """
<script>
(() => {
  const root = document.currentScript.closest("[data-dashboard-tabs]"); if (!root) return;
  const tabs = Array.from(root.querySelectorAll("[data-tab]")); const panels = Array.from(root.querySelectorAll("[data-tab-panel]")); const names = new Set(tabs.map((tab) => tab.dataset.tab));
  const activate = (name, hash = false) => { if (!names.has(name)) return; tabs.forEach((tab) => { const on = tab.dataset.tab === name; tab.classList.toggle("active", on); tab.setAttribute("aria-selected", on ? "true" : "false"); tab.tabIndex = on ? 0 : -1; }); panels.forEach((panel) => { const on = panel.dataset.tabPanel === name; panel.classList.toggle("active", on); panel.hidden = !on; }); if (hash) history.replaceState(null, "", `#tab-${name}`); };
  const fromHash = () => { const hash = location.hash.slice(1); if (hash.startsWith("tab-") && names.has(hash.slice(4))) return hash.slice(4); const section = document.getElementById(hash); const panel = section ? section.closest("[data-tab-panel]") : null; return panel ? panel.dataset.tabPanel : null; };
  tabs.forEach((tab, index) => { tab.addEventListener("click", () => activate(tab.dataset.tab, true)); tab.addEventListener("keydown", (event) => { const move = event.key === "ArrowRight" ? 1 : event.key === "ArrowLeft" ? -1 : 0; if (!move) return; event.preventDefault(); const next = tabs[(index + move + tabs.length) % tabs.length]; next.focus(); activate(next.dataset.tab, true); }); });
  root.querySelectorAll("form").forEach((form) => form.addEventListener("submit", () => { let input = form.querySelector('input[name="active_tab"]'); if (!input) { input = document.createElement("input"); input.type = "hidden"; input.name = "active_tab"; form.appendChild(input); } input.value = root.querySelector("[data-tab].active").dataset.tab; }));
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

    def _dash_values(self, form_data: typing.Any, key: str) -> typing.List[str]:
        if hasattr(form_data, "getlist"):
            values = form_data.getlist(key)
        elif hasattr(form_data, "get"):
            value = form_data.get(key, [])
            values = value if isinstance(value, (list, tuple)) else [value]
        else:
            values = []
        return [str(value) for value in values if str(value).strip()]

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
        default: typing.Optional[int] = None,
        minimum: typing.Optional[int] = None,
        maximum: typing.Optional[int] = None,
        optional: bool = False,
    ) -> typing.Optional[int]:
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

    def _dash_optional_id(self, form_data: typing.Any, key: str) -> typing.Optional[int]:
        value = self._dash_value(form_data, key).strip()
        if not value:
            return None
        try:
            return int(value)
        except (TypeError, ValueError) as exc:
            raise commands.BadArgument(f"`{key}` must be a Discord ID.") from exc

    def _dash_csrf(self, kwargs: typing.Dict[str, typing.Any]) -> str:
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
        member: typing.Optional[discord.Member],
        action: str,
        form_data: typing.Any,
        selected_profile: str,
    ) -> typing.Tuple[str, typing.List[typing.Dict[str, str]]]:
        messages: typing.List[typing.Dict[str, str]] = []

        if action == "save_global":
            await self.config.guild(guild).enabled.set(self._dash_bool(form_data, "enabled"))
            next_ticket_id = self._dash_int(
                form_data,
                "next_ticket_id",
                default=1,
                minimum=1,
            )
            await self.config.guild(guild).next_ticket_id.set(next_ticket_id)
            messages.append({"message": "TicketHub global settings saved.", "category": "success"})

        elif action == "select_profile":
            selected_profile = self._clean_name(self._dash_value(form_data, "selected_profile", "main"))

        elif action == "create_profile":
            selected_profile = await self._dashboard_create_profile(guild, form_data)
            messages.append(
                {
                    "message": f"Profile `{selected_profile}` created.",
                    "category": "success",
                }
            )

        elif action == "delete_profile":
            target = self._clean_name(self._dash_value(form_data, "selected_profile", "main"))
            await self._dashboard_delete_profile(guild, target)
            selected_profile = "main"
            messages.append({"message": f"Profile `{target}` deleted.", "category": "success"})

        elif action == "save_profile":
            selected_profile = await self._dashboard_save_profile(guild, form_data)
            messages.append(
                {
                    "message": f"Profile `{selected_profile}` settings saved.",
                    "category": "success",
                }
            )

        elif action == "save_modal":
            selected_profile = await self._dashboard_save_modal(guild, form_data)
            messages.append(
                {
                    "message": f"Profile `{selected_profile}` modal settings saved.",
                    "category": "success",
                }
            )

        elif action == "add_modal_question":
            selected_profile = await self._dashboard_add_modal_question(guild, form_data)
            messages.append(
                {
                    "message": f"Modal question added to `{selected_profile}`.",
                    "category": "success",
                }
            )

        elif action == "remove_modal_question":
            selected_profile, removed_label = await self._dashboard_remove_modal_question(
                guild,
                form_data,
            )
            messages.append(
                {
                    "message": f"Removed `{removed_label}` from `{selected_profile}`.",
                    "category": "success",
                }
            )

        elif action == "default_reason_modal":
            selected_profile = self._clean_name(self._dash_value(form_data, "selected_profile", "main"))
            profile = await self._ensure_profile(guild, selected_profile)
            profile["creating_modal"] = self._default_reason_modal()
            await self._set_profile(guild, selected_profile, profile)
            messages.append({"message": "Default reason modal enabled.", "category": "success"})

        elif action == "clear_modal":
            selected_profile = self._clean_name(self._dash_value(form_data, "selected_profile", "main"))
            profile = await self._ensure_profile(guild, selected_profile)
            profile["creating_modal"] = None
            await self._set_profile(guild, selected_profile, profile)
            messages.append({"message": "Modal questions cleared.", "category": "success"})

        elif action == "post_panel":
            selected_profile, message = await self._dashboard_post_panel(guild, form_data)
            messages.append(
                {
                    "message": f"Panel posted for `{selected_profile}`: {message.jump_url}",
                    "category": "success",
                }
            )

        elif action == "attach_panel":
            selected_profile, message = await self._dashboard_attach_panel(guild, form_data)
            messages.append(
                {
                    "message": f"Panel attached for `{selected_profile}`: {message.jump_url}",
                    "category": "success",
                }
            )

        elif action == "clear_panel":
            await self._dashboard_clear_panel(guild, form_data)
            messages.append({"message": "Panel tracking and controls cleared.", "category": "success"})

        elif action == "save_multi_panel":
            message = await self._dashboard_save_multi_panel(guild, form_data)
            messages.append(
                {
                    "message": f"Multi-panel saved: {message.jump_url}",
                    "category": "success",
                }
            )

        elif action == "clear_multi_panel":
            await self._dashboard_clear_multi_panel(guild, form_data)
            messages.append({"message": "Multi-panel cleared.", "category": "success"})

        elif action == "import_aaa3a_panels":
            records = await self._collect_aaa3a_panel_records(guild)
            cleaned = await self._set_aaa3a_panel_records(guild, records)
            messages.append(
                {
                    "message": f"Imported {len(cleaned)} AAA3A panel record(s).",
                    "category": "success",
                }
            )

        elif action == "clear_aaa3a_panels":
            await self._dashboard_clear_aaa3a_panels(guild)
            messages.append({"message": "Imported AAA3A panel records cleared.", "category": "success"})

        elif action == "ticket_action":
            if member is None:
                raise commands.BadArgument("You must be in this server to manage tickets.")
            message = await self._dashboard_ticket_action(guild, member, form_data)
            messages.append({"message": message, "category": "success"})

        elif action == "create_ticket":
            message = await self._dashboard_create_ticket(guild, form_data)
            messages.append({"message": message, "category": "success"})

        elif action == "recover_ticket":
            if member is None:
                raise commands.BadArgument("You must be in this server to recover tickets.")
            record = await self._dashboard_recover_ticket(guild, member, form_data)
            messages.append(
                {
                    "message": f"Recovered ticket #{record['id']}.",
                    "category": "success",
                }
            )

        elif action:
            raise commands.BadArgument("Unknown TicketHub dashboard action.")

        return selected_profile or "main", messages

    async def _dashboard_create_profile(self, guild: discord.Guild, form_data: typing.Any) -> str:
        profile_name = self._clean_name(self._dash_value(form_data, "new_profile_name"))
        profiles = await self._get_profiles(guild)
        if profile_name in profiles:
            raise commands.BadArgument(f"A profile named `{profile_name}` already exists.")
        clone_name = self._dash_value(form_data, "clone_profile")
        profile = self._merge_profile(profiles.get(clone_name)) if clone_name in profiles else self._default_profile()
        profile["panel_channel_id"] = None
        profile["panel_message_id"] = None
        profile["next_profile_ticket_id"] = None
        await self._set_profile(guild, profile_name, profile)
        return profile_name

    async def _dashboard_delete_profile(self, guild: discord.Guild, profile_name: str) -> None:
        if profile_name == "main":
            raise commands.BadArgument("The default `main` profile cannot be deleted.")
        profiles = await self._get_profiles(guild)
        if profile_name not in profiles:
            raise commands.BadArgument(f"No profile named `{profile_name}` exists.")

        tickets = await self.config.guild(guild).tickets()
        if any(str(record.get("profile") or "main") == profile_name for record in tickets.values()):
            raise commands.BadArgument("Delete or recover this profile's tickets before deleting it.")

        multi_panels = await self.config.guild(guild).multi_panels()
        for message_id, raw_record in multi_panels.items():
            try:
                record = self._sanitize_multi_panel_record(raw_record, message_id=int(message_id))
            except (TypeError, ValueError):
                record = None
            if record and any(option["profile"] == profile_name for option in record["options"]):
                raise commands.BadArgument("Remove this profile from multi-panels before deleting it.")

        if profiles[profile_name].get("panel_message_id"):
            raise commands.BadArgument("Clear this profile's panel before deleting it.")

        async with self.config.guild(guild).profiles() as stored_profiles:
            for raw_name in list(stored_profiles):
                if self._clean_name(str(raw_name)) == profile_name:
                    stored_profiles.pop(raw_name, None)
                    break
            if not stored_profiles:
                stored_profiles["main"] = self._default_profile()

    async def _dashboard_save_profile(self, guild: discord.Guild, form_data: typing.Any) -> str:
        profile_name = self._clean_name(self._dash_value(form_data, "selected_profile", "main"))
        profile = await self._ensure_profile(guild, profile_name)
        old_emojis = dict(profile.get("control_emojis") or {})

        profile["enabled"] = self._dash_bool(form_data, "profile_enabled")
        profile["panel_style"] = self._parse_panel_style(self._dash_value(form_data, "panel_style", "button"))
        profile["ticket_mode"] = "thread" if self._dash_value(form_data, "ticket_mode") == "thread" else "channel"
        profile["panel_channel_id"] = self._dash_optional_id(form_data, "panel_channel_id")
        profile["panel_message_id"] = self._dash_optional_id(form_data, "panel_message_id")
        profile["ticket_category_id"] = self._dash_optional_id(form_data, "ticket_category_id")
        profile["closed_category_id"] = self._dash_optional_id(form_data, "closed_category_id")
        profile["thread_parent_channel_id"] = self._dash_optional_id(form_data, "thread_parent_channel_id")
        profile["log_channel_id"] = self._dash_optional_id(form_data, "log_channel_id")
        profile["transcript_channel_id"] = self._dash_optional_id(form_data, "transcript_channel_id")
        profile["ticket_role_id"] = self._dash_optional_id(form_data, "ticket_role_id")
        profile["max_open_tickets_by_member"] = self._dash_int(
            form_data,
            "max_open_tickets_by_member",
            default=5,
            minimum=0,
            maximum=50,
        )
        profile["next_profile_ticket_id"] = self._dash_int(
            form_data,
            "next_profile_ticket_id",
            minimum=1,
            optional=True,
        )
        profile["channel_name"] = self._validate_channel_name_template(
            self._dash_value(form_data, "channel_name", "ticket-{id}-{owner_name}")
        )
        profile["panel_title"] = self._clean_modal_text(self._dash_value(form_data, "panel_title"), 256) or "Need Help?"
        profile["panel_message"] = (
            self._clean_modal_text(self._dash_value(form_data, "panel_message"), 2048)
            or "Open a ticket and staff will help you as soon as possible."
        )
        profile["welcome_message"] = self._clean_modal_text(self._dash_value(form_data, "welcome_message"), 1900)
        profile["custom_message"] = self._clean_modal_text(self._dash_value(form_data, "custom_message"), 1900)
        profile["transcripts"] = self._dash_bool(form_data, "transcripts")
        profile["dm_transcript"] = self._dash_bool(form_data, "dm_transcript")
        profile["owner_can_close"] = self._dash_bool(form_data, "owner_can_close")
        profile["owner_can_reopen"] = self._dash_bool(form_data, "owner_can_reopen")
        profile["owner_can_add_members"] = self._dash_bool(form_data, "owner_can_add_members")
        profile["owner_can_remove_members"] = self._dash_bool(form_data, "owner_can_remove_members")
        profile["close_on_leave"] = self._dash_bool(form_data, "close_on_leave")
        profile["close_request_timeout_minutes"] = self._dash_int(
            form_data,
            "close_request_timeout_minutes",
            default=self.DEFAULT_CLOSE_REQUEST_TIMEOUT_MINUTES,
            minimum=self.MIN_CLOSE_REQUEST_TIMEOUT_MINUTES,
            maximum=self.MAX_CLOSE_REQUEST_TIMEOUT_MINUTES,
        )

        auto_delete = self._dash_value(form_data, "auto_delete_on_close_hours").strip().lower()
        if auto_delete in {"", "off", "none", "disabled", "disable"}:
            profile["auto_delete_on_close_hours"] = None
        else:
            profile["auto_delete_on_close_hours"] = self._dash_int(
                form_data,
                "auto_delete_on_close_hours",
                default=0,
                minimum=0,
                maximum=720,
            )

        for field in (
            "support_role_ids",
            "speak_role_ids",
            "view_role_ids",
            "ping_role_ids",
            "whitelist_role_ids",
            "blacklist_role_ids",
        ):
            profile[field] = sorted({int(role_id) for role_id in self._dash_values(form_data, field)})

        defaults = self._default_profile()["control_emojis"]
        configured = {}
        for action, default_emoji in defaults.items():
            value = self._dash_value(form_data, f"emoji_{action}").strip()
            if not value or value.lower() in {"default", "reset"} or value == default_emoji:
                continue
            try:
                parsed_emoji = discord.PartialEmoji.from_str(value)
            except (TypeError, ValueError) as exc:
                raise commands.BadArgument(f"`{action}` emoji is not valid.") from exc
            if parsed_emoji.id is not None and self.bot.get_emoji(parsed_emoji.id) is None:
                raise commands.BadArgument(f"I cannot access the custom emoji for `{action}`.")
            if len(value) > 100:
                raise commands.BadArgument(f"`{action}` emoji is too long.")
            configured[action] = value
        profile["control_emojis"] = configured

        await self._set_profile(guild, profile_name, profile)
        await self._dashboard_refresh_profile_panel(guild, profile_name, profile)

        tickets = await self.config.guild(guild).tickets()
        if configured != old_emojis:
            for record in tickets.values():
                if str(record.get("profile") or "main") == profile_name:
                    await self._update_ticket_message(guild, record, profile)
        for record in tickets.values():
            if (
                str(record.get("profile") or "main") == profile_name
                and record.get("status") == "closed"
            ):
                self._schedule_ticket_auto_delete(guild.id, record, profile)
        return profile_name

    async def _dashboard_save_modal(self, guild: discord.Guild, form_data: typing.Any) -> str:
        profile_name = self._clean_name(self._dash_value(form_data, "selected_profile", "main"))
        profile = await self._ensure_profile(guild, profile_name)
        fields = []
        for index in range(5):
            if not self._dash_bool(form_data, f"modal_{index}_enabled"):
                continue
            label = self._clean_modal_text(self._dash_value(form_data, f"modal_{index}_label"), 45)
            if not label:
                raise commands.BadArgument("Enabled modal questions need a label.")
            question_type = self._modal_type_name(self._dash_value(form_data, f"modal_{index}_type")) or "text"
            choices = self._clean_modal_choices(self._dash_value(form_data, f"modal_{index}_choices"))
            if question_type == "choice" and len(choices) < 2:
                raise commands.BadArgument("Choice questions need at least two choices.")
            style_name = self._dash_value(form_data, f"modal_{index}_style")
            style = (
                discord.TextStyle.short.value
                if style_name == "short"
                else discord.TextStyle.paragraph.value
            )
            min_length = self._dash_int(
                form_data,
                f"modal_{index}_min_length",
                minimum=0,
                maximum=4000,
                optional=True,
            )
            max_length = self._dash_int(
                form_data,
                f"modal_{index}_max_length",
                minimum=1,
                maximum=4000,
                optional=True,
            )
            fields.append(
                {
                    "label": label,
                    "type": question_type,
                    "style": style,
                    "required": self._dash_bool(form_data, f"modal_{index}_required"),
                    "default": self._clean_modal_text(
                        self._dash_value(form_data, f"modal_{index}_default"),
                        4000,
                    ),
                    "placeholder": self._clean_modal_text(
                        self._dash_value(form_data, f"modal_{index}_placeholder"),
                        100,
                    ),
                    "min_length": min_length,
                    "max_length": max_length,
                    "choices": choices,
                }
            )
        profile["creating_modal"] = self._sanitize_modal_fields(fields)
        await self._set_profile(guild, profile_name, profile)
        return profile_name

    async def _dashboard_add_modal_question(
        self,
        guild: discord.Guild,
        form_data: typing.Any,
    ) -> str:
        profile_name = self._clean_name(self._dash_value(form_data, "selected_profile", "main"))
        profile = await self._ensure_profile(guild, profile_name)
        fields = list(profile.get("creating_modal") or [])
        if len(fields) >= 5:
            raise commands.BadArgument("A Discord modal can only have 5 questions.")

        label = self._clean_modal_text(self._dash_value(form_data, "add_modal_label"), 45)
        if not label:
            raise commands.BadArgument("New modal questions need a label.")

        question_type = self._modal_type_name(self._dash_value(form_data, "add_modal_type")) or "text"
        choices = self._clean_modal_choices(self._dash_value(form_data, "add_modal_choices"))
        if question_type == "choice" and len(choices) < 2:
            raise commands.BadArgument("Choice questions need at least two choices.")

        style_name = self._dash_value(form_data, "add_modal_style")
        style = (
            discord.TextStyle.short.value
            if style_name == "short"
            else discord.TextStyle.paragraph.value
        )
        fields.append(
            {
                "label": label,
                "type": question_type,
                "style": style,
                "required": self._dash_bool(form_data, "add_modal_required"),
                "default": self._clean_modal_text(
                    self._dash_value(form_data, "add_modal_default"),
                    4000,
                ),
                "placeholder": self._clean_modal_text(
                    self._dash_value(form_data, "add_modal_placeholder"),
                    100,
                ),
                "min_length": None,
                "max_length": None,
                "choices": choices,
            }
        )
        profile["creating_modal"] = self._sanitize_modal_fields(fields)
        await self._set_profile(guild, profile_name, profile)
        return profile_name

    async def _dashboard_remove_modal_question(
        self,
        guild: discord.Guild,
        form_data: typing.Any,
    ) -> typing.Tuple[str, str]:
        profile_name = self._clean_name(self._dash_value(form_data, "selected_profile", "main"))
        profile = await self._ensure_profile(guild, profile_name)
        fields = list(profile.get("creating_modal") or [])
        if not fields:
            raise commands.BadArgument(f"`{profile_name}` has no modal questions.")

        index = self._dash_int(
            form_data,
            "remove_modal_index",
            minimum=1,
            maximum=len(fields),
        )
        removed = fields.pop(index - 1)
        removed_label = self._clean_modal_text(removed.get("label"), 45) or f"Question {index}"
        profile["creating_modal"] = self._sanitize_modal_fields(fields)
        await self._set_profile(guild, profile_name, profile)
        return profile_name, removed_label

    async def _dashboard_post_panel(
        self,
        guild: discord.Guild,
        form_data: typing.Any,
    ) -> typing.Tuple[str, discord.Message]:
        profile_name = self._clean_name(self._dash_value(form_data, "selected_profile", "main"))
        profile = await self._ensure_profile(guild, profile_name)
        channel_id = self._dash_optional_id(form_data, "post_panel_channel_id")
        channel = guild.get_channel(channel_id) if channel_id else None
        if not isinstance(channel, discord.TextChannel):
            raise commands.BadArgument("Choose a text channel for the panel.")
        style = self._parse_panel_style(self._dash_value(form_data, "post_panel_style", profile.get("panel_style")))
        message = await self._post_panel(guild, profile_name, profile, channel, style)
        await self.config.guild(guild).enabled.set(True)
        return profile_name, message

    async def _dashboard_attach_panel(
        self,
        guild: discord.Guild,
        form_data: typing.Any,
    ) -> typing.Tuple[str, discord.Message]:
        profile_name = self._clean_name(self._dash_value(form_data, "selected_profile", "main"))
        profile = await self._ensure_profile(guild, profile_name)
        message = await self._dashboard_fetch_message(
            guild,
            self._dash_value(form_data, "attach_panel_channel_id"),
            self._dash_value(form_data, "attach_panel_message_id"),
        )
        style = self._parse_panel_style(self._dash_value(form_data, "attach_panel_style", profile.get("panel_style")))
        message = await self._attach_panel(guild, profile_name, profile, message, style)
        await self.config.guild(guild).enabled.set(True)
        return profile_name, message

    async def _dashboard_clear_panel(self, guild: discord.Guild, form_data: typing.Any) -> None:
        message = await self._dashboard_fetch_message(
            guild,
            self._dash_value(form_data, "clear_panel_channel_id"),
            self._dash_value(form_data, "clear_panel_message_id"),
        )
        tracked = False
        multi_panels = await self.config.guild(guild).multi_panels()
        if str(message.id) in multi_panels:
            await self._clear_multi_panel(guild, message)
            tracked = True
        profiles = await self._get_profiles(guild)
        for profile_name, profile in profiles.items():
            if str(profile.get("panel_message_id")) == str(message.id):
                profile["panel_message_id"] = None
                profile["panel_channel_id"] = None
                await self._set_profile(guild, profile_name, profile)
                tracked = True
        if not tracked:
            raise commands.BadArgument("That message is not tracked as a TicketHub panel.")
        try:
            await message.edit(view=None)
        except discord.HTTPException as exc:
            raise commands.CommandError("Panel tracking was cleared, but I could not edit the message.") from exc

    async def _dashboard_save_multi_panel(
        self,
        guild: discord.Guild,
        form_data: typing.Any,
    ) -> discord.Message:
        message = await self._dashboard_fetch_message(
            guild,
            self._dash_value(form_data, "multi_panel_channel_id"),
            self._dash_value(form_data, "multi_panel_message_id"),
        )
        if guild.me is None or message.author.id != guild.me.id:
            raise commands.BadArgument("I can only manage multi-panels on messages sent by this bot.")

        profiles = await self._get_profiles(guild)
        options = []
        for raw_line in self._dash_value(form_data, "multi_panel_options").splitlines():
            line = raw_line.strip()
            if not line:
                continue
            parts = [part.strip() for part in line.split("|")]
            while len(parts) < 4:
                parts.append("")
            profile_name = self._clean_name(parts[0])
            if profile_name not in profiles:
                raise commands.BadArgument(f"No profile named `{profile_name}` exists.")
            emoji = parts[1] or None
            label = parts[2][:80]
            description = parts[3][:100] or None
            if not label:
                raise commands.BadArgument("Every multi-panel option needs a label.")
            options.append(
                {
                    "profile": profile_name,
                    "emoji": emoji,
                    "label": label,
                    "description": description,
                }
            )
            if len(options) >= 25:
                break
        if not options:
            raise commands.BadArgument("Provide at least one multi-panel option.")

        record = {
            "channel_id": message.channel.id,
            "message_id": message.id,
            "style": self._parse_panel_style(self._dash_value(form_data, "multi_panel_style", "button")),
            "placeholder": (
                self._clean_modal_text(
                    self._dash_value(form_data, "multi_panel_placeholder"),
                    100,
                )
                or "Choose a ticket type..."
            ),
            "options": options,
        }
        await self._save_multi_panel(guild, message, record)
        for option in options:
            profile = profiles[option["profile"]]
            profile["panel_channel_id"] = message.channel.id
            await self._set_profile(guild, option["profile"], profile)
        await self.config.guild(guild).enabled.set(True)
        return message

    async def _dashboard_clear_multi_panel(self, guild: discord.Guild, form_data: typing.Any) -> None:
        message = await self._dashboard_fetch_message(
            guild,
            self._dash_value(form_data, "multi_panel_channel_id"),
            self._dash_value(form_data, "multi_panel_message_id"),
        )
        await self._clear_multi_panel(guild, message)

    async def _dashboard_clear_aaa3a_panels(self, guild: discord.Guild) -> None:
        panels = await self.config.guild(guild).aaa3a_panels()
        for raw_record in panels.values():
            record = self._sanitize_aaa3a_panel_record(raw_record)
            if record is None:
                continue
            view = self._aaa3a_panel_views.pop(int(record["message_id"]), None)
            if view is not None:
                view.stop()
        await self.config.guild(guild).aaa3a_panels.set({})

    async def _dashboard_ticket_action(
        self,
        guild: discord.Guild,
        member: discord.Member,
        form_data: typing.Any,
    ) -> str:
        ticket_id = self._dash_int(form_data, "ticket_id", minimum=1)
        action = self._dash_value(form_data, "ticket_action")
        record = await self._get_ticket_record_by_id(guild, ticket_id)
        reason = self._dash_value(form_data, "ticket_reason").strip() or None

        if action == "claim":
            await self._claim_ticket(guild, record, member)
        elif action == "unclaim":
            await self._unclaim_ticket(guild, record, member)
        elif action == "lock":
            await self._lock_ticket(guild, record, member)
        elif action == "unlock":
            await self._unlock_ticket(guild, record, member)
        elif action == "close":
            await self._close_ticket(guild, record, member, reason=reason)
        elif action == "reopen":
            await self._reopen_ticket(guild, record, member, reason=reason)
        elif action == "delete":
            await self._delete_ticket_channel(guild, record, member, reason=reason)
        elif action == "transcript":
            profile = await self._get_profile(guild, str(record.get("profile") or "main"))
            return await self._send_transcript_bundle(guild, record, profile, requested_by=member)
        elif action in {"add_member", "remove_member"}:
            target_id = self._dash_int(form_data, "ticket_member_id", minimum=1)
            target = guild.get_member(target_id)
            if target is None:
                raise commands.BadArgument("That member is not in this server.")
            if action == "add_member":
                note = await self._add_ticket_member(guild, record, member, target)
                return f"Added {target} to ticket #{ticket_id}.{note}"
            await self._remove_ticket_member(guild, record, member, target)
            return f"Removed {target} from ticket #{ticket_id}."
        else:
            raise commands.BadArgument("Choose a valid ticket action.")
        return f"Ticket #{ticket_id} {action.replace('_', ' ')} completed."

    async def _dashboard_create_ticket(self, guild: discord.Guild, form_data: typing.Any) -> str:
        owner_id = self._dash_int(form_data, "create_ticket_owner_id", minimum=1)
        owner = guild.get_member(owner_id)
        if owner is None:
            raise commands.BadArgument("The ticket owner must be a member of this server.")
        profile_name = self._clean_name(self._dash_value(form_data, "create_ticket_profile", "main"))
        reason = self._dash_value(form_data, "create_ticket_reason").strip() or "Created from Dashboard."
        record, channel = await self._create_ticket(guild, owner, profile_name, reason=reason)
        return f"Ticket #{record['id']} created for {owner}: {channel.mention}"

    async def _dashboard_recover_ticket(
        self,
        guild: discord.Guild,
        member: discord.Member,
        form_data: typing.Any,
    ) -> typing.Dict[str, typing.Any]:
        channel_id = self._dash_int(form_data, "recover_channel_id", minimum=1)
        channel = guild.get_channel(channel_id)
        if not isinstance(channel, (discord.TextChannel, discord.Thread)):
            raise commands.BadArgument("Choose a ticket text channel or thread.")
        return await self._recover_ticket_record(guild, channel, member)

    async def _dashboard_fetch_message(
        self,
        guild: discord.Guild,
        channel_id: typing.Any,
        message_id: typing.Any,
    ) -> discord.Message:
        try:
            clean_channel_id = int(str(channel_id).strip())
            clean_message_id = int(str(message_id).strip())
        except (TypeError, ValueError) as exc:
            raise commands.BadArgument("Provide both channel ID and message ID.") from exc
        channel = guild.get_channel(clean_channel_id)
        if not isinstance(channel, (discord.TextChannel, discord.Thread)):
            raise commands.BadArgument("The channel ID must resolve to a text channel or thread.")
        try:
            return await channel.fetch_message(clean_message_id)
        except discord.HTTPException as exc:
            raise commands.CommandError("I could not fetch that message.") from exc

    async def _dashboard_refresh_profile_panel(
        self,
        guild: discord.Guild,
        profile_name: str,
        profile: typing.Dict[str, typing.Any],
    ) -> None:
        if not profile.get("panel_channel_id") or not profile.get("panel_message_id"):
            return
        try:
            message = await self._dashboard_fetch_message(
                guild,
                profile.get("panel_channel_id"),
                profile.get("panel_message_id"),
            )
            await message.edit(
                embed=self._panel_embed(guild, profile_name, profile),
                view=self._panel_view_for_style(profile.get("panel_style")),
            )
        except (commands.CommandError, discord.HTTPException):
            log.debug("Could not refresh TicketHub panel for %s in %s.", profile_name, guild.id, exc_info=True)

    async def _dashboard_source(
        self,
        guild: discord.Guild,
        selected_profile: str,
        kwargs: typing.Dict[str, typing.Any],
    ) -> str:
        enabled = await self.config.guild(guild).enabled()
        next_ticket_id = await self.config.guild(guild).next_ticket_id()
        profiles = await self._get_profiles(guild)
        tickets = await self.config.guild(guild).tickets()
        multi_panels = await self.config.guild(guild).multi_panels()
        aaa3a_panels = await self.config.guild(guild).aaa3a_panels()
        if selected_profile not in profiles:
            selected_profile = "main" if "main" in profiles else next(iter(profiles), "main")
        profile = profiles[selected_profile]
        csrf = self._dash_csrf(kwargs)

        open_count = sum(1 for record in tickets.values() if record.get("status") == "open")
        closed_count = sum(1 for record in tickets.values() if record.get("status") == "closed")
        claimed_count = sum(
            1
            for record in tickets.values()
            if record.get("status") == "open" and record.get("claimed_by")
        )
        active_tab = self._dashboard_active_tab(
            kwargs,
            {
                "save_global": "setup",
                "select_profile": "setup",
                "create_profile": "setup",
                "delete_profile": "setup",
                "save_profile": "setup",
                "save_modal": "modal",
                "add_modal_question": "modal",
                "remove_modal_question": "modal",
                "default_reason_modal": "modal",
                "clear_modal": "modal",
                "post_panel": "panels",
                "attach_panel": "panels",
                "clear_panel": "panels",
                "save_multi_panel": "panels",
                "clear_multi_panel": "panels",
                "ticket_action": "tickets",
                "create_ticket": "tickets",
                "recover_ticket": "tickets",
                "import_aaa3a_panels": "imports",
                "clear_aaa3a_panels": "imports",
            },
            "tickets",
        )

        return f"""
        <style>
            .th-wrap {{ max-width: 1180px; margin: 0 auto; color: #e5e7eb; }}
            .th-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(260px, 1fr)); gap: 16px; }}
            .th-card {{ background: #1f2937; border: 1px solid #374151; border-radius: 8px; padding: 16px; margin-bottom: 16px; }}
            .th-card h2, .th-card h3 {{ margin: 0 0 12px 0; color: #f9fafb; }}
            .th-muted {{ color: #9ca3af; }}
            .th-stat {{ font-size: 1.5rem; font-weight: 700; color: #f9fafb; }}
            .th-row {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 12px; margin-bottom: 12px; }}
            .th-field label {{ display: block; font-weight: 600; margin-bottom: 4px; color: #d1d5db; }}
            .th-field input, .th-field select, .th-field textarea {{
                width: 100%; box-sizing: border-box; border: 1px solid #4b5563; border-radius: 6px;
                background: #111827; color: #f9fafb; padding: 8px; min-height: 38px;
            }}
            .th-field textarea {{ min-height: 82px; font-family: ui-monospace, SFMono-Regular, Menlo, monospace; }}
            .th-check {{ display: flex; align-items: center; gap: 8px; margin: 6px 0; color: #d1d5db; }}
            .th-check input {{ width: auto; }}
            .th-btn {{ background: #2563eb; color: white; border: 0; border-radius: 6px; padding: 9px 14px; cursor: pointer; font-weight: 700; }}
            .th-btn.secondary {{ background: #4b5563; }}
            .th-btn.danger {{ background: #dc2626; }}
            .dash-tabs {{ display: flex; gap: 4px; overflow-x: auto; position: sticky; top: 0; z-index: 10; margin: 0 0 16px; padding: 5px; background: #111827; border: 1px solid #374151; border-radius: 8px; }}
            .dash-tab {{ flex: 0 0 auto; border: 0; border-radius: 6px; padding: 9px 13px; background: transparent; color: #9ca3af; cursor: pointer; font-weight: 700; white-space: nowrap; }}
            .dash-tab:hover {{ background: #1f2937; color: #f9fafb; }} .dash-tab.active {{ background: #2563eb; color: white; }}
            .dash-panel {{ display: none; }} .dash-panel.active {{ display: block; }}
            .th-table {{ width: 100%; border-collapse: collapse; font-size: 0.92rem; }}
            .th-table th, .th-table td {{ border-bottom: 1px solid #374151; padding: 8px; text-align: left; vertical-align: top; }}
            .th-table th {{ color: #d1d5db; }}
            .th-inline {{ display: inline; }}
        </style>
        <div class="th-wrap" data-dashboard-tabs="1">
            <div class="th-card">
                <h2>TicketHub Dashboard</h2>
                <div class="th-grid">
                    <div><div class="th-muted">Profiles</div><div class="th-stat">{len(profiles)}</div></div>
                    <div><div class="th-muted">Open tickets</div><div class="th-stat">{open_count}</div></div>
                    <div><div class="th-muted">Claimed tickets</div><div class="th-stat">{claimed_count}</div></div>
                    <div><div class="th-muted">Closed tickets</div><div class="th-stat">{closed_count}</div></div>
                </div>
            </div>
            <div class="dash-tabs" role="tablist" aria-label="TicketHub sections">
                {self._dashboard_tab_button("tickets", "Tickets", active_tab)}
                {self._dashboard_tab_button("setup", "Profile Setup", active_tab)}
                {self._dashboard_tab_button("modal", "Modal", active_tab)}
                {self._dashboard_tab_button("panels", "Panels", active_tab)}
                {self._dashboard_tab_button("imports", "AAA3A Imports", active_tab)}
            </div>
            <section class="dash-panel{' active' if active_tab == 'tickets' else ''}" data-tab-panel="tickets">{self._dashboard_tickets_section(guild, profiles, tickets, selected_profile, csrf)}</section>
            <section class="dash-panel{' active' if active_tab == 'setup' else ''}" data-tab-panel="setup">{self._dashboard_global_section(enabled, next_ticket_id, csrf)}{self._dashboard_profile_selector(profiles, selected_profile, csrf)}{self._dashboard_profile_section(guild, selected_profile, profile, csrf)}</section>
            <section class="dash-panel{' active' if active_tab == 'modal' else ''}" data-tab-panel="modal">{self._dashboard_modal_section(selected_profile, profile, csrf)}</section>
            <section class="dash-panel{' active' if active_tab == 'panels' else ''}" data-tab-panel="panels">{self._dashboard_panels_section(guild, selected_profile, profile, multi_panels, csrf)}</section>
            <section class="dash-panel{' active' if active_tab == 'imports' else ''}" data-tab-panel="imports">{self._dashboard_imports_section(aaa3a_panels, csrf)}</section>
            {self._dashboard_tabs_script()}
        </div>
        """

    def _dashboard_global_section(self, enabled: bool, next_ticket_id: int, csrf: str) -> str:
        return f"""
        <div id="global" class="th-card">
            <h3>Global</h3>
            <form method="POST">
                {csrf}
                <input type="hidden" name="action" value="save_global">
                <label class="th-check"><input type="checkbox" name="enabled" value="1" {self._checked(enabled)}> Enabled</label>
                <div class="th-row">
                    {self._input("next_ticket_id", "Next Global Ticket ID", next_ticket_id, "number", min_value=1)}
                </div>
                <button class="th-btn" type="submit">Save Global Settings</button>
            </form>
        </div>
        """

    def _dashboard_profile_selector(
        self,
        profiles: typing.Dict[str, typing.Dict[str, typing.Any]],
        selected_profile: str,
        csrf: str,
    ) -> str:
        options = "".join(
            f'<option value="{self._h(name)}" {self._selected(name, selected_profile)}>{self._h(name)}</option>'
            for name in sorted(profiles)
        )
        return f"""
        <div class="th-card">
            <h3>Profiles</h3>
            <div class="th-grid">
                <form method="POST">
                    {csrf}
                    <input type="hidden" name="action" value="select_profile">
                    <div class="th-field">
                        <label>Selected Profile</label>
                        <select name="selected_profile" onchange="this.form.submit()">{options}</select>
                    </div>
                </form>
                <form method="POST">
                    {csrf}
                    <input type="hidden" name="action" value="create_profile">
                    <div class="th-row">
                        {self._input("new_profile_name", "New Profile Name", "")}
                        <div class="th-field"><label>Clone From</label><select name="clone_profile"><option value="">Default</option>{options}</select></div>
                    </div>
                    <button class="th-btn" type="submit">Create Profile</button>
                </form>
                <form method="POST">
                    {csrf}
                    <input type="hidden" name="action" value="delete_profile">
                    <input type="hidden" name="selected_profile" value="{self._h(selected_profile)}">
                    <button class="th-btn danger" type="submit">Delete Selected Profile</button>
                </form>
            </div>
        </div>
        """

    def _dashboard_profile_section(
        self,
        guild: discord.Guild,
        profile_name: str,
        profile: typing.Dict[str, typing.Any],
        csrf: str,
    ) -> str:
        role_fields = "".join(
            self._multi_role_select(
                guild,
                field,
                label,
                profile.get(field) or [],
            )
            for field, label in (
                ("support_role_ids", "Support Roles"),
                ("speak_role_ids", "Speak Roles"),
                ("view_role_ids", "View Roles"),
                ("ping_role_ids", "Ping Roles"),
                ("whitelist_role_ids", "Whitelist Roles"),
                ("blacklist_role_ids", "Blacklist Roles"),
            )
        )
        emoji_fields = "".join(
            self._input(
                f"emoji_{action}",
                f"{action.title()} Emoji",
                (profile.get("control_emojis") or {}).get(action) or default,
            )
            for action, default in self._default_profile()["control_emojis"].items()
        )
        return f"""
        <div id="profile" class="th-card">
            <h3>Profile: {self._h(profile_name)}</h3>
            <form method="POST">
                {csrf}
                <input type="hidden" name="action" value="save_profile">
                <input type="hidden" name="selected_profile" value="{self._h(profile_name)}">
                <div class="th-grid">
                    <div>
                        <label class="th-check"><input type="checkbox" name="profile_enabled" value="1" {self._checked(profile.get("enabled"))}> Profile Enabled</label>
                        <label class="th-check"><input type="checkbox" name="transcripts" value="1" {self._checked(profile.get("transcripts"))}> Transcripts on Delete</label>
                        <label class="th-check"><input type="checkbox" name="dm_transcript" value="1" {self._checked(profile.get("dm_transcript"))}> DM Transcripts</label>
                        <label class="th-check"><input type="checkbox" name="close_on_leave" value="1" {self._checked(profile.get("close_on_leave"))}> Close on Leave</label>
                    </div>
                    <div>
                        <label class="th-check"><input type="checkbox" name="owner_can_close" value="1" {self._checked(profile.get("owner_can_close"))}> Owner Can Close</label>
                        <label class="th-check"><input type="checkbox" name="owner_can_reopen" value="1" {self._checked(profile.get("owner_can_reopen"))}> Owner Can Reopen</label>
                        <label class="th-check"><input type="checkbox" name="owner_can_add_members" value="1" {self._checked(profile.get("owner_can_add_members"))}> Owner Can Add Members</label>
                        <label class="th-check"><input type="checkbox" name="owner_can_remove_members" value="1" {self._checked(profile.get("owner_can_remove_members"))}> Owner Can Remove Members</label>
                    </div>
                </div>
                <div class="th-row">
                    <div class="th-field"><label>Panel Style</label><select name="panel_style">{self._option("button", "Button", profile.get("panel_style"))}{self._option("dropdown", "Dropdown", profile.get("panel_style"))}</select></div>
                    <div class="th-field"><label>Ticket Mode</label><select name="ticket_mode">{self._option("channel", "Channel", profile.get("ticket_mode"))}{self._option("thread", "Thread", profile.get("ticket_mode"))}</select></div>
                    {self._input("max_open_tickets_by_member", "Max Open Per Member", profile.get("max_open_tickets_by_member", 5), "number", min_value=0, max_value=50)}
                    {self._input("close_request_timeout_minutes", "Close Timeout Minutes", self._close_request_timeout_minutes(profile), "number", min_value=self.MIN_CLOSE_REQUEST_TIMEOUT_MINUTES, max_value=self.MAX_CLOSE_REQUEST_TIMEOUT_MINUTES)}
                    {self._input("auto_delete_on_close_hours", "Auto-Delete Hours", "" if profile.get("auto_delete_on_close_hours") is None else profile.get("auto_delete_on_close_hours"), "text")}
                    {self._input("next_profile_ticket_id", "Next Profile Ticket ID", "" if profile.get("next_profile_ticket_id") is None else profile.get("next_profile_ticket_id"), "number", min_value=1)}
                </div>
                <div class="th-row">
                    {self._input("channel_name", "Channel Name Template", profile.get("channel_name") or "ticket-{id}-{owner_name}")}
                    {self._input("panel_message_id", "Tracked Panel Message ID", profile.get("panel_message_id") or "")}
                </div>
                <div class="th-row">
                    {self._channel_select(guild, "panel_channel_id", "Panel Channel", profile.get("panel_channel_id"))}
                    {self._category_select(guild, "ticket_category_id", "Open Category", profile.get("ticket_category_id"))}
                    {self._category_select(guild, "closed_category_id", "Closed Category", profile.get("closed_category_id"))}
                    {self._channel_select(guild, "thread_parent_channel_id", "Thread Parent", profile.get("thread_parent_channel_id"))}
                    {self._channel_select(guild, "log_channel_id", "Log Channel", profile.get("log_channel_id"))}
                    {self._channel_select(guild, "transcript_channel_id", "Transcript Channel", profile.get("transcript_channel_id"))}
                    {self._role_select(guild, "ticket_role_id", "Ticket Role", profile.get("ticket_role_id"))}
                </div>
                <div class="th-row">
                    {self._textarea("panel_title", "Panel Title", profile.get("panel_title") or "Need Help?", rows=2)}
                    {self._textarea("panel_message", "Panel Message", profile.get("panel_message") or "", rows=3)}
                    {self._textarea("welcome_message", "Welcome Message", profile.get("welcome_message") or "", rows=3)}
                    {self._textarea("custom_message", "Custom Message", profile.get("custom_message") or "", rows=3)}
                </div>
                <h3>Roles</h3>
                <div class="th-row">{role_fields}</div>
                <h3>Control Emojis</h3>
                <div class="th-row">{emoji_fields}</div>
                <button class="th-btn" type="submit">Save Profile</button>
            </form>
        </div>
        """

    def _dashboard_modal_section(
        self,
        profile_name: str,
        profile: typing.Dict[str, typing.Any],
        csrf: str,
    ) -> str:
        fields = list(profile.get("creating_modal") or [])
        rows = []
        for index in range(5):
            field = fields[index] if index < len(fields) else {}
            field_type = field.get("type") or "text"
            style = "short" if int(field.get("style") or 2) == discord.TextStyle.short.value else "paragraph"
            rows.append(
                f"""
                <div class="th-card">
                    <label class="th-check"><input type="checkbox" name="modal_{index}_enabled" value="1" {self._checked(index < len(fields))}> Question {index + 1}</label>
                    <div class="th-row">
                        {self._input(f"modal_{index}_label", "Label", field.get("label") or "")}
                        <div class="th-field"><label>Type</label><select name="modal_{index}_type">{self._option("text", "Text", field_type)}{self._option("choice", "Choice", field_type)}{self._option("boolean", "Boolean", field_type)}</select></div>
                        <div class="th-field"><label>Text Style</label><select name="modal_{index}_style">{self._option("paragraph", "Paragraph", style)}{self._option("short", "Short", style)}</select></div>
                        <label class="th-check"><input type="checkbox" name="modal_{index}_required" value="1" {self._checked(field.get("required", True))}> Required</label>
                    </div>
                    <div class="th-row">
                        {self._input(f"modal_{index}_placeholder", "Placeholder", field.get("placeholder") or "")}
                        {self._input(f"modal_{index}_default", "Default", field.get("default") or "")}
                        {self._input(f"modal_{index}_min_length", "Min Length", "" if field.get("min_length") is None else field.get("min_length"), "number", min_value=0, max_value=4000)}
                        {self._input(f"modal_{index}_max_length", "Max Length", "" if field.get("max_length") is None else field.get("max_length"), "number", min_value=1, max_value=4000)}
                    </div>
                    {self._input(f"modal_{index}_choices", "Choices", ", ".join(field.get("choices") or []))}
                </div>
                """
            )
        remove_options = "".join(
            f'<option value="{index}">{index}. {self._h(field.get("label") or "Question")}</option>'
            for index, field in enumerate(fields, start=1)
        )
        remove_form = (
            f"""
            <form method="POST">
                {csrf}
                <input type="hidden" name="action" value="remove_modal_question">
                <input type="hidden" name="selected_profile" value="{self._h(profile_name)}">
                <div class="th-row">
                    <div class="th-field">
                        <label>Remove Question</label>
                        <select name="remove_modal_index">{remove_options}</select>
                    </div>
                </div>
                <button class="th-btn danger" type="submit">Remove Question</button>
            </form>
            """
            if fields
            else '<p class="th-muted">No modal questions are currently configured.</p>'
        )
        return f"""
        <div id="modal" class="th-card">
            <h3>Modal Questions</h3>
            <form method="POST">
                {csrf}
                <input type="hidden" name="action" value="save_modal">
                <input type="hidden" name="selected_profile" value="{self._h(profile_name)}">
                {''.join(rows)}
                <button class="th-btn" type="submit">Save Modal</button>
            </form>
            <div class="th-grid">
                <form method="POST">
                    {csrf}
                    <input type="hidden" name="action" value="add_modal_question">
                    <input type="hidden" name="selected_profile" value="{self._h(profile_name)}">
                    <div class="th-row">
                        {self._input("add_modal_label", "New Question Label", "")}
                        <div class="th-field"><label>Type</label><select name="add_modal_type">{self._option("text", "Text", "text")}{self._option("choice", "Choice", "text")}{self._option("boolean", "Boolean", "text")}</select></div>
                        <div class="th-field"><label>Text Style</label><select name="add_modal_style">{self._option("paragraph", "Paragraph", "paragraph")}{self._option("short", "Short", "paragraph")}</select></div>
                        <label class="th-check"><input type="checkbox" name="add_modal_required" value="1" checked> Required</label>
                    </div>
                    <div class="th-row">
                        {self._input("add_modal_placeholder", "Placeholder", "")}
                        {self._input("add_modal_default", "Default", "")}
                    </div>
                    {self._input("add_modal_choices", "Choices for Choice Type", "")}
                    <button class="th-btn secondary" type="submit">Add Question</button>
                </form>
                {remove_form}
            </div>
            <form class="th-inline" method="POST">{csrf}<input type="hidden" name="action" value="default_reason_modal"><input type="hidden" name="selected_profile" value="{self._h(profile_name)}"><button class="th-btn secondary" type="submit">Use Default Reason Modal</button></form>
            <form class="th-inline" method="POST">{csrf}<input type="hidden" name="action" value="clear_modal"><input type="hidden" name="selected_profile" value="{self._h(profile_name)}"><button class="th-btn danger" type="submit">Clear Modal</button></form>
        </div>
        """

    def _dashboard_panels_section(
        self,
        guild: discord.Guild,
        profile_name: str,
        profile: typing.Dict[str, typing.Any],
        multi_panels: typing.Dict[str, typing.Any],
        csrf: str,
    ) -> str:
        multi_rows = []
        for message_id, raw_record in multi_panels.items():
            try:
                record = self._sanitize_multi_panel_record(raw_record, message_id=int(message_id))
            except (TypeError, ValueError):
                record = None
            if record is None:
                continue
            option_text = ", ".join(f"{option['label']} ({option['profile']})" for option in record["options"])
            multi_rows.append(
                f"<tr><td>{self._h(record['message_id'])}</td><td>{self._h(record['channel_id'])}</td><td>{self._h(record['style'])}</td><td>{self._h(option_text)}</td></tr>"
            )
        multi_table = "".join(multi_rows) or '<tr><td colspan="4" class="th-muted">No multi-panels configured.</td></tr>'
        return f"""
        <div id="panels" class="th-card">
            <h3>Panels</h3>
            <div class="th-grid">
                <form method="POST">
                    {csrf}
                    <input type="hidden" name="action" value="post_panel">
                    <input type="hidden" name="selected_profile" value="{self._h(profile_name)}">
                    {self._channel_select(guild, "post_panel_channel_id", "Post Panel Channel", profile.get("panel_channel_id"))}
                    <div class="th-field"><label>Style</label><select name="post_panel_style">{self._option("button", "Button", profile.get("panel_style"))}{self._option("dropdown", "Dropdown", profile.get("panel_style"))}</select></div>
                    <button class="th-btn" type="submit">Post Panel</button>
                </form>
                <form method="POST">
                    {csrf}
                    <input type="hidden" name="action" value="attach_panel">
                    <input type="hidden" name="selected_profile" value="{self._h(profile_name)}">
                    {self._input("attach_panel_channel_id", "Channel ID", profile.get("panel_channel_id") or "")}
                    {self._input("attach_panel_message_id", "Message ID", profile.get("panel_message_id") or "")}
                    <div class="th-field"><label>Style</label><select name="attach_panel_style">{self._option("button", "Button", profile.get("panel_style"))}{self._option("dropdown", "Dropdown", profile.get("panel_style"))}</select></div>
                    <button class="th-btn" type="submit">Attach Panel</button>
                </form>
                <form method="POST">
                    {csrf}
                    <input type="hidden" name="action" value="clear_panel">
                    {self._input("clear_panel_channel_id", "Channel ID", profile.get("panel_channel_id") or "")}
                    {self._input("clear_panel_message_id", "Message ID", profile.get("panel_message_id") or "")}
                    <button class="th-btn danger" type="submit">Clear Panel</button>
                </form>
            </div>
            <h3>Multi-Panels</h3>
            <table class="th-table"><thead><tr><th>Message</th><th>Channel</th><th>Style</th><th>Options</th></tr></thead><tbody>{multi_table}</tbody></table>
            <form method="POST">
                {csrf}
                <input type="hidden" name="action" value="save_multi_panel">
                <div class="th-row">
                    {self._input("multi_panel_channel_id", "Multi-Panel Channel ID", "")}
                    {self._input("multi_panel_message_id", "Multi-Panel Message ID", "")}
                    <div class="th-field"><label>Style</label><select name="multi_panel_style">{self._option("button", "Button", "button")}{self._option("dropdown", "Dropdown", "button")}</select></div>
                    {self._input("multi_panel_placeholder", "Dropdown Placeholder", "Choose a ticket type...")}
                </div>
                {self._textarea("multi_panel_options", "Options: profile | emoji | label | description", "", rows=6)}
                <button class="th-btn" type="submit">Save Multi-Panel</button>
            </form>
            <form method="POST">
                {csrf}
                <input type="hidden" name="action" value="clear_multi_panel">
                <div class="th-row">
                    {self._input("multi_panel_channel_id", "Multi-Panel Channel ID", "")}
                    {self._input("multi_panel_message_id", "Multi-Panel Message ID", "")}
                </div>
                <button class="th-btn danger" type="submit">Clear Multi-Panel</button>
            </form>
        </div>
        """

    def _dashboard_tickets_section(
        self,
        guild: discord.Guild,
        profiles: typing.Dict[str, typing.Dict[str, typing.Any]],
        tickets: typing.Dict[str, typing.Dict[str, typing.Any]],
        selected_profile: str,
        csrf: str,
    ) -> str:
        rows = []
        for record in sorted(tickets.values(), key=lambda item: int(item.get("id") or 0), reverse=True)[:100]:
            channel_id = record.get("channel_id")
            channel = guild.get_channel(int(channel_id)) if channel_id else None
            channel_text = channel.mention if channel else self._h(channel_id or "missing")
            rows.append(
                "<tr>"
                f"<td>{self._h(record.get('id'))}</td>"
                f"<td>{self._h(record.get('profile') or 'main')}</td>"
                f"<td>{self._h(record.get('status') or 'open')}</td>"
                f"<td>{self._h(record.get('owner_id') or '')}</td>"
                f"<td>{self._h(record.get('claimed_by') or '')}</td>"
                f"<td>{'Yes' if record.get('locked') else 'No'}</td>"
                f"<td>{channel_text}</td>"
                "</tr>"
            )
        table = "".join(rows) or '<tr><td colspan="7" class="th-muted">No tickets tracked.</td></tr>'
        profile_options = "".join(
            f'<option value="{self._h(name)}" {self._selected(name, selected_profile)}>{self._h(name)}</option>'
            for name in sorted(profiles)
        )
        return f"""
        <div id="tickets" class="th-card">
            <h3>Tickets</h3>
            <table class="th-table"><thead><tr><th>ID</th><th>Profile</th><th>Status</th><th>Owner ID</th><th>Claimed By</th><th>Locked</th><th>Location</th></tr></thead><tbody>{table}</tbody></table>
            <div class="th-grid">
                <form method="POST">
                    {csrf}
                    <input type="hidden" name="action" value="ticket_action">
                    <div class="th-row">
                        {self._input("ticket_id", "Ticket ID", "", "number", min_value=1)}
                        <div class="th-field"><label>Action</label><select name="ticket_action">
                            <option value="claim">Claim</option><option value="unclaim">Unclaim</option>
                            <option value="lock">Lock</option><option value="unlock">Unlock</option>
                            <option value="close">Close Now</option><option value="reopen">Reopen</option>
                            <option value="transcript">Transcript</option><option value="delete">Delete</option>
                            <option value="add_member">Add Member</option><option value="remove_member">Remove Member</option>
                        </select></div>
                        {self._input("ticket_member_id", "Member ID", "")}
                    </div>
                    {self._textarea("ticket_reason", "Reason", "", rows=3)}
                    <button class="th-btn" type="submit">Run Ticket Action</button>
                </form>
                <form method="POST">
                    {csrf}
                    <input type="hidden" name="action" value="create_ticket">
                    <div class="th-row">
                        {self._input("create_ticket_owner_id", "Owner Member ID", "")}
                        <div class="th-field"><label>Profile</label><select name="create_ticket_profile">{profile_options}</select></div>
                    </div>
                    {self._textarea("create_ticket_reason", "Reason", "Created from Dashboard.", rows=3)}
                    <button class="th-btn" type="submit">Create Ticket</button>
                </form>
                <form method="POST">
                    {csrf}
                    <input type="hidden" name="action" value="recover_ticket">
                    {self._input("recover_channel_id", "Ticket Channel or Thread ID", "")}
                    <button class="th-btn secondary" type="submit">Recover Ticket</button>
                </form>
            </div>
        </div>
        """

    def _dashboard_imports_section(self, aaa3a_panels: typing.Dict[str, typing.Any], csrf: str) -> str:
        rows = []
        for key, raw_record in aaa3a_panels.items():
            record = self._sanitize_aaa3a_panel_record(raw_record, message_key=str(key))
            if record is None:
                continue
            option_count = len(record.get("buttons") or {}) + len(record.get("dropdown_options") or {})
            rows.append(
                f"<tr><td>{self._h(key)}</td><td>{self._h(record['channel_id'])}</td><td>{self._h(record['message_id'])}</td><td>{option_count}</td></tr>"
            )
        table = "".join(rows) or '<tr><td colspan="4" class="th-muted">No imported AAA3A panels tracked.</td></tr>'
        return f"""
        <div id="imports" class="th-card">
            <h3>AAA3A Imports</h3>
            <table class="th-table"><thead><tr><th>Key</th><th>Channel</th><th>Message</th><th>Options</th></tr></thead><tbody>{table}</tbody></table>
            <form class="th-inline" method="POST">{csrf}<input type="hidden" name="action" value="import_aaa3a_panels"><button class="th-btn" type="submit">Import/Refresh AAA3A Panels</button></form>
            <form class="th-inline" method="POST">{csrf}<input type="hidden" name="action" value="clear_aaa3a_panels"><button class="th-btn danger" type="submit">Clear Imported Panels</button></form>
        </div>
        """

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
                f'<option value="{channel.id}" {self._selected(channel.id, selected)}>#{self._h(channel.name)}</option>'
            )
        return f'<div class="th-field"><label>{self._h(label)}</label><select name="{self._h(name)}">{"".join(options)}</select></div>'

    def _category_select(
        self,
        guild: discord.Guild,
        name: str,
        label: str,
        selected: typing.Any,
    ) -> str:
        options = ['<option value="">None</option>']
        for category in sorted(guild.categories, key=lambda item: item.name.lower()):
            options.append(
                f'<option value="{category.id}" {self._selected(category.id, selected)}>{self._h(category.name)}</option>'
            )
        return f'<div class="th-field"><label>{self._h(label)}</label><select name="{self._h(name)}">{"".join(options)}</select></div>'

    def _role_select(
        self,
        guild: discord.Guild,
        name: str,
        label: str,
        selected: typing.Any,
    ) -> str:
        options = ['<option value="">None</option>']
        for role in sorted(
            [role for role in guild.roles if role.name != "@everyone"],
            key=lambda item: item.position,
            reverse=True,
        ):
            options.append(
                f'<option value="{role.id}" {self._selected(role.id, selected)}>{self._h(role.name)}</option>'
            )
        return f'<div class="th-field"><label>{self._h(label)}</label><select name="{self._h(name)}">{"".join(options)}</select></div>'

    def _multi_role_select(
        self,
        guild: discord.Guild,
        name: str,
        label: str,
        selected: typing.Sequence[int],
    ) -> str:
        selected_ids = {str(role_id) for role_id in selected}
        options = []
        for role in sorted(
            [role for role in guild.roles if role.name != "@everyone"],
            key=lambda item: item.position,
            reverse=True,
        ):
            options.append(
                f'<option value="{role.id}" {"selected" if str(role.id) in selected_ids else ""}>{self._h(role.name)}</option>'
            )
        return f'<div class="th-field"><label>{self._h(label)}</label><select name="{self._h(name)}" multiple size="8">{"".join(options)}</select></div>'

    def _input(
        self,
        name: str,
        label: str,
        value: typing.Any,
        input_type: str = "text",
        *,
        min_value: typing.Optional[int] = None,
        max_value: typing.Optional[int] = None,
    ) -> str:
        attrs = []
        if min_value is not None:
            attrs.append(f'min="{min_value}"')
        if max_value is not None:
            attrs.append(f'max="{max_value}"')
        return (
            f'<div class="th-field"><label>{self._h(label)}</label>'
            f'<input type="{self._h(input_type)}" name="{self._h(name)}" value="{self._h(value)}" {" ".join(attrs)}></div>'
        )

    def _textarea(self, name: str, label: str, value: typing.Any, *, rows: int = 4) -> str:
        return (
            f'<div class="th-field"><label>{self._h(label)}</label>'
            f'<textarea name="{self._h(name)}" rows="{rows}">{self._h(value)}</textarea></div>'
        )

    def _option(self, value: typing.Any, label: str, selected: typing.Any) -> str:
        return f'<option value="{self._h(value)}" {self._selected(value, selected)}>{self._h(label)}</option>'

    def _selected(self, value: typing.Any, selected: typing.Any) -> str:
        return "selected" if str(value) == str(selected) else ""

    def _checked(self, value: typing.Any) -> str:
        return "checked" if bool(value) else ""

    def _h(self, value: typing.Any) -> str:
        return html.escape("" if value is None else str(value), quote=True)
