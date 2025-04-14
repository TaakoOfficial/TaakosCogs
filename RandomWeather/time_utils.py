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
    now = datetime.now(tz)  # Ensure `now` is timezone-aware

    if refresh_interval:
        # Ensure the datetime from timestamp is timezone-aware
        next_post_time = datetime.fromtimestamp(last_refresh, tz) + timedelta(seconds=refresh_interval)
    elif refresh_time:
        # Parse the refresh time and set it for today
        target_time = datetime.strptime(refresh_time, "%H%M").replace(
            tzinfo=tz, year=now.year, month=now.month, day=now.day
        )

        # If the target time has already passed today, set it for tomorrow
        if now >= target_time:
            target_time += timedelta(days=1)

        next_post_time = target_time
    else:
        # Default to midnight of the next day if no refresh time or interval is set
        next_post_time = now.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)

    return next_post_time

# Edited by Taako
