from .reviewhub import ReviewHub

__red_end_user_data_statement__ = (
    "This cog stores per-guild review settings, review request records, review/vouch records, "
    "Discord user IDs for reviewers, reviewed users, reporters, useful votes, moderators, "
    "review text, ratings, message/channel IDs, timestamps, and deletion metadata. CSV exports "
    "are generated on demand and sent directly to Discord."
)


async def setup(bot):
    cog = ReviewHub(bot)
    await bot.add_cog(cog)
    cog.register_app_commands()
