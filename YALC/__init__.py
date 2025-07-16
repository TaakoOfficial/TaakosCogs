"""YALC - Yet Another Logging Cog for Red-DiscordBot."""
from typing import TYPE_CHECKING
from redbot.core.bot import Red

from .yalc import YALC

if TYPE_CHECKING:
    from redbot.core.bot import Red

async def setup(bot: "Red") -> None:
    """Set up the YALC cog."""
    from .yalc import YALC
    cog = YALC(bot)
    await bot.add_cog(cog)
    # Ensure dashboard integration is bound after cog is initialized
    # (This is redundant if already done in YALC.__init__, but safe if not)
    try:
        from .dashboard_integration import DashboardIntegration
        DashboardIntegration(cog).setup_dashboard()
    except Exception as e:
        import logging
        logging.getLogger("red.taako.yalc").error(f"Dashboard integration setup failed in __init__.py: {e}", exc_info=True)
