from .forumflow import ForumFlow


async def setup(bot):
    await bot.add_cog(ForumFlow(bot))
