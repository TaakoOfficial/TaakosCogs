# This file marks the Fable directory as a Python package for Red-DiscordBot.

from .fable import Fable

async def setup(bot):
    await bot.add_cog(Fable(bot))
