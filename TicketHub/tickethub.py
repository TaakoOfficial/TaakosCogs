"""TicketHub cog for Red-DiscordBot."""

from __future__ import annotations

import asyncio
import csv
import html
import io
import logging
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Sequence, Tuple, Union

import discord
from redbot.core import Config, commands
from redbot.core.bot import Red
from redbot.core.utils.chat_formatting import box, pagify

try:
    import chat_exporter
except ImportError:
    chat_exporter = None

log = logging.getLogger("red.taakoscogs.tickethub")


TicketRecord = Dict[str, Any]
ProfileRecord = Dict[str, Any]
ModalFieldRecord = Dict[str, Any]
MultiPanelRecord = Dict[str, Any]
TicketLocation = Union[discord.TextChannel, discord.Thread]
MODAL_SELECTS_SUPPORTED = hasattr(discord.ui, "Label")


class TicketPanelView(discord.ui.View):
    """Persistent view for ticket panel messages."""

    def __init__(self, cog: "TicketHub") -> None:
        super().__init__(timeout=None)
        self.cog = cog

    @discord.ui.button(
        label="Open Ticket",
        emoji="\N{ENVELOPE WITH DOWNWARDS ARROW ABOVE}",
        style=discord.ButtonStyle.primary,
        custom_id="taakoscogs:tickethub:open",
    )
    async def open_ticket(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ) -> None:
        await self.cog.handle_panel_open(interaction)


class TicketPanelSelectView(discord.ui.View):
    """Persistent dropdown view for ticket panel messages."""

    def __init__(self, cog: "TicketHub") -> None:
        super().__init__(timeout=None)
        self.cog = cog

    @discord.ui.select(
        placeholder="Open a ticket...",
        min_values=1,
        max_values=1,
        options=[
            discord.SelectOption(
                label="Open Ticket",
                value="open",
                emoji="\N{ENVELOPE WITH DOWNWARDS ARROW ABOVE}",
            )
        ],
        custom_id="taakoscogs:tickethub:open-select",
    )
    async def open_ticket(
        self,
        interaction: discord.Interaction,
        select: discord.ui.Select,
    ) -> None:
        await self.cog.handle_panel_open(interaction)


class TicketMultiPanelButton(discord.ui.Button):
    """Button that opens a specific profile from a multi-panel."""

    def __init__(
        self,
        cog: "TicketHub",
        message_id: int,
        option: Dict[str, Any],
        *,
        row: int,
    ) -> None:
        self.cog = cog
        self.profile_name = str(option["profile"])
        super().__init__(
            label=str(option["label"]),
            emoji=option.get("emoji") or None,
            style=discord.ButtonStyle.secondary,
            custom_id=(f"taakoscogs:tickethub:multi:{message_id}:{self.profile_name}"),
            row=row,
        )

    async def callback(self, interaction: discord.Interaction) -> None:
        await self.cog.handle_panel_open(interaction, self.profile_name)


class TicketMultiPanelSelect(discord.ui.Select):
    """Dropdown that routes each option to its configured profile."""

    def __init__(
        self,
        cog: "TicketHub",
        message_id: int,
        record: MultiPanelRecord,
    ) -> None:
        self.cog = cog
        super().__init__(
            placeholder=str(record.get("placeholder") or "Choose a ticket type...")[
                :100
            ],
            min_values=1,
            max_values=1,
            options=[
                discord.SelectOption(
                    label=str(option["label"]),
                    value=str(option["profile"]),
                    description=option.get("description") or None,
                    emoji=option.get("emoji") or None,
                )
                for option in record.get("options", [])
            ],
            custom_id=f"taakoscogs:tickethub:multi-select:{message_id}",
        )

    async def callback(self, interaction: discord.Interaction) -> None:
        if not self.values:
            await interaction.response.send_message(
                "Choose a ticket type first.",
                ephemeral=True,
            )
            return
        await self.cog.handle_panel_open(interaction, self.values[0])


class TicketMultiPanelView(discord.ui.View):
    """Persistent multi-profile ticket panel view."""

    def __init__(
        self,
        cog: "TicketHub",
        message_id: int,
        record: MultiPanelRecord,
    ) -> None:
        super().__init__(timeout=None)
        style = cog._panel_style(record.get("style"))
        if style == "dropdown":
            self.add_item(TicketMultiPanelSelect(cog, message_id, record))
            return
        for index, option in enumerate(record.get("options", [])):
            self.add_item(
                TicketMultiPanelButton(
                    cog,
                    message_id,
                    option,
                    row=index // 5,
                )
            )


class TicketControlView(discord.ui.View):
    """Persistent view for ticket control messages."""

    def __init__(self, cog: "TicketHub") -> None:
        super().__init__(timeout=None)
        self.cog = cog

    @discord.ui.button(
        label="Claim",
        emoji="\N{WHITE HEAVY CHECK MARK}",
        style=discord.ButtonStyle.success,
        custom_id="taakoscogs:tickethub:claim",
    )
    async def claim(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ) -> None:
        await self.cog.handle_ticket_button(interaction, "claim")

    @discord.ui.button(
        label="Close",
        emoji="\N{LOCK}",
        style=discord.ButtonStyle.danger,
        custom_id="taakoscogs:tickethub:close",
    )
    async def close(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ) -> None:
        await self.cog.handle_ticket_button(interaction, "close")

    @discord.ui.button(
        label="Transcript",
        emoji="\N{PAGE FACING UP}",
        style=discord.ButtonStyle.secondary,
        custom_id="taakoscogs:tickethub:transcript",
    )
    async def transcript(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ) -> None:
        await self.cog.handle_ticket_button(interaction, "transcript")


class TicketOpenModal(discord.ui.Modal):
    """Dynamic modal shown before opening a ticket from a panel."""

    def __init__(
        self,
        cog: "TicketHub",
        guild: discord.Guild,
        owner: discord.Member,
        profile_name: str,
        fields: Sequence[ModalFieldRecord],
    ) -> None:
        super().__init__(title="Open Ticket", timeout=300)
        self.cog = cog
        self.guild = guild
        self.owner = owner
        self.profile_name = profile_name
        self.inputs: List[Tuple[str, discord.ui.Item]] = []

        for field in fields[:5]:
            label = str(field.get("label") or "Question").strip()[:45]
            if not label:
                continue
            display_label = label
            if not display_label.endswith((":", "?")):
                display_label = f"{display_label}:"
            display_label = display_label[:45]
            question_type = str(field.get("type") or "text")
            required = bool(field.get("required", True))
            component: discord.ui.Item
            if MODAL_SELECTS_SUPPORTED and question_type == "choice":
                component = discord.ui.Select(
                    placeholder=str(field.get("placeholder") or "Choose an option")[:100],
                    options=[
                        discord.SelectOption(
                            label=str(choice)[:100],
                            value=str(choice)[:100],
                        )
                        for choice in field.get("choices", [])[:25]
                    ],
                    min_values=1 if required else 0,
                    max_values=1,
                    required=required,
                )
            elif MODAL_SELECTS_SUPPORTED and question_type == "boolean":
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
            else:
                style_value = int(field.get("style") or discord.TextStyle.paragraph.value)
                style = (
                    discord.TextStyle.short
                    if style_value == discord.TextStyle.short.value
                    else discord.TextStyle.paragraph
                )
                default = field.get("default")
                placeholder = field.get("placeholder")
                component = discord.ui.TextInput(
                    label=None if MODAL_SELECTS_SUPPORTED else display_label,
                    style=style,
                    required=required,
                    default=str(default)[:4000] if default not in (None, "") else None,
                    placeholder=str(placeholder)[:100] if placeholder not in (None, "") else None,
                    min_length=field.get("min_length"),
                    max_length=field.get("max_length"),
                )

            if MODAL_SELECTS_SUPPORTED:
                self.add_item(
                    discord.ui.Label(
                        text=display_label,
                        component=component,
                    )
                )
            else:
                self.add_item(component)
            self.inputs.append((label, component))

    @staticmethod
    def _input_value(component: discord.ui.Item) -> str:
        if isinstance(component, discord.ui.Select):
            return str(component.values[0]).strip() if component.values else ""
        return str(getattr(component, "value", "") or "").strip()

    async def on_submit(self, interaction: discord.Interaction) -> None:
        if not interaction.guild or not isinstance(interaction.user, discord.Member):
            await interaction.response.send_message(
                "This form only works in a server.",
                ephemeral=True,
            )
            return
        if interaction.user.id != self.owner.id:
            await interaction.response.send_message(
                "Only the ticket opener can submit this form.",
                ephemeral=True,
            )
            return

        await interaction.response.defer(ephemeral=True, thinking=True)
        form_answers = []
        for label, component in self.inputs:
            value = self._input_value(component)
            if value:
                form_answers.append({"label": label, "value": value[:4000]})
        reason = "Opened from ticket panel."
        if len(form_answers) == 1 and form_answers[0]["label"].strip().lower() == "reason":
            reason = form_answers[0]["value"][:1000]

        try:
            record, channel = await self.cog._create_ticket(
                self.guild,
                interaction.user,
                self.profile_name,
                reason=reason,
                form_answers=form_answers,
            )
        except commands.CommandError as error:
            await interaction.followup.send(str(error), ephemeral=True)
            return

        await interaction.followup.send(
            f"Ticket #{record['id']} opened: {channel.mention}",
            ephemeral=True,
        )

    async def on_error(self, interaction: discord.Interaction, error: Exception) -> None:
        log.exception(
            "TicketHub open-ticket modal failed.",
            exc_info=(type(error), error, error.__traceback__),
        )
        if interaction.response.is_done():
            await interaction.followup.send("I could not create that ticket.", ephemeral=True)
        else:
            await interaction.response.send_message(
                "I could not create that ticket.",
                ephemeral=True,
            )


class TicketQuestionTextModal(discord.ui.Modal):
    """Collect one text answer for a mixed ticket questionnaire."""

    def __init__(
        self,
        questionnaire: "TicketQuestionnaireView",
        field_index: int,
        field: ModalFieldRecord,
    ) -> None:
        label = str(field.get("label") or "Question").strip()[:45] or "Question"
        super().__init__(title="Open Ticket", timeout=300)
        self.questionnaire = questionnaire
        self.field_index = field_index
        style_value = int(field.get("style") or discord.TextStyle.paragraph.value)
        style = (
            discord.TextStyle.short
            if style_value == discord.TextStyle.short.value
            else discord.TextStyle.paragraph
        )
        default = field.get("default")
        placeholder = field.get("placeholder")
        self.answer = discord.ui.TextInput(
            label=label,
            style=style,
            required=bool(field.get("required", True)),
            default=str(default)[:4000] if default not in (None, "") else None,
            placeholder=str(placeholder)[:100] if placeholder not in (None, "") else None,
            min_length=field.get("min_length"),
            max_length=field.get("max_length"),
        )
        self.add_item(self.answer)

    async def on_submit(self, interaction: discord.Interaction) -> None:
        await self.questionnaire.record_answer(
            interaction,
            self.field_index,
            str(self.answer.value or "").strip(),
        )


class TicketQuestionnaireView(discord.ui.View):
    """Collect dropdown, boolean, and text ticket answers one question at a time."""

    def __init__(
        self,
        cog: "TicketHub",
        guild: discord.Guild,
        owner: discord.Member,
        profile_name: str,
        fields: Sequence[ModalFieldRecord],
    ) -> None:
        super().__init__(timeout=300)
        self.cog = cog
        self.guild = guild
        self.owner = owner
        self.profile_name = profile_name
        self.fields = list(fields[:5])
        self.field_index = 0
        self.form_answers: List[Dict[str, str]] = []
        self._build_items()

    @property
    def current_field(self) -> ModalFieldRecord:
        return self.fields[self.field_index]

    def question_embed(self) -> discord.Embed:
        field = self.current_field
        question_type = str(field.get("type") or "text")
        description = str(field.get("label") or "Question")
        if question_type == "choice":
            choices = "\n".join(
                f"- {choice}" for choice in field.get("choices", [])
            )
            if choices:
                description = f"{description}\n\n{choices}"
        embed = discord.Embed(
            title=f"Open Ticket - Question {self.field_index + 1}/{len(self.fields)}",
            description=description,
            color=discord.Color(TicketHub.DEFAULT_COLOR),
        )
        required = "Required" if field.get("required", True) else "Optional"
        embed.set_footer(text=f"{required} {question_type} question")
        return embed

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user and interaction.user.id == self.owner.id:
            return True
        await interaction.response.send_message(
            "Only the ticket opener can answer this form.",
            ephemeral=True,
        )
        return False

    def _build_items(self) -> None:
        self.clear_items()
        field = self.current_field
        question_type = str(field.get("type") or "text")

        if question_type == "choice":
            select = discord.ui.Select(
                placeholder=str(field.get("placeholder") or "Choose an option")[:100],
                options=[
                    discord.SelectOption(label=str(choice)[:100], value=str(choice)[:100])
                    for choice in field.get("choices", [])[:25]
                ],
                min_values=1,
                max_values=1,
            )
            select.callback = self._choice_callback
            self.add_item(select)
        elif question_type == "boolean":
            yes = discord.ui.Button(label="Yes", style=discord.ButtonStyle.success)
            yes.callback = self._yes_callback
            self.add_item(yes)
            no = discord.ui.Button(label="No", style=discord.ButtonStyle.danger)
            no.callback = self._no_callback
            self.add_item(no)
        else:
            answer = discord.ui.Button(
                label="Answer",
                style=discord.ButtonStyle.primary,
            )
            answer.callback = self._text_callback
            self.add_item(answer)

        if not field.get("required", True):
            skip = discord.ui.Button(label="Skip", style=discord.ButtonStyle.secondary)
            skip.callback = self._skip_callback
            self.add_item(skip)

        cancel = discord.ui.Button(label="Cancel", style=discord.ButtonStyle.secondary)
        cancel.callback = self._cancel_callback
        self.add_item(cancel)

    async def _text_callback(self, interaction: discord.Interaction) -> None:
        await interaction.response.send_modal(
            TicketQuestionTextModal(self, self.field_index, self.current_field)
        )

    async def _choice_callback(self, interaction: discord.Interaction) -> None:
        values = (interaction.data or {}).get("values") or []
        if not values:
            await interaction.response.send_message(
                "Choose an option before continuing.",
                ephemeral=True,
            )
            return
        await self.record_answer(interaction, self.field_index, str(values[0]))

    async def _yes_callback(self, interaction: discord.Interaction) -> None:
        await self.record_answer(interaction, self.field_index, "Yes")

    async def _no_callback(self, interaction: discord.Interaction) -> None:
        await self.record_answer(interaction, self.field_index, "No")

    async def _skip_callback(self, interaction: discord.Interaction) -> None:
        await self.record_answer(interaction, self.field_index, "")

    async def _cancel_callback(self, interaction: discord.Interaction) -> None:
        self.stop()
        await interaction.response.edit_message(
            content="Ticket creation cancelled.",
            embed=None,
            view=None,
        )

    async def record_answer(
        self,
        interaction: discord.Interaction,
        field_index: int,
        value: str,
    ) -> None:
        if field_index != self.field_index:
            await interaction.response.send_message(
                "That question is no longer active.",
                ephemeral=True,
            )
            return
        field = self.current_field
        cleaned = value.strip()
        if cleaned:
            self.form_answers.append(
                {
                    "label": str(field.get("label") or "Question")[:45],
                    "value": cleaned[:4000],
                }
            )
        self.field_index += 1
        if self.field_index < len(self.fields):
            self._build_items()
            await interaction.response.edit_message(
                content=None,
                embed=self.question_embed(),
                view=self,
            )
            return
        await self._finish(interaction)

    async def _finish(self, interaction: discord.Interaction) -> None:
        self.stop()
        await interaction.response.defer()
        reason = "Opened from ticket panel."
        if (
            len(self.form_answers) == 1
            and self.form_answers[0]["label"].strip().lower() == "reason"
        ):
            reason = self.form_answers[0]["value"][:1000]
        try:
            record, channel = await self.cog._create_ticket(
                self.guild,
                self.owner,
                self.profile_name,
                reason=reason,
                form_answers=self.form_answers,
            )
        except commands.CommandError as error:
            await interaction.edit_original_response(
                content=str(error),
                embed=None,
                view=None,
            )
            return
        await interaction.edit_original_response(
            content=f"Ticket #{record['id']} opened: {channel.mention}",
            embed=None,
            view=None,
        )

    async def on_error(
        self,
        interaction: discord.Interaction,
        error: Exception,
        item: discord.ui.Item,
    ) -> None:
        log.exception(
            "TicketHub ticket questionnaire failed.",
            exc_info=(type(error), error, error.__traceback__),
        )
        if interaction.response.is_done():
            await interaction.followup.send(
                "I could not continue that ticket form.",
                ephemeral=True,
            )
        else:
            await interaction.response.send_message(
                "I could not continue that ticket form.",
                ephemeral=True,
            )


