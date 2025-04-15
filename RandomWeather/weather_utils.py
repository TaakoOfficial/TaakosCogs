"""Weather generation utilities for the RandomWeather cog."""
from typing import Dict
import random
import discord
import datetime

def generate_weather(time_zone: str) -> Dict[str, str]:
    """Generate random weather data."""
    try:
        import pytz
        tz = pytz.timezone(time_zone)
        current_time = datetime.datetime.now(tz)
    except ImportError:
        current_time = datetime.datetime.now()

    # Rest of weather generation code...
    weather_conditions = [
        "Sunny ☀️", "Partly Cloudy 🌤️", "Cloudy ☁️", "Rainy 🌧️", 
        "Thunderstorm ⛈️", "Snowy 🌨️", "Windy 🌬️", "Foggy 🌫️"
    ]
    
    temp_f = random.randint(0, 100)
    temp_c = round((temp_f - 32) * 5/9, 1)
    humidity = random.randint(30, 90)
    wind_speed = random.randint(0, 30)
    condition = random.choice(weather_conditions)
    
    return {
        "temperature_f": f"{temp_f}°F",
        "temperature_c": f"{temp_c}°C",
        "humidity": f"{humidity}%",
        "wind_speed": f"{wind_speed} mph",
        "condition": condition,
        "time": current_time.strftime("%I:%M %p")
    }

def create_weather_embed(weather_data: Dict[str, str], guild_settings: Dict[str, any]) -> discord.Embed:
    """Create a Discord embed for weather data."""
    embed = discord.Embed(
        title="🌦️ Current Weather",
        color=discord.Color(guild_settings.get("embed_color", 0xFF0000))
    )
    
    embed.add_field(
        name="Condition",
        value=weather_data["condition"],
        inline=True
    )
    embed.add_field(
        name="Temperature", 
        value=f"{weather_data['temperature_f']} ({weather_data['temperature_c']})",
        inline=True
    )
    embed.add_field(
        name="Humidity",
        value=weather_data["humidity"],
        inline=True
    )
    embed.add_field(
        name="Wind Speed",
        value=weather_data["wind_speed"],
        inline=True
    )
    embed.add_field(
        name="Time",
        value=weather_data["time"],
        inline=True
    )
    
    if guild_settings.get("show_footer", True):
        embed.set_footer(text="🎲 Weather conditions are randomly generated")
    
    return embed
