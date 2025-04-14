from .rpcalander import RPCalander  # Edited by Taako

async def setup(bot):
    await bot.add_cog(RPCalander(bot))  # Edited by Taako
