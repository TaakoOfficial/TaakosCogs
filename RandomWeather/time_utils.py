import pytz
from datetime import datetime, timedelta

def validate_timezone(configured_timezone: str) -> str:
    """Validate the configured timezone against pytz timezones."""
    if configured_timezone in pytz.all_timezones:
        return configured_timezone
    return "UTC"

def calculate_next_refresh_time(last_refresh: int, refresh_interval: int, refresh_time: str, time_zone: str):
    """Calculate the next refresh time based on the configuration."""
    tz = pytz.timezone(time_zone)
    # Get system time and convert it to the guild's timezone
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
        
        # Get today's target time
        target_time = now.replace(hour=target_hour, minute=target_minute, second=0, microsecond=0)
        
        if now >= target_time:
            # Calculate seconds until next occurrence
            current_seconds = now.hour * 3600 + now.minute * 60 + now.second
            target_seconds = target_hour * 3600 + target_minute * 60
            
            # If target is earlier in the day than current time,
            # we need to wait until that time tomorrow
            if target_seconds <= current_seconds:
                seconds_to_wait = (24 * 3600) - (current_seconds - target_seconds)
            else:
                seconds_to_wait = target_seconds - current_seconds
                
            next_post_time = now + timedelta(seconds=seconds_to_wait)
            # Ensure the time is exactly what we want
            next_post_time = next_post_time.replace(hour=target_hour, minute=target_minute, second=0, microsecond=0)
        else:
            next_post_time = target_time
    else:
        # Calculate exact seconds until next midnight
        seconds_until_midnight = ((24 - now.hour) * 3600) - (now.minute * 60) - now.second
        next_post_time = now + timedelta(seconds=seconds_until_midnight)
        next_post_time = next_post_time.replace(microsecond=0)
    
    return next_post_time
