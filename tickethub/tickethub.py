"""TicketHub cog for Red-DiscordBot."""

from __future__ import annotations

import asyncio
import contextlib
import csv
import html
import io
import logging
import re
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any, Union

import discord
from redbot.core import Config, commands
from redbot.core.utils.chat_formatting import box, pagify

from .dashboard_integration import DashboardIntegration

if TYPE_CHECKING:
    from collections.abc import Sequence

    from redbot.core.bot import Red

try:
    import chat_exporter
except ImportError:
    chat_exporter = None

log = logging.getLogger("red.taakoscogs.tickethub")

RECOVERABLE_EXCEPTIONS = (
    discord.DiscordException,
    OSError,
    RuntimeError,
    ValueError,
    KeyError,
    TypeError,
    AttributeError,
)

TicketRecord = dict[str, Any]
ProfileRecord = dict[str, Any]
ModalFieldRecord = dict[str, Any]
MultiPanelRecord = dict[str, Any]
AAA3APanelRecord = dict[str, Any]
TicketLocation = Union[discord.TextChannel, discord.Thread]
MODAL_SELECTS_SUPPORTED = hasattr(discord.ui, "Label")


class TicketPanelView(discord.ui.View):
    """Persistent view for ticket panel messages."""

    def __init__(self, cog: TicketHub) -> None:
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

    def __init__(self, cog: TicketHub) -> None:
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
            ),
        ],
        custom_id="taakoscogs:tickethub:open-select",
    )
    async def open_ticket(
        self,
        interaction: discord.Interaction,
        select: discord.ui.Select,
    ) -> None:
        await self.cog.handle_panel_open(interaction)


class AAA3APanelButton(discord.ui.Button):
    """Compatibility button for imported AAA3A Tickets panel messages."""

    def __init__(
        self,
        cog: TicketHub,
        config_identifier: str,
        option: dict[str, Any],
    ) -> None:
        self.cog = cog
        self.config_identifier = config_identifier
        label = str(option.get("label") or "").strip()[:80] or None
        emoji = cog._component_emoji(option.get("emoji"))
        if label is None and emoji is None:
            label = "Open Ticket"
        try:
            style = discord.ButtonStyle(int(option.get("style") or 2))
        except (TypeError, ValueError):
            style = discord.ButtonStyle.secondary
        super().__init__(
            label=label,
            emoji=emoji,
            style=style,
            custom_id=f"Tickets_{config_identifier}",
        )

    async def callback(self, interaction: discord.Interaction) -> None:
        await self.cog.handle_aaa3a_panel_open(
            interaction,
            "buttons",
            self.config_identifier,
        )


class AAA3APanelSelect(discord.ui.Select):
    """Compatibility dropdown for imported AAA3A Tickets panel messages."""

    def __init__(
        self,
        cog: TicketHub,
        options: dict[str, dict[str, Any]],
    ) -> None:
        self.cog = cog
        select_options = []
        for config_identifier, option in list(options.items())[:25]:
            label = str(
                option.get("label") or option.get("profile") or "Ticket",
            ).strip()
            select_options.append(
                discord.SelectOption(
                    label=label[:100] or "Ticket",
                    value=str(config_identifier)[:100],
                    description=(
                        str(option.get("description"))[:100]
                        if option.get("description")
                        else None
                    ),
                    emoji=cog._component_emoji(option.get("emoji")),
                ),
            )
        super().__init__(
            placeholder="Open a ticket...",
            min_values=1,
            max_values=1,
            options=select_options,
            custom_id="Tickets_dropdown",
        )

    async def callback(self, interaction: discord.Interaction) -> None:
        if not self.values:
            await interaction.response.send_message(
                "Choose a ticket type first.",
                ephemeral=True,
            )
            return
        await self.cog.handle_aaa3a_panel_open(
            interaction,
            "dropdown_options",
            self.values[0],
        )


class AAA3APanelCompatView(discord.ui.View):
    """Persistent handlers for existing AAA3A Tickets panel components."""

    def __init__(self, cog: TicketHub, record: AAA3APanelRecord) -> None:
        super().__init__(timeout=None)
        for config_identifier, option in (record.get("buttons") or {}).items():
            self.add_item(AAA3APanelButton(
                cog, str(config_identifier), option))
        dropdown_options = record.get("dropdown_options") or {}
        if dropdown_options:
            self.add_item(AAA3APanelSelect(cog, dropdown_options))


class TicketMultiPanelButton(discord.ui.Button):
    """Button that opens a specific profile from a multi-panel."""

    def __init__(
        self,
        cog: TicketHub,
        message_id: int,
        option: dict[str, Any],
        *,
        row: int,
    ) -> None:
        self.cog = cog
        self.profile_name = str(option["profile"])
        super().__init__(
            label=str(option["label"]),
            emoji=option.get("emoji") or None,
            style=discord.ButtonStyle.secondary,
            custom_id=(
                f"taakoscogs:tickethub:multi:{message_id}:{self.profile_name}"),
            row=row,
        )

    async def callback(self, interaction: discord.Interaction) -> None:
        await self.cog.handle_panel_open(interaction, self.profile_name)


class TicketMultiPanelSelect(discord.ui.Select):
    """Dropdown that routes each option to its configured profile."""

    def __init__(
        self,
        cog: TicketHub,
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
        cog: TicketHub,
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
                ),
            )


class TicketControlView(discord.ui.View):
    """Persistent view for ticket control messages."""

    def __init__(
        self,
        cog: TicketHub,
        *,
        claimed: bool = False,
        locked: bool = False,
        closed: bool = False,
    ) -> None:
        super().__init__(timeout=None)
        self.cog = cog
        if claimed:
            self.claim.label = "Unclaim"
            self.claim.emoji = "\N{OPEN LOCK}"
            self.claim.style = discord.ButtonStyle.secondary
        if locked:
            self.lock.label = "Unlock"
            self.lock.emoji = "\N{OPEN LOCK}"
            self.lock.style = discord.ButtonStyle.success
        if closed:
            self.claim.disabled = True
            self.lock.disabled = True
            self.members.disabled = True
            self.close.label = "Reopen"
            self.close.emoji = "\N{OPEN HANDS SIGN}"
            self.close.style = discord.ButtonStyle.secondary
        else:
            self.remove_item(self.delete)

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
        await self.cog.handle_ticket_button(interaction, "claim_toggle")

    @discord.ui.button(
        label="Lock",
        emoji="\N{LOCK}",
        style=discord.ButtonStyle.secondary,
        custom_id="taakoscogs:tickethub:lock",
    )
    async def lock(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ) -> None:
        await self.cog.handle_ticket_button(interaction, "lock_toggle")

    @discord.ui.button(
        label="Close",
        emoji="\N{CROSS MARK}",
        style=discord.ButtonStyle.danger,
        custom_id="taakoscogs:tickethub:close",
    )
    async def close(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ) -> None:
        await self.cog.handle_ticket_button(interaction, "close_toggle")

    @discord.ui.button(
        label="Members",
        emoji="\N{BUSTS IN SILHOUETTE}",
        style=discord.ButtonStyle.secondary,
        custom_id="taakoscogs:tickethub:members",
    )
    async def members(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ) -> None:
        await self.cog.handle_ticket_button(interaction, "members")

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

    @discord.ui.button(
        label="Delete",
        emoji="\N{WASTEBASKET}",
        style=discord.ButtonStyle.danger,
        custom_id="taakoscogs:tickethub:delete",
        row=1,
    )
    async def delete(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ) -> None:
        await self.cog.handle_ticket_button(interaction, "delete")


class TicketMemberSelect(discord.ui.UserSelect):
    """Add or remove members from a ticket using Discord's member picker."""

    def __init__(self, parent: TicketMembersView, action: str) -> None:
        self.parent_view = parent
        self.action = action
        super().__init__(
            placeholder=(
                "Select members to add"
                if action == "add"
                else "Select members to remove"
            ),
            min_values=1,
            max_values=10,
            row=0 if action == "add" else 1,
        )

    async def callback(self, interaction: discord.Interaction) -> None:
        await self.parent_view.cog.handle_ticket_member_selection(
            interaction,
            self.parent_view.ticket_id,
            self.action,
            list(self.values),
        )


class TicketMembersView(discord.ui.View):
    """Temporary member-management controls for one ticket."""

    def __init__(self, cog: TicketHub, ticket_id: int) -> None:
        super().__init__(timeout=300)
        self.cog = cog
        self.ticket_id = ticket_id
        self.add_item(TicketMemberSelect(self, "add"))
        self.add_item(TicketMemberSelect(self, "remove"))


class TicketReopenReasonModal(discord.ui.Modal):
    """Collect a reason before reopening a ticket."""

    def __init__(
        self,
        cog: TicketHub,
        guild_id: int,
        ticket_id: int,
        requester_id: int,
    ) -> None:
        super().__init__(title="Reopen Ticket", timeout=300)
        self.cog = cog
        self.guild_id = guild_id
        self.ticket_id = ticket_id
        self.requester_id = requester_id
        self.reason = discord.ui.TextInput(
            label="Reason for reopening",
            style=discord.TextStyle.paragraph,
            placeholder="Why should this ticket be reopened?",
            required=False,
            max_length=1000,
        )
        self.add_item(self.reason)

    async def on_submit(self, interaction: discord.Interaction) -> None:
        if (
            not interaction.guild
            or not isinstance(interaction.user, discord.Member)
            or interaction.guild.id != self.guild_id
            or interaction.user.id != self.requester_id
        ):
            await interaction.response.send_message(
                "This reopen request is not valid here.",
                ephemeral=True,
            )
            return
        await interaction.response.defer(ephemeral=True, thinking=True)
        try:
            record = await self.cog._get_ticket_record_by_id(
                interaction.guild,
                self.ticket_id,
            )
            await self.cog._reopen_ticket(
                interaction.guild,
                record,
                interaction.user,
                reason=str(self.reason.value or "").strip(),
            )
        except commands.CommandError as error:
            await interaction.followup.send(str(error), ephemeral=True)
            return
        await interaction.followup.send("Ticket reopened.", ephemeral=True)


class TicketCloseReasonModal(discord.ui.Modal):
    """Collect a close reason before posting the confirmation prompt."""

    def __init__(
        self,
        cog: TicketHub,
        guild_id: int,
        ticket_id: int,
        requester_id: int,
    ) -> None:
        super().__init__(title="Close Ticket", timeout=300)
        self.cog = cog
        self.guild_id = guild_id
        self.ticket_id = ticket_id
        self.requester_id = requester_id
        self.reason = discord.ui.TextInput(
            label="Reason for closing",
            style=discord.TextStyle.paragraph,
            placeholder="Why should this ticket be closed?",
            required=False,
            max_length=1000,
        )
        self.add_item(self.reason)

    async def on_submit(self, interaction: discord.Interaction) -> None:
        if interaction.user.id != self.requester_id:
            await interaction.response.send_message(
                "Only the person who started this close request can submit the reason.",
                ephemeral=True,
            )
            return
        await interaction.response.defer(ephemeral=True, thinking=True)
        try:
            message = await self.cog.start_close_confirmation(
                interaction,
                self.guild_id,
                self.ticket_id,
                self.requester_id,
                str(self.reason.value or "").strip(),
            )
        except commands.CommandError as error:
            await interaction.followup.send(str(error), ephemeral=True)
            return
        await interaction.followup.send(
            f"Close confirmation posted: {message.jump_url}",
            ephemeral=True,
        )

    async def on_error(
        self,
        interaction: discord.Interaction,
        error: Exception,
    ) -> None:
        log.exception(
            "TicketHub close-reason modal failed.",
            exc_info=(type(error), error, error.__traceback__),
        )
        if interaction.response.is_done():
            await interaction.followup.send(
                "I could not start that close confirmation.",
                ephemeral=True,
            )
        else:
            await interaction.response.send_message(
                "I could not start that close confirmation.",
                ephemeral=True,
            )


class TicketCloseReasonLauncherView(discord.ui.View):
    """Temporary command view that can open a Discord modal."""

    def __init__(
        self,
        cog: TicketHub,
        guild_id: int,
        ticket_id: int,
        requester_id: int,
    ) -> None:
        super().__init__(timeout=300)
        self.cog = cog
        self.guild_id = guild_id
        self.ticket_id = ticket_id
        self.requester_id = requester_id
        self.enter_reason.custom_id = (
            f"taakoscogs:tickethub:close-reason:{ticket_id}:{requester_id}"
        )

    @discord.ui.button(
        label="Enter Close Reason",
        emoji="\N{MEMO}",
        style=discord.ButtonStyle.danger,
        custom_id="taakoscogs:tickethub:close-reason",
    )
    async def enter_reason(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ) -> None:
        if interaction.user.id != self.requester_id:
            await interaction.response.send_message(
                "Only the person who ran the close command can use this button.",
                ephemeral=True,
            )
            return
        try:
            await self.cog.validate_close_request_ids(
                self.guild_id,
                self.ticket_id,
                interaction.user.id,
            )
        except commands.CommandError as error:
            await interaction.response.send_message(str(error), ephemeral=True)
            return
        await interaction.response.send_modal(
            TicketCloseReasonModal(
                self.cog,
                self.guild_id,
                self.ticket_id,
                self.requester_id,
            ),
        )
        self.stop()
        if interaction.message is not None:
            with contextlib.suppress(discord.HTTPException):
                await interaction.message.edit(view=None)


class TicketCloseConfirmationView(discord.ui.View):
    """Persistent Cancel/Close confirmation controls."""

    def __init__(self, cog: TicketHub, ticket_id: int) -> None:
        super().__init__(timeout=None)
        self.cog = cog
        self.ticket_id = ticket_id
        self.cancel.custom_id = f"taakoscogs:tickethub:close-cancel:{ticket_id}"
        self.confirm.custom_id = f"taakoscogs:tickethub:close-confirm:{ticket_id}"

    @discord.ui.button(
        label="Cancel",
        style=discord.ButtonStyle.secondary,
        custom_id="taakoscogs:tickethub:close-cancel",
    )
    async def cancel(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ) -> None:
        await self.cog.handle_close_confirmation(
            interaction,
            self.ticket_id,
            confirmed=False,
        )

    @discord.ui.button(
        label="Close",
        emoji="\N{CROSS MARK}",
        style=discord.ButtonStyle.danger,
        custom_id="taakoscogs:tickethub:close-confirm",
    )
    async def confirm(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ) -> None:
        await self.cog.handle_close_confirmation(
            interaction,
            self.ticket_id,
            confirmed=True,
        )


class TicketOpenModal(discord.ui.Modal):
    """Dynamic modal shown before opening a ticket from a panel."""

    def __init__(
        self,
        cog: TicketHub,
        guild: discord.Guild,
        owner: discord.Member,
        profile_name: str,
        fields: Sequence[ModalFieldRecord],
        panel_label: str | None = None,
    ) -> None:
        super().__init__(title="Open Ticket", timeout=300)
        self.cog = cog
        self.guild = guild
        self.owner = owner
        self.profile_name = profile_name
        self.panel_label = panel_label
        self.inputs: list[tuple[str, discord.ui.Item]] = []

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
                    placeholder=str(field.get("placeholder") or "Choose an option")[
                        :100
                    ],
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
                style_value = int(
                    field.get("style") or discord.TextStyle.paragraph.value,
                )
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
                    default=str(default)[:4000] if default not in (
                        None, "") else None,
                    placeholder=str(placeholder)[:100]
                    if placeholder not in (None, "")
                    else None,
                    min_length=field.get("min_length"),
                    max_length=field.get("max_length"),
                )

            if MODAL_SELECTS_SUPPORTED:
                self.add_item(
                    discord.ui.Label(
                        text=display_label,
                        component=component,
                    ),
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
        if (
            len(form_answers) == 1
            and form_answers[0]["label"].strip().lower() == "reason"
        ):
            reason = form_answers[0]["value"][:1000]

        try:
            record, channel = await self.cog._create_ticket(
                self.guild,
                interaction.user,
                self.profile_name,
                reason=reason,
                form_answers=form_answers,
                panel_label=self.panel_label,
            )
        except commands.CommandError as error:
            await interaction.followup.send(str(error), ephemeral=True)
            return

        await interaction.followup.send(
            f"Ticket #{record['id']} opened: {channel.mention}",
            ephemeral=True,
        )

    async def on_error(
        self,
        interaction: discord.Interaction,
        error: Exception,
    ) -> None:
        log.exception(
            "TicketHub open-ticket modal failed.",
            exc_info=(type(error), error, error.__traceback__),
        )
        if interaction.response.is_done():
            await interaction.followup.send(
                "I could not create that ticket.",
                ephemeral=True,
            )
        else:
            await interaction.response.send_message(
                "I could not create that ticket.",
                ephemeral=True,
            )


class TicketQuestionTextModal(discord.ui.Modal):
    """Collect one text answer for a mixed ticket questionnaire."""

    def __init__(
        self,
        questionnaire: TicketQuestionnaireView,
        field_index: int,
        field: ModalFieldRecord,
    ) -> None:
        label = str(field.get("label") or "Question").strip()[
                    :45] or "Question"
        super().__init__(title="Open Ticket", timeout=300)
        self.questionnaire = questionnaire
        self.field_index = field_index
        style_value = int(field.get("style")
                          or discord.TextStyle.paragraph.value)
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
            placeholder=str(placeholder)[:100]
            if placeholder not in (None, "")
            else None,
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
        cog: TicketHub,
        guild: discord.Guild,
        owner: discord.Member,
        profile_name: str,
        fields: Sequence[ModalFieldRecord],
        panel_label: str | None = None,
    ) -> None:
        super().__init__(timeout=300)
        self.cog = cog
        self.guild = guild
        self.owner = owner
        self.profile_name = profile_name
        self.panel_label = panel_label
        self.fields = list(fields[:5])
        self.field_index = 0
        self.form_answers: list[dict[str, str]] = []
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
                f"- {choice}" for choice in field.get("choices", []))
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
                placeholder=str(field.get("placeholder")
                                or "Choose an option")[:100],
                options=[
                    discord.SelectOption(
                        label=str(choice)[:100],
                        value=str(choice)[:100],
                    )
                    for choice in field.get("choices", [])[:25]
                ],
                min_values=1,
                max_values=1,
            )
            select.callback = self._choice_callback
            self.add_item(select)
        elif question_type == "boolean":
            yes = discord.ui.Button(
                label="Yes", style=discord.ButtonStyle.success)
            yes.callback = self._yes_callback
            self.add_item(yes)
            no = discord.ui.Button(
                label="No", style=discord.ButtonStyle.danger)
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
            skip = discord.ui.Button(
                label="Skip", style=discord.ButtonStyle.secondary)
            skip.callback = self._skip_callback
            self.add_item(skip)

        cancel = discord.ui.Button(
            label="Cancel", style=discord.ButtonStyle.secondary)
        cancel.callback = self._cancel_callback
        self.add_item(cancel)

    async def _text_callback(self, interaction: discord.Interaction) -> None:
        await interaction.response.send_modal(
            TicketQuestionTextModal(
                self, self.field_index, self.current_field),
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
                },
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
                panel_label=self.panel_label,
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


