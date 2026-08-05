"""Pure validation, search, pagination, and scheduling helpers."""

from __future__ import annotations

import asyncio
import re
from typing import TYPE_CHECKING, TypeVar

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable, Iterable, Sequence

    from .models import Hub, HubCommand

DISCORD_COMMAND_NAME = re.compile(r"^[a-z0-9_-]{1,32}$")
DESTRUCTIVE_COMMAND_WORDS = {"ban", "kick", "purge", "delete", "reset", "clear", "transfer", "massrole"}
T = TypeVar("T")


class ValidationError(ValueError):
    """Configuration input is invalid."""


def validate_hub_name(name: str) -> str:
    value = name.strip()
    if value != value.lower():
        raise ValidationError("Hub names must be lowercase.")
    if not DISCORD_COMMAND_NAME.fullmatch(value):
        raise ValidationError("Use 1-32 lowercase letters, numbers, hyphens, or underscores.")
    return value


def validate_category_name(name: str) -> str:
    value = " ".join(name.split())
    if not value or len(value) > 100:
        raise ValidationError("Category names must contain 1-100 characters.")
    return value


def is_potentially_destructive(qualified_name: str) -> bool:
    """Provide a conservative default that administrators can explicitly override."""
    words = set(re.split(r"[\s_-]+", qualified_name.casefold()))
    return bool(words.intersection(DESTRUCTIVE_COMMAND_WORDS))


def paginate(items: Sequence[T], page: int, per_page: int = 25) -> tuple[list[T], int, int]:
    if per_page < 1 or per_page > 25:
        raise ValueError("per_page must be between 1 and 25")
    pages = max(1, (len(items) + per_page - 1) // per_page)
    current = min(max(0, page), pages - 1)
    start = current * per_page
    return list(items[start : start + per_page]), current, pages


def rank_commands(commands: Iterable[HubCommand], query: str) -> list[HubCommand]:
    needle = query.casefold().strip()
    if not needle:
        return sorted(commands, key=lambda item: item.qualified_name.casefold())

    def score(command: HubCommand) -> tuple[int, int, str]:
        qualified = command.qualified_name.casefold()
        display = command.display_name.casefold()
        fields = (
            qualified,
            display,
            command.description.casefold(),
            (command.cog_name or "").casefold(),
            (command.category or "").casefold(),
        )
        if qualified == needle or display == needle:
            rank = 0
        elif qualified.startswith(needle) or display.startswith(needle):
            rank = 1
        elif needle in qualified or needle in display:
            rank = 2
        elif needle in fields[2]:
            rank = 3
        elif any(needle in field for field in fields[3:]):
            rank = 4
        else:
            rank = 5
        position = min((field.find(needle) for field in fields if needle in field), default=10_000)
        return rank, position, qualified

    return [command for command in sorted(commands, key=score) if score(command)[0] < 5]


def hub_scope_allows(
    hub: Hub, role_ids: set[int], channel_id: int | None, user_permissions: int, bot_permissions: int
) -> tuple[bool, str | None]:
    """Evaluate configured hub gates using primitive values for easy testing."""
    if hub.blocked_roles and role_ids.intersection(hub.blocked_roles):
        return False, "One of your roles is blocked from this hub."
    if hub.allowed_roles and not role_ids.intersection(hub.allowed_roles):
        return False, "You do not have an allowed role for this hub."
    if channel_id in hub.blocked_channels:
        return False, "This hub is blocked in this channel."
    if hub.allowed_channels and channel_id not in hub.allowed_channels:
        return False, "This hub is not available in this channel."
    if user_permissions & hub.required_user_permissions != hub.required_user_permissions:
        return False, "You are missing permissions required by this hub."
    if bot_permissions & hub.required_bot_permissions != hub.required_bot_permissions:
        return False, "I am missing permissions required by this hub."
    return True, None


class Debouncer:
    """Collapse repeated async work into one delayed call."""

    def __init__(self, callback: Callable[[], Awaitable[None]]) -> None:
        self.callback = callback
        self.task: asyncio.Task[None] | None = None

    def schedule(self, delay: float) -> None:
        self.cancel()

        async def runner() -> None:
            await asyncio.sleep(max(0.0, delay))
            await self.callback()

        self.task = asyncio.create_task(runner())

    def cancel(self) -> None:
        if self.task and not self.task.done():
            self.task.cancel()
        self.task = None
