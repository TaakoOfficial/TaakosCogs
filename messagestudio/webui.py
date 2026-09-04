"""Discord OAuth2-authenticated built-in WebUI transport for MessageStudio."""

from __future__ import annotations

import asyncio
import hmac
import html
import logging
import secrets
import time
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlencode, urlparse

import aiohttp
import discord
from aiohttp import web

log = logging.getLogger("red.taakoscogs.messagestudio.webui")


@dataclass(slots=True)
class _SessionRecord:
    user_id: int
    expires_at: float
    csrf_token: str


class WebUIError(RuntimeError):
    """Raised when the built-in WebUI cannot be configured or started."""


class WebUIIntegration:
    """Serve the existing editor without requiring Red-Web-Dashboard."""

    WEBUI_PATH = "/messagestudio"
    WEBUI_OAUTH_TTL = 10 * 60
    WEBUI_SESSION_TTL = 60 * 60
    DISCORD_API = "https://discord.com/api/v10"

    def _init_webui(self) -> None:
        self._webui_runner: web.AppRunner | None = None
        self._webui_site: web.TCPSite | None = None
        self._webui_oauth_states: dict[str, float] = {}
        self._webui_sessions: dict[str, _SessionRecord] = {}
        self._webui_lock = asyncio.Lock()
        self._webui_bound_port: int | None = None

    @staticmethod
    def _validate_webui_settings(settings: dict[str, Any]) -> dict[str, Any]:
        host = str(settings.get("host", "127.0.0.1")).strip()
        if not host or any(character in host for character in "/?#"):
            raise WebUIError("The bind host must be a hostname or IP address, without a URL scheme.")
        try:
            port = int(settings.get("port", 8069))
        except (TypeError, ValueError) as exc:
            raise WebUIError("The WebUI port must be a number from 1024 to 65535.") from exc
        if not 1024 <= port <= 65535:
            raise WebUIError("The WebUI port must be from 1024 to 65535.")

        public_url = str(settings.get("public_url", "")).strip().rstrip("/")
        if not public_url:
            if host not in {"127.0.0.1", "localhost", "::1"}:
                raise WebUIError("Set a public URL before binding the WebUI beyond localhost.")
            display_host = f"[{host}]" if ":" in host else host
            public_url = f"http://{display_host}:{port}"
        parsed = urlparse(public_url)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise WebUIError("The public URL must be an absolute HTTP(S) URL.")
        if parsed.username or parsed.password or parsed.query or parsed.fragment or parsed.path not in {"", "/"}:
            raise WebUIError("The public URL must contain only a scheme and host, with an optional port.")
        if parsed.scheme != "https" and parsed.hostname not in {"127.0.0.1", "localhost", "::1"}:
            raise WebUIError("A non-local public URL, including a server IP, must use HTTPS.")
        return {"enabled": bool(settings.get("enabled", False)), "host": host, "port": port, "public_url": public_url}

    async def _start_webui(self, settings: dict[str, Any] | None = None) -> None:
        settings = self._validate_webui_settings(settings or await self.config.webui())
        if not settings["enabled"]:
            return
        await self._oauth_credentials()
        async with self._webui_lock:
            if self._webui_runner is not None:
                return
            runner = web.AppRunner(self._build_webui_app(), access_log=None)
            await runner.setup()
            try:
                site = web.TCPSite(runner, settings["host"], settings["port"])
                await site.start()
            except Exception:
                await runner.cleanup()
                raise
            self._webui_runner = runner
            self._webui_site = site
            self._webui_bound_port = settings["port"]
            log.info("MessageStudio WebUI listening on %s:%s", settings["host"], settings["port"])

    def _build_webui_app(self) -> web.Application:
        """Build the bounded HTTP application used by production and route tests."""
        app = web.Application(client_max_size=512 * 1024, middlewares=[self._webui_security_headers])
        app.router.add_get(f"{self.WEBUI_PATH}/", self._webui_home)
        app.router.add_get(f"{self.WEBUI_PATH}/login", self._webui_login)
        app.router.add_get(f"{self.WEBUI_PATH}/oauth/callback", self._webui_oauth_callback)
        app.router.add_get(f"{self.WEBUI_PATH}/guild/{{guild_id}}", self._webui_editor)
        app.router.add_get(f"{self.WEBUI_PATH}/guild/{{guild_id}}/api", self._webui_editor)
        app.router.add_post(f"{self.WEBUI_PATH}/guild/{{guild_id}}/api", self._webui_api)
        return app

    async def _stop_webui(self) -> None:
        async with self._webui_lock:
            runner, self._webui_runner = self._webui_runner, None
            self._webui_site = None
            self._webui_bound_port = None
            self._webui_oauth_states.clear()
            self._webui_sessions.clear()
            if runner is not None:
                await runner.cleanup()

    def _prune_webui_access(self) -> None:
        now = time.monotonic()
        self._webui_oauth_states = {
            state: expires_at for state, expires_at in self._webui_oauth_states.items() if expires_at > now
        }
        expired = [session_id for session_id, record in self._webui_sessions.items() if record.expires_at <= now]
        for session_id in expired:
            self._webui_sessions.pop(session_id, None)

    async def _oauth_credentials(self) -> tuple[str, str]:
        tokens = await self.bot.get_shared_api_tokens("messagestudio")
        client_id = str(tokens.get("client_id") or getattr(self.bot, "application_id", "") or "").strip()
        client_secret = str(tokens.get("client_secret", "")).strip()
        if not client_id or not client_secret:
            raise WebUIError(
                "Discord OAuth is not configured. Use `[p]set api messagestudio client_id,<application ID> "
                "client_secret,<client secret>` in DM, then enable the WebUI."
            )
        return client_id, client_secret

    async def _webui_home(self, request: web.Request) -> web.Response:
        record = self._webui_session(request)
        if record is None:
            body = self._webui_shell(
                "MessageStudio",
                "Build rich Discord messages in your browser.",
                f'<a class="button" href="{self.WEBUI_PATH}/login">Log in with Discord</a>',
            )
            return web.Response(text=body, content_type="text/html")

        guild_links = []
        seen: set[int] = set()
        for guild in self.bot.guilds:
            member = guild.get_member(record.user_id)
            if member is not None and await self._can_manage_studio(member, guild):
                seen.add(guild.id)
                guild_links.append(self._guild_link(guild))
        if record.user_id in getattr(self.bot, "owner_ids", set()):
            guild_links.extend(self._guild_link(guild) for guild in self.bot.guilds if guild.id not in seen)
        content = "".join(guild_links) or "<p>You do not have Manage Server access in a shared server.</p>"
        body = self._webui_shell("Choose a server", "Only servers you can manage are shown.", content)
        return web.Response(text=body, content_type="text/html")

    def _guild_link(self, guild: discord.Guild) -> str:
        return (
            f'<a class="guild" href="{self.WEBUI_PATH}/guild/{guild.id}">'
            f"<strong>{html.escape(guild.name)}</strong><span>Open editor</span></a>"
        )

    async def _webui_login(self, _request: web.Request) -> web.StreamResponse:
        settings = self._validate_webui_settings(await self.config.webui())
        client_id, _ = await self._oauth_credentials()
        state = secrets.token_urlsafe(32)
        self._prune_webui_access()
        self._webui_oauth_states[state] = time.monotonic() + self.WEBUI_OAUTH_TTL
        redirect_uri = f"{settings['public_url']}{self.WEBUI_PATH}/oauth/callback"
        query = urlencode(
            {
                "client_id": client_id,
                "redirect_uri": redirect_uri,
                "response_type": "code",
                "scope": "identify",
                "state": state,
            }
        )
        response = web.HTTPFound(location=f"https://discord.com/oauth2/authorize?{query}")
        response.set_cookie(
            "messagestudio_oauth_state",
            state,
            max_age=self.WEBUI_OAUTH_TTL,
            httponly=True,
            secure=settings["public_url"].startswith("https://"),
            samesite="Lax",
            path=f"{self.WEBUI_PATH}/oauth/callback",
        )
        raise response

    async def _webui_oauth_callback(self, request: web.Request) -> web.StreamResponse:
        self._prune_webui_access()
        state = request.query.get("state", "")
        state_cookie = request.cookies.get("messagestudio_oauth_state", "")
        expires_at = self._webui_oauth_states.pop(state, 0)
        if not state or not hmac.compare_digest(state, state_cookie) or expires_at <= time.monotonic():
            raise web.HTTPBadRequest(text="The Discord login state is invalid or expired. Start again from MessageStudio.")
        code = request.query.get("code", "")
        if not code:
            raise web.HTTPBadRequest(text="Discord did not return an authorization code.")

        user_id = await self._exchange_discord_code(code)

        settings = self._validate_webui_settings(await self.config.webui())
        session_id = secrets.token_urlsafe(32)
        self._webui_sessions[session_id] = _SessionRecord(
            user_id=user_id,
            expires_at=time.monotonic() + self.WEBUI_SESSION_TTL,
            csrf_token=secrets.token_urlsafe(32),
        )
        response = web.HTTPSeeOther(location=f"{self.WEBUI_PATH}/")
        response.del_cookie("messagestudio_oauth_state", path=f"{self.WEBUI_PATH}/oauth/callback")
        response.set_cookie(
            "messagestudio_session",
            session_id,
            max_age=self.WEBUI_SESSION_TTL,
            httponly=True,
            secure=settings["public_url"].startswith("https://"),
            samesite="Strict",
            path=self.WEBUI_PATH,
        )
        raise response

    async def _exchange_discord_code(self, code: str) -> int:
        """Exchange an authorization code, verify identity, and retain no Discord token."""
        settings = self._validate_webui_settings(await self.config.webui())
        client_id, client_secret = await self._oauth_credentials()
        redirect_uri = f"{settings['public_url']}{self.WEBUI_PATH}/oauth/callback"
        timeout = aiohttp.ClientTimeout(total=15, connect=5)
        try:
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.post(
                    f"{self.DISCORD_API}/oauth2/token",
                    data={
                        "client_id": client_id,
                        "client_secret": client_secret,
                        "grant_type": "authorization_code",
                        "code": code,
                        "redirect_uri": redirect_uri,
                    },
                ) as token_response:
                    token_data = await token_response.json(content_type=None)
                    if token_response.status != 200 or not token_data.get("access_token"):
                        raise web.HTTPBadGateway(text="Discord could not complete the OAuth token exchange.")
                async with session.get(
                    f"{self.DISCORD_API}/users/@me",
                    headers={"Authorization": f"Bearer {token_data['access_token']}"},
                ) as user_response:
                    user_data = await user_response.json(content_type=None)
                    if user_response.status != 200 or not str(user_data.get("id", "")).isdigit():
                        raise web.HTTPBadGateway(text="Discord could not verify the signed-in user.")
        except (aiohttp.ClientError, asyncio.TimeoutError, ValueError) as error:
            raise web.HTTPBadGateway(text="Discord authentication is temporarily unavailable.") from error
        return int(user_data["id"])

    def _webui_session(self, request: web.Request) -> _SessionRecord | None:
        self._prune_webui_access()
        return self._webui_sessions.get(request.cookies.get("messagestudio_session", ""))

    async def _webui_guild_session(
        self, request: web.Request
    ) -> tuple[_SessionRecord, discord.Guild, discord.Member | discord.User]:
        record = self._webui_session(request)
        if record is None:
            raise web.HTTPSeeOther(location=f"{self.WEBUI_PATH}/")
        try:
            guild_id = int(request.match_info["guild_id"])
        except ValueError as exc:
            raise web.HTTPNotFound(text="That server does not exist.") from exc
        guild = self.bot.get_guild(guild_id)
        if guild is None:
            raise web.HTTPNotFound(text="That server is not connected to this bot.")
        member = guild.get_member(record.user_id)
        if member is None:
            try:
                member = await guild.fetch_member(record.user_id)
            except (discord.NotFound, discord.Forbidden, discord.HTTPException):
                member = None
        if member is None and record.user_id not in getattr(self.bot, "owner_ids", set()):
            raise web.HTTPForbidden(text="You are not a member of that server.")
        user = member or self.bot.get_user(record.user_id)
        if user is None or not await self._can_manage_studio(user, guild):
            raise web.HTTPForbidden(text="You need Manage Server, Red admin, or bot owner access.")
        return record, guild, user

    async def _webui_editor(self, request: web.Request) -> web.Response:
        record, guild, user = await self._webui_guild_session(request)
        result = await self.dashboard_guild(
            user=user,
            guild=guild,
            method="GET",
            csrf_token=("csrf_token", record.csrf_token),
            request_url=f"{self.WEBUI_PATH}/guild/{guild.id}/api",
        )
        if result.get("status") != 0:
            raise web.HTTPForbidden(text=result.get("error_message", "MessageStudio access was denied."))
        return web.Response(text=result["web_content"]["source"], content_type="text/html")

    async def _webui_api(self, request: web.Request) -> web.Response:
        record, guild, user = await self._webui_guild_session(request)
        settings = self._validate_webui_settings(await self.config.webui())
        origin = request.headers.get("Origin", "")
        if not origin or not hmac.compare_digest(origin, self._origin(settings["public_url"])):
            raise web.HTTPForbidden(text="The request origin was not allowed.")
        form = await request.post()
        if not hmac.compare_digest(str(form.get("csrf_token", "")), record.csrf_token):
            raise web.HTTPBadRequest(text="The MessageStudio security token is invalid. Reload the editor and try again.")
        return web.json_response(await self.dashboard_guild(user=user, guild=guild, method="POST", data=form))

    @web.middleware
    async def _webui_security_headers(self, request: web.Request, handler: Any) -> web.StreamResponse:
        """Apply browser hardening headers to success and error responses."""
        try:
            response = await handler(request)
        except web.HTTPException as error:
            self._secure_webui_response(error)
            raise
        self._secure_webui_response(response)
        return response

    @staticmethod
    def _origin(url: str) -> str:
        parsed = urlparse(url)
        return f"{parsed.scheme}://{parsed.netloc}"

    @staticmethod
    def _secure_webui_response(response: web.StreamResponse) -> None:
        response.headers["Cache-Control"] = "no-store"
        response.headers["Content-Security-Policy"] = (
            "default-src 'none'; style-src 'unsafe-inline'; script-src 'unsafe-inline'; "
            "img-src https: data:; connect-src 'self'; base-uri 'none'; form-action 'self'; frame-ancestors 'none'"
        )
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"

    @staticmethod
    def _webui_shell(title: str, subtitle: str, content: str) -> str:
        """Render the small pre-editor OAuth and guild-selection surface."""
        return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{html.escape(title)} · MessageStudio</title><style>
:root{{color-scheme:dark;font-family:ui-sans-serif,system-ui,sans-serif;background:#111827;color:#d8e0ea}}
*{{box-sizing:border-box}}body{{margin:0;min-height:100dvh;display:grid;place-items:center;padding:24px}}
main{{width:min(620px,100%);background:#182334;border:1px solid #40536a;border-radius:12px;padding:32px}}
h1{{margin:0 0 8px;font-size:28px}}p{{color:#9aa9ba;line-height:1.5;margin:0 0 24px}}
.button,.guild{{display:flex;align-items:center;justify-content:space-between;gap:16px;border-radius:7px;text-decoration:none}}
.button{{width:max-content;background:#5865f2;color:white;padding:11px 16px;font-weight:700}}
.guild{{color:#d8e0ea;border-top:1px solid #40536a;padding:16px 4px}}.guild span{{color:#8fb8ff}}
a:focus-visible{{outline:3px solid #93c5fd;outline-offset:3px}}
</style></head><body><main><h1>{html.escape(title)}</h1><p>{html.escape(subtitle)}</p>{content}</main></body></html>"""
