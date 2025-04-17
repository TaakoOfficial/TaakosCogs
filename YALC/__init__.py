"""YALC - Yet Another Logging Cog for Red-DiscordBot."""
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from redbot.core.bot import Red

async def setup(bot: "Red") -> None:
    """Set up the YALC cog."""
    from .yalc import YALC
    cog = YALC(bot)
    await bot.add_cog(cog)
    
    # Register slash commands
    if bot.owner_ids:
        for owner_id in bot.owner_ids:
            owner = bot.get_user(owner_id)
            if owner:
                # Add the log command group
                bot.tree.add_command(cog.slash_group)
                # Global sync
                await bot.tree.sync()
                break
