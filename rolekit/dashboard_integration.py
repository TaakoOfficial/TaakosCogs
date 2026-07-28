"""Red-Web-Dashboard controls for community role packs and leveling."""

from __future__ import annotations

import html
import logging
from string import Formatter
from typing import Any, Callable

import discord
from redbot.core import commands

log = logging.getLogger("red.taakoscogs.rolekit.dashboard")


def dashboard_page(*args, **kwargs):
    """Dashboard page decorator compatible with Red-Web-Dashboard."""

    def decorator(func: Callable):
        func.__dashboard_decorator_params__ = (args, kwargs)
        return func

    return decorator


class DashboardIntegration:
    """Purpose-built dashboard for RoleKit."""

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
        description="Create community role packs and configure activity leveling.",
        methods=("GET", "POST"),
    )
    async def dashboard_page(
        self,
        user: discord.User,
        guild: discord.Guild,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Render and process the role-pack and leveling dashboard."""
        if not await self._dashboard_can_manage(user, guild):
            return {
                "status": 1,
                "error_title": "Insufficient Permissions",
                "error_message": (
                    "You need Manage Server, Red admin, or bot owner access."
                ),
            }

        notifications: list[dict[str, str]] = []
        if kwargs.get("method", "GET").upper() == "POST":
            form = self._dashboard_form(kwargs)
            action = self._dashboard_value(form, "action")
            try:
                message = await self._dashboard_handle_action(guild, action, form)
            except (commands.CommandError, ValueError, TypeError) as error:
                notifications.append({"message": str(error), "category": "error"})
            except Exception as error:
                log.exception("RoleKit dashboard action failed")
                notifications.append(
                    {
                        "message": f"Dashboard action failed: {error}",
                        "category": "error",
                    },
                )
            else:
                notifications.append({"message": message, "category": "success"})

        try:
            source = await self._dashboard_source(guild, kwargs)
        except Exception as error:
            log.exception("RoleKit dashboard render failed")
            return {
                "status": 1,
                "error_title": "Dashboard Error",
                "error_message": f"Could not render dashboard page: {error}",
            }

        return {
            "status": 0,
            "notifications": notifications,
            "web_content": {"source": source, "expanded": True},
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

    async def _dashboard_handle_action(
        self,
        guild: discord.Guild,
        action: str,
        form: Any,
    ) -> str:
        if action == "save_leveling":
            return await self._dashboard_save_leveling(guild, form)
        if action == "save_rewards":
            return await self._dashboard_save_rewards(guild, form)
        if action == "create_pack":
            pack = self._normalize_pack(self._dashboard_value(form, "pack"))
            if pack not in self.PACK_LABELS:
                raise commands.BadArgument("Choose a valid role pack.")
            if guild.me is None or not guild.me.guild_permissions.manage_roles:
                raise commands.BotMissingPermissions(["manage_roles"])
            created, existing, failed = await self._create_role_pack(guild, pack)
            return (
                f"{self.PACK_LABELS[pack]}: {len(created)} created, "
                f"{len(existing)} already present, {len(failed)} failed."
            )
        raise commands.BadArgument("Choose a valid dashboard action.")

    async def _dashboard_save_leveling(self, guild: discord.Guild, form: Any) -> str:
        xp_min = self._dashboard_int(form, "xp_min", minimum=1, maximum=1000)
        xp_max = self._dashboard_int(form, "xp_max", minimum=xp_min, maximum=1000)
        cooldown = self._dashboard_int(
            form,
            "xp_cooldown",
            minimum=5,
            maximum=3600,
        )
        channel_id = self._dashboard_optional_id(form, "level_up_channel_id")
        if channel_id is not None:
            channel = guild.get_channel(channel_id)
            if not isinstance(channel, (discord.TextChannel, discord.Thread)):
                raise commands.BadArgument("Choose a valid level-up text channel.")

        ignored_channel_ids = []
        for raw_channel_id in self._dashboard_values(form, "ignored_channel_ids"):
            try:
                ignored_channel_id = int(raw_channel_id)
            except (TypeError, ValueError) as error:
                raise commands.BadArgument("An ignored channel ID is invalid.") from error
            channel = guild.get_channel(ignored_channel_id)
            if not isinstance(channel, discord.TextChannel):
                raise commands.BadArgument("Choose only valid text channels to ignore.")
            if ignored_channel_id not in ignored_channel_ids:
                ignored_channel_ids.append(ignored_channel_id)

        level_up_message = self._dashboard_value(form, "level_up_message").strip()
        if not 1 <= len(level_up_message) <= 2000:
            raise commands.BadArgument("The level-up message must contain 1 to 2,000 characters.")
        try:
            fields = {
                field_name
                for _literal, field_name, _format_spec, _conversion in Formatter().parse(
                    level_up_message,
                )
                if field_name is not None
            }
            if not fields <= {"user", "display_name", "level", "server"}:
                raise KeyError("unknown placeholder")
            level_up_message.format(
                user="@member",
                display_name="member",
                level=10,
                server=guild.name,
            )
        except (KeyError, ValueError) as error:
            raise commands.BadArgument(
                "The level-up message contains an unknown or malformed placeholder.",
            ) from error

        guild_conf = self.config.guild(guild)
        await guild_conf.leveling_enabled.set(self._dashboard_checked(form, "leveling_enabled"))
        await guild_conf.xp_min.set(xp_min)
        await guild_conf.xp_max.set(xp_max)
        await guild_conf.xp_cooldown.set(cooldown)
        await guild_conf.level_up_channel_id.set(channel_id)
        await guild_conf.level_up_message.set(level_up_message)
        await guild_conf.stack_level_roles.set(
            self._dashboard_checked(form, "stack_level_roles"),
        )
        await guild_conf.ignored_channel_ids.set(ignored_channel_ids)
        state = "enabled" if self._dashboard_checked(form, "leveling_enabled") else "disabled"
        return f"Activity leveling settings saved; leveling is {state}."

    async def _dashboard_save_rewards(self, guild: discord.Guild, form: Any) -> str:
        raw_mapping = self._dashboard_value(form, "level_roles")
        rewards: dict[str, int] = {}
        for line_number, raw_line in enumerate(raw_mapping.splitlines(), start=1):
            line = raw_line.strip()
            if not line:
                continue
            separator = "=" if "=" in line else ":" if ":" in line else None
            if separator is None:
                raise commands.BadArgument(
                    f"Reward line {line_number} must use `level = role_id`.",
                )
            raw_level, raw_role_id = (part.strip() for part in line.split(separator, 1))
            try:
                level = int(raw_level)
                role_id = int(raw_role_id)
            except ValueError as error:
                raise commands.BadArgument(
                    f"Reward line {line_number} must contain numeric IDs.",
                ) from error
            if not 1 <= level <= self.MAX_LEVEL:
                raise commands.BadArgument(
                    f"Reward line {line_number} has a level outside 1–{self.MAX_LEVEL}.",
                )
            role = guild.get_role(role_id)
            if role is None:
                raise commands.BadArgument(f"Reward line {line_number} references a missing role.")
            if guild.me is None or role >= guild.me.top_role:
                raise commands.BadArgument(
                    f"{role.name} must be below the bot's highest role.",
                )
            rewards[str(level)] = role_id
        await self.config.guild(guild).level_roles.set(rewards)
        return f"Saved {len(rewards)} level reward role mapping(s)."

    async def _dashboard_source(
        self,
        guild: discord.Guild,
        kwargs: dict[str, Any],
    ) -> str:
        settings = await self.config.guild(guild).all()
        csrf = self._dashboard_csrf(kwargs)
        pack_cards = self._dashboard_pack_cards(guild, csrf)
        channel_options = self._dashboard_channel_options(
            guild,
            settings.get("level_up_channel_id"),
        )
        ignored_options = self._dashboard_ignored_channel_options(
            guild,
            settings.get("ignored_channel_ids", []),
        )
        reward_lines = "\n".join(
            f"{level} = {role_id}"
            for level, role_id in sorted(
                settings.get("level_roles", {}).items(),
                key=lambda item: int(item[0]),
            )
        )
        member_records = await self.config.all_members(guild)
        ranked_members = sum(1 for data in member_records.values() if int(data.get("xp", 0)) > 0)
        total_xp = sum(max(0, int(data.get("xp", 0))) for data in member_records.values())
        enabled = self._dashboard_checked_attr(settings.get("leveling_enabled", False))
        stacked = self._dashboard_checked_attr(settings.get("stack_level_roles", True))

        return f"""
<section class="zcr-dashboard">
  <style>
    .zcr-dashboard {{ --zcr-border: rgba(127,127,127,.28); }}
    .zcr-grid {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(220px,1fr)); gap:1rem; }}
    .zcr-card {{ border:1px solid var(--zcr-border); border-radius:.6rem; padding:1rem; margin-bottom:1rem; }}
    .zcr-card h3, .zcr-card h4 {{ margin-top:0; }}
    .zcr-row {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(180px,1fr)); gap:.8rem; }}
    .zcr-field {{ display:flex; flex-direction:column; gap:.3rem; margin-bottom:.8rem; }}
    .zcr-field input, .zcr-field select, .zcr-field textarea {{
      width:100%; padding:.55rem; border:1px solid var(--zcr-border); border-radius:.35rem;
      background:var(--background,#202225); color:var(--text,#f8f9fa);
    }}
    .zcr-field textarea {{ min-height:7rem; font-family:ui-monospace,SFMono-Regular,Menlo,monospace; }}
    .zcr-check {{ display:flex; align-items:center; gap:.5rem; margin:.7rem 0; }}
    .zcr-check input {{ width:auto; }}
    .zcr-muted {{ opacity:.78; }}
    .zcr-stat {{ font-size:1.35rem; font-weight:700; }}
    .zcr-actions {{ display:flex; gap:.6rem; flex-wrap:wrap; margin-top:.8rem; }}
    .zcr-pack-roles {{ min-height:3.5rem; font-size:.88rem; }}
  </style>
  <h2>Community Roles &amp; Leveling</h2>
  <p>Build useful opt-in role sets and reward genuine server activity in
     <strong>{html.escape(guild.name)}</strong>.</p>

  <div class="zcr-grid">
    <article class="zcr-card"><div class="zcr-stat">{len(self.PACK_LABELS)}</div><div>available role packs</div></article>
    <article class="zcr-card"><div class="zcr-stat">{ranked_members:,}</div><div>ranked members</div></article>
    <article class="zcr-card"><div class="zcr-stat">{total_xp:,}</div><div>total activity XP</div></article>
  </div>

  <article class="zcr-card">
    <h3>Curated role packs</h3>
    <p class="zcr-muted">Create only the sets that fit your community. Existing roles are reused.</p>
    <div class="zcr-grid">{pack_cards}</div>
  </article>

  <article class="zcr-card">
    <h3>Activity leveling</h3>
    <form method="POST">
      {csrf}<input type="hidden" name="action" value="save_leveling">
      <label class="zcr-check"><input type="checkbox" name="leveling_enabled"{enabled}> Enable message XP</label>
      <div class="zcr-row">
        <label class="zcr-field">Minimum XP per eligible message
          <input type="number" name="xp_min" min="1" max="1000" value="{int(settings['xp_min'])}" required>
        </label>
        <label class="zcr-field">Maximum XP per eligible message
          <input type="number" name="xp_max" min="1" max="1000" value="{int(settings['xp_max'])}" required>
        </label>
        <label class="zcr-field">Cooldown per member (seconds)
          <input type="number" name="xp_cooldown" min="5" max="3600" value="{int(settings['xp_cooldown'])}" required>
        </label>
      </div>
      <label class="zcr-field">Level-up announcement channel
        <select name="level_up_channel_id">{channel_options}</select>
      </label>
      <label class="zcr-field">Level-up message
        <input name="level_up_message" maxlength="2000"
               value="{html.escape(str(settings['level_up_message']), quote=True)}" required>
        <span class="zcr-muted">Placeholders: {{user}}, {{display_name}}, {{level}}, {{server}}</span>
      </label>
      <label class="zcr-check"><input type="checkbox" name="stack_level_roles"{stacked}> Keep every earned milestone role</label>
      <label class="zcr-field">Channels that should not award XP
        <select name="ignored_channel_ids" multiple size="6">{ignored_options}</select>
        <span class="zcr-muted">Hold Ctrl/Cmd to select more than one.</span>
      </label>
      <button type="submit" class="btn btn-primary">Save Leveling Settings</button>
    </form>
  </article>

  <article class="zcr-card">
    <h3>Level reward roles</h3>
    <p class="zcr-muted">One mapping per line using <code>level = role_id</code>.
       Creating the Levels pack fills this automatically.</p>
    <form method="POST">
      {csrf}<input type="hidden" name="action" value="save_rewards">
      <label class="zcr-field">Reward mapping
        <textarea name="level_roles" spellcheck="false"
                  placeholder="5 = 123456789012345678">{html.escape(reward_lines)}</textarea>
      </label>
      <button type="submit" class="btn btn-primary">Save Reward Roles</button>
    </form>
  </article>

  <details class="zcr-card">
    <summary>Available commands</summary>
    {self._dashboard_commands_html()}
  </details>
</section>
"""

    def _dashboard_pack_cards(self, guild: discord.Guild, csrf: str) -> str:
        cards = []
        for pack, label in self.PACK_LABELS.items():
            definitions = self._pack_definitions(pack)
            names = [name for name, _color, _level in definitions]
            existing = sum(discord.utils.get(guild.roles, name=name) is not None for name in names)
            cards.append(
                f"""
<section class="zcr-card">
  <h4>{html.escape(label)}</h4>
  <p><strong>{existing}/{len(names)}</strong> roles already exist.</p>
  <p class="zcr-muted zcr-pack-roles">{html.escape(', '.join(names))}</p>
  <form method="POST">
    {csrf}<input type="hidden" name="action" value="create_pack">
    <input type="hidden" name="pack" value="{html.escape(pack, quote=True)}">
    <button type="submit" class="btn btn-secondary">Create Missing Roles</button>
  </form>
</section>
""",
            )
        return "".join(cards)

    @staticmethod
    def _dashboard_channel_options(
        guild: discord.Guild,
        selected_channel_id: int | None,
    ) -> str:
        options = [
            '<option value="">Use the channel where the member leveled up</option>',
        ]
        for channel in guild.text_channels:
            selected = " selected" if channel.id == selected_channel_id else ""
            options.append(
                f'<option value="{channel.id}"{selected}>#{html.escape(channel.name)}</option>',
            )
        return "".join(options)

    @staticmethod
    def _dashboard_ignored_channel_options(
        guild: discord.Guild,
        ignored_channel_ids: list[int],
    ) -> str:
        ignored = {int(channel_id) for channel_id in ignored_channel_ids}
        return "".join(
            f'<option value="{channel.id}"{" selected" if channel.id in ignored else ""}>'
            f'#{html.escape(channel.name)}</option>'
            for channel in guild.text_channels
        )

    def _dashboard_commands_html(self) -> str:
        visible = sorted(
            command.qualified_name
            for command in self.walk_commands()
            if not command.hidden
        )
        return "<ul>" + "".join(
            f"<li><code>{html.escape(command)}</code></li>" for command in visible
        ) + "</ul>"

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

    @classmethod
    def _dashboard_values(cls, form: Any, key: str) -> list[str]:
        if hasattr(form, "getlist"):
            return [str(value) for value in form.getlist(key)]
        value = form.get(key, []) if hasattr(form, "get") else []
        if isinstance(value, (list, tuple)):
            return [str(item) for item in value]
        return [] if value in (None, "") else [str(value)]

    @classmethod
    def _dashboard_checked(cls, form: Any, key: str) -> bool:
        return cls._dashboard_value(form, key).lower() in {"1", "true", "yes", "on"}

    @staticmethod
    def _dashboard_checked_attr(value: Any) -> str:
        return " checked" if bool(value) else ""

    @classmethod
    def _dashboard_int(
        cls,
        form: Any,
        key: str,
        *,
        minimum: int,
        maximum: int,
    ) -> int:
        try:
            value = int(cls._dashboard_value(form, key))
        except ValueError as error:
            raise commands.BadArgument(f"{key.replace('_', ' ').title()} must be a number.") from error
        if not minimum <= value <= maximum:
            raise commands.BadArgument(
                f"{key.replace('_', ' ').title()} must be between {minimum} and {maximum}.",
            )
        return value

    @classmethod
    def _dashboard_optional_id(cls, form: Any, key: str) -> int | None:
        raw_value = cls._dashboard_value(form, key).strip()
        if not raw_value:
            return None
        try:
            return int(raw_value)
        except ValueError as error:
            raise commands.BadArgument(f"{key.replace('_', ' ').title()} is invalid.") from error

    @staticmethod
    def _dashboard_csrf(kwargs: dict[str, Any]) -> str:
        token = kwargs.get("csrf_token")
        if not isinstance(token, (tuple, list)) or len(token) != 2:
            return ""
        return (
            '<input type="hidden" name="csrf_token" value="'
            f'{html.escape(str(token[1]), quote=True)}">'
        )
