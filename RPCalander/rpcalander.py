import discord  # Import from the actual discord.py package
from typing import Optional, List, Union

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
        """View the current settings for the RP calendar including moon phase information if enabled."""
        if not interaction.guild:
            await interaction.response.send_message("This command can only be used in a server.", ephemeral=True)
            return
        await interaction.response.defer(ephemeral=True)
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
        
        # Add moon phase settings
        show_moon_phase = guild_settings.get("show_moon_phase", False)
        blood_moon_enabled = guild_settings.get("blood_moon_enabled", False)
        moon_channel_id = guild_settings.get("moon_channel_id")
        
        moon_status = "Enabled" if show_moon_phase else "Disabled"
        blood_moon_status = "Enabled" if blood_moon_enabled else "Disabled"
        moon_channel = f"<#{moon_channel_id}>" if moon_channel_id else "Same as calendar"
        
        embed.add_field(
            name="🌙 Moon Phase Settings",
            value=f"**Status:** {moon_status}\n"
                  f"**Blood Moon:** {blood_moon_status}\n"
                  f"**Moon Channel:** {moon_channel}",
            inline=False
        )
        
        # Get current moon phase if enabled
        if show_moon_phase and current_date != "Not set":
            try:
                from .moon_utils import get_moon_data
                current_date_obj = datetime.strptime(current_date, "%m-%d-%Y")
                moon_data = get_moon_data(current_date_obj, blood_moon_enabled)
                embed.add_field(
                    name="🌙 Current Moon Phase",
                    value=f"{moon_data['emoji']} {moon_data['name']}",
                    inline=False
                )
            except Exception as e:
                logging.error(f"Error getting moon phase: {e}")
        
        embed.set_footer(text="RP Calendar by Taako", icon_url="https://cdn-icons-png.flaticon.com/512/869/869869.png")
        await interaction.followup.send(embed=embed, ephemeral=True)

    @app_commands.command(name="force", description="Force post a calendar update to the configured channel immediately.")
    async def force(self, interaction: discord.Interaction) -> None:
        if not interaction.guild:
            await interaction.response.send_message("This command can only be used in a server.", ephemeral=True)
            return
        await interaction.response.defer(ephemeral=True)
        status, message = await self.cog.force_post_slash(interaction.guild)
        await interaction.followup.send(message, ephemeral=True)

    @app_commands.command(name="settitle", description="Set a custom title for the main embed.")
    async def settitle(self, interaction: discord.Interaction, title: str) -> None:
        if not interaction.guild:
            await interaction.response.send_message("This command can only be used in a server.", ephemeral=True)
            return
        await interaction.response.defer(ephemeral=True)
        if not title:
            await interaction.followup.send("Title cannot be empty.", ephemeral=True)
            return
        await self.cog._config.guild(interaction.guild).embed_title.set(title)
        await interaction.followup.send(f"Embed title set to: {title}", ephemeral=True)

    @app_commands.command(name="setcolor", description="Set the embed color for calendar updates.")
    async def setcolor(self, interaction: discord.Interaction, color: str) -> None:
        if not interaction.guild:
            await interaction.response.send_message("This command can only be used in a server.", ephemeral=True)
            return
        await interaction.response.defer(ephemeral=True)
        if not color:
            await interaction.followup.send("Color value is required.", ephemeral=True)
            return
        color_str = color.strip().lower().replace("#", "").replace("0x", "")
        try:
            color_value = int(color_str, 16)
            if not (0x000000 <= color_value <= 0xFFFFFF):
                raise ValueError
        except Exception:
            await interaction.followup.send(
                "Invalid color. Please provide a valid hex code (e.g. #00ff00).", ephemeral=True)
            return
        await self.cog._config.guild(interaction.guild).embed_color.set(color_value)
        await interaction.followup.send(f"Embed color set to: #{color_str.zfill(6)}", ephemeral=True)

    @app_commands.command(name="settimezone", description="Set the timezone for the calendar.")
    async def settimezone(self, interaction: discord.Interaction, timezone: str) -> None:
        if not interaction.guild:
            await interaction.response.send_message("This command can only be used in a server.", ephemeral=True)
            return
        await interaction.response.defer(ephemeral=True)
        if not timezone:
            await interaction.followup.send("Timezone is required.", ephemeral=True)
            return
        if timezone not in pytz.all_timezones:
            await interaction.followup.send("Invalid timezone. See: https://en.wikipedia.org/wiki/List_of_tz_database_time_zones", ephemeral=True)
            return
        await self.cog._config.guild(interaction.guild).time_zone.set(timezone)
        await interaction.followup.send(f"Timezone set to: {timezone}", ephemeral=True)

    @app_commands.command(name="setchannel", description="Set the channel for daily calendar updates.")
    async def setchannel(self, interaction: discord.Interaction, channel: discord.TextChannel) -> None:
        if not interaction.guild:
            await interaction.response.send_message("This command can only be used in a server.", ephemeral=True)
            return
        await interaction.response.defer(ephemeral=True)
        if not channel:
            await interaction.followup.send("Channel is required.", ephemeral=True)
            return
        await self.cog._config.guild(interaction.guild).channel_id.set(channel.id)
        await interaction.followup.send(f"Calendar updates will now be sent to: {channel.mention}", ephemeral=True)

    @app_commands.command(name="togglefooter", description="Toggle the footer on/off for calendar embeds.")
    async def togglefooter(self, interaction: discord.Interaction) -> None:
        if not interaction.guild:
            await interaction.response.send_message("This command can only be used in a server.", ephemeral=True)
            return
        await interaction.response.defer(ephemeral=True)
        current = await self.cog._config.guild(interaction.guild).show_footer()
        await self.cog._config.guild(interaction.guild).show_footer.set(not current)
        state = "enabled" if not current else "disabled"
        await interaction.followup.send(f"Footer has been {state}.", ephemeral=True)

    @app_commands.command(name="moonphase", description="View the current moon phase for the RP calendar date.")
    async def moonphase(self, interaction: discord.Interaction) -> None:
        """View the current moon phase for the RP calendar date."""
        if not interaction.guild:
            await interaction.response.send_message("This command can only be used in a server.", ephemeral=True)
            return
        
        await interaction.response.defer(ephemeral=True)
        guild_settings = await self.cog._config.guild(interaction.guild).all()
        
        # Check if moon phases are enabled
        if not guild_settings.get("show_moon_phase", False):
            await interaction.followup.send("Moon phase tracking is not enabled. An administrator can enable it with `/rpca moonconfig enable`.", ephemeral=True)
            return
        
        # Get the current RP date
        current_date_str = guild_settings.get("current_date")
        if not current_date_str:
            await interaction.followup.send("The RP calendar has not been set up yet. Please set a start date first.", ephemeral=True)
            return
        
        try:
            # Parse the current date string to a datetime object
            current_date = datetime.strptime(current_date_str, "%m-%d-%Y")
            
            # Get moon data and create embed
            from .moon_utils import get_moon_data, create_moon_embed
            moon_data = get_moon_data(current_date, guild_settings.get("blood_moon_enabled", False))
            embed = create_moon_embed(moon_data, guild_settings)
            
            await interaction.followup.send(embed=embed, ephemeral=False)
        except Exception as e:
            await interaction.followup.send(f"Error displaying moon phase: {str(e)}", ephemeral=True)

    @app_commands.command(name="forcemoonupdate", description="Force post a moon phase update to the configured channel.")
    @app_commands.default_permissions(administrator=True)
    async def forcemoonupdate(self, interaction: discord.Interaction) -> None:
        """Force post a moon phase update to the configured channel."""
        if not interaction.guild:
            await interaction.response.send_message("This command can only be used in a server.", ephemeral=True)
            return
        
        await interaction.response.defer(ephemeral=True)
        guild_settings = await self.cog._config.guild(interaction.guild).all()
        
        # Check if moon phases are enabled
        if not guild_settings.get("show_moon_phase", False):
            await interaction.followup.send("Moon phase tracking is not enabled. Enable it with `/rpca moonconfig enable`.", ephemeral=True)
            return
        
        # Get the current RP date
        current_date_str = guild_settings.get("current_date")
        if not current_date_str:
            await interaction.followup.send("The RP calendar has not been set up yet. Please set a start date first.", ephemeral=True)
            return
        
        try:
            # Post moon update
            await self.cog._post_moon_update(interaction.guild)
            await interaction.followup.send("Moon phase update has been posted.", ephemeral=True)
        except Exception as e:
            await interaction.followup.send(f"Error posting moon phase update: {str(e)}", ephemeral=True)

    @app_commands.command(name="moonconfig", description="Configure moon phase settings for the RP calendar.")
    @app_commands.default_permissions(administrator=True)
    @app_commands.describe(
        action="Action to perform",
        channel="Channel for moon phase updates (optional)",
        required_approvals="Number of admin approvals required for blood moon mode (1-10)"
    )
    @app_commands.choices(action=[
        app_commands.Choice(name="enable", value="enable"),
        app_commands.Choice(name="disable", value="disable"),
        app_commands.Choice(name="bloodmoon", value="bloodmoon"),
        app_commands.Choice(name="setchannel", value="setchannel")
    ])
    async def moonconfig(
        self, 
        interaction: discord.Interaction, 
        action: str,
        channel: Optional[discord.TextChannel] = None,
        required_approvals: Optional[int] = None
    ) -> None:
        """
        Configure moon phase settings for the RP calendar.
        
        Parameters
        ----------
        action: str
            The action to perform (enable, disable, bloodmoon, setchannel)
        channel: Optional[discord.TextChannel]
            The channel for moon phase updates (required for setchannel action)
        required_approvals: Optional[int]
            Parameter kept for backward compatibility but no longer used
        """
        if not interaction.guild:
            await interaction.response.send_message("This command can only be used in a server.", ephemeral=True)
            return
        
        await interaction.response.defer(ephemeral=True)
        guild_settings = await self.cog._config.guild(interaction.guild).all()
        
        if action == "enable":
            await self.cog._config.guild(interaction.guild).show_moon_phase.set(True)
            await interaction.followup.send("Moon phase tracking has been enabled.", ephemeral=True)
        
        elif action == "disable":
            await self.cog._config.guild(interaction.guild).show_moon_phase.set(False)
            await interaction.followup.send("Moon phase tracking has been disabled.", ephemeral=True)
        
        elif action == "bloodmoon":
            # Simply toggle blood moon mode on/off
            blood_moon_enabled = guild_settings.get("blood_moon_enabled", False)
            
            # Toggle the setting
            new_setting = not blood_moon_enabled
            await self.cog._config.guild(interaction.guild).blood_moon_enabled.set(new_setting)
            
            if new_setting:
                await interaction.followup.send("🔴 **BLOOD MOON MODE ACTIVATED!** The moon may now occasionally turn blood red during full moons!", ephemeral=False)
            else:
                await interaction.followup.send("Blood moon mode has been disabled.", ephemeral=True)
        
        elif action == "setchannel":
            if not channel:
                await interaction.followup.send("Please specify a channel for moon phase updates.", ephemeral=True)
                return
            
            await self.cog._config.guild(interaction.guild).moon_channel_id.set(channel.id)
            await interaction.followup.send(f"Moon phase updates will now be sent to: {channel.mention}", ephemeral=True)
            
        # Removed setrequired action as we no longer need approvals for blood moon mode
    
    @app_commands.command(name="resetbloodmoon", description="Disable blood moon mode.")
    @app_commands.default_permissions(administrator=True)
    async def resetbloodmoon(self, interaction: discord.Interaction) -> None:
        """Disable blood moon mode."""
        if not interaction.guild:
            await interaction.response.send_message("This command can only be used in a server.", ephemeral=True)
            return
        
        await interaction.response.defer(ephemeral=True)
        
        # Reset blood moon settings
        await self.cog._config.guild(interaction.guild).blood_moon_enabled.set(False)
        
        await interaction.followup.send("Blood moon mode has been disabled.", ephemeral=True)

