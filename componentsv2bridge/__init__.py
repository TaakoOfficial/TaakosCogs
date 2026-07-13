from .componentsv2bridge import ComponentsV2Builder

__red_end_user_data_statement__ = (
    "This cog does not persistently store user data. Message layouts are parsed on demand and sent directly to Discord."
)


async def setup(bot):
    await bot.add_cog(ComponentsV2Builder(bot))
