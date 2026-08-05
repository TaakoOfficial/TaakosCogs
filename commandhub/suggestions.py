"""Deterministic setup suggestions built from loaded cog and command metadata."""

from __future__ import annotations

import asyncio
import inspect
import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

from .utils import is_potentially_destructive, validate_hub_name

if TYPE_CHECKING:
    from .models import HubCommand


@dataclass(slots=True, frozen=True)
class CogMetadata:
    name: str
    description: str = ""
    tags: tuple[str, ...] = ()


@dataclass(slots=True, frozen=True)
class PlannedCommand:
    command: HubCommand
    confirmation_required: bool = False


@dataclass(slots=True)
class PlannedHub:
    name: str
    title: str
    description: str
    categories: dict[str, list[PlannedCommand]] = field(default_factory=dict)

    @property
    def command_count(self) -> int:
        return sum(len(commands) for commands in self.categories.values())


@dataclass(slots=True)
class SuggestionPlan:
    kind: str
    hubs: dict[str, PlannedHub]
    skipped: list[str] = field(default_factory=list)

    @property
    def command_count(self) -> int:
        return sum(hub.command_count for hub in self.hubs.values())


HUB_DETAILS = {
    "admin": ("Administration", "Moderation, configuration, and permission-gated commands."),
    "community": ("Community", "Events, onboarding, tickets, feedback, and member programs."),
    "fun": ("Fun and Games", "Games, drawings, random choices, and social commands."),
    "music": ("Music", "Playback, queues, playlists, and voice controls."),
    "other": ("Other Commands", "Commands that need an administrator to choose a better home."),
    "utility": ("Utilities", "Lookups, comparisons, status checks, and everyday server tools."),
}

KEYWORDS: dict[str, dict[str, int]] = {
    "admin": {
        "admin": 6,
        "audit": 5,
        "ban": 7,
        "config": 6,
        "delete": 5,
        "kick": 7,
        "manage": 5,
        "moderation": 6,
        "mod": 4,
        "purge": 7,
        "reset": 5,
        "settings": 5,
    },
    "community": {
        "application": 5,
        "event": 4,
        "giveaway": 4,
        "invite": 4,
        "reputation": 5,
        "review": 4,
        "suggestion": 5,
        "ticket": 5,
        "welcome": 5,
    },
    "fun": {
        "dice": 5,
        "flip": 5,
        "fun": 5,
        "game": 5,
        "random": 4,
        "roll": 5,
        "spin": 5,
        "trivia": 5,
        "wheel": 5,
    },
    "music": {
        "album": 4,
        "music": 7,
        "pause": 4,
        "play": 4,
        "playlist": 6,
        "queue": 6,
        "song": 6,
        "volume": 5,
    },
    "utility": {
        "avatar": 4,
        "compare": 5,
        "info": 5,
        "lookup": 5,
        "member": 2,
        "role": 2,
        "server": 2,
        "status": 5,
        "time": 4,
        "user": 2,
        "weather": 4,
    },
}


def _metadata_from_file(cog: Any) -> CogMetadata:
    name = str(getattr(cog, "qualified_name", cog.__class__.__name__))
    description = str(getattr(cog, "description", "") or "")
    tags: tuple[str, ...] = ()
    try:
        source = Path(inspect.getfile(cog.__class__)).resolve()
        info_path = source.parent / "info.json"
        if info_path.is_file():
            payload = json.loads(info_path.read_text(encoding="utf-8"))
            if isinstance(payload, dict):
                name = str(payload.get("name") or name)
                description = str(payload.get("description") or payload.get("short") or description)
                raw_tags = payload.get("tags", [])
                if isinstance(raw_tags, list | tuple):
                    tags = tuple(str(tag) for tag in raw_tags if tag)
    except (OSError, TypeError, ValueError, json.JSONDecodeError):
        pass
    return CogMetadata(name=name, description=description, tags=tags)


