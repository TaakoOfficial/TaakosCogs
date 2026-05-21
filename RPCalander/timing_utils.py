from datetime import datetime, timedelta
import pytz

def get_next_post_time(time_zone: str) -> datetime:
    """Calculate the next post time (00:00) in the given timezone."""
    tz = pytz.timezone(time_zone)
    now = datetime.now(tz)
    next_post_time = now.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)
    return next_post_time

def has_already_posted_today(last_posted: datetime, time_zone: str) -> bool:
    """Check if the last post was made today in the given timezone."""
    if not last_posted:
        return False

    tz = pytz.timezone(time_zone)
    if isinstance(last_posted, str):
        last_posted = datetime.fromisoformat(last_posted)
    
    last_posted_dt = last_posted.astimezone(tz)
    today = datetime.now(tz).replace(hour=0, minute=0, second=0, microsecond=0)
    return last_posted_dt >= today

def calculate_next_refresh_time(last_posted: datetime, time_zone: str) -> datetime:
    """Calculate the next refresh time based on the last posted time."""
    tz = pytz.timezone(time_zone)
    now = datetime.now(tz)
    next_post_time = now.replace(hour=0, minute=0, second=0, microsecond=0)
    
    if now >= next_post_time:
        next_post_time += timedelta(days=1)
    
    return next_post_time
