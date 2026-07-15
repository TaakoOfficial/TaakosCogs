from .rolekit import RoleKit


async def setup(bot):
    await bot.add_cog(RoleKit(bot))
