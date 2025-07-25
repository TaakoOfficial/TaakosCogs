"""Dicey Cog - Provides random chance commands like coin flip and dice roll."""

import random
from redbot.core import commands, checks

class Dicey(commands.Cog):
    """Random chance utilities."""

    @commands.hybrid_command()
    async def coinflip(self, ctx):
        """Flip a coin."""
        result = random.choice(["Heads", "Tails"])
        await ctx.send(f":coin: {result}")

    @commands.hybrid_command()
    async def roll(self, ctx, sides: int = 6):
        """Roll a dice with a given number of sides (default 6)."""
        if sides < 1:
            await ctx.send("Number of sides must be at least 1.")
            return
        result = random.randint(1, sides)
        await ctx.send(f":game_die: You rolled a {result} (1-{sides})")

def setup(bot):
    bot.add_cog(Dicey())