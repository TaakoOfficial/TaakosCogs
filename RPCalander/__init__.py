from .rpcalander import rpcalander  # Edited by Taako

async def setup(bot):
    await bot.add_cog(rpcalander(bot))  # Edited by Taako
