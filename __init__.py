from .weather_cog import WeatherCog  # Edited by Taako

async def setup(bot):
    await bot.add_cog(WeatherCog(bot))  # Edited by Taako
