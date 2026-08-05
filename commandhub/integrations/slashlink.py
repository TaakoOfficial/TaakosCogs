"""Duck-typed, optional SlashLink integration."""

from __future__ import annotations

import inspect
import logging
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    import discord

log = logging.getLogger("red.taakoscogs.commandhub.slashlink")


class SlashLinkAdapter:
    REQUIRED_METHODS = ("get_linked_commands", "get_command_schema", "invoke_linked_command")

    def __init__(self, bot: Any) -> None:
        self.bot = bot
        self._warned_for: int | None = None

    @property
    def cog(self) -> Any | None:
        return self.bot.get_cog("SlashLink")

    @property
    def available(self) -> bool:
        cog = self.cog
        return cog is not None and all(callable(getattr(cog, method, None)) for method in self.REQUIRED_METHODS)

    def check_compatibility(self) -> bool:
        cog = self.cog
        if cog is None:
            return False
        compatible = self.available
        if not compatible and self._warned_for != id(cog):
            self._warned_for = id(cog)
            log.warning("SlashLink is loaded but does not expose CommandHub's optional adapter API; integration disabled.")
        return compatible

    async def get_linked_commands(self) -> list[Any]:
        if not self.check_compatibility():
            return []
        result = self.cog.get_linked_commands()
        return list(await result if inspect.isawaitable(result) else result)

    async def get_schema(self, qualified_name: str) -> Any:
        if not self.check_compatibility():
            return None
        result = self.cog.get_command_schema(qualified_name)
        return await result if inspect.isawaitable(result) else result

    async def invoke(self, interaction: discord.Interaction, qualified_name: str, arguments: dict[str, Any]) -> None:
        if not self.check_compatibility():
            raise RuntimeError("SlashLink is unavailable or incompatible.")
        await self.cog.invoke_linked_command(interaction, qualified_name, arguments)
