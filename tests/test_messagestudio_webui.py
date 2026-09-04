import asyncio
from urllib.parse import parse_qs, urlparse

import aiohttp
from aiohttp.test_utils import TestClient, TestServer

from messagestudio.webui import WebUIError, WebUIIntegration


class _Permissions:
    manage_guild = True


class _Member:
    id = 42
    guild_permissions = _Permissions()


class _Guild:
    id = 100
    name = "Test Server"

    def get_member(self, user_id):
        return _Member() if user_id == _Member.id else None

    async def fetch_member(self, user_id):
        member = self.get_member(user_id)
        if member is None:
            raise RuntimeError("not found")
        return member


class _Bot:
    application_id = 1234

    def __init__(self):
        self.guild = _Guild()
        self.guilds = [self.guild]
        self.owner_ids = set()

    async def get_shared_api_tokens(self, service):
        assert service == "messagestudio"
        return {"client_id": "1234", "client_secret": "secret"}

    def get_guild(self, guild_id):
        return self.guild if guild_id == self.guild.id else None

    def get_user(self, user_id):
        return self.guild.get_member(user_id)


class _Config:
    async def webui(self):
        return {
            "enabled": True,
            "host": "127.0.0.1",
            "port": 8069,
            "public_url": "http://127.0.0.1:8069",
        }


class _Harness(WebUIIntegration):
    def __init__(self):
        self.bot = _Bot()
        self.config = _Config()
        self._init_webui()

    async def _can_manage_studio(self, user, guild):
        return user.id == 42 and guild.id == 100

    async def _exchange_discord_code(self, code):
        assert code == "valid-code"
        return 42

    async def dashboard_guild(self, **kwargs):
        if kwargs["method"] == "GET":
            csrf = kwargs["csrf_token"][1]
            return {"status": 0, "web_content": {"source": f'<input name="csrf_token" value="{csrf}">'}}
        return {"status": 0, "data": {"ok": True, "message": "Saved."}}


def test_webui_settings_default_to_localhost_url():
    settings = WebUIIntegration._validate_webui_settings({"enabled": False, "host": "127.0.0.1", "port": 8069, "public_url": ""})
    assert settings["public_url"] == "http://127.0.0.1:8069"


def test_webui_settings_require_https_for_public_hostname_or_ip():
    unsafe_settings = (
        {"enabled": True, "host": "0.0.0.0", "port": 8069, "public_url": ""},
        {"enabled": True, "host": "0.0.0.0", "port": 8069, "public_url": "http://203.0.113.10:8069"},
        {"enabled": True, "host": "127.0.0.1", "port": 8069, "public_url": "http://messages.example.com"},
    )
    for settings in unsafe_settings:
        try:
            WebUIIntegration._validate_webui_settings(settings)
        except WebUIError:
            pass
        else:
            raise AssertionError("Unsafe remote WebUI settings were accepted")

    accepted = WebUIIntegration._validate_webui_settings(
        {"enabled": True, "host": "0.0.0.0", "port": 8069, "public_url": "https://203.0.113.10:8069"}
    )
    assert accepted["public_url"] == "https://203.0.113.10:8069"


def test_webui_discord_oauth_session_permissions_csrf_and_headers():
    async def scenario():
        harness = _Harness()
        cookie_jar = aiohttp.CookieJar(unsafe=True)
        async with TestClient(TestServer(harness._build_webui_app()), cookie_jar=cookie_jar) as client:
            landing = await client.get("/messagestudio/")
            assert landing.status == 200
            assert "Log in with Discord" in await landing.text()
            assert landing.headers["Cache-Control"] == "no-store"
            assert "frame-ancestors 'none'" in landing.headers["Content-Security-Policy"]

            login = await client.get("/messagestudio/login", allow_redirects=False)
            assert login.status == 302
            authorize_url = login.headers["Location"]
            query = parse_qs(urlparse(authorize_url).query)
            assert query["scope"] == ["identify"]
            assert query["redirect_uri"] == ["http://127.0.0.1:8069/messagestudio/oauth/callback"]
            state = query["state"][0]

            callback = await client.get(f"/messagestudio/oauth/callback?code=valid-code&state={state}", allow_redirects=False)
            assert callback.status == 303
            assert "HttpOnly" in callback.headers.getall("Set-Cookie")[-1]
            assert "SameSite=Strict" in callback.headers.getall("Set-Cookie")[-1]

            replay = await client.get(f"/messagestudio/oauth/callback?code=valid-code&state={state}", allow_redirects=False)
            assert replay.status == 400

            server_picker = await client.get("/messagestudio/")
            assert "Test Server" in await server_picker.text()

            editor = await client.get("/messagestudio/guild/100")
            assert editor.status == 200
            editor_text = await editor.text()
            session = next(iter(harness._webui_sessions.values()))
            assert session.csrf_token in editor_text

            missing_csrf = await client.post("/messagestudio/guild/100/api", data={}, headers={"Origin": "http://127.0.0.1:8069"})
            assert missing_csrf.status == 400

            wrong_origin = await client.post(
                "/messagestudio/guild/100/api",
                data={"csrf_token": session.csrf_token},
                headers={"Origin": "https://attacker.example"},
            )
            assert wrong_origin.status == 403

            accepted = await client.post(
                "/messagestudio/guild/100/api",
                data={"csrf_token": session.csrf_token},
                headers={"Origin": "http://127.0.0.1:8069"},
            )
            assert accepted.status == 200
            assert (await accepted.json())["data"]["ok"] is True

    asyncio.run(scenario())
