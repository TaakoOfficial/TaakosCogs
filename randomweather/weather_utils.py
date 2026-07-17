"""Weather generation utilities for the RandomWeather cog."""

import datetime
import random

import discord

# Try to import pytz once globally to avoid repeated imports
try:
    import pytz

    HAS_PYTZ = True
except ImportError:
    HAS_PYTZ = False

RECOVERABLE_EXCEPTIONS = (
    OSError,
    RuntimeError,
    ValueError,
    KeyError,
    TypeError,
    AttributeError,
)

TWEMOJI_BASE_URL = "https://cdn.jsdelivr.net/gh/jdecked/twemoji@v17.0.3/assets/72x72"
WEATHER_ICON_URLS = {
    "Sunny ☀️": f"{TWEMOJI_BASE_URL}/2600.png",
    "Partly Cloudy 🌤️": f"{TWEMOJI_BASE_URL}/1f324.png",
    "Cloudy ☁️": f"{TWEMOJI_BASE_URL}/2601.png",
    "Rainy 🌧️": f"{TWEMOJI_BASE_URL}/1f327.png",
    "Thunderstorm ⛈️": f"{TWEMOJI_BASE_URL}/26c8.png",
    "Light Snow ❄️": f"{TWEMOJI_BASE_URL}/2744.png",
    "Snowy 🌨️": f"{TWEMOJI_BASE_URL}/1f328.png",
    "Windy 🌬️": f"{TWEMOJI_BASE_URL}/1f32c.png",
    "Foggy 🌫️": f"{TWEMOJI_BASE_URL}/1f32b.png",
    "Typhoon 🌀": f"{TWEMOJI_BASE_URL}/1f300.png",
    "Hurricane 🌀": f"{TWEMOJI_BASE_URL}/1f300.png",
    "Flash Flooding 🌊": f"{TWEMOJI_BASE_URL}/1f30a.png",
    "Acid Rain ☢️": f"{TWEMOJI_BASE_URL}/2622.png",
    "Tornado 🌪️": f"{TWEMOJI_BASE_URL}/1f32a.png",
    "Ice Storm 🧊": f"{TWEMOJI_BASE_URL}/1f9ca.png",
    "Flash Freeze 🥶": f"{TWEMOJI_BASE_URL}/1f976.png",
    "Heavy Smog 🟣": f"{TWEMOJI_BASE_URL}/1f7e3.png",
    "Blood Fog 🔴": f"{TWEMOJI_BASE_URL}/1f534.png",
    "Lightning Storm ⚡": f"{TWEMOJI_BASE_URL}/26a1.png",
    "Noxious Gas ☁️": f"{TWEMOJI_BASE_URL}/2601.png",
}


