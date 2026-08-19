from .decisionledger import DecisionLedger


async def setup(bot):
    await bot.add_cog(DecisionLedger(bot))
