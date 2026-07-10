# This file marks the Fable directory as a Python package for Red-DiscordBot.

import importlib.util
import subprocess
import sys

from .fable import Fable


def ensure_google_deps():
    if (
        importlib.util.find_spec("google.oauth2.service_account") is None
        or importlib.util.find_spec("googleapiclient.discovery") is None
    ):
        subprocess.check_call(
            [
                sys.executable,
                "-m",
                "pip",
                "install",
                "google-auth",
                "google-api-python-client",
            ],
        )


ensure_google_deps()


async def setup(bot):
    await bot.add_cog(Fable(bot))
