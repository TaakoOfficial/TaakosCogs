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

    weather_conditions = [
        "Sunny ☀️", "Partly Cloudy 🌤️", "Cloudy ☁️", "Rainy 🌧️", 
        "Thunderstorm ⛈️", "Snowy 🌨️", "Windy 🌬️", "Foggy 🌫️"
    ]
    
    temp_f = random.randint(0, 100)
    feels_like = temp_f + random.randint(-5, 5)  # Random variation for "feels like"
    temp_c = round((temp_f - 32) * 5/9, 1)
    humidity = random.randint(30, 90)
    wind_speed = random.randint(0, 30)
    visibility = round(random.uniform(0.5, 10.0), 1)
    condition = random.choice(weather_conditions)
    
    # Determine season based on month
    month = current_time.month
    if month in (3, 4, 5):
        season = "Spring 🌸"
    elif month in (6, 7, 8):
        season = "Summer ☀️"
    elif month in (9, 10, 11):
        season = "Fall 🍂"
    else:
        season = "Winter ❄️"
    
    return {
        "temperature_f": f"{temp_f}°F",
        "temperature_c": f"{temp_c}°C",
        "feels_like": f"{feels_like}°F",
        "humidity": f"{humidity}%",
        "wind_speed": f"{wind_speed} mph",
        "visibility": f"{visibility} miles",
        "condition": condition,
        "season": season,
        "time": current_time.strftime("%I:%M %p")
    }

def create_weather_embed(weather_data: Dict[str, str], guild_settings: Dict[str, any]) -> discord.Embed:
    """Create a Discord embed for weather data."""
    embed = discord.Embed(
        title="☀️ Today's Weather",
        color=discord.Color(guild_settings.get("embed_color", 0xFF0000))
    )
    
    # Temperature and Feels Like
    embed.add_field(
        name="🌡️ Temperature | 🌡️ Feels Like",
        value=f"{weather_data['temperature_f']} | {weather_data['feels_like']}",
        inline=False
    )
    
    # Conditions
    embed.add_field(
        name="☁️ Conditions",
        value=weather_data["condition"],
        inline=False
    )
    
    # Wind, Humidity, and Visibility
    embed.add_field(
        name="🌬️ Wind | 💧 Humidity | 👀 Visibility",
        value=f"{weather_data['wind_speed']} | {weather_data['humidity']} | {weather_data['visibility']}",
        inline=False
    )
    
    # Current Season
    embed.add_field(
        name="🍂 Current Season",
        value=weather_data["season"],
        inline=False
    )
    
    if guild_settings.get("show_footer", True):
        embed.set_footer(text="🎲 Weather conditions are randomly generated")
    
    return embed
