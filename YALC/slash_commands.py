"""
YALC Slash Commands for Redbot.
"""
from redbot.core import app_commands, commands
import discord
from .utils import set_embed_footer

class YALCSlashGroup(app_commands.Group):
    """Slash command group for YALC logging configuration."""
    def __init__(self, cog: commands.Cog):
        super().__init__(name="yalc", description="YALC logging commands.")
        self.cog = cog

    @app_commands.command(name="info", description="Show enabled events and their log channels.")
    async def info(self, interaction: discord.Interaction) -> None:
        if not interaction.guild or not interaction.user:
            await interaction.response.send_message("This command can only be used in a server.", ephemeral=True)
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
            await interaction.response.send_message(f"Error: {e}", ephemeral=True)

    @app_commands.command(name="listevents", description="List all available log event types.")
    async def listevents(self, interaction: discord.Interaction) -> None:
        if not interaction.guild or not interaction.user:
            await interaction.response.send_message("This command can only be used in a server.", ephemeral=True)
            return
        try:
            event_types = list((await self.cog.config.guild(interaction.guild).log_events()).keys())
            embed = discord.Embed(
                title="Available Log Event Types",
                description="\n".join(f"`{e}`" for e in event_types),
                color=discord.Color.blurple()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"Error: {e}", ephemeral=True)

    @app_commands.command(name="retention", description="Show the current log retention period.")
    async def retention(self, interaction: discord.Interaction) -> None:
        if not interaction.guild or not interaction.user:
            await interaction.response.send_message("This command can only be used in a server.", ephemeral=True)
            return
        try:
            days = await self.cog.config.guild(interaction.guild).get_raw("retention_days", default=30)
            await interaction.response.send_message(f"Current log retention: {days} days.", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"Error: {e}", ephemeral=True)

    @app_commands.command(name="setretention", description="Set the log retention period in days (1-365).")
    async def setretention(self, interaction: discord.Interaction, days: int) -> None:
        if not interaction.guild or not interaction.user:
            await interaction.response.send_message("This command can only be used in a server.", ephemeral=True)
            return
        member = interaction.guild.get_member(interaction.user.id)
        from .utils import check_manage_guild, validate_retention_days
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
            await interaction.response.send_message(f"Error: {e}", ephemeral=True)

    @app_commands.command(name="ignores", description="List all ignored users, roles, and channels.")
    async def ignores(self, interaction: discord.Interaction) -> None:
        if not interaction.guild or not interaction.user:
            await interaction.response.send_message("This command can only be used in a server.", ephemeral=True)
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
                name="Users", value=", ".join(user_mentions) or "None", inline=False
            )
            embed.add_field(
                name="Roles", value=", ".join(role_mentions) or "None", inline=False
            )
            embed.add_field(
                name="Channels", value=", ".join(channel_mentions) or "None", inline=False
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"Error: {e}", ephemeral=True)

    @app_commands.command(name="filters", description="List all filters for an event.")
    async def filters(self, interaction: discord.Interaction, event: str) -> None:
        if not interaction.guild or not interaction.user:
            await interaction.response.send_message("This command can only be used in a server.", ephemeral=True)
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
            await interaction.response.send_message(embed=embed, ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"Error: {e}", ephemeral=True)
```
