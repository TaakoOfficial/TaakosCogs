from .captcha import Captcha

__red_end_user_data_statement__ = (
    "This cog stores per-guild captcha panel message IDs, channel IDs, role IDs, and "
    "button labels. Verification codes and user IDs are held only in memory while a "
    "modal is active and are not stored persistently."
)


async def setup(bot):
    await bot.add_cog(Captcha(bot))
