"""Serializable domain models used by CommandHub."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class CommandSource(str, Enum):
    PREFIX = "prefix"
    HYBRID = "hybrid"
    APPLICATION = "application"
    SLASHLINK = "slashlink"


class ParameterKind(str, Enum):
    STRING = "string"
    INTEGER = "integer"
    FLOAT = "float"
    BOOLEAN = "boolean"
    MEMBER = "member"
    USER = "user"
    ROLE = "role"
    CHANNEL = "channel"
    TEXT_CHANNEL = "text_channel"
    VOICE_CHANNEL = "voice_channel"
    MENTIONABLE = "mentionable"
    CHOICE = "choice"
    UNSUPPORTED = "unsupported"


@dataclass(slots=True)
class CommandParameter:
    name: str
    description: str = ""
    kind: ParameterKind = ParameterKind.STRING
    required: bool = True
    default: Any = None
    choices: dict[str, Any] = field(default_factory=dict)
    greedy: bool = False
    remainder: bool = False
    sensitive: bool = False
    minimum: int | float | None = None
    maximum: int | float | None = None


@dataclass(slots=True)
class HubCommand:
    source: CommandSource
    qualified_name: str
    display_name: str
    description: str
    cog_name: str | None
    category: str | None
    parameters: list[CommandParameter] = field(default_factory=list)
    checks: list[Any] = field(default_factory=list, repr=False)
    required_user_permissions: int = 0
    required_bot_permissions: int = 0
    nsfw: bool = False
    enabled: bool = True
    callback: Any = field(default=None, repr=False, compare=False)
    unsupported_reason: str | None = None

    @property
    def key(self) -> str:
        return f"{self.source.value}:{self.qualified_name.casefold()}"


@dataclass(slots=True)
class CommandAssignment:
    qualified_name: str
    source: CommandSource
    position: int = 0
    confirmation_required: bool = False
    hidden: bool = False
    disabled: bool = False

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> CommandAssignment:
        return cls(
            qualified_name=str(data["qualified_name"]),
            source=CommandSource(data.get("source", CommandSource.PREFIX.value)),
            position=int(data.get("position", 0)),
            confirmation_required=bool(data.get("confirmation_required", False)),
            hidden=bool(data.get("hidden", False)),
            disabled=bool(data.get("disabled", False)),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "qualified_name": self.qualified_name,
            "source": self.source.value,
            "position": self.position,
            "confirmation_required": self.confirmation_required,
            "hidden": self.hidden,
            "disabled": self.disabled,
        }


@dataclass(slots=True)
class HubCategory:
    name: str
    position: int = 0
    commands: list[CommandAssignment] = field(default_factory=list)

    @classmethod
    def from_dict(cls, name: str, data: dict[str, Any]) -> HubCategory:
        commands = [CommandAssignment.from_dict(item) for item in data.get("commands", [])]
        commands.sort(key=lambda item: item.position)
        return cls(name=name, position=int(data.get("position", 0)), commands=commands)

    def to_dict(self) -> dict[str, Any]:
        return {
            "position": self.position,
            "commands": [item.to_dict() for item in self.commands],
        }


@dataclass(slots=True)
class Hub:
    name: str
    title: str
    description: str
    emoji: str | None = None
    enabled: bool = True
    ephemeral: bool = True
    search_enabled: bool = True
    repeat_enabled: bool = True
    allowed_roles: list[int] = field(default_factory=list)
    blocked_roles: list[int] = field(default_factory=list)
    allowed_channels: list[int] = field(default_factory=list)
    blocked_channels: list[int] = field(default_factory=list)
    required_user_permissions: int = 0
    required_bot_permissions: int = 0
    default_page: int = 0
    unavailable_behavior: str = "hide"
    categories: dict[str, HubCategory] = field(default_factory=dict)

    @classmethod
    def create(cls, name: str) -> Hub:
        return cls(
            name=name,
            title=name.replace("-", " ").replace("_", " ").title(),
            description=f"Browse {name} commands.",
            categories={"General": HubCategory("General")},
        )

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Hub:
        categories = {str(name): HubCategory.from_dict(str(name), value) for name, value in data.get("categories", {}).items()}
        return cls(
            name=str(data["name"]),
            title=str(data.get("title") or data["name"]),
            description=str(data.get("description") or "Browse server commands."),
            emoji=data.get("emoji"),
            enabled=bool(data.get("enabled", True)),
            ephemeral=bool(data.get("ephemeral", True)),
            search_enabled=bool(data.get("search_enabled", True)),
            repeat_enabled=bool(data.get("repeat_enabled", True)),
            allowed_roles=[int(value) for value in data.get("allowed_roles", [])],
            blocked_roles=[int(value) for value in data.get("blocked_roles", [])],
            allowed_channels=[int(value) for value in data.get("allowed_channels", [])],
            blocked_channels=[int(value) for value in data.get("blocked_channels", [])],
            required_user_permissions=int(data.get("required_user_permissions", data.get("required_permissions", 0))),
            required_bot_permissions=int(data.get("required_bot_permissions", 0)),
            default_page=max(0, int(data.get("default_page", 0))),
            unavailable_behavior=str(data.get("unavailable_behavior", "hide")),
            categories=categories or {"General": HubCategory("General")},
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "title": self.title,
            "description": self.description,
            "emoji": self.emoji,
            "enabled": self.enabled,
            "ephemeral": self.ephemeral,
            "search_enabled": self.search_enabled,
            "repeat_enabled": self.repeat_enabled,
            "allowed_roles": self.allowed_roles,
            "blocked_roles": self.blocked_roles,
            "allowed_channels": self.allowed_channels,
            "blocked_channels": self.blocked_channels,
            "required_user_permissions": self.required_user_permissions,
            "required_bot_permissions": self.required_bot_permissions,
            "default_page": self.default_page,
            "unavailable_behavior": self.unavailable_behavior,
            "categories": {name: category.to_dict() for name, category in self.categories.items()},
        }

    def assignments(self) -> list[tuple[str, CommandAssignment]]:
        result: list[tuple[str, CommandAssignment]] = []
        for category in sorted(self.categories.values(), key=lambda item: (item.position, item.name.casefold())):
            result.extend((category.name, item) for item in sorted(category.commands, key=lambda item: item.position))
        return result

    def find_assignment(self, qualified_name: str, source: CommandSource | None = None) -> tuple[str, CommandAssignment] | None:
        needle = qualified_name.casefold()
        for category, assignment in self.assignments():
            if assignment.qualified_name.casefold() == needle and (source is None or assignment.source is source):
                return category, assignment
        return None


@dataclass(slots=True)
class RepeatRecord:
    hub: str
    qualified_name: str
    source: CommandSource
    arguments: dict[str, Any]
    executed_at: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "hub": self.hub,
            "qualified_name": self.qualified_name,
            "source": self.source.value,
            "arguments": self.arguments,
            "executed_at": self.executed_at,
        }
