"""Temporary voice channel cog for Red-DiscordBot."""

from __future__ import annotations

import asyncio
import contextlib
import logging
import re
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any

import discord
from discord import app_commands
from redbot.core import Config, commands

from .dashboard_integration import DashboardIntegration

if TYPE_CHECKING:
    from redbot.core.bot import Red

log = logging.getLogger("red.taakoscogs.tempvoice")


TempVoiceRecord = dict[str, Any]
GuildSettings = dict[str, Any]
MODAL_SELECTS_SUPPORTED = hasattr(discord.ui, "Label")


class RenameChannelModal(discord.ui.Modal):
    """Modal used by owners to rename a temporary voice channel."""

    def __init__(self, cog: TempVoice, channel_id: int, current_name: str) -> None:
        super().__init__(title="Rename Voice Channel", timeout=300)
        self.cog = cog
        self.channel_id = channel_id
        self.name_input = discord.ui.TextInput(
            label="New channel name",
            default=current_name[:100],
            min_length=1,
            max_length=100,
        )
        self.add_item(self.name_input)

    async def on_submit(self, interaction: discord.Interaction) -> None:
        await self.cog.handle_rename_submit(
            interaction,
            self.channel_id,
            str(self.name_input.value),
        )

    async def on_error(
        self,
        interaction: discord.Interaction,
        error: Exception,
    ) -> None:
        await self.cog.handle_modal_error(interaction, error)


class UserLimitModal(discord.ui.Modal):
    """Modal used by owners to set a temporary voice user limit."""

    def __init__(self, cog: TempVoice, channel_id: int, current_limit: int) -> None:
        super().__init__(title="Set User Limit", timeout=300)
        self.cog = cog
        self.channel_id = channel_id
        self.limit_input = discord.ui.TextInput(
            label="User limit",
            default=str(current_limit),
            placeholder="0 for no limit, 1-99 for a cap",
            min_length=1,
            max_length=2,
        )
        self.add_item(self.limit_input)

    async def on_submit(self, interaction: discord.Interaction) -> None:
        await self.cog.handle_limit_submit(
            interaction,
            self.channel_id,
            str(self.limit_input.value),
        )

    async def on_error(
        self,
        interaction: discord.Interaction,
        error: Exception,
    ) -> None:
        await self.cog.handle_modal_error(interaction, error)


class MemberTargetModal(discord.ui.Modal):
    """Modal used by owners to target a member by mention or Discord ID."""

    def __init__(
        self,
        cog: TempVoice,
        channel_id: int,
        action: str,
        title: str,
        label: str,
    ) -> None:
        super().__init__(title=title, timeout=300)
        self.cog = cog
        self.channel_id = channel_id
        self.action = action
        if MODAL_SELECTS_SUPPORTED:
            self.member_input = discord.ui.UserSelect(
                placeholder="Choose a server member",
                min_values=1,
                max_values=1,
                required=True,
            )
            self.add_item(
                discord.ui.Label(
                    text=label[:45],
                    component=self.member_input,
                ),
            )
        else:
            self.member_input = discord.ui.TextInput(
                label=label,
                placeholder="@member or Discord user ID",
                min_length=2,
                max_length=100,
            )
            self.add_item(self.member_input)

    async def on_submit(self, interaction: discord.Interaction) -> None:
        if isinstance(self.member_input, discord.ui.UserSelect):
            selected = self.member_input.values[0] if self.member_input.values else None
            raw_member = str(getattr(selected, "id", ""))
        else:
            raw_member = str(self.member_input.value)
        await self.cog.handle_member_submit(
            interaction,
            self.channel_id,
            self.action,
            raw_member,
        )

    async def on_error(
        self,
        interaction: discord.Interaction,
        error: Exception,
    ) -> None:
        await self.cog.handle_modal_error(interaction, error)


class TempVoiceControlView(discord.ui.View):
    """Persistent control panel for temporary voice channels."""

    def __init__(self, cog: TempVoice) -> None:
        super().__init__(timeout=None)
        self.cog = cog

    @discord.ui.button(
        label="Rename",
        style=discord.ButtonStyle.primary,
        custom_id="taakoscogs:tempvoice:rename",
        row=0,
    )
    async def rename(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ) -> None:
        await self.cog.handle_control_button(interaction, "rename")

    @discord.ui.button(
        label="Lock / Unlock",
        style=discord.ButtonStyle.secondary,
        custom_id="taakoscogs:tempvoice:lock",
        row=0,
    )
    async def lock(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ) -> None:
        await self.cog.handle_control_button(interaction, "lock")

    @discord.ui.button(
        label="User Limit",
        style=discord.ButtonStyle.secondary,
        custom_id="taakoscogs:tempvoice:limit",
        row=0,
    )
    async def limit(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ) -> None:
        await self.cog.handle_control_button(interaction, "limit")

    @discord.ui.button(
        label="Transfer",
        style=discord.ButtonStyle.secondary,
        custom_id="taakoscogs:tempvoice:transfer",
        row=0,
    )
    async def transfer(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ) -> None:
        await self.cog.handle_control_button(interaction, "transfer")

    @discord.ui.button(
        label="Permit User",
        style=discord.ButtonStyle.success,
        custom_id="taakoscogs:tempvoice:permit",
        row=1,
    )
    async def permit(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ) -> None:
        await self.cog.handle_control_button(interaction, "permit")

    @discord.ui.button(
        label="Remove User",
        style=discord.ButtonStyle.danger,
        custom_id="taakoscogs:tempvoice:remove",
        row=1,
    )
    async def remove(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ) -> None:
        await self.cog.handle_control_button(interaction, "remove")

    @discord.ui.button(
        label="Claim",
        style=discord.ButtonStyle.secondary,
        custom_id="taakoscogs:tempvoice:claim",
        row=1,
    )
    async def claim(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ) -> None:
        await self.cog.handle_control_button(interaction, "claim")


