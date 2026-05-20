from .applications import Applications

__red_end_user_data_statement__ = (
    "This cog stores per-guild application forms, panel message IDs, poll records, "
    "application response answers, applicant user IDs, reviewer user IDs, vote records, "
    "and role/channel IDs needed to operate the configured workflows."
)


async def setup(bot):
    await bot.add_cog(Applications(bot))
