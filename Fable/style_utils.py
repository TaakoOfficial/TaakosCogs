"""Utility module for managing visual styles and embeds in Fable."""
from typing import Dict, List, Optional, Union, Any
import discord
from redbot.core import commands

class FableEmbed:
    """Manages consistent embed styling across Fable features."""

    COLORS = {
        "PRIMARY": 0x7289DA,    # Discord Blurple - Main brand color
        "SUCCESS": 0x43B581,    # Green - Positive actions/success
        "WARNING": 0xFAA61A,    # Yellow - Warnings/cautions
        "ERROR": 0xF04747,      # Red - Errors/failures
        "INFO": 0x4F545C,       # Gray - Neutral information
        "BACKGROUND": 0x2F3136  # Dark - Background/secondary
    }

    LOCATION_COLORS = {
        "tavern": 0xC19A6B,
        "castle": 0x808080,
        "house": 0x43B581,
        "shop": 0xFAA61A,
        "dungeon": 0xF04747,
        "other": 0x7289DA
    }

    ICONS = {
        # Character Icons
        "character": "🎭",
        "milestone": "🎯",
        "achievement": "✨",
        "story": "📖",
        "progress": "📈",
        
        # Relationship Icons
        "relationship": "👥",
        "ally": "💚",
        "rival": "❤️",
        "family": "💙",
        "neutral": "⚪",
        "custom": "🟣",
        
        # Location Icons
        "location": "🗺️",
        "castle": "🏰",
        "tavern": "🍺",
        "house": "🏠",
        "shop": "🏪",
        "dungeon": "⚔️",
        "landmark": "🗿",
        
        # Timeline Icons
        "timeline": "📅",
        "event": "📝",
        "visit": "📍"
    }

    @classmethod
    async def character_embed(
        cls,
        ctx: commands.Context,
        name: str,
        description: str,
        thumbnail_url: Optional[str] = None,
        fields: Optional[List[Dict[str, Any]]] = None
    ) -> discord.Embed:
        """Generate a character profile embed."""
        embed = discord.Embed(
            title=f"{cls.ICONS['character']} {name}",
            description=description,
            color=cls.COLORS["PRIMARY"]
        )

        if thumbnail_url:
            embed.set_thumbnail(url=thumbnail_url)

        if fields:
            for field in fields:
                icon = cls.ICONS.get(field.get("icon", ""), "")
                name = f"{icon} {field['name']}" if icon else field["name"]
                embed.add_field(
                    name=name,
                    value=field["value"],
                    inline=field.get("inline", False)
                )

        embed.set_footer(text=f"Profile • {discord.utils.utcnow().strftime('%Y-%m-%d %H:%M UTC')}")
        return embed

    @classmethod
    async def location_embed(
        cls,
        location_type: str,
        name: str,
        description: str,
        image_url: Optional[str] = None,
        fields: Optional[List[Dict[str, Any]]] = None
    ) -> discord.Embed:
        """Generate a location card embed."""
        color = cls.LOCATION_COLORS.get(location_type.lower(), cls.LOCATION_COLORS["other"])
        icon = cls.ICONS.get(location_type.lower(), cls.ICONS["location"])
        
        embed = discord.Embed(
            title=f"{icon} {name}",
            description=description,
            color=color
        )

        if image_url:
            embed.set_image(url=image_url)

        if fields:
            for field in fields:
                icon = cls.ICONS.get(field.get("icon", ""), "")
                name = f"{icon} {field['name']}" if icon else field["name"]
                embed.add_field(
                    name=name,
                    value=field["value"],
                    inline=field.get("inline", False)
                )

        embed.set_footer(text=f"Location • {discord.utils.utcnow().strftime('%Y-%m-%d %H:%M UTC')}")
        return embed

    @classmethod
    async def timeline_embed(
        cls,
        title: str,
        description: str,
        events: List[Dict[str, Any]]
    ) -> discord.Embed:
        """Generate a timeline view embed."""
        embed = discord.Embed(
            title=f"{cls.ICONS['timeline']} {title}",
            description=description,
            color=cls.COLORS["PRIMARY"]
        )

        for event in events:
            icon = cls.ICONS.get(event["type"], cls.ICONS["event"])
            name = f"{icon} {event['date']}"
            embed.add_field(
                name=name,
                value=event["description"],
                inline=False
            )

        embed.set_footer(text=f"Timeline • {discord.utils.utcnow().strftime('%Y-%m-%d %H:%M UTC')}")
        return embed

    @classmethod
    async def relationship_embed(
        cls,
        name: str,
        description: str,
        relationships: List[Dict[str, Any]]
    ) -> discord.Embed:
        """Generate a relationship display embed."""
        embed = discord.Embed(
            title=f"{cls.ICONS['relationship']} {name}'s Relationships",
            description=description,
            color=cls.COLORS["PRIMARY"]
        )

        for rel in relationships:
            rel_type = rel["type"].lower()
            intensity = rel.get("intensity", 0)
            icon = cls.ICONS.get(rel_type, cls.ICONS["custom"])
            stars = "⭐" * intensity if intensity > 0 else ""
            
            embed.add_field(
                name=f"{icon} {rel['name']} {stars}",
                value=rel["description"],
                inline=False
            )

        embed.set_footer(text=f"Relationships • {discord.utils.utcnow().strftime('%Y-%m-%d %H:%M UTC')}")
        return embed

    @classmethod
    async def status_embed(
        cls,
        title: str,
        description: str,
        status: str = "info"
    ) -> discord.Embed:
        """Generate a status message embed."""
        status = status.upper()
        embed = discord.Embed(
            title=title,
            description=description,
            color=cls.COLORS.get(status, cls.COLORS["INFO"])
        )

        embed.set_footer(text=f"Status • {discord.utils.utcnow().strftime('%Y-%m-%d %H:%M UTC')}")
        return embed

