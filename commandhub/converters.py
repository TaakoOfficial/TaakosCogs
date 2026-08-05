"""Modal-text converters with no fabricated Discord objects."""

from __future__ import annotations

import re
from typing import Any

import discord

from .models import CommandParameter, ParameterKind

ID_RE = re.compile(r"^(?:<[@#&!]*(\d{15,22})>|(\d{15,22}))$")
TRUE_VALUES = {"true", "yes", "y", "on", "1"}
FALSE_VALUES = {"false", "no", "n", "off", "0"}


class ConversionError(ValueError):
    pass


def _validate_bounds(parameter: CommandParameter, converted: Any) -> Any:
    measured = len(converted) if isinstance(converted, str) else converted
    if parameter.minimum is not None and measured < parameter.minimum:
        label = "length" if isinstance(converted, str) else "value"
        raise ConversionError(f"{parameter.name} {label} must be at least {parameter.minimum}.")
    if parameter.maximum is not None and measured > parameter.maximum:
        label = "length" if isinstance(converted, str) else "value"
        raise ConversionError(f"{parameter.name} {label} must be at most {parameter.maximum}.")
    return converted


def extract_id(value: str) -> int | None:
    match = ID_RE.fullmatch(value.strip())
    return int(match.group(1) or match.group(2)) if match else None


def _named(items: list[Any], value: str, label: str) -> Any:
    item_id = extract_id(value)
    if item_id is not None:
        found = discord.utils.get(items, id=item_id)
        if found is not None:
            return found
    matches = [item for item in items if getattr(item, "name", "").casefold() == value.strip().casefold()]
    if len(matches) == 1:
        return matches[0]
    if len(matches) > 1:
        raise ConversionError(f"More than one {label} has that name; use a mention or ID.")
    raise ConversionError(f"No {label} matching `{value}` was found.")


async def convert_argument(interaction: discord.Interaction, parameter: CommandParameter, value: str) -> Any:
    raw = value.strip()
    if not raw and not parameter.required:
        return parameter.default
    if not raw:
        raise ConversionError(f"{parameter.name} is required.")
    kind = parameter.kind
    try:
        if kind is ParameterKind.STRING:
            return _validate_bounds(parameter, value)
        if kind is ParameterKind.INTEGER:
            return _validate_bounds(parameter, int(raw))
        if kind is ParameterKind.FLOAT:
            return _validate_bounds(parameter, float(raw))
        if kind is ParameterKind.BOOLEAN:
            folded = raw.casefold()
            if folded in TRUE_VALUES:
                return True
            if folded in FALSE_VALUES:
                return False
            raise ConversionError("Enter yes/no, true/false, on/off, or 1/0.")
        if kind is ParameterKind.CHOICE:
            folded = raw.casefold()
            for name, choice_value in parameter.choices.items():
                if name.casefold() == folded or str(choice_value).casefold() == folded:
                    return choice_value
            raise ConversionError(f"Choose one of: {', '.join(parameter.choices)}")
    except (TypeError, ValueError) as exc:
        if isinstance(exc, ConversionError):
            raise
        raise ConversionError(f"`{raw}` is not a valid {kind.value}.") from exc

    guild = interaction.guild
    if guild is None:
        raise ConversionError("Discord entity parameters require a server.")
    if kind is ParameterKind.MEMBER:
        return _named(list(guild.members), raw, "member")
    if kind is ParameterKind.USER:
        user_id = extract_id(raw)
        if user_id is not None:
            user = interaction.client.get_user(user_id)
            if user is not None:
                return user
        return _named(list(guild.members), raw, "user")
    if kind is ParameterKind.ROLE:
        return _named(list(guild.roles), raw, "role")
    if kind in {ParameterKind.CHANNEL, ParameterKind.TEXT_CHANNEL, ParameterKind.VOICE_CHANNEL}:
        channels = list(guild.channels)
        if kind is ParameterKind.TEXT_CHANNEL:
            channels = [item for item in channels if isinstance(item, discord.TextChannel)]
        elif kind is ParameterKind.VOICE_CHANNEL:
            channels = [item for item in channels if isinstance(item, discord.VoiceChannel)]
        return _named(channels, raw, "channel")
    if kind is ParameterKind.MENTIONABLE:
        return _named([*guild.members, *guild.roles], raw, "member or role")
    raise ConversionError(f"Parameter type `{kind.value}` cannot be collected safely.")


def serialize_prefix_argument(value: Any) -> str:
    """Quote parser input and express Discord entities as unambiguous IDs/mentions."""
    if isinstance(value, discord.Member | discord.User):
        return f"<@{value.id}>"
    if isinstance(value, discord.Role):
        return f"<@&{value.id}>"
    if isinstance(value, discord.abc.GuildChannel):
        return f"<#{value.id}>"
    if isinstance(value, bool):
        return "true" if value else "false"
    text = str(value)
    return '"' + text.replace("\\", "\\\\").replace('"', '\\"') + '"'
