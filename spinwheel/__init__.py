"""SpinWheel cog package."""

from .spinwheel import SpinWheel

__red_end_user_data_statement__ = (
    "This cog stores server-created wheel names, user-provided entry labels, color settings, "
    "winner-removal preferences, and aggregate spin counts. It does not store Discord user IDs."
)


async def setup(bot):
    cog = SpinWheel(bot)
    await bot.add_cog(cog)
    bot.tree.add_command(cog.wheel_slash)
