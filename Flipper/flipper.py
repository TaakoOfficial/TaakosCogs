"""Flipper Cog - Provides a coin flip command."""

import random
from redbot.core import commands

class Flipper(commands.Cog):
    """Coin flip utility."""

    @commands.hybrid_command()
    async def coinflip(self, ctx):
        """Flip a coin."""
        result = random.choice(["Heads", "Tails"])
        await ctx.send(f":coin: {result}")