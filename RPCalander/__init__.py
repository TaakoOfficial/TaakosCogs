from .rpcalander import RPCalander
import subprocess
import sys
import logging
import pkg_resources
from redbot.core import commands

log = logging.getLogger("red.taakoscogs.rpcalander")

def check_and_install_pytz():
    try:
        pkg_resources.get_distribution("pytz")
        log.debug("pytz is already installed.")
    except pkg_resources.DistributionNotFound:
        log.info("pytz not found. Attempting to install...")
        try:
            subprocess.check_call([sys.executable, "-m", "pip", "install", "pytz"])
            log.info("pytz installed successfully.")
            pkg_resources.get_distribution("pytz")
        except subprocess.CalledProcessError as e:
            log.error(f"Failed to install pytz: {e}")
            raise commands.ExtensionFailed(name="RPCalander", original=e) from e
        except pkg_resources.DistributionNotFound:
            log.error("pytz still not found after attempting installation.")
            raise commands.ExtensionFailed(name="RPCalander", original=RuntimeError("Failed to install and verify pytz dependency."))

async def setup(bot: commands.Bot):
    check_and_install_pytz()
    cog = RPCalander(bot)
    await bot.add_cog(cog)
    # Register the grouped slash commands
    if hasattr(cog, "rpca_group"):
        bot.tree.add_command(cog.rpca_group)
