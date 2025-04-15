import pytz
from datetime import datetime, timedelta

def validate_timezone(configured_timezone: str) -> str:
    """Validate the configured timezone against pytz timezones."""
    if configured_timezone in pytz.all_timezones:
        return configured_timezone
    return "UTC"  # Default to UTC if the configured timezone is invalid

def calculate_next_refresh_time(last_refresh: int, refresh_interval: int, refresh_time: str, time_zone: str):
    """Calculate the next refresh time based on the configuration."""
    tz = pytz.timezone(time_zone)
    now = datetime.now(tz)

    if refresh_interval:
        # For intervals, use now as the base if no last refresh, otherwise use last refresh
        base_time = datetime.fromtimestamp(last_refresh, tz) if last_refresh else now
        next_post_time = base_time + timedelta(seconds=refresh_interval)
        
        # If next post would be in the past, add intervals until it's in the future
        while next_post_time <= now:
            next_post_time += timedelta(seconds=refresh_interval)

    elif refresh_time:
        # Parse the refresh time (military time HHMM)
        refresh_hour = int(refresh_time[:2])
        refresh_minute = int(refresh_time[2:])
        
        # Calculate next occurrence of the target time
        target_time = now.replace(hour=refresh_hour, minute=refresh_minute, second=0, microsecond=0)
        if now >= target_time:
            # Move time forward by seconds until we find next valid occurrence
            seconds_to_add = (24 * 60 * 60) - (now.hour * 60 * 60 + now.minute * 60 + now.second)
            target_time = now + timedelta(seconds=seconds_to_add)
            target_time = target_time.replace(hour=refresh_hour, minute=refresh_minute, second=0, microsecond=0)
            
        next_post_time = target_time
    else:
        # Find next occurrence of midnight by adding seconds until next day
        seconds_until_midnight = (24 * 60 * 60) - (now.hour * 60 * 60 + now.minute * 60 + now.second)
        next_post_time = now + timedelta(seconds=seconds_until_midnight)
        next_post_time = next_post_time.replace(microsecond=0)

    return next_post_time
