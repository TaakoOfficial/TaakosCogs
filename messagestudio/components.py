"""Components V2 payload parsing and legacy Discord embed conversion."""

from __future__ import annotations

import base64
import binascii
import copy
import io
import json
from datetime import datetime
from typing import Any

import discord
import yaml
from redbot.core import commands

COMPONENTS_V2_FLAG = 1 << 15
MAX_COMPONENTS = 40
MAX_DISPLAY_CHARACTERS = 4000


class ComponentsV2Error(commands.BadArgument):
    """Raised when a Components V2 payload cannot be converted safely."""


def load_payload(argument: str, conversion_type: str = "json") -> Any:
    """Load JSON or YAML without mutating the caller's data."""
    argument = argument.strip()
    if argument.startswith("```") and argument.endswith("```"):
        argument = argument[3:-3].strip()
        if argument.startswith(("json\n", "yaml\n", "yml\n")):
            argument = argument.split("\n", 1)[1]
    try:
        if conversion_type == "json":
            return json.loads(argument)
        return yaml.safe_load(argument)
    except (json.JSONDecodeError, yaml.YAMLError) as error:
        raise ComponentsV2Error(f"Could not parse {conversion_type.upper()}: {error}") from error


def payload_to_view(payload: Any) -> discord.ui.LayoutView:
    """Convert native Components V2 or legacy Discord embed data to a LayoutView."""
    _require_components_v2()
    payload = copy.deepcopy(payload)
    if _is_native_payload(payload):
        if isinstance(payload, dict) and any(payload.get(key) for key in ("content", "embed", "embeds")):
            raise ComponentsV2Error(
                "Native Components V2 cannot be combined with legacy `content` or `embeds`. "
                "Remove `components` to have this builder convert a legacy embed payload.",
            )
        components = payload.get("components", []) if isinstance(payload, dict) else payload
    else:
        components = legacy_embeds_to_components(payload)

    if not isinstance(components, list) or not components:
        raise ComponentsV2Error("The payload must contain at least one component.")

    view = discord.ui.LayoutView(timeout=None)
    try:
        for component in components:
            view.add_item(_build_component(component, location="top"))
    except ComponentsV2Error:
        raise
    except (TypeError, ValueError, KeyError) as error:
        raise ComponentsV2Error(f"Invalid Components V2 layout: {error}") from error

    component_count = sum(1 for _ in view.walk_children())
    if component_count > MAX_COMPONENTS:
        raise ComponentsV2Error(
            f"The layout has {component_count} components; Discord allows {MAX_COMPONENTS}.",
        )
    display_length = view.content_length()
    if display_length > MAX_DISPLAY_CHARACTERS:
        raise ComponentsV2Error(
            f"Text displays contain {display_length} characters; Discord allows {MAX_DISPLAY_CHARACTERS}.",
        )
    return view


def view_to_payload(view: discord.ui.LayoutView) -> dict[str, Any]:
    """Serialize a LayoutView as a Discord API message payload."""
    return {"flags": COMPONENTS_V2_FLAG, "components": view.to_components()}


def payload_to_files(payload: Any) -> list[discord.File]:
    """Decode optional dashboard-uploaded files from a message payload."""
    if not isinstance(payload, dict) or "uploads" not in payload:
        return []
    uploads = payload.get("uploads")
    if not isinstance(uploads, list) or len(uploads) > 10:
        raise ComponentsV2Error("`uploads` must be a list containing no more than 10 files.")
    files = []
    total_size = 0
    for upload in uploads:
        if not isinstance(upload, dict):
            raise ComponentsV2Error("Every upload must be an object.")
        filename = str(upload.get("filename", "")).replace("/", "_").replace("\\", "_")
        encoded = upload.get("data")
        if not filename or not isinstance(encoded, str):
            raise ComponentsV2Error("Every upload requires a filename and base64 data.")
        try:
            raw = base64.b64decode(encoded, validate=True)
        except (ValueError, binascii.Error) as error:
            raise ComponentsV2Error(f"Upload `{filename}` is not valid base64 data.") from error
        total_size += len(raw)
        if len(raw) > 10_000_000 or total_size > 25_000_000:
            raise ComponentsV2Error("Uploads are limited to 10 MB each and 25 MB total.")
        files.append(discord.File(io.BytesIO(raw), filename=filename, spoiler=bool(upload.get("spoiler"))))
    return files


