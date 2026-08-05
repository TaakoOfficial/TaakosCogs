"""Cached discovery and normalization for Red and Discord commands."""

from __future__ import annotations

import asyncio
import inspect
import logging
from datetime import datetime, timezone
from types import UnionType
from typing import TYPE_CHECKING, Any, Union, get_args, get_origin

import discord
from discord.ext import commands as dpy_commands
from redbot.core import app_commands, commands

from .models import CommandParameter, CommandSource, HubCommand, ParameterKind

if TYPE_CHECKING:
    from .integrations import SlashLinkAdapter

log = logging.getLogger("red.taakoscogs.commandhub.registry")


def _unwrap_optional(annotation: Any) -> tuple[Any, bool]:
    origin = get_origin(annotation)
    if origin in (Union, UnionType):
        args = get_args(annotation)
        remaining = [item for item in args if item is not type(None)]
        if len(remaining) == 1 and len(remaining) != len(args):
            return remaining[0], True
    return annotation, False


def parameter_kind(annotation: Any) -> ParameterKind:
    annotation, _ = _unwrap_optional(annotation)
    if isinstance(annotation, dpy_commands.Greedy):
        annotation = annotation.converter
    origin = get_origin(annotation)
    if origin is not None and "Greedy" in str(origin):
        annotation = get_args(annotation)[0]
    mapping = {
        str: ParameterKind.STRING,
        int: ParameterKind.INTEGER,
        float: ParameterKind.FLOAT,
        bool: ParameterKind.BOOLEAN,
        discord.Member: ParameterKind.MEMBER,
        discord.User: ParameterKind.USER,
        discord.Role: ParameterKind.ROLE,
        discord.TextChannel: ParameterKind.TEXT_CHANNEL,
        discord.VoiceChannel: ParameterKind.VOICE_CHANNEL,
    }
    try:
        if annotation in mapping:
            return mapping[annotation]
    except TypeError:
        return ParameterKind.UNSUPPORTED
    try:
        if inspect.isclass(annotation) and issubclass(annotation, discord.abc.GuildChannel):
            return ParameterKind.CHANNEL
    except TypeError:
        pass
    if annotation in (inspect.Parameter.empty, Any, None):
        return ParameterKind.STRING
    return ParameterKind.UNSUPPORTED


def normalize_prefix(command: commands.Command[Any, ..., Any]) -> HubCommand:
    clean_params = getattr(command, "clean_params", {})
    parameters: list[CommandParameter] = []
    for name, param in clean_params.items():
        annotation, optional = _unwrap_optional(param.annotation)
        greedy = isinstance(getattr(param, "converter", None), dpy_commands.Greedy)
        kind = parameter_kind(annotation)
        parameters.append(
            CommandParameter(
                name=name,
                description="",
                kind=kind,
                required=param.default is inspect.Parameter.empty and not optional,
                default=None if param.default is inspect.Parameter.empty else param.default,
                greedy=greedy,
                remainder=bool(getattr(command, "rest_is_raw", False) and name == next(reversed(clean_params), "")),
                sensitive=any(token in name.casefold() for token in ("token", "password", "secret", "key")),
            ),
        )
    source = CommandSource.HYBRID if getattr(command, "__commands_is_hybrid__", False) else CommandSource.PREFIX
    unsupported = next(
        (
            f"Unsupported parameter `{item.name}` ({'greedy collection' if item.greedy else item.kind.value})."
            for item in parameters
            if item.kind is ParameterKind.UNSUPPORTED or item.greedy
        ),
        None,
    )
    requirements = getattr(command, "requires", None)
    user_permissions = getattr(getattr(requirements, "user_perms", None), "value", 0)
    bot_permissions = getattr(getattr(requirements, "bot_perms", None), "value", 0)
    return HubCommand(
        source=source,
        qualified_name=command.qualified_name,
        display_name=command.qualified_name,
        description=(command.short_doc or "No description provided.")[:100],
        cog_name=command.cog.qualified_name if command.cog else None,
        category=command.cog.qualified_name if command.cog else None,
        parameters=parameters,
        checks=list(command.checks),
        required_user_permissions=user_permissions,
        required_bot_permissions=bot_permissions,
        enabled=command.enabled,
        callback=command,
        unsupported_reason=unsupported,
    )


def _app_kind(parameter: Any) -> ParameterKind:
    command_type = getattr(parameter, "type", None)
    channel_types = set(getattr(parameter, "channel_types", []) or [])
    if command_type is discord.AppCommandOptionType.channel:
        if channel_types and channel_types <= {discord.ChannelType.text, discord.ChannelType.news}:
            return ParameterKind.TEXT_CHANNEL
        if channel_types == {discord.ChannelType.voice}:
            return ParameterKind.VOICE_CHANNEL
        return ParameterKind.CHANNEL
    mapping = {
        discord.AppCommandOptionType.string: ParameterKind.STRING,
        discord.AppCommandOptionType.integer: ParameterKind.INTEGER,
        discord.AppCommandOptionType.number: ParameterKind.FLOAT,
        discord.AppCommandOptionType.boolean: ParameterKind.BOOLEAN,
        discord.AppCommandOptionType.user: ParameterKind.USER,
        discord.AppCommandOptionType.role: ParameterKind.ROLE,
        discord.AppCommandOptionType.mentionable: ParameterKind.MENTIONABLE,
    }
    return mapping.get(command_type, ParameterKind.UNSUPPORTED)


