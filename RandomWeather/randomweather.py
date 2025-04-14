from redbot.core import commands, Config
from typing import Optional, Union  # Edited by Taako
import discord
import pytz
from datetime import datetime, timedelta
from .weather_utils import generate_weather, create_weather_embed
import logging
from redbot.core.i18n import Translator  # Edited by Taako

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
        self.bot.loop.create_task(self._startup_debug())  # Debug helper
        self._refresh_weather_loop.start()

    async def _startup_debug(self):
        """Log debug information when the cog is loaded."""  # Edited by Taako
        await self.bot.wait_until_ready()
        logging.info(f"WeatherCog loaded in {len(self.bot.guilds)} guilds.")  # Edited by Taako

    @tasks.loop(minutes=1)
    async def _refresh_weather_loop(self):
        """Task loop to post daily weather updates."""  # Edited by Taako
        all_guilds = await self.config.all_guilds()  # Edited by Taako
        for guild_id, guild_settings in all_guilds.items():
            refresh_interval = guild_settings.get("refresh_interval")  # Edited by Taako
            refresh_time = guild_settings.get("refresh_time")  # Edited by Taako

            try:
                if refresh_interval:
                    last_refresh = guild_settings.get("last_refresh", 0)  # Edited by Taako
                    next_post_time = datetime.fromtimestamp(last_refresh) + timedelta(seconds=refresh_interval)  # Edited by Taako
                elif refresh_time:
                    time_zone = guild_settings.get("time_zone", "UTC")  # Edited by Taako
                    tz = pytz.timezone(time_zone)  # Edited by Taako
                    now = datetime.now(tz)  # Edited by Taako
                    target_time = datetime.strptime(refresh_time, "%H%M").replace(
                        tzinfo=tz, year=now.year, month=now.month, day=now.day
                    )  # Edited by Taako
                    if now >= target_time:
                        target_time += timedelta(days=1)  # Edited by Taako
                    next_post_time = target_time  # Edited by Taako
                else:
                    next_post_time = datetime.now().replace(hour=0, minute=0, second=0) + timedelta(days=1)  # Edited by Taako

                if datetime.now() >= next_post_time:
                    await self._post_weather_update(guild_id, guild_settings)  # Edited by Taako
            except Exception as e:
                logging.error(f"Error in weather update loop for guild {guild_id}: {e}")  # Edited by Taako

    async def _post_weather_update(self, guild_id: int, guild_settings: dict):
        """Post a weather update to the configured channel for a specific guild."""  # Edited by Taako
        channel_id = guild_settings.get("channel_id")  # Edited by Taako
        if not channel_id:
            logging.debug(f"No channel configured for guild {guild_id}. Skipping.")  # Edited by Taako
            return

        time_zone = guild_settings.get("time_zone", "UTC")  # Edited by Taako
        weather_data = generate_weather(time_zone)  # Edited by Taako
        embed = create_weather_embed(weather_data, guild_settings)  # Edited by Taako

        channel = self.bot.get_channel(channel_id)  # Edited by Taako
        if channel:
            await channel.send(embed=embed)  # Edited by Taako
            await self.config.guild_from_id(guild_id).last_refresh.set(datetime.now().timestamp())  # Edited by Taako
            logging.info(f"Weather update sent to channel {channel.name} in guild {guild_id}.")  # Edited by Taako
        else:
            logging.warning(f"Channel {channel_id} not found for guild {guild_id}.")  # Edited by Taako

    @_refresh_weather_loop.before_loop
    async def before_refresh_weather_loop(self):
        """Wait until the bot is ready before starting the loop."""  # Edited by Taako
        await self.bot.wait_until_ready()  # Edited by Taako

    @_refresh_weather_loop.error
    async def _refresh_weather_loop_error(self, error: Exception):
        """Handle errors in the weather update loop."""  # Edited by Taako
        logging.error(f"Error in weather update loop: {error}")  # Edited by Taako

    @commands.group(name="rweather", invoke_without_command=True)
    async def rweather(self, ctx: commands.Context):
        """Main command group for RandomWeather."""  # Edited by Taako
        if ctx.invoked_subcommand is None:
            await ctx.send_help(ctx.command)  # Edited by Taako

    @rweather.command(name="setchannel")
    async def set_channel(self, ctx: commands.Context, channel: discord.TextChannel):
        """Set the channel for weather updates."""  # Edited by Taako
        await self.config.guild(ctx.guild).channel_id.set(channel.id)  # Edited by Taako
        await ctx.send(f"Weather updates will now be sent to: {channel.mention}")  # Edited by Taako

    @rweather.command(name="setrole")
    async def set_role(self, ctx: commands.Context, role: discord.Role):
        """Set the role to be tagged for weather updates."""  # Edited by Taako
        await self.config.guild(ctx.guild).role_id.set(role.id)  # Edited by Taako
        await ctx.send(f"Weather updates will now tag the role: {role.name}")  # Edited by Taako

    @rweather.command(name="toggle_role")
    async def toggle_role(self, ctx: commands.Context):
        """Toggle whether the role should be tagged in weather updates."""  # Edited by Taako
        tag_role = await self.config.guild(ctx.guild).tag_role()  # Edited by Taako
        await self.config.guild(ctx.guild).tag_role.set(not tag_role)  # Edited by Taako
        status = "enabled" if not tag_role else "disabled"  # Edited by Taako
        await ctx.send(f"Role tagging has been {status}.")  # Edited by Taako

    @rweather.command(name="setrefresh")
    async def set_refresh(self, ctx: commands.Context, value: str):
        """Set how often the weather should refresh or specify a time (e.g., `10m` or `1830`)."""  # Edited by Taako
        time_units = {"s": 1, "m": 60, "h": 3600, "d": 86400}  # Edited by Taako

        if value.isdigit() and len(value) == 4:  # Edited by Taako
            await self.config.guild(ctx.guild).refresh_time.set(value)  # Edited by Taako
            await self.config.guild(ctx.guild).refresh_interval.set(None)  # Edited by Taako
            await ctx.send(f"Weather will now refresh daily at {value} (military time).")  # Edited by Taako
        elif value[-1] in time_units:  # Edited by Taako
            try:
                unit = value[-1]  # Edited by Taako
                interval = int(value[:-1])  # Edited by Taako
                refresh_interval = interval * time_units[unit]  # Edited by Taako
                await self.config.guild(ctx.guild).refresh_interval.set(refresh_interval)  # Edited by Taako
                await self.config.guild(ctx.guild).refresh_time.set(None)  # Edited by Taako
                await ctx.send(f"Weather will now refresh every {value}.")  # Edited by Taako
            except (ValueError, IndexError):
                await ctx.send("Invalid format. Use a number followed by s (seconds), m (minutes), h (hours), or d (days).")  # Edited by Taako
        else:
            await ctx.send("Invalid format. Use a valid military time (e.g., 1830) or an interval (e.g., 10m, 1h).")  # Edited by Taako

    @rweather.command(name="set_embed_color")
    async def set_embed_color(self, ctx: commands.Context, color: discord.Color):
        """Set the embed color for weather updates dynamically."""  # Edited by Taako
        await self.config.guild(ctx.guild).embed_color.set(color.value)  # Edited by Taako
        await ctx.send(f"Embed color updated to: {color}")  # Edited by Taako

    @rweather.command(name="set_time_zone")
    async def set_time_zone(self, ctx: commands.Context, time_zone: str):
        """Set the time zone for weather updates dynamically."""  # Edited by Taako
        if time_zone in pytz.all_timezones:  # Edited by Taako
            await self.config.guild(ctx.guild).time_zone.set(time_zone)  # Edited by Taako
            await ctx.send(f"Time zone updated to: {time_zone}")  # Edited by Taako
        else:
            await ctx.send("Invalid time zone. Please provide a valid time zone.")  # Edited by Taako

    @rweather.command(name="info")
    async def info(self, ctx: commands.Context):
        """View the current settings for weather updates."""  # Edited by Taako
        guild_settings = await self.config.guild(ctx.guild).all()  # Edited by Taako
        embed_color = discord.Color(guild_settings.get("embed_color", 0xFF0000))  # Edited by Taako
        time_zone = guild_settings.get("time_zone", "UTC")  # Edited by Taako
        refresh_interval = guild_settings.get("refresh_interval")  # Edited by Taako
        refresh_time = guild_settings.get("refresh_time")  # Edited by Taako

        embed = discord.Embed(
            title=_("🌦️ RandomWeather Settings"),  # Edited by Taako
            color=embed_color  # Edited by Taako
        )  # Edited by Taako
        embed.add_field(name=_("Time Zone"), value=time_zone, inline=False)  # Edited by Taako
        embed.add_field(name=_("Refresh Interval"), value=f"{refresh_interval} seconds" if refresh_interval else _("Not set"), inline=False)  # Edited by Taako
        embed.add_field(name=_("Refresh Time"), value=refresh_time if refresh_time else _("Not set"), inline=False)  # Edited by Taako
        embed.add_field(name=_("Embed Color"), value=str(embed_color), inline=False)  # Edited by Taako
        await ctx.send(embed=embed)  # Edited by Taako
