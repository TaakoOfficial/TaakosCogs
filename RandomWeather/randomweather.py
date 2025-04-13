import random
import discord  # Edited by Taako
from redbot.core import commands
import asyncio  # Edited by Taako

class WeatherCog(commands.Cog):
    """A cog for generating random daily weather."""
    
    # Edited by Taako
    def __init__(self, bot):
        self._bot = bot  # Store the bot instance
        self._current_weather = self._generate_weather()  # Generate initial weather
        self._role_id = None  # Role ID for tagging
        self._channel_id = None  # Channel ID for sending updates
        self._tag_role = False  # Whether to tag the role
        self._refresh_task = None  # Task for automatic weather refresh
        self._refresh_interval = None  # Refresh interval in seconds

    def _generate_weather(self):
        """Generate realistic random weather."""
        # Edited by Taako
        temperature = random.randint(30, 100)  # Temperature in °F
        feels_like = temperature + random.randint(-3, 3)  # Feels like temperature
        conditions = random.choice(["Clear sky", "Partly cloudy", "Overcast", "Rainy", "Stormy", "Snowy"])
        wind_speed = round(random.uniform(0.5, 20.0), 1)  # Wind speed in mph
        wind_direction = random.choice(["N", "NE", "E", "SE", "S", "SW", "W", "NW"])
        pressure = random.randint(980, 1050)  # Pressure in hPa
        humidity = random.randint(20, 100)  # Humidity in %
        dew_point = round(temperature - ((100 - humidity) / 5), 1)  # Dew point in °F

        # Adjust visibility based on conditions
        if conditions == "Clear sky":
            visibility = round(random.uniform(5.0, 6.2), 1)  # High visibility in miles
        elif conditions in ["Partly cloudy", "Overcast"]:
            visibility = round(random.uniform(3.1, 5.0), 1)  # Moderate visibility in miles
        elif conditions in ["Rainy", "Stormy"]:
            visibility = round(random.uniform(0.6, 3.1), 1)  # Low visibility in miles
        elif conditions == "Snowy":
            visibility = round(random.uniform(0.3, 1.9), 1)  # Very low visibility in miles
        else:
            visibility = round(random.uniform(0.6, 6.2), 1)  # Default fallback in miles

        return {
            "temperature": f"{temperature}°F",
            "feels_like": f"{feels_like}°F",
            "conditions": conditions,
            "wind": f"{wind_speed} mph {wind_direction}",
            "pressure": f"{pressure} hPa",
            "humidity": f"{humidity}%",
            "dew_point": f"{dew_point}°F",
            "visibility": f"{visibility} miles",  # Updated to miles
        }

    def _get_weather_icon(self, condition):
        """Get an icon URL based on the weather condition."""
        # Edited by Taako
        icons = {
            "Clear sky": "https://cdn-icons-png.flaticon.com/512/869/869869.png",
            "Partly cloudy": "https://cdn-icons-png.flaticon.com/512/1163/1163624.png",
            "Overcast": "https://cdn-icons-png.flaticon.com/512/414/414825.png",
            "Rainy": "https://cdn-icons-png.flaticon.com/512/1163/1163626.png",
            "Stormy": "https://cdn-icons-png.flaticon.com/512/1146/1146869.png",
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
        embed.add_field(name="🌡️ Pressure", value=weather_data["pressure"], inline=True)
        embed.add_field(name="💧 Humidity", value=weather_data["humidity"], inline=True)
        embed.add_field(name="🌡️ Dew Point", value=weather_data["dew_point"], inline=True)
        embed.add_field(name="👀 Visibility", value=weather_data["visibility"], inline=True)
        embed.set_thumbnail(url=icon_url)  # Add a weather-specific icon
        embed.set_footer(text="RandomWeather by Taako", icon_url="https://i.imgur.com/3ZQZ3cQ.png")
        return embed

    async def _refresh_weather_task(self):
        """Background task to refresh weather at the set interval."""
        # Edited by Taako
        while self._refresh_interval and self._channel_id:
            await asyncio.sleep(self._refresh_interval)
            channel = self._bot.get_channel(self._channel_id)
            if channel:
                embed = self._create_weather_embed(self._current_weather)
                role_mention = f"<@&{self._role_id}>" if self._role_id and self._tag_role else ""
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
        embed = self._create_weather_embed(self._current_weather)
        role_mention = f"<@&{self._role_id}>" if self._role_id and self._tag_role else ""
        if self._channel_id:
            channel = self._bot.get_channel(self._channel_id)
            if channel:
                await channel.send(content=role_mention, embed=embed)
                await ctx.send(f"Weather update sent to {channel.mention}.")
            else:
                await ctx.send("The set channel is invalid. Please set a valid channel.")
        else:
            await ctx.send(embed=embed)

    @rweather.command()
    async def role(self, ctx, role_id: int):
        """Set the role to be tagged for weather updates."""
        # Edited by Taako
        role = ctx.guild.get_role(role_id)
        if role:
            self._role_id = role_id
            await ctx.send(f"Weather updates will now tag the role: {role.name}")
        else:
            await ctx.send("Invalid role ID. Please provide a valid role ID.")

    @rweather.command()
    async def toggle(self, ctx):
        """Toggle whether the role should be tagged in weather updates."""
        # Edited by Taako
        self._tag_role = not self._tag_role
        status = "enabled" if self._tag_role else "disabled"
        await ctx.send(f"Role tagging has been {status}.")

    @rweather.command()
    async def channel(self, ctx, channel_id: int):
        """Set the channel for weather updates."""
        # Edited by Taako
        channel = self._bot.get_channel(channel_id)
        if channel:
            self._channel_id = channel_id
            await ctx.send(f"Weather updates will now be sent to: {channel.mention}")
        else:
            await ctx.send("Invalid channel ID. Please provide a valid channel ID.")

    @rweather.command(name="load")
    async def load_weather(self, ctx):
        """Manually load the current weather."""
        # Edited by Taako
        embed = self._create_weather_embed(self._current_weather)
        role_mention = f"<@&{self._role_id}>" if self._role_id and self._tag_role else ""
        if self._channel_id:
            channel = self._bot.get_channel(self._channel_id)
            if channel:
                await channel.send(content=role_mention, embed=embed)
                await ctx.send(f"Weather update sent to {channel.mention}.")
            else:
                await ctx.send("The set channel is invalid. Please set a valid channel.")
        else:
            await ctx.send(embed=embed)

    @rweather.command(name="setrefresh")
    async def set_refresh(self, ctx, interval: str):
        """Set how often the weather should refresh in the set channel."""
        # Edited by Taako
        time_units = {"s": 1, "m": 60, "h": 3600, "d": 86400}
        try:
            unit = interval[-1]
            value = int(interval[:-1])
            if unit not in time_units:
                raise ValueError("Invalid time unit.")
            self._refresh_interval = value * time_units[unit]
            if self._refresh_task:
                self._refresh_task.cancel()
            if self._refresh_interval > 0:
                self._refresh_task = self._bot.loop.create_task(self._refresh_weather_task())
                await ctx.send(f"Weather will now refresh every {interval}.")
            else:
                await ctx.send("Invalid interval. Please provide a positive value.")
        except (ValueError, IndexError):
            await ctx.send("Invalid format. Use a number followed by s (seconds), m (minutes), h (hours), or d (days).")

def setup(bot):
    # Edited by Taako
    bot.add_cog(WeatherCog(bot))
