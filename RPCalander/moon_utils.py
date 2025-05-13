"""Moon phase calculation and display utilities for the RPCalendar cog."""
from datetime import datetime
import random
import math
import discord

# Moon phase definitions
MOON_PHASES = {
    0: {"name": "New Moon 🌑", "emoji": "🌑", "icon": "https://cdn-icons-png.flaticon.com/512/616/616465.png"},
    1: {"name": "Waxing Crescent 🌒", "emoji": "🌒", "icon": "https://cdn-icons-png.flaticon.com/512/616/616467.png"},
    2: {"name": "First Quarter 🌓", "emoji": "🌓", "icon": "https://cdn-icons-png.flaticon.com/512/616/616469.png"},
    3: {"name": "Waxing Gibbous 🌔", "emoji": "🌔", "icon": "https://cdn-icons-png.flaticon.com/512/616/616471.png"},
    4: {"name": "Full Moon 🌕", "emoji": "🌕", "icon": "https://cdn-icons-png.flaticon.com/512/616/616456.png"},
    5: {"name": "Waning Gibbous 🌖", "emoji": "🌖", "icon": "https://cdn-icons-png.flaticon.com/512/616/616459.png"},
    6: {"name": "Last Quarter 🌗", "emoji": "🌗", "icon": "https://cdn-icons-png.flaticon.com/512/616/616461.png"},
    7: {"name": "Waning Crescent 🌘", "emoji": "🌘", "icon": "https://cdn-icons-png.flaticon.com/512/616/616463.png"}
}

# Blood moon details
BLOOD_MOON = {
    "name": "Blood Moon 🔴", 
    "emoji": "🔴", 
    "icon": "https://img.freepik.com/free-psd/red-planet-mars-surface-texture-space-exploration_84443-38546.jpg?semt=ais_hybrid&w=740",
    "description": "A rare Blood Moon has appeared in the night sky! Such events are often associated with mystical occurrences and heightened magical energies."
}