def _require_components_v2() -> None:
    if not hasattr(discord.ui, "LayoutView"):
        raise ComponentsV2Error(
            "This cog requires discord.py 2.6 or newer (LayoutView support). Update Red first.",
        )


def _is_native_payload(payload: Any) -> bool:
    if isinstance(payload, list):
        return bool(payload) and all(isinstance(item, dict) and "type" in item for item in payload)
    return isinstance(payload, dict) and "components" in payload


def _media_url(value: Any, field: str = "media") -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, dict) and isinstance(value.get("url"), str):
        return value["url"]
    raise ComponentsV2Error(f"`{field}` must be a URL string or an object containing `url`.")


def _optional_id(data: dict[str, Any]) -> int | None:
    value = data.get("id")
    if value is None:
        return None
    if not isinstance(value, int) or isinstance(value, bool):
        raise ComponentsV2Error("Component `id` values must be integers.")
    return value


def _emoji(value: Any) -> str | discord.PartialEmoji | None:
    if value is None or isinstance(value, str):
        return value
    if not isinstance(value, dict):
        raise ComponentsV2Error("Button `emoji` must be a string or Discord emoji object.")
    emoji_id = value.get("id")
    return discord.PartialEmoji(
        name=value.get("name") or "_",
        animated=bool(value.get("animated", False)),
        id=int(emoji_id) if emoji_id is not None else None,
    )


def _build_button(data: dict[str, Any]) -> discord.ui.Button:
    style = int(data.get("style", 2))
    disabled = bool(data.get("disabled", False))
    custom_id = data.get("custom_id")
    url = data.get("url")
    sku_id = data.get("sku_id")
    if style not in range(1, 7):
        raise ComponentsV2Error("Button `style` must be between 1 and 6.")
    button = discord.ui.Button(
        style=discord.ButtonStyle(style),
        label=data.get("label"),
        disabled=disabled,
        custom_id=custom_id,
        url=url,
        sku_id=int(sku_id) if sku_id is not None else None,
        emoji=_emoji(data.get("emoji")),
        id=_optional_id(data),
    )
    if not disabled and url is None and sku_id is None and not data.get("actions"):
        _attach_fallback_callback(button, data)
    return button


def _attach_fallback_callback(item: discord.ui.Item, data: dict[str, Any]) -> None:
    """Give imported custom-ID controls a valid interaction response."""
    response = str(
        data.get("response") or "This control has no custom action configured in MessageStudio yet.",
    )

    async def callback(interaction: discord.Interaction) -> None:
        await interaction.response.send_message(response[:2000], ephemeral=True)

    item.callback = callback


def _build_select(data: dict[str, Any], component_type: int) -> discord.ui.Item:
    """Build any Discord message select supported by Action Rows."""
    common = {
        "custom_id": data.get("custom_id", discord.utils.MISSING),
        "placeholder": data.get("placeholder"),
        "min_values": int(data.get("min_values", 1)),
        "max_values": int(data.get("max_values", 1)),
        "disabled": bool(data.get("disabled", False)),
        "id": _optional_id(data),
    }
    if component_type != 3 and data.get("default_values") is not None:
        defaults = data["default_values"]
        if not isinstance(defaults, list):
            raise ComponentsV2Error("Select `default_values` must be a list.")
        try:
            common["default_values"] = [
                discord.SelectDefaultValue(
                    id=int(value["id"]),
                    type=discord.SelectDefaultValueType(str(value["type"])),
                )
                for value in defaults
                if isinstance(value, dict)
            ]
        except (KeyError, TypeError, ValueError) as error:
            raise ComponentsV2Error(
                "Select defaults require an `id` and a type of user, role, or channel.",
            ) from error
        if len(common["default_values"]) != len(defaults):
            raise ComponentsV2Error("Every Select default value must be an object.")
    if component_type == 3:
        options = data.get("options")
        if not isinstance(options, list) or not 1 <= len(options) <= 25:
            raise ComponentsV2Error("A String Select requires 1 to 25 options.")
        common["options"] = [
            discord.SelectOption(
                label=str(option.get("label", "")),
                value=str(option.get("value", option.get("label", ""))),
                description=option.get("description"),
                emoji=_emoji(option.get("emoji")),
                default=bool(option.get("default", False)),
            )
            for option in options
            if isinstance(option, dict)
        ]
        if len(common["options"]) != len(options):
            raise ComponentsV2Error("Every String Select option must be an object.")
        select = discord.ui.Select(**common)
    elif component_type == 5:
        select = discord.ui.UserSelect(**common)
    elif component_type == 6:
        select = discord.ui.RoleSelect(**common)
    elif component_type == 7:
        select = discord.ui.MentionableSelect(**common)
    else:
        channel_types = data.get("channel_types")
        if channel_types is not None:
            if not isinstance(channel_types, list):
                raise ComponentsV2Error("Channel Select `channel_types` must be a list.")
            common["channel_types"] = [discord.ChannelType(int(value)) for value in channel_types]
        select = discord.ui.ChannelSelect(**common)
    if not common["disabled"] and not data.get("actions"):
        _attach_fallback_callback(select, data)
    return select


