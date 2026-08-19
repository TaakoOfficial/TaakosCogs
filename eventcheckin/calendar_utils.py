"""Calendar helpers kept independent from Discord for reliable testing."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Iterable


def escape_ics(value: str) -> str:
    """Escape a text value according to RFC 5545's TEXT rules."""
    return value.replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,").replace("\r\n", "\\n").replace("\n", "\\n")


def utc_stamp(timestamp: int) -> str:
    return datetime.fromtimestamp(timestamp, timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def build_calendar(guild_id: int, guild_name: str, events: Iterable[dict[str, Any]], generated_at: int) -> str:
    """Build a stable UTF-8 iCalendar document for retained events."""
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//TaakosCogs//EventCheckin//EN",
        "CALSCALE:GREGORIAN",
        f"X-WR-CALNAME:{escape_ics(guild_name)} Events",
    ]
    for event in sorted(events, key=lambda item: (int(item.get("starts_at", 0)), int(item.get("event_id", 0)))):
        starts_at = int(event["starts_at"])
        duration = max(1, int(event.get("duration_minutes") or 60))
        lines.extend(
            [
                "BEGIN:VEVENT",
                f"UID:eventcheckin-{guild_id}-{int(event['event_id'])}@discord.red",
                f"DTSTAMP:{utc_stamp(generated_at)}",
                f"DTSTART:{utc_stamp(starts_at)}",
                f"DTEND:{utc_stamp(starts_at + duration * 60)}",
                f"SUMMARY:{escape_ics(str(event.get('title') or 'Discord event'))}",
                f"DESCRIPTION:{escape_ics(str(event.get('description') or ''))}",
                f"LOCATION:{escape_ics(str(event.get('location') or 'Discord'))}",
                f"STATUS:{'CANCELLED' if event.get('status') == 'cancelled' else 'CONFIRMED'}",
                "END:VEVENT",
            ]
        )
    lines.extend(["END:VCALENDAR", ""])
    return "\r\n".join(lines)