def calculate_moon_phase(date: datetime) -> int:
    """
    Calculate the moon phase for a given date.
    
    Algorithm based on calculations by John Conway (fitting the moon's orbit to a circle).
    Returns a value from 0-7 representing the moon phase:
    0: New Moon
    1: Waxing Crescent
    2: First Quarter
    3: Waxing Gibbous
    4: Full Moon
    5: Waning Gibbous
    6: Last Quarter
    7: Waning Crescent
    
    Parameters
    ----------
    date : datetime
        The date for which to calculate the moon phase
        
    Returns
    -------
    int
        Moon phase index (0-7)
    """
    # Normalize the year for the calculation
    year = date.year
    month = date.month
    day = date.day
    
    # Adjust months - Jan and Feb are counted as months 13 and 14 of the previous year
    if month == 1 or month == 2:
        month += 12
        year -= 1
        
    # Calculate Julian date
    jd = day + ((153 * (month - 3) + 2) // 5) + (365 * year) + (year // 4) - (year // 100) + (year // 400) + 1721119
    
    # Calculate days since new moon on Jan 1, 2000
    days_since = jd - 2451550.1
    
    # Moon's orbital period is ~29.53 days
    lunar_cycle = 29.53
    
    # Calculate current position in lunar cycle (0-1)
    position = (days_since % lunar_cycle) / lunar_cycle
    
    # Convert position to phase index (0-7)
    phase_index = round(position * 8) % 8
    
    return phase_index

def should_trigger_blood_moon(date: datetime, blood_moon_enabled: bool) -> bool:
    """
    Determine if a blood moon should occur on the given date.
    
    Blood moons are rare events that only occur:
    1. During a full moon (phase index 4)
    2. With a probability similar to real lunar eclipses (~3-4 times per year)
    3. Only when blood moon mode is enabled by admins
    
    Parameters
    ----------
    date : datetime
        The current date
    blood_moon_enabled : bool
        Whether blood moon mode is enabled
        
    Returns
    -------
    bool
        True if blood moon should occur, False otherwise
    """
    if not blood_moon_enabled:
        return False
    
    # Must be a full moon
    phase = calculate_moon_phase(date)
    if phase != 4:  # Full moon
        return False
    
    # Blood moons should be rare (about 3-4 per year, so ~25% chance of any full moon being a blood moon)
    # This equates to roughly a 1/28 chance on any given day
    random_seed = date.year * 10000 + date.month * 100 + date.day  # Deterministic seed based on date
    random.seed(random_seed)
    return random.random() < 0.25  # ~25% chance for a full moon to be a blood moon

def get_moon_data(date: datetime, blood_moon_enabled: bool) -> dict:
    """
    Get all moon data for the given date, including phase and whether it's a blood moon.
    
    Parameters
    ----------
    date : datetime
        The date for which to get moon data
    blood_moon_enabled : bool
        Whether blood moon mode is enabled
        
    Returns
    -------
    dict
        Dictionary containing moon phase data
    """
    phase_index = calculate_moon_phase(date)
    is_blood_moon = phase_index == 4 and should_trigger_blood_moon(date, blood_moon_enabled)
    
    if is_blood_moon:
        return {
            "phase_index": phase_index,
            "is_blood_moon": True,
            "name": BLOOD_MOON["name"],
            "emoji": BLOOD_MOON["emoji"],
            "icon": BLOOD_MOON["icon"],
            "description": BLOOD_MOON["description"]
        }
    else:
        phase_data = MOON_PHASES[phase_index]
        return {
            "phase_index": phase_index,
            "is_blood_moon": False,
            "name": phase_data["name"],
            "emoji": phase_data["emoji"],
            "icon": phase_data["icon"],
            "description": f"The moon is currently in its {phase_data['name']} phase."
        }

def create_moon_embed(moon_data: dict, guild_settings: dict) -> discord.Embed:
    """
    Create a Discord embed for the current moon phase.
    
    Parameters
    ----------
    moon_data : dict
        Moon phase data from get_moon_data()
    guild_settings : dict
        Guild configuration settings
        
    Returns
    -------
    discord.Embed
        Formatted embed with moon phase information
    """
    embed_color = discord.Color(guild_settings.get("embed_color", 0x0000FF))
    
    # For blood moons, override with red color
    if moon_data["is_blood_moon"]:
        embed_color = discord.Color(0xA30000)  # Dark red for blood moon
    
    embed = discord.Embed(
        title=f"🌙 {moon_data['name']}",
        description=moon_data["description"],
        color=embed_color
    )
    
    # Set the moon phase as the thumbnail
    embed.set_thumbnail(url=moon_data["icon"])
    
    # Add footer if enabled
    if guild_settings.get("show_footer", True):
        embed.set_footer(text="RP Calendar Moon Phases", icon_url="https://cdn-icons-png.flaticon.com/512/2456/2456533.png")
    
    return embed

def get_blood_moon_settings_embed(guild_settings: dict) -> discord.Embed:
    """
    Create an embed displaying the current blood moon settings.
    
    Parameters
    ----------
    guild_settings : dict
        The guild settings dict
        
    Returns
    -------
    discord.Embed
        Formatted embed with blood moon settings information
    """
    blood_moon_enabled = guild_settings.get("blood_moon_enabled", False)
    embed_color = discord.Color(guild_settings.get("embed_color", 0x0000FF))
    
    if blood_moon_enabled:
        title = "🔴 Blood Moon Mode: ENABLED"
        color = discord.Color(0xA30000)  # Dark red for blood moon
        description = "Blood Moon mode is currently active. During full moons, there is a chance the moon will turn blood red."
    else:
        title = "🌕 Blood Moon Mode: DISABLED"
        color = embed_color
        description = "Blood Moon mode is currently disabled. Administrators can toggle this feature."
    
    embed = discord.Embed(
        title=title,
        description=description,
        color=color
    )
    
    embed.add_field(
        name="About Blood Moons",
        value="Blood Moons are rare occurrences that have approximately a 25% chance of appearing during a full moon when enabled.",
        inline=False
    )
    
    embed.set_footer(
        text="RP Calendar Moon Phases",
        icon_url=BLOOD_MOON["icon"]
    )
    
    return embed
