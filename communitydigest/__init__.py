from .communitydigest import CommunityDigest


async def setup(bot):
    await bot.add_cog(CommunityDigest(bot))
