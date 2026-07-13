from .messagestudio import MessageStudio

__red_end_user_data_statement__ = (
    "This cog stores saved message payloads, their author Discord user IDs, lock settings, "
    "and usage counts when moderators use the message storage commands."
)


async def setup(bot):
    await bot.add_cog(MessageStudio(bot))
