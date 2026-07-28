"""DeepDelve package."""

from .deepdelve import DeepDelve

__version__ = "4.3.3"


async def setup(bot):
    """Load DeepDelve."""
    await bot.add_cog(DeepDelve(bot))
