from .flipper import Flipper

async def setup(bot):
    await bot.add_cog(Flipper())