def normalize_application(command: app_commands.Command[Any, ..., Any], parents: tuple[str, ...] = ()) -> HubCommand:
    qualified = " ".join((*parents, command.name))
    parameters = []
    for parameter in command.parameters:
        choices = {choice.name: choice.value for choice in getattr(parameter, "choices", [])}
        internal = getattr(command, "_params", {}).get(parameter.name)
        transformer = getattr(internal, "_annotation", None)
        kind = ParameterKind.CHOICE if choices else _app_kind(parameter)
        if transformer is not None and type(transformer).__module__ != "discord.app_commands.transformers":
            kind = ParameterKind.UNSUPPORTED
        parameters.append(
            CommandParameter(
                name=parameter.name,
                description=parameter.description or "",
                kind=kind,
                required=parameter.required,
                default=None if parameter.required else parameter.default,
                choices=choices,
                sensitive=any(token in parameter.name.casefold() for token in ("token", "password", "secret", "key")),
                minimum=getattr(parameter, "min_value", None),
                maximum=getattr(parameter, "max_value", None),
            ),
        )
    unsupported = next(
        (
            (
                f"Unsupported parameter `{item.name}` (minimum string length exceeds the modal limit)."
                if item.kind is ParameterKind.STRING and item.minimum is not None and item.minimum > 4000
                else f"Unsupported parameter `{item.name}` ({item.kind.value})."
            )
            for item in parameters
            if item.kind is ParameterKind.UNSUPPORTED
            or (item.kind is ParameterKind.STRING and item.minimum is not None and item.minimum > 4000)
        ),
        None,
    )
    binding = getattr(command, "binding", None)
    return HubCommand(
        source=CommandSource.APPLICATION,
        qualified_name=qualified,
        display_name=qualified,
        description=(command.description or "No description provided.")[:100],
        cog_name=getattr(binding, "qualified_name", None),
        category=parents[0] if parents else getattr(binding, "qualified_name", None),
        parameters=parameters,
        checks=list(command.checks),
        callback=command,
        unsupported_reason=unsupported,
    )


class CommandRegistry:
    def __init__(self, bot: Any, slashlink: SlashLinkAdapter) -> None:
        self.bot = bot
        self.slashlink = slashlink
        self.commands: dict[str, HubCommand] = {}
        self.refreshed_at: datetime | None = None
        self.lock = asyncio.Lock()
        self.counts = dict.fromkeys(CommandSource, 0)
        self.unsupported_types: set[str] = set()

    async def refresh(self) -> None:
        async with self.lock:
            found: dict[str, HubCommand] = {}
            for command in self.bot.walk_commands():
                normalized = normalize_prefix(command)
                found[normalized.key] = normalized
            for root in self.bot.tree.get_commands():
                self._walk_application(root, (), found)
            if self.slashlink.check_compatibility():
                for item in await self.slashlink.get_linked_commands():
                    normalized = await self._normalize_slashlink(item)
                    if normalized:
                        found[normalized.key] = normalized
            self.commands = found
            self.counts = {source: sum(item.source is source for item in found.values()) for source in CommandSource}
            self.unsupported_types = {
                parameter.kind.value
                for item in found.values()
                for parameter in item.parameters
                if parameter.kind is ParameterKind.UNSUPPORTED
            }
            self.refreshed_at = datetime.now(timezone.utc)
            log.info("Command registry refreshed with %d commands.", len(found))

    def _walk_application(self, command: Any, parents: tuple[str, ...], found: dict[str, HubCommand]) -> None:
        if isinstance(command, app_commands.Group):
            for child in command.commands:
                self._walk_application(child, (*parents, command.name), found)
        elif isinstance(command, app_commands.Command) and not command.extras.get("commandhub", False):
            normalized = normalize_application(command, parents)
            # Hybrid entries use the prefix adapter, which preserves Red's full pipeline.
            hybrid_key = f"{CommandSource.HYBRID.value}:{normalized.qualified_name.casefold()}"
            if hybrid_key not in found:
                found[normalized.key] = normalized

    async def _normalize_slashlink(self, item: Any) -> HubCommand | None:
        qualified = getattr(item, "qualified_name", None) or (item.get("qualified_name") if isinstance(item, dict) else None)
        if not qualified:
            return None
        schema = await self.slashlink.get_schema(str(qualified))
        description = getattr(item, "description", None) or (item.get("description", "") if isinstance(item, dict) else "")
        return HubCommand(
            CommandSource.SLASHLINK,
            str(qualified),
            str(qualified),
            str(description or "Linked command"),
            None,
            None,
            callback=schema,
        )

    def get(self, source: CommandSource, qualified_name: str) -> HubCommand | None:
        return self.commands.get(f"{source.value}:{qualified_name.casefold()}")

    def resolve(self, reference: str) -> list[HubCommand]:
        folded = reference.casefold().strip()
        source_name, separator, qualified = folded.partition(":")
        if separator and source_name in {source.value for source in CommandSource}:
            command = self.commands.get(f"{source_name}:{qualified}")
            return [command] if command else []
        return [item for item in self.commands.values() if item.qualified_name.casefold() == folded]

    def search(self, query: str) -> list[HubCommand]:
        from .utils import rank_commands

        return rank_commands(self.commands.values(), query)
