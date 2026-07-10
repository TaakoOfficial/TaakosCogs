"""FiveM server status panel for Red-DiscordBot."""

from __future__ import annotations

import asyncio
import logging
import re
from datetime import datetime, time, timedelta, timezone
from typing import TYPE_CHECKING, Any
from urllib.parse import urlparse
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import aiohttp
import discord
from discord.ext import tasks
from redbot.core import Config, commands
from redbot.core.utils.chat_formatting import box, pagify

from .dashboard_integration import DashboardIntegration

if TYPE_CHECKING:
    from redbot.core.bot import Red

log = logging.getLogger("red.taakoscogs.fivemstatus")

RECOVERABLE_EXCEPTIONS = (
    aiohttp.ClientError,
    discord.DiscordException,
    OSError,
    RuntimeError,
    ValueError,
    KeyError,
    TypeError,
    AttributeError,
)

ServerData = dict[str, Any]
GuildSettings = dict[str, Any]


class FiveMStatus(DashboardIntegration, commands.Cog):
    """Post and maintain a live FiveM server status embed."""

    REQUEST_TIMEOUT = aiohttp.ClientTimeout(total=10)
    DEFAULT_COLOR = 0x3B315F
    OFFLINE_COLOR = 0xD84E4E
    CFX_JOIN_CODE_RE = re.compile(r"[a-z0-9]{3,24}", re.IGNORECASE)

    def __init__(self, bot: Red) -> None:
        self.bot = bot
        self.config = Config.get_conf(
            self,
            identifier=2026051301,
            force_registration=True,
        )
        self.config.register_guild(
            enabled=False,
            server_address=None,
            status_channel_id=None,
            status_message_id=None,
            display_name=None,
            status_message="The city is vibing, grab your character and jump in!",
            logo_url=None,
            image_url=None,
            embed_color=self.DEFAULT_COLOR,
            connect_url=None,
            discord_url=None,
            hosting_url=None,
            restart_times=[],
            timezone="America/Chicago",
            online_since=None,
            last_seen_online=False,
        )
        self._session: aiohttp.ClientSession | None = None
        self._task = self.status_loop.start()

    async def cog_unload(self) -> None:
        """Cancel background work and close HTTP resources."""
        if self._task:
            self._task.cancel()
        if self._session and not self._session.closed:
            await self._session.close()

    async def red_delete_data_for_user(self, *, requester: str, user_id: int) -> None:
        """This cog does not store Discord user IDs."""
        return

    @tasks.loop(minutes=1)
    async def status_loop(self) -> None:
        """Refresh every configured status message."""
        all_guilds = await self.config.all_guilds()
        for guild_id, settings in all_guilds.items():
            if not settings.get("enabled"):
                continue
            guild = self.bot.get_guild(guild_id)
            if guild is None:
                continue
            try:
                await self._update_status_message(guild, settings)
            except RECOVERABLE_EXCEPTIONS:
                log.exception(
                    "Failed to update FiveM status for guild %s", guild_id)

    @status_loop.before_loop
    async def before_status_loop(self) -> None:
        """Wait until the bot is ready before polling FiveM servers."""
        await self.bot.wait_until_ready()

    @commands.hybrid_group(
        name="fivemstatus",
        aliases=["fivem"],
        invoke_without_command=True,
    )
    @commands.guild_only()
    async def fivemstatus(self, ctx: commands.Context) -> None:
        """Configure and post a live FiveM server status panel."""
        await self._send_settings(ctx)

    @fivemstatus.command(name="setup")
    @commands.admin_or_permissions(manage_guild=True)
    async def fivemstatus_setup(
        self,
        ctx: commands.Context,
        server: str,
        channel: discord.TextChannel | None = None,
    ) -> None:
        """Set the FiveM server endpoint and post the status panel.

        The server can be an IP:port, hostname:port, cfx.re/join URL, or join code.
        """
        assert ctx.guild is not None
        if channel is None:
            if not isinstance(ctx.channel, discord.TextChannel):
                await ctx.send("Run this in a text channel or provide a channel.")
                return
            channel = ctx.channel

        normalized = self._normalize_server_address(server)
        await self.config.guild(ctx.guild).server_address.set(normalized)
        await self.config.guild(ctx.guild).status_channel_id.set(channel.id)
        await self.config.guild(ctx.guild).enabled.set(True)

        try:
            message = await self._update_status_message(ctx.guild, force_post=True)
        except commands.CommandError as error:
            await ctx.send(str(error))
            return

        await ctx.send(
            f"FiveM status is posting in {channel.mention}: {message.jump_url}",
        )

    @fivemstatus.command(name="server")
    @commands.admin_or_permissions(manage_guild=True)
    async def fivemstatus_server(self, ctx: commands.Context, server: str) -> None:
        """Set the FiveM server endpoint without reposting the panel."""
        assert ctx.guild is not None
        normalized = self._normalize_server_address(server)
        await self.config.guild(ctx.guild).server_address.set(normalized)
        await self.config.guild(ctx.guild).online_since.set(None)
        await self.config.guild(ctx.guild).last_seen_online.set(False)
        await ctx.tick()

    @fivemstatus.command(name="channel")
    @commands.admin_or_permissions(manage_guild=True)
    async def fivemstatus_channel(
        self,
        ctx: commands.Context,
        channel: discord.TextChannel | None = None,
    ) -> None:
        """Set the channel used for the status panel."""
        assert ctx.guild is not None
        if channel is None:
            if not isinstance(ctx.channel, discord.TextChannel):
                await ctx.send("Run this in a text channel or provide a channel.")
                return
            channel = ctx.channel
        await self.config.guild(ctx.guild).status_channel_id.set(channel.id)
        await ctx.send(f"FiveM status channel set to {channel.mention}.")

    @fivemstatus.command(name="post")
    @commands.admin_or_permissions(manage_guild=True)
    async def fivemstatus_post(self, ctx: commands.Context) -> None:
        """Post a fresh status panel in the configured channel."""
        assert ctx.guild is not None
        try:
            message = await self._update_status_message(ctx.guild, force_post=True)
        except commands.CommandError as error:
            await ctx.send(str(error))
            return
        await self.config.guild(ctx.guild).enabled.set(True)
        await ctx.send(f"FiveM status panel posted: {message.jump_url}")

    @fivemstatus.command(name="refresh")
    @commands.admin_or_permissions(manage_guild=True)
    async def fivemstatus_refresh(self, ctx: commands.Context) -> None:
        """Refresh the configured status panel now."""
        assert ctx.guild is not None
        try:
            message = await self._update_status_message(ctx.guild)
        except commands.CommandError as error:
            await ctx.send(str(error))
            return
        await ctx.send(f"FiveM status refreshed: {message.jump_url}")

    @fivemstatus.command(name="enable")
    @commands.admin_or_permissions(manage_guild=True)
    async def fivemstatus_enable(self, ctx: commands.Context, enabled: bool) -> None:
        """Enable or disable automatic status refreshes."""
        assert ctx.guild is not None
        await self.config.guild(ctx.guild).enabled.set(enabled)
        await ctx.send(
            f"FiveM status refreshes are now {'enabled' if enabled else 'disabled'}.",
        )

    @fivemstatus.command(name="name")
    @commands.admin_or_permissions(manage_guild=True)
    async def fivemstatus_name(
        self,
        ctx: commands.Context,
        *,
        name: str | None = None,
    ) -> None:
        """Set or clear the display name shown in the status embed."""
        assert ctx.guild is not None
        await self.config.guild(ctx.guild).display_name.set(
            self._clean_optional_text(name, 120),
        )
        await ctx.tick()

    @fivemstatus.command(name="message")
    @commands.admin_or_permissions(manage_guild=True)
    async def fivemstatus_message(
        self,
        ctx: commands.Context,
        *,
        message: str | None = None,
    ) -> None:
        """Set or clear the short message shown below the server name."""
        assert ctx.guild is not None
        await self.config.guild(ctx.guild).status_message.set(
            self._clean_optional_text(message, 300),
        )
        await ctx.tick()

    @fivemstatus.command(name="logo")
    @commands.admin_or_permissions(manage_guild=True)
    async def fivemstatus_logo(
        self,
        ctx: commands.Context,
        url: str | None = None,
    ) -> None:
        """Set or clear the thumbnail logo URL."""
        assert ctx.guild is not None
        await self.config.guild(ctx.guild).logo_url.set(self._clean_optional_url(url))
        await ctx.tick()

    @fivemstatus.command(name="image")
    @commands.admin_or_permissions(manage_guild=True)
    async def fivemstatus_image(
        self,
        ctx: commands.Context,
        url: str | None = None,
    ) -> None:
        """Set or clear the large image URL."""
        assert ctx.guild is not None
        await self.config.guild(ctx.guild).image_url.set(self._clean_optional_url(url))
        await ctx.tick()

    @fivemstatus.command(name="color")
    @commands.admin_or_permissions(manage_guild=True)
    async def fivemstatus_color(
        self,
        ctx: commands.Context,
        color: discord.Color | None,
    ) -> None:
        """Set the embed color, or omit the color to restore the default."""
        assert ctx.guild is not None
        await self.config.guild(ctx.guild).embed_color.set(
            color.value if color else self.DEFAULT_COLOR,
        )
        await ctx.tick()

    @fivemstatus.command(name="connecturl")
    @commands.admin_or_permissions(manage_guild=True)
    async def fivemstatus_connect_url(
        self,
        ctx: commands.Context,
        url: str | None = None,
    ) -> None:
        """Set or clear the Join Server button URL."""
        assert ctx.guild is not None
        await self.config.guild(ctx.guild).connect_url.set(
            self._clean_optional_url(url),
        )
        await ctx.tick()

    @fivemstatus.command(name="joincode", aliases=["cfxjoin", "cfxcode"])
    @commands.admin_or_permissions(manage_guild=True)
    async def fivemstatus_join_code(
        self,
        ctx: commands.Context,
        *,
        code: str | None = None,
    ) -> None:
        """Set or clear the CFX join code used by the Join Server button."""
        assert ctx.guild is not None
        join_code = self._clean_optional_cfx_join_code(code)
        connect_url = self._cfx_join_url(join_code) if join_code else None
        await self.config.guild(ctx.guild).connect_url.set(connect_url)
        if connect_url:
            await ctx.send(f"Join Server button set to `{connect_url}`.")
        else:
            await ctx.send("Join Server button URL cleared.")

    @fivemstatus.command(name="discordurl")
    @commands.admin_or_permissions(manage_guild=True)
    async def fivemstatus_discord_url(
        self,
        ctx: commands.Context,
        url: str | None = None,
    ) -> None:
        """Set or clear the Discord/community button URL."""
        assert ctx.guild is not None
        await self.config.guild(ctx.guild).discord_url.set(
            self._clean_optional_url(url),
        )
        await ctx.tick()

    @fivemstatus.command(name="hostingurl")
    @commands.admin_or_permissions(manage_guild=True)
    async def fivemstatus_hosting_url(
        self,
        ctx: commands.Context,
        url: str | None = None,
    ) -> None:
        """Set or clear the hosting/sponsor button URL."""
        assert ctx.guild is not None
        await self.config.guild(ctx.guild).hosting_url.set(
            self._clean_optional_url(url),
        )
        await ctx.tick()

    @fivemstatus.group(name="restart", invoke_without_command=True)
    @commands.admin_or_permissions(manage_guild=True)
    async def fivemstatus_restart(self, ctx: commands.Context) -> None:
        """Manage scheduled restart times shown on the panel."""
        await ctx.send_help()

    @fivemstatus_restart.command(name="add")
    @commands.admin_or_permissions(manage_guild=True)
    async def fivemstatus_restart_add(
        self,
        ctx: commands.Context,
        restart_time: str,
    ) -> None:
        """Add a daily restart time in 24-hour HH:MM format."""
        assert ctx.guild is not None
        parsed = self._parse_restart_time(restart_time)
        async with self.config.guild(ctx.guild).restart_times() as restart_times:
            if parsed not in restart_times:
                restart_times.append(parsed)
                restart_times.sort()
        await ctx.send(f"Added restart time `{parsed}`.")

    @fivemstatus_restart.command(name="remove")
    @commands.admin_or_permissions(manage_guild=True)
    async def fivemstatus_restart_remove(
        self,
        ctx: commands.Context,
        restart_time: str,
    ) -> None:
        """Remove a configured daily restart time."""
        assert ctx.guild is not None
        parsed = self._parse_restart_time(restart_time)
        async with self.config.guild(ctx.guild).restart_times() as restart_times:
            if parsed in restart_times:
                restart_times.remove(parsed)
                await ctx.send(f"Removed restart time `{parsed}`.")
                return
        await ctx.send(f"`{parsed}` is not configured.")

    @fivemstatus_restart.command(name="clear")
    @commands.admin_or_permissions(manage_guild=True)
    async def fivemstatus_restart_clear(self, ctx: commands.Context) -> None:
        """Clear all configured restart times."""
        assert ctx.guild is not None
        await self.config.guild(ctx.guild).restart_times.set([])
        await ctx.send("Restart schedule cleared.")

    @fivemstatus.command(name="timezone")
    @commands.admin_or_permissions(manage_guild=True)
    async def fivemstatus_timezone(
        self,
        ctx: commands.Context,
        timezone_name: str,
    ) -> None:
        """Set the timezone used for restart countdowns."""
        assert ctx.guild is not None
        try:
            ZoneInfo(timezone_name)
        except ZoneInfoNotFoundError:
            await ctx.send("Unknown timezone. Use an IANA name like `America/Chicago`.")
            return
        await self.config.guild(ctx.guild).timezone.set(timezone_name)
        await ctx.send(f"FiveM restart timezone set to `{timezone_name}`.")

    @fivemstatus.command(name="players")
    async def fivemstatus_players(self, ctx: commands.Context) -> None:
        """Show the current online FiveM players from the configured server."""
        assert ctx.guild is not None
        settings = await self.config.guild(ctx.guild).all()
        server_address = settings.get("server_address")
        if not server_address:
            await ctx.send("No FiveM server is configured yet.")
            return

        data = await self._fetch_server_data(server_address)
        if not data["online"]:
            await ctx.send(
                f"The FiveM server appears to be offline: {data.get('error') or 'no response'}",
            )
            return

        players = data.get("players") or []
        if not players:
            await ctx.send("The server is online, but no players are currently listed.")
            return

        lines = []
        for player in players:
            player_id = player.get("id", "?")
            name = str(player.get("name") or "Unknown")
            ping = player.get("ping")
            ping_text = f" - {ping} ms" if ping is not None else ""
            lines.append(f"{player_id}: {name}{ping_text}")

        header = f"{len(players)} player(s) online"
        pages = [
            f"{header}\n\n{page}" for page in pagify("\n".join(lines), page_length=1800)
        ]
        for page in pages:
            await ctx.send(box(page))

    @fivemstatus.command(name="settings")
    async def fivemstatus_settings(self, ctx: commands.Context) -> None:
        """Show the current FiveM status configuration."""
        await self._send_settings(ctx)

    @staticmethod
    def _clean_optional_text(value: str | None, limit: int) -> str | None:
        if value is None:
            return None
        cleaned = value.strip()
        if cleaned.lower() in {"clear", "none", "reset", "off"}:
            return None
        return cleaned[:limit] or None

    @staticmethod
    def _clean_optional_url(value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip()
        if cleaned.lower() in {"clear", "none", "reset", "off"}:
            return None
        parsed = urlparse(cleaned)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise commands.BadArgument(
                "Provide a full `http://` or `https://` URL, or `clear`.",
            )
        return cleaned

    @classmethod
    def _clean_optional_cfx_join_code(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip().lower()
        if cleaned in {"clear", "none", "reset", "off"}:
            return None

        if cleaned.startswith("fivem://connect/"):
            cleaned = cleaned.split("/", 3)[-1]

        join_match = re.search(
            r"(?:cfx\.re/join/|servers/single/)([a-z0-9]+)", cleaned)
        if join_match:
            cleaned = join_match.group(1)

        if cleaned.startswith("cfx:"):
            cleaned = cleaned[4:]

        if not cls.CFX_JOIN_CODE_RE.fullmatch(cleaned):
            raise commands.BadArgument(
                "Provide a CFX join code like `gmblex`, a `https://cfx.re/join/...` URL, or `clear`.",
            )
        return cleaned

    @staticmethod
    def _cfx_join_url(join_code: str) -> str:
        return f"https://cfx.re/join/{join_code}"

    @classmethod
    def _normalize_server_address(cls, value: str) -> str:
        server = value.strip()
        if not server:
            raise commands.BadArgument(
                "Provide a FiveM IP:port, hostname:port, cfx.re/join URL, or join code.",
            )

        lowered = server.lower()
        if lowered.startswith("fivem://connect/"):
            server = server.split("/", 3)[-1]
            lowered = server.lower()

        join_match = re.search(
            r"(?:cfx\.re/join/|servers/single/)([a-z0-9]+)", lowered)
        if join_match:
            return f"cfx:{join_match.group(1)}"

        if (
            cls.CFX_JOIN_CODE_RE.fullmatch(lowered)
            and "." not in lowered
            and ":" not in lowered
        ):
            return f"cfx:{lowered}"

        if "://" in server:
            parsed = urlparse(server)
            host = parsed.hostname
            if not host:
                raise commands.BadArgument(
                    "Could not read a host from that server URL.",
                )
            if parsed.port:
                return f"{host}:{parsed.port}"
            return f"{host}:30120"

        if "/" in server:
            server = server.split("/", 1)[0]

        return server if ":" in server else f"{server}:30120"

    @staticmethod
    def _parse_restart_time(value: str) -> str:
        match = re.fullmatch(r"(\d{1,2}):?(\d{2})", value.strip())
        if not match:
            raise commands.BadArgument(
                "Use 24-hour time like `06:00` or `1800`.")
        hour = int(match.group(1))
        minute = int(match.group(2))
        if hour > 23 or minute > 59:
            raise commands.BadArgument(
                "Restart times must be valid 24-hour times.")
        return f"{hour:02d}:{minute:02d}"

    async def _session_get_json(self, url: str) -> Any:
        session = await self._get_session()
        headers = {
            "Accept": "application/json",
            "User-Agent": "TaakosCogs-fivemstatus/1.1",
        }
        async with session.get(
            url,
            headers=headers,
            timeout=self.REQUEST_TIMEOUT,
        ) as response:
            if response.status >= 400:
                raise aiohttp.ClientResponseError(
                    response.request_info,
                    response.history,
                    status=response.status,
                    message=response.reason,
                    headers=response.headers,
                )
            return await response.json(content_type=None)

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
        return self._session

    async def _fetch_server_data(self, server_address: str) -> ServerData:
        if server_address.startswith("cfx:"):
            return await self._fetch_cfx_data(server_address[4:])
        return await self._fetch_direct_data(server_address)

    async def _fetch_cfx_data(self, join_code: str) -> ServerData:
        url = f"https://servers-frontend.fivem.net/api/servers/single/{join_code}"
        try:
            payload = await self._session_get_json(url)
            data = payload.get("Data", payload) if isinstance(
                payload, dict) else {}
            players = data.get("players") or data.get("Players") or []
            vars_data = data.get("vars") or data.get("Vars") or {}
            endpoints = (
                data.get("connectEndPoints") or data.get(
                    "connectEndpoints") or []
            )
            connect_endpoint = endpoints[0] if endpoints else f"cfx.re/join/{join_code}"
            hostname = (
                data.get("hostname")
                or vars_data.get("sv_projectName")
                or "FiveM Server"
            )
            clients = self._to_int(data.get("clients"), len(players))
            max_clients = self._to_int(
                data.get("svMaxclients")
                or data.get("sv_maxclients")
                or vars_data.get("sv_maxClients")
                or vars_data.get("sv_maxclients"),
                None,
            )
            return {
                "online": True,
                "hostname": self._strip_fivem_formatting(str(hostname)),
                "clients": clients,
                "max_clients": max_clients,
                "players": players if isinstance(players, list) else [],
                "vars": vars_data if isinstance(vars_data, dict) else {},
                "connect_endpoint": str(connect_endpoint),
                "join_code": join_code,
                "error": None,
            }
        except RECOVERABLE_EXCEPTIONS as error:
            data = self._offline_data(f"cfx.re/join/{join_code}", error)
            data["join_code"] = join_code
            return data

    async def _fetch_direct_data(self, server_address: str) -> ServerData:
        base_url = f"http://{server_address}"
        try:
            dynamic_task = asyncio.create_task(
                self._session_get_json(f"{base_url}/dynamic.json"),
            )
            info_task = asyncio.create_task(
                self._session_get_json(f"{base_url}/info.json"),
            )
            players_task = asyncio.create_task(
                self._session_get_json(f"{base_url}/players.json"),
            )
            dynamic, info, players = await asyncio.gather(
                dynamic_task,
                info_task,
                players_task,
                return_exceptions=True,
            )

            if isinstance(dynamic, Exception) and isinstance(info, Exception):
                raise dynamic

            dynamic_data = dynamic if isinstance(dynamic, dict) else {}
            info_data = info if isinstance(info, dict) else {}
            players_data = players if isinstance(players, list) else []
            vars_data = (
                info_data.get("vars") if isinstance(
                    info_data.get("vars"), dict) else {}
            )

            hostname = (
                dynamic_data.get("hostname")
                or vars_data.get("sv_projectName")
                or vars_data.get("sv_hostname")
                or "FiveM Server"
            )
            clients = self._to_int(dynamic_data.get(
                "clients"), len(players_data))
            max_clients = self._to_int(
                dynamic_data.get("sv_maxclients")
                or dynamic_data.get("sv_maxClients")
                or vars_data.get("sv_maxClients")
                or vars_data.get("sv_maxclients"),
                None,
            )
            return {
                "online": True,
                "hostname": self._strip_fivem_formatting(str(hostname)),
                "clients": clients,
                "max_clients": max_clients,
                "players": players_data,
                "vars": vars_data,
                "connect_endpoint": server_address,
                "join_code": None,
                "error": None,
            }
        except RECOVERABLE_EXCEPTIONS as error:
            return self._offline_data(server_address, error)

    @classmethod
    def _offline_data(cls, server_address: str, error: Exception) -> ServerData:
        return {
            "online": False,
            "hostname": "FiveM Server",
            "clients": 0,
            "max_clients": None,
            "players": [],
            "vars": {},
            "connect_endpoint": server_address,
            "join_code": None,
            "error": f"{type(error).__name__}: {error}",
        }

    @staticmethod
    def _to_int(value: Any, default: int | None) -> int | None:
        try:
            return int(value)
        except (TypeError, ValueError):
            return default

    @staticmethod
    def _strip_fivem_formatting(value: str) -> str:
        text = re.sub(r"\^[0-9]", "", value)
        text = re.sub(r"~[a-z_]+~", "", text, flags=re.IGNORECASE)
        return discord.utils.remove_markdown(text).strip() or "FiveM Server"

    @staticmethod
    def _shorten(text: str, limit: int) -> str:
        if len(text) <= limit:
            return text
        return text[: max(0, limit - 3)].rstrip() + "..."

    @staticmethod
    def _format_duration(seconds: float | None) -> str:
        if seconds is None:
            return "Not tracked"
        seconds = max(0, int(seconds))
        days, seconds = divmod(seconds, 86400)
        hours, seconds = divmod(seconds, 3600)
        minutes, _seconds = divmod(seconds, 60)
        parts = []
        if days:
            parts.append(f"{days} day{'s' if days != 1 else ''}")
        if hours:
            parts.append(f"{hours} hr{'s' if hours != 1 else ''}")
        if minutes or not parts:
            parts.append(f"{minutes} min{'s' if minutes != 1 else ''}")
        return ", ".join(parts[:2])

    def _format_next_restart(self, settings: GuildSettings) -> str:
        restart_times = settings.get("restart_times") or []
        if not restart_times:
            return "Not set"

        timezone_name = settings.get("timezone") or "UTC"
        try:
            tz = ZoneInfo(timezone_name)
        except ZoneInfoNotFoundError:
            tz = timezone.utc

        now = datetime.now(tz)
        candidates = []
        for raw_time in restart_times:
            try:
                hour, minute = [int(part)
                                    for part in str(raw_time).split(":", 1)]
                restart_at = datetime.combine(
                    now.date(), time(hour, minute), tzinfo=tz)
            except (TypeError, ValueError):
                continue
            if restart_at <= now:
                restart_at += timedelta(days=1)
            candidates.append(restart_at)

        if not candidates:
            return "Not set"

        next_restart = min(candidates)
        return f"in {self._format_duration((next_restart - now).total_seconds())}"

    async def _update_status_message(
        self,
        guild: discord.Guild,
        settings: GuildSettings | None = None,
        *,
        force_post: bool = False,
    ) -> discord.Message:
        settings = settings or await self.config.guild(guild).all()
        server_address = settings.get("server_address")
        channel_id = settings.get("status_channel_id")
        if not server_address:
            raise commands.UserFeedbackCheckFailure(
                "No FiveM server is configured yet.",
            )
        if not channel_id:
            raise commands.UserFeedbackCheckFailure(
                "No FiveM status channel is configured yet.",
            )

        try:
            channel = guild.get_channel(int(channel_id))
        except (TypeError, ValueError):
            channel = None
        if not isinstance(channel, discord.TextChannel):
            raise commands.UserFeedbackCheckFailure(
                "The configured FiveM status channel was not found.",
            )

        data = await self._fetch_server_data(server_address)
        settings = await self._sync_uptime_state(guild, settings, data["online"])
        embed = self._build_status_embed(settings, data)
        view = self._build_status_view(settings, data)

        message = None
        message_id = settings.get("status_message_id")
        if message_id and not force_post:
            try:
                message = await channel.fetch_message(int(message_id))
            except (
                discord.NotFound,
                discord.Forbidden,
                discord.HTTPException,
                ValueError,
                TypeError,
            ):
                message = None

        if message is None:
            try:
                message = await channel.send(embed=embed, view=view)
            except discord.Forbidden as error:
                raise commands.UserFeedbackCheckFailure(
                    "I cannot send the FiveM status panel in the configured channel.",
                ) from error
            except discord.HTTPException as error:
                raise commands.UserFeedbackCheckFailure(
                    f"Discord rejected the FiveM status panel: {error}",
                ) from error
            await self.config.guild(guild).status_message_id.set(message.id)
            return message

        try:
            await message.edit(embed=embed, view=view)
        except discord.Forbidden as error:
            raise commands.UserFeedbackCheckFailure(
                "I cannot edit the configured FiveM status panel.",
            ) from error
        except discord.HTTPException as error:
            raise commands.UserFeedbackCheckFailure(
                f"Discord rejected the FiveM status update: {error}",
            ) from error
        return message

    async def _sync_uptime_state(
        self,
        guild: discord.Guild,
        settings: GuildSettings,
        online: bool,
    ) -> GuildSettings:
        now_ts = int(datetime.now(timezone.utc).timestamp())
        config = self.config.guild(guild)
        online_since = settings.get("online_since")
        last_seen_online = bool(settings.get("last_seen_online"))

        if online:
            if not online_since or not last_seen_online:
                online_since = now_ts
                await config.online_since.set(online_since)
            if not last_seen_online:
                await config.last_seen_online.set(True)
        else:
            if online_since is not None:
                await config.online_since.set(None)
            if last_seen_online:
                await config.last_seen_online.set(False)
            online_since = None

        settings["online_since"] = online_since
        settings["last_seen_online"] = online
        return settings

    def _build_status_embed(
        self,
        settings: GuildSettings,
        data: ServerData,
    ) -> discord.Embed:
        online = bool(data.get("online"))
        configured_color = (
            self._to_int(settings.get("embed_color"), self.DEFAULT_COLOR)
            or self.DEFAULT_COLOR
        )
        color = configured_color if online else self.OFFLINE_COLOR
        title = settings.get("display_name") or data.get(
            "hostname") or "FiveM Server"
        description = settings.get("status_message") or ""
        if not online and data.get("error"):
            description = "The city is currently offline or unreachable."

        embed = discord.Embed(
            title=self._shorten(str(title), 256),
            description=self._shorten(
                str(description), 350) if description else None,
            color=discord.Color(color),
            timestamp=discord.utils.utcnow(),
        )

        logo_url = settings.get("logo_url")
        if logo_url:
            embed.set_thumbnail(url=logo_url)

        image_url = settings.get("image_url") or self._best_banner_url(data)
        if image_url:
            embed.set_image(url=image_url)

        status_text = "🟢 Online" if online else "🔴 Offline"
        max_clients = data.get("max_clients")
        max_text = str(max_clients) if max_clients is not None else "?"
        players_text = (
            f"{data.get('clients', 0)}/{max_text}" if online else f"0/{max_text}"
        )
        connect_endpoint = str(
            data.get("connect_endpoint")
            or settings.get("server_address")
            or "not configured",
        )
        connect_command = f"connect {connect_endpoint}"

        online_since = self._to_int(settings.get("online_since"), None)
        uptime_seconds = None
        if online and online_since:
            uptime_seconds = datetime.now(
                timezone.utc).timestamp() - online_since

        embed.add_field(name="STATUS", value=f"`{status_text}`", inline=True)
        embed.add_field(name="PLAYERS", value=f"`{players_text}`", inline=True)
        embed.add_field(name="\u200b", value="\u200b", inline=True)
        embed.add_field(
            name="F8 CONNECT COMMAND",
            value=box(connect_command),
            inline=False,
        )
        embed.add_field(
            name="NEXT RESTART",
            value=f"`{self._format_next_restart(settings)}`",
            inline=True,
        )
        embed.add_field(
            name="UPTIME",
            value=f"`{self._format_duration(uptime_seconds)}`",
            inline=True,
        )
        embed.add_field(name="\u200b", value="\u200b", inline=True)

        vars_data = data.get("vars") or {}
        txadmin_version = vars_data.get("txAdmin-version") or vars_data.get(
            "txadmin-version",
        )
        footer_parts = []
        if txadmin_version:
            footer_parts.append(f"txAdmin {txadmin_version}")
        footer_parts.append("Updated every minute")
        embed.set_footer(text=" • ".join(footer_parts))
        return embed

    @staticmethod
    def _best_banner_url(data: ServerData) -> str | None:
        vars_data = data.get("vars") or {}
        for key in ("banner_detail", "banner_connecting"):
            value = vars_data.get(key)
            if isinstance(value, str) and value.startswith(("http://", "https://")):
                return value
        return None

    def _build_status_view(
        self,
        settings: GuildSettings,
        data: ServerData,
    ) -> discord.ui.View | None:
        view = discord.ui.View(timeout=None)

        connect_url = settings.get("connect_url")
        if not connect_url:
            join_code = data.get("join_code")
            server_address = settings.get("server_address")
            if (
                not join_code
                and isinstance(server_address, str)
                and server_address.startswith("cfx:")
            ):
                join_code = server_address[4:]
            if join_code:
                connect_url = self._cfx_join_url(str(join_code))
        if connect_url:
            view.add_item(discord.ui.Button(
                label="Join Server", url=connect_url))

        discord_url = settings.get("discord_url")
        if discord_url:
            view.add_item(discord.ui.Button(label="Discord", url=discord_url))

        hosting_url = settings.get("hosting_url")
        if hosting_url:
            view.add_item(discord.ui.Button(label="Hosting", url=hosting_url))

        return view if view.children else None

    async def _send_settings(self, ctx: commands.Context) -> None:
        assert ctx.guild is not None
        settings = await self.config.guild(ctx.guild).all()
        channel = (
            ctx.guild.get_channel(settings["status_channel_id"])
            if settings.get("status_channel_id")
            else None
        )
        restarts = ", ".join(settings.get("restart_times") or []) or "Not set"
        lines = [
            f"Enabled: {settings.get('enabled')}",
            f"Server: {settings.get('server_address') or 'Not set'}",
            f"Channel: {channel.mention if isinstance(channel, discord.TextChannel) else 'Not set'}",
            f"Message ID: {settings.get('status_message_id') or 'Not set'}",
            f"Display name: {settings.get('display_name') or 'Auto from server'}",
            f"Timezone: {settings.get('timezone') or 'UTC'}",
            f"Restart times: {restarts}",
            f"Logo URL: {settings.get('logo_url') or 'Not set'}",
            f"Image URL: {settings.get('image_url') or 'Auto/server banner'}",
            f"Join Server button: {settings.get('connect_url') or 'Auto for cfx.re join codes'}",
            f"Discord button: {settings.get('discord_url') or 'Not set'}",
            f"Hosting button: {settings.get('hosting_url') or 'Not set'}",
        ]
        embed = discord.Embed(
            title="FiveM Status Settings",
            description=box("\n".join(lines)),
            color=discord.Color(self.DEFAULT_COLOR),
        )
        embed.add_field(
            name="Quick Start",
            value=(
                "`[p]fivem setup <ip:port|cfx_code> [#channel]`\n"
                "`[p]fivem logo <image_url>`\n"
                "`[p]fivem image <banner_url>`\n"
                "`[p]fivem restart add 06:00`"
            ),
            inline=False,
        )
        await ctx.send(embed=embed)
