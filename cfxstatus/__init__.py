from .cfxstatus import CfxStatus

__red_end_user_data_statement__ = (
    "This cog stores per-guild Cfx.re status panel settings, including enabled "
    "state, channel IDs, message IDs, polling interval, and the last poll "
    "timestamp. It does not store Discord end user data."
)


async def setup(bot):
    await bot.add_cog(CfxStatus(bot))
