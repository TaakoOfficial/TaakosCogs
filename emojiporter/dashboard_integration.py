"""Red-Web-Dashboard integration."""

from __future__ import annotations

import html
import json
import logging
from typing import TYPE_CHECKING, Any, Callable

from redbot.core import commands

if TYPE_CHECKING:
    import discord

log = logging.getLogger("red.taakoscogs.emojiporter.dashboard")


def dashboard_page(*args, **kwargs):
    """Dashboard page decorator compatible with Red-Web-Dashboard."""

    def decorator(func: Callable):
        func.__dashboard_decorator_params__ = (args, kwargs)
        return func

    return decorator


class DashboardIntegration:
    """Generic editable dashboard integration for guild configuration."""

    _DASHBOARD_CONFIG_LIMIT = 1_000_000

    @commands.Cog.listener()
    async def on_dashboard_cog_add(self, dashboard_cog: commands.Cog) -> None:
        """Register the cog as a Red-Web-Dashboard third party."""
        handler = dashboard_cog.rpc.third_parties_handler
        try:
            handler.add_third_party(self, overwrite=True)
        except TypeError:
            handler.add_third_party(self)

    @dashboard_page(
        name=None,
        description="View and edit this cog's server configuration.",
        methods=("GET", "POST"),
    )
    async def dashboard_page(
        self,
        user: discord.User,
        guild: discord.Guild,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Render the dashboard page and persist validated configuration changes."""
        if not await self._dashboard_can_manage(user, guild):
            return {
                "status": 1,
                "error_title": "Insufficient Permissions",
                "error_message": (
                    "You need Manage Server, Red admin, or bot owner access."
                ),
            }

        notifications: list[dict[str, str]] = []
        editor_value: str | None = None
        if kwargs.get("method", "GET").upper() == "POST":
            editor_value = self._dashboard_value(
                self._dashboard_form(kwargs),
                "config_json",
            )
            try:
                await self._dashboard_save_config(guild, kwargs)
            except (json.JSONDecodeError, ValueError, TypeError) as error:
                notifications.append({"message": str(error), "category": "error"})
            except Exception as error:
                log.exception("Dashboard save failed for %s.", self.qualified_name)
                return {
                    "status": 1,
                    "error_title": "Dashboard Error",
                    "error_message": f"Could not save server configuration: {error}",
                }
            else:
                notifications.append(
                    {
                        "message": "Server configuration saved.",
                        "category": "success",
                    },
                )
                editor_value = None

        try:
            source = await self._dashboard_source(guild, kwargs, editor_value)
        except Exception as error:
            log.exception("Dashboard render failed for %s.", self.qualified_name)
            return {
                "status": 1,
                "error_title": "Dashboard Error",
                "error_message": f"Could not render dashboard page: {error}",
            }

        return {
            "status": 0,
            "notifications": notifications,
            "web_content": {
                "source": source,
                "expanded": True,
            },
        }

    async def _dashboard_can_manage(
        self,
        user: discord.User,
        guild: discord.Guild,
    ) -> bool:
        member = guild.get_member(user.id)
        is_owner = user.id in getattr(self.bot, "owner_ids", set())
        is_admin = member is not None and await self.bot.is_admin(member)
        return bool(
            is_owner
            or is_admin
            or (member is not None and member.guild_permissions.manage_guild),
        )

    async def _dashboard_source(
        self,
        guild: discord.Guild,
        kwargs: dict[str, Any],
        editor_value: str | None = None,
    ) -> str:
        cog_name = html.escape(self.qualified_name)
        config = await self._dashboard_guild_config(guild)
        commands_html = self._dashboard_commands_html()
        config_html = self._dashboard_config_editor(config, kwargs, editor_value)

        return f"""
<section class="third-party-dashboard cog-config-dashboard">
  <style>
    .cog-config-dashboard .config-editor {{
      width: 100%; min-height: 28rem; resize: vertical;
      padding: .8rem; border: 1px solid var(--gray, #6c757d); border-radius: .35rem;
      background: var(--background, #202225); color: var(--text, #f8f9fa);
      font: .9rem/1.45 ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
    }}
    .cog-config-dashboard .config-actions {{
      display: flex; align-items: center; gap: .75rem; margin-top: .75rem;
    }}
    .cog-config-dashboard .config-help {{ opacity: .8; }}
  </style>
  <h2>{cog_name}</h2>
  <p>Manage this cog's configuration for <strong>{html.escape(guild.name)}</strong>.</p>
  <h3>Server Settings</h3>
  {config_html}
  <details>
    <summary>Available commands</summary>
    {commands_html}
  </details>
</section>
"""

    async def _dashboard_save_config(
        self,
        guild: discord.Guild,
        kwargs: dict[str, Any],
    ) -> None:
        group = self._dashboard_guild_group(guild)
        if group is None:
            raise ValueError("This cog does not store per-server configuration.")

        form = self._dashboard_form(kwargs)
        raw_config = self._dashboard_value(form, "config_json")
        if not raw_config.strip():
            raise ValueError("Configuration JSON cannot be empty.")
        if len(raw_config.encode("utf-8")) > self._DASHBOARD_CONFIG_LIMIT:
            raise ValueError("Configuration JSON is too large to save from the dashboard.")

        proposed = json.loads(
            raw_config,
            parse_constant=lambda value: self._dashboard_invalid_json_constant(value),
        )
        current = await group.all()
        defaults = self._dashboard_guild_defaults()
        self._dashboard_validate_config(current, proposed, defaults)
        await group.set(proposed)

    def _dashboard_guild_group(self, guild: discord.Guild) -> Any | None:
        config = getattr(self, "config", None) or getattr(self, "_config", None)
        guild_config = getattr(config, "guild", None) if config is not None else None
        return guild_config(guild) if guild_config is not None else None

    def _dashboard_guild_defaults(self) -> dict[str, Any]:
        config = getattr(self, "config", None) or getattr(self, "_config", None)
        defaults = getattr(config, "_defaults", {}) if config is not None else {}
        guild_defaults = defaults.get("GUILD", {}) if isinstance(defaults, dict) else {}
        return guild_defaults if isinstance(guild_defaults, dict) else {}

    async def _dashboard_guild_config(
        self,
        guild: discord.Guild,
    ) -> dict[str, Any] | None:
        group = self._dashboard_guild_group(guild)
        return None if group is None else await group.all()

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
        return (
            '<input type="hidden" name="csrf_token" value="'
            f'{html.escape(str(token[1]), quote=True)}">'
        )

    @staticmethod
    def _dashboard_invalid_json_constant(value: str) -> None:
        raise ValueError(f"{value} is not valid configuration JSON.")

    @classmethod
    def _dashboard_validate_config(
        cls,
        current: dict[str, Any],
        proposed: Any,
        defaults: dict[str, Any] | None = None,
    ) -> None:
        if not isinstance(proposed, dict):
            raise TypeError("Configuration must be a JSON object.")

        missing = sorted(set(current) - set(proposed))
        unknown = sorted(set(proposed) - set(current))
        if missing:
            raise ValueError(f"Missing configuration key(s): {', '.join(missing)}.")
        if unknown:
            raise ValueError(f"Unknown configuration key(s): {', '.join(unknown)}.")

        for key, old_value in current.items():
            new_value = proposed[key]
            expected_value = (defaults or {}).get(key, old_value)
            if expected_value is None and new_value is None:
                continue
            if expected_value is None:
                expected_value = old_value
            if expected_value is None:
                if key.endswith("_id"):
                    valid = isinstance(new_value, int) and not isinstance(new_value, bool)
                    if not valid:
                        raise TypeError(
                            f'Configuration key "{key}" must be an integer or null.',
                        )
                continue
            if isinstance(expected_value, bool):
                valid = isinstance(new_value, bool)
            elif isinstance(expected_value, int):
                valid = isinstance(new_value, int) and not isinstance(new_value, bool)
            elif isinstance(expected_value, float):
                valid = (
                    isinstance(new_value, (int, float))
                    and not isinstance(new_value, bool)
                )
            else:
                valid = isinstance(new_value, type(expected_value))
            if not valid:
                expected = cls._dashboard_type_name(expected_value)
                raise TypeError(f'Configuration key "{key}" must be {expected}.')

    @staticmethod
    def _dashboard_type_name(value: Any) -> str:
        names = {
            bool: "a boolean",
            int: "an integer",
            float: "a number",
            str: "a string",
            list: "an array",
            dict: "an object",
        }
        return names.get(type(value), type(value).__name__)

    def _dashboard_commands_html(self) -> str:
        commands_list = sorted(
            command.qualified_name
            for command in self.walk_commands()
            if not command.hidden
        )
        if not commands_list:
            return "<p>No visible commands were found for this cog.</p>"
        items = "\n".join(
            f"<li><code>{html.escape(command)}</code></li>" for command in commands_list
        )
        return f"<ul>{items}</ul>"

    @classmethod
    def _dashboard_config_editor(
        cls,
        config: dict[str, Any] | None,
        kwargs: dict[str, Any],
        editor_value: str | None = None,
    ) -> str:
        if config is None:
            return "<p>This cog does not store per-server configuration.</p>"
        dumped = (
            editor_value
            if editor_value is not None
            else json.dumps(config, indent=2, sort_keys=True, default=str)
        )
        return f"""
<form method="POST">
  {cls._dashboard_csrf(kwargs)}
  <label for="cog-config-json" class="config-help">
    Edit values as JSON. Key names and value types are validated before saving.
  </label>
  <textarea id="cog-config-json" class="config-editor" name="config_json"
            spellcheck="false" required>{html.escape(dumped)}</textarea>
  <div class="config-actions">
    <button type="submit" class="btn btn-primary">Save Settings</button>
    <span class="config-help">Changes apply immediately to this server.</span>
  </div>
</form>
"""
