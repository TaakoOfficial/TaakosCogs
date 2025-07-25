from .dicey import Dicey

async def setup(bot):
    await bot.add_cog(Dicey())