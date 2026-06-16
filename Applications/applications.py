"""Application and form workflows for Red-DiscordBot."""

from __future__ import annotations

import asyncio
import contextlib
import csv
import io
import json
import logging
import re
import time
import uuid
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

import discord
from redbot.core import Config, app_commands, commands
from redbot.core.bot import Red
from redbot.core.utils.chat_formatting import box, pagify

log = logging.getLogger("red.taakoscogs.applications")


ApplicationDict = Dict[str, Any]
ResponseDict = Dict[str, Any]
QuestionDict = Dict[str, Any]
PollDict = Dict[str, Any]
MODAL_SELECTS_SUPPORTED = hasattr(discord.ui, "Label")


def utc_ts() -> int:
    return int(time.time())


def make_id(length: int = 12) -> str:
    return uuid.uuid4().hex[:length]


def app_key(name: str) -> str:
    key = re.sub(r"[^a-z0-9_-]+", "-", name.strip().lower())
    key = re.sub(r"-+", "-", key).strip("-")
    return key[:40] or "application"


def truncate(value: Any, limit: int) -> str:
    text = str(value) if value is not None else ""
    if len(text) <= limit:
        return text
    return text[: max(0, limit - 3)] + "..."


def bool_text(value: bool) -> str:
    return "enabled" if value else "disabled"


def unique_ids(items: Iterable[int]) -> List[int]:
    seen: List[int] = []
    for item in items:
        if item not in seen:
            seen.append(item)
    return seen


def parse_csv_values(value: Any) -> List[str]:
    if value is None:
        return []
    if isinstance(value, str):
        values = [value]
    else:
        try:
            values = list(value)
        except TypeError:
            values = [value]

    parsed: List[str] = []
    for raw_value in values:
        for item in str(raw_value).split(","):
            cleaned = item.strip()
            if cleaned:
                parsed.append(cleaned)
    return parsed


def parse_mentions_or_ids(value: str) -> List[int]:
    ids: List[int] = []
    for item in re.findall(r"\d{15,25}", value):
        with contextlib.suppress(ValueError):
            ids.append(int(item))
    return unique_ids(ids)


class QuestionChoiceView(discord.ui.View):
    def __init__(
        self,
        author_id: int,
        question: QuestionDict,
        *,
        timeout: float = 600.0,
    ) -> None:
        super().__init__(timeout=timeout)
        self.author_id = author_id
        self.question = question
        self.answer: Optional[str] = None
        self.cancelled = False
        self.skipped = False

        options = [
            discord.SelectOption(label=truncate(choice, 100), value=choice[:100])
            for choice in question.get("choices", [])[:25]
        ]
        if question.get("allow_other"):
            options.append(discord.SelectOption(label="Other", value="__other__"))

        select = discord.ui.Select(
            placeholder="Choose an answer",
            options=options,
            min_values=1,
            max_values=1,
        )
        select.callback = self._select_callback
        self.add_item(select)

        if not question.get("required", True):
            skip = discord.ui.Button(label="Skip", style=discord.ButtonStyle.secondary)
            skip.callback = self._skip_callback
            self.add_item(skip)

        cancel = discord.ui.Button(label="Cancel", style=discord.ButtonStyle.danger)
        cancel.callback = self._cancel_callback
        self.add_item(cancel)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user and interaction.user.id == self.author_id:
            return True
        await interaction.response.send_message("This application prompt is not for you.", ephemeral=True)
        return False

    async def _select_callback(self, interaction: discord.Interaction) -> None:
        select = interaction.data or {}
        values = select.get("values") or []
        if not values:
            await interaction.response.send_message("No answer was selected.", ephemeral=True)
            return
        self.answer = str(values[0])
        await interaction.response.defer()
        self.stop()

    async def _skip_callback(self, interaction: discord.Interaction) -> None:
        self.skipped = True
        await interaction.response.defer()
        self.stop()

    async def _cancel_callback(self, interaction: discord.Interaction) -> None:
        self.cancelled = True
        await interaction.response.defer()
        self.stop()


class QuestionBooleanView(discord.ui.View):
    def __init__(
        self,
        author_id: int,
        *,
        required: bool,
        timeout: float = 600.0,
    ) -> None:
        super().__init__(timeout=timeout)
        self.author_id = author_id
        self.answer: Optional[str] = None
        self.cancelled = False
        self.skipped = False

        yes = discord.ui.Button(label="Yes", style=discord.ButtonStyle.success)
        yes.callback = self._yes_callback
        self.add_item(yes)

        no = discord.ui.Button(label="No", style=discord.ButtonStyle.danger)
        no.callback = self._no_callback
        self.add_item(no)

        if not required:
            skip = discord.ui.Button(label="Skip", style=discord.ButtonStyle.secondary)
            skip.callback = self._skip_callback
            self.add_item(skip)

        cancel = discord.ui.Button(label="Cancel", style=discord.ButtonStyle.secondary)
        cancel.callback = self._cancel_callback
        self.add_item(cancel)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user and interaction.user.id == self.author_id:
            return True
        await interaction.response.send_message("This application prompt is not for you.", ephemeral=True)
        return False

    async def _yes_callback(self, interaction: discord.Interaction) -> None:
        self.answer = "Yes"
        await interaction.response.defer()
        self.stop()

    async def _no_callback(self, interaction: discord.Interaction) -> None:
        self.answer = "No"
        await interaction.response.defer()
        self.stop()

    async def _skip_callback(self, interaction: discord.Interaction) -> None:
        self.skipped = True
        await interaction.response.defer()
        self.stop()

    async def _cancel_callback(self, interaction: discord.Interaction) -> None:
        self.cancelled = True
        await interaction.response.defer()
        self.stop()


class DecisionModal(discord.ui.Modal):
    def __init__(
        self,
        cog: "Applications",
        guild_id: int,
        application: str,
        response_id: str,
        decision: str,
    ) -> None:
        title = "Accept Application" if decision == "accepted" else "Deny Application"
        super().__init__(title=title, timeout=300.0)
        self.cog = cog
        self.guild_id = guild_id
        self.application = application
        self.response_id = response_id
        self.decision = decision
        self.reason = discord.ui.TextInput(
            label="Reason",
            style=discord.TextStyle.paragraph,
            required=False,
            max_length=1000,
            placeholder="Optional reason to store and DM to the applicant.",
        )
        self.add_item(self.reason)

    async def on_submit(self, interaction: discord.Interaction) -> None:
        await self.cog._set_response_decision(
            interaction,
            self.guild_id,
            self.application,
            self.response_id,
            self.decision,
            str(self.reason.value or "").strip(),
        )


class ApplicationFormModal(discord.ui.Modal):
    """Collect an application in one native Discord modal."""

    def __init__(
        self,
        cog: "Applications",
        guild_id: int,
        application: str,
        app: ApplicationDict,
        *,
        bypass: bool = False,
    ) -> None:
        super().__init__(
            title=truncate(app.get("name") or "Application", 45),
            timeout=600.0,
        )
        self.cog = cog
        self.guild_id = guild_id
        self.application = application
        self.bypass = bypass
        self.questions = list(app.get("questions", [])[:5])
        self.inputs: List[Tuple[QuestionDict, discord.ui.Item]] = []

        for question in self.questions:
            question_type = str(question.get("type") or "text").lower()
            question_label = truncate(question.get("text") or "Question", 45)
            required = bool(question.get("required", True))
            placeholder: Optional[str] = None
            max_length = 4000
            style = discord.TextStyle.paragraph
            component: discord.ui.Item
            if MODAL_SELECTS_SUPPORTED and question_type == "boolean":
                component = discord.ui.Select(
                    placeholder="Choose Yes or No",
                    options=[
                        discord.SelectOption(label="Yes", value="Yes"),
                        discord.SelectOption(label="No", value="No"),
                    ],
                    min_values=1 if required else 0,
                    max_values=1,
                    required=required,
                )
            elif (
                MODAL_SELECTS_SUPPORTED
                and question_type == "choice"
                and not question.get("allow_other")
            ):
                component = discord.ui.Select(
                    placeholder="Choose an answer",
                    options=[
                        discord.SelectOption(
                            label=truncate(choice, 100),
                            value=str(choice)[:100],
                        )
                        for choice in question.get("choices", [])[:25]
                    ],
                    min_values=1 if required else 0,
                    max_values=1,
                    required=required,
                )
            else:
                if question_type == "boolean":
                    placeholder = "Enter Yes or No"
                    max_length = 5
                    style = discord.TextStyle.short
                elif question_type == "choice":
                    choices = ", ".join(
                        str(choice)[:100] for choice in question.get("choices", [])
                    )
                    placeholder = truncate(f"Choose: {choices}", 100)
                    max_length = 100
                    style = discord.TextStyle.short
                component = discord.ui.TextInput(
                    label=None if MODAL_SELECTS_SUPPORTED else question_label,
                    style=style,
                    required=required,
                    placeholder=placeholder,
                    max_length=max_length,
                )

            if MODAL_SELECTS_SUPPORTED:
                self.add_item(
                    discord.ui.Label(
                        text=question_label,
                        component=component,
                    )
                )
            else:
                self.add_item(component)
            self.inputs.append((question, component))

    @staticmethod
    def _input_value(component: discord.ui.Item) -> str:
        if isinstance(component, discord.ui.Select):
            return str(component.values[0]).strip() if component.values else ""
        return str(getattr(component, "value", "") or "").strip()

    async def on_submit(self, interaction: discord.Interaction) -> None:
        answers: List[Dict[str, str]] = []
        for question, component in self.inputs:
            question_type = str(question.get("type") or "text").lower()
            value = self._input_value(component)
            if not value:
                value = "Skipped"
            elif question_type == "boolean":
                lowered = value.lower()
                if lowered in {"yes", "y", "true", "1"}:
                    value = "Yes"
                elif lowered in {"no", "n", "false", "0"}:
                    value = "No"
                else:
                    await interaction.response.send_message(
                        f"`{question.get('text', 'Question')}` must be answered with Yes or No.",
                        ephemeral=True,
                    )
                    return
            elif question_type == "choice":
                choices = [str(choice)[:100] for choice in question.get("choices", [])]
                matched = next(
                    (choice for choice in choices if choice.casefold() == value.casefold()),
                    None,
                )
                if matched is not None:
                    value = matched
                elif not question.get("allow_other"):
                    await interaction.response.send_message(
                        f"`{question.get('text', 'Question')}` must match one of its choices.",
                        ephemeral=True,
                    )
                    return
            answers.append(
                {
                    "question": str(question.get("text") or "Question"),
                    "type": question_type,
                    "answer": value,
                }
            )
        await self.cog._submit_modal_application(
            interaction,
            self.guild_id,
            self.application,
            answers,
            bypass=self.bypass,
        )


