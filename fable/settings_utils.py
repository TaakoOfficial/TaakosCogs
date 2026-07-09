"""Settings management for Fable's visual customization."""
from typing import Dict, Optional
from redbot.core import Config
import discord
import re

class FableSettings:
    """Manages server-specific visual settings for Fable."""

    def __init__(self, config: Config):
        self.config = config
        self.default_theme = {
            "primary_color": 0x7289DA,
            "success_color": 0x43B581,
            "warning_color": 0xFAA61A,
            "error_color": 0xF04747,
            "info_color": 0x4F545C,
            "background_color": 0x2F3136,
            "use_emojis": True,
            "compact_mode": False,
            "show_timestamps": True
        }

    async def get_theme(self, guild_id: int) -> Dict:
        """
        Get the server's theme settings.

        Parameters
        ----------
        guild_id: int
            The Discord guild ID

        Returns
        -------
        Dict
            The server's theme settings
        """
        theme = await self.config.guild_from_id(guild_id).theme()
        return theme or self.default_theme

    async def set_theme_color(
        self,
        guild_id: int,
        color_type: str,
        color_value: str
    ) -> bool:
        """
        Set a theme color for the server.

        Parameters
        ----------
        guild_id: int
            The Discord guild ID
        color_type: str
            The type of color to set
        color_value: str
            The hex color value

        Returns
        -------
        bool
            Whether the color was set successfully
        """
        # Validate hex color
        if not re.match(r'^#(?:[0-9a-fA-F]{3}){1,2}$', color_value):
            return False

        async with self.config.guild_from_id(guild_id).theme() as theme:
            if not theme:
                theme = self.default_theme.copy()
            
            color_int = int(color_value.lstrip('#'), 16)
            color_key = f"{color_type.lower()}_color"
            
            if color_key in theme:
                theme[color_key] = color_int
                return True
            return False

    async def toggle_setting(
        self,
        guild_id: int,
        setting: str
    ) -> Optional[bool]:
        """
        Toggle a boolean theme setting.

        Parameters
        ----------
        guild_id: int
            The Discord guild ID
        setting: str
            The setting to toggle

        Returns
        -------
        Optional[bool]
            The new setting value or None if invalid
        """
        async with self.config.guild_from_id(guild_id).theme() as theme:
            if not theme:
                theme = self.default_theme.copy()
            
            if setting in theme and isinstance(theme[setting], bool):
                theme[setting] = not theme[setting]
                return theme[setting]
            return None

    async def reset_theme(self, guild_id: int) -> None:
        """
        Reset the server's theme to default.

        Parameters
        ----------
        guild_id: int
            The Discord guild ID
        """
        await self.config.guild_from_id(guild_id).theme.set(self.default_theme)

    async def get_embed_style(self, guild_id: int) -> Dict:
        """
        Get the server's embed style preferences.

        Parameters
        ----------
        guild_id: int
            The Discord guild ID

        Returns
        -------
        Dict
            The server's embed style settings
        """
        theme = await self.get_theme(guild_id)
        return {
            "colors": {
                "primary": theme["primary_color"],
                "success": theme["success_color"],
                "warning": theme["warning_color"],
                "error": theme["error_color"],
                "info": theme["info_color"],
                "background": theme["background_color"]
            },
            "use_emojis": theme["use_emojis"],
            "compact_mode": theme["compact_mode"],
            "show_timestamps": theme["show_timestamps"]
        }
