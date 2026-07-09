from .captcha import Captcha

__red_end_user_data_statement__ = (
    "This cog stores per-guild captcha panel message IDs, channel IDs, role IDs, and "
    "button labels. Verification codes and user IDs are held transiently in memory for "
    "code rotation and active modal validation and are not stored persistently."
)


async def setup(bot):
    await bot.add_cog(Captcha(bot))
