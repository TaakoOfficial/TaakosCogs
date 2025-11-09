"""WHMCS COG for Red-Bot - WHMCS Integration Package."""

from .whmcs import WHMCS

__red_end_user_data_statement__ = (
    "This cog stores WHMCS API credentials and configuration data. "
    "No end user data is persistently stored beyond what is necessary for WHMCS integration."
)


async def setup(bot):
    """Load the WHMCS cog."""
    await bot.add_cog(WHMCS(bot))