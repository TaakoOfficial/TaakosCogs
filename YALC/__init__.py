"""YALC - Yet Another Logging Cog for Redbot."""
from . import yalc

async def setup(bot):
    """Load YALC cog."""
    cog = yalc.YALC(bot)
    await bot.add_cog(cog)
