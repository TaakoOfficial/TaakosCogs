"""Normalized event models shared by YALC listeners and storage."""

from __future__ import annotations

import datetime
from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class LogEvent:
    """A normalized logging event independent of its Discord renderer."""

    guild_id: int
    event_type: str
    summary: str
    occurred_at: datetime.datetime = field(
        default_factory=lambda: datetime.datetime.now(datetime.timezone.utc),
    )
    actor_id: int | None = None
    target_id: int | None = None
    source_channel_id: int | None = None
    audit_entry_id: int | None = None
    confidence: str = "unavailable"
    details: dict[str, Any] = field(default_factory=dict)

    def journal_payload(self, *, include_content: bool) -> dict[str, Any]:
        details = dict(self.details)
        if not include_content:
            for key in ("content", "before_content", "after_content"):
                details.pop(key, None)
        return {
            "guild_id": self.guild_id,
            "event_type": self.event_type,
            "summary": self.summary,
            "occurred_at": self.occurred_at.isoformat(),
            "actor_id": self.actor_id,
            "target_id": self.target_id,
            "source_channel_id": self.source_channel_id,
            "audit_entry_id": self.audit_entry_id,
            "confidence": self.confidence,
            "details": details,
        }
