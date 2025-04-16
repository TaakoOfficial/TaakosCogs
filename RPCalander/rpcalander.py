import discord  # Import from the actual discord.py package
from typing import Optional

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

from redbot.core import commands, Config, app_commands
from datetime import datetime, timedelta
import pytz
from discord.ext import tasks
from .timing_utils import get_next_post_time, has_already_posted_today
from .file_utils import read_last_posted, write_last_posted
import logging

class RPCAGroup(app_commands.Group):
    """Slash command group for RP Calendar management."""
    def __init__(self, cog: "RPCalander"):
        super().__init__(name="rpca", description="RP Calendar management commands.")
        self.cog = cog

    @app_commands.command(name="info", description="View the current settings for the RP calendar.")
    async def info(self, interaction: discord.Interaction) -> None:
        """Slash command to view the current RP calendar settings."""
        if not interaction.guild:
            await interaction.response.send_message("This command can only be used in a server.", ephemeral=True)
            return
        guild_settings = await self.cog._config.guild(interaction.guild).all()
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
        try:
            tomorrow_obj = now + timedelta(days=1)
            if current_date != "Not set":
                current_date_obj = datetime.strptime(current_date, "%m-%d-%Y")
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
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="force", description="Force post a calendar update to the configured channel immediately.")
    async def force(self, interaction: discord.Interaction) -> None:
        """Slash command to force post a calendar update."""
        if not interaction.guild:
            await interaction.response.send_message("This command can only be used in a server.", ephemeral=True)
            return
        ctx = await self.cog.bot.get_context(interaction)
        await self.cog.force_post(ctx)
        await interaction.response.send_message("Force post triggered.", ephemeral=True)

    @app_commands.command(name="settitle", description="Set a custom title for the main embed.")
    async def settitle(self, interaction: discord.Interaction, title: str) -> None:
        """Slash command to set the embed title."""
        if not interaction.guild:
            await interaction.response.send_message("This command can only be used in a server.", ephemeral=True)
            return
        if not title:
            await interaction.response.send_message("Title cannot be empty.", ephemeral=True)
            return
        await self.cog._config.guild(interaction.guild).embed_title.set(title)
        await interaction.response.send_message(f"Embed title set to: {title}", ephemeral=True)

    @app_commands.command(name="setcolor", description="Set the embed color for calendar updates.")
    async def setcolor(self, interaction: discord.Interaction, color: str) -> None:
        """Slash command to set the embed color. Accepts a hex code (e.g. #00ff00 or 0x00ff00 or 00ff00)."""
        if not interaction.guild:
            await interaction.response.send_message("This command can only be used in a server.", ephemeral=True)
            return
        color_str = color.strip().lower().replace("#", "").replace("0x", "")
        try:
            color_value = int(color_str, 16)
            if not (0x000000 <= color_value <= 0xFFFFFF):
                raise ValueError
            color_obj = discord.Color(color_value)
        except Exception:
            await interaction.response.send_message(
                "Invalid color. Please provide a valid hex code (e.g. #00ff00).", ephemeral=True)
            return
        await self.cog._config.guild(interaction.guild).embed_color.set(color_value)
        await interaction.response.send_message(f"Embed color set to: #{color_str.zfill(6)}", ephemeral=True)

    @app_commands.command(name="settimezone", description="Set the timezone for the calendar.")
    async def settimezone(self, interaction: discord.Interaction, timezone: str) -> None:
        """Slash command to set the timezone."""
        if not interaction.guild:
            await interaction.response.send_message("This command can only be used in a server.", ephemeral=True)
            return
        if timezone not in pytz.all_timezones:
            await interaction.response.send_message("Invalid timezone. See: https://en.wikipedia.org/wiki/List_of_tz_database_time_zones", ephemeral=True)
            return
        await self.cog._config.guild(interaction.guild).time_zone.set(timezone)
        await interaction.response.send_message(f"Timezone set to: {timezone}", ephemeral=True)

    @app_commands.command(name="setchannel", description="Set the channel for daily calendar updates.")
    async def setchannel(self, interaction: discord.Interaction, channel: discord.TextChannel) -> None:
        """Slash command to set the update channel."""
        if not interaction.guild:
            await interaction.response.send_message("This command can only be used in a server.", ephemeral=True)
            return
        await self.cog._config.guild(interaction.guild).channel_id.set(channel.id)
        await interaction.response.send_message(f"Calendar updates will now be sent to: {channel.mention}", ephemeral=True)

    @app_commands.command(name="togglefooter", description="Toggle the footer on/off for calendar embeds.")
    async def togglefooter(self, interaction: discord.Interaction) -> None:
        """Slash command to toggle the embed footer."""
        if not interaction.guild:
            await interaction.response.send_message("This command can only be used in a server.", ephemeral=True)
            return
        current = await self.cog._config.guild(interaction.guild).show_footer()
        await self.cog._config.guild(interaction.guild).show_footer.set(not current)
        state = "enabled" if not current else "disabled"
        await interaction.response.send_message(f"Footer has been {state}.", ephemeral=True)

