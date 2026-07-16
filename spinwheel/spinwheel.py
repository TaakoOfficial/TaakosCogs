"""Animated wheel spinner for Red-DiscordBot."""

from __future__ import annotations

import asyncio
import io
import re
import secrets
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

import discord
from redbot.core import Config, app_commands, commands
from redbot.core.utils.chat_formatting import humanize_list, pagify

from .dashboard_integration import DashboardIntegration
from .render import render_png, render_spin_gif, winner_rotation

if TYPE_CHECKING:
    from redbot.core.bot import Red

THEMES: dict[str, tuple[str, ...]] = {
    "rainbow": ("#ef4444", "#f97316", "#eab308", "#22c55e", "#06b6d4", "#3b82f6", "#8b5cf6", "#ec4899"),
    "ocean": ("#0f766e", "#0891b2", "#0284c7", "#2563eb", "#4f46e5", "#06b6d4"),
    "sunset": ("#7c2d12", "#dc2626", "#f97316", "#f59e0b", "#facc15", "#db2777"),
    "forest": ("#14532d", "#166534", "#15803d", "#16a34a", "#65a30d", "#84cc16"),
    "candy": ("#fb7185", "#f472b6", "#c084fc", "#818cf8", "#67e8f9", "#f9a8d4"),
    "pastel": ("#fda4af", "#fdba74", "#fde68a", "#86efac", "#a5f3fc", "#c4b5fd"),
    "neon": ("#ff006e", "#fb5607", "#ffbe0b", "#00f5d4", "#00bbf9", "#8338ec"),
    "midnight": ("#172554", "#312e81", "#581c87", "#831843", "#164e63", "#1e3a8a"),
}
HEX_RE = re.compile(r"^#?([0-9a-fA-F]{6})$")


@dataclass(frozen=True)
class SpinResult:
    """A securely selected and rendered wheel result."""

    winner: str
    winner_index: int
    gif: bytes
    final_png: bytes
    colors: tuple[str, ...]


class WheelSlashGroup(app_commands.Group):
    """Slash commands for wheel spins."""

    def __init__(self, cog: SpinWheel) -> None:
        super().__init__(name="wheel", description="Create and spin colorful wheels.")
        self.cog = cog

    @app_commands.command(name="spin", description="Spin an instant wheel from comma-separated entries.")
    @app_commands.describe(
        entries="Entries separated by commas, vertical bars, or new lines",
        theme="Color theme: rainbow, ocean, sunset, forest, candy, pastel, neon, or midnight",
    )
    @app_commands.guild_only()
    @app_commands.choices(
        theme=[app_commands.Choice(name=name.title(), value=name) for name in THEMES],
    )
    async def spin(
        self,
        interaction: discord.Interaction,
        entries: str,
        theme: str = "rainbow",
    ) -> None:
        if interaction.guild is None:
            return
        if not await self.cog._member_spins_allowed(interaction):
            await interaction.response.send_message(
                "Only members with Manage Server can spin wheels here.",
                ephemeral=True,
            )
            return
        await interaction.response.defer(thinking=True)
        try:
            parsed = await self.cog._validated_entries(interaction.guild, entries)
            result = await self.cog._spin(parsed, theme=theme)
        except commands.CommandError as error:
            await interaction.followup.send(str(error), ephemeral=True)
            return
        await self.cog._send_interaction_result(interaction, result, title="Instant wheel")

    @app_commands.command(name="saved", description="Spin one of this server's saved wheels.")
    @app_commands.describe(name="Saved wheel name")
    @app_commands.guild_only()
    async def saved(self, interaction: discord.Interaction, name: str) -> None:
        if interaction.guild is None:
            return
        if not await self.cog._member_spins_allowed(interaction):
            await interaction.response.send_message(
                "Only members with Manage Server can spin wheels here.",
                ephemeral=True,
            )
            return
        await interaction.response.defer(thinking=True)
        lock = self.cog._guild_spin_locks.setdefault(interaction.guild.id, asyncio.Lock())
        async with lock:
            try:
                clean_name, wheel = await self.cog._saved_wheel(interaction.guild, name)
                result = await self.cog._spin_record(wheel)
            except commands.CommandError as error:
                await interaction.followup.send(str(error), ephemeral=True)
                return
            await self.cog._send_interaction_result(interaction, result, title=clean_name)
            await self.cog._record_saved_spin(interaction.guild, clean_name, result)

    @saved.autocomplete("name")
    async def saved_autocomplete(
        self,
        interaction: discord.Interaction,
        current: str,
    ) -> list[app_commands.Choice[str]]:
        """Suggest saved wheels from the current server."""
        if interaction.guild is None:
            return []
        wheels = await self.cog.config.guild(interaction.guild).wheels()
        needle = current.casefold().strip()
        return [
            app_commands.Choice(name=self.cog._display_name(name)[:100], value=name[:100])
            for name in sorted(wheels)
            if needle in name.casefold()
        ][:25]


