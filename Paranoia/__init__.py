from .paranoia import Paranoia


async def setup(bot):
    await bot.add_cog(Paranoia(bot))