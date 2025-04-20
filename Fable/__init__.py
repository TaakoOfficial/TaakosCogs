# This file marks the Fable directory as a Python package for Red-DiscordBot.

import sys
import subprocess

def ensure_google_deps():
    try:
        import google.oauth2.service_account
        import googleapiclient.discovery
    except ImportError:
        subprocess.check_call([
            sys.executable, "-m", "pip", "install", "google-auth", "google-api-python-client"
        ])

ensure_google_deps()

from .fable import Fable

async def setup(bot):
    await bot.add_cog(Fable(bot))