class SpinWheel(DashboardIntegration, commands.Cog):
    """Create colorful wheels and animate cryptographically secure random spins."""

    CONFIG_IDENTIFIER = 2026071501
    ABSOLUTE_MAX_ENTRIES = 60
    MAX_LABEL_LENGTH = 80
    MAX_GIF_BYTES = 7_500_000
    CHANNEL_SPIN_SECONDS = 4.4

    def __init__(self, bot: Red) -> None:
        self.bot = bot
        self.config = Config.get_conf(self, identifier=self.CONFIG_IDENTIFIER, force_registration=True)
        self.config.register_guild(
            wheels={},
            default_wheel=None,
            default_theme="rainbow",
            allow_member_spins=True,
            max_entries=40,
        )
        self.wheel_slash = WheelSlashGroup(self)
        self._render_slots = asyncio.Semaphore(2)
        self._guild_spin_locks: dict[int, asyncio.Lock] = {}
        self._settle_tasks: set[asyncio.Task] = set()

    def cog_unload(self) -> None:
        """Stop pending result edits and unregister the custom slash group."""
        for task in self._settle_tasks:
            task.cancel()
        self._settle_tasks.clear()
        self.bot.tree.remove_command(
            self.wheel_slash.name,
            type=discord.AppCommandType.chat_input,
        )

    async def red_delete_data_for_user(self, *, requester: str, user_id: int) -> None:
        """SpinWheel does not store Discord user IDs."""

    @staticmethod
    def _clean_name(name: str) -> str:
        clean = " ".join(name.casefold().split())
        if not clean or len(clean) > 50:
            raise commands.BadArgument("Wheel names must be between 1 and 50 characters.")
        return clean

    @staticmethod
    def _display_name(name: str) -> str:
        return " ".join(part.capitalize() for part in name.split())

    @classmethod
    def parse_entries(cls, argument: str) -> list[str]:
        """Parse comma, vertical-bar, or newline separated entries."""
        entries = [" ".join(item.split()) for item in re.split(r"[,|\n\r]+", argument) if item.strip()]
        if len(entries) < 2:
            raise commands.BadArgument("A wheel needs at least two entries.")
        too_long = next((item for item in entries if len(item) > cls.MAX_LABEL_LENGTH), None)
        if too_long:
            raise commands.BadArgument(
                f"Wheel entries can be at most {cls.MAX_LABEL_LENGTH} characters: `{too_long[:30]}…`",
            )
        return entries

    async def _validated_entries(self, guild: discord.Guild, argument: str) -> list[str]:
        entries = self.parse_entries(argument)
        maximum = min(
            self.ABSOLUTE_MAX_ENTRIES,
            max(2, int(await self.config.guild(guild).max_entries())),
        )
        if len(entries) > maximum:
            raise commands.BadArgument(f"This server allows at most {maximum} entries per wheel; you provided {len(entries)}.")
        return entries

    @staticmethod
    def parse_colors(argument: str) -> list[str]:
        colors: list[str] = []
        for raw in re.split(r"[,|\s]+", argument.strip()):
            if not raw:
                continue
            match = HEX_RE.fullmatch(raw)
            if match is None:
                raise commands.BadArgument(f"`{raw}` is not a six-digit hex color.")
            color = f"#{match.group(1).lower()}"
            if color not in colors:
                colors.append(color)
        if len(colors) < 2:
            raise commands.BadArgument("A custom palette needs at least two different hex colors.")
        return colors[:20]

    @staticmethod
    def _theme_colors(theme: str, custom_colors: list[str] | None = None) -> tuple[str, ...]:
        theme = theme.casefold().strip()
        if theme == "custom":
            if not custom_colors or len(custom_colors) < 2:
                raise commands.BadArgument("The custom theme needs at least two colors.")
            return tuple(custom_colors)
        colors = THEMES.get(theme)
        if colors is None:
            raise commands.BadArgument(
                "Unknown theme. Choose " + humanize_list([f"`{name}`" for name in (*THEMES, "custom")]) + ".",
            )
        return colors

    async def _member_spins_allowed(self, source: discord.Interaction | commands.Context) -> bool:
        guild = source.guild
        if guild is None:
            return False
        if await self.config.guild(guild).allow_member_spins():
            return True
        member = source.user if isinstance(source, discord.Interaction) else source.author
        return isinstance(member, discord.Member) and member.guild_permissions.manage_guild

    async def _spin(
        self,
        entries: list[str],
        *,
        theme: str,
        custom_colors: list[str] | None = None,
    ) -> SpinResult:
        winner_index = secrets.randbelow(len(entries))
        turns = 5 + secrets.randbelow(4)
        colors = self._theme_colors(theme, custom_colors)
        async with self._render_slots:
            gif = await asyncio.to_thread(
                render_spin_gif,
                entries,
                colors,
                winner_index,
                turns=turns,
                frame_count=36,
                size=520,
            )
            if len(gif) > self.MAX_GIF_BYTES:
                # Preserve visible in-channel motion under Discord's base upload limit.
                gif = await asyncio.to_thread(
                    render_spin_gif,
                    entries,
                    colors,
                    winner_index,
                    turns=turns,
                    frame_count=28,
                    size=420,
                )
            rotation = winner_rotation(winner_index, len(entries), turns)
            final_png = await asyncio.to_thread(
                render_png,
                entries,
                colors,
                rotation=rotation,
                winner_index=winner_index,
            )
            if len(gif) > self.MAX_GIF_BYTES:
                gif = final_png
        return SpinResult(
            winner=entries[winner_index],
            winner_index=winner_index,
            gif=gif,
            final_png=final_png,
            colors=colors,
        )

    async def _spin_record(self, wheel: dict[str, Any]) -> SpinResult:
        entries = [str(item) for item in wheel.get("entries", [])]
        if len(entries) < 2:
            raise commands.BadArgument("That saved wheel has fewer than two entries remaining.")
        return await self._spin(
            entries,
            theme=str(wheel.get("theme", "rainbow")),
            custom_colors=[str(color) for color in wheel.get("colors", [])],
        )

    async def _saved_wheel(
        self,
        guild: discord.Guild,
        name: str,
    ) -> tuple[str, dict[str, Any]]:
        wheels = await self.config.guild(guild).wheels()
        clean_name = self._clean_name(name)
        wheel = wheels.get(clean_name)
        if wheel is None:
            raise commands.BadArgument(f"Saved wheel `{clean_name}` was not found.")
        return clean_name, wheel

    async def _record_saved_spin(
        self,
        guild: discord.Guild,
        name: str,
        result: SpinResult,
    ) -> None:
        async with self.config.guild(guild).wheels() as wheels:
            wheel = wheels.get(name)
            if wheel is None:
                return
            wheel["spin_count"] = int(wheel.get("spin_count", 0)) + 1
            wheel["last_winner"] = result.winner
            if wheel.get("remove_winner"):
                entries = list(wheel.get("entries", []))
                if len(entries) > 2:
                    with_index = min(result.winner_index, len(entries) - 1)
                    entries.pop(with_index)
                    wheel["entries"] = entries

    @staticmethod
    def _file_and_name(payload: bytes) -> tuple[discord.File, str]:
        animated = payload[:6] in {b"GIF87a", b"GIF89a"}
        filename = "wheel-spin.gif" if animated else "wheel-result.png"
        return discord.File(io.BytesIO(payload), filename=filename), filename

    @staticmethod
    def _result_embed(result: SpinResult, title: str, filename: str) -> discord.Embed:
        color = discord.Color(int(result.colors[0].lstrip("#"), 16))
        embed = discord.Embed(
            title=f"🎡 {SpinWheel._display_name(title)}",
            description=f"The wheel selected:\n# **{discord.utils.escape_markdown(result.winner)}**",
            color=color,
        )
        embed.set_image(url=f"attachment://{filename}")
        embed.set_footer(text="Secure random selection • Every spin is independent")
        return embed

    @staticmethod
    def _spinning_embed(result: SpinResult, title: str, filename: str) -> discord.Embed:
        color = discord.Color(int(result.colors[0].lstrip("#"), 16))
        embed = discord.Embed(
            title=f"🎡 {SpinWheel._display_name(title)}",
            description="## The wheel is spinning…",
            color=color,
        )
        embed.set_image(url=f"attachment://{filename}")
        embed.set_footer(text="The selected result appears when the wheel stops")
        return embed

    def _schedule_settle(
        self,
        message: discord.Message,
        result: SpinResult,
        title: str,
    ) -> None:
        task = asyncio.create_task(
            self._settle_channel_message(message, result, title),
            name=f"spinwheel-settle-{message.id}",
        )
        self._settle_tasks.add(task)
        task.add_done_callback(self._settle_tasks.discard)

    async def _settle_channel_message(
        self,
        message: discord.Message,
        result: SpinResult,
        title: str,
    ) -> None:
        """Replace the animation with its exact final resting frame."""
        try:
            await asyncio.sleep(self.CHANNEL_SPIN_SECONDS)
            filename = "wheel-result.png"
            final_file = discord.File(io.BytesIO(result.final_png), filename=filename)
            await message.edit(
                embed=self._result_embed(result, title, filename),
                attachments=[final_file],
            )
        except (asyncio.CancelledError, discord.HTTPException):
            return

    async def _send_ctx_result(
        self,
        ctx: commands.Context,
        result: SpinResult,
        *,
        title: str,
    ) -> None:
        file, filename = self._file_and_name(result.gif)
        animated = filename.endswith(".gif")
        message = await ctx.send(
            embed=(self._spinning_embed(result, title, filename) if animated else self._result_embed(result, title, filename)),
            file=file,
            allowed_mentions=discord.AllowedMentions.none(),
        )
        if animated:
            self._schedule_settle(message, result, title)

    async def _send_interaction_result(
        self,
        interaction: discord.Interaction,
        result: SpinResult,
        *,
        title: str,
    ) -> None:
        file, filename = self._file_and_name(result.gif)
        animated = filename.endswith(".gif")
        message = await interaction.followup.send(
            embed=(self._spinning_embed(result, title, filename) if animated else self._result_embed(result, title, filename)),
            file=file,
            allowed_mentions=discord.AllowedMentions.none(),
            wait=True,
        )
        if animated:
            self._schedule_settle(message, result, title)

    async def _create_or_update_wheel(
        self,
        guild: discord.Guild,
        name: str,
        entries: list[str],
        *,
        theme: str = "rainbow",
        colors: list[str] | None = None,
        remove_winner: bool = False,
    ) -> str:
        clean_name = self._clean_name(name)
        palette = self._theme_colors(theme, colors)
        async with self.config.guild(guild).wheels() as wheels:
            old = wheels.get(clean_name, {})
            wheels[clean_name] = {
                "entries": entries,
                "theme": theme.casefold(),
                "colors": list(palette) if theme.casefold() == "custom" else [],
                "remove_winner": bool(remove_winner),
                "spin_count": int(old.get("spin_count", 0)),
                "last_winner": old.get("last_winner"),
            }
        if await self.config.guild(guild).default_wheel() is None:
            await self.config.guild(guild).default_wheel.set(clean_name)
        return clean_name

    @commands.guild_only()
    @commands.group(name="wheel", aliases=["spinwheel"], invoke_without_command=True)
    async def wheel_group(self, ctx: commands.Context, *, entries: str = "") -> None:
        """Create and spin colorful wheels."""
        if not entries:
            await ctx.send_help(ctx.command)
            return
        await self._spin_instant_for_context(ctx, entries)

    @wheel_group.command(name="spin")
    @commands.cooldown(2, 15, commands.BucketType.member)
    async def wheel_spin(self, ctx: commands.Context, *, entries: str = "") -> None:
        """Spin entries separated by commas, vertical bars, or new lines."""
        if not await self._member_spins_allowed(ctx):
            raise commands.UserFeedbackCheckFailure(
                "Only members with Manage Server can spin wheels here.",
            )
        if not entries:
            default_name = await self.config.guild(ctx.guild).default_wheel()
            if not default_name:
                raise commands.BadArgument("Provide entries or configure a default saved wheel.")
            await self._spin_saved_for_context(ctx, default_name)
            return
        await self._spin_instant_for_context(ctx, entries)

    async def _spin_instant_for_context(self, ctx: commands.Context, entries: str) -> None:
        """Validate and render an ad-hoc wheel for a prefix context."""
        if not await self._member_spins_allowed(ctx):
            raise commands.UserFeedbackCheckFailure(
                "Only members with Manage Server can spin wheels here.",
            )
        parsed = await self._validated_entries(ctx.guild, entries)
        theme = await self.config.guild(ctx.guild).default_theme()
        async with ctx.typing():
            result = await self._spin(parsed, theme=theme)
        await self._send_ctx_result(ctx, result, title="Instant wheel")

    @wheel_group.command(name="colorful", aliases=["themed"])
    @commands.cooldown(2, 15, commands.BucketType.member)
    async def wheel_colorful(
        self,
        ctx: commands.Context,
        theme: str,
        *,
        entries: str,
    ) -> None:
        """Spin an instant wheel using one of the named color themes."""
        if not await self._member_spins_allowed(ctx):
            raise commands.UserFeedbackCheckFailure(
                "Only members with Manage Server can spin wheels here.",
            )
        parsed = await self._validated_entries(ctx.guild, entries)
        async with ctx.typing():
            result = await self._spin(parsed, theme=theme)
        await self._send_ctx_result(ctx, result, title=f"{theme} wheel")

    @wheel_group.command(name="saved")
    @commands.cooldown(2, 15, commands.BucketType.member)
    async def wheel_saved(self, ctx: commands.Context, *, name: str) -> None:
        """Spin a saved wheel."""
        if not await self._member_spins_allowed(ctx):
            raise commands.UserFeedbackCheckFailure(
                "Only members with Manage Server can spin wheels here.",
            )
        await self._spin_saved_for_context(ctx, name)

    async def _spin_saved_for_context(self, ctx: commands.Context, name: str) -> None:
        lock = self._guild_spin_locks.setdefault(ctx.guild.id, asyncio.Lock())
        async with lock, ctx.typing():
            clean_name, wheel = await self._saved_wheel(ctx.guild, name)
            result = await self._spin_record(wheel)
            await self._send_ctx_result(ctx, result, title=clean_name)
            await self._record_saved_spin(ctx.guild, clean_name, result)

    @wheel_group.command(name="create", aliases=["save"])
    @commands.admin_or_permissions(manage_guild=True)
    async def wheel_create(
        self,
        ctx: commands.Context,
        name: str,
        *,
        entries: str,
    ) -> None:
        """Create or replace a saved wheel using the server default theme."""
        parsed = await self._validated_entries(ctx.guild, entries)
        theme = await self.config.guild(ctx.guild).default_theme()
        clean_name = await self._create_or_update_wheel(
            ctx.guild,
            name,
            parsed,
            theme=theme,
        )
        await ctx.send(f"Saved wheel `{clean_name}` with {len(parsed)} entries.")

    @wheel_group.command(name="theme")
    @commands.admin_or_permissions(manage_guild=True)
    async def wheel_theme(
        self,
        ctx: commands.Context,
        name: str,
        theme: str,
        *,
        custom_colors: str = "",
    ) -> None:
        """Set a saved wheel theme, with hex colors when the theme is `custom`."""
        clean_name, _wheel = await self._saved_wheel(ctx.guild, name)
        colors = self.parse_colors(custom_colors) if theme.casefold() == "custom" else None
        self._theme_colors(theme, colors)
        async with self.config.guild(ctx.guild).wheels() as wheels:
            wheels[clean_name]["theme"] = theme.casefold()
            wheels[clean_name]["colors"] = colors or []
        await ctx.send(f"Set `{clean_name}` to the `{theme.casefold()}` theme.")

    @wheel_group.command(name="removeonwin")
    @commands.admin_or_permissions(manage_guild=True)
    async def wheel_remove_on_win(
        self,
        ctx: commands.Context,
        enabled: bool,
        *,
        name: str,
    ) -> None:
        """Choose whether a saved winner is removed after each spin."""
        clean_name, _wheel = await self._saved_wheel(ctx.guild, name)
        async with self.config.guild(ctx.guild).wheels() as wheels:
            wheels[clean_name]["remove_winner"] = enabled
        await ctx.send(f"Winner removal for `{clean_name}` is now `{enabled}`.")

    @wheel_group.command(name="default")
    @commands.admin_or_permissions(manage_guild=True)
    async def wheel_default(self, ctx: commands.Context, *, name: str) -> None:
        """Set the wheel used by `[p]wheel spin` with no entries."""
        clean_name, _wheel = await self._saved_wheel(ctx.guild, name)
        await self.config.guild(ctx.guild).default_wheel.set(clean_name)
        await ctx.send(f"`{clean_name}` is now the default wheel.")

    @wheel_group.command(name="delete")
    @commands.admin_or_permissions(manage_guild=True)
    async def wheel_delete(
        self,
        ctx: commands.Context,
        confirmation: str,
        *,
        name: str,
    ) -> None:
        """Delete a saved wheel; confirmation must be `CONFIRM`."""
        if confirmation.upper() != "CONFIRM":
            raise commands.BadArgument("Run the command again with `CONFIRM` before the wheel name.")
        clean_name = self._clean_name(name)
        async with self.config.guild(ctx.guild).wheels() as wheels:
            if wheels.pop(clean_name, None) is None:
                raise commands.BadArgument("That saved wheel was not found.")
        if await self.config.guild(ctx.guild).default_wheel() == clean_name:
            await self.config.guild(ctx.guild).default_wheel.set(None)
        await ctx.send(f"Deleted wheel `{clean_name}`.")

    @wheel_group.command(name="list")
    async def wheel_list(self, ctx: commands.Context) -> None:
        """List saved wheels and their current entry counts."""
        wheels = await self.config.guild(ctx.guild).wheels()
        default_name = await self.config.guild(ctx.guild).default_wheel()
        if not wheels:
            await ctx.send("No wheels have been saved in this server.")
            return
        lines = []
        for name, wheel in sorted(wheels.items()):
            marker = " ⭐" if name == default_name else ""
            lines.append(
                f"**{self._display_name(name)}**{marker} — {len(wheel.get('entries', []))} entries • "
                f"{wheel.get('theme', 'rainbow')} • {int(wheel.get('spin_count', 0))} spins",
            )
        for page in pagify("\n".join(lines), page_length=1900):
            await ctx.send(page)

    @wheel_group.command(name="show")
    async def wheel_show(self, ctx: commands.Context, *, name: str) -> None:
        """Show a static preview and entries for a saved wheel."""
        clean_name, wheel = await self._saved_wheel(ctx.guild, name)
        entries = [str(item) for item in wheel.get("entries", [])]
        colors = self._theme_colors(
            str(wheel.get("theme", "rainbow")),
            [str(color) for color in wheel.get("colors", [])],
        )
        png = await asyncio.to_thread(render_png, entries, colors)
        file = discord.File(io.BytesIO(png), filename="wheel-preview.png")
        embed = discord.Embed(
            title=f"🎡 {self._display_name(clean_name)}",
            description="\n".join(f"{index}. {discord.utils.escape_markdown(entry)}" for index, entry in enumerate(entries, 1))[
                :4000
            ],
            color=discord.Color(int(colors[0].lstrip("#"), 16)),
        )
        embed.set_image(url="attachment://wheel-preview.png")
        await ctx.send(embed=embed, file=file)

    @wheel_group.command(name="settings")
    @commands.admin_or_permissions(manage_guild=True)
    async def wheel_settings(
        self,
        ctx: commands.Context,
        allow_member_spins: bool | None = None,
        max_entries: int | None = None,
        default_theme: str | None = None,
    ) -> None:
        """View or update member access, entry limit, and instant-wheel theme."""
        conf = self.config.guild(ctx.guild)
        if allow_member_spins is not None:
            await conf.allow_member_spins.set(allow_member_spins)
        if max_entries is not None:
            await conf.max_entries.set(max(2, min(max_entries, self.ABSOLUTE_MAX_ENTRIES)))
        if default_theme is not None:
            self._theme_colors(default_theme)
            await conf.default_theme.set(default_theme.casefold())
        await ctx.send(
            "\n".join(
                [
                    f"Member spins: `{await conf.allow_member_spins()}`",
                    f"Maximum entries: `{await conf.max_entries()}`",
                    f"Instant-wheel theme: `{await conf.default_theme()}`",
                    f"Default saved wheel: `{await conf.default_wheel() or 'none'}`",
                ],
            ),
        )
