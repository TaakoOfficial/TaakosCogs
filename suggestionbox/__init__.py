from .suggestionbox import SuggestionBox


async def setup(bot):
    await bot.add_cog(SuggestionBox(bot))
