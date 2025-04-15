from redbot.core import commands, Config
from redbot.core.i18n import Translator
from discord.ext import tasks
import discord
import pytz
from datetime import datetime
from typing import Dict, Any, Optional
from .weather_utils import generate_weather, create_weather_embed
from .time_utils import calculate_next_refresh_time
from .file_utils import write_last_posted
import logging

_ = Translator("RandomWeather", __file__)

class WeatherCog(commands.Cog):
    """A cog for generating random daily weather updates."""

    __author__ = ["Taako"]
    __version__ = "2.0.1"

    def __init__(self, bot: commands.Bot):
        """Initialize the weather cog."""
        self.bot = bot
        self.config = Config.get_conf(self, identifier=1234567890, force_registration=True)
        default_guild = {
            "role_id": None,
            "channel_id": None,
            "tag_role": False,
            "refresh_interval": None,
            "refresh_time": "0000",
            "show_footer": True,
            "embed_color": 0xFF0000,
            "last_refresh": 0,
            "time_zone": "UTC",  # Per-guild time zone support
        }
        self.config.register_guild(**default_guild)
        self.weather_update_loop.start()

    @commands.group(name="rweather", invoke_without_command=True)
    @commands.admin_or_permissions(administrator=True)
    async def rweather(self, ctx: commands.Context):
        """Weather management commands. Requires administrator permissions."""
        if ctx.invoked_subcommand is None:
            await ctx.send_help(ctx.command)

    @rweather.command(name="timezone")
    async def set_timezone(self, ctx: commands.Context, timezone: str = None):
        """Set the timezone for weather updates (e.g., UTC, America/New_York)."""
        if not timezone:
            await ctx.send("Please provide a timezone (e.g., UTC, America/New_York)")
            return
        if timezone in pytz.all_timezones:
            await self.config.guild(ctx.guild).time_zone.set(timezone)
            await ctx.send(f"Timezone set to: {timezone}")
        else:
            await ctx.send("Invalid timezone. See: https://en.wikipedia.org/wiki/List_of_tz_database_time_zones")

    @tasks.loop(minutes=1)
    async def weather_update_loop(self) -> None:
        """Task loop to post daily weather updates at the correct time or interval."""
        try:
            all_guilds = await self.config.all_guilds()
            for guild_id, guild_settings in all_guilds.items():
                try:
                    channel_id = guild_settings.get("channel_id")
                    if not channel_id:
                        continue
                    last_refresh = guild_settings.get("last_refresh", 0)
                    refresh_interval = guild_settings.get("refresh_interval")
                    refresh_time = guild_settings.get("refresh_time")
                    time_zone = guild_settings.get("time_zone") or "UTC"
                    
                    tz = pytz.timezone(time_zone)
                    now = datetime.now(tz)
                    
                    # Get next scheduled post time
                    next_post_time = calculate_next_refresh_time(
                        last_refresh, refresh_interval, refresh_time, time_zone
                    )
                    
                    # Ensure times are timezone-aware for comparison
                    if next_post_time.tzinfo is None:
                        next_post_time = tz.localize(next_post_time)
                    if now.tzinfo is None:
                        now = tz.localize(now)
                    
                    if now >= next_post_time:
                        await self._post_weather_update(
                            guild_id, 
                            guild_settings,
                            scheduled_time=next_post_time.timestamp()
                        )
                except Exception as e:
                    logging.error(f"Error in weather update for guild {guild_id}: {e}")
        except Exception as e:
            logging.error(f"Error in weather update loop: {e}")

    @weather_update_loop.before_loop
    async def before_weather_loop(self):
        """Wait for bot to be ready before starting the loop."""
        await self.bot.wait_until_ready()

    async def cog_unload(self):
        """Clean up tasks when the cog is unloaded."""
        if self.weather_update_loop.is_running():
            self.weather_update_loop.cancel()

    @rweather.command(name="channel")
    async def set_channel(self, ctx: commands.Context, channel: discord.TextChannel):
        """Set the channel for weather updates."""
        await self.config.guild(ctx.guild).channel_id.set(channel.id)
        await ctx.send(f"Weather updates will now be sent to {channel.mention}")

    @rweather.command(name="role")
    async def set_role(self, ctx: commands.Context, role: discord.Role):
        """Set the role to be tagged for weather updates."""
        await self.config.guild(ctx.guild).role_id.set(role.id)
        await ctx.send(f"Weather updates will now tag {role.name}")

    @rweather.command(name="toggle")
    async def toggle_role(self, ctx: commands.Context):
        """Toggle role tagging on/off for weather updates."""
        current = await self.config.guild(ctx.guild).tag_role()
        await self.config.guild(ctx.guild).tag_role.set(not current)
        state = "enabled" if not current else "disabled"
        await ctx.send(f"Role tagging has been {state}")

    @rweather.command(name="refresh")
    async def set_refresh(self, ctx: commands.Context, value: str):
        """Set refresh interval (10m, 1h) or time (1830)."""
        time_units = {"s": 1, "m": 60, "h": 3600, "d": 86400}

        if value.isdigit() and len(value) == 4:
            await self.config.guild(ctx.guild).refresh_time.set(value)
            await self.config.guild(ctx.guild).refresh_interval.set(None)
            await ctx.send(f"Weather will refresh daily at {value}")
            return

        if not value[-1] in time_units:
            await ctx.send("Invalid format. Use time (1830) or interval (10m, 1h)")
            return

        try:
            unit = value[-1]
            interval = int(value[:-1])
            refresh_interval = interval * time_units[unit]
            await self.config.guild(ctx.guild).refresh_interval.set(refresh_interval)
            await self.config.guild(ctx.guild).refresh_time.set(None)
            await ctx.send(f"Weather will refresh every {value}")
        except ValueError:
            await ctx.send("Invalid format. Use a number with s, m, h, or d")

    @rweather.command(name="color")
    async def set_color(self, ctx: commands.Context, color: discord.Color):
        """Set the embed color for weather updates."""
        await self.config.guild(ctx.guild).embed_color.set(color.value)
        await ctx.send(f"Embed color set to: {str(color)}")

    @rweather.command(name="footer")
    async def toggle_footer(self, ctx: commands.Context):
        """Toggle footer on/off for weather embeds."""
        current = await self.config.guild(ctx.guild).show_footer()
        await self.config.guild(ctx.guild).show_footer.set(not current)
        state = "enabled" if not current else "disabled"
        await ctx.send(f"Footer has been {state}")

    @rweather.command(name="info")
    async def info(self, ctx: commands.Context):
        """View the current settings for weather updates."""
        guild_settings = await self.config.guild(ctx.guild).all()
        embed_color = discord.Color(guild_settings.get("embed_color", 0xFF0000))
        refresh_interval = guild_settings.get("refresh_interval")
        refresh_time = guild_settings.get("refresh_time")
        last_refresh = guild_settings.get("last_refresh", 0)
        time_zone = guild_settings.get("time_zone") or "UTC"

        # Get current time in guild's timezone
        tz = pytz.timezone(time_zone)
        now = datetime.now(tz)
        time_until_next_refresh_str = "❌ Not set"

        try:
            next_post_time = calculate_next_refresh_time(
                last_refresh, refresh_interval, refresh_time, time_zone
            )

            # Ensure both are timezone-aware
            if next_post_time is not None and hasattr(next_post_time, 'tzinfo') and next_post_time.tzinfo is not None:
                if now.tzinfo is None:
                    now = tz.localize(now)
                time_until_next_refresh = (next_post_time - now).total_seconds()
                if time_until_next_refresh > 0:
                    days, remainder = divmod(time_until_next_refresh, 86400)
                    hours, remainder = divmod(remainder, 3600)
                    minutes, seconds = divmod(remainder, 60)
                    time_until_next_refresh_str = (
                        (f"{int(days)}d " if days else "") +
                        (f"{int(hours)}h " if hours else "") +
                        (f"{int(minutes)}m " if minutes else "") +
                        (f"{int(seconds)}s" if seconds else "")
                    ).strip()
                else:
                    time_until_next_refresh_str = "❌ Not set"
            else:
                time_until_next_refresh_str = "❌ Error"
        except Exception as e:
            logging.error(f"Error calculating next refresh time: {e}")
            time_until_next_refresh_str = "❌ Error"

        # Determine current season
        month = now.month
        if month in [12, 1, 2]:
            current_season = "❄️ Winter"
        elif month in [3, 4, 5]:
            current_season = "🌸 Spring"
        elif month in [6, 7, 8]:
            current_season = "☀️ Summer"
        else:
            current_season = "🍂 Autumn"

        # Get channel and role
        channel = self.bot.get_channel(guild_settings.get("channel_id")) if guild_settings.get("channel_id") else None
        role = ctx.guild.get_role(guild_settings.get("role_id")) if guild_settings.get("role_id") else None

        # Get the current time in the guild's timezone
        current_time = now.strftime('%Y-%m-%d %H:%M:%S')

        embed = discord.Embed(
            title=_("🌦️ RandomWeather Settings"),
            color=embed_color
        )
        embed.add_field(name=_("🔄 Refresh Mode:"), value="⏱️ Interval: {} seconds".format(refresh_interval) if refresh_interval else "🕒 Military Time: {}".format(refresh_time) if refresh_time else "❌ Not set", inline=True)
        embed.add_field(name=_("⏳ Time Until Next Refresh:"), value=time_until_next_refresh_str, inline=True)
        embed.add_field(name=_("🕰️ Current Time:"), value=current_time, inline=True)
        embed.add_field(name=_("📢 Channel:"), value=channel.mention if channel else "❌ Not set", inline=True)
        embed.add_field(name=_("🏷️ Role Tagging:"), value="✅ Enabled" if guild_settings.get("tag_role") else "❌ Disabled", inline=True)
        embed.add_field(name=_("🔖 Tag Role:"), value=role.name if role else "❌ Not set", inline=True)
        embed.add_field(name=_("🎨 Embed Color:"), value=str(embed_color), inline=True)
        embed.add_field(name=_("📜 Footer:"), value="✅ Enabled" if guild_settings.get("show_footer") else "❌ Disabled", inline=True)
        embed.add_field(name=_("🌱 Current Season:"), value=current_season, inline=True)

        await ctx.send(embed=embed)

    @rweather.command(name="force")
    @commands.admin_or_permissions(administrator=True)
    async def force_post(self, ctx: commands.Context) -> None:
        """Force post a weather update to the configured channel immediately."""
        guild_settings = await self.config.guild(ctx.guild).all()
        channel_id = guild_settings.get("channel_id")
        if not channel_id:
            await ctx.send("No channel configured for weather updates.")
            return
        try:
            await self._post_weather_update(ctx.guild.id, guild_settings, is_forced=True)
            await ctx.send("Weather update posted.")
        except Exception as e:
            logging.error(f"Error in force post: {e}")
            await ctx.send(f"Failed to post weather update: {e}")

    async def _post_weather_update(
        self, 
        guild_id: int, 
        guild_settings: Dict[str, Any], 
        scheduled_time: Optional[float] = None, 
        is_forced: bool = False
    ) -> None:
        """Post a weather update for a guild.
        
        Parameters
        ----------
        guild_id: int
            The ID of the guild to post the update for
        guild_settings: Dict[str, Any]
            The guild's settings dictionary
        scheduled_time: Optional[float]
            The scheduled time for this post (timestamp). If not provided, uses now.
        is_forced: bool
            Whether this is a forced post
        """
        try:
            channel = self.bot.get_channel(guild_settings.get("channel_id"))
            if not channel:
                return
            
            time_zone = guild_settings.get("time_zone") or "UTC"
            tz = pytz.timezone(time_zone)
            now = datetime.now(tz)
            
            # For forced posts, we want to use the current time
            # For scheduled posts, we use the scheduled time
            update_time = now if is_forced else (
                datetime.fromtimestamp(scheduled_time, tz) if scheduled_time 
                else now
            )
            
            update_settings = guild_settings.copy()
            update_settings["time_zone"] = time_zone
            data = generate_weather(time_zone=time_zone)
            embed = create_weather_embed(data, update_settings)
            
            content = None
            if guild_settings.get("tag_role"):
                role_id = guild_settings.get("role_id")
                if role_id:
                    content = f"<@&{role_id}>"
            
            await channel.send(content=content, embed=embed)
            
            # Update the last refresh time
            await self.config.guild(self.bot.get_guild(guild_id)).last_refresh.set(update_time.timestamp())
            write_last_posted()
            
        except Exception as e:
            logging.error(f"Error posting weather update for guild {guild_id}: {e}")
