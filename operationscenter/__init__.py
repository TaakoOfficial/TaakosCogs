from .operationscenter import OperationsCenter


async def setup(bot):
    await bot.add_cog(OperationsCenter(bot))
