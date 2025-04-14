import pytz
from datetime import datetime, timedelta  # Ensure timedelta is imported

def get_system_time_and_timezone():
    """Get the current system time and timezone."""
    now = datetime.now()
    try:
        import tzlocal
        system_timezone = tzlocal.get_localzone().zone
    except ImportError:
        system_timezone = "UTC"  # Fallback if tzlocal is not available

    return now, system_timezone

def validate_timezone(configured_timezone: str) -> str:
    """Validate the configured timezone against the system timezone."""
    if configured_timezone in pytz.all_timezones:
        return configured_timezone
    else:
        return "UTC"  # Default to UTC if the configured timezone is invalid

def calculate_next_refresh_time(
    last_refresh: int, refresh_interval: int, refresh_time: str, time_zone: str
):
    """Calculate the next refresh time based on the configuration."""
    tz = pytz.timezone(time_zone)
    now = datetime.now(tz)

    if refresh_interval:
        next_post_time = datetime.fromtimestamp(last_refresh, tz) + timedelta(seconds=refresh_interval)
    elif refresh_time:
        target_time = datetime.strptime(refresh_time, "%H%M").replace(
            tzinfo=tz, year=now.year, month=now.month, day=now.day
        )
        if now >= target_time:
            target_time += timedelta(days=1)
        next_post_time = target_time
    else:
        next_post_time = now.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)

    return next_post_time

# Edited by Taako
