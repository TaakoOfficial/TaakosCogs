from .rpcalander import RPCalander
import subprocess
import sys
import logging
import pkg_resources
from redbot.core import commands  # Import commands for ExtensionFailed and type hints

# Configure logging
log = logging.getLogger("red.taakoscogs.rpcalander")

def check_and_install_pytz():
    """Check if pytz is installed and install it if not."""
    try:
        pkg_resources.get_distribution("pytz")
        log.debug("pytz is already installed.")
    except pkg_resources.DistributionNotFound:
        log.info("pytz not found. Attempting to install...")
        try:
            # Ensure pip is available and install pytz
            subprocess.check_call([sys.executable, "-m", "pip", "install", "pytz"])
            log.info("pytz installed successfully.")
            # Re-check after installation
            pkg_resources.get_distribution("pytz")
        except subprocess.CalledProcessError as e:
            log.error(f"Failed to install pytz: {e}")
            raise RuntimeError("Failed to install pytz dependency.") from e
        except pkg_resources.DistributionNotFound:
            log.error("pytz still not found after attempting installation.")
            raise RuntimeError("Failed to install and verify pytz dependency.")

async def setup(bot: commands.Bot):  # Added type hint for bot
    # Check and install dependencies first
    try:
        check_and_install_pytz()
    except RuntimeError as e:
        log.error(f"Failed to load RPCalander cog due to dependency issue: {e}")
        # Raise ExtensionFailed correctly
        raise commands.ExtensionFailed(name="RPCalander", original=e) from e

    cog = RPCalander(bot)  # Create instance first
    await bot.add_cog(cog)  # Add the cog instance