def get_seasonal_ranges(month: int) -> tuple[int, int, list[tuple[str, float]]]:
    """Get temperature ranges and weighted conditions for the season."""
    # Base extreme weather conditions that can happen in any season (but still rare)
    base_extreme = [
        ("Acid Rain ☢️", 0.006),
        ("Heavy Smog 🟣", 0.005),
        ("Blood Fog 🔴", 0.003),
        ("Noxious Gas ☁️", 0.004),
    ]

    # Season-specific extreme weather
    spring_extreme = base_extreme + [
        ("Tornado 🌪️", 0.006),  # Tornadoes more common in spring
        ("Flash Flooding 🌊", 0.005),
        ("Lightning Storm ⚡", 0.005),
    ]

    summer_extreme = base_extreme + [
        ("Hurricane 🌀", 0.008),  # Hurricanes peak in summer/early fall
        ("Typhoon 🌀", 0.007),  # Typhoons more common in summer
        ("Lightning Storm ⚡", 0.008),  # More thunderstorm activity in summer
        ("Flash Flooding 🌊", 0.004),
    ]

    fall_extreme = base_extreme + [
        ("Hurricane 🌀", 0.005),  # Hurricane season extends into fall
        ("Flash Flooding 🌊", 0.004),
        ("Lightning Storm ⚡", 0.003),
    ]

    winter_extreme = base_extreme + [
        ("Ice Storm 🧊", 0.010),  # Ice storms primarily in winter
        ("Flash Freeze 🥶", 0.008),  # Flash freeze primarily in winter
        ("Flash Flooding 🌊", 0.003),
    ]

    # Spring (March-May)
    if month in (3, 4, 5):
        temp_range = (45, 75)
        conditions = [
            ("Sunny ☀️", 0.245),
            ("Partly Cloudy 🌤️", 0.295),
            ("Cloudy ☁️", 0.195),
            ("Rainy 🌧️", 0.145),
            ("Thunderstorm ⛈️", 0.045),
            ("Windy 🌬️", 0.025),
            ("Foggy 🌫️", 0.018),
        ] + spring_extreme
    # Summer (June-August)
    elif month in (6, 7, 8):
        temp_range = (65, 95)
        conditions = [
            ("Sunny ☀️", 0.395),
            ("Partly Cloudy 🌤️", 0.295),
            ("Cloudy ☁️", 0.095),
            ("Thunderstorm ⛈️", 0.145),
            ("Windy 🌬️", 0.025),
            ("Foggy 🌫️", 0.018),
        ] + summer_extreme
    # Fall (September-November)
    elif month in (9, 10, 11):
        temp_range = (40, 70)
        conditions = [
            ("Sunny ☀️", 0.195),
            ("Partly Cloudy 🌤️", 0.295),
            ("Cloudy ☁️", 0.245),
            ("Rainy 🌧️", 0.145),
            ("Windy 🌬️", 0.045),
            ("Foggy 🌫️", 0.048),
        ] + fall_extreme
    # Winter (December-February)
    else:
        temp_range = (20, 45)
        conditions = [
            ("Sunny ☀️", 0.100),
            ("Partly Cloudy 🌤️", 0.150),
            ("Cloudy ☁️", 0.220),
            ("Light Snow ❄️", 0.160),  # Light snow
            ("Snowy 🌨️", 0.200),  # Increased snow probability
            ("Windy 🌬️", 0.095),
            ("Foggy 🌫️", 0.048),
        ] + winter_extreme
    return temp_range[0], temp_range[1], conditions


def calculate_feels_like(temp_f: int, humidity: int, wind_speed: int) -> int:
    """Calculate 'feels like' temperature using heat index and wind chill."""
    if temp_f >= 80:
        # Heat index calculation (Rothfusz regression)
        feels_like = -42.379 + (2.04901523 * temp_f) + (10.14333127 * humidity)
        feels_like -= 0.22475541 * temp_f * humidity
        feels_like -= 6.83783e-3 * temp_f**2
        feels_like -= 5.481717e-2 * humidity**2
        feels_like += 1.22874e-3 * temp_f**2 * humidity
        feels_like += 8.5282e-4 * temp_f * humidity**2
        feels_like -= 1.99e-6 * temp_f**2 * humidity**2
    elif temp_f <= 50 and wind_speed > 3:
        # Wind chill calculation
        feels_like = 35.74 + (0.6215 * temp_f) - (35.75 * wind_speed**0.16)
        feels_like += 0.4275 * temp_f * wind_speed**0.16
    else:
        feels_like = temp_f

    return round(feels_like)


def get_condition_based_values(condition: str) -> tuple[int, float]:
    """Get appropriate humidity and visibility ranges based on condition."""
    condition_values = {
        # Normal conditions
        "Sunny ☀️": (30, 10.0),  # Low humidity, high visibility
        "Partly Cloudy 🌤️": (45, 8.0),  # Moderate humidity, good visibility
        "Cloudy ☁️": (60, 6.0),  # Higher humidity, reduced visibility
        "Rainy 🌧️": (85, 3.0),  # High humidity, low visibility
        # Very high humidity, very low visibility
        "Thunderstorm ⛈️": (90, 1.0),
        "Light Snow ❄️": (70, 2.0),  # Moderate humidity, moderate visibility
        "Snowy 🌨️": (75, 0.5),  # High humidity, very low visibility
        "Windy 🌬️": (40, 7.0),  # Lower humidity, good visibility
        "Foggy 🌫️": (95, 0.25),  # Very high humidity, extremely low visibility
        # Extreme conditions
        # Extremely high humidity, near-zero visibility
        "Typhoon 🌀": (95, 0.1),
        # Maximum humidity, very low visibility
        "Flash Flooding 🌊": (100, 0.2),
        "Acid Rain ☢️": (85, 0.5),  # High humidity, low visibility
        # Extremely high humidity, near-zero visibility
        "Hurricane 🌀": (98, 0.1),
        # Variable humidity, extremely low visibility
        "Tornado 🌪️": (70, 0.05),
        "Ice Storm 🧊": (75, 0.3),  # High humidity, very low visibility
        "Flash Freeze 🥶": (40, 0.4),  # Low humidity, moderate visibility
        # Very high humidity, extremely low visibility
        "Heavy Smog 🟣": (90, 0.2),
        # Extremely high humidity, near-zero visibility
        "Blood Fog 🔴": (95, 0.1),
        "Lightning Storm ⚡": (80, 0.4),  # High humidity, very low visibility
        "Noxious Gas ☁️": (30, 0.2),  # Low humidity, extremely low visibility
    }
    base_humidity, base_visibility = condition_values.get(condition, (50, 5.0))

    # Add some randomness
    humidity = base_humidity + random.randint(-10, 10)
    # Ensure humidity stays between 0 and 100
    humidity = max(0, min(100, humidity))
    visibility = max(0.1, round(base_visibility + random.uniform(-0.5, 0.5), 1))

    return humidity, visibility


