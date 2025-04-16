"""
YALC utility functions.
Helper methods for formatting, validation, and DRY logic.
"""
from redbot.core import commands
import discord
from typing import Any, Optional

# Utility: Format a mention for a user, role, or channel by ID

def mention_from_id(guild: discord.Guild, id_: int, type_: str) -> str:
    """Return a mention string for a user, role, or channel by ID."""
    if type_ == "user":
        member = guild.get_member(id_)
        return member.mention if member else f"<@{id_}>"
    if type_ == "role":
        role = guild.get_role(id_)
        return role.mention if role else f"<@&{id_}>"
    if type_ == "channel":
        channel = guild.get_channel(id_)
        return channel.mention if channel else f"<# {id_}>"
    return str(id_)

# Utility: Validate retention days

def validate_retention_days(days: int) -> bool:
    """Return True if days is between 1 and 365 inclusive."""
    return 1 <= days <= 365

# Utility: Add an embed footer with cog info

def set_embed_footer(embed: discord.Embed, cog: commands.Cog) -> None:
    """Set a standard embed footer for YALC embeds."""
    embed.set_footer(text=f"YALC Logging • {cog.__class__.__name__}")

# Utility: Exception logging

def log_exception(cog: commands.Cog, error: Exception, context: Optional[Any] = None) -> None:
    """Log an exception for debugging."""
    cog.bot.logger.error(f"[YALC] Exception: {error} | Context: {context}")

# Permission and error helpers for DRY logic

def check_manage_guild(member: discord.Member) -> bool:
    """Return True if the member has Manage Server permission."""
    return member.guild_permissions.manage_guild

async def safe_send(interaction_or_ctx, content=None, embed=None, ephemeral=True):
    """Send a message safely, handling both discord.Interaction and commands.Context."""
    try:
        if hasattr(interaction_or_ctx, 'response'):
            if embed:
                await interaction_or_ctx.response.send_message(content=content, embed=embed, ephemeral=ephemeral)
            else:
                await interaction_or_ctx.response.send_message(content=content, ephemeral=ephemeral)
        else:
            await interaction_or_ctx.send(content=content, embed=embed)
    except Exception as e:
        # Optionally log or handle
        pass
