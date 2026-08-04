from .fable import Fable


async def setup(bot):
    await bot.add_cog(Fable(bot))
