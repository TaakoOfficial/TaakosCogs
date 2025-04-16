"""Yet Another Logging Cog (YALC) - A powerful logging cog for Red-DiscordBot."""
import json
from pathlib import Path

from .yalc import YALC

with open(Path(__file__).parent / "info.json") as fp:
    __red_end_user_data_statement__ = json.load(fp).get("end_user_data_statement", 
        "This cog stores log channel and event settings per guild. No personal user data is stored."
    )

async def setup(bot):
    """Load the YALC cog."""
    await bot.add_cog(YALC(bot))
