from redbot.core import commands

from .rpcalander import RPCalander


async def setup(bot: commands.Bot):
    cog = RPCalander(bot)
    await bot.add_cog(cog)
    # Register the grouped slash commands
    if hasattr(cog, "rpca_group"):
        bot.tree.add_command(cog.rpca_group)
