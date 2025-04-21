"""Character profile module for Fable."""
from typing import Optional
import discord
from redbot.core import commands
from .style_utils import FableEmbed

class CharacterProfile(commands.Cog):
    """Handles character profile management in Fable."""

    def __init__(self, bot):
        self.bot = bot

    @commands.hybrid_command(name="profile", description="View a character's profile")
    @commands.guild_only()
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def view_profile(
        self,
        ctx: commands.Context,
        character_name: str
    ) -> None:
        """
        View a character's profile with rich formatting.

        Parameters
        ----------
        ctx: commands.Context
            The command context
        character_name: str
            The name of the character to view
        """
        # Example character data - would come from Config in real implementation
        character_data = {
            "name": character_name,
            "description": "An elven spy from the mystical Silverwood, known for her cunning.",
            "image_url": "https://example.com/character.png",
            "fields": [
                {
                    "name": "Basic Information",
                    "icon": "character",
                    "value": "**Species:** High Elf\n**Age:** 247\n**Role:** Spy",
                    "inline": True
                },
                {
                    "name": "Current Status",
                    "icon": "progress",
                    "value": "**Location:** Silverwood\n**Mission:** Active\n**Condition:** Healthy",
                    "inline": True
                },
                {
                    "name": "Recent Milestone",
                    "icon": "milestone",
                    "value": "Completed advanced magical training",
                    "inline": False
                }
            ]
        }

        embed = await FableEmbed.character_embed(
            ctx,
            character_data["name"],
            character_data["description"],
            character_data["image_url"],
            character_data["fields"]
        )

        await ctx.send(embed=embed)

    @commands.hybrid_command(name="location", description="View a location's details")
    @commands.guild_only()
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def view_location(
        self,
        ctx: commands.Context,
        location_name: str
    ) -> None:
        """
        View a location's details with themed formatting.

        Parameters
        ----------
        ctx: commands.Context
            The command context
        location_name: str
            The name of the location to view
        """
        # Example location data - would come from Config in real implementation
        location_data = {
            "name": location_name,
            "type": "castle",
            "description": "An ancient fortress overlooking the misty valley.",
            "image_url": "https://example.com/castle.png",
            "fields": [
                {
                    "name": "Notable Features",
                    "icon": "landmark",
                    "value": "- Ancient library\n- Magical barriers\n- Hidden passages",
                    "inline": True
                },
                {
                    "name": "Current Visitors",
                    "icon": "character",
                    "value": "- Aria (Studying)\n- Elder Moonshadow (Teaching)",
                    "inline": True
                }
            ]
        }

        embed = await FableEmbed.location_embed(
            location_data["type"],
            location_data["name"],
            location_data["description"],
            location_data["image_url"],
            location_data["fields"]
        )

        await ctx.send(embed=embed)
