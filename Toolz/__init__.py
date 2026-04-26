from .toolz import Toolz

__red_end_user_data_statement__ = (
    "This cog does not persistently store any end user data. Role member exports are "
    "generated on demand and sent directly to Discord without being saved locally."
)


async def setup(bot):
    await bot.add_cog(Toolz(bot))