class RPCalander(commands.Cog, DashboardIntegration):
    """A cog for managing an RP calendar with daily updates."""
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
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
        self.rpca_group = RPCAGroup(self)
    async def cog_unload(self) -> None:
        if hasattr(self, 'bot'):
            self.bot.tree.remove_command(self.rpca_group.name)
        if hasattr(self, '_daily_update_loop') and self._daily_update_loop.is_running():
            self._daily_update_loop.cancel()

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
    async def _daily_update_loop(self) -> None:
        """Task loop to post daily calendar updates at the correct time for each guild."""
        all_guilds = await self._config.all_guilds()
        for guild_id, guild_settings in all_guilds.items():
            channel_id = guild_settings.get("channel_id")
            current_date = guild_settings.get("current_date")
            time_zone = guild_settings.get("time_zone") or "America/Chicago"
            embed_color = guild_settings.get("embed_color") or 0x0000FF
            embed_title = guild_settings.get("embed_title") or "📅 RP Calendar Update"
            show_footer = guild_settings.get("show_footer", True)
            last_posted = guild_settings.get("last_posted")
            if not channel_id or not current_date:
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
                    current_date_obj = datetime.strptime(current_date, "%m-%d-%Y")
                except Exception:
                    current_date_obj = now
                # Always increment the date by 1 day for the new post
                new_date_obj = current_date_obj + timedelta(days=1)
                new_date_str = new_date_obj.strftime("%A %m-%d-%Y")
                await self._config.guild_from_id(guild_id).current_date.set(new_date_obj.strftime("%m-%d-%Y"))
                await self._config.guild_from_id(guild_id).last_posted.set(now.isoformat())
                embed = discord.Embed(
                    title=embed_title,
                    description=f"Today's date: **{new_date_str}**",
                    color=discord.Color(embed_color)
                )
                if show_footer:
                    embed.set_footer(
                        text="RP Calendar by Taako",
                        icon_url="https://cdn-icons-png.flaticon.com/512/869/869869.png"
                    )
                channel = self.bot.get_channel(channel_id)
                if channel:
                    try:
                        await channel.send(embed=embed)
                    except Exception as e:
                        logging.error(f"Failed to send daily calendar update: {e}")

    @_daily_update_loop.error
    async def _daily_update_loop_error(self, error):
        """Handle errors in the daily update loop and restart it if necessary."""
        logging.error(f"Error in daily update loop: {error}")
        if not self._daily_update_loop.is_running():
            logging.debug("Restarting daily update loop after error.")
            self._daily_update_loop.start()

    @commands.command(name="force")
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
            
            channel = self.bot.get_channel(channel_id)
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

    if _dashboard_available:
        @dashboard_page("test", "RP Calendar Dashboard Test")
        async def dashboard_test(self, request, guild):
            """A test page to verify dashboard integration."""
            return {"message": "Dashboard integration is working!"}

        @dashboard_page("settings", "RP Calendar Settings")
        async def dashboard_settings(self, request, guild):
            """Dashboard page for viewing and editing RP Calendar settings."""
            settings = await self._config.guild(guild).all()
            if request.method == "POST":
                data = await request.post()
                embed_title = data.get("embed_title", settings["embed_title"])
                time_zone = data.get("time_zone", settings["time_zone"])
                embed_color = int(data.get("embed_color", settings["embed_color"]))
                show_footer = data.get("show_footer", "off") == "on"
                await self._config.guild(guild).embed_title.set(embed_title)
                await self._config.guild(guild).time_zone.set(time_zone)
                await self._config.guild(guild).embed_color.set(embed_color)
                await self._config.guild(guild).show_footer.set(show_footer)
                settings = await self._config.guild(guild).all()
            return {
                "embed_title": settings["embed_title"],
                "time_zone": settings["time_zone"],
                "embed_color": settings["embed_color"],
                "show_footer": settings["show_footer"],
            }

        def get_dashboard_views(self):
            """Return dashboard page methods for Red-Dashboard discovery."""
            return [self.dashboard_test, self.dashboard_settings]