class TempVoice(DashboardIntegration, commands.Cog):
    """Create temporary voice channels with owner control panels."""

    CONFIG_IDENTIFIER = 2026052001
    DEFAULT_COLOR = 0x5865F2
    SUCCESS_COLOR = 0x57F287
    WARNING_COLOR = 0xFEE75C
    ERROR_COLOR = 0xED4245
    DEFAULT_TEMPLATE = "{owner}'s channel"
    MAX_DELETE_DELAY = 300
    USER_ID_RE = re.compile(r"(\d{15,22})")

    def __init__(self, bot: Red) -> None:
        self.bot = bot
        self.config = Config.get_conf(
            self,
            identifier=self.CONFIG_IDENTIFIER,
            force_registration=True,
        )
        self.config.register_guild(
            enabled=False,
            join_channel_id=None,
            category_id=None,
            panel_channel_id=None,
            channel_name_template=self.DEFAULT_TEMPLATE,
            default_user_limit=0,
            auto_delete_delay=3,
            clone_trigger_permissions=True,
            temp_channels={},
        )
        self._locks: dict[int, asyncio.Lock] = {}
        self._delete_tasks: dict[int, asyncio.Task] = {}
        self._startup_task: asyncio.Task | None = None
        self._control_view = TempVoiceControlView(self)

    async def cog_load(self) -> None:
        """Register persistent component callbacks."""
        self.bot.add_view(self._control_view)
        self._startup_task = asyncio.create_task(self._startup_cleanup())

    async def cog_unload(self) -> None:
        """Cancel pending cleanup tasks when the cog unloads."""
        if self._startup_task and not self._startup_task.done():
            self._startup_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._startup_task
        for task in self._delete_tasks.values():
            task.cancel()
        for task in self._delete_tasks.values():
            with contextlib.suppress(asyncio.CancelledError):
                await task
        self._delete_tasks.clear()

    async def red_delete_data_for_user(self, *, requester: str, user_id: int) -> None:
        """Remove stored references to a Discord user ID."""
        user_key = str(user_id)
        all_guilds = await self.config.all_guilds()
        for guild_id in all_guilds:
            async with self.config.guild_from_id(guild_id).temp_channels() as records:
                for record in records.values():
                    if str(record.get("owner_id")) == user_key:
                        record["owner_id"] = None
                        record["owner_removed"] = True
                    record["permitted_ids"] = [
                        member_id
                        for member_id in record.get("permitted_ids", [])
                        if str(member_id) != user_key
                    ]

    def _guild_lock(self, guild_id: int) -> asyncio.Lock:
        return self._locks.setdefault(guild_id, asyncio.Lock())

    @staticmethod
    def _now_ts() -> float:
        return datetime.now(timezone.utc).timestamp()

    @staticmethod
    def _format_ts(value: Any, style: str = "R") -> str:
        if value in (None, ""):
            return "Unknown"
        try:
            timestamp = int(float(value))
        except (TypeError, ValueError):
            return "Unknown"
        return f"<t:{timestamp}:{style}>"

    @staticmethod
    def _channel_ref(guild: discord.Guild, channel_id: Any) -> str:
        if channel_id in (None, ""):
            return "Not set"
        try:
            channel = guild.get_channel(int(channel_id))
        except (TypeError, ValueError):
            return "Not set"
        if channel:
            return getattr(channel, "mention", f"`{channel.id}`")
        return f"`{channel_id}` (missing)"

    @staticmethod
    def _human_members(channel: discord.VoiceChannel) -> list[discord.Member]:
        return [member for member in channel.members if not member.bot]

    @staticmethod
    def _member_in_channel(
        member: discord.Member,
        channel: discord.VoiceChannel,
    ) -> bool:
        return bool(
            member.voice
            and member.voice.channel
            and member.voice.channel.id == channel.id,
        )

    @classmethod
    def _clean_channel_name(cls, value: str) -> str:
        cleaned = re.sub(r"[\r\n\t]+", " ", value)
        cleaned = re.sub(r"\s+", " ", cleaned).strip()
        return (cleaned or "Temporary Voice")[:100]

    @classmethod
    def _render_channel_name(
        cls,
        template: str,
        member: discord.Member,
        guild: discord.Guild,
    ) -> str:
        replacements = {
            "{owner}": member.display_name,
            "{username}": member.name,
            "{user}": member.display_name,
            "{guild}": guild.name,
        }
        rendered = template or cls.DEFAULT_TEMPLATE
        for token, value in replacements.items():
            rendered = rendered.replace(token, value)
        return cls._clean_channel_name(rendered)

    @staticmethod
    def _limit_text(limit: Any) -> str:
        try:
            value = int(limit or 0)
        except (TypeError, ValueError):
            value = 0
        return "No limit" if value <= 0 else str(value)

    async def _send_interaction_message(
        self,
        interaction: discord.Interaction,
        message: str,
        *,
        ephemeral: bool = True,
    ) -> None:
        if interaction.response.is_done():
            await interaction.followup.send(message, ephemeral=ephemeral)
        else:
            await interaction.response.send_message(message, ephemeral=ephemeral)

    async def _guard_control(
        self,
        interaction: discord.Interaction,
        *,
        channel_id: int | None = None,
        require_owner: bool = True,
    ) -> tuple[TempVoiceRecord, discord.VoiceChannel, discord.Member] | None:
        if not interaction.guild or not isinstance(interaction.user, discord.Member):
            await self._send_interaction_message(
                interaction,
                "This control panel only works in a server.",
            )
            return None

        if channel_id is None:
            record, channel = await self._record_from_interaction(interaction)
        else:
            record = await self._get_temp_record(interaction.guild, channel_id)
            channel = interaction.guild.get_channel(channel_id)

        if not record or not isinstance(channel, discord.VoiceChannel):
            await self._send_interaction_message(
                interaction,
                "That temporary voice channel no longer exists.",
            )
            return None

        if require_owner and not self._can_control(interaction.user, record, channel):
            await self._send_interaction_message(
                interaction,
                "Only the channel owner or a member with Manage Channels can use that control.",
            )
            return None

        return record, channel, interaction.user

    def _can_control(
        self,
        member: discord.Member,
        record: TempVoiceRecord,
        channel: discord.VoiceChannel,
    ) -> bool:
        if (
            member.guild_permissions.administrator
            or member.guild_permissions.manage_channels
        ):
            return True
        try:
            owner_id = int(record.get("owner_id") or 0)
        except (TypeError, ValueError):
            owner_id = 0
        return member.id == owner_id and self._member_in_channel(member, channel)

    @staticmethod
    def _owner_present(
        guild: discord.Guild,
        record: TempVoiceRecord,
        channel: discord.VoiceChannel,
    ) -> bool:
        try:
            owner_id = int(record.get("owner_id") or 0)
        except (TypeError, ValueError):
            return False
        owner = guild.get_member(owner_id)
        return bool(owner and owner in channel.members)

    async def _get_temp_record(
        self,
        guild: discord.Guild,
        channel_id: int,
    ) -> TempVoiceRecord | None:
        records = await self.config.guild(guild).temp_channels()
        return records.get(str(channel_id))

    async def _record_from_interaction(
        self,
        interaction: discord.Interaction,
    ) -> tuple[TempVoiceRecord | None, discord.abc.GuildChannel | None]:
        guild = interaction.guild
        if guild is None:
            return None, None

        records = await self.config.guild(guild).temp_channels()
        if interaction.channel_id is not None:
            record = records.get(str(interaction.channel_id))
            if record:
                return record, guild.get_channel(int(interaction.channel_id))

        message_id = interaction.message.id if interaction.message else None
        if message_id is not None:
            for channel_id, record in records.items():
                if int(record.get("panel_message_id") or 0) == message_id:
                    try:
                        return record, guild.get_channel(int(channel_id))
                    except (TypeError, ValueError):
                        return record, None

        return None, None

    async def _resolve_member(self, guild: discord.Guild, raw: str) -> discord.Member:
        match = self.USER_ID_RE.search(raw)
        if not match:
            raise commands.BadArgument(
                "Enter a member mention or Discord user ID.")
        member_id = int(match.group(1))
        member = guild.get_member(member_id)
        if member is not None:
            return member
        try:
            return await guild.fetch_member(member_id)
        except discord.NotFound as exc:
            raise commands.BadArgument(
                "I could not find that member in this server.",
            ) from exc
        except discord.HTTPException as exc:
            raise commands.BadArgument(
                "I could not look up that member right now.",
            ) from exc

    async def _ensure_member_override(
        self,
        channel: discord.VoiceChannel,
        member: discord.Member,
        *,
        reason: str,
    ) -> None:
        overwrite = channel.overwrites_for(member)
        overwrite.view_channel = True
        overwrite.connect = True
        await channel.set_permissions(member, overwrite=overwrite, reason=reason)

    async def _update_record(
        self,
        guild: discord.Guild,
        channel_id: int,
        **updates: Any,
    ) -> TempVoiceRecord:
        async with self.config.guild(guild).temp_channels() as records:
            record = records.setdefault(str(channel_id), {})
            record.update(updates)
            return dict(record)

    def _control_embed(
        self,
        guild: discord.Guild,
        channel: discord.VoiceChannel,
        record: TempVoiceRecord,
    ) -> discord.Embed:
        owner_id = record.get("owner_id")
        owner_text = f"<@{owner_id}>" if owner_id else "Unclaimed"
        locked = bool(record.get("locked"))
        embed = discord.Embed(
            title="Temporary Voice Controls",
            description=f"Controls for {channel.mention}",
            color=self.WARNING_COLOR if locked else self.DEFAULT_COLOR,
            timestamp=datetime.now(timezone.utc),
        )
        embed.add_field(name="Owner", value=owner_text, inline=True)
        embed.add_field(
            name="Status",
            value="Locked" if locked else "Unlocked",
            inline=True,
        )
        embed.add_field(
            name="User Limit",
            value=self._limit_text(record.get("user_limit")),
            inline=True,
        )
        embed.add_field(
            name="Created",
            value=self._format_ts(record.get("created_at")),
            inline=True,
        )
        embed.add_field(name="Channel ID",
                        value=f"`{channel.id}`", inline=True)
        embed.set_footer(
            text="Owner controls are available while the owner is in the voice channel.",
        )
        return embed

    async def _send_control_panel(
        self,
        guild: discord.Guild,
        channel: discord.VoiceChannel,
        record: TempVoiceRecord,
        settings: GuildSettings,
    ) -> discord.Message | None:
        target = channel
        panel_channel_id = settings.get("panel_channel_id")
        if panel_channel_id:
            configured_target = guild.get_channel(int(panel_channel_id))
            if configured_target is not None:
                target = configured_target

        send = getattr(target, "send", None)
        if send is None:
            return None

        me = guild.me
        if me is None:
            return None
        permissions = target.permissions_for(me)
        if not permissions.send_messages or not permissions.embed_links:
            return None

        try:
            return await send(
                embed=self._control_embed(guild, channel, record),
                view=self._control_view,
                allowed_mentions=discord.AllowedMentions.none(),
            )
        except (discord.Forbidden, discord.HTTPException):
            log.exception(
                "Could not send TempVoice control panel in guild %s.",
                guild.id,
            )
            return None

    async def _update_control_panel(
        self,
        guild: discord.Guild,
        channel: discord.VoiceChannel,
        record: TempVoiceRecord,
        *,
        interaction: discord.Interaction | None = None,
    ) -> None:
        embed = self._control_embed(guild, channel, record)
        if interaction and interaction.message:
            with contextlib.suppress(discord.HTTPException):
                await interaction.message.edit(embed=embed, view=self._control_view)
                return

        panel_message_id = record.get("panel_message_id")
        panel_channel_id = record.get("panel_channel_id") or channel.id
        if not panel_message_id:
            return
        panel_channel = guild.get_channel(int(panel_channel_id))
        if panel_channel is None:
            return
        try:
            message = await panel_channel.fetch_message(int(panel_message_id))
            await message.edit(embed=embed, view=self._control_view)
        except (discord.Forbidden, discord.NotFound, discord.HTTPException):
            return

    async def _remove_temp_record(
        self,
        guild: discord.Guild,
        channel_id: int,
    ) -> TempVoiceRecord | None:
        async with self.config.guild(guild).temp_channels() as records:
            return records.pop(str(channel_id), None)

    async def _delete_temp_channel(
        self,
        guild: discord.Guild,
        channel_id: int,
        *,
        reason: str,
    ) -> None:
        await self._remove_temp_record(guild, channel_id)
        channel = guild.get_channel(channel_id)
        if isinstance(channel, discord.VoiceChannel):
            try:
                await channel.delete(reason=reason)
            except discord.NotFound:
                return
            except (discord.Forbidden, discord.HTTPException):
                log.exception(
                    "Could not delete TempVoice channel %s in guild %s.",
                    channel_id,
                    guild.id,
                )

    def _cancel_cleanup(self, channel_id: int) -> None:
        task = self._delete_tasks.pop(channel_id, None)
        if task and not task.done():
            task.cancel()

    def _schedule_cleanup(self, guild_id: int, channel_id: int, delay: int) -> None:
        self._cancel_cleanup(channel_id)
        self._delete_tasks[channel_id] = asyncio.create_task(
            self._cleanup_after_delay(guild_id, channel_id, delay),
        )

    async def _cleanup_after_delay(
        self,
        guild_id: int,
        channel_id: int,
        delay: int,
    ) -> None:
        try:
            await asyncio.sleep(max(0, min(delay, self.MAX_DELETE_DELAY)))
            guild = self.bot.get_guild(guild_id)
            if guild is None:
                return
            channel = guild.get_channel(channel_id)
            if not isinstance(channel, discord.VoiceChannel):
                await self._remove_temp_record(guild, channel_id)
                return
            if self._human_members(channel):
                return
            await self._delete_temp_channel(
                guild,
                channel_id,
                reason="TempVoice channel was empty.",
            )
        except asyncio.CancelledError:
            raise
        finally:
            self._delete_tasks.pop(channel_id, None)

    async def _startup_cleanup(self) -> None:
        """Schedule cleanup for empty persisted temporary channels after a restart."""
        try:
            await self.bot.wait_until_ready()
            all_guilds = await self.config.all_guilds()
            for guild_id, settings in all_guilds.items():
                guild = self.bot.get_guild(guild_id)
                if guild is None:
                    continue
                stale_ids: list[str] = []
                for channel_id in settings.get("temp_channels", {}):
                    try:
                        channel = guild.get_channel(int(channel_id))
                    except (TypeError, ValueError):
                        stale_ids.append(channel_id)
                        continue
                    if not isinstance(channel, discord.VoiceChannel):
                        stale_ids.append(channel_id)
                        continue
                    if not self._human_members(channel):
                        self._schedule_cleanup(
                            guild.id,
                            channel.id,
                            int(settings.get("auto_delete_delay") or 0),
                        )

                if stale_ids:
                    async with self.config.guild(guild).temp_channels() as stored:
                        for channel_id in stale_ids:
                            stored.pop(channel_id, None)
        except asyncio.CancelledError:
            raise
        except Exception:
            log.exception("TempVoice startup cleanup failed.")

    async def _active_owner_channel(
        self,
        guild: discord.Guild,
        owner_id: int,
    ) -> discord.VoiceChannel | None:
        records = await self.config.guild(guild).temp_channels()
        for channel_id, record in records.items():
            if int(record.get("owner_id") or 0) != owner_id:
                continue
            try:
                channel = guild.get_channel(int(channel_id))
            except (TypeError, ValueError):
                continue
            if isinstance(channel, discord.VoiceChannel):
                return channel
        return None

    async def _create_temp_channel_for(
        self,
        member: discord.Member,
        trigger: discord.VoiceChannel,
    ) -> None:
        guild = member.guild
        async with self._guild_lock(guild.id):
            settings = await self.config.guild(guild).all()
            if not settings.get("enabled"):
                return
            if int(settings.get("join_channel_id") or 0) != trigger.id:
                return

            existing = await self._active_owner_channel(guild, member.id)
            if existing is not None:
                self._cancel_cleanup(existing.id)
                try:
                    await member.move_to(
                        existing,
                        reason="TempVoice owner returned to their channel.",
                    )
                except (discord.Forbidden, discord.HTTPException):
                    log.exception(
                        "Could not move TempVoice owner %s to existing channel.",
                        member.id,
                    )
                return

            category = None
            category_id = settings.get("category_id")
            if category_id:
                maybe_category = guild.get_channel(int(category_id))
                if isinstance(maybe_category, discord.CategoryChannel):
                    category = maybe_category
            if category is None:
                category = trigger.category

            name = self._render_channel_name(
                str(settings.get("channel_name_template")
                    or self.DEFAULT_TEMPLATE),
                member,
                guild,
            )
            user_limit = max(
                0, min(int(settings.get("default_user_limit") or 0), 99))

            overwrites = (
                dict(trigger.overwrites)
                if settings.get("clone_trigger_permissions", True)
                else {}
            )
            default_overwrite = overwrites.get(
                guild.default_role,
                discord.PermissionOverwrite(),
            )
            owner_overwrite = overwrites.get(
                member, discord.PermissionOverwrite())
            owner_overwrite.view_channel = True
            owner_overwrite.connect = True
            overwrites[member] = owner_overwrite

            reason = f"TempVoice channel created for {member} ({member.id})."
            try:
                if category is not None:
                    channel = await category.create_voice_channel(
                        name=name,
                        overwrites=overwrites,
                        user_limit=user_limit,
                        reason=reason,
                    )
                else:
                    channel = await guild.create_voice_channel(
                        name=name,
                        overwrites=overwrites,
                        user_limit=user_limit,
                        reason=reason,
                    )
            except (discord.Forbidden, discord.HTTPException):
                log.exception(
                    "Could not create TempVoice channel in guild %s.",
                    guild.id,
                )
                return

            record: TempVoiceRecord = {
                "channel_id": channel.id,
                "owner_id": member.id,
                "join_channel_id": trigger.id,
                "created_at": self._now_ts(),
                "locked": False,
                "user_limit": user_limit,
                "name": channel.name,
                "base_default_connect": default_overwrite.connect,
                "panel_channel_id": None,
                "panel_message_id": None,
                "permitted_ids": [],
            }

            await self._update_record(guild, channel.id, **record)
            try:
                await member.move_to(channel, reason="TempVoice channel created.")
            except (discord.Forbidden, discord.HTTPException):
                log.exception(
                    "Could not move member %s to TempVoice channel %s.",
                    member.id,
                    channel.id,
                )
                await self._delete_temp_channel(
                    guild,
                    channel.id,
                    reason="TempVoice could not move the owner into the channel.",
                )
                return

            message = await self._send_control_panel(guild, channel, record, settings)
            if message:
                await self._update_record(
                    guild,
                    channel.id,
                    panel_channel_id=message.channel.id,
                    panel_message_id=message.id,
                )

    async def _maybe_cleanup_channel(
        self,
        channel: discord.abc.GuildChannel | None,
    ) -> None:
        if not isinstance(channel, discord.VoiceChannel):
            return
        record = await self._get_temp_record(channel.guild, channel.id)
        if not record:
            return
        if self._human_members(channel):
            return
        delay = int((await self.config.guild(channel.guild).auto_delete_delay()) or 0)
        self._schedule_cleanup(channel.guild.id, channel.id, delay)

    @commands.Cog.listener()
    async def on_voice_state_update(
        self,
        member: discord.Member,
        before: discord.VoiceState,
        after: discord.VoiceState,
    ) -> None:
        """Create temp channels from the trigger channel and remove empty ones."""
        if member.bot or before.channel == after.channel:
            return

        if isinstance(after.channel, discord.VoiceChannel):
            self._cancel_cleanup(after.channel.id)
            settings = await self.config.guild(member.guild).all()
            if (
                settings.get("enabled")
                and int(settings.get("join_channel_id") or 0) == after.channel.id
            ):
                await self._create_temp_channel_for(member, after.channel)

        if before.channel is not None:
            await self._maybe_cleanup_channel(before.channel)

    async def handle_control_button(
        self,
        interaction: discord.Interaction,
        action: str,
    ) -> None:
        """Route persistent control panel button interactions."""
        if action == "claim":
            await self._handle_claim(interaction)
            return

        guarded = await self._guard_control(interaction)
        if guarded is None:
            return
        record, channel, member = guarded

        if action == "rename":
            await interaction.response.send_modal(
                RenameChannelModal(self, channel.id, channel.name),
            )
            return
        if action == "limit":
            await interaction.response.send_modal(
                UserLimitModal(
                    self,
                    channel.id,
                    int(record.get("user_limit") or channel.user_limit or 0),
                ),
            )
            return
        if action == "transfer":
            await interaction.response.send_modal(
                MemberTargetModal(
                    self,
                    channel.id,
                    "transfer",
                    "Transfer Ownership",
                    "New owner",
                ),
            )
            return
        if action == "permit":
            await interaction.response.send_modal(
                MemberTargetModal(
                    self,
                    channel.id,
                    "permit",
                    "Permit User",
                    "Member to permit",
                ),
            )
            return
        if action == "remove":
            await interaction.response.send_modal(
                MemberTargetModal(
                    self,
                    channel.id,
                    "remove",
                    "Remove User",
                    "Member to remove",
                ),
            )
            return
        if action == "lock":
            await interaction.response.defer(ephemeral=True)
            await self._toggle_lock(interaction, channel, record, member)

    async def _toggle_lock(
        self,
        interaction: discord.Interaction,
        channel: discord.VoiceChannel,
        record: TempVoiceRecord,
        actor: discord.Member,
    ) -> None:
        locked = not bool(record.get("locked"))
        overwrite = channel.overwrites_for(channel.guild.default_role)
        base_connect = record.get("base_default_connect")
        if base_connect not in (True, False, None):
            base_connect = None
        overwrite.connect = False if locked else base_connect
        try:
            if overwrite.is_empty():
                await channel.set_permissions(
                    channel.guild.default_role,
                    overwrite=None,
                    reason=f"TempVoice lock toggled by {actor} ({actor.id}).",
                )
            else:
                await channel.set_permissions(
                    channel.guild.default_role,
                    overwrite=overwrite,
                    reason=f"TempVoice lock toggled by {actor} ({actor.id}).",
                )
        except discord.Forbidden:
            await interaction.followup.send(
                "I do not have permission to edit that channel.",
                ephemeral=True,
            )
            return
        except discord.HTTPException:
            await interaction.followup.send(
                "Discord rejected that channel update.",
                ephemeral=True,
            )
            return

        updated = await self._update_record(channel.guild, channel.id, locked=locked)
        await self._update_control_panel(
            channel.guild,
            channel,
            updated,
            interaction=interaction,
        )
        await interaction.followup.send(
            f"{channel.mention} is now {'locked' if locked else 'unlocked'}.",
            ephemeral=True,
            allowed_mentions=discord.AllowedMentions.none(),
        )

    async def _handle_claim(self, interaction: discord.Interaction) -> None:
        guarded = await self._guard_control(interaction, require_owner=False)
        if guarded is None:
            return
        record, channel, member = guarded
        if not self._member_in_channel(member, channel):
            await self._send_interaction_message(
                interaction,
                "Join the temporary voice channel before claiming it.",
            )
            return
        if self._owner_present(channel.guild, record, channel) and not (
            member.guild_permissions.administrator
            or member.guild_permissions.manage_channels
        ):
            await self._send_interaction_message(
                interaction,
                "The current owner is still in the channel.",
            )
            return

        await interaction.response.defer(ephemeral=True)
        try:
            await self._ensure_member_override(
                channel,
                member,
                reason=f"TempVoice claimed by {member} ({member.id}).",
            )
        except (discord.Forbidden, discord.HTTPException):
            await interaction.followup.send(
                "I could not update that channel owner.",
                ephemeral=True,
            )
            return

        updated = await self._update_record(
            channel.guild,
            channel.id,
            owner_id=member.id,
        )
        await self._update_control_panel(
            channel.guild,
            channel,
            updated,
            interaction=interaction,
        )
        await interaction.followup.send(
            f"You now own {channel.mention}.",
            ephemeral=True,
        )

    async def handle_rename_submit(
        self,
        interaction: discord.Interaction,
        channel_id: int,
        raw_name: str,
    ) -> None:
        guarded = await self._guard_control(interaction, channel_id=channel_id)
        if guarded is None:
            return
        _record, channel, member = guarded
        name = self._clean_channel_name(raw_name)
        await interaction.response.defer(ephemeral=True)
        try:
            await channel.edit(
                name=name,
                reason=f"TempVoice renamed by {member} ({member.id}).",
            )
        except discord.Forbidden:
            await interaction.followup.send(
                "I do not have permission to rename that channel.",
                ephemeral=True,
            )
            return
        except discord.HTTPException:
            await interaction.followup.send(
                "Discord rejected that channel name.",
                ephemeral=True,
            )
            return

        updated = await self._update_record(channel.guild, channel.id, name=name)
        await self._update_control_panel(
            channel.guild,
            channel,
            updated,
            interaction=interaction,
        )
        await interaction.followup.send(
            f"Renamed the channel to **{discord.utils.escape_markdown(name)}**.",
            ephemeral=True,
        )

    async def handle_limit_submit(
        self,
        interaction: discord.Interaction,
        channel_id: int,
        raw_limit: str,
    ) -> None:
        guarded = await self._guard_control(interaction, channel_id=channel_id)
        if guarded is None:
            return
        _record, channel, member = guarded
        try:
            limit = int(raw_limit.strip())
        except ValueError:
            await self._send_interaction_message(
                interaction,
                "User limit must be a number from 0 to 99.",
            )
            return
        if limit < 0 or limit > 99:
            await self._send_interaction_message(
                interaction,
                "User limit must be between 0 and 99.",
            )
            return

        await interaction.response.defer(ephemeral=True)
        try:
            await channel.edit(
                user_limit=limit,
                reason=f"TempVoice user limit changed by {member} ({member.id}).",
            )
        except discord.Forbidden:
            await interaction.followup.send(
                "I do not have permission to edit that channel.",
                ephemeral=True,
            )
            return
        except discord.HTTPException:
            await interaction.followup.send(
                "Discord rejected that user limit.",
                ephemeral=True,
            )
            return

        updated = await self._update_record(channel.guild, channel.id, user_limit=limit)
        await self._update_control_panel(
            channel.guild,
            channel,
            updated,
            interaction=interaction,
        )
        await interaction.followup.send(
            f"User limit set to {self._limit_text(limit)}.",
            ephemeral=True,
        )

    async def handle_member_submit(
        self,
        interaction: discord.Interaction,
        channel_id: int,
        action: str,
        raw_member: str,
    ) -> None:
        guarded = await self._guard_control(interaction, channel_id=channel_id)
        if guarded is None or interaction.guild is None:
            return
        record, channel, actor = guarded

        try:
            target = await self._resolve_member(interaction.guild, raw_member)
        except commands.BadArgument as error:
            await self._send_interaction_message(interaction, str(error))
            return

        if action == "transfer":
            await self._transfer_owner(interaction, channel, target, actor)
            return
        if action == "permit":
            await self._permit_member(interaction, channel, record, target, actor)
            return
        if action == "remove":
            await self._remove_member(interaction, channel, record, target, actor)

    async def _transfer_owner(
        self,
        interaction: discord.Interaction,
        channel: discord.VoiceChannel,
        target: discord.Member,
        actor: discord.Member,
    ) -> None:
        if target.bot:
            await self._send_interaction_message(
                interaction,
                "Ownership cannot be transferred to a bot.",
            )
            return
        if not self._member_in_channel(target, channel):
            await self._send_interaction_message(
                interaction,
                "The new owner must be in the voice channel.",
            )
            return

        await interaction.response.defer(ephemeral=True)
        try:
            await self._ensure_member_override(
                channel,
                target,
                reason=f"TempVoice ownership transferred by {actor} ({actor.id}).",
            )
        except (discord.Forbidden, discord.HTTPException):
            await interaction.followup.send(
                "I could not update that channel owner.",
                ephemeral=True,
            )
            return

        updated = await self._update_record(
            channel.guild,
            channel.id,
            owner_id=target.id,
        )
        await self._update_control_panel(
            channel.guild,
            channel,
            updated,
            interaction=interaction,
        )
        await interaction.followup.send(
            f"Ownership transferred to {target.mention}.",
            ephemeral=True,
        )

    async def _permit_member(
        self,
        interaction: discord.Interaction,
        channel: discord.VoiceChannel,
        record: TempVoiceRecord,
        target: discord.Member,
        actor: discord.Member,
    ) -> None:
        await interaction.response.defer(ephemeral=True)
        try:
            await self._ensure_member_override(
                channel,
                target,
                reason=f"TempVoice access granted by {actor} ({actor.id}).",
            )
        except (discord.Forbidden, discord.HTTPException):
            await interaction.followup.send(
                "I could not permit that member.",
                ephemeral=True,
            )
            return

        permitted_ids = list(record.get("permitted_ids", []))
        if target.id not in permitted_ids:
            permitted_ids.append(target.id)
        updated = await self._update_record(
            channel.guild,
            channel.id,
            permitted_ids=permitted_ids,
        )
        await self._update_control_panel(
            channel.guild,
            channel,
            updated,
            interaction=interaction,
        )
        await interaction.followup.send(
            f"{target.mention} can now join {channel.mention}.",
            ephemeral=True,
        )

    async def _remove_member(
        self,
        interaction: discord.Interaction,
        channel: discord.VoiceChannel,
        record: TempVoiceRecord,
        target: discord.Member,
        actor: discord.Member,
    ) -> None:
        if int(record.get("owner_id") or 0) == target.id:
            await self._send_interaction_message(
                interaction,
                "Transfer ownership before removing the owner.",
            )
            return

        await interaction.response.defer(ephemeral=True)
        try:
            await channel.set_permissions(
                target,
                overwrite=None,
                reason=f"TempVoice access removed by {actor} ({actor.id}).",
            )
            if self._member_in_channel(target, channel):
                await target.move_to(
                    None,
                    reason=f"Removed from TempVoice by {actor} ({actor.id}).",
                )
        except discord.Forbidden:
            await interaction.followup.send(
                "I do not have permission to remove that member.",
                ephemeral=True,
            )
            return
        except discord.HTTPException:
            await interaction.followup.send(
                "Discord rejected that member update.",
                ephemeral=True,
            )
            return

        permitted_ids = [
            member_id
            for member_id in record.get("permitted_ids", [])
            if int(member_id) != target.id
        ]
        updated = await self._update_record(
            channel.guild,
            channel.id,
            permitted_ids=permitted_ids,
        )
        await self._update_control_panel(
            channel.guild,
            channel,
            updated,
            interaction=interaction,
        )
        await interaction.followup.send(
            f"{target.mention} was removed from {channel.mention}.",
            ephemeral=True,
        )

    async def handle_modal_error(
        self,
        interaction: discord.Interaction,
        error: Exception,
    ) -> None:
        log.exception(
            "TempVoice modal failed.",
            exc_info=(type(error), error, error.__traceback__),
        )
        await self._send_interaction_message(
            interaction,
            "I could not process that control panel action.",
        )

    def _settings_embed(
        self,
        guild: discord.Guild,
        settings: GuildSettings,
    ) -> discord.Embed:
        embed = discord.Embed(
            title="TempVoice Settings",
            color=self.SUCCESS_COLOR if settings.get(
                "enabled") else self.ERROR_COLOR,
        )
        embed.add_field(
            name="Enabled",
            value="Yes" if settings.get("enabled") else "No",
            inline=True,
        )
        embed.add_field(
            name="Join Channel",
            value=self._channel_ref(guild, settings.get("join_channel_id")),
            inline=True,
        )
        embed.add_field(
            name="Category",
            value=self._channel_ref(guild, settings.get("category_id")),
            inline=True,
        )
        panel_channel_id = settings.get("panel_channel_id")
        panel_value = (
            self._channel_ref(guild, panel_channel_id)
            if panel_channel_id
            else "Voice channel chat"
        )
        embed.add_field(name="Control Panels", value=panel_value, inline=True)
        embed.add_field(
            name="Default User Limit",
            value=self._limit_text(settings.get("default_user_limit")),
            inline=True,
        )
        embed.add_field(
            name="Auto Delete Delay",
            value=f"{int(settings.get('auto_delete_delay') or 0)} seconds",
            inline=True,
        )
        embed.add_field(
            name="Name Template",
            value=f"`{settings.get('channel_name_template') or self.DEFAULT_TEMPLATE}`",
            inline=False,
        )
        temp_channels = settings.get("temp_channels", {})
        embed.add_field(
            name="Active Channels",
            value=str(len(temp_channels)),
            inline=True,
        )
        return embed

    @commands.hybrid_group(
        name="tempvoice",
        aliases=["tv"],
        invoke_without_command=True,
        description="Manage temporary voice channels.",
    )
    @commands.guild_only()
    @commands.bot_has_permissions(embed_links=True)
    async def tempvoice(self, ctx: commands.Context) -> None:
        """Manage temporary voice channels."""
        await ctx.send_help(ctx.command)

    @tempvoice.command(
        name="settings",
        aliases=["status"],
        description="Show TempVoice settings.",
    )
    @commands.guild_only()
    @commands.bot_has_permissions(embed_links=True)
    async def tempvoice_settings(self, ctx: commands.Context) -> None:
        """Show TempVoice settings."""
        assert ctx.guild is not None
        settings = await self.config.guild(ctx.guild).all()
        await ctx.send(embed=self._settings_embed(ctx.guild, settings))

    @tempvoice.command(
        name="setup",
        description="Configure the join-to-create voice channel.",
    )
    @commands.guild_only()
    @commands.admin_or_permissions(manage_guild=True)
    @commands.bot_has_permissions(
        manage_channels=True,
        move_members=True,
        embed_links=True,
    )
    @app_commands.describe(
        join_channel="Existing voice channel users join to create temporary channels",
        category="Category where temporary voice channels should be created",
    )
    async def tempvoice_setup(
        self,
        ctx: commands.Context,
        join_channel: discord.VoiceChannel | None = None,
        category: discord.CategoryChannel | None = None,
    ) -> None:
        """Set up or create the join-to-create voice channel."""
        assert ctx.guild is not None
        if join_channel is None:
            try:
                join_channel = await ctx.guild.create_voice_channel(
                    "Join to Create",
                    category=category,
                    reason=f"TempVoice setup by {ctx.author} ({ctx.author.id}).",
                )
            except discord.Forbidden:
                await ctx.send("I do not have permission to create a voice channel.")
                return
            except discord.HTTPException:
                await ctx.send("Discord rejected the voice channel creation.")
                return

        if category is None:
            category = join_channel.category

        await self.config.guild(ctx.guild).enabled.set(True)
        await self.config.guild(ctx.guild).join_channel_id.set(join_channel.id)
        await self.config.guild(ctx.guild).category_id.set(
            category.id if category else None,
        )

        await ctx.send(
            f"TempVoice is enabled. Users who join {join_channel.mention} will get a temporary voice channel.",
        )

    @tempvoice.command(name="enable", description="Enable temporary voice creation.")
    @commands.guild_only()
    @commands.admin_or_permissions(manage_guild=True)
    async def tempvoice_enable(self, ctx: commands.Context) -> None:
        """Enable temporary voice creation."""
        assert ctx.guild is not None
        join_channel_id = await self.config.guild(ctx.guild).join_channel_id()
        if not join_channel_id:
            await ctx.send(
                "Set a join channel first with `[p]tempvoice setup` or `[p]tempvoice joinchannel`.",
            )
            return
        await self.config.guild(ctx.guild).enabled.set(True)
        await ctx.send("TempVoice is enabled.")

    @tempvoice.command(name="disable", description="Disable temporary voice creation.")
    @commands.guild_only()
    @commands.admin_or_permissions(manage_guild=True)
    async def tempvoice_disable(self, ctx: commands.Context) -> None:
        """Disable temporary voice creation without deleting active channels."""
        assert ctx.guild is not None
        await self.config.guild(ctx.guild).enabled.set(False)
        await ctx.send(
            "TempVoice is disabled. Existing temporary channels are not deleted.",
        )

    @tempvoice.command(
        name="joinchannel",
        aliases=["trigger"],
        description="Set the join-to-create voice channel.",
    )
    @commands.guild_only()
    @commands.admin_or_permissions(manage_guild=True)
    async def tempvoice_joinchannel(
        self,
        ctx: commands.Context,
        channel: discord.VoiceChannel,
    ) -> None:
        """Set the voice channel that creates temporary channels."""
        assert ctx.guild is not None
        await self.config.guild(ctx.guild).join_channel_id.set(channel.id)
        await self.config.guild(ctx.guild).enabled.set(True)
        await ctx.send(
            f"Users who join {channel.mention} will get a temporary voice channel.",
        )

    @tempvoice.command(
        name="category",
        description="Set or clear the temp voice category.",
    )
    @commands.guild_only()
    @commands.admin_or_permissions(manage_guild=True)
    async def tempvoice_category(
        self,
        ctx: commands.Context,
        category: discord.CategoryChannel | None = None,
    ) -> None:
        """Set the category where temporary voice channels are created."""
        assert ctx.guild is not None
        await self.config.guild(ctx.guild).category_id.set(
            category.id if category else None,
        )
        if category:
            await ctx.send(
                f"Temporary voice channels will be created in **{category.name}**.",
            )
        else:
            await ctx.send(
                "Temporary voice channels will use the join channel's category.",
            )

    @tempvoice.command(
        name="panelchannel",
        aliases=["panel"],
        description="Set or clear the control panel text channel.",
    )
    @commands.guild_only()
    @commands.admin_or_permissions(manage_guild=True)
    async def tempvoice_panelchannel(
        self,
        ctx: commands.Context,
        channel: discord.TextChannel | None = None,
    ) -> None:
        """Set where control panels are posted, or clear to use voice channel chat."""
        assert ctx.guild is not None
        if channel is not None:
            me = ctx.guild.me
            if me is None:
                await ctx.send("I could not check my channel permissions.")
                return
            permissions = channel.permissions_for(me)
            if not permissions.send_messages or not permissions.embed_links:
                await ctx.send(
                    f"I need Send Messages and Embed Links in {channel.mention}.",
                )
                return
        await self.config.guild(ctx.guild).panel_channel_id.set(
            channel.id if channel else None,
        )
        if channel:
            await ctx.send(f"Control panels will be posted in {channel.mention}.")
        else:
            await ctx.send(
                "Control panels will be posted in the temporary voice channel chat when Discord allows it.",
            )

    @tempvoice.command(
        name="defaultlimit",
        aliases=["limit"],
        description="Set the default user limit.",
    )
    @commands.guild_only()
    @commands.admin_or_permissions(manage_guild=True)
    async def tempvoice_defaultlimit(self, ctx: commands.Context, limit: int) -> None:
        """Set the default user limit for newly created temporary channels."""
        assert ctx.guild is not None
        if limit < 0 or limit > 99:
            await ctx.send(
                "Default user limit must be between 0 and 99. Use 0 for no limit.",
            )
            return
        await self.config.guild(ctx.guild).default_user_limit.set(limit)
        await ctx.send(f"Default user limit set to {self._limit_text(limit)}.")

    @tempvoice.command(
        name="template",
        description="Set the temporary channel name template.",
    )
    @commands.guild_only()
    @commands.admin_or_permissions(manage_guild=True)
    async def tempvoice_template(self, ctx: commands.Context, *, template: str) -> None:
        """Set the temporary voice channel naming template."""
        assert ctx.guild is not None
        template = self._clean_channel_name(template)
        await self.config.guild(ctx.guild).channel_name_template.set(template)
        await ctx.send(
            "Temporary voice channels will use this template: "
            f"`{discord.utils.escape_markdown(template)}`",
        )

    @tempvoice.command(
        name="autodelete",
        description="Set the empty-channel delete delay.",
    )
    @commands.guild_only()
    @commands.admin_or_permissions(manage_guild=True)
    async def tempvoice_autodelete(self, ctx: commands.Context, seconds: int) -> None:
        """Set how long empty temporary channels wait before deletion."""
        assert ctx.guild is not None
        if seconds < 0 or seconds > self.MAX_DELETE_DELAY:
            await ctx.send(
                f"Auto delete delay must be between 0 and {self.MAX_DELETE_DELAY} seconds.",
            )
            return
        await self.config.guild(ctx.guild).auto_delete_delay.set(seconds)
        await ctx.send(
            f"Empty temporary channels will be deleted after {seconds} seconds.",
        )

    @tempvoice.command(name="list", description="List active temporary voice channels.")
    @commands.guild_only()
    @commands.bot_has_permissions(embed_links=True)
    async def tempvoice_list(self, ctx: commands.Context) -> None:
        """List active temporary voice channels."""
        assert ctx.guild is not None
        records = await self.config.guild(ctx.guild).temp_channels()
        if not records:
            await ctx.send("There are no active temporary voice channels.")
            return

        lines = []
        stale = 0
        for channel_id, record in records.items():
            try:
                channel = ctx.guild.get_channel(int(channel_id))
            except (TypeError, ValueError):
                channel = None
            if not isinstance(channel, discord.VoiceChannel):
                stale += 1
                continue
            owner_id = record.get("owner_id")
            owner = f"<@{owner_id}>" if owner_id else "Unclaimed"
            lines.append(
                f"{channel.mention} - owner {owner}, {len(self._human_members(channel))} member(s), "
                f"{'locked' if record.get('locked') else 'unlocked'}",
            )

        embed = discord.Embed(
            title="Active TempVoice Channels",
            color=self.DEFAULT_COLOR,
        )
        embed.description = "\n".join(
            lines[:20]) or "No active channels found."
        if len(lines) > 20:
            embed.set_footer(
                text=f"Showing 20 of {len(lines)} active channels.")
        elif stale:
            embed.set_footer(
                text=f"{stale} stale record(s) can be removed with cleanup.",
            )
        await ctx.send(embed=embed, allowed_mentions=discord.AllowedMentions.none())

    @tempvoice.command(
        name="claim",
        description="Claim your current temporary voice channel.",
    )
    @commands.guild_only()
    @commands.bot_has_permissions(manage_channels=True)
    async def tempvoice_claim(self, ctx: commands.Context) -> None:
        """Claim the temporary voice channel you are currently in if the owner is gone."""
        assert ctx.guild is not None
        if not isinstance(ctx.author, discord.Member):
            return
        if not ctx.author.voice or not isinstance(
            ctx.author.voice.channel,
            discord.VoiceChannel,
        ):
            await ctx.send("Join a temporary voice channel before claiming it.")
            return
        channel = ctx.author.voice.channel
        record = await self._get_temp_record(ctx.guild, channel.id)
        if not record:
            await ctx.send("You are not in a TempVoice-managed channel.")
            return
        if self._owner_present(ctx.guild, record, channel) and not (
            ctx.author.guild_permissions.administrator
            or ctx.author.guild_permissions.manage_channels
        ):
            await ctx.send("The current owner is still in the channel.")
            return

        try:
            await self._ensure_member_override(
                channel,
                ctx.author,
                reason=f"TempVoice claimed by {ctx.author} ({ctx.author.id}).",
            )
        except (discord.Forbidden, discord.HTTPException):
            await ctx.send("I could not update that channel owner.")
            return

        updated = await self._update_record(
            ctx.guild,
            channel.id,
            owner_id=ctx.author.id,
        )
        await self._update_control_panel(ctx.guild, channel, updated)
        await ctx.send(f"You now own {channel.mention}.")

    @tempvoice.command(
        name="cleanup",
        description="Delete empty temp channels and stale records.",
    )
    @commands.guild_only()
    @commands.admin_or_permissions(manage_channels=True)
    @commands.bot_has_permissions(manage_channels=True)
    async def tempvoice_cleanup(self, ctx: commands.Context) -> None:
        """Delete empty temporary channels and remove stale records."""
        assert ctx.guild is not None
        records = await self.config.guild(ctx.guild).temp_channels()
        stale_ids: list[str] = []
        empty_ids: list[int] = []

        for channel_id in records:
            try:
                channel = ctx.guild.get_channel(int(channel_id))
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
                ctx.guild,
                channel_id,
                reason=f"TempVoice cleanup by {ctx.author} ({ctx.author.id}).",
            )
            deleted += 1

        if stale_ids:
            async with self.config.guild(ctx.guild).temp_channels() as stored:
                for channel_id in stale_ids:
                    stored.pop(channel_id, None)

        await ctx.send(
            f"Deleted {deleted} empty channel(s) and removed {len(stale_ids)} stale record(s).",
        )
