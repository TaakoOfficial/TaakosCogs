"""RandomWeather - A cog for generating random daily weather updates."""

from redbot.core import commands

from .randomweather import WeatherCog


async def setup(bot: commands.Bot):
    cog = WeatherCog(bot)
    await bot.add_cog(cog)
    # Register the slash command group for /rweather
    if hasattr(cog, "weather_group"):
        bot.tree.add_command(cog.weather_group)
