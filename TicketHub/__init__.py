from .tickethub import TicketHub


async def setup(bot):
    await bot.add_cog(TicketHub(bot))
