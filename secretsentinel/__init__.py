from .secretsentinel import SecretSentinel


async def setup(bot):
    await bot.add_cog(SecretSentinel(bot))
