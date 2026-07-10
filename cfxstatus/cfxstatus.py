"""Cfx.re service status checker for Red-DiscordBot."""

from __future__ import annotations

import asyncio
import logging
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from html.parser import HTMLParser
from typing import TYPE_CHECKING

import aiohttp
import discord
from discord.ext import tasks
from redbot.core import Config, commands

if TYPE_CHECKING:
    from redbot.core.bot import Red

log = logging.getLogger("red.taakoscogs.cfxstatus")


@dataclass(frozen=True)
class CfxStatusPayload:
    """Parsed Cfx.re service-status data."""

    updated_at: str | None
    components: dict[str, str]
    source_name: str
    source_url: str
    source_note: str | None = None


class StatusPageError(RuntimeError):
    """Raised when the Rockstar status page cannot be fetched or parsed."""


class VisibleTextParser(HTMLParser):
    """Extract visible text nodes from the Rockstar status page HTML."""

    SKIP_TAGS = {"script", "style", "noscript", "svg"}

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self._skip_depth = 0

    def handle_starttag(self, tag: str, attrs) -> None:
        if tag.lower() in self.SKIP_TAGS:
            self._skip_depth += 1

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() in self.SKIP_TAGS and self._skip_depth:
            self._skip_depth -= 1

    def handle_data(self, data: str) -> None:
        if not self._skip_depth:
            self.parts.append(data)


