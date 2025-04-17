"""Yet Another Logging Cog (YALC) for Red-DiscordBot."""
from redbot.core.bot import Red

try:
    from .yalc import YALC
except (ImportError, ModuleNotFoundError):
    from yalc import YALC

try:
    from .utils import *  # Pre-import utils to ensure it's available for other modules
except (ImportError, ModuleNotFoundError):
    from utils import *

__red_end_user_data_statement__ = "This cog stores guild-specific settings like log channels and event configurations. No personal user data is stored permanently."

def __path__(self):
    """Return the package path."""
    import os
    return [os.path.dirname(os.path.abspath(__file__))]

async def setup(bot: Red) -> None:
    """Set up the YALC cog."""
    cog = YALC(bot)
    await bot.add_cog(cog)
