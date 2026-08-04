from .staffops import StaffOps


async def setup(bot):
    await bot.add_cog(StaffOps(bot))
