import discord  # Edited by Taako
from redbot.core import commands, Config  # Edited by Taako
from datetime import datetime, timedelta  # Edited by Taako
import pytz  # Edited by Taako
from discord.ext import tasks  # Edited by Taako

class RPCalander(commands.Cog):
    """A cog for managing an RP calendar with daily updates."""  # Edited by Taako

    def __init__(self, bot):
        self._bot = bot  # Edited by Taako
        self.config = Config.get_conf(self, identifier=9876543210, force_registration=True)  # Edited by Taako
        default_guild = {
            "start_date": None,  # Starting date (MM-DD-YYYY)  # Edited by Taako
            "channel_id": None,  # Channel ID for updates
            "current_date": None,  # Current date in the calendar
            "time_zone": "America/Chicago",  # Default time zone  # Edited by Taako
            "embed_color": 0x0000FF,  # Default embed color (blue)  # Edited by Taako
            "show_footer": True,  # Whether to show the footer in the main embed  # Edited by Taako
            "embed_title": "📅 RP Calendar Update",  # Default embed title  # Edited by Taako
        }
        self.config.register_guild(**default_guild)
        self._daily_update_loop.start()  # Start the daily update loop

    async def cog_load(self):
        """Restart the daily update loop and check for missed dates when the cog is loaded."""  # Edited by Taako
        if not self._daily_update_loop.is_running():
            self._daily_update_loop.start()  # Restart the loop if not running  # Edited by Taako

        # Check for missed dates
        all_guilds = await self.config.all_guilds()
        for guild_id, guild_settings in all_guilds.items():
            current_date = guild_settings["current_date"]
            if not current_date:
                continue

            time_zone = guild_settings["time_zone"] or "America/Chicago"  # Edited by Taako
            tz = pytz.timezone(time_zone)  # Edited by Taako
            current_date_obj = datetime.strptime(current_date, "%m-%d-%Y").astimezone(tz)  # Edited by Taako
            today_date_obj = datetime.now(tz).replace(hour=0, minute=0, second=0, microsecond=0)  # Edited by Taako

            # If the bot was offline for multiple days, update the date
            if today_date_obj > current_date_obj:
                days_missed = (today_date_obj - current_date_obj).days
                new_date_obj = current_date_obj + timedelta(days=days_missed)
                await self.config.guild_from_id(guild_id).current_date.set(new_date_obj.strftime("%m-%d-%Y"))  # Edited by Taako

    @tasks.loop(hours=24)
    async def _daily_update_loop(self):
        """Task loop to post daily calendar updates."""  # Edited by Taako
        all_guilds = await self.config.all_guilds()
        for guild_id, guild_settings in all_guilds.items():
            channel_id = guild_settings["channel_id"]
            if not channel_id:
                continue

            current_date = guild_settings["current_date"]
            time_zone = guild_settings["time_zone"] or "America/Chicago"  # Edited by Taako
            embed_color = guild_settings["embed_color"] or 0x0000FF  # Default to blue  # Edited by Taako
            embed_title = guild_settings["embed_title"] or "📅 RP Calendar Update"  # Edited by Taako
            show_footer = guild_settings["show_footer"]  # Edited by Taako
            if not current_date:
                continue

            # Increment the current date
            tz = pytz.timezone(time_zone)  # Edited by Taako
            current_date_obj = datetime.strptime(current_date, "%m-%d-%Y").astimezone(tz)  # Edited by Taako
            next_date_obj = current_date_obj + timedelta(days=1)
            next_date_str = next_date_obj.strftime("%A %m-%d-%Y")  # Edited by Taako

            # Update the stored current date
            await self.config.guild_from_id(guild_id).current_date.set(next_date_obj.strftime("%m-%d-%Y"))  # Edited by Taako

            # Create and send the embed
            embed = discord.Embed(
                title=embed_title,  # Use the configured embed title  # Edited by Taako
                description=f"Today's date: **{next_date_str}**",
                color=discord.Color(embed_color)  # Use the configured embed color  # Edited by Taako
            )
            if show_footer:  # Add footer if enabled  # Edited by Taako
                embed.set_footer(text="RP Calendar by Taako", icon_url="https://cdn-icons-png.flaticon.com/512/869/869869.png")
            channel = self._bot.get_channel(channel_id)
            if channel:
                await channel.send(embed=embed)

    @commands.group(name="rpcalander", invoke_without_command=True)
    async def rpcalander(self, ctx):
        """Main command group for the RP Calendar cog."""  # Edited by Taako
        if ctx.invoked_subcommand is None:
            await ctx.send_help(ctx.command)  # Show help if no subcommand is invoked

    @rpcalander.command(name="settitle")
    async def set_title(self, ctx, *, title: str):
        """Set a custom title for the main embed."""  # Edited by Taako
        await self.config.guild(ctx.guild).embed_title.set(title)
        await ctx.send(f"Embed title set to: {title}")  # Edited by Taako

    @rpcalander.command(name="info")
    async def info(self, ctx):
        """View the current settings for the RP calendar."""  # Edited by Taako
        guild_settings = await self.config.guild(ctx.guild).all()
        start_date = guild_settings["start_date"] or "Not set"
        current_date = guild_settings["current_date"] or "Not set"
        channel_id = guild_settings["channel_id"]
        channel = f"<#{channel_id}>" if channel_id else "Not set"
        time_zone = guild_settings["time_zone"] or "America/Chicago"  # Edited by Taako
        embed_color = discord.Color(guild_settings["embed_color"])  # Edited by Taako
        embed_title = guild_settings["embed_title"] or "📅 RP Calendar Update"  # Edited by Taako

        embed = discord.Embed(
            title="📅 RP Calendar Settings",
            color=embed_color  # Use the configured embed color  # Edited by Taako
        )
        embed.add_field(name="Start Date", value=start_date, inline=False)
        embed.add_field(name="Current Date", value=current_date, inline=False)
        embed.add_field(name="Update Channel", value=channel, inline=False)
        embed.add_field(name="Time Zone", value=time_zone, inline=False)
        embed.add_field(name="Embed Color", value=str(embed_color), inline=False)  # Edited by Taako
        embed.add_field(name="Embed Title", value=embed_title, inline=False)  # Edited by Taako
        embed.set_footer(text="RP Calendar by Taako", icon_url="https://cdn-icons-png.flaticon.com/512/869/869869.png")  # Always show footer in info embed  # Edited by Taako
        await ctx.send(embed=embed)

    def cog_unload(self):
        """Clean up tasks and unregister commands when the cog is unloaded."""  # Edited by Taako
        self._daily_update_loop.cancel()  # Stop the daily update loop  # Edited by Taako
