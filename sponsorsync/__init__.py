from .sponsorsync import SponsorSync


async def setup(bot):
    await bot.add_cog(SponsorSync(bot))