async def read_loaded_cog_metadata(cogs: list[Any]) -> dict[str, CogMetadata]:
    records = await asyncio.gather(*(asyncio.to_thread(_metadata_from_file, cog) for cog in cogs))
    metadata: dict[str, CogMetadata] = {}
    for cog, record in zip(cogs, records, strict=True):
        runtime_name = str(getattr(cog, "qualified_name", cog.__class__.__name__))
        metadata[runtime_name.casefold()] = record
        metadata[record.name.casefold()] = record
    return metadata


def _eligible(commands: list[HubCommand]) -> tuple[list[HubCommand], list[str]]:
    usable: list[HubCommand] = []
    skipped: list[str] = []
    for command in commands:
        if (command.cog_name or "").casefold() == "commandhub":
            continue
        if not command.enabled:
            skipped.append(f"{command.qualified_name}: disabled")
        elif command.unsupported_reason:
            skipped.append(f"{command.qualified_name}: {command.unsupported_reason}")
        else:
            usable.append(command)
    return usable, skipped


def build_bootstrap_plan(commands: list[HubCommand], hub_name: str, cog_names: list[str]) -> SuggestionPlan:
    hub_name = validate_hub_name(hub_name)
    requested = {name.casefold(): name for name in cog_names}
    selected = [
        command
        for command in commands
        if (command.cog_name or "").casefold() in requested and (command.cog_name or "").casefold() != "commandhub"
    ]
    usable, skipped = _eligible(selected)
    available_cogs = {(command.cog_name or "").casefold() for command in commands if command.cog_name}
    missing = [original for folded, original in requested.items() if folded not in available_cogs]
    if missing:
        raise ValueError(f"Loaded cogs not found in the command registry: {', '.join(missing)}")

    planned = PlannedHub(
        name=hub_name,
        title=hub_name.replace("-", " ").replace("_", " ").title(),
        description=f"Browse commands from {', '.join(requested.values())}.",
    )
    seen: set[str] = set()
    for command in sorted(usable, key=lambda item: ((item.cog_name or "").casefold(), item.qualified_name.casefold())):
        cog_name = command.cog_name or "Unsorted"
        if cog_name.casefold() not in requested or command.key in seen:
            continue
        seen.add(command.key)
        planned.categories.setdefault(cog_name[:100], []).append(
            PlannedCommand(command, is_potentially_destructive(command.qualified_name)),
        )
    return SuggestionPlan("bootstrap", {hub_name: planned}, skipped)


def classify_command(command: HubCommand, metadata: CogMetadata | None = None) -> str:
    text_parts = [command.qualified_name, command.display_name, command.description, command.cog_name or ""]
    if metadata:
        text_parts.extend((metadata.description, *metadata.tags))
    words = re.findall(r"[a-z0-9]+", " ".join(text_parts).casefold())
    scores = dict.fromkeys(KEYWORDS, 0)
    for word in words:
        for hub, keywords in KEYWORDS.items():
            scores[hub] += sum(
                weight for keyword, weight in keywords.items() if word == keyword or (len(keyword) >= 4 and keyword in word)
            )
    if command.required_user_permissions:
        scores["admin"] += 8
    priority = {"admin": 5, "music": 4, "fun": 3, "community": 2, "utility": 1}
    winner = max(scores, key=lambda hub: (scores[hub], priority[hub]))
    return winner if scores[winner] >= 2 else "other"


def build_suggestion_plan(
    commands: list[HubCommand],
    metadata: dict[str, CogMetadata] | None = None,
) -> SuggestionPlan:
    metadata = metadata or {}
    usable, skipped = _eligible(commands)
    hubs: dict[str, PlannedHub] = {}
    seen: set[str] = set()
    for command in sorted(usable, key=lambda item: item.qualified_name.casefold()):
        if command.key in seen:
            continue
        seen.add(command.key)
        cog_name = command.cog_name or "Unsorted"
        hub_name = classify_command(command, metadata.get(cog_name.casefold()))
        title, description = HUB_DETAILS[hub_name]
        hub = hubs.setdefault(hub_name, PlannedHub(hub_name, title, description))
        category = cog_name if hub_name != "other" else f"Unsorted · {cog_name}"
        hub.categories.setdefault(category[:100], []).append(
            PlannedCommand(command, is_potentially_destructive(command.qualified_name)),
        )
    return SuggestionPlan("suggest", hubs, skipped)
