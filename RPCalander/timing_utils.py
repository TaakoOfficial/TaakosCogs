from datetime import datetime, timedelta
import pytz  # Edited by Taako

# Utility functions for handling timing logic in the RPCalander cog  # Edited by Taako

def get_next_post_time(time_zone: str) -> datetime:
    """Calculate the next post time (00:00) in the given timezone."""  # Edited by Taako
    tz = pytz.timezone(time_zone)  # Edited by Taako
    now = datetime.now(tz)  # Get the current time in the timezone  # Edited by Taako
    next_post_time = now.replace(hour=0, minute=0, second=0) + timedelta(days=1)  # Edited by Taako
    return next_post_time  # Edited by Taako

def has_already_posted_today(last_posted: str, time_zone: str) -> bool:
    """Check if the last post was made today in the given timezone."""  # Edited by Taako
    if not last_posted:
        return False  # No post has been made yet  # Edited by Taako

    tz = pytz.timezone(time_zone)  # Edited by Taako
    last_posted_dt = datetime.fromisoformat(last_posted).astimezone(tz)  # Convert to timezone-aware datetime  # Edited by Taako
    today = datetime.now(tz).replace(hour=0, minute=0, second=0)  # Start of today  # Edited by Taako
    return last_posted_dt >= today  # Edited by Taako

def save_last_posted(config, guild_id: int, time_zone: str):
    """Save the current time as the last posted time in the given timezone."""  # Edited by Taako
    tz = pytz.timezone(time_zone)  # Edited by Taako
    now = datetime.now(tz)  # Get the current time in the timezone  # Edited by Taako
    config.guild_from_id(guild_id).last_posted.set(now.isoformat())  # Save as ISO format  # Edited by Taako
