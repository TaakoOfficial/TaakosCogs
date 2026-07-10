"""ReviewHub-style reviews and vouches for Red-DiscordBot."""

from __future__ import annotations

import asyncio
import contextlib
import csv
import io
import logging
import re
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING, Any

import discord
from redbot.core import Config, app_commands, commands

from .dashboard_integration import DashboardIntegration

if TYPE_CHECKING:
    from redbot.core.bot import Red

log = logging.getLogger("red.taakoscogs.reviewhub")


ReviewRecord = dict[str, Any]
RequestRecord = dict[str, Any]
StatsRecord = dict[str, Any]
MODAL_SELECTS_SUPPORTED = hasattr(discord.ui, "Label")


class ReviewSubmitModal(discord.ui.Modal):
    """Modal used by slash commands and submit-review buttons."""

    def __init__(
        self,
        cog: ReviewHub,
        guild_id: int,
        reviewer_id: int,
        *,
        target_id: int | None = None,
        request_message_id: int | None = None,
        mode_override: str | None = None,
        title: str = "Rate your experience",
    ) -> None:
        super().__init__(title=title[:45]
              or "Rate your experience", timeout=300.0)
        self.cog = cog
        self.guild_id = guild_id
        self.reviewer_id = reviewer_id
        self.target_id = target_id
        self.request_message_id = request_message_id
        self.mode_override = mode_override

        if MODAL_SELECTS_SUPPORTED:
            self.rating = discord.ui.Select(
                placeholder="Choose a rating",
                options=[
                    discord.SelectOption(
                        label=f"{rating} star{'s' if rating != 1 else ''}",
                        value=str(rating),
                    )
                    for rating in range(5, 0, -1)
                ],
                min_values=1,
                max_values=1,
                required=True,
            )
        else:
            self.rating = discord.ui.TextInput(
                label="Rating (1-5)",
                placeholder="5",
                min_length=1,
                max_length=1,
                required=True,
                style=discord.TextStyle.short,
            )
        self.review = discord.ui.TextInput(
            label=None if MODAL_SELECTS_SUPPORTED else "Review",
            placeholder="Share the feedback you want posted.",
            max_length=ReviewHub.MAX_REVIEW_LENGTH,
            required=True,
            style=discord.TextStyle.paragraph,
        )
        if MODAL_SELECTS_SUPPORTED:
            self.add_item(
                discord.ui.Label(
                    text="Rating",
                    description="Choose a score from 1 to 5 stars.",
                    component=self.rating,
                ),
            )
            self.add_item(
                discord.ui.Label(
                    text="Review",
                    component=self.review,
                ),
            )
        else:
            self.add_item(self.rating)
            self.add_item(self.review)

    async def on_submit(self, interaction: discord.Interaction) -> None:
        guild = interaction.guild
        if guild is None or guild.id != self.guild_id:
            await interaction.response.send_message(
                "This review form only works in its server.",
                ephemeral=True,
            )
            return
        if not isinstance(interaction.user, discord.Member):
            await interaction.response.send_message(
                "This review form only works for server members.",
                ephemeral=True,
            )
            return
        if interaction.user.id != self.reviewer_id:
            await interaction.response.send_message(
                "This review form is not for you.",
                ephemeral=True,
            )
            return

        rating_value = (
            self.rating.values[0]
            if isinstance(self.rating, discord.ui.Select) and self.rating.values
            else getattr(self.rating, "value", "")
        )
        try:
            rating = int(str(rating_value).strip())
        except ValueError:
            await interaction.response.send_message(
                "Rating must be a number from 1 to 5.",
                ephemeral=True,
            )
            return

        target = guild.get_member(self.target_id) if self.target_id else None
        await interaction.response.defer(ephemeral=True, thinking=True)
        try:
            record, _settings, message = await self.cog._create_review(
                guild,
                interaction.user,
                rating,
                str(self.review.value),
                target=target,
                source_channel=interaction.channel,
                request_message_id=self.request_message_id,
                mode_override=self.mode_override,
            )
        except commands.CommandError as error:
            await interaction.followup.send(str(error), ephemeral=True)
            return

        await self.cog._send_submit_result(interaction, record, message)

    async def on_error(
        self,
        interaction: discord.Interaction,
        error: Exception,
    ) -> None:
        log.exception(
            "ReviewHub review modal failed.",
            exc_info=(type(error), error, error.__traceback__),
        )
        if interaction.response.is_done():
            await interaction.followup.send(
                "I could not submit that review.",
                ephemeral=True,
            )
            return
        await interaction.response.send_message(
            "I could not submit that review.",
            ephemeral=True,
        )


class ReviewPublicView(discord.ui.View):
    """Persistent buttons attached to public review messages."""

    SUBMIT_ID = "taakoscogs:reviewhub:submit-public"
    REPORT_ID = "taakoscogs:reviewhub:report"
    USEFUL_ID = "taakoscogs:reviewhub:useful"

    def __init__(
        self,
        cog: ReviewHub,
        settings: dict[str, Any] | None = None,
        *,
        include_submit: bool = True,
        include_report: bool = True,
        include_useful: bool = True,
    ) -> None:
        super().__init__(timeout=None)
        self.cog = cog
        settings = settings or {}

        if include_submit:
            button = discord.ui.Button(
                label=str(settings.get("review_button_label")
                          or "Submit Review")[:80],
                emoji=str(settings.get("submit_review_emoji")
                          or "\N{MEMO}")[:100],
                style=discord.ButtonStyle.primary,
                custom_id=self.SUBMIT_ID,
            )
            button.callback = self._submit_callback
            self.add_item(button)

        if include_report:
            button = discord.ui.Button(
                label="Report",
                emoji=str(settings.get("report_button_emoji") or "\N{WARNING SIGN}")[
                    :100
                ],
                style=discord.ButtonStyle.danger,
                custom_id=self.REPORT_ID,
            )
            button.callback = self._report_callback
            self.add_item(button)

        if include_useful:
            button = discord.ui.Button(
                label="Useful",
                emoji=str(settings.get("useful_button_emoji") or "\N{THUMBS UP SIGN}")[
                    :100
                ],
                style=discord.ButtonStyle.secondary,
                custom_id=self.USEFUL_ID,
            )
            button.callback = self._useful_callback
            self.add_item(button)

    async def _submit_callback(self, interaction: discord.Interaction) -> None:
        await self.cog.handle_public_submit(interaction)

    async def _report_callback(self, interaction: discord.Interaction) -> None:
        await self.cog.handle_report_button(interaction)

    async def _useful_callback(self, interaction: discord.Interaction) -> None:
        await self.cog.handle_useful_button(interaction)


class ReviewRequestView(discord.ui.View):
    """Persistent button attached to /rateme request messages."""

    SUBMIT_ID = "taakoscogs:reviewhub:submit-request"

    def __init__(self, cog: ReviewHub, settings: dict[str, Any] | None = None) -> None:
        super().__init__(timeout=None)
        self.cog = cog
        settings = settings or {}
        button = discord.ui.Button(
            label=str(settings.get("review_button_label")
                      or "Submit Review")[:80],
            emoji=str(settings.get("submit_review_emoji") or "\N{MEMO}")[:100],
            style=discord.ButtonStyle.primary,
            custom_id=self.SUBMIT_ID,
        )
        button.callback = self._submit_callback
        self.add_item(button)

    async def _submit_callback(self, interaction: discord.Interaction) -> None:
        await self.cog.handle_request_submit(interaction)


class ReviewTargetPickerView(discord.ui.View):
    """Ephemeral target picker shown before opening a public review modal."""

    def __init__(
        self,
        cog: ReviewHub,
        guild_id: int,
        reviewer_id: int,
        settings: dict[str, Any],
    ) -> None:
        super().__init__(timeout=300)
        self.cog = cog
        self.guild_id = guild_id
        self.reviewer_id = reviewer_id
        self.settings = settings
        self.add_item(ReviewTargetSelect(self))

    async def _send_modal(
        self,
        interaction: discord.Interaction,
        *,
        target_id: int | None = None,
    ) -> None:
        if not interaction.guild or interaction.guild.id != self.guild_id:
            await interaction.response.send_message(
                "This picker only works in its server.",
                ephemeral=True,
            )
            return
        if not isinstance(interaction.user, discord.Member):
            await interaction.response.send_message(
                "This picker only works for server members.",
                ephemeral=True,
            )
            return
        if interaction.user.id != self.reviewer_id:
            await interaction.response.send_message(
                "This picker is not for you.",
                ephemeral=True,
            )
            return
        title = str(
            self.settings.get(
                "rate_experience_title") or "Rate your experience",
        )
        await interaction.response.send_modal(
            ReviewSubmitModal(
                self.cog,
                self.guild_id,
                self.reviewer_id,
                target_id=target_id,
                title=title,
            ),
        )

    @discord.ui.button(label="No specific person", style=discord.ButtonStyle.secondary)
    async def skip_target(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ) -> None:
        await self._send_modal(interaction)


class ReviewTargetSelect(discord.ui.UserSelect):
    """User select used by ReviewTargetPickerView."""

    def __init__(self, view: ReviewTargetPickerView) -> None:
        super().__init__(
            placeholder="Choose the person this review is about",
            min_values=1,
            max_values=1,
        )
        self.picker_view = view

    async def callback(self, interaction: discord.Interaction) -> None:
        if not interaction.guild or not isinstance(interaction.user, discord.Member):
            await interaction.response.send_message(
                "This picker only works in a server.",
                ephemeral=True,
            )
            return
        if interaction.user.id != self.picker_view.reviewer_id:
            await interaction.response.send_message(
                "This picker is not for you.",
                ephemeral=True,
            )
            return
        selected = self.values[0] if self.values else None
        target = selected if isinstance(selected, discord.Member) else None
        if target is None and selected is not None:
            target = interaction.guild.get_member(int(selected.id))
        if target is None:
            await interaction.response.send_message(
                "I could not find that member in this server.",
                ephemeral=True,
            )
            return
        if target.bot:
            await interaction.response.send_message(
                "Reviews for bot accounts are not supported.",
                ephemeral=True,
            )
            return
        if target.id == interaction.user.id:
            await interaction.response.send_message(
                "You cannot review yourself.",
                ephemeral=True,
            )
            return
        await self.picker_view._send_modal(interaction, target_id=target.id)