def _build_component(data: Any, *, location: str) -> discord.ui.Item:
    if not isinstance(data, dict):
        raise ComponentsV2Error("Every component must be a JSON/YAML object.")
    try:
        component_type = int(data["type"])
    except (KeyError, TypeError, ValueError) as error:
        raise ComponentsV2Error("Every component requires an integer `type`.") from error

    component_id = _optional_id(data)
    if component_type == 10:
        content = data.get("content")
        if not isinstance(content, str) or not content:
            raise ComponentsV2Error("Text Display `content` must be a non-empty string.")
        return discord.ui.TextDisplay(content, id=component_id)

    if component_type == 11:
        if location != "accessory":
            raise ComponentsV2Error("A Thumbnail (type 11) can only be a Section accessory.")
        return discord.ui.Thumbnail(
            _media_url(data.get("media")),
            description=data.get("description"),
            spoiler=bool(data.get("spoiler", False)),
            id=component_id,
        )

    if component_type == 2:
        if location not in {"accessory", "action_row"}:
            raise ComponentsV2Error("A Button (type 2) must be in an Action Row or Section accessory.")
        return _build_button(data)

    if component_type in {3, 5, 6, 7, 8}:
        if location != "action_row":
            raise ComponentsV2Error("Select menus must be inside an Action Row.")
        return _build_select(data, component_type)

    if component_type == 9:
        children = data.get("components")
        accessory = data.get("accessory")
        if not isinstance(children, list) or not 1 <= len(children) <= 3:
            raise ComponentsV2Error("A Section requires 1 to 3 Text Display components.")
        if not isinstance(accessory, dict):
            raise ComponentsV2Error("A Section requires a Button or Thumbnail `accessory`.")
        return discord.ui.Section(
            *[_build_component(child, location="section") for child in children],
            accessory=_build_component(accessory, location="accessory"),
            id=component_id,
        )

    if component_type == 12:
        items = data.get("items")
        if not isinstance(items, list) or not 1 <= len(items) <= 10:
            raise ComponentsV2Error("A Media Gallery requires 1 to 10 `items`.")
        gallery_items = [
            discord.MediaGalleryItem(
                _media_url(item.get("media"), "items[].media"),
                description=item.get("description"),
                spoiler=bool(item.get("spoiler", False)),
            )
            for item in items
            if isinstance(item, dict)
        ]
        if len(gallery_items) != len(items):
            raise ComponentsV2Error("Every Media Gallery item must be an object.")
        return discord.ui.MediaGallery(*gallery_items, id=component_id)

    if component_type == 13:
        media = _media_url(data.get("file", data.get("media")), "file")
        if not media.startswith("attachment://"):
            raise ComponentsV2Error("File components must use an `attachment://filename` URL.")
        return discord.ui.File(media, spoiler=bool(data.get("spoiler", False)), id=component_id)

    if component_type == 14:
        spacing = int(data.get("spacing", 1))
        if spacing not in (1, 2):
            raise ComponentsV2Error("Separator `spacing` must be 1 (small) or 2 (large).")
        return discord.ui.Separator(
            visible=bool(data.get("divider", data.get("visible", True))),
            spacing=discord.SeparatorSpacing(spacing),
            id=component_id,
        )

    if component_type == 1:
        children = data.get("components")
        if not isinstance(children, list) or not 1 <= len(children) <= 5:
            raise ComponentsV2Error("An Action Row requires 1 to 5 child controls.")
        supported_controls = {2, 3, 5, 6, 7, 8}
        if any(not isinstance(child, dict) or int(child.get("type", 0)) not in supported_controls for child in children):
            raise ComponentsV2Error(
                "Action Rows support Buttons and string, user, role, mentionable, or channel selects.",
            )
        return discord.ui.ActionRow(
            *[_build_component(child, location="action_row") for child in children],
            id=component_id,
        )

    if component_type == 17:
        children = data.get("components")
        if not isinstance(children, list) or not 1 <= len(children) <= 10:
            raise ComponentsV2Error("A Container requires 1 to 10 child components.")
        accent = data.get("accent_color", data.get("accent_colour"))
        return discord.ui.Container(
            *[_build_component(child, location="container") for child in children],
            accent_color=int(accent) if accent is not None else None,
            spoiler=bool(data.get("spoiler", False)),
            id=component_id,
        )

    raise ComponentsV2Error(f"Unsupported message component type: {component_type}.")


