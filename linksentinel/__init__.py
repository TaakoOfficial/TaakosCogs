from .linksentinel import LinkSentinel


async def setup(bot):
    await bot.add_cog(LinkSentinel(bot))
