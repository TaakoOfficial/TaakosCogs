"""Red Config persistence and schema migrations."""

from __future__ import annotations

import asyncio
from copy import deepcopy
from typing import Any

import discord
from redbot.core import Config

from .models import Hub

SCHEMA_VERSION = 2
GLOBAL_DEFAULTS = {"schema_version": SCHEMA_VERSION}
GUILD_DEFAULTS = {
    "hubs": {},
    "settings": {
        "default_ephemeral": True,
        "hide_unavailable_commands": True,
        "sync_debounce_seconds": 10,
        "persist_last_command": False,
    },
    "sync_state": {"last_success": None, "last_error": None, "pending": False},
}
MEMBER_DEFAULTS = {"last_command": None}


def migrate_payload(payload: dict[str, Any], from_version: int) -> dict[str, Any]:
    """Migrate one guild payload. Kept pure for unit testing."""
    result = deepcopy(payload)
    hubs = result.setdefault("hubs", {})
    if from_version < 2:
        for name, hub in list(hubs.items()):
            hub.setdefault("name", name)
            old_permissions = hub.pop("required_permissions", [])
            if isinstance(old_permissions, list):
                permissions = discord.Permissions.none()
                valid = {name: True for name in old_permissions if name in dict(discord.Permissions.all())}
                permissions.update(**valid)
                hub.setdefault("required_user_permissions", permissions.value)
            else:
                hub.setdefault("required_user_permissions", int(old_permissions or 0))
            hub.setdefault("required_bot_permissions", 0)
            hub.setdefault("unavailable_behavior", "hide")
            for category in hub.get("categories", {}).values():
                for command in category.get("commands", []):
                    command.setdefault("disabled", False)
    merged_settings = deepcopy(GUILD_DEFAULTS["settings"])
    merged_settings.update(result.get("settings", {}))
    result["settings"] = merged_settings
    result.setdefault("sync_state", deepcopy(GUILD_DEFAULTS["sync_state"]))
    return result


class HubConfigStore:
    def __init__(self, cog: Any) -> None:
        self.config = Config.get_conf(cog, identifier=0x434F4D4D414E4448, force_registration=True)
        self.config.register_global(**GLOBAL_DEFAULTS)
        self.config.register_guild(**GUILD_DEFAULTS)
        self.config.register_member(**MEMBER_DEFAULTS)
        self._locks: dict[int, asyncio.Lock] = {}

    def lock(self, guild_id: int) -> asyncio.Lock:
        return self._locks.setdefault(guild_id, asyncio.Lock())

    async def migrate(self) -> tuple[int, int]:
        current = int(await self.config.schema_version())
        if current >= SCHEMA_VERSION:
            return current, current
        all_guilds = await self.config.all_guilds()
        for guild_id, payload in all_guilds.items():
            await self.config.guild_from_id(guild_id).set(migrate_payload(payload, current))
        await self.config.schema_version.set(SCHEMA_VERSION)
        return current, SCHEMA_VERSION

    async def list_hubs(self, guild_id: int) -> list[Hub]:
        raw = await self.config.guild_from_id(guild_id).hubs()
        return sorted((Hub.from_dict(value) for value in raw.values()), key=lambda hub: hub.name)

    async def get_hub(self, guild_id: int, name: str) -> Hub | None:
        raw = await self.config.guild_from_id(guild_id).hubs()
        data = raw.get(name.casefold())
        return Hub.from_dict(data) if data else None

    async def save_hub(self, guild_id: int, hub: Hub) -> None:
        async with self.lock(guild_id), self.config.guild_from_id(guild_id).hubs() as hubs:
            hubs[hub.name] = hub.to_dict()

    async def delete_hub(self, guild_id: int, name: str) -> bool:
        async with self.lock(guild_id), self.config.guild_from_id(guild_id).hubs() as hubs:
            return hubs.pop(name.casefold(), None) is not None

    async def settings(self, guild_id: int) -> dict[str, Any]:
        return await self.config.guild_from_id(guild_id).settings()

    async def all_guild_ids(self) -> list[int]:
        return [int(guild_id) for guild_id in (await self.config.all_guilds())]

    async def set_sync_state(
        self, guild_id: int, *, success: str | None = None, error: str | None = None, pending: bool = False
    ) -> None:
        previous = await self.config.guild_from_id(guild_id).sync_state()
        if pending and success is None and error is None:
            success = previous.get("last_success")
            error = previous.get("last_error")
        elif success is None and error is not None:
            success = previous.get("last_success")
        await self.config.guild_from_id(guild_id).sync_state.set(
            {"last_success": success, "last_error": error, "pending": pending},
        )
