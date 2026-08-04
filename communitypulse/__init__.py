from .communitypulse import CommunityPulse


async def setup(bot):
    await bot.add_cog(CommunityPulse(bot))
