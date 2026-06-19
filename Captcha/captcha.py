"""Button-and-modal captcha verification for Red-DiscordBot."""

from __future__ import annotations

import logging
import secrets
from typing import Any, Dict, Optional, Tuple

import discord
from redbot.core import Config, commands
from redbot.core.bot import Red
from redbot.core.utils.chat_formatting import box, pagify

log = logging.getLogger("red.taakoscogs.captcha")

PanelRecord = Dict[str, Any]
ChallengeKey = Tuple[int, int, int]


class CaptchaCodeModal(discord.ui.Modal):
    """Ask one member to repeat the random code shown in the modal title."""

    def __init__(
        self,
        cog: "Captcha",
        guild_id: int,
        panel_message_id: int,
        member_id: int,
        code: str,
    ) -> None:
        super().__init__(title=f"Verification Code: {code}", timeout=300)
        self.cog = cog
        self.guild_id = guild_id
        self.panel_message_id = panel_message_id
        self.member_id = member_id
        self.code = code
        self.answer = discord.ui.TextInput(
            label="Enter the code shown in the title",
            placeholder="Type the six-character code",
            required=True,
            min_length=len(code),
            max_length=len(code),
        )
        self.add_item(self.answer)

    async def on_submit(self, interaction: discord.Interaction) -> None:
        await self.cog.complete_challenge(
            interaction,
            self.guild_id,
            self.panel_message_id,
            self.member_id,
            self.code,
            str(self.answer.value),
        )

    async def on_timeout(self) -> None:
        self.cog.clear_challenge(
            self.guild_id,
            self.panel_message_id,
            self.member_id,
            self.code,
        )

    async def on_error(self, interaction: discord.Interaction, error: Exception) -> None:
        log.exception(
            "Captcha verification modal failed.",
            exc_info=(type(error), error, error.__traceback__),
        )
        self.cog.clear_challenge(
            self.guild_id,
            self.panel_message_id,
            self.member_id,
            self.code,
        )
        message = "I could not complete that verification. Please try again."
        if interaction.response.is_done():
            await interaction.followup.send(message, ephemeral=True)
        else:
            await interaction.response.send_message(message, ephemeral=True)


class CaptchaPanelView(discord.ui.View):
    """Persistent verification button for one configured panel."""

    def __init__(self, cog: "Captcha", message_id: int, label: str = "Verify") -> None:
        super().__init__(timeout=None)
        self.cog = cog
        self.message_id = message_id
        self.verify.label = label[:80] or "Verify"
        self.verify.custom_id = f"taakoscogs:captcha:verify:{message_id}"

    @discord.ui.button(
        label="Verify",
        emoji="\N{WHITE HEAVY CHECK MARK}",
        style=discord.ButtonStyle.success,
        custom_id="taakoscogs:captcha:verify",
    )
    async def verify(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ) -> None:
        await self.cog.start_challenge(interaction, self.message_id)


