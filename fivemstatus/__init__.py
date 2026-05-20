from .fivemstatus import FiveMStatus

__red_end_user_data_statement__ = (
    "This cog stores per-guild FiveM status configuration, including server endpoints, "
    "channel IDs, message IDs, display text, image URLs, button URLs, restart schedule, "
    "and the timestamp when the configured server was first observed online. It does "
    "not store FiveM player records or Discord end user data."
)


async def setup(bot):
    await bot.add_cog(FiveMStatus(bot))
