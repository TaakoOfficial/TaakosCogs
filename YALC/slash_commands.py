"""
Yet Another Logging Cog (YALC) Slash Commands for Redbot.

This module contains all slash command implementations for YALC.
Commands are organized in a group structure for better organization.
"""
from redbot.core import app_commands, commands
import discord
from typing import Optional, Dict, List, cast
from .utils import (
    set_embed_footer,
    check_manage_guild,
    validate_retention_days,
    safe_send
)

class YALCSlashGroup(app_commands.Group):
    """Slash command group for YALC logging configuration.
    
    This class implements all slash commands for YALC, organized in a
    command group structure. All commands use proper permission checking
    and error handling.
    """

    def __init__(self, cog: commands.Cog):
        """Initialize the YALC slash command group.
        
        Parameters
        ----------
        cog: commands.Cog
            The YALC cog instance that owns this command group.
        """
        super().__init__(name="yalc", description="YALC logging configuration commands.")
        self.cog = cog

    @app_commands.command(name="info", description="Show enabled events and their log channels.")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def info(self, interaction: discord.Interaction) -> None:
        """Show enabled log events and their channels.
        
        This command displays all configured log events and their
        associated channels in a clean embed format.
        
        Parameters
        ----------
        interaction: discord.Interaction
            The interaction that triggered this command.
        """
        if not interaction.guild or not interaction.user:
            await interaction.response.send_message("❌ This command can only be used in a server.", ephemeral=True)
            return
        try:
            settings = await self.cog.config.guild(interaction.guild).all()
            log_events = settings["log_events"]
            event_channels = settings["event_channels"]
            log_channel_id = settings["log_channel"]
            log_channel = interaction.guild.get_channel(log_channel_id) if log_channel_id else None
            lines = []
            for event, enabled in log_events.items():
                channel_id = event_channels.get(event, log_channel_id)
                channel = interaction.guild.get_channel(channel_id) if channel_id else None
                emoji = "✅" if enabled else "❌"
                channel_str = channel.mention if channel else "*Not set*"
                lines.append(f"{emoji} `{event}` → {channel_str}")
            embed = discord.Embed(
                title="📝 YALC Logging Status",
                description="\n".join(lines) or "No events configured.",
                color=discord.Color.blurple()
            )
            set_embed_footer(embed, self.cog)
            await interaction.response.send_message(embed=embed, ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"❌ Error: {e}", ephemeral=True)

    @app_commands.command(name="listevents", description="List all available log event types.")
    async def listevents(self, interaction: discord.Interaction) -> None:
        """List all available log event types.
        
        This command provides a list of all log event types that can be
        configured for logging in the server.
        
        Parameters
        ----------
        interaction: discord.Interaction
            The interaction that triggered this command.
        """
        if not interaction.guild or not interaction.user:
            await interaction.response.send_message("❌ This command can only be used in a server.", ephemeral=True)
            return
        try:
            event_types = list((await self.cog.config.guild(interaction.guild).log_events()).keys())
            embed = discord.Embed(
                title="Available Log Event Types",
                description="\n".join(f"`{e}`" for e in event_types),
                color=discord.Color.blurple()
            )
            set_embed_footer(embed, self.cog)
            await interaction.response.send_message(embed=embed, ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"❌ Error: {e}", ephemeral=True)

    @app_commands.command(name="retention", description="Show the current log retention period.")
    async def retention(self, interaction: discord.Interaction) -> None:
        """Show the current log retention period.
        
        This command displays the number of days that logs are retained
        before being deleted.
        
        Parameters
        ----------
        interaction: discord.Interaction
            The interaction that triggered this command.
        """
        if not interaction.guild or not interaction.user:
            await interaction.response.send_message("❌ This command can only be used in a server.", ephemeral=True)
            return
        try:
            days = await self.cog.config.guild(interaction.guild).get_raw("retention_days", default=30)
            await interaction.response.send_message(f"Current log retention: {days} days.", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"❌ Error: {e}", ephemeral=True)

    @app_commands.command(name="setretention", description="Set the log retention period in days (1-365).")
    async def setretention(self, interaction: discord.Interaction, days: int) -> None:
        """Set the log retention period in days.
        
        This command allows you to configure how many days logs are kept
        before they are automatically deleted by the bot.
        
        Parameters
        ----------
        interaction: discord.Interaction
            The interaction that triggered this command.
        days: int
            The number of days to retain logs for. Must be between 1 and 365.
        """
        if not interaction.guild or not interaction.user:
            await interaction.response.send_message("❌ This command can only be used in a server.", ephemeral=True)
            return
        member = interaction.guild.get_member(interaction.user.id)
        if not member or not check_manage_guild(member):
            await interaction.response.send_message("❌ You need Manage Server permission!", ephemeral=True)
            return
        if not validate_retention_days(days):
            await interaction.response.send_message("❌ Please provide a value between 1 and 365 days.", ephemeral=True)
            return
        try:
            await self.cog.config.guild(interaction.guild).set_raw("retention_days", value=days)
            await interaction.response.send_message(f"✅ Log retention set to {days} days.", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"❌ Error: {e}", ephemeral=True)

    @app_commands.command(name="ignores", description="List all ignored users, roles, and channels.")
    async def ignores(self, interaction: discord.Interaction) -> None:
        """List all ignored users, roles, and channels.
        
        This command provides a list of all users, roles, and channels
        that are currently being ignored by the logging system.
        
        Parameters
        ----------
        interaction: discord.Interaction
            The interaction that triggered this command.
        """
        if not interaction.guild or not interaction.user:
            await interaction.response.send_message("❌ This command can only be used in a server.", ephemeral=True)
            return
        try:
            users = await self.cog.config.guild(interaction.guild).get_raw("ignored_users", default=[])
            roles = await self.cog.config.guild(interaction.guild).get_raw("ignored_roles", default=[])
            channels = await self.cog.config.guild(interaction.guild).get_raw("ignored_channels", default=[])
            user_mentions = [f"<@{uid}>" for uid in users]
            role_mentions = [f"<@&{rid}>" for rid in roles]
            channel_mentions = [f"<# {cid}>" for cid in channels]
            embed = discord.Embed(
                title="YALC Ignore Lists",
                color=discord.Color.blurple()
            )
            embed.add_field(
                name="users", value=", ".join(user_mentions) or "None", inline=False
            )
            embed.add_field(
                name="roles", value=", ".join(role_mentions) or "None", inline=False
            )
            embed.add_field(
                name="channels", value=", ".join(channel_mentions) or "None", inline=False
            )
            set_embed_footer(embed, self.cog)
            await interaction.response.send_message(embed=embed, ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"❌ Error: {e}", ephemeral=True)

    @app_commands.command(name="filters", description="List all filters for an event.")
    async def filters(self, interaction: discord.Interaction, event: str) -> None:
        """List all filters for a log event.
        
        This command shows all filters that have been applied to a
        specific log event, which determine what gets logged for that
        event.
        
        Parameters
        ----------
        interaction: discord.Interaction
            The interaction that triggered this command.
        event: str
            The name of the log event to list filters for.
        """
        if not interaction.guild or not interaction.user:
            await interaction.response.send_message("❌ This command can only be used in a server.", ephemeral=True)
            return
        try:
            valid_events = list((await self.cog.config.guild(interaction.guild).log_events()).keys())
            if event not in valid_events:
                await interaction.response.send_message(
                    f"❌ Invalid event type. Valid events: {', '.join(valid_events)}",
                    ephemeral=True,
                )
                return
            filters = await self.cog.config.guild(interaction.guild).get_raw(f"filters_{event}", default=[])
            embed = discord.Embed(
                title=f"Filters for {event}",
                description="\n".join(filters) or "No filters set.",
                color=discord.Color.blurple()
            )
            set_embed_footer(embed, self.cog)
            await interaction.response.send_message(embed=embed, ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"❌ Error: {e}", ephemeral=True)
