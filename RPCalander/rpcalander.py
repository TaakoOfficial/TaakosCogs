import discord  # Edited by Taako
from redbot.core import commands, Config  # Edited by Taako
from datetime import datetime, timedelta  # Edited by Taako
import pytz  # Edited by Taako
from discord.ext import tasks  # Edited by Taako

class RPCalander(commands.Cog):
    """A cog for managing an RP calendar with daily updates."""  # Edited by Taako

    def __init__(self, bot):
        self._bot = bot  # Edited by Taako
        self._config = Config.get_conf(self, identifier=9876543210, force_registration=True)  # Edited by Taako
        self._default_guild = {
            "start_date": None,  # Format: MM-DD-YYYY  # Edited by Taako
            "current_date": None,  # Current tracked date  # Edited by Taako
            "channel_id": None,  # Channel for updates  # Edited by Taako
            "time_zone": "America/Chicago",  # Default timezone  # Edited by Taako
            "embed_color": 0x0000FF,  # Default color (blue)  # Edited by Taako
            "show_footer": True,  # Show footer in embeds  # Edited by Taako
            "embed_title": "📅 RP Calendar Update",  # Default title  # Edited by Taako
            "last_posted": None  # Store the last posted time  # Edited by Taako
        }
        self._config.register_guild(**self._default_guild)  # Edited by Taako

    async def cog_load(self):
        """Start the daily update loop without triggering an immediate post."""  # Edited by Taako
        if not self._daily_update_loop.is_running():
            self._daily_update_loop.start()  # Start the loop without sending an embed  # Edited by Taako

        # Check for missed dates without sending an embed  # Edited by Taako
        all_guilds = await self._config.all_guilds()  # Edited by Taako
        for guild_id, guild_settings in all_guilds.items():
            current_date = guild_settings["current_date"]  # Edited by Taako
            if not current_date:
                continue

            time_zone = guild_settings["time_zone"] or "America/Chicago"  # Edited by Taako
            tz = pytz.timezone(time_zone)  # Edited by Taako
            current_date_obj = datetime.strptime(current_date, "%m-%d-%Y").astimezone(tz)  # Edited by Taako
            today_date_obj = datetime.now(tz).replace(hour=0, minute=0, second=0, microsecond=0)  # Edited by Taako

            # If the bot was offline for multiple days, update the date  # Edited by Taako
            if today_date_obj > current_date_obj:
                days_missed = (today_date_obj - current_date_obj).days  # Edited by Taako
                new_date_obj = current_date_obj + timedelta(days=days_missed)  # Edited by Taako
                await self._config.guild_from_id(guild_id).current_date.set(new_date_obj.strftime("%m-%d-%Y"))  # Edited by Taako

    @tasks.loop(hours=24)
    async def _daily_update_loop(self):
        """Task loop to post daily calendar updates."""  # Edited by Taako
        all_guilds = await self._config.all_guilds()
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
            await self._config.guild_from_id(guild_id).current_date.set(next_date_obj.strftime("%m-%d-%Y"))  # Edited by Taako

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

    @commands.group(name="rpca")
    @commands.admin_or_permissions(administrator=True)  # Add permission check  # Edited by Taako
    async def rpca(self, ctx):
        """Calendar management commands. Requires administrator permissions."""  # Edited by Taako
        if ctx.invoked_subcommand is None:
            await ctx.send_help(ctx.command)

    @rpca.error
    async def rpca_error(self, ctx, error):
        """Handle errors in calendar commands."""  # Edited by Taako
        if isinstance(error, commands.CheckFailure):
            await ctx.send("You need administrator permissions to use this command.")  # Edited by Taako
        else:
            await ctx.send(f"An error occurred: {str(error)}")  # Edited by Taako

    async def red_delete_data_for_user(self, *, requester, user_id):
        """Nothing to delete as we don't store user data."""  # Edited by Taako
        pass

    @rpca.command(name="settitle")
    async def set_title(self, ctx, *, title: str):
        """Set a custom title for the main embed."""  # Edited by Taako
        await self._config.guild(ctx.guild).embed_title.set(title)
        await ctx.send(f"Embed title set to: {title}")  # Edited by Taako

    @rpca.command(name="info")
    async def info(self, ctx):
        """View the current settings for the RP calendar."""  # Edited by Taako
        guild_settings = await self._config.guild(ctx.guild).all()
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

        # Calculate the next post time explicitly for 00:00 in the configured timezone
        tz = pytz.timezone(time_zone)  # Edited by Taako
        now = datetime.now(tz)  # Get the current time in the configured timezone  # Edited by Taako
        next_post_time = now.replace(hour=0, minute=0, second=0) + timedelta(days=1)  # Set to 00:00 of the next day  # Edited by Taako

        # Calculate the time until the next post
        time_until_next_post = next_post_time - now  # Edited by Taako
        days, seconds = divmod(time_until_next_post.total_seconds(), 86400)  # Edited by Taako
        hours, remainder = divmod(seconds, 3600)  # Edited by Taako
        minutes, seconds = divmod(remainder, 60)  # Edited by Taako

        # Build the time string, excluding `00` for days and hours, but keeping `00m`  # Edited by Taako
        time_components = []  # Edited by Taako
        if days > 0:
            time_components.append(f"{int(days)}d")  # Edited by Taako
        if hours > 0:
            time_components.append(f"{int(hours)}h")  # Edited by Taako
        time_components.append(f"{int(minutes):02}m")  # Always include minutes  # Edited by Taako
        time_components.append(f"{int(seconds):02}s")  # Always include seconds  # Edited by Taako
        time_until_next_post_str = " ".join(time_components)  # Edited by Taako

        if not time_components:  # Edited by Taako
            time_until_next_post_str = "Not scheduled"  # Edited by Taako

        embed.add_field(name="Time Until Next Post", value=time_until_next_post_str, inline=False)  # Edited by Taako

        # Add the update channel field after the time until next post field
        embed.add_field(name="Update Channel", value=channel, inline=False)
        embed.add_field(name="Time Zone", value=time_zone, inline=False)
        embed.add_field(name="Embed Color", value=str(embed_color), inline=False)  # Edited by Taako
        embed.add_field(name="Embed Title", value=embed_title, inline=False)  # Edited by Taako
        embed.set_footer(text="RP Calendar by Taako", icon_url="https://cdn-icons-png.flaticon.com/512/869/869869.png")  # Always show footer in info embed  # Edited by Taako

        await ctx.send(embed=embed)

    @rpca.command(name="setstart")
    async def set_start_date(self, ctx, month: int, day: int, year: int):
        """Set the starting date for the RP calendar."""  # Edited by Taako
        try:
            date = datetime(year, month, day)
            date_str = date.strftime("%m-%d-%Y")
            await self._config.guild(ctx.guild).start_date.set(date_str)
            await self._config.guild(ctx.guild).current_date.set(date_str)
            await ctx.send(f"Calendar start date set to: {date_str}")  # Edited by Taako
        except ValueError:
            await ctx.send("Invalid date format. Please use: month day year")  # Edited by Taako

    @rpca.command(name="setchannel")
    async def set_channel(self, ctx, channel: discord.TextChannel):
        """Set the channel for daily calendar updates."""  # Edited by Taako
        await self._config.guild(ctx.guild).channel_id.set(channel.id)
        await ctx.send(f"Calendar updates will now be sent to: {channel.mention}")  # Edited by Taako

    @rpca.command(name="settimezone")
    async def set_timezone(self, ctx, timezone: str = None):
        """Set the timezone for the calendar."""  # Edited by Taako
        if not timezone:
            await ctx.send("Please provide a timezone (e.g., UTC, America/New_York)")  # Edited by Taako
            return

        if timezone in pytz.all_timezones:
            await self._config.guild(ctx.guild).time_zone.set(timezone)
            await ctx.send(f"Timezone set to: {timezone}")  # Edited by Taako
        else:
            await ctx.send("Invalid timezone. See: https://en.wikipedia.org/wiki/List_of_tz_database_time_zones")  # Edited by Taako

    @rpca.command(name="setcolor")
    async def set_color(self, ctx, color: discord.Color):
        """Set the embed color for calendar updates."""  # Edited by Taako
        await self._config.guild(ctx.guild).embed_color.set(color.value)
        await ctx.send(f"Embed color set to: {str(color)}")  # Edited by Taako

    @rpca.command(name="togglefooter")
    async def toggle_footer(self, ctx):
        """Toggle the footer on/off for calendar embeds."""  # Edited by Taako
        current = await self._config.guild(ctx.guild).show_footer()
        await self._config.guild(ctx.guild).show_footer.set(not current)
        state = "enabled" if not current else "disabled"
        await ctx.send(f"Footer has been {state}")  # Edited by Taako

    def _format_date(self, date_obj: datetime) -> str:
        """Format a datetime object into our standard format."""  # Edited by Taako
        return date_obj.strftime("%A %m-%d-%Y")  # Edited by Taako

    def _parse_date(self, date_str: str, tz: datetime.tzinfo) -> datetime:
        """Parse a date string into a datetime object."""  # Edited by Taako
        return datetime.strptime(date_str, "%m-%d-%Y").replace(tzinfo=tz)  # Edited by Taako

    @rpca.command(name="refresh")
    async def refresh(self, ctx):
        """Manually trigger a calendar update."""  # Edited by Taako
        guild_settings = await self._config.guild(ctx.guild).all()
        
        if not guild_settings["current_date"]:
            await ctx.send("Calendar not initialized. Use `[p]rpca setstart` first.")  # Edited by Taako
            return

        channel_id = guild_settings["channel_id"]
        if not channel_id:
            await ctx.send("Update channel not set. Use `[p]rpca setchannel` first.")  # Edited by Taako
            return

        channel = self._bot.get_channel(channel_id)
        if not channel:
            await ctx.send("Invalid channel. Please set a valid channel.")  # Edited by Taako
            return

        # Create and send the embed using current date
        tz = pytz.timezone(guild_settings["time_zone"])
        current_date = self._parse_date(guild_settings["current_date"], tz)
        
        embed = discord.Embed(
            title=guild_settings["embed_title"],
            description=f"Today's date: **{self._format_date(current_date)}**",
            color=discord.Color(guild_settings["embed_color"])
        )
        
        if guild_settings["show_footer"]:
            embed.set_footer(text="RP Calendar by Taako", icon_url="https://cdn-icons-png.flaticon.com/512/869/869869.png")
        
        await channel.send(embed=embed)
        await ctx.send(f"Calendar update sent to {channel.mention}")  # Edited by Taako

    @_daily_update_loop.before_loop
    async def before_daily_update_loop(self):
        """Wait until the bot is ready before starting the loop."""  # Edited by Taako
        await self._bot.wait_until_ready()

    def cog_unload(self):
        """Clean up tasks and unregister commands when the cog is unloaded."""  # Edited by Taako
        self._daily_update_loop.cancel()  # Stop the daily update loop  # Edited by Taako