class CfxStatus(commands.Cog):
    """Check the official Cfx.re service status."""

    CONFIG_IDENTIFIER = 2026070801
    ROCKSTAR_STATUS_PAGE_URL = "https://support.rockstargames.com/servicestatus"
    CFX_STATUS_PAGE_URL = "https://status.cfx.re/"
    CFX_SUMMARY_API_URL = "https://ntfwm21l4wbw.statuspage.io/api/v2/summary.json"
    DEFAULT_POLL_INTERVAL_MINUTES = 5
    MIN_POLL_INTERVAL_MINUTES = 1
    MAX_POLL_INTERVAL_MINUTES = 60
    REQUEST_TIMEOUT = aiohttp.ClientTimeout(total=10)
    REQUEST_HEADERS = {
        "Accept": "application/json,text/html,application/xhtml+xml",
        "User-Agent": (
            "Mozilla/5.0 (compatible; Red-DiscordBot CfxStatus; "
            "+https://github.com/TaakoOfficial/TaakosCogs)"
        ),
    }
    CFX_COMPONENTS = (
        "Authentication",
        "FiveM",
        "RedM",
        "Community Servers",
        "Marketplace",
    )
    STATUSPAGE_COMPONENT_MAP = {
        "Authentication": ("CnL", "IDMS"),
        "FiveM": ("FiveM",),
        "RedM": ("RedM",),
        "Community Servers": ("Cfx.re Platform Server (FXServer)",),
        "Marketplace": ("Portal",),
    }
    OPERATIONAL_COLOR = 0x57F287
    DEGRADED_COLOR = 0xFEE75C
    PARTIAL_COLOR = 0xF97316
    OUTAGE_COLOR = 0xED4245
    UNKNOWN_COLOR = 0x747F8D

    def __init__(self, bot: Red) -> None:
        self.bot = bot
        self.config = Config.get_conf(
            self,
            identifier=self.CONFIG_IDENTIFIER,
            force_registration=True,
        )
        self.config.register_guild(
            enabled=False,
            status_channel_id=None,
            status_message_id=None,
            poll_interval_minutes=self.DEFAULT_POLL_INTERVAL_MINUTES,
            last_poll_at=0,
        )
        self._session: aiohttp.ClientSession | None = None
        self.status_loop.start()

    async def cog_unload(self) -> None:
        """Close HTTP resources when the cog unloads."""
        self.status_loop.cancel()
        if self._session and not self._session.closed:
            await self._session.close()

    async def red_delete_data_for_user(self, *, requester: str, user_id: int) -> None:
        """This cog does not store end user data."""
        return

    @tasks.loop(minutes=1)
    async def status_loop(self) -> None:
        """Refresh configured Cfx.re status panels."""
        all_guilds = await self.config.all_guilds()
        now_ts = self._utc_timestamp()
        due_guilds = []

        for guild_id, settings in all_guilds.items():
            if not settings.get("enabled"):
                continue
            if not settings.get("status_channel_id"):
                continue

            interval = self._poll_interval(settings)
            last_poll_at = int(settings.get("last_poll_at") or 0)
            if last_poll_at and now_ts - last_poll_at < interval * 60:
                continue

            guild = self.bot.get_guild(guild_id)
            if guild is not None:
                due_guilds.append((guild, settings))

        if not due_guilds:
            return

        payload: CfxStatusPayload | None = None
        error: str | None = None
        try:
            payload = await self.fetch_status()
        except StatusPageError as status_error:
            error = str(status_error)
        except Exception:
            log.exception("Unexpected error while polling Cfx.re service status")
            error = "I could not check the Cfx.re service status right now."

        for guild, settings in due_guilds:
            try:
                await self._update_status_message(guild, settings, payload, error)
            except Exception:
                log.exception("Failed to update Cfx.re status for guild %s", guild.id)

    @status_loop.before_loop
    async def before_status_loop(self) -> None:
        """Wait until the bot is ready before polling Cfx.re status."""
        await self.bot.wait_until_ready()

    @commands.hybrid_group(
        name="cfxstatus",
        aliases=["cfx", "cfxre"],
        invoke_without_command=True,
    )
    async def cfxstatus(self, ctx: commands.Context) -> None:
        """Show Cfx.re status commands."""
        await ctx.send_help(ctx.command)

    @cfxstatus.command(name="check", aliases=["status", "now"])
    async def cfxstatus_check(self, ctx: commands.Context) -> None:
        """Check the current official Cfx.re status once."""
        await self._send_current_status(ctx)

    @cfxstatus.command(name="setup")
    @commands.guild_only()
    @commands.admin_or_permissions(manage_guild=True)
    async def cfxstatus_setup(
        self,
        ctx: commands.Context,
        channel: discord.TextChannel | None = None,
    ) -> None:
        """Choose a channel and post an auto-updating Cfx.re status panel."""
        assert ctx.guild is not None
        channel = await self._resolve_target_channel(ctx, channel)
        if channel is None:
            return
        try:
            self._ensure_channel_permissions(ctx.guild, channel)
        except commands.CommandError as error:
            await ctx.send(str(error))
            return

        await self.config.guild(ctx.guild).status_channel_id.set(channel.id)
        await self.config.guild(ctx.guild).enabled.set(True)

        try:
            message = await self._update_status_message(
                ctx.guild,
                force_post=True,
                allow_error_embed=True,
            )
        except commands.CommandError as error:
            await ctx.send(str(error))
            return

        await ctx.send(
            "Cfx.re status panel is posting in "
            f"{channel.mention}: "
            f"{self._message_url(ctx.guild.id, channel.id, message.id)}",
        )

    @cfxstatus.command(name="channel")
    @commands.guild_only()
    @commands.admin_or_permissions(manage_guild=True)
    async def cfxstatus_channel(
        self,
        ctx: commands.Context,
        channel: discord.TextChannel | None = None,
    ) -> None:
        """Set the channel used for the auto-updating status panel."""
        assert ctx.guild is not None
        channel = await self._resolve_target_channel(ctx, channel)
        if channel is None:
            return
        try:
            self._ensure_channel_permissions(ctx.guild, channel)
        except commands.CommandError as error:
            await ctx.send(str(error))
            return

        await self.config.guild(ctx.guild).status_channel_id.set(channel.id)
        await self.config.guild(ctx.guild).status_message_id.set(None)
        await ctx.send(f"Cfx.re status channel set to {channel.mention}.")

    @cfxstatus.command(name="post")
    @commands.guild_only()
    @commands.admin_or_permissions(manage_guild=True)
    async def cfxstatus_post(self, ctx: commands.Context) -> None:
        """Post a fresh auto-updating status panel in the configured channel."""
        assert ctx.guild is not None
        try:
            message = await self._update_status_message(
                ctx.guild,
                force_post=True,
                allow_error_embed=True,
            )
        except commands.CommandError as error:
            await ctx.send(str(error))
            return

        await self.config.guild(ctx.guild).enabled.set(True)
        channel_id = await self.config.guild(ctx.guild).status_channel_id()
        await ctx.send(
            "Cfx.re status panel posted: "
            f"{self._message_url(ctx.guild.id, channel_id, message.id)}",
        )

    @cfxstatus.command(name="refresh")
    @commands.guild_only()
    @commands.admin_or_permissions(manage_guild=True)
    async def cfxstatus_refresh(self, ctx: commands.Context) -> None:
        """Refresh the configured status panel immediately."""
        assert ctx.guild is not None
        try:
            message = await self._update_status_message(
                ctx.guild,
                allow_error_embed=True,
            )
        except commands.CommandError as error:
            await ctx.send(str(error))
            return

        channel_id = await self.config.guild(ctx.guild).status_channel_id()
        await ctx.send(
            "Cfx.re status panel refreshed: "
            f"{self._message_url(ctx.guild.id, channel_id, message.id)}",
        )

    @cfxstatus.command(name="enable")
    @commands.guild_only()
    @commands.admin_or_permissions(manage_guild=True)
    async def cfxstatus_enable(self, ctx: commands.Context, enabled: bool) -> None:
        """Enable or disable automatic Cfx.re status updates."""
        assert ctx.guild is not None
        if enabled and not await self.config.guild(ctx.guild).status_channel_id():
            await ctx.send(
                "Set a status channel first with `[p]cfxstatus setup [channel]`.",
            )
            return

        await self.config.guild(ctx.guild).enabled.set(enabled)
        state = "enabled" if enabled else "disabled"
        await ctx.send(f"Automatic Cfx.re status updates are now {state}.")

    @cfxstatus.command(name="interval")
    @commands.guild_only()
    @commands.admin_or_permissions(manage_guild=True)
    async def cfxstatus_interval(self, ctx: commands.Context, minutes: int) -> None:
        """Set how often the status panel refreshes, in minutes."""
        assert ctx.guild is not None
        if not (
            self.MIN_POLL_INTERVAL_MINUTES <= minutes <= self.MAX_POLL_INTERVAL_MINUTES
        ):
            await ctx.send(
                "The polling interval must be between "
                f"{self.MIN_POLL_INTERVAL_MINUTES} and "
                f"{self.MAX_POLL_INTERVAL_MINUTES} minutes.",
            )
            return

        await self.config.guild(ctx.guild).poll_interval_minutes.set(minutes)
        await ctx.send(f"Cfx.re status panel will refresh every {minutes} minutes.")

    @cfxstatus.command(name="settings", aliases=["config"])
    @commands.guild_only()
    async def cfxstatus_settings(self, ctx: commands.Context) -> None:
        """Show Cfx.re status panel settings for this server."""
        assert ctx.guild is not None
        settings = await self.config.guild(ctx.guild).all()
        await ctx.send(embed=self.build_settings_embed(ctx.guild, settings))

    async def _send_current_status(self, ctx: commands.Context) -> None:
        """Fetch and send the current status as a one-off message."""
        async with ctx.typing():
            try:
                payload = await self.fetch_status()
            except StatusPageError as error:
                await ctx.send(str(error))
                return
            except Exception:
                log.exception("Unexpected error while checking Cfx.re service status")
                await ctx.send("I could not check the Cfx.re service status right now.")
                return

        await ctx.send(embed=self.build_status_embed(payload))

    async def fetch_status(self) -> CfxStatusPayload:
        """Fetch Cfx.re status from the fastest official source available."""
        errors = []

        try:
            return await self._fetch_statuspage_status()
        except StatusPageError as error:
            errors.append(str(error))
            log.warning("Cfx.re Statuspage API failed: %s", error)

        try:
            return await self._fetch_rockstar_status()
        except StatusPageError as error:
            errors.append(str(error))
            log.warning("Rockstar service-status page failed: %s", error)

        detail = " ".join(errors) or "No status source returned data."
        raise StatusPageError(f"I could not check the Cfx.re service status. {detail}")

    async def _fetch_statuspage_status(self) -> CfxStatusPayload:
        """Fetch Cfx.re status from the official Statuspage JSON API."""
        session = await self._get_session()
        try:
            async with session.get(self.CFX_SUMMARY_API_URL) as response:
                if response.status != 200:
                    raise StatusPageError(
                        f"Cfx.re's Statuspage API returned HTTP {response.status}.",
                    )
                data = await response.json(content_type=None)
        except asyncio.TimeoutError as error:
            raise StatusPageError("Cfx.re's Statuspage API timed out.") from error
        except aiohttp.ClientError as error:
            raise StatusPageError(
                "I could not reach Cfx.re's Statuspage API.",
            ) from error
        except ValueError as error:
            raise StatusPageError(
                "Cfx.re's Statuspage API returned invalid JSON.",
            ) from error

        components = self._parse_statuspage_components(data)
        if not components:
            raise StatusPageError(
                "I reached Cfx.re's Statuspage API, but could not find "
                "the expected components.",
            )

        page = data.get("page") if isinstance(data, dict) else {}
        updated_at = page.get("updated_at") if isinstance(page, dict) else None
        return CfxStatusPayload(
            updated_at=updated_at,
            components=components,
            source_name="Cfx.re Statuspage",
            source_url=self.CFX_STATUS_PAGE_URL,
            source_note="Official Cfx.re JSON API",
        )

    async def _fetch_rockstar_status(self) -> CfxStatusPayload:
        """Fetch and parse the Cfx.re section of the Rockstar status page."""
        session = await self._get_session()
        try:
            async with session.get(self.ROCKSTAR_STATUS_PAGE_URL) as response:
                if response.status != 200:
                    raise StatusPageError(
                        "Rockstar's service-status page returned "
                        f"HTTP {response.status}.",
                    )
                html = await response.text()
        except asyncio.TimeoutError as error:
            raise StatusPageError(
                "Rockstar's service-status page timed out.",
            ) from error
        except aiohttp.ClientError as error:
            raise StatusPageError(
                "I could not reach Rockstar's service-status page.",
            ) from error

        if not html.strip():
            raise StatusPageError("Rockstar's service-status page returned no content.")

        payload = self.parse_status_page(html)
        if not payload.components:
            raise StatusPageError(
                "I reached Rockstar's service-status page, but could not find "
                "the Cfx.re status section.",
            )
        return payload

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(
                timeout=self.REQUEST_TIMEOUT,
                headers=self.REQUEST_HEADERS,
            )
        return self._session

    def parse_status_page(self, html: str) -> CfxStatusPayload:
        """Parse Cfx.re component statuses from Rockstar's rendered HTML."""
        lines = self._extract_visible_lines(html)
        updated_at = self._extract_updated_at(lines)
        components = self._extract_cfx_components(lines)
        return CfxStatusPayload(
            updated_at=updated_at,
            components=components,
            source_name="Rockstar Games Service Status",
            source_url=self.ROCKSTAR_STATUS_PAGE_URL,
            source_note=None,
        )

    def build_status_embed(
        self,
        payload: CfxStatusPayload,
        poll_interval_minutes: int | None = None,
    ) -> discord.Embed:
        """Build the Discord embed for a parsed status payload."""
        status_text = self._overall_status(payload.components)
        overall_emoji = self._overall_status_emoji(payload.components)
        embed = discord.Embed(
            title=f"{overall_emoji} Cfx.re Platform Status",
            description=(
                f"**{status_text}**\n"
                "Live platform health for FiveM, RedM, and Cfx.re services."
            ),
            color=self._status_color(payload.components),
        )
        embed.timestamp = datetime.now(timezone.utc)

        service_lines = [
            self._component_status_line(
                component,
                payload.components.get(component, "Unknown"),
            )
            for component in self.CFX_COMPONENTS
        ]
        embed.add_field(
            name="Service Board",
            value="\n".join(service_lines),
            inline=False,
        )

        details = []
        if poll_interval_minutes is not None:
            details.append(f"Refresh: every {poll_interval_minutes} minutes")
        details.append(f"Source: {payload.source_name}")
        embed.add_field(name="Panel Info", value="\n".join(details), inline=False)
        embed.set_footer(text="Cfx.re status panel | Last checked")
        return embed

    def build_error_embed(
        self,
        error: str,
        poll_interval_minutes: int | None = None,
    ) -> discord.Embed:
        """Build the Discord embed shown when a scheduled poll fails."""
        embed = discord.Embed(
            title="⚪ Cfx.re Platform Status",
            description=(
                "**Unable to check Cfx.re status**\n"
                "The panel will keep retrying on the next refresh."
            ),
            color=self.UNKNOWN_COLOR,
        )
        embed.timestamp = datetime.now(timezone.utc)
        embed.add_field(
            name="Service Board",
            value="⚪ **Status** - Unknown",
            inline=False,
        )
        embed.add_field(name="Last Error", value=error[:1024], inline=False)
        if poll_interval_minutes is not None:
            embed.add_field(
                name="Panel Info",
                value=f"Every {poll_interval_minutes} minutes",
                inline=False,
            )
        embed.set_footer(text="Cfx.re status panel | Last checked")
        return embed

    def build_settings_embed(
        self,
        guild: discord.Guild,
        settings: dict,
    ) -> discord.Embed:
        """Build an embed showing this guild's panel settings."""
        channel_id = settings.get("status_channel_id")
        message_id = settings.get("status_message_id")
        channel = guild.get_channel(channel_id) if channel_id else None
        interval = self._poll_interval(settings)
        last_poll_at = int(settings.get("last_poll_at") or 0)

        embed = discord.Embed(
            title="Cfx.re Status Panel Settings",
            color=self.UNKNOWN_COLOR,
        )
        embed.add_field(
            name="Automatic Updates",
            value="Enabled" if settings.get("enabled") else "Disabled",
            inline=True,
        )
        embed.add_field(name="Interval", value=f"{interval} minutes", inline=True)

        if isinstance(channel, discord.TextChannel):
            channel_value = channel.mention
        elif channel_id:
            channel_value = f"Missing channel ({channel_id})"
        else:
            channel_value = "Not set"
        embed.add_field(name="Channel", value=channel_value, inline=False)

        if channel_id and message_id:
            message_value = (
                f"[Open panel]({self._message_url(guild.id, channel_id, message_id)})"
            )
        else:
            message_value = "Not posted"
        embed.add_field(name="Panel Message", value=message_value, inline=False)

        last_poll_value = f"<t:{last_poll_at}:R>" if last_poll_at else "Never"
        embed.add_field(name="Last Poll", value=last_poll_value, inline=True)
        embed.set_footer(text="Use setup or channel to choose where the panel posts.")
        return embed

    async def _update_status_message(
        self,
        guild: discord.Guild,
        settings: dict | None = None,
        payload: CfxStatusPayload | None = None,
        error: str | None = None,
        *,
        force_post: bool = False,
        allow_error_embed: bool = False,
    ):
        """Post or edit the configured status panel for a guild."""
        if settings is None:
            settings = await self.config.guild(guild).all()

        channel = self._configured_channel(guild, settings)
        self._ensure_channel_permissions(guild, channel)
        interval = self._poll_interval(settings)

        if payload is None and error is None:
            try:
                payload = await self.fetch_status()
            except StatusPageError as status_error:
                if not allow_error_embed:
                    raise
                error = str(status_error)

        if error is not None:
            embed = self.build_error_embed(error, interval)
        elif payload is not None:
            embed = self.build_status_embed(payload, interval)
        else:
            embed = self.build_error_embed(
                "The status payload was empty.",
                interval,
            )

        message = None
        message_id = settings.get("status_message_id")
        if message_id and not force_post:
            partial = channel.get_partial_message(int(message_id))
            try:
                message = await partial.edit(embed=embed)
            except discord.NotFound:
                message = None
            except discord.Forbidden as discord_error:
                raise commands.CommandError(
                    "I do not have permission to edit the configured Cfx.re "
                    "status message.",
                ) from discord_error
            except discord.HTTPException as discord_error:
                raise commands.CommandError(
                    "Discord rejected the Cfx.re status message update.",
                ) from discord_error

        if message is None:
            try:
                message = await channel.send(embed=embed)
            except discord.Forbidden as discord_error:
                raise commands.CommandError(
                    f"I do not have permission to post in {channel.mention}.",
                ) from discord_error
            except discord.HTTPException as discord_error:
                raise commands.CommandError(
                    "Discord rejected the Cfx.re status panel.",
                ) from discord_error
            await self.config.guild(guild).status_message_id.set(message.id)

        await self.config.guild(guild).last_poll_at.set(self._utc_timestamp())
        return message

    def _configured_channel(
        self,
        guild: discord.Guild,
        settings: dict,
    ) -> discord.TextChannel:
        """Return the configured text channel or raise a command-facing error."""
        channel_id = settings.get("status_channel_id")
        if not channel_id:
            raise commands.CommandError(
                "No Cfx.re status channel is configured. Use "
                "`[p]cfxstatus setup [channel]` first.",
            )

        channel = guild.get_channel(channel_id)
        if not isinstance(channel, discord.TextChannel):
            raise commands.CommandError(
                "The configured Cfx.re status channel no longer exists or is "
                "not a text channel.",
            )
        return channel

    @staticmethod
    def _ensure_channel_permissions(
        guild: discord.Guild,
        channel: discord.TextChannel,
    ) -> None:
        """Raise a command-facing error if the bot cannot maintain the panel."""
        me = guild.me
        if me is None:
            raise commands.CommandError("I could not check my channel permissions.")

        permissions = channel.permissions_for(me)
        missing = []
        if not permissions.view_channel:
            missing.append("View Channel")
        if not permissions.send_messages:
            missing.append("Send Messages")
        if not permissions.embed_links:
            missing.append("Embed Links")

        if missing:
            joined = ", ".join(missing)
            raise commands.CommandError(
                f"I need {joined} in {channel.mention} to maintain the panel.",
            )

    async def _resolve_target_channel(
        self,
        ctx: commands.Context,
        channel: discord.TextChannel | None,
    ) -> discord.TextChannel | None:
        """Resolve an optional setup channel argument."""
        if channel is not None:
            return channel
        if isinstance(ctx.channel, discord.TextChannel):
            return ctx.channel
        await ctx.send("Run this in a text channel or provide a channel.")
        return None

    def _poll_interval(self, settings: dict) -> int:
        """Return a clamped polling interval for a settings payload."""
        interval = int(
            settings.get("poll_interval_minutes") or self.DEFAULT_POLL_INTERVAL_MINUTES,
        )
        return max(
            self.MIN_POLL_INTERVAL_MINUTES,
            min(interval, self.MAX_POLL_INTERVAL_MINUTES),
        )

    def _component_status_line(self, component: str, status: str) -> str:
        """Format a component row for the status-board embed field."""
        return (
            f"{self._status_emoji(status)} **{component}** - "
            f"{self._status_label(status)}"
        )

    def _status_label(self, status: str) -> str:
        if self._is_partial_outage(status):
            return "Partial Outage"
        if self._is_maintenance(status):
            return "Maintenance"
        if self._is_outage(status):
            return "Unavailable"
        if self._is_degraded(status):
            return "Degraded"
        if self._is_operational(status):
            return "Operational"
        return "Unknown"

    def _status_emoji(self, status: str) -> str:
        if self._is_partial_outage(status):
            return "🟠"
        if self._is_maintenance(status):
            return "🔵"
        if self._is_outage(status):
            return "🔴"
        if self._is_degraded(status):
            return "🟡"
        if self._is_operational(status):
            return "🟢"
        return "⚪"

    def _overall_status_emoji(self, components: dict[str, str]) -> str:
        statuses = list(components.values())
        if not statuses:
            return "⚪"
        if any(self._is_outage(status) for status in statuses):
            return "🔴"
        if any(self._is_partial_outage(status) for status in statuses):
            return "🟠"
        if any(self._is_maintenance(status) for status in statuses):
            return "🔵"
        if any(self._is_degraded(status) for status in statuses):
            return "🟡"
        if all(self._is_operational(status) for status in statuses):
            return "🟢"
        return "⚪"

    @staticmethod
    def _format_status_text(status: str) -> str:
        return status.replace("_", " ").strip().title()

    @staticmethod
    def _utc_timestamp() -> int:
        return int(datetime.now(timezone.utc).timestamp())

    @staticmethod
    def _message_url(guild_id: int, channel_id: int, message_id: int) -> str:
        return f"https://discord.com/channels/{guild_id}/{channel_id}/{message_id}"

    def _parse_statuspage_components(self, data: dict) -> dict[str, str]:
        """Map Cfx.re Statuspage API components to the panel's display rows."""
        if not isinstance(data, dict):
            return {}

        raw_components = data.get("components")
        if not isinstance(raw_components, list):
            return {}

        by_name = {
            str(component.get("name")): component
            for component in raw_components
            if isinstance(component, dict)
        }
        components: dict[str, str] = {}

        for display_name, source_names in self.STATUSPAGE_COMPONENT_MAP.items():
            source_component = None
            for source_name in source_names:
                source_component = by_name.get(source_name)
                if source_component is not None:
                    break
            if source_component is None:
                continue

            status = source_component.get("status")
            if isinstance(status, str) and status:
                components[display_name] = self._format_status_text(status)

        return components

    @staticmethod
    def _extract_visible_lines(html: str) -> list[str]:
        parser = VisibleTextParser()
        parser.feed(html)
        parser.close()

        lines: list[str] = []
        for part in parser.parts:
            for line in part.splitlines():
                cleaned = re.sub(r"\s+", " ", line).strip()
                if cleaned:
                    lines.append(cleaned)
        return lines

    @staticmethod
    def _extract_updated_at(lines: list[str]) -> str | None:
        for line in lines:
            if line.lower().startswith("as of "):
                return line[6:].strip()
        return None

    def _extract_cfx_components(self, lines: list[str]) -> dict[str, str]:
        cfx_index = self._find_line_index(lines, "Cfx.re")
        if cfx_index is None:
            return {}

        components = self._extract_components_from_lines(lines, cfx_index)
        if components:
            return components

        section_text = " ".join(lines[cfx_index + 1 :])
        return self._extract_components_from_text(section_text)

    def _extract_components_from_lines(
        self,
        lines: list[str],
        cfx_index: int,
    ) -> dict[str, str]:
        components: dict[str, str] = {}
        section_lines = lines[cfx_index + 1 :]
        component_names = {name.lower() for name in self.CFX_COMPONENTS}

        for index, line in enumerate(section_lines):
            if line.lower() not in component_names:
                continue
            status = self._next_status_line(section_lines, index + 1)
            if status:
                canonical = self._canonical_component_name(line)
                if canonical:
                    components[canonical] = status

        return components

    def _extract_components_from_text(self, section_text: str) -> dict[str, str]:
        components: dict[str, str] = {}
        pattern = "|".join(re.escape(name) for name in self.CFX_COMPONENTS)
        for component in self.CFX_COMPONENTS:
            match = re.search(
                rf"\b{re.escape(component)}\b\s+(.+?)(?=\b(?:{pattern})\b|$)",
                section_text,
                flags=re.IGNORECASE,
            )
            if match:
                status = re.sub(r"\s+", " ", match.group(1)).strip(" :")
                if status:
                    components[component] = status
        return components

    @staticmethod
    def _find_line_index(lines: list[str], needle: str) -> int | None:
        normalized_needle = needle.lower()
        for index, line in enumerate(lines):
            if line.lower() == normalized_needle:
                return index
        return None

    def _next_status_line(self, lines: list[str], start_index: int) -> str | None:
        component_names = {name.lower() for name in self.CFX_COMPONENTS}
        for line in lines[start_index:]:
            if line.lower() in component_names:
                return None
            if line.lower() == "cfx.re":
                return None
            return line
        return None

    def _canonical_component_name(self, component: str) -> str | None:
        for name in self.CFX_COMPONENTS:
            if name.lower() == component.lower():
                return name
        return None

    def _overall_status(self, components: dict[str, str]) -> str:
        if not components:
            return "Cfx.re service status is unknown."

        statuses = list(components.values())
        if all(self._is_operational(status) for status in statuses):
            return "All Cfx.re services are operational."
        if any(self._is_outage(status) for status in statuses):
            return "One or more Cfx.re services are unavailable."
        if any(self._is_partial_outage(status) for status in statuses):
            return "One or more Cfx.re services have a partial outage."
        if any(self._is_maintenance(status) for status in statuses):
            return "One or more Cfx.re services are under maintenance."
        if any(self._is_degraded(status) for status in statuses):
            return "One or more Cfx.re services are degraded."
        return "Cfx.re service status has mixed or unknown results."

    def _status_color(self, components: dict[str, str]) -> int:
        statuses = list(components.values())
        if not statuses:
            return self.UNKNOWN_COLOR
        if any(self._is_outage(status) for status in statuses):
            return self.OUTAGE_COLOR
        if any(self._is_partial_outage(status) for status in statuses):
            return self.PARTIAL_COLOR
        if any(self._is_maintenance(status) for status in statuses):
            return self.UNKNOWN_COLOR
        if any(self._is_degraded(status) for status in statuses):
            return self.DEGRADED_COLOR
        if all(self._is_operational(status) for status in statuses):
            return self.OPERATIONAL_COLOR
        return self.UNKNOWN_COLOR

    @staticmethod
    def _is_operational(status: str) -> bool:
        lowered = status.lower()
        return lowered == "operational" or "all services operational" in lowered

    @staticmethod
    def _is_degraded(status: str) -> bool:
        lowered = status.lower()
        return any(keyword in lowered for keyword in ("degraded", "limited"))

    @staticmethod
    def _is_outage(status: str) -> bool:
        lowered = status.lower()
        if "partial" in lowered:
            return False
        return any(
            keyword in lowered
            for keyword in ("outage", "unavailable", "offline", "down")
        )

    @staticmethod
    def _is_partial_outage(status: str) -> bool:
        lowered = status.lower()
        return "partial" in lowered

    @staticmethod
    def _is_maintenance(status: str) -> bool:
        lowered = status.lower()
        return "maintenance" in lowered
