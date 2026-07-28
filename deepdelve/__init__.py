"""DeepDelve package."""

from .deepdelve import DeepDelve


async def setup(bot):
    """Load DeepDelve."""
    await bot.add_cog(DeepDelve(bot))
