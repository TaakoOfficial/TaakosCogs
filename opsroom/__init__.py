from .opsroom import OpsRoom


async def setup(bot):
    await bot.add_cog(OpsRoom(bot))