class ApplicationModalLaunchView(discord.ui.View):
    """Offer a native application modal from a prefix command."""

    def __init__(
        self,
        cog: "Applications",
        author_id: int,
        application: str,
        *,
        bypass: bool = False,
    ) -> None:
        super().__init__(timeout=300.0)
        self.cog = cog
        self.author_id = author_id
        self.application = application
        self.bypass = bypass
        button = discord.ui.Button(
            label="Open Application Form",
            style=discord.ButtonStyle.primary,
        )
        button.callback = self._open_callback
        self.add_item(button)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user and interaction.user.id == self.author_id:
            return True
        await interaction.response.send_message(
            "This application form is not for you.",
            ephemeral=True,
        )
        return False

    async def _open_callback(self, interaction: discord.Interaction) -> None:
        await self.cog._start_application_from_interaction(
            interaction,
            self.application,
            bypass=self.bypass,
        )


class ReviewView(discord.ui.View):
    def __init__(
        self,
        cog: "Applications",
        guild_id: int,
        application: str,
        response_id: str,
        *,
        disabled: bool = False,
        voting_enabled: bool = True,
    ) -> None:
        super().__init__(timeout=None)
        self.cog = cog
        self.guild_id = guild_id
        self.application = application
        self.response_id = response_id

        accept = discord.ui.Button(
            label="Accept",
            style=discord.ButtonStyle.success,
            custom_id=f"applications:review:{guild_id}:{application}:{response_id}:accept",
            disabled=disabled,
        )
        accept.callback = self._accept_callback
        self.add_item(accept)

        deny = discord.ui.Button(
            label="Deny",
            style=discord.ButtonStyle.danger,
            custom_id=f"applications:review:{guild_id}:{application}:{response_id}:deny",
            disabled=disabled,
        )
        deny.callback = self._deny_callback
        self.add_item(deny)

        if voting_enabled:
            upvote = discord.ui.Button(
                label="Upvote",
                style=discord.ButtonStyle.secondary,
                custom_id=f"applications:vote:{guild_id}:{application}:{response_id}:up",
                disabled=disabled,
            )
            upvote.callback = self._upvote_callback
            self.add_item(upvote)

            neutral = discord.ui.Button(
                label="Neutral",
                style=discord.ButtonStyle.secondary,
                custom_id=f"applications:vote:{guild_id}:{application}:{response_id}:neutral",
                disabled=disabled,
            )
            neutral.callback = self._neutral_callback
            self.add_item(neutral)

            downvote = discord.ui.Button(
                label="Downvote",
                style=discord.ButtonStyle.secondary,
                custom_id=f"applications:vote:{guild_id}:{application}:{response_id}:down",
                disabled=disabled,
            )
            downvote.callback = self._downvote_callback
            self.add_item(downvote)

    async def _accept_callback(self, interaction: discord.Interaction) -> None:
        await interaction.response.send_modal(
            DecisionModal(
                self.cog,
                self.guild_id,
                self.application,
                self.response_id,
                "accepted",
            )
        )

    async def _deny_callback(self, interaction: discord.Interaction) -> None:
        await interaction.response.send_modal(
            DecisionModal(
                self.cog,
                self.guild_id,
                self.application,
                self.response_id,
                "denied",
            )
        )

    async def _upvote_callback(self, interaction: discord.Interaction) -> None:
        await self.cog._record_vote(
            interaction, self.guild_id, self.application, self.response_id, "up"
        )

    async def _neutral_callback(self, interaction: discord.Interaction) -> None:
        await self.cog._record_vote(
            interaction, self.guild_id, self.application, self.response_id, "neutral"
        )

    async def _downvote_callback(self, interaction: discord.Interaction) -> None:
        await self.cog._record_vote(
            interaction, self.guild_id, self.application, self.response_id, "down"
        )


class ApplicationPanelView(discord.ui.View):
    def __init__(
        self,
        cog: "Applications",
        guild_id: int,
        applications: Sequence[ApplicationDict],
        *,
        mode: str = "buttons",
        panel_id: Optional[str] = None,
    ) -> None:
        super().__init__(timeout=None)
        self.cog = cog
        self.guild_id = guild_id
        self.applications = list(applications)
        self.mode = mode
        self.panel_id = panel_id or make_id(10)

        if mode == "select" and len(self.applications) > 1:
            options = [
                discord.SelectOption(
                    label=truncate(app["name"], 100),
                    value=app["key"],
                    description=truncate(app.get("description", ""), 100),
                )
                for app in self.applications[:25]
            ]
            select = discord.ui.Select(
                placeholder="Choose an application",
                options=options,
                custom_id=f"applications:select:{guild_id}:{self.panel_id}",
            )
            select.callback = self._select_callback
            self.add_item(select)
            return

        for app in self.applications[:25]:
            button = discord.ui.Button(
                label=truncate(app.get("button_label") or app["name"], 80),
                style=self.cog._button_style(app.get("button_style")),
                emoji=app.get("button_emoji") or None,
                custom_id=f"applications:apply:{guild_id}:{app['key']}",
            )
            button.callback = self._make_button_callback(app["key"])
            self.add_item(button)

    async def _select_callback(self, interaction: discord.Interaction) -> None:
        values = (interaction.data or {}).get("values") or []
        if not values:
            await interaction.response.send_message("No application was selected.", ephemeral=True)
            return
        await self.cog._start_application_from_interaction(interaction, str(values[0]))

    def _make_button_callback(self, application: str):
        async def callback(interaction: discord.Interaction) -> None:
            await self.cog._start_application_from_interaction(interaction, application)

        return callback


class PollView(discord.ui.View):
    def __init__(
        self,
        cog: "Applications",
        guild_id: int,
        poll_id: str,
        options: Sequence[str],
        *,
        disabled: bool = False,
    ) -> None:
        super().__init__(timeout=None)
        self.cog = cog
        self.guild_id = guild_id
        self.poll_id = poll_id
        for idx, option in enumerate(options[:25]):
            button = discord.ui.Button(
                label=truncate(option, 80),
                style=discord.ButtonStyle.secondary,
                custom_id=f"applications:poll:{guild_id}:{poll_id}:{idx}",
                disabled=disabled,
            )
            button.callback = self._make_vote_callback(idx)
            self.add_item(button)

    def _make_vote_callback(self, index: int):
        async def callback(interaction: discord.Interaction) -> None:
            await self.cog._vote_poll(interaction, self.guild_id, self.poll_id, index)

        return callback