class ReviewHubConfigGroup(app_commands.Group):
    """Slash /config group matching ReviewHub's documented command shape."""

    def __init__(self, cog: ReviewHub) -> None:
        super().__init__(name="config", description="Configure ReviewHub settings.")
        self.cog = cog

    async def _is_admin(self, interaction: discord.Interaction) -> bool:
        if not interaction.guild or not isinstance(interaction.user, discord.Member):
            return False
        return bool(interaction.user.guild_permissions.manage_guild)

    async def _require_admin(self, interaction: discord.Interaction) -> bool:
        if await self._is_admin(interaction):
            return True
        await interaction.response.send_message(
            "You need the Manage Server permission to configure ReviewHub.",
            ephemeral=True,
        )
        return False

    @app_commands.command(
        name="server",
        description="Configure ReviewHub channels, threads, and core behavior.",
    )
    @app_commands.describe(
        reviewchannel="Where reviews and vouches are published",
        reportchannel="Where review reports are sent",
        autothread="Auto-create discussion threads on review posts",
        threadtitle="Default thread title, supports {id}, {reviewer}, {target}, and {server}",
        reviewtitle="Custom review embed title",
        ratememessage="Custom /rateme request message",
        reviewrequesttitle="Custom review request embed title",
        rateexperiencetitle="Modal title for rating experiences",
        reviewcommand="Enable or disable review/vouch submissions",
        reviewcommandname="Preferred display command name: review or vouch",
        deletereviewrequests="Delete /rateme request messages after submit",
        vouchmode="Enable recommendation/vouch mode",
        reviewtargets="Allow regular reviews to choose a reviewed member",
    )
    @app_commands.choices(
        reviewcommandname=[
            app_commands.Choice(name="review", value="review"),
            app_commands.Choice(name="vouch", value="vouch"),
        ],
    )
    @app_commands.guild_only()
    async def server(
        self,
        interaction: discord.Interaction,
        reviewchannel: discord.TextChannel | None = None,
        reportchannel: discord.TextChannel | None = None,
        autothread: bool | None = None,
        threadtitle: str | None = None,
        reviewtitle: str | None = None,
        ratememessage: str | None = None,
        reviewrequesttitle: str | None = None,
        rateexperiencetitle: str | None = None,
        reviewcommand: bool | None = None,
        reviewcommandname: str | None = None,
        deletereviewrequests: bool | None = None,
        vouchmode: bool | None = None,
        reviewtargets: bool | None = None,
    ) -> None:
        if not await self._require_admin(interaction):
            return
        assert interaction.guild is not None

        changed: list[str] = []
        guild_conf = self.cog.config.guild(interaction.guild)
        if reviewchannel is not None:
            await guild_conf.review_channel_id.set(reviewchannel.id)
            changed.append(f"review channel -> {reviewchannel.mention}")
        if reportchannel is not None:
            await guild_conf.report_channel_id.set(reportchannel.id)
            changed.append(f"report channel -> {reportchannel.mention}")
        if autothread is not None:
            await guild_conf.auto_thread.set(autothread)
            changed.append(
                f"auto threads -> {self.cog._enabled_text(autothread)}")
        if threadtitle is not None:
            await guild_conf.thread_title.set(threadtitle[:100])
            changed.append("thread title")
        if reviewtitle is not None:
            await guild_conf.review_title.set(reviewtitle[:120])
            changed.append("review title")
        if ratememessage is not None:
            await guild_conf.rateme_message.set(ratememessage[:1000])
            changed.append("/rateme message")
        if reviewrequesttitle is not None:
            await guild_conf.review_request_title.set(reviewrequesttitle[:120])
            changed.append("request title")
        if rateexperiencetitle is not None:
            await guild_conf.rate_experience_title.set(rateexperiencetitle[:45])
            changed.append("rate experience title")
        if reviewcommand is not None:
            await guild_conf.review_command_enabled.set(reviewcommand)
            changed.append(
                f"review command -> {self.cog._enabled_text(reviewcommand)}")
        if reviewcommandname is not None:
            await guild_conf.review_command_name.set(reviewcommandname)
            changed.append(f"display command name -> {reviewcommandname}")
        if deletereviewrequests is not None:
            await guild_conf.delete_review_requests.set(deletereviewrequests)
            changed.append(
                f"delete requests -> {self.cog._enabled_text(deletereviewrequests)}",
            )
        if vouchmode is not None:
            await guild_conf.vouch_mode.set(vouchmode)
            changed.append(
                f"vouch mode -> {self.cog._enabled_text(vouchmode)}")
        if reviewtargets is not None:
            await guild_conf.review_targets_enabled.set(reviewtargets)
            changed.append(
                f"review targets -> {self.cog._enabled_text(reviewtargets)}")

        if not changed:
            await interaction.response.send_message(
                embed=await self.cog._settings_embed(interaction.guild),
                ephemeral=True,
            )
            return
        await interaction.response.send_message(
            "Updated: " + ", ".join(changed) + ".",
            ephemeral=True,
        )

    @app_commands.command(
        name="appearance",
        description="Configure ReviewHub buttons and review templates.",
    )
    @app_commands.describe(
        reviewbuttonshow="Show or hide the submit review button",
        reportbuttonshow="Show or hide the report button",
        usefulbuttonshow="Show or hide the useful button",
        reviewtemplate="Review embed layout style",
        reviewembedcolor="Review embed color as hex, e.g. #5865F2",
        reviewbuttonlabel="Submit review button label",
        staremoji="Star emoji used for ratings",
        reviewauthortext="Embed author text, supports {user} and {server}",
        reportbuttonemoji="Report button emoji",
        submitreviewemoji="Submit review button emoji",
        usefulbuttonemoji="Useful button emoji",
    )
    @app_commands.choices(
        reviewtemplate=[
            app_commands.Choice(name="Classic", value="classic"),
            app_commands.Choice(name="Detailed", value="detailed"),
        ],
    )
    @app_commands.guild_only()
    async def appearance(
        self,
        interaction: discord.Interaction,
        reviewbuttonshow: bool | None = None,
        reportbuttonshow: bool | None = None,
        usefulbuttonshow: bool | None = None,
        reviewtemplate: str | None = None,
        reviewembedcolor: str | None = None,
        reviewbuttonlabel: str | None = None,
        staremoji: str | None = None,
        reviewauthortext: str | None = None,
        reportbuttonemoji: str | None = None,
        submitreviewemoji: str | None = None,
        usefulbuttonemoji: str | None = None,
    ) -> None:
        if not await self._require_admin(interaction):
            return
        assert interaction.guild is not None

        changed: list[str] = []
        guild_conf = self.cog.config.guild(interaction.guild)
        if reviewbuttonshow is not None:
            await guild_conf.review_button_show.set(reviewbuttonshow)
            changed.append(
                f"submit button -> {self.cog._enabled_text(reviewbuttonshow)}",
            )
        if reportbuttonshow is not None:
            await guild_conf.report_button_show.set(reportbuttonshow)
            changed.append(
                f"report button -> {self.cog._enabled_text(reportbuttonshow)}",
            )
        if usefulbuttonshow is not None:
            await guild_conf.useful_button_show.set(usefulbuttonshow)
            changed.append(
                f"useful button -> {self.cog._enabled_text(usefulbuttonshow)}",
            )
        if reviewtemplate is not None:
            await guild_conf.review_template.set(reviewtemplate)
            changed.append(f"template -> {reviewtemplate.title()}")
        if reviewembedcolor is not None:
            try:
                color = self.cog._parse_color(reviewembedcolor)
            except commands.BadArgument as error:
                await interaction.response.send_message(str(error), ephemeral=True)
                return
            await guild_conf.review_embed_color.set(color)
            changed.append(f"embed color -> #{color:06X}")
        if reviewbuttonlabel is not None:
            await guild_conf.review_button_label.set(reviewbuttonlabel[:80])
            changed.append("submit button label")
        if staremoji is not None:
            await guild_conf.star_emoji.set(staremoji[:100])
            changed.append("star emoji")
        if reviewauthortext is not None:
            await guild_conf.review_author_text.set(reviewauthortext[:120])
            changed.append("author text")
        if reportbuttonemoji is not None:
            await guild_conf.report_button_emoji.set(reportbuttonemoji[:100])
            changed.append("report emoji")
        if submitreviewemoji is not None:
            await guild_conf.submit_review_emoji.set(submitreviewemoji[:100])
            changed.append("submit emoji")
        if usefulbuttonemoji is not None:
            await guild_conf.useful_button_emoji.set(usefulbuttonemoji[:100])
            changed.append("useful emoji")

        if not changed:
            await interaction.response.send_message(
                embed=await self.cog._settings_embed(interaction.guild),
                ephemeral=True,
            )
            return
        await interaction.response.send_message(
            "Updated: " + ", ".join(changed) + ".",
            ephemeral=True,
        )

    @app_commands.command(
        name="access",
        description="Configure ReviewHub command roles.",
    )
    @app_commands.describe(
        ratemerole="Role allowed to use /rateme",
        ratemeroleclear="Remove the /rateme role requirement",
        reviewcommandrole="Role allowed to submit reviews and vouches",
        reviewcommandroleclear="Remove the review/vouch role requirement",
    )
    @app_commands.guild_only()
    async def access(
        self,
        interaction: discord.Interaction,
        ratemerole: discord.Role | None = None,
        ratemeroleclear: bool | None = None,
        reviewcommandrole: discord.Role | None = None,
        reviewcommandroleclear: bool | None = None,
    ) -> None:
        if not await self._require_admin(interaction):
            return
        assert interaction.guild is not None

        changed: list[str] = []
        guild_conf = self.cog.config.guild(interaction.guild)
        if ratemeroleclear:
            await guild_conf.rateme_role_id.set(None)
            changed.append("/rateme role cleared")
        elif ratemerole is not None:
            await guild_conf.rateme_role_id.set(ratemerole.id)
            changed.append(f"/rateme role -> {ratemerole.mention}")
        if reviewcommandroleclear:
            await guild_conf.review_command_role_id.set(None)
            changed.append("review command role cleared")
        elif reviewcommandrole is not None:
            await guild_conf.review_command_role_id.set(reviewcommandrole.id)
            changed.append(
                f"review command role -> {reviewcommandrole.mention}")

        if not changed:
            await interaction.response.send_message(
                embed=await self.cog._settings_embed(interaction.guild),
                ephemeral=True,
            )
            return
        await interaction.response.send_message(
            "Updated: " + ", ".join(changed) + ".",
            ephemeral=True,
        )


