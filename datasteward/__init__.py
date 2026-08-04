from .datasteward import DataSteward


async def setup(bot):
    await bot.add_cog(DataSteward(bot))
