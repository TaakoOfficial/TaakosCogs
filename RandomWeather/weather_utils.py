import random  # Edited by Taako
from datetime import datetime  # Edited by Taako
import pytz  # Edited by Taako
import discord  # Edited by Taako

# Utility functions for weather generation and embed creation  # Edited by Taako

def get_current_season(time_zone):
    """Determine the current season based on the time zone and date."""  # Edited by Taako
    now = datetime.now(pytz.timezone(time_zone))  # Edited by Taako
    month = now.month  # Edited by Taako
    day = now.day  # Edited by Taako

    if (month == 12 and day >= 21) or (1 <= month <= 2) or (month == 3 and day < 20):
        return "Winter"  # Edited by Taako
    elif (month == 3 and day >= 20) or (4 <= month <= 5) or (month == 6 and day < 21):
        return "Spring"  # Edited by Taako
    elif (month == 6 and day >= 21) or (7 <= month <= 8) or (month == 9 and day < 22):
        return "Summer"  # Edited by Taako
    elif (month == 9 and day >= 22) or (10 <= month <= 11) or (month == 12 and day < 21):
        return "Autumn"  # Edited by Taako
    return "Unknown"  # Edited by Taako

def generate_weather(time_zone):
    """Generate realistic random weather based on the current season."""  # Edited by Taako
    season = get_current_season(time_zone)  # Edited by Taako

    if season == "Winter":
        conditions = random.choice(["Snowy", "Overcast", "Clear sky"])  # Edited by Taako
        temperature = random.randint(10, 35)  # Edited by Taako
    elif season == "Spring":
        conditions = random.choice(["Rainy", "Partly cloudy", "Clear sky"])  # Edited by Taako
        temperature = random.randint(40, 65)  # Edited by Taako
    elif season == "Summer":
        conditions = random.choice(["Clear sky", "Partly cloudy", "Stormy"])  # Edited by Taako
        temperature = random.randint(70, 90)  # Edited by Taako
    elif season == "Autumn":
        conditions = random.choice(["Overcast", "Rainy", "Partly cloudy"])  # Edited by Taako
        temperature = random.randint(45, 65)  # Edited by Taako
    else:
        conditions = random.choice(["Clear sky", "Partly cloudy", "Overcast", "Rainy", "Stormy", "Snowy"])  # Edited by Taako
        temperature = random.randint(10, 90)  # Edited by Taako

    if conditions == "Stormy":
        temperature -= random.randint(5, 10)  # Edited by Taako
        humidity = random.randint(80, 100)  # Edited by Taako
    else:
        humidity = random.randint(30, 70)  # Edited by Taako

    wind_speed = round(random.uniform(0.5, 40.0), 1)  # Edited by Taako
    wind_direction = random.choice(["N", "NE", "E", "SE", "S", "SW", "W", "NW"])  # Edited by Taako

    feels_like = temperature + random.randint(-3, 3)  # Edited by Taako
    if wind_speed > 20.0:
        feels_like -= random.randint(2, 5)  # Edited by Taako

    pressure = random.randint(950, 1050)  # Edited by Taako
    visibility = round(random.uniform(0.5, 6.2), 1)  # Edited by Taako

    return {
        "temperature": f"{temperature}°F",  # Edited by Taako
        "feels_like": f"{feels_like}°F",  # Edited by Taako
        "conditions": conditions,  # Edited by Taako
        "wind": f"{wind_speed} mph {wind_direction}",  # Edited by Taako
        "pressure": f"{pressure} hPa",  # Edited by Taako
        "humidity": f"{humidity}%",  # Edited by Taako
        "visibility": f"{visibility} miles",  # Edited by Taako
    }  # Edited by Taako

def get_weather_icon(condition):
    """Get an icon URL based on the weather condition."""  # Edited by Taako
    icons = {
        "Clear sky": "https://cdn-icons-png.flaticon.com/512/869/869869.png",  # Edited by Taako
        "Partly cloudy": "https://cdn-icons-png.flaticon.com/512/1146/1146869.png",  # Edited by Taako
        "Overcast": "https://cdn-icons-png.flaticon.com/512/414/414825.png",  # Edited by Taako
        "Rainy": "https://cdn-icons-png.flaticon.com/512/1163/1163626.png",  # Edited by Taako
        "Stormy": "https://cdn-icons-png.flaticon.com/512/4668/4668778.png",  # Edited by Taako
        "Snowy": "https://cdn-icons-png.flaticon.com/512/642/642102.png",  # Edited by Taako
    }  # Edited by Taako
    return icons.get(condition, "https://cdn-icons-png.flaticon.com/512/869/869869.png")  # Edited by Taako

def create_weather_embed(weather_data, guild_settings):
    """Create a Discord embed for the weather data."""  # Edited by Taako
    embed_color = guild_settings.get("embed_color", 0xFF0000)  # Edited by Taako
    icon_url = get_weather_icon(weather_data["conditions"])  # Edited by Taako
    current_season = get_current_season(guild_settings["time_zone"])  # Edited by Taako

    embed = discord.Embed(
        title="🌤️ Today's Weather",  # Edited by Taako
        color=discord.Color(embed_color)  # Edited by Taako
    )  # Edited by Taako
    embed.add_field(name="🌡️ Temperature", value=weather_data["temperature"], inline=True)  # Edited by Taako
    embed.add_field(name="🌡️ Feels Like", value=weather_data["feels_like"], inline=True)  # Edited by Taako
    embed.add_field(name="🌥️ Conditions", value=weather_data["conditions"], inline=False)  # Edited by Taako
    embed.add_field(name="💨 Wind", value=weather_data["wind"], inline=True)  # Edited by Taako
    embed.add_field(name="💧 Humidity", value=weather_data["humidity"], inline=True)  # Edited by Taako
    embed.add_field(name="👀 Visibility", value=weather_data["visibility"], inline=True)  # Edited by Taako
    embed.add_field(name="🍂 Current Season", value=current_season, inline=False)  # Edited by Taako
    embed.set_thumbnail(url=icon_url)  # Edited by Taako

    if guild_settings.get("show_footer", True):
        embed.set_footer(text="RandomWeather by Taako", icon_url="https://cdn-icons-png.flaticon.com/512/869/869869.png")  # Edited by Taako

    return embed  # Edited by Taako
