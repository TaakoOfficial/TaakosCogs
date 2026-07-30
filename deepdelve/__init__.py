"""DeepDelve package."""

from .deepdelve import DeepDelve

__version__ = "5.0.1"


async def setup(bot):
    """Load DeepDelve."""
    await bot.add_cog(DeepDelve(bot))