class RPCalander(commands.Cog, DashboardIntegration):
    """
    A cog for managing an RP calendar with daily updates.
    
    Features:
    - Daily calendar updates based on a custom RP timeline
    - Configurable time zone, channel, and embed styling
    - Moon phase tracking with blood moon events
    """
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
            "last_posted": None,
            "show_moon_phase": False,  # Whether to show moon phase info
            "blood_moon_enabled": False,  # Whether blood moons can occur
            "moon_channel_id": None  # Separate channel for moon phase updates (defaults to same as calendar)
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
                        
                        # Post moon phase update if enabled
                        if guild_settings.get("show_moon_phase", False):
                            guild = self.bot.get_guild(guild_id)
                            if guild:
                                await self._post_moon_update(guild)
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
    async def force_post_command(self, ctx: commands.Context) -> None:
        """Force post a calendar update to the configured channel immediately."""
        status, message = await self.force_post(ctx.guild)
        await ctx.send(message)

    async def force_post(self, guild: discord.Guild) -> tuple[bool, str]:
        """Core logic for posting a calendar update. Returns (success, message)."""
        guild_settings = await self._config.guild(guild).all()
        channel_id = guild_settings.get("channel_id")
        if not channel_id:
            return False, "No channel configured for calendar updates."
        current_date = guild_settings.get("current_date")
        if not current_date:
            return False, "No current date set for the calendar."
        time_zone = guild_settings.get("time_zone") or "America/Chicago"
        embed_color = guild_settings.get("embed_color") or 0x0000FF
        embed_title = guild_settings.get("embed_title") or "📅 RP Calendar Update"
        show_footer = guild_settings.get("show_footer", True)
        tz = pytz.timezone(time_zone)
        now = datetime.now(tz)
        try:
            current_date_obj = datetime.strptime(current_date, "%m-%d-%Y").replace(tzinfo=tz)
            today_date_obj = now.replace(hour=0, minute=0, second=0, microsecond=0)
            if not self._is_same_month_day(current_date_obj, today_date_obj):
                days_missed = (today_date_obj - current_date_obj.replace(year=today_date_obj.year)).days
                if days_missed < 1:
                    days_missed = 1
                new_date_obj = current_date_obj + timedelta(days=days_missed)
            else:
                new_date_obj = current_date_obj
            new_date_str = new_date_obj.strftime("%A %m-%d-%Y")
            await self._config.guild(guild).current_date.set(new_date_obj.strftime("%m-%d-%Y"))
            await self._config.guild(guild).last_posted.set(now.isoformat())
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
                    return True, "Calendar update posted."
                except Exception as e:
                    logging.error(f"Error in force post: {e}")
                    return False, f"Failed to post calendar update: {e}"
            else:
                return False, "Configured channel not found."
        except Exception as e:
            logging.error(f"Error in force post date calculation: {e}")
            return False, f"Failed to calculate current date: {e}"

    async def force_post_slash(self, guild: discord.Guild) -> tuple[bool, str]:
        """Wrapper for slash command force post, returns (success, message)."""
        return await self.force_post(guild)

    async def _post_moon_update(self, guild) -> None:
        """
        Post a moon phase update to the configured channel.
        
        Parameters
        ----------
        guild : discord.Guild
            The guild to post the update for
        """
        try:
            guild_settings = await self._config.guild(guild).all()
            
            # Check if moon phase updates are enabled
            if not guild_settings.get("show_moon_phase", False):
                return
            
            # Get the channel to post to
            moon_channel_id = guild_settings.get("moon_channel_id") or guild_settings.get("channel_id")
            if not moon_channel_id:
                logging.error(f"No channel set for moon phase updates in guild {guild.name} ({guild.id})")
                return
            
            channel = guild.get_channel(moon_channel_id)
            if not channel:
                logging.error(f"Could not find channel {moon_channel_id} for moon phase updates in guild {guild.name} ({guild.id})")
                return
            
            # Get the current date
            current_date_str = guild_settings.get("current_date")
            if not current_date_str:
                logging.error(f"No current date set for guild {guild.name} ({guild.id})")
                return
            
            current_date = datetime.strptime(current_date_str, "%m-%d-%Y")
            
            # Import moon phase utilities
            from .moon_utils import get_moon_data, create_moon_embed
            
            # Get moon data and create embed
            moon_data = get_moon_data(
                current_date, 
                guild_settings.get("blood_moon_enabled", False)
            )
            
            embed = create_moon_embed(moon_data, guild_settings)
            
            # Send the embed
            await channel.send(embed=embed)
            
            # If this is a blood moon, add an extra mention to draw attention
            if moon_data.get("is_blood_moon", False):
                await channel.send("@everyone **A Blood Moon has risen! Strange energies fill the air...**")
                
        except Exception as e:
            logging.error(f"Error posting moon phase update for guild {guild.name}: {str(e)}")

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
                show_moon_phase = data.get("show_moon_phase", "off") == "on"
                
                await self._config.guild(guild).embed_title.set(embed_title)
                await self._config.guild(guild).time_zone.set(time_zone)
                await self._config.guild(guild).embed_color.set(embed_color)
                await self._config.guild(guild).show_footer.set(show_footer)
                await self._config.guild(guild).show_moon_phase.set(show_moon_phase)
                
                settings = await self._config.guild(guild).all()
            return {
                "embed_title": settings["embed_title"],
                "time_zone": settings["time_zone"],
                "embed_color": settings["embed_color"],
                "show_footer": settings["show_footer"],
                "show_moon_phase": settings.get("show_moon_phase", False),
                "blood_moon_enabled": settings.get("blood_moon_enabled", False),
            }

        def get_dashboard_views(self):
            """Return dashboard page methods for Red-Dashboard discovery."""
            return [self.dashboard_test, self.dashboard_settings]
