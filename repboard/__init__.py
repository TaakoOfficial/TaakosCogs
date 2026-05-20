from .repboard import RepBoard


async def setup(bot):
    await bot.add_cog(RepBoard(bot))