class Captcha(commands.Cog):
    """Give members a configured role after a randomized modal challenge."""

    CONFIG_IDENTIFIER = 2026061901
    CODE_LENGTH = 6
    CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
    DEFAULT_TITLE = "Verification Required"
    DEFAULT_DESCRIPTION = (
        "Press **Verify** below. A modal will show a random code in its title. "
        "Enter that code correctly to receive the verification role."
    )
    DEFAULT_COLOR = 0x57F287

    def __init__(self, bot: Red) -> None:
        self.bot = bot
        self.config = Config.get_conf(
            self,
            identifier=self.CONFIG_IDENTIFIER,
            force_registration=True,
        )
        self.config.register_guild(panels={})
        self._panel_views: Dict[Tuple[int, int], CaptchaPanelView] = {}
        self._active_challenges: Dict[ChallengeKey, str] = {}
        self._last_codes: Dict[ChallengeKey, str] = {}

    async def cog_load(self) -> None:
        all_guilds = await self.config.all_guilds()
        for guild_id, guild_data in all_guilds.items():
            for message_id, record in (guild_data.get("panels") or {}).items():
                try:
                    panel_message_id = int(message_id)
                except (TypeError, ValueError):
                    continue
                view = CaptchaPanelView(
                    self,
                    panel_message_id,
                    str(record.get("button_label") or "Verify"),
                )
                self.bot.add_view(view, message_id=panel_message_id)
                self._panel_views[(int(guild_id), panel_message_id)] = view

    def cog_unload(self) -> None:
        for view in self._panel_views.values():
            view.stop()
        self._panel_views.clear()
        self._active_challenges.clear()
        self._last_codes.clear()

    async def red_delete_data_for_user(self, *, requester: str, user_id: int) -> None:
        """Captcha does not persistently store user data."""
        for key in list(self._active_challenges):
            if key[2] == user_id:
                self._active_challenges.pop(key, None)
        for key in list(self._last_codes):
            if key[2] == user_id:
                self._last_codes.pop(key, None)

    @classmethod
    def _generate_code(cls, previous: Optional[str] = None) -> str:
        while True:
            code = "".join(secrets.choice(cls.CODE_ALPHABET) for _ in range(cls.CODE_LENGTH))
            if code != previous:
                return code

    @staticmethod
    def _dangerous_role_permissions(role: discord.Role) -> bool:
        permissions = role.permissions
        return any(
            (
                permissions.administrator,
                permissions.manage_guild,
                permissions.manage_roles,
                permissions.manage_channels,
                permissions.kick_members,
                permissions.ban_members,
                permissions.moderate_members,
                permissions.manage_webhooks,
            )
        )

    def _validate_role(self, guild: discord.Guild, role: discord.Role) -> None:
        me = guild.me
        if role.guild.id != guild.id:
            raise commands.BadArgument("The verification role must belong to this server.")
        if role.is_default() or role.managed:
            raise commands.BadArgument("Choose a normal role managed by server staff.")
        if self._dangerous_role_permissions(role):
            raise commands.BadArgument(
                "The verification role cannot have administrative or moderation permissions."
            )
        if me is None or not me.guild_permissions.manage_roles:
            raise commands.CommandError("I need the Manage Roles permission.")
        if role >= me.top_role:
            raise commands.CommandError(
                "Move my highest role above the verification role before using it."
            )

    async def _get_panel(self, guild: discord.Guild, message_id: int) -> PanelRecord:
        panels = await self.config.guild(guild).panels()
        record = panels.get(str(message_id))
        if not isinstance(record, dict):
            raise commands.CommandError("That captcha panel is no longer configured.")
        return record

    async def _save_panel(
        self,
        guild: discord.Guild,
        message: discord.Message,
        role: discord.Role,
        label: str,
        view: CaptchaPanelView,
    ) -> None:
        record: PanelRecord = {
            "message_id": message.id,
            "channel_id": message.channel.id,
            "role_id": role.id,
            "button_label": label,
        }
        async with self.config.guild(guild).panels() as panels:
            panels[str(message.id)] = record
        key = (guild.id, message.id)
        previous = self._panel_views.pop(key, None)
        if previous is not None:
            previous.stop()
        self._panel_views[key] = view

    async def _remove_panel_record(self, guild_id: int, message_id: int) -> bool:
        removed = False
        async with self.config.guild_from_id(guild_id).panels() as panels:
            removed = panels.pop(str(message_id), None) is not None
        view = self._panel_views.pop((guild_id, message_id), None)
        if view is not None:
            view.stop()
        for key in list(self._active_challenges):
            if key[:2] == (guild_id, message_id):
                self._active_challenges.pop(key, None)
        for key in list(self._last_codes):
            if key[:2] == (guild_id, message_id):
                self._last_codes.pop(key, None)
        return removed

    async def _install_panel(
        self,
        guild: discord.Guild,
        message: discord.Message,
        role: discord.Role,
        label: str,
    ) -> None:
        label = label.strip()[:80] or "Verify"
        view = CaptchaPanelView(self, message.id, label)
        try:
            await message.edit(view=view)
        except discord.HTTPException as exc:
            raise commands.CommandError("I could not attach the verification button.") from exc
        await self._save_panel(guild, message, role, label, view)

    async def start_challenge(
        self,
        interaction: discord.Interaction,
        message_id: int,
    ) -> None:
        if not interaction.guild or not isinstance(interaction.user, discord.Member):
            await interaction.response.send_message(
                "This verification button only works in a server.",
                ephemeral=True,
            )
            return
        if interaction.user.bot:
            await interaction.response.send_message("Bots cannot verify.", ephemeral=True)
            return
        if interaction.message is None or interaction.message.id != message_id:
            await interaction.response.send_message(
                "This verification button is not attached to the expected message.",
                ephemeral=True,
            )
            return
        try:
            panel = await self._get_panel(interaction.guild, message_id)
            if str(panel.get("channel_id")) != str(interaction.channel_id):
                raise commands.CommandError("This verification panel is not valid here.")
            role = interaction.guild.get_role(int(panel.get("role_id") or 0))
            if role is None:
                raise commands.CommandError(
                    "The verification role no longer exists. Please contact server staff."
                )
            self._validate_role(interaction.guild, role)
        except commands.CommandError as error:
            await interaction.response.send_message(str(error), ephemeral=True)
            return
        if role in interaction.user.roles:
            await interaction.response.send_message(
                f"You already have {role.mention}.",
                ephemeral=True,
            )
            return
        key = (interaction.guild.id, message_id, interaction.user.id)
        code = self._generate_code(self._last_codes.get(key))
        self._last_codes[key] = code
        self._active_challenges[key] = code
        await interaction.response.send_modal(
            CaptchaCodeModal(
                self,
                interaction.guild.id,
                message_id,
                interaction.user.id,
                code,
            )
        )

    def clear_challenge(
        self,
        guild_id: int,
        message_id: int,
        member_id: int,
        expected_code: str,
    ) -> None:
        key = (guild_id, message_id, member_id)
        if self._active_challenges.get(key) == expected_code:
            self._active_challenges.pop(key, None)

    async def complete_challenge(
        self,
        interaction: discord.Interaction,
        guild_id: int,
        message_id: int,
        member_id: int,
        expected_code: str,
        answer: str,
    ) -> None:
        if (
            not interaction.guild
            or not isinstance(interaction.user, discord.Member)
            or interaction.guild.id != guild_id
            or interaction.user.id != member_id
        ):
            await interaction.response.send_message(
                "This verification challenge is not valid here.",
                ephemeral=True,
            )
            return
        key = (guild_id, message_id, member_id)
        if self._active_challenges.get(key) != expected_code:
            await interaction.response.send_message(
                "That code has expired. Click Verify to receive a new code.",
                ephemeral=True,
            )
            return
        entered = answer.strip().upper()
        if not secrets.compare_digest(entered, expected_code):
            self._active_challenges.pop(key, None)
            await interaction.response.send_message(
                "Incorrect code. Click Verify to try again with a new code.",
                ephemeral=True,
            )
            return
        try:
            panel = await self._get_panel(interaction.guild, message_id)
            role = interaction.guild.get_role(int(panel.get("role_id") or 0))
            if role is None:
                raise commands.CommandError("The verification role no longer exists.")
            self._validate_role(interaction.guild, role)
            await interaction.user.add_roles(
                role,
                reason=f"Captcha completed from panel {message_id}",
            )
        except commands.CommandError as error:
            self._active_challenges.pop(key, None)
            await interaction.response.send_message(str(error), ephemeral=True)
            return
        except discord.HTTPException:
            self._active_challenges.pop(key, None)
            await interaction.response.send_message(
                "I could not assign the verification role. Please contact server staff.",
                ephemeral=True,
            )
            return
        self._active_challenges.pop(key, None)
        await interaction.response.send_message(
            f"Verification successful. You received {role.mention}.",
            ephemeral=True,
        )

    @commands.group(name="captcha", aliases=["verification"], invoke_without_command=True)
    @commands.guild_only()
    @commands.bot_has_permissions(embed_links=True)
    async def captcha(self, ctx: commands.Context) -> None:
        """Configure button-and-modal captcha verification."""
        assert ctx.guild is not None
        panels = await self.config.guild(ctx.guild).panels()
        embed = discord.Embed(
            title="Captcha Verification",
            description=(
                "Verification codes are randomized for every button click and are shown "
                "only in the modal title."
            ),
            color=self.DEFAULT_COLOR,
        )
        embed.add_field(name="Configured Panels", value=str(len(panels)), inline=True)
        embed.add_field(
            name="Setup",
            value=(
                f"`{ctx.clean_prefix}captcha post #channel @Verified`\n"
                f"`{ctx.clean_prefix}captcha attach <message-link> @Verified`"
            ),
            inline=False,
        )
        await ctx.send(embed=embed)

    @captcha.command(name="post")
    @commands.admin_or_permissions(manage_guild=True)
    @commands.bot_has_permissions(send_messages=True, embed_links=True, manage_roles=True)
    async def captcha_post(
        self,
        ctx: commands.Context,
        channel: discord.TextChannel,
        role: discord.Role,
        *,
        label: str = "Verify",
    ) -> None:
        """Post the predefined captcha message and configure its success role."""
        assert ctx.guild is not None
        try:
            self._validate_role(ctx.guild, role)
        except commands.CommandError as error:
            await ctx.send(str(error))
            return
        embed = discord.Embed(
            title=self.DEFAULT_TITLE,
            description=self.DEFAULT_DESCRIPTION,
            color=self.DEFAULT_COLOR,
        )
        embed.set_footer(text="Each verification attempt uses a new code.")
        message = None
        try:
            message = await channel.send(embed=embed)
            await self._install_panel(ctx.guild, message, role, label)
        except (commands.CommandError, discord.HTTPException) as error:
            if message is not None:
                try:
                    await message.delete()
                except discord.HTTPException:
                    pass
            await ctx.send(str(error))
            return
        await ctx.send(f"Captcha panel posted: {message.jump_url}")

    @captcha.command(name="attach")
    @commands.admin_or_permissions(manage_guild=True)
    @commands.bot_has_permissions(manage_roles=True)
    async def captcha_attach(
        self,
        ctx: commands.Context,
        message: discord.Message,
        role: discord.Role,
        *,
        label: str = "Verify",
    ) -> None:
        """Attach a captcha button to an existing bot-authored message."""
        assert ctx.guild is not None
        if message.guild is None or message.guild.id != ctx.guild.id:
            await ctx.send("The message must be in this server.")
            return
        if ctx.guild.me is None or message.author.id != ctx.guild.me.id:
            await ctx.send("I can only attach buttons to messages sent by this bot.")
            return
        panels = await self.config.guild(ctx.guild).panels()
        if message.components and str(message.id) not in panels:
            await ctx.send("That message already has components I do not manage.")
            return
        try:
            self._validate_role(ctx.guild, role)
            await self._install_panel(ctx.guild, message, role, label)
        except commands.CommandError as error:
            await ctx.send(str(error))
            return
        await ctx.send(f"Captcha button attached: {message.jump_url}")

    @captcha.command(name="remove")
    @commands.admin_or_permissions(manage_guild=True)
    async def captcha_remove(
        self,
        ctx: commands.Context,
        message: discord.Message,
    ) -> None:
        """Remove a configured captcha button from a message."""
        assert ctx.guild is not None
        panels = await self.config.guild(ctx.guild).panels()
        if str(message.id) not in panels:
            await ctx.send("That message is not a configured captcha panel.")
            return
        try:
            await message.edit(view=None)
        except discord.HTTPException as exc:
            await ctx.send(f"I could not remove the button: {exc}")
            return
        await self._remove_panel_record(ctx.guild.id, message.id)
        await ctx.send("Captcha panel removed.")

    @captcha.command(name="list")
    @commands.admin_or_permissions(manage_guild=True)
    async def captcha_list(self, ctx: commands.Context) -> None:
        """List configured captcha panels."""
        assert ctx.guild is not None
        panels = await self.config.guild(ctx.guild).panels()
        if not panels:
            await ctx.send("No captcha panels are configured.")
            return
        lines = []
        for message_id, record in panels.items():
            channel = ctx.guild.get_channel(int(record.get("channel_id") or 0))
            role = ctx.guild.get_role(int(record.get("role_id") or 0))
            lines.append(
                f"Message {message_id} | "
                f"{channel.mention if channel else 'missing channel'} | "
                f"{role.mention if role else 'missing role'} | "
                f"button `{record.get('button_label') or 'Verify'}`"
            )
        for page in pagify("\n".join(lines), page_length=1800):
            await ctx.send(box(page))

    @commands.Cog.listener()
    async def on_raw_message_delete(self, payload: Any) -> None:
        guild_id = getattr(payload, "guild_id", None)
        message_id = getattr(payload, "message_id", None)
        if guild_id is not None and message_id is not None:
            await self._remove_panel_record(int(guild_id), int(message_id))

    @commands.Cog.listener()
    async def on_raw_bulk_message_delete(self, payload: Any) -> None:
        guild_id = getattr(payload, "guild_id", None)
        message_ids = getattr(payload, "message_ids", ())
        if guild_id is None:
            return
        for message_id in message_ids:
            await self._remove_panel_record(int(guild_id), int(message_id))