class Applications(commands.Cog):
    """Configurable application forms with panels, reviews, role actions, exports, and polls."""

    DEFAULT_COLOR = 0x5865F2
    MAX_QUESTIONS = 100
    MAX_CHOICES = 25
    QUESTION_TIMEOUT = 600.0
    VALID_QUESTION_TYPES = ("text", "boolean", "choice", "attachment")
    VALID_BUTTON_STYLES = ("green", "red", "gray", "blurple")
    VALID_NOTIFICATION_ROLE_TARGETS = ("channel", "thread", "both")
    ROLE_LISTS = {
        "manager": "manager",
        "whitelist": "whitelist",
        "allowlist": "whitelist",
        "blacklist": "blacklist",
        "blocklist": "blacklist",
        "apply": "apply_add",
        "submit": "submit_add",
        "accept": "accept_add",
        "acceptremove": "accept_remove",
        "deny": "deny_add",
        "denyremove": "deny_remove",
    }

    def __init__(self, bot: Red) -> None:
        self.bot = bot
        self.config = Config.get_conf(self, identifier=2026050901, force_registration=True)
        self.config.register_guild(applications={}, panels={}, polls={})

    async def cog_load(self) -> None:
        await self._restore_persistent_views()

    async def red_delete_data_for_user(self, *, requester: str, user_id: int) -> None:
        all_guilds = await self.config.all_guilds()
        for guild_id, data in all_guilds.items():
            async with self.config.guild_from_id(guild_id).applications() as apps:
                for app in apps.values():
                    for response in app.get("responses", []):
                        if response.get("user_id") == user_id:
                            response["user_id"] = None
                        if response.get("reviewed_by") == user_id:
                            response["reviewed_by"] = None
                        votes = response.setdefault("votes", {"up": [], "neutral": [], "down": []})
                        for key in ("up", "neutral", "down"):
                            votes[key] = [vote for vote in votes.get(key, []) if vote != user_id]
            async with self.config.guild_from_id(guild_id).polls() as polls:
                for poll in polls.values():
                    votes = poll.setdefault("votes", {})
                    for voters in votes.values():
                        if user_id in voters:
                            voters.remove(user_id)

    @staticmethod
    def _default_roles() -> Dict[str, List[int]]:
        return {
            "manager": [],
            "whitelist": [],
            "blacklist": [],
            "apply_add": [],
            "submit_add": [],
            "accept_add": [],
            "accept_remove": [],
            "deny_add": [],
            "deny_remove": [],
        }

    @classmethod
    def _new_application(
        cls,
        *,
        name: str,
        description: str,
        channel_id: int,
        creator_id: int,
    ) -> ApplicationDict:
        key = app_key(name)
        return {
            "key": key,
            "name": name.strip(),
            "description": description.strip(),
            "channel_id": channel_id,
            "created_by": creator_id,
            "created_at": utc_ts(),
            "open": True,
            "color": cls.DEFAULT_COLOR,
            "cooldown_minutes": 0,
            "allow_multiple_pending": False,
            "form_mode": "dm",
            "panel_message": "Click below to apply for **{application}**.",
            "button_label": "Apply",
            "button_style": "green",
            "button_emoji": None,
            "thread_enabled": True,
            "thread_name": "{application} - {user}",
            "notification_enabled": True,
            "notification_message": (
                "New application submitted by {user_mention} for **{application}**."
            ),
            "notification_channel_ids": [],
            "notification_role_ids": [],
            "notification_role_target": "channel",
            "completion_message": (
                "Your application for **{application}** was submitted.\n"
                "Response ID: `{response_id}`"
            ),
            "accept_message": "Your application for **{application}** was accepted.",
            "deny_message": (
                "Your application for **{application}** was denied."
                "\nReason: {reason}"
            ),
            "questions": [],
            "responses": [],
            "roles": cls._default_roles(),
            "voting": {"enabled": True, "threshold": 0},
        }

    @classmethod
    def _migrate_application(cls, key: str, app: ApplicationDict) -> ApplicationDict:
        app.setdefault("key", key)
        app.setdefault("name", key)
        app.setdefault("description", "")
        app.setdefault("channel_id", None)
        app.setdefault("created_by", None)
        app.setdefault("created_at", utc_ts())
        app.setdefault("open", True)
        app.setdefault("color", cls.DEFAULT_COLOR)
        app.setdefault("cooldown_minutes", 0)
        app.setdefault("allow_multiple_pending", False)
        if app.get("form_mode") not in {"dm", "modal"}:
            app["form_mode"] = "dm"
        app.setdefault("panel_message", "Click below to apply for **{application}**.")
        app.setdefault("button_label", "Apply")
        app.setdefault("button_style", "green")
        app.setdefault("button_emoji", None)
        app.setdefault("thread_enabled", True)
        app.setdefault("thread_name", "{application} - {user}")
        app.setdefault(
            "notification_message",
            "New application submitted by {user_mention} for **{application}**.",
        )
        app.setdefault("notification_enabled", True)
        app.setdefault("notification_channel_ids", [])
        app.setdefault("notification_role_ids", [])
        app["notification_role_target"] = cls._notification_role_target(app)
        app.setdefault(
            "completion_message",
            "Your application for **{application}** was submitted.\nResponse ID: `{response_id}`",
        )
        app.setdefault("accept_message", "Your application for **{application}** was accepted.")
        app.setdefault(
            "deny_message",
            "Your application for **{application}** was denied.\nReason: {reason}",
        )
        app.setdefault("questions", [])
        app.setdefault("responses", [])
        roles = app.setdefault("roles", {})
        for role_key, value in cls._default_roles().items():
            roles.setdefault(role_key, value)
        app.setdefault("voting", {"enabled": True, "threshold": 0})
        for response in app.get("responses", []):
            response.setdefault("votes", {"up": [], "neutral": [], "down": []})
            response.setdefault("status", "pending")
        return app

    @classmethod
    def _notification_role_target(cls, app: ApplicationDict) -> str:
        target = str(app.get("notification_role_target") or "channel").strip().lower()
        aliases = {
            "channels": "channel",
            "response": "channel",
            "responses": "channel",
            "review": "channel",
            "reviews": "channel",
            "threads": "thread",
            "reviewthread": "thread",
            "reviewthreads": "thread",
            "all": "both",
        }
        target = aliases.get(target, target)
        return target if target in cls.VALID_NOTIFICATION_ROLE_TARGETS else "channel"

    async def _restore_persistent_views(self) -> None:
        all_guilds = await self.config.all_guilds()
        for guild_id, data in all_guilds.items():
            apps = data.get("applications", {})
            migrated_apps: Dict[str, ApplicationDict] = {}
            for key, app in apps.items():
                migrated_apps[key] = self._migrate_application(key, app)

            for panel in data.get("panels", {}).values():
                app_list = [
                    migrated_apps[key]
                    for key in panel.get("applications", [])
                    if key in migrated_apps
                ]
                if app_list:
                    self.bot.add_view(
                        ApplicationPanelView(
                            self,
                            guild_id,
                            app_list,
                            mode=panel.get("mode", "buttons"),
                            panel_id=panel.get("id"),
                        )
                    )

            for key, app in migrated_apps.items():
                for response in app.get("responses", []):
                    if response.get("status") == "pending":
                        self.bot.add_view(
                            ReviewView(
                                self,
                                guild_id,
                                key,
                                response.get("id", "unknown"),
                                voting_enabled=bool(
                                    app.get("voting", {}).get("enabled", True)
                                ),
                            )
                        )

            for poll_id, poll in data.get("polls", {}).items():
                self.bot.add_view(
                    PollView(
                        self,
                        guild_id,
                        poll_id,
                        poll.get("options", []),
                        disabled=poll.get("closed", False),
                    )
                )

            if migrated_apps != apps:
                await self.config.guild_from_id(guild_id).applications.set(migrated_apps)

    @staticmethod
    def _button_style(style: Optional[str]) -> discord.ButtonStyle:
        style = (style or "green").lower()
        return {
            "green": discord.ButtonStyle.success,
            "success": discord.ButtonStyle.success,
            "red": discord.ButtonStyle.danger,
            "danger": discord.ButtonStyle.danger,
            "gray": discord.ButtonStyle.secondary,
            "grey": discord.ButtonStyle.secondary,
            "secondary": discord.ButtonStyle.secondary,
            "blurple": discord.ButtonStyle.primary,
            "primary": discord.ButtonStyle.primary,
        }.get(style, discord.ButtonStyle.success)

    @staticmethod
    def _status_color(app: ApplicationDict, status: str) -> discord.Color:
        if status == "accepted":
            return discord.Color.green()
        if status == "denied":
            return discord.Color.red()
        return discord.Color(int(app.get("color", Applications.DEFAULT_COLOR)))

    async def _get_apps(self, guild_id: int) -> Dict[str, ApplicationDict]:
        apps = await self.config.guild_from_id(guild_id).applications()
        migrated = {
            key: self._migrate_application(key, app)
            for key, app in apps.items()
        }
        if migrated != apps:
            await self.config.guild_from_id(guild_id).applications.set(migrated)
        return migrated

    async def _get_app(self, guild_id: int, name: str) -> Tuple[str, ApplicationDict]:
        apps = await self._get_apps(guild_id)
        key = app_key(name)
        if key in apps:
            return key, apps[key]
        lowered = name.strip().lower()
        for possible_key, app in apps.items():
            if app.get("name", "").lower() == lowered:
                return possible_key, app
        raise commands.UserFeedbackCheckFailure("That application does not exist.")

    async def _save_app(self, guild_id: int, app: ApplicationDict) -> None:
        key = app["key"]
        async with self.config.guild_from_id(guild_id).applications() as apps:
            apps[key] = app

    @staticmethod
    def _find_response(app: ApplicationDict, response_id: str) -> ResponseDict:
        response_id = response_id.lower()
        for response in app.get("responses", []):
            rid = str(response.get("id", "")).lower()
            if rid == response_id or rid.startswith(response_id):
                return response
        raise commands.UserFeedbackCheckFailure("That response does not exist.")

    @staticmethod
    def _member_has_any(member: discord.Member, role_ids: Iterable[int]) -> bool:
        member_role_ids = {role.id for role in member.roles}
        return any(role_id in member_role_ids for role_id in role_ids)

    async def _is_setup_manager(self, member: discord.Member) -> bool:
        if member.guild_permissions.manage_guild or member.guild_permissions.administrator:
            return True
        return await self.bot.is_owner(member)

    async def _is_app_manager(self, member: discord.Member, app: ApplicationDict) -> bool:
        if await self._is_setup_manager(member):
            return True
        return self._member_has_any(member, app.get("roles", {}).get("manager", []))

    async def _require_setup_manager(self, ctx: commands.GuildContext) -> None:
        if not isinstance(ctx.author, discord.Member) or not await self._is_setup_manager(ctx.author):
            raise commands.UserFeedbackCheckFailure(
                "You need `Manage Server` or bot owner permissions to configure applications."
            )

    async def _require_app_manager(
        self,
        ctx: commands.GuildContext,
        app: ApplicationDict,
    ) -> None:
        if not isinstance(ctx.author, discord.Member) or not await self._is_app_manager(ctx.author, app):
            raise commands.UserFeedbackCheckFailure(
                "You need `Manage Server` or an application manager role to do that."
            )

    async def _can_member_apply(
        self,
        member: discord.Member,
        app: ApplicationDict,
        *,
        bypass: bool = False,
    ) -> Optional[str]:
        if bypass:
            return None
        if not app.get("open", True):
            return "This application is currently closed."
        questions = app.get("questions", [])
        if not questions:
            return "This application does not have any questions yet."

        roles = app.get("roles", {})
        whitelist = roles.get("whitelist", [])
        blacklist = roles.get("blacklist", [])
        if whitelist and not self._member_has_any(member, whitelist):
            return "You do not have a required role for this application."
        if blacklist and self._member_has_any(member, blacklist):
            return "One of your roles is blocked from using this application."

        if not app.get("allow_multiple_pending", False):
            for response in app.get("responses", []):
                if response.get("user_id") == member.id and response.get("status") == "pending":
                    return "You already have a pending response for this application."

        cooldown = int(app.get("cooldown_minutes") or 0)
        if cooldown > 0:
            latest = 0
            for response in app.get("responses", []):
                if response.get("user_id") == member.id:
                    latest = max(latest, int(response.get("created_at") or 0))
            remaining = latest + cooldown * 60 - utc_ts()
            if remaining > 0:
                minutes = max(1, remaining // 60)
                return f"You can apply again in about {minutes} minute(s)."
        return None

    async def _apply_role_action(
        self,
        member: Optional[discord.Member],
        app: ApplicationDict,
        role_list: str,
    ) -> None:
        if member is None:
            return
        roles = [
            role
            for role_id in app.get("roles", {}).get(role_list, [])
            if (role := member.guild.get_role(role_id))
        ]
        if not roles:
            return
        with contextlib.suppress(discord.HTTPException):
            if role_list.endswith("_remove"):
                await member.remove_roles(*roles, reason=f"[Applications] {role_list}")
            else:
                await member.add_roles(*roles, reason=f"[Applications] {role_list}")

    @staticmethod
    def _render_template(
        template: str,
        *,
        guild: Optional[discord.Guild],
        member: Optional[discord.abc.User],
        app: ApplicationDict,
        response: Optional[ResponseDict] = None,
        reviewer: Optional[discord.abc.User] = None,
        reason: str = "",
    ) -> str:
        response = response or {}
        replacements = {
            "application": app.get("name", ""),
            "application_key": app.get("key", ""),
            "description": app.get("description", ""),
            "server": guild.name if guild else "",
            "guild": guild.name if guild else "",
            "user": str(member) if member else "",
            "user_name": getattr(member, "display_name", str(member) if member else ""),
            "user_mention": getattr(member, "mention", ""),
            "user_id": str(getattr(member, "id", "")),
            "response_id": str(response.get("id", "")),
            "status": str(response.get("status", "")),
            "reviewer": str(reviewer) if reviewer else "",
            "reviewer_mention": getattr(reviewer, "mention", ""),
            "reason": reason or "No reason provided.",
        }
        rendered = template
        for key, value in replacements.items():
            rendered = rendered.replace("{" + key + "}", value)
        return rendered

    def _application_embed(self, guild: discord.Guild, app: ApplicationDict) -> discord.Embed:
        channel = guild.get_channel(app.get("channel_id"))
        questions = app.get("questions", [])
        responses = app.get("responses", [])
        pending = sum(1 for response in responses if response.get("status") == "pending")
        accepted = sum(1 for response in responses if response.get("status") == "accepted")
        denied = sum(1 for response in responses if response.get("status") == "denied")
        embed = discord.Embed(
            title=app.get("name", "Application"),
            description=app.get("description", ""),
            color=discord.Color(int(app.get("color", self.DEFAULT_COLOR))),
            timestamp=discord.utils.utcnow(),
        )
        embed.add_field(name="Status", value="open" if app.get("open", True) else "closed")
        embed.add_field(name="Response Channel", value=channel.mention if channel else "Not set")
        embed.add_field(name="Questions", value=str(len(questions)))
        embed.add_field(name="Cooldown", value=f"{int(app.get('cooldown_minutes') or 0)} minute(s)")
        embed.add_field(
            name="Responses",
            value=f"Pending: {pending}\nAccepted: {accepted}\nDenied: {denied}",
            inline=False,
        )
        embed.add_field(
            name="Features",
            value=(
                f"Form mode: {str(app.get('form_mode', 'dm')).upper()}\n"
                f"Threads: {bool_text(bool(app.get('thread_enabled', True)))}\n"
                f"Notifications: {bool_text(bool(app.get('notification_enabled', True)))}\n"
                f"Notification role pings: {self._notification_role_target(app)}\n"
                f"Review voting: {bool_text(bool(app.get('voting', {}).get('enabled', True)))}"
            ),
            inline=False,
        )
        embed.set_footer(text=f"Key: {app.get('key')}")
        return embed

    def _response_embed(
        self,
        guild: discord.Guild,
        app: ApplicationDict,
        response: ResponseDict,
    ) -> discord.Embed:
        user_id = response.get("user_id")
        member = guild.get_member(user_id) if user_id else None
        user_text = member.mention if member else f"`{user_id}`"
        status = response.get("status", "pending")
        votes = response.setdefault("votes", {"up": [], "neutral": [], "down": []})
        embed = discord.Embed(
            title=f"{app.get('name', 'Application')} Response",
            description=(
                f"**Applicant:** {user_text}\n"
                f"**Status:** {status}\n"
                f"**Response ID:** `{response.get('id')}`\n"
                f"**Submitted:** <t:{int(response.get('created_at') or utc_ts())}:F>\n"
                f"**Votes:** +{len(votes.get('up', []))} / "
                f"0 {len(votes.get('neutral', []))} / -{len(votes.get('down', []))}"
            ),
            color=self._status_color(app, status),
            timestamp=discord.utils.utcnow(),
        )
        if member:
            embed.set_author(name=str(member), icon_url=member.display_avatar.url)
        for idx, answer in enumerate(response.get("answers", [])[:25], start=1):
            value = answer.get("answer", "")
            if answer.get("type") == "attachment" and answer.get("url"):
                value = f"{value}\n{answer.get('url')}"
            embed.add_field(
                name=f"{idx}. {truncate(answer.get('question', ''), 240)}",
                value=truncate(value or "No answer", 1024),
                inline=False,
            )
        if response.get("reviewed_by"):
            reviewer = guild.get_member(int(response["reviewed_by"]))
            reviewer_text = reviewer.mention if reviewer else f"`{response['reviewed_by']}`"
            embed.add_field(
                name="Review",
                value=(
                    f"Reviewer: {reviewer_text}\n"
                    f"Reviewed: <t:{int(response.get('reviewed_at') or utc_ts())}:F>\n"
                    f"Reason: {truncate(response.get('review_reason') or 'No reason provided.', 800)}"
                ),
                inline=False,
            )
        return embed

    def _panel_embed(
        self,
        guild: discord.Guild,
        applications: Sequence[ApplicationDict],
        *,
        title: str,
        description: str,
    ) -> discord.Embed:
        embed = discord.Embed(
            title=title,
            description=description,
            color=discord.Color(self.DEFAULT_COLOR),
            timestamp=discord.utils.utcnow(),
        )
        for app in applications[:25]:
            embed.add_field(
                name=app.get("name", app.get("key", "Application")),
                value=truncate(app.get("description", ""), 1024),
                inline=False,
            )
        embed.set_footer(text=guild.name)
        return embed

    @staticmethod
    def _modal_form_error(app: ApplicationDict) -> Optional[str]:
        questions = app.get("questions", [])
        if not questions:
            return "Modal forms need at least one question."
        if len(questions) > 5:
            return "Modal forms can contain at most 5 questions."
        if any(
            str(question.get("type") or "text").lower() == "attachment"
            for question in questions
        ):
            return "Modal forms cannot contain attachment questions."
        if any(
            str(question.get("type") or "text").lower() == "choice"
            and not question.get("choices")
            for question in questions
        ):
            return "Every modal choice question needs at least one configured choice."
        return None

    def _application_intro_embed(
        self,
        guild: discord.Guild,
        app: ApplicationDict,
    ) -> discord.Embed:
        return discord.Embed(
            title=app.get("name", "Application"),
            description=(
                f"{app.get('description', '')}\n\n"
                "Answer each question in this DM. You can type `cancel` on text prompts."
            ),
            color=discord.Color(int(app.get("color", self.DEFAULT_COLOR))),
        ).set_footer(text=guild.name)

    async def _send_application_intro(
        self,
        guild: discord.Guild,
        member: discord.Member,
        app: ApplicationDict,
    ) -> discord.Message:
        return await member.send(embed=self._application_intro_embed(guild, app))

    async def _ask_question(
        self,
        member: discord.Member,
        guild: discord.Guild,
        app: ApplicationDict,
        question: QuestionDict,
        index: int,
    ) -> Optional[Dict[str, str]]:
        qtype = question.get("type", "text").lower()
        prompt = discord.Embed(
            title=f"{app.get('name')} - Question {index}",
            description=question.get("text", ""),
            color=discord.Color(int(app.get("color", self.DEFAULT_COLOR))),
        )
        prompt.set_footer(text="Reply `cancel` to stop. Reply `skip` for optional text prompts.")
        required = bool(question.get("required", True))

        if qtype == "boolean":
            view = QuestionBooleanView(member.id, required=required, timeout=self.QUESTION_TIMEOUT)
            message = await member.send(embed=prompt, view=view)
            timed_out = await view.wait()
            with contextlib.suppress(discord.HTTPException):
                await message.edit(view=None)
            if timed_out:
                await member.send("Application timed out while waiting for your answer.")
                return None
            if view.cancelled:
                await member.send("Application cancelled.")
                return None
            if view.skipped:
                return {"question": question["text"], "type": qtype, "answer": "Skipped"}
            return {"question": question["text"], "type": qtype, "answer": view.answer or "No"}

        if qtype == "choice":
            if not question.get("choices"):
                return {"question": question["text"], "type": qtype, "answer": "No choices configured"}
            view = QuestionChoiceView(member.id, question, timeout=self.QUESTION_TIMEOUT)
            message = await member.send(embed=prompt, view=view)
            timed_out = await view.wait()
            with contextlib.suppress(discord.HTTPException):
                await message.edit(view=None)
            if timed_out:
                await member.send("Application timed out while waiting for your answer.")
                return None
            if view.cancelled:
                await member.send("Application cancelled.")
                return None
            if view.skipped:
                return {"question": question["text"], "type": qtype, "answer": "Skipped"}
            if view.answer == "__other__":
                await member.send("Type your custom answer for this question.")
                custom = await self._wait_for_dm(member, attachment=False)
                if custom is None:
                    return None
                return {"question": question["text"], "type": qtype, "answer": custom}
            return {"question": question["text"], "type": qtype, "answer": view.answer or ""}

        await member.send(embed=prompt)
        answer = await self._wait_for_dm(member, attachment=(qtype == "attachment"))
        if answer is None:
            return None
        if answer.lower() == "cancel":
            await member.send("Application cancelled.")
            return None
        if answer.lower() == "skip" and not required:
            answer = "Skipped"
        elif answer.lower() == "skip" and required:
            await member.send("That question is required, so `skip` was stored as your answer.")
        return {"question": question["text"], "type": qtype, "answer": answer}

    async def _wait_for_dm(self, member: discord.Member, *, attachment: bool) -> Optional[str]:
        def check(message: discord.Message) -> bool:
            return (
                message.author.id == member.id
                and isinstance(message.channel, discord.DMChannel)
            )

        try:
            message = await self.bot.wait_for("message", check=check, timeout=self.QUESTION_TIMEOUT)
        except asyncio.TimeoutError:
            with contextlib.suppress(discord.HTTPException):
                await member.send("Application timed out while waiting for your answer.")
            return None

        if attachment:
            if message.content.lower().strip() == "cancel":
                return "cancel"
            if message.attachments:
                return message.attachments[0].url
            if message.content.strip():
                return message.content.strip()
            await member.send("No attachment or link was found for that answer.")
            return None
        return message.content.strip()

    async def _start_application_from_context(
        self,
        ctx: commands.GuildContext,
        name: str,
        *,
        member: Optional[discord.Member] = None,
        bypass: bool = False,
    ) -> None:
        if ctx.guild is None:
            raise commands.UserFeedbackCheckFailure("Applications can only be used in a server.")
        target = member or ctx.author
        if not isinstance(target, discord.Member):
            raise commands.UserFeedbackCheckFailure("Could not resolve that member.")
        key, app = await self._get_app(ctx.guild.id, name)
        reason = await self._can_member_apply(target, app, bypass=bypass)
        if reason:
            raise commands.UserFeedbackCheckFailure(reason)
        if app.get("form_mode", "dm") == "modal":
            modal_error = self._modal_form_error(app)
            if modal_error:
                raise commands.UserFeedbackCheckFailure(modal_error)
            context_interaction = getattr(ctx, "interaction", None)
            if context_interaction is not None and target.id == ctx.author.id:
                await context_interaction.response.send_modal(
                    ApplicationFormModal(
                        self,
                        ctx.guild.id,
                        key,
                        app,
                        bypass=bypass,
                    )
                )
                return
            await ctx.send(
                f"{target.mention}, click below to open the **{app['name']}** form.",
                view=ApplicationModalLaunchView(
                    self,
                    target.id,
                    key,
                    bypass=bypass,
                ),
                allowed_mentions=discord.AllowedMentions(users=True),
            )
            return
        try:
            await self._send_application_intro(ctx.guild, target, app)
        except discord.HTTPException:
            if target.id == ctx.author.id:
                failure = (
                    "I couldn't send you a DM. Enable direct messages from server "
                    "members and try again."
                )
            else:
                failure = (
                    f"I couldn't DM {target.mention}. They need to enable direct "
                    "messages from server members and try again."
                )
            await ctx.send(
                failure,
                allowed_mentions=discord.AllowedMentions(users=True),
            )
            return
        await ctx.send(
            f"I sent the **{app['name']}** application to {target.mention}'s DMs.",
            allowed_mentions=discord.AllowedMentions(users=True),
        )
        await self._run_application_flow(
            ctx.guild,
            target,
            key,
            app,
            bypass=bypass,
            intro_sent=True,
        )

    async def _start_application_from_interaction(
        self,
        interaction: discord.Interaction,
        application: str,
        *,
        bypass: bool = False,
    ) -> None:
        if interaction.guild is None or not isinstance(interaction.user, discord.Member):
            await interaction.response.send_message(
                "Applications can only be started from a server.",
                ephemeral=True,
            )
            return
        try:
            key, app = await self._get_app(interaction.guild.id, application)
        except commands.UserFeedbackCheckFailure as exc:
            await interaction.response.send_message(str(exc), ephemeral=True)
            return
        reason = await self._can_member_apply(interaction.user, app, bypass=bypass)
        if reason:
            await interaction.response.send_message(reason, ephemeral=True)
            return
        if app.get("form_mode", "dm") == "modal":
            modal_error = self._modal_form_error(app)
            if modal_error:
                await interaction.response.send_message(modal_error, ephemeral=True)
                return
            await interaction.response.send_modal(
                ApplicationFormModal(
                    self,
                    interaction.guild.id,
                    key,
                    app,
                    bypass=bypass,
                )
            )
            return
        try:
            await self._send_application_intro(interaction.guild, interaction.user, app)
        except discord.HTTPException:
            await interaction.response.send_message(
                "I couldn't send you a DM. Enable direct messages from server members "
                "and try again.",
                ephemeral=True,
            )
            return
        await interaction.response.send_message(
            f"I sent the **{app['name']}** application to your DMs.",
            ephemeral=True,
        )
        await self._run_application_flow(
            interaction.guild,
            interaction.user,
            key,
            app,
            bypass=bypass,
            intro_sent=True,
        )

    async def _run_application_flow(
        self,
        guild: discord.Guild,
        member: discord.Member,
        key: str,
        app: ApplicationDict,
        *,
        bypass: bool = False,
        intro_sent: bool = False,
    ) -> None:
        if not intro_sent:
            try:
                await self._send_application_intro(guild, member, app)
            except discord.HTTPException:
                return

        if not bypass:
            await self._apply_role_action(member, app, "apply_add")

        answers: List[Dict[str, str]] = []
        for idx, question in enumerate(app.get("questions", []), start=1):
            answer = await self._ask_question(member, guild, app, question, idx)
            if answer is None:
                return
            answers.append(answer)
            with contextlib.suppress(discord.HTTPException):
                await member.send(f"Stored answer for question {idx}.")

        try:
            response, latest_app = await self._submit_application_response(
                guild,
                member,
                key,
                answers,
            )
        except (commands.CommandError, discord.HTTPException) as exc:
            with contextlib.suppress(discord.HTTPException):
                await member.send(
                    str(exc) or "I could not post your application for staff review."
                )
            return

        completion = self._render_template(
            latest_app.get("completion_message", ""),
            guild=guild,
            member=member,
            app=latest_app,
            response=response,
        )
        with contextlib.suppress(discord.HTTPException):
            await member.send(completion)

    async def _submit_modal_application(
        self,
        interaction: discord.Interaction,
        guild_id: int,
        application: str,
        answers: Sequence[Dict[str, str]],
        *,
        bypass: bool = False,
    ) -> None:
        guild = interaction.guild or self.bot.get_guild(guild_id)
        if guild is None or not isinstance(interaction.user, discord.Member):
            await interaction.response.send_message(
                "Applications can only be submitted from a server.",
                ephemeral=True,
            )
            return
        await interaction.response.defer(ephemeral=True, thinking=True)
        try:
            key, app = await self._get_app(guild_id, application)
            reason = await self._can_member_apply(interaction.user, app, bypass=bypass)
            if reason:
                raise commands.CommandError(reason)
            modal_error = self._modal_form_error(app)
            if modal_error:
                raise commands.CommandError(modal_error)
            response, latest_app = await self._submit_application_response(
                guild,
                interaction.user,
                key,
                answers,
                apply_role=not bypass,
            )
        except (commands.CommandError, discord.HTTPException) as exc:
            await interaction.followup.send(
                str(exc) or "I could not post your application for staff review.",
                ephemeral=True,
            )
            return

        completion = self._render_template(
            latest_app.get("completion_message", ""),
            guild=guild,
            member=interaction.user,
            app=latest_app,
            response=response,
        )
        await interaction.followup.send(
            truncate(completion or "Your application was submitted.", 2000),
            ephemeral=True,
        )
        if completion:
            with contextlib.suppress(discord.HTTPException):
                await interaction.user.send(completion)

    async def _submit_application_response(
        self,
        guild: discord.Guild,
        member: discord.Member,
        key: str,
        answers: Sequence[Dict[str, str]],
        *,
        apply_role: bool = False,
    ) -> Tuple[ResponseDict, ApplicationDict]:
        latest_app = (await self._get_apps(guild.id)).get(key)
        if latest_app is None:
            raise commands.CommandError("That application no longer exists.")
        channel = guild.get_channel(latest_app.get("channel_id"))
        if not isinstance(channel, discord.TextChannel):
            raise commands.CommandError(
                "This application is missing a valid response channel."
            )

        if apply_role:
            await self._apply_role_action(member, latest_app, "apply_add")

        response: ResponseDict = {
            "id": make_id(),
            "user_id": member.id,
            "answers": list(answers),
            "status": "pending",
            "created_at": utc_ts(),
            "reviewed_by": None,
            "reviewed_at": None,
            "review_reason": "",
            "message_id": None,
            "channel_id": channel.id,
            "thread_id": None,
            "votes": {"up": [], "neutral": [], "down": []},
        }

        voting_enabled = bool(latest_app.get("voting", {}).get("enabled", True))
        view = ReviewView(
            self,
            guild.id,
            key,
            response["id"],
            voting_enabled=voting_enabled,
        )
        message = await channel.send(
            embed=self._response_embed(guild, latest_app, response),
            view=view,
        )
        response["message_id"] = message.id
        self.bot.add_view(view)

        thread: Optional[discord.Thread] = None
        if latest_app.get("thread_enabled", True):
            thread_name = self._render_template(
                latest_app.get("thread_name", "{application} - {user}"),
                guild=guild,
                member=member,
                app=latest_app,
                response=response,
            )
            with contextlib.suppress(discord.HTTPException):
                thread = await message.create_thread(name=truncate(thread_name, 90))
                response["thread_id"] = thread.id

        latest_app.setdefault("responses", []).append(response)
        await self._save_app(guild.id, latest_app)

        await self._apply_role_action(member, latest_app, "submit_add")
        await self._send_notifications(guild, member, latest_app, response, message, thread)
        return response, latest_app

    async def _send_notifications(
        self,
        guild: discord.Guild,
        member: discord.Member,
        app: ApplicationDict,
        response: ResponseDict,
        response_message: discord.Message,
        thread: Optional[discord.Thread] = None,
    ) -> None:
        if not app.get("notification_enabled", True):
            return
        content = self._render_template(
            app.get("notification_message", ""),
            guild=guild,
            member=member,
            app=app,
            response=response,
        )
        role_mentions = " ".join(
            role.mention
            for role_id in app.get("notification_role_ids", [])
            if (role := guild.get_role(role_id))
        )
        role_target = self._notification_role_target(app)
        channel_content = content
        if role_mentions and role_target in {"channel", "both"}:
            channel_content = f"{role_mentions} {content}".strip()
        allowed = discord.AllowedMentions(roles=True, users=True, everyone=False)
        channel_ids = unique_ids([app.get("channel_id"), *app.get("notification_channel_ids", [])])
        for channel_id in channel_ids:
            channel = guild.get_channel(channel_id)
            if not isinstance(channel, discord.TextChannel):
                continue
            with contextlib.suppress(discord.HTTPException):
                await channel.send(
                    content=truncate(channel_content, 2000),
                    reference=(
                        response_message.to_reference(fail_if_not_exists=False)
                        if channel.id == response_message.channel.id
                        else None
                    ),
                    allowed_mentions=allowed,
                )
        if role_mentions and role_target in {"thread", "both"} and thread is not None:
            thread_content = f"{role_mentions} {content}".strip()
            with contextlib.suppress(discord.HTTPException):
                await thread.send(
                    content=truncate(thread_content, 2000),
                    allowed_mentions=allowed,
                )

    async def _set_response_decision(
        self,
        interaction: discord.Interaction,
        guild_id: int,
        application: str,
        response_id: str,
        decision: str,
        reason: str,
    ) -> None:
        guild = interaction.guild or self.bot.get_guild(guild_id)
        if guild is None or not isinstance(interaction.user, discord.Member):
            await interaction.response.send_message("This can only be used in the server.", ephemeral=True)
            return
        await interaction.response.defer(ephemeral=True)
        try:
            key, app = await self._get_app(guild_id, application)
            response = self._find_response(app, response_id)
        except commands.UserFeedbackCheckFailure as exc:
            await interaction.followup.send(str(exc), ephemeral=True)
            return
        if not await self._is_app_manager(interaction.user, app):
            await interaction.followup.send(
                "You need `Manage Server` or an application manager role to review this.",
                ephemeral=True,
            )
            return
        if response.get("status") != "pending":
            await interaction.followup.send("That response has already been reviewed.", ephemeral=True)
            return

        response["status"] = decision
        response["reviewed_by"] = interaction.user.id
        response["reviewed_at"] = utc_ts()
        response["review_reason"] = reason

        member = guild.get_member(response.get("user_id")) if response.get("user_id") else None
        if decision == "accepted":
            await self._apply_role_action(member, app, "accept_add")
            await self._apply_role_action(member, app, "accept_remove")
            dm_template = app.get("accept_message", "")
        else:
            await self._apply_role_action(member, app, "deny_add")
            await self._apply_role_action(member, app, "deny_remove")
            dm_template = app.get("deny_message", "")

        await self._save_app(guild_id, app)

        if member and dm_template:
            dm_content = self._render_template(
                dm_template,
                guild=guild,
                member=member,
                app=app,
                response=response,
                reviewer=interaction.user,
                reason=reason,
            )
            with contextlib.suppress(discord.HTTPException):
                await member.send(truncate(dm_content, 2000))

        channel = guild.get_channel(response.get("channel_id"))
        if isinstance(channel, discord.TextChannel) and response.get("message_id"):
            with contextlib.suppress(discord.HTTPException):
                message = await channel.fetch_message(response["message_id"])
                await message.edit(
                    embed=self._response_embed(guild, app, response),
                    view=ReviewView(
                        self,
                        guild_id,
                        key,
                        response_id,
                        disabled=True,
                        voting_enabled=bool(
                            app.get("voting", {}).get("enabled", True)
                        ),
                    ),
                )

        await interaction.followup.send(
            f"Application response `{response_id}` marked as **{decision}**.",
            ephemeral=True,
        )

    async def _refresh_application_review_views(
        self,
        guild: discord.Guild,
        key: str,
        app: ApplicationDict,
    ) -> None:
        voting_enabled = bool(app.get("voting", {}).get("enabled", True))
        for response in app.get("responses", []):
            channel = guild.get_channel(response.get("channel_id"))
            if not isinstance(channel, discord.TextChannel) or not response.get("message_id"):
                continue
            try:
                message = await channel.fetch_message(int(response["message_id"]))
                await message.edit(
                    view=ReviewView(
                        self,
                        guild.id,
                        key,
                        str(response.get("id") or "unknown"),
                        disabled=response.get("status") != "pending",
                        voting_enabled=voting_enabled,
                    )
                )
            except discord.HTTPException:
                continue

    async def _record_vote(
        self,
        interaction: discord.Interaction,
        guild_id: int,
        application: str,
        response_id: str,
        vote: str,
    ) -> None:
        guild = interaction.guild or self.bot.get_guild(guild_id)
        if guild is None or not isinstance(interaction.user, discord.Member):
            await interaction.response.send_message("This can only be used in the server.", ephemeral=True)
            return
        await interaction.response.defer(ephemeral=True)
        try:
            key, app = await self._get_app(guild_id, application)
            response = self._find_response(app, response_id)
        except commands.UserFeedbackCheckFailure as exc:
            await interaction.followup.send(str(exc), ephemeral=True)
            return
        if not app.get("voting", {}).get("enabled", True):
            await interaction.followup.send("Voting is disabled for this application.", ephemeral=True)
            return
        if not await self._is_app_manager(interaction.user, app):
            await interaction.followup.send(
                "You need `Manage Server` or an application manager role to vote.",
                ephemeral=True,
            )
            return

        votes = response.setdefault("votes", {"up": [], "neutral": [], "down": []})
        for voters in votes.values():
            if interaction.user.id in voters:
                voters.remove(interaction.user.id)
        votes.setdefault(vote, []).append(interaction.user.id)
        await self._save_app(guild_id, app)

        channel = guild.get_channel(response.get("channel_id"))
        if isinstance(channel, discord.TextChannel) and response.get("message_id"):
            with contextlib.suppress(discord.HTTPException):
                message = await channel.fetch_message(response["message_id"])
                await message.edit(embed=self._response_embed(guild, app, response))
        await interaction.followup.send(f"Recorded your **{vote}** vote.", ephemeral=True)

    def _poll_embed(self, poll: PollDict) -> discord.Embed:
        votes = poll.setdefault("votes", {})
        total = sum(len(voters) for voters in votes.values())
        lines = []
        for idx, option in enumerate(poll.get("options", [])):
            count = len(votes.setdefault(str(idx), []))
            pct = 0 if total == 0 else round(count / total * 100)
            lines.append(f"**{idx + 1}. {option}** - {count} vote(s), {pct}%")
        embed = discord.Embed(
            title=poll.get("question", "Poll"),
            description="\n".join(lines) or "No options configured.",
            color=discord.Color(self.DEFAULT_COLOR),
            timestamp=discord.utils.utcnow(),
        )
        embed.set_footer(text=f"Poll ID: {poll.get('id')} | Total votes: {total}")
        if poll.get("closed"):
            embed.title = f"{embed.title} (Closed)"
        return embed

    async def _vote_poll(
        self,
        interaction: discord.Interaction,
        guild_id: int,
        poll_id: str,
        option_index: int,
    ) -> None:
        guild = interaction.guild or self.bot.get_guild(guild_id)
        if guild is None or interaction.user is None:
            await interaction.response.send_message("This poll is not available.", ephemeral=True)
            return
        await interaction.response.defer(ephemeral=True)
        polls = await self.config.guild_from_id(guild_id).polls()
        poll = polls.get(poll_id)
        if not poll:
            await interaction.followup.send("That poll no longer exists.", ephemeral=True)
            return
        if poll.get("closed"):
            await interaction.followup.send("That poll is closed.", ephemeral=True)
            return

        votes = poll.setdefault("votes", {})
        for voters in votes.values():
            if interaction.user.id in voters:
                voters.remove(interaction.user.id)
        votes.setdefault(str(option_index), []).append(interaction.user.id)
        async with self.config.guild_from_id(guild_id).polls() as poll_data:
            poll_data[poll_id] = poll

        channel = guild.get_channel(poll.get("channel_id"))
        if isinstance(channel, discord.TextChannel):
            with contextlib.suppress(discord.HTTPException):
                message = await channel.fetch_message(poll.get("message_id"))
                await message.edit(embed=self._poll_embed(poll))
        await interaction.followup.send("Your vote was recorded.", ephemeral=True)

    @commands.hybrid_command(name="apply")
    @commands.guild_only()
    @app_commands.describe(name="Application name")
    async def apply_command(self, ctx: commands.GuildContext, *, name: str) -> None:
        """Apply to a configured application."""
        await self._start_application_from_context(ctx, name)

    @commands.hybrid_group(
        name="application",
        aliases=["app", "apps"],
        invoke_without_command=True,
    )
    @commands.guild_only()
    async def application_group(self, ctx: commands.GuildContext) -> None:
        """Manage application forms."""
        await self.application_list(ctx)

    @application_group.command(name="create", aliases=["+"])
    @app_commands.describe(
        name="Short application name",
        description="Longer application description",
        channel="Channel where completed applications are posted",
    )
    async def application_create(
        self,
        ctx: commands.GuildContext,
        name: commands.Range[str, 1, 60],
        description: commands.Range[str, 1, 200],
        channel: discord.TextChannel,
    ) -> None:
        """Create a new application form."""
        await self._require_setup_manager(ctx)
        key = app_key(name)
        async with self.config.guild(ctx.guild).applications() as apps:
            if key in apps:
                raise commands.UserFeedbackCheckFailure("An application with that name already exists.")
            app = self._new_application(
                name=name,
                description=description,
                channel_id=channel.id,
                creator_id=ctx.author.id,
            )
            apps[key] = app
        await ctx.send(embed=self._application_embed(ctx.guild, app))

    @application_group.command(name="delete", aliases=["remove"])
    @app_commands.describe(name="Application name")
    async def application_delete(self, ctx: commands.GuildContext, *, name: str) -> None:
        """Delete an application form and its stored responses."""
        await self._require_setup_manager(ctx)
        key, app = await self._get_app(ctx.guild.id, name)
        async with self.config.guild(ctx.guild).applications() as apps:
            apps.pop(key, None)
        await ctx.send(f"Deleted the **{app['name']}** application.")

    @application_group.command(name="list", aliases=["all"])
    async def application_list(self, ctx: commands.GuildContext) -> None:
        """List configured applications."""
        await self._require_setup_manager(ctx)
        apps = await self._get_apps(ctx.guild.id)
        if not apps:
            await ctx.send("There are no applications configured yet.")
            return
        lines = []
        for app in apps.values():
            lines.append(
                "`{key}` - **{name}** ({status}) | {questions} question(s), {responses} response(s)".format(
                    key=app["key"],
                    name=app["name"],
                    status="open" if app.get("open", True) else "closed",
                    questions=len(app.get("questions", [])),
                    responses=len(app.get("responses", [])),
                )
            )
        for page in pagify("\n".join(lines), page_length=1800):
            await ctx.send(page)

    @application_group.command(name="view", aliases=["settings", "show"])
    @app_commands.describe(name="Application name")
    async def application_view(self, ctx: commands.GuildContext, *, name: str) -> None:
        """Show one application's settings."""
        key, app = await self._get_app(ctx.guild.id, name)
        await self._require_app_manager(ctx, app)
        await ctx.send(embed=self._application_embed(ctx.guild, app))
        questions = app.get("questions", [])
        if questions:
            question_lines = []
            for idx, question in enumerate(questions, start=1):
                choices = ", ".join(question.get("choices", []))
                question_lines.append(
                    f"{idx}. [{question.get('type')}] {question.get('text')}"
                    f"{' | ' + choices if choices else ''}"
                )
            for page in pagify("\n".join(question_lines), page_length=1800):
                await ctx.send(box(page))

    @application_group.command(name="panel")
    @app_commands.describe(
        channel="Channel to post the panel in",
        mode="buttons or select",
        names="Comma-separated application names. Leave empty for every open application.",
    )
    async def application_panel(
        self,
        ctx: commands.GuildContext,
        channel: discord.TextChannel,
        mode: str = "buttons",
        *,
        names: str = "",
    ) -> None:
        """Post an application panel with buttons or a dropdown."""
        await self._require_setup_manager(ctx)
        mode = mode.lower()
        if mode not in ("buttons", "select"):
            raise commands.UserFeedbackCheckFailure("Panel mode must be `buttons` or `select`.")
        apps = await self._get_apps(ctx.guild.id)
        selected: List[ApplicationDict] = []
        if names:
            for item in parse_csv_values(names):
                _key, app = await self._get_app(ctx.guild.id, item)
                selected.append(app)
        else:
            selected = [app for app in apps.values() if app.get("open", True)]
        if not selected:
            raise commands.UserFeedbackCheckFailure("No matching open applications were found.")
        if len(selected) > 25:
            raise commands.UserFeedbackCheckFailure("A panel can contain at most 25 applications.")
        panel_id = make_id(10)
        description = "\n".join(
            self._render_template(
                app.get("panel_message", ""),
                guild=ctx.guild,
                member=ctx.author,
                app=app,
            )
            for app in selected[:1]
        )
        if len(selected) > 1:
            description = "Choose an application below."
        view = ApplicationPanelView(
            self,
            ctx.guild.id,
            selected,
            mode=mode,
            panel_id=panel_id,
        )
        message = await channel.send(
            embed=self._panel_embed(
                ctx.guild,
                selected,
                title="Applications",
                description=description,
            ),
            view=view,
        )
        self.bot.add_view(view)
        async with self.config.guild(ctx.guild).panels() as panels:
            panels[str(message.id)] = {
                "id": panel_id,
                "channel_id": channel.id,
                "message_id": message.id,
                "applications": [app["key"] for app in selected],
                "mode": mode,
            }
        await ctx.send(f"Posted an application panel in {channel.mention}.")

    @application_group.command(name="send")
    @app_commands.describe(
        name="Application name",
        member="Member to send the application to",
    )
    async def application_send(
        self,
        ctx: commands.GuildContext,
        name: str,
        member: discord.Member,
    ) -> None:
        """Send an application directly to a member, bypassing role restrictions."""
        key, app = await self._get_app(ctx.guild.id, name)
        await self._require_app_manager(ctx, app)
        await self._start_application_from_context(ctx, key, member=member, bypass=True)

    @application_group.command(name="responses", aliases=["history"])
    @app_commands.describe(name="Application name", status="all, pending, accepted, or denied")
    async def application_responses(
        self,
        ctx: commands.GuildContext,
        name: str,
        status: str = "all",
        member: Optional[discord.Member] = None,
    ) -> None:
        """List responses for an application."""
        key, app = await self._get_app(ctx.guild.id, name)
        await self._require_app_manager(ctx, app)
        status = status.lower()
        rows = []
        for response in app.get("responses", []):
            if status != "all" and response.get("status") != status:
                continue
            if member and response.get("user_id") != member.id:
                continue
            user = ctx.guild.get_member(response.get("user_id")) if response.get("user_id") else None
            rows.append(
                "`{id}` | {status} | {user} | <t:{created}:R>".format(
                    id=response.get("id"),
                    status=response.get("status", "pending"),
                    user=user.mention if user else response.get("user_id"),
                    created=int(response.get("created_at") or utc_ts()),
                )
            )
        if not rows:
            await ctx.send("No responses matched that query.")
            return
        for page in pagify("\n".join(rows), page_length=1800):
            await ctx.send(page, allowed_mentions=discord.AllowedMentions.none())

    @application_group.command(name="response")
    @app_commands.describe(name="Application name", response_id="Response ID")
    async def application_response(
        self,
        ctx: commands.GuildContext,
        name: str,
        response_id: str,
    ) -> None:
        """Show one response by ID."""
        key, app = await self._get_app(ctx.guild.id, name)
        await self._require_app_manager(ctx, app)
        response = self._find_response(app, response_id)
        await ctx.send(embed=self._response_embed(ctx.guild, app, response))

    @application_group.command(name="export")
    @app_commands.describe(name="Application name", status="all, pending, accepted, or denied")
    async def application_export(
        self,
        ctx: commands.GuildContext,
        name: str,
        status: str = "all",
    ) -> None:
        """Export responses to CSV."""
        key, app = await self._get_app(ctx.guild.id, name)
        await self._require_app_manager(ctx, app)
        output = io.StringIO()
        writer = csv.writer(output)
        questions = [question.get("text", "") for question in app.get("questions", [])]
        writer.writerow(["response_id", "user_id", "status", "created_at", "reviewed_by", *questions])
        for response in app.get("responses", []):
            if status != "all" and response.get("status") != status:
                continue
            answers = [answer.get("answer", "") for answer in response.get("answers", [])]
            writer.writerow(
                [
                    response.get("id"),
                    response.get("user_id"),
                    response.get("status"),
                    response.get("created_at"),
                    response.get("reviewed_by"),
                    *answers,
                ]
            )
        data = output.getvalue().encode("utf-8")
        await ctx.send(
            file=discord.File(
                fp=io.BytesIO(data),
                filename=f"applications-{key}-{status}.csv",
            )
        )

    @application_group.command(name="backup")
    async def application_backup(self, ctx: commands.GuildContext) -> None:
        """Export all application configuration and responses as JSON."""
        await self._require_setup_manager(ctx)
        data = {
            "applications": await self.config.guild(ctx.guild).applications(),
            "panels": await self.config.guild(ctx.guild).panels(),
            "polls": await self.config.guild(ctx.guild).polls(),
        }
        payload = json.dumps(data, indent=2, sort_keys=True).encode("utf-8")
        await ctx.send(
            file=discord.File(io.BytesIO(payload), filename=f"applications-backup-{ctx.guild.id}.json")
        )

    @application_group.group(name="config", aliases=["conf"])
    async def application_config_group(self, ctx: commands.GuildContext) -> None:
        """Configure application settings."""

    @application_config_group.command(name="channel")
    async def application_config_channel(
        self,
        ctx: commands.GuildContext,
        name: str,
        channel: discord.TextChannel,
    ) -> None:
        """Set the response channel."""
        await self._require_setup_manager(ctx)
        key, app = await self._get_app(ctx.guild.id, name)
        app["channel_id"] = channel.id
        await self._save_app(ctx.guild.id, app)
        await ctx.send(f"Response channel for **{app['name']}** set to {channel.mention}.")

    @application_config_group.command(name="status")
    async def application_config_status(
        self,
        ctx: commands.GuildContext,
        name: str,
        status: str,
    ) -> None:
        """Open or close an application."""
        await self._require_setup_manager(ctx)
        key, app = await self._get_app(ctx.guild.id, name)
        status = status.lower()
        if status not in ("open", "close", "closed"):
            raise commands.UserFeedbackCheckFailure("Status must be `open` or `close`.")
        app["open"] = status == "open"
        await self._save_app(ctx.guild.id, app)
        await ctx.send(f"**{app['name']}** is now {'open' if app['open'] else 'closed'}.")

    @application_config_group.command(name="color")
    async def application_config_color(
        self,
        ctx: commands.GuildContext,
        name: str,
        color: str,
    ) -> None:
        """Set the application embed color."""
        await self._require_setup_manager(ctx)
        key, app = await self._get_app(ctx.guild.id, name)
        try:
            discord_color = discord.Color.from_str(color)
        except ValueError:
            raise commands.UserFeedbackCheckFailure("Use a valid Discord color, such as `#5865F2`.")
        app["color"] = discord_color.value
        await self._save_app(ctx.guild.id, app)
        await ctx.send(embed=discord.Embed(description="Color updated.", color=discord_color))

    @application_config_group.command(name="cooldown")
    async def application_config_cooldown(
        self,
        ctx: commands.GuildContext,
        name: str,
        minutes: commands.Range[int, 0, 43200],
    ) -> None:
        """Set the cooldown between applications for one user."""
        await self._require_setup_manager(ctx)
        key, app = await self._get_app(ctx.guild.id, name)
        app["cooldown_minutes"] = int(minutes)
        await self._save_app(ctx.guild.id, app)
        await ctx.send(f"Cooldown for **{app['name']}** set to {minutes} minute(s).")

    @application_config_group.command(name="multiple")
    async def application_config_multiple(
        self,
        ctx: commands.GuildContext,
        name: str,
        enabled: bool,
    ) -> None:
        """Allow or block multiple pending responses from the same user."""
        await self._require_setup_manager(ctx)
        key, app = await self._get_app(ctx.guild.id, name)
        app["allow_multiple_pending"] = enabled
        await self._save_app(ctx.guild.id, app)
        await ctx.send(f"Multiple pending responses are now {bool_text(enabled)}.")

    @application_config_group.command(name="form", aliases=["formmode", "input"])
    async def application_config_form(
        self,
        ctx: commands.GuildContext,
        name: str,
        mode: str,
    ) -> None:
        """Choose whether applicants answer in DMs or a native Discord modal."""
        await self._require_setup_manager(ctx)
        key, app = await self._get_app(ctx.guild.id, name)
        mode = mode.lower()
        if mode not in {"dm", "modal"}:
            raise commands.UserFeedbackCheckFailure("Form mode must be `dm` or `modal`.")
        if mode == "modal":
            modal_error = self._modal_form_error(app)
            if modal_error:
                raise commands.UserFeedbackCheckFailure(modal_error)
        app["form_mode"] = mode
        await self._save_app(ctx.guild.id, app)
        await ctx.send(f"**{app['name']}** now uses the **{mode}** form flow.")

    @application_config_group.command(name="thread")
    async def application_config_thread(
        self,
        ctx: commands.GuildContext,
        name: str,
        enabled: bool,
        *,
        template: str = "{application} - {user}",
    ) -> None:
        """Configure response thread creation."""
        await self._require_setup_manager(ctx)
        key, app = await self._get_app(ctx.guild.id, name)
        app["thread_enabled"] = enabled
        app["thread_name"] = template
        await self._save_app(ctx.guild.id, app)
        await ctx.send(f"Threads are now {bool_text(enabled)} for **{app['name']}**.")

    @application_config_group.command(name="message")
    async def application_config_message(
        self,
        ctx: commands.GuildContext,
        name: str,
        message_type: str,
        *,
        message: str,
    ) -> None:
        """Set panel, notification, completion, accept, or deny messages."""
        await self._require_setup_manager(ctx)
        key, app = await self._get_app(ctx.guild.id, name)
        fields = {
            "panel": "panel_message",
            "notification": "notification_message",
            "completion": "completion_message",
            "accept": "accept_message",
            "deny": "deny_message",
        }
        field = fields.get(message_type.lower())
        if not field:
            raise commands.UserFeedbackCheckFailure(
                "Message type must be `panel`, `notification`, `completion`, `accept`, or `deny`."
            )
        app[field] = message
        await self._save_app(ctx.guild.id, app)
        await ctx.send(f"Updated the **{message_type.lower()}** message for **{app['name']}**.")

    @application_config_group.command(name="button")
    async def application_config_button(
        self,
        ctx: commands.GuildContext,
        name: str,
        field: str,
        *,
        value: str,
    ) -> None:
        """Set panel button label, emoji, or style."""
        await self._require_setup_manager(ctx)
        key, app = await self._get_app(ctx.guild.id, name)
        field = field.lower()
        if field == "label":
            app["button_label"] = value
        elif field == "emoji":
            app["button_emoji"] = value
        elif field == "style":
            if value.lower() not in self.VALID_BUTTON_STYLES:
                raise commands.UserFeedbackCheckFailure("Style must be green, red, gray, or blurple.")
            app["button_style"] = value.lower()
        else:
            raise commands.UserFeedbackCheckFailure("Button field must be `label`, `emoji`, or `style`.")
        await self._save_app(ctx.guild.id, app)
        await ctx.send(f"Updated button {field} for **{app['name']}**.")

    @application_config_group.command(name="notifications")
    async def application_config_notifications(
        self,
        ctx: commands.GuildContext,
        name: str,
        enabled: bool,
    ) -> None:
        """Enable or disable application notifications."""
        await self._require_setup_manager(ctx)
        key, app = await self._get_app(ctx.guild.id, name)
        app["notification_enabled"] = enabled
        await self._save_app(ctx.guild.id, app)
        await ctx.send(f"Notifications are now {bool_text(enabled)} for **{app['name']}**.")

    @application_config_group.command(name="notifychannels")
    async def application_config_notifychannels(
        self,
        ctx: commands.GuildContext,
        name: str,
        *,
        channels: str,
    ) -> None:
        """Set extra notification channels with IDs or mentions separated by commas/spaces."""
        await self._require_setup_manager(ctx)
        key, app = await self._get_app(ctx.guild.id, name)
        ids = parse_mentions_or_ids(channels)
        valid = [channel_id for channel_id in ids if isinstance(ctx.guild.get_channel(channel_id), discord.TextChannel)]
        app["notification_channel_ids"] = valid
        await self._save_app(ctx.guild.id, app)
        await ctx.send(f"Stored {len(valid)} notification channel(s).")

    @application_config_group.command(name="notifyroles")
    async def application_config_notifyroles(
        self,
        ctx: commands.GuildContext,
        name: str,
        *,
        roles: str,
    ) -> None:
        """Set roles to ping on new responses with IDs or mentions separated by commas/spaces."""
        await self._require_setup_manager(ctx)
        key, app = await self._get_app(ctx.guild.id, name)
        ids = parse_mentions_or_ids(roles)
        valid = [role_id for role_id in ids if ctx.guild.get_role(role_id)]
        app["notification_role_ids"] = valid
        await self._save_app(ctx.guild.id, app)
        await ctx.send(f"Stored {len(valid)} notification role(s).")

    @application_config_group.command(
        name="notifytarget",
        aliases=["notificationtarget", "notifyroletarget", "pingtarget"],
    )
    async def application_config_notifytarget(
        self,
        ctx: commands.GuildContext,
        name: str,
        target: str,
    ) -> None:
        """Set where notification roles are pinged: channel, thread, or both."""
        await self._require_setup_manager(ctx)
        _key, app = await self._get_app(ctx.guild.id, name)
        raw_target = target.strip().lower()
        valid_inputs = {
            *self.VALID_NOTIFICATION_ROLE_TARGETS,
            "channels",
            "response",
            "responses",
            "review",
            "reviews",
            "threads",
            "reviewthread",
            "reviewthreads",
            "all",
        }
        if raw_target not in valid_inputs:
            raise commands.UserFeedbackCheckFailure(
                "Notification role ping target must be `channel`, `thread`, or `both`."
            )
        normalized = self._notification_role_target({"notification_role_target": raw_target})
        app["notification_role_target"] = normalized
        await self._save_app(ctx.guild.id, app)
        note = ""
        if normalized in {"thread", "both"} and not app.get("thread_enabled", True):
            note = " Thread pings only work when response threads are enabled."
        await ctx.send(
            f"Notification role pings for **{app['name']}** will go to **{normalized}**.{note}"
        )

    @application_config_group.command(name="voting")
    async def application_config_voting(
        self,
        ctx: commands.GuildContext,
        name: str,
        enabled: bool,
        threshold: int = 0,
    ) -> None:
        """Enable review voting and optionally set a positive vote threshold."""
        await self._require_setup_manager(ctx)
        key, app = await self._get_app(ctx.guild.id, name)
        app["voting"] = {"enabled": enabled, "threshold": int(threshold)}
        await self._save_app(ctx.guild.id, app)
        await self._refresh_application_review_views(ctx.guild, key, app)
        await ctx.send(f"Voting is now {bool_text(enabled)} for **{app['name']}**.")

    @application_group.group(name="question", aliases=["questions", "q"])
    async def application_question_group(self, ctx: commands.GuildContext) -> None:
        """Configure application questions."""

    @application_question_group.command(name="add", aliases=["create", "+"])
    @app_commands.describe(
        name="Application name",
        question="Question text",
        question_type="text, boolean, choice, or attachment",
        required="Whether this question is required",
        choices="Comma-separated choices for choice questions. Include `other` to allow custom answers.",
    )
    async def application_question_add(
        self,
        ctx: commands.GuildContext,
        name: str,
        question: str,
        question_type: str = "text",
        required: bool = True,
        *,
        choices: str = "",
    ) -> None:
        """Add a question to an application."""
        await self._require_setup_manager(ctx)
        key, app = await self._get_app(ctx.guild.id, name)
        question_type = question_type.lower()
        if question_type not in self.VALID_QUESTION_TYPES:
            raise commands.UserFeedbackCheckFailure("Question type must be text, boolean, choice, or attachment.")
        if len(app.get("questions", [])) >= self.MAX_QUESTIONS:
            raise commands.UserFeedbackCheckFailure(f"Applications can have at most {self.MAX_QUESTIONS} questions.")
        allow_other = False
        text = question.strip()
        if not text:
            raise commands.UserFeedbackCheckFailure("Question text cannot be empty.")
        if app.get("form_mode", "dm") == "modal":
            if question_type == "attachment":
                raise commands.UserFeedbackCheckFailure(
                    "Modal forms cannot contain attachment questions."
                )
            if len(app.get("questions", [])) >= 5:
                raise commands.UserFeedbackCheckFailure(
                    "Modal forms can contain at most 5 questions."
                )
        if question_type == "choice":
            choice_values = parse_csv_values(choices)
            if not choice_values:
                raise commands.UserFeedbackCheckFailure(
                    "Choice questions need comma-separated choices, for example: "
                    "`[p]application question add staff \"Favorite color?\" choice true red, blue`."
                )
            if len(choice_values) > self.MAX_CHOICES:
                raise commands.UserFeedbackCheckFailure("Choice questions can have at most 25 choices.")
            allow_other = any(choice.lower() == "other" for choice in choice_values)
            parsed_choices = [choice for choice in choice_values if choice.lower() != "other"]
        else:
            parsed_choices = []
        app.setdefault("questions", []).append(
            {
                "id": make_id(8),
                "text": text.strip(),
                "type": question_type,
                "required": bool(required),
                "choices": parsed_choices,
                "allow_other": allow_other,
            }
        )
        await self._save_app(ctx.guild.id, app)
        await ctx.send(f"Added question {len(app['questions'])} to **{app['name']}**.")

    @application_question_group.command(name="remove", aliases=["delete", "-"])
    async def application_question_remove(
        self,
        ctx: commands.GuildContext,
        name: str,
        position: commands.Range[int, 1, 100],
    ) -> None:
        """Remove a question by position."""
        await self._require_setup_manager(ctx)
        key, app = await self._get_app(ctx.guild.id, name)
        questions = app.get("questions", [])
        if position > len(questions):
            raise commands.UserFeedbackCheckFailure("That question position does not exist.")
        removed = questions.pop(position - 1)
        await self._save_app(ctx.guild.id, app)
        await ctx.send(f"Removed question: {removed.get('text')}")

    @application_question_group.command(name="list", aliases=["view"])
    async def application_question_list(self, ctx: commands.GuildContext, *, name: str) -> None:
        """List questions for an application."""
        key, app = await self._get_app(ctx.guild.id, name)
        await self._require_app_manager(ctx, app)
        questions = app.get("questions", [])
        if not questions:
            await ctx.send("This application has no questions.")
            return
        lines = []
        for idx, question in enumerate(questions, start=1):
            choices = ", ".join(question.get("choices", []))
            lines.append(
                f"{idx}. [{question.get('type')}] "
                f"{'required' if question.get('required', True) else 'optional'} - "
                f"{question.get('text')}"
                f"{' | ' + choices if choices else ''}"
            )
        for page in pagify("\n".join(lines), page_length=1800):
            await ctx.send(box(page))

    @application_group.group(name="role", aliases=["roles"])
    async def application_role_group(self, ctx: commands.GuildContext) -> None:
        """Configure application role restrictions and actions."""

    @application_role_group.command(name="set")
    async def application_role_set(
        self,
        ctx: commands.GuildContext,
        role_type: str,
        add_or_remove: str,
        name: str,
        *,
        roles: str,
    ) -> None:
        """Manage roles: manager, whitelist, blacklist, apply, submit, accept, acceptremove, deny, denyremove."""
        await self._require_setup_manager(ctx)
        key, app = await self._get_app(ctx.guild.id, name)
        target = self.ROLE_LISTS.get(role_type.lower())
        if not target:
            raise commands.UserFeedbackCheckFailure(
                "Role type must be manager, whitelist, blacklist, apply, submit, accept, acceptremove, deny, or denyremove."
            )
        if add_or_remove.lower() not in ("add", "remove"):
            raise commands.UserFeedbackCheckFailure("Use `add` or `remove`.")
        role_ids_to_change = [
            role_id
            for role_id in parse_mentions_or_ids(roles)
            if ctx.guild.get_role(role_id)
        ]
        if not role_ids_to_change:
            raise commands.UserFeedbackCheckFailure("Provide at least one role.")
        role_ids = app.setdefault("roles", self._default_roles()).setdefault(target, [])
        if add_or_remove.lower() == "add":
            role_ids.extend(role_id for role_id in role_ids_to_change if role_id not in role_ids)
        else:
            for role_id in role_ids_to_change:
                if role_id in role_ids:
                    role_ids.remove(role_id)
        app["roles"][target] = unique_ids(role_ids)
        await self._save_app(ctx.guild.id, app)
        await ctx.send(f"Updated **{target}** roles for **{app['name']}**.")

    @application_role_group.command(name="view", aliases=["list"])
    async def application_role_view(self, ctx: commands.GuildContext, *, name: str) -> None:
        """View configured role lists."""
        key, app = await self._get_app(ctx.guild.id, name)
        await self._require_app_manager(ctx, app)
        lines = []
        for role_key, role_ids in app.get("roles", {}).items():
            mentions = [
                role.mention if (role := ctx.guild.get_role(role_id)) else f"`{role_id}`"
                for role_id in role_ids
            ]
            lines.append(f"**{role_key}:** {', '.join(mentions) if mentions else 'none'}")
        await ctx.send("\n".join(lines), allowed_mentions=discord.AllowedMentions.none())

    @commands.hybrid_group(name="apppoll", aliases=["applicationpoll"], invoke_without_command=True)
    @commands.guild_only()
    async def apppoll_group(self, ctx: commands.GuildContext) -> None:
        """Create and manage simple polls."""
        await ctx.send_help(ctx.command)

    @apppoll_group.command(name="create")
    async def apppoll_create(
        self,
        ctx: commands.GuildContext,
        channel: discord.TextChannel,
        *,
        poll: str,
    ) -> None:
        """Create a poll. Format: question | option one, option two, option three."""
        await self._require_setup_manager(ctx)
        if "|" not in poll:
            raise commands.UserFeedbackCheckFailure(
                "Use `question | option one, option two` for the poll content."
            )
        question, option_text = poll.split("|", 1)
        options = parse_csv_values(option_text)
        if len(options) < 2:
            raise commands.UserFeedbackCheckFailure("Polls need at least two options.")
        if len(options) > 25:
            raise commands.UserFeedbackCheckFailure("Polls can have at most 25 options.")
        poll_id = make_id(10)
        record: PollDict = {
            "id": poll_id,
            "question": question.strip(),
            "options": options,
            "votes": {str(idx): [] for idx in range(len(options))},
            "created_by": ctx.author.id,
            "created_at": utc_ts(),
            "channel_id": channel.id,
            "message_id": None,
            "closed": False,
        }
        view = PollView(self, ctx.guild.id, poll_id, options)
        message = await channel.send(embed=self._poll_embed(record), view=view)
        record["message_id"] = message.id
        self.bot.add_view(view)
        async with self.config.guild(ctx.guild).polls() as polls:
            polls[poll_id] = record
        await ctx.send(f"Poll `{poll_id}` created in {channel.mention}.")

    @apppoll_group.command(name="close")
    async def apppoll_close(self, ctx: commands.GuildContext, poll_id: str) -> None:
        """Close a poll by ID."""
        await self._require_setup_manager(ctx)
        async with self.config.guild(ctx.guild).polls() as polls:
            poll = polls.get(poll_id)
            if not poll:
                raise commands.UserFeedbackCheckFailure("That poll does not exist.")
            poll["closed"] = True
        channel = ctx.guild.get_channel(poll.get("channel_id"))
        if isinstance(channel, discord.TextChannel):
            with contextlib.suppress(discord.HTTPException):
                message = await channel.fetch_message(poll.get("message_id"))
                await message.edit(
                    embed=self._poll_embed(poll),
                    view=PollView(self, ctx.guild.id, poll_id, poll.get("options", []), disabled=True),
                )
        await ctx.send(f"Poll `{poll_id}` closed.")
