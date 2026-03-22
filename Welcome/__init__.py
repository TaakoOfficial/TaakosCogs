from .welcome import Welcome

__red_end_user_data_statement__ = (
    "This cog stores per-guild welcome settings, including channel IDs, message and embed "
    "templates, and optionally one cached welcome image per guild. It does not store end user data."
)


async def setup(bot):
    await bot.add_cog(Welcome(bot))