class ReviewHub(DashboardIntegration, commands.Cog):
    """Collect reviews and vouches with ReviewHub-style commands."""

    CONFIG_IDENTIFIER = 2026051601
    DEFAULT_COLOR = 0x5865F2
    DELETED_COLOR = 0xED4245
    REQUEST_COLOR = 0xFEE75C
    MAX_REVIEW_LENGTH = 1000
    DAILY_LIMIT = 5
    UTC_PLUS_TWO = timezone(timedelta(hours=2))

    def __init__(self, bot: Red) -> None:
        self.bot = bot
        self.config = Config.get_conf(
            self,
            identifier=self.CONFIG_IDENTIFIER,
            force_registration=True,
        )
        self.config.register_guild(
            review_channel_id=None,
            report_channel_id=None,
            review_button_show=True,
            report_button_show=True,
            useful_button_show=True,
            review_template="classic",
            rateme_role_id=None,
            review_command_role_id=None,
            auto_thread=False,
            thread_title="Review {id} discussion",
            review_title="New Review",
            review_embed_color=self.DEFAULT_COLOR,
            rateme_message="{reviewer}, {requester} requested a review from you.",
            review_request_title="Review Request",
            rate_experience_title="Rate your experience",
            review_button_label="Submit Review",
            review_command_enabled=True,
            review_command_name="review",
            star_emoji="\N{WHITE MEDIUM STAR}",
            review_author_text="{user} submitted a review",
            delete_review_requests=True,
            vouch_mode=False,
            review_targets_enabled=False,
            report_button_emoji="\N{WARNING SIGN}",
            submit_review_emoji="\N{MEMO}",
            useful_button_emoji="\N{THUMBS UP SIGN}",
            daily_limit=self.DAILY_LIMIT,
            daily_key=None,
            daily_count=0,
            next_review_id=1,
            next_request_id=1,
            reviews={},
            requests={},
            stats={},
        )
        self._locks: dict[int, asyncio.Lock] = {}
        self._public_view = ReviewPublicView(self)
        self._request_view = ReviewRequestView(self)
        self._config_group = ReviewHubConfigGroup(self)
        self._help_command = app_commands.Command(
            name="help",
            description="View all ReviewHub commands and important links.",
            callback=self._slash_help,
        )
        self._registered_app_commands: list[str] = []

    async def cog_load(self) -> None:
        self.bot.add_view(self._public_view)
        self.bot.add_view(self._request_view)

    async def cog_unload(self) -> None:
        for name in self._registered_app_commands:
            self.bot.tree.remove_command(name)

    def register_app_commands(self) -> None:
        """Register optional slash-only commands that should not create prefix commands."""
        self._try_add_app_command(self._config_group)
        self._try_add_app_command(self._help_command)

    def _try_add_app_command(self, command: Any) -> None:
        try:
            self.bot.tree.add_command(command)
        except Exception as exc:
            if exc.__class__.__name__ == "CommandAlreadyRegistered":
                log.warning(
                    "Slash command /%s is already registered; ReviewHub skipped it.",
                    command.name,
                )
                return
            raise
        self._registered_app_commands.append(command.name)

    async def red_delete_data_for_user(self, *, requester: str, user_id: int) -> None:
        """Remove stored review data associated with a Discord user ID."""
        user_key = str(user_id)
        all_guilds = await self.config.all_guilds()
        for guild_id in all_guilds:
            guild_conf = self.config.guild_from_id(guild_id)
            async with guild_conf.reviews() as reviews:
                for record in reviews.values():
                    touched = False
                    if str(record.get("reviewer_id")) == user_key:
                        record["reviewer_id"] = None
                        record["reviewer_removed"] = True
                        touched = True
                    if str(record.get("target_id")) == user_key:
                        record["target_id"] = None
                        record["target_removed"] = True
                        touched = True
                    if str(record.get("deleted_by")) == user_key:
                        record["deleted_by"] = None
                    record["useful_user_ids"] = [
                        voter_id
                        for voter_id in record.get("useful_user_ids", [])
                        if str(voter_id) != user_key
                    ]
                    record["reports"] = [
                        report
                        for report in record.get("reports", [])
                        if str(report.get("reporter_id")) != user_key
                    ]
                    if touched:
                        record["content"] = "[deleted by data request]"
                        record["active"] = False
                        record["deleted_at"] = (
                            record.get("deleted_at") or self._now_ts()
                        )
                        record["delete_reason"] = "Deleted by data request."

            async with guild_conf.requests() as requests:
                for request in requests.values():
                    if str(request.get("requester_id")) == user_key:
                        request["requester_id"] = None
                        request["active"] = False
                    if str(request.get("reviewer_id")) == user_key:
                        request["reviewer_id"] = None
                        request["active"] = False

            reviews = await guild_conf.reviews()
            await guild_conf.stats.set(self._rebuild_stats(reviews))

    def _guild_lock(self, guild_id: int) -> asyncio.Lock:
        return self._locks.setdefault(guild_id, asyncio.Lock())

    @staticmethod
    def _now() -> datetime:
        return datetime.now(timezone.utc)

    @classmethod
    def _now_ts(cls) -> float:
        return cls._now().timestamp()

    @classmethod
    def _daily_key(cls) -> str:
        return cls._now().astimezone(cls.UTC_PLUS_TWO).strftime("%Y-%m-%d")

    @staticmethod
    def _enabled_text(value: bool) -> str:
        return "enabled" if value else "disabled"

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
    def _safe_text(value: Any, fallback: str = "Not set") -> str:
        text = str(value or "").strip()
        return text if text else fallback

    @classmethod
    def _parse_color(cls, value: str) -> int:
        cleaned = value.strip().lower().replace("#", "").replace("0x", "")
        if not re.fullmatch(r"[0-9a-f]{1,6}", cleaned):
            raise commands.BadArgument(
                "Color must be a hex value like `#5865F2`.")
        color = int(cleaned, 16)
        if not 0 <= color <= 0xFFFFFF:
            raise commands.BadArgument(
                "Color must be between `#000000` and `#FFFFFF`.")
        return color

    @staticmethod
    def _channel_from_id(
        guild: discord.Guild,
        channel_id: Any,
    ) -> discord.TextChannel | None:
        if not channel_id:
            return None
        try:
            channel = guild.get_channel(int(channel_id))
        except (TypeError, ValueError):
            return None
        return channel if isinstance(channel, discord.TextChannel) else None

    @staticmethod
    def _role_from_id(guild: discord.Guild, role_id: Any) -> discord.Role | None:
        if not role_id:
            return None
        try:
            return guild.get_role(int(role_id))
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _can_send_embed(channel: discord.TextChannel, member: discord.Member) -> bool:
        permissions = channel.permissions_for(member)
        return bool(permissions.send_messages and permissions.embed_links)

    @staticmethod
    def _has_role(member: discord.Member, role_id: Any) -> bool:
        if not role_id:
            return True
        try:
            wanted = int(role_id)
        except (TypeError, ValueError):
            return True
        return any(role.id == wanted for role in member.roles)

    @staticmethod
    def _is_manager(member: discord.Member) -> bool:
        return bool(member.guild_permissions.manage_guild)

    @classmethod
    def _review_key(cls, review_id: int) -> str:
        return str(int(review_id))

    @classmethod
    def _display_review_id(cls, review_id: Any) -> str:
        try:
            return f"RH-{int(review_id):06d}"
        except (TypeError, ValueError):
            return "RH-000000"

    @classmethod
    def _resolve_review_key(
        cls,
        review_id: str,
        records: dict[str, ReviewRecord],
    ) -> str:
        cleaned = str(review_id).strip().upper()
        if cleaned.startswith("#"):
            cleaned = cleaned[1:]
        if cleaned.startswith("RH-"):
            cleaned = cleaned[3:]
        if cleaned.isdigit():
            key = str(int(cleaned))
            if key in records:
                return key
        lowered = str(review_id).strip().lower()
        for key, record in records.items():
            if str(record.get("display_id", "")).lower() == lowered:
                return key
        raise commands.BadArgument(
            f"No review with ID `{review_id}` was found.")

    @staticmethod
    def _empty_stats() -> StatsRecord:
        return {
            "submitted": 0,
            "received": 0,
            "useful": 0,
        }

    @classmethod
    def _ensure_stats(cls, stats: dict[str, StatsRecord], user_id: Any) -> StatsRecord:
        key = str(user_id)
        record = stats.setdefault(key, cls._empty_stats())
        record.setdefault("submitted", 0)
        record.setdefault("received", 0)
        record.setdefault("useful", 0)
        return record

    @classmethod
    def _active_records(cls, records: dict[str, ReviewRecord]) -> list[ReviewRecord]:
        return [record for record in records.values() if record.get("active", True)]

    @classmethod
    def _rebuild_stats(cls, records: dict[str, ReviewRecord]) -> dict[str, StatsRecord]:
        stats: dict[str, StatsRecord] = {}
        for record in cls._active_records(records):
            reviewer_id = record.get("reviewer_id")
            target_id = record.get("target_id")
            useful_count = len(record.get("useful_user_ids", []))
            if reviewer_id:
                reviewer_stats = cls._ensure_stats(stats, reviewer_id)
                reviewer_stats["submitted"] += 1
                reviewer_stats["useful"] += useful_count
            if target_id:
                target_stats = cls._ensure_stats(stats, target_id)
                target_stats["received"] += 1
        return stats

    @classmethod
    def _rankings(
        cls,
        stats: dict[str, StatsRecord],
        mode: str,
    ) -> list[tuple[int, int]]:
        rows: list[tuple[int, int]] = []
        for user_id, record in stats.items():
            try:
                member_id = int(user_id)
            except (TypeError, ValueError):
                continue
            value = int(record.get(mode) or 0)
            if value > 0:
                rows.append((value, member_id))
        rows.sort(key=lambda item: (item[0], -item[1]), reverse=True)
        return rows

    @classmethod
    def _normalise_leaderboard_mode(cls, mode: str) -> str:
        aliases = {
            "active": "submitted",
            "activity": "submitted",
            "submitted": "submitted",
            "reviewed": "submitted",
            "reviews": "submitted",
            "received": "received",
            "vouched": "received",
            "useful": "useful",
            "helpful": "useful",
        }
        lowered = mode.strip().lower()
        if lowered not in aliases:
            raise commands.BadArgument(
                "Mode must be `submitted`, `received`, or `useful`.",
            )
        return aliases[lowered]

    @classmethod
    def _clean_review_text(cls, value: str) -> str:
        cleaned = " ".join(str(value or "").strip().split())
        if not cleaned:
            raise commands.BadArgument("Review text is required.")
        if len(cleaned) > cls.MAX_REVIEW_LENGTH:
            raise commands.BadArgument(
                f"Review text must be {cls.MAX_REVIEW_LENGTH} characters or fewer.",
            )
        return cleaned

    @classmethod
    def _stars(cls, rating: int, settings: dict[str, Any]) -> str:
        star = str(settings.get("star_emoji") or "\N{WHITE MEDIUM STAR}")
        return (star * max(0, min(rating, 5))) or str(rating)

    @staticmethod
    def _quote(value: str) -> str:
        lines = str(value or "").splitlines() or [str(value or "")]
        return "\n".join(f"> {line}" if line else ">" for line in lines)

    @staticmethod
    def _placeholders(
        template: str,
        *,
        guild: discord.Guild,
        reviewer: Any = None,
        target: Any = None,
        record: Any = None,
    ) -> str:
        reviewer_text = getattr(reviewer, "mention", None) or ReviewHub._user_ref(
            getattr(reviewer, "id", reviewer),
        )
        target_text = getattr(target, "mention", None) or ReviewHub._user_ref(
            getattr(target, "id", target),
        )
        display_id = ""
        if isinstance(record, dict):
            display_id = str(
                record.get("display_id")
                or ReviewHub._display_review_id(record.get("id")),
            )
        return (
            str(template or "")
            .replace("{server}", guild.name)
            .replace("{user}", reviewer_text)
            .replace("{reviewer}", reviewer_text)
            .replace("{target}", target_text)
            .replace("{id}", display_id)
        )

    async def _get_review_channel(
        self,
        guild: discord.Guild,
        settings: dict[str, Any] | None = None,
    ) -> discord.TextChannel | None:
        settings = settings or await self.config.guild(guild).all()
        return self._channel_from_id(guild, settings.get("review_channel_id"))

    async def _get_report_channel(
        self,
        guild: discord.Guild,
        settings: dict[str, Any] | None = None,
    ) -> discord.TextChannel | None:
        settings = settings or await self.config.guild(guild).all()
        return self._channel_from_id(guild, settings.get("report_channel_id"))

    def _review_embed(
        self,
        guild: discord.Guild,
        record: ReviewRecord,
        settings: dict[str, Any],
    ) -> discord.Embed:
        active = bool(record.get("active", True))
        display_id = str(
            record.get("display_id") or self._display_review_id(
                record.get("id")),
        )
        rating = int(record.get("rating") or 0)
        useful_count = len(record.get("useful_user_ids", []))
        title = str(settings.get("review_title") or "New Review")
        if record.get("mode") == "vouch":
            title = title.replace("Review", "Vouch")
        if not active:
            title = f"Deleted {title}"

        template = str(settings.get("review_template") or "classic").lower()
        color = int(settings.get("review_embed_color") or self.DEFAULT_COLOR)
        embed = discord.Embed(
            title=title[:256],
            color=color if active else self.DELETED_COLOR,
            timestamp=self._now(),
        )
        reviewer_text = self._user_ref(record.get("reviewer_id"))
        target_text = self._user_ref(record.get("target_id"))
        content = str(record.get("content") or "")

        author_template = str(
            settings.get("review_author_text") or "{user} submitted a review",
        )
        author_name = self._placeholders(
            author_template,
            guild=guild,
            reviewer=record.get("reviewer_id"),
            target=record.get("target_id"),
            record=record,
        )
        embed.set_author(name=author_name[:256])

        if template == "detailed":
            embed.description = self._quote(content)
            embed.add_field(name="Reviewer", value=reviewer_text, inline=True)
            if record.get("target_id"):
                embed.add_field(name="Target", value=target_text, inline=True)
            embed.add_field(
                name="Rating",
                value=f"{self._stars(rating, settings)} ({rating}/5)",
                inline=True,
            )
            embed.add_field(
                name="Date",
                value=self._format_ts(record.get("created_at"), "F"),
                inline=True,
            )
        else:
            embed.description = content
            embed.add_field(
                name="Rating",
                value=f"{self._stars(rating, settings)} ({rating}/5)",
                inline=True,
            )
            embed.add_field(name="Reviewer", value=reviewer_text, inline=True)
            embed.add_field(
                name="Date",
                value=self._format_ts(record.get("created_at"), "R"),
                inline=True,
            )
            if record.get("target_id"):
                embed.add_field(name="Target", value=target_text, inline=True)

        if useful_count:
            embed.add_field(name="Useful", value=self._count(
                useful_count), inline=True)
        if not active:
            embed.add_field(
                name="Deleted By",
                value=self._user_ref(record.get("deleted_by")),
                inline=True,
            )
            embed.add_field(
                name="Deleted",
                value=self._format_ts(record.get("deleted_at"), "R"),
                inline=True,
            )
            if record.get("delete_reason"):
                embed.add_field(
                    name="Delete Reason",
                    value=str(record["delete_reason"])[:1024],
                    inline=False,
                )
        embed.set_footer(text=f"Review ID: {display_id}")
        return embed

    def _request_embed(
        self,
        guild: discord.Guild,
        requester: discord.Member,
        reviewer: discord.Member,
        settings: dict[str, Any],
    ) -> discord.Embed:
        title = str(settings.get("review_request_title") or "Review Request")
        description = self._placeholders(
            str(
                settings.get("rateme_message")
                or "{reviewer}, {requester} requested a review from you.",
            ),
            guild=guild,
            reviewer=reviewer,
            target=requester,
        ).replace("{requester}", requester.mention)
        embed = discord.Embed(
            title=title[:256],
            description=description[:4096],
            color=self.REQUEST_COLOR,
            timestamp=self._now(),
        )
        embed.add_field(name="Requester", value=requester.mention, inline=True)
        embed.add_field(name="Reviewer", value=reviewer.mention, inline=True)
        embed.set_footer(text="Use the button below to submit a review.")
        return embed

    async def _settings_embed(self, guild: discord.Guild) -> discord.Embed:
        settings = await self.config.guild(guild).all()
        records = settings.get("reviews") or {}
        active_count = len(self._active_records(records))
        review_channel = await self._get_review_channel(guild, settings)
        report_channel = await self._get_report_channel(guild, settings)
        rateme_role = self._role_from_id(guild, settings.get("rateme_role_id"))
        review_role = self._role_from_id(
            guild, settings.get("review_command_role_id"))

        embed = discord.Embed(
            title="ReviewHub Settings",
            color=int(settings.get("review_embed_color")
                      or self.DEFAULT_COLOR),
            timestamp=self._now(),
        )
        embed.add_field(
            name="Status",
            value=(
                f"Submissions: **{self._enabled_text(bool(settings.get('review_command_enabled')))}**\n"
                f"Mode: **{'vouch' if settings.get('vouch_mode') else 'review'}**\n"
                f"Review targets: **{self._enabled_text(bool(settings.get('review_targets_enabled')))}**\n"
                f"Active reviews: **{self._count(active_count)}**"
            ),
            inline=True,
        )
        embed.add_field(
            name="Channels",
            value=(
                f"Reviews: {review_channel.mention if review_channel else 'not set'}\n"
                f"Reports: {report_channel.mention if report_channel else 'not set'}"
            ),
            inline=True,
        )
        embed.add_field(
            name="Access",
            value=(
                f"/rateme: {rateme_role.mention if rateme_role else 'Manage Server'}\n"
                f"Submit: {review_role.mention if review_role else 'everyone'}"
            ),
            inline=True,
        )
        embed.add_field(
            name="Appearance",
            value=(
                f"Template: **{str(settings.get('review_template') or 'classic').title()}**\n"
                f"Buttons: submit {self._enabled_text(bool(settings.get('review_button_show')))}, "
                f"report {self._enabled_text(bool(settings.get('report_button_show')))}, "
                f"useful {self._enabled_text(bool(settings.get('useful_button_show')))}"
            ),
            inline=False,
        )
        return embed

    def _review_view(self, settings: dict[str, Any]) -> discord.ui.View | None:
        include_submit = bool(settings.get("review_button_show"))
        include_report = bool(settings.get("report_button_show"))
        include_useful = bool(settings.get("useful_button_show"))
        if not include_submit and not include_report and not include_useful:
            return None
        return ReviewPublicView(
            self,
            settings,
            include_submit=include_submit,
            include_report=include_report,
            include_useful=include_useful,
        )

    async def _create_review_thread(
        self,
        guild: discord.Guild,
        message: discord.Message,
        record: ReviewRecord,
        settings: dict[str, Any],
    ) -> None:
        if not settings.get("auto_thread"):
            return
        if not isinstance(message.channel, discord.TextChannel):
            return
        me = guild.me
        if me is None:
            return
        permissions = message.channel.permissions_for(me)
        if not getattr(permissions, "create_public_threads", False):
            return
        title_template = str(settings.get("thread_title")
                             or "Review {id} discussion")
        title = self._placeholders(
            title_template,
            guild=guild,
            reviewer=record.get("reviewer_id"),
            target=record.get("target_id"),
            record=record,
        )[:100]
        try:
            await message.create_thread(name=title, auto_archive_duration=1440)
        except discord.HTTPException:
            log.exception(
                "Failed to create ReviewHub thread in guild %s", guild.id)

    async def _store_review_message(
        self,
        guild: discord.Guild,
        record: ReviewRecord,
        message: discord.Message,
        settings: dict[str, Any],
    ) -> None:
        async with self.config.guild(guild).reviews() as reviews:
            key = self._review_key(int(record["id"]))
            stored = reviews.get(key)
            if not stored:
                return
            stored["channel_id"] = message.channel.id
            stored["message_id"] = message.id
            stored["message_jump_url"] = message.jump_url
            reviews[key] = stored
            record.update(stored)
        await self._create_review_thread(guild, message, record, settings)

    async def _send_review_announcement(
        self,
        guild: discord.Guild,
        record: ReviewRecord,
        settings: dict[str, Any],
        source_channel: Any | None,
    ) -> discord.Message | None:
        me = guild.me
        if me is None:
            return None
        channels: list[discord.TextChannel] = []
        review_channel = await self._get_review_channel(guild, settings)
        if review_channel is not None:
            channels.append(review_channel)
        if (
            isinstance(source_channel, discord.TextChannel)
            and source_channel not in channels
        ):
            channels.append(source_channel)

        embed = self._review_embed(guild, record, settings)
        view = self._review_view(settings)
        for channel in channels:
            if not self._can_send_embed(channel, me):
                continue
            try:
                return await channel.send(
                    embed=embed,
                    view=view,
                    allowed_mentions=discord.AllowedMentions.none(),
                )
            except discord.HTTPException:
                log.exception(
                    "Failed to send ReviewHub announcement in guild %s",
                    guild.id,
                )
        return None

    async def _finalize_request_message(
        self,
        guild: discord.Guild,
        request_message_id: int | None,
        settings: dict[str, Any],
    ) -> None:
        if not request_message_id or not settings.get("delete_review_requests"):
            return
        request = (settings.get("requests") or {}).get(str(request_message_id))
        if not request:
            return
        channel = self._channel_from_id(guild, request.get("channel_id"))
        if channel is None:
            return
        try:
            message = await channel.fetch_message(int(request_message_id))
            await message.delete()
        except (discord.NotFound, discord.Forbidden, discord.HTTPException):
            return

    async def _create_review(
        self,
        guild: discord.Guild,
        reviewer: discord.Member,
        rating: int,
        content: str,
        *,
        target: discord.Member | None = None,
        source_channel: Any | None = None,
        request_message_id: int | None = None,
        mode_override: str | None = None,
    ) -> tuple[ReviewRecord, dict[str, Any], discord.Message | None]:
        if rating < 1 or rating > 5:
            raise commands.BadArgument("Rating must be between 1 and 5.")
        cleaned = self._clean_review_text(content)

        async with self._guild_lock(guild.id):
            guild_conf = self.config.guild(guild)
            settings = await guild_conf.all()
            if not settings.get("review_command_enabled"):
                raise commands.CommandError(
                    "Review submissions are disabled here.")
            if not self._has_role(
                reviewer,
                settings.get("review_command_role_id"),
            ) and not self._is_manager(reviewer):
                raise commands.CommandError(
                    "You do not have the configured review command role.",
                )
            mode = mode_override or (
                "vouch" if settings.get("vouch_mode") else "review"
            )
            if mode == "vouch" and target is None:
                raise commands.CommandError(
                    "Choose the member you want to vouch for.")
            targeted_review = (
                target is not None and mode != "vouch" and request_message_id is None
            )
            if targeted_review and not settings.get("review_targets_enabled"):
                raise commands.CommandError(
                    "Targeted reviews are disabled here.")
            if target is not None:
                if target.bot:
                    raise commands.CommandError(
                        "Reviews for bot accounts are not supported.",
                    )
                if target.id == reviewer.id:
                    raise commands.CommandError(
                        "You cannot review or vouch for yourself.",
                    )

            daily_limit = int(settings.get("daily_limit") or 0)
            daily_key = self._daily_key()
            daily_count = int(settings.get("daily_count") or 0)
            if settings.get("daily_key") != daily_key:
                daily_count = 0
                settings["daily_key"] = daily_key
            if daily_limit > 0 and daily_count >= daily_limit:
                raise commands.CommandError(
                    f"This server has reached the daily limit of {daily_limit} "
                    "reviews. The limit resets at midnight UTC+2.",
                )

            review_id = int(settings.get("next_review_id") or 1)
            records: dict[str, ReviewRecord] = settings.get("reviews") or {}
            stats: dict[str, StatsRecord] = settings.get("stats") or {}
            requests: dict[str, RequestRecord] = settings.get("requests") or {}
            record: ReviewRecord = {
                "id": review_id,
                "display_id": self._display_review_id(review_id),
                "mode": mode,
                "reviewer_id": reviewer.id,
                "target_id": target.id if target else None,
                "rating": rating,
                "content": cleaned,
                "active": True,
                "created_at": self._now_ts(),
                "deleted_at": None,
                "deleted_by": None,
                "delete_reason": None,
                "channel_id": None,
                "message_id": None,
                "message_jump_url": None,
                "useful_user_ids": [],
                "reports": [],
                "request_message_id": request_message_id,
            }
            records[self._review_key(review_id)] = record
            reviewer_stats = self._ensure_stats(stats, reviewer.id)
            reviewer_stats["submitted"] = int(
                reviewer_stats.get("submitted") or 0) + 1
            if target is not None:
                target_stats = self._ensure_stats(stats, target.id)
                target_stats["received"] = int(
                    target_stats.get("received") or 0) + 1
            if request_message_id and str(request_message_id) in requests:
                requests[str(request_message_id)]["active"] = False
                requests[str(request_message_id)
                             ]["submitted_review_id"] = review_id

            await guild_conf.reviews.set(records)
            await guild_conf.stats.set(stats)
            await guild_conf.requests.set(requests)
            await guild_conf.next_review_id.set(review_id + 1)
            await guild_conf.daily_key.set(daily_key)
            await guild_conf.daily_count.set(daily_count + 1)
            settings["reviews"] = records
            settings["stats"] = stats
            settings["requests"] = requests
            settings["next_review_id"] = review_id + 1
            settings["daily_key"] = daily_key
            settings["daily_count"] = daily_count + 1

        message = await self._send_review_announcement(
            guild,
            record,
            settings,
            source_channel,
        )
        if message is not None:
            await self._store_review_message(guild, record, message, settings)
        await self._finalize_request_message(guild, request_message_id, settings)
        return record, settings, message

    async def _delete_review(
        self,
        guild: discord.Guild,
        review_id: str,
        moderator: discord.Member,
        reason: str | None,
    ) -> tuple[ReviewRecord, dict[str, Any]]:
        async with self._guild_lock(guild.id):
            guild_conf = self.config.guild(guild)
            settings = await guild_conf.all()
            records: dict[str, ReviewRecord] = settings.get("reviews") or {}
            key = self._resolve_review_key(review_id, records)
            record = records[key]
            if not record.get("active", True):
                raise commands.BadArgument(
                    f"Review `{review_id}` is already deleted.")
            record["active"] = False
            record["deleted_at"] = self._now_ts()
            record["deleted_by"] = moderator.id
            record["delete_reason"] = (reason or "No reason provided.")[:300]
            records[key] = record
            stats = self._rebuild_stats(records)
            await guild_conf.reviews.set(records)
            await guild_conf.stats.set(stats)
            settings["reviews"] = records
            settings["stats"] = stats

        await self._sync_review_message(guild, record, settings)
        return record, settings

    async def _sync_review_message(
        self,
        guild: discord.Guild,
        record: ReviewRecord,
        settings: dict[str, Any] | None = None,
    ) -> None:
        settings = settings or await self.config.guild(guild).all()
        channel = self._channel_from_id(guild, record.get("channel_id"))
        message_id = record.get("message_id")
        if channel is None or not message_id:
            return
        try:
            message = await channel.fetch_message(int(message_id))
            view = self._review_view(settings) if record.get(
                "active", True) else None
            await message.edit(
                embed=self._review_embed(guild, record, settings),
                view=view,
            )
        except (discord.NotFound, discord.Forbidden, discord.HTTPException):
            return

    async def _send_submit_result(
        self,
        interaction: discord.Interaction,
        record: ReviewRecord,
        message: discord.Message | None,
    ) -> None:
        display_id = str(
            record.get("display_id") or self._display_review_id(
                record.get("id")),
        )
        if message is None:
            await interaction.followup.send(
                f"Review `{display_id}` was recorded, but I could not post it to a channel.",
                ephemeral=True,
            )
            return
        await interaction.followup.send(
            f"Review `{display_id}` posted: {message.jump_url}",
            ephemeral=True,
        )

    async def handle_public_submit(self, interaction: discord.Interaction) -> None:
        if not interaction.guild or not isinstance(interaction.user, discord.Member):
            await interaction.response.send_message(
                "This button only works in a server.",
                ephemeral=True,
            )
            return
        settings = await self.config.guild(interaction.guild).all()
        if settings.get("vouch_mode"):
            await interaction.response.send_message(
                "Use `/vouch` and choose a member to submit a vouch.",
                ephemeral=True,
            )
            return
        if settings.get("review_targets_enabled"):
            await interaction.response.send_message(
                "Choose who this review is about, or continue without a specific person.",
                view=ReviewTargetPickerView(
                    self,
                    interaction.guild.id,
                    interaction.user.id,
                    settings,
                ),
                ephemeral=True,
            )
            return
        title = str(settings.get("rate_experience_title")
                    or "Rate your experience")
        await interaction.response.send_modal(
            ReviewSubmitModal(
                self,
                interaction.guild.id,
                interaction.user.id,
                title=title,
            ),
        )

    async def handle_request_submit(self, interaction: discord.Interaction) -> None:
        if not interaction.guild or not isinstance(interaction.user, discord.Member):
            await interaction.response.send_message(
                "This button only works in a server.",
                ephemeral=True,
            )
            return
        if not interaction.message:
            await interaction.response.send_message(
                "I could not identify this review request.",
                ephemeral=True,
            )
            return
        settings = await self.config.guild(interaction.guild).all()
        request = (settings.get("requests") or {}).get(
            str(interaction.message.id))
        if not request or not request.get("active", True):
            await interaction.response.send_message(
                "This review request is no longer active.",
                ephemeral=True,
            )
            return
        if int(
            request.get("reviewer_id") or 0,
        ) != interaction.user.id and not self._is_manager(interaction.user):
            await interaction.response.send_message(
                "This review request was sent to another member.",
                ephemeral=True,
            )
            return
        target_id = request.get("requester_id")
        if not target_id or interaction.guild.get_member(int(target_id)) is None:
            await interaction.response.send_message(
                "The requester is no longer available.",
                ephemeral=True,
            )
            return
        title = str(settings.get("rate_experience_title")
                    or "Rate your experience")
        await interaction.response.send_modal(
            ReviewSubmitModal(
                self,
                interaction.guild.id,
                interaction.user.id,
                target_id=int(target_id),
                request_message_id=interaction.message.id,
                title=title,
            ),
        )

    async def _find_record_by_message(
        self,
        guild: discord.Guild,
        message_id: int,
    ) -> tuple[str | None, ReviewRecord | None, dict[str, Any]]:
        settings = await self.config.guild(guild).all()
        records: dict[str, ReviewRecord] = settings.get("reviews") or {}
        for key, record in records.items():
            if str(record.get("message_id")) == str(message_id):
                return key, record, settings
        return None, None, settings

    async def handle_report_button(self, interaction: discord.Interaction) -> None:
        if (
            not interaction.guild
            or not interaction.message
            or not isinstance(interaction.user, discord.Member)
        ):
            await interaction.response.send_message(
                "This button only works on review messages.",
                ephemeral=True,
            )
            return
        key, record, settings = await self._find_record_by_message(
            interaction.guild,
            interaction.message.id,
        )
        if not key or not record or not record.get("active", True):
            await interaction.response.send_message(
                "I could not find an active review for this message.",
                ephemeral=True,
            )
            return
        reports = record.setdefault("reports", [])
        if any(
            str(report.get("reporter_id")) == str(interaction.user.id)
            for report in reports
        ):
            await interaction.response.send_message(
                "You already reported this review.",
                ephemeral=True,
            )
            return
        report = {
            "reporter_id": interaction.user.id,
            "created_at": self._now_ts(),
        }
        reports.append(report)
        async with self.config.guild(interaction.guild).reviews() as records:
            records[key] = record

        report_channel = await self._get_report_channel(interaction.guild, settings)
        if (
            report_channel is not None
            and interaction.guild.me
            and self._can_send_embed(report_channel, interaction.guild.me)
        ):
            embed = discord.Embed(
                title="Review Reported",
                color=self.DELETED_COLOR,
                timestamp=self._now(),
            )
            embed.add_field(
                name="Review",
                value=str(record.get("display_id")),
                inline=True,
            )
            embed.add_field(
                name="Reporter",
                value=interaction.user.mention,
                inline=True,
            )
            if record.get("message_jump_url"):
                embed.add_field(
                    name="Message",
                    value=str(record.get("message_jump_url")),
                    inline=False,
                )
            try:
                await report_channel.send(
                    embed=embed,
                    allowed_mentions=discord.AllowedMentions.none(),
                )
            except discord.HTTPException:
                log.exception(
                    "Failed to send ReviewHub report in guild %s",
                    interaction.guild.id,
                )
        await interaction.response.send_message("Report recorded.", ephemeral=True)

    async def handle_useful_button(self, interaction: discord.Interaction) -> None:
        if (
            not interaction.guild
            or not interaction.message
            or not isinstance(interaction.user, discord.Member)
        ):
            await interaction.response.send_message(
                "This button only works on review messages.",
                ephemeral=True,
            )
            return
        key, record, settings = await self._find_record_by_message(
            interaction.guild,
            interaction.message.id,
        )
        if not key or not record or not record.get("active", True):
            await interaction.response.send_message(
                "I could not find an active review for this message.",
                ephemeral=True,
            )
            return
        if str(record.get("reviewer_id")) == str(interaction.user.id):
            await interaction.response.send_message(
                "You cannot mark your own review as useful.",
                ephemeral=True,
            )
            return

        user_id = interaction.user.id
        useful_user_ids = [int(value)
                               for value in record.get("useful_user_ids", [])]
        if user_id in useful_user_ids:
            useful_user_ids = [
                value for value in useful_user_ids if value != user_id]
            response = "Removed your useful vote."
        else:
            useful_user_ids.append(user_id)
            response = "Marked this review as useful."
        record["useful_user_ids"] = useful_user_ids

        async with self.config.guild(interaction.guild).reviews() as records:
            records[key] = record
            stats = self._rebuild_stats(records)
        await self.config.guild(interaction.guild).stats.set(stats)

        with contextlib.suppress(discord.HTTPException):
            await interaction.message.edit(
                embed=self._review_embed(interaction.guild, record, settings),
                view=self._review_view(settings),
            )
        await interaction.response.send_message(response, ephemeral=True)

    async def _send_review_from_context(
        self,
        ctx: commands.Context,
        *,
        target: discord.Member | None,
        rating: int | None,
        message: str | None,
        mode_override: str | None = None,
    ) -> None:
        assert ctx.guild is not None
        if not isinstance(ctx.author, discord.Member):
            await ctx.send(
                "This command only works in a server.",
                ephemeral=bool(ctx.interaction),
            )
            return

        if ctx.interaction and (rating is None or message is None):
            settings = await self.config.guild(ctx.guild).all()
            effective_mode = mode_override or (
                "vouch" if settings.get("vouch_mode") else "review"
            )
            if effective_mode == "vouch" and target is None:
                await ctx.send(
                    "Choose a member when submitting a vouch.",
                    ephemeral=True,
                )
                return
            if (
                target is not None
                and effective_mode != "vouch"
                and not settings.get("review_targets_enabled")
            ):
                await ctx.send("Targeted reviews are disabled here.", ephemeral=True)
                return
            await ctx.interaction.response.send_modal(
                ReviewSubmitModal(
                    self,
                    ctx.guild.id,
                    ctx.author.id,
                    target_id=target.id if target else None,
                    mode_override=mode_override,
                    title=str(
                        settings.get(
                            "rate_experience_title") or "Rate your experience",
                    ),
                ),
            )
            return

        if rating is None or message is None:
            await ctx.send(
                f"Use `{ctx.clean_prefix}reviewhub review [member] <rating> <message>`.",
                ephemeral=bool(ctx.interaction),
            )
            return

        try:
            record, _settings, sent_message = await self._create_review(
                ctx.guild,
                ctx.author,
                rating,
                message,
                target=target,
                source_channel=ctx.channel,
                mode_override=mode_override,
            )
        except commands.CommandError as error:
            await ctx.send(str(error), ephemeral=bool(ctx.interaction))
            return

        display_id = str(
            record.get("display_id") or self._display_review_id(
                record.get("id")),
        )
        if sent_message is None:
            await ctx.send(
                f"Review `{display_id}` was recorded, but I could not post it to a channel.",
                ephemeral=bool(ctx.interaction),
            )
            return
        await ctx.send(
            f"Review `{display_id}` posted: {sent_message.jump_url}",
            ephemeral=bool(ctx.interaction),
        )

    async def _send_rateme_request(
        self,
        ctx: commands.Context,
        reviewer: discord.Member,
    ) -> None:
        assert ctx.guild is not None
        if not isinstance(ctx.author, discord.Member):
            await ctx.send(
                "This command only works in a server.",
                ephemeral=bool(ctx.interaction),
            )
            return
        if not isinstance(ctx.channel, discord.TextChannel):
            await ctx.send(
                "Review requests can only be posted in standard text channels.",
                ephemeral=bool(ctx.interaction),
            )
            return
        settings = await self.config.guild(ctx.guild).all()
        if not self._is_manager(ctx.author) and not self._has_role(
            ctx.author,
            settings.get("rateme_role_id"),
        ):
            await ctx.send(
                "You do not have permission to use /rateme.",
                ephemeral=bool(ctx.interaction),
            )
            return
        if reviewer.bot:
            await ctx.send(
                "You cannot request reviews from bot accounts.",
                ephemeral=bool(ctx.interaction),
            )
            return
        if reviewer.id == ctx.author.id:
            await ctx.send(
                "Choose another member to request a review from.",
                ephemeral=bool(ctx.interaction),
            )
            return

        guild_conf = self.config.guild(ctx.guild)
        request_id = int(settings.get("next_request_id") or 1)
        embed = self._request_embed(ctx.guild, ctx.author, reviewer, settings)
        try:
            message = await ctx.channel.send(
                reviewer.mention,
                embed=embed,
                view=ReviewRequestView(self, settings),
                allowed_mentions=discord.AllowedMentions(
                    users=True,
                    roles=False,
                    everyone=False,
                ),
            )
        except discord.HTTPException:
            await ctx.send(
                "I could not post the review request.",
                ephemeral=bool(ctx.interaction),
            )
            return

        request: RequestRecord = {
            "id": request_id,
            "requester_id": ctx.author.id,
            "reviewer_id": reviewer.id,
            "channel_id": message.channel.id,
            "message_id": message.id,
            "created_at": self._now_ts(),
            "active": True,
            "submitted_review_id": None,
        }
        async with guild_conf.requests() as requests:
            requests[str(message.id)] = request
        await guild_conf.next_request_id.set(request_id + 1)
        await ctx.send(
            f"Review request sent to {reviewer.mention}: {message.jump_url}",
            ephemeral=bool(ctx.interaction),
        )

    async def _send_stats(
        self,
        ctx: commands.Context,
        member: discord.Member | None,
        *,
        global_stats: bool = False,
    ) -> None:
        assert ctx.guild is not None
        if global_stats:
            records: dict[str, ReviewRecord] = {}
            all_guilds = await self.config.all_guilds()
            for guild_id, settings in all_guilds.items():
                for key, record in (settings.get("reviews") or {}).items():
                    records[f"{guild_id}:{key}"] = record
            title_scope = "Global"
        else:
            records = await self.config.guild(ctx.guild).reviews()
            title_scope = ctx.guild.name

        active = self._active_records(records)
        stats = self._rebuild_stats(records)
        if member is not None:
            member_stats = self._ensure_stats(stats, member.id)
            received_records = [
                record
                for record in active
                if str(record.get("target_id")) == str(member.id)
            ]
            submitted_records = [
                record
                for record in active
                if str(record.get("reviewer_id")) == str(member.id)
            ]
            ratings = [
                int(record.get("rating") or 0)
                for record in received_records
                if record.get("rating")
            ]
            average = sum(ratings) / len(ratings) if ratings else 0
            embed = discord.Embed(
                title=f"{member.display_name}'s ReviewHub Stats",
                color=self.DEFAULT_COLOR,
                timestamp=self._now(),
            )
            embed.set_thumbnail(url=member.display_avatar.url)
            embed.add_field(name="Scope", value=title_scope, inline=True)
            embed.add_field(
                name="Submitted",
                value=self._count(int(member_stats.get("submitted") or 0)),
                inline=True,
            )
            embed.add_field(
                name="Received",
                value=self._count(int(member_stats.get("received") or 0)),
                inline=True,
            )
            embed.add_field(
                name="Useful Votes",
                value=self._count(int(member_stats.get("useful") or 0)),
                inline=True,
            )
            embed.add_field(
                name="Average Rating",
                value=f"{average:.2f}/5" if ratings else "No ratings",
                inline=True,
            )
            recent = sorted(
                submitted_records,
                key=lambda item: float(item.get("created_at") or 0),
                reverse=True,
            )[:5]
            if recent:
                lines = [
                    "{} - {}/5 - {}".format(
                        record.get("display_id"),
                        record.get("rating"),
                        self._format_ts(record.get("created_at"), "R"),
                    )
                    for record in recent
                ]
                embed.add_field(
                    name="Recent Submissions",
                    value="\n".join(lines),
                    inline=False,
                )
            await ctx.send(embed=embed, ephemeral=bool(ctx.interaction))
            return

        ratings = [
            int(record.get("rating") or 0) for record in active if record.get("rating")
        ]
        average = sum(ratings) / len(ratings) if ratings else 0
        unique_reviewers = {
            record.get("reviewer_id") for record in active if record.get("reviewer_id")
        }
        unique_targets = {
            record.get("target_id") for record in active if record.get("target_id")
        }
        embed = discord.Embed(
            title=f"{title_scope} ReviewHub Stats",
            color=self.DEFAULT_COLOR,
            timestamp=self._now(),
        )
        embed.add_field(
            name="Active Reviews",
            value=self._count(len(active)),
            inline=True,
        )
        embed.add_field(
            name="Average Rating",
            value=f"{average:.2f}/5" if ratings else "No ratings",
            inline=True,
        )
        embed.add_field(
            name="Reviewers",
            value=self._count(len(unique_reviewers)),
            inline=True,
        )
        embed.add_field(
            name="Reviewed Members",
            value=self._count(len(unique_targets)),
            inline=True,
        )
        top = self._rankings(stats, "submitted")[:1]
        if top:
            embed.add_field(
                name="Most Active",
                value=f"{self._user_ref(top[0][1])} - **{self._count(top[0][0])}**",
                inline=False,
            )
        await ctx.send(embed=embed, ephemeral=bool(ctx.interaction))

    async def _send_leaderboard(
        self,
        ctx: commands.Context,
        mode: str,
        global_stats: bool = False,
    ) -> None:
        assert ctx.guild is not None
        try:
            mode = self._normalise_leaderboard_mode(mode)
        except commands.BadArgument as error:
            await ctx.send(str(error), ephemeral=bool(ctx.interaction))
            return

        if global_stats:
            records: dict[str, ReviewRecord] = {}
            all_guilds = await self.config.all_guilds()
            for guild_id, settings in all_guilds.items():
                for key, record in (settings.get("reviews") or {}).items():
                    records[f"{guild_id}:{key}"] = record
            scope = "Global"
        else:
            records = await self.config.guild(ctx.guild).reviews()
            scope = ctx.guild.name
        stats = self._rebuild_stats(records)
        rows = self._rankings(stats, mode)[:10]
        if not rows:
            await ctx.send(
                "No leaderboard data is available yet.",
                ephemeral=bool(ctx.interaction),
            )
            return

        labels = {
            "submitted": "Most Active Members",
            "received": "Most Reviewed Members",
            "useful": "Most Useful Reviewers",
        }
        lines = [
            f"{index}. {self._user_ref(member_id)} - **{self._count(value)}**"
            for index, (value, member_id) in enumerate(rows, start=1)
        ]
        embed = discord.Embed(
            title=f"ReviewHub Leaderboard - {labels[mode]}",
            description="\n".join(lines),
            color=self.DEFAULT_COLOR,
            timestamp=self._now(),
        )
        embed.set_footer(text=f"Scope: {scope}")
        await ctx.send(embed=embed, ephemeral=bool(ctx.interaction))

    def _help_embed(self, prefix: str) -> discord.Embed:
        embed = discord.Embed(
            title="ReviewHub Commands",
            color=self.DEFAULT_COLOR,
            timestamp=self._now(),
        )
        embed.add_field(
            name="User Commands",
            value=(
                "`/review [member]` or `/vouch` - submit a review or recommendation\n"
                "`/stats [user]` - view server or user statistics\n"
                "`/leaderboard` - view the top 10 active members"
            ),
            inline=False,
        )
        embed.add_field(
            name="Staff Commands",
            value=(
                "`/rateme @User` - request a review from a member\n"
                "`/deletereview id:<review id>` - delete a review\n"
                "`/config server`, `/config appearance`, `/config access` - configure settings"
            ),
            inline=False,
        )
        embed.add_field(
            name="Prefix Fallbacks",
            value=(
                f"`{prefix}reviewhub review [member] <rating> <message>`\n"
                f"`{prefix}reviewhub rateme @member`\n"
                f"`{prefix}reviewhub config`"
            ),
            inline=False,
        )
        embed.add_field(
            name="Links",
            value="[ReviewHub reference documentation](https://reviewhubs.info/documentation)",
            inline=False,
        )
        return embed

    async def _slash_help(self, interaction: discord.Interaction) -> None:
        await interaction.response.send_message(
            embed=self._help_embed("/"),
            ephemeral=True,
        )

    async def _send_help(self, ctx: commands.Context) -> None:
        embed = self._help_embed(ctx.clean_prefix)
        await ctx.send(embed=embed, ephemeral=bool(ctx.interaction))

    @commands.hybrid_command(name="review", description="Submit a review.")
    @commands.guild_only()
    @commands.bot_has_permissions(embed_links=True)
    @app_commands.describe(
        member="Member this review is about, if targeted reviews are enabled",
        rating="Rating from 1 to 5",
        message="Review text",
    )
    async def review_command(
        self,
        ctx: commands.Context,
        member: discord.Member | None = None,
        rating: int | None = None,
        *,
        message: str | None = None,
    ) -> None:
        """Submit a review."""
        await self._send_review_from_context(
            ctx,
            target=member,
            rating=rating,
            message=message,
        )

    @commands.hybrid_command(name="vouch", description="Recommend another user.")
    @commands.guild_only()
    @commands.bot_has_permissions(embed_links=True)
    @app_commands.describe(
        member="Member you want to vouch for",
        rating="Rating from 1 to 5",
        message="Vouch text",
    )
    async def vouch_command(
        self,
        ctx: commands.Context,
        member: discord.Member | None = None,
        rating: int | None = None,
        *,
        message: str | None = None,
    ) -> None:
        """Recommend another user."""
        if member is None:
            await ctx.send(
                f"Use `{ctx.clean_prefix}reviewhub vouch @member <rating> <message>`.",
                ephemeral=bool(ctx.interaction),
            )
            return
        await self._send_review_from_context(
            ctx,
            target=member,
            rating=rating,
            message=message,
            mode_override="vouch",
        )

    @commands.hybrid_command(
        name="rateme",
        description="Request a review from a specific user.",
    )
    @commands.guild_only()
    @commands.bot_has_permissions(embed_links=True)
    @app_commands.describe(member="Member you want to request a review from")
    async def rateme_command(
        self,
        ctx: commands.Context,
        member: discord.Member,
    ) -> None:
        """Request a review from a specific user."""
        await self._send_rateme_request(ctx, member)

    @commands.hybrid_command(
        name="stats",
        description="View server or user review statistics.",
    )
    @commands.guild_only()
    @commands.bot_has_permissions(embed_links=True)
    @app_commands.describe(
        member="Optional member to inspect",
        global_stats="Include all servers using this cog",
    )
    async def stats_command(
        self,
        ctx: commands.Context,
        member: discord.Member | None = None,
        global_stats: bool = False,
    ) -> None:
        """View server or user statistics."""
        await self._send_stats(ctx, member, global_stats=global_stats)

    @commands.hybrid_command(
        name="leaderboard",
        description="View the ReviewHub top 10.",
    )
    @commands.guild_only()
    @commands.bot_has_permissions(embed_links=True)
    @app_commands.describe(
        mode="submitted, received, or useful",
        global_stats="Include all servers using this cog",
    )
    async def leaderboard_command(
        self,
        ctx: commands.Context,
        mode: str = "submitted",
        global_stats: bool = False,
    ) -> None:
        """View top 10 active members."""
        await self._send_leaderboard(ctx, mode, global_stats=global_stats)

    @commands.hybrid_command(name="deletereview", description="Delete a review by ID.")
    @commands.guild_only()
    @commands.admin_or_permissions(manage_messages=True)
    @commands.bot_has_permissions(embed_links=True)
    @app_commands.describe(
        review_id="Review ID, e.g. RH-000001",
        reason="Optional deletion reason",
    )
    @app_commands.rename(review_id="id")
    async def delete_review_command(
        self,
        ctx: commands.Context,
        review_id: str,
        *,
        reason: str | None = None,
    ) -> None:
        """Delete a review by ID."""
        assert ctx.guild is not None
        if not isinstance(ctx.author, discord.Member):
            await ctx.send(
                "This command only works in a server.",
                ephemeral=bool(ctx.interaction),
            )
            return
        try:
            record, _settings = await self._delete_review(
                ctx.guild,
                review_id,
                ctx.author,
                reason,
            )
        except commands.CommandError as error:
            await ctx.send(str(error), ephemeral=bool(ctx.interaction))
            return
        await ctx.send(
            f"Deleted review `{record.get('display_id')}`.",
            ephemeral=bool(ctx.interaction),
        )

    @commands.hybrid_group(
        name="reviewhub",
        aliases=["rh"],
        invoke_without_command=True,
    )
    @commands.guild_only()
    @commands.bot_has_permissions(embed_links=True)
    async def reviewhub_group(self, ctx: commands.Context) -> None:
        """View ReviewHub settings and help."""
        assert ctx.guild is not None
        await ctx.send(
            embed=await self._settings_embed(ctx.guild),
            ephemeral=bool(ctx.interaction),
        )

    @reviewhub_group.command(name="help")
    async def reviewhub_help(self, ctx: commands.Context) -> None:
        """Show ReviewHub command help."""
        await self._send_help(ctx)

    @reviewhub_group.command(name="setup")
    @commands.admin_or_permissions(manage_guild=True)
    async def reviewhub_setup(
        self,
        ctx: commands.Context,
        review_channel: discord.TextChannel | None = None,
        report_channel: discord.TextChannel | None = None,
    ) -> None:
        """Quick setup for review and report channels."""
        assert ctx.guild is not None
        if review_channel is None:
            if isinstance(ctx.channel, discord.TextChannel):
                review_channel = ctx.channel
            else:
                await ctx.send(
                    "Run this in a text channel or provide a review channel.",
                    ephemeral=bool(ctx.interaction),
                )
                return
        guild_conf = self.config.guild(ctx.guild)
        await guild_conf.review_channel_id.set(review_channel.id)
        if report_channel is not None:
            await guild_conf.report_channel_id.set(report_channel.id)
        await ctx.send(
            f"ReviewHub configured. Reviews: {review_channel.mention}. "
            f"Reports: {report_channel.mention if report_channel else 'unchanged/not set'}.",
            ephemeral=bool(ctx.interaction),
        )

    @reviewhub_group.command(name="review")
    async def reviewhub_review(
        self,
        ctx: commands.Context,
        member: discord.Member | None = None,
        rating: int | None = None,
        *,
        message: str | None = None,
    ) -> None:
        """Submit a review using the namespaced fallback command."""
        await self._send_review_from_context(
            ctx,
            target=member,
            rating=rating,
            message=message,
        )

    @reviewhub_group.command(name="vouch")
    async def reviewhub_vouch(
        self,
        ctx: commands.Context,
        member: discord.Member | None = None,
        rating: int | None = None,
        *,
        message: str | None = None,
    ) -> None:
        """Submit a vouch using the namespaced fallback command."""
        if member is None:
            await ctx.send(
                f"Use `{ctx.clean_prefix}reviewhub vouch @member <rating> <message>`.",
                ephemeral=bool(ctx.interaction),
            )
            return
        await self._send_review_from_context(
            ctx,
            target=member,
            rating=rating,
            message=message,
            mode_override="vouch",
        )

    @reviewhub_group.command(name="rateme")
    async def reviewhub_rateme(
        self,
        ctx: commands.Context,
        member: discord.Member,
    ) -> None:
        """Request a review from a specific user."""
        await self._send_rateme_request(ctx, member)

    @reviewhub_group.command(name="stats")
    async def reviewhub_stats(
        self,
        ctx: commands.Context,
        member: discord.Member | None = None,
        global_stats: bool = False,
    ) -> None:
        """View server or user statistics."""
        await self._send_stats(ctx, member, global_stats=global_stats)

    @reviewhub_group.command(name="leaderboard")
    async def reviewhub_leaderboard(
        self,
        ctx: commands.Context,
        mode: str = "submitted",
        global_stats: bool = False,
    ) -> None:
        """View top 10 active members."""
        await self._send_leaderboard(ctx, mode, global_stats=global_stats)

    @reviewhub_group.command(name="deletereview")
    @commands.admin_or_permissions(manage_messages=True)
    async def reviewhub_delete_review(
        self,
        ctx: commands.Context,
        review_id: str,
        *,
        reason: str | None = None,
    ) -> None:
        """Delete a review by ID."""
        assert ctx.guild is not None
        if not isinstance(ctx.author, discord.Member):
            await ctx.send(
                "This command only works in a server.",
                ephemeral=bool(ctx.interaction),
            )
            return
        try:
            record, _settings = await self._delete_review(
                ctx.guild,
                review_id,
                ctx.author,
                reason,
            )
        except commands.CommandError as error:
            await ctx.send(str(error), ephemeral=bool(ctx.interaction))
            return
        await ctx.send(
            f"Deleted review `{record.get('display_id')}`.",
            ephemeral=bool(ctx.interaction),
        )

    @reviewhub_group.group(name="config", invoke_without_command=True)
    @commands.admin_or_permissions(manage_guild=True)
    async def reviewhub_config(self, ctx: commands.Context) -> None:
        """Show ReviewHub settings."""
        assert ctx.guild is not None
        await ctx.send(
            embed=await self._settings_embed(ctx.guild),
            ephemeral=bool(ctx.interaction),
        )

    @reviewhub_config.command(name="reviewchannel")
    @commands.admin_or_permissions(manage_guild=True)
    async def reviewhub_config_review_channel(
        self,
        ctx: commands.Context,
        channel: discord.TextChannel | None = None,
    ) -> None:
        """Set or clear the review channel."""
        assert ctx.guild is not None
        await self.config.guild(ctx.guild).review_channel_id.set(
            channel.id if channel else None,
        )
        await ctx.send(
            f"Review channel set to {channel.mention if channel else 'none'}.",
            ephemeral=bool(ctx.interaction),
        )

    @reviewhub_config.command(name="reportchannel")
    @commands.admin_or_permissions(manage_guild=True)
    async def reviewhub_config_report_channel(
        self,
        ctx: commands.Context,
        channel: discord.TextChannel | None = None,
    ) -> None:
        """Set or clear the report channel."""
        assert ctx.guild is not None
        await self.config.guild(ctx.guild).report_channel_id.set(
            channel.id if channel else None,
        )
        await ctx.send(
            f"Report channel set to {channel.mention if channel else 'none'}.",
            ephemeral=bool(ctx.interaction),
        )

    @reviewhub_config.command(name="template")
    @commands.admin_or_permissions(manage_guild=True)
    async def reviewhub_config_template(
        self,
        ctx: commands.Context,
        template: str,
    ) -> None:
        """Set review template to classic or detailed."""
        assert ctx.guild is not None
        normalized = template.strip().lower()
        if normalized not in {"classic", "detailed"}:
            await ctx.send(
                "Template must be `classic` or `detailed`.",
                ephemeral=bool(ctx.interaction),
            )
            return
        await self.config.guild(ctx.guild).review_template.set(normalized)
        await ctx.send(
            f"Review template set to **{normalized}**.",
            ephemeral=bool(ctx.interaction),
        )

    @reviewhub_config.command(name="color")
    @commands.admin_or_permissions(manage_guild=True)
    async def reviewhub_config_color(self, ctx: commands.Context, color: str) -> None:
        """Set review embed color."""
        assert ctx.guild is not None
        try:
            parsed = self._parse_color(color)
        except commands.BadArgument as error:
            await ctx.send(str(error), ephemeral=bool(ctx.interaction))
            return
        await self.config.guild(ctx.guild).review_embed_color.set(parsed)
        await ctx.send(
            f"Review embed color set to `#{parsed:06X}`.",
            ephemeral=bool(ctx.interaction),
        )

    @reviewhub_config.command(name="vouchmode")
    @commands.admin_or_permissions(manage_guild=True)
    async def reviewhub_config_vouch_mode(
        self,
        ctx: commands.Context,
        enabled: bool,
    ) -> None:
        """Enable or disable vouch mode."""
        assert ctx.guild is not None
        await self.config.guild(ctx.guild).vouch_mode.set(enabled)
        await ctx.send(
            f"Vouch mode {self._enabled_text(enabled)}.",
            ephemeral=bool(ctx.interaction),
        )

    @reviewhub_config.command(name="reviewtargets")
    @commands.admin_or_permissions(manage_guild=True)
    async def reviewhub_config_review_targets(
        self,
        ctx: commands.Context,
        enabled: bool,
    ) -> None:
        """Allow or block member targets on regular reviews."""
        assert ctx.guild is not None
        await self.config.guild(ctx.guild).review_targets_enabled.set(enabled)
        await ctx.send(
            f"Review targets {self._enabled_text(enabled)}.",
            ephemeral=bool(ctx.interaction),
        )

    @reviewhub_config.command(name="autothread")
    @commands.admin_or_permissions(manage_guild=True)
    async def reviewhub_config_auto_thread(
        self,
        ctx: commands.Context,
        enabled: bool,
    ) -> None:
        """Enable or disable automatic discussion threads."""
        assert ctx.guild is not None
        await self.config.guild(ctx.guild).auto_thread.set(enabled)
        await ctx.send(
            f"Auto threads {self._enabled_text(enabled)}.",
            ephemeral=bool(ctx.interaction),
        )

    @reviewhub_config.command(name="ratemerole")
    @commands.admin_or_permissions(manage_guild=True)
    async def reviewhub_config_rateme_role(
        self,
        ctx: commands.Context,
        role: discord.Role | None = None,
    ) -> None:
        """Set or clear the /rateme role."""
        assert ctx.guild is not None
        await self.config.guild(ctx.guild).rateme_role_id.set(role.id if role else None)
        await ctx.send(
            f"/rateme role set to {role.mention if role else 'Manage Server only'}.",
            ephemeral=bool(ctx.interaction),
        )

    @reviewhub_group.command(name="export")
    @commands.admin_or_permissions(manage_guild=True)
    @commands.bot_has_permissions(attach_files=True)
    async def reviewhub_export(self, ctx: commands.Context) -> None:
        """Export ReviewHub records as CSV."""
        assert ctx.guild is not None
        records = await self.config.guild(ctx.guild).reviews()
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(
            [
                "id",
                "display_id",
                "active",
                "mode",
                "reviewer_id",
                "target_id",
                "rating",
                "content",
                "created_at",
                "deleted_at",
                "deleted_by",
                "delete_reason",
                "useful_count",
                "report_count",
                "channel_id",
                "message_id",
                "message_jump_url",
            ],
        )
        for record in sorted(
            records.values(),
            key=lambda item: int(item.get("id") or 0),
        ):
            writer.writerow(
                [
                    record.get("id"),
                    record.get("display_id"),
                    bool(record.get("active", True)),
                    record.get("mode"),
                    record.get("reviewer_id"),
                    record.get("target_id"),
                    record.get("rating"),
                    record.get("content"),
                    self._format_export_time(record.get("created_at")),
                    self._format_export_time(record.get("deleted_at")),
                    record.get("deleted_by"),
                    record.get("delete_reason"),
                    len(record.get("useful_user_ids", [])),
                    len(record.get("reports", [])),
                    record.get("channel_id"),
                    record.get("message_id"),
                    record.get("message_jump_url"),
                ],
            )
        file = discord.File(
            io.BytesIO(output.getvalue().encode("utf-8")),
            filename=f"reviewhub-{ctx.guild.id}.csv",
        )
        await ctx.send("ReviewHub export:", file=file, ephemeral=bool(ctx.interaction))