def generate_weather(time_zone: str) -> dict[str, str]:
    """Generate random weather data."""
    current_time = datetime.datetime.now(datetime.timezone.utc)
    if HAS_PYTZ and time_zone:
        try:
            tz = pytz.timezone(time_zone)
            current_time = datetime.datetime.now(tz)
        except RECOVERABLE_EXCEPTIONS:
            current_time = datetime.datetime.now(datetime.timezone.utc)

    # Get seasonal temperature ranges and weighted conditions
    min_temp, max_temp, weighted_conditions = get_seasonal_ranges(
        current_time.month)

    # Generate base temperature within seasonal range
    temp_f = random.randint(min_temp, max_temp)
    temp_c = round((temp_f - 32) * 5 / 9, 1)

    # Select weather condition based on weights
    condition = random.choices(
        [c[0] for c in weighted_conditions],
        weights=[c[1] for c in weighted_conditions],
    )[0]

    # Get condition-appropriate humidity and visibility
    humidity, visibility = get_condition_based_values(condition)

    # Generate wind speed based on condition
    if condition == "Windy 🌬️":
        wind_speed = random.randint(15, 30)
    elif condition == "Snowy 🌨️":
        wind_speed = random.randint(10, 25)  # Moderate wind with heavy snow
    elif condition == "Light Snow ❄️":
        wind_speed = random.randint(5, 15)  # Light wind with light snow
    elif condition == "Thunderstorm ⛈️":
        wind_speed = random.randint(10, 25)
    # Extreme wind conditions
    elif condition in ["Typhoon 🌀", "Hurricane 🌀"]:
        wind_speed = random.randint(75, 120)
    elif condition == "Tornado 🌪️":
        wind_speed = random.randint(65, 150)
    elif condition in [
        "Flash Flooding 🌊",
        "Acid Rain ☢️",
        "Ice Storm 🧊",
        "Lightning Storm ⚡",
    ]:
        wind_speed = random.randint(20, 40)
    elif condition == "Flash Freeze 🥶":
        # Cold, biting wind with flash freeze
        wind_speed = random.randint(15, 35)
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
        "time": current_time.strftime("%I:%M %p"),
    }


def create_weather_embed(
    weather_data: dict[str, str],
    guild_settings: dict[str, any],
) -> discord.Embed:
    """Create a Discord embed for weather data. Uses special alert embed for extreme weather."""

    # Check if this is extreme weather - if so, use the alert embed instead
    if is_extreme_weather(weather_data["condition"]):
        return create_extreme_weather_alert(weather_data, guild_settings)

    embed = discord.Embed(
        title="☀️ Today's Weather",
        color=discord.Color(guild_settings.get("embed_color", 0xFF0000)),
    )

    # Set thumbnail based on weather condition
    if weather_data["condition"] in WEATHER_ICON_URLS:
        embed.set_thumbnail(url=WEATHER_ICON_URLS[weather_data["condition"]])

    # Temperature and Feels Like (show both only if different)
    temp = weather_data["temperature_f"]
    feels_like = weather_data["feels_like"]
    if temp != feels_like:
        embed.add_field(
            name="🌡️ Temperature | 🌡️ Feels Like",
            value=f"{temp} | {feels_like}",
            inline=False,
        )
    else:
        embed.add_field(
            name="🌡️ Temperature",
            value=f"{temp}",
            inline=False,
        )

    # Conditions
    embed.add_field(
        name="☁️ Conditions",
        value=weather_data["condition"],
        inline=False,
    )

    # Wind, Humidity, and Visibility
    embed.add_field(
        name="🌬️ Wind | 💧 Humidity | 👀 Visibility",
        value=f"{weather_data['wind_speed']} | {weather_data['humidity']} | {weather_data['visibility']}",
        inline=False,
    )

    # Current Season
    embed.add_field(
        name="🍂 Current Season",
        value=weather_data["season"],
        inline=False,
    )

    if guild_settings.get("show_footer", True):
        embed.set_footer(text="🎲 Weather conditions are randomly generated")

    return embed


