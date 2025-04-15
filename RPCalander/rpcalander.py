import discord
from redbot.core import commands, Config
from datetime import datetime, timedelta
import pytz
from discord.ext import tasks
from .timing_utils import get_next_post_time, has_already_posted_today
from .file_utils import read_last_posted, write_last_posted
import logging

# Optional Red-Dashboard integration
try:
    from redbot.core.utils.dashboard import DashboardIntegration, dashboard_page
    _dashboard_available = True
except ImportError:
    _dashboard_available = False
    class DashboardIntegration:
        pass
    def dashboard_page(*args, **kwargs):
        def decorator(func):
            return func
        return decorator

# Configure logging for debugging
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')

class RPCalander(commands.Cog, DashboardIntegration):
    """A cog for managing an RP calendar with daily updates."""

    def __init__(self, bot: commands.Bot) -> None:
        self._bot = bot
        self._config = Config.get_conf(self, identifier=9876543210, force_registration=True)
        self._default_guild = {
            "start_date": None,
            "current_date": None,
            "channel_id": None,
            "time_zone": "America/Chicago",
            "embed_color": 0x0000FF,
            "show_footer": True,
            "embed_title": "📅 RP Calendar Update",
            "last_posted": None
        }
        self._config.register_guild(**self._default_guild)

    async def cog_load(self):
        """Start the daily update loop without triggering an immediate post."""
        logging.debug("Starting cog_load method.")
        last_posted = read_last_posted()  # Read the last posted timestamp from the file

        # Skip starting the loop if already posted today
        if last_posted:
            tz = pytz.timezone("America/Chicago")  # Default timezone
            last_posted_dt = datetime.fromisoformat(last_posted).astimezone(tz)
            today = datetime.now(tz).replace(hour=0, minute=0, second=0)  # Start of today

            if last_posted_dt >= today:
                logging.debug("Already posted today. Skipping loop start.")
                return

        if not self._daily_update_loop.is_running():
            logging.debug("Starting daily update loop.")
            self._daily_update_loop.start()

        # Check for missed dates without sending an embed
        all_guilds = await self._config.all_guilds()
        for guild_id, guild_settings in all_guilds.items():
            time_zone = guild_settings["time_zone"] or "America/Chicago"
            last_posted = guild_settings.get("last_posted")

            # Skip posting if already posted today
            if has_already_posted_today(last_posted, time_zone):
                continue

            # Update the current date if necessary
            current_date = guild_settings["current_date"]
            if current_date:
                tz = pytz.timezone(time_zone)
                current_date_obj = datetime.strptime(current_date, "%m-%d-%Y").astimezone(tz)
                today_date_obj = datetime.now(tz).replace(hour=0, minute=0, second=0, microsecond=0)

                if today_date_obj > current_date_obj:
                    days_missed = (today_date_obj - current_date_obj).days
                    new_date_obj = current_date_obj + timedelta(days=days_missed)
                    await self._config.guild_from_id(guild_id).current_date.set(new_date_obj.strftime("%m-%d-%Y"))

    @commands.group(name="rpca", invoke_without_command=True)
    @commands.admin_or_permissions(administrator=True)
    async def rpca(self, ctx: commands.Context) -> None:
        """Calendar management commands. Requires administrator permissions."""
        # Only send help if not a subcommand and not already invoked
        if ctx.invoked_subcommand is None and ctx.command is not None:
            await ctx.send_help(ctx.command)

    @rpca.error
    async def rpca_error(self, ctx: commands.Context, error: Exception) -> None:
        """Handle errors in calendar commands."""
        if isinstance(error, commands.CheckFailure):
            await ctx.send("You need administrator permissions to use this command.")
        else:
            await ctx.send(f"An error occurred: {str(error)}")

    async def red_delete_data_for_user(self, *, requester, user_id) -> None:
        """Nothing to delete as we don't store user data."""
        pass

    @rpca.command(name="settitle")
    async def set_title(self, ctx: commands.Context, *, title: str) -> None:
        """Set a custom title for the main embed."""
        if not title:
            await ctx.send("Title cannot be empty.")
            return
        await self._config.guild(ctx.guild).embed_title.set(title)
        await ctx.send(f"Embed title set to: {title}")

    @rpca.command(name="info")
    async def info(self, ctx: commands.Context) -> None:
        """View the current settings for the RP calendar."""
        guild_settings = await self._config.guild(ctx.guild).all()
        embed_color = discord.Color(guild_settings.get("embed_color", 0x0000FF))
        embed = discord.Embed(title="RP Calendar Settings", color=embed_color)
        start_date = guild_settings["start_date"] or "Not set"
        current_date = guild_settings["current_date"] or "Not set"
        channel_id = guild_settings["channel_id"]
        channel = f"<#{channel_id}>" if channel_id else "Not set"
        time_zone = guild_settings["time_zone"] or "America/Chicago"
        embed_title = guild_settings["embed_title"] or "📅 RP Calendar Update"

        tz = pytz.timezone(time_zone)
        now = datetime.now(tz)
        # Calculate tomorrow's date based on the system's current date
        try:
            tomorrow_obj = now + timedelta(days=1)
            if current_date != "Not set":
                current_date_obj = datetime.strptime(current_date, "%m-%d-%Y")
                # Keep the year from the current_date but use tomorrow's month and day
                tomorrow_obj = tomorrow_obj.replace(year=current_date_obj.year)
            tomorrow_str = tomorrow_obj.strftime("%A %m-%d-%Y")
        except Exception as e:
            logging.error(f"Error calculating tomorrow's date: {e}")
            tomorrow_str = "Error"

        embed.add_field(name="Start Date", value=start_date, inline=False)
        embed.add_field(name="Current Date", value=current_date, inline=False)
        embed.add_field(name="Tomorrow's Date", value=tomorrow_str, inline=False)

        next_post_time = now.replace(hour=0, minute=0, second=0) + timedelta(days=1)
        time_until_next_post = next_post_time - now
        days, seconds = divmod(time_until_next_post.total_seconds(), 86400)
        hours, remainder = divmod(seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        time_components = []
        if days > 0:
            time_components.append(f"{int(days)}d")
        if hours > 0:
            time_components.append(f"{int(hours)}h")
        time_components.append(f"{int(minutes):02}m")
        time_components.append(f"{int(seconds):02}s")
        time_until_next_post_str = " ".join(time_components)
        if not time_components:
            time_until_next_post_str = "Not scheduled"
        embed.add_field(name="Time Until Next Post", value=time_until_next_post_str, inline=False)
        embed.add_field(name="Update Channel", value=channel, inline=False)
        embed.add_field(name="Time Zone", value=time_zone, inline=False)
        embed.add_field(name="Embed Color", value=str(embed_color), inline=False)
        embed.add_field(name="Embed Title", value=embed_title, inline=False)
        embed.set_footer(text="RP Calendar by Taako", icon_url="https://cdn-icons-png.flaticon.com/512/869/869869.png")
        await ctx.send(embed=embed)

    @rpca.command(name="setstart")
    async def set_start_date(self, ctx: commands.Context, year: int) -> None:
        """Set the starting date for the RP calendar using the current month and day, and a custom year."""
        guild_settings = await self._config.guild(ctx.guild).all()
        time_zone = guild_settings.get("time_zone") or "America/Chicago"
        tz = pytz.timezone(time_zone)
        now = datetime.now(tz)
        try:
            date = datetime(year, now.month, now.day)
            date_str = date.strftime("%m-%d-%Y")
            await self._config.guild(ctx.guild).start_date.set(date_str)
            await self._config.guild(ctx.guild).current_date.set(date_str)
            await ctx.send(f"Calendar start date set to: {date_str}")
        except ValueError:
            await ctx.send("Invalid year provided. Please provide a valid year (e.g., 2025).")

    @rpca.command(name="setchannel")
    async def set_channel(self, ctx, channel: discord.TextChannel):
        """Set the channel for daily calendar updates."""
        await self._config.guild(ctx.guild).channel_id.set(channel.id)
        await ctx.send(f"Calendar updates will now be sent to: {channel.mention}")

    @rpca.command(name="settimezone")
    async def set_timezone(self, ctx, timezone: str = None):
        """Set the timezone for the calendar."""
        if not timezone:
            await ctx.send("Please provide a timezone (e.g., UTC, America/New_York)")
            return

        if timezone in pytz.all_timezones:
            await self._config.guild(ctx.guild).time_zone.set(timezone)
            await ctx.send(f"Timezone set to: {timezone}")
        else:
            await ctx.send("Invalid timezone. See: https://en.wikipedia.org/wiki/List_of_tz_database_time_zones")

    @rpca.command(name="setcolor")
    async def set_color(self, ctx, color: discord.Color):
        """Set the embed color for calendar updates."""
        await self._config.guild(ctx.guild).embed_color.set(color.value)
        await ctx.send(f"Embed color set to: {str(color)}")

    @rpca.command(name="togglefooter")
    async def toggle_footer(self, ctx):
        """Toggle the footer on/off for calendar embeds."""
        current = await self._config.guild(ctx.guild).show_footer()
        await self._config.guild(ctx.guild).show_footer.set(not current)
        state = "enabled" if not current else "disabled"
        await ctx.send(f"Footer has been {state}")

    def _format_date(self, date_obj: datetime) -> str:
        """Format a datetime object into our standard format."""
        return date_obj.strftime("%A %m-%d-%Y")

    def _parse_date(self, date_str: str, tz: datetime.tzinfo) -> datetime:
        """Parse a date string into a datetime object."""
        return datetime.strptime(date_str, "%m-%d-%Y").replace(tzinfo=tz)

    def _is_same_month_day(self, date1: datetime, date2: datetime) -> bool:
        """Check if two dates have the same month and day."""
        return date1.month == date2.month and date1.day == date2.day

    @tasks.loop(minutes=1)
    async def _daily_update_loop(self):
        """Task loop to post daily calendar updates at the correct time for each guild."""
        all_guilds = await self._config.all_guilds()
        for guild_id, guild_settings in all_guilds.items():
            channel_id = guild_settings["channel_id"]
            if not channel_id:
                continue
            current_date = guild_settings["current_date"]
            time_zone = guild_settings["time_zone"] or "America/Chicago"
            embed_color = guild_settings["embed_color"] or 0x0000FF
            embed_title = guild_settings["embed_title"] or "📅 RP Calendar Update"
            show_footer = guild_settings["show_footer"]
            last_posted = guild_settings.get("last_posted")
            if not current_date:
                continue
            tz = pytz.timezone(time_zone)
            now = datetime.now(tz)
            # Calculate the next post time (00:00 in the configured timezone)
            if last_posted:
                try:
                    last_posted_dt = datetime.fromisoformat(last_posted).astimezone(tz)
                except Exception:
                    last_posted_dt = now - timedelta(days=1)
            else:
                last_posted_dt = now - timedelta(days=1)
            next_post_time = last_posted_dt.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)
            if now >= next_post_time:
                try:
                    current_date_obj = datetime.strptime(current_date, "%m-%d-%Y").astimezone(tz)
                except Exception:
                    current_date_obj = now
                today_date_obj = now.replace(hour=0, minute=0, second=0, microsecond=0)
                # Only increment if month and day are not the same
                if not self._is_same_month_day(current_date_obj, today_date_obj):
                    days_missed = (today_date_obj - current_date_obj).days
                    if days_missed < 1:
                        days_missed = 1
                    new_date_obj = current_date_obj + timedelta(days=days_missed)
                else:
                    new_date_obj = current_date_obj
                new_date_str = new_date_obj.strftime("%A %m-%d-%Y")
                await self._config.guild_from_id(guild_id).current_date.set(new_date_obj.strftime("%m-%d-%Y"))
                await self._config.guild_from_id(guild_id).last_posted.set(now.isoformat())
                embed = discord.Embed(
                    title=embed_title,
                    description=f"Today's date: **{new_date_str}**",
                    color=discord.Color(embed_color)
                )
                if show_footer:
                    embed.set_footer(text="RP Calendar by Taako", icon_url="https://cdn-icons-png.flaticon.com/512/869/869869.png")
                channel = self._bot.get_channel(channel_id)
                if channel:
                    await channel.send(embed=embed)

    @_daily_update_loop.error
    async def _daily_update_loop_error(self, error):
        """Handle errors in the daily update loop and restart it if necessary."""
        logging.error(f"Error in daily update loop: {error}")
        if not self._daily_update_loop.is_running():
            logging.debug("Restarting daily update loop after error.")
            self._daily_update_loop.start()

    async def cog_unload(self) -> None:
        """Cleanup tasks when the cog is unloaded."""
        if hasattr(self, '_daily_update_loop') and self._daily_update_loop.is_running():
            self._daily_update_loop.cancel()

    @rpca.command(name="force")
    @commands.admin_or_permissions(administrator=True)
    async def force_post(self, ctx: commands.Context) -> None:
        """Force post a calendar update to the configured channel immediately."""
        guild_settings = await self._config.guild(ctx.guild).all()
        channel_id = guild_settings.get("channel_id")
        if not channel_id:
            await ctx.send("No channel configured for calendar updates.")
            return
        current_date = guild_settings.get("current_date")
        if not current_date:
            await ctx.send("No current date set for the calendar.")
            return
        
        time_zone = guild_settings.get("time_zone") or "America/Chicago"
        embed_color = guild_settings.get("embed_color") or 0x0000FF
        embed_title = guild_settings.get("embed_title") or "📅 RP Calendar Update"
        show_footer = guild_settings.get("show_footer", True)
        
        tz = pytz.timezone(time_zone)
        now = datetime.now(tz)
        
        try:
            # Parse current stored date
            current_date_obj = datetime.strptime(current_date, "%m-%d-%Y").replace(tzinfo=tz)
            today_date_obj = now.replace(hour=0, minute=0, second=0, microsecond=0)

            # Check if we need to increment the date
            if not self._is_same_month_day(current_date_obj, today_date_obj):
                days_missed = (today_date_obj - current_date_obj.replace(year=today_date_obj.year)).days
                if days_missed < 1:
                    days_missed = 1
                # Keep the stored year but increment by the needed days
                new_date_obj = current_date_obj + timedelta(days=days_missed)
            else:
                new_date_obj = current_date_obj

            # Update the stored current_date and format display string
            new_date_str = new_date_obj.strftime("%A %m-%d-%Y")
            await self._config.guild(ctx.guild).current_date.set(new_date_obj.strftime("%m-%d-%Y"))
            await self._config.guild(ctx.guild).last_posted.set(now.isoformat())
            
            embed = discord.Embed(
                title=embed_title,
                description=f"Today's date: **{new_date_str}**",
                color=discord.Color(embed_color)
            )
            if show_footer:
                embed.set_footer(text="RP Calendar by Taako", icon_url="https://cdn-icons-png.flaticon.com/512/869/869869.png")
            
            channel = self._bot.get_channel(channel_id)
            if channel:
                try:
                    await channel.send(embed=embed)
                    await ctx.send("Calendar update posted.")
                except Exception as e:
                    logging.error(f"Error in force post: {e}")
                    await ctx.send(f"Failed to post calendar update: {e}")
            else:
                await ctx.send("Configured channel not found.")
        except Exception as e:
            logging.error(f"Error in force post date calculation: {e}")
            await ctx.send(f"Failed to calculate current date: {e}")
