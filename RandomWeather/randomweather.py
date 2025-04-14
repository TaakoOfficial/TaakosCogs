from redbot.core import commands, Config
from redbot.core.i18n import Translator  # Edited by Taako
from discord.ext import tasks  # Edited by Taako
import discord
import pytz
from datetime import datetime, timedelta
from typing import Optional
from .weather_utils import generate_weather, create_weather_embed
import logging

_ = Translator("RandomWeather", __file__)  # Edited by Taako

class WeatherCog(commands.Cog):
    """A cog for generating random daily weather updates."""

    __author__ = ["Taako"]
    __version__ = "2.0.0"

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.config = Config.get_conf(self, identifier=1234567890, force_registration=True)
        default_guild = {
            "role_id": None,
            "channel_id": None,
            "tag_role": False,
            "refresh_interval": None,
            "refresh_time": "0000",
            "time_zone": "America/Chicago",
            "show_footer": True,
            "embed_color": 0xFF0000,
            "last_refresh": 0,
        }
        self.config.register_guild(**default_guild)
        self.bot.loop.create_task(self._startup_debug())
        self._refresh_weather_loop.start()

    async def _startup_debug(self):
        """Log debug information when the cog is loaded."""
        await self.bot.wait_until_ready()
        logging.info(f"WeatherCog loaded in {len(self.bot.guilds)} guilds.")

    @tasks.loop(minutes=1)
    async def _refresh_weather_loop(self):
        """Task loop to post daily weather updates."""
        all_guilds = await self.config.all_guilds()
        for guild_id, guild_settings in all_guilds.items():
            refresh_interval = guild_settings.get("refresh_interval")
            refresh_time = guild_settings.get("refresh_time")

            try:
                if refresh_interval:
                    last_refresh = guild_settings.get("last_refresh", 0)
                    next_post_time = datetime.fromtimestamp(last_refresh) + timedelta(seconds=refresh_interval)
                elif refresh_time:
                    time_zone = guild_settings.get("time_zone", "UTC")
                    tz = pytz.timezone(time_zone)
                    now = datetime.now(tz)
                    target_time = datetime.strptime(refresh_time, "%H%M").replace(
                        tzinfo=tz, year=now.year, month=now.month, day=now.day
                    )
                    if now >= target_time:
                        target_time += timedelta(days=1)
                    next_post_time = target_time
                else:
                    next_post_time = datetime.now().replace(hour=0, minute=0, second=0) + timedelta(days=1)

                if datetime.now() >= next_post_time:
                    await self._post_weather_update(guild_id, guild_settings)
            except Exception as e:
                logging.error(f"Error in weather update loop for guild {guild_id}: {e}")

    async def _post_weather_update(self, guild_id: int, guild_settings: dict):
        """Post a weather update to the configured channel for a specific guild."""
        channel_id = guild_settings.get("channel_id")
        if not channel_id:
            logging.debug(f"No channel configured for guild {guild_id}. Skipping.")
            return

        time_zone = guild_settings.get("time_zone", "UTC")
        weather_data = generate_weather(time_zone)
        embed = create_weather_embed(weather_data, guild_settings)

        channel = self.bot.get_channel(channel_id)
        if channel:
            await channel.send(embed=embed)
            await self.config.guild_from_id(guild_id).last_refresh.set(datetime.now().timestamp())
            logging.info(f"Weather update sent to channel {channel.name} in guild {guild_id}.")
        else:
            logging.warning(f"Channel {channel_id} not found for guild {guild_id}.")

    @_refresh_weather_loop.before_loop
    async def before_refresh_weather_loop(self):
        """Wait until the bot is ready before starting the loop."""
        await self.bot.wait_until_ready()

    @_refresh_weather_loop.error
    async def _refresh_weather_loop_error(self, error: Exception):
        """Handle errors in the weather update loop."""
        logging.error(f"Error in weather update loop: {error}")

    @commands.group(name="rweather", invoke_without_command=True)
    async def rweather(self, ctx: commands.Context):
        """Main command group for RandomWeather."""
        if ctx.invoked_subcommand is None:
            await ctx.send_help(ctx.command)

    @rweather.command(name="setchannel")
    async def set_channel(self, ctx: commands.Context, channel: discord.TextChannel):
        """Set the channel for weather updates."""
        await self.config.guild(ctx.guild).channel_id.set(channel.id)
        await ctx.send(f"Weather updates will now be sent to: {channel.mention}")

    @rweather.command(name="setrole")
    async def set_role(self, ctx: commands.Context, role: discord.Role):
        """Set the role to be tagged for weather updates."""
        await self.config.guild(ctx.guild).role_id.set(role.id)
        await ctx.send(f"Weather updates will now tag the role: {role.name}")

    @rweather.command(name="toggle_role")
    async def toggle_role(self, ctx: commands.Context):
        """Toggle whether the role should be tagged in weather updates."""
        tag_role = await self.config.guild(ctx.guild).tag_role()
        await self.config.guild(ctx.guild).tag_role.set(not tag_role)
        status = "enabled" if not tag_role else "disabled"
        await ctx.send(f"Role tagging has been {status}.")

    @rweather.command(name="setrefresh")
    async def set_refresh(self, ctx: commands.Context, value: str):
        """Set how often the weather should refresh or specify a time (e.g., `10m` or `1830`)."""
        time_units = {"s": 1, "m": 60, "h": 3600, "d": 86400}

        if value.isdigit() and len(value) == 4:
            await self.config.guild(ctx.guild).refresh_time.set(value)
            await self.config.guild(ctx.guild).refresh_interval.set(None)
            await ctx.send(f"Weather will now refresh daily at {value} (military time).")
        elif value[-1] in time_units:
            try:
                unit = value[-1]
                interval = int(value[:-1])
                refresh_interval = interval * time_units[unit]
                await self.config.guild(ctx.guild).refresh_interval.set(refresh_interval)
                await self.config.guild(ctx.guild).refresh_time.set(None)
                await ctx.send(f"Weather will now refresh every {value}.")
            except (ValueError, IndexError):
                await ctx.send("Invalid format. Use a number followed by s (seconds), m (minutes), h (hours), or d (days).")
        else:
            await ctx.send("Invalid format. Use a valid military time (e.g., 1830) or an interval (e.g., 10m, 1h).")

    @rweather.command(name="set_embed_color")
    async def set_embed_color(self, ctx: commands.Context, color: discord.Color):
        """Set the embed color for weather updates dynamically."""
        await self.config.guild(ctx.guild).embed_color.set(color.value)
        await ctx.send(f"Embed color updated to: {color}")

    @rweather.command(name="set_time_zone")
    async def set_time_zone(self, ctx: commands.Context, time_zone: str):
        """Set the time zone for weather updates dynamically."""
        if time_zone in pytz.all_timezones:
            await self.config.guild(ctx.guild).time_zone.set(time_zone)
            await ctx.send(f"Time zone updated to: {time_zone}")
        else:
            await ctx.send("Invalid time zone. Please provide a valid time zone.")

    @rweather.command(name="info")
    async def info(self, ctx: commands.Context):
        """View the current settings for weather updates."""
        guild_settings = await self.config.guild(ctx.guild).all()
        embed_color = discord.Color(guild_settings.get("embed_color", 0xFF0000))
        time_zone = guild_settings.get("time_zone", "UTC")
        refresh_interval = guild_settings.get("refresh_interval")
        refresh_time = guild_settings.get("refresh_time")

        embed = discord.Embed(
            title=_("🌦️ RandomWeather Settings"),
            color=embed_color
        )
        embed.add_field(name=_("Time Zone"), value=time_zone, inline=False)
        embed.add_field(name=_("Refresh Interval"), value=f"{refresh_interval} seconds" if refresh_interval else _("Not set"), inline=False)
        embed.add_field(name=_("Refresh Time"), value=refresh_time if refresh_time else _("Not set"), inline=False)
        embed.add_field(name=_("Embed Color"), value=str(embed_color), inline=False)
        await ctx.send(embed=embed)
