from .serverdoctor import ServerDoctor


async def setup(bot):
    await bot.add_cog(ServerDoctor(bot))