def create_extreme_weather_alert(
    weather_data: dict[str, str],
    guild_settings: dict[str, any],
) -> discord.Embed:
    """Create a dramatic and eye-catching alert embed for extreme weather conditions."""
    # Use the guild's configured embed color instead of condition-specific colors
    condition = weather_data["condition"]

    embed = discord.Embed(
        title="⚠️ EXTREME WEATHER ALERT ⚠️",
        description=f"**{condition.upper()}** has been detected in your area!\nTake necessary precautions!",
        color=discord.Color(guild_settings.get("embed_color", 0xFF0000)),
    )

    # Add a timestamp for urgency
    embed.timestamp = datetime.datetime.now(datetime.timezone.utc)

    # Set thumbnail based on condition
    if condition in WEATHER_ICON_URLS:
        embed.set_thumbnail(url=WEATHER_ICON_URLS[condition])

    # Add an image for visual impact - dramatic severe weather warning banner
    embed.set_image(
        url="https://file.taako.org/api/file/share.php?token=2bc05c04ade85792546ff265bd6c345d",
    )

    # Temperature with alert formatting
    temp = weather_data["temperature_f"]
    feels_like = weather_data["feels_like"]
    if temp != feels_like:
        embed.add_field(
            name="🌡️ Current Temperature | 🌡️ Feels Like",
            value=f"**{temp}** | **{feels_like}**",
            inline=False,
        )
    else:
        embed.add_field(
            name="🌡️ Current Temperature",
            value=f"**{temp}**",
            inline=False,
        )

    # Add danger level based on condition
    danger_levels = {
        "Typhoon 🌀": "SEVERE",
        "Hurricane 🌀": "SEVERE",
        "Tornado 🌪️": "EXTREME",
        "Flash Flooding 🌊": "HIGH",
        "Ice Storm 🧊": "HIGH",
        "Flash Freeze 🥶": "HIGH",
        "Acid Rain ☢️": "MODERATE",
        "Heavy Smog 🟣": "MODERATE",
        "Blood Fog 🔴": "UNKNOWN",
        "Lightning Storm ⚡": "HIGH",
        "Noxious Gas ☁️": "HIGH",
    }

    danger = danger_levels.get(condition, "HIGH")
    embed.add_field(
        name="⚠️ DANGER LEVEL",
        value=f"**{danger}**",
        inline=True,
    )

    # Wind, Humidity, and Visibility with alert formatting
    embed.add_field(
        name="🌬️ Wind Speed",
        value=f"**{weather_data['wind_speed']}**",
        inline=True,
    )

    embed.add_field(
        name="👀 Visibility",
        value=f"**{weather_data['visibility']}**",
        inline=True,
    )

    # Add special recommendations based on condition
    recommendations = {
        "Typhoon 🌀": "Seek sturdy shelter immediately. Stay away from windows.",
        "Hurricane 🌀": "Evacuate low-lying areas. Secure property and seek stable shelter.",
        "Tornado 🌪️": "Go to basement or interior room. Stay away from windows.",
        "Flash Flooding 🌊": "Move to higher ground. Do not walk or drive through floodwaters.",
        "Ice Storm 🧊": "Stay indoors. Roads are extremely hazardous.",
        "Flash Freeze 🥶": "Seek warm shelter. Protect exposed skin from frostbite.",
        "Acid Rain ☢️": "Stay indoors. Cover vehicles and sensitive equipment.",
        "Heavy Smog 🟣": "Wear respiratory protection. Limit outdoor activities.",
        "Blood Fog 🔴": "Unknown phenomenon. Stay indoors until cleared.",
        "Lightning Storm ⚡": "Stay indoors. Avoid open areas and tall structures.",
        "Noxious Gas ☁️": "Evacuate area immediately. Use breathing protection.",
    }

    embed.add_field(
        name="🚨 SAFETY RECOMMENDATIONS",
        value=recommendations.get(
            condition,
            "Seek shelter and await further instructions.",
        ),
        inline=False,
    )

    # Footer with warning
    embed.set_footer(text="⚠️ This is a extreme weather alert! ⚠️")

    return embed


