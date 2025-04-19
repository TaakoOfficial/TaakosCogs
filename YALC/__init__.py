"""YALC - Yet Another Logging Cog for Red-DiscordBot."""
from typing import TYPE_CHECKING
from redbot.core.bot import Red

from .yalc import YALC

if TYPE_CHECKING:
    from redbot.core.bot import Red

async def setup(bot: "Red") -> None:
    """Set up the YALC cog."""
    from .yalc import YALC
    cog = YALC(bot)
    await bot.add_cog(cog)
    # No need to manually register a slash_group; hybrid commands are auto-registered.
