from .tempvoice import TempVoice

__red_end_user_data_statement__ = (
    "This cog stores per-guild temporary voice settings, active temporary voice channel IDs, "
    "control panel message/channel IDs, owner Discord user IDs, permitted Discord user IDs, "
    "creation timestamps, channel names, lock state, and user limits."
)


async def setup(bot):
    await bot.add_cog(TempVoice(bot))
