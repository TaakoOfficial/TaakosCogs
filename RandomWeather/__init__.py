"""RandomWeather - A cog for generating random daily weather updates."""
import sys
import subprocess
import logging
from redbot.core.bot import Red
from redbot.core.utils.chat_formatting import error

def ensure_pytz_installed() -> bool:
    """Ensure pytz is installed on the system."""
    try:
        import pytz
        return True
    except ImportError:
        try:
            python_exe = sys.executable
            subprocess.check_call(
                [python_exe, "-m", "pip", "install", "pytz"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            import pytz
            return True
        except (subprocess.SubprocessError, ImportError) as e:
            logging.error(f"Failed to install pytz: {e}")
            return False

from .randomweather import WeatherCog
from redbot.core import commands

async def setup(bot: commands.Bot):
    cog = WeatherCog(bot)
    await bot.add_cog(cog)
    # Register the slash command group for /rweather
    if hasattr(cog, "weather_group"):
        bot.tree.add_command(cog.weather_group)