class FableView(discord.ui.View):
    """Base view for Fable's interactive components."""

    def __init__(self, timeout: int = 60):
        super().__init__(timeout=timeout)

class ConfirmView(FableView):
    """Standard confirmation view with approve/deny buttons."""

    def __init__(self, ctx: commands.Context, timeout: int = 60):
        super().__init__(timeout=timeout)
        self.ctx = ctx
        self.value = None

    @discord.ui.button(label="Confirm", style=discord.ButtonStyle.green)
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Handle confirmation button click."""
        if interaction.user.id != self.ctx.author.id:
            await interaction.response.send_message("This button isn't for you!", ephemeral=True)
            return

        self.value = True
        await interaction.response.edit_message(
            embed=await FableEmbed.status_embed(
                "Action Confirmed",
                "Your changes have been saved.",
                "SUCCESS"
            ),
            view=None
        )
        self.stop()

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.red)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Handle cancellation button click."""
        if interaction.user.id != self.ctx.author.id:
            await interaction.response.send_message("This button isn't for you!", ephemeral=True)
            return

        self.value = False
        await interaction.response.edit_message(
            embed=await FableEmbed.status_embed(
                "Action Cancelled",
                "No changes were made.",
                "ERROR"
            ),
            view=None
        )
        self.stop()

class PaginationView(FableView):
    """View for paginated content navigation."""

    def __init__(
        self,
        ctx: commands.Context,
        pages: List[discord.Embed],
        timeout: int = 180
    ):
        super().__init__(timeout=timeout)
        self.ctx = ctx
        self.pages = pages
        self.current_page = 0

    @discord.ui.button(label="◀️", style=discord.ButtonStyle.blurple)
    async def previous_page(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Handle previous page button click."""
        if interaction.user.id != self.ctx.author.id:
            await interaction.response.send_message("This button isn't for you!", ephemeral=True)
            return

        self.current_page = (self.current_page - 1) % len(self.pages)
        await interaction.response.edit_message(embed=self.pages[self.current_page])

    @discord.ui.button(label="▶️", style=discord.ButtonStyle.blurple)
    async def next_page(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Handle next page button click."""
        if interaction.user.id != self.ctx.author.id:
            await interaction.response.send_message("This button isn't for you!", ephemeral=True)
            return

        self.current_page = (self.current_page + 1) % len(self.pages)
        await interaction.response.edit_message(embed=self.pages[self.current_page])