class TicketHub(DashboardIntegration, commands.Cog):
    """Ticket panels, ticket lifecycle controls, imports, and HTML transcripts."""

    CONFIG_IDENTIFIER = 2026051401
    DEFAULT_COLOR = 0x5865F2
    OPEN_COLOR = 0x57F287
    CLOSED_COLOR = 0xED4245
    CLAIMED_COLOR = 0xFEE75C
    MAX_TRANSCRIPT_MESSAGES = 5000
    DEFAULT_CLOSE_REQUEST_TIMEOUT_MINUTES = 5
    MIN_CLOSE_REQUEST_TIMEOUT_MINUTES = 1
    MAX_CLOSE_REQUEST_TIMEOUT_MINUTES = 4320
    CHANNEL_TEMPLATE_FIELDS = {
        "id",
        "ticket_id",
        "profile_id",
        "global_id",
        "owner_display_name",
        "owner_name",
        "owner_mention",
        "owner_id",
        "guild_name",
        "guild_id",
        "profile",
    }

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
            aaa3a_panels={},
        )
        self._locks: dict[int, asyncio.Lock] = {}
        self._prefix_conflict_mode = False
        self._set_prefix_conflict_mode = False
        self._panel_view = TicketPanelView(self)
        self._panel_select_view = TicketPanelSelectView(self)
        self._control_view = TicketControlView(self)
        self._closed_control_view = TicketControlView(self, closed=True)
        self._multi_panel_views: dict[int, TicketMultiPanelView] = {}
        self._aaa3a_panel_views: dict[int, AAA3APanelCompatView] = {}
        self._close_confirmation_views: dict[
            tuple[int, int],
            TicketCloseConfirmationView,
        ] = {}
        self._close_confirmation_tasks: dict[tuple[int, int], asyncio.Task] = {
            }
        self._auto_delete_tasks: dict[tuple[int, int], asyncio.Task] = {}
        self._control_refresh_task: asyncio.Task | None = None

    def use_conflict_safe_prefix_root(self) -> None:
        """Rename the prefix root when another loaded cog already owns `ticket`."""
        self._prefix_conflict_mode = True
        for command in self.__cog_commands__:
            if command.name != "ticket":
                continue
            command.name = "tickethub"
            command.aliases = [
                alias for alias in ("thub",) if self.bot.get_command(alias) is None
            ]
            app_command = getattr(command, "app_command", None)
            if app_command is not None:
                try:
                    app_command.name = "tickethub"
                except RECOVERABLE_EXCEPTIONS:
                    log.debug(
                        "Could not rename TicketHub app command during conflict-safe load.",
                    )
            break

    def use_conflict_safe_set_root(self) -> None:
        """Rename the setup prefix root when another cog already owns `ticketset`."""
        self._set_prefix_conflict_mode = True
        for command in self.__cog_commands__:
            if command.name != "ticketset":
                continue
            command.name = "tickethubset"
            command.aliases = [
                alias for alias in ("thubset",) if self.bot.get_command(alias) is None
            ]
            app_command = getattr(command, "app_command", None)
            if app_command is not None:
                try:
                    app_command.name = "tickethubset"
                except RECOVERABLE_EXCEPTIONS:
                    log.debug(
                        "Could not rename TicketHub setup app command during conflict-safe load.",
                    )
            break

    def _prefix_root(self) -> str:
        return "tickethub" if self._prefix_conflict_mode else "ticket"

    def _prefixed_root(self, ctx: commands.Context) -> str:
        return f"{ctx.clean_prefix}{self._prefix_root()}"

    def _set_prefix_root(self) -> str:
        return "tickethubset" if self._set_prefix_conflict_mode else "ticketset"

    def _prefixed_set_root(self, ctx: commands.Context) -> str:
        return f"{ctx.clean_prefix}{self._set_prefix_root()}"

    async def cog_load(self) -> None:
        """Register persistent views."""
        self.bot.add_view(self._panel_view)
        self.bot.add_view(self._panel_select_view)
        self.bot.add_view(self._control_view)
        self.bot.add_view(self._closed_control_view)
        await self._restore_multi_panel_views()
        await self._restore_aaa3a_panel_views()
        await self._restore_close_confirmations()
        await self._restore_auto_delete_tasks()
        self._control_refresh_task = asyncio.create_task(
            self._refresh_ticket_control_messages(),
        )

    @commands.Cog.listener()
    async def on_cog_remove(self, cog: commands.Cog) -> None:
        """Restore imported panel handlers after AAA3A Tickets unloads."""
        if cog.qualified_name != "Tickets":
            return
        # AAA3A and TicketHub intentionally use the same message/component IDs.
        # discord.py removes those shared dispatch keys when AAA3A's views stop,
        # so register fresh TicketHub views after its unload has completed.
        await self._restore_aaa3a_panel_views()
        log.info("Restored imported AAA3A Tickets panel handlers after cog unload.")

    def cog_unload(self) -> None:
        if self._control_refresh_task is not None:
            self._control_refresh_task.cancel()
            self._control_refresh_task = None
        for task in self._close_confirmation_tasks.values():
            task.cancel()
        self._close_confirmation_tasks.clear()
        for task in self._auto_delete_tasks.values():
            task.cancel()
        self._auto_delete_tasks.clear()
        for view in self._close_confirmation_views.values():
            view.stop()
        self._close_confirmation_views.clear()
        for view in self._aaa3a_panel_views.values():
            view.stop()
        self._aaa3a_panel_views.clear()

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
                    if str(record.get("locked_by")) == user_key:
                        record["locked_by"] = None
                    if str(record.get("unlocked_by")) == user_key:
                        record["unlocked_by"] = None
                    if str(record.get("closed_by")) == user_key:
                        record["closed_by"] = None
                    if str(record.get("reopened_by")) == user_key:
                        record["reopened_by"] = None
                    pending_close = record.get("pending_close")
                    if (
                        isinstance(pending_close, dict)
                        and str(pending_close.get("requested_by")) == user_key
                    ):
                        pending_close["requested_by"] = None
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

    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member) -> None:
        """Close configured tickets when their owner leaves the server."""
        tickets = await self.config.guild(member.guild).tickets()
        for record in tickets.values():
            if record.get("status") != "open" or str(record.get("owner_id")) != str(
                member.id,
            ):
                continue
            profile = await self._get_profile(
                member.guild,
                str(record.get("profile") or "main"),
            )
            if not profile.get("close_on_leave"):
                continue
            try:
                async with self._guild_lock(member.guild.id):
                    current = await self._get_ticket_record_by_id(
                        member.guild,
                        int(record["id"]),
                    )
                    if current.get("status") != "open":
                        continue
                    await self._close_ticket(
                        member.guild,
                        current,
                        member,
                        reason="Ticket owner left the server.",
                        permission_checked=True,
                    )
            except (commands.CommandError, discord.HTTPException):
                log.exception(
                    "Failed to close TicketHub ticket %s after owner departure.",
                    record.get("id"),
                )

    async def _forget_deleted_ticket_location(
        self,
        guild_id: int,
        channel_id: int,
    ) -> None:
        removed_ids = []
        async with self.config.guild_from_id(guild_id).tickets() as tickets:
            for key, record in list(tickets.items()):
                if str(record.get("channel_id")) != str(channel_id):
                    continue
                removed_ids.append(int(record.get("id") or key))
                tickets.pop(key, None)
        for ticket_id in removed_ids:
            self._cancel_close_confirmation_resources(guild_id, ticket_id)
            self._cancel_ticket_auto_delete(guild_id, ticket_id)

    @commands.Cog.listener()
    async def on_guild_channel_delete(self, channel: discord.abc.GuildChannel) -> None:
        if isinstance(channel, discord.TextChannel):
            await self._forget_deleted_ticket_location(channel.guild.id, channel.id)

    @commands.Cog.listener()
    async def on_raw_thread_delete(self, payload: Any) -> None:
        guild_id = getattr(payload, "guild_id", None)
        thread_id = getattr(payload, "thread_id", None)
        if guild_id is not None and thread_id is not None:
            await self._forget_deleted_ticket_location(int(guild_id), int(thread_id))

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
            "max_open_tickets_by_member": 5,
            "channel_name": "ticket-{id}-{owner_name}",
            "next_profile_ticket_id": None,
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
            "owner_can_reopen": True,
            "owner_can_add_members": False,
            "owner_can_remove_members": False,
            "close_on_leave": True,
            "close_request_timeout_minutes": TicketHub.DEFAULT_CLOSE_REQUEST_TIMEOUT_MINUTES,
            "ticket_role_id": None,
            "speak_role_ids": [],
            "control_emojis": {
                "claim": "✅",
                "unclaim": "🔓",
                "lock": "🔒",
                "unlock": "🔓",
                "close": "❌",
                "reopen": "👐",
                "members": "👥",
                "transcript": "📄",
                "delete": "🗑️",
            },
            "auto_delete_on_close_hours": None,
        }

    @staticmethod
    def _default_reason_modal() -> list[ModalFieldRecord]:
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
            },
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
    def _format_minutes(value: int) -> str:
        try:
            minutes = max(0, int(value))
        except (TypeError, ValueError):
            minutes = 0
        if minutes < 60:
            return f"{minutes} minute{'s' if minutes != 1 else ''}"
        hours, remaining_minutes = divmod(minutes, 60)
        hour_text = f"{hours} hour{'s' if hours != 1 else ''}"
        if remaining_minutes == 0:
            return hour_text
        minute_text = (
            f"{remaining_minutes} minute{'s' if remaining_minutes != 1 else ''}"
        )
        return f"{hour_text} {minute_text}"

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
    def _ticket_url(guild_id: int, channel_id: Any) -> str | None:
        if channel_id in (None, ""):
            return None
        try:
            return f"https://discord.com/channels/{int(guild_id)}/{int(channel_id)}"
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _status_display(record: TicketRecord) -> str:
        if record.get("status") == "closed":
            return "🔴 Closed"
        if record.get("claimed_by"):
            return "🟡 Claimed"
        return "🟢 Open"

    @staticmethod
    def _quote_text(value: Any, limit: int = 1024) -> str:
        text = str(value or "Not provided.").strip()
        quoted = "\n".join(
            f"> {line}" if line else ">" for line in text.splitlines())
        return quoted[:limit]

    @staticmethod
    def _event_icon(title: str) -> str:
        lowered = title.lower()
        if "deleted" in lowered:
            return "🗑️"
        if "reopened" in lowered or "opened" in lowered or "unlocked" in lowered:
            return "🟢"
        if "closed" in lowered or "locked" in lowered:
            return "🔴"
        if "claimed" in lowered:
            return "🟡"
        if "transcript" in lowered:
            return "📄"
        if "member" in lowered:
            return "👥"
        return "🎫"

    @staticmethod
    def _set_member_identity(
        embed: discord.Embed,
        member: discord.abc.User | None,
        *,
        fallback_name: str | None = None,
        thumbnail: bool = True,
    ) -> None:
        if member is None:
            if fallback_name:
                embed.set_author(name=fallback_name)
            return
        avatar_url = str(member.display_avatar.url)
        embed.set_author(
            name=f"{member.display_name} ({member.id})",
            icon_url=avatar_url,
        )
        if thumbnail:
            embed.set_thumbnail(url=avatar_url)

    @staticmethod
    def _jump_view(url: str | None) -> discord.ui.View | None:
        if url is None:
            return None
        view = discord.ui.View()
        view.add_item(
            discord.ui.Button(
                label="Jump to Ticket",
                emoji="↗️",
                style=discord.ButtonStyle.link,
                url=url,
            ),
        )
        return view

    @staticmethod
    def _clean_name(value: str) -> str:
        cleaned = value.strip().lower()
        cleaned = re.sub(r"[^a-z0-9_-]+", "-", cleaned)
        cleaned = cleaned.strip("-_")
        if not cleaned:
            raise commands.BadArgument(
                "Profile names can only contain letters, numbers, dashes, and underscores.",
            )
        return cleaned[:40]

    @staticmethod
    def _clean_optional_text(value: str | None, limit: int) -> str | None:
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
        default: int | None = None,
        minimum: int | None = None,
        maximum: int | None = None,
    ) -> int | None:
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
    def _modal_type_name(cls, value: Any) -> str | None:
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
    def _clean_modal_choices(cls, value: Any) -> list[str]:
        if isinstance(value, str):
            raw_choices = value.split(",")
        elif isinstance(value, (list, tuple)):
            raw_choices = value
        else:
            raw_choices = []
        choices: list[str] = []
        for raw_choice in raw_choices:
            choice = cls._clean_modal_text(raw_choice, 100)
            if choice and choice not in choices:
                choices.append(choice)
            if len(choices) >= 25:
                break
        return choices

    @classmethod
    def _sanitize_modal_fields(cls, value: Any) -> list[ModalFieldRecord] | None:
        if not isinstance(value, list):
            return None
        fields: list[ModalFieldRecord] = []
        for raw_field in value[:5]:
            if not isinstance(raw_field, dict):
                continue
            label = cls._clean_modal_text(raw_field.get("label"), 45)
            if not label:
                continue
            question_type = cls._modal_type_name(
                raw_field.get("type")) or "text"
            choices = cls._clean_modal_choices(raw_field.get("choices"))
            if question_type == "choice" and len(choices) < 2:
                question_type = "text"
                choices = []
            style = (
                cls._clean_modal_int(
                    raw_field.get("style"),
                    default=2,
                    minimum=1,
                    maximum=2,
                )
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
            if (
                min_length is not None
                and max_length is not None
                and min_length > max_length
            ):
                min_length = None
            fields.append(
                {
                    "label": label,
                    "type": question_type,
                    "style": style,
                    "required": cls._clean_modal_bool(
                        raw_field.get("required"),
                        default=True,
                    ),
                    "default": cls._clean_modal_text(raw_field.get("default"), 4000),
                    "placeholder": cls._clean_modal_text(
                        raw_field.get("placeholder"),
                        100,
                    ),
                    "min_length": min_length,
                    "max_length": max_length,
                    "choices": choices,
                },
            )
        return fields or None

    @staticmethod
    def _merge_profile(value: dict[str, Any] | None) -> ProfileRecord:
        profile = TicketHub._default_profile()
        if value:
            profile.update(value)
            for key in (
                "support_role_ids",
                "speak_role_ids",
                "view_role_ids",
                "ping_role_ids",
                "whitelist_role_ids",
                "blacklist_role_ids",
            ):
                profile[key] = list(profile.get(key) or [])
            profile["control_emojis"] = dict(
                profile.get("control_emojis") or {})
            profile["creating_modal"] = TicketHub._sanitize_modal_fields(
                profile.get("creating_modal"),
            )
            profile["panel_style"] = TicketHub._panel_style(
                profile.get("panel_style"))
            profile["ticket_mode"] = TicketHub._ticket_mode(profile)
            try:
                next_profile_ticket_id = profile.get("next_profile_ticket_id")
                profile["next_profile_ticket_id"] = (
                    max(1, int(next_profile_ticket_id))
                    if next_profile_ticket_id is not None
                    else None
                )
            except (TypeError, ValueError):
                profile["next_profile_ticket_id"] = None
            try:
                thread_parent_id = profile.get("thread_parent_channel_id")
                profile["thread_parent_channel_id"] = (
                    int(thread_parent_id) if thread_parent_id else None
                )
            except (TypeError, ValueError):
                profile["thread_parent_channel_id"] = None
            profile["close_request_timeout_minutes"] = (
                TicketHub._close_request_timeout_minutes(profile)
            )
        return profile

    @staticmethod
    def _close_request_timeout_minutes(profile: ProfileRecord) -> int:
        try:
            minutes = int(
                profile.get(
                    "close_request_timeout_minutes",
                    TicketHub.DEFAULT_CLOSE_REQUEST_TIMEOUT_MINUTES,
                ),
            )
        except (TypeError, ValueError):
            minutes = TicketHub.DEFAULT_CLOSE_REQUEST_TIMEOUT_MINUTES
        return max(
            TicketHub.MIN_CLOSE_REQUEST_TIMEOUT_MINUTES,
            min(minutes, TicketHub.MAX_CLOSE_REQUEST_TIMEOUT_MINUTES),
        )

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
                "Panel style must be `button` or `dropdown`.",
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
        message_id: int | None = None,
    ) -> MultiPanelRecord | None:
        if not isinstance(value, dict):
            return None
        try:
            cleaned_message_id = int(
                value.get("message_id") or message_id or 0)
            channel_id = int(value.get("channel_id") or 0)
        except (TypeError, ValueError):
            return None
        if not cleaned_message_id or not channel_id:
            return None
        options: list[dict[str, Any]] = []
        seen_profiles = set()
        for raw_option in (value.get("options") or [])[:25]:
            if not isinstance(raw_option, dict):
                continue
            try:
                profile_name = cls._clean_name(
                    str(raw_option.get("profile") or ""))
            except commands.BadArgument:
                continue
            if profile_name in seen_profiles:
                continue
            label = str(raw_option.get("label") or "").strip()[:80]
            if not label:
                continue
            description = str(raw_option.get(
                "description") or "").strip()[:100]
            emoji = str(raw_option.get("emoji") or "").strip()[:100]
            options.append(
                {
                    "profile": profile_name,
                    "label": label,
                    "description": description or None,
                    "emoji": emoji or None,
                },
            )
            seen_profiles.add(profile_name)
        placeholder = str(value.get("placeholder")
                          or "Choose a ticket type...").strip()
        return {
            "channel_id": channel_id,
            "message_id": cleaned_message_id,
            "style": cls._panel_style(value.get("style")),
            "placeholder": placeholder[:100] or "Choose a ticket type...",
            "options": options,
        }

    @staticmethod
    def _multi_panel_emoji(value: str) -> str | None:
        emoji = value.strip()
        if emoji.lower() in {"none", "no", "off", "clear", "-"}:
            return None
        if not emoji or len(emoji) > 100:
            raise commands.BadArgument(
                "Provide one Unicode/custom emoji, or use `none`.",
            )
        return emoji

    @staticmethod
    def _multi_panel_option_text(details: str) -> tuple[str, str | None]:
        label, separator, description = details.partition("|")
        label = label.strip()
        description = description.strip() if separator else ""
        if not 1 <= len(label) <= 80:
            raise commands.BadArgument(
                "Multi-panel option names must be between 1 and 80 characters.",
            )
        if len(description) > 100:
            raise commands.BadArgument(
                "Multi-panel option descriptions cannot exceed 100 characters.",
            )
        return label, description or None

    def _build_multi_panel_view(
        self,
        record: MultiPanelRecord,
    ) -> TicketMultiPanelView:
        cleaned = self._sanitize_multi_panel_record(record)
        if cleaned is None or not cleaned["options"]:
            raise commands.BadArgument(
                "A multi-panel needs at least one valid profile option.",
            )
        try:
            return TicketMultiPanelView(
                self,
                int(cleaned["message_id"]),
                cleaned,
            )
        except (TypeError, ValueError) as exc:
            raise commands.BadArgument(
                "One of the configured panel emojis is not valid for Discord.",
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
                "That message is not a tracked TicketHub multi-panel.",
            )
        return record

    async def _save_multi_panel(
        self,
        guild: discord.Guild,
        message: discord.Message,
        record: MultiPanelRecord,
    ) -> MultiPanelRecord:
        cleaned = self._sanitize_multi_panel_record(
            record, message_id=message.id)
        if cleaned is None or not cleaned["options"]:
            raise commands.BadArgument(
                "A multi-panel needs at least one valid profile option.",
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
                "I could not update that multi-panel message.",
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
                "I could not remove the components from that message.",
            ) from exc
        async with self.config.guild(guild).multi_panels() as panels:
            panels.pop(str(message.id), None)
        view = self._multi_panel_views.pop(message.id, None)
        if view is not None:
            view.stop()

    def _component_emoji(self, value: Any) -> str | None:
        emoji = str(value or "").strip()
        if not emoji:
            return None
        if emoji.isdigit():
            cached_emoji = self.bot.get_emoji(int(emoji))
            return str(cached_emoji) if cached_emoji is not None else None
        return emoji[:100]

    @classmethod
    def _sanitize_aaa3a_panel_record(
        cls,
        value: Any,
        *,
        message_key: str | None = None,
    ) -> AAA3APanelRecord | None:
        if not isinstance(value, dict):
            return None
        channel_id = value.get("channel_id")
        message_id = value.get("message_id")
        if (not channel_id or not message_id) and message_key is not None:
            try:
                channel_id, message_id = str(message_key).split("-", 1)
            except ValueError:
                return None
        try:
            cleaned_channel_id = int(channel_id)
            cleaned_message_id = int(message_id)
        except (TypeError, ValueError):
            return None

        buttons: dict[str, dict[str, Any]] = {}
        raw_buttons = value.get("buttons") or {}
        if isinstance(raw_buttons, dict):
            for config_identifier, raw_option in raw_buttons.items():
                if not isinstance(raw_option, dict):
                    continue
                clean_identifier = str(config_identifier).strip()[:100]
                if not clean_identifier:
                    continue
                try:
                    profile = cls._clean_name(
                        str(raw_option.get("profile") or "main"))
                except commands.BadArgument:
                    continue
                label = cls._clean_modal_text(
                    raw_option.get("label"), 80) or None
                emoji = cls._clean_modal_text(
                    raw_option.get("emoji"), 100) or None
                if label is None and emoji is None:
                    label = "Open Ticket"
                buttons[clean_identifier] = {
                    "profile": profile,
                    "label": label,
                    "emoji": emoji,
                    "style": cls._clean_modal_int(
                        raw_option.get("style"),
                        default=2,
                        minimum=1,
                        maximum=4,
                    )
                    or 2,
                }

        dropdown_options: dict[str, dict[str, Any]] = {}
        raw_dropdown_options = value.get("dropdown_options") or {}
        if isinstance(raw_dropdown_options, dict):
            for config_identifier, raw_option in raw_dropdown_options.items():
                if not isinstance(raw_option, dict):
                    continue
                clean_identifier = str(config_identifier).strip()[:100]
                if not clean_identifier:
                    continue
                try:
                    profile = cls._clean_name(
                        str(raw_option.get("profile") or "main"))
                except commands.BadArgument:
                    continue
                label = cls._clean_modal_text(raw_option.get("label"), 100)
                if not label:
                    label = profile
                dropdown_options[clean_identifier] = {
                    "profile": profile,
                    "label": label,
                    "description": cls._clean_modal_text(
                        raw_option.get("description"),
                        100,
                    )
                    or None,
                    "emoji": cls._clean_modal_text(raw_option.get("emoji"), 100)
                    or None,
                }

        if not buttons and not dropdown_options:
            return None
        return {
            "channel_id": cleaned_channel_id,
            "message_id": cleaned_message_id,
            "buttons": buttons,
            "dropdown_options": dropdown_options,
        }

    def _build_aaa3a_panel_view(
        self,
        record: AAA3APanelRecord,
    ) -> AAA3APanelCompatView:
        cleaned = self._sanitize_aaa3a_panel_record(record)
        if cleaned is None:
            raise commands.BadArgument("That AAA3A panel record is invalid.")
        return AAA3APanelCompatView(self, cleaned)

    def _register_aaa3a_panel_view(self, record: AAA3APanelRecord) -> None:
        cleaned = self._sanitize_aaa3a_panel_record(record)
        if cleaned is None:
            return
        message_id = int(cleaned["message_id"])
        previous_view = self._aaa3a_panel_views.pop(message_id, None)
        if previous_view is not None:
            previous_view.stop()
        view = self._build_aaa3a_panel_view(cleaned)
        self.bot.add_view(view, message_id=message_id)
        self._aaa3a_panel_views[message_id] = view

    async def _restore_aaa3a_panel_views(self) -> None:
        all_guilds = await self.config.all_guilds()
        for guild_data in all_guilds.values():
            panels = guild_data.get("aaa3a_panels") or {}
            if not isinstance(panels, dict):
                continue
            for message_key, raw_record in panels.items():
                record = self._sanitize_aaa3a_panel_record(
                    raw_record,
                    message_key=str(message_key),
                )
                if record is None:
                    continue
                try:
                    self._register_aaa3a_panel_view(record)
                except (commands.CommandError, TypeError, ValueError):
                    log.exception(
                        "Failed to restore imported AAA3A Tickets panel %s.",
                        message_key,
                    )

    async def _set_aaa3a_panel_records(
        self,
        guild: discord.Guild,
        records: dict[str, AAA3APanelRecord],
    ) -> dict[str, AAA3APanelRecord]:
        cleaned_records: dict[str, AAA3APanelRecord] = {}
        for message_key, record in records.items():
            cleaned = self._sanitize_aaa3a_panel_record(
                record,
                message_key=str(message_key),
            )
            if cleaned is None:
                continue
            key = f"{cleaned['channel_id']}-{cleaned['message_id']}"
            cleaned_records[key] = cleaned
        await self.config.guild(guild).aaa3a_panels.set(cleaned_records)
        for record in cleaned_records.values():
            try:
                self._register_aaa3a_panel_view(record)
            except (commands.CommandError, TypeError, ValueError):
                log.exception(
                    "Failed to register imported AAA3A Tickets panel %s.",
                    record.get("message_id"),
                )
        return cleaned_records

    async def _collect_aaa3a_panel_records(
        self,
        guild: discord.Guild,
    ) -> dict[str, AAA3APanelRecord]:
        aaa_cog = self.bot.get_cog("Tickets")
        if aaa_cog is None or not hasattr(aaa_cog, "config"):
            return {}
        try:
            raw_panels = await aaa_cog.config.guild(guild).buttons_dropdowns()
        except RECOVERABLE_EXCEPTIONS:
            log.exception("Could not read AAA3A Tickets panel settings.")
            return {}
        if not isinstance(raw_panels, dict):
            return {}
        records: dict[str, AAA3APanelRecord] = {}
        for message_key, components in raw_panels.items():
            record = self._sanitize_aaa3a_panel_record(
                components,
                message_key=str(message_key),
            )
            if record is None:
                continue
            key = f"{record['channel_id']}-{record['message_id']}"
            records[key] = record
        return records

    def _aaa3a_panel_label(self, option: dict[str, Any]) -> str | None:
        label = str(option.get("label") or "").strip()
        emoji = self._component_emoji(option.get("emoji"))
        value = f"{emoji} {label}".strip() if emoji else label
        return value[:100] or None

    async def handle_aaa3a_panel_open(
        self,
        interaction: discord.Interaction,
        component_type: str,
        config_identifier: str,
    ) -> None:
        """Open a TicketHub ticket from an imported AAA3A panel component."""
        if not interaction.guild or interaction.message is None:
            await interaction.response.send_message(
                "I could not identify this imported ticket panel.",
                ephemeral=True,
            )
            return
        channel_id = getattr(interaction.message.channel, "id", None)
        if channel_id is None:
            await interaction.response.send_message(
                "I could not identify this imported ticket panel.",
                ephemeral=True,
            )
            return
        panels = await self.config.guild(interaction.guild).aaa3a_panels()
        key = f"{channel_id}-{interaction.message.id}"
        record = self._sanitize_aaa3a_panel_record(
            panels.get(key),
            message_key=key,
        )
        if record is None:
            for raw_record in panels.values():
                candidate = self._sanitize_aaa3a_panel_record(raw_record)
                if (
                    candidate is not None
                    and int(candidate.get("message_id") or 0) == interaction.message.id
                ):
                    record = candidate
                    break
        if record is None:
            await interaction.response.send_message(
                "This imported AAA3A ticket panel is not tracked by TicketHub.",
                ephemeral=True,
            )
            return
        options = record.get(component_type) or {}
        option = options.get(str(config_identifier))
        if option is None:
            await interaction.response.send_message(
                "That imported AAA3A ticket option is not tracked by TicketHub.",
                ephemeral=True,
            )
            return
        await self.handle_panel_open(
            interaction,
            str(option.get("profile") or "main"),
            panel_label=self._aaa3a_panel_label(option),
        )

    @staticmethod
    def _ticket_mode(profile: ProfileRecord) -> str:
        mode = str(profile.get("ticket_mode") or "channel").lower()
        return "thread" if mode == "thread" else "channel"

    async def _get_profiles(self, guild: discord.Guild) -> dict[str, ProfileRecord]:
        raw_profiles = await self.config.guild(guild).profiles()
        if not raw_profiles:
            raw_profiles = {"main": self._default_profile()}
            await self.config.guild(guild).profiles.set(raw_profiles)
        return {
            self._clean_name(name): self._merge_profile(profile)
            for name, profile in raw_profiles.items()
        }

    async def _get_profile(
        self,
        guild: discord.Guild,
        profile_name: str = "main",
    ) -> ProfileRecord:
        profiles = await self._get_profiles(guild)
        key = self._clean_name(profile_name)
        if key not in profiles:
            raise commands.BadArgument(
                f"No TicketHub profile named `{key}` exists.")
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

    async def _ensure_profile(
        self,
        guild: discord.Guild,
        profile_name: str = "main",
    ) -> ProfileRecord:
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
    ) -> discord.TextChannel | None:
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
    ) -> discord.TextChannel | None:
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
    ) -> discord.CategoryChannel | None:
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

    def _is_support_member(
        self,
        member: discord.Member,
        profile: ProfileRecord,
    ) -> bool:
        if self._has_admin_permissions(member):
            return True
        return self._member_has_any_role(member, profile.get("support_role_ids") or [])

    def _can_speak_in_ticket(
        self,
        member: discord.Member,
        profile: ProfileRecord,
    ) -> bool:
        return self._is_support_member(member, profile) or self._member_has_any_role(
            member,
            profile.get("speak_role_ids") or [],
        )

    @staticmethod
    def _has_admin_permissions(member: discord.Member) -> bool:
        permissions = member.guild_permissions
        return permissions.administrator or permissions.manage_guild

    def _can_create_ticket(
        self,
        member: discord.Member,
        profile: ProfileRecord,
    ) -> tuple[bool, str]:
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
                "Set one with `[p]ticketset threadparent <profile> #channel`.",
            )
        me = guild.me
        if me is None:
            raise commands.CommandError(
                "I could not inspect my server permissions.")

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
                f"I need {', '.join(missing)} in {parent.mention} to create thread tickets.",
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
                "to use thread tickets.",
            )

    async def _validate_ticket_open_request(
        self,
        guild: discord.Guild,
        owner: discord.Member,
        profile_name: str,
    ) -> tuple[str, ProfileRecord]:
        if not await self.config.guild(guild).enabled():
            raise commands.CommandError("TicketHub is not enabled yet.")

        profile_name = self._clean_name(profile_name)
        profile = await self._get_profile(guild, profile_name)
        if not profile.get("enabled"):
            raise commands.CommandError(
                f"TicketHub profile `{profile_name}` is disabled.",
            )

        allowed, denial = self._can_create_ticket(owner, profile)
        if not allowed:
            raise commands.CommandError(denial)

        max_open = int(profile.get("max_open_tickets_by_member") or 0)
        if max_open > 0:
            open_count = await self._user_open_ticket_count(
                guild,
                owner.id,
                profile_name,
            )
            if open_count >= max_open:
                raise commands.CommandError(
                    f"You already have {open_count} open ticket(s) for `{profile_name}`.",
                )

        me = guild.me
        if me is None:
            raise commands.CommandError(
                "I could not inspect my server permissions.")
        if self._ticket_mode(profile) == "thread":
            self._validate_thread_parent_permissions(guild, owner, profile)
        elif not me.guild_permissions.manage_channels:
            raise commands.CommandError(
                "I need `Manage Channels` to create ticket channels.",
            )

        return profile_name, profile

    async def _user_open_ticket_count(
        self,
        guild: discord.Guild,
        owner_id: int,
        profile_name: str | None = None,
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
        answers: Sequence[dict[str, str]] | None,
    ) -> list[dict[str, str]]:
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
        template: str | None,
        *,
        ticket_id: int,
        global_ticket_id: int,
        owner: discord.Member,
        guild: discord.Guild,
        profile: str,
    ) -> str:
        template = template or "ticket-{id}-{owner_name}"
        values = {
            "id": str(ticket_id),
            "ticket_id": str(ticket_id),
            "profile_id": str(ticket_id),
            "global_id": str(global_ticket_id),
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

    @classmethod
    def _validate_channel_name_template(cls, value: str) -> str:
        template = value.strip()
        if template.lower() in {"default", "reset"}:
            return "ticket-{id}-{owner_name}"
        if not 1 <= len(template) <= 200:
            raise commands.BadArgument(
                "Channel name templates must be between 1 and 200 characters.",
            )
        placeholders = set(re.findall(r"\{([^{}]+)\}", template))
        unknown = placeholders - cls.CHANNEL_TEMPLATE_FIELDS
        if unknown:
            supported = ", ".join(
                f"`{{{name}}}`" for name in sorted(cls.CHANNEL_TEMPLATE_FIELDS)
            )
            raise commands.BadArgument(
                f"Unknown placeholder(s): {', '.join(sorted(unknown))}. "
                f"Supported placeholders: {supported}.",
            )
        without_placeholders = re.sub(r"\{[^{}]+\}", "", template)
        if "{" in without_placeholders or "}" in without_placeholders:
            raise commands.BadArgument(
                "Channel name template braces are not balanced.")
        return template

    @staticmethod
    def _next_profile_ticket_number(
        profile: ProfileRecord,
        tickets: dict[str, TicketRecord],
        profile_name: str,
    ) -> int:
        try:
            configured_next = max(
                1, int(profile.get("next_profile_ticket_id") or 1))
        except (TypeError, ValueError):
            configured_next = 1
        existing_numbers = []
        for record in tickets.values():
            if str(record.get("profile") or "main") != profile_name:
                continue
            try:
                existing_numbers.append(
                    int(record.get("profile_ticket_id")
                        or record.get("id") or 0),
                )
            except (TypeError, ValueError):
                continue
        return max(configured_next, max(existing_numbers, default=0) + 1)

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
        profile_name = str(record.get("profile") or "main")
        profile_label = profile_name.replace(
            "-", " ").replace("_", " ").title()
        reason = str(record.get("reason") or "No reason provided.")
        embed = discord.Embed(
            title=f"🎫 Ticket #{record.get('id')}  •  {profile_label}",
            description=f"### Request\n{self._quote_text(reason, 1200)}",
            color=color,
            timestamp=self._now(),
        )
        owner = (
            guild.get_member(int(record["owner_id"]))
            if record.get("owner_id")
            else None
        )
        self._set_member_identity(
            embed,
            owner,
            fallback_name=f"Ticket owner ({record.get('owner_id') or 'unknown'})",
        )
        embed.add_field(
            name="Status", value=self._status_display(record), inline=True)
        embed.add_field(
            name="Claimed By",
            value=(
                self._user_ref(record.get("claimed_by"))
                if record.get("claimed_by")
                else "Waiting for staff"
            ),
            inline=True,
        )
        embed.add_field(
            name="Access",
            value="🔒 Locked" if record.get("locked") else "🔓 Unlocked",
            inline=True,
        )
        embed.add_field(
            name="Owner",
            value=self._user_ref(record.get("owner_id")),
            inline=True,
        )
        profile_value = f"`{profile_name}`"
        if record.get("profile_ticket_id") is not None:
            profile_value += f" • **#{record['profile_ticket_id']}**"
        embed.add_field(name="Profile", value=profile_value, inline=True)
        embed.add_field(
            name="Created",
            value=(
                f"{self._format_ts(record.get('created_at'), 'F')}\n"
                f"{self._format_ts(record.get('created_at'), 'R')}"
            ),
            inline=True,
        )
        if record.get("closed_at"):
            embed.add_field(
                name="Closed",
                value=(
                    f"{self._format_ts(record.get('closed_at'), 'F')}\n"
                    f"{self._format_ts(record.get('closed_at'), 'R')}"
                ),
                inline=True,
            )
            if record.get("close_reason"):
                embed.add_field(
                    name="Close Reason",
                    value=self._quote_text(record["close_reason"], 600),
                    inline=False,
                )
        if record.get("panel_label"):
            embed.add_field(
                name="Panel Option",
                value=self._quote_text(record["panel_label"], 300),
                inline=False,
            )
        for answer in self._clean_form_answers(record.get("form_answers")):
            if (
                answer["label"].strip().lower() == "reason"
                and answer["value"].strip() == reason.strip()
            ):
                continue
            embed.add_field(
                name=self._truncate_field(answer["label"], 256),
                value=self._quote_text(answer["value"], 600),
                inline=False,
            )
        footer_icon = str(guild.icon.url) if guild.icon else None
        embed.set_footer(
            text=f"Ticket ID: {record.get('id')}  •  {guild.name}  •  TicketHub",
            icon_url=footer_icon,
        )
        return embed

    def _ticket_control_view(
        self,
        profile: ProfileRecord,
        record: TicketRecord,
    ) -> TicketControlView:
        claimed = bool(record.get("claimed_by"))
        locked = bool(record.get("locked"))
        closed = record.get("status") == "closed"
        view = TicketControlView(
            self,
            claimed=claimed,
            locked=locked,
            closed=closed,
        )
        defaults = self._default_profile()["control_emojis"]
        configured = profile.get("control_emojis") or {}
        actions = {
            "taakoscogs:tickethub:claim": "unclaim" if claimed else "claim",
            "taakoscogs:tickethub:lock": "unlock" if locked else "lock",
            "taakoscogs:tickethub:close": "reopen" if closed else "close",
            "taakoscogs:tickethub:members": "members",
            "taakoscogs:tickethub:transcript": "transcript",
            "taakoscogs:tickethub:delete": "delete",
        }
        for item in view.children:
            action = actions.get(getattr(item, "custom_id", None))
            if action is None or not isinstance(item, discord.ui.Button):
                continue
            emoji = configured.get(action) or defaults[action]
            try:
                item.emoji = emoji
            except (TypeError, ValueError):
                item.emoji = defaults[action]
        return view

    def _panel_embed(
        self,
        guild: discord.Guild,
        profile_name: str,
        profile: ProfileRecord,
    ) -> discord.Embed:
        embed = discord.Embed(
            title=str(profile.get("panel_title") or "Need Help?"),
            description=str(
                profile.get("panel_message") or "Open a ticket for support.",
            ),
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
        color: int | None = None,
        record: TicketRecord | None = None,
        ticket_channel: TicketLocation | None = None,
        include_jump: bool = True,
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
            title=f"{self._event_icon(title)} {title}",
            description=description,
            color=color or self.DEFAULT_COLOR,
            timestamp=self._now(),
        )
        ticket_url = None
        if record is not None:
            owner = (
                guild.get_member(int(record["owner_id"]))
                if record.get("owner_id")
                else None
            )
            self._set_member_identity(
                embed,
                owner,
                fallback_name=f"Ticket owner ({record.get('owner_id') or 'unknown'})",
            )
            profile_name = str(record.get("profile") or "main")
            embed.add_field(
                name="Ticket",
                value=f"**#{record.get('id')}**  •  `{profile_name}`",
                inline=True,
            )
            embed.add_field(
                name="Owner",
                value=self._user_ref(record.get("owner_id")),
                inline=True,
            )
            embed.add_field(
                name="Status",
                value=self._status_display(record),
                inline=True,
            )
            embed.add_field(
                name="Claimed By",
                value=(
                    self._user_ref(record.get("claimed_by"))
                    if record.get("claimed_by")
                    else "Not claimed"
                ),
                inline=True,
            )
            embed.add_field(
                name="Opened",
                value=self._format_ts(record.get("created_at"), "R"),
                inline=True,
            )
            location = ticket_channel
            if location is None and include_jump and record.get("channel_id"):
                cached = guild.get_channel(int(record["channel_id"]))
                if isinstance(cached, (discord.TextChannel, discord.Thread)):
                    location = cached
            embed.add_field(
                name="Location",
                value=location.mention if location is not None else "Channel deleted",
                inline=True,
            )
            if include_jump:
                ticket_url = self._ticket_url(
                    guild.id, record.get("channel_id"))
        footer_icon = str(guild.icon.url) if guild.icon else None
        embed.set_footer(
            text=f"{guild.name}  •  TicketHub Logs", icon_url=footer_icon)
        try:
            await channel.send(
                embed=embed,
                view=self._jump_view(ticket_url),
                allowed_mentions=discord.AllowedMentions.none(),
            )
        except discord.HTTPException:
            log.exception("Failed to send TicketHub log in guild %s", guild.id)

    async def _fetch_ticket_channel(
        self,
        guild: discord.Guild,
        record: TicketRecord,
    ) -> TicketLocation | None:
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
        return (
            channel
            if isinstance(channel, (discord.TextChannel, discord.Thread))
            else None
        )

    async def _find_ticket_by_channel(
        self,
        guild: discord.Guild,
        channel_id: int,
    ) -> tuple[str, TicketRecord]:
        tickets = await self.config.guild(guild).tickets()
        for key, record in tickets.items():
            if int(record.get("channel_id") or 0) == int(channel_id):
                return key, record
        raise commands.BadArgument(
            "This channel or thread is not a tracked TicketHub ticket.",
        )

    async def _find_ticket_by_control_message(
        self,
        guild: discord.Guild,
        message_id: int,
    ) -> tuple[str, TicketRecord]:
        tickets = await self.config.guild(guild).tickets()
        for key, record in tickets.items():
            if int(record.get("message_id") or 0) == int(message_id):
                return key, record
        raise commands.BadArgument(
            "This message is not a tracked TicketHub ticket.")

    async def _find_panel_profile(
        self,
        guild: discord.Guild,
        message_id: int,
    ) -> tuple[str, ProfileRecord]:
        profiles = await self._get_profiles(guild)
        for name, profile in profiles.items():
            if int(profile.get("panel_message_id") or 0) == int(message_id):
                return name, profile
        raise commands.BadArgument("This panel is not tracked by TicketHub.")

    async def handle_panel_open(
        self,
        interaction: discord.Interaction,
        profile_name: str | None = None,
        *,
        panel_label: str | None = None,
    ) -> None:
        """Open a ticket from a persistent panel button."""
        if not interaction.guild or not isinstance(interaction.user, discord.Member):
            await interaction.response.send_message(
                "This button only works in a server.",
                ephemeral=True,
            )
            return
        if interaction.message is None:
            await interaction.response.send_message(
                "I could not identify this panel.",
                ephemeral=True,
            )
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
                            panel_label=panel_label,
                        ),
                    )
                else:
                    questionnaire = TicketQuestionnaireView(
                        self,
                        interaction.guild,
                        interaction.user,
                        profile_name,
                        modal_fields,
                        panel_label=panel_label,
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
                panel_label=panel_label,
            )
        except commands.CommandError as error:
            await interaction.followup.send(str(error), ephemeral=True)
            return
        await interaction.followup.send(
            f"Ticket #{record['id']} opened: {channel.mention}",
            ephemeral=True,
        )

    async def handle_ticket_button(
        self,
        interaction: discord.Interaction,
        action: str,
    ) -> None:
        """Handle ticket control buttons."""
        if not interaction.guild or not isinstance(interaction.user, discord.Member):
            await interaction.response.send_message(
                "This button only works in a server.",
                ephemeral=True,
            )
            return
        if interaction.message is None:
            await interaction.response.send_message(
                "I could not identify this ticket.",
                ephemeral=True,
            )
            return
        if action == "close_toggle":
            try:
                _key, record = await self._find_ticket_by_control_message(
                    interaction.guild,
                    interaction.message.id,
                )
                if record.get("status") == "closed":
                    await self._validate_reopen_request(
                        interaction.guild,
                        record,
                        interaction.user,
                    )
                else:
                    await self._validate_close_request(
                        interaction.guild,
                        record,
                        interaction.user,
                    )
            except commands.CommandError as error:
                await interaction.response.send_message(str(error), ephemeral=True)
                return
            if record.get("status") == "closed":
                await interaction.response.send_modal(
                    TicketReopenReasonModal(
                        self,
                        interaction.guild.id,
                        int(record["id"]),
                        interaction.user.id,
                    ),
                )
            else:
                await interaction.response.send_modal(
                    TicketCloseReasonModal(
                        self,
                        interaction.guild.id,
                        int(record["id"]),
                        interaction.user.id,
                    ),
                )
            return
        if action == "members":
            try:
                _key, record = await self._find_ticket_by_control_message(
                    interaction.guild,
                    interaction.message.id,
                )
                profile = await self._get_profile(
                    interaction.guild,
                    str(record.get("profile") or "main"),
                )
                is_owner = interaction.user.id == int(
                    record.get("owner_id") or 0)
                if not self._is_support_member(interaction.user, profile) and not (
                    is_owner
                    and (
                        profile.get("owner_can_add_members")
                        or profile.get("owner_can_remove_members")
                    )
                ):
                    raise commands.CommandError(
                        "You do not have permission to manage this ticket's members.",
                    )
                if record.get("status") != "open":
                    raise commands.CommandError(
                        "Members can only be changed on open tickets.",
                    )
            except commands.CommandError as error:
                await interaction.response.send_message(str(error), ephemeral=True)
                return
            participant_mentions = [
                self._user_ref(member_id)
                for member_id in record.get("participants", [])
                if str(member_id) != str(record.get("owner_id"))
            ]
            await interaction.response.send_message(
                "Manage ticket members below.\nCurrent added members: "
                + (", ".join(participant_mentions) or "None"),
                view=TicketMembersView(self, int(record["id"])),
                ephemeral=True,
            )
            return
        await interaction.response.defer(ephemeral=True, thinking=True)
        try:
            _key, record = await self._find_ticket_by_control_message(
                interaction.guild,
                interaction.message.id,
            )
            profile = await self._get_profile(
                interaction.guild,
                str(record.get("profile") or "main"),
            )
            if action == "claim_toggle":
                if record.get("claimed_by"):
                    await self._unclaim_ticket(
                        interaction.guild,
                        record,
                        interaction.user,
                    )
                    await interaction.followup.send("Ticket unclaimed.", ephemeral=True)
                else:
                    await self._claim_ticket(
                        interaction.guild,
                        record,
                        interaction.user,
                    )
                    await interaction.followup.send("Ticket claimed.", ephemeral=True)
            elif action == "lock_toggle":
                if record.get("locked"):
                    await self._unlock_ticket(
                        interaction.guild,
                        record,
                        interaction.user,
                    )
                    await interaction.followup.send("Ticket unlocked.", ephemeral=True)
                else:
                    await self._lock_ticket(
                        interaction.guild,
                        record,
                        interaction.user,
                    )
                    await interaction.followup.send("Ticket locked.", ephemeral=True)
            elif action == "transcript":
                if not self._is_support_member(
                    interaction.user,
                    profile,
                ) and interaction.user.id != int(record.get("owner_id") or 0):
                    await interaction.followup.send(
                        "Only the ticket owner or support staff can generate transcripts.",
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
            elif action == "delete":
                await self._delete_ticket_channel(
                    interaction.guild,
                    record,
                    interaction.user,
                    reason="Deleted from ticket controls.",
                )
                await interaction.followup.send("Ticket deleted.", ephemeral=True)
        except commands.CommandError as error:
            await interaction.followup.send(str(error), ephemeral=True)

    async def _create_ticket(
        self,
        guild: discord.Guild,
        owner: discord.Member,
        profile_name: str,
        *,
        reason: str | None = None,
        form_answers: Sequence[dict[str, str]] | None = None,
        panel_label: str | None = None,
    ) -> tuple[TicketRecord, TicketLocation]:
        profile_name, profile = await self._validate_ticket_open_request(
            guild,
            owner,
            profile_name,
        )
        clean_form_answers = self._clean_form_answers(form_answers)
        clean_panel_label = self._clean_modal_text(panel_label, 100) or None

        async with self._guild_lock(guild.id):
            ticket_id = int(await self.config.guild(guild).next_ticket_id())
            tickets = await self.config.guild(guild).tickets()
            profile_ticket_id = self._next_profile_ticket_number(
                profile,
                tickets,
                profile_name,
            )
            category = self._profile_category(
                guild, profile, "ticket_category_id")
            channel_name = self._format_template(
                profile.get("channel_name"),
                ticket_id=profile_ticket_id,
                global_ticket_id=ticket_id,
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
                overwrites = self._ticket_overwrites(
                    guild,
                    owner,
                    profile,
                    closed=False,
                )
                try:
                    channel = await guild.create_text_channel(
                        channel_name,
                        category=category,
                        overwrites=overwrites,
                        reason=f"TicketHub ticket #{ticket_id} opened by {owner}",
                    )
                except discord.HTTPException as exc:
                    raise commands.CommandError(
                        "I could not create the ticket channel.",
                    ) from exc

            record: TicketRecord = {
                "id": ticket_id,
                "profile_ticket_id": profile_ticket_id,
                "profile": profile_name,
                "owner_id": owner.id,
                "channel_id": channel.id,
                "location_type": mode,
                "thread_parent_channel_id": (
                    channel.parent_id if isinstance(
                        channel, discord.Thread) else None
                ),
                "message_id": None,
                "status": "open",
                "claimed_by": None,
                "locked": False,
                "locked_by": None,
                "locked_at": None,
                "unlocked_by": None,
                "unlocked_at": None,
                "reason": (reason or "No reason provided.")[:1000],
                "form_answers": clean_form_answers,
                "panel_label": clean_panel_label,
                "created_at": self._now_ts(),
                "closed_at": None,
                "closed_by": None,
                "close_reason": None,
                "reopened_at": None,
                "reopened_by": None,
                "reopen_reason": None,
                "pending_close": None,
                "participants": [owner.id],
                "events": [
                    {
                        "type": "created",
                        "actor_id": owner.id,
                        "at": self._now_ts(),
                        "reason": reason,
                    },
                ],
                "transcript_count": 0,
            }

            welcome = self._render_ticket_text(
                profile.get("welcome_message"),
                owner,
                guild,
                profile_ticket_id,
                global_ticket_id=ticket_id,
            )
            custom = self._render_ticket_text(
                profile.get("custom_message"),
                owner,
                guild,
                profile_ticket_id,
                global_ticket_id=ticket_id,
            )
            ping_text = self._role_mentions(
                guild, profile.get("ping_role_ids") or [])
            mention_parts = [ping_text] if ping_text else []
            if owner.mention not in welcome:
                mention_parts.insert(0, owner.mention)
            mention_line = " ".join(mention_parts)
            welcome_line = f"### 👋 {welcome}" if welcome else ""
            intro = "\n".join(
                part for part in (mention_line, welcome_line, custom) if part
            )
            embed = self._ticket_embed(guild, record, profile)
            try:
                message = await channel.send(
                    intro[:1900] if intro else owner.mention,
                    embed=embed,
                    view=self._ticket_control_view(profile, record),
                    allowed_mentions=discord.AllowedMentions(
                        users=True,
                        roles=True,
                        everyone=False,
                    ),
                )
            except discord.HTTPException as exc:
                with contextlib.suppress(discord.HTTPException):
                    await channel.delete(
                        reason="TicketHub failed to send ticket controls.",
                    )
                raise commands.CommandError(
                    "I created the ticket but could not send the ticket panel.",
                ) from exc
            record["message_id"] = message.id
            async with self.config.guild(guild).tickets() as tickets:
                tickets[str(ticket_id)] = record
            profile["next_profile_ticket_id"] = profile_ticket_id + 1
            await self._set_profile(guild, profile_name, profile)
            await self.config.guild(guild).next_ticket_id.set(ticket_id + 1)

        ticket_role = guild.get_role(int(profile.get("ticket_role_id") or 0))
        if ticket_role is not None and ticket_role not in owner.roles:
            try:
                await owner.add_roles(
                    ticket_role,
                    reason=f"TicketHub ticket #{ticket_id} opened",
                )
            except discord.HTTPException:
                log.exception(
                    "Failed to add TicketHub ticket role in guild %s.",
                    guild.id,
                )
        await self._send_log(
            guild,
            profile,
            "Ticket Opened",
            f"Ticket #{ticket_id} opened by {owner.mention}: {channel.mention}",
            color=self.OPEN_COLOR,
            record=record,
            ticket_channel=channel,
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
                "Set one with `[p]ticketset threadparent <profile> #channel`.",
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
            raise commands.CommandError(
                "I could not create the ticket thread.",
            ) from exc

        try:
            await thread.add_user(owner)
        except discord.HTTPException as exc:
            with contextlib.suppress(discord.HTTPException):
                await thread.delete(reason="TicketHub failed to add ticket owner.")
            raise commands.CommandError(
                "I created the ticket thread but could not add the ticket owner.",
            ) from exc

        await self._add_cached_support_members_to_thread(guild, thread, profile, owner)
        return thread

    async def _add_cached_support_members_to_thread(
        self,
        guild: discord.Guild,
        thread: discord.Thread,
        profile: ProfileRecord,
        owner: discord.Member | None,
    ) -> None:
        members: dict[int, discord.Member] = {}
        owner_id = owner.id if owner is not None else None
        role_ids = list(profile.get("support_role_ids") or []) + list(
            profile.get("speak_role_ids") or [],
        )
        for role_id in role_ids:
            role = guild.get_role(int(role_id))
            if role is None:
                continue
            for member in role.members:
                if member.id != owner_id and not member.bot:
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

    async def _restore_thread_claim_access(
        self,
        guild: discord.Guild,
        thread: discord.Thread,
        profile: ProfileRecord,
        owner: discord.Member | None,
        participant_ids: Sequence[int],
    ) -> None:
        if owner is not None:
            try:
                await thread.add_user(owner)
            except discord.HTTPException:
                log.debug(
                    "Failed to restore owner %s to TicketHub thread %s",
                    owner.id,
                    thread.id,
                )
        await self._add_cached_support_members_to_thread(
            guild,
            thread,
            profile,
            owner,
        )
        for participant_id in participant_ids:
            try:
                participant = guild.get_member(int(participant_id))
            except (TypeError, ValueError):
                continue
            if participant is None or participant.bot:
                continue
            try:
                await thread.add_user(participant)
            except discord.HTTPException:
                log.debug(
                    "Failed to restore participant %s to TicketHub thread %s",
                    participant.id,
                    thread.id,
                )

    async def _set_ticket_claim_access(
        self,
        guild: discord.Guild,
        record: TicketRecord,
        profile: ProfileRecord,
        claimed_by: discord.Member | None,
        *,
        owner_locked: bool | None = None,
    ) -> None:
        channel = await self._fetch_ticket_channel(guild, record)
        if channel is None:
            raise commands.CommandError(
                "I could not find that ticket channel or thread.",
            )
        owner = (
            guild.get_member(int(record["owner_id"]))
            if record.get("owner_id")
            else None
        )
        participant_ids = record.get("participants") or []
        if owner_locked is None:
            owner_locked = bool(record.get("locked"))
        if owner_locked != bool(record.get("locked")):
            action = "locked" if owner_locked else "unlocked"
        else:
            action = "claimed" if claimed_by is not None else "unclaimed"
        if isinstance(channel, discord.TextChannel):
            overwrites = self._ticket_overwrites(
                guild,
                owner,
                profile,
                closed=False,
                claimed_by=claimed_by,
                participant_ids=participant_ids,
                owner_locked=owner_locked,
            )
            try:
                await channel.edit(
                    overwrites=overwrites,
                    reason=f"TicketHub ticket #{record['id']} {action}",
                )
            except discord.HTTPException as exc:
                raise commands.CommandError(
                    "I could not update the ticket's send permissions.",
                ) from exc
            return

        if claimed_by is None and not owner_locked:
            await self._restore_thread_claim_access(
                guild,
                channel,
                profile,
                owner,
                participant_ids,
            )
            return

        allowed_ids = set()
        if claimed_by is not None:
            allowed_ids.add(claimed_by.id)
        if owner is not None and not owner_locked:
            allowed_ids.add(owner.id)
        if guild.me is not None:
            allowed_ids.add(guild.me.id)
        administrators = [
            member
            for member in guild.members
            if not member.bot and self._has_admin_permissions(member)
        ]
        allowed_ids.update(member.id for member in administrators)
        support_members = []
        if claimed_by is None:
            support_members = [
                member
                for member in guild.members
                if not member.bot and self._can_speak_in_ticket(member, profile)
            ]
            allowed_ids.update(member.id for member in support_members)
        required_members = [claimed_by, *administrators, *support_members]
        if not owner_locked:
            required_members.insert(0, owner)
        for member in required_members:
            if member is None:
                continue
            try:
                await channel.add_user(member)
            except discord.HTTPException as exc:
                raise commands.CommandError(
                    "I could not add all required members before locking the ticket thread.",
                ) from exc
        try:
            thread_members = await channel.fetch_members()
        except discord.HTTPException:
            thread_members = channel.members
        removed_members: list[discord.abc.Snowflake] = []
        failed_member_ids: list[int] = []
        for thread_member in thread_members:
            member_id = int(thread_member.id)
            member = guild.get_member(member_id)
            if member_id in allowed_ids:
                continue
            if member is not None and self._has_admin_permissions(member):
                continue
            target = member or thread_member
            try:
                await channel.remove_user(target)
                removed_members.append(target)
            except discord.HTTPException:
                failed_member_ids.append(member_id)
        if failed_member_ids:
            for removed_member in removed_members:
                with contextlib.suppress(discord.HTTPException):
                    await channel.add_user(removed_member)
            raise commands.CommandError(
                "I could not lock the ticket thread for every member.",
            )

    def _ticket_overwrites(
        self,
        guild: discord.Guild,
        owner: discord.Member | None,
        profile: ProfileRecord,
        *,
        closed: bool,
        claimed_by: discord.Member | None = None,
        participant_ids: Sequence[int] = (),
        owner_locked: bool = False,
    ) -> dict[discord.abc.Snowflake, discord.PermissionOverwrite]:
        claim_locked = claimed_by is not None and not closed
        overwrites: dict[discord.abc.Snowflake, discord.PermissionOverwrite] = {
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
            owner_can_send = not closed and not owner_locked
            overwrites[owner] = discord.PermissionOverwrite(
                view_channel=True,
                send_messages=owner_can_send,
                read_message_history=True,
                attach_files=owner_can_send,
                embed_links=owner_can_send,
            )
        role_ids = list(profile.get("support_role_ids") or []) + list(
            profile.get("speak_role_ids") or [],
        )
        for role_id in role_ids:
            role = guild.get_role(int(role_id))
            if role is not None:
                overwrites[role] = discord.PermissionOverwrite(
                    view_channel=True,
                    send_messages=not claim_locked,
                    read_message_history=True,
                    attach_files=not claim_locked,
                    embed_links=not claim_locked,
                )
        for role_id in profile.get("view_role_ids") or []:
            role = guild.get_role(int(role_id))
            if role is not None and role not in overwrites:
                overwrites[role] = discord.PermissionOverwrite(
                    view_channel=True,
                    send_messages=False,
                    read_message_history=True,
                )
        if claim_locked:
            for role in guild.roles:
                if role.permissions.administrator or role.permissions.manage_guild:
                    overwrites[role] = discord.PermissionOverwrite(
                        view_channel=True,
                        send_messages=True,
                        read_message_history=True,
                        attach_files=True,
                        embed_links=True,
                    )
        owner_id = owner.id if owner is not None else None
        claimed_by_id = claimed_by.id if claimed_by is not None else None
        for participant_id in participant_ids:
            try:
                participant = guild.get_member(int(participant_id))
            except (TypeError, ValueError):
                continue
            if participant is None or participant.id == owner_id:
                continue
            can_send = (
                not closed
                and not owner_locked
                and (
                    not claim_locked
                    or participant.id == claimed_by_id
                    or self._has_admin_permissions(participant)
                )
            )
            overwrites[participant] = discord.PermissionOverwrite(
                view_channel=True,
                send_messages=can_send,
                read_message_history=True,
                attach_files=can_send,
                embed_links=can_send,
            )
        if claimed_by is not None and claimed_by.id != owner_id and not closed:
            overwrites[claimed_by] = discord.PermissionOverwrite(
                view_channel=True,
                send_messages=True,
                read_message_history=True,
                attach_files=True,
                embed_links=True,
            )
        return overwrites

    @staticmethod
    def _render_ticket_text(
        template: str | None,
        owner: discord.Member,
        guild: discord.Guild,
        ticket_id: int,
        *,
        global_ticket_id: int | None = None,
    ) -> str:
        if not template:
            return ""
        values = {
            "id": str(ticket_id),
            "ticket_id": str(ticket_id),
            "profile_id": str(ticket_id),
            "global_id": str(
                global_ticket_id if global_ticket_id is not None else ticket_id,
            ),
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
        profile: ProfileRecord | None = None,
    ) -> None:
        profile = profile or await self._get_profile(
            guild,
            str(record.get("profile") or "main"),
        )
        channel = await self._fetch_ticket_channel(guild, record)
        if channel is None or not record.get("message_id"):
            return
        try:
            message = await channel.fetch_message(int(record["message_id"]))
            await message.edit(
                embed=self._ticket_embed(guild, record, profile),
                view=self._ticket_control_view(profile, record),
            )
        except discord.HTTPException:
            log.exception(
                "Failed to update TicketHub ticket message in guild %s",
                guild.id,
            )

    async def _refresh_ticket_control_messages(self) -> None:
        """Refresh existing open-ticket controls after loading a new cog version."""
        try:
            await self.bot.wait_until_red_ready()
            all_guilds = await self.config.all_guilds()
            for guild_id, guild_data in all_guilds.items():
                guild = self.bot.get_guild(int(guild_id))
                if guild is None:
                    continue
                for record in (guild_data.get("tickets") or {}).values():
                    if not record.get("message_id"):
                        continue
                    await self._update_ticket_message(guild, record)
        except asyncio.CancelledError:
            raise
        except RECOVERABLE_EXCEPTIONS:
            log.exception(
                "Failed to refresh existing TicketHub control messages.")

    async def _claim_ticket(
        self,
        guild: discord.Guild,
        record: TicketRecord,
        member: discord.Member,
    ) -> None:
        profile = await self._get_profile(guild, str(record.get("profile") or "main"))
        if not self._is_support_member(member, profile):
            raise commands.CommandError(
                "Only support staff can claim tickets.")
        if record.get("status") != "open":
            raise commands.CommandError("Only open tickets can be claimed.")
        if record.get("claimed_by"):
            raise commands.CommandError("This ticket is already claimed.")
        await self._set_ticket_claim_access(guild, record, profile, member)
        record["claimed_by"] = member.id
        record.setdefault("events", []).append(
            {"type": "claimed", "actor_id": member.id, "at": self._now_ts()},
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
            record=record,
        )

    async def _unclaim_ticket(
        self,
        guild: discord.Guild,
        record: TicketRecord,
        member: discord.Member,
    ) -> None:
        profile = await self._get_profile(guild, str(record.get("profile") or "main"))
        if not self._is_support_member(member, profile):
            raise commands.CommandError(
                "Only support staff can unclaim tickets.")
        if record.get("status") != "open":
            raise commands.CommandError("Only open tickets can be unclaimed.")
        if not record.get("claimed_by"):
            raise commands.CommandError("This ticket is not claimed.")
        await self._set_ticket_claim_access(guild, record, profile, None)
        record["claimed_by"] = None
        record.setdefault("events", []).append(
            {"type": "unclaimed", "actor_id": member.id, "at": self._now_ts()},
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
            record=record,
        )

    async def _lock_ticket(
        self,
        guild: discord.Guild,
        record: TicketRecord,
        member: discord.Member,
    ) -> None:
        profile = await self._get_profile(guild, str(record.get("profile") or "main"))
        if not self._is_support_member(member, profile):
            raise commands.CommandError("Only support staff can lock tickets.")
        if record.get("status") != "open":
            raise commands.CommandError("Only open tickets can be locked.")
        if record.get("locked"):
            raise commands.CommandError("This ticket is already locked.")
        claimed_by = (
            guild.get_member(int(record["claimed_by"]))
            if record.get("claimed_by")
            else None
        )
        await self._set_ticket_claim_access(
            guild,
            record,
            profile,
            claimed_by,
            owner_locked=True,
        )
        record["locked"] = True
        record["locked_by"] = member.id
        record["locked_at"] = self._now_ts()
        record.setdefault("events", []).append(
            {"type": "locked", "actor_id": member.id,
                "at": record["locked_at"]},
        )
        async with self.config.guild(guild).tickets() as tickets:
            tickets[str(record["id"])] = record
        await self._update_ticket_message(guild, record, profile)
        await self._send_log(
            guild,
            profile,
            "Ticket Locked",
            f"Ticket #{record['id']} locked by {member.mention}.",
            color=self.CLOSED_COLOR,
            record=record,
        )

    async def _unlock_ticket(
        self,
        guild: discord.Guild,
        record: TicketRecord,
        member: discord.Member,
    ) -> None:
        profile = await self._get_profile(guild, str(record.get("profile") or "main"))
        if not self._is_support_member(member, profile):
            raise commands.CommandError(
                "Only support staff can unlock tickets.")
        if record.get("status") != "open":
            raise commands.CommandError("Only open tickets can be unlocked.")
        if not record.get("locked"):
            raise commands.CommandError("This ticket is not locked.")
        claimed_by = (
            guild.get_member(int(record["claimed_by"]))
            if record.get("claimed_by")
            else None
        )
        await self._set_ticket_claim_access(
            guild,
            record,
            profile,
            claimed_by,
            owner_locked=False,
        )
        record["locked"] = False
        record["unlocked_by"] = member.id
        record["unlocked_at"] = self._now_ts()
        record.setdefault("events", []).append(
            {"type": "unlocked", "actor_id": member.id,
                "at": record["unlocked_at"]},
        )
        async with self.config.guild(guild).tickets() as tickets:
            tickets[str(record["id"])] = record
        await self._update_ticket_message(guild, record, profile)
        await self._send_log(
            guild,
            profile,
            "Ticket Unlocked",
            f"Ticket #{record['id']} unlocked by {member.mention}.",
            color=self.OPEN_COLOR,
            record=record,
        )

    def _can_manage_ticket_members(
        self,
        actor: discord.Member,
        record: TicketRecord,
        profile: ProfileRecord,
        action: str,
    ) -> bool:
        if self._is_support_member(actor, profile):
            return True
        if actor.id != int(record.get("owner_id") or 0):
            return False
        setting = (
            "owner_can_add_members" if action == "add" else "owner_can_remove_members"
        )
        return bool(profile.get(setting))

    async def _add_ticket_member(
        self,
        guild: discord.Guild,
        record: TicketRecord,
        actor: discord.Member,
        member: discord.Member,
    ) -> str:
        profile = await self._get_profile(guild, str(record.get("profile") or "main"))
        if not self._can_manage_ticket_members(actor, record, profile, "add"):
            raise commands.CommandError(
                "You are not allowed to add members to this ticket.",
            )
        if record.get("status") != "open":
            raise commands.CommandError(
                "Members can only be added to open tickets.")
        participant_ids = {
            int(member_id) for member_id in record.get("participants", [])
        }
        if member.id in participant_ids:
            raise commands.CommandError(
                "That member is already in this ticket.")
        if member.id == int(record.get("owner_id") or 0) or self._is_support_member(
            member,
            profile,
        ):
            raise commands.CommandError(
                "That member already has ticket access through ownership or a support role.",
            )
        channel = await self._fetch_ticket_channel(guild, record)
        if channel is None:
            raise commands.CommandError(
                "I could not find that ticket channel or thread.",
            )
        claim_locked = bool(record.get("claimed_by"))
        ticket_locked = bool(record.get("locked"))
        can_send_while_claimed = self._has_admin_permissions(
            member,
        ) or member.id == int(record.get("claimed_by") or 0)
        can_send = not ticket_locked and (
            not claim_locked or can_send_while_claimed)
        try:
            if isinstance(channel, discord.Thread):
                if can_send:
                    await channel.add_user(member)
            else:
                await channel.set_permissions(
                    member,
                    view_channel=True,
                    send_messages=can_send,
                    read_message_history=True,
                    attach_files=can_send,
                    embed_links=can_send,
                    reason=f"TicketHub member added by {actor}",
                )
        except discord.HTTPException as exc:
            raise commands.CommandError(
                "I could not add that member to the ticket.",
            ) from exc
        participant_ids.add(member.id)
        record["participants"] = sorted(participant_ids)
        record.setdefault("events", []).append(
            {
                "type": "member_added",
                "actor_id": actor.id,
                "target_id": member.id,
                "at": self._now_ts(),
            },
        )
        async with self.config.guild(guild).tickets() as tickets:
            tickets[str(record["id"])] = record
        await self._send_log(
            guild,
            profile,
            "Member Added",
            f"{member.mention} added to ticket #{record['id']} by {actor.mention}.",
            color=self.OPEN_COLOR,
            record=record,
        )
        if not can_send:
            return " They will be restored when the ticket is unlocked or unclaimed."
        return ""

    async def _remove_ticket_member(
        self,
        guild: discord.Guild,
        record: TicketRecord,
        actor: discord.Member,
        member: discord.Member,
    ) -> None:
        profile = await self._get_profile(guild, str(record.get("profile") or "main"))
        if not self._can_manage_ticket_members(actor, record, profile, "remove"):
            raise commands.CommandError(
                "You are not allowed to remove members from this ticket.",
            )
        participant_ids = {
            int(member_id) for member_id in record.get("participants", [])
        }
        if (
            member.id == int(record.get("owner_id") or 0)
            or member.id not in participant_ids
        ):
            raise commands.CommandError(
                "That member is not an added member of this ticket.",
            )
        channel = await self._fetch_ticket_channel(guild, record)
        if channel is None:
            raise commands.CommandError(
                "I could not find that ticket channel or thread.",
            )
        try:
            if isinstance(channel, discord.Thread):
                with contextlib.suppress(discord.NotFound):
                    await channel.remove_user(member)
            else:
                await channel.set_permissions(
                    member,
                    overwrite=None,
                    reason=f"TicketHub member removed by {actor}",
                )
        except discord.HTTPException as exc:
            raise commands.CommandError(
                "I could not remove that member from the ticket.",
            ) from exc
        participant_ids.discard(member.id)
        record["participants"] = sorted(participant_ids)
        record.setdefault("events", []).append(
            {
                "type": "member_removed",
                "actor_id": actor.id,
                "target_id": member.id,
                "at": self._now_ts(),
            },
        )
        async with self.config.guild(guild).tickets() as tickets:
            tickets[str(record["id"])] = record
        await self._send_log(
            guild,
            profile,
            "Member Removed",
            f"{member.mention} removed from ticket #{record['id']} by {actor.mention}.",
            color=self.DEFAULT_COLOR,
            record=record,
        )

    async def handle_ticket_member_selection(
        self,
        interaction: discord.Interaction,
        ticket_id: int,
        action: str,
        members: Sequence[discord.Member],
    ) -> None:
        if not interaction.guild or not isinstance(interaction.user, discord.Member):
            await interaction.response.send_message(
                "This control only works in a server.",
                ephemeral=True,
            )
            return
        await interaction.response.defer(ephemeral=True, thinking=True)
        results = []
        for member in members:
            if not isinstance(member, discord.Member):
                results.append(
                    f"{member}: that user is not a member of this server.")
                continue
            try:
                record = await self._get_ticket_record_by_id(
                    interaction.guild,
                    ticket_id,
                )
                if action == "add":
                    note = await self._add_ticket_member(
                        interaction.guild,
                        record,
                        interaction.user,
                        member,
                    )
                    results.append(f"Added {member.mention}.{note}")
                else:
                    await self._remove_ticket_member(
                        interaction.guild,
                        record,
                        interaction.user,
                        member,
                    )
                    results.append(f"Removed {member.mention}.")
            except commands.CommandError as error:
                results.append(f"{member.mention}: {error}")
        await interaction.followup.send("\n".join(results)[:1900], ephemeral=True)

    async def _get_ticket_record_by_id(
        self,
        guild: discord.Guild,
        ticket_id: int,
    ) -> TicketRecord:
        tickets = await self.config.guild(guild).tickets()
        record = tickets.get(str(ticket_id))
        if record is None:
            raise commands.BadArgument(
                f"No ticket with ID `{ticket_id}` was found.")
        return record

    async def _validate_close_request(
        self,
        guild: discord.Guild,
        record: TicketRecord,
        member: discord.Member,
    ) -> ProfileRecord:
        profile = await self._get_profile(guild, str(record.get("profile") or "main"))
        owner = (
            guild.get_member(int(record["owner_id"]))
            if record.get("owner_id")
            else None
        )
        owner_is_closing = owner is not None and owner.id == member.id
        if not self._is_support_member(member, profile) and not (
            owner_is_closing and profile.get("owner_can_close")
        ):
            raise commands.CommandError(
                "You do not have permission to close this ticket.",
            )
        if record.get("status") == "closed":
            raise commands.CommandError("This ticket is already closed.")
        return profile

    async def validate_close_request_ids(
        self,
        guild_id: int,
        ticket_id: int,
        requester_id: int,
    ) -> tuple[discord.Guild, TicketRecord, discord.Member]:
        guild = self.bot.get_guild(guild_id)
        if guild is None:
            raise commands.CommandError("I could not find that server.")
        requester = guild.get_member(requester_id)
        if requester is None:
            raise commands.CommandError(
                "I could not find the close requester in this server.",
            )
        record = await self._get_ticket_record_by_id(guild, ticket_id)
        await self._validate_close_request(guild, record, requester)
        return guild, record, requester

    def _close_confirmation_embed(
        self,
        reason: str,
        *,
        state: str = "pending",
        timeout_minutes: int | None = None,
    ) -> discord.Embed:
        reason = reason.strip()[:1000] or "No reason provided."
        if state == "closed":
            return discord.Embed(
                title="Ticket Closed",
                description=(
                    f"This ticket has been closed.\n\n**Reason:**\n{reason}"),
                color=self.CLOSED_COLOR,
                timestamp=self._now(),
            )
        timeout_minutes = timeout_minutes or self.DEFAULT_CLOSE_REQUEST_TIMEOUT_MINUTES
        embed = discord.Embed(
            title="Close Ticket",
            description=(
                "If you would like to close this ticket, press the **Close** button. "
                "If you would like to keep this ticket open for further assistance, "
                "press **Cancel**.\n\n"
                "**Note: If there is no response within "
                f"{self._format_minutes(timeout_minutes)}, the ticket will be closed "
                "automatically.**"
            ),
            color=self.CLOSED_COLOR,
            timestamp=self._now(),
        )
        embed.add_field(name="Reason", value=reason, inline=False)
        return embed

    def _cancel_close_confirmation_resources(
        self,
        guild_id: int,
        ticket_id: int,
    ) -> None:
        key = (guild_id, ticket_id)
        task = self._close_confirmation_tasks.pop(key, None)
        if task is not None and task is not asyncio.current_task():
            task.cancel()
        view = self._close_confirmation_views.pop(key, None)
        if view is not None:
            view.stop()

    def _schedule_close_confirmation(
        self,
        guild_id: int,
        ticket_id: int,
        expires_at: float,
    ) -> None:
        key = (guild_id, ticket_id)
        previous = self._close_confirmation_tasks.pop(key, None)
        if previous is not None:
            previous.cancel()
        task = asyncio.create_task(
            self._close_confirmation_timeout(guild_id, ticket_id, expires_at),
        )
        self._close_confirmation_tasks[key] = task

        def remove_finished(completed: asyncio.Task) -> None:
            if self._close_confirmation_tasks.get(key) is completed:
                self._close_confirmation_tasks.pop(key, None)

        task.add_done_callback(remove_finished)

    async def _fetch_close_confirmation_message(
        self,
        guild: discord.Guild,
        record: TicketRecord,
        pending: dict[str, Any],
    ) -> discord.Message | None:
        channel = await self._fetch_ticket_channel(guild, record)
        if channel is None or not pending.get("message_id"):
            return None
        try:
            return await channel.fetch_message(int(pending["message_id"]))
        except (discord.NotFound, discord.Forbidden, discord.HTTPException):
            return None

    async def _restore_close_confirmations(self) -> None:
        all_guilds = await self.config.all_guilds()
        for guild_id, guild_data in all_guilds.items():
            for record in (guild_data.get("tickets") or {}).values():
                pending = record.get("pending_close")
                if (
                    not isinstance(pending, dict)
                    or record.get("status") != "open"
                    or not pending.get("message_id")
                ):
                    continue
                try:
                    ticket_id = int(record["id"])
                    message_id = int(pending["message_id"])
                    expires_at = float(pending["expires_at"])
                except (KeyError, TypeError, ValueError):
                    continue
                view = TicketCloseConfirmationView(self, ticket_id)
                self.bot.add_view(view, message_id=message_id)
                self._close_confirmation_views[(
                    int(guild_id), ticket_id)] = view
                self._schedule_close_confirmation(
                    int(guild_id), ticket_id, expires_at)

    async def _start_close_confirmation(
        self,
        guild: discord.Guild,
        record: TicketRecord,
        requester: discord.Member,
        reason: str,
    ) -> discord.Message:
        async with self._guild_lock(guild.id):
            current_record = await self._get_ticket_record_by_id(
                guild,
                int(record["id"]),
            )
            return await self._start_close_confirmation_unlocked(
                guild,
                current_record,
                requester,
                reason,
            )

    async def _start_close_confirmation_unlocked(
        self,
        guild: discord.Guild,
        record: TicketRecord,
        requester: discord.Member,
        reason: str,
    ) -> discord.Message:
        profile = await self._validate_close_request(guild, record, requester)
        existing = record.get("pending_close")
        if (
            isinstance(existing, dict)
            and float(existing.get("expires_at") or 0) > self._now_ts()
        ):
            raise commands.CommandError(
                "This ticket already has an active close confirmation.",
            )
        channel = await self._fetch_ticket_channel(guild, record)
        if channel is None:
            raise commands.CommandError(
                "I could not find that ticket channel or thread.",
            )
        owner = (
            guild.get_member(int(record["owner_id"]))
            if record.get("owner_id")
            else None
        )
        target = owner or requester
        clean_reason = reason.strip()[:1000] or "No reason provided."
        timeout_minutes = self._close_request_timeout_minutes(profile)
        view = TicketCloseConfirmationView(self, int(record["id"]))
        try:
            message = await channel.send(
                f"{target.mention}, is there anything else we can help you with?",
                embed=self._close_confirmation_embed(
                    clean_reason,
                    timeout_minutes=timeout_minutes,
                ),
                view=view,
                allowed_mentions=discord.AllowedMentions(
                    users=True,
                    roles=False,
                    everyone=False,
                ),
            )
        except discord.HTTPException as exc:
            raise commands.CommandError(
                "I could not post the close confirmation in the ticket.",
            ) from exc
        expires_at = self._now_ts() + (timeout_minutes * 60)
        record["pending_close"] = {
            "requested_by": requester.id,
            "reason": clean_reason,
            "message_id": message.id,
            "expires_at": expires_at,
        }
        record.setdefault("events", []).append(
            {
                "type": "close_requested",
                "actor_id": requester.id,
                "at": self._now_ts(),
                "reason": clean_reason,
            },
        )
        async with self.config.guild(guild).tickets() as tickets:
            tickets[str(record["id"])] = record
        ticket_id = int(record["id"])
        self._close_confirmation_views[(guild.id, ticket_id)] = view
        self._schedule_close_confirmation(guild.id, ticket_id, expires_at)
        return message

    async def start_close_confirmation(
        self,
        interaction: discord.Interaction,
        guild_id: int,
        ticket_id: int,
        requester_id: int,
        reason: str,
    ) -> discord.Message:
        if interaction.guild_id != guild_id or interaction.user.id != requester_id:
            raise commands.CommandError(
                "This close request is not valid here.")
        guild, record, requester = await self.validate_close_request_ids(
            guild_id,
            ticket_id,
            requester_id,
        )
        return await self._start_close_confirmation(
            guild,
            record,
            requester,
            reason,
        )

    async def _clear_pending_close(
        self,
        guild: discord.Guild,
        record: TicketRecord,
    ) -> None:
        record["pending_close"] = None
        async with self.config.guild(guild).tickets() as tickets:
            tickets[str(record["id"])] = record
        self._cancel_close_confirmation_resources(guild.id, int(record["id"]))

    async def _resolve_close_confirmation(
        self,
        guild: discord.Guild,
        ticket_id: int,
        member: discord.Member,
        *,
        confirmed: bool,
        expected_expires_at: float | None = None,
    ) -> tuple[TicketRecord, str]:
        async with self._guild_lock(guild.id):
            record = await self._get_ticket_record_by_id(guild, ticket_id)
            pending = record.get("pending_close")
            if not isinstance(pending, dict):
                raise commands.CommandError(
                    "This close confirmation is no longer active.",
                )
            if (
                expected_expires_at is not None
                and float(pending.get("expires_at") or 0) != expected_expires_at
            ):
                raise commands.CommandError(
                    "This close confirmation has been replaced.",
                )
            reason = str(pending.get("reason") or "No reason provided.")
            if confirmed:
                await self._close_ticket(
                    guild,
                    record,
                    member,
                    reason=reason,
                    permission_checked=True,
                )
            else:
                record.setdefault("events", []).append(
                    {
                        "type": "close_cancelled",
                        "actor_id": member.id,
                        "at": self._now_ts(),
                    },
                )
                await self._clear_pending_close(guild, record)
            return record, reason

    async def handle_close_confirmation(
        self,
        interaction: discord.Interaction,
        ticket_id: int,
        *,
        confirmed: bool,
    ) -> None:
        if not interaction.guild or not isinstance(interaction.user, discord.Member):
            await interaction.response.send_message(
                "This confirmation only works in a server.",
                ephemeral=True,
            )
            return
        try:
            record = await self._get_ticket_record_by_id(interaction.guild, ticket_id)
            pending = record.get("pending_close")
            if not isinstance(pending, dict):
                raise commands.CommandError(
                    "This close confirmation is no longer active.",
                )
            profile = await self._get_profile(
                interaction.guild,
                str(record.get("profile") or "main"),
            )
            allowed_ids = {
                int(record.get("owner_id") or 0),
                int(pending.get("requested_by") or 0),
            }
            if interaction.user.id not in allowed_ids and not self._is_support_member(
                interaction.user,
                profile,
            ):
                raise commands.CommandError(
                    "Only the ticket opener, close requester, or support staff can use this.",
                )
        except commands.CommandError as error:
            await interaction.response.send_message(str(error), ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True, thinking=True)
        try:
            record, reason = await self._resolve_close_confirmation(
                interaction.guild,
                ticket_id,
                interaction.user,
                confirmed=confirmed,
            )
        except commands.CommandError as error:
            await interaction.followup.send(str(error), ephemeral=True)
            return
        if not confirmed:
            if interaction.message is not None:
                try:
                    await interaction.message.delete()
                except discord.HTTPException:
                    # At minimum remove the now-invalid controls if Discord does
                    # not allow the confirmation message to be deleted.
                    with contextlib.suppress(discord.HTTPException):
                        await interaction.message.edit(view=None)
            await interaction.followup.send(
                "Close cancelled. The ticket will remain open.",
                ephemeral=True,
            )
            return

        if interaction.message is not None:
            with contextlib.suppress(discord.HTTPException):
                await interaction.message.edit(
                    content=f"Ticket closed by {interaction.user}.",
                    embed=self._close_confirmation_embed(
                        reason, state="closed"),
                    view=None,
                )
        await interaction.followup.send("Ticket closed.", ephemeral=True)

    async def _close_confirmation_timeout(
        self,
        guild_id: int,
        ticket_id: int,
        expires_at: float,
    ) -> None:
        try:
            await self.bot.wait_until_red_ready()
            await asyncio.sleep(max(0.0, expires_at - self._now_ts()))
            guild = self.bot.get_guild(guild_id)
            if guild is None:
                return
            record = await self._get_ticket_record_by_id(guild, ticket_id)
            pending = record.get("pending_close")
            if (
                not isinstance(pending, dict)
                or record.get("status") != "open"
                or float(pending.get("expires_at") or 0) != expires_at
            ):
                return
            actor = guild.get_member(
                int(pending.get("requested_by") or 0)) or guild.me
            if actor is None:
                return
            message = await self._fetch_close_confirmation_message(
                guild,
                record,
                pending,
            )
            reason = str(pending.get("reason") or "No reason provided.")
            record, reason = await self._resolve_close_confirmation(
                guild,
                ticket_id,
                actor,
                confirmed=True,
                expected_expires_at=expires_at,
            )
            if message is not None:
                with contextlib.suppress(discord.HTTPException):
                    await message.edit(
                        content="Close confirmation timed out; ticket closed automatically.",
                        embed=self._close_confirmation_embed(
                            reason, state="closed"),
                        view=None,
                    )
        except asyncio.CancelledError:
            raise
        except (commands.CommandError, discord.HTTPException):
            log.exception(
                "Failed to auto-close TicketHub ticket %s in guild %s.",
                ticket_id,
                guild_id,
            )

    def _cancel_ticket_auto_delete(self, guild_id: int, ticket_id: int) -> None:
        key = (guild_id, ticket_id)
        task = self._auto_delete_tasks.pop(key, None)
        if task is not None and task is not asyncio.current_task():
            task.cancel()

    def _schedule_ticket_auto_delete(
        self,
        guild_id: int,
        record: TicketRecord,
        profile: ProfileRecord,
    ) -> None:
        ticket_id = int(record["id"])
        self._cancel_ticket_auto_delete(guild_id, ticket_id)
        configured_hours = profile.get("auto_delete_on_close_hours")
        if configured_hours is None or record.get("status") != "closed":
            return
        try:
            hours = max(0.0, float(configured_hours))
            closed_at = float(record["closed_at"])
        except (KeyError, TypeError, ValueError):
            return
        delete_at = self._now_ts() + 5 if hours == 0 else closed_at + (hours * 3600)
        key = (guild_id, ticket_id)
        task = asyncio.create_task(
            self._ticket_auto_delete_timeout(
                guild_id,
                ticket_id,
                closed_at,
                delete_at,
            ),
        )
        self._auto_delete_tasks[key] = task

        def remove_finished(completed: asyncio.Task) -> None:
            if self._auto_delete_tasks.get(key) is completed:
                self._auto_delete_tasks.pop(key, None)

        task.add_done_callback(remove_finished)

    async def _restore_auto_delete_tasks(self) -> None:
        all_guilds = await self.config.all_guilds()
        for guild_id, guild_data in all_guilds.items():
            profiles = guild_data.get("profiles") or {}
            for record in (guild_data.get("tickets") or {}).values():
                if record.get("status") != "closed":
                    continue
                profile_name = str(record.get("profile") or "main")
                profile = self._merge_profile(profiles.get(profile_name))
                self._schedule_ticket_auto_delete(
                    int(guild_id), record, profile)

    async def _ticket_auto_delete_timeout(
        self,
        guild_id: int,
        ticket_id: int,
        expected_closed_at: float,
        delete_at: float,
    ) -> None:
        try:
            await self.bot.wait_until_red_ready()
            await asyncio.sleep(max(0.0, delete_at - self._now_ts()))
            guild = self.bot.get_guild(guild_id)
            if guild is None:
                return
            record = await self._get_ticket_record_by_id(guild, ticket_id)
            if (
                record.get("status") != "closed"
                or float(record.get("closed_at") or 0) != expected_closed_at
            ):
                return
            await self._delete_ticket_channel(
                guild,
                record,
                None,
                reason=f"TicketHub ticket #{ticket_id} auto-delete timer expired",
                permission_checked=True,
            )
        except asyncio.CancelledError:
            raise
        except (commands.CommandError, discord.HTTPException):
            log.exception(
                "Failed to auto-delete TicketHub ticket %s in guild %s.",
                ticket_id,
                guild_id,
            )

    async def _close_ticket(
        self,
        guild: discord.Guild,
        record: TicketRecord,
        member: discord.Member,
        *,
        reason: str | None = None,
        permission_checked: bool = False,
    ) -> None:
        if permission_checked:
            profile = await self._get_profile(
                guild,
                str(record.get("profile") or "main"),
            )
            if record.get("status") == "closed":
                raise commands.CommandError("This ticket is already closed.")
        else:
            profile = await self._validate_close_request(guild, record, member)
        owner = (
            guild.get_member(int(record["owner_id"]))
            if record.get("owner_id")
            else None
        )

        record["status"] = "closed"
        record["pending_close"] = None
        self._cancel_close_confirmation_resources(guild.id, int(record["id"]))
        record["closed_at"] = self._now_ts()
        record["closed_by"] = member.id
        record["close_reason"] = (reason or "No reason provided.")[:1000]
        record.setdefault("events", []).append(
            {
                "type": "closed",
                "actor_id": member.id,
                "at": self._now_ts(),
                "reason": record["close_reason"],
            },
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
                        allowed_mentions=discord.AllowedMentions(
                            users=True,
                            roles=False,
                            everyone=False,
                        ),
                    )
                except discord.HTTPException:
                    log.exception(
                        "Failed to post closed ticket thread notice in guild %s",
                        guild.id,
                    )
            else:
                overwrites = self._ticket_overwrites(
                    guild, owner, profile, closed=True)
                closed_category = self._profile_category(
                    guild,
                    profile,
                    "closed_category_id",
                )
                try:
                    await channel.edit(
                        category=closed_category or channel.category,
                        overwrites=overwrites,
                        name=f"closed-{channel.name}"[:100]
                        if not channel.name.startswith("closed-")
                        else channel.name,
                        reason=f"TicketHub ticket #{record['id']} closed",
                    )
                except discord.HTTPException:
                    log.exception(
                        "Failed to edit closed ticket channel in guild %s",
                        guild.id,
                    )
                with contextlib.suppress(discord.HTTPException):
                    await channel.send(
                        f"Ticket closed by {member.mention}. Reason: {record['close_reason']}",
                        allowed_mentions=discord.AllowedMentions(
                            users=True,
                            roles=False,
                            everyone=False,
                        ),
                    )

        async with self.config.guild(guild).tickets() as tickets:
            tickets[str(record["id"])] = record
        await self._update_ticket_message(guild, record, profile)

        await self._send_log(
            guild,
            profile,
            "Ticket Closed",
            f"Ticket #{record['id']} closed by {member.mention}.\nReason: {record['close_reason']}",
            color=self.CLOSED_COLOR,
            record=record,
            ticket_channel=channel,
        )

        if isinstance(channel, discord.Thread):
            try:
                await channel.edit(
                    name=f"closed-{channel.name}"[:100]
                    if not channel.name.startswith("closed-")
                    else channel.name,
                    archived=True,
                    locked=True,
                    reason=f"TicketHub ticket #{record['id']} closed",
                )
            except discord.HTTPException:
                log.exception(
                    "Failed to archive closed ticket thread in guild %s",
                    guild.id,
                )
        self._schedule_ticket_auto_delete(guild.id, record, profile)

    async def _validate_reopen_request(
        self,
        guild: discord.Guild,
        record: TicketRecord,
        member: discord.Member,
    ) -> ProfileRecord:
        profile = await self._get_profile(guild, str(record.get("profile") or "main"))
        owner = (
            guild.get_member(int(record["owner_id"]))
            if record.get("owner_id")
            else None
        )
        owner_is_reopening = owner is not None and owner.id == member.id
        if not self._is_support_member(member, profile) and not (
            owner_is_reopening and profile.get("owner_can_reopen")
        ):
            raise commands.CommandError(
                "You do not have permission to reopen this ticket.",
            )
        if record.get("status") == "open":
            raise commands.CommandError("This ticket is already open.")
        return profile

    async def _reopen_ticket(
        self,
        guild: discord.Guild,
        record: TicketRecord,
        member: discord.Member,
        *,
        reason: str | None = None,
    ) -> None:
        profile = await self._validate_reopen_request(guild, record, member)
        owner = (
            guild.get_member(int(record["owner_id"]))
            if record.get("owner_id")
            else None
        )

        record["status"] = "open"
        record["closed_at"] = None
        record["closed_by"] = None
        record["close_reason"] = None
        record["reopened_at"] = self._now_ts()
        record["reopened_by"] = member.id
        record["reopen_reason"] = (reason or "No reason provided.")[:1000]
        self._cancel_ticket_auto_delete(guild.id, int(record["id"]))
        record.setdefault("events", []).append(
            {
                "type": "reopened",
                "actor_id": member.id,
                "at": record["reopened_at"],
                "reason": record["reopen_reason"],
            },
        )
        claimed_by = (
            guild.get_member(int(record["claimed_by"]))
            if record.get("claimed_by")
            else None
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
                    log.exception(
                        "Failed to reopen ticket thread in guild %s",
                        guild.id,
                    )
                if claimed_by is not None or record.get("locked"):
                    await self._set_ticket_claim_access(
                        guild,
                        record,
                        profile,
                        claimed_by,
                    )
            else:
                open_category = self._profile_category(
                    guild,
                    profile,
                    "ticket_category_id",
                )
                overwrites = self._ticket_overwrites(
                    guild,
                    owner,
                    profile,
                    closed=False,
                    claimed_by=claimed_by,
                    participant_ids=record.get("participants") or [],
                    owner_locked=bool(record.get("locked")),
                )
                try:
                    await channel.edit(
                        category=open_category or channel.category,
                        overwrites=overwrites,
                        name=channel.name.removeprefix("closed-")[:100],
                        reason=f"TicketHub ticket #{record['id']} reopened",
                    )
                    await channel.send(f"Ticket reopened by {member.mention}.")
                except discord.HTTPException:
                    log.exception(
                        "Failed to reopen ticket channel in guild %s",
                        guild.id,
                    )
        async with self.config.guild(guild).tickets() as tickets:
            tickets[str(record["id"])] = record
        await self._update_ticket_message(guild, record, profile)
        await self._send_log(
            guild,
            profile,
            "Ticket Reopened",
            (
                f"Ticket #{record['id']} reopened by {member.mention}.\n"
                f"Reason: {record['reopen_reason']}"
            ),
            color=self.OPEN_COLOR,
            record=record,
            ticket_channel=channel,
        )

    async def _delete_ticket_channel(
        self,
        guild: discord.Guild,
        record: TicketRecord,
        member: discord.Member | None,
        *,
        reason: str | None = None,
        permission_checked: bool = False,
    ) -> None:
        profile = await self._get_profile(guild, str(record.get("profile") or "main"))
        if not permission_checked and (
            member is None or not self._is_support_member(member, profile)
        ):
            raise commands.CommandError(
                "Only support staff can delete tickets.")
        actor = member or guild.me
        channel = await self._fetch_ticket_channel(guild, record)
        if profile.get("transcripts"):
            if channel is None:
                log.info(
                    "Skipping transcript for TicketHub ticket %s in guild %s because "
                    "the ticket channel or thread no longer exists.",
                    record.get("id"),
                    guild.id,
                )
            else:
                await self._send_transcript_bundle(
                    guild,
                    record,
                    profile,
                    requested_by=actor,
                    channel=channel,
                )
        if channel is not None:
            try:
                await channel.delete(
                    reason=reason or f"TicketHub ticket #{record['id']} deleted",
                )
            except discord.HTTPException as exc:
                raise commands.CommandError(
                    "I could not delete that ticket channel or thread.",
                ) from exc
        async with self.config.guild(guild).tickets() as tickets:
            tickets.pop(str(record["id"]), None)
        self._cancel_close_confirmation_resources(guild.id, int(record["id"]))
        self._cancel_ticket_auto_delete(guild.id, int(record["id"]))
        await self._send_log(
            guild,
            profile,
            "Ticket Deleted",
            (
                f"Ticket #{record['id']} deleted by {actor.mention}."
                if actor is not None
                else f"Ticket #{record['id']} deleted automatically."
            ),
            color=self.CLOSED_COLOR,
            record=record,
            include_jump=False,
        )

    async def _recover_ticket_record(
        self,
        guild: discord.Guild,
        channel: TicketLocation,
        actor: discord.Member,
    ) -> TicketRecord:
        tickets = await self.config.guild(guild).tickets()
        if any(
            str(record.get("channel_id")) == str(channel.id)
            for record in tickets.values()
        ):
            raise commands.CommandError(
                "That channel is already linked to a ticket.")
        control_message = None
        control_embed = None
        try:
            async for message in channel.history(limit=100, oldest_first=True):
                if message.author != guild.me:
                    continue
                for embed in message.embeds:
                    footer = str(getattr(embed.footer, "text", "") or "")
                    if footer.startswith("Ticket ID:"):
                        control_message = message
                        control_embed = embed
                        break
                if control_message is not None:
                    break
        except discord.HTTPException as exc:
            raise commands.CommandError(
                "I could not inspect that channel's history.",
            ) from exc
        if control_message is None or control_embed is None:
            raise commands.CommandError(
                "No TicketHub control message was found in that channel.",
            )
        footer = str(control_embed.footer.text or "")
        ticket_id_match = re.search(r"Ticket ID:\s*(\d+)", footer)
        if ticket_id_match is None:
            raise commands.CommandError(
                "The ticket control message has an invalid ID.")
        ticket_id = int(ticket_id_match.group(1))
        if str(ticket_id) in tickets:
            raise commands.CommandError(
                f"Ticket ID `{ticket_id}` is already in use.")
        fields = {field.name: field.value for field in control_embed.fields}
        owner_match = re.search(r"<@!?(\d+)>", str(fields.get("Owner") or ""))
        if owner_match is None:
            raise commands.CommandError(
                "I could not recover the ticket owner from the embed.",
            )
        owner_id = int(owner_match.group(1))
        profile_match = re.search(
            r"`([^`]+)`", str(fields.get("Profile") or ""))
        profile_name = self._clean_name(
            profile_match.group(1) if profile_match else "main",
        )
        profiles = await self._get_profiles(guild)
        if profile_name not in profiles:
            raise commands.CommandError(
                f"Ticket profile `{profile_name}` no longer exists.",
            )
        profile_value = str(fields.get("Profile") or "")
        profile_id_match = re.search(
            r"(?:Profile ID:\s*|[|•]\s*)\*\*#(\d+)\*\*",
            profile_value,
        )
        profile_ticket_id = (
            int(profile_id_match.group(1)) if profile_id_match else ticket_id
        )
        status_value = str(fields.get("Status") or "open").strip().lower()
        status = "closed" if "closed" in status_value else "open"
        claimed_match = re.search(
            r"<@!?(\d+)>", str(fields.get("Claimed By") or ""))
        locked_value = str(fields.get("Access")
                           or fields.get("Locked") or "No").lower()
        locked = "locked" in locked_value and "unlocked" not in locked_value
        created_match = re.search(
            r"<t:(\d+)", str(fields.get("Created") or ""))
        created_at = (
            float(created_match.group(1))
            if created_match
            else (
                control_embed.timestamp.timestamp()
                if control_embed.timestamp is not None
                else control_message.created_at.timestamp()
            )
        )
        closed_match = re.search(r"<t:(\d+)", str(fields.get("Closed") or ""))
        closed_at = (
            float(closed_match.group(1))
            if status == "closed" and closed_match is not None
            else (created_at if status == "closed" else None)
        )
        record: TicketRecord = {
            "id": ticket_id,
            "profile_ticket_id": profile_ticket_id,
            "profile": profile_name,
            "owner_id": owner_id,
            "channel_id": channel.id,
            "location_type": "thread"
            if isinstance(channel, discord.Thread)
            else "channel",
            "thread_parent_channel_id": (
                channel.parent_id if isinstance(
                    channel, discord.Thread) else None
            ),
            "message_id": control_message.id,
            "status": status,
            "claimed_by": int(claimed_match.group(1)) if claimed_match else None,
            "locked": locked,
            "locked_by": None,
            "locked_at": None,
            "unlocked_by": None,
            "unlocked_at": None,
            "reason": re.sub(
                r"(?m)^>\s?",
                "",
                re.sub(
                    r"^###\s+Request\s*",
                    "",
                    str(control_embed.description or "Recovered ticket"),
                    flags=re.IGNORECASE,
                ),
            )[:1000],
            "form_answers": [],
            "created_at": created_at,
            "closed_at": closed_at,
            "closed_by": None,
            "close_reason": re.sub(
                r"(?m)^>\s?",
                "",
                str(fields.get("Close Reason") or ""),
            )[:1000]
            or None,
            "reopened_at": None,
            "reopened_by": None,
            "reopen_reason": None,
            "pending_close": None,
            "participants": [owner_id],
            "events": [
                {
                    "type": "recovered",
                    "actor_id": actor.id,
                    "at": self._now_ts(),
                },
            ],
            "transcript_count": 0,
        }
        async with self.config.guild(guild).tickets() as stored_tickets:
            stored_tickets[str(ticket_id)] = record
        next_ticket_id = int(await self.config.guild(guild).next_ticket_id())
        if next_ticket_id <= ticket_id:
            await self.config.guild(guild).next_ticket_id.set(ticket_id + 1)
        profile = profiles[profile_name]
        current_profile_next = int(profile.get("next_profile_ticket_id") or 1)
        if current_profile_next <= profile_ticket_id:
            profile["next_profile_ticket_id"] = profile_ticket_id + 1
            await self._set_profile(guild, profile_name, profile)
        await self._update_ticket_message(guild, record, profile)
        if status == "closed":
            self._schedule_ticket_auto_delete(guild.id, record, profile)
        await self._send_log(
            guild,
            profile,
            "Ticket Recovered",
            f"Ticket #{ticket_id} recovered by {actor.mention}: {channel.mention}",
            color=self.DEFAULT_COLOR,
            record=record,
            ticket_channel=channel,
        )
        return record

    def _transcript_embed(
        self,
        guild: discord.Guild,
        record: TicketRecord,
        *,
        requested_by: discord.Member | None,
        message_count: int,
        html_file_name: str,
        text_file_name: str,
    ) -> discord.Embed:
        embed = discord.Embed(
            title=f"📄 Ticket #{record.get('id')} Transcript",
            description="A complete archive of this support conversation is attached below.",
            color=self.DEFAULT_COLOR,
            timestamp=self._now(),
        )
        owner = (
            guild.get_member(int(record["owner_id"]))
            if record.get("owner_id")
            else None
        )
        self._set_member_identity(
            embed,
            owner,
            fallback_name=f"Ticket owner ({record.get('owner_id') or 'unknown'})",
        )
        embed.add_field(
            name="Ticket",
            value=f"**#{record.get('id')}**  •  `{record.get('profile') or 'main'}`",
            inline=True,
        )
        embed.add_field(
            name="Status", value=self._status_display(record), inline=True)
        embed.add_field(name="Messages", value=self._count(
            message_count), inline=True)
        embed.add_field(
            name="Owner",
            value=self._user_ref(record.get("owner_id")),
            inline=True,
        )
        embed.add_field(
            name="Generated By",
            value=requested_by.mention if requested_by is not None else "Automatic",
            inline=True,
        )
        embed.add_field(
            name="Opened",
            value=self._format_ts(record.get("created_at"), "R"),
            inline=True,
        )
        embed.add_field(
            name="Attachments",
            value=f"`{html_file_name}`\n`{text_file_name}`",
            inline=False,
        )
        footer_icon = str(guild.icon.url) if guild.icon else None
        embed.set_footer(
            text=f"{guild.name}  •  TicketHub Transcript",
            icon_url=footer_icon,
        )
        return embed

    async def _send_transcript_bundle(
        self,
        guild: discord.Guild,
        record: TicketRecord,
        profile: ProfileRecord,
        *,
        requested_by: discord.Member | None = None,
        channel: TicketLocation | None = None,
    ) -> str:
        channel = channel or await self._fetch_ticket_channel(guild, record)
        if channel is None:
            raise commands.CommandError(
                "I could not find that ticket channel or thread.",
            )
        messages = await self._collect_messages(channel)
        html_transcript = await self._render_chat_exporter_transcript(
            guild,
            channel,
            messages,
        )
        if html_transcript is None:
            html_transcript = self._render_html_transcript(
                guild,
                channel,
                record,
                profile,
                messages,
            )
        html_bytes = html_transcript.encode("utf-8")
        text_bytes = self._render_text_transcript(
            guild,
            channel,
            record,
            messages,
        ).encode("utf-8")
        html_file_name = f"ticket-{record['id']}-transcript.html"
        text_file_name = f"ticket-{record['id']}-transcript.txt"
        transcript_embed = self._transcript_embed(
            guild,
            record,
            requested_by=requested_by,
            message_count=len(messages),
            html_file_name=html_file_name,
            text_file_name=text_file_name,
        )
        jump_view = self._jump_view(self._ticket_url(guild.id, channel.id))

        sent_targets: list[str] = []
        failed_targets: list[str] = []
        target_channel = self._profile_channel(
            guild,
            profile,
            "transcript_channel_id",
        ) or self._profile_channel(
            guild,
            profile,
            "log_channel_id",
        )
        if target_channel is not None:
            try:
                await target_channel.send(
                    embed=transcript_embed,
                    files=[
                        discord.File(io.BytesIO(html_bytes),
                                     filename=html_file_name),
                        discord.File(io.BytesIO(text_bytes),
                                     filename=text_file_name),
                    ],
                    view=jump_view,
                    allowed_mentions=discord.AllowedMentions.none(),
                )
                sent_targets.append(target_channel.mention)
            except discord.HTTPException:
                log.exception(
                    "Failed to send transcript to channel in guild %s",
                    guild.id,
                )
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
                        embed=transcript_embed,
                        files=[
                            discord.File(
                                io.BytesIO(html_bytes),
                                filename=html_file_name,
                            ),
                            discord.File(
                                io.BytesIO(text_bytes),
                                filename=text_file_name,
                            ),
                        ],
                        view=self._jump_view(
                            self._ticket_url(guild.id, channel.id)),
                    )
                    sent_targets.append("ticket owner DM")
                except discord.HTTPException:
                    failed_targets.append("ticket owner DM")

        record["transcript_count"] = int(
            record.get("transcript_count") or 0) + 1
        record.setdefault("events", []).append(
            {
                "type": "transcript",
                "actor_id": requested_by.id if requested_by else None,
                "at": self._now_ts(),
                "message_count": len(messages),
            },
        )
        async with self.config.guild(guild).tickets() as tickets:
            if str(record["id"]) in tickets:
                tickets[str(record["id"])] = record

        if sent_targets:
            result = "Transcript sent to " + ", ".join(sent_targets) + "."
            if failed_targets:
                result += " Failed to send to " + \
                    ", ".join(failed_targets) + "."
            return result
        if failed_targets:
            return (
                "Transcript generated, but failed to send to "
                + ", ".join(failed_targets)
                + "."
            )
        return "Transcript generated, but I could not send it to any configured destination."

    async def _collect_messages(self, channel: TicketLocation) -> list[discord.Message]:
        messages: list[discord.Message] = []
        try:
            async for message in channel.history(
                limit=self.MAX_TRANSCRIPT_MESSAGES,
                oldest_first=True,
            ):
                messages.append(message)
        except discord.HTTPException as exc:
            raise commands.CommandError(
                "I could not read the ticket message history.",
            ) from exc
        return messages

    async def _render_chat_exporter_transcript(
        self,
        guild: discord.Guild,
        channel: TicketLocation,
        messages: Sequence[discord.Message],
    ) -> str | None:
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
        except RECOVERABLE_EXCEPTIONS:
            log.exception(
                "DiscordChatExporterPy failed for ticket transcript in guild %s",
                guild.id,
            )
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
            lines.append(
                f"[{timestamp}] {message.author} ({message.author.id}): {content}",
            )
            for attachment in message.attachments:
                lines.append(
                    f"  Attachment: {attachment.filename} - {attachment.url}")
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
        events = "".join(
            self._render_html_event(event) for event in record.get("events", [])
        )
        generated = datetime.now(timezone.utc).strftime(
            "%Y-%m-%d %H:%M:%S UTC")
        owner = self._user_ref(record.get("owner_id"))
        return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Ticket #{html.escape(str(record.get("id")))} Transcript</title>
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
  <h1>Ticket #{html.escape(str(record.get("id")))} Transcript</h1>
  <div class="meta">
    <span>Server: {html.escape(guild.name)} ({guild.id})</span>
    <span>Channel: #{html.escape(channel.name)} ({channel.id})</span>
    <span>Owner: {html.escape(owner)}</span>
    <span>Status: {html.escape(str(record.get("status")))}</span>
    <span>Generated: {generated}</span>
  </div>
  <div class="toolbar"><input id="search" type="search" placeholder="Search messages, names, attachments..."></div>
</header>
<main>
  <section class="messages" id="messages">
    {"".join(rows) if rows else '<div class="message"><div></div><div>No messages found.</div></div>'}
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
        timestamp = message.created_at.astimezone(timezone.utc).strftime(
            "%Y-%m-%d %H:%M:%S UTC",
        )
        content = html.escape(message.clean_content or "")
        bot_tag = '<span class="bot">BOT</span>' if message.author.bot else ""
        attachments = "".join(
            f'<a href="{html.escape(attachment.url)}" target="_blank" rel="noreferrer">'
            f"{html.escape(attachment.filename)}</a>"
            for attachment in message.attachments
        )
        if attachments:
            attachments = f'<div class="attachments">{attachments}</div>'
        embeds = "".join(self._render_html_embed(embed)
                         for embed in message.embeds)
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
                f"<div><strong>{html.escape(str(field.name))}</strong>: {html.escape(str(field.value))}</div>",
            )
        if not parts:
            return ""
        return '<div class="embed">' + "".join(parts) + "</div>"

    def _render_html_event(self, event: dict[str, Any]) -> str:
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
        ticket_id: int | None = None,
    ) -> tuple[str, TicketRecord]:
        assert ctx.guild is not None
        if ticket_id is not None:
            tickets = await self.config.guild(ctx.guild).tickets()
            record = tickets.get(str(ticket_id))
            if not record:
                raise commands.BadArgument(
                    f"No ticket with ID `{ticket_id}` was found.",
                )
            return str(ticket_id), record
        if isinstance(ctx.channel, (discord.TextChannel, discord.Thread)):
            return await self._find_ticket_by_channel(ctx.guild, ctx.channel.id)
        raise commands.BadArgument(
            "Run this in a ticket channel/thread or provide a ticket ID.",
        )

    async def _send_settings(self, ctx: commands.Context) -> None:
        assert ctx.guild is not None
        profiles = await self._get_profiles(ctx.guild)
        tickets = await self.config.guild(ctx.guild).tickets()
        multi_panels = await self.config.guild(ctx.guild).multi_panels()
        enabled = await self.config.guild(ctx.guild).enabled()
        open_count = sum(
            1 for record in tickets.values() if record.get("status") == "open"
        )
        closed_count = sum(
            1 for record in tickets.values() if record.get("status") == "closed"
        )
        set_command_root = self._prefixed_set_root(ctx)
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
            panel_channel = self._profile_channel(
                ctx.guild,
                profile,
                "panel_channel_id",
            )
            ticket_category = self._profile_category(
                ctx.guild,
                profile,
                "ticket_category_id",
            )
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
                f"- modal fields {modal_count}",
            )
        embed.add_field(
            name="Profiles",
            value="\n".join(profile_lines)[:1024] if profile_lines else "None",
            inline=False,
        )
        embed.add_field(
            name="Start Here",
            value=(
                f"`{set_command_root} walkthrough`\n"
                f"`{set_command_root} panel main #tickets button`\n"
                f"`{set_command_root} attachpanel main <message-link> dropdown`\n"
                f"`{set_command_root} multipanel` for multi-profile panels\n"
                f"`{set_command_root} data importaaa3aall` for migration preview"
            ),
            inline=False,
        )
        await ctx.send(embed=embed)

    @commands.hybrid_group(
        name="ticket",
        aliases=["tickethub", "thub"],
        invoke_without_command=True,
        fallback="help",
    )
    @commands.guild_only()
    @commands.bot_has_permissions(embed_links=True)
    async def tickethub(self, ctx: commands.Context) -> None:
        """Show TicketHub commands."""
        await ctx.send_help(ctx.command)

    @tickethub.command(name="status", aliases=["settings"])
    async def tickethub_status(self, ctx: commands.Context) -> None:
        """Show TicketHub status, profiles, and setup hints."""
        await self._send_settings(ctx)

    @commands.hybrid_group(
        name="ticketset",
        aliases=["tickethubset", "thubset"],
        invoke_without_command=True,
        fallback="help",
    )
    @commands.guild_only()
    @commands.admin_or_permissions(manage_guild=True)
    @commands.bot_has_permissions(embed_links=True)
    async def tickethub_set(self, ctx: commands.Context) -> None:
        """Configure TicketHub profiles, panels, roles, automation, and exports."""
        await ctx.send_help(ctx.command)

    @tickethub_set.command(name="walkthrough", aliases=["wizard"])
    @commands.admin_or_permissions(manage_guild=True)
    async def tickethub_walkthrough(
        self,
        ctx: commands.Context,
        profile_name: str = "main",
    ) -> None:
        """Walk through a basic TicketHub setup."""
        assert ctx.guild is not None
        profile_name = self._clean_name(profile_name)
        await ctx.send(
            "TicketHub setup walkthrough started. Reply `cancel` at any step to stop.",
        )
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
                "Step 3/4: Which channel should ticket logs/transcripts go to? "
                "Reply with a channel, `here`, or `none`.",
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
            message = await self._post_panel(
                ctx.guild,
                profile_name,
                profile,
                panel_channel,
            )
        except commands.CommandError as error:
            await ctx.send(str(error))
            return
        await ctx.send(
            f"TicketHub setup complete for profile `{profile_name}`.\n"
            f"Panel: {message.jump_url}\n"
            f"Users can open tickets from the panel or with "
            f"`{self._prefixed_root(ctx)} open {profile_name}`.",
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
            raise commands.CommandError(
                "TicketHub walkthrough timed out.") from exc
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
    ) -> discord.TextChannel | None:
        while True:
            answer = await self._wait_for_setup_reply(ctx, prompt)
            lowered = answer.lower()
            if allow_none and lowered in {"none", "no", "skip", "off"}:
                return None
            if lowered in {"here", "current"} and isinstance(
                ctx.channel,
                discord.TextChannel,
            ):
                return ctx.channel
            try:
                return await commands.TextChannelConverter().convert(ctx, answer)
            except commands.BadArgument:
                await ctx.send(
                    "Reply with a text channel mention, channel ID, `here`, or `none` when allowed.",
                )

    async def _prompt_category(
        self,
        ctx: commands.Context,
        prompt: str,
        *,
        allow_none: bool = False,
    ) -> discord.CategoryChannel | None:
        while True:
            answer = await self._wait_for_setup_reply(ctx, prompt)
            lowered = answer.lower()
            if allow_none and lowered in {"none", "no", "skip", "off"}:
                return None
            try:
                return await commands.CategoryChannelConverter().convert(ctx, answer)
            except commands.BadArgument:
                await ctx.send(
                    "Reply with a category name, category ID, or `none` when allowed.",
                )

    async def _prompt_roles(
        self,
        ctx: commands.Context,
        prompt: str,
    ) -> list[discord.Role]:
        answer = await self._wait_for_setup_reply(ctx, prompt)
        if answer.lower() in {"none", "no", "skip", "off"}:
            return []
        roles: list[discord.Role] = []
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
    def _modal_summary_lines(
        cls,
        fields: Sequence[ModalFieldRecord] | None,
    ) -> list[str]:
        if not fields:
            return ["No modal questions are configured."]
        lines = []
        for index, field in enumerate(fields, start=1):
            label = cls._clean_modal_text(field.get("label"), 45) or "Question"
            question_type = cls._modal_type_name(field.get("type")) or "text"
            required = "required" if field.get(
                "required", True) else "optional"
            placeholder = cls._clean_modal_text(
                field.get("placeholder"), 100) or "none"
            if question_type == "choice":
                choices = ", ".join(
                    cls._clean_modal_choices(field.get("choices")))
                details = f"choice, {required}, options: {choices}"
            elif question_type == "boolean":
                details = f"boolean, {required}"
            else:
                style = cls._modal_style_name(field.get("style"))
                details = f"text/{style}, {required}, placeholder: {placeholder}"
            lines.append(f"{index}. {label} ({details})")
        return lines

    async def _send_modal_settings(
        self,
        ctx: commands.Context,
        profile_name: str = "main",
    ) -> None:
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

    async def _prompt_modal_choices(
        self,
        ctx: commands.Context,
        prompt: str,
    ) -> list[str]:
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
            raise commands.CommandError(
                "I could not inspect my server permissions.")
        perms = channel.permissions_for(me)
        if not perms.send_messages or not perms.embed_links:
            raise commands.CommandError(
                f"I need `Send Messages` and `Embed Links` in {channel.mention}.",
            )
        style = self._parse_panel_style(style)
        embed = self._panel_embed(guild, profile_name, profile)
        try:
            message = await channel.send(
                embed=embed,
                view=self._panel_view_for_style(style),
            )
        except discord.HTTPException as exc:
            raise commands.CommandError(
                "I could not post the ticket panel.") from exc
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
            raise commands.CommandError(
                "I could not inspect my server identity.")
        if message.guild is None or message.guild.id != guild.id:
            raise commands.BadArgument(
                "The panel message must be in this server.")
        if message.author.id != me.id:
            raise commands.BadArgument(
                "I can only attach a panel to a message sent by this bot.",
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
                f"That message is already the panel for `{other_profile_name}`.",
            )
        if message.components and profile_name not in tracked_profile_names:
            raise commands.BadArgument(
                "That message already has components. Remove them before attaching "
                "a TicketHub panel.",
            )
        style = self._parse_panel_style(style)
        try:
            await message.edit(view=self._panel_view_for_style(style))
        except discord.HTTPException as exc:
            raise commands.CommandError(
                "I could not attach the ticket panel to that message.",
            ) from exc
        profile["panel_channel_id"] = message.channel.id
        profile["panel_message_id"] = message.id
        profile["panel_style"] = style
        await self._set_profile(guild, profile_name, profile)
        return message

    @tickethub_set.command(name="enable")
    @commands.admin_or_permissions(manage_guild=True)
    async def tickethub_enable(
        self,
        ctx: commands.Context,
        enabled: bool = True,
    ) -> None:
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
        reason: str | None = None,
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

    @tickethub.command(name="createfor")
    @commands.admin_or_permissions(manage_guild=True)
    async def tickethub_create_for(
        self,
        ctx: commands.Context,
        owner: discord.Member,
        profile_name: str = "main",
        *,
        reason: str | None = None,
    ) -> None:
        """Create a ticket for another member."""
        assert ctx.guild is not None
        try:
            record, channel = await self._create_ticket(
                ctx.guild,
                owner,
                profile_name,
                reason=reason or f"Created for {owner} by {ctx.author}.",
            )
        except commands.CommandError as error:
            await ctx.send(str(error))
            return
        await ctx.send(
            f"Ticket #{record['id']} created for {owner.mention}: {channel.mention}",
        )

    @tickethub_set.command(name="panel")
    @commands.admin_or_permissions(manage_guild=True)
    async def tickethub_panel(
        self,
        ctx: commands.Context,
        profile_name: str = "main",
        channel: discord.TextChannel | None = None,
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
            f"{message.jump_url}",
        )

    @tickethub_set.command(name="attachpanel")
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
            f"{message.jump_url}",
        )

    @tickethub_set.command(name="clearpanel")
    @commands.admin_or_permissions(manage_guild=True)
    async def tickethub_clear_panel(
        self,
        ctx: commands.Context,
        message: discord.Message,
    ) -> None:
        """Remove TicketHub components from a tracked panel message."""
        assert ctx.guild is not None
        if message.guild is None or message.guild.id != ctx.guild.id:
            await ctx.send("That message is not in this server.")
            return
        tracked = False
        multi_panels = await self.config.guild(ctx.guild).multi_panels()
        if str(message.id) in multi_panels:
            await self._clear_multi_panel(ctx.guild, message)
            tracked = True
        profiles = await self._get_profiles(ctx.guild)
        for profile_name, profile in profiles.items():
            if str(profile.get("panel_message_id")) != str(message.id):
                continue
            profile["panel_message_id"] = None
            profile["panel_channel_id"] = None
            await self._set_profile(ctx.guild, profile_name, profile)
            tracked = True
        if not tracked:
            await ctx.send("That message is not a tracked TicketHub panel.")
            return
        try:
            await message.edit(view=None)
        except discord.HTTPException as exc:
            await ctx.send(
                f"Panel tracking cleared, but I could not edit the message: {exc}",
            )
            return
        await ctx.send(f"TicketHub panel controls removed: {message.jump_url}")

    @tickethub_set.group(
        name="multipanel",
        aliases=["mpanel"],
        invoke_without_command=True,
    )
    @commands.admin_or_permissions(manage_guild=True)
    async def tickethub_multi_panel(self, ctx: commands.Context) -> None:
        """Manage messages that offer multiple TicketHub profiles."""
        command_root = self._prefixed_set_root(ctx)
        await ctx.send(
            "Multi-panel commands:\n"
            f"`{command_root} multipanel add <message> <profile> "
            "<button|dropdown> <emoji|none> <name> | <description>`\n"
            f"`{command_root} multipanel remove <message> <profile>`\n"
            f"`{command_root} multipanel style <message> <button|dropdown>`\n"
            f"`{command_root} multipanel placeholder <message> <text>`\n"
            f"`{command_root} multipanel show <message>`\n"
            f"`{command_root} multipanel clear <message>`",
        )

    @tickethub_multi_panel.command(name="add", aliases=["multi-add"])
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
                raise commands.BadArgument(
                    "The panel message must be in this server.")
            if ctx.guild.me is None or message.author.id != ctx.guild.me.id:
                raise commands.BadArgument(
                    "I can only attach a multi-panel to a message sent by this bot.",
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
                        "creating a TicketHub multi-panel.",
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
                        f"That message is already the single panel for `{tracked_profile}`.",
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
                        "That multi-panel configuration is invalid; clear it and try again.",
                    )
                if record["style"] != style:
                    raise commands.BadArgument(
                        f"That multi-panel uses `{record['style']}`. Use the `style` "
                        "subcommand to change all its options.",
                    )
            if any(
                option["profile"] == profile_name
                for option in record.get("options", [])
            ):
                raise commands.BadArgument(
                    f"Profile `{profile_name}` is already on that multi-panel.",
                )
            if len(record.get("options", [])) >= 25:
                raise commands.BadArgument(
                    "A Discord multi-panel can contain at most 25 profile options.",
                )
            record["options"].append(
                {
                    "profile": profile_name,
                    "label": label,
                    "description": description,
                    "emoji": emoji_value,
                },
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
            f"multi-panel: {message.jump_url}.{description_note}",
        )

    @tickethub_multi_panel.command(name="remove", aliases=["multi-remove"])
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
                    f"Profile `{profile_name}` is not on that multi-panel.",
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
            f"Removed `{profile_name}` from the multi-panel: {message.jump_url}",
        )

    @tickethub_multi_panel.command(name="style", aliases=["multi-style"])
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
            await ctx.send(
                "Dropdown placeholders must be between 1 and 100 characters.",
            )
            return
        try:
            record = await self._get_multi_panel_record(ctx.guild, message.id)
            record["placeholder"] = placeholder
            await self._save_multi_panel(ctx.guild, message, record)
        except commands.CommandError as error:
            await ctx.send(str(error))
            return
        await ctx.send(f"Multi-panel placeholder updated: {message.jump_url}")

    @tickethub_multi_panel.command(name="show", aliases=["multi-show"])
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
                f" — {option['description']}" if option.get(
                    "description") else ""
            )
            lines.append(
                f"{index}. {emoji_text}{option['label']} (`{option['profile']}`)"
                f"{description_text}",
            )
        await ctx.send(box("\n".join(lines)))

    @tickethub_multi_panel.command(name="clear", aliases=["multi-clear"])
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

    async def _send_profile_info(
        self,
        ctx: commands.Context,
        profile_name: str = "main",
    ) -> None:
        """Show an existing profile's settings."""
        assert ctx.guild is not None
        try:
            profile_name = self._clean_name(profile_name)
            profile = await self._get_profile(ctx.guild, profile_name)
        except commands.CommandError as error:
            await ctx.send(str(error))
            return
        enabled_text = "Enabled" if profile.get("enabled") else "Disabled"
        ticket_mode = self._ticket_mode(profile)
        mode_text = ticket_mode.title()
        panel_channel = self._profile_channel(
            ctx.guild, profile, "panel_channel_id")
        ticket_category = self._profile_category(
            ctx.guild,
            profile,
            "ticket_category_id",
        )
        closed_category = self._profile_category(
            ctx.guild,
            profile,
            "closed_category_id",
        )
        thread_parent = self._thread_parent_channel(ctx.guild, profile)
        log_channel = self._profile_channel(
            ctx.guild, profile, "log_channel_id")
        transcript_channel = self._profile_channel(
            ctx.guild,
            profile,
            "transcript_channel_id",
        )
        ticket_role = ctx.guild.get_role(
            int(profile.get("ticket_role_id") or 0))
        auto_delete_hours = profile.get("auto_delete_on_close_hours")
        if auto_delete_hours is None:
            auto_delete_text = "Off"
        else:
            try:
                auto_delete_value = int(auto_delete_hours)
            except (TypeError, ValueError):
                auto_delete_text = "Off"
            else:
                if auto_delete_value == 0:
                    auto_delete_text = "Immediate, after a short grace period"
                else:
                    auto_delete_text = (
                        f"{auto_delete_value} "
                        f"hour{'s' if auto_delete_value != 1 else ''} after close"
                    )
        thread_parent_text = (
            thread_parent.mention
            if ticket_mode == "thread" and thread_parent
            else "Not used"
        )
        embed = discord.Embed(
            title="TicketHub Profile",
            description=(
                f"`{profile_name}` - **{enabled_text}** - **{mode_text} tickets**\n"
                f"Channel template: `{profile.get('channel_name') or 'ticket-{id}-{owner_name}'}`"
            ),
            color=self.DEFAULT_COLOR,
            timestamp=self._now(),
        )
        embed.add_field(
            name="Basics",
            value=(
                f"Max open per member: **{profile.get('max_open_tickets_by_member')}**\n"
                f"Panel style: **{self._panel_style(profile.get('panel_style')).title()}**\n"
                f"Modal questions: **{len(profile.get('creating_modal') or [])}**"
            ),
            inline=False,
        )
        embed.add_field(
            name="Destinations",
            value=(
                f"Panel: {panel_channel.mention if panel_channel else 'Not set'}\n"
                f"Open category: {ticket_category.name if ticket_category else 'Not set'}\n"
                f"Closed category: {closed_category.name if closed_category else 'Not set'}\n"
                f"Thread parent: {thread_parent_text}\n"
                f"Logs: {log_channel.mention if log_channel else 'Not set'}\n"
                f"Transcripts: {transcript_channel.mention if transcript_channel else 'Not set'}"
            ),
            inline=False,
        )
        embed.add_field(
            name="Lifecycle",
            value=(
                f"Close on leave: **{'Yes' if profile.get('close_on_leave') else 'No'}**\n"
                "Close request timeout: "
                f"**{self._format_minutes(self._close_request_timeout_minutes(profile))}**\n"
                f"Auto-delete closed tickets: **{auto_delete_text}**\n"
                f"Transcripts on delete: **{'Enabled' if profile.get('transcripts') else 'Disabled'}**\n"
                f"DM transcripts: **{'Enabled' if profile.get('dm_transcript') else 'Disabled'}**"
            ),
            inline=False,
        )
        embed.add_field(
            name="Owner Permissions",
            value=(
                f"Close: **{'Allowed' if profile.get('owner_can_close') else 'Blocked'}**\n"
                f"Reopen: **{'Allowed' if profile.get('owner_can_reopen') else 'Blocked'}**\n"
                f"Add members: **{'Allowed' if profile.get('owner_can_add_members') else 'Blocked'}**\n"
                f"Remove members: **{'Allowed' if profile.get('owner_can_remove_members') else 'Blocked'}**"
            ),
            inline=False,
        )
        embed.add_field(
            name="Roles",
            value=(
                f"Support: {self._role_mentions(ctx.guild, profile.get('support_role_ids') or []) or 'None'}\n"
                f"Speak: {self._role_mentions(ctx.guild, profile.get('speak_role_ids') or []) or 'None'}\n"
                f"View: {self._role_mentions(ctx.guild, profile.get('view_role_ids') or []) or 'None'}\n"
                f"Ping: {self._role_mentions(ctx.guild, profile.get('ping_role_ids') or []) or 'None'}\n"
                f"Ticket role: {ticket_role.mention if ticket_role else 'None'}\n"
                f"Whitelist: {self._role_mentions(ctx.guild, profile.get('whitelist_role_ids') or []) or 'None'}\n"
                f"Blacklist: {self._role_mentions(ctx.guild, profile.get('blacklist_role_ids') or []) or 'None'}"
            )[:1024],
            inline=False,
        )
        embed.set_footer(text="TicketHub profile settings")
        await ctx.send(embed=embed)

    async def _send_profile_list(self, ctx: commands.Context) -> None:
        assert ctx.guild is not None
        profiles = await self._get_profiles(ctx.guild)
        tickets = await self.config.guild(ctx.guild).tickets()
        multi_panels = await self.config.guild(ctx.guild).multi_panels()
        lines = [f"TicketHub profiles: {len(profiles)}"]
        for name, profile in sorted(profiles.items()):
            profile_tickets = [
                record
                for record in tickets.values()
                if str(record.get("profile") or "main") == name
            ]
            open_count = sum(
                1 for record in profile_tickets if record.get("status") == "open"
            )
            closed_count = sum(
                1 for record in profile_tickets if record.get("status") == "closed"
            )
            panel = self._profile_channel(
                ctx.guild, profile, "panel_channel_id")
            multi_count = 0
            for message_id, raw_record in multi_panels.items():
                try:
                    record = self._sanitize_multi_panel_record(
                        raw_record,
                        message_id=int(message_id),
                    )
                except (TypeError, ValueError):
                    record = None
                if record is None:
                    continue
                if any(option["profile"] == name for option in record["options"]):
                    multi_count += 1
            lines.append(
                f"- `{name}` | enabled: {bool(profile.get('enabled'))} "
                f"| mode: {self._ticket_mode(profile)} "
                f"| panel: {panel.mention if panel else 'not set'} "
                f"| multi-panels: {multi_count} "
                f"| tickets: {len(profile_tickets)} "
                f"({open_count} open, {closed_count} closed)",
            )
        for page in pagify("\n".join(lines), page_length=1800):
            await ctx.send(box(page))

    @tickethub_set.group(name="profile", invoke_without_command=True)
    @commands.admin_or_permissions(manage_guild=True)
    async def tickethub_profile(
        self,
        ctx: commands.Context,
        profile_name: str = "main",
    ) -> None:
        """Show, list, create, or delete TicketHub profiles."""
        await self._send_profile_info(ctx, profile_name)

    @tickethub_profile.command(name="show")
    @commands.admin_or_permissions(manage_guild=True)
    async def tickethub_profile_show(
        self,
        ctx: commands.Context,
        profile_name: str = "main",
    ) -> None:
        """Show an existing profile's settings."""
        await self._send_profile_info(ctx, profile_name)

    @tickethub_profile.command(name="list", aliases=["ls"])
    @commands.admin_or_permissions(manage_guild=True)
    async def tickethub_profile_list(self, ctx: commands.Context) -> None:
        """List configured profiles and ticket counts."""
        await self._send_profile_list(ctx)

    @tickethub_profile.command(name="create")
    @commands.admin_or_permissions(manage_guild=True)
    async def tickethub_profile_create(
        self,
        ctx: commands.Context,
        profile_name: str,
    ) -> None:
        """Create a TicketHub profile."""
        assert ctx.guild is not None
        try:
            clean_profile_name = self._clean_name(profile_name)
        except commands.BadArgument as error:
            await ctx.send(str(error))
            return

        profiles = await self._get_profiles(ctx.guild)
        if clean_profile_name in profiles:
            await ctx.send(
                f"A TicketHub profile named `{clean_profile_name}` already exists.",
            )
            return
        await self._set_profile(ctx.guild, clean_profile_name, self._default_profile())
        await ctx.send(
            f"Created TicketHub profile `{clean_profile_name}`. "
            f"Run `{self._prefixed_set_root(ctx)} profile {clean_profile_name}` to review it.",
        )

    @tickethub_profile.command(name="delete", aliases=["remove", "del"])
    @commands.admin_or_permissions(manage_guild=True)
    async def tickethub_profile_delete(
        self,
        ctx: commands.Context,
        profile_name: str,
        confirmation: str = "",
    ) -> None:
        """Delete an unused TicketHub profile with confirmation."""
        assert ctx.guild is not None
        try:
            clean_profile_name = self._clean_name(profile_name)
        except commands.BadArgument as error:
            await ctx.send(str(error))
            return
        if clean_profile_name == "main":
            await ctx.send("The default `main` profile cannot be deleted.")
            return

        profiles = await self._get_profiles(ctx.guild)
        profile = profiles.get(clean_profile_name)
        if profile is None:
            await ctx.send(f"No TicketHub profile named `{clean_profile_name}` exists.")
            return

        tickets = await self.config.guild(ctx.guild).tickets()
        profile_tickets = [
            record
            for record in tickets.values()
            if str(record.get("profile") or "main") == clean_profile_name
        ]
        if profile_tickets:
            open_count = sum(
                1 for record in profile_tickets if record.get("status") == "open"
            )
            closed_count = sum(
                1 for record in profile_tickets if record.get("status") == "closed"
            )
            await ctx.send(
                f"`{clean_profile_name}` is still used by {len(profile_tickets)} "
                f"tracked ticket(s): {open_count} open, {closed_count} closed. "
                "Delete those tickets before deleting the profile.",
            )
            return

        if profile.get("panel_message_id"):
            await ctx.send(
                f"`{clean_profile_name}` still has a single-profile panel configured. "
                f"Clear it first with `{self._prefixed_set_root(ctx)} clearpanel <message>`.",
            )
            return

        multi_panels = await self.config.guild(ctx.guild).multi_panels()
        multi_refs = []
        for message_id, raw_record in multi_panels.items():
            try:
                record = self._sanitize_multi_panel_record(
                    raw_record,
                    message_id=int(message_id),
                )
            except (TypeError, ValueError):
                record = None
            if record is None:
                continue
            if any(
                option["profile"] == clean_profile_name for option in record["options"]
            ):
                multi_refs.append(message_id)
        if multi_refs:
            await ctx.send(
                f"`{clean_profile_name}` is still used by {len(multi_refs)} "
                "multi-panel(s). Remove it from those panels first with "
                f"`{self._prefixed_set_root(ctx)} multipanel remove <message> "
                f"{clean_profile_name}`.",
            )
            return

        if confirmation.lower() != "confirm":
            await ctx.send(
                f"This will delete the unused `{clean_profile_name}` profile. "
                f"Run `{self._prefixed_set_root(ctx)} profile delete "
                f"{clean_profile_name} confirm` to apply.",
            )
            return

        async with self.config.guild(ctx.guild).profiles() as stored_profiles:
            target_key = None
            for raw_name in stored_profiles:
                if self._clean_name(str(raw_name)) == clean_profile_name:
                    target_key = raw_name
                    break
            if target_key is None:
                await ctx.send(
                    f"No TicketHub profile named `{clean_profile_name}` exists.",
                )
                return
            stored_profiles.pop(target_key, None)
            if not stored_profiles:
                stored_profiles["main"] = self._default_profile()
        await ctx.send(f"Deleted unused TicketHub profile `{clean_profile_name}`.")

    @tickethub_set.command(name="channelname", aliases=["channeltemplate"])
    @commands.admin_or_permissions(manage_guild=True)
    async def tickethub_channel_name(
        self,
        ctx: commands.Context,
        profile_name: str = "main",
        *,
        template: str | None = None,
    ) -> None:
        """Show or set the ticket channel-name template for a profile."""
        assert ctx.guild is not None
        profile_name = self._clean_name(profile_name)
        profile = await self._ensure_profile(ctx.guild, profile_name)
        if template is None:
            next_number = self._next_profile_ticket_number(
                profile,
                await self.config.guild(ctx.guild).tickets(),
                profile_name,
            )
            await ctx.send(
                f"Channel name template for `{profile_name}`: "
                f"`{profile.get('channel_name') or 'ticket-{id}-{owner_name}'}`\n"
                f"Next profile ID: **{next_number}**",
            )
            return
        try:
            template = self._validate_channel_name_template(template)
        except commands.CommandError as error:
            await ctx.send(str(error))
            return
        profile["channel_name"] = template
        await self._set_profile(ctx.guild, profile_name, profile)
        await ctx.send(
            f"Channel name template for `{profile_name}` set to `{template}`.",
        )

    @tickethub_set.command(name="category")
    @commands.admin_or_permissions(manage_guild=True)
    async def tickethub_category(
        self,
        ctx: commands.Context,
        profile_name: str,
        category: discord.CategoryChannel | None = None,
    ) -> None:
        """Set the open-ticket category for a profile."""
        assert ctx.guild is not None
        profile = await self._ensure_profile(ctx.guild, profile_name)
        profile["ticket_category_id"] = category.id if category else None
        await self._set_profile(ctx.guild, profile_name, profile)
        await ctx.send(
            f"Open-ticket category for `{profile_name}` set to {category.name if category else 'none'}.",
        )

    @tickethub_set.command(name="closedcategory")
    @commands.admin_or_permissions(manage_guild=True)
    async def tickethub_closed_category(
        self,
        ctx: commands.Context,
        profile_name: str,
        category: discord.CategoryChannel | None = None,
    ) -> None:
        """Set the closed-ticket category for a profile."""
        assert ctx.guild is not None
        profile = await self._ensure_profile(ctx.guild, profile_name)
        profile["closed_category_id"] = category.id if category else None
        await self._set_profile(ctx.guild, profile_name, profile)
        await ctx.send(
            f"Closed-ticket category for `{profile_name}` set to {category.name if category else 'none'}.",
        )

    @tickethub_set.command(name="mode", aliases=["ticketmode"])
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
            extra = "\nSet a thread parent with `[p]ticketset threadparent <profile> #channel`."
        await ctx.send(f"Ticket mode for `{profile_name}` set to **{mode}**.{extra}")

    @tickethub_set.command(name="threadparent", aliases=["threadchannel"])
    @commands.admin_or_permissions(manage_guild=True)
    async def tickethub_thread_parent(
        self,
        ctx: commands.Context,
        profile_name: str,
        channel: discord.TextChannel | None = None,
    ) -> None:
        """Set the parent channel used for private thread tickets."""
        assert ctx.guild is not None
        profile = await self._ensure_profile(ctx.guild, profile_name)
        profile["thread_parent_channel_id"] = channel.id if channel else None
        await self._set_profile(ctx.guild, profile_name, profile)
        target = channel.mention if channel else "panel channel fallback"
        await ctx.send(f"Thread-ticket parent for `{profile_name}` set to {target}.")

    @tickethub_set.command(name="logchannel")
    @commands.admin_or_permissions(manage_guild=True)
    async def tickethub_log_channel(
        self,
        ctx: commands.Context,
        profile_name: str,
        channel: discord.TextChannel | None = None,
    ) -> None:
        """Set the log channel for a profile."""
        assert ctx.guild is not None
        profile = await self._ensure_profile(ctx.guild, profile_name)
        profile["log_channel_id"] = channel.id if channel else None
        await self._set_profile(ctx.guild, profile_name, profile)
        await ctx.send(
            f"Log channel for `{profile_name}` set to {channel.mention if channel else 'none'}.",
        )

    @tickethub_set.command(name="transcriptchannel")
    @commands.admin_or_permissions(manage_guild=True)
    async def tickethub_transcript_channel(
        self,
        ctx: commands.Context,
        profile_name: str,
        channel: discord.TextChannel | None = None,
    ) -> None:
        """Set the transcript channel for a profile."""
        assert ctx.guild is not None
        profile = await self._ensure_profile(ctx.guild, profile_name)
        profile["transcript_channel_id"] = channel.id if channel else None
        await self._set_profile(ctx.guild, profile_name, profile)
        await ctx.send(
            f"Transcript channel for `{profile_name}` set to {channel.mention if channel else 'none'}.",
        )

    @tickethub_set.group(name="modal", invoke_without_command=True)
    @commands.admin_or_permissions(manage_guild=True)
    async def tickethub_modal(
        self,
        ctx: commands.Context,
        profile_name: str = "main",
    ) -> None:
        """Manage modal questions shown from ticket panels."""
        await self._send_modal_settings(ctx, profile_name)

    @tickethub_modal.command(name="show")
    @commands.admin_or_permissions(manage_guild=True)
    async def tickethub_modal_show(
        self,
        ctx: commands.Context,
        profile_name: str = "main",
    ) -> None:
        """Show modal questions for a profile."""
        await self._send_modal_settings(ctx, profile_name)

    @tickethub_modal.command(name="wizard")
    @commands.admin_or_permissions(manage_guild=True)
    async def tickethub_modal_wizard(
        self,
        ctx: commands.Context,
        profile_name: str = "main",
    ) -> None:
        """Walk through creating a custom ticket modal."""
        assert ctx.guild is not None
        profile_name = self._clean_name(profile_name)
        await self._ensure_profile(ctx.guild, profile_name)
        await ctx.send(
            "TicketHub modal builder started. Reply `cancel` at any step to stop.",
        )
        try:
            count = await self._prompt_modal_count(ctx)
            fields: list[ModalFieldRecord] = []
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
                choices: list[str] = []
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
                    },
                )
        except commands.CommandError as error:
            await ctx.send(str(error))
            return

        profile = await self._ensure_profile(ctx.guild, profile_name)
        profile["creating_modal"] = self._sanitize_modal_fields(fields)
        await self._set_profile(ctx.guild, profile_name, profile)
        await ctx.send(
            f"Modal for `{profile_name}` saved.\n"
            + box("\n".join(self._modal_summary_lines(profile["creating_modal"]))),
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
        choices: list[str] = []
        if normalized_type == "choice":
            if "|" not in label:
                await ctx.send(
                    "Choice questions must use `Question label | choice one, choice two`.",
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
            },
        )
        profile["creating_modal"] = self._sanitize_modal_fields(fields)
        await self._set_profile(ctx.guild, profile_name, profile)
        await ctx.send(
            f"Added modal question to `{self._clean_name(profile_name)}`.\n"
            + box("\n".join(self._modal_summary_lines(profile["creating_modal"]))),
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
            await ctx.send(
                f"`{self._clean_name(profile_name)}` has no modal questions.",
            )
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
            + box("\n".join(self._modal_summary_lines(profile["creating_modal"]))),
        )

    @tickethub_modal.command(
        name="defaultreason",
        aliases=["reason", "default"],
    )
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
        await ctx.send(
            f"`{self._clean_name(profile_name)}` now uses the default Reason modal.",
        )

    @tickethub_modal.command(
        name="clear",
        aliases=["disable", "off"],
    )
    @commands.admin_or_permissions(manage_guild=True)
    async def tickethub_modal_clear(
        self,
        ctx: commands.Context,
        profile_name: str = "main",
    ) -> None:
        """Disable modal questions for a profile."""
        assert ctx.guild is not None
        profile = await self._ensure_profile(ctx.guild, profile_name)
        profile["creating_modal"] = None
        await self._set_profile(ctx.guild, profile_name, profile)
        await ctx.send(
            f"Modal questions disabled for `{self._clean_name(profile_name)}`.",
        )

    @tickethub_set.group(name="roles", invoke_without_command=True)
    @commands.admin_or_permissions(manage_guild=True)
    async def tickethub_roles(self, ctx: commands.Context) -> None:
        """Manage support, speak, view, ping, whitelist, blacklist, and ticket roles."""
        await ctx.send_help(ctx.command)

    @tickethub_roles.command(name="supportadd")
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
        role_ids = {int(role_id)
                        for role_id in profile.get("support_role_ids") or []}
        role_ids.add(role.id)
        profile["support_role_ids"] = sorted(role_ids)
        await self._set_profile(ctx.guild, profile_name, profile)
        await ctx.send(f"{role.mention} can now support `{profile_name}` tickets.")

    @tickethub_roles.command(name="support-add", hidden=True)
    @commands.admin_or_permissions(manage_guild=True)
    async def tickethub_support_role_add_legacy(
        self,
        ctx: commands.Context,
        profile_name: str,
        role: discord.Role,
    ) -> None:
        """Keep the historical prefix and slash subcommand name working."""
        await self.tickethub_support_role_add.callback(
            self,
            ctx,
            profile_name,
            role,
        )

    @tickethub_roles.command(name="supportremove")
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
        role_ids = {int(role_id)
                        for role_id in profile.get("support_role_ids") or []}
        role_ids.discard(role.id)
        profile["support_role_ids"] = sorted(role_ids)
        await self._set_profile(ctx.guild, profile_name, profile)
        await ctx.send(f"{role.mention} removed from `{profile_name}` support roles.")

    @tickethub_roles.command(name="support-remove", hidden=True)
    @commands.admin_or_permissions(manage_guild=True)
    async def tickethub_support_role_remove_legacy(
        self,
        ctx: commands.Context,
        profile_name: str,
        role: discord.Role,
    ) -> None:
        """Keep the historical prefix and slash subcommand name working."""
        await self.tickethub_support_role_remove.callback(
            self,
            ctx,
            profile_name,
            role,
        )

    @staticmethod
    def _profile_role_field(role_type: str) -> str:
        fields = {
            "support": "support_role_ids",
            "speak": "speak_role_ids",
            "view": "view_role_ids",
            "ping": "ping_role_ids",
            "whitelist": "whitelist_role_ids",
            "blacklist": "blacklist_role_ids",
        }
        try:
            return fields[role_type.lower()]
        except KeyError as exc:
            raise commands.BadArgument(
                "Role type must be support, speak, view, ping, whitelist, or blacklist.",
            ) from exc

    @tickethub_roles.command(name="add")
    @commands.admin_or_permissions(manage_guild=True)
    async def tickethub_roles_add(
        self,
        ctx: commands.Context,
        profile_name: str,
        role_type: str,
        role: discord.Role,
    ) -> None:
        """Add a profile role by role type."""
        assert ctx.guild is not None
        try:
            field = self._profile_role_field(role_type)
        except commands.BadArgument as error:
            await ctx.send(str(error))
            return
        profile = await self._ensure_profile(ctx.guild, profile_name)
        role_ids = {int(role_id) for role_id in profile.get(field) or []}
        role_ids.add(role.id)
        profile[field] = sorted(role_ids)
        await self._set_profile(ctx.guild, profile_name, profile)
        await ctx.send(
            f"{role.mention} added as a `{role_type.lower()}` role for `{profile_name}`.",
        )

    @tickethub_roles.command(name="remove")
    @commands.admin_or_permissions(manage_guild=True)
    async def tickethub_roles_remove(
        self,
        ctx: commands.Context,
        profile_name: str,
        role_type: str,
        role: discord.Role,
    ) -> None:
        """Remove a profile role by role type."""
        assert ctx.guild is not None
        try:
            field = self._profile_role_field(role_type)
        except commands.BadArgument as error:
            await ctx.send(str(error))
            return
        profile = await self._ensure_profile(ctx.guild, profile_name)
        role_ids = {int(role_id) for role_id in profile.get(field) or []}
        role_ids.discard(role.id)
        profile[field] = sorted(role_ids)
        await self._set_profile(ctx.guild, profile_name, profile)
        await ctx.send(
            f"{role.mention} removed from `{role_type.lower()}` roles for `{profile_name}`.",
        )

    @tickethub_roles.command(name="ticketrole")
    @commands.admin_or_permissions(manage_guild=True)
    async def tickethub_ticket_role(
        self,
        ctx: commands.Context,
        profile_name: str,
        role: discord.Role | None = None,
    ) -> None:
        """Set the role assigned when a member opens a ticket; omit it to clear."""
        assert ctx.guild is not None
        profile = await self._ensure_profile(ctx.guild, profile_name)
        profile["ticket_role_id"] = role.id if role is not None else None
        await self._set_profile(ctx.guild, profile_name, profile)
        await ctx.send(
            f"Ticket role for `{profile_name}` set to "
            f"{role.mention if role is not None else 'disabled'}.",
        )

    @tickethub_set.group(name="behavior", invoke_without_command=True)
    @commands.admin_or_permissions(manage_guild=True)
    async def tickethub_behavior(self, ctx: commands.Context) -> None:
        """Manage profile behavior, lifecycle, transcript, and control settings."""
        await ctx.send_help(ctx.command)

    @tickethub_behavior.command(name="ownerpermission")
    @commands.admin_or_permissions(manage_guild=True)
    async def tickethub_owner_permission(
        self,
        ctx: commands.Context,
        profile_name: str,
        action: str,
        enabled: bool,
    ) -> None:
        """Set whether owners can close, reopen, add members, or remove members."""
        assert ctx.guild is not None
        fields = {
            "close": "owner_can_close",
            "reopen": "owner_can_reopen",
            "add": "owner_can_add_members",
            "remove": "owner_can_remove_members",
        }
        field = fields.get(action.lower())
        if field is None:
            await ctx.send("Action must be `close`, `reopen`, `add`, or `remove`.")
            return
        profile = await self._ensure_profile(ctx.guild, profile_name)
        profile[field] = enabled
        await self._set_profile(ctx.guild, profile_name, profile)
        await ctx.send(
            f"Ticket owners can now{'' if enabled else ' not'} `{action.lower()}` "
            f"for `{profile_name}`.",
        )

    @tickethub_behavior.command(name="closeonleave")
    @commands.admin_or_permissions(manage_guild=True)
    async def tickethub_close_on_leave(
        self,
        ctx: commands.Context,
        profile_name: str,
        enabled: bool,
    ) -> None:
        """Set whether tickets close when their owner leaves the server."""
        assert ctx.guild is not None
        profile = await self._ensure_profile(ctx.guild, profile_name)
        profile["close_on_leave"] = enabled
        await self._set_profile(ctx.guild, profile_name, profile)
        await ctx.send(
            f"Close-on-leave for `{profile_name}` is now "
            f"{'enabled' if enabled else 'disabled'}.",
        )

    @tickethub_behavior.command(
        name="closetimeout",
        aliases=["close-timeout", "closerequesttimeout", "closewait"],
    )
    @commands.admin_or_permissions(manage_guild=True)
    async def tickethub_close_timeout(
        self,
        ctx: commands.Context,
        profile_or_minutes: str = "main",
        minutes: str | None = None,
    ) -> None:
        """Set minutes before unanswered close requests auto-close."""
        assert ctx.guild is not None
        profile_name = profile_or_minutes
        amount_arg = minutes
        if amount_arg is None:
            if profile_or_minutes.lower() in {"default", "reset"}:
                profile_name = "main"
                amount_arg = profile_or_minutes
            else:
                try:
                    int(profile_or_minutes)
                except ValueError:
                    amount_arg = None
                else:
                    profile_name = "main"
                    amount_arg = profile_or_minutes

        profile_name = self._clean_name(profile_name)
        profile = await self._ensure_profile(ctx.guild, profile_name)
        if amount_arg is None:
            await ctx.send(
                f"Close request timeout for `{profile_name}` is "
                f"**{self._format_minutes(self._close_request_timeout_minutes(profile))}**.",
            )
            return

        if amount_arg.lower() in {"default", "reset"}:
            configured_minutes = self.DEFAULT_CLOSE_REQUEST_TIMEOUT_MINUTES
        else:
            try:
                configured_minutes = int(amount_arg)
            except ValueError:
                await ctx.send(
                    "Minutes must be a whole number from "
                    f"{self.MIN_CLOSE_REQUEST_TIMEOUT_MINUTES} to "
                    f"{self.MAX_CLOSE_REQUEST_TIMEOUT_MINUTES}, or `default`.",
                )
                return
        if not (
            self.MIN_CLOSE_REQUEST_TIMEOUT_MINUTES
            <= configured_minutes
            <= self.MAX_CLOSE_REQUEST_TIMEOUT_MINUTES
        ):
            await ctx.send(
                "Minutes must be between "
                f"{self.MIN_CLOSE_REQUEST_TIMEOUT_MINUTES} and "
                f"{self.MAX_CLOSE_REQUEST_TIMEOUT_MINUTES}.",
            )
            return

        profile["close_request_timeout_minutes"] = configured_minutes
        await self._set_profile(ctx.guild, profile_name, profile)
        await ctx.send(
            f"Close request timeout for `{profile_name}` set to "
            f"**{self._format_minutes(configured_minutes)}**. "
            "Active close confirmations keep their current timeout.",
        )

    @tickethub_behavior.command(name="autodelete")
    @commands.admin_or_permissions(manage_guild=True)
    async def tickethub_auto_delete(
        self,
        ctx: commands.Context,
        profile_name: str,
        hours: str,
    ) -> None:
        """Set hours before closed tickets are deleted, 0 for immediate, or off."""
        assert ctx.guild is not None
        if hours.lower() in {"off", "disable", "disabled", "none"}:
            configured_hours: int | None = None
        else:
            try:
                configured_hours = int(hours)
            except ValueError:
                await ctx.send("Hours must be `off` or a whole number from 0 to 720.")
                return
            if not 0 <= configured_hours <= 720:
                await ctx.send("Hours must be between 0 and 720.")
                return
        profile_name = self._clean_name(profile_name)
        profile = await self._ensure_profile(ctx.guild, profile_name)
        profile["auto_delete_on_close_hours"] = configured_hours
        await self._set_profile(ctx.guild, profile_name, profile)
        tickets = await self.config.guild(ctx.guild).tickets()
        for record in tickets.values():
            if (
                str(record.get("profile") or "main") == profile_name
                and record.get("status") == "closed"
            ):
                self._schedule_ticket_auto_delete(
                    ctx.guild.id, record, profile)
        await ctx.send(
            f"Auto-delete for `{profile_name}` set to "
            + (
                "off."
                if configured_hours is None
                else f"{configured_hours} hour(s) after closing."
            ),
        )

    @tickethub_behavior.command(name="emoji")
    @commands.admin_or_permissions(manage_guild=True)
    async def tickethub_control_emoji(
        self,
        ctx: commands.Context,
        profile_name: str,
        action: str,
        *,
        emoji: str,
    ) -> None:
        """Set a ticket-control emoji, or use default to reset it."""
        assert ctx.guild is not None
        action = action.lower()
        defaults = self._default_profile()["control_emojis"]
        if action not in defaults:
            await ctx.send(
                "Action must be claim, unclaim, lock, unlock, close, reopen, members, "
                "transcript, or delete.",
            )
            return
        profile_name = self._clean_name(profile_name)
        profile = await self._ensure_profile(ctx.guild, profile_name)
        configured = dict(profile.get("control_emojis") or {})
        if emoji.lower() in {"default", "reset"}:
            configured.pop(action, None)
            selected = defaults[action]
        else:
            selected = emoji.strip()
            if not selected or len(selected) > 100:
                await ctx.send("Provide one Unicode or custom Discord emoji.")
                return
            try:
                parsed_emoji = discord.PartialEmoji.from_str(selected)
            except (TypeError, ValueError):
                await ctx.send("That is not a valid Unicode or custom Discord emoji.")
                return
            if (
                parsed_emoji.id is not None
                and self.bot.get_emoji(parsed_emoji.id) is None
            ):
                await ctx.send("I cannot access that custom Discord emoji.")
                return
            configured[action] = selected
        profile["control_emojis"] = configured
        await self._set_profile(ctx.guild, profile_name, profile)
        tickets = await self.config.guild(ctx.guild).tickets()
        for record in tickets.values():
            if str(record.get("profile") or "main") == profile_name:
                await self._update_ticket_message(ctx.guild, record, profile)
        await ctx.send(f"`{action}` emoji for `{profile_name}` set to {selected}.")

    @tickethub_behavior.command(name="maxopen")
    @commands.admin_or_permissions(manage_guild=True)
    async def tickethub_max_open(
        self,
        ctx: commands.Context,
        profile_name: str,
        amount: int,
    ) -> None:
        """Set the max open tickets per member for a profile."""
        assert ctx.guild is not None
        amount = max(0, min(amount, 50))
        profile = await self._ensure_profile(ctx.guild, profile_name)
        profile["max_open_tickets_by_member"] = amount
        await self._set_profile(ctx.guild, profile_name, profile)
        await ctx.send(f"Max open tickets for `{profile_name}` set to **{amount}**.")

    @tickethub_behavior.command(name="dmtranscript")
    @commands.admin_or_permissions(manage_guild=True)
    async def tickethub_dm_transcript(
        self,
        ctx: commands.Context,
        profile_name: str,
        enabled: bool,
    ) -> None:
        """Choose whether transcripts are DM'd to ticket owners."""
        assert ctx.guild is not None
        profile = await self._ensure_profile(ctx.guild, profile_name)
        profile["dm_transcript"] = enabled
        await self._set_profile(ctx.guild, profile_name, profile)
        await ctx.send(
            f"Ticket owner transcript DMs for `{profile_name}` are now {'enabled' if enabled else 'disabled'}.",
        )

    @tickethub_behavior.command(name="transcripts")
    @commands.admin_or_permissions(manage_guild=True)
    async def tickethub_transcripts(
        self,
        ctx: commands.Context,
        profile_name: str,
        enabled: bool,
    ) -> None:
        """Enable or disable automatic transcript generation on ticket delete."""
        assert ctx.guild is not None
        profile = await self._ensure_profile(ctx.guild, profile_name)
        profile["transcripts"] = enabled
        await self._set_profile(ctx.guild, profile_name, profile)
        await ctx.send(
            f"Transcripts for `{profile_name}` are now {'enabled' if enabled else 'disabled'}.",
        )

    @tickethub.command(name="claim")
    @commands.guild_only()
    async def tickethub_claim(
        self,
        ctx: commands.Context,
        ticket_id: int | None = None,
    ) -> None:
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
    async def tickethub_unclaim(
        self,
        ctx: commands.Context,
        ticket_id: int | None = None,
    ) -> None:
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

    @tickethub.command(name="lock")
    @commands.guild_only()
    async def tickethub_lock(
        self,
        ctx: commands.Context,
        ticket_id: int | None = None,
    ) -> None:
        """Lock a ticket so its owner and added members cannot post."""
        assert ctx.guild is not None
        if not isinstance(ctx.author, discord.Member):
            return
        try:
            _key, record = await self._resolve_ticket_argument(ctx, ticket_id)
            await self._lock_ticket(ctx.guild, record, ctx.author)
        except commands.CommandError as error:
            await ctx.send(str(error))
            return
        await ctx.send(f"Ticket #{record['id']} locked.")

    @tickethub.command(name="unlock")
    @commands.guild_only()
    async def tickethub_unlock(
        self,
        ctx: commands.Context,
        ticket_id: int | None = None,
    ) -> None:
        """Unlock a ticket and restore its members' access."""
        assert ctx.guild is not None
        if not isinstance(ctx.author, discord.Member):
            return
        try:
            _key, record = await self._resolve_ticket_argument(ctx, ticket_id)
            await self._unlock_ticket(ctx.guild, record, ctx.author)
        except commands.CommandError as error:
            await ctx.send(str(error))
            return
        await ctx.send(f"Ticket #{record['id']} unlocked.")

    @tickethub.command(name="close")
    @commands.guild_only()
    async def tickethub_close(
        self,
        ctx: commands.Context,
        ticket_id: int | None = None,
        *,
        reason: str | None = None,
    ) -> None:
        """Request ticket closure with an optional reason and confirmation."""
        assert ctx.guild is not None
        if not isinstance(ctx.author, discord.Member):
            return
        try:
            _key, record = await self._resolve_ticket_argument(ctx, ticket_id)
            await self._validate_close_request(ctx.guild, record, ctx.author)
        except commands.CommandError as error:
            await ctx.send(str(error))
            return
        try:
            message = await self._start_close_confirmation(
                ctx.guild,
                record,
                ctx.author,
                reason or "",
            )
        except commands.CommandError as error:
            await ctx.send(str(error))
            return
        await ctx.send(f"Close confirmation posted: {message.jump_url}")

    @tickethub.command(name="reopen")
    @commands.guild_only()
    async def tickethub_reopen(
        self,
        ctx: commands.Context,
        ticket_id: int | None = None,
        *,
        reason: str | None = None,
    ) -> None:
        """Reopen a ticket with an optional reason."""
        assert ctx.guild is not None
        if not isinstance(ctx.author, discord.Member):
            return
        try:
            _key, record = await self._resolve_ticket_argument(ctx, ticket_id)
            await self._reopen_ticket(
                ctx.guild,
                record,
                ctx.author,
                reason=reason,
            )
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
        ticket_id: int | None = None,
        *,
        reason: str | None = None,
    ) -> None:
        """Delete a ticket channel or thread after saving a transcript."""
        assert ctx.guild is not None
        if not isinstance(ctx.author, discord.Member):
            return
        try:
            _key, record = await self._resolve_ticket_argument(ctx, ticket_id)
            await self._delete_ticket_channel(
                ctx.guild,
                record,
                ctx.author,
                reason=reason,
            )
        except commands.CommandError as error:
            await ctx.send(str(error))
            return

    @tickethub.command(name="recover")
    @commands.admin_or_permissions(manage_guild=True)
    async def tickethub_recover(
        self,
        ctx: commands.Context,
        channel: discord.TextChannel | discord.Thread | None = None,
    ) -> None:
        """Recover a TicketHub record from its control message."""
        assert ctx.guild is not None
        if not isinstance(ctx.author, discord.Member):
            return
        target = channel or ctx.channel
        if not isinstance(target, (discord.TextChannel, discord.Thread)):
            await ctx.send("Choose a ticket text channel or thread to recover.")
            return
        try:
            record = await self._recover_ticket_record(
                ctx.guild,
                target,
                ctx.author,
            )
        except commands.CommandError as error:
            await ctx.send(str(error))
            return
        await ctx.send(
            f"Recovered TicketHub ticket #{record['id']} from {target.mention}.",
        )

    @tickethub.command(name="transcript")
    @commands.guild_only()
    @commands.bot_has_permissions(attach_files=True)
    async def tickethub_transcript(
        self,
        ctx: commands.Context,
        ticket_id: int | None = None,
    ) -> None:
        """Generate and send a ticket transcript."""
        assert ctx.guild is not None
        if not isinstance(ctx.author, discord.Member):
            return
        try:
            _key, record = await self._resolve_ticket_argument(ctx, ticket_id)
            profile = await self._get_profile(
                ctx.guild,
                str(record.get("profile") or "main"),
            )
            if not self._is_support_member(
                ctx.author,
                profile,
            ) and ctx.author.id != int(record.get("owner_id") or 0):
                await ctx.send(
                    "Only the ticket owner or support staff can generate transcripts.",
                )
                return
            result = await self._send_transcript_bundle(
                ctx.guild,
                record,
                profile,
                requested_by=ctx.author,
            )
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
        ticket_id: int | None = None,
    ) -> None:
        """Add a member to a ticket."""
        assert ctx.guild is not None
        if not isinstance(ctx.author, discord.Member):
            return
        try:
            _key, record = await self._resolve_ticket_argument(ctx, ticket_id)
            note = await self._add_ticket_member(
                ctx.guild,
                record,
                ctx.author,
                member,
            )
        except commands.CommandError as error:
            await ctx.send(str(error))
            return
        await ctx.send(f"{member.mention} added to ticket #{record['id']}.{note}")

    @tickethub.command(name="removemember")
    @commands.guild_only()
    async def tickethub_remove_member(
        self,
        ctx: commands.Context,
        member: discord.Member,
        ticket_id: int | None = None,
    ) -> None:
        """Remove a member from a ticket."""
        assert ctx.guild is not None
        if not isinstance(ctx.author, discord.Member):
            return
        try:
            _key, record = await self._resolve_ticket_argument(ctx, ticket_id)
            await self._remove_ticket_member(
                ctx.guild,
                record,
                ctx.author,
                member,
            )
        except commands.CommandError as error:
            await ctx.send(str(error))
            return
        await ctx.send(f"{member.mention} removed from ticket #{record['id']}.")

    @tickethub.command(name="list")
    @commands.guild_only()
    async def tickethub_list(
        self,
        ctx: commands.Context,
        status: str = "open",
        owner: discord.Member | None = None,
    ) -> None:
        """List tracked tickets."""
        assert ctx.guild is not None
        status = status.lower()
        if status not in {"open", "claimed", "unclaimed", "closed", "all"}:
            await ctx.send(
                "Status must be `open`, `claimed`, `unclaimed`, `closed`, or `all`.",
            )
            return
        tickets = await self.config.guild(ctx.guild).tickets()
        records = list(tickets.values())
        if status in {"open", "closed"}:
            records = [record for record in records if record.get(
                "status") == status]
        elif status == "claimed":
            records = [
                record
                for record in records
                if record.get("status") == "open" and record.get("claimed_by")
            ]
        elif status == "unclaimed":
            records = [
                record
                for record in records
                if record.get("status") == "open" and not record.get("claimed_by")
            ]
        if owner is not None:
            records = [
                record
                for record in records
                if str(record.get("owner_id")) == str(owner.id)
            ]
        records.sort(key=lambda record: int(
            record.get("id") or 0), reverse=True)
        if not records:
            await ctx.send("No tickets matched that filter.")
            return
        lines = []
        for record in records[:100]:
            channel = await self._fetch_ticket_channel(ctx.guild, record)
            profile = await self._get_profile(
                ctx.guild,
                str(record.get("profile") or "main"),
            )
            is_owner = ctx.author.id == int(record.get("owner_id") or 0)
            can_view_channel = (
                channel is not None and channel.permissions_for(
                    ctx.author).view_channel
            )
            if (
                not is_owner
                and not self._is_support_member(ctx.author, profile)
                and not can_view_channel
            ):
                continue
            profile_ticket_id = record.get(
                "profile_ticket_id") or record.get("id")
            lines.append(
                f"#{record.get('id')} | `{record.get('profile')}` #{profile_ticket_id} "
                f"| {record.get('status')} | {self._user_ref(record.get('owner_id'))} "
                f"| {'locked | ' if record.get('locked') else ''}"
                f"{channel.mention if channel else 'missing location'}",
            )
        if not lines:
            await ctx.send("No tickets matched that filter that you can view.")
            return
        for page in pagify("\n".join(lines), page_length=1800):
            await ctx.send(box(page))

    @tickethub.command(name="show", aliases=["info"])
    @commands.guild_only()
    async def tickethub_show(
        self,
        ctx: commands.Context,
        ticket_id: int | None = None,
    ) -> None:
        """Show the stored details for a ticket."""
        assert ctx.guild is not None
        if not isinstance(ctx.author, discord.Member):
            return
        try:
            _key, record = await self._resolve_ticket_argument(ctx, ticket_id)
            profile = await self._get_profile(
                ctx.guild,
                str(record.get("profile") or "main"),
            )
            if not self._is_support_member(
                ctx.author,
                profile,
            ) and ctx.author.id != int(
                record.get("owner_id") or 0,
            ):
                raise commands.CommandError(
                    "You cannot view that ticket's details.")
        except commands.CommandError as error:
            await ctx.send(str(error))
            return
        await ctx.send(embed=self._ticket_embed(ctx.guild, record, profile))

    @tickethub_set.group(name="data", invoke_without_command=True)
    @commands.admin_or_permissions(manage_guild=True)
    async def tickethub_import(self, ctx: commands.Context) -> None:
        """Import or export TicketHub data."""
        await ctx.send_help(ctx.command)

    async def _get_aaa3a_profiles(self, guild: discord.Guild) -> dict[str, Any]:
        aaa_cog = self.bot.get_cog("Tickets")
        if aaa_cog is None or not hasattr(aaa_cog, "config"):
            raise commands.CommandError(
                "AAA3A's `Tickets` cog is not loaded, so I cannot read its config.",
            )
        try:
            aaa_profiles = await aaa_cog.config.guild(guild).profiles()
        except RECOVERABLE_EXCEPTIONS as exc:
            raise commands.CommandError(
                "I could not read AAA3A Tickets profile settings.",
            ) from exc
        if not isinstance(aaa_profiles, dict):
            raise commands.CommandError(
                "I could not read AAA3A Tickets profile settings.",
            )
        return aaa_profiles

    @tickethub_import.command(name="importaaa3a")
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
            mapped_profile, summary = await self._build_aaa3a_import(
                ctx.guild,
                aaa3a_profile,
            )
            panel_records = await self._collect_aaa3a_panel_records(ctx.guild)
        except commands.CommandError as error:
            await ctx.send(str(error))
            return
        target_profile = self._clean_name(aaa3a_profile)
        panel_count = len(panel_records)
        button_count = sum(
            len(record.get("buttons") or {}) for record in panel_records.values()
        )
        dropdown_count = sum(
            len(record.get("dropdown_options") or {})
            for record in panel_records.values()
        )
        if panel_count:
            summary.append(
                "- buttons_dropdowns -> aaa3a_panels: "
                f"{panel_count} panel message(s), {button_count} button(s), "
                f"{dropdown_count} dropdown option(s)",
            )
        else:
            summary.append("- buttons_dropdowns -> aaa3a_panels: none found")
        preview = "\n".join(summary)
        if confirmation.lower() != "confirm":
            await ctx.send(
                "AAA3A Tickets import preview. Nothing has been changed yet.\n"
                f"Run `{self._prefixed_set_root(ctx)} data importaaa3a {aaa3a_profile} confirm` to apply.\n\n"
                + box(preview[:1800]),
            )
            return
        await self._set_profile(ctx.guild, target_profile, mapped_profile)
        saved_panels = await self._set_aaa3a_panel_records(ctx.guild, panel_records)
        await self.config.guild(ctx.guild).enabled.set(True)
        panel_note = (
            f" Imported {len(saved_panels)} existing AAA3A panel message(s)."
            if saved_panels
            else ""
        )
        await ctx.send(
            f"Imported AAA3A Tickets profile `{aaa3a_profile}` into TicketHub "
            f"profile `{target_profile}`.{panel_note}",
        )

    @tickethub_import.command(name="import-aaa3a", hidden=True)
    @commands.admin_or_permissions(manage_guild=True)
    async def tickethub_import_aaa3a_legacy(
        self,
        ctx: commands.Context,
        aaa3a_profile: str = "main",
        confirmation: str = "",
    ) -> None:
        """Keep the historical prefix and slash subcommand name working."""
        await self.tickethub_import_aaa3a.callback(
            self,
            ctx,
            aaa3a_profile,
            confirmation,
        )

    @tickethub_import.command(name="importaaa3aall")
    @commands.admin_or_permissions(manage_guild=True)
    async def tickethub_import_aaa3a_all(
        self,
        ctx: commands.Context,
        confirmation: str = "",
    ) -> None:
        """Import every profile from AAA3A's Tickets cog. Use `confirm` to apply."""
        assert ctx.guild is not None
        try:
            aaa_profiles = await self._get_aaa3a_profiles(ctx.guild)
            panel_records = await self._collect_aaa3a_panel_records(ctx.guild)
            mapped_profiles: dict[str, ProfileRecord] = {}
            profile_mappings: list[tuple[str, str]] = []
            for aaa3a_profile in sorted(aaa_profiles):
                target_profile = self._clean_name(aaa3a_profile)
                if target_profile in mapped_profiles:
                    raise commands.CommandError(
                        "Multiple AAA3A profiles resolve to the same TicketHub profile "
                        f"name `{target_profile}`. Rename one in AAA3A before importing all.",
                    )
                mapped_profile, _summary = await self._build_aaa3a_import(
                    ctx.guild,
                    aaa3a_profile,
                )
                mapped_profiles[target_profile] = mapped_profile
                profile_mappings.append((aaa3a_profile, target_profile))
        except commands.CommandError as error:
            await ctx.send(str(error))
            return
        if not mapped_profiles:
            await ctx.send("AAA3A Tickets has no profiles to import.")
            return

        panel_count = len(panel_records)
        button_count = sum(
            len(record.get("buttons") or {}) for record in panel_records.values()
        )
        dropdown_count = sum(
            len(record.get("dropdown_options") or {})
            for record in panel_records.values()
        )
        preview_lines = [
            "AAA3A Tickets import-all preview. Nothing has been changed yet.",
            f"Profiles to import: {len(mapped_profiles)}",
            "Profile mappings:",
        ]
        preview_lines.extend(
            f"- {source_name} -> {target_name}"
            for source_name, target_name in profile_mappings
        )
        preview_lines.append(
            "Panel routing: "
            f"{panel_count} panel message(s), {button_count} button(s), "
            f"{dropdown_count} dropdown option(s)",
        )
        preview_lines.append(
            f"Run `{self._prefixed_set_root(ctx)} data importaaa3aall confirm` to apply.",
        )
        if confirmation.lower() != "confirm":
            for page in pagify("\n".join(preview_lines), page_length=1800):
                await ctx.send(box(page))
            return

        async with self.config.guild(ctx.guild).profiles() as profiles:
            for target_profile, mapped_profile in mapped_profiles.items():
                profiles[target_profile] = mapped_profile
        saved_panels = await self._set_aaa3a_panel_records(ctx.guild, panel_records)
        await self.config.guild(ctx.guild).enabled.set(True)
        await ctx.send(
            f"Imported {len(mapped_profiles)} AAA3A Tickets profile(s) into "
            f"TicketHub. Imported {len(saved_panels)} existing AAA3A panel message(s).",
        )

    @tickethub_import.command(name="import-aaa3a-all", hidden=True)
    @commands.admin_or_permissions(manage_guild=True)
    async def tickethub_import_aaa3a_all_legacy(
        self,
        ctx: commands.Context,
        confirmation: str = "",
    ) -> None:
        """Keep the historical prefix and slash subcommand name working."""
        await self.tickethub_import_aaa3a_all.callback(
            self,
            ctx,
            confirmation,
        )

    async def _build_aaa3a_import(
        self,
        guild: discord.Guild,
        aaa3a_profile: str,
    ) -> tuple[ProfileRecord, list[str]]:
        aaa_profiles = await self._get_aaa3a_profiles(guild)
        if aaa3a_profile not in aaa_profiles:
            available = ", ".join(sorted(aaa_profiles)) or "none"
            raise commands.CommandError(
                f"AAA3A profile `{aaa3a_profile}` was not found. Available: {available}",
            )

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
            "owner_can_add_members": "owner_can_add_members",
            "owner_can_remove_members": "owner_can_remove_members",
            "close_on_leave": "close_on_leave",
            "ticket_role": "ticket_role_id",
            "support_roles": "support_role_ids",
            "speak_roles": "speak_role_ids",
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
                "speak_roles",
                "view_roles",
                "ping_roles",
                "whitelist_roles",
                "blacklist_roles",
            }:
                profile[target_key] = [int(role_id) for role_id in value or []]
            elif source_key == "logs_channel":
                profile[target_key] = int(value) if value else None
                profile["transcript_channel_id"] = int(
                    value) if value else None
            elif source_key in {"category_open", "category_closed"}:
                profile[target_key] = int(value) if value else None
            elif source_key == "channel_name" and not value:
                profile[target_key] = self._default_profile()["channel_name"]
            else:
                profile[target_key] = value
            summary.append(
                f"- {source_key} -> {target_key}: {profile.get(target_key)!r}",
            )

        forum_channel_id = source.get("forum_channel")
        if forum_channel_id:
            try:
                forum_channel = guild.get_channel(int(forum_channel_id))
            except (TypeError, ValueError):
                forum_channel = None
            if isinstance(forum_channel, discord.TextChannel):
                profile["ticket_mode"] = "thread"
                profile["thread_parent_channel_id"] = forum_channel.id
                profile["panel_channel_id"] = (
                    profile.get("panel_channel_id") or forum_channel.id
                )
                summary.append(
                    "- forum_channel -> ticket_mode/thread_parent_channel_id: "
                    f"thread in #{forum_channel.name}",
                )
            else:
                summary.append(
                    "- forum_channel -> thread_parent_channel_id: skipped "
                    "(TicketHub supports text-channel private threads)",
                )

        auto_delete = source.get("auto_delete_on_close")
        profile["auto_delete_on_close_hours"] = auto_delete
        summary.append(
            f"- auto_delete_on_close -> auto_delete_on_close_hours: {auto_delete!r}",
        )
        source_emojis = source.get("emojis") or {}
        control_emojis = dict(profile.get("control_emojis") or {})
        for action in (
            "claim",
            "unclaim",
            "lock",
            "unlock",
            "close",
            "reopen",
            "transcript",
            "delete",
        ):
            if source_emojis.get(action):
                source_emoji = str(source_emojis[action])
                if source_emoji.isdigit():
                    cached_emoji = self.bot.get_emoji(int(source_emoji))
                    if cached_emoji is None:
                        continue
                    source_emoji = str(cached_emoji)
                control_emojis[action] = source_emoji
        profile["control_emojis"] = control_emojis
        summary.append(
            "- emojis -> control_emojis: imported supported controls")
        modal_fields = self._sanitize_modal_fields(
            source.get("creating_modal"))
        uses_default_reason_modal = False
        if modal_fields is None and not source.get("disable_default_open_modal", False):
            modal_fields = self._default_reason_modal()
            uses_default_reason_modal = True
        profile["creating_modal"] = modal_fields
        if uses_default_reason_modal:
            summary.append(
                "- creating_modal -> creating_modal: default reason field")
        elif modal_fields:
            summary.append(
                f"- creating_modal -> creating_modal: {len(modal_fields)} field(s)",
            )
        else:
            summary.append("- creating_modal -> creating_modal: none")
        summary.append(
            "Not imported: existing open ticket records, modlog cases, and forum tags.",
        )
        return profile, summary

    @tickethub_import.command(name="export")
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
                "profile_ticket_id",
                "profile",
                "owner_id",
                "channel_id",
                "location_type",
                "status",
                "claimed_by",
                "locked",
                "locked_by",
                "locked_at",
                "unlocked_by",
                "unlocked_at",
                "created_at",
                "closed_at",
                "closed_by",
                "reopened_at",
                "reopened_by",
                "reason",
                "close_reason",
                "reopen_reason",
            ],
        )
        for record in sorted(
            tickets.values(),
            key=lambda item: int(item.get("id") or 0),
        ):
            writer.writerow(
                [
                    record.get("id"),
                    record.get("profile_ticket_id"),
                    record.get("profile"),
                    record.get("owner_id"),
                    record.get("channel_id"),
                    record.get("location_type") or "channel",
                    record.get("status"),
                    record.get("claimed_by"),
                    bool(record.get("locked")),
                    record.get("locked_by"),
                    self._format_export_time(record.get("locked_at")),
                    record.get("unlocked_by"),
                    self._format_export_time(record.get("unlocked_at")),
                    self._format_export_time(record.get("created_at")),
                    self._format_export_time(record.get("closed_at")),
                    record.get("closed_by"),
                    self._format_export_time(record.get("reopened_at")),
                    record.get("reopened_by"),
                    record.get("reason"),
                    record.get("close_reason"),
                    record.get("reopen_reason"),
                ],
            )
        file = discord.File(
            io.BytesIO(output.getvalue().encode("utf-8")),
            filename=f"tickethub-{ctx.guild.id}.csv",
        )
        await ctx.send("TicketHub export:", file=file)
