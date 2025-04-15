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

async def setup(bot: Red) -> None:
    """Load the RandomWeather cog."""
    if not ensure_pytz_installed():
        msg = error("Failed to load RandomWeather: Could not install required 'pytz' package. "
                   "Please install it manually with `pip install pytz`")
        await bot.send_to_owners(msg)
        return

    from .randomweather import WeatherCog
    await bot.add_cog(WeatherCog(bot))
