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
            "start_date": None,  # Starting date (YYYY-MM-DD)
            "channel_id": None,  # Channel ID for updates
            "current_date": None,  # Current date in the calendar
            "time_zone": "America/Chicago",  # Default time zone  # Edited by Taako
        }
        self.config.register_guild(**default_guild)
        self._daily_update_loop.start()  # Start the daily update loop

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
            if not current_date:
                continue

            # Increment the current date
            tz = pytz.timezone(time_zone)  # Edited by Taako
            current_date_obj = datetime.strptime(current_date, "%Y-%m-%d").astimezone(tz)  # Edited by Taako
            next_date_obj = current_date_obj + timedelta(days=1)
            next_date_str = next_date_obj.strftime("%Y-%m-%d")
            day_of_week = next_date_obj.strftime("%A")

            # Update the stored current date
            await self.config.guild_from_id(guild_id).current_date.set(next_date_str)

            # Send the update to the channel
            channel = self._bot.get_channel(channel_id)
            if channel:
                await channel.send(f"📅 **RP Calendar Update**\nToday's date: {next_date_str} ({day_of_week})")

    @_daily_update_loop.before_loop
    async def before_daily_update_loop(self):
        """Wait until the bot is ready and align to midnight in the guild's time zone."""  # Edited by Taako
        await self._bot.wait_until_ready()
        now = datetime.now(pytz.timezone("America/Chicago"))  # Default to America/Chicago  # Edited by Taako
        next_midnight = (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
        await discord.utils.sleep_until(next_midnight)

    @rpcalander.command(name="settimezone")
    async def set_timezone(self, ctx, time_zone: str):
        """Set the time zone for the RP calendar."""  # Edited by Taako
        if time_zone not in pytz.all_timezones:
            await ctx.send("Invalid time zone. Please provide a valid time zone (e.g., `America/New_York`).")
            return
        await self.config.guild(ctx.guild).time_zone.set(time_zone)
        await ctx.send(f"Time zone set to {time_zone}.")

    @rpcalander.command(name="info")
    async def info(self, ctx):
        """View the current settings for the RP calendar."""  # Edited by Taako
        guild_settings = await self.config.guild(ctx.guild).all()
        start_date = guild_settings["start_date"] or "Not set"
        current_date = guild_settings["current_date"] or "Not set"
        channel_id = guild_settings["channel_id"]
        channel = f"<#{channel_id}>" if channel_id else "Not set"
        time_zone = guild_settings["time_zone"] or "America/Chicago"  # Edited by Taako

        embed = discord.Embed(
            title="📅 RP Calendar Settings",
            color=discord.Color.blue()
        )
        embed.add_field(name="Start Date", value=start_date, inline=False)
        embed.add_field(name="Current Date", value=current_date, inline=False)
        embed.add_field(name="Update Channel", value=channel, inline=False)
        embed.add_field(name="Time Zone", value=time_zone, inline=False)  # Edited by Taako
        await ctx.send(embed=embed)
