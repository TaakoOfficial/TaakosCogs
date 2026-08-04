from .eventcheckin import EventCheckin


async def setup(bot):
    await bot.add_cog(EventCheckin(bot))
