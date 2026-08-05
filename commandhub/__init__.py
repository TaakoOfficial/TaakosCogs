"""CommandHub cog package."""

from redbot.core.bot import Red

from .commandhub import CommandHub

__red_end_user_data_statement__ = (
    "This cog stores per-guild hub configuration and, when repeat persistence is enabled, "
    "the most recent CommandHub invocation for each member."
)


async def setup(bot: Red) -> None:
    await bot.add_cog(CommandHub(bot))
