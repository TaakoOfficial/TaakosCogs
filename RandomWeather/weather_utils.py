"""Weather generation utilities for the RandomWeather cog."""
from typing import Dict, List, Tuple
import random
import discord
import datetime
import math

def get_seasonal_ranges(month: int) -> Tuple[int, int, List[Tuple[str, float]]]:
    """Get temperature ranges and weighted conditions for the season."""
    # Spring (March-May)
    if month in (3, 4, 5):
        temp_range = (45, 75)
        conditions = [
            ("Sunny ☀️", 0.25),
            ("Partly Cloudy 🌤️", 0.3),
            ("Cloudy ☁️", 0.2),
            ("Rainy 🌧️", 0.15),
            ("Thunderstorm ⛈️", 0.05),
            ("Windy 🌬️", 0.03),
            ("Foggy 🌫️", 0.02)
        ]
    # Summer (June-August)
    elif month in (6, 7, 8):
        temp_range = (65, 95)
        conditions = [
            ("Sunny ☀️", 0.4),
            ("Partly Cloudy 🌤️", 0.3),
            ("Cloudy ☁️", 0.1),
            ("Thunderstorm ⛈️", 0.15),
            ("Windy 🌬️", 0.03),
            ("Foggy 🌫️", 0.02)
        ]
    # Fall (September-November)
    elif month in (9, 10, 11):
        temp_range = (40, 70)
        conditions = [
            ("Sunny ☀️", 0.2),
            ("Partly Cloudy 🌤️", 0.3),
            ("Cloudy ☁️", 0.25),
            ("Rainy 🌧️", 0.15),
            ("Windy 🌬️", 0.05),
            ("Foggy 🌫️", 0.05)
        ]
    # Winter (December-February)
    else:
        temp_range = (20, 45)
        conditions = [
            ("Sunny ☀️", 0.15),
            ("Partly Cloudy 🌤️", 0.2),
            ("Cloudy ☁️", 0.25),
            ("Snowy 🌨️", 0.25),
            ("Windy 🌬️", 0.1),
            ("Foggy 🌫️", 0.05)
        ]
    return temp_range[0], temp_range[1], conditions

def calculate_feels_like(temp_f: int, humidity: int, wind_speed: int) -> int:
    """Calculate 'feels like' temperature using heat index and wind chill."""
    if temp_f >= 80:
        # Heat index calculation (Rothfusz regression)
        feels_like = -42.379 + (2.04901523 * temp_f) + (10.14333127 * humidity)
        feels_like -= (0.22475541 * temp_f * humidity)
        feels_like -= (6.83783e-3 * temp_f**2)
        feels_like -= (5.481717e-2 * humidity**2)
        feels_like += (1.22874e-3 * temp_f**2 * humidity)
        feels_like += (8.5282e-4 * temp_f * humidity**2)
        feels_like -= (1.99e-6 * temp_f**2 * humidity**2)
    elif temp_f <= 50 and wind_speed > 3:
        # Wind chill calculation
        feels_like = 35.74 + (0.6215 * temp_f) - (35.75 * wind_speed**0.16)
        feels_like += (0.4275 * temp_f * wind_speed**0.16)
    else:
        feels_like = temp_f
    
    return round(feels_like)

def get_condition_based_values(condition: str) -> Tuple[int, float]:
    """Get appropriate humidity and visibility ranges based on condition."""
    condition_values = {
        "Sunny ☀️": (30, 10.0),           # Low humidity, high visibility
        "Partly Cloudy 🌤️": (45, 8.0),    # Moderate humidity, good visibility
        "Cloudy ☁️": (60, 6.0),           # Higher humidity, reduced visibility
        "Rainy 🌧️": (85, 3.0),            # High humidity, low visibility
        "Thunderstorm ⛈️": (90, 1.0),      # Very high humidity, very low visibility
        "Snowy 🌨️": (75, 0.5),            # High humidity, very low visibility
        "Windy 🌬️": (40, 7.0),            # Lower humidity, good visibility
        "Foggy 🌫️": (95, 0.25)            # Very high humidity, extremely low visibility
    }
    base_humidity, base_visibility = condition_values.get(condition, (50, 5.0))
    
    # Add some randomness
    humidity = base_humidity + random.randint(-10, 10)
    visibility = max(0.1, round(base_visibility + random.uniform(-0.5, 0.5), 1))
    
    return humidity, visibility

def generate_weather(time_zone: str) -> Dict[str, str]:
    """Generate random weather data."""
    try:
        import pytz
        tz = pytz.timezone(time_zone)
        current_time = datetime.datetime.now(tz)
    except ImportError:
        current_time = datetime.datetime.now()

    # Get seasonal temperature ranges and weighted conditions
    min_temp, max_temp, weighted_conditions = get_seasonal_ranges(current_time.month)
    
    # Generate base temperature within seasonal range
    temp_f = random.randint(min_temp, max_temp)
    temp_c = round((temp_f - 32) * 5/9, 1)
    
    # Select weather condition based on weights
    condition = random.choices(
        [c[0] for c in weighted_conditions],
        weights=[c[1] for c in weighted_conditions]
    )[0]
    
    # Get condition-appropriate humidity and visibility
    humidity, visibility = get_condition_based_values(condition)
    
    # Generate wind speed based on condition
    if condition == "Windy 🌬️":
        wind_speed = random.randint(15, 30)
    elif condition in ["Thunderstorm ⛈️", "Snowy 🌨️"]:
        wind_speed = random.randint(10, 25)
    else:
        wind_speed = random.randint(0, 15)
    
    # Calculate feels like temperature
    feels_like = calculate_feels_like(temp_f, humidity, wind_speed)
    
    # Determine season based on month
    if current_time.month in (3, 4, 5):
        season = "Spring 🌸"
    elif current_time.month in (6, 7, 8):
        season = "Summer ☀️"
    elif current_time.month in (9, 10, 11):
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
    # Define weather condition icons
    condition_icons = {
        "Sunny ☀️": "https://cdn-icons-png.flaticon.com/512/869/869869.png",        
        "Partly Cloudy 🌤️": "https://cdn-icons-png.flaticon.com/512/1163/1163661.png",        
        "Cloudy ☁️": "https://cdn-icons-png.flaticon.com/512/414/414825.png",        
        "Rainy 🌧️": "https://cdn-icons-png.flaticon.com/512/3351/3351979.png",
        "Thunderstorm ⛈️": "https://cdn-icons-png.flaticon.com/512/1146/1146860.png",
        "Snowy 🌨️": "https://cdn-icons-png.flaticon.com/512/2315/2315309.png",
        "Windy 🌬️": "https://cdn-icons-png.flaticon.com/512/17640214/17640214.png",
        "Foggy 🌫️": "https://cdn-icons-png.flaticon.com/512/4005/4005901.png"
    }

    embed = discord.Embed(
        title="☀️ Today's Weather",
        color=discord.Color(guild_settings.get("embed_color", 0xFF0000))
    )
    
    # Set thumbnail based on weather condition
    if weather_data["condition"] in condition_icons:
        embed.set_thumbnail(url=condition_icons[weather_data["condition"]])

    # Temperature and Feels Like (show both only if different)
    temp = weather_data["temperature_f"]
    feels_like = weather_data["feels_like"]
    if temp != feels_like:
        embed.add_field(
            name="🌡️ Temperature | 🌡️ Feels Like",
            value=f"{temp} | {feels_like}",
            inline=False
        )
    else:
        embed.add_field(
            name="🌡️ Temperature",
            value=f"{temp}",
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
