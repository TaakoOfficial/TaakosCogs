# This file marks the Fable directory as a Python package for Red-DiscordBot.

from .dependency_utils import check_and_install_google_dependencies
from .fable import Fable

async def setup(bot):
    check_and_install_google_dependencies()
    await bot.add_cog(Fable(bot))