def legacy_embeds_to_components(payload: Any) -> list[dict[str, Any]]:
    """Translate legacy Discord embed JSON into native Components V2 dictionaries."""
    content: str | None = None
    embeds: list[dict[str, Any]]
    if isinstance(payload, list):
        embeds = payload
    elif not isinstance(payload, dict):
        raise ComponentsV2Error("The payload must be an object or list.")
    else:
        content = payload.get("content")
        if "embeds" in payload:
            embeds = payload.get("embeds") or []
            if isinstance(embeds, dict):
                embeds = list(embeds.values())
        elif "embed" in payload:
            embeds = [payload["embed"]]
        elif any(key in payload for key in ("title", "description", "fields", "image")):
            embeds = [payload]
        else:
            embeds = []

    if content is not None and not isinstance(content, str):
        raise ComponentsV2Error("Legacy message `content` must be a string.")
    if not isinstance(embeds, list) or any(not isinstance(embed, dict) for embed in embeds):
        raise ComponentsV2Error("Legacy message `embeds` must be a list of objects.")

    components: list[dict[str, Any]] = []
    if content:
        components.append({"type": 10, "content": content})
    for embed in embeds:
        components.append(_embed_to_container(embed))
    if not components:
        raise ComponentsV2Error("No Components V2 data or legacy content/embeds were found.")
    return components


def _embed_to_container(embed: dict[str, Any]) -> dict[str, Any]:
    children: list[dict[str, Any]] = []
    author = embed.get("author") or {}
    if author.get("name"):
        name = str(author["name"])
        author_url = author.get("url")
        children.append({"type": 10, "content": f"### [{name}]({author_url})" if author_url else f"### {name}"})

    title = embed.get("title")
    if title:
        url = embed.get("url")
        title_text = f"[{title}]({url})" if url else str(title)
        children.append({"type": 10, "content": f"## {title_text}"})
    if embed.get("description"):
        children.append({"type": 10, "content": str(embed["description"])})

    fields = embed.get("fields") or []
    if not isinstance(fields, list):
        raise ComponentsV2Error("Embed `fields` must be a list.")
    for field in fields:
        if not isinstance(field, dict):
            raise ComponentsV2Error("Every embed field must be an object.")
        field_name = field.get("name", "\u200b")
        field_value = field.get("value", "\u200b")
        children.append(
            {
                "type": 10,
                "content": f"**{field_name}**\n{field_value}",
            },
        )

    image = embed.get("image") or {}
    if image.get("url"):
        children.append({"type": 12, "items": [{"media": {"url": image["url"]}}]})
    thumbnail = embed.get("thumbnail") or {}
    if thumbnail.get("url"):
        children.append({"type": 12, "items": [{"media": {"url": thumbnail["url"]}}]})

    footer_parts: list[str] = []
    footer = embed.get("footer") or {}
    if footer.get("text"):
        footer_parts.append(str(footer["text"]))
    if embed.get("timestamp"):
        timestamp = str(embed["timestamp"])
        try:
            parsed = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
            footer_parts.append(f"<t:{int(parsed.timestamp())}:f>")
        except ValueError:
            footer_parts.append(timestamp)
    if footer_parts:
        children.append({"type": 10, "content": "-# " + " • ".join(footer_parts)})
    if not children:
        children.append({"type": 10, "content": "\u200b"})

    color = embed.get("color", embed.get("colour"))
    if isinstance(color, str):
        color = int(color.removeprefix("#"), 16)
    container: dict[str, Any] = {"type": 17, "components": children}
    if color is not None:
        container["accent_color"] = color
    return container
