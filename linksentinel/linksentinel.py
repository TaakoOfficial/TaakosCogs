"""Scheduled HTTP and TLS monitoring for community resource links."""

from __future__ import annotations

import asyncio
import csv
import io
import ipaddress
import re
import socket
import ssl
import time
from contextlib import suppress
from typing import TYPE_CHECKING, Any
from urllib.parse import urljoin, urlparse

import aiohttp
import discord
from discord.ext import tasks
from redbot.core import Config, commands

from .dashboard_integration import DashboardIntegration

if TYPE_CHECKING:
    from redbot.core.bot import Red


URL_RE = re.compile(r"https?://[^\s<>\])}\"']+", re.IGNORECASE)


class LinkSentinel(DashboardIntegration, commands.Cog):
    """Find broken community resources before members do."""

    CONFIG_IDENTIFIER = 2026080304
    COLOR = 0x3498DB

    def __init__(self, bot: Red) -> None:
        self.bot = bot
        self.session: aiohttp.ClientSession | None = None
        self._scan_lock = asyncio.Lock()
        self.config = Config.get_conf(self, identifier=self.CONFIG_IDENTIFIER, force_registration=True)
        self.config.register_guild(
            alert_channel_id=None,
            interval_hours=24,
            timeout_seconds=15,
            tls_warning_days=21,
            next_link_id=1,
            last_scan_at=0,
            links={},
        )

    async def cog_load(self) -> None:
        self.session = aiohttp.ClientSession(headers={"User-Agent": "TaakosCogs-LinkSentinel/1.0"})
        self.scheduled_scan.start()

    def cog_unload(self) -> None:
        self.scheduled_scan.cancel()
        if self.session and not self.session.closed:
            asyncio.create_task(self.session.close())

    async def red_delete_data_for_user(self, *, requester: str, user_id: int) -> None:
        return

    @staticmethod
    def _now() -> int:
        return int(time.time())

    @staticmethod
    def _normalise_url(url: str) -> str:
        clean = url.strip().rstrip(".,;:!?")
        parsed = urlparse(clean)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise commands.BadArgument("Provide a complete http:// or https:// URL.")
        if parsed.username or parsed.password:
            raise commands.BadArgument("URLs containing credentials are not accepted.")
        return clean[:2000]

    async def _add_link(
        self,
        guild: discord.Guild,
        url: str,
        label: str,
        *,
        source_channel_id: int | None = None,
        source_message_id: int | None = None,
    ) -> tuple[int, bool]:
        conf = self.config.guild(guild)
        links = await conf.links()
        existing = next((int(key) for key, item in links.items() if item.get("url") == url), None)
        if existing is not None:
            return existing, False
        link_id = await conf.next_link_id()
        links[str(link_id)] = {
            "link_id": link_id,
            "url": url,
            "label": label[:200] or urlparse(url).netloc,
            "source_channel_id": source_channel_id,
            "source_message_id": source_message_id,
            "enabled": True,
            "created_at": self._now(),
            "last_checked_at": None,
            "status": "new",
            "status_code": None,
            "final_url": None,
            "response_ms": None,
            "tls_expires_at": None,
            "error": None,
            "failures": 0,
        }
        await conf.links.set(links)
        await conf.next_link_id.set(link_id + 1)
        return link_id, True

    async def _check_tls(self, url: str, timeout: int) -> int | None:
        parsed = urlparse(url)
        if parsed.scheme != "https" or not parsed.hostname:
            return None
        port = parsed.port or 443
        context = ssl.create_default_context()
        writer = None
        try:
            _reader, writer = await asyncio.wait_for(
                asyncio.open_connection(parsed.hostname, port, ssl=context, server_hostname=parsed.hostname),
                timeout=timeout,
            )
            ssl_object = writer.get_extra_info("ssl_object")
            certificate = ssl_object.getpeercert() if ssl_object else None
            not_after = certificate.get("notAfter") if certificate else None
            return int(ssl.cert_time_to_seconds(not_after)) if not_after else None
        except (OSError, asyncio.TimeoutError, ssl.SSLError, ValueError):
            return None
        finally:
            if writer:
                writer.close()
                with suppress(OSError, ssl.SSLError):
                    await writer.wait_closed()

    async def _validate_public_target(self, url: str) -> None:
        """Reject local and special-use targets before each request or redirect."""
        parsed = urlparse(url)
        hostname = parsed.hostname
        if not hostname or hostname.casefold() == "localhost":
            raise ValueError("Local network targets are not allowed")
        port = parsed.port or (443 if parsed.scheme == "https" else 80)
        try:
            addresses = await asyncio.get_running_loop().getaddrinfo(
                hostname,
                port,
                type=socket.SOCK_STREAM,
            )
        except OSError as exc:
            raise ValueError(f"DNS resolution failed: {exc}") from exc
        for address in addresses:
            ip = ipaddress.ip_address(address[4][0])
            if not ip.is_global:
                raise ValueError(f"Non-public target {ip} is not allowed")

    async def _fetch(self, url: str, timeout: int) -> tuple[int, str]:
        """Fetch with manually validated redirects to prevent redirect-based SSRF."""
        if not self.session:
            raise RuntimeError("HTTP session is not ready")
        current = url
        client_timeout = aiohttp.ClientTimeout(total=timeout)
        for _redirect in range(9):
            await self._validate_public_target(current)
            async with self.session.get(
                current,
                allow_redirects=False,
                timeout=client_timeout,
                read_until_eof=False,
            ) as response:
                if 300 <= response.status < 400 and response.headers.get("Location"):
                    current = urljoin(current, response.headers["Location"])
                    continue
                return response.status, str(response.url)
        raise ValueError("Too many redirects")

    async def _check_link(self, item: dict[str, Any], timeout: int) -> dict[str, Any]:
        if not self.session:
            raise RuntimeError("HTTP session is not ready")
        started = time.monotonic()
        status_code = None
        final_url = None
        error = None
        try:
            status_code, final_url = await self._fetch(item["url"], timeout)
        except (aiohttp.ClientError, asyncio.TimeoutError, RuntimeError, ValueError) as exc:
            error = f"{type(exc).__name__}: {exc}"[:300]
        elapsed = int((time.monotonic() - started) * 1000)
        tls_expires_at = await self._check_tls(item["url"], timeout) if status_code is not None else None
        healthy = status_code is not None and status_code < 400
        result = dict(item)
        result.update(
            last_checked_at=self._now(),
            status="healthy" if healthy else "failed",
            status_code=status_code,
            final_url=final_url,
            response_ms=elapsed,
            tls_expires_at=tls_expires_at,
            error=error,
            failures=0 if healthy else int(item.get("failures", 0)) + 1,
        )
        return result

    async def _notify_change(self, guild: discord.Guild, old: dict[str, Any], new: dict[str, Any], warning_days: int) -> None:
        reasons = []
        if new["status"] == "failed" and old.get("status") != "failed":
            reasons.append(f"became unavailable ({new.get('error') or new.get('status_code')})")
        if new["status"] == "healthy" and old.get("status") == "failed":
            reasons.append("recovered")
        if new.get("final_url") and new["final_url"] != new["url"] and old.get("final_url") != new["final_url"]:
            reasons.append(f"redirects to {new['final_url']}")
        tls_expires_at = new.get("tls_expires_at")
        if tls_expires_at and tls_expires_at - self._now() <= warning_days * 86400:
            old_expiry = old.get("tls_expires_at")
            if old_expiry != tls_expires_at or old.get("last_checked_at") is None:
                reasons.append(f"TLS certificate expires <t:{tls_expires_at}:R>")
        if not reasons:
            return
        channel_id = await self.config.guild(guild).alert_channel_id()
        channel = guild.get_channel(channel_id) if channel_id else None
        if not isinstance(channel, discord.TextChannel):
            return
        color = 0x57F287 if new["status"] == "healthy" else 0xED4245
        embed = discord.Embed(
            title=f"LinkSentinel · {new['label']}",
            description=f"<{new['url']}>\n" + "\n".join(f"• {reason}" for reason in reasons),
            color=color,
            timestamp=discord.utils.utcnow(),
        )
        if new.get("source_channel_id") and new.get("source_message_id"):
            embed.add_field(
                name="Source",
                value=f"[Open message](https://discord.com/channels/{guild.id}/{new['source_channel_id']}/{new['source_message_id']})",
            )
        with suppress(discord.HTTPException):
            await channel.send(embed=embed)

    async def _scan_guild(self, guild: discord.Guild) -> tuple[int, int]:
        conf = self.config.guild(guild)
        settings = await conf.all()
        links = settings["links"]
        checked = failed = 0
        semaphore = asyncio.Semaphore(4)

        async def check(key: str, item: dict[str, Any]) -> tuple[str, dict[str, Any]]:
            async with semaphore:
                return key, await self._check_link(item, int(settings["timeout_seconds"]))

        jobs = [check(key, item) for key, item in links.items() if item.get("enabled", True)]
        for key, result in await asyncio.gather(*jobs):
            checked += 1
            failed += result["status"] == "failed"
            await self._notify_change(guild, links[key], result, int(settings["tls_warning_days"]))
            links[key] = result
        await conf.links.set(links)
        await conf.last_scan_at.set(self._now())
        return checked, failed

    @tasks.loop(minutes=15)
    async def scheduled_scan(self) -> None:
        if self._scan_lock.locked():
            return
        async with self._scan_lock:
            now = self._now()
            for guild in self.bot.guilds:
                settings = await self.config.guild(guild).all()
                if settings["links"] and now - settings["last_scan_at"] >= int(settings["interval_hours"]) * 3600:
                    await self._scan_guild(guild)

    @scheduled_scan.before_loop
    async def before_scheduled_scan(self) -> None:
        await self.bot.wait_until_red_ready()

    @commands.hybrid_group(name="linksentinel", aliases=["links"], invoke_without_command=True)
    @commands.guild_only()
    async def linksentinel(self, ctx: commands.Context) -> None:
        """Monitor important links and TLS certificates."""
        await ctx.send_help()

    @linksentinel.command(name="alertchannel")
    @commands.admin_or_permissions(manage_guild=True)
    async def alert_channel(self, ctx: commands.Context, channel: discord.TextChannel | None = None) -> None:
        """Set the channel for failure, recovery, redirect, and TLS alerts."""
        await self.config.guild(ctx.guild).alert_channel_id.set(channel.id if channel else None)
        await ctx.send(f"Link alerts will be sent to {channel.mention}." if channel else "Link alerts disabled.")

    @linksentinel.command(name="interval")
    @commands.admin_or_permissions(manage_guild=True)
    async def interval(self, ctx: commands.Context, hours: commands.Range[int, 1, 168]) -> None:
        """Set the scheduled check interval in hours."""
        await self.config.guild(ctx.guild).interval_hours.set(int(hours))
        await ctx.send(f"Links will be checked every **{hours} hour(s)**.")

    @linksentinel.command(name="add")
    @commands.admin_or_permissions(manage_guild=True)
    async def add(self, ctx: commands.Context, url: str, *, label: str = "") -> None:
        """Add a URL to the monitor."""
        clean = self._normalise_url(url)
        link_id, created = await self._add_link(ctx.guild, clean, label)
        await ctx.send(f"Added link **#{link_id}**." if created else f"That URL is already link **#{link_id}**.")

    @linksentinel.command(name="remove")
    @commands.admin_or_permissions(manage_guild=True)
    async def remove(self, ctx: commands.Context, link_id: int) -> None:
        """Remove a monitored link."""
        async with self.config.guild(ctx.guild).links() as links:
            removed = links.pop(str(link_id), None)
        if not removed:
            raise commands.BadArgument("Link not found.")
        await ctx.send(f"Removed **{removed['label']}**.")

    @linksentinel.command(name="discover")
    @commands.admin_or_permissions(manage_guild=True)
    async def discover(
        self, ctx: commands.Context, channel: discord.TextChannel | None = None, limit: commands.Range[int, 1, 500] = 100
    ) -> None:
        """Discover URLs in recent messages and pinned messages."""
        source = channel or ctx.channel
        if not isinstance(source, discord.TextChannel):
            raise commands.BadArgument("Choose a text channel.")
        messages: dict[int, discord.Message] = {}
        async for message in source.history(limit=int(limit)):
            messages[message.id] = message
        try:
            for message in await source.pins():
                messages[message.id] = message
        except discord.HTTPException:
            pass
        created = found = 0
        for message in messages.values():
            text = message.content + " " + " ".join(embed.url or "" for embed in message.embeds)
            for raw in URL_RE.findall(text):
                found += 1
                try:
                    url = self._normalise_url(raw)
                except commands.BadArgument:
                    continue
                _link_id, was_created = await self._add_link(
                    ctx.guild,
                    url,
                    urlparse(url).netloc,
                    source_channel_id=source.id,
                    source_message_id=message.id,
                )
                created += was_created
        await ctx.send(f"Found **{found}** URL occurrence(s); added **{created}** new unique link(s).")

    @linksentinel.command(name="scan")
    @commands.admin_or_permissions(manage_guild=True)
    async def scan(self, ctx: commands.Context) -> None:
        """Run a check immediately."""
        async with ctx.typing():
            checked, failed = await self._scan_guild(ctx.guild)
        await ctx.send(f"Checked **{checked}** link(s); **{failed}** currently failing.")

    @linksentinel.command(name="list")
    async def list_links(self, ctx: commands.Context, status: str = "all") -> None:
        """List monitored links, optionally filtered by healthy or failed."""
        links = await self.config.guild(ctx.guild).links()
        lines = []
        for item in links.values():
            if status != "all" and item.get("status") != status:
                continue
            icon = {"healthy": "✅", "failed": "❌"}.get(item.get("status"), "➖")
            lines.append(
                f"{icon} **#{item['link_id']} {item['label']}** · "
                f"{item.get('status_code') or item.get('status')} · <{item['url']}>"
            )
        await ctx.send(
            embed=discord.Embed(title="LinkSentinel", description="\n".join(lines[:25]) or "No matching links.", color=self.COLOR)
        )

    @linksentinel.command(name="export")
    @commands.admin_or_permissions(manage_guild=True)
    async def export(self, ctx: commands.Context) -> None:
        """Export monitoring results as CSV."""
        links = await self.config.guild(ctx.guild).links()
        output = io.StringIO()
        fields = [
            "link_id",
            "label",
            "url",
            "status",
            "status_code",
            "final_url",
            "response_ms",
            "tls_expires_at",
            "last_checked_at",
            "failures",
            "error",
        ]
        writer = csv.DictWriter(output, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(links.values())
        await ctx.send(file=discord.File(io.BytesIO(output.getvalue().encode()), filename="linksentinel.csv"))
