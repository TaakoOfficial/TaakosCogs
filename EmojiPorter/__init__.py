from .emojiporter import EmojiPorter

__red_end_user_data_statement__ = "This cog does not persistently store any end user data."

async def setup(bot):
    await bot.add_cog(EmojiPorter(bot))