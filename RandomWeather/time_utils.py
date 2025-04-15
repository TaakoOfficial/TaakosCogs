import pytz
from datetime import datetime, timedelta
from typing import Optional, Union

def validate_timezone(configured_timezone: str) -> str:
    """Validate the configured timezone against pytz timezones."""
    if configured_timezone in pytz.all_timezones:
        return configured_timezone
    return "America/Chicago"  # Default to US Central Time

def get_seconds_until_target(current_time: datetime, target_hour: int, target_minute: int) -> int:
    """Calculate seconds until the next occurrence of a target time."""
    current_seconds = current_time.hour * 3600 + current_time.minute * 60 + current_time.second
    target_seconds = target_hour * 3600 + target_minute * 60
    
    if target_seconds <= current_seconds:
        return (24 * 3600) - (current_seconds - target_seconds)
    else:
        return target_seconds - current_seconds

def should_post_now(current_time: datetime, target_hour: int, target_minute: int) -> bool:
    """
    Check if we should post at the current time.
    Allows for a 1-minute window to avoid missing the exact time.
    """
    return (current_time.hour == target_hour and 
            current_time.minute == target_minute and 
            current_time.second < 60)

def calculate_next_refresh_time(
    last_refresh: Union[int, float],
    refresh_interval: Optional[int], 
    refresh_time: Optional[str],
    time_zone: str
) -> datetime:
    """
    Calculate the next refresh time based on the configuration.
    
    Args:
        last_refresh: Timestamp of last refresh
        refresh_interval: Interval in seconds between refreshes
        refresh_time: Daily refresh time in HHMM format
        time_zone: Timezone string (e.g., 'UTC', 'America/New_York')
    
    Returns:
        datetime: The next scheduled refresh time
    """
    tz = pytz.timezone(time_zone)
    now = datetime.now().astimezone(tz)
    
    if refresh_interval:
        # For intervals, use now as the base if no last refresh
        if last_refresh:
            base_time = datetime.fromtimestamp(last_refresh).astimezone(tz)
        else:
            base_time = now
            
        next_post_time = base_time + timedelta(seconds=refresh_interval)
        # If next post would be in the past, add intervals until it's in the future
        while next_post_time <= now:
            next_post_time += timedelta(seconds=refresh_interval)
            
    elif refresh_time:
        # Parse the refresh time (military time HHMM)
        target_hour = int(refresh_time[:2])
        target_minute = int(refresh_time[2:])
        
        # Check if we should post right now
        if should_post_now(now, target_hour, target_minute):
            return now
            
        # Set up next post time at the target hour/minute
        next_post_time = now.replace(
            hour=target_hour,
            minute=target_minute,
            second=0,
            microsecond=0
        )
        
        # If this time has already passed today, move to tomorrow
        if next_post_time <= now:
            next_post_time += timedelta(days=1)
            
    else:
        # Default to next midnight in the specified timezone
        next_post_time = now.replace(
            hour=0,
            minute=0,
            second=0,
            microsecond=0
        ) + timedelta(days=1)
    
    return next_post_time
