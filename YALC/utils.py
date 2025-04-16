"""
YALC utility functions.

This module contains helper functions used across YALC's commands and listeners.
All functions include proper type hints and error handling.
"""
from redbot.core import commands
import discord
from typing import Optional, Union, List, Dict, cast
import datetime

def set_embed_footer(embed: discord.Embed, cog: commands.Cog) -> None:
    """Set consistent footer for YALC embeds.
    
    Parameters
    ----------
    embed: discord.Embed
        The embed to set the footer on
    cog: commands.Cog
        The YALC cog instance for version info
    """
    embed.set_footer(text=f"YALC v{cog.__version__}")

async def check_manage_guild(ctx: Union[commands.Context, discord.Interaction]) -> bool:
    """Check if user has manage guild permission.
    
    Parameters
    ----------
    ctx: Union[commands.Context, discord.Interaction]
        The context or interaction to check permissions for
        
    Returns
    -------
    bool
        True if user has permission, False otherwise
    
    Raises
    ------
    commands.CheckFailure
        If the user lacks required permissions
    """
    if isinstance(ctx, discord.Interaction):
        if not ctx.guild or not ctx.user:
            return False
        member = cast(discord.Member, ctx.user)
        return member.guild_permissions.manage_guild
    return ctx.author.guild_permissions.manage_guild

def validate_retention_days(days: int) -> bool:
    """Validate log retention period is within acceptable range.
    
    Parameters
    ----------
    days: int
        Number of days to validate
        
    Returns
    -------
    bool
        True if days is within valid range (1-365)
    """
    return 1 <= days <= 365

async def safe_send(
    channel: discord.TextChannel,
    content: Optional[str] = None,
    *,
    embed: Optional[discord.Embed] = None,
    **kwargs
) -> Optional[discord.Message]:
    """Safely send a message to a channel with error handling.
    
    Parameters
    ----------
    channel: discord.TextChannel
        The channel to send the message to
    content: Optional[str]
        The message content to send
    embed: Optional[discord.Embed]
        The embed to send
    **kwargs
        Additional kwargs to pass to send()
        
    Returns
    -------
    Optional[discord.Message]
        The sent message if successful, None otherwise
    """
    try:
        return await channel.send(content=content, embed=embed, **kwargs)
    except (discord.Forbidden, discord.HTTPException):
        return None
