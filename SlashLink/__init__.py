"""Load SlashLink."""

from redbot.core.bot import Red

from .slashlink import SlashLink


async def setup(bot: Red) -> None:
    await bot.add_cog(SlashLink(bot))