class TicketHub(commands.Cog):
    """Ticket panels, ticket lifecycle controls, imports, and HTML transcripts."""

    CONFIG_IDENTIFIER = 2026051401
    DEFAULT_COLOR = 0x5865F2
    OPEN_COLOR = 0x57F287
    CLOSED_COLOR = 0xED4245
    CLAIMED_COLOR = 0xFEE75C
    MAX_TRANSCRIPT_MESSAGES = 5000

    def __init__(self, bot: Red) -> None:
        self.bot = bot
        self.config = Config.get_conf(
            self,
            identifier=self.CONFIG_IDENTIFIER,
            force_registration=True,
        )
        self.config.register_guild(
            enabled=False,
            next_ticket_id=1,
            profiles={"main": self._default_profile()},
            tickets={},
            multi_panels={},
        )
        self._locks: Dict[int, asyncio.Lock] = {}
        self._panel_view = TicketPanelView(self)
        self._panel_select_view = TicketPanelSelectView(self)
        self._control_view = TicketControlView(self)
        self._multi_panel_views: Dict[int, TicketMultiPanelView] = {}

    async def cog_load(self) -> None:
        """Register persistent views."""
        self.bot.add_view(self._panel_view)
        self.bot.add_view(self._panel_select_view)
        self.bot.add_view(self._control_view)
        await self._restore_multi_panel_views()

    async def red_delete_data_for_user(self, *, requester: str, user_id: int) -> None:
        """Remove stored ticket references for a Discord user ID."""
        user_key = str(user_id)
        all_guilds = await self.config.all_guilds()
        for guild_id in all_guilds:
            async with self.config.guild_from_id(guild_id).tickets() as tickets:
                for record in tickets.values():
                    if str(record.get("owner_id")) == user_key:
                        record["owner_id"] = None
                        record["owner_removed"] = True
                    if str(record.get("claimed_by")) == user_key:
                        record["claimed_by"] = None
                    if str(record.get("closed_by")) == user_key:
                        record["closed_by"] = None
                    record["participants"] = [
                        member_id
                        for member_id in record.get("participants", [])
                        if str(member_id) != user_key
                    ]
                    for event in record.get("events", []):
                        if str(event.get("actor_id")) == user_key:
                            event["actor_id"] = None
                        if str(event.get("target_id")) == user_key:
                            event["target_id"] = None

    @staticmethod
    def _default_profile() -> ProfileRecord:
        return {
            "enabled": True,
            "panel_channel_id": None,
            "panel_message_id": None,
            "panel_style": "button",
            "ticket_category_id": None,
            "closed_category_id": None,
            "ticket_mode": "channel",
            "thread_parent_channel_id": None,
            "log_channel_id": None,
            "transcript_channel_id": None,
            "support_role_ids": [],
            "view_role_ids": [],
            "ping_role_ids": [],
            "whitelist_role_ids": [],
            "blacklist_role_ids": [],
            "max_open_tickets_by_member": 3,
            "channel_name": "ticket-{id}-{owner_name}",
            "panel_title": "Need Help?",
            "panel_message": "Open a ticket and staff will help you as soon as possible.",
            "welcome_message": (
                "Welcome {owner_mention}. A staff member will be with you shortly."
            ),
            "custom_message": "Please describe what you need help with.",
            "creating_modal": None,
            "transcripts": True,
            "dm_transcript": True,
            "owner_can_close": True,
            "owner_can_reopen": False,
            "auto_delete_on_close_hours": None,
        }

    @staticmethod
    def _default_reason_modal() -> List[ModalFieldRecord]:
        return [
            {
                "label": "Reason",
                "type": "text",
                "style": discord.TextStyle.paragraph.value,
                "required": True,
                "default": "",
                "placeholder": "Enter the reason for creating the ticket...",
                "min_length": 1,
                "max_length": 1000,
                "choices": [],
            }
        ]

    def _guild_lock(self, guild_id: int) -> asyncio.Lock:
        return self._locks.setdefault(guild_id, asyncio.Lock())

    @staticmethod
    def _now() -> datetime:
        return datetime.now(timezone.utc)

    @classmethod
    def _now_ts(cls) -> float:
        return cls._now().timestamp()

    @staticmethod
    def _count(value: int) -> str:
        return f"{value:,}"

    @staticmethod
    def _format_ts(value: Any, style: str = "F") -> str:
        if value in (None, ""):
            return "Unknown"
        try:
            timestamp = int(float(value))
        except (TypeError, ValueError):
            return "Unknown"
        return f"<t:{timestamp}:{style}>"

    @staticmethod
    def _format_export_time(value: Any) -> str:
        if value in (None, ""):
            return ""
        try:
            return datetime.fromtimestamp(float(value), tz=timezone.utc).isoformat()
        except (TypeError, ValueError, OSError):
            return ""

    @staticmethod
    def _user_ref(user_id: Any) -> str:
        if user_id in (None, ""):
            return "Unknown"
        try:
            return f"<@{int(user_id)}>"
        except (TypeError, ValueError):
            return "Unknown"

    @staticmethod
    def _clean_name(value: str) -> str:
        cleaned = value.strip().lower()
        cleaned = re.sub(r"[^a-z0-9_-]+", "-", cleaned)
        cleaned = cleaned.strip("-_")
        if not cleaned:
            raise commands.BadArgument("Profile names can only contain letters, numbers, dashes, and underscores.")
        return cleaned[:40]

    @staticmethod
    def _clean_optional_text(value: Optional[str], limit: int) -> Optional[str]:
        if value is None:
            return None
        cleaned = value.strip()
        if cleaned.lower() in {"clear", "none", "reset", "off"}:
            return None
        return cleaned[:limit] or None

    @staticmethod
    def _clean_modal_text(value: Any, limit: int) -> str:
        if value in (None, "None"):
            return ""
        return str(value).strip()[:limit]

    @staticmethod
    def _clean_modal_bool(value: Any, default: bool = True) -> bool:
        if isinstance(value, bool):
            return value
        if value is None:
            return default
        lowered = str(value).strip().lower()
        if lowered in {"yes", "y", "true", "t", "1", "enable", "enabled", "on"}:
            return True
        if lowered in {"no", "n", "false", "f", "0", "disable", "disabled", "off"}:
            return False
        return default

    @staticmethod
    def _clean_modal_int(
        value: Any,
        *,
        default: Optional[int] = None,
        minimum: Optional[int] = None,
        maximum: Optional[int] = None,
    ) -> Optional[int]:
        if value in (None, "", "None"):
            return default
        try:
            cleaned = int(value)
        except (TypeError, ValueError):
            return default
        if minimum is not None:
            cleaned = max(minimum, cleaned)
        if maximum is not None:
            cleaned = min(maximum, cleaned)
        return cleaned

    @classmethod
    def _modal_type_name(cls, value: Any) -> Optional[str]:
        cleaned = cls._clean_modal_text(value, 20).lower()
        aliases = {
            "": "text",
            "text": "text",
            "short": "text",
            "paragraph": "text",
            "choice": "choice",
            "choices": "choice",
            "dropdown": "choice",
            "select": "choice",
            "boolean": "boolean",
            "bool": "boolean",
            "yesno": "boolean",
            "yes/no": "boolean",
        }
        return aliases.get(cleaned)

    @classmethod
    def _clean_modal_choices(cls, value: Any) -> List[str]:
        if isinstance(value, str):
            raw_choices = value.split(",")
        elif isinstance(value, (list, tuple)):
            raw_choices = value
        else:
            raw_choices = []
        choices: List[str] = []
        for raw_choice in raw_choices:
            choice = cls._clean_modal_text(raw_choice, 100)
            if choice and choice not in choices:
                choices.append(choice)
            if len(choices) >= 25:
                break
        return choices

    @classmethod
    def _sanitize_modal_fields(cls, value: Any) -> Optional[List[ModalFieldRecord]]:
        if not isinstance(value, list):
            return None
        fields: List[ModalFieldRecord] = []
        for raw_field in value[:5]:
            if not isinstance(raw_field, dict):
                continue
            label = cls._clean_modal_text(raw_field.get("label"), 45)
            if not label:
                continue
            question_type = cls._modal_type_name(raw_field.get("type")) or "text"
            choices = cls._clean_modal_choices(raw_field.get("choices"))
            if question_type == "choice" and len(choices) < 2:
                question_type = "text"
                choices = []
            style = (
                cls._clean_modal_int(raw_field.get("style"), default=2, minimum=1, maximum=2)
                or 2
            )
            min_length = cls._clean_modal_int(
                raw_field.get("min_length"),
                minimum=0,
                maximum=4000,
            )
            max_length = cls._clean_modal_int(
                raw_field.get("max_length"),
                minimum=1,
                maximum=4000,
            )
            if min_length is not None and max_length is not None and min_length > max_length:
                min_length = None
            fields.append(
                {
                    "label": label,
                    "type": question_type,
                    "style": style,
                    "required": cls._clean_modal_bool(raw_field.get("required"), default=True),
                    "default": cls._clean_modal_text(raw_field.get("default"), 4000),
                    "placeholder": cls._clean_modal_text(raw_field.get("placeholder"), 100),
                    "min_length": min_length,
                    "max_length": max_length,
                    "choices": choices,
                }
            )
        return fields or None

    @staticmethod
    def _merge_profile(value: Optional[Dict[str, Any]]) -> ProfileRecord:
        profile = TicketHub._default_profile()
        if value:
            profile.update(value)
            for key in (
                "support_role_ids",
                "view_role_ids",
                "ping_role_ids",
                "whitelist_role_ids",
                "blacklist_role_ids",
            ):
                profile[key] = list(profile.get(key) or [])
            profile["creating_modal"] = TicketHub._sanitize_modal_fields(
                profile.get("creating_modal")
            )
            profile["panel_style"] = TicketHub._panel_style(profile.get("panel_style"))
            profile["ticket_mode"] = TicketHub._ticket_mode(profile)
            try:
                thread_parent_id = profile.get("thread_parent_channel_id")
                profile["thread_parent_channel_id"] = int(thread_parent_id) if thread_parent_id else None
            except (TypeError, ValueError):
                profile["thread_parent_channel_id"] = None
        return profile

    @staticmethod
    def _panel_style(value: Any) -> str:
        style = str(value or "button").strip().lower()
        if style in {"dropdown", "menu", "select", "selectmenu", "select-menu"}:
            return "dropdown"
        return "button"

    @classmethod
    def _parse_panel_style(cls, value: Any) -> str:
        style = str(value or "button").strip().lower()
        aliases = {
            "button": "button",
            "buttons": "button",
            "dropdown": "dropdown",
            "menu": "dropdown",
            "select": "dropdown",
            "selectmenu": "dropdown",
            "select-menu": "dropdown",
        }
        try:
            return aliases[style]
        except KeyError as exc:
            raise commands.BadArgument(
                "Panel style must be `button` or `dropdown`."
            ) from exc

    def _panel_view_for_style(self, style: Any) -> discord.ui.View:
        if self._panel_style(style) == "dropdown":
            return self._panel_select_view
        return self._panel_view

    @classmethod
    def _sanitize_multi_panel_record(
        cls,
        value: Any,
        *,
        message_id: Optional[int] = None,
    ) -> Optional[MultiPanelRecord]:
        if not isinstance(value, dict):
            return None
        try:
            cleaned_message_id = int(value.get("message_id") or message_id or 0)
            channel_id = int(value.get("channel_id") or 0)
        except (TypeError, ValueError):
            return None
        if not cleaned_message_id or not channel_id:
            return None
        options: List[Dict[str, Any]] = []
        seen_profiles = set()
        for raw_option in (value.get("options") or [])[:25]:
            if not isinstance(raw_option, dict):
                continue
            try:
                profile_name = cls._clean_name(str(raw_option.get("profile") or ""))
            except commands.BadArgument:
                continue
            if profile_name in seen_profiles:
                continue
            label = str(raw_option.get("label") or "").strip()[:80]
            if not label:
                continue
            description = str(raw_option.get("description") or "").strip()[:100]
            emoji = str(raw_option.get("emoji") or "").strip()[:100]
            options.append(
                {
                    "profile": profile_name,
                    "label": label,
                    "description": description or None,
                    "emoji": emoji or None,
                }
            )
            seen_profiles.add(profile_name)
        placeholder = str(value.get("placeholder") or "Choose a ticket type...").strip()
        return {
            "channel_id": channel_id,
            "message_id": cleaned_message_id,
            "style": cls._panel_style(value.get("style")),
            "placeholder": placeholder[:100] or "Choose a ticket type...",
            "options": options,
        }

    @staticmethod
    def _multi_panel_emoji(value: str) -> Optional[str]:
        emoji = value.strip()
        if emoji.lower() in {"none", "no", "off", "clear", "-"}:
            return None
        if not emoji or len(emoji) > 100:
            raise commands.BadArgument(
                "Provide one Unicode/custom emoji, or use `none`."
            )
        return emoji

    @staticmethod
    def _multi_panel_option_text(details: str) -> Tuple[str, Optional[str]]:
        label, separator, description = details.partition("|")
        label = label.strip()
        description = description.strip() if separator else ""
        if not 1 <= len(label) <= 80:
            raise commands.BadArgument(
                "Multi-panel option names must be between 1 and 80 characters."
            )
        if len(description) > 100:
            raise commands.BadArgument(
                "Multi-panel option descriptions cannot exceed 100 characters."
            )
        return label, description or None

    def _build_multi_panel_view(
        self,
        record: MultiPanelRecord,
    ) -> TicketMultiPanelView:
        cleaned = self._sanitize_multi_panel_record(record)
        if cleaned is None or not cleaned["options"]:
            raise commands.BadArgument(
                "A multi-panel needs at least one valid profile option."
            )
        try:
            return TicketMultiPanelView(
                self,
                int(cleaned["message_id"]),
                cleaned,
            )
        except (TypeError, ValueError) as exc:
            raise commands.BadArgument(
                "One of the configured panel emojis is not valid for Discord."
            ) from exc

    async def _restore_multi_panel_views(self) -> None:
        all_guilds = await self.config.all_guilds()
        for guild_data in all_guilds.values():
            multi_panels = guild_data.get("multi_panels") or {}
            if not isinstance(multi_panels, dict):
                continue
            for message_key, raw_record in multi_panels.items():
                try:
                    message_id = int(message_key)
                except (TypeError, ValueError):
                    continue
                record = self._sanitize_multi_panel_record(
                    raw_record,
                    message_id=message_id,
                )
                if record is None or not record["options"]:
                    continue
                try:
                    view = self._build_multi_panel_view(record)
                    self.bot.add_view(view, message_id=message_id)
                except (commands.CommandError, TypeError, ValueError):
                    log.exception(
                        "Failed to restore TicketHub multi-panel message %s.",
                        message_id,
                    )
                    continue
                self._multi_panel_views[message_id] = view

    async def _get_multi_panel_record(
        self,
        guild: discord.Guild,
        message_id: int,
    ) -> MultiPanelRecord:
        panels = await self.config.guild(guild).multi_panels()
        record = self._sanitize_multi_panel_record(
            panels.get(str(message_id)),
            message_id=message_id,
        )
        if record is None:
            raise commands.BadArgument(
                "That message is not a tracked TicketHub multi-panel."
            )
        return record

    async def _save_multi_panel(
        self,
        guild: discord.Guild,
        message: discord.Message,
        record: MultiPanelRecord,
    ) -> MultiPanelRecord:
        cleaned = self._sanitize_multi_panel_record(record, message_id=message.id)
        if cleaned is None or not cleaned["options"]:
            raise commands.BadArgument(
                "A multi-panel needs at least one valid profile option."
            )
        view = self._build_multi_panel_view(cleaned)
        panels = await self.config.guild(guild).multi_panels()
        previous_record = self._sanitize_multi_panel_record(
            panels.get(str(message.id)),
            message_id=message.id,
        )
        previous_view = self._multi_panel_views.get(message.id)
        if previous_view is not None:
            previous_view.stop()
        try:
            await message.edit(view=view)
        except discord.HTTPException as exc:
            if previous_record is not None and previous_record["options"]:
                restored_view = self._build_multi_panel_view(previous_record)
                self.bot.add_view(restored_view, message_id=message.id)
                self._multi_panel_views[message.id] = restored_view
            raise commands.CommandError(
                "I could not update that multi-panel message."
            ) from exc
        async with self.config.guild(guild).multi_panels() as panels:
            panels[str(message.id)] = cleaned
        self._multi_panel_views[message.id] = view
        return cleaned

    async def _clear_multi_panel(
        self,
        guild: discord.Guild,
        message: discord.Message,
    ) -> None:
        await self._get_multi_panel_record(guild, message.id)
        try:
            await message.edit(view=None)
        except discord.HTTPException as exc:
            raise commands.CommandError(
                "I could not remove the components from that message."
            ) from exc
        async with self.config.guild(guild).multi_panels() as panels:
            panels.pop(str(message.id), None)
        view = self._multi_panel_views.pop(message.id, None)
        if view is not None:
            view.stop()

    @staticmethod
    def _ticket_mode(profile: ProfileRecord) -> str:
        mode = str(profile.get("ticket_mode") or "channel").lower()
        return "thread" if mode == "thread" else "channel"

    async def _get_profiles(self, guild: discord.Guild) -> Dict[str, ProfileRecord]:
        raw_profiles = await self.config.guild(guild).profiles()
        if not raw_profiles:
            raw_profiles = {"main": self._default_profile()}
            await self.config.guild(guild).profiles.set(raw_profiles)
        return {
            self._clean_name(name): self._merge_profile(profile)
            for name, profile in raw_profiles.items()
        }

    async def _get_profile(self, guild: discord.Guild, profile_name: str = "main") -> ProfileRecord:
        profiles = await self._get_profiles(guild)
        key = self._clean_name(profile_name)
        if key not in profiles:
            raise commands.BadArgument(f"No TicketHub profile named `{key}` exists.")
        return profiles[key]

    async def _set_profile(
        self,
        guild: discord.Guild,
        profile_name: str,
        profile: ProfileRecord,
    ) -> None:
        key = self._clean_name(profile_name)
        async with self.config.guild(guild).profiles() as profiles:
            profiles[key] = self._merge_profile(profile)

    async def _ensure_profile(self, guild: discord.Guild, profile_name: str = "main") -> ProfileRecord:
        key = self._clean_name(profile_name)
        async with self.config.guild(guild).profiles() as profiles:
            profile = self._merge_profile(profiles.get(key))
            profiles[key] = profile
            return profile

    @staticmethod
    def _profile_channel(
        guild: discord.Guild,
        profile: ProfileRecord,
        key: str,
    ) -> Optional[discord.TextChannel]:
        channel_id = profile.get(key)
        if not channel_id:
            return None
        try:
            channel = guild.get_channel(int(channel_id))
        except (TypeError, ValueError):
            return None
        return channel if isinstance(channel, discord.TextChannel) else None

    @staticmethod
    def _thread_parent_channel(
        guild: discord.Guild,
        profile: ProfileRecord,
    ) -> Optional[discord.TextChannel]:
        for key in ("thread_parent_channel_id", "panel_channel_id"):
            channel = TicketHub._profile_channel(guild, profile, key)
            if channel is not None:
                return channel
        return None

    @staticmethod
    def _profile_category(
        guild: discord.Guild,
        profile: ProfileRecord,
        key: str,
    ) -> Optional[discord.CategoryChannel]:
        channel_id = profile.get(key)
        if not channel_id:
            return None
        try:
            channel = guild.get_channel(int(channel_id))
        except (TypeError, ValueError):
            return None
        return channel if isinstance(channel, discord.CategoryChannel) else None

    @staticmethod
    def _role_mentions(guild: discord.Guild, role_ids: Sequence[int]) -> str:
        mentions = []
        for role_id in role_ids:
            role = guild.get_role(int(role_id))
            if role is not None:
                mentions.append(role.mention)
        return " ".join(mentions)

    @staticmethod
    def _member_has_any_role(member: discord.Member, role_ids: Sequence[int]) -> bool:
        if not role_ids:
            return False
        member_role_ids = {role.id for role in member.roles}
        return any(int(role_id) in member_role_ids for role_id in role_ids)

    def _is_support_member(self, member: discord.Member, profile: ProfileRecord) -> bool:
        if member.guild_permissions.manage_guild:
            return True
        return self._member_has_any_role(member, profile.get("support_role_ids") or [])

    def _can_create_ticket(self, member: discord.Member, profile: ProfileRecord) -> Tuple[bool, str]:
        blacklist = profile.get("blacklist_role_ids") or []
        whitelist = profile.get("whitelist_role_ids") or []
        if self._member_has_any_role(member, blacklist):
            return False, "Your roles are blocked from opening tickets."
        if whitelist and not self._member_has_any_role(member, whitelist):
            return False, "You do not have a role allowed to open tickets."
        return True, ""

    def _validate_thread_parent_permissions(
        self,
        guild: discord.Guild,
        owner: discord.Member,
        profile: ProfileRecord,
    ) -> None:
        parent = self._thread_parent_channel(guild, profile)
        if parent is None:
            raise commands.CommandError(
                "Thread ticket mode needs a thread parent channel. "
                "Set one with `[p]tickethub threadparent <profile> #channel`."
            )
        me = guild.me
        if me is None:
            raise commands.CommandError("I could not inspect my server permissions.")

        bot_perms = parent.permissions_for(me)
        missing = []
        if not bot_perms.view_channel:
            missing.append("View Channel")
        if not getattr(bot_perms, "create_private_threads", False):
            missing.append("Create Private Threads")
        if not getattr(bot_perms, "send_messages_in_threads", False):
            missing.append("Send Messages in Threads")
        if not getattr(bot_perms, "manage_threads", False):
            missing.append("Manage Threads")
        if not bot_perms.read_message_history:
            missing.append("Read Message History")
        if not bot_perms.embed_links:
            missing.append("Embed Links")
        if missing:
            raise commands.CommandError(
                f"I need {', '.join(missing)} in {parent.mention} to create thread tickets."
            )

        owner_perms = parent.permissions_for(owner)
        owner_missing = []
        if not owner_perms.view_channel:
            owner_missing.append("View Channel")
        if not getattr(owner_perms, "send_messages_in_threads", False):
            owner_missing.append("Send Messages in Threads")
        if not owner_perms.read_message_history:
            owner_missing.append("Read Message History")
        if owner_missing:
            raise commands.CommandError(
                f"{owner.mention} needs {', '.join(owner_missing)} in {parent.mention} "
                "to use thread tickets."
            )

    async def _validate_ticket_open_request(
        self,
        guild: discord.Guild,
        owner: discord.Member,
        profile_name: str,
    ) -> Tuple[str, ProfileRecord]:
        if not await self.config.guild(guild).enabled():
            raise commands.CommandError("TicketHub is not enabled yet.")

        profile_name = self._clean_name(profile_name)
        profile = await self._get_profile(guild, profile_name)
        if not profile.get("enabled"):
            raise commands.CommandError(f"TicketHub profile `{profile_name}` is disabled.")

        allowed, denial = self._can_create_ticket(owner, profile)
        if not allowed:
            raise commands.CommandError(denial)

        max_open = int(profile.get("max_open_tickets_by_member") or 0)
        if max_open > 0:
            open_count = await self._user_open_ticket_count(guild, owner.id, profile_name)
            if open_count >= max_open:
                raise commands.CommandError(
                    f"You already have {open_count} open ticket(s) for `{profile_name}`."
                )

        me = guild.me
        if me is None:
            raise commands.CommandError("I could not inspect my server permissions.")
        if self._ticket_mode(profile) == "thread":
            self._validate_thread_parent_permissions(guild, owner, profile)
        elif not me.guild_permissions.manage_channels:
            raise commands.CommandError("I need `Manage Channels` to create ticket channels.")

        return profile_name, profile

    async def _user_open_ticket_count(
        self,
        guild: discord.Guild,
        owner_id: int,
        profile_name: Optional[str] = None,
    ) -> int:
        tickets = await self.config.guild(guild).tickets()
        return sum(
            1
            for record in tickets.values()
            if str(record.get("owner_id")) == str(owner_id)
            and record.get("status") == "open"
            and (profile_name is None or record.get("profile") == profile_name)
        )

    @classmethod
    def _clean_form_answers(
        cls,
        answers: Optional[Sequence[Dict[str, str]]],
    ) -> List[Dict[str, str]]:
        if not isinstance(answers, list):
            return []
        cleaned_answers = []
        for answer in answers or []:
            if not isinstance(answer, dict):
                continue
            label = cls._clean_modal_text(answer.get("label"), 45)
            value = cls._clean_modal_text(answer.get("value"), 4000)
            if label and value:
                cleaned_answers.append({"label": label, "value": value})
        return cleaned_answers[:5]

    @staticmethod
    def _truncate_field(value: str, limit: int) -> str:
        if len(value) <= limit:
            return value
        return value[: limit - 3] + "..."

    def _format_template(
        self,
        template: Optional[str],
        *,
        ticket_id: int,
        owner: discord.Member,
        guild: discord.Guild,
        profile: str,
    ) -> str:
        template = template or "ticket-{id}-{owner_name}"
        values = {
            "id": str(ticket_id),
            "owner_display_name": owner.display_name,
            "owner_name": owner.name,
            "owner_mention": owner.mention,
            "owner_id": str(owner.id),
            "guild_name": guild.name,
            "guild_id": str(guild.id),
            "profile": profile,
        }
        rendered = template
        for key, value in values.items():
            rendered = rendered.replace("{" + key + "}", value)
        rendered = rendered.lower()
        rendered = re.sub(r"[^a-z0-9_-]+", "-", rendered)
        rendered = rendered.strip("-_") or f"ticket-{ticket_id}"
        return rendered[:95]

    def _ticket_embed(
        self,
        guild: discord.Guild,
        record: TicketRecord,
        profile: ProfileRecord,
    ) -> discord.Embed:
        status = str(record.get("status") or "open")
        color = self.OPEN_COLOR if status == "open" else self.CLOSED_COLOR
        if record.get("claimed_by") and status == "open":
            color = self.CLAIMED_COLOR
        embed = discord.Embed(
            title=f"Ticket #{record.get('id')}",
            description=str(record.get("reason") or "No reason provided."),
            color=color,
            timestamp=self._now(),
        )
        embed.add_field(name="Status", value=status.title(), inline=True)
        embed.add_field(name="Owner", value=self._user_ref(record.get("owner_id")), inline=True)
        embed.add_field(name="Profile", value=f"`{record.get('profile')}`", inline=True)
        embed.add_field(
            name="Claimed By",
            value=self._user_ref(record.get("claimed_by")),
            inline=True,
        )
        embed.add_field(
            name="Created",
            value=self._format_ts(record.get("created_at"), "R"),
            inline=True,
        )
        if record.get("closed_at"):
            embed.add_field(
                name="Closed",
                value=self._format_ts(record.get("closed_at"), "R"),
                inline=True,
            )
            if record.get("close_reason"):
                embed.add_field(name="Close Reason", value=str(record["close_reason"])[:1024], inline=False)
        for answer in self._clean_form_answers(record.get("form_answers")):
            embed.add_field(
                name=self._truncate_field(f"Form: {answer['label']}", 256),
                value=self._truncate_field(answer["value"], 1024),
                inline=False,
            )
        embed.set_footer(text=f"Ticket ID: {record.get('id')}")
        return embed

    def _panel_embed(
        self,
        guild: discord.Guild,
        profile_name: str,
        profile: ProfileRecord,
    ) -> discord.Embed:
        embed = discord.Embed(
            title=str(profile.get("panel_title") or "Need Help?"),
            description=str(profile.get("panel_message") or "Open a ticket for support."),
            color=self.DEFAULT_COLOR,
            timestamp=self._now(),
        )
        embed.add_field(name="Profile", value=f"`{profile_name}`", inline=True)
        max_open = int(profile.get("max_open_tickets_by_member") or 0)
        embed.add_field(name="Max Open", value=str(max_open), inline=True)
        if guild.icon:
            embed.set_author(name=guild.name, icon_url=guild.icon.url)
        else:
            embed.set_author(name=guild.name)
        embed.set_footer(text="TicketHub")
        return embed

    async def _send_log(
        self,
        guild: discord.Guild,
        profile: ProfileRecord,
        title: str,
        description: str,
        *,
        color: Optional[int] = None,
    ) -> None:
        channel = self._profile_channel(guild, profile, "log_channel_id")
        if channel is None:
            return
        me = guild.me
        if me is None:
            return
        perms = channel.permissions_for(me)
        if not perms.send_messages or not perms.embed_links:
            return
        embed = discord.Embed(
            title=title,
            description=description,
            color=color or self.DEFAULT_COLOR,
            timestamp=self._now(),
        )
        try:
            await channel.send(embed=embed, allowed_mentions=discord.AllowedMentions.none())
        except discord.HTTPException:
            log.exception("Failed to send TicketHub log in guild %s", guild.id)

    async def _fetch_ticket_channel(
        self,
        guild: discord.Guild,
        record: TicketRecord,
    ) -> Optional[TicketLocation]:
        channel_id = record.get("channel_id")
        if not channel_id:
            return None
        channel_id = int(channel_id)
        channel = guild.get_channel(channel_id)
        if isinstance(channel, (discord.TextChannel, discord.Thread)):
            return channel
        get_thread = getattr(guild, "get_thread", None)
        if callable(get_thread):
            thread = get_thread(channel_id)
            if isinstance(thread, discord.Thread):
                return thread
        try:
            channel = await guild.fetch_channel(channel_id)
        except (discord.NotFound, discord.Forbidden, discord.HTTPException):
            return None
        return channel if isinstance(channel, (discord.TextChannel, discord.Thread)) else None

    async def _find_ticket_by_channel(
        self,
        guild: discord.Guild,
        channel_id: int,
    ) -> Tuple[str, TicketRecord]:
        tickets = await self.config.guild(guild).tickets()
        for key, record in tickets.items():
            if int(record.get("channel_id") or 0) == int(channel_id):
                return key, record
        raise commands.BadArgument("This channel or thread is not a tracked TicketHub ticket.")

    async def _find_ticket_by_control_message(
        self,
        guild: discord.Guild,
        message_id: int,
    ) -> Tuple[str, TicketRecord]:
        tickets = await self.config.guild(guild).tickets()
        for key, record in tickets.items():
            if int(record.get("message_id") or 0) == int(message_id):
                return key, record
        raise commands.BadArgument("This message is not a tracked TicketHub ticket.")

    async def _find_panel_profile(
        self,
        guild: discord.Guild,
        message_id: int,
    ) -> Tuple[str, ProfileRecord]:
        profiles = await self._get_profiles(guild)
        for name, profile in profiles.items():
            if int(profile.get("panel_message_id") or 0) == int(message_id):
                return name, profile
        raise commands.BadArgument("This panel is not tracked by TicketHub.")

    async def handle_panel_open(
        self,
        interaction: discord.Interaction,
        profile_name: Optional[str] = None,
    ) -> None:
        """Open a ticket from a persistent panel button."""
        if not interaction.guild or not isinstance(interaction.user, discord.Member):
            await interaction.response.send_message("This button only works in a server.", ephemeral=True)
            return
        if interaction.message is None:
            await interaction.response.send_message("I could not identify this panel.", ephemeral=True)
            return
        try:
            if profile_name is None:
                profile_name, profile = await self._find_panel_profile(
                    interaction.guild,
                    interaction.message.id,
                )
            else:
                profile_name = self._clean_name(profile_name)
                profile = await self._get_profile(interaction.guild, profile_name)
            modal_fields = profile.get("creating_modal")
            if modal_fields:
                await self._validate_ticket_open_request(
                    interaction.guild,
                    interaction.user,
                    profile_name,
                )
                if MODAL_SELECTS_SUPPORTED or all(
                    str(field.get("type") or "text") == "text" for field in modal_fields
                ):
                    await interaction.response.send_modal(
                        TicketOpenModal(
                            self,
                            interaction.guild,
                            interaction.user,
                            profile_name,
                            modal_fields,
                        )
                    )
                else:
                    questionnaire = TicketQuestionnaireView(
                        self,
                        interaction.guild,
                        interaction.user,
                        profile_name,
                        modal_fields,
                    )
                    await interaction.response.send_message(
                        embed=questionnaire.question_embed(),
                        view=questionnaire,
                        ephemeral=True,
                    )
                return
        except commands.CommandError as error:
            await interaction.response.send_message(str(error), ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True, thinking=True)
        try:
            record, channel = await self._create_ticket(
                interaction.guild,
                interaction.user,
                profile_name,
                reason="Opened from ticket panel.",
            )
        except commands.CommandError as error:
            await interaction.followup.send(str(error), ephemeral=True)
            return
        await interaction.followup.send(
            f"Ticket #{record['id']} opened: {channel.mention}",
            ephemeral=True,
        )

    async def handle_ticket_button(self, interaction: discord.Interaction, action: str) -> None:
        """Handle ticket control buttons."""
        if not interaction.guild or not isinstance(interaction.user, discord.Member):
            await interaction.response.send_message("This button only works in a server.", ephemeral=True)
            return
        if interaction.message is None:
            await interaction.response.send_message("I could not identify this ticket.", ephemeral=True)
            return
        await interaction.response.defer(ephemeral=True, thinking=True)
        try:
            _key, record = await self._find_ticket_by_control_message(
                interaction.guild,
                interaction.message.id,
            )
            profile = await self._get_profile(interaction.guild, str(record.get("profile") or "main"))
            if action == "claim":
                await self._claim_ticket(interaction.guild, record, interaction.user)
                await interaction.followup.send("Ticket claimed.", ephemeral=True)
            elif action == "close":
                await self._close_ticket(
                    interaction.guild,
                    record,
                    interaction.user,
                    reason="Closed from ticket controls.",
                )
                await interaction.followup.send("Ticket closed.", ephemeral=True)
            elif action == "transcript":
                if not self._is_support_member(interaction.user, profile):
                    await interaction.followup.send(
                        "Only support staff can generate transcripts from this button.",
                        ephemeral=True,
                    )
                    return
                result = await self._send_transcript_bundle(
                    interaction.guild,
                    record,
                    profile,
                    requested_by=interaction.user,
                )
                await interaction.followup.send(result, ephemeral=True)
        except commands.CommandError as error:
            await interaction.followup.send(str(error), ephemeral=True)

    async def _create_ticket(
        self,
        guild: discord.Guild,
        owner: discord.Member,
        profile_name: str,
        *,
        reason: Optional[str] = None,
        form_answers: Optional[Sequence[Dict[str, str]]] = None,
    ) -> Tuple[TicketRecord, TicketLocation]:
        profile_name, profile = await self._validate_ticket_open_request(
            guild,
            owner,
            profile_name,
        )
        clean_form_answers = self._clean_form_answers(form_answers)

        async with self._guild_lock(guild.id):
            ticket_id = int(await self.config.guild(guild).next_ticket_id())
            category = self._profile_category(guild, profile, "ticket_category_id")
            channel_name = self._format_template(
                profile.get("channel_name"),
                ticket_id=ticket_id,
                owner=owner,
                guild=guild,
                profile=profile_name,
            )
            mode = self._ticket_mode(profile)
            if mode == "thread":
                channel = await self._create_ticket_thread(
                    guild,
                    owner,
                    profile,
                    channel_name,
                    ticket_id,
                )
            else:
                overwrites = self._ticket_overwrites(guild, owner, profile, closed=False)
                try:
                    channel = await guild.create_text_channel(
                        channel_name,
                        category=category,
                        overwrites=overwrites,
                        reason=f"TicketHub ticket #{ticket_id} opened by {owner}",
                    )
                except discord.HTTPException as exc:
                    raise commands.CommandError("I could not create the ticket channel.") from exc

            record: TicketRecord = {
                "id": ticket_id,
                "profile": profile_name,
                "owner_id": owner.id,
                "channel_id": channel.id,
                "location_type": mode,
                "thread_parent_channel_id": (
                    channel.parent_id if isinstance(channel, discord.Thread) else None
                ),
                "message_id": None,
                "status": "open",
                "claimed_by": None,
                "reason": (reason or "No reason provided.")[:1000],
                "form_answers": clean_form_answers,
                "created_at": self._now_ts(),
                "closed_at": None,
                "closed_by": None,
                "close_reason": None,
                "participants": [owner.id],
                "events": [
                    {
                        "type": "created",
                        "actor_id": owner.id,
                        "at": self._now_ts(),
                        "reason": reason,
                    }
                ],
                "transcript_count": 0,
            }

            welcome = self._render_ticket_text(profile.get("welcome_message"), owner, guild, ticket_id)
            custom = self._render_ticket_text(profile.get("custom_message"), owner, guild, ticket_id)
            ping_text = self._role_mentions(guild, profile.get("ping_role_ids") or [])
            intro = "\n".join(part for part in (owner.mention, ping_text, welcome, custom) if part)
            embed = self._ticket_embed(guild, record, profile)
            try:
                message = await channel.send(
                    intro[:1900] if intro else owner.mention,
                    embed=embed,
                    view=self._control_view,
                    allowed_mentions=discord.AllowedMentions(users=True, roles=True, everyone=False),
                )
            except discord.HTTPException as exc:
                try:
                    await channel.delete(reason="TicketHub failed to send ticket controls.")
                except discord.HTTPException:
                    pass
                raise commands.CommandError("I created the ticket but could not send the ticket panel.") from exc
            record["message_id"] = message.id
            async with self.config.guild(guild).tickets() as tickets:
                tickets[str(ticket_id)] = record
            await self.config.guild(guild).next_ticket_id.set(ticket_id + 1)

        await self._send_log(
            guild,
            profile,
            "Ticket Opened",
            f"Ticket #{ticket_id} opened by {owner.mention}: {channel.mention}",
            color=self.OPEN_COLOR,
        )
        return record, channel

    async def _create_ticket_thread(
        self,
        guild: discord.Guild,
        owner: discord.Member,
        profile: ProfileRecord,
        channel_name: str,
        ticket_id: int,
    ) -> discord.Thread:
        parent = self._thread_parent_channel(guild, profile)
        if parent is None:
            raise commands.CommandError(
                "Thread ticket mode needs a thread parent channel. "
                "Set one with `[p]tickethub threadparent <profile> #channel`."
            )
        try:
            try:
                thread = await parent.create_thread(
                    name=channel_name,
                    type=discord.ChannelType.private_thread,
                    invitable=False,
                    reason=f"TicketHub ticket #{ticket_id} opened by {owner}",
                )
            except TypeError:
                thread = await parent.create_thread(
                    name=channel_name,
                    type=discord.ChannelType.private_thread,
                    reason=f"TicketHub ticket #{ticket_id} opened by {owner}",
                )
        except discord.HTTPException as exc:
            raise commands.CommandError("I could not create the ticket thread.") from exc

        try:
            await thread.add_user(owner)
        except discord.HTTPException as exc:
            try:
                await thread.delete(reason="TicketHub failed to add ticket owner.")
            except discord.HTTPException:
                pass
            raise commands.CommandError(
                "I created the ticket thread but could not add the ticket owner."
            ) from exc

        await self._add_cached_support_members_to_thread(guild, thread, profile, owner)
        return thread

    async def _add_cached_support_members_to_thread(
        self,
        guild: discord.Guild,
        thread: discord.Thread,
        profile: ProfileRecord,
        owner: discord.Member,
    ) -> None:
        members: Dict[int, discord.Member] = {}
        for role_id in profile.get("support_role_ids") or []:
            role = guild.get_role(int(role_id))
            if role is None:
                continue
            for member in role.members:
                if member.id != owner.id and not member.bot:
                    members[member.id] = member
        for member in members.values():
            try:
                await thread.add_user(member)
            except discord.HTTPException:
                log.debug(
                    "Failed to add support member %s to TicketHub thread %s in guild %s",
                    member.id,
                    thread.id,
                    guild.id,
                )

    def _ticket_overwrites(
        self,
        guild: discord.Guild,
        owner: Optional[discord.Member],
        profile: ProfileRecord,
        *,
        closed: bool,
    ) -> Dict[discord.abc.Snowflake, discord.PermissionOverwrite]:
        overwrites: Dict[discord.abc.Snowflake, discord.PermissionOverwrite] = {
            guild.default_role: discord.PermissionOverwrite(view_channel=False),
        }
        me = guild.me
        if me is not None:
            overwrites[me] = discord.PermissionOverwrite(
                view_channel=True,
                send_messages=True,
                read_message_history=True,
                manage_channels=True,
                manage_messages=True,
                attach_files=True,
                embed_links=True,
            )
        if owner is not None:
            overwrites[owner] = discord.PermissionOverwrite(
                view_channel=True,
                send_messages=not closed,
                read_message_history=True,
                attach_files=not closed,
                embed_links=not closed,
            )
        for role_id in profile.get("support_role_ids") or []:
            role = guild.get_role(int(role_id))
            if role is not None:
                overwrites[role] = discord.PermissionOverwrite(
                    view_channel=True,
                    send_messages=True,
                    read_message_history=True,
                    attach_files=True,
                    embed_links=True,
                )
        for role_id in profile.get("view_role_ids") or []:
            role = guild.get_role(int(role_id))
            if role is not None and role not in overwrites:
                overwrites[role] = discord.PermissionOverwrite(
                    view_channel=True,
                    send_messages=False,
                    read_message_history=True,
                )
        return overwrites

    @staticmethod
    def _render_ticket_text(
        template: Optional[str],
        owner: discord.Member,
        guild: discord.Guild,
        ticket_id: int,
    ) -> str:
        if not template:
            return ""
        values = {
            "id": str(ticket_id),
            "owner_display_name": owner.display_name,
            "owner_name": owner.name,
            "owner_mention": owner.mention,
            "owner_id": str(owner.id),
            "guild_name": guild.name,
            "guild_id": str(guild.id),
        }
        rendered = str(template)
        for key, value in values.items():
            rendered = rendered.replace("{" + key + "}", value)
        return rendered

    async def _update_ticket_message(
        self,
        guild: discord.Guild,
        record: TicketRecord,
        profile: Optional[ProfileRecord] = None,
    ) -> None:
        profile = profile or await self._get_profile(guild, str(record.get("profile") or "main"))
        channel = await self._fetch_ticket_channel(guild, record)
        if channel is None or not record.get("message_id"):
            return
        try:
            message = await channel.fetch_message(int(record["message_id"]))
            await message.edit(embed=self._ticket_embed(guild, record, profile), view=self._control_view)
        except discord.HTTPException:
            log.exception("Failed to update TicketHub ticket message in guild %s", guild.id)

    async def _claim_ticket(
        self,
        guild: discord.Guild,
        record: TicketRecord,
        member: discord.Member,
    ) -> None:
        profile = await self._get_profile(guild, str(record.get("profile") or "main"))
        if not self._is_support_member(member, profile):
            raise commands.CommandError("Only support staff can claim tickets.")
        if record.get("status") != "open":
            raise commands.CommandError("Only open tickets can be claimed.")
        record["claimed_by"] = member.id
        record.setdefault("events", []).append(
            {"type": "claimed", "actor_id": member.id, "at": self._now_ts()}
        )
        async with self.config.guild(guild).tickets() as tickets:
            tickets[str(record["id"])] = record
        await self._update_ticket_message(guild, record, profile)
        await self._send_log(
            guild,
            profile,
            "Ticket Claimed",
            f"Ticket #{record['id']} claimed by {member.mention}.",
            color=self.CLAIMED_COLOR,
        )

    async def _unclaim_ticket(
        self,
        guild: discord.Guild,
        record: TicketRecord,
        member: discord.Member,
    ) -> None:
        profile = await self._get_profile(guild, str(record.get("profile") or "main"))
        if not self._is_support_member(member, profile):
            raise commands.CommandError("Only support staff can unclaim tickets.")
        record["claimed_by"] = None
        record.setdefault("events", []).append(
            {"type": "unclaimed", "actor_id": member.id, "at": self._now_ts()}
        )
        async with self.config.guild(guild).tickets() as tickets:
            tickets[str(record["id"])] = record
        await self._update_ticket_message(guild, record, profile)
        await self._send_log(
            guild,
            profile,
            "Ticket Unclaimed",
            f"Ticket #{record['id']} unclaimed by {member.mention}.",
            color=self.DEFAULT_COLOR,
        )

    async def _close_ticket(
        self,
        guild: discord.Guild,
        record: TicketRecord,
        member: discord.Member,
        *,
        reason: Optional[str] = None,
    ) -> None:
        profile = await self._get_profile(guild, str(record.get("profile") or "main"))
        owner = guild.get_member(int(record["owner_id"])) if record.get("owner_id") else None
        owner_is_closing = owner is not None and owner.id == member.id
        if not self._is_support_member(member, profile):
            if not (owner_is_closing and profile.get("owner_can_close")):
                raise commands.CommandError("You do not have permission to close this ticket.")
        if record.get("status") == "closed":
            raise commands.CommandError("This ticket is already closed.")

        record["status"] = "closed"
        record["closed_at"] = self._now_ts()
        record["closed_by"] = member.id
        record["close_reason"] = (reason or "No reason provided.")[:1000]
        record.setdefault("events", []).append(
            {
                "type": "closed",
                "actor_id": member.id,
                "at": self._now_ts(),
                "reason": record["close_reason"],
            }
        )
        channel = await self._fetch_ticket_channel(guild, record)
        if channel is not None:
            if isinstance(channel, discord.Thread):
                try:
                    if channel.archived or channel.locked:
                        await channel.edit(
                            archived=False,
                            locked=False,
                            reason=f"TicketHub ticket #{record['id']} preparing to close",
                        )
                    await channel.send(
                        f"Ticket closed by {member.mention}. Reason: {record['close_reason']}",
                        allowed_mentions=discord.AllowedMentions(users=True, roles=False, everyone=False),
                    )
                except discord.HTTPException:
                    log.exception("Failed to post closed ticket thread notice in guild %s", guild.id)
            else:
                overwrites = self._ticket_overwrites(guild, owner, profile, closed=True)
                closed_category = self._profile_category(guild, profile, "closed_category_id")
                try:
                    await channel.edit(
                        category=closed_category or channel.category,
                        overwrites=overwrites,
                        name=f"closed-{channel.name}"[:100] if not channel.name.startswith("closed-") else channel.name,
                        reason=f"TicketHub ticket #{record['id']} closed",
                    )
                except discord.HTTPException:
                    log.exception("Failed to edit closed ticket channel in guild %s", guild.id)
                try:
                    await channel.send(
                        f"Ticket closed by {member.mention}. Reason: {record['close_reason']}",
                        allowed_mentions=discord.AllowedMentions(users=True, roles=False, everyone=False),
                    )
                except discord.HTTPException:
                    pass

        async with self.config.guild(guild).tickets() as tickets:
            tickets[str(record["id"])] = record
        await self._update_ticket_message(guild, record, profile)

        transcript_note = ""
        if profile.get("transcripts"):
            try:
                transcript_note = "\n" + await self._send_transcript_bundle(
                    guild,
                    record,
                    profile,
                    requested_by=member,
                )
            except commands.CommandError as error:
                transcript_note = f"\nTranscript failed: {error}"

        await self._send_log(
            guild,
            profile,
            "Ticket Closed",
            f"Ticket #{record['id']} closed by {member.mention}.\nReason: {record['close_reason']}",
            color=self.CLOSED_COLOR,
        )
        if channel is not None and transcript_note:
            try:
                await channel.send(transcript_note[:1900])
            except discord.HTTPException:
                pass
        if isinstance(channel, discord.Thread):
            try:
                await channel.edit(
                    name=f"closed-{channel.name}"[:100] if not channel.name.startswith("closed-") else channel.name,
                    archived=True,
                    locked=True,
                    reason=f"TicketHub ticket #{record['id']} closed",
                )
            except discord.HTTPException:
                log.exception("Failed to archive closed ticket thread in guild %s", guild.id)

    async def _reopen_ticket(
        self,
        guild: discord.Guild,
        record: TicketRecord,
        member: discord.Member,
    ) -> None:
        profile = await self._get_profile(guild, str(record.get("profile") or "main"))
        owner = guild.get_member(int(record["owner_id"])) if record.get("owner_id") else None
        owner_is_reopening = owner is not None and owner.id == member.id
        if not self._is_support_member(member, profile):
            if not (owner_is_reopening and profile.get("owner_can_reopen")):
                raise commands.CommandError("You do not have permission to reopen this ticket.")
        if record.get("status") == "open":
            raise commands.CommandError("This ticket is already open.")

        record["status"] = "open"
        record["closed_at"] = None
        record["closed_by"] = None
        record["close_reason"] = None
        record.setdefault("events", []).append(
            {"type": "reopened", "actor_id": member.id, "at": self._now_ts()}
        )
        channel = await self._fetch_ticket_channel(guild, record)
        if channel is not None:
            if isinstance(channel, discord.Thread):
                try:
                    await channel.edit(
                        archived=False,
                        locked=False,
                        name=channel.name.removeprefix("closed-")[:100],
                        reason=f"TicketHub ticket #{record['id']} reopened",
                    )
                    await channel.send(f"Ticket reopened by {member.mention}.")
                except discord.HTTPException:
                    log.exception("Failed to reopen ticket thread in guild %s", guild.id)
            else:
                open_category = self._profile_category(guild, profile, "ticket_category_id")
                overwrites = self._ticket_overwrites(guild, owner, profile, closed=False)
                try:
                    await channel.edit(
                        category=open_category or channel.category,
                        overwrites=overwrites,
                        name=channel.name.removeprefix("closed-")[:100],
                        reason=f"TicketHub ticket #{record['id']} reopened",
                    )
                    await channel.send(f"Ticket reopened by {member.mention}.")
                except discord.HTTPException:
                    log.exception("Failed to reopen ticket channel in guild %s", guild.id)
        async with self.config.guild(guild).tickets() as tickets:
            tickets[str(record["id"])] = record
        await self._update_ticket_message(guild, record, profile)
        await self._send_log(
            guild,
            profile,
            "Ticket Reopened",
            f"Ticket #{record['id']} reopened by {member.mention}.",
            color=self.OPEN_COLOR,
        )

    async def _delete_ticket_channel(
        self,
        guild: discord.Guild,
        record: TicketRecord,
        member: discord.Member,
        *,
        reason: Optional[str] = None,
    ) -> None:
        profile = await self._get_profile(guild, str(record.get("profile") or "main"))
        if not self._is_support_member(member, profile):
            raise commands.CommandError("Only support staff can delete tickets.")
        if profile.get("transcripts"):
            await self._send_transcript_bundle(guild, record, profile, requested_by=member)
        channel = await self._fetch_ticket_channel(guild, record)
        async with self.config.guild(guild).tickets() as tickets:
            tickets.pop(str(record["id"]), None)
        if channel is not None:
            try:
                await channel.delete(reason=reason or f"TicketHub ticket #{record['id']} deleted")
            except discord.HTTPException as exc:
                raise commands.CommandError("I could not delete that ticket channel or thread.") from exc
        await self._send_log(
            guild,
            profile,
            "Ticket Deleted",
            f"Ticket #{record['id']} deleted by {member.mention}.",
            color=self.CLOSED_COLOR,
        )

    async def _send_transcript_bundle(
        self,
        guild: discord.Guild,
        record: TicketRecord,
        profile: ProfileRecord,
        *,
        requested_by: Optional[discord.Member] = None,
    ) -> str:
        channel = await self._fetch_ticket_channel(guild, record)
        if channel is None:
            raise commands.CommandError("I could not find that ticket channel or thread.")
        messages = await self._collect_messages(channel)
        html_transcript = await self._render_chat_exporter_transcript(guild, channel, messages)
        if html_transcript is None:
            html_transcript = self._render_html_transcript(guild, channel, record, profile, messages)
        html_bytes = html_transcript.encode("utf-8")
        text_bytes = self._render_text_transcript(guild, channel, record, messages).encode("utf-8")
        html_file_name = f"ticket-{record['id']}-transcript.html"
        text_file_name = f"ticket-{record['id']}-transcript.txt"

        sent_targets: List[str] = []
        failed_targets: List[str] = []
        target_channel = self._profile_channel(guild, profile, "transcript_channel_id") or self._profile_channel(
            guild, profile, "log_channel_id"
        )
        if target_channel is not None:
            try:
                await target_channel.send(
                    f"Transcript for ticket #{record['id']}",
                    files=[
                        discord.File(io.BytesIO(html_bytes), filename=html_file_name),
                        discord.File(io.BytesIO(text_bytes), filename=text_file_name),
                    ],
                )
                sent_targets.append(target_channel.mention)
            except discord.HTTPException:
                log.exception("Failed to send transcript to channel in guild %s", guild.id)
                failed_targets.append(target_channel.mention)

        if profile.get("dm_transcript") and record.get("owner_id"):
            owner = guild.get_member(int(record["owner_id"]))
            if owner is None:
                try:
                    owner = await self.bot.fetch_user(int(record["owner_id"]))
                except (discord.NotFound, discord.HTTPException):
                    owner = None
            if owner is not None:
                try:
                    await owner.send(
                        f"Transcript for your ticket #{record['id']} in {guild.name}.",
                        files=[
                            discord.File(io.BytesIO(html_bytes), filename=html_file_name),
                            discord.File(io.BytesIO(text_bytes), filename=text_file_name),
                        ],
                    )
                    sent_targets.append("ticket owner DM")
                except discord.HTTPException:
                    failed_targets.append("ticket owner DM")

        record["transcript_count"] = int(record.get("transcript_count") or 0) + 1
        record.setdefault("events", []).append(
            {
                "type": "transcript",
                "actor_id": requested_by.id if requested_by else None,
                "at": self._now_ts(),
                "message_count": len(messages),
            }
        )
        async with self.config.guild(guild).tickets() as tickets:
            if str(record["id"]) in tickets:
                tickets[str(record["id"])] = record

        if sent_targets:
            result = "Transcript sent to " + ", ".join(sent_targets) + "."
            if failed_targets:
                result += " Failed to send to " + ", ".join(failed_targets) + "."
            return result
        if failed_targets:
            return "Transcript generated, but failed to send to " + ", ".join(failed_targets) + "."
        return "Transcript generated, but I could not send it to any configured destination."

    async def _collect_messages(self, channel: TicketLocation) -> List[discord.Message]:
        messages: List[discord.Message] = []
        try:
            async for message in channel.history(limit=self.MAX_TRANSCRIPT_MESSAGES, oldest_first=True):
                messages.append(message)
        except discord.HTTPException as exc:
            raise commands.CommandError("I could not read the ticket message history.") from exc
        return messages

    async def _render_chat_exporter_transcript(
        self,
        guild: discord.Guild,
        channel: TicketLocation,
        messages: Sequence[discord.Message],
    ) -> Optional[str]:
        if chat_exporter is None:
            return None
        try:
            transcript = await chat_exporter.raw_export(
                channel,
                messages=list(messages),
                tz_info="UTC",
                guild=guild,
                bot=self.bot,
                military_time=True,
                fancy_times=True,
                support_dev=False,
                raise_exceptions=True,
            )
        except Exception:
            log.exception("DiscordChatExporterPy failed for ticket transcript in guild %s", guild.id)
            return None
        if not transcript or transcript == "Whoops! Something went wrong...":
            return None
        return transcript

    def _render_text_transcript(
        self,
        guild: discord.Guild,
        channel: TicketLocation,
        record: TicketRecord,
        messages: Sequence[discord.Message],
    ) -> str:
        lines = [
            f"TicketHub Transcript - Ticket #{record.get('id')}",
            f"Server: {guild.name} ({guild.id})",
            f"Channel: #{channel.name} ({channel.id})",
            f"Owner: {record.get('owner_id')}",
            f"Status: {record.get('status')}",
            "",
        ]
        for message in messages:
            timestamp = message.created_at.astimezone(timezone.utc).isoformat()
            content = message.clean_content or ""
            lines.append(f"[{timestamp}] {message.author} ({message.author.id}): {content}")
            for attachment in message.attachments:
                lines.append(f"  Attachment: {attachment.filename} - {attachment.url}")
            for embed in message.embeds:
                if embed.title:
                    lines.append(f"  Embed title: {embed.title}")
                if embed.description:
                    lines.append(f"  Embed: {embed.description}")
        return "\n".join(lines)

    def _render_html_transcript(
        self,
        guild: discord.Guild,
        channel: TicketLocation,
        record: TicketRecord,
        profile: ProfileRecord,
        messages: Sequence[discord.Message],
    ) -> str:
        rows = []
        for message in messages:
            rows.append(self._render_html_message(message))
        events = "".join(self._render_html_event(event) for event in record.get("events", []))
        generated = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
        owner = self._user_ref(record.get("owner_id"))
        return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Ticket #{html.escape(str(record.get('id')))} Transcript</title>
