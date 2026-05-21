from .giveaway import Giveaway

__red_end_user_data_statement__ = (
    "This cog stores per-guild giveaway records, including giveaway message IDs, channel IDs, "
    "host IDs, winner IDs, prize text, and timestamps needed to end giveaways automatically."
)


async def setup(bot):
    cog = Giveaway(bot)
    await bot.add_cog(cog)
    if hasattr(cog, "giveaway_group"):
        bot.tree.add_command(cog.giveaway_group)
