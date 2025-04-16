from .yalc import YALC

async def setup(bot):
    await bot.add_cog(YALC(bot))