<style>
:root {{
  color-scheme: dark;
  --bg: #101214;
  --panel: #171a1f;
  --panel-2: #1f232a;
  --text: #e7e9ee;
  --muted: #9ca3af;
  --accent: #5865f2;
  --border: #2b3038;
}}
* {{ box-sizing: border-box; }}
body {{
  margin: 0;
  background: var(--bg);
  color: var(--text);
  font: 14px/1.45 -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
}}
header {{
  position: sticky;
  top: 0;
  z-index: 1;
  background: rgba(16, 18, 20, 0.96);
  border-bottom: 1px solid var(--border);
  padding: 18px 22px;
}}
h1 {{ margin: 0 0 8px; font-size: 22px; }}
.meta {{ display: flex; flex-wrap: wrap; gap: 10px; color: var(--muted); }}
.meta span, .pill {{
  border: 1px solid var(--border);
  background: var(--panel);
  border-radius: 999px;
  padding: 4px 10px;
}}
main {{ display: grid; grid-template-columns: minmax(0, 1fr) 320px; gap: 18px; padding: 18px; }}
@media (max-width: 850px) {{ main {{ grid-template-columns: 1fr; }} }}
.toolbar {{ margin-top: 14px; }}
input {{
  width: min(520px, 100%);
  background: var(--panel);
  border: 1px solid var(--border);
  color: var(--text);
  border-radius: 6px;
  padding: 10px 12px;
}}
.messages, aside {{
  background: var(--panel);
  border: 1px solid var(--border);
  border-radius: 8px;
}}
.message {{
  display: grid;
  grid-template-columns: 42px minmax(0, 1fr);
  gap: 12px;
  padding: 14px;
  border-bottom: 1px solid var(--border);
}}
.message:last-child {{ border-bottom: 0; }}
.avatar {{
  width: 40px;
  height: 40px;
  border-radius: 50%;
  background: var(--panel-2);
}}
.author {{ font-weight: 700; }}
.bot {{ color: #57f287; font-size: 12px; margin-left: 6px; }}
.time {{ color: var(--muted); font-size: 12px; margin-left: 8px; }}
.content {{ margin-top: 4px; white-space: pre-wrap; overflow-wrap: anywhere; }}
.attachments {{ margin-top: 8px; display: grid; gap: 6px; }}
a {{ color: #8ea1ff; }}
.embed {{
  margin-top: 8px;
  border-left: 4px solid var(--accent);
  background: var(--panel-2);
  border-radius: 5px;
  padding: 8px 10px;
}}
aside {{ padding: 14px; align-self: start; }}
aside h2 {{ font-size: 15px; margin: 0 0 10px; }}
.event {{
  border-top: 1px solid var(--border);
  padding: 10px 0;
  color: var(--muted);
}}
.hidden {{ display: none; }}
</style>
</head>
<body>
<header>
  <h1>Ticket #{html.escape(str(record.get('id')))} Transcript</h1>
  <div class="meta">
    <span>Server: {html.escape(guild.name)} ({guild.id})</span>
    <span>Channel: #{html.escape(channel.name)} ({channel.id})</span>
    <span>Owner: {html.escape(owner)}</span>
    <span>Status: {html.escape(str(record.get('status')))}</span>
    <span>Generated: {generated}</span>
  </div>
  <div class="toolbar"><input id="search" type="search" placeholder="Search messages, names, attachments..."></div>
</header>
<main>
  <section class="messages" id="messages">
    {''.join(rows) if rows else '<div class="message"><div></div><div>No messages found.</div></div>'}
  </section>
  <aside>
    <h2>Ticket Events</h2>
    {events if events else '<div class="event">No stored events.</div>'}
  </aside>
</main>
<script>
const search = document.getElementById('search');
const messages = Array.from(document.querySelectorAll('.message'));
search.addEventListener('input', () => {{
  const query = search.value.trim().toLowerCase();
  for (const message of messages) {{
    message.classList.toggle('hidden', query && !message.innerText.toLowerCase().includes(query));
  }}
}});
</script>
</body>
</html>"""

    def _render_html_message(self, message: discord.Message) -> str:
        author = html.escape(str(message.author))
        author_id = html.escape(str(message.author.id))
        avatar = html.escape(str(message.author.display_avatar.url))
        timestamp = message.created_at.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
        content = html.escape(message.clean_content or "")
        bot_tag = '<span class="bot">BOT</span>' if message.author.bot else ""
        attachments = "".join(
            f'<a href="{html.escape(attachment.url)}" target="_blank" rel="noreferrer">'
            f'{html.escape(attachment.filename)}</a>'
            for attachment in message.attachments
        )
        if attachments:
            attachments = f'<div class="attachments">{attachments}</div>'
        embeds = "".join(self._render_html_embed(embed) for embed in message.embeds)
        return f"""<article class="message" data-author="{author}" data-author-id="{author_id}">
  <img class="avatar" src="{avatar}" alt="">
  <div>
    <div><span class="author">{author}</span>{bot_tag}<span class="time">{timestamp}</span></div>
    <div class="content">{content}</div>
    {attachments}
    {embeds}
  </div>
</article>"""

    @staticmethod
    def _render_html_embed(embed: discord.Embed) -> str:
        parts = []
        if embed.title:
            parts.append(f"<strong>{html.escape(embed.title)}</strong>")
        if embed.description:
            parts.append(f"<div>{html.escape(str(embed.description))}</div>")
        for field in embed.fields[:6]:
            parts.append(
                f"<div><strong>{html.escape(str(field.name))}</strong>: {html.escape(str(field.value))}</div>"
            )
        if not parts:
            return ""
        return '<div class="embed">' + "".join(parts) + "</div>"

    def _render_html_event(self, event: Dict[str, Any]) -> str:
        event_type = html.escape(str(event.get("type") or "event").title())
        actor = html.escape(self._user_ref(event.get("actor_id")))
        at = self._format_export_time(event.get("at")) or "Unknown time"
        reason = html.escape(str(event.get("reason") or ""))
        if reason:
            reason = f"<div>{reason}</div>"
        return f'<div class="event"><strong>{event_type}</strong><br>{actor}<br>{html.escape(at)}{reason}</div>'

    async def _resolve_ticket_argument(
        self,
        ctx: commands.Context,
        ticket_id: Optional[int] = None,
    ) -> Tuple[str, TicketRecord]:
        assert ctx.guild is not None
        if ticket_id is not None:
            tickets = await self.config.guild(ctx.guild).tickets()
            record = tickets.get(str(ticket_id))
            if not record:
                raise commands.BadArgument(f"No ticket with ID `{ticket_id}` was found.")
            return str(ticket_id), record
        if isinstance(ctx.channel, (discord.TextChannel, discord.Thread)):
            return await self._find_ticket_by_channel(ctx.guild, ctx.channel.id)
        raise commands.BadArgument("Run this in a ticket channel/thread or provide a ticket ID.")

    async def _send_settings(self, ctx: commands.Context) -> None:
        assert ctx.guild is not None
        profiles = await self._get_profiles(ctx.guild)
        tickets = await self.config.guild(ctx.guild).tickets()
        multi_panels = await self.config.guild(ctx.guild).multi_panels()
        enabled = await self.config.guild(ctx.guild).enabled()
        open_count = sum(1 for record in tickets.values() if record.get("status") == "open")
        closed_count = sum(1 for record in tickets.values() if record.get("status") == "closed")
        prefix = ctx.clean_prefix
        embed = discord.Embed(
            title="TicketHub",
            color=self.DEFAULT_COLOR,
            timestamp=self._now(),
        )
        embed.add_field(
            name="Status",
            value=(
                f"Enabled: **{'Yes' if enabled else 'No'}**\n"
                f"Profiles: **{self._count(len(profiles))}**\n"
                f"Multi-panels: **{self._count(len(multi_panels))}**\n"
                f"Open tickets: **{self._count(open_count)}**\n"
                f"Closed tickets: **{self._count(closed_count)}**"
            ),
            inline=True,
        )
        profile_lines = []
        for name, profile in sorted(profiles.items()):
            panel_channel = self._profile_channel(ctx.guild, profile, "panel_channel_id")
            ticket_category = self._profile_category(ctx.guild, profile, "ticket_category_id")
            ticket_mode = self._ticket_mode(profile)
            thread_parent = self._thread_parent_channel(ctx.guild, profile)
            location_text = (
                f"thread parent {thread_parent.mention if thread_parent else 'not set'}"
                if ticket_mode == "thread"
                else f"category {ticket_category.name if ticket_category else 'not set'}"
            )
            modal_count = len(profile.get("creating_modal") or [])
            profile_lines.append(
                f"`{name}` - panel {panel_channel.mention if panel_channel else 'not set'} "
                f"- style {self._panel_style(profile.get('panel_style'))} "
                f"- mode {ticket_mode} - {location_text} "
                f"- modal fields {modal_count}"
            )
        embed.add_field(
            name="Profiles",
            value="\n".join(profile_lines)[:1024] if profile_lines else "None",
            inline=False,
        )
        embed.add_field(
            name="Start Here",
            value=(
                f"`{prefix}tickethub walkthrough`\n"
                f"`{prefix}tickethub panel main #tickets button`\n"
                f"`{prefix}tickethub attachpanel main <message-link> dropdown`\n"
                f"`{prefix}tickethub multipanel` for multi-profile panels\n"
                f"`{prefix}tickethub import aaa3a main` for migration preview"
            ),
            inline=False,
        )
        await ctx.send(embed=embed)

    @commands.group(name="tickethub", aliases=["thub"], invoke_without_command=True)
    @commands.guild_only()
    @commands.bot_has_permissions(embed_links=True)
    async def tickethub(self, ctx: commands.Context) -> None:
        """Configure and manage TicketHub."""
        await self._send_settings(ctx)

    @tickethub.command(name="walkthrough", aliases=["wizard"])
    @commands.admin_or_permissions(manage_guild=True)
    async def tickethub_walkthrough(self, ctx: commands.Context, profile_name: str = "main") -> None:
        """Walk through a basic TicketHub setup."""
        assert ctx.guild is not None
        profile_name = self._clean_name(profile_name)
        await ctx.send("TicketHub setup walkthrough started. Reply `cancel` at any step to stop.")
        try:
            panel_channel = await self._prompt_text_channel(
                ctx,
                "Step 1/4: Which channel should the ticket panel be posted in? Reply with a channel or `here`.",
            )
            ticket_category = await self._prompt_category(
                ctx,
                "Step 2/4: Which category should new ticket channels go in? Reply with a category name/ID or `none`.",
                allow_none=True,
            )
            log_channel = await self._prompt_text_channel(
                ctx,
                "Step 3/4: Which channel should ticket logs/transcripts go to? Reply with a channel, `here`, or `none`.",
                allow_none=True,
            )
            support_roles = await self._prompt_roles(
                ctx,
                "Step 4/4: Which roles are support staff? Mention roles, give role IDs, or reply `none`.",
            )
        except commands.CommandError as error:
            await ctx.send(str(error))
            return

        assert panel_channel is not None
        profile = await self._ensure_profile(ctx.guild, profile_name)
        profile["panel_channel_id"] = panel_channel.id
        profile["ticket_category_id"] = ticket_category.id if ticket_category else None
        profile["log_channel_id"] = log_channel.id if log_channel else None
        profile["transcript_channel_id"] = log_channel.id if log_channel else None
        profile["support_role_ids"] = [role.id for role in support_roles]
        profile["enabled"] = True
        await self._set_profile(ctx.guild, profile_name, profile)
        await self.config.guild(ctx.guild).enabled.set(True)
        try:
            message = await self._post_panel(ctx.guild, profile_name, profile, panel_channel)
        except commands.CommandError as error:
            await ctx.send(str(error))
            return
        await ctx.send(
            f"TicketHub setup complete for profile `{profile_name}`.\n"
            f"Panel: {message.jump_url}\n"
            f"Users can open tickets from the panel or with `{ctx.clean_prefix}tickethub open {profile_name}`."
        )

    async def _wait_for_setup_reply(
        self,
        ctx: commands.Context,
        prompt: str,
        timeout: int = 120,
    ) -> str:
        await ctx.send(prompt)

        def check(message: discord.Message) -> bool:
            return (
                message.author.id == ctx.author.id
                and message.channel.id == ctx.channel.id
                and message.guild == ctx.guild
            )

        try:
            message = await self.bot.wait_for("message", check=check, timeout=timeout)
        except asyncio.TimeoutError as exc:
            raise commands.CommandError("TicketHub walkthrough timed out.") from exc
        answer = message.content.strip()
        if answer.lower() in {"cancel", "stop", "quit"}:
            raise commands.CommandError("TicketHub walkthrough cancelled.")
        return answer

    async def _prompt_text_channel(
        self,
        ctx: commands.Context,
        prompt: str,
        *,
        allow_none: bool = False,
    ) -> Optional[discord.TextChannel]:
        while True:
            answer = await self._wait_for_setup_reply(ctx, prompt)
            lowered = answer.lower()
            if allow_none and lowered in {"none", "no", "skip", "off"}:
                return None
            if lowered in {"here", "current"} and isinstance(ctx.channel, discord.TextChannel):
                return ctx.channel
            try:
                return await commands.TextChannelConverter().convert(ctx, answer)
            except commands.BadArgument:
                await ctx.send("Reply with a text channel mention, channel ID, `here`, or `none` when allowed.")

    async def _prompt_category(
        self,
        ctx: commands.Context,
        prompt: str,
        *,
        allow_none: bool = False,
    ) -> Optional[discord.CategoryChannel]:
        while True:
            answer = await self._wait_for_setup_reply(ctx, prompt)
            lowered = answer.lower()
            if allow_none and lowered in {"none", "no", "skip", "off"}:
                return None
            try:
                return await commands.CategoryChannelConverter().convert(ctx, answer)
            except commands.BadArgument:
                await ctx.send("Reply with a category name, category ID, or `none` when allowed.")

    async def _prompt_roles(
        self,
        ctx: commands.Context,
        prompt: str,
    ) -> List[discord.Role]:
        answer = await self._wait_for_setup_reply(ctx, prompt)
        if answer.lower() in {"none", "no", "skip", "off"}:
            return []
        roles: List[discord.Role] = []
        for token in answer.split():
            try:
                role = await commands.RoleConverter().convert(ctx, token)
            except commands.BadArgument:
                continue
            if role not in roles:
                roles.append(role)
        return roles

    @staticmethod
    def _modal_style_name(style: Any) -> str:
        try:
            style_value = int(style)
        except (TypeError, ValueError):
            style_value = discord.TextStyle.paragraph.value
        return "short" if style_value == discord.TextStyle.short.value else "paragraph"

    @classmethod
    def _modal_summary_lines(cls, fields: Optional[Sequence[ModalFieldRecord]]) -> List[str]:
        if not fields:
            return ["No modal questions are configured."]
        lines = []
        for index, field in enumerate(fields, start=1):
            label = cls._clean_modal_text(field.get("label"), 45) or "Question"
            question_type = cls._modal_type_name(field.get("type")) or "text"
            required = "required" if field.get("required", True) else "optional"
            placeholder = cls._clean_modal_text(field.get("placeholder"), 100) or "none"
            if question_type == "choice":
                choices = ", ".join(cls._clean_modal_choices(field.get("choices")))
                details = f"choice, {required}, options: {choices}"
            elif question_type == "boolean":
                details = f"boolean, {required}"
            else:
                style = cls._modal_style_name(field.get("style"))
                details = f"text/{style}, {required}, placeholder: {placeholder}"
            lines.append(f"{index}. {label} ({details})")
        return lines

    async def _send_modal_settings(self, ctx: commands.Context, profile_name: str = "main") -> None:
        assert ctx.guild is not None
        profile_name = self._clean_name(profile_name)
        profile = await self._get_profile(ctx.guild, profile_name)
        lines = self._modal_summary_lines(profile.get("creating_modal"))
        summary = "\n".join(lines)
        await ctx.send(f"Modal questions for `{profile_name}`:\n{box(summary)}")

    async def _prompt_modal_count(self, ctx: commands.Context) -> int:
        while True:
            answer = await self._wait_for_setup_reply(
                ctx,
                "How many questions should this modal have? Reply with a number from `1` to `5`.",
            )
            try:
                count = int(answer)
            except ValueError:
                await ctx.send("Reply with a number from `1` to `5`.")
                continue
            if 1 <= count <= 5:
                return count
            await ctx.send("A Discord modal can have between 1 and 5 questions.")

    async def _prompt_modal_label(self, ctx: commands.Context, prompt: str) -> str:
        while True:
            label = await self._wait_for_setup_reply(ctx, prompt)
            label = label.strip()
            if 1 <= len(label) <= 45:
                return label
            await ctx.send("Question labels must be between 1 and 45 characters.")

    async def _prompt_modal_style(self, ctx: commands.Context, prompt: str) -> int:
        while True:
            answer = (await self._wait_for_setup_reply(ctx, prompt)).lower()
            if answer in {"short", "single", "line", "1"}:
                return discord.TextStyle.short.value
            if answer in {"paragraph", "long", "multi", "2"}:
                return discord.TextStyle.paragraph.value
            await ctx.send("Reply with `short` or `paragraph`.")

    async def _prompt_modal_bool(self, ctx: commands.Context, prompt: str) -> bool:
        while True:
            answer = (await self._wait_for_setup_reply(ctx, prompt)).lower()
            if answer in {"yes", "y", "true", "t", "1", "required", "on"}:
                return True
            if answer in {"no", "n", "false", "f", "0", "optional", "off"}:
                return False
            await ctx.send("Reply with `yes` or `no`.")

    async def _prompt_modal_type(self, ctx: commands.Context, prompt: str) -> str:
        while True:
            answer = await self._wait_for_setup_reply(ctx, prompt)
            question_type = self._modal_type_name(answer)
            if question_type is not None:
                return question_type
            await ctx.send("Reply with `text`, `choice`, or `boolean`.")

    async def _prompt_modal_choices(self, ctx: commands.Context, prompt: str) -> List[str]:
        while True:
            answer = await self._wait_for_setup_reply(ctx, prompt)
            choices = self._clean_modal_choices(answer)
            if 2 <= len(choices) <= 25:
                return choices
            await ctx.send("Provide between 2 and 25 comma-separated choices.")

    async def _prompt_optional_modal_text(
        self,
        ctx: commands.Context,
        prompt: str,
        *,
        limit: int,
    ) -> str:
        answer = await self._wait_for_setup_reply(ctx, prompt)
        if answer.lower() in {"none", "no", "skip", "off", "clear"}:
            return ""
        return answer[:limit]

    async def _post_panel(
        self,
        guild: discord.Guild,
        profile_name: str,
        profile: ProfileRecord,
        channel: discord.TextChannel,
        style: str = "button",
    ) -> discord.Message:
        me = guild.me
        if me is None:
            raise commands.CommandError("I could not inspect my server permissions.")
        perms = channel.permissions_for(me)
        if not perms.send_messages or not perms.embed_links:
            raise commands.CommandError(
                f"I need `Send Messages` and `Embed Links` in {channel.mention}."
            )
        style = self._parse_panel_style(style)
        embed = self._panel_embed(guild, profile_name, profile)
        try:
            message = await channel.send(
                embed=embed,
                view=self._panel_view_for_style(style),
            )
        except discord.HTTPException as exc:
            raise commands.CommandError("I could not post the ticket panel.") from exc
        profile["panel_channel_id"] = channel.id
        profile["panel_message_id"] = message.id
        profile["panel_style"] = style
        await self._set_profile(guild, profile_name, profile)
        return message

    async def _attach_panel(
        self,
        guild: discord.Guild,
        profile_name: str,
        profile: ProfileRecord,
        message: discord.Message,
        style: str = "button",
    ) -> discord.Message:
        me = guild.me
        if me is None:
            raise commands.CommandError("I could not inspect my server identity.")
        if message.guild is None or message.guild.id != guild.id:
            raise commands.BadArgument("The panel message must be in this server.")
        if message.author.id != me.id:
            raise commands.BadArgument(
                "I can only attach a panel to a message sent by this bot."
            )
        tracked_profile_names = [
            name
            for name, tracked_profile in (await self._get_profiles(guild)).items()
            if int(tracked_profile.get("panel_message_id") or 0) == message.id
        ]
        other_profile_name = next(
            (name for name in tracked_profile_names if name != profile_name),
            None,
        )
        if other_profile_name:
            raise commands.BadArgument(
                f"That message is already the panel for `{other_profile_name}`."
            )
        if message.components and profile_name not in tracked_profile_names:
            raise commands.BadArgument(
                "That message already has components. Remove them before attaching "
                "a TicketHub panel."
            )
        style = self._parse_panel_style(style)
        try:
            await message.edit(view=self._panel_view_for_style(style))
        except discord.HTTPException as exc:
            raise commands.CommandError(
                "I could not attach the ticket panel to that message."
            ) from exc
        profile["panel_channel_id"] = message.channel.id
        profile["panel_message_id"] = message.id
        profile["panel_style"] = style
        await self._set_profile(guild, profile_name, profile)
        return message

    @tickethub.command(name="enable")
    @commands.admin_or_permissions(manage_guild=True)
    async def tickethub_enable(self, ctx: commands.Context, enabled: bool = True) -> None:
        """Enable or disable TicketHub."""
        assert ctx.guild is not None
        await self.config.guild(ctx.guild).enabled.set(enabled)
        await ctx.send(f"TicketHub is now {'enabled' if enabled else 'disabled'}.")

    @tickethub.command(name="open")
    @commands.guild_only()
    async def tickethub_open(
        self,
        ctx: commands.Context,
        profile_name: str = "main",
        *,
        reason: Optional[str] = None,
    ) -> None:
        """Open a ticket."""
        assert ctx.guild is not None
        if not isinstance(ctx.author, discord.Member):
            await ctx.send("This command only works in a server.")
            return
        try:
            record, channel = await self._create_ticket(
                ctx.guild,
                ctx.author,
                profile_name,
                reason=reason or "Opened by command.",
            )
        except commands.CommandError as error:
            await ctx.send(str(error))
            return
        await ctx.send(f"Ticket #{record['id']} opened: {channel.mention}")

    @tickethub.command(name="panel")
    @commands.admin_or_permissions(manage_guild=True)
    async def tickethub_panel(
        self,
        ctx: commands.Context,
        profile_name: str = "main",
        channel: Optional[discord.TextChannel] = None,
        style: str = "button",
    ) -> None:
        """Post a button or dropdown ticket panel for a profile."""
        assert ctx.guild is not None
        if channel is None:
            if not isinstance(ctx.channel, discord.TextChannel):
                await ctx.send("Run this in a text channel or provide a panel channel.")
                return
            channel = ctx.channel
        profile_name = self._clean_name(profile_name)
        profile = await self._ensure_profile(ctx.guild, profile_name)
        try:
            message = await self._post_panel(
                ctx.guild,
                profile_name,
                profile,
                channel,
                style,
            )
        except commands.CommandError as error:
            await ctx.send(str(error))
            return
        await self.config.guild(ctx.guild).enabled.set(True)
        await ctx.send(
            f"Ticket {profile['panel_style']} panel posted for `{profile_name}`: "
            f"{message.jump_url}"
        )

    @tickethub.command(name="attachpanel")
    @commands.admin_or_permissions(manage_guild=True)
    async def tickethub_attachpanel(
        self,
        ctx: commands.Context,
        profile_name: str,
        message: discord.Message,
        style: str = "button",
    ) -> None:
        """Attach a button or dropdown panel to an existing bot-authored message."""
        assert ctx.guild is not None
        profile_name = self._clean_name(profile_name)
        profile = await self._ensure_profile(ctx.guild, profile_name)
        try:
            message = await self._attach_panel(
                ctx.guild,
                profile_name,
                profile,
                message,
                style,
            )
        except commands.CommandError as error:
            await ctx.send(str(error))
            return
        await self.config.guild(ctx.guild).enabled.set(True)
        await ctx.send(
            f"Ticket {profile['panel_style']} panel attached for `{profile_name}`: "
            f"{message.jump_url}"
        )

    @tickethub.group(
        name="multipanel",
        aliases=["mpanel"],
        invoke_without_command=True,
    )
    @commands.admin_or_permissions(manage_guild=True)
    async def tickethub_multi_panel(self, ctx: commands.Context) -> None:
        """Manage messages that offer multiple TicketHub profiles."""
        prefix = ctx.clean_prefix
        await ctx.send(
            "Multi-panel commands:\n"
            f"`{prefix}tickethub multipanel add <message> <profile> "
            "<button|dropdown> <emoji|none> <name> | <description>`\n"
            f"`{prefix}tickethub multipanel remove <message> <profile>`\n"
            f"`{prefix}tickethub multipanel style <message> <button|dropdown>`\n"
            f"`{prefix}tickethub multipanel placeholder <message> <text>`\n"
            f"`{prefix}tickethub multipanel show <message>`\n"
            f"`{prefix}tickethub multipanel clear <message>`"
        )

    @tickethub_multi_panel.command(name="add", aliases=["option"])
    @commands.admin_or_permissions(manage_guild=True)
    async def tickethub_multi_panel_add(
        self,
        ctx: commands.Context,
        message: discord.Message,
        profile_name: str,
        style: str,
        emoji: str,
        *,
        details: str,
    ) -> None:
        """Add a named profile option to a multi-panel message."""
        assert ctx.guild is not None
        try:
            if message.guild is None or message.guild.id != ctx.guild.id:
                raise commands.BadArgument("The panel message must be in this server.")
            if ctx.guild.me is None or message.author.id != ctx.guild.me.id:
                raise commands.BadArgument(
                    "I can only attach a multi-panel to a message sent by this bot."
                )
            profile_name = self._clean_name(profile_name)
            profile = await self._get_profile(ctx.guild, profile_name)
            style = self._parse_panel_style(style)
            emoji_value = self._multi_panel_emoji(emoji)
            label, description = self._multi_panel_option_text(details)

            panels = await self.config.guild(ctx.guild).multi_panels()
            raw_record = panels.get(str(message.id))
            if raw_record is None:
                if message.components:
                    raise commands.BadArgument(
                        "That message already has components. Remove them before "
                        "creating a TicketHub multi-panel."
                    )
                profiles = await self._get_profiles(ctx.guild)
                tracked_profile = next(
                    (
                        name
                        for name, profile in profiles.items()
                        if int(profile.get("panel_message_id") or 0) == message.id
                    ),
                    None,
                )
                if tracked_profile:
                    raise commands.BadArgument(
                        f"That message is already the single panel for `{tracked_profile}`."
                    )
                record: MultiPanelRecord = {
                    "channel_id": message.channel.id,
                    "message_id": message.id,
                    "style": style,
                    "placeholder": "Choose a ticket type...",
                    "options": [],
                }
            else:
                record = self._sanitize_multi_panel_record(
                    raw_record,
                    message_id=message.id,
                )
                if record is None:
                    raise commands.BadArgument(
                        "That multi-panel configuration is invalid; clear it and try again."
                    )
                if record["style"] != style:
                    raise commands.BadArgument(
                        f"That multi-panel uses `{record['style']}`. Use the `style` "
                        "subcommand to change all its options."
                    )
            if any(
                option["profile"] == profile_name for option in record.get("options", [])
            ):
                raise commands.BadArgument(
                    f"Profile `{profile_name}` is already on that multi-panel."
                )
            if len(record.get("options", [])) >= 25:
                raise commands.BadArgument(
                    "A Discord multi-panel can contain at most 25 profile options."
                )
            record["options"].append(
                {
                    "profile": profile_name,
                    "label": label,
                    "description": description,
                    "emoji": emoji_value,
                }
            )
            record = await self._save_multi_panel(ctx.guild, message, record)
            profile["panel_channel_id"] = message.channel.id
            await self._set_profile(ctx.guild, profile_name, profile)
        except commands.CommandError as error:
            await ctx.send(str(error))
            return
        await self.config.guild(ctx.guild).enabled.set(True)
        description_note = (
            " Descriptions are displayed only when the panel uses a dropdown."
            if description and record["style"] == "button"
            else ""
        )
        await ctx.send(
            f"Added **{label}** (`{profile_name}`) to the {record['style']} "
            f"multi-panel: {message.jump_url}.{description_note}"
        )

    @tickethub_multi_panel.command(name="remove")
    @commands.admin_or_permissions(manage_guild=True)
    async def tickethub_multi_panel_remove(
        self,
        ctx: commands.Context,
        message: discord.Message,
        profile_name: str,
    ) -> None:
        """Remove a profile option from a multi-panel."""
        assert ctx.guild is not None
        try:
            profile_name = self._clean_name(profile_name)
            record = await self._get_multi_panel_record(ctx.guild, message.id)
            options = [
                option
                for option in record["options"]
                if option["profile"] != profile_name
            ]
            if len(options) == len(record["options"]):
                raise commands.BadArgument(
                    f"Profile `{profile_name}` is not on that multi-panel."
                )
            if not options:
                await self._clear_multi_panel(ctx.guild, message)
            else:
                record["options"] = options
                await self._save_multi_panel(ctx.guild, message, record)
        except commands.CommandError as error:
            await ctx.send(str(error))
            return
        await ctx.send(
            f"Removed `{profile_name}` from the multi-panel: {message.jump_url}"
        )

    @tickethub_multi_panel.command(name="style")
    @commands.admin_or_permissions(manage_guild=True)
    async def tickethub_multi_panel_style(
        self,
        ctx: commands.Context,
        message: discord.Message,
        style: str,
    ) -> None:
        """Switch every option between buttons and one dropdown."""
        assert ctx.guild is not None
        try:
            style = self._parse_panel_style(style)
            record = await self._get_multi_panel_record(ctx.guild, message.id)
            record["style"] = style
            await self._save_multi_panel(ctx.guild, message, record)
        except commands.CommandError as error:
            await ctx.send(str(error))
            return
        await ctx.send(f"Multi-panel style changed to **{style}**: {message.jump_url}")

    @tickethub_multi_panel.command(name="placeholder")
    @commands.admin_or_permissions(manage_guild=True)
    async def tickethub_multi_panel_placeholder(
        self,
        ctx: commands.Context,
        message: discord.Message,
        *,
        placeholder: str,
    ) -> None:
        """Set the dropdown placeholder for a multi-panel."""
        assert ctx.guild is not None
        placeholder = placeholder.strip()
        if not 1 <= len(placeholder) <= 100:
            await ctx.send("Dropdown placeholders must be between 1 and 100 characters.")
            return
        try:
            record = await self._get_multi_panel_record(ctx.guild, message.id)
            record["placeholder"] = placeholder
            await self._save_multi_panel(ctx.guild, message, record)
        except commands.CommandError as error:
            await ctx.send(str(error))
            return
        await ctx.send(f"Multi-panel placeholder updated: {message.jump_url}")

    @tickethub_multi_panel.command(name="show")
    @commands.admin_or_permissions(manage_guild=True)
    async def tickethub_multi_panel_show(
        self,
        ctx: commands.Context,
        message: discord.Message,
    ) -> None:
        """Show the options configured on a multi-panel."""
        assert ctx.guild is not None
        try:
            record = await self._get_multi_panel_record(ctx.guild, message.id)
        except commands.CommandError as error:
            await ctx.send(str(error))
            return
        lines = [
            f"Style: {record['style']}",
            f"Placeholder: {record['placeholder']}",
        ]
        for index, option in enumerate(record["options"], start=1):
            emoji_text = f"{option['emoji']} " if option.get("emoji") else ""
            description_text = (
                f" — {option['description']}" if option.get("description") else ""
            )
            lines.append(
                f"{index}. {emoji_text}{option['label']} (`{option['profile']}`)"
                f"{description_text}"
            )
        await ctx.send(box("\n".join(lines)))

    @tickethub_multi_panel.command(name="clear")
    @commands.admin_or_permissions(manage_guild=True)
    async def tickethub_multi_panel_clear(
        self,
        ctx: commands.Context,
        message: discord.Message,
    ) -> None:
        """Remove a multi-panel and all its components from a message."""
        assert ctx.guild is not None
        try:
            await self._clear_multi_panel(ctx.guild, message)
        except commands.CommandError as error:
            await ctx.send(str(error))
            return
        await ctx.send(f"Multi-panel removed: {message.jump_url}")

    @tickethub.command(name="profile")
    @commands.admin_or_permissions(manage_guild=True)
    async def tickethub_profile(self, ctx: commands.Context, profile_name: str = "main") -> None:
        """Create a profile if it does not exist."""
        assert ctx.guild is not None
        profile_name = self._clean_name(profile_name)
        await self._ensure_profile(ctx.guild, profile_name)
        await ctx.send(f"TicketHub profile `{profile_name}` is ready.")

    @tickethub.command(name="category")
    @commands.admin_or_permissions(manage_guild=True)
    async def tickethub_category(
        self,
        ctx: commands.Context,
        profile_name: str,
        category: Optional[discord.CategoryChannel] = None,
    ) -> None:
        """Set the open-ticket category for a profile."""
        assert ctx.guild is not None
        profile = await self._ensure_profile(ctx.guild, profile_name)
        profile["ticket_category_id"] = category.id if category else None
        await self._set_profile(ctx.guild, profile_name, profile)
        await ctx.send(f"Open-ticket category for `{profile_name}` set to {category.name if category else 'none'}.")

    @tickethub.command(name="closedcategory")
    @commands.admin_or_permissions(manage_guild=True)
    async def tickethub_closed_category(
        self,
        ctx: commands.Context,
        profile_name: str,
        category: Optional[discord.CategoryChannel] = None,
    ) -> None:
        """Set the closed-ticket category for a profile."""
        assert ctx.guild is not None
        profile = await self._ensure_profile(ctx.guild, profile_name)
        profile["closed_category_id"] = category.id if category else None
        await self._set_profile(ctx.guild, profile_name, profile)
        await ctx.send(f"Closed-ticket category for `{profile_name}` set to {category.name if category else 'none'}.")

    @tickethub.command(name="mode", aliases=["ticketmode"])
    @commands.admin_or_permissions(manage_guild=True)
    async def tickethub_mode(
        self,
        ctx: commands.Context,
        profile_name: str,
        mode: str,
    ) -> None:
        """Set whether a profile opens ticket channels or private threads."""
        assert ctx.guild is not None
        mode = mode.lower()
        if mode not in {"channel", "thread"}:
            await ctx.send("Ticket mode must be `channel` or `thread`.")
            return
        profile = await self._ensure_profile(ctx.guild, profile_name)
        profile["ticket_mode"] = mode
        await self._set_profile(ctx.guild, profile_name, profile)
        extra = ""
        if mode == "thread" and self._thread_parent_channel(ctx.guild, profile) is None:
            extra = "\nSet a thread parent with `[p]tickethub threadparent <profile> #channel`."
        await ctx.send(f"Ticket mode for `{profile_name}` set to **{mode}**.{extra}")

    @tickethub.command(name="threadparent", aliases=["threadchannel"])
    @commands.admin_or_permissions(manage_guild=True)
    async def tickethub_thread_parent(
        self,
        ctx: commands.Context,
        profile_name: str,
        channel: Optional[discord.TextChannel] = None,
    ) -> None:
        """Set the parent channel used for private thread tickets."""
        assert ctx.guild is not None
        profile = await self._ensure_profile(ctx.guild, profile_name)
        profile["thread_parent_channel_id"] = channel.id if channel else None
        await self._set_profile(ctx.guild, profile_name, profile)
        target = channel.mention if channel else "panel channel fallback"
        await ctx.send(f"Thread-ticket parent for `{profile_name}` set to {target}.")

    @tickethub.command(name="logchannel")
    @commands.admin_or_permissions(manage_guild=True)
    async def tickethub_log_channel(
        self,
        ctx: commands.Context,
        profile_name: str,
        channel: Optional[discord.TextChannel] = None,
    ) -> None:
        """Set the log channel for a profile."""
        assert ctx.guild is not None
        profile = await self._ensure_profile(ctx.guild, profile_name)
        profile["log_channel_id"] = channel.id if channel else None
        await self._set_profile(ctx.guild, profile_name, profile)
        await ctx.send(f"Log channel for `{profile_name}` set to {channel.mention if channel else 'none'}.")

    @tickethub.command(name="transcriptchannel")
    @commands.admin_or_permissions(manage_guild=True)
    async def tickethub_transcript_channel(
        self,
        ctx: commands.Context,
        profile_name: str,
        channel: Optional[discord.TextChannel] = None,
    ) -> None:
        """Set the transcript channel for a profile."""
        assert ctx.guild is not None
        profile = await self._ensure_profile(ctx.guild, profile_name)
        profile["transcript_channel_id"] = channel.id if channel else None
        await self._set_profile(ctx.guild, profile_name, profile)
        await ctx.send(f"Transcript channel for `{profile_name}` set to {channel.mention if channel else 'none'}.")

    @tickethub.group(name="modal", invoke_without_command=True)
    @commands.admin_or_permissions(manage_guild=True)
    async def tickethub_modal(self, ctx: commands.Context, profile_name: str = "main") -> None:
        """Manage modal questions shown from ticket panels."""
        await self._send_modal_settings(ctx, profile_name)

    @tickethub_modal.command(name="show")
    @commands.admin_or_permissions(manage_guild=True)
    async def tickethub_modal_show(self, ctx: commands.Context, profile_name: str = "main") -> None:
        """Show modal questions for a profile."""
        await self._send_modal_settings(ctx, profile_name)

    @tickethub_modal.command(name="wizard")
    @commands.admin_or_permissions(manage_guild=True)
    async def tickethub_modal_wizard(self, ctx: commands.Context, profile_name: str = "main") -> None:
        """Walk through creating a custom ticket modal."""
        assert ctx.guild is not None
        profile_name = self._clean_name(profile_name)
        await self._ensure_profile(ctx.guild, profile_name)
        await ctx.send("TicketHub modal builder started. Reply `cancel` at any step to stop.")
        try:
            count = await self._prompt_modal_count(ctx)
            fields: List[ModalFieldRecord] = []
            for index in range(1, count + 1):
                label = await self._prompt_modal_label(
                    ctx,
                    f"Question {index}/{count}: What should the label be?",
                )
                question_type = await self._prompt_modal_type(
                    ctx,
                    f"Question {index}/{count}: Should this be `text`, `choice`, or `boolean`?",
                )
                required = await self._prompt_modal_bool(
                    ctx,
                    f"Question {index}/{count}: Should this be required? Reply `yes` or `no`.",
                )
                style = discord.TextStyle.paragraph.value
                placeholder = ""
                choices: List[str] = []
                if question_type == "text":
                    style = await self._prompt_modal_style(
                        ctx,
                        f"Question {index}/{count}: Should this be `short` or `paragraph`?",
                    )
                    placeholder = await self._prompt_optional_modal_text(
                        ctx,
                        f"Question {index}/{count}: Placeholder text? Reply `none` to skip.",
                        limit=100,
                    )
                elif question_type == "choice":
                    choices = await self._prompt_modal_choices(
                        ctx,
                        f"Question {index}/{count}: Enter comma-separated choices.",
                    )
                fields.append(
                    {
                        "label": label,
                        "type": question_type,
                        "style": style,
                        "required": required,
                        "default": "",
                        "placeholder": placeholder,
                        "min_length": None,
                        "max_length": None,
                        "choices": choices,
                    }
                )
        except commands.CommandError as error:
            await ctx.send(str(error))
            return

        profile = await self._ensure_profile(ctx.guild, profile_name)
        profile["creating_modal"] = self._sanitize_modal_fields(fields)
        await self._set_profile(ctx.guild, profile_name, profile)
        await ctx.send(
            f"Modal for `{profile_name}` saved.\n"
            + box("\n".join(self._modal_summary_lines(profile["creating_modal"])))
        )

    @tickethub_modal.command(name="add")
    @commands.admin_or_permissions(manage_guild=True)
    async def tickethub_modal_add(
        self,
        ctx: commands.Context,
        profile_name: str,
        question_type: str = "text",
        *,
        label: str = "",
    ) -> None:
        """Add a text, choice, or boolean question to a profile form."""
        assert ctx.guild is not None
        normalized_type = self._modal_type_name(question_type)
        if normalized_type is None:
            label = f"{question_type} {label}".strip()
            normalized_type = "text"
        choices: List[str] = []
        if normalized_type == "choice":
            if "|" not in label:
                await ctx.send(
                    "Choice questions must use `Question label | choice one, choice two`."
                )
                return
            label, raw_choices = (part.strip() for part in label.split("|", 1))
            choices = self._clean_modal_choices(raw_choices)
            if len(choices) < 2:
                await ctx.send("Choice questions need between 2 and 25 choices.")
                return
        label = label.strip()
        if not 1 <= len(label) <= 45:
            await ctx.send("Question labels must be between 1 and 45 characters.")
            return
        profile = await self._ensure_profile(ctx.guild, profile_name)
        fields = list(profile.get("creating_modal") or [])
        if len(fields) >= 5:
            await ctx.send("A Discord modal can only have 5 questions.")
            return
        fields.append(
            {
                "label": label,
                "type": normalized_type,
                "style": discord.TextStyle.paragraph.value,
                "required": True,
                "default": "",
                "placeholder": "",
                "min_length": None,
                "max_length": None,
                "choices": choices,
            }
        )
        profile["creating_modal"] = self._sanitize_modal_fields(fields)
        await self._set_profile(ctx.guild, profile_name, profile)
        await ctx.send(
            f"Added modal question to `{self._clean_name(profile_name)}`.\n"
            + box("\n".join(self._modal_summary_lines(profile["creating_modal"])))
        )

    @tickethub_modal.command(name="remove", aliases=["delete"])
    @commands.admin_or_permissions(manage_guild=True)
    async def tickethub_modal_remove(
        self,
        ctx: commands.Context,
        profile_name: str,
        index: int,
    ) -> None:
        """Remove a modal question by number."""
        assert ctx.guild is not None
        profile = await self._ensure_profile(ctx.guild, profile_name)
        fields = list(profile.get("creating_modal") or [])
        if not fields:
            await ctx.send(f"`{self._clean_name(profile_name)}` has no modal questions.")
            return
        if index < 1 or index > len(fields):
            await ctx.send(f"Question number must be between 1 and {len(fields)}.")
            return
        removed = fields.pop(index - 1)
        profile["creating_modal"] = self._sanitize_modal_fields(fields)
        await self._set_profile(ctx.guild, profile_name, profile)
        removed_label = self._clean_modal_text(removed.get("label"), 45)
        clean_profile_name = self._clean_name(profile_name)
        await ctx.send(
            f"Removed `{removed_label}` from `{clean_profile_name}`.\n"
            + box("\n".join(self._modal_summary_lines(profile["creating_modal"])))
        )

    @tickethub_modal.command(name="defaultreason", aliases=["reason", "default"])
    @commands.admin_or_permissions(manage_guild=True)
    async def tickethub_modal_default_reason(
        self,
        ctx: commands.Context,
        profile_name: str = "main",
    ) -> None:
        """Use the default ticket reason modal for a profile."""
        assert ctx.guild is not None
        profile = await self._ensure_profile(ctx.guild, profile_name)
        profile["creating_modal"] = self._default_reason_modal()
        await self._set_profile(ctx.guild, profile_name, profile)
        await ctx.send(f"`{self._clean_name(profile_name)}` now uses the default Reason modal.")

    @tickethub_modal.command(name="clear", aliases=["disable", "off"])
    @commands.admin_or_permissions(manage_guild=True)
    async def tickethub_modal_clear(self, ctx: commands.Context, profile_name: str = "main") -> None:
        """Disable modal questions for a profile."""
        assert ctx.guild is not None
        profile = await self._ensure_profile(ctx.guild, profile_name)
        profile["creating_modal"] = None
        await self._set_profile(ctx.guild, profile_name, profile)
        await ctx.send(f"Modal questions disabled for `{self._clean_name(profile_name)}`.")

    @tickethub.group(name="supportrole", invoke_without_command=True)
    @commands.admin_or_permissions(manage_guild=True)
    async def tickethub_support_role(self, ctx: commands.Context) -> None:
        """Manage support roles."""
        await ctx.send_help(ctx.command)

    @tickethub_support_role.command(name="add")
    @commands.admin_or_permissions(manage_guild=True)
    async def tickethub_support_role_add(
        self,
        ctx: commands.Context,
        profile_name: str,
        role: discord.Role,
    ) -> None:
        """Add a support role."""
        assert ctx.guild is not None
        profile = await self._ensure_profile(ctx.guild, profile_name)
        role_ids = set(int(role_id) for role_id in profile.get("support_role_ids") or [])
        role_ids.add(role.id)
        profile["support_role_ids"] = sorted(role_ids)
        await self._set_profile(ctx.guild, profile_name, profile)
        await ctx.send(f"{role.mention} can now support `{profile_name}` tickets.")

    @tickethub_support_role.command(name="remove")
    @commands.admin_or_permissions(manage_guild=True)
    async def tickethub_support_role_remove(
        self,
        ctx: commands.Context,
        profile_name: str,
        role: discord.Role,
    ) -> None:
        """Remove a support role."""
        assert ctx.guild is not None
        profile = await self._ensure_profile(ctx.guild, profile_name)
        role_ids = set(int(role_id) for role_id in profile.get("support_role_ids") or [])
        role_ids.discard(role.id)
        profile["support_role_ids"] = sorted(role_ids)
        await self._set_profile(ctx.guild, profile_name, profile)
        await ctx.send(f"{role.mention} removed from `{profile_name}` support roles.")

    @tickethub.command(name="maxopen")
    @commands.admin_or_permissions(manage_guild=True)
    async def tickethub_max_open(self, ctx: commands.Context, profile_name: str, amount: int) -> None:
        """Set the max open tickets per member for a profile."""
        assert ctx.guild is not None
        amount = max(0, min(amount, 50))
        profile = await self._ensure_profile(ctx.guild, profile_name)
        profile["max_open_tickets_by_member"] = amount
        await self._set_profile(ctx.guild, profile_name, profile)
        await ctx.send(f"Max open tickets for `{profile_name}` set to **{amount}**.")

    @tickethub.command(name="dmtranscript")
    @commands.admin_or_permissions(manage_guild=True)
    async def tickethub_dm_transcript(self, ctx: commands.Context, profile_name: str, enabled: bool) -> None:
        """Choose whether transcripts are DM'd to ticket owners."""
        assert ctx.guild is not None
        profile = await self._ensure_profile(ctx.guild, profile_name)
        profile["dm_transcript"] = enabled
        await self._set_profile(ctx.guild, profile_name, profile)
        await ctx.send(f"Ticket owner transcript DMs for `{profile_name}` are now {'enabled' if enabled else 'disabled'}.")

    @tickethub.command(name="transcripts")
    @commands.admin_or_permissions(manage_guild=True)
    async def tickethub_transcripts(self, ctx: commands.Context, profile_name: str, enabled: bool) -> None:
        """Enable or disable transcript generation on close/delete."""
        assert ctx.guild is not None
        profile = await self._ensure_profile(ctx.guild, profile_name)
        profile["transcripts"] = enabled
        await self._set_profile(ctx.guild, profile_name, profile)
        await ctx.send(f"Transcripts for `{profile_name}` are now {'enabled' if enabled else 'disabled'}.")

    @tickethub.command(name="claim")
    @commands.guild_only()
    async def tickethub_claim(self, ctx: commands.Context, ticket_id: Optional[int] = None) -> None:
        """Claim a ticket."""
        assert ctx.guild is not None
        if not isinstance(ctx.author, discord.Member):
            return
        try:
            _key, record = await self._resolve_ticket_argument(ctx, ticket_id)
            await self._claim_ticket(ctx.guild, record, ctx.author)
        except commands.CommandError as error:
            await ctx.send(str(error))
            return
        await ctx.send(f"Ticket #{record['id']} claimed.")

    @tickethub.command(name="unclaim")
    @commands.guild_only()
    async def tickethub_unclaim(self, ctx: commands.Context, ticket_id: Optional[int] = None) -> None:
        """Unclaim a ticket."""
        assert ctx.guild is not None
        if not isinstance(ctx.author, discord.Member):
            return
        try:
            _key, record = await self._resolve_ticket_argument(ctx, ticket_id)
            await self._unclaim_ticket(ctx.guild, record, ctx.author)
        except commands.CommandError as error:
            await ctx.send(str(error))
            return
        await ctx.send(f"Ticket #{record['id']} unclaimed.")

    @tickethub.command(name="close")
    @commands.guild_only()
    async def tickethub_close(
        self,
        ctx: commands.Context,
        ticket_id: Optional[int] = None,
        *,
        reason: Optional[str] = None,
    ) -> None:
        """Close a ticket."""
        assert ctx.guild is not None
        if not isinstance(ctx.author, discord.Member):
            return
        try:
            _key, record = await self._resolve_ticket_argument(ctx, ticket_id)
            await self._close_ticket(ctx.guild, record, ctx.author, reason=reason)
        except commands.CommandError as error:
            await ctx.send(str(error))
            return
        await ctx.send(f"Ticket #{record['id']} closed.")

    @tickethub.command(name="reopen")
    @commands.guild_only()
    async def tickethub_reopen(self, ctx: commands.Context, ticket_id: Optional[int] = None) -> None:
        """Reopen a ticket."""
        assert ctx.guild is not None
        if not isinstance(ctx.author, discord.Member):
            return
        try:
            _key, record = await self._resolve_ticket_argument(ctx, ticket_id)
            await self._reopen_ticket(ctx.guild, record, ctx.author)
        except commands.CommandError as error:
            await ctx.send(str(error))
            return
        await ctx.send(f"Ticket #{record['id']} reopened.")

    @tickethub.command(name="delete")
    @commands.guild_only()
    @commands.admin_or_permissions(manage_guild=True)
    async def tickethub_delete(
        self,
        ctx: commands.Context,
        ticket_id: Optional[int] = None,
        *,
        reason: Optional[str] = None,
    ) -> None:
        """Delete a ticket channel or thread after saving a transcript."""
        assert ctx.guild is not None
        if not isinstance(ctx.author, discord.Member):
            return
        try:
            _key, record = await self._resolve_ticket_argument(ctx, ticket_id)
            await self._delete_ticket_channel(ctx.guild, record, ctx.author, reason=reason)
        except commands.CommandError as error:
            await ctx.send(str(error))
            return

    @tickethub.command(name="transcript")
    @commands.guild_only()
    @commands.bot_has_permissions(attach_files=True)
    async def tickethub_transcript(self, ctx: commands.Context, ticket_id: Optional[int] = None) -> None:
        """Generate and send a ticket transcript."""
        assert ctx.guild is not None
        if not isinstance(ctx.author, discord.Member):
            return
        try:
            _key, record = await self._resolve_ticket_argument(ctx, ticket_id)
            profile = await self._get_profile(ctx.guild, str(record.get("profile") or "main"))
            if not self._is_support_member(ctx.author, profile):
                await ctx.send("Only support staff can generate transcripts.")
                return
            result = await self._send_transcript_bundle(ctx.guild, record, profile, requested_by=ctx.author)
        except commands.CommandError as error:
            await ctx.send(str(error))
            return
        await ctx.send(result)

    @tickethub.command(name="addmember")
    @commands.guild_only()
    async def tickethub_add_member(
        self,
        ctx: commands.Context,
        member: discord.Member,
        ticket_id: Optional[int] = None,
    ) -> None:
        """Add a member to a ticket."""
        assert ctx.guild is not None
        if not isinstance(ctx.author, discord.Member):
            return
        try:
            _key, record = await self._resolve_ticket_argument(ctx, ticket_id)
            profile = await self._get_profile(ctx.guild, str(record.get("profile") or "main"))
            if not self._is_support_member(ctx.author, profile):
                await ctx.send("Only support staff can add members.")
                return
            channel = await self._fetch_ticket_channel(ctx.guild, record)
            if channel is None:
                await ctx.send("I could not find that ticket channel or thread.")
                return
            if isinstance(channel, discord.Thread):
                await channel.add_user(member)
            else:
                await channel.set_permissions(
                    member,
                    view_channel=True,
                    send_messages=record.get("status") == "open",
                    read_message_history=True,
                    attach_files=record.get("status") == "open",
                    embed_links=record.get("status") == "open",
                    reason=f"TicketHub member added by {ctx.author}",
                )
            participants = {int(member_id) for member_id in record.get("participants", [])}
            participants.add(member.id)
            record["participants"] = sorted(participants)
            record.setdefault("events", []).append(
                {"type": "member_added", "actor_id": ctx.author.id, "target_id": member.id, "at": self._now_ts()}
            )
            async with self.config.guild(ctx.guild).tickets() as tickets:
                tickets[str(record["id"])] = record
        except (commands.CommandError, discord.HTTPException) as error:
            await ctx.send(str(error))
            return
        await ctx.send(f"{member.mention} added to ticket #{record['id']}.")

    @tickethub.command(name="removemember")
    @commands.guild_only()
    async def tickethub_remove_member(
        self,
        ctx: commands.Context,
        member: discord.Member,
        ticket_id: Optional[int] = None,
    ) -> None:
        """Remove a member from a ticket."""
        assert ctx.guild is not None
        if not isinstance(ctx.author, discord.Member):
            return
        try:
            _key, record = await self._resolve_ticket_argument(ctx, ticket_id)
            profile = await self._get_profile(ctx.guild, str(record.get("profile") or "main"))
            if not self._is_support_member(ctx.author, profile):
                await ctx.send("Only support staff can remove members.")
                return
            channel = await self._fetch_ticket_channel(ctx.guild, record)
            if channel is None:
                await ctx.send("I could not find that ticket channel or thread.")
                return
            if isinstance(channel, discord.Thread):
                await channel.remove_user(member)
            else:
                await channel.set_permissions(
                    member,
                    overwrite=None,
                    reason=f"TicketHub member removed by {ctx.author}",
                )
            record["participants"] = [
                member_id for member_id in record.get("participants", []) if int(member_id) != member.id
            ]
            record.setdefault("events", []).append(
                {"type": "member_removed", "actor_id": ctx.author.id, "target_id": member.id, "at": self._now_ts()}
            )
            async with self.config.guild(ctx.guild).tickets() as tickets:
                tickets[str(record["id"])] = record
        except (commands.CommandError, discord.HTTPException) as error:
            await ctx.send(str(error))
            return
        await ctx.send(f"{member.mention} removed from ticket #{record['id']}.")

    @tickethub.command(name="list")
    @commands.guild_only()
    async def tickethub_list(
        self,
        ctx: commands.Context,
        status: str = "open",
        owner: Optional[discord.Member] = None,
    ) -> None:
        """List tracked tickets."""
        assert ctx.guild is not None
        status = status.lower()
        if status not in {"open", "closed", "all"}:
            await ctx.send("Status must be `open`, `closed`, or `all`.")
            return
        tickets = await self.config.guild(ctx.guild).tickets()
        records = list(tickets.values())
        if status != "all":
            records = [record for record in records if record.get("status") == status]
        if owner is not None:
            records = [record for record in records if str(record.get("owner_id")) == str(owner.id)]
        records.sort(key=lambda record: int(record.get("id") or 0), reverse=True)
        if not records:
            await ctx.send("No tickets matched that filter.")
            return
        lines = []
        for record in records[:100]:
            channel = await self._fetch_ticket_channel(ctx.guild, record)
            lines.append(
                f"#{record.get('id')} | {record.get('status')} | {self._user_ref(record.get('owner_id'))} "
                f"| {channel.mention if channel else 'missing location'} | `{record.get('profile')}`"
            )
        for page in pagify("\n".join(lines), page_length=1800):
            await ctx.send(box(page))

    @tickethub.group(name="import", invoke_without_command=True)
    @commands.admin_or_permissions(manage_guild=True)
    async def tickethub_import(self, ctx: commands.Context) -> None:
        """Import settings from other ticket systems."""
        await ctx.send_help(ctx.command)

    @tickethub_import.command(name="aaa3a")
    @commands.admin_or_permissions(manage_guild=True)
    async def tickethub_import_aaa3a(
        self,
        ctx: commands.Context,
        aaa3a_profile: str = "main",
        confirmation: str = "",
    ) -> None:
        """Import a profile from AAA3A's Tickets cog. Use `confirm` to apply."""
        assert ctx.guild is not None
        try:
            mapped_profile, summary = await self._build_aaa3a_import(ctx.guild, aaa3a_profile)
        except commands.CommandError as error:
            await ctx.send(str(error))
            return
        target_profile = self._clean_name(aaa3a_profile)
        preview = "\n".join(summary)
        if confirmation.lower() != "confirm":
            await ctx.send(
                "AAA3A Tickets import preview. Nothing has been changed yet.\n"
                f"Run `{ctx.clean_prefix}tickethub import aaa3a {aaa3a_profile} confirm` to apply.\n\n"
                + box(preview[:1800])
            )
            return
        await self._set_profile(ctx.guild, target_profile, mapped_profile)
        await self.config.guild(ctx.guild).enabled.set(True)
        await ctx.send(f"Imported AAA3A Tickets profile `{aaa3a_profile}` into TicketHub profile `{target_profile}`.")

    async def _build_aaa3a_import(
        self,
        guild: discord.Guild,
        aaa3a_profile: str,
    ) -> Tuple[ProfileRecord, List[str]]:
        aaa_cog = self.bot.get_cog("Tickets")
        if aaa_cog is None or not hasattr(aaa_cog, "config"):
            raise commands.CommandError("AAA3A's `Tickets` cog is not loaded, so I cannot read its config.")
        try:
            aaa_profiles = await aaa_cog.config.guild(guild).profiles()
        except Exception as exc:
            raise commands.CommandError("I could not read AAA3A Tickets profile settings.") from exc
        if aaa3a_profile not in aaa_profiles:
            available = ", ".join(sorted(aaa_profiles)) or "none"
            raise commands.CommandError(f"AAA3A profile `{aaa3a_profile}` was not found. Available: {available}")

        source = aaa_profiles[aaa3a_profile]
        profile = self._merge_profile(None)
        mapping = {
            "enabled": "enabled",
            "max_open_tickets_by_member": "max_open_tickets_by_member",
            "channel_name": "channel_name",
            "welcome_message": "welcome_message",
            "custom_message": "custom_message",
            "transcripts": "transcripts",
            "owner_can_close": "owner_can_close",
            "owner_can_reopen": "owner_can_reopen",
            "support_roles": "support_role_ids",
            "view_roles": "view_role_ids",
            "ping_roles": "ping_role_ids",
            "whitelist_roles": "whitelist_role_ids",
            "blacklist_roles": "blacklist_role_ids",
            "category_open": "ticket_category_id",
            "category_closed": "closed_category_id",
            "logs_channel": "log_channel_id",
        }
        summary = [f"Source profile: {aaa3a_profile}", "Mapped settings:"]
        for source_key, target_key in mapping.items():
            if source_key not in source:
                continue
            value = source.get(source_key)
            if source_key in {
                "support_roles",
                "view_roles",
                "ping_roles",
                "whitelist_roles",
                "blacklist_roles",
            }:
                profile[target_key] = [int(role_id) for role_id in value or []]
            elif source_key == "logs_channel":
                profile[target_key] = int(value) if value else None
                profile["transcript_channel_id"] = int(value) if value else None
            elif source_key in {"category_open", "category_closed"}:
                profile[target_key] = int(value) if value else None
            elif source_key == "channel_name" and not value:
                profile[target_key] = self._default_profile()["channel_name"]
            else:
                profile[target_key] = value
            summary.append(f"- {source_key} -> {target_key}: {profile.get(target_key)!r}")

        auto_delete = source.get("auto_delete_on_close")
        profile["auto_delete_on_close_hours"] = auto_delete
        summary.append(f"- auto_delete_on_close -> auto_delete_on_close_hours: {auto_delete!r}")
        modal_fields = self._sanitize_modal_fields(source.get("creating_modal"))
        uses_default_reason_modal = False
        if modal_fields is None and not source.get("disable_default_open_modal", False):
            modal_fields = self._default_reason_modal()
            uses_default_reason_modal = True
        profile["creating_modal"] = modal_fields
        if uses_default_reason_modal:
            summary.append("- creating_modal -> creating_modal: default reason field")
        elif modal_fields:
            summary.append(f"- creating_modal -> creating_modal: {len(modal_fields)} field(s)")
        else:
            summary.append("- creating_modal -> creating_modal: none")
        summary.append(
            "Not imported: existing open ticket records, modlog cases, forum tags, and panel buttons."
        )
        return profile, summary

    @tickethub.command(name="export")
    @commands.admin_or_permissions(manage_guild=True)
    @commands.bot_has_permissions(attach_files=True)
    async def tickethub_export(self, ctx: commands.Context) -> None:
        """Export TicketHub records as CSV."""
        assert ctx.guild is not None
        tickets = await self.config.guild(ctx.guild).tickets()
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(
            [
                "id",
                "profile",
                "owner_id",
                "channel_id",
                "location_type",
                "status",
                "claimed_by",
                "created_at",
                "closed_at",
                "closed_by",
                "reason",
                "close_reason",
            ]
        )
        for record in sorted(tickets.values(), key=lambda item: int(item.get("id") or 0)):
            writer.writerow(
                [
                    record.get("id"),
                    record.get("profile"),
                    record.get("owner_id"),
                    record.get("channel_id"),
                    record.get("location_type") or "channel",
                    record.get("status"),
                    record.get("claimed_by"),
                    self._format_export_time(record.get("created_at")),
                    self._format_export_time(record.get("closed_at")),
                    record.get("closed_by"),
                    record.get("reason"),
                    record.get("close_reason"),
                ]
            )
        file = discord.File(io.BytesIO(output.getvalue().encode("utf-8")), filename=f"tickethub-{ctx.guild.id}.csv")
        await ctx.send("TicketHub export:", file=file)
