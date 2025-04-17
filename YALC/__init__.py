"""Yet Another Logging Cog (YALC) for Red-DiscordBot."""
from redbot.core.bot import Red

from .yalc import YALC
from . import utils

__red_end_user_data_statement__ = "This cog stores guild-specific settings like log channels and event configurations. No personal user data is stored permanently."

async def setup(bot: Red) -> None:
    """Set up the YALC cog."""
    cog = YALC(bot)
    await bot.add_cog(cog)