def is_extreme_weather(condition: str) -> bool:
    """Check if the weather condition is considered extreme/severe weather."""
    # These match exactly with the keys in condition_icons dictionary in create_extreme_weather_alert
    extreme_conditions = [
        "Typhoon 🌀",
        "Flash Flooding 🌊",
        "Acid Rain ☢️",
        "Hurricane 🌀",
        "Tornado 🌪️",
        "Ice Storm 🧊",
        "Flash Freeze 🥶",
        "Heavy Smog 🟣",
        "Blood Fog 🔴",
        "Lightning Storm ⚡",
        "Noxious Gas ☁️",
    ]
    return condition in extreme_conditions


def generate_extreme_weather(time_zone: str) -> dict[str, str]:
    """
    Generate random extreme weather data.

    This function forces the generation of an extreme weather condition
    regardless of season or normal probability.

    Parameters
    ----------
    time_zone : str
        The timezone to use for time calculations

    Returns
    -------
    Dict[str, str]
        Weather data with a randomly selected extreme condition
    """
    current_time = datetime.datetime.now(datetime.timezone.utc)
    if HAS_PYTZ and time_zone:
        try:
            tz = pytz.timezone(time_zone)
            current_time = datetime.datetime.now(tz)
        except RECOVERABLE_EXCEPTIONS:
            current_time = datetime.datetime.now(datetime.timezone.utc)

    # List of all extreme weather conditions
    # These match exactly with the keys in condition_icons dictionary in create_extreme_weather_alert
    extreme_conditions = [
        "Typhoon 🌀",
        "Flash Flooding 🌊",
        "Acid Rain ☢️",
        "Hurricane 🌀",
        "Tornado 🌪️",
        "Ice Storm 🧊",
        "Flash Freeze 🥶",
        "Heavy Smog 🟣",
        "Blood Fog 🔴",
        "Lightning Storm ⚡",
        "Noxious Gas ☁️",
    ]

    # Get seasonal temperature ranges (we'll still respect the temperature range for the season)
    min_temp, max_temp, _ = get_seasonal_ranges(current_time.month)

    # Generate base temperature with more extreme variance
    # For extreme conditions, we'll push toward the edges of the range
    if random.choice([True, False]):  # 50% chance for extremely hot
        temp_f = random.randint(max(max_temp - 10, min_temp), max_temp + 15)
    else:  # 50% chance for extremely cold
        temp_f = random.randint(min_temp - 15, min(min_temp + 10, max_temp))

    temp_c = round((temp_f - 32) * 5 / 9, 1)

    # Randomly select an extreme condition
    condition = random.choice(extreme_conditions)

    # Get condition-appropriate humidity and visibility
    humidity, visibility = get_condition_based_values(condition)

    # Generate wind speed based on condition - more extreme than normal
    if condition in ["Typhoon 🌀", "Hurricane 🌀"]:
        wind_speed = random.randint(95, 140)  # More extreme winds
    elif condition == "Tornado 🌪️":
        wind_speed = random.randint(85, 175)  # More extreme tornado winds
    elif condition in [
        "Flash Flooding 🌊",
        "Acid Rain ☢️",
        "Ice Storm 🧊",
        "Lightning Storm ⚡",
    ]:
        wind_speed = random.randint(30, 60)  # More extreme storm winds
    elif condition == "Flash Freeze 🥶":
        wind_speed = random.randint(25, 45)  # More extreme cold winds
    else:
        wind_speed = random.randint(15, 35)  # Generally more extreme winds

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
        "time": current_time.strftime("%I:%M %p"),
    }
