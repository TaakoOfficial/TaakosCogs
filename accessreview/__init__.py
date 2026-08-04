from .accessreview import AccessReview


async def setup(bot):
    await bot.add_cog(AccessReview(bot))
