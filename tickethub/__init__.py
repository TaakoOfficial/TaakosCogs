from .tickethub import TicketHub


async def setup(bot):
    cog = TicketHub(bot)
    if bot.get_command("ticket") is not None:
        cog.use_conflict_safe_prefix_root()
    if bot.get_command("ticketset") is not None:
        cog.use_conflict_safe_set_root()
    await bot.add_cog(cog)
