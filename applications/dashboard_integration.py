"""Red-Web-Dashboard integration for Applications."""

from __future__ import annotations

import contextlib
import html
import logging
import typing

import discord
from redbot.core import commands

log = logging.getLogger("red.taakoscogs.applications.dashboard")


def dashboard_page(*args, **kwargs):
    """Dashboard page decorator compatible with Red-Web-Dashboard."""

    def decorator(func: typing.Callable):
        func.__dashboard_decorator_params__ = (args, kwargs)
        return func

    return decorator


class DashboardIntegration:
    """Dashboard integration mixin for Applications."""

    ROLE_FIELD_LABELS = (
        ("manager", "Manager Roles"),
        ("whitelist", "Whitelist Roles"),
        ("blacklist", "Blacklist Roles"),
        ("apply_add", "Apply Add Roles"),
        ("submit_add", "Submit Add Roles"),
        ("accept_add", "Accept Add Roles"),
        ("accept_remove", "Accept Remove Roles"),
        ("deny_add", "Deny Add Roles"),
        ("deny_remove", "Deny Remove Roles"),
    )

    @commands.Cog.listener()
    async def on_dashboard_cog_add(self, dashboard_cog: commands.Cog) -> None:
        """Register Applications as a Red-Web-Dashboard third party."""
        handler = dashboard_cog.rpc.third_parties_handler
        try:
            handler.add_third_party(self, overwrite=True)
        except TypeError:
            handler.add_third_party(self)

    @dashboard_page(
        name=None,
        description="Configure Applications forms, questions, panels, responses, and polls.",
        methods=("GET", "POST"),
    )
    async def dashboard_page(
        self,
        user: discord.User,
        guild: discord.Guild,
        **kwargs,
    ) -> dict[str, typing.Any]:
        """Render and process the Applications dashboard page."""
        member, can_manage = await self._dashboard_member_can_manage(user, guild)
        if not can_manage:
            return {
                "status": 1,
                "error_title": "Insufficient Permissions",
                "error_message": "You need Manage Server, Red admin, or bot owner access.",
            }

        notifications = []
        form_data = self._dashboard_form_data(kwargs)
        selected_application = self._dashboard_selected_application(form_data)

        if kwargs.get("method", "GET") == "POST":
            action = self._dash_value(form_data, "action")
            try:
                selected_application, messages = await self._dashboard_handle_action(
                    guild,
                    user,
                    member,
                    action,
                    form_data,
                    selected_application,
                )
            except commands.CommandError as error:
                notifications.append({"message": str(error), "category": "error"})
            except Exception as error:
                log.exception("Applications dashboard action failed.")
                notifications.append(
                    {
                        "message": f"Applications dashboard action failed: {error}",
                        "category": "error",
                    },
                )
            else:
                notifications.extend(messages)

        source = await self._dashboard_source(guild, selected_application, kwargs)
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

    def _dashboard_selected_application(self, form_data: typing.Any) -> str:
        return (
            self._dash_value(form_data, "selected_application")
            or self._dash_value(form_data, "application_key")
        ).strip()

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

    def _dash_values(self, form_data: typing.Any, key: str) -> list[str]:
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
            value = self._dash_value(form_data, key, "1").lower()
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
            raise commands.BadArgument(f"`{key}` must be a Discord ID.") from exc

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
        selected_application: str,
    ) -> tuple[str, list[dict[str, str]]]:
        messages: list[dict[str, str]] = []

        if action == "select_application":
            selected_application = self._dashboard_selected_application(form_data)

        elif action == "create_application":
            selected_application = await self._dashboard_create_application(
                guild,
                user.id,
                form_data,
            )
            messages.append(
                {
                    "message": f"Application `{selected_application}` created.",
                    "category": "success",
                },
            )

        elif action == "delete_application":
            target = self._dashboard_selected_application(form_data)
            deleted_name = await self._dashboard_delete_application(guild, target)
            selected_application = ""
            messages.append(
                {
                    "message": f"Application `{deleted_name}` deleted.",
                    "category": "success",
                },
            )

        elif action == "save_application":
            selected_application = await self._dashboard_save_application(
                guild,
                form_data,
            )
            messages.append(
                {
                    "message": f"Application `{selected_application}` saved.",
                    "category": "success",
                },
            )

        elif action == "add_question":
            selected_application, position = await self._dashboard_add_question(
                guild,
                form_data,
            )
            messages.append(
                {
                    "message": f"Question {position} added to `{selected_application}`.",
                    "category": "success",
                },
            )

        elif action == "remove_question":
            selected_application, removed = await self._dashboard_remove_question(
                guild,
                form_data,
            )
            messages.append(
                {
                    "message": f"Removed question from `{selected_application}`: {removed}",
                    "category": "success",
                },
            )

        elif action == "post_panel":
            selected_application, message = await self._dashboard_post_panel(
                guild,
                form_data,
                selected_application,
            )
            messages.append(
                {
                    "message": f"Application panel posted: {message.jump_url}",
                    "category": "success",
                },
            )

        elif action == "clear_panel":
            await self._dashboard_clear_panel(guild, form_data)
            messages.append(
                {
                    "message": "Panel tracking and controls cleared.",
                    "category": "success",
                },
            )

        elif action == "set_response_status":
            (
                selected_application,
                response_id,
                decision,
            ) = await self._dashboard_set_response_status(
                guild,
                user,
                member,
                form_data,
            )
            messages.append(
                {
                    "message": f"Response `{response_id}` marked as {decision}.",
                    "category": "success",
                },
            )

        elif action == "create_poll":
            poll_id = await self._dashboard_create_poll(guild, user.id, form_data)
            messages.append(
                {"message": f"Poll `{poll_id}` created.", "category": "success"},
            )

        elif action == "close_poll":
            poll_id = await self._dashboard_close_poll(guild, form_data)
            messages.append(
                {"message": f"Poll `{poll_id}` closed.", "category": "success"},
            )

        elif action:
            raise commands.BadArgument("Unknown Applications dashboard action.")

        return selected_application, messages

    async def _dashboard_create_application(
        self,
        guild: discord.Guild,
        creator_id: int,
        form_data: typing.Any,
    ) -> str:
        from .applications import app_key

        name = self._dash_value(form_data, "new_application_name").strip()
        description = self._dash_value(form_data, "new_application_description").strip()
        if not name:
            raise commands.BadArgument("Application name cannot be empty.")
        if len(name) > 60:
            raise commands.BadArgument(
                "Application name must be 60 characters or fewer.",
            )
        if not description:
            raise commands.BadArgument("Application description cannot be empty.")
        if len(description) > 200:
            raise commands.BadArgument(
                "Application description must be 200 characters or fewer.",
            )

        channel = self._dashboard_required_text_channel(
            guild,
            self._dash_optional_id(form_data, "new_application_channel_id"),
            "Choose a response channel for the new application.",
        )
        key = app_key(name)
        async with self.config.guild(guild).applications() as apps:
            if key in apps:
                raise commands.BadArgument(
                    "An application with that name already exists.",
                )
            apps[key] = self._new_application(
                name=name,
                description=description,
                channel_id=channel.id,
                creator_id=creator_id,
            )
        return key

    async def _dashboard_delete_application(
        self,
        guild: discord.Guild,
        selected_application: str,
    ) -> str:
        if not selected_application:
            raise commands.BadArgument("Choose an application to delete.")
        key, app = await self._get_app(guild.id, selected_application)
        async with self.config.guild(guild).applications() as apps:
            apps.pop(key, None)
        return str(app.get("name") or key)

    async def _dashboard_save_application(
        self,
        guild: discord.Guild,
        form_data: typing.Any,
    ) -> str:
        selected_application = self._dashboard_selected_application(form_data)
        if not selected_application:
            raise commands.BadArgument("Choose an application to save.")
        key, app = await self._get_app(guild.id, selected_application)

        name = self._dash_value(
            form_data,
            "application_name",
            app.get("name", key),
        ).strip()
        description = self._dash_value(form_data, "application_description").strip()
        if not name:
            raise commands.BadArgument("Application display name cannot be empty.")
        if len(name) > 60:
            raise commands.BadArgument(
                "Application display name must be 60 characters or fewer.",
            )
        if len(description) > 2048:
            raise commands.BadArgument(
                "Application description must be 2048 characters or fewer.",
            )

        channel = self._dashboard_required_text_channel(
            guild,
            self._dash_optional_id(form_data, "channel_id"),
            "Choose a response channel.",
        )
        color_value = self._dashboard_parse_color(
            self._dash_value(form_data, "color", self._color_hex(app.get("color"))),
        )
        form_mode = self._dash_value(form_data, "form_mode", "dm").strip().lower()
        if form_mode not in {"dm", "modal"}:
            raise commands.BadArgument("Form mode must be `dm` or `modal`.")
        button_style = (
            self._dash_value(form_data, "button_style", "green").strip().lower()
        )
        if button_style not in self.VALID_BUTTON_STYLES:
            raise commands.BadArgument(
                "Button style must be green, red, gray, or blurple.",
            )
        notify_target = self._notification_role_target(
            {
                "notification_role_target": self._dash_value(
                    form_data,
                    "notification_role_target",
                    "channel",
                ),
            },
        )

        app["name"] = name
        app["description"] = description
        app["channel_id"] = channel.id
        app["open"] = self._dash_bool(form_data, "open")
        app["color"] = color_value
        app["cooldown_minutes"] = self._dash_int(
            form_data,
            "cooldown_minutes",
            default=int(app.get("cooldown_minutes") or 0),
            minimum=0,
            maximum=43200,
        )
        app["allow_multiple_pending"] = self._dash_bool(
            form_data,
            "allow_multiple_pending",
        )
        app["form_mode"] = form_mode
        app["panel_message"] = self._dash_value(form_data, "panel_message")
        app["button_label"] = (
            self._dash_value(form_data, "button_label", "Apply").strip() or "Apply"
        )[:80]
        app["button_style"] = button_style
        app["button_emoji"] = (
            self._dash_value(form_data, "button_emoji").strip() or None
        )
        app["thread_enabled"] = self._dash_bool(form_data, "thread_enabled")
        app["thread_name"] = (
            self._dash_value(form_data, "thread_name", "{application} - {user}").strip()
            or "{application} - {user}"
        )
        app["notification_enabled"] = self._dash_bool(form_data, "notification_enabled")
        app["notification_message"] = self._dash_value(
            form_data,
            "notification_message",
        )
        app["notification_channel_ids"] = self._dashboard_valid_text_channel_ids(
            guild,
            self._dash_values(form_data, "notification_channel_ids"),
        )
        app["notification_role_ids"] = self._dashboard_valid_role_ids(
            guild,
            self._dash_values(form_data, "notification_role_ids"),
        )
        app["notification_role_target"] = notify_target
        app["completion_message"] = self._dash_value(form_data, "completion_message")
        app["accept_message"] = self._dash_value(form_data, "accept_message")
        app["deny_message"] = self._dash_value(form_data, "deny_message")
        app["voting"] = {
            "enabled": self._dash_bool(form_data, "voting_enabled"),
            "threshold": self._dash_int(
                form_data,
                "voting_threshold",
                default=int((app.get("voting") or {}).get("threshold") or 0),
                minimum=0,
                maximum=100,
            ),
        }

        roles = app.setdefault("roles", self._default_roles())
        for role_key, _label in self.ROLE_FIELD_LABELS:
            roles[role_key] = self._dashboard_valid_role_ids(
                guild,
                self._dash_values(form_data, f"roles_{role_key}"),
            )
        for role_key, value in self._default_roles().items():
            roles.setdefault(role_key, value)

        if form_mode == "modal":
            modal_error = self._modal_form_error(app)
            if modal_error:
                raise commands.BadArgument(modal_error)

        await self._save_app(guild.id, app)
        await self._refresh_application_review_views(guild, key, app)
        return key

    async def _dashboard_add_question(
        self,
        guild: discord.Guild,
        form_data: typing.Any,
    ) -> tuple[str, int]:
        from .applications import make_id, parse_csv_values

        selected_application = self._dashboard_selected_application(form_data)
        if not selected_application:
            raise commands.BadArgument(
                "Choose an application before adding a question.",
            )
        key, app = await self._get_app(guild.id, selected_application)
        question_type = self._dash_value(form_data, "add_question_type", "text").lower()
        if question_type not in self.VALID_QUESTION_TYPES:
            raise commands.BadArgument(
                "Question type must be text, boolean, choice, or attachment.",
            )
        questions = app.setdefault("questions", [])
        if len(questions) >= self.MAX_QUESTIONS:
            raise commands.BadArgument(
                f"Applications can have at most {self.MAX_QUESTIONS} questions.",
            )

        text = self._dash_value(form_data, "add_question_text").strip()
        if not text:
            raise commands.BadArgument("Question text cannot be empty.")
        if app.get("form_mode", "dm") == "modal":
            if question_type == "attachment":
                raise commands.BadArgument(
                    "Modal forms cannot contain attachment questions.",
                )
            if len(questions) >= 5:
                raise commands.BadArgument(
                    "Modal forms can contain at most 5 questions.",
                )

        allow_other = False
        parsed_choices: list[str] = []
        if question_type == "choice":
            choice_values = parse_csv_values(
                self._dash_value(form_data, "add_question_choices"),
            )
            if not choice_values:
                raise commands.BadArgument(
                    "Choice questions need comma-separated choices.",
                )
            if len(choice_values) > self.MAX_CHOICES:
                raise commands.BadArgument(
                    "Choice questions can have at most 25 choices.",
                )
            allow_other = any(choice.lower() == "other" for choice in choice_values)
            parsed_choices = [
                choice for choice in choice_values if choice.lower() != "other"
            ]

        questions.append(
            {
                "id": make_id(8),
                "text": text,
                "type": question_type,
                "required": self._dash_bool(form_data, "add_question_required"),
                "choices": parsed_choices,
                "allow_other": allow_other,
            },
        )
        if app.get("form_mode", "dm") == "modal":
            modal_error = self._modal_form_error(app)
            if modal_error:
                questions.pop()
                raise commands.BadArgument(modal_error)
        await self._save_app(guild.id, app)
        return key, len(questions)

    async def _dashboard_remove_question(
        self,
        guild: discord.Guild,
        form_data: typing.Any,
    ) -> tuple[str, str]:
        selected_application = self._dashboard_selected_application(form_data)
        if not selected_application:
            raise commands.BadArgument(
                "Choose an application before removing a question.",
            )
        key, app = await self._get_app(guild.id, selected_application)
        questions = app.get("questions", [])
        if not questions:
            raise commands.BadArgument("This application has no questions.")
        position = self._dash_int(
            form_data,
            "remove_question_position",
            minimum=1,
            maximum=len(questions),
        )
        removed = questions.pop(position - 1)
        await self._save_app(guild.id, app)
        return key, str(removed.get("text") or f"Question {position}")

    async def _dashboard_post_panel(
        self,
        guild: discord.Guild,
        form_data: typing.Any,
        selected_application: str,
    ) -> tuple[str, discord.Message]:
        from .applications import ApplicationPanelView, make_id

        channel = self._dashboard_required_text_channel(
            guild,
            self._dash_optional_id(form_data, "panel_channel_id"),
            "Choose a text channel for the panel.",
        )
        mode = self._dash_value(form_data, "panel_mode", "buttons").strip().lower()
        if mode not in {"buttons", "select"}:
            raise commands.BadArgument("Panel mode must be `buttons` or `select`.")

        apps = await self._get_apps(guild.id)
        selected_keys = self._dash_values(form_data, "panel_application_keys")
        selected_apps = []
        if selected_keys:
            for key in selected_keys:
                if key not in apps:
                    raise commands.BadArgument(f"No application named `{key}` exists.")
                selected_apps.append(apps[key])
        else:
            selected_apps = [app for app in apps.values() if app.get("open", True)]
        if not selected_apps:
            raise commands.BadArgument("No matching applications were found.")
        if len(selected_apps) > 25:
            raise commands.BadArgument("A panel can contain at most 25 applications.")

        title = (
            self._dash_value(form_data, "panel_title", "Applications").strip()
            or "Applications"
        )
        description = self._dash_value(form_data, "panel_description").strip()
        if not description:
            if len(selected_apps) > 1:
                description = "Choose an application below."
            else:
                description = self._render_template(
                    selected_apps[0].get("panel_message", ""),
                    guild=guild,
                    member=None,
                    app=selected_apps[0],
                )

        panel_id = make_id(10)
        view = ApplicationPanelView(
            self,
            guild.id,
            selected_apps,
            mode=mode,
            panel_id=panel_id,
        )
        message = await channel.send(
            embed=self._panel_embed(
                guild,
                selected_apps,
                title=title[:256],
                description=description[:4096],
            ),
            view=view,
        )
        self.bot.add_view(view)
        async with self.config.guild(guild).panels() as panels:
            panels[str(message.id)] = {
                "id": panel_id,
                "channel_id": channel.id,
                "message_id": message.id,
                "applications": [app["key"] for app in selected_apps],
                "mode": mode,
            }
        return selected_application or selected_apps[0]["key"], message

    async def _dashboard_clear_panel(
        self,
        guild: discord.Guild,
        form_data: typing.Any,
    ) -> None:
        message = await self._dashboard_fetch_message(
            guild,
            self._dash_value(form_data, "clear_panel_channel_id"),
            self._dash_value(form_data, "clear_panel_message_id"),
        )
        async with self.config.guild(guild).panels() as panels:
            tracked = panels.pop(str(message.id), None) is not None
        if not tracked:
            raise commands.BadArgument(
                "That message is not tracked as an Applications panel.",
            )
        try:
            await message.edit(view=None)
        except discord.HTTPException as exc:
            raise commands.CommandError(
                "Panel tracking was cleared, but I could not edit the message.",
            ) from exc

    async def _dashboard_set_response_status(
        self,
        guild: discord.Guild,
        user: discord.User,
        member: discord.Member | None,
        form_data: typing.Any,
    ) -> tuple[str, str, str]:
        from .applications import ReviewView

        selected_application = self._dashboard_selected_application(form_data)
        if not selected_application:
            raise commands.BadArgument(
                "Choose an application before reviewing a response.",
            )
        response_id = self._dash_value(form_data, "response_id").strip()
        if not response_id:
            raise commands.BadArgument("Choose a response to review.")
        decision = self._dash_value(form_data, "response_decision").strip().lower()
        if decision not in {"accepted", "denied"}:
            raise commands.BadArgument("Response decision must be accepted or denied.")
        reason = self._dash_value(form_data, "response_reason").strip()

        key, app = await self._get_app(guild.id, selected_application)
        response = self._find_response(app, response_id)
        if response.get("status") != "pending":
            raise commands.BadArgument("That response has already been reviewed.")

        response["status"] = decision
        response["reviewed_by"] = user.id
        response["reviewed_at"] = self._dashboard_now()
        response["review_reason"] = reason

        applicant = (
            guild.get_member(response.get("user_id"))
            if response.get("user_id")
            else None
        )
        if decision == "accepted":
            await self._apply_role_action(applicant, app, "accept_add")
            await self._apply_role_action(applicant, app, "accept_remove")
            dm_template = app.get("accept_message", "")
        else:
            await self._apply_role_action(applicant, app, "deny_add")
            await self._apply_role_action(applicant, app, "deny_remove")
            dm_template = app.get("deny_message", "")

        await self._save_app(guild.id, app)

        if applicant and dm_template:
            dm_content = self._render_template(
                dm_template,
                guild=guild,
                member=applicant,
                app=app,
                response=response,
                reviewer=member or user,
                reason=reason,
            )
            with contextlib.suppress(discord.HTTPException):
                await applicant.send(dm_content[:2000])

        channel = guild.get_channel(response.get("channel_id"))
        if isinstance(channel, discord.TextChannel) and response.get("message_id"):
            with contextlib.suppress(discord.HTTPException, TypeError, ValueError):
                message = await channel.fetch_message(int(response["message_id"]))
                await message.edit(
                    embed=self._response_embed(guild, app, response),
                    view=ReviewView(
                        self,
                        guild.id,
                        key,
                        str(response.get("id") or response_id),
                        disabled=True,
                        voting_enabled=bool(
                            app.get("voting", {}).get("enabled", True),
                        ),
                    ),
                )

        return key, str(response.get("id") or response_id), decision

    async def _dashboard_create_poll(
        self,
        guild: discord.Guild,
        creator_id: int,
        form_data: typing.Any,
    ) -> str:
        from .applications import PollView, make_id, parse_csv_values

        channel = self._dashboard_required_text_channel(
            guild,
            self._dash_optional_id(form_data, "poll_channel_id"),
            "Choose a text channel for the poll.",
        )
        question = self._dash_value(form_data, "poll_question").strip()
        if not question:
            raise commands.BadArgument("Poll question cannot be empty.")
        options = parse_csv_values(self._dash_value(form_data, "poll_options"))
        if len(options) < 2:
            raise commands.BadArgument("Polls need at least two options.")
        if len(options) > 25:
            raise commands.BadArgument("Polls can have at most 25 options.")

        poll_id = make_id(10)
        record = {
            "id": poll_id,
            "question": question,
            "options": options,
            "votes": {str(idx): [] for idx in range(len(options))},
            "created_by": creator_id,
            "created_at": self._dashboard_now(),
            "channel_id": channel.id,
            "message_id": None,
            "closed": False,
        }
        view = PollView(self, guild.id, poll_id, options)
        message = await channel.send(embed=self._poll_embed(record), view=view)
        record["message_id"] = message.id
        self.bot.add_view(view)
        async with self.config.guild(guild).polls() as polls:
            polls[poll_id] = record
        return poll_id

    async def _dashboard_close_poll(
        self,
        guild: discord.Guild,
        form_data: typing.Any,
    ) -> str:
        from .applications import PollView

        poll_id = self._dash_value(form_data, "poll_id").strip()
        if not poll_id:
            raise commands.BadArgument("Choose a poll to close.")
        async with self.config.guild(guild).polls() as polls:
            poll = polls.get(poll_id)
            if not poll:
                raise commands.BadArgument("That poll does not exist.")
            poll["closed"] = True

        channel = guild.get_channel(poll.get("channel_id"))
        if isinstance(channel, discord.TextChannel):
            with contextlib.suppress(discord.HTTPException, TypeError, ValueError):
                message = await channel.fetch_message(int(poll.get("message_id")))
                await message.edit(
                    embed=self._poll_embed(poll),
                    view=PollView(
                        self,
                        guild.id,
                        poll_id,
                        poll.get("options", []),
                        disabled=True,
                    ),
                )
        return poll_id

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
            raise commands.BadArgument(
                "Provide both channel ID and message ID.",
            ) from exc
        channel = guild.get_channel(clean_channel_id)
        if not isinstance(channel, discord.TextChannel):
            raise commands.BadArgument("The channel ID must resolve to a text channel.")
        try:
            return await channel.fetch_message(clean_message_id)
        except discord.HTTPException as exc:
            raise commands.CommandError("I could not fetch that message.") from exc

    async def _dashboard_source(
        self,
        guild: discord.Guild,
        selected_application: str,
        kwargs: dict[str, typing.Any],
    ) -> str:
        apps = await self._get_apps(guild.id)
        panels = await self.config.guild(guild).panels()
        polls = await self.config.guild(guild).polls()
        if selected_application not in apps:
            selected_application = next(
                iter(sorted(apps, key=lambda key: apps[key].get("name", key).lower())),
                "",
            )
        app = apps.get(selected_application)
        csrf = self._dash_csrf(kwargs)

        total_responses = sum(
            len(app_data.get("responses", [])) for app_data in apps.values()
        )
        pending_responses = sum(
            1
            for app_data in apps.values()
            for response in app_data.get("responses", [])
            if response.get("status") == "pending"
        )
        open_polls = sum(1 for poll in polls.values() if not poll.get("closed"))
        active_tab = self._dashboard_active_tab(
            kwargs,
            {
                "select_application": "setup",
                "create_application": "setup",
                "delete_application": "setup",
                "save_application": "setup",
                "add_question": "questions",
                "remove_question": "questions",
                "post_panel": "panels",
                "clear_panel": "panels",
                "set_response_status": "responses",
                "create_poll": "polls",
                "close_poll": "polls",
            },
            "setup",
        )

        return f"""
        <style>
            .appdash-wrap {{ max-width: 1180px; margin: 0 auto; color: #e5e7eb; }}
            .appdash-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(260px, 1fr)); gap: 16px; }}
            .appdash-row {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 12px; margin-bottom: 12px; }}
            .appdash-card {{ background: #1f2937; border: 1px solid #374151; border-radius: 8px; padding: 16px; margin-bottom: 16px; }}
            .appdash-card h2, .appdash-card h3 {{ margin: 0 0 12px 0; color: #f9fafb; }}
            .appdash-muted {{ color: #9ca3af; }}
            .appdash-stat {{ font-size: 1.5rem; font-weight: 700; color: #f9fafb; }}
            .appdash-field label {{ display: block; font-weight: 600; margin-bottom: 4px; color: #d1d5db; }}
            .appdash-field input, .appdash-field select, .appdash-field textarea {{
                width: 100%; box-sizing: border-box; border: 1px solid #4b5563; border-radius: 6px;
                background: #111827; color: #f9fafb; padding: 8px; min-height: 38px;
            }}
            .appdash-field textarea {{ min-height: 82px; font-family: ui-monospace, SFMono-Regular, Menlo, monospace; }}
            .appdash-check {{ display: flex; align-items: center; gap: 8px; margin: 6px 0; color: #d1d5db; }}
            .appdash-check input {{ width: auto; }}
            .appdash-btn {{ background: #2563eb; color: white; border: 0; border-radius: 6px; padding: 9px 14px; cursor: pointer; font-weight: 700; }}
            .appdash-btn.secondary {{ background: #4b5563; }}
            .appdash-btn.danger {{ background: #dc2626; }}
            .dash-tabs {{ display: flex; gap: 4px; overflow-x: auto; position: sticky; top: 0; z-index: 10; margin: 0 0 16px; padding: 5px; background: #111827; border: 1px solid #374151; border-radius: 8px; }}
            .dash-tab {{ flex: 0 0 auto; border: 0; border-radius: 6px; padding: 9px 13px; background: transparent; color: #9ca3af; cursor: pointer; font-weight: 700; white-space: nowrap; }}
            .dash-tab:hover {{ background: #1f2937; color: #f9fafb; }} .dash-tab.active {{ background: #2563eb; color: white; }}
            .dash-panel {{ display: none; }} .dash-panel.active {{ display: block; }}
            .appdash-table {{ width: 100%; border-collapse: collapse; font-size: 0.92rem; }}
            .appdash-table th, .appdash-table td {{ border-bottom: 1px solid #374151; padding: 8px; text-align: left; vertical-align: top; }}
            .appdash-table th {{ color: #d1d5db; }}
            .appdash-inline {{ display: inline; }}
        </style>
        <div class="appdash-wrap" data-dashboard-tabs="1">
            <div class="appdash-card">
                <h2>Applications Dashboard</h2>
                <div class="appdash-grid">
                    <div><div class="appdash-muted">Applications</div><div class="appdash-stat">{len(apps)}</div></div>
                    <div><div class="appdash-muted">Panels</div><div class="appdash-stat">{len(panels)}</div></div>
                    <div><div class="appdash-muted">Responses</div><div class="appdash-stat">{total_responses}</div></div>
                    <div><div class="appdash-muted">Pending Reviews</div><div class="appdash-stat">{pending_responses}</div></div>
                    <div><div class="appdash-muted">Open Polls</div><div class="appdash-stat">{open_polls}</div></div>
                </div>
            </div>
            <div class="dash-tabs" role="tablist" aria-label="Applications sections">
                {self._dashboard_tab_button("setup", "Application Setup", active_tab)}
                {self._dashboard_tab_button("questions", "Questions", active_tab)}
                {self._dashboard_tab_button("panels", "Panels", active_tab)}
                {self._dashboard_tab_button("responses", "Responses", active_tab)}
                {self._dashboard_tab_button("polls", "Polls", active_tab)}
            </div>
            <section class="dash-panel{" active" if active_tab == "setup" else ""}" data-tab-panel="setup">{self._dashboard_application_selector(apps, selected_application, guild, csrf)}{self._dashboard_application_settings(guild, selected_application, app, csrf)}</section>
            <section class="dash-panel{" active" if active_tab == "questions" else ""}" data-tab-panel="questions">{self._dashboard_questions_section(selected_application, app, csrf)}</section>
            <section class="dash-panel{" active" if active_tab == "panels" else ""}" data-tab-panel="panels">{self._dashboard_panels_section(guild, apps, panels, selected_application, csrf)}</section>
            <section class="dash-panel{" active" if active_tab == "responses" else ""}" data-tab-panel="responses">{self._dashboard_responses_section(guild, selected_application, app, csrf)}</section>
            <section class="dash-panel{" active" if active_tab == "polls" else ""}" data-tab-panel="polls">{self._dashboard_polls_section(guild, polls, csrf)}</section>
            {self._dashboard_tabs_script()}
        </div>
        """

    def _dashboard_application_selector(
        self,
        apps: dict[str, dict[str, typing.Any]],
        selected_application: str,
        guild: discord.Guild,
        csrf: str,
    ) -> str:
        options = self._application_options(apps, selected_application)
        delete_form = ""
        if selected_application:
            delete_form = f"""
            <form method="POST">
                {csrf}
                <input type="hidden" name="action" value="delete_application">
                <input type="hidden" name="selected_application" value="{self._h(selected_application)}">
                <button class="appdash-btn danger" type="submit">Delete Selected Application</button>
            </form>
            """
        return f"""
        <div id="applications" class="appdash-card">
            <h3>Applications</h3>
            <div class="appdash-grid">
                <form method="POST">
                    {csrf}
                    <input type="hidden" name="action" value="select_application">
                    <div class="appdash-field">
                        <label>Selected Application</label>
                        <select name="selected_application" onchange="this.form.submit()">{options}</select>
                    </div>
                </form>
                <form method="POST">
                    {csrf}
                    <input type="hidden" name="action" value="create_application">
                    <div class="appdash-row">
                        {self._input("new_application_name", "New Application Name", "")}
                        {self._channel_select(guild, "new_application_channel_id", "Response Channel", None, include_none=False)}
                    </div>
                    {self._textarea("new_application_description", "Description", "", rows=3)}
                    <button class="appdash-btn" type="submit">Create Application</button>
                </form>
                {delete_form}
            </div>
        </div>
        """

    def _dashboard_application_settings(
        self,
        guild: discord.Guild,
        selected_application: str,
        app: dict[str, typing.Any] | None,
        csrf: str,
    ) -> str:
        if app is None:
            return """
            <div id="settings" class="appdash-card">
                <h3>Settings</h3>
                <p class="appdash-muted">Create an application to configure settings.</p>
            </div>
            """

        role_fields = "".join(
            self._multi_role_select(
                guild,
                f"roles_{role_key}",
                label,
                app.get("roles", {}).get(role_key, []),
            )
            for role_key, label in self.ROLE_FIELD_LABELS
        )
        return f"""
        <div id="settings" class="appdash-card">
            <h3>Settings: {self._h(app.get("name") or selected_application)}</h3>
            <form method="POST">
                {csrf}
                <input type="hidden" name="action" value="save_application">
                <input type="hidden" name="selected_application" value="{self._h(selected_application)}">
                <div class="appdash-grid">
                    <div>
                        <label class="appdash-check"><input type="checkbox" name="open" value="1" {self._checked(app.get("open", True))}> Open</label>
                        <label class="appdash-check"><input type="checkbox" name="allow_multiple_pending" value="1" {self._checked(app.get("allow_multiple_pending"))}> Allow Multiple Pending</label>
                        <label class="appdash-check"><input type="checkbox" name="thread_enabled" value="1" {self._checked(app.get("thread_enabled", True))}> Create Review Threads</label>
                        <label class="appdash-check"><input type="checkbox" name="notification_enabled" value="1" {self._checked(app.get("notification_enabled", True))}> Notifications Enabled</label>
                        <label class="appdash-check"><input type="checkbox" name="voting_enabled" value="1" {self._checked((app.get("voting") or {}).get("enabled", True))}> Review Voting</label>
                    </div>
                    <div class="appdash-row">
                        {self._input("application_name", "Display Name", app.get("name") or "")}
                        {self._input("color", "Embed Color", self._color_hex(app.get("color")))}
                        {self._input("cooldown_minutes", "Cooldown Minutes", app.get("cooldown_minutes", 0), "number", min_value=0, max_value=43200)}
                        {self._input("voting_threshold", "Voting Threshold", (app.get("voting") or {}).get("threshold", 0), "number", min_value=0, max_value=100)}
                    </div>
                </div>
                <div class="appdash-row">
                    {self._channel_select(guild, "channel_id", "Response Channel", app.get("channel_id"), include_none=False)}
                    <div class="appdash-field"><label>Form Mode</label><select name="form_mode">{self._option("dm", "DM Flow", app.get("form_mode", "dm"))}{self._option("modal", "Discord Modal", app.get("form_mode", "dm"))}</select></div>
                    {self._input("thread_name", "Thread Name Template", app.get("thread_name") or "{application} - {user}")}
                </div>
                <div class="appdash-row">
                    {self._input("button_label", "Panel Button Label", app.get("button_label") or "Apply")}
                    <div class="appdash-field"><label>Panel Button Style</label><select name="button_style">{self._option("green", "Green", app.get("button_style"))}{self._option("red", "Red", app.get("button_style"))}{self._option("gray", "Gray", app.get("button_style"))}{self._option("blurple", "Blurple", app.get("button_style"))}</select></div>
                    {self._input("button_emoji", "Panel Button Emoji", app.get("button_emoji") or "")}
                    <div class="appdash-field"><label>Notification Role Ping Target</label><select name="notification_role_target">{self._option("channel", "Channel", self._notification_role_target(app))}{self._option("thread", "Thread", self._notification_role_target(app))}{self._option("both", "Both", self._notification_role_target(app))}</select></div>
                </div>
                <div class="appdash-row">
                    {self._textarea("application_description", "Description", app.get("description") or "", rows=3)}
                    {self._textarea("panel_message", "Panel Message", app.get("panel_message") or "", rows=3)}
                    {self._textarea("notification_message", "Notification Message", app.get("notification_message") or "", rows=3)}
                </div>
                <div class="appdash-row">
                    {self._textarea("completion_message", "Completion DM", app.get("completion_message") or "", rows=3)}
                    {self._textarea("accept_message", "Accept DM", app.get("accept_message") or "", rows=3)}
                    {self._textarea("deny_message", "Deny DM", app.get("deny_message") or "", rows=3)}
                </div>
                <h3>Notification Targets</h3>
                <div class="appdash-row">
                    {self._multi_channel_select(guild, "notification_channel_ids", "Extra Notification Channels", app.get("notification_channel_ids") or [])}
                    {self._multi_role_select(guild, "notification_role_ids", "Notification Ping Roles", app.get("notification_role_ids") or [])}
                </div>
                <h3>Roles</h3>
                <div class="appdash-row">{role_fields}</div>
                <button class="appdash-btn" type="submit">Save Application</button>
            </form>
        </div>
        """

    def _dashboard_questions_section(
        self,
        selected_application: str,
        app: dict[str, typing.Any] | None,
        csrf: str,
    ) -> str:
        if app is None:
            return """
            <div id="questions" class="appdash-card">
                <h3>Questions</h3>
                <p class="appdash-muted">Create an application before adding questions.</p>
            </div>
            """

        rows = []
        questions = app.get("questions", [])
        for index, question in enumerate(questions, start=1):
            choices = ", ".join(question.get("choices") or [])
            if question.get("allow_other"):
                choices = f"{choices}, other" if choices else "other"
            rows.append(
                "<tr>"
                f"<td>{index}</td>"
                f"<td>{self._h(question.get('type') or 'text')}</td>"
                f"<td>{'Yes' if question.get('required', True) else 'No'}</td>"
                f"<td>{self._h(question.get('text') or '')}</td>"
                f"<td>{self._h(choices)}</td>"
                "</tr>",
            )
        table = "".join(rows) or (
            '<tr><td colspan="5" class="appdash-muted">No questions configured.</td></tr>'
        )
        remove_options = "".join(
            f'<option value="{index}">{index}. {self._h(question.get("text") or "Question")}</option>'
            for index, question in enumerate(questions, start=1)
        )
        remove_form = (
            f"""
            <form method="POST">
                {csrf}
                <input type="hidden" name="action" value="remove_question">
                <input type="hidden" name="selected_application" value="{self._h(selected_application)}">
                <div class="appdash-field">
                    <label>Remove Question</label>
                    <select name="remove_question_position">{remove_options}</select>
                </div>
                <button class="appdash-btn danger" type="submit">Remove Question</button>
            </form>
            """
            if questions
            else '<p class="appdash-muted">No question is available to remove.</p>'
        )
        return f"""
        <div id="questions" class="appdash-card">
            <h3>Questions</h3>
            <table class="appdash-table"><thead><tr><th>#</th><th>Type</th><th>Required</th><th>Question</th><th>Choices</th></tr></thead><tbody>{table}</tbody></table>
            <div class="appdash-grid">
                <form method="POST">
                    {csrf}
                    <input type="hidden" name="action" value="add_question">
                    <input type="hidden" name="selected_application" value="{self._h(selected_application)}">
                    {self._textarea("add_question_text", "New Question", "", rows=3)}
                    <div class="appdash-row">
                        <div class="appdash-field"><label>Type</label><select name="add_question_type">{self._option("text", "Text", "text")}{self._option("boolean", "Boolean", "text")}{self._option("choice", "Choice", "text")}{self._option("attachment", "Attachment", "text")}</select></div>
                        <label class="appdash-check"><input type="checkbox" name="add_question_required" value="1" checked> Required</label>
                    </div>
                    {self._input("add_question_choices", "Choices for Choice Type", "")}
                    <button class="appdash-btn" type="submit">Add Question</button>
                </form>
                {remove_form}
            </div>
        </div>
        """

    def _dashboard_panels_section(
        self,
        guild: discord.Guild,
        apps: dict[str, dict[str, typing.Any]],
        panels: dict[str, typing.Any],
        selected_application: str,
        csrf: str,
    ) -> str:
        rows = []
        for message_id, panel in panels.items():
            app_names = [
                apps[key].get("name", key) if key in apps else key
                for key in panel.get("applications", [])
            ]
            channel_id = panel.get("channel_id")
            channel = guild.get_channel(channel_id) if channel_id else None
            rows.append(
                "<tr>"
                f"<td>{self._h(message_id)}</td>"
                f"<td>{self._channel_label(channel, channel_id)}</td>"
                f"<td>{self._h(panel.get('mode') or 'buttons')}</td>"
                f"<td>{self._h(', '.join(app_names))}</td>"
                "</tr>",
            )
        table = "".join(rows) or (
            '<tr><td colspan="4" class="appdash-muted">No panels tracked.</td></tr>'
        )
        return f"""
        <div id="panels" class="appdash-card">
            <h3>Panels</h3>
            <table class="appdash-table"><thead><tr><th>Message</th><th>Channel</th><th>Mode</th><th>Applications</th></tr></thead><tbody>{table}</tbody></table>
            <div class="appdash-grid">
                <form method="POST">
                    {csrf}
                    <input type="hidden" name="action" value="post_panel">
                    <input type="hidden" name="selected_application" value="{self._h(selected_application)}">
                    <div class="appdash-row">
                        {self._channel_select(guild, "panel_channel_id", "Post Panel Channel", None, include_none=False)}
                        <div class="appdash-field"><label>Mode</label><select name="panel_mode">{self._option("buttons", "Buttons", "buttons")}{self._option("select", "Dropdown", "buttons")}</select></div>
                        {self._input("panel_title", "Panel Title", "Applications")}
                    </div>
                    {self._multi_application_select(apps, "panel_application_keys", "Panel Applications", [selected_application] if selected_application else [])}
                    {self._textarea("panel_description", "Panel Description Override", "", rows=3)}
                    <button class="appdash-btn" type="submit">Post Panel</button>
                </form>
                <form method="POST">
                    {csrf}
                    <input type="hidden" name="action" value="clear_panel">
                    <div class="appdash-row">
                        {self._input("clear_panel_channel_id", "Panel Channel ID", "")}
                        {self._input("clear_panel_message_id", "Panel Message ID", "")}
                    </div>
                    <button class="appdash-btn danger" type="submit">Clear Panel</button>
                </form>
            </div>
        </div>
        """

    def _dashboard_responses_section(
        self,
        guild: discord.Guild,
        selected_application: str,
        app: dict[str, typing.Any] | None,
        csrf: str,
    ) -> str:
        if app is None:
            return """
            <div id="responses" class="appdash-card">
                <h3>Responses</h3>
                <p class="appdash-muted">Select an application to view responses.</p>
            </div>
            """

        responses = sorted(
            app.get("responses", []),
            key=lambda response: int(response.get("created_at") or 0),
            reverse=True,
        )
        rows = []
        pending_options = []
        for response in responses[:100]:
            user_id = response.get("user_id")
            applicant = guild.get_member(user_id) if user_id else None
            votes = response.get("votes") or {}
            rows.append(
                "<tr>"
                f"<td>{self._h(response.get('id') or '')}</td>"
                f"<td>{self._h(response.get('status') or 'pending')}</td>"
                f"<td>{self._h(applicant or user_id or '')}</td>"
                f"<td>{self._h(response.get('created_at') or '')}</td>"
                f"<td>+{len(votes.get('up', []))} / 0 {len(votes.get('neutral', []))} / -{len(votes.get('down', []))}</td>"
                "</tr>",
            )
            if response.get("status") == "pending":
                label = f"{response.get('id')} - {applicant or user_id or 'unknown'}"
                pending_options.append(
                    f'<option value="{self._h(response.get("id"))}">{self._h(label)}</option>',
                )
        table = "".join(rows) or (
            '<tr><td colspan="5" class="appdash-muted">No responses stored.</td></tr>'
        )
        decision_form = (
            f"""
            <form method="POST">
                {csrf}
                <input type="hidden" name="action" value="set_response_status">
                <input type="hidden" name="selected_application" value="{self._h(selected_application)}">
                <div class="appdash-row">
                    <div class="appdash-field"><label>Pending Response</label><select name="response_id">{"".join(pending_options)}</select></div>
                    <div class="appdash-field"><label>Decision</label><select name="response_decision">{self._option("accepted", "Accept", "accepted")}{self._option("denied", "Deny", "accepted")}</select></div>
                </div>
                {self._textarea("response_reason", "Reason", "", rows=3)}
                <button class="appdash-btn" type="submit">Set Response Status</button>
            </form>
            """
            if pending_options
            else '<p class="appdash-muted">No pending responses are available to review.</p>'
        )
        return f"""
        <div id="responses" class="appdash-card">
            <h3>Responses</h3>
            <table class="appdash-table"><thead><tr><th>ID</th><th>Status</th><th>User</th><th>Created</th><th>Votes</th></tr></thead><tbody>{table}</tbody></table>
            {decision_form}
        </div>
        """

    def _dashboard_polls_section(
        self,
        guild: discord.Guild,
        polls: dict[str, typing.Any],
        csrf: str,
    ) -> str:
        rows = []
        close_options = []
        for poll_id, poll in sorted(polls.items()):
            votes = poll.get("votes") or {}
            total = sum(len(voters) for voters in votes.values())
            channel_id = poll.get("channel_id")
            channel = guild.get_channel(channel_id)
            rows.append(
                "<tr>"
                f"<td>{self._h(poll_id)}</td>"
                f"<td>{self._h(poll.get('question') or '')}</td>"
                f"<td>{self._channel_label(channel, channel_id)}</td>"
                f"<td>{'Closed' if poll.get('closed') else 'Open'}</td>"
                f"<td>{total}</td>"
                "</tr>",
            )
            if not poll.get("closed"):
                close_options.append(
                    f'<option value="{self._h(poll_id)}">{self._h(poll.get("question") or poll_id)}</option>',
                )
        table = "".join(rows) or (
            '<tr><td colspan="5" class="appdash-muted">No polls tracked.</td></tr>'
        )
        close_form = (
            f"""
            <form method="POST">
                {csrf}
                <input type="hidden" name="action" value="close_poll">
                <div class="appdash-field"><label>Open Poll</label><select name="poll_id">{"".join(close_options)}</select></div>
                <button class="appdash-btn danger" type="submit">Close Poll</button>
            </form>
            """
            if close_options
            else '<p class="appdash-muted">No open polls are available to close.</p>'
        )
        return f"""
        <div id="polls" class="appdash-card">
            <h3>Polls</h3>
            <table class="appdash-table"><thead><tr><th>ID</th><th>Question</th><th>Channel</th><th>Status</th><th>Votes</th></tr></thead><tbody>{table}</tbody></table>
            <div class="appdash-grid">
                <form method="POST">
                    {csrf}
                    <input type="hidden" name="action" value="create_poll">
                    {self._channel_select(guild, "poll_channel_id", "Poll Channel", None, include_none=False)}
                    {self._input("poll_question", "Question", "")}
                    {self._input("poll_options", "Options", "Yes, No")}
                    <button class="appdash-btn" type="submit">Create Poll</button>
                </form>
                {close_form}
            </div>
        </div>
        """

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

    def _dashboard_valid_text_channel_ids(
        self,
        guild: discord.Guild,
        raw_values: typing.Iterable[str],
    ) -> list[int]:
        channel_ids = []
        for raw_value in raw_values:
            with contextlib.suppress(TypeError, ValueError):
                channel_id = int(raw_value)
                if isinstance(guild.get_channel(channel_id), discord.TextChannel):
                    channel_ids.append(channel_id)
        return sorted(set(channel_ids))

    def _dashboard_valid_role_ids(
        self,
        guild: discord.Guild,
        raw_values: typing.Iterable[str],
    ) -> list[int]:
        role_ids = []
        for raw_value in raw_values:
            with contextlib.suppress(TypeError, ValueError):
                role_id = int(raw_value)
                if guild.get_role(role_id):
                    role_ids.append(role_id)
        return sorted(set(role_ids))

    @staticmethod
    def _dashboard_now() -> int:
        import time

        return int(time.time())

    def _dashboard_parse_color(self, value: str) -> int:
        value = value.strip()
        if not value:
            return self.DEFAULT_COLOR
        try:
            return discord.Color.from_str(value).value
        except ValueError as exc:
            raise commands.BadArgument(
                "Use a valid Discord color, such as `#5865F2`.",
            ) from exc

    def _color_hex(self, value: typing.Any) -> str:
        try:
            number = int(value)
        except (TypeError, ValueError):
            number = self.DEFAULT_COLOR
        return f"#{number:06X}"

    def _application_options(
        self,
        apps: dict[str, dict[str, typing.Any]],
        selected: typing.Any,
    ) -> str:
        if not apps:
            return '<option value="">No applications configured</option>'
        options = []
        for key, app in sorted(
            apps.items(),
            key=lambda item: item[1].get("name", item[0]).lower(),
        ):
            label = f"{app.get('name', key)} ({key})"
            options.append(
                f'<option value="{self._h(key)}" {self._selected(key, selected)}>{self._h(label)}</option>',
            )
        return "".join(options)

    def _channel_select(
        self,
        guild: discord.Guild,
        name: str,
        label: str,
        selected: typing.Any,
        *,
        include_none: bool = True,
    ) -> str:
        options = ['<option value="">None</option>'] if include_none else []
        for channel in sorted(guild.text_channels, key=lambda item: item.name.lower()):
            options.append(
                f'<option value="{channel.id}" {self._selected(channel.id, selected)}>#{self._h(channel.name)}</option>',
            )
        return (
            f'<div class="appdash-field"><label>{self._h(label)}</label>'
            f'<select name="{self._h(name)}">{"".join(options)}</select></div>'
        )

    def _channel_label(
        self,
        channel: discord.abc.GuildChannel | None,
        fallback: typing.Any,
    ) -> str:
        if channel is None:
            return self._h(fallback or "missing")
        return self._h(f"#{channel.name}")

    def _multi_channel_select(
        self,
        guild: discord.Guild,
        name: str,
        label: str,
        selected: typing.Sequence[int],
    ) -> str:
        selected_ids = {str(channel_id) for channel_id in selected}
        options = []
        for channel in sorted(guild.text_channels, key=lambda item: item.name.lower()):
            options.append(
                f'<option value="{channel.id}" {"selected" if str(channel.id) in selected_ids else ""}>#{self._h(channel.name)}</option>',
            )
        return (
            f'<div class="appdash-field"><label>{self._h(label)}</label>'
            f'<select name="{self._h(name)}" multiple size="8">{"".join(options)}</select></div>'
        )

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
                f'<option value="{role.id}" {"selected" if str(role.id) in selected_ids else ""}>{self._h(role.name)}</option>',
            )
        return (
            f'<div class="appdash-field"><label>{self._h(label)}</label>'
            f'<select name="{self._h(name)}" multiple size="8">{"".join(options)}</select></div>'
        )

    def _multi_application_select(
        self,
        apps: dict[str, dict[str, typing.Any]],
        name: str,
        label: str,
        selected: typing.Sequence[str],
    ) -> str:
        selected_keys = {str(key) for key in selected}
        options = []
        for key, app in sorted(
            apps.items(),
            key=lambda item: item[1].get("name", item[0]).lower(),
        ):
            options.append(
                f'<option value="{self._h(key)}" {"selected" if key in selected_keys else ""}>{self._h(app.get("name", key))}</option>',
            )
        return (
            f'<div class="appdash-field"><label>{self._h(label)}</label>'
            f'<select name="{self._h(name)}" multiple size="10">{"".join(options)}</select></div>'
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
            f'<div class="appdash-field"><label>{self._h(label)}</label>'
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
            f'<div class="appdash-field"><label>{self._h(label)}</label>'
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
