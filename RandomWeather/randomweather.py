import random
import discord  # Edited by Taako
from redbot.core import commands, Config  # Edited by Taako
import asyncio  # Edited by Taako
from datetime import datetime, timedelta  # Edited by Taako
import pytz  # Edited by Taako
from redbot.core.utils.chat_formatting import humanize_list  # Edited by Taako

try:
    from .dashboard_integration import register_dashboard_settings  # Edited by Taako
    AAA3A_AVAILABLE = True
except ImportError:
    register_dashboard_settings = None  # Edited by Taako
    AAA3A_AVAILABLE = False  # Edited by Taako

class WeatherCog(commands.Cog):
    """A cog for generating random daily weather."""  # Edited by Taako

    # Edited by Taako
    def __init__(self, bot):
        self._bot = bot  # Store the bot instance
        self._current_weather = self._generate_weather()  # Generate initial weather
        self._refresh_task = None  # Task for automatic weather refresh

        # Persistent storage using Config
        self.config = Config.get_conf(self, identifier=1234567890, force_registration=True)  # Edited by Taako
        default_guild = {
            "role_id": None,  # Role ID for tagging
            "channel_id": None,  # Channel ID for updates
            "tag_role": False,  # Whether to tag the role
            "refresh_interval": None,  # Refresh interval in seconds
            "refresh_time": "0000",  # Default to military time 00:00 (midnight)
            "time_zone": "America/Chicago",  # Default to Central Time (America/Chicago)
            "show_footer": True,  # Whether to show the footer in embeds
        }
        self.config.register_guild(**default_guild)

        # Register settings for the AAA3A Dashboard Cog if available
        if AAA3A_AVAILABLE:
            try:
                register_dashboard_settings(self)
                bot.logger.info("Dashboard settings registered successfully for RandomWeather.")  # Debug log
            except Exception as e:
                bot.logger.error(f"Failed to register dashboard settings for RandomWeather: {e}")  # Debug log

    def _generate_weather(self):
        """Generate realistic random weather."""
        # Edited by Taako
        conditions = random.choice(["Clear sky", "Partly cloudy", "Overcast", "Rainy", "Stormy", "Snowy"])

        # Define temperature ranges based on conditions
        if conditions in ["Clear sky", "Partly cloudy"]:
            temperature = random.randint(70, 100)  # Warmer weather
        elif conditions in ["Overcast", "Rainy"]:
            temperature = random.randint(50, 80)  # Cooler weather
        elif conditions == "Stormy":
            temperature = random.randint(60, 85)  # Moderate temperature
        elif conditions == "Snowy":
            temperature = random.randint(20, 40)  # Cold weather
        else:
            temperature = random.randint(30, 100)  # Default fallback

        # Feels like temperature with a slight variation
        feels_like = temperature + random.randint(-3, 3)

        # Wind speed and direction
        if conditions == "Stormy":
            wind_speed = round(random.uniform(15.0, 40.0), 1)  # Strong winds
        elif conditions in ["Rainy", "Snowy"]:
            wind_speed = round(random.uniform(5.0, 20.0), 1)  # Moderate winds
        else:
            wind_speed = round(random.uniform(0.5, 10.0), 1)  # Light winds
        wind_direction = random.choice(["N", "NE", "E", "SE", "S", "SW", "W", "NW"])

        # Pressure
        if conditions == "Stormy":
            pressure = random.randint(950, 1000)  # Low pressure
        elif conditions in ["Rainy", "Snowy"]:
            pressure = random.randint(1000, 1020)  # Moderate pressure
        else:
            pressure = random.randint(1020, 1050)  # High pressure

        # Humidity
        if conditions in ["Rainy", "Stormy", "Snowy"]:
            humidity = random.randint(70, 100)  # High humidity
        else:
            humidity = random.randint(20, 60)  # Low to moderate humidity

        # Visibility
        if conditions == "Clear sky":
            visibility = round(random.uniform(5.0, 6.2), 1)  # High visibility
        elif conditions in ["Partly cloudy", "Overcast"]:
            visibility = round(random.uniform(3.0, 5.0), 1)  # Moderate visibility
        elif conditions in ["Rainy", "Stormy"]:
            visibility = round(random.uniform(0.5, 3.0), 1)  # Low visibility
        elif conditions == "Snowy":
            visibility = round(random.uniform(0.2, 1.5), 1)  # Very low visibility
        else:
            visibility = round(random.uniform(0.5, 6.2), 1)  # Default fallback

        return {
            "temperature": f"{temperature}°F",
            "feels_like": f"{feels_like}°F",
            "conditions": conditions,
            "wind": f"{wind_speed} mph {wind_direction}",
            "pressure": f"{pressure} hPa",
            "humidity": f"{humidity}%",
            "visibility": f"{visibility} miles",  # Updated to miles
        }

    def _get_weather_icon(self, condition):
        """Get an icon URL based on the weather condition."""
        # Edited by Taako
        icons = {
            "Clear sky": "https://cdn-icons-png.flaticon.com/512/869/869869.png",
            "Partly cloudy": "https://cdn-icons-png.flaticon.com/512/1146/1146869.png",
            "Overcast": "https://cdn-icons-png.flaticon.com/512/414/414825.png",
            "Rainy": "https://cdn-icons-png.flaticon.com/512/1163/1163626.png",
            "Stormy": "https://cdn-icons-png.flaticon.com/512/4668/4668778.png",  # Updated icon for Stormy
            "Snowy": "https://cdn-icons-png.flaticon.com/512/642/642102.png",
        }
        return icons.get(condition, "https://cdn-icons-png.flaticon.com/512/869/869869.png")  # Default icon

    def _create_weather_embed(self, weather_data):
        """Create a Discord embed for the weather data."""
        # Edited by Taako
        icon_url = self._get_weather_icon(weather_data["conditions"])
        embed = discord.Embed(
            title="🌤️ Today's Weather", 
            color=discord.Color.red()  # Set embed color to red
        )
        embed.add_field(name="🌡️ Temperature", value=weather_data["temperature"], inline=True)
        embed.add_field(name="🌡️ Feels Like", value=weather_data["feels_like"], inline=True)
        embed.add_field(name="🌥️ Conditions", value=weather_data["conditions"], inline=False)
        embed.add_field(name="💨 Wind", value=weather_data["wind"], inline=True)
        embed.add_field(name="💧 Humidity", value=weather_data["humidity"], inline=True)
        embed.add_field(name="👀 Visibility", value=weather_data["visibility"], inline=True)
        embed.set_thumbnail(url=icon_url)  # Add a weather-specific icon

        # Add footer if enabled
        if weather_data.get("show_footer", True):  # Default to True if not set
            embed.set_footer(text="RandomWeather by Taako", icon_url="https://cdn-icons-png.flaticon.com/512/869/869869.png")
        
        return embed

    async def _refresh_weather_task(self, guild_id):
        """Background task to refresh weather at the set interval or specific time."""
        # Edited by Taako
        while True:
            guild_settings = await self.config.guild_from_id(guild_id).all()
            refresh_interval = guild_settings["refresh_interval"]
            refresh_time = guild_settings["refresh_time"]
            time_zone = guild_settings["time_zone"]
            channel_id = guild_settings["channel_id"]
            role_id = guild_settings["role_id"]
            tag_role = guild_settings["tag_role"]

            if not channel_id:
                break

            if refresh_interval:
                await asyncio.sleep(refresh_interval)
            elif refresh_time:
                now = datetime.now(pytz.timezone(time_zone))
                target_time = datetime.strptime(refresh_time, "%H%M").replace(
                    tzinfo=pytz.timezone(time_zone)
                )
                if now > target_time:
                    target_time += timedelta(days=1)
                await asyncio.sleep((target_time - now).total_seconds())
            else:
                break

            channel = self._bot.get_channel(channel_id)
            if channel:
                self._current_weather = self._generate_weather()  # Generate new weather data
                embed = self._create_weather_embed(self._current_weather)
                role_mention = f"<@&{role_id}>" if role_id and tag_role else ""
                await channel.send(content=role_mention, embed=embed)

    @commands.group(name="rweather", invoke_without_command=True)
    async def rweather(self, ctx):
        """Main rweather command."""
        # Edited by Taako
        if ctx.invoked_subcommand is None:
            await ctx.send_help(ctx.command)  # Show the help menu if no subcommand is provided

    @rweather.command()
    async def refresh(self, ctx):
        """Refresh the weather for the day."""
        # Edited by Taako
        self._current_weather = self._generate_weather()
        guild_settings = await self.config.guild(ctx.guild).all()
        embed = self._create_weather_embed(self._current_weather, guild_id=ctx.guild.id)
        role_mention = f"<@&{guild_settings['role_id']}>" if guild_settings["role_id"] and guild_settings["tag_role"] else ""
        channel_id = guild_settings["channel_id"]
        if channel_id:
            channel = self._bot.get_channel(channel_id)
            if channel:
                await channel.send(content=role_mention, embed=embed)
                await ctx.send(f"Weather update sent to {channel.mention}.")
            else:
                await ctx.send("The set channel is invalid. Please set a valid channel.")
        else:
            await ctx.send(embed=embed)

    @rweather.command()
    async def role(self, ctx, role: discord.Role):
        """Set the role to be tagged for weather updates."""
        # Edited by Taako
        await self.config.guild(ctx.guild).role_id.set(role.id)
        await ctx.send(f"Weather updates will now tag the role: {role.name}")

    @rweather.command()
    async def toggle(self, ctx):
        """Toggle whether the role should be tagged in weather updates."""
        # Edited by Taako
        tag_role = await self.config.guild(ctx.guild).tag_role()
        await self.config.guild(ctx.guild).tag_role.set(not tag_role)
        status = "enabled" if not tag_role else "disabled"
        await ctx.send(f"Role tagging has been {status}.")

    @rweather.command()
    async def channel(self, ctx, channel: discord.TextChannel):
        """Set the channel for weather updates."""
        # Edited by Taako
        await self.config.guild(ctx.guild).channel_id.set(channel.id)
        await ctx.send(f"Weather updates will now be sent to: {channel.mention}")

    @rweather.command(name="setrefresh")
    async def set_refresh(self, ctx, value: str):
        """Set how often the weather should refresh or specify a time (e.g., `10m` or `1830`)."""
        # Edited by Taako
        guild_settings = await self.config.guild(ctx.guild).all()
        is_time_interval = guild_settings["refresh_interval"] is not None

        if is_time_interval:
            # Handle time interval (e.g., 10m, 1h)
            time_units = {"s": 1, "m": 60, "h": 3600, "d": 86400}
            try:
                unit = value[-1]
                interval = int(value[:-1])
                if unit not in time_units:
                    raise ValueError("Invalid time unit.")
                refresh_interval = interval * time_units[unit]
                await self.config.guild(ctx.guild).refresh_interval.set(refresh_interval)
                await self.config.guild(ctx.guild).refresh_time.set(None)
                await ctx.send(f"Weather will now refresh every {value}.")
            except (ValueError, IndexError):
                await ctx.send("Invalid format. Use a number followed by s (seconds), m (minutes), h (hours), or d (days).")
        else:
            # Handle specific time in military format (e.g., 1830)
            if value.isdigit() and len(value) == 4:
                await self.config.guild(ctx.guild).refresh_time.set(value)
                await self.config.guild(ctx.guild).refresh_interval.set(None)
                await ctx.send(f"Weather will now refresh daily at {value} (military time).")
            else:
                await ctx.send("Invalid format. Use a valid military time (e.g., 1830).")

        # Restart the refresh task
        if self._refresh_task:
            self._refresh_task.cancel()
        self._refresh_task = self._bot.loop.create_task(self._refresh_weather_task(ctx.guild.id))

    @rweather.command(name="settimezone")
    async def set_timezone(self, ctx, time_zone: str = None):
        """Set the time zone for weather updates (e.g., `UTC`, `America/New_York`)."""
        # Edited by Taako
        if not time_zone:
            await ctx.send(
                "Please provide a valid time zone using the correct syntax (e.g., `UTC`, `America/New_York`).\n"
                "You can view the full list of time zones here: https://en.wikipedia.org/wiki/List_of_tz_database_time_zones"
            )
            return

        if time_zone in pytz.all_timezones:
            await self.config.guild(ctx.guild).time_zone.set(time_zone)
            await ctx.send(f"Time zone set to {time_zone}.")
        else:
            await ctx.send(
                "Invalid time zone. Please provide a valid time zone using the correct syntax (e.g., `UTC`, `America/New_York`).\n"
                "You can view the full list of time zones here: https://en.wikipedia.org/wiki/List_of_tz_database_time_zones"
            )

    @rweather.command(name="info")
    async def info(self, ctx):
        """View the current settings for weather updates."""
        # Edited by Taako
        guild_settings = await self.config.guild(ctx.guild).all()
        show_footer = await self.config.guild(ctx.guild).get_raw("show_footer", default=True)
        embed = discord.Embed(
            title="🌦️ RandomWeather Settings",
            color=discord.Color.blue()  # Set embed color to blue
        )
        embed.add_field(
            name="📅 Refresh Mode",
            value=(
                f"**Interval**: {guild_settings['refresh_interval']} seconds"
                if guild_settings["refresh_interval"]
                else f"**Time**: {guild_settings['refresh_time']} (military time)"
            ),
            inline=False,
        )
        embed.add_field(
            name="🌍 Time Zone",
            value=guild_settings["time_zone"],
            inline=False,
        )
        embed.add_field(
            name="📢 Channel",
            value=(
                f"<#{guild_settings['channel_id']}>" if guild_settings["channel_id"] else "Not set"
            ),
            inline=False,
        )
        embed.add_field(
            name="🔔 Role Tagging",
            value="Enabled" if guild_settings["tag_role"] else "Disabled",
            inline=True,
        )
        embed.add_field(
            name="👥 Tag Role",
            value=(
                f"<@&{guild_settings['role_id']}>" if guild_settings["role_id"] else "Not set"
            ),
            inline=True,
        )
        embed.add_field(
            name="📄 Footer",
            value="Enabled" if show_footer else "Disabled",
            inline=False,
        )
        embed.set_footer(text="RandomWeather by Taako")
        await ctx.send(embed=embed)

    @rweather.command(name="togglefooter")
    async def toggle_footer(self, ctx):
        """Toggle the footer on or off for the weather embed."""
        # Edited by Taako
        show_footer = await self.config.guild(ctx.guild).get_raw("show_footer", default=True)
        new_state = not show_footer
        await self.config.guild(ctx.guild).set_raw("show_footer", value=new_state)
        status = "enabled" if new_state else "disabled"
        await ctx.send(f"The footer has been {status} for the weather embed.")

def setup(bot):
    # Edited by Taako
    bot.add_cog(WeatherCog(bot))
