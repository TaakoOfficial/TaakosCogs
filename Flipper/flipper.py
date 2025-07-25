"""Flipper Cog - Provides a coin flip command."""

import random
import discord
from redbot.core import commands

class Flipper(commands.Cog):
    """Coin flip utility."""

    @commands.hybrid_command()
    async def coinflip(self, ctx):
        """Flip a coin."""
        result = random.choice(["Heads", "Tails"])
        color = discord.Color.gold() if result == "Heads" else discord.Color.blue()
        embed = discord.Embed(
            title="🪙 Coin Flip",
            description=f"**Result:** :coin: {result}",
            color=color
        )
        embed.set_footer(text="Flipper • Coin Toss")
        await ctx.send(embed=embed)