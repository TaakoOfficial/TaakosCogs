"""RandomWeather - A cog for generating random daily weather updates."""

import importlib.util
import logging
import subprocess
import sys

from redbot.core import commands

from .randomweather import WeatherCog


def ensure_pytz_installed() -> bool:
    """Ensure pytz is installed on the system."""
    if importlib.util.find_spec("pytz") is not None:
        return True

    try:
        python_exe = sys.executable
        subprocess.check_call(
            [python_exe, "-m", "pip", "install", "pytz"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        return importlib.util.find_spec("pytz") is not None
    except subprocess.SubprocessError as e:
        logging.error(f"Failed to install pytz: {e}")
        return False


async def setup(bot: commands.Bot):
    cog = WeatherCog(bot)
    await bot.add_cog(cog)
    # Register the slash command group for /rweather
    if hasattr(cog, "weather_group"):
        bot.tree.add_command(cog.weather_group)
