from .rpcalander import RPCalander  # Edited by Taako

async def setup(bot):
    cog = RPCalander(bot)  # Create instance first  # Edited by Taako
    await bot.add_cog(cog)  # Add the cog instance  # Edited by Taako
