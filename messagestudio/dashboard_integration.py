"""Red-Web-Dashboard visual editor and sender for MessageStudio."""

from __future__ import annotations

import html
import json
import logging
from pathlib import Path
from typing import Any, Callable

import discord
from redbot.core import commands

from .components import ComponentsV2Error, load_payload, payload_to_files, payload_to_view

log = logging.getLogger("red.taakoscogs.messagestudio.dashboard")


def dashboard_page(*args, **kwargs):
    """Mark a callback as a Red-Web-Dashboard third-party page."""

    def decorator(func: Callable):
        func.__dashboard_decorator_params__ = (args, kwargs)
        return func

    return decorator


class DashboardIntegration:
    """Dashboard integration mixin for the standalone visual builder."""

    @commands.Cog.listener()
    async def on_dashboard_cog_add(self, dashboard_cog: commands.Cog) -> None:
        """Register this cog with Red-Web-Dashboard."""
        handler = dashboard_cog.rpc.third_parties_handler
        try:
            handler.add_third_party(self, overwrite=True)
        except TypeError:
            handler.add_third_party(self)

    @dashboard_page(
        name=None,
        description="Open the standalone visual MessageStudio builder.",
        methods=("GET",),
    )
    async def dashboard_editor(self, **kwargs: Any) -> dict[str, Any]:
        """Render the dedicated editor page without guild sending controls."""
        source = self._load_editor(
            csrf="",
            payload=self._example_payload(),
            channel_options="",
            guild_name="Standalone editor",
            guild_id="global",
            send_enabled=False,
            stored_messages={},
            form_action="",
        )
        return {
            "status": 0,
            "web_content": {"source": source, "standalone": True},
        }

    @dashboard_page(
        name="guild",
        description="Build and send Components V2 messages to a server.",
        methods=("GET", "POST"),
    )
    async def dashboard_guild(
        self,
        user: discord.User,
        guild: discord.Guild,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Render the visual builder and process its channel sends."""
        member = guild.get_member(user.id)
        is_owner = user.id in getattr(self.bot, "owner_ids", set())
        is_admin = member is not None and await self.bot.is_admin(member)
        if not (is_owner or is_admin or (member and member.guild_permissions.manage_guild)):
            return {
                "status": 1,
                "error_title": "Insufficient Permissions",
                "error_message": "You need Manage Server, Red admin, or bot owner access.",
            }

        notifications: list[dict[str, str]] = []
        form = self._dashboard_form(kwargs)
        payload_text = self._dashboard_value(form, "payload") or self._example_payload()
        selected_channel = self._dashboard_value(form, "channel_id")

        if kwargs.get("method", "GET") == "POST":
            action = self._dashboard_value(form, "dashboard_action", "send")
            try:
                payload = load_payload(payload_text, "json")
                view = payload_to_view(payload)
                files = payload_to_files(payload)
                if action == "store":
                    name = self._dashboard_value(form, "store_name").strip()
                    if not name or len(name) > 100:
                        raise ComponentsV2Error("Saved-message names must contain 1 to 100 characters.")
                    locked = self._dashboard_value(form, "store_locked").lower() in {
                        "1",
                        "true",
                        "on",
                        "yes",
                    }
                    async with self.config.guild(guild).stored_messages() as stored:
                        if name not in stored and len(stored) >= 100:
                            raise ComponentsV2Error("This server has reached the 100-message limit.")
                        stored[name] = {
                            "author": user.id,
                            "payload": payload,
                            "locked": locked,
                            "uses": 0,
                        }
                    notifications.append(
                        {"message": f"Saved `{name}` to Stored Messages.", "category": "success"},
                    )
                else:
                    channel_id = int(selected_channel)
                    channel = guild.get_channel(channel_id)
                    if not isinstance(channel, (discord.TextChannel, discord.VoiceChannel, discord.Thread)):
                        raise ComponentsV2Error("Choose a valid text-capable channel.")
                    if member is not None and not is_owner and not channel.permissions_for(member).send_messages:
                        raise ComponentsV2Error("You cannot send messages in that channel.")
                    if not channel.permissions_for(guild.me).send_messages:
                        raise ComponentsV2Error("The bot cannot send messages in that channel.")
                    component_actions = await self._prepare_actions(payload, guild, member or user)
                    message = await channel.send(
                        view=view,
                        files=files,
                        allowed_mentions=discord.AllowedMentions.none(),
                    )
                    await self._register_message_actions(
                        message,
                        component_actions,
                        member or user,
                        guild=guild,
                    )
                    notifications.append(
                        {"message": f"Components V2 message sent in #{channel.name}.", "category": "success"},
                    )
            except (ComponentsV2Error, ValueError) as error:
                notifications.append({"message": str(error), "category": "danger"})
            except discord.HTTPException as error:
                notifications.append(
                    {"message": f"Discord rejected the message: {error}", "category": "danger"},
                )
            except Exception as error:
                log.exception("Components V2 dashboard send failed")
                notifications.append(
                    {"message": f"Could not send the message: {error}", "category": "danger"},
                )
            if self._dashboard_value(form, "dashboard_ajax") == "1":
                notification = notifications[-1]
                return {
                    "status": 0,
                    "data": {
                        "ok": notification["category"] == "success",
                        "message": notification["message"],
                        "action": action,
                        "name": self._dashboard_value(form, "store_name").strip(),
                    },
                }

        source = self._load_editor(
            csrf=self._dashboard_csrf(kwargs),
            payload=payload_text,
            channel_options=self._channel_options(guild, selected_channel),
            guild_name=guild.name,
            guild_id=guild.id,
            send_enabled=True,
            stored_messages=await self.config.guild(guild).stored_messages(),
            form_action=kwargs.get("request_url", ""),
        )
        return {
            "status": 0,
            "notifications": notifications,
            "web_content": {"source": source, "standalone": True},
        }

    @staticmethod
    def _dashboard_form(kwargs: dict[str, Any]) -> Any:
        data = kwargs.get("data") or {}
        if isinstance(data, dict) and ("form" in data or "json" in data):
            return data.get("form") or data.get("json") or {}
        return data

    @staticmethod
    def _dashboard_value(form: Any, key: str, default: str = "") -> str:
        value = form.get(key, default) if hasattr(form, "get") else default
        if isinstance(value, (list, tuple)):
            value = value[0] if value else default
        return default if value is None else str(value)

    @staticmethod
    def _dashboard_csrf(kwargs: dict[str, Any]) -> str:
        token = kwargs.get("csrf_token")
        if not isinstance(token, (tuple, list)) or len(token) != 2:
            return ""
        value = html.escape(str(token[1]), quote=True)
        return f'<input type="hidden" name="csrf_token" value="{value}">'

    @staticmethod
    def _channel_options(guild: discord.Guild, selected_channel: str) -> str:
        options = []
        for channel in guild.channels:
            if (
                isinstance(channel, (discord.TextChannel, discord.VoiceChannel))
                and channel.permissions_for(guild.me).send_messages
            ):
                selected = " selected" if str(channel.id) == selected_channel else ""
                options.append(
                    f'<option value="{channel.id}"{selected}>#{html.escape(channel.name)}</option>',
                )
        return "".join(options)

    @staticmethod
    def _load_editor(
        *,
        csrf: str,
        payload: str,
        channel_options: str,
        guild_name: str,
        guild_id: int | str,
        send_enabled: bool,
        stored_messages: dict[str, Any],
        form_action: str,
    ) -> str:
        source = Path(__file__).with_name("editor.html").read_text(encoding="utf-8")
        replacements = {
            "%%CSRF%%": csrf,
            "%%PAYLOAD%%": html.escape(payload),
            "%%CHANNEL_OPTIONS%%": channel_options,
            "%%GUILD_NAME%%": html.escape(guild_name),
            "%%GUILD_ID%%": str(guild_id),
            "%%SEND_HIDDEN%%": "" if send_enabled else "hidden",
            "%%STORED_MESSAGES%%": json.dumps(stored_messages).replace("<", "\\u003c"),
            "%%FORM_ACTION%%": html.escape(form_action, quote=True),
        }
        for marker, value in replacements.items():
            source = source.replace(marker, value)
        return source

    @staticmethod
    def _example_payload() -> str:
        return json.dumps(
            {
                "flags": 32768,
                "components": [
                    {
                        "type": 17,
                        "accent_color": 5793266,
                        "spoiler": False,
                        "components": [
                            {"type": 10, "content": "## Welcome to Components V2"},
                            {
                                "type": 10,
                                "content": "Build this message visually, then send it directly to Discord.",
                            },
                            {"type": 14, "divider": True, "spacing": 1},
                            {
                                "type": 1,
                                "components": [
                                    {
                                        "type": 2,
                                        "style": 5,
                                        "label": "Discord Components",
                                        "url": "https://discord.com/developers/docs/components/reference",
                                    },
                                ],
                            },
                        ],
                    },
                ],
            },
            indent=2,
        )
