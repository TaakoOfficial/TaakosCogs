"""Combined role management tools for Red-DiscordBot."""

from __future__ import annotations

import asyncio
import contextlib
import io
import json
import logging
import re
import secrets
import time
from collections import deque
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING, Any, Union

import discord
from discord.ext import tasks
from redbot.core import Config, app_commands, bank, commands
from redbot.core.utils.chat_formatting import humanize_list, pagify
from redbot.core.utils.mod import get_audit_reason

from .advanced import (
    normalize_component_policy,
    parse_target_query,
    plan_reaction_role_changes,
    reaction_record_issues,
    trim_history,
)
from .components import RoleButton, RoleManagerView, RoleSelect
from .dashboard_integration import DashboardIntegration
from .reaction_compat import (
    canonical_emoji_key,
    normalize_reaction_bindings,
    role_assignment_blocker,
)

if TYPE_CHECKING:
    from collections.abc import Iterable, Sequence

    from redbot.core.bot import Red

log = logging.getLogger("red.taakoscogs.rolemanager")

RECOVERABLE_EXCEPTIONS = (
    discord.DiscordException,
    OSError,
    RuntimeError,
    ValueError,
    KeyError,
    TypeError,
    AttributeError,
)

TargetType = Union[
    discord.Role,
    discord.TextChannel,
    discord.VoiceChannel,
    discord.StageChannel,
    discord.Thread,
    discord.Member,
    str,
]


@dataclass
class RoleChangeResponse:
    """A failed or skipped role policy result."""

    role: discord.Role | None
    reason: str


class RoleManager(DashboardIntegration, commands.Cog):
    """Role rules, self roles, role panels, sticky/temp roles, and bulk role tools."""

    CONFIG_IDENTIFIER = 2026070901
    DURATION_RE = re.compile(
        r"(?P<value>\d+)\s*(?P<unit>years?|yrs?|y|months?|mos?|mo|weeks?|w|"
        r"days?|d|hours?|hrs?|h|minutes?|mins?|m|seconds?|secs?|s)",
        re.IGNORECASE,
    )
    TARGET_NAMES = {"everyone", "here", "humans", "bots"}

    def __init__(self, bot: Red) -> None:
        self.bot = bot
        self.config = Config.get_conf(
            self,
            identifier=self.CONFIG_IDENTIFIER,
            force_registration=True,
        )
        self.config.register_guild(
            atomic=None,
            react_roles={},
            auto_roles={
                "enabled": False,
                "all": [],
                "humans": [],
                "bots": [],
                "all_enabled": True,
                "humans_enabled": True,
                "bots_enabled": True,
                "delay_seconds": 0,
                "minimum_account_age_hours": 0,
                "retries": 3,
            },
            buttons={},
            select_options={},
            select_menus={},
            temporary_roles=[],
            role_rules={},
            audit_channel_id=None,
            audit_history=[],
            backups={},
            target_presets={},
            bulk_jobs=[],
            migration_history=[],
            autorole_queue=[],
        )
        self.config.register_global(atomic=True)
        self.config.register_role(
            self_assignable=False,
            self_removable=False,
            sticky=False,
            temp_duration=None,
            required=[],
            require_any=False,
            inclusive_with=[],
            exclusive_to=[],
            cost=0,
            buttons=[],
            select_options=[],
        )
        self.config.register_member(sticky_roles=[])
        self._reaction_message_cache: set[int] = set()
        self._component_views: dict[int, dict[str, RoleManagerView]] = {}
        self._role_rule_processing: set[tuple[int, int]] = set()
        self._member_locks: dict[tuple[int, int], asyncio.Lock] = {}
        self._component_cooldowns: dict[tuple[int, int, str], float] = {}
        self._bulk_tasks: dict[str, asyncio.Task] = {}
        self._autorole_tasks: dict[tuple[int, int], asyncio.Task] = {}
        self._deleted_user_ids: set[int] = set()
        self._startup_task = asyncio.create_task(self._startup())
        self._temp_sweeper.start()

    async def cog_unload(self) -> None:
        self._startup_task.cancel()
        self._temp_sweeper.cancel()
        for task in (*self._bulk_tasks.values(), *self._autorole_tasks.values()):
            task.cancel()
        for guild_views in self._component_views.values():
            for view in guild_views.values():
                view.stop()

    async def _startup(self) -> None:
        await self.bot.wait_until_red_ready()
        await self._repair_advanced_records()
        repaired = await self._repair_reaction_role_records()
        await self._refresh_reaction_cache()
        await self._load_component_views()
        await self._resume_autorole_queue()
        if repaired:
            log.info("Repaired %s imported reaction-role binding record(s).", repaired)

    async def _repair_advanced_records(self) -> None:
        """Upgrade older component and autorole records in place."""
        for guild_id, data in (await self.config.all_guilds()).items():
            conf = self.config.guild_from_id(guild_id)
            buttons = data.get("buttons", {})
            repaired_buttons = {
                name: normalize_component_policy(record) for name, record in buttons.items() if isinstance(record, dict)
            }
            if repaired_buttons != buttons:
                await conf.buttons.set(repaired_buttons)

            menus = data.get("select_menus", {})
            repaired_menus = {
                name: normalize_component_policy(record, select=True)
                for name, record in menus.items()
                if isinstance(record, dict)
            }
            if repaired_menus != menus:
                await conf.select_menus.set(repaired_menus)

            autoroles = dict(data.get("auto_roles", {}))
            autoroles.setdefault("enabled", False)
            autoroles.setdefault("all", [])
            autoroles.setdefault("humans", [])
            autoroles.setdefault("bots", [])
            autoroles.setdefault("all_enabled", True)
            autoroles.setdefault("humans_enabled", True)
            autoroles.setdefault("bots_enabled", True)
            autoroles.setdefault("delay_seconds", 0)
            autoroles.setdefault("minimum_account_age_hours", 0)
            autoroles.setdefault("retries", 3)
            if autoroles != data.get("auto_roles", {}):
                await conf.auto_roles.set(autoroles)

    async def red_delete_data_for_user(self, *, requester: str, user_id: int) -> None:
        """Remove stored member, temp, audit, job, and backup references for a user."""
        user_id = int(user_id)
        self._deleted_user_ids.add(user_id)
        all_guilds = await self.config.all_guilds()
        for guild_id, data in all_guilds.items():
            conf = self.config.guild_from_id(guild_id)
            temp_roles = []
            for raw_item in data.get("temporary_roles", []):
                item = dict(raw_item)
                if int(item.get("member_id", 0) or 0) == user_id:
                    continue
                if int(item.get("granted_by", 0) or 0) == user_id:
                    item["granted_by"] = None
                temp_roles.append(item)
            await conf.temporary_roles.set(temp_roles)
            await conf.audit_history.set(
                [
                    item
                    for item in data.get("audit_history", [])
                    if int(item.get("member_id", 0) or 0) != user_id and int(item.get("actor_id", 0) or 0) != user_id
                ],
            )
            for item in data.get("bulk_jobs", []):
                if int(item.get("actor_id", 0) or 0) == user_id:
                    task = self._bulk_tasks.get(f"{guild_id}:{item.get('id')}")
                    if task is not None:
                        task.cancel()
            await conf.bulk_jobs.set([item for item in data.get("bulk_jobs", []) if int(item.get("actor_id", 0) or 0) != user_id])
            await conf.autorole_queue.set(
                [item for item in data.get("autorole_queue", []) if int(item.get("member_id", 0) or 0) != user_id],
            )
            queued_task = self._autorole_tasks.get((int(guild_id), user_id))
            if queued_task is not None:
                queued_task.cancel()
            backups = dict(data.get("backups", {}))
            for backup in backups.values():
                snapshot = backup.get("guild", {})
                snapshot["temporary_roles"] = [
                    item
                    for item in snapshot.get("temporary_roles", [])
                    if int(item.get("member_id", 0) or 0) != user_id and int(item.get("granted_by", 0) or 0) != user_id
                ]
                snapshot["audit_history"] = [
                    item
                    for item in snapshot.get("audit_history", [])
                    if int(item.get("member_id", 0) or 0) != user_id and int(item.get("actor_id", 0) or 0) != user_id
                ]
                snapshot["bulk_jobs"] = [
                    item for item in snapshot.get("bulk_jobs", []) if int(item.get("actor_id", 0) or 0) != user_id
                ]
                snapshot["autorole_queue"] = [
                    item for item in snapshot.get("autorole_queue", []) if int(item.get("member_id", 0) or 0) != user_id
                ]
            await conf.backups.set(backups)
            await self.config.member_from_ids(guild_id, user_id).clear()

    @staticmethod
    def _now() -> datetime:
        return datetime.now(timezone.utc)

    @classmethod
    def _now_ts(cls) -> float:
        return cls._now().timestamp()

    @staticmethod
    def _count(value: int) -> str:
        return f"{value:,}"

    @staticmethod
    def _role_list(roles: Sequence[discord.Role]) -> str:
        if not roles:
            return "None"
        return humanize_list([role.mention for role in roles])

    @staticmethod
    def _format_ts(value: Any, style: str = "R") -> str:
        try:
            timestamp = int(float(value))
        except (TypeError, ValueError, OSError):
            return "Unknown"
        return f"<t:{timestamp}:{style}>"

    @staticmethod
    def _format_duration(seconds: int) -> str:
        seconds = int(seconds)
        parts: list[str] = []
        units = (
            ("year", 365 * 24 * 60 * 60),
            ("month", 30 * 24 * 60 * 60),
            ("week", 7 * 24 * 60 * 60),
            ("day", 24 * 60 * 60),
            ("hour", 60 * 60),
            ("minute", 60),
            ("second", 1),
        )
        for name, size in units:
            amount, seconds = divmod(seconds, size)
            if amount:
                suffix = "" if amount == 1 else "s"
                parts.append(f"{amount} {name}{suffix}")
            if len(parts) >= 2:
                break
        return humanize_list(parts) if parts else "0 seconds"

    @classmethod
    def _parse_duration(cls, argument: str) -> int:
        argument = argument.strip()
        if not argument:
            raise commands.BadArgument("Duration cannot be empty.")

        total = 0
        matched_ranges: list[tuple[int, int]] = []
        multipliers = {
            "s": 1,
            "sec": 1,
            "secs": 1,
            "second": 1,
            "seconds": 1,
            "m": 60,
            "min": 60,
            "mins": 60,
            "minute": 60,
            "minutes": 60,
            "h": 60 * 60,
            "hr": 60 * 60,
            "hrs": 60 * 60,
            "hour": 60 * 60,
            "hours": 60 * 60,
            "d": 24 * 60 * 60,
            "day": 24 * 60 * 60,
            "days": 24 * 60 * 60,
            "w": 7 * 24 * 60 * 60,
            "week": 7 * 24 * 60 * 60,
            "weeks": 7 * 24 * 60 * 60,
            "mo": 30 * 24 * 60 * 60,
            "mos": 30 * 24 * 60 * 60,
            "month": 30 * 24 * 60 * 60,
            "months": 30 * 24 * 60 * 60,
            "y": 365 * 24 * 60 * 60,
            "yr": 365 * 24 * 60 * 60,
            "yrs": 365 * 24 * 60 * 60,
            "year": 365 * 24 * 60 * 60,
            "years": 365 * 24 * 60 * 60,
        }

        for match in cls.DURATION_RE.finditer(argument):
            value = int(match.group("value"))
            unit = match.group("unit").lower()
            total += value * multipliers[unit]
            matched_ranges.append(match.span())

        if not matched_ranges:
            raise commands.BadArgument("Use a duration like `30m`, `2 hours`, or `7d`.")

        cleaned = list(argument)
        for start, end in matched_ranges:
            for index in range(start, end):
                cleaned[index] = " "
        leftovers = "".join(cleaned).strip(" ,")
        if leftovers:
            raise commands.BadArgument(
                "I could not understand part of that duration. Use examples like `30m`, `2 hours`, or `7d`.",
            )
        if total <= 0:
            raise commands.BadArgument("Duration must be greater than zero.")
        return total

    @classmethod
    def _emoji_key(cls, emoji: Any) -> str:
        return canonical_emoji_key(emoji)

    @classmethod
    def _normalise_target(cls, target: str) -> str:
        lowered = target.lower().strip()
        if lowered not in cls.TARGET_NAMES:
            raise commands.BadArgument(
                "Target must be a member, role, text channel, or one of `everyone`, `here`, `humans`, `bots`.",
            )
        return lowered

    @staticmethod
    def _find_role(guild: discord.Guild, argument: str) -> discord.Role | None:
        argument = argument.strip()
        match = re.fullmatch(r"<@&([0-9]+)>", argument)
        if match:
            return guild.get_role(int(match.group(1)))
        if argument.isdigit():
            return guild.get_role(int(argument))
        lowered = argument.casefold()
        return discord.utils.find(
            lambda role: role.name.casefold() == lowered,
            guild.roles,
        )

    def _roles_from_argument(
        self,
        guild: discord.Guild,
        argument: str,
    ) -> list[discord.Role]:
        roles: list[discord.Role] = []
        for part in argument.split(","):
            role = self._find_role(guild, part.strip())
            if role is None:
                raise commands.BadArgument(f"I could not find role `{part.strip()}`.")
            roles.append(role)
        return list(dict.fromkeys(roles))

    def _role_actions_from_spec(
        self,
        guild: discord.Guild,
        spec: str,
    ) -> tuple[list[discord.Role], list[discord.Role]]:
        """Parse ``--add`` and ``--remove`` role lists from a command argument."""
        add_part = ""
        remove_part = ""
        lowered = spec.lower()
        add_index = lowered.find("--add")
        remove_index = lowered.find("--remove")
        if add_index != -1:
            end = remove_index if remove_index > add_index else len(spec)
            add_part = spec[add_index + 5 : end].strip()
        if remove_index != -1:
            end = add_index if add_index > remove_index else len(spec)
            remove_part = spec[remove_index + 8 : end].strip()
        to_add = self._roles_from_argument(guild, add_part) if add_part else []
        to_remove = self._roles_from_argument(guild, remove_part) if remove_part else []
        if not to_add and not to_remove:
            raise commands.BadArgument("Use `--add role,role` or `--remove role,role`.")
        overlap = set(to_add) & set(to_remove)
        if overlap:
            raise commands.BadArgument(
                f"A rule cannot add and remove the same role: {self._format_role_names(overlap)}.",
            )
        return to_add, to_remove

    @staticmethod
    def _normalise_rule_name(name: str) -> str:
        normalised = name.strip().lower()
        if not normalised or not re.fullmatch(r"[a-z0-9_-]{1,50}", normalised):
            raise commands.BadArgument(
                "Rule names may contain only letters, numbers, underscores, and hyphens.",
            )
        return normalised

    async def _refresh_reaction_cache(self) -> None:
        cache: set[int] = set()
        all_guilds = await self.config.all_guilds()
        for data in all_guilds.values():
            for message_id, message_data in data.get("react_roles", {}).items():
                if message_data.get("binds"):
                    with contextlib.suppress(TypeError, ValueError):
                        cache.add(int(message_id))
        self._reaction_message_cache = cache

    async def _repair_reaction_role_records(self) -> int:
        """Normalize records imported by older cogs so existing panels stay live."""
        repaired = 0
        all_guilds = await self.config.all_guilds()
        for guild_id in all_guilds:
            async with self.config.guild_from_id(guild_id).react_roles() as react_roles:
                for message_id, message_data in list(react_roles.items()):
                    if not isinstance(message_data, dict):
                        del react_roles[message_id]
                        repaired += 1
                        continue
                    normalized, changes = normalize_reaction_bindings(message_data.get("binds", {}))
                    message_data["binds"] = normalized
                    channel_id = message_data.get("channel_id")
                    if channel_id is not None:
                        try:
                            message_data["channel_id"] = int(channel_id)
                        except (TypeError, ValueError):
                            message_data["channel_id"] = None
                            changes += 1
                    if not normalized:
                        del react_roles[message_id]
                        changes += 1
                    repaired += changes
        return repaired

    async def _load_component_views(self) -> None:
        """Load persistent button/select views from config."""
        for guild_views in self._component_views.values():
            for view in guild_views.values():
                view.stop()
        self._component_views = {}
        all_guilds = await self.config.all_guilds()
        for guild_id, data in all_guilds.items():
            guild = self.bot.get_guild(guild_id)
            if guild is None:
                continue
            message_keys: set[str] = set()
            for button_data in data.get("buttons", {}).values():
                message_keys.update(str(key) for key in button_data.get("messages", []))
            for menu_data in data.get("select_menus", {}).values():
                message_keys.update(str(key) for key in menu_data.get("messages", []))

            for message_key in message_keys:
                view = self._build_component_view(guild, message_key, data)
                if view is None:
                    continue
                self._component_views.setdefault(guild_id, {})[message_key] = view
                try:
                    _channel_id, message_id = message_key.split("-", 1)
                    self.bot.add_view(view, message_id=int(message_id))
                except (AttributeError, TypeError, ValueError):
                    log.debug("Could not register persistent view for %s.", message_key)

    def _build_component_view(
        self,
        guild: discord.Guild,
        message_key: str,
        data: dict[str, Any],
        *,
        timeout: float | None = None,
    ) -> RoleManagerView | None:
        view = RoleManagerView(self, timeout=timeout)
        for name, button_data in sorted(data.get("buttons", {}).items()):
            if message_key not in button_data.get("messages", []):
                continue
            role = guild.get_role(int(button_data.get("role_id", 0)))
            if role is None:
                continue
            button = RoleButton(
                name=name,
                role_id=role.id,
                label=str(button_data.get("label") or f"@{role.name}"),
                emoji=button_data.get("emoji"),
                style=int(
                    button_data.get("style") or discord.ButtonStyle.secondary.value,
                ),
                guild_id=guild.id,
            )
            button.refresh_label(guild)
            try:
                view.add_item(button)
            except ValueError:
                log.debug("Could not add button %s to view %s.", name, message_key)

        select_options = data.get("select_options", {})
        for name, menu_data in sorted(data.get("select_menus", {}).items()):
            if message_key not in menu_data.get("messages", []):
                continue
            options = []
            for option_name in menu_data.get("options", []):
                option = select_options.get(option_name)
                if not option:
                    continue
                role = guild.get_role(int(option.get("role_id", 0)))
                if role is None:
                    continue
                options.append(option)
            if not options:
                continue
            select = RoleSelect(
                name=name,
                guild_id=guild.id,
                placeholder=menu_data.get("placeholder"),
                min_values=int(menu_data.get("min_values") or 0),
                max_values=int(menu_data.get("max_values") or len(options)),
                options=options,
            )
            select.refresh_options(guild)
            try:
                view.add_item(select)
            except ValueError:
                log.debug("Could not add select %s to view %s.", name, message_key)

        return view if view.children else None

    @staticmethod
    def _component_message_key(message: discord.Message) -> str:
        return f"{message.channel.id}-{message.id}"

    @staticmethod
    def _parse_name_list(argument: str) -> list[str]:
        if not argument or argument.lower() in {"none", "null", "-"}:
            return []
        return [part.strip().lower() for part in argument.split(",") if part.strip()]

    @staticmethod
    def _button_style_value(style: str) -> int:
        styles = {
            "primary": discord.ButtonStyle.primary.value,
            "blurple": discord.ButtonStyle.primary.value,
            "secondary": discord.ButtonStyle.secondary.value,
            "grey": discord.ButtonStyle.secondary.value,
            "gray": discord.ButtonStyle.secondary.value,
            "success": discord.ButtonStyle.success.value,
            "green": discord.ButtonStyle.success.value,
            "danger": discord.ButtonStyle.danger.value,
            "red": discord.ButtonStyle.danger.value,
        }
        try:
            return styles[style.lower()]
        except KeyError as exc:
            raise commands.BadArgument(
                "Style must be primary, secondary, success, or danger.",
            ) from exc

    @staticmethod
    def _format_role_names(roles: Iterable[discord.Role]) -> str:
        names = [role.mention for role in roles]
        return humanize_list(names) if names else "None"

    async def _ensure_member_cache(self, guild: discord.Guild) -> None:
        if getattr(guild, "chunked", False):
            return
        intents = getattr(self.bot, "intents", None)
        if not getattr(intents, "members", False):
            return
        try:
            await asyncio.wait_for(guild.chunk(cache=True), timeout=20)
        except (asyncio.TimeoutError, discord.HTTPException):
            log.debug("Could not chunk guild %s before role operation.", guild.id)

    def _check_role_manageable(
        self,
        ctx: commands.Context,
        role: discord.Role,
        *,
        check_author: bool = True,
    ) -> None:
        guild = ctx.guild
        if guild is None:
            raise commands.UserFeedbackCheckFailure(
                "This command can only be used in a server.",
            )
        if role.is_default():
            raise commands.UserFeedbackCheckFailure(
                "I cannot manage the everyone role.",
            )
        if role.managed:
            raise commands.UserFeedbackCheckFailure(
                "I cannot manage integration-managed roles.",
            )
        me = guild.me
        if me is None or not me.guild_permissions.manage_roles:
            raise commands.UserFeedbackCheckFailure(
                "I need the Manage Roles permission.",
            )
        if role >= me.top_role:
            raise commands.UserFeedbackCheckFailure(
                f"My top role must be above {role.mention}.",
            )
        author = ctx.author
        if check_author and isinstance(author, discord.Member) and author.id != guild.owner_id and role >= author.top_role:
            raise commands.UserFeedbackCheckFailure(
                f"Your top role must be above {role.mention}.",
            )

    def _bot_can_apply_to_member(
        self,
        member: discord.Member,
        role: discord.Role,
    ) -> bool:
        # Role assignment is governed by the position of the role being
        # granted, not the target member's highest role. RoleTools therefore
        # allows a moderator whose staff role is above the bot to receive a
        # lower reaction role. Rejecting that member here made otherwise valid
        # imported panels appear disconnected.
        return role_assignment_blocker(member, role) is None

    async def _check_guild_verification(
        self,
        member: discord.Member,
        guild: discord.Guild,
    ) -> bool | int:
        """Return seconds to wait if Discord verification gates role assignment."""
        if member.roles:
            return False
        account_age = datetime.now(timezone.utc) - member.created_at
        joined_at = member.joined_at or datetime.now(timezone.utc)
        server_age = datetime.now(timezone.utc) - joined_at
        verification_level = getattr(guild, "verification_level", None)
        if verification_level is None:
            return False
        if verification_level.value >= 2 and account_age < timedelta(minutes=5):
            return max(1, 300 - int(account_age.total_seconds()))
        if verification_level.value >= 3 and server_age < timedelta(minutes=10):
            return max(1, 600 - int(server_age.total_seconds()))
        return False

    async def _wait_for_guild_verification(self, member: discord.Member) -> None:
        wait = await self._check_guild_verification(member, member.guild)
        if wait:
            await asyncio.sleep(int(wait))

    async def _atomic_enabled(self, guild: discord.Guild) -> bool:
        guild_setting = await self.config.guild(guild).atomic()
        if guild_setting is None:
            return bool(await self.config.atomic())
        return bool(guild_setting)

    async def _validate_required_roles(
        self,
        member: discord.Member,
        role: discord.Role,
        owned_role_ids: set[int],
    ) -> str | None:
        required = [int(role_id) for role_id in await self.config.role(role).required()]
        if not required:
            return None
        required = [role_id for role_id in required if member.guild.get_role(role_id)]
        await self.config.role(role).required.set(required)
        if not required:
            return None
        require_any = bool(await self.config.role(role).require_any())
        if require_any and not any(role_id in owned_role_ids for role_id in required):
            return "You do not have any of the required roles."
        if not require_any and not all(role_id in owned_role_ids for role_id in required):
            return "You do not have all of the required roles."
        return None

    async def _charge_for_roles(
        self,
        member: discord.Member,
        roles: Sequence[discord.Role],
        *,
        check_cost: bool,
    ) -> tuple[list[RoleChangeResponse], list[tuple[discord.Role, int]]]:
        failures: list[RoleChangeResponse] = []
        charged: list[tuple[discord.Role, int]] = []
        if not check_cost:
            return failures, charged
        for role in roles:
            cost = int(await self.config.role(role).cost() or 0)
            if cost <= 0:
                continue
            currency = await bank.get_currency_name(member.guild)
            if not await bank.can_spend(member, cost):
                failures.append(
                    RoleChangeResponse(
                        role,
                        f"You need {cost:,} {currency} to acquire {role.name}.",
                    ),
                )
                continue
            try:
                await bank.withdraw_credits(member, cost)
            except RECOVERABLE_EXCEPTIONS:
                failures.append(
                    RoleChangeResponse(
                        role,
                        f"I could not withdraw {cost:,} {currency} for {role.name}.",
                    ),
                )
            else:
                charged.append((role, cost))
        return failures, charged

    async def _refund_charged_roles(
        self,
        member: discord.Member,
        charged: Sequence[tuple[discord.Role, int]],
    ) -> None:
        for _role, amount in charged:
            try:
                await bank.deposit_credits(member, amount)
            except RECOVERABLE_EXCEPTIONS:
                log.exception("Failed to refund role cost for %s.", member.id)

    async def _give_roles(
        self,
        member: discord.Member,
        roles: Sequence[discord.Role],
        reason: str,
        *,
        check_required: bool = True,
        check_exclusive: bool = True,
        check_inclusive: bool = True,
        check_cost: bool = True,
        atomic: bool | None = None,
        duration_overrides: dict[int, int] | None = None,
        dry_run: bool = False,
    ) -> tuple[list[RoleChangeResponse], set[discord.Role], set[discord.Role]]:
        guild = member.guild
        failures: list[RoleChangeResponse] = []
        if not roles:
            return failures, set(), set()
        if guild.me is None or not guild.me.guild_permissions.manage_roles:
            return [RoleChangeResponse(None, "I need Manage Roles.")], set(), set()
        if atomic is None:
            atomic = await self._atomic_enabled(guild)

        current_roles = set(member.roles)
        to_add: set[discord.Role] = set()
        to_remove: set[discord.Role] = set()
        charged_roles: list[tuple[discord.Role, int]] = []
        requested_for_cost: list[discord.Role] = []

        for role in dict.fromkeys(roles):
            if role is None:
                failures.append(RoleChangeResponse(None, "That role no longer exists."))
                continue
            if not self._bot_can_apply_to_member(member, role):
                failures.append(
                    RoleChangeResponse(
                        role,
                        f"I cannot manage {role.name} for this member.",
                    ),
                )
                continue
            if role in current_roles or role in to_add:
                failures.append(
                    RoleChangeResponse(role, f"You already have {role.name}."),
                )
                continue

            owned_role_ids = {item.id for item in (current_roles | to_add) if item not in to_remove}
            if check_required:
                failure = await self._validate_required_roles(
                    member,
                    role,
                    owned_role_ids,
                )
                if failure:
                    failures.append(RoleChangeResponse(role, failure))
                    continue

            if check_exclusive:
                skip_role = False
                exclusive_ids = [int(role_id) for role_id in await self.config.role(role).exclusive_to()]
                for role_id in exclusive_ids:
                    excluded = guild.get_role(role_id)
                    if excluded is None:
                        continue
                    if excluded in current_roles or excluded in to_add:
                        if await self.config.role(excluded).self_removable():
                            to_remove.add(excluded)
                            to_add.discard(excluded)
                        else:
                            skip_role = True
                if skip_role:
                    failures.append(
                        RoleChangeResponse(
                            role,
                            f"{role.name} conflicts with a role that is not removable.",
                        ),
                    )
                    continue

            if check_inclusive:
                inclusive_ids = [int(role_id) for role_id in await self.config.role(role).inclusive_with()]
                for role_id in inclusive_ids:
                    included = guild.get_role(role_id)
                    if included is None:
                        continue
                    if not self._bot_can_apply_to_member(member, included):
                        continue
                    if not await self.config.role(included).self_assignable():
                        continue
                    if included not in current_roles and included not in to_add:
                        to_add.add(included)

            to_add.add(role)
            requested_for_cost.append(role)

        cost_failures, charged_roles = await self._charge_for_roles(
            member,
            requested_for_cost,
            check_cost=check_cost and not dry_run,
        )
        if cost_failures:
            failures.extend(cost_failures)
            failed_roles = {failure.role for failure in cost_failures if failure.role}
            to_add.difference_update(failed_roles)
            for failed_role in failed_roles:
                inclusive_ids = [int(role_id) for role_id in await self.config.role(failed_role).inclusive_with()]
                to_add.difference_update(role for role in to_add if role.id in inclusive_ids)

        if dry_run:
            return failures, to_add, to_remove

        try:
            if atomic:
                if to_remove:
                    await member.remove_roles(*to_remove, reason=reason)
                if to_add:
                    await member.add_roles(*to_add, reason=reason)
            else:
                final_roles = (current_roles - to_remove) | to_add
                await member.edit(roles=list(final_roles), reason=reason)
        except discord.HTTPException:
            await self._refund_charged_roles(member, charged_roles)
            log.exception("Failed to apply role policy update for %s.", member.id)
            failures.append(
                RoleChangeResponse(None, "Discord rejected the role update."),
            )
            return failures, set(), set()

        duration_overrides = duration_overrides or {}
        for role in to_add:
            await self._maybe_track_temp_role(
                member,
                role,
                duration=duration_overrides.get(role.id),
            )
        for role in to_remove:
            await self._clear_temp_role(member, role)
        if to_add or to_remove:
            await self._record_role_audit(
                guild,
                action="role_policy_update",
                member_id=member.id,
                role_ids=[role.id for role in (*to_add, *to_remove)],
                source="role-change",
                detail=reason,
            )
        return failures, to_add, to_remove

    async def _remove_roles(
        self,
        member: discord.Member,
        roles: Sequence[discord.Role],
        reason: str,
        *,
        check_inclusive: bool = True,
        atomic: bool | None = None,
        dry_run: bool = False,
    ) -> tuple[list[RoleChangeResponse], set[discord.Role]]:
        guild = member.guild
        failures: list[RoleChangeResponse] = []
        if guild.me is None or not guild.me.guild_permissions.manage_roles:
            return [RoleChangeResponse(None, "I need Manage Roles.")], set()
        if atomic is None:
            atomic = await self._atomic_enabled(guild)

        current_roles = set(member.roles)
        to_remove: set[discord.Role] = set()
        for role in dict.fromkeys(roles):
            if role is None:
                failures.append(RoleChangeResponse(None, "That role no longer exists."))
                continue
            if not self._bot_can_apply_to_member(member, role):
                failures.append(
                    RoleChangeResponse(
                        role,
                        f"I cannot manage {role.name} for this member.",
                    ),
                )
                continue
            if role not in current_roles:
                failures.append(
                    RoleChangeResponse(role, f"You do not have {role.name}."),
                )
                continue
            to_remove.add(role)
            if check_inclusive:
                inclusive_ids = [int(role_id) for role_id in await self.config.role(role).inclusive_with()]
                for role_id in inclusive_ids:
                    included = guild.get_role(role_id)
                    if included is not None and included in current_roles and await self.config.role(included).self_removable():
                        to_remove.add(included)

        if dry_run:
            return failures, to_remove

        try:
            if atomic:
                if to_remove:
                    await member.remove_roles(*to_remove, reason=reason)
            else:
                await member.edit(roles=list(current_roles - to_remove), reason=reason)
        except discord.HTTPException:
            log.exception("Failed to remove role policy update for %s.", member.id)
            failures.append(
                RoleChangeResponse(None, "Discord rejected the role update."),
            )
            return failures, set()

        for role in to_remove:
            await self._clear_temp_role(member, role)
        if to_remove:
            await self._record_role_audit(
                guild,
                action="role_remove",
                member_id=member.id,
                role_ids=[role.id for role in to_remove],
                source="role-change",
                detail=reason,
            )
        return failures, to_remove

    @staticmethod
    def _response_text(responses: Sequence[RoleChangeResponse]) -> str:
        lines = []
        for response in responses:
            prefix = f"{response.role.mention}: " if response.role else ""
            lines.append(f"- {prefix}{response.reason}")
        return "\n".join(lines)

    def _member_lock(self, member: discord.Member) -> asyncio.Lock:
        """Return the per-member lock used by every interactive role control."""
        return self._member_locks.setdefault(
            (member.guild.id, member.id),
            asyncio.Lock(),
        )

    async def _record_role_audit(
        self,
        guild: discord.Guild,
        *,
        action: str,
        member_id: int | None = None,
        role_ids: Sequence[int] = (),
        actor_id: int | None = None,
        source: str = "RoleManager",
        detail: str = "",
    ) -> None:
        """Persist and optionally deliver a bounded RoleManager audit record."""
        if member_id in self._deleted_user_ids:
            member_id = None
        if actor_id in self._deleted_user_ids:
            actor_id = None
        entry = {
            "id": secrets.token_hex(6),
            "timestamp": self._now_ts(),
            "action": str(action)[:80],
            "member_id": int(member_id) if member_id else None,
            "role_ids": [int(role_id) for role_id in role_ids],
            "actor_id": int(actor_id) if actor_id else None,
            "source": str(source)[:80],
            "detail": str(detail)[:500],
        }
        async with self.config.guild(guild).audit_history() as history:
            history.append(entry)
            history[:] = trim_history(history, maximum=250)

        channel_id = await self.config.guild(guild).audit_channel_id()
        channel = guild.get_channel(int(channel_id or 0))
        if not isinstance(channel, discord.TextChannel):
            return
        roles = [guild.get_role(role_id) for role_id in entry["role_ids"]]
        role_text = humanize_list([role.mention for role in roles if role]) or "None"
        lines = [f"**{entry['action']}** · {entry['source']}"]
        if member_id:
            lines.append(f"Member: <@{member_id}> (`{member_id}`)")
        if actor_id:
            lines.append(f"Actor: <@{actor_id}> (`{actor_id}`)")
        lines.append(f"Roles: {role_text}")
        if detail:
            lines.append(str(detail)[:500])
        with contextlib.suppress(discord.HTTPException):
            await channel.send(
                "\n".join(lines),
                allowed_mentions=discord.AllowedMentions.none(),
            )

    async def _component_policy_error(
        self,
        member: discord.Member,
        policy: dict[str, Any],
        *,
        key: str,
        adding_role: discord.Role | None = None,
    ) -> str | None:
        required = {int(role_id) for role_id in policy.get("required_role_ids", [])}
        blocked = {int(role_id) for role_id in policy.get("blocked_role_ids", [])}
        owned = {role.id for role in member.roles}
        if required and not required.issubset(owned):
            missing = [member.guild.get_role(role_id) for role_id in required - owned]
            return "Required role(s): " + humanize_list(
                [role.name for role in missing if role],
            )
        if blocked & owned:
            present = [member.guild.get_role(role_id) for role_id in blocked & owned]
            return "Blocked by role(s): " + humanize_list(
                [role.name for role in present if role],
            )
        cooldown = int(policy.get("cooldown_seconds", 0) or 0)
        cooldown_key = (member.guild.id, member.id, key)
        last_used = self._component_cooldowns.get(cooldown_key, 0.0)
        remaining = cooldown - (time.monotonic() - last_used)
        if remaining > 0:
            return f"This control is on cooldown for {int(remaining) + 1}s."
        if adding_role is not None:
            maximum = int(policy.get("max_holders", 0) or 0)
            if maximum and len(adding_role.members) >= maximum:
                return f"{adding_role.name} has reached its {maximum:,}-member limit."
        self._component_cooldowns[cooldown_key] = time.monotonic()
        return None

    async def handle_button_interaction(
        self,
        interaction: discord.Interaction,
        button: RoleButton,
    ) -> None:
        """Handle a persistent role button click."""
        if interaction.guild is None or not isinstance(
            interaction.user,
            discord.Member,
        ):
            await interaction.response.send_message(
                "This can only be used in a server.",
                ephemeral=True,
            )
            return
        if await self.bot.cog_disabled_in_guild(self, interaction.guild):
            await interaction.response.send_message(
                "RoleManager is disabled in this server.",
                ephemeral=True,
            )
            return
        role = interaction.guild.get_role(button.role_id)
        if role is None:
            await interaction.response.send_message(
                "That role no longer exists.",
                ephemeral=True,
            )
            return
        buttons = await self.config.guild(interaction.guild).buttons()
        button_data = buttons.get(button.name)
        if not button_data or int(button_data.get("role_id", 0)) != button.role_id:
            await interaction.response.send_message(
                "That button is no longer active.",
                ephemeral=True,
            )
            return
        button_data = normalize_component_policy(button_data)
        await interaction.response.defer(ephemeral=True, thinking=True)
        async with self._member_lock(interaction.user):
            adding = role not in interaction.user.roles
            mode = button_data["mode"]
            if mode == "add":
                adding = True
            elif mode == "remove":
                adding = False
            policy_error = await self._component_policy_error(
                interaction.user,
                button_data,
                key=f"button:{button.name}",
                adding_role=role if adding else None,
            )
            if policy_error:
                message = policy_error
            elif adding and role in interaction.user.roles:
                message = f"You already have {role.name}."
            elif not adding and role not in interaction.user.roles:
                message = f"You do not have {role.name}."
            else:
                message = await self._component_toggle_role(
                    interaction.user,
                    role,
                    "Button role.",
                    force_adding=adding,
                    temp_seconds=int(button_data.get("temp_seconds", 0) or 0),
                )
                await self._record_role_audit(
                    interaction.guild,
                    action="component_add" if adding else "component_remove",
                    member_id=interaction.user.id,
                    role_ids=[role.id],
                    actor_id=interaction.user.id,
                    source=f"button:{button.name}",
                    detail=message,
                )
        button.refresh_label(interaction.guild)
        if interaction.message and isinstance(button.view, RoleManagerView):
            with contextlib.suppress(discord.HTTPException):
                await interaction.message.edit(view=button.view)
        await interaction.followup.send(message, ephemeral=True)

    async def handle_select_interaction(
        self,
        interaction: discord.Interaction,
        select: RoleSelect,
    ) -> None:
        """Handle a persistent role select interaction."""
        if interaction.guild is None or not isinstance(
            interaction.user,
            discord.Member,
        ):
            await interaction.response.send_message(
                "This can only be used in a server.",
                ephemeral=True,
            )
            return
        if await self.bot.cog_disabled_in_guild(self, interaction.guild):
            await interaction.response.send_message(
                "RoleManager is disabled in this server.",
                ephemeral=True,
            )
            return
        await interaction.response.defer(ephemeral=True, thinking=True)
        menus = await self.config.guild(interaction.guild).select_menus()
        menu_data = menus.get(select.name)
        if not menu_data:
            await interaction.followup.send(
                "That select menu is no longer active.",
                ephemeral=True,
            )
            return
        menu_data = normalize_component_policy(menu_data, select=True)
        messages = []
        async with self._member_lock(interaction.user):
            policy_error = await self._component_policy_error(
                interaction.user,
                menu_data,
                key=f"select:{select.name}",
            )
            if policy_error:
                messages.append(policy_error)
            else:
                selected_ids = {int(value) for value in select.values}
                options = await self.config.guild(interaction.guild).select_options()
                option_role_ids = {int(options[name]["role_id"]) for name in menu_data.get("options", []) if name in options}
                mode = menu_data["mode"]
                for role_id in option_role_ids:
                    role = interaction.guild.get_role(role_id)
                    if role is None:
                        continue
                    selected = role_id in selected_ids
                    if mode == "add" and not selected:
                        continue
                    if mode == "toggle" and not selected:
                        continue
                    should_add = selected
                    if mode == "toggle":
                        should_add = role not in interaction.user.roles
                    if should_add and role in interaction.user.roles:
                        continue
                    if not should_add and role not in interaction.user.roles:
                        continue
                    error = await self._component_policy_error(
                        interaction.user,
                        {**menu_data, "cooldown_seconds": 0},
                        key=f"select-role:{select.name}:{role.id}",
                        adding_role=role if should_add else None,
                    )
                    if error:
                        messages.append(error)
                        continue
                    messages.append(
                        await self._component_toggle_role(
                            interaction.user,
                            role,
                            "Select role.",
                            force_adding=should_add,
                            temp_seconds=int(menu_data.get("temp_seconds", 0) or 0),
                        ),
                    )
                await self._record_role_audit(
                    interaction.guild,
                    action=f"component_select_{mode}",
                    member_id=interaction.user.id,
                    role_ids=list(selected_ids),
                    actor_id=interaction.user.id,
                    source=f"select:{select.name}",
                    detail="; ".join(messages)[:500],
                )
        select.refresh_options(interaction.guild)
        if interaction.message and isinstance(select.view, RoleManagerView):
            with contextlib.suppress(discord.HTTPException):
                await interaction.message.edit(view=select.view)
        await interaction.followup.send(
            "\n".join(messages) or "No role changes made.",
            ephemeral=True,
        )

    async def _component_toggle_role(
        self,
        member: discord.Member,
        role: discord.Role,
        reason: str,
        *,
        force_adding: bool | None = None,
        temp_seconds: int = 0,
    ) -> str:
        if member.bot:
            return "Bots cannot use role controls."
        adding = role not in member.roles if force_adding is None else force_adding
        if not adding:
            if not await self.config.role(role).self_removable():
                return f"{role.name} is not self-removable."
            responses, removed = await self._remove_roles(member, [role], reason)
            if responses:
                return self._response_text(responses)
            return f"Removed {self._format_role_names(removed)}."

        if not await self.config.role(role).self_assignable():
            return f"{role.name} is not self-assignable."
        wait = await self._check_guild_verification(member, member.guild)
        if wait:
            retry_at = datetime.now(timezone.utc) + timedelta(seconds=int(wait))
            return f"You need to spend more time in this server first. Try again {discord.utils.format_dt(retry_at, 'R')}."
        if getattr(member, "pending", False):
            return "Finish Discord membership screening before taking self roles."
        responses, added, _removed = await self._give_roles(
            member,
            [role],
            reason,
            duration_overrides={role.id: temp_seconds} if temp_seconds else None,
        )
        if responses:
            return self._response_text(responses)
        return f"Added {self._format_role_names(added)}."

    async def _maybe_track_temp_role(
        self,
        member: discord.Member,
        role: discord.Role,
        *,
        duration: int | None = None,
        granted_by: int | None = None,
        reason: str | None = None,
        notify_channel_id: int | None = None,
        notify_member: bool = False,
    ) -> None:
        if duration is None:
            duration = await self.config.role(role).temp_duration()
        if not duration:
            return
        expires_at = self._now_ts() + int(duration)
        async with self.config.guild(member.guild).temporary_roles() as temp_roles:
            temp_roles[:] = [
                item
                for item in temp_roles
                if not (int(item.get("member_id", 0)) == member.id and int(item.get("role_id", 0)) == role.id)
            ]
            temp_roles.append(
                {
                    "member_id": member.id,
                    "role_id": role.id,
                    "expires_at": expires_at,
                    "created_at": self._now_ts(),
                    "granted_by": granted_by,
                    "reason": reason,
                    "notify_channel_id": notify_channel_id,
                    "notify_member": notify_member,
                },
            )

    async def _clear_temp_role(
        self,
        member: discord.Member,
        role: discord.Role,
    ) -> None:
        async with self.config.guild(member.guild).temporary_roles() as temp_roles:
            temp_roles[:] = [
                item
                for item in temp_roles
                if not (int(item.get("member_id", 0)) == member.id and int(item.get("role_id", 0)) == role.id)
            ]

    async def _members_from_targets(
        self,
        ctx: commands.Context,
        targets: Sequence[TargetType],
    ) -> tuple[list[discord.Member], list[str]]:
        guild = ctx.guild
        if guild is None:
            raise commands.UserFeedbackCheckFailure(
                "This command can only be used in a server.",
            )
        if not targets:
            raise commands.BadArgument(
                "Provide at least one target: a member, role, text channel, `everyone`, `here`, `humans`, or `bots`.",
            )
        await self._ensure_member_cache(guild)

        members: dict[int, discord.Member] = {}
        labels: list[str] = []
        for target in targets:
            target_members: Iterable[discord.Member]
            if isinstance(target, discord.Member):
                target_members = [target]
                labels.append(target.display_name)
            elif isinstance(target, discord.Role):
                target_members = target.members if not target.is_default() else guild.members
                labels.append(target.name)
            elif isinstance(
                target,
                (discord.TextChannel, discord.VoiceChannel, discord.StageChannel),
            ):
                target_members = target.members
                labels.append(target.mention)
            elif isinstance(target, discord.Thread):
                fetched = await target.fetch_members()
                target_members = [
                    member for thread_member in fetched if (member := guild.get_member(thread_member.id)) is not None
                ]
                labels.append(target.mention)
            else:
                target_name = self._normalise_target(target)
                labels.append(target_name)
                if target_name == "everyone":
                    target_members = guild.members
                elif target_name == "here":
                    target_members = [member for member in guild.members if member.status != discord.Status.offline]
                elif target_name == "humans":
                    target_members = [member for member in guild.members if not member.bot]
                else:
                    target_members = [member for member in guild.members if member.bot]

            for member in target_members:
                members[member.id] = member

        return list(members.values()), labels

    def _find_guild_channel(self, guild: discord.Guild, value: str) -> Any:
        """Resolve a guild channel/thread by ID, mention, or case-insensitive name."""
        cleaned = value.strip().strip("<#>")
        if cleaned.isdigit():
            channel = guild.get_channel_or_thread(int(cleaned))
            if channel is not None:
                return channel
        lowered = value.casefold()
        return next(
            (channel for channel in [*guild.channels, *guild.threads] if channel.name.casefold() == lowered),
            None,
        )

    async def _members_from_query(
        self,
        guild: discord.Guild,
        argument: str,
    ) -> list[discord.Member]:
        """Resolve advanced `key=value` member targeting filters."""
        try:
            query = parse_target_query(argument)
        except ValueError as exc:
            raise commands.BadArgument(str(exc)) from exc
        await self._ensure_member_cache(guild)
        members = list(guild.members)

        types = {value.casefold() for value in query.get("type")}
        if types:
            if not types <= {"humans", "bots"}:
                raise commands.BadArgument("type must be humans or bots.")
            members = [member for member in members if ("bots" if member.bot else "humans") in types]

        statuses = {value.casefold() for value in query.get("status")}
        if statuses:
            valid = {"online", "idle", "dnd", "offline"}
            if not statuses <= valid:
                raise commands.BadArgument(
                    "status must be online, idle, dnd, or offline.",
                )
            members = [member for member in members if str(member.status) in statuses]

        def resolve_roles(values: Sequence[str]) -> set[int]:
            resolved = set()
            for value in values:
                role = self._find_role(guild, value)
                if role is None:
                    raise commands.BadArgument(f"Could not resolve role `{value}`.")
                resolved.add(role.id)
            return resolved

        required = resolve_roles(query.get("has"))
        any_roles = resolve_roles(query.get("any"))
        excluded = resolve_roles(query.get("none"))
        if required or any_roles or excluded:
            filtered = []
            for member in members:
                owned = {role.id for role in member.roles}
                if required and not required.issubset(owned):
                    continue
                if any_roles and not any_roles.intersection(owned):
                    continue
                if excluded.intersection(owned):
                    continue
                filtered.append(member)
            members = filtered

        channel_member_ids: set[int] | None = None
        for key in ("channel", "voice", "thread"):
            for value in query.get(key):
                channel = self._find_guild_channel(guild, value)
                if channel is None:
                    raise commands.BadArgument(f"Could not resolve {key} `{value}`.")
                if key == "thread":
                    if not isinstance(channel, discord.Thread):
                        raise commands.BadArgument(f"`{value}` is not a thread.")
                    fetched = await channel.fetch_members()
                    ids = {item.id for item in fetched}
                else:
                    if key == "voice" and not isinstance(
                        channel,
                        (discord.VoiceChannel, discord.StageChannel),
                    ):
                        raise commands.BadArgument(f"`{value}` is not a voice channel.")
                    ids = {member.id for member in channel.members}
                channel_member_ids = ids if channel_member_ids is None else channel_member_ids & ids
        if channel_member_ids is not None:
            members = [member for member in members if member.id in channel_member_ids]

        now = self._now()
        if query.get("joined_days"):
            try:
                days = int(query.get("joined_days")[0])
            except ValueError as exc:
                raise commands.BadArgument("joined_days must be a whole number.") from exc
            cutoff = now - timedelta(days=max(0, days))
            members = [member for member in members if member.joined_at and member.joined_at >= cutoff]
        if query.get("account_days"):
            try:
                days = int(query.get("account_days")[0])
            except ValueError as exc:
                raise commands.BadArgument("account_days must be a whole number.") from exc
            cutoff = now - timedelta(days=max(0, days))
            members = [member for member in members if member.created_at <= cutoff]
        return members

    async def _apply_role_to_members(
        self,
        ctx: commands.Context,
        role: discord.Role,
        members: Sequence[discord.Member],
        *,
        adding: bool,
        reason: str,
        duration: int | None = None,
    ) -> dict[str, Any]:
        completed: list[discord.Member] = []
        skipped: list[discord.Member] = []
        failed: list[discord.Member] = []
        response_lines: list[str] = []

        for member in members:
            if not self._bot_can_apply_to_member(member, role):
                skipped.append(member)
                continue
            if adding and role in member.roles:
                skipped.append(member)
                continue
            if not adding and role not in member.roles:
                skipped.append(member)
                continue

            try:
                if adding:
                    responses, added, _removed = await self._give_roles(
                        member,
                        [role],
                        reason,
                        check_cost=False,
                        duration_overrides={role.id: duration} if duration else None,
                    )
                    if responses:
                        response_lines.append(f"{member}: {responses[0].reason}")
                    if role in added:
                        completed.append(member)
                    elif responses:
                        failed.append(member)
                    else:
                        skipped.append(member)
                else:
                    responses, removed = await self._remove_roles(
                        member,
                        [role],
                        reason,
                    )
                    if responses:
                        response_lines.append(f"{member}: {responses[0].reason}")
                    if role in removed:
                        completed.append(member)
                    elif responses:
                        failed.append(member)
                    else:
                        skipped.append(member)
            except discord.HTTPException:
                failed.append(member)
                log.exception(
                    "Failed to update role %s for member %s.",
                    role.id,
                    member.id,
                )

        return {
            "completed": completed,
            "skipped": skipped,
            "failed": failed,
            "responses": response_lines,
        }

    async def _send_operation_result(
        self,
        ctx: commands.Context,
        role: discord.Role,
        result: dict[str, Any],
        *,
        adding: bool,
    ) -> None:
        verb = "Added" if adding else "Removed"
        preposition = "to" if adding else "from"
        lines = [
            f"{verb} {role.mention} {preposition} {self._count(len(result['completed']))} member(s).",
        ]
        if result["skipped"]:
            lines.append(f"Skipped {self._count(len(result['skipped']))} member(s).")
        if result["failed"]:
            lines.append(f"Failed for {self._count(len(result['failed']))} member(s).")
        if result.get("responses"):
            preview = "\n".join(result["responses"][:5])
            lines.append(f"First failure(s):\n{preview}")
        await ctx.send(
            "\n".join(lines),
            allowed_mentions=discord.AllowedMentions.none(),
        )

    @tasks.loop(seconds=60)
    async def _temp_sweeper(self) -> None:
        now = self._now_ts()
        all_guilds = await self.config.all_guilds()
        for guild_id, data in all_guilds.items():
            pending = data.get("temporary_roles", [])
            if not pending:
                continue
            guild = self.bot.get_guild(guild_id)
            if guild is None:
                continue

            keep: list[dict[str, Any]] = []
            for item in pending:
                member = guild.get_member(int(item.get("member_id", 0)))
                role = guild.get_role(int(item.get("role_id", 0)))
                expires_at = float(item.get("expires_at", 0))
                if member is None or role is None or role not in member.roles:
                    continue
                if expires_at > now:
                    keep.append(item)
                    continue
                if not self._bot_can_apply_to_member(member, role):
                    keep.append(item)
                    continue
                try:
                    await member.remove_roles(role, reason="Temporary role expired.")
                except discord.HTTPException:
                    keep.append(item)
                    log.exception(
                        "Failed to remove expired temporary role %s from %s.",
                        role.id,
                        member.id,
                    )
                    continue
                await self._record_role_audit(
                    guild,
                    action="temporary_role_expired",
                    member_id=member.id,
                    role_ids=[role.id],
                    actor_id=item.get("granted_by"),
                    source="temporary-role-sweeper",
                    detail=str(item.get("reason") or "Temporary assignment expired."),
                )
                notice = f"Your temporary **{role.name}** role in **{guild.name}** has expired."
                if item.get("notify_member"):
                    with contextlib.suppress(discord.HTTPException):
                        await member.send(notice)
                channel = guild.get_channel(int(item.get("notify_channel_id", 0) or 0))
                if isinstance(channel, discord.TextChannel):
                    with contextlib.suppress(discord.HTTPException):
                        await channel.send(
                            f"Temporary role `{role.name}` expired for {member.mention}.",
                            allowed_mentions=discord.AllowedMentions(users=False),
                        )

            await self.config.guild_from_id(guild_id).temporary_roles.set(keep)

    @_temp_sweeper.before_loop
    async def _before_temp_sweeper(self) -> None:
        await self.bot.wait_until_red_ready()

    @commands.guild_only()
    @commands.group(name="rolemanager", aliases=["rm"], invoke_without_command=True)
    async def rolemanager(self, ctx: commands.Context) -> None:
        """Combined role management setup and staff tools."""
        await ctx.send_help(ctx.command)

    @commands.guild_only()
    @rolemanager.group(
        name="selfrole",
        aliases=["selfroles", "iam"],
        invoke_without_command=True,
    )
    @commands.bot_has_permissions(manage_roles=True)
    async def selfrole_settings(
        self,
        ctx: commands.Context,
        *,
        role: discord.Role | None = None,
    ) -> None:
        """Add, remove, or configure member self roles."""
        if role is None:
            await ctx.send_help(ctx.command)
            return

        self._check_role_manageable(ctx, role, check_author=False)
        member = ctx.author
        if not isinstance(member, discord.Member):
            return

        if role in member.roles:
            if not await self.config.role(role).self_removable():
                await ctx.send(f"{role.mention} is not self-removable.")
                return
            responses, removed = await self._remove_roles(
                member,
                [role],
                "Selfrole command.",
            )
            if responses:
                await ctx.send(self._response_text(responses))
                return
            await ctx.send(
                f"Removed {self._format_role_names(removed)} from you.",
                allowed_mentions=discord.AllowedMentions.none(),
            )
            return

        if not await self.config.role(role).self_assignable():
            await ctx.send(f"{role.mention} is not self-assignable.")
            return
        wait = await self._check_guild_verification(member, member.guild)
        if wait:
            retry_at = datetime.now(timezone.utc) + timedelta(seconds=int(wait))
            await ctx.send(
                f"You need to spend more time in this server first. Try again {discord.utils.format_dt(retry_at, 'R')}.",
            )
            return
        if getattr(member, "pending", False):
            await ctx.send(
                "Finish Discord membership screening before taking self roles.",
            )
            return
        responses, added, _removed = await self._give_roles(
            member,
            [role],
            "Selfrole command.",
        )
        if responses:
            await ctx.send(self._response_text(responses))
            return
        await ctx.send(
            f"Added {self._format_role_names(added)} to you.",
            allowed_mentions=discord.AllowedMentions.none(),
        )

    @selfrole_settings.command(name="allow")
    @commands.admin_or_permissions(manage_roles=True)
    @commands.bot_has_permissions(manage_roles=True)
    async def selfrole_allow(
        self,
        ctx: commands.Context,
        role: discord.Role,
        removable: bool = True,
    ) -> None:
        """Make a role self-assignable."""
        self._check_role_manageable(ctx, role)
        await self.config.role(role).self_assignable.set(True)
        await self.config.role(role).self_removable.set(removable)
        remove_text = "and self-removable" if removable else "but not self-removable"
        await ctx.send(
            f"{role.mention} is now self-assignable {remove_text}.",
            allowed_mentions=discord.AllowedMentions.none(),
        )

    @selfrole_settings.command(name="deny", aliases=["remove"])
    @commands.admin_or_permissions(manage_roles=True)
    async def selfrole_deny(self, ctx: commands.Context, *, role: discord.Role) -> None:
        """Remove a role from self-role availability."""
        await self.config.role(role).self_assignable.set(False)
        await self.config.role(role).self_removable.set(False)
        await ctx.send(
            f"{role.mention} is no longer a self role.",
            allowed_mentions=discord.AllowedMentions.none(),
        )

    @selfrole_settings.command(name="list")
    @commands.admin_or_permissions(manage_roles=True)
    async def selfrole_list(self, ctx: commands.Context) -> None:
        """List configured self roles."""
        lines: list[str] = []
        for role in sorted(
            ctx.guild.roles,
            key=lambda item: item.position,
            reverse=True,
        ):
            if role.is_default():
                continue
            assignable = await self.config.role(role).self_assignable()
            removable = await self.config.role(role).self_removable()
            if assignable or removable:
                lines.append(
                    f"{role.mention} - assignable: {assignable}, removable: {removable}",
                )
        if not lines:
            await ctx.send("No self roles are configured.")
            return
        for page in pagify("\n".join(lines), page_length=1900):
            await ctx.send(page, allowed_mentions=discord.AllowedMentions.none())

    @rolemanager.command(name="selfassignable", aliases=["selfadd", "selfassign"])
    @commands.admin_or_permissions(manage_roles=True)
    async def legacy_selfassignable(
        self,
        ctx: commands.Context,
        enabled: bool | None = None,
        *,
        role: discord.Role,
    ) -> None:
        """Trusty-style alias for setting self-assignable roles."""
        self._check_role_manageable(ctx, role)
        if enabled is None:
            enabled = not await self.config.role(role).self_assignable()
        await self.config.role(role).self_assignable.set(bool(enabled))
        await ctx.send(
            f"{role.mention} is {'now' if enabled else 'no longer'} self-assignable.",
            allowed_mentions=discord.AllowedMentions.none(),
        )

    @rolemanager.command(name="selfremovable", aliases=["selfrem"])
    @commands.admin_or_permissions(manage_roles=True)
    async def legacy_selfremovable(
        self,
        ctx: commands.Context,
        enabled: bool | None = None,
        *,
        role: discord.Role,
    ) -> None:
        """Trusty-style alias for setting self-removable roles."""
        self._check_role_manageable(ctx, role)
        if enabled is None:
            enabled = not await self.config.role(role).self_removable()
        await self.config.role(role).self_removable.set(bool(enabled))
        await ctx.send(
            f"{role.mention} is {'now' if enabled else 'no longer'} self-removable.",
            allowed_mentions=discord.AllowedMentions.none(),
        )

    @rolemanager.command(name="cost")
    @commands.admin_or_permissions(manage_roles=True)
    async def role_cost(
        self,
        ctx: commands.Context,
        cost: int | None = None,
        *,
        role: discord.Role,
    ) -> None:
        """Set the Red bank credit cost for a self-assigned role."""
        self._check_role_manageable(ctx, role)
        if await bank.is_global() and not await self.bot.is_owner(ctx.author):
            await ctx.send(
                "Only bot owners can set role costs while the bank is global.",
            )
            return
        if cost is None:
            current = int(await self.config.role(role).cost() or 0)
            currency = await bank.get_currency_name(ctx.guild)
            await ctx.send(f"{role.mention} currently costs {current:,} {currency}.")
            return
        if cost <= 0:
            await self.config.role(role).cost.clear()
            await ctx.send(
                f"{role.mention} no longer has a credit cost.",
                allowed_mentions=discord.AllowedMentions.none(),
            )
            return
        max_balance = await bank.get_max_balance(ctx.guild)
        if cost >= max_balance:
            raise commands.BadArgument(
                "Cost cannot be higher than the bank max balance.",
            )
        await self.config.role(role).cost.set(cost)
        currency = await bank.get_currency_name(ctx.guild)
        await ctx.send(
            f"{role.mention} now costs {cost:,} {currency}.",
            allowed_mentions=discord.AllowedMentions.none(),
        )

    @rolemanager.command(name="atomic")
    @commands.admin_or_permissions(manage_roles=True)
    async def atomic_setting(
        self,
        ctx: commands.Context,
        enabled: bool | str | None = None,
    ) -> None:
        """Set guild atomic role assignment behavior."""
        if enabled is None:
            current = await self.config.guild(ctx.guild).atomic()
            if current is None:
                current = f"global default ({await self.config.atomic()})"
            await ctx.send(f"Guild atomic assignment is `{current}`.")
            return
        if isinstance(enabled, str) and enabled.lower() == "clear":
            await self.config.guild(ctx.guild).atomic.clear()
            await ctx.send("Guild atomic assignment now uses the global default.")
            return
        await self.config.guild(ctx.guild).atomic.set(bool(enabled))
        await ctx.send(f"Guild atomic assignment set to `{bool(enabled)}`.")

    @rolemanager.command(name="globalatomic")
    @commands.is_owner()
    async def global_atomic_setting(
        self,
        ctx: commands.Context,
        enabled: bool | None = None,
    ) -> None:
        """Set global atomic role assignment behavior."""
        if enabled is None:
            await ctx.send(
                f"Global atomic assignment is `{await self.config.atomic()}`.",
            )
            return
        await self.config.atomic.set(bool(enabled))
        await ctx.send(f"Global atomic assignment set to `{bool(enabled)}`.")

    @rolemanager.group(name="required", aliases=["requires", "require", "req"])
    @commands.admin_or_permissions(manage_roles=True)
    async def required_group(self, ctx: commands.Context) -> None:
        """Configure prerequisite roles."""

    @required_group.command(name="any")
    async def required_any(
        self,
        ctx: commands.Context,
        role: discord.Role,
        require_any: bool,
    ) -> None:
        """Require any prerequisite role instead of every prerequisite role."""
        self._check_role_manageable(ctx, role)
        await self.config.role(role).require_any.set(bool(require_any))
        await ctx.send(f"{role.mention} require-any is now `{bool(require_any)}`.")

    @required_group.command(name="add")
    async def required_add(
        self,
        ctx: commands.Context,
        role: discord.Role,
        required: commands.Greedy[discord.Role],
    ) -> None:
        """Add prerequisite roles for a role."""
        self._check_role_manageable(ctx, role)
        if not required:
            await ctx.send_help(ctx.command)
            return
        async with self.config.role(role).required() as stored:
            for required_role in required:
                if required_role.id not in stored:
                    stored.append(required_role.id)
        await ctx.send(
            f"{role.mention} now requires {self._format_role_names(required)}.",
            allowed_mentions=discord.AllowedMentions.none(),
        )

    @required_group.command(name="remove")
    async def required_remove(
        self,
        ctx: commands.Context,
        role: discord.Role,
        required: commands.Greedy[discord.Role],
    ) -> None:
        """Remove prerequisite roles for a role."""
        self._check_role_manageable(ctx, role)
        async with self.config.role(role).required() as stored:
            for required_role in required:
                if required_role.id in stored:
                    stored.remove(required_role.id)
        await ctx.send(f"Updated requirements for {role.mention}.")

    @rolemanager.group(name="include", aliases=["inclusive"])
    @commands.admin_or_permissions(manage_roles=True)
    async def include_group(self, ctx: commands.Context) -> None:
        """Configure roles that are added together."""

    @include_group.command(name="add")
    async def include_add(
        self,
        ctx: commands.Context,
        role: discord.Role,
        include: commands.Greedy[discord.Role],
    ) -> None:
        """Add inclusive roles."""
        self._check_role_manageable(ctx, role)
        if not include:
            await ctx.send_help(ctx.command)
            return
        exclusive = await self.config.role(role).exclusive_to()
        async with self.config.role(role).inclusive_with() as stored:
            for included_role in include:
                if included_role.id in exclusive:
                    raise commands.BadArgument(
                        "A role cannot be inclusive and exclusive.",
                    )
                if included_role.id not in stored:
                    stored.append(included_role.id)
        await ctx.send(
            f"{role.mention} now includes {self._format_role_names(include)}.",
            allowed_mentions=discord.AllowedMentions.none(),
        )

    @include_group.command(name="mutual")
    async def include_mutual(
        self,
        ctx: commands.Context,
        roles: commands.Greedy[discord.Role],
    ) -> None:
        """Make roles mutually inclusive."""
        if len(roles) < 2:
            await ctx.send_help(ctx.command)
            return
        for role in roles:
            self._check_role_manageable(ctx, role)
            async with self.config.role(role).inclusive_with() as stored:
                for other in roles:
                    if other.id != role.id and other.id not in stored:
                        stored.append(other.id)
        await ctx.send(
            f"Made mutually inclusive: {self._format_role_names(roles)}.",
            allowed_mentions=discord.AllowedMentions.none(),
        )

    @include_group.command(name="remove")
    async def include_remove(
        self,
        ctx: commands.Context,
        role: discord.Role,
        include: commands.Greedy[discord.Role],
    ) -> None:
        """Remove inclusive roles."""
        self._check_role_manageable(ctx, role)
        async with self.config.role(role).inclusive_with() as stored:
            for included_role in include:
                if included_role.id in stored:
                    stored.remove(included_role.id)
        await ctx.send(f"Updated inclusive roles for {role.mention}.")

    @rolemanager.group(name="exclude", aliases=["exclusive"])
    @commands.admin_or_permissions(manage_roles=True)
    async def exclude_group(self, ctx: commands.Context) -> None:
        """Configure roles that conflict with each other."""

    @exclude_group.command(name="add")
    async def exclude_add(
        self,
        ctx: commands.Context,
        role: discord.Role,
        exclude: commands.Greedy[discord.Role],
    ) -> None:
        """Add exclusive roles."""
        self._check_role_manageable(ctx, role)
        if not exclude:
            await ctx.send_help(ctx.command)
            return
        inclusive = await self.config.role(role).inclusive_with()
        async with self.config.role(role).exclusive_to() as stored:
            for excluded_role in exclude:
                if excluded_role.id in inclusive:
                    raise commands.BadArgument(
                        "A role cannot be inclusive and exclusive.",
                    )
                if excluded_role.id not in stored:
                    stored.append(excluded_role.id)
        await ctx.send(
            f"{role.mention} now excludes {self._format_role_names(exclude)}.",
            allowed_mentions=discord.AllowedMentions.none(),
        )

    @exclude_group.command(name="mutual")
    async def exclude_mutual(
        self,
        ctx: commands.Context,
        roles: commands.Greedy[discord.Role],
    ) -> None:
        """Make roles mutually exclusive."""
        if len(roles) < 2:
            await ctx.send_help(ctx.command)
            return
        for role in roles:
            self._check_role_manageable(ctx, role)
            async with self.config.role(role).exclusive_to() as stored:
                for other in roles:
                    if other.id != role.id and other.id not in stored:
                        stored.append(other.id)
        await ctx.send(
            f"Made mutually exclusive: {self._format_role_names(roles)}.",
            allowed_mentions=discord.AllowedMentions.none(),
        )

    @exclude_group.command(name="remove")
    async def exclude_remove(
        self,
        ctx: commands.Context,
        role: discord.Role,
        exclude: commands.Greedy[discord.Role],
    ) -> None:
        """Remove exclusive roles."""
        self._check_role_manageable(ctx, role)
        async with self.config.role(role).exclusive_to() as stored:
            for excluded_role in exclude:
                if excluded_role.id in stored:
                    stored.remove(excluded_role.id)
        await ctx.send(f"Updated exclusive roles for {role.mention}.")

    @rolemanager.group(name="rule", aliases=["rules"])
    @commands.admin_or_permissions(manage_roles=True)
    @commands.bot_has_permissions(manage_roles=True)
    async def role_rule_group(self, ctx: commands.Context) -> None:
        """Configure rules that react to every member role change."""

    @role_rule_group.command(name="set", aliases=["create", "add"])
    async def role_rule_set(
        self,
        ctx: commands.Context,
        name: str,
        trigger_event: str,
        trigger_role: discord.Role,
        *,
        actions: str,
    ) -> None:
        """Create or replace a role-change rule.

        Example: `rule set verified add @Verified --add @Member --remove @Unverified`
        """
        name = self._normalise_rule_name(name)
        trigger_event = trigger_event.lower()
        if trigger_event not in {"add", "remove"}:
            raise commands.BadArgument("Trigger event must be `add` or `remove`.")
        if trigger_role.is_default():
            raise commands.BadArgument("The everyone role cannot be a rule trigger.")
        if isinstance(ctx.author, discord.Member) and ctx.author.id != ctx.guild.owner_id and trigger_role >= ctx.author.top_role:
            raise commands.BadArgument("Your top role must be above the trigger role.")

        to_add, to_remove = self._role_actions_from_spec(ctx.guild, actions)
        for role in to_add + to_remove:
            self._check_role_manageable(ctx, role)
        if trigger_role in to_add or trigger_role in to_remove:
            raise commands.BadArgument("A rule cannot modify its own trigger role.")

        async with self.config.guild(ctx.guild).role_rules() as rules:
            rules[name] = {
                "trigger_role_id": trigger_role.id,
                "trigger_event": trigger_event,
                "add_role_ids": [role.id for role in to_add],
                "remove_role_ids": [role.id for role in to_remove],
                "enabled": True,
            }
        event_text = "added" if trigger_event == "add" else "removed"
        await ctx.send(
            f"Saved role rule `{name}`: when {trigger_role.mention} is {event_text}, "
            f"add {self._format_role_names(to_add)} and remove "
            f"{self._format_role_names(to_remove)}.",
            allowed_mentions=discord.AllowedMentions.none(),
        )

    @role_rule_group.command(name="toggle")
    async def role_rule_toggle(
        self,
        ctx: commands.Context,
        name: str,
        enabled: bool | None = None,
    ) -> None:
        """Enable, disable, or toggle a role-change rule."""
        name = self._normalise_rule_name(name)
        async with self.config.guild(ctx.guild).role_rules() as rules:
            rule = rules.get(name)
            if rule is None:
                raise commands.BadArgument(f"Role rule `{name}` was not found.")
            if enabled is None:
                enabled = not bool(rule.get("enabled", True))
            rule["enabled"] = bool(enabled)
        await ctx.send(
            f"Role rule `{name}` is now {'enabled' if enabled else 'disabled'}.",
        )

    @role_rule_group.command(name="delete", aliases=["remove", "del"])
    async def role_rule_delete(self, ctx: commands.Context, *, name: str) -> None:
        """Delete a role-change rule."""
        name = self._normalise_rule_name(name)
        async with self.config.guild(ctx.guild).role_rules() as rules:
            if rules.pop(name, None) is None:
                raise commands.BadArgument(f"Role rule `{name}` was not found.")
        await ctx.send(f"Deleted role rule `{name}`.")

    @role_rule_group.command(name="list", aliases=["view"])
    async def role_rule_list(self, ctx: commands.Context) -> None:
        """List role-change rules."""
        rules = await self.config.guild(ctx.guild).role_rules()
        if not rules:
            await ctx.send("No role-change rules are configured.")
            return
        lines = []
        for name, rule in sorted(rules.items()):
            trigger = ctx.guild.get_role(int(rule.get("trigger_role_id", 0)))
            add_roles = [
                role for role_id in rule.get("add_role_ids", []) if (role := ctx.guild.get_role(int(role_id))) is not None
            ]
            remove_roles = [
                role for role_id in rule.get("remove_role_ids", []) if (role := ctx.guild.get_role(int(role_id))) is not None
            ]
            lines.append(
                f"**{name}** ({'on' if rule.get('enabled', True) else 'off'}): "
                f"{rule.get('trigger_event', 'add')} "
                f"{trigger.mention if trigger else 'missing trigger'} -> "
                f"add {self._format_role_names(add_roles)}; "
                f"remove {self._format_role_names(remove_roles)}",
            )
        for page in pagify("\n".join(lines), page_length=1900):
            await ctx.send(page, allowed_mentions=discord.AllowedMentions.none())

    @rolemanager.command(name="viewroles", aliases=["viewrole"])
    @commands.admin_or_permissions(manage_roles=True)
    async def viewroles(
        self,
        ctx: commands.Context,
        *,
        role: discord.Role | None = None,
    ) -> None:
        """View RoleManager settings for one role or all configured roles."""
        roles = [role] if role else [item for item in ctx.guild.roles if not item.is_default()]
        lines: list[str] = []
        for item in roles:
            config = await self.config.role(item).all()
            if role is None and not any(
                [
                    config.get("self_assignable"),
                    config.get("self_removable"),
                    config.get("sticky"),
                    config.get("temp_duration"),
                    config.get("required"),
                    config.get("inclusive_with"),
                    config.get("exclusive_to"),
                    config.get("cost"),
                ],
            ):
                continue
            lines.append(await self._role_settings_line(ctx.guild, item, config))
        if not lines:
            await ctx.send("No RoleManager role settings are configured.")
            return
        for page in pagify("\n\n".join(lines), page_length=1900):
            await ctx.send(page, allowed_mentions=discord.AllowedMentions.none())

    async def _role_settings_line(
        self,
        guild: discord.Guild,
        role: discord.Role,
        config: dict[str, Any],
    ) -> str:
        def roles_from_ids(role_ids: Sequence[int]) -> str:
            roles = [found for role_id in role_ids if (found := guild.get_role(int(role_id))) is not None]
            return self._format_role_names(roles)

        duration = config.get("temp_duration")
        duration_text = self._format_duration(duration) if duration else "None"
        return (
            f"**{role.name}** (`{role.id}`)\n"
            f"Self assignable: `{bool(config.get('self_assignable'))}` | "
            f"Self removable: `{bool(config.get('self_removable'))}` | "
            f"Sticky: `{bool(config.get('sticky'))}` | "
            f"Cost: `{int(config.get('cost') or 0):,}` | "
            f"Temp: `{duration_text}`\n"
            f"Required ({'any' if config.get('require_any') else 'all'}): "
            f"{roles_from_ids(config.get('required') or [])}\n"
            f"Includes: {roles_from_ids(config.get('inclusive_with') or [])}\n"
            f"Excludes: {roles_from_ids(config.get('exclusive_to') or [])}"
        )

    async def _create_config_backup(self, guild: discord.Guild, source: str) -> str:
        """Create a bounded, restorable snapshot before a migration or bulk edit."""
        guild_data = await self.config.guild(guild).all()
        guild_data.pop("backups", None)
        role_data = {str(role.id): await self.config.role(role).all() for role in guild.roles if not role.is_default()}
        backup_id = f"{int(self._now_ts())}-{secrets.token_hex(2)}"
        backup = {
            "id": backup_id,
            "source": source,
            "created_at": self._now_ts(),
            "guild": guild_data,
            "roles": role_data,
        }
        async with self.config.guild(guild).backups() as backups:
            backups[backup_id] = backup
            for old_id in sorted(
                backups,
                key=lambda item: float(backups[item].get("created_at", 0)),
                reverse=True,
            )[5:]:
                del backups[old_id]
        return backup_id

    async def _restore_config_backup(self, guild: discord.Guild, backup_id: str) -> bool:
        backups = await self.config.guild(guild).backups()
        backup = backups.get(backup_id)
        if not backup:
            return False
        current_backups = backups.copy()
        restored = dict(backup.get("guild", {}))
        restored["backups"] = current_backups
        await self.config.guild(guild).set(restored)
        for role_id, data in backup.get("roles", {}).items():
            role = guild.get_role(int(role_id))
            if role is not None:
                await self.config.role(role).set(data)
        await self._repair_advanced_records()
        await self._refresh_reaction_cache()
        await self._load_component_views()
        return True

    async def _reaction_health(self, guild: discord.Guild) -> dict[str, Any]:
        records = await self.config.guild(guild).react_roles()
        issues = reaction_record_issues(
            records,
            channel_ids={channel.id for channel in [*guild.channels, *guild.threads]},
            role_ids={role.id for role in guild.roles},
        )
        for message_id, data in records.items():
            channel = guild.get_channel_or_thread(int(data.get("channel_id", 0) or 0))
            if channel is None or not hasattr(channel, "fetch_message"):
                continue
            try:
                await channel.fetch_message(int(message_id))
            except discord.NotFound:
                issues.append(f"Message {message_id} no longer exists.")
            except discord.Forbidden:
                issues.append(f"Message {message_id} cannot be read by the bot.")
            except (discord.HTTPException, ValueError):
                issues.append(f"Message {message_id} could not be verified.")
        invalid_messages = {str(message_id) for message_id in records if any(str(message_id) in issue for issue in issues)}
        valid = max(0, len(records) - len(invalid_messages))
        return {"messages": len(records), "valid": valid, "issues": issues}

    async def _reconcile_reaction_roles(
        self,
        guild: discord.Guild,
        *,
        remove_missing: bool,
    ) -> dict[str, int]:
        """Reapply roles from live reactions and optionally remove stale assignments."""
        records = await self.config.guild(guild).react_roles()
        desired: dict[int, set[int]] = {}
        managed_roles: set[int] = set()
        stats = {"messages": 0, "added": 0, "removed": 0, "missing": 0}
        for message_id, data in records.items():
            channel = guild.get_channel_or_thread(int(data.get("channel_id", 0) or 0))
            if not isinstance(channel, (discord.TextChannel, discord.Thread)):
                stats["missing"] += 1
                continue
            try:
                message = await channel.fetch_message(int(message_id))
            except (discord.NotFound, discord.Forbidden, discord.HTTPException, ValueError):
                stats["missing"] += 1
                continue
            stats["messages"] += 1
            bindings = data.get("binds", {})
            managed_roles.update(int(bind.get("role_id", 0) or 0) for bind in bindings.values())
            for reaction in message.reactions:
                bind = bindings.get(self._emoji_key(reaction.emoji))
                if not bind:
                    continue
                role_id = int(bind.get("role_id", 0) or 0)
                async for user in reaction.users(limit=None):
                    if not user.bot:
                        desired.setdefault(user.id, set()).add(role_id)
        current = {member.id: {role.id for role in member.roles} for member in guild.members if not member.bot}
        plan = plan_reaction_role_changes(
            current,
            desired,
            managed_roles,
            remove_missing=remove_missing,
        )
        for member_id, changes in plan.items():
            member = guild.get_member(member_id)
            if member is None:
                continue
            additions = [
                role
                for role_id in changes["add"]
                if (role := guild.get_role(role_id)) is not None and self._bot_can_apply_to_member(member, role)
            ]
            removals = [
                role
                for role_id in changes["remove"]
                if (role := guild.get_role(role_id)) is not None and self._bot_can_apply_to_member(member, role)
            ]
            if additions:
                with contextlib.suppress(discord.HTTPException):
                    await member.add_roles(*additions, reason="RoleManager reaction reconciliation.")
                    stats["added"] += len(additions)
            if removals:
                with contextlib.suppress(discord.HTTPException):
                    await member.remove_roles(*removals, reason="RoleManager reaction reconciliation.")
                    stats["removed"] += len(removals)
        return stats

    async def _inspect_legacy_source(
        self,
        guild: discord.Guild,
        source: str,
    ) -> dict[str, int]:
        """Read legacy cog data and return a no-write migration preview."""
        source = source.casefold()
        if source == "roletools":
            old = Config.get_conf(None, identifier=218773382617890828, cog_name="RoleTools")
            old.register_guild(
                reaction_roles={},
                auto_roles=[],
                buttons={},
                select_options={},
                select_menus={},
                temporary_roles=[],
            )
            old.register_role(
                sticky=False,
                selfassignable=False,
                selfremovable=False,
                exclusive_to=[],
                inclusive_with=[],
                required=[],
                cost=0,
                duration=None,
            )
            data = await old.guild(guild).all()
            configured_roles = 0
            for role in guild.roles:
                if role.is_default():
                    continue
                role_data = await old.role(role).all()
                if any(role_data.get(key) for key in role_data):
                    configured_roles += 1
            return {
                "reaction_bindings": len(data.get("reaction_roles", {})),
                "buttons": len(data.get("buttons", {})),
                "select_options": len(data.get("select_options", {})),
                "select_menus": len(data.get("select_menus", {})),
                "autoroles": len(data.get("auto_roles", [])),
                "temporary_roles": len(data.get("temporary_roles", [])),
                "configured_roles": configured_roles,
            }
        if source == "roleutils":
            old = Config.get_conf(None, identifier=326235423452394523, cog_name="RoleUtils")
            old.register_guild(
                autoroles={
                    "toggle": False,
                    "roles": [],
                    "bots": {"toggle": False, "roles": []},
                    "humans": {"toggle": False, "roles": []},
                },
            )
            old.register_role(sticky=False)
            old.init_custom("GuildMessage", 2)
            old.register_custom("GuildMessage", reactroles={"react_to_roleid": {}})
            data = await old.guild(guild).all()
            autoroles = data.get("autoroles", {})
            custom = await old.custom("GuildMessage", guild.id).all()
            sticky_roles = 0
            for role in guild.roles:
                if not role.is_default() and await old.role(role).sticky():
                    sticky_roles += 1
            return {
                "reaction_bindings": sum(len(item.get("reactroles", {}).get("react_to_roleid", {})) for item in custom.values()),
                "autoroles": len(autoroles.get("roles", []))
                + len(autoroles.get("humans", {}).get("roles", []))
                + len(autoroles.get("bots", {}).get("roles", [])),
                "sticky_roles": sticky_roles,
            }
        raise commands.BadArgument("Migration source must be roletools or roleutils.")

    @rolemanager.group(name="import")
    @commands.admin_or_permissions(manage_roles=True)
    async def import_group(self, ctx: commands.Context) -> None:
        """Import settings from RoleTools or RoleUtils config when present."""

    @import_group.command(name="roletools")
    async def import_roletools(self, ctx: commands.Context) -> None:
        """Import compatible settings from TrustyJAID RoleTools."""
        backup_id = await self._create_config_backup(ctx.guild, "before-roletools-import")
        imported = await self._import_roletools_settings(ctx.guild)
        await ctx.send(
            f"Imported RoleTools-compatible settings. Records touched: {imported:,}. Backup: `{backup_id}`.",
        )

    async def _import_roletools_settings(self, guild: discord.Guild) -> int:
        """Import RoleTools settings for a guild and return records touched."""
        old = Config.get_conf(None, identifier=218773382617890828, cog_name="RoleTools")
        old.register_guild(
            reaction_roles={},
            auto_roles=[],
            buttons={},
            select_options={},
            select_menus={},
            temporary_roles=[],
        )
        old.register_role(
            sticky=False,
            auto=False,
            reactions=[],
            buttons=[],
            select_options=[],
            selfassignable=False,
            selfremovable=False,
            exclusive_to=[],
            inclusive_with=[],
            required=[],
            require_any=False,
            cost=0,
            duration=None,
        )
        guild_data = await old.guild(guild).all()
        imported = 0
        async with self.config.guild(guild).react_roles() as react_roles:
            for key, role_id in guild_data.get("reaction_roles", {}).items():
                try:
                    channel_id, message_id, emoji_key = str(key).split("-", 2)
                except ValueError:
                    continue
                message_data = react_roles.setdefault(
                    str(message_id),
                    {"channel_id": int(channel_id), "binds": {}},
                )
                message_data["binds"][self._emoji_key(emoji_key)] = {
                    "role_id": int(role_id),
                    "remove_on_unreact": True,
                    "emoji": emoji_key,
                }
                imported += 1
        await self.config.guild(guild).buttons.set(guild_data.get("buttons", {}))
        await self.config.guild(guild).select_options.set(
            guild_data.get("select_options", {}),
        )
        await self.config.guild(guild).select_menus.set(
            guild_data.get("select_menus", {}),
        )
        auto_roles = [int(role_id) for role_id in guild_data.get("auto_roles", [])]
        if auto_roles:
            await self.config.guild(guild).auto_roles.set(
                {"enabled": True, "all": auto_roles, "humans": [], "bots": []},
            )
            imported += len(auto_roles)
        temp_roles = []
        for item in guild_data.get("temporary_roles", []):
            member_id = item.get("member_id", item.get("user_id"))
            role_id = item.get("role_id")
            expires_at = item.get("expires_at", item.get("remove_at"))
            if member_id and role_id and expires_at:
                temp_roles.append(
                    {
                        "member_id": int(member_id),
                        "role_id": int(role_id),
                        "expires_at": float(expires_at),
                    },
                )
        if temp_roles:
            await self.config.guild(guild).temporary_roles.set(temp_roles)
            imported += len(temp_roles)
        for role in guild.roles:
            if role.is_default():
                continue
            data = await old.role(role).all()
            await self.config.role(role).self_assignable.set(
                bool(data.get("selfassignable")),
            )
            await self.config.role(role).self_removable.set(
                bool(data.get("selfremovable")),
            )
            await self.config.role(role).sticky.set(bool(data.get("sticky")))
            await self.config.role(role).temp_duration.set(data.get("duration"))
            await self.config.role(role).exclusive_to.set(
                data.get("exclusive_to") or [],
            )
            await self.config.role(role).inclusive_with.set(
                data.get("inclusive_with") or [],
            )
            await self.config.role(role).required.set(data.get("required") or [])
            await self.config.role(role).require_any.set(bool(data.get("require_any")))
            await self.config.role(role).cost.set(int(data.get("cost") or 0))
        await self._repair_advanced_records()
        await self._refresh_reaction_cache()
        await self._load_component_views()
        async with self.config.guild(guild).migration_history() as history:
            history.append(
                {
                    "source": "RoleTools",
                    "records": imported,
                    "timestamp": self._now_ts(),
                },
            )
            history[:] = trim_history(history, maximum=25)
        return imported

    @import_group.command(name="roleutils")
    async def import_roleutils(self, ctx: commands.Context) -> None:
        """Import compatible settings from Seina RoleUtils."""
        backup_id = await self._create_config_backup(ctx.guild, "before-roleutils-import")
        imported = await self._import_roleutils_settings(ctx.guild)
        await ctx.send(
            f"Imported RoleUtils-compatible settings. Records touched: {imported:,}. Backup: `{backup_id}`.",
        )

    async def _import_roleutils_settings(self, guild: discord.Guild) -> int:
        """Import RoleUtils settings for a guild and return records touched."""
        old = Config.get_conf(None, identifier=326235423452394523, cog_name="RoleUtils")
        old.register_guild(
            reactroles={"channels": [], "enabled": True},
            autoroles={
                "toggle": False,
                "roles": [],
                "bots": {"toggle": False, "roles": []},
                "humans": {"toggle": False, "roles": []},
            },
        )
        old.register_role(sticky=False)
        old.init_custom("GuildMessage", 2)
        old.register_custom("GuildMessage", reactroles={"react_to_roleid": {}})
        guild_data = await old.guild(guild).all()
        autoroles = guild_data.get("autoroles", {})
        await self.config.guild(guild).auto_roles.set(
            {
                "enabled": bool(autoroles.get("toggle")),
                "all": [int(role_id) for role_id in autoroles.get("roles", [])],
                "humans": [int(role_id) for role_id in autoroles.get("humans", {}).get("roles", [])],
                "bots": [int(role_id) for role_id in autoroles.get("bots", {}).get("roles", [])],
            },
        )
        imported = len(autoroles.get("roles", []))
        custom_data = await old.custom("GuildMessage", guild.id).all()
        async with self.config.guild(guild).react_roles() as react_roles:
            for message_id, message_data in custom_data.items():
                rr_data = message_data.get("reactroles", {})
                binds = rr_data.get("react_to_roleid", {})
                if not binds:
                    continue
                converted = react_roles.setdefault(
                    str(message_id),
                    {"channel_id": rr_data.get("channel"), "binds": {}},
                )
                for emoji_key, role_id in binds.items():
                    if emoji_key == "rules":
                        continue
                    converted["binds"][self._emoji_key(emoji_key)] = {
                        "role_id": int(role_id),
                        "remove_on_unreact": True,
                        "emoji": str(emoji_key),
                    }
                    imported += 1
        for role in guild.roles:
            if role.is_default():
                continue
            data = await old.role(role).all()
            if data.get("sticky"):
                await self.config.role(role).sticky.set(True)
                imported += 1
        await self._repair_advanced_records()
        await self._refresh_reaction_cache()
        async with self.config.guild(guild).migration_history() as history:
            history.append(
                {
                    "source": "RoleUtils",
                    "records": imported,
                    "timestamp": self._now_ts(),
                },
            )
            history[:] = trim_history(history, maximum=25)
        return imported

    @rolemanager.group(name="migration", aliases=["migrate"])
    @commands.admin_or_permissions(manage_roles=True)
    async def migration_group(self, ctx: commands.Context) -> None:
        """Verify, reconcile, export, or roll back imported role data."""

    @migration_group.command(name="verify", aliases=["preview"])
    async def migration_verify(self, ctx: commands.Context) -> None:
        """Validate imported reaction, component, role, and temporary-role records."""
        health = await self._reaction_health(ctx.guild)
        data = await self.config.guild(ctx.guild).all()
        invalid_temp = sum(
            1
            for item in data.get("temporary_roles", [])
            if ctx.guild.get_member(int(item.get("member_id", 0) or 0)) is None
            or ctx.guild.get_role(int(item.get("role_id", 0) or 0)) is None
        )
        component_issues = sum(
            1 for item in data.get("buttons", {}).values() if ctx.guild.get_role(int(item.get("role_id", 0) or 0)) is None
        )
        saved_options = data.get("select_options", {})
        component_issues += sum(
            1 for item in saved_options.values() if ctx.guild.get_role(int(item.get("role_id", 0) or 0)) is None
        )
        component_issues += sum(
            1
            for menu in data.get("select_menus", {}).values()
            for option in menu.get("options", [])
            if option not in saved_options
        )
        lines = [
            f"Reaction messages: {health['valid']}/{health['messages']} valid",
            f"Buttons: {len(data.get('buttons', {}))}",
            f"Select menus: {len(data.get('select_menus', {}))}",
            f"Component references needing cleanup: {component_issues}",
            f"Temporary records needing cleanup: {invalid_temp}",
        ]
        lines.extend(f"- {issue}" for issue in health["issues"][:20])
        await ctx.send("\n".join(lines))

    @migration_group.command(name="inspect")
    async def migration_inspect(self, ctx: commands.Context, source: str) -> None:
        """Preview legacy RoleTools or RoleUtils records without changing anything."""
        counts = await self._inspect_legacy_source(ctx.guild, source)
        await ctx.send(
            f"{source.title()} migration preview:\n"
            + "\n".join(f"- {key.replace('_', ' ').title()}: {value:,}" for key, value in counts.items()),
        )

    @migration_group.command(name="reconcile", aliases=["sync"])
    @commands.bot_has_permissions(manage_roles=True, read_message_history=True)
    async def migration_reconcile(
        self,
        ctx: commands.Context,
        mode: str = "add",
        confirmation: str = "",
    ) -> None:
        """Reapply live reaction roles; use `sync` to also remove stale roles."""
        mode = mode.lower()
        if mode not in {"add", "sync"}:
            raise commands.BadArgument("Mode must be `add` or `sync`.")
        if mode == "sync" and confirmation.upper() != "CONFIRM":
            await ctx.send("Full sync can remove roles. Run it again as `sync CONFIRM`.")
            return
        stats = await self._reconcile_reaction_roles(ctx.guild, remove_missing=mode == "sync")
        await ctx.send(
            f"Reconciled {stats['messages']} message(s): {stats['added']} added, "
            f"{stats['removed']} removed, {stats['missing']} unavailable.",
        )

    @migration_group.command(name="backups")
    async def migration_backups(self, ctx: commands.Context) -> None:
        """List automatic migration backups."""
        backups = await self.config.guild(ctx.guild).backups()
        if not backups:
            await ctx.send("No RoleManager backups exist for this server.")
            return
        lines = [
            f"`{backup_id}` — {item.get('source', 'manual')} — <t:{int(item.get('created_at', 0))}:R>"
            for backup_id, item in sorted(backups.items(), key=lambda pair: pair[1].get("created_at", 0), reverse=True)
        ]
        await ctx.send("\n".join(lines))

    @migration_group.command(name="backup")
    async def migration_backup(self, ctx: commands.Context, *, label: str = "manual") -> None:
        """Create a manual configuration backup."""
        backup_id = await self._create_config_backup(ctx.guild, label[:80])
        await ctx.send(f"Created backup `{backup_id}`.")

    @migration_group.command(name="rollback", aliases=["restore"])
    async def migration_rollback(self, ctx: commands.Context, backup_id: str) -> None:
        """Restore a RoleManager backup."""
        safety_id = await self._create_config_backup(ctx.guild, "before-rollback")
        if not await self._restore_config_backup(ctx.guild, backup_id):
            await ctx.send(f"Backup `{backup_id}` was not found.")
            return
        await ctx.send(f"Restored `{backup_id}`. Pre-rollback safety backup: `{safety_id}`.")

    @migration_group.command(name="export")
    async def migration_export(self, ctx: commands.Context) -> None:
        """Export the current guild and role configuration as JSON."""
        payload = {
            "guild_id": ctx.guild.id,
            "exported_at": self._now_ts(),
            "guild": await self.config.guild(ctx.guild).all(),
            "roles": {str(role.id): await self.config.role(role).all() for role in ctx.guild.roles if not role.is_default()},
        }
        content = json.dumps(payload, indent=2, sort_keys=True, default=str).encode()
        await ctx.send(file=discord.File(io.BytesIO(content), filename=f"rolemanager-{ctx.guild.id}.json"))

    @rolemanager.group(name="role")
    @commands.admin_or_permissions(manage_roles=True)
    @commands.bot_has_permissions(manage_roles=True)
    async def role_group(self, ctx: commands.Context) -> None:
        """Add, remove, or toggle roles for one member."""

    @role_group.command(name="add")
    async def role_add(
        self,
        ctx: commands.Context,
        member: discord.Member,
        *,
        role: discord.Role,
    ) -> None:
        """Add a role to one member."""
        self._check_role_manageable(ctx, role)
        result = await self._apply_role_to_members(
            ctx,
            role,
            [member],
            adding=True,
            reason=get_audit_reason(ctx.author, "RoleManager role add."),
        )
        await self._send_operation_result(ctx, role, result, adding=True)

    @role_group.command(name="remove")
    async def role_remove(
        self,
        ctx: commands.Context,
        member: discord.Member,
        *,
        role: discord.Role,
    ) -> None:
        """Remove a role from one member."""
        self._check_role_manageable(ctx, role)
        result = await self._apply_role_to_members(
            ctx,
            role,
            [member],
            adding=False,
            reason=get_audit_reason(ctx.author, "RoleManager role remove."),
        )
        await self._send_operation_result(ctx, role, result, adding=False)

    @role_group.command(name="toggle")
    async def role_toggle(
        self,
        ctx: commands.Context,
        member: discord.Member,
        *,
        role: discord.Role,
    ) -> None:
        """Add or remove a role from one member depending on current state."""
        self._check_role_manageable(ctx, role)
        adding = role not in member.roles
        result = await self._apply_role_to_members(
            ctx,
            role,
            [member],
            adding=adding,
            reason=get_audit_reason(ctx.author, "RoleManager role toggle."),
        )
        await self._send_operation_result(ctx, role, result, adding=adding)

    @role_group.command(name="create")
    async def role_create(self, ctx: commands.Context, *, name: str) -> None:
        """Create a role."""
        if len(ctx.guild.roles) >= 250:
            await ctx.send("This server is already at Discord's 250 role limit.")
            return
        role = await ctx.guild.create_role(
            name=name,
            reason=get_audit_reason(ctx.author, "RoleManager role create."),
        )
        await self._record_role_audit(
            ctx.guild,
            action="role_created",
            role_ids=[role.id],
            actor_id=ctx.author.id,
            source="role-command",
            detail=role.name,
        )
        await ctx.send(
            f"Created {role.mention}.",
            allowed_mentions=discord.AllowedMentions.none(),
        )

    @role_group.command(name="name", aliases=["rename"])
    async def role_name(
        self,
        ctx: commands.Context,
        role: discord.Role,
        *,
        name: str,
    ) -> None:
        """Rename a role."""
        self._check_role_manageable(ctx, role)
        old_name = role.name
        await role.edit(
            name=name,
            reason=get_audit_reason(ctx.author, "RoleManager role rename."),
        )
        await self._record_role_audit(
            ctx.guild,
            action="role_renamed",
            role_ids=[role.id],
            actor_id=ctx.author.id,
            source="role-command",
            detail=f"{old_name} -> {name}",
        )
        await ctx.send(f"Renamed `{old_name}` to `{name}`.")

    @role_group.command(name="color", aliases=["colour"])
    async def role_color(
        self,
        ctx: commands.Context,
        role: discord.Role,
        color: discord.Color,
    ) -> None:
        """Change a role color."""
        self._check_role_manageable(ctx, role)
        await role.edit(
            color=color,
            reason=get_audit_reason(ctx.author, "RoleManager role color."),
        )
        await self._record_role_audit(
            ctx.guild,
            action="role_color_changed",
            role_ids=[role.id],
            actor_id=ctx.author.id,
            source="role-command",
            detail=str(color),
        )
        await ctx.send(
            f"Changed {role.mention} color to `{color}`.",
            allowed_mentions=discord.AllowedMentions.none(),
        )

    @role_group.command(name="hoist")
    async def role_hoist(
        self,
        ctx: commands.Context,
        role: discord.Role,
        enabled: bool | None = None,
    ) -> None:
        """Toggle whether a role appears separately in the member list."""
        self._check_role_manageable(ctx, role)
        enabled = not role.hoist if enabled is None else bool(enabled)
        await role.edit(
            hoist=enabled,
            reason=get_audit_reason(ctx.author, "RoleManager role hoist."),
        )
        await self._record_role_audit(
            ctx.guild,
            action="role_hoist_changed",
            role_ids=[role.id],
            actor_id=ctx.author.id,
            source="role-command",
            detail=str(enabled),
        )
        await ctx.send(
            f"{role.mention} is {'now' if enabled else 'no longer'} hoisted.",
            allowed_mentions=discord.AllowedMentions.none(),
        )

    @role_group.command(name="mentionable")
    async def role_mentionable(
        self,
        ctx: commands.Context,
        role: discord.Role,
        enabled: bool | None = None,
    ) -> None:
        """Toggle whether everyone can mention a role."""
        self._check_role_manageable(ctx, role)
        enabled = not role.mentionable if enabled is None else bool(enabled)
        await role.edit(
            mentionable=enabled,
            reason=get_audit_reason(ctx.author, "RoleManager role mentionable."),
        )
        await self._record_role_audit(
            ctx.guild,
            action="role_mentionable_changed",
            role_ids=[role.id],
            actor_id=ctx.author.id,
            source="role-command",
            detail=str(enabled),
        )
        await ctx.send(
            f"{role.mention} is {'now' if enabled else 'no longer'} mentionable.",
            allowed_mentions=discord.AllowedMentions.none(),
        )

    @role_group.command(name="info")
    async def role_info(self, ctx: commands.Context, role: discord.Role) -> None:
        """Show Discord and RoleManager details for a role."""
        data = await self.config.role(role).all()
        permissions = [name for name, enabled in role.permissions if enabled]
        embed = discord.Embed(
            title=role.name,
            color=role.color,
            description=role.mention,
        )
        embed.add_field(name="ID", value=str(role.id))
        embed.add_field(name="Members", value=str(len(role.members)))
        embed.add_field(name="Position", value=str(role.position))
        embed.add_field(name="Hoisted", value=str(role.hoist))
        embed.add_field(name="Mentionable", value=str(role.mentionable))
        embed.add_field(name="Managed", value=str(role.managed))
        embed.add_field(
            name="RoleManager",
            value=(
                f"Self assignable: {bool(data.get('self_assignable'))}\n"
                f"Self removable: {bool(data.get('self_removable'))}\n"
                f"Sticky: {bool(data.get('sticky'))}\n"
                f"Temporary: {int(data.get('temp_duration') or 0)} seconds"
            ),
            inline=False,
        )
        embed.add_field(
            name="Permissions",
            value=", ".join(permissions)[:1024] or "None",
            inline=False,
        )
        await ctx.send(embed=embed, allowed_mentions=discord.AllowedMentions.none())

    @role_group.command(name="members", aliases=["dump", "export"])
    async def role_members(self, ctx: commands.Context, role: discord.Role) -> None:
        """List or export every member with a role."""
        lines = [f"{member.id}\t{member}" for member in sorted(role.members, key=lambda item: item.id)]
        if not lines:
            await ctx.send(f"No members have {role.mention}.")
            return
        content = "\n".join(lines)
        if len(content) <= 1800:
            await ctx.send(f"```text\n{content}\n```")
            return
        await ctx.send(
            f"Exported {len(lines)} member(s) with {role.name}.",
            file=discord.File(io.BytesIO(content.encode()), filename=f"role-{role.id}-members.txt"),
        )

    @role_group.command(name="colors", aliases=["colours"])
    async def role_colors(self, ctx: commands.Context) -> None:
        """Export the server's role color palette."""
        roles = [role for role in reversed(ctx.guild.roles) if not role.is_default()]
        lines = [f"#{role.color.value:06X}\t{role.id}\t{role.name}" for role in roles]
        content = "\n".join(lines) or "No roles."
        await ctx.send(
            file=discord.File(io.BytesIO(content.encode()), filename=f"{ctx.guild.id}-role-colors.txt"),
        )

    @role_group.command(name="unused")
    async def role_unused(self, ctx: commands.Context) -> None:
        """Find editable roles which have no members."""
        roles = [role for role in reversed(ctx.guild.roles) if not role.is_default() and not role.managed and not role.members]
        content = "\n".join(f"{role.id}\t{role.name}" for role in roles)
        if not content:
            await ctx.send("There are no unused editable roles.")
        elif len(content) <= 1800:
            await ctx.send(f"```text\n{content}\n```")
        else:
            await ctx.send(
                f"Found {len(roles)} unused roles.",
                file=discord.File(io.BytesIO(content.encode()), filename="unused-roles.txt"),
            )

    @role_group.command(name="clone")
    async def role_clone(
        self,
        ctx: commands.Context,
        role: discord.Role,
        *,
        name: str | None = None,
    ) -> None:
        """Clone a role's appearance and permissions."""
        self._check_role_manageable(ctx, role)
        clone = await ctx.guild.create_role(
            name=name or f"{role.name} copy",
            permissions=role.permissions,
            color=role.color,
            hoist=role.hoist,
            mentionable=role.mentionable,
            reason=get_audit_reason(ctx.author, "RoleManager role clone."),
        )
        with contextlib.suppress(discord.HTTPException):
            await clone.edit(position=max(1, role.position - 1))
        await self._record_role_audit(
            ctx.guild,
            action="role_cloned",
            role_ids=[role.id, clone.id],
            actor_id=ctx.author.id,
            source="role-command",
            detail=clone.name,
        )
        await ctx.send(f"Created {clone.mention} from `{role.name}`.")

    @role_group.command(name="delete")
    async def role_delete(
        self,
        ctx: commands.Context,
        role: discord.Role,
        confirmation: str = "",
    ) -> None:
        """Delete a role. The final argument must be CONFIRM."""
        self._check_role_manageable(ctx, role)
        if confirmation.upper() != "CONFIRM":
            await ctx.send("This is destructive. Run the command again with `CONFIRM` at the end.")
            return
        name = role.name
        role_id = role.id
        await role.delete(reason=get_audit_reason(ctx.author, "RoleManager role delete."))
        await self._record_role_audit(
            ctx.guild,
            action="role_deleted",
            role_ids=[role_id],
            actor_id=ctx.author.id,
            source="role-command",
            detail=name,
        )
        await ctx.send(f"Deleted `{name}`.")

    @role_group.command(name="position")
    async def role_position(
        self,
        ctx: commands.Context,
        role: discord.Role,
        position: int,
    ) -> None:
        """Move a role to a new hierarchy position."""
        self._check_role_manageable(ctx, role)
        maximum = max(1, ctx.guild.me.top_role.position - 1)
        position = max(1, min(position, maximum))
        await role.edit(
            position=position,
            reason=get_audit_reason(ctx.author, "RoleManager role position."),
        )
        await self._record_role_audit(
            ctx.guild,
            action="role_position_changed",
            role_ids=[role.id],
            actor_id=ctx.author.id,
            source="role-command",
            detail=str(position),
        )
        await ctx.send(f"Moved {role.mention} to position {position}.")

    @role_group.command(name="permission", aliases=["perm"])
    async def role_permission(
        self,
        ctx: commands.Context,
        role: discord.Role,
        permission: str,
        enabled: bool,
    ) -> None:
        """Enable or disable one Discord permission on a role."""
        self._check_role_manageable(ctx, role)
        permission = permission.lower().replace(" ", "_")
        if permission not in discord.Permissions.VALID_FLAGS:
            raise commands.BadArgument(f"Unknown Discord permission: {permission}")
        permissions = role.permissions
        permissions.update(**{permission: enabled})
        await role.edit(
            permissions=permissions,
            reason=get_audit_reason(ctx.author, "RoleManager role permission."),
        )
        await self._record_role_audit(
            ctx.guild,
            action="role_permission_changed",
            role_ids=[role.id],
            actor_id=ctx.author.id,
            source="role-command",
            detail=f"{permission}={enabled}",
        )
        await ctx.send(f"Set `{permission}` on {role.mention} to `{enabled}`.")

    @role_group.command(name="icon")
    async def role_icon(
        self,
        ctx: commands.Context,
        role: discord.Role,
        icon: str | None = None,
    ) -> None:
        """Set a role icon from an attachment or Unicode emoji; use `none` to clear."""
        self._check_role_manageable(ctx, role)
        display_icon: bytes | str | None
        if ctx.message.attachments:
            display_icon = await ctx.message.attachments[0].read()
        elif icon and icon.casefold() not in {"none", "clear", "off"}:
            display_icon = icon
        else:
            display_icon = None
        try:
            await role.edit(
                display_icon=display_icon,
                reason=get_audit_reason(ctx.author, "RoleManager role icon."),
            )
        except TypeError as exc:
            raise commands.UserFeedbackCheckFailure(
                "This Discord.py/Red version does not support editing role icons.",
            ) from exc
        await self._record_role_audit(
            ctx.guild,
            action="role_icon_changed",
            role_ids=[role.id],
            actor_id=ctx.author.id,
            source="role-command",
        )
        await ctx.send(f"Updated the icon for {role.mention}.")

    @role_group.command(name="addmulti", aliases=["addmany"])
    async def role_addmulti(
        self,
        ctx: commands.Context,
        role: discord.Role,
        members: commands.Greedy[discord.Member],
    ) -> None:
        """Add one role to multiple explicit members."""
        self._check_role_manageable(ctx, role)
        if not members:
            await ctx.send_help(ctx.command)
            return
        result = await self._apply_role_to_members(
            ctx,
            role,
            members,
            adding=True,
            reason=get_audit_reason(ctx.author, "RoleManager role addmulti."),
        )
        await self._send_operation_result(ctx, role, result, adding=True)

    @role_group.command(name="removemulti", aliases=["removemany"])
    async def role_removemulti(
        self,
        ctx: commands.Context,
        role: discord.Role,
        members: commands.Greedy[discord.Member],
    ) -> None:
        """Remove one role from multiple explicit members."""
        self._check_role_manageable(ctx, role)
        if not members:
            await ctx.send_help(ctx.command)
            return
        result = await self._apply_role_to_members(
            ctx,
            role,
            members,
            adding=False,
            reason=get_audit_reason(ctx.author, "RoleManager role removemulti."),
        )
        await self._send_operation_result(ctx, role, result, adding=False)

    @role_group.command(name="multigive", aliases=["multiadd"])
    async def role_multigive(
        self,
        ctx: commands.Context,
        member: discord.Member,
        roles: commands.Greedy[discord.Role],
    ) -> None:
        """Add multiple roles to one member."""
        if not roles:
            await ctx.send_help(ctx.command)
            return
        for role in roles:
            self._check_role_manageable(ctx, role)
        responses, added, removed = await self._give_roles(
            member,
            roles,
            get_audit_reason(ctx.author, "RoleManager multigive."),
            check_cost=False,
        )
        lines = [f"Added: {self._format_role_names(added)}"]
        if removed:
            lines.append(f"Removed by policy: {self._format_role_names(removed)}")
        if responses:
            lines.append("Issues:\n" + self._response_text(responses))
        await ctx.send(
            "\n".join(lines),
            allowed_mentions=discord.AllowedMentions.none(),
        )

    @role_group.command(name="multiremove", aliases=["multirem"])
    async def role_multiremove(
        self,
        ctx: commands.Context,
        member: discord.Member,
        roles: commands.Greedy[discord.Role],
    ) -> None:
        """Remove multiple roles from one member."""
        if not roles:
            await ctx.send_help(ctx.command)
            return
        for role in roles:
            self._check_role_manageable(ctx, role)
        responses, removed = await self._remove_roles(
            member,
            roles,
            get_audit_reason(ctx.author, "RoleManager multiremove."),
        )
        lines = [f"Removed: {self._format_role_names(removed)}"]
        if responses:
            lines.append("Issues:\n" + self._response_text(responses))
        await ctx.send(
            "\n".join(lines),
            allowed_mentions=discord.AllowedMentions.none(),
        )

    @role_group.command(name="uniquemembers", aliases=["um"])
    async def role_unique_members(
        self,
        ctx: commands.Context,
        roles: commands.Greedy[discord.Role],
    ) -> None:
        """View the total unique members between multiple roles."""
        if len(roles) < 2:
            raise commands.BadArgument("Provide at least two roles.")
        await self._ensure_member_cache(ctx.guild)
        unique_members: set[discord.Member] = set()
        lines = []
        for role in roles:
            unique_members.update(role.members)
            lines.append(f"{role.mention}: {len(role.members):,} member(s)")
        lines.insert(0, f"Unique members: {len(unique_members):,}")
        embed = discord.Embed(
            title=f"Unique members between {len(roles):,} roles",
            description="\n".join(lines),
            color=roles[0].color,
        )
        await ctx.send(embed=embed, allowed_mentions=discord.AllowedMentions.none())

    @role_group.command(name="custom")
    async def role_custom(
        self,
        ctx: commands.Context,
        members: commands.Greedy[discord.Member],
        *,
        spec: str,
    ) -> None:
        """Add and remove roles for users with `--add role,role --remove role,role`."""
        if not members:
            await ctx.send_help(ctx.command)
            return
        to_add, to_remove = self._role_actions_from_spec(ctx.guild, spec)
        for role in to_add + to_remove:
            self._check_role_manageable(ctx, role)
        completed = 0
        failed = 0
        for member in members:
            add_responses, _added, _removed_by_policy = await self._give_roles(
                member,
                to_add,
                get_audit_reason(ctx.author, "RoleManager custom add."),
                check_cost=False,
            )
            remove_responses, _removed = await self._remove_roles(
                member,
                to_remove,
                get_audit_reason(ctx.author, "RoleManager custom remove."),
            )
            if add_responses or remove_responses:
                failed += 1
            else:
                completed += 1
        await ctx.send(f"Updated {completed:,} member(s); {failed:,} had issues.")

    @rolemanager.group(name="dryrun")
    @commands.admin_or_permissions(manage_roles=True)
    @commands.bot_has_permissions(manage_roles=True)
    async def dryrun_group(self, ctx: commands.Context) -> None:
        """Preview bulk role changes without applying them."""

    @dryrun_group.command(name="add")
    async def dryrun_add(
        self,
        ctx: commands.Context,
        role: discord.Role,
        *targets: TargetType,
    ) -> None:
        """Preview a bulk role add."""
        self._check_role_manageable(ctx, role)
        members, labels = await self._members_from_targets(ctx, targets)
        eligible = 0
        failures = 0
        policy_added: set[discord.Role] = set()
        policy_removed: set[discord.Role] = set()
        for member in members[:500]:
            responses, added, removed = await self._give_roles(
                member,
                [role],
                "RoleManager dry-run.",
                check_cost=False,
                dry_run=True,
            )
            if role in added:
                eligible += 1
            if responses:
                failures += 1
            policy_added.update(added)
            policy_removed.update(removed)
        await ctx.send(
            "\n".join(
                [
                    f"Targets: {len(members):,} from {humanize_list(labels)}",
                    f"Would add {role.mention} to {eligible:,} member(s).",
                    f"Members with policy issues: {failures:,}",
                    f"Policy may also add: {self._format_role_names(policy_added - {role})}",
                    f"Policy may remove: {self._format_role_names(policy_removed)}",
                ],
            ),
            allowed_mentions=discord.AllowedMentions.none(),
        )

    @dryrun_group.command(name="remove")
    async def dryrun_remove(
        self,
        ctx: commands.Context,
        role: discord.Role,
        *targets: TargetType,
    ) -> None:
        """Preview a bulk role removal."""
        self._check_role_manageable(ctx, role)
        members, labels = await self._members_from_targets(ctx, targets)
        eligible = 0
        failures = 0
        policy_removed: set[discord.Role] = set()
        for member in members[:500]:
            responses, removed = await self._remove_roles(
                member,
                [role],
                "RoleManager dry-run.",
                dry_run=True,
            )
            if role in removed:
                eligible += 1
            if responses:
                failures += 1
            policy_removed.update(removed)
        await ctx.send(
            "\n".join(
                [
                    f"Targets: {len(members):,} from {humanize_list(labels)}",
                    f"Would remove {role.mention} from {eligible:,} member(s).",
                    f"Members with policy issues: {failures:,}",
                    f"Policy may also remove: {self._format_role_names(policy_removed - {role})}",
                ],
            ),
            allowed_mentions=discord.AllowedMentions.none(),
        )

    @rolemanager.command(name="giverole")
    @commands.admin_or_permissions(manage_roles=True)
    @commands.bot_has_permissions(manage_roles=True)
    @commands.max_concurrency(1, commands.BucketType.guild)
    async def giverole(
        self,
        ctx: commands.Context,
        role: discord.Role,
        *targets: TargetType,
    ) -> None:
        """Bulk-add a role to members, roles, channels, humans, bots, here, or everyone."""
        self._check_role_manageable(ctx, role)
        members, labels = await self._members_from_targets(ctx, targets)
        if not members:
            await ctx.send("No members matched those targets.")
            return
        await ctx.send(
            f"Adding {role.mention} to matching members from {humanize_list(labels)}...",
            allowed_mentions=discord.AllowedMentions.none(),
        )
        result = await self._apply_role_to_members(
            ctx,
            role,
            members,
            adding=True,
            reason=get_audit_reason(ctx.author, "RoleManager bulk add."),
        )
        await self._send_operation_result(ctx, role, result, adding=True)

    @rolemanager.command(name="removerole")
    @commands.admin_or_permissions(manage_roles=True)
    @commands.bot_has_permissions(manage_roles=True)
    @commands.max_concurrency(1, commands.BucketType.guild)
    async def removerole(
        self,
        ctx: commands.Context,
        role: discord.Role,
        *targets: TargetType,
    ) -> None:
        """Bulk-remove a role from members, roles, channels, humans, bots, here, or everyone."""
        self._check_role_manageable(ctx, role)
        members, labels = await self._members_from_targets(ctx, targets)
        if not members:
            await ctx.send("No members matched those targets.")
            return
        await ctx.send(
            f"Removing {role.mention} from matching members from {humanize_list(labels)}...",
            allowed_mentions=discord.AllowedMentions.none(),
        )
        result = await self._apply_role_to_members(
            ctx,
            role,
            members,
            adding=False,
            reason=get_audit_reason(ctx.author, "RoleManager bulk remove."),
        )
        await self._send_operation_result(ctx, role, result, adding=False)

    @rolemanager.group(name="target", aliases=["targets"])
    @commands.admin_or_permissions(manage_roles=True)
    async def target_group(self, ctx: commands.Context) -> None:
        """Preview, save, and apply advanced member targeting queries."""

    @target_group.command(name="preview")
    async def target_preview(self, ctx: commands.Context, *, query: str) -> None:
        """Preview `key=value` filters without changing roles."""
        members = await self._members_from_query(ctx.guild, query)
        preview = "\n".join(f"{member} ({member.id})" for member in members)
        summary = f"Matched {len(members):,} member(s)."
        if not preview:
            await ctx.send(summary)
        elif len(preview) <= 1700:
            await ctx.send(f"{summary}\n```text\n{preview}\n```")
        else:
            await ctx.send(
                summary,
                file=discord.File(
                    io.BytesIO(preview.encode("utf-8")),
                    filename="rolemanager-target-preview.txt",
                ),
            )

    @target_group.command(name="add")
    @commands.bot_has_permissions(manage_roles=True)
    async def target_add(
        self,
        ctx: commands.Context,
        role: discord.Role,
        *,
        query: str,
    ) -> None:
        """Add a role to members matching an advanced query."""
        self._check_role_manageable(ctx, role)
        members = await self._members_from_query(ctx.guild, query)
        result = await self._apply_role_to_members(
            ctx,
            role,
            members,
            adding=True,
            reason=get_audit_reason(ctx.author, f"RoleManager target add: {query}"),
        )
        await self._send_operation_result(ctx, role, result, adding=True)

    @target_group.command(name="remove")
    @commands.bot_has_permissions(manage_roles=True)
    async def target_remove(
        self,
        ctx: commands.Context,
        role: discord.Role,
        *,
        query: str,
    ) -> None:
        """Remove a role from members matching an advanced query."""
        self._check_role_manageable(ctx, role)
        members = await self._members_from_query(ctx.guild, query)
        result = await self._apply_role_to_members(
            ctx,
            role,
            members,
            adding=False,
            reason=get_audit_reason(ctx.author, f"RoleManager target remove: {query}"),
        )
        await self._send_operation_result(ctx, role, result, adding=False)

    @target_group.command(name="save")
    async def target_save(
        self,
        ctx: commands.Context,
        name: str,
        *,
        query: str,
    ) -> None:
        """Save a validated advanced target query."""
        await self._members_from_query(ctx.guild, query)
        clean_name = name.casefold().strip()
        if not clean_name or len(clean_name) > 50:
            raise commands.BadArgument("Preset name must be 1-50 characters.")
        async with self.config.guild(ctx.guild).target_presets() as presets:
            presets[clean_name] = query
        await ctx.send(f"Saved target preset `{clean_name}`.")

    @target_group.command(name="delete")
    async def target_delete(self, ctx: commands.Context, *, name: str) -> None:
        """Delete a saved target query."""
        async with self.config.guild(ctx.guild).target_presets() as presets:
            if presets.pop(name.casefold().strip(), None) is None:
                raise commands.BadArgument("That target preset does not exist.")
        await ctx.send("Target preset deleted.")

    @target_group.command(name="list")
    async def target_list(self, ctx: commands.Context) -> None:
        """List saved advanced target queries."""
        presets = await self.config.guild(ctx.guild).target_presets()
        if not presets:
            await ctx.send("No target presets are saved.")
            return
        await ctx.send(
            "\n".join(f"`{name}`: `{query}`" for name, query in sorted(presets.items())),
        )

    @target_group.command(name="run", aliases=["apply"])
    @commands.bot_has_permissions(manage_roles=True)
    async def target_run(
        self,
        ctx: commands.Context,
        action: str,
        role: discord.Role,
        *,
        name: str,
    ) -> None:
        """Apply a saved target preset with action `add` or `remove`."""
        action = action.lower()
        if action not in {"add", "remove"}:
            raise commands.BadArgument("Action must be `add` or `remove`.")
        self._check_role_manageable(ctx, role)
        presets = await self.config.guild(ctx.guild).target_presets()
        query = presets.get(name.casefold().strip())
        if query is None:
            raise commands.BadArgument("That target preset does not exist.")
        members = await self._members_from_query(ctx.guild, query)
        result = await self._apply_role_to_members(
            ctx,
            role,
            members,
            adding=action == "add",
            reason=get_audit_reason(ctx.author, f"RoleManager target preset {name}."),
        )
        await self._send_operation_result(ctx, role, result, adding=action == "add")

    async def _save_bulk_job(self, guild: discord.Guild, record: dict[str, Any]) -> None:
        record = dict(record)
        if int(record.get("actor_id", 0) or 0) in self._deleted_user_ids:
            record["actor_id"] = None
        async with self.config.guild(guild).bulk_jobs() as jobs:
            jobs[:] = [item for item in jobs if item.get("id") != record.get("id")]
            jobs.append(dict(record))
            jobs[:] = trim_history(jobs, maximum=25)

    async def _run_bulk_job(
        self,
        guild: discord.Guild,
        record: dict[str, Any],
        member_ids: Sequence[int],
    ) -> None:
        key = f"{guild.id}:{record['id']}"
        role = guild.get_role(int(record["role_id"]))
        try:
            if role is None:
                record.update(status="failed", error="Role no longer exists.")
                return
            for index, member_id in enumerate(member_ids, start=1):
                member = guild.get_member(int(member_id))
                if member is None:
                    record["skipped"] += 1
                elif record["action"] == "add":
                    responses, added, _removed = await self._give_roles(
                        member,
                        [role],
                        f"RoleManager bulk job {record['id']}.",
                        check_cost=False,
                    )
                    if role in added:
                        record["completed"] += 1
                    elif responses:
                        record["failed"] += 1
                    else:
                        record["skipped"] += 1
                else:
                    responses, removed = await self._remove_roles(
                        member,
                        [role],
                        f"RoleManager bulk job {record['id']}.",
                    )
                    if role in removed:
                        record["completed"] += 1
                    elif responses:
                        record["failed"] += 1
                    else:
                        record["skipped"] += 1
                record["processed"] = index
                if index % 20 == 0:
                    await self._save_bulk_job(guild, record)
                    await asyncio.sleep(1)
            record["status"] = "completed"
        except asyncio.CancelledError:
            record["status"] = "cancelled"
            raise
        except Exception as exc:
            record.update(status="failed", error=str(exc)[:300])
            log.exception("RoleManager bulk job %s failed.", record["id"])
        finally:
            record["finished_at"] = self._now_ts()
            await self._save_bulk_job(guild, record)
            self._bulk_tasks.pop(key, None)

    @rolemanager.group(name="job", aliases=["jobs"])
    @commands.admin_or_permissions(manage_roles=True)
    async def job_group(self, ctx: commands.Context) -> None:
        """Run and inspect persistent, cancellable bulk role jobs."""

    @job_group.command(name="start")
    @commands.bot_has_permissions(manage_roles=True)
    async def job_start(
        self,
        ctx: commands.Context,
        action: str,
        role: discord.Role,
        *,
        query: str,
    ) -> None:
        """Start a background `add` or `remove` job using an advanced target query."""
        action = action.lower()
        if action not in {"add", "remove"}:
            raise commands.BadArgument("Action must be `add` or `remove`.")
        self._check_role_manageable(ctx, role)
        members = await self._members_from_query(ctx.guild, query)
        if not members:
            raise commands.BadArgument("No members matched that target query.")
        job_id = secrets.token_hex(3)
        record = {
            "id": job_id,
            "action": action,
            "role_id": role.id,
            "query": query,
            "actor_id": ctx.author.id,
            "status": "running",
            "total": len(members),
            "processed": 0,
            "completed": 0,
            "skipped": 0,
            "failed": 0,
            "created_at": self._now_ts(),
        }
        await self._save_bulk_job(ctx.guild, record)
        key = f"{ctx.guild.id}:{job_id}"
        self._bulk_tasks[key] = asyncio.create_task(self._run_bulk_job(ctx.guild, record, [member.id for member in members]))
        await ctx.send(f"Started job `{job_id}` for {len(members):,} member(s).")

    @job_group.command(name="list", aliases=["status"])
    async def job_list(self, ctx: commands.Context, job_id: str | None = None) -> None:
        """Show recent jobs or one job's detailed status."""
        jobs = await self.config.guild(ctx.guild).bulk_jobs()
        if job_id:
            jobs = [item for item in jobs if item.get("id") == job_id]
        if not jobs:
            await ctx.send("No matching bulk jobs were found.")
            return
        lines = [
            f"`{item.get('id')}` {item.get('status')} {item.get('action')} role "
            f"`{item.get('role_id')}` — {item.get('processed', 0)}/{item.get('total', 0)} "
            f"processed, {item.get('failed', 0)} failed"
            for item in reversed(jobs[-10:])
        ]
        await ctx.send("\n".join(lines))

    @job_group.command(name="cancel")
    async def job_cancel(self, ctx: commands.Context, job_id: str) -> None:
        """Cancel a running bulk job."""
        task = self._bulk_tasks.get(f"{ctx.guild.id}:{job_id}")
        if task is None or task.done():
            await ctx.send("That job is not running on this bot process.")
            return
        task.cancel()
        await ctx.send(f"Cancellation requested for job `{job_id}`.")

    @job_group.command(name="export")
    async def job_export(self, ctx: commands.Context) -> None:
        """Export recent bulk-job records as JSON."""
        content = json.dumps(await self.config.guild(ctx.guild).bulk_jobs(), indent=2, default=str).encode()
        await ctx.send(file=discord.File(io.BytesIO(content), filename="rolemanager-jobs.json"))

    @rolemanager.group(name="audit")
    @commands.admin_or_permissions(manage_roles=True)
    async def audit_group(self, ctx: commands.Context) -> None:
        """Configure and inspect RoleManager's local role-change journal."""

    @audit_group.command(name="channel")
    async def audit_channel(
        self,
        ctx: commands.Context,
        channel: discord.TextChannel | None = None,
    ) -> None:
        """Set the audit delivery channel, or omit it to disable delivery."""
        await self.config.guild(ctx.guild).audit_channel_id.set(channel.id if channel else None)
        await ctx.send(f"Audit delivery channel: {channel.mention if channel else 'disabled'}.")

    @audit_group.command(name="list", aliases=["recent"])
    async def audit_list(self, ctx: commands.Context, limit: int = 15) -> None:
        """Show recent RoleManager audit records."""
        history = await self.config.guild(ctx.guild).audit_history()
        limit = max(1, min(limit, 50))
        if not history:
            await ctx.send("The RoleManager audit journal is empty.")
            return
        lines = [
            f"<t:{int(item.get('timestamp', 0))}:R> `{item.get('action')}` "
            f"member `{item.get('member_id') or '-'}` roles "
            f"`{','.join(str(role_id) for role_id in item.get('role_ids', [])) or '-'}` "
            f"via {item.get('source')}"
            for item in reversed(history[-limit:])
        ]
        for page in pagify("\n".join(lines), page_length=1900):
            await ctx.send(page)

    @audit_group.command(name="export")
    async def audit_export(self, ctx: commands.Context) -> None:
        """Export the full bounded role-change journal."""
        content = json.dumps(await self.config.guild(ctx.guild).audit_history(), indent=2, default=str).encode()
        await ctx.send(file=discord.File(io.BytesIO(content), filename="rolemanager-audit.json"))

    @audit_group.command(name="clear")
    async def audit_clear(self, ctx: commands.Context, confirmation: str = "") -> None:
        """Clear the journal; the final argument must be CONFIRM."""
        if confirmation.upper() != "CONFIRM":
            await ctx.send("Run this command again with `CONFIRM` to clear the journal.")
            return
        await self.config.guild(ctx.guild).audit_history.clear()
        await ctx.send("RoleManager audit journal cleared.")

    @rolemanager.group(name="autorole", invoke_without_command=True)
    @commands.admin_or_permissions(manage_roles=True)
    @commands.bot_has_permissions(manage_roles=True)
    async def autorole_group(
        self,
        ctx: commands.Context,
        enabled: bool | None = None,
        *,
        role: discord.Role | None = None,
    ) -> None:
        """Configure roles automatically given to joining members."""
        if role is None:
            await ctx.send_help(ctx.command)
            return
        self._check_role_manageable(ctx, role)
        if enabled is None:
            all_roles = (await self.config.guild(ctx.guild).auto_roles()).get("all", [])
            enabled = role.id not in all_roles
        async with self.config.guild(ctx.guild).auto_roles() as settings:
            roles = settings.setdefault("all", [])
            if enabled and role.id not in roles:
                roles.append(role.id)
            if not enabled and role.id in roles:
                roles.remove(role.id)
            settings["enabled"] = bool(settings.get("enabled") or enabled)
        await ctx.send(
            f"{role.mention} is {'now' if enabled else 'no longer'} an autorole.",
            allowed_mentions=discord.AllowedMentions.none(),
        )

    @autorole_group.command(name="toggle")
    async def autorole_toggle(
        self,
        ctx: commands.Context,
        enabled: bool | None = None,
    ) -> None:
        """Enable, disable, or toggle autoroles."""
        settings = await self.config.guild(ctx.guild).auto_roles()
        if enabled is None:
            enabled = not bool(settings.get("enabled"))
        settings["enabled"] = bool(enabled)
        await self.config.guild(ctx.guild).auto_roles.set(settings)
        await ctx.send(f"Autoroles are now {'enabled' if enabled else 'disabled'}.")

    @autorole_group.command(name="add")
    async def autorole_add(
        self,
        ctx: commands.Context,
        role: discord.Role,
        target: str = "all",
    ) -> None:
        """Add an autorole for all members, humans, or bots."""
        self._check_role_manageable(ctx, role)
        target = target.lower()
        if target not in {"all", "humans", "bots"}:
            raise commands.BadArgument("Target must be `all`, `humans`, or `bots`.")
        async with self.config.guild(ctx.guild).auto_roles() as settings:
            role_ids = settings.setdefault(target, [])
            if role.id not in role_ids:
                role_ids.append(role.id)
            settings["enabled"] = True
        await ctx.send(
            f"{role.mention} will be assigned to new {target} members.",
            allowed_mentions=discord.AllowedMentions.none(),
        )

    @autorole_group.command(name="remove")
    async def autorole_remove(
        self,
        ctx: commands.Context,
        role: discord.Role,
        target: str = "all",
    ) -> None:
        """Remove an autorole target."""
        target = target.lower()
        if target not in {"all", "humans", "bots"}:
            raise commands.BadArgument("Target must be `all`, `humans`, or `bots`.")
        async with self.config.guild(ctx.guild).auto_roles() as settings:
            role_ids = settings.setdefault(target, [])
            if role.id in role_ids:
                role_ids.remove(role.id)
        await ctx.send(
            f"{role.mention} was removed from the {target} autorole list.",
            allowed_mentions=discord.AllowedMentions.none(),
        )

    @autorole_group.command(name="list")
    async def autorole_list(self, ctx: commands.Context) -> None:
        """Show autorole settings."""
        settings = await self.config.guild(ctx.guild).auto_roles()
        lines = [
            f"Enabled: {bool(settings.get('enabled'))}",
            f"Delay: {int(settings.get('delay_seconds', 0))} seconds",
            f"Minimum account age: {int(settings.get('minimum_account_age_hours', 0))} hours",
            f"Retries: {int(settings.get('retries', 3))}",
        ]
        for target in ("all", "humans", "bots"):
            roles = [role for role_id in settings.get(target, []) if (role := ctx.guild.get_role(int(role_id))) is not None]
            lines.append(
                f"{target.title()} ({'enabled' if settings.get(f'{target}_enabled', True) else 'disabled'}): "
                f"{self._role_list(roles)}",
            )
        await ctx.send(
            "\n".join(lines),
            allowed_mentions=discord.AllowedMentions.none(),
        )

    @autorole_group.command(name="clear")
    async def autorole_clear(self, ctx: commands.Context) -> None:
        """Clear all autoroles for this server."""
        await self.config.guild(ctx.guild).auto_roles.set(
            {
                "enabled": False,
                "all": [],
                "humans": [],
                "bots": [],
                "all_enabled": True,
                "humans_enabled": True,
                "bots_enabled": True,
                "delay_seconds": 0,
                "minimum_account_age_hours": 0,
                "retries": 3,
            },
        )
        await ctx.send("Autoroles have been cleared and disabled.")

    @autorole_group.command(name="settings", aliases=["policy"])
    async def autorole_settings(
        self,
        ctx: commands.Context,
        delay_seconds: int = 0,
        minimum_account_age_hours: int = 0,
        retries: int = 3,
        all_enabled: bool = True,
        humans_enabled: bool = True,
        bots_enabled: bool = True,
    ) -> None:
        """Set delay, account-age safety, retries, and independent list toggles."""
        async with self.config.guild(ctx.guild).auto_roles() as settings:
            settings["delay_seconds"] = max(0, min(delay_seconds, 86_400))
            settings["minimum_account_age_hours"] = max(0, min(minimum_account_age_hours, 876_000))
            settings["retries"] = max(1, min(retries, 10))
            settings["all_enabled"] = all_enabled
            settings["humans_enabled"] = humans_enabled
            settings["bots_enabled"] = bots_enabled
        await ctx.send("Autorole delivery settings updated.")

    @rolemanager.command(name="auto")
    @commands.admin_or_permissions(manage_roles=True)
    @commands.bot_has_permissions(manage_roles=True)
    async def legacy_auto(
        self,
        ctx: commands.Context,
        enabled: bool | None = None,
        *,
        role: discord.Role,
    ) -> None:
        """Trusty-style alias for toggling a role as an all-member autorole."""
        self._check_role_manageable(ctx, role)
        if enabled is None:
            all_roles = (await self.config.guild(ctx.guild).auto_roles()).get("all", [])
            enabled = role.id not in all_roles
        async with self.config.guild(ctx.guild).auto_roles() as settings:
            roles = settings.setdefault("all", [])
            if enabled and role.id not in roles:
                roles.append(role.id)
            if not enabled and role.id in roles:
                roles.remove(role.id)
            settings["enabled"] = bool(settings.get("enabled") or enabled)
        await ctx.send(
            f"{role.mention} is {'now' if enabled else 'no longer'} an autorole.",
            allowed_mentions=discord.AllowedMentions.none(),
        )

    @rolemanager.group(name="sticky", invoke_without_command=True)
    @commands.admin_or_permissions(manage_roles=True)
    @commands.bot_has_permissions(manage_roles=True)
    async def sticky_group(
        self,
        ctx: commands.Context,
        enabled: bool | None = None,
        *,
        role: discord.Role | None = None,
    ) -> None:
        """Configure sticky roles that return when members rejoin."""
        if role is None:
            await ctx.send_help(ctx.command)
            return
        self._check_role_manageable(ctx, role)
        current = await self.config.role(role).sticky()
        if enabled is None:
            enabled = not current
        await self.config.role(role).sticky.set(bool(enabled))
        await ctx.send(
            f"{role.mention} is {'now' if enabled else 'no longer'} a sticky role.",
            allowed_mentions=discord.AllowedMentions.none(),
        )

    @sticky_group.command(name="set")
    async def sticky_set(
        self,
        ctx: commands.Context,
        role: discord.Role,
        enabled: bool | None = None,
    ) -> None:
        """Mark or unmark a role as sticky for future rejoins."""
        self._check_role_manageable(ctx, role)
        current = await self.config.role(role).sticky()
        if enabled is None:
            enabled = not current
        await self.config.role(role).sticky.set(bool(enabled))
        await ctx.send(
            f"{role.mention} is {'now' if enabled else 'no longer'} a sticky role.",
            allowed_mentions=discord.AllowedMentions.none(),
        )

    @sticky_group.command(name="add", aliases=["force"])
    async def sticky_add(
        self,
        ctx: commands.Context,
        member: discord.Member,
        *,
        role: discord.Role,
    ) -> None:
        """Force a sticky role onto a member."""
        self._check_role_manageable(ctx, role)
        async with self.config.member(member).sticky_roles() as sticky_roles:
            if role.id not in sticky_roles:
                sticky_roles.append(role.id)
        if role not in member.roles:
            await self._give_roles(
                member,
                [role],
                get_audit_reason(ctx.author, "Sticky role added."),
                check_required=False,
                check_exclusive=False,
                check_inclusive=False,
                check_cost=False,
            )
        await ctx.send(
            f"{role.mention} will be restored for {member.mention} when they rejoin.",
            allowed_mentions=discord.AllowedMentions(users=False, roles=False),
        )

    @sticky_group.command(name="remove", aliases=["forget"])
    async def sticky_remove(
        self,
        ctx: commands.Context,
        member: discord.Member,
        *,
        role: discord.Role,
    ) -> None:
        """Remove a forced sticky role from a member."""
        self._check_role_manageable(ctx, role)
        async with self.config.member(member).sticky_roles() as sticky_roles:
            if role.id in sticky_roles:
                sticky_roles.remove(role.id)
        if role in member.roles:
            await self._remove_roles(
                member,
                [role],
                get_audit_reason(ctx.author, "Sticky role removed."),
                check_inclusive=False,
            )
        await ctx.send(
            f"{role.mention} is no longer forced sticky for {member.mention}.",
            allowed_mentions=discord.AllowedMentions(users=False, roles=False),
        )

    @sticky_group.command(name="forgetid")
    async def sticky_forget_id(
        self,
        ctx: commands.Context,
        user_id: int,
        *,
        role: discord.Role,
    ) -> None:
        """Forget a sticky role for a user ID that is not currently in the server."""
        async with self.config.member_from_ids(
            ctx.guild.id,
            user_id,
        ).sticky_roles() as roles:
            if role.id in roles:
                roles.remove(role.id)
        await ctx.send(f"Forgot sticky {role.name} for user ID {user_id}.")

    @sticky_group.command(name="list")
    async def sticky_list(self, ctx: commands.Context) -> None:
        """List roles that are configured as sticky for future leaves."""
        roles = []
        for role in sorted(
            ctx.guild.roles,
            key=lambda item: item.position,
            reverse=True,
        ):
            if role.is_default():
                continue
            if await self.config.role(role).sticky():
                roles.append(role)
        if not roles:
            await ctx.send("No roles are configured as sticky.")
            return
        await ctx.send(
            "Sticky roles: " + self._role_list(roles),
            allowed_mentions=discord.AllowedMentions.none(),
        )

    @rolemanager.group(name="temp", aliases=["temporary"])
    @commands.bot_has_permissions(manage_roles=True)
    async def temp_group(self, ctx: commands.Context) -> None:
        """Configure and inspect temporary roles."""

    @temp_group.command(name="give")
    @commands.admin_or_permissions(manage_roles=True)
    async def temp_give(
        self,
        ctx: commands.Context,
        member: discord.Member,
        role: discord.Role,
        *,
        specification: str,
    ) -> None:
        """Give an expiring role. Format: `duration | optional reason | notify true/false`."""
        self._check_role_manageable(ctx, role)
        parts = [part.strip() for part in specification.split("|", 2)]
        seconds = self._parse_duration(parts[0])
        reason = parts[1] if len(parts) > 1 and parts[1] else "Temporary role granted by staff."
        notify_member = len(parts) > 2 and parts[2].casefold() in {
            "1",
            "true",
            "yes",
            "on",
            "notify",
        }
        responses, added, _removed = await self._give_roles(
            member,
            [role],
            get_audit_reason(ctx.author, reason[:400]),
            check_cost=False,
            duration_overrides={role.id: seconds},
        )
        if responses and role not in added:
            await ctx.send(self._response_text(responses))
            return
        async with self.config.guild(ctx.guild).temporary_roles() as records:
            for item in reversed(records):
                if int(item.get("member_id", 0)) == member.id and int(item.get("role_id", 0)) == role.id:
                    item.update(
                        granted_by=ctx.author.id,
                        reason=reason[:500],
                        notify_channel_id=ctx.channel.id,
                        notify_member=notify_member,
                    )
                    break
        await ctx.send(
            f"{role.mention} added to {member.mention} for {self._format_duration(seconds)}.",
            allowed_mentions=discord.AllowedMentions(users=False, roles=False),
        )

    @temp_group.command(name="extend")
    @commands.admin_or_permissions(manage_roles=True)
    async def temp_extend(
        self,
        ctx: commands.Context,
        member: discord.Member,
        role: discord.Role,
        *,
        duration: str,
    ) -> None:
        """Extend a pending temporary role from now."""
        seconds = self._parse_duration(duration)
        found = False
        async with self.config.guild(ctx.guild).temporary_roles() as records:
            for item in records:
                if int(item.get("member_id", 0)) == member.id and int(item.get("role_id", 0)) == role.id:
                    item["expires_at"] = self._now_ts() + seconds
                    item["extended_by"] = ctx.author.id
                    found = True
        if not found:
            await ctx.send("That member and role do not have a pending temporary assignment.")
            return
        await ctx.send(f"Extended the assignment by {self._format_duration(seconds)} from now.")

    @temp_group.command(name="revoke")
    @commands.admin_or_permissions(manage_roles=True)
    async def temp_revoke(
        self,
        ctx: commands.Context,
        member: discord.Member,
        role: discord.Role,
        *,
        reason: str = "Temporary role revoked by staff.",
    ) -> None:
        """Remove a temporary role immediately and clear its schedule."""
        self._check_role_manageable(ctx, role)
        responses, removed = await self._remove_roles(member, [role], get_audit_reason(ctx.author, reason[:400]))
        await self._clear_temp_role(member, role)
        if responses and not removed:
            await ctx.send(self._response_text(responses))
            return
        await ctx.send(f"Revoked {role.mention} from {member.mention}.")

    @temp_group.command(name="setduration", aliases=["duration"])
    @commands.admin_or_permissions(manage_roles=True)
    async def temp_setduration(
        self,
        ctx: commands.Context,
        role: discord.Role,
        *,
        duration: str | None = None,
    ) -> None:
        """Set or clear the default temp duration for assignments made by this cog."""
        self._check_role_manageable(ctx, role)
        if duration is None:
            await self.config.role(role).temp_duration.clear()
            await ctx.send(
                f"{role.mention} no longer has a default temporary duration.",
                allowed_mentions=discord.AllowedMentions.none(),
            )
            return
        seconds = self._parse_duration(duration)
        await self.config.role(role).temp_duration.set(seconds)
        await ctx.send(
            f"{role.mention} will expire after {self._format_duration(seconds)} when assigned by rolemanager.",
            allowed_mentions=discord.AllowedMentions.none(),
        )

    @temp_group.command(name="list")
    async def temp_list(
        self,
        ctx: commands.Context,
        *,
        member: discord.Member | None = None,
    ) -> None:
        """List pending temporary roles."""
        pending = await self.config.guild(ctx.guild).temporary_roles()
        show_all = member is None and ctx.channel.permissions_for(ctx.author).manage_roles
        if member is None:
            member = ctx.author if isinstance(ctx.author, discord.Member) else None

        lines: list[str] = []
        for item in pending:
            item_member = ctx.guild.get_member(int(item.get("member_id", 0)))
            role = ctx.guild.get_role(int(item.get("role_id", 0)))
            if item_member is None or role is None:
                continue
            if not show_all and member is not None and item_member.id != member.id:
                continue
            lines.append(
                f"{item_member.mention} - {role.mention} expires {self._format_ts(item.get('expires_at'))}",
            )

        if not lines:
            await ctx.send("No pending temporary roles found.")
            return
        for page in pagify("\n".join(lines), page_length=1900):
            await ctx.send(page, allowed_mentions=discord.AllowedMentions.none())

    @temp_group.command(name="clear")
    @commands.admin_or_permissions(manage_roles=True)
    async def temp_clear(
        self,
        ctx: commands.Context,
        member: discord.Member,
        *,
        role: discord.Role,
    ) -> None:
        """Stop tracking a pending temporary role without removing the role."""
        await self._clear_temp_role(member, role)
        await ctx.send(
            f"Cleared pending temporary tracking for {role.mention} on {member.mention}.",
            allowed_mentions=discord.AllowedMentions(users=False, roles=False),
        )

    @rolemanager.group(
        name="reactrole",
        aliases=["rr", "reaction", "react", "reactions"],
    )
    @commands.admin_or_permissions(manage_roles=True)
    async def reactrole_group(self, ctx: commands.Context) -> None:
        """Configure reaction roles."""

    @reactrole_group.command(name="bind")
    @commands.bot_has_permissions(
        manage_roles=True,
        add_reactions=True,
        read_message_history=True,
    )
    async def reactrole_bind(
        self,
        ctx: commands.Context,
        message: discord.Message,
        emoji: str,
        role: discord.Role,
        remove_on_unreact: bool = True,
    ) -> None:
        """Bind an emoji on an existing message to a role."""
        self._check_role_manageable(ctx, role)
        await self.config.role(role).self_assignable.set(True)
        if remove_on_unreact:
            await self.config.role(role).self_removable.set(True)
        emoji_key = self._emoji_key(emoji)
        async with self.config.guild(ctx.guild).react_roles() as react_roles:
            message_data = react_roles.setdefault(
                str(message.id),
                {"channel_id": message.channel.id, "binds": {}},
            )
            message_data["channel_id"] = message.channel.id
            message_data.setdefault("binds", {})[emoji_key] = {
                "role_id": role.id,
                "remove_on_unreact": bool(remove_on_unreact),
                "emoji": str(emoji),
            }
        self._reaction_message_cache.add(message.id)
        await message.add_reaction(emoji)
        await ctx.send(
            f"Bound {emoji} to {role.mention} on {message.jump_url}.",
            allowed_mentions=discord.AllowedMentions.none(),
        )

    @reactrole_group.command(name="create")
    @commands.bot_has_permissions(
        manage_roles=True,
        add_reactions=True,
        send_messages=True,
        embed_links=True,
    )
    async def reactrole_create(
        self,
        ctx: commands.Context,
        channel: discord.TextChannel | None = None,
        *,
        spec: str,
    ) -> None:
        """Create a reaction-role panel.

        Format: `Title | emoji;role | emoji;role`
        """
        channel = channel or ctx.channel
        parts = [part.strip() for part in spec.split("|") if part.strip()]
        if len(parts) < 2:
            raise commands.BadArgument(
                "Use `Title | emoji;role | emoji;role`, for example `Pings | <:game:123456789012345678>;Gamer`.",
            )
        title = parts[0][:256]
        bindings: list[tuple[str, discord.Role]] = []
        for part in parts[1:]:
            if ";" not in part:
                raise commands.BadArgument(
                    f"`{part}` is missing `;` between emoji and role.",
                )
            emoji, role_text = [piece.strip() for piece in part.split(";", 1)]
            role = self._find_role(ctx.guild, role_text)
            if role is None:
                raise commands.BadArgument(
                    f"I could not find a role named `{role_text}`.",
                )
            self._check_role_manageable(ctx, role)
            await self.config.role(role).self_assignable.set(True)
            await self.config.role(role).self_removable.set(True)
            bindings.append((emoji, role))

        description = "\n".join(f"{emoji} - {role.mention}" for emoji, role in bindings)
        embed = discord.Embed(
            title=title,
            description=description,
            color=await ctx.embed_color(),
        )
        panel = await channel.send(
            embed=embed,
            allowed_mentions=discord.AllowedMentions.none(),
        )
        react_roles: dict[str, Any] = {
            "channel_id": channel.id,
            "binds": {},
        }
        for emoji, role in bindings:
            await panel.add_reaction(emoji)
            react_roles["binds"][self._emoji_key(emoji)] = {
                "role_id": role.id,
                "remove_on_unreact": True,
                "emoji": str(emoji),
            }
        async with self.config.guild(ctx.guild).react_roles() as configured:
            configured[str(panel.id)] = react_roles
        self._reaction_message_cache.add(panel.id)
        await ctx.send(f"Reaction-role panel created: {panel.jump_url}")

    @reactrole_group.command(name="unbind", aliases=["remove"])
    async def reactrole_unbind(
        self,
        ctx: commands.Context,
        message: discord.Message,
        emoji: str,
    ) -> None:
        """Remove one reaction-role binding from a message."""
        emoji_key = self._emoji_key(emoji)
        async with self.config.guild(ctx.guild).react_roles() as react_roles:
            message_data = react_roles.get(str(message.id))
            if not message_data or emoji_key not in message_data.get("binds", {}):
                await ctx.send("That emoji is not bound on that message.")
                return
            del message_data["binds"][emoji_key]
            if not message_data["binds"]:
                del react_roles[str(message.id)]
                self._reaction_message_cache.discard(message.id)
        await ctx.send(f"Removed the {emoji} reaction-role binding.")

    @reactrole_group.command(name="clear")
    async def reactrole_clear(
        self,
        ctx: commands.Context,
        message: discord.Message,
    ) -> None:
        """Remove every reaction-role binding from a message."""
        async with self.config.guild(ctx.guild).react_roles() as react_roles:
            if str(message.id) not in react_roles:
                await ctx.send("That message does not have reaction roles configured.")
                return
            del react_roles[str(message.id)]
        self._reaction_message_cache.discard(message.id)
        await ctx.send("Reaction-role bindings cleared for that message.")

    @reactrole_group.command(name="list")
    async def reactrole_list(self, ctx: commands.Context) -> None:
        """List reaction roles for this server."""
        react_roles = await self.config.guild(ctx.guild).react_roles()
        if not react_roles:
            await ctx.send("No reaction roles are configured.")
            return
        lines: list[str] = []
        for message_id, data in react_roles.items():
            channel = ctx.guild.get_channel_or_thread(int(data.get("channel_id", 0)))
            if channel is None:
                continue
            jump_url = f"https://discord.com/channels/{ctx.guild.id}/{channel.id}/{message_id}"
            lines.append(f"[Message {message_id}]({jump_url}) in {channel.mention}")
            for bind in data.get("binds", {}).values():
                role = ctx.guild.get_role(int(bind.get("role_id", 0)))
                if role is not None:
                    lines.append(f"  {bind.get('emoji', '?')} - {role.mention}")
        if not lines:
            await ctx.send("No valid reaction roles are configured.")
            return
        for page in pagify("\n".join(lines), page_length=1900):
            await ctx.send(page, allowed_mentions=discord.AllowedMentions.none())

    @reactrole_group.command(name="cleanup")
    @commands.bot_has_permissions(read_message_history=True)
    async def reactrole_cleanup(self, ctx: commands.Context) -> None:
        """Remove stale reaction-role records."""
        removed = 0
        async with self.config.guild(ctx.guild).react_roles() as react_roles:
            for message_id, data in list(react_roles.items()):
                channel = ctx.guild.get_channel_or_thread(int(data.get("channel_id", 0)))
                if not isinstance(channel, (discord.TextChannel, discord.Thread)):
                    del react_roles[message_id]
                    self._reaction_message_cache.discard(int(message_id))
                    removed += 1
                    continue
                try:
                    await channel.fetch_message(int(message_id))
                except (discord.NotFound, discord.HTTPException):
                    del react_roles[message_id]
                    self._reaction_message_cache.discard(int(message_id))
                    removed += 1
                    continue
                for emoji_key, bind in list(data.get("binds", {}).items()):
                    if ctx.guild.get_role(int(bind.get("role_id", 0))) is None:
                        del data["binds"][emoji_key]
                        removed += 1
                if not data.get("binds"):
                    del react_roles[message_id]
                    self._reaction_message_cache.discard(int(message_id))
        await ctx.send(f"Removed {removed:,} stale reaction-role record(s).")

    @reactrole_group.command(name="refresh")
    @commands.bot_has_permissions(add_reactions=True, read_message_history=True)
    async def reactrole_refresh(
        self,
        ctx: commands.Context,
        message: discord.Message,
    ) -> None:
        """Re-add configured bot reactions for one reaction-role message."""
        react_roles = await self.config.guild(ctx.guild).react_roles()
        data = react_roles.get(str(message.id))
        if not data:
            await ctx.send("That message has no configured reaction roles.")
            return
        for bind in data.get("binds", {}).values():
            with contextlib.suppress(discord.HTTPException):
                await message.add_reaction(bind.get("emoji"))
        await ctx.send("Reaction-role reactions refreshed.")

    @reactrole_group.command(name="reset")
    @commands.bot_has_permissions(manage_messages=True, add_reactions=True, read_message_history=True)
    async def reactrole_reset(
        self,
        ctx: commands.Context,
        message: discord.Message,
        confirmation: str = "",
    ) -> None:
        """Clear and rebuild the reactions on one configured panel."""
        if confirmation.upper() != "CONFIRM":
            await ctx.send("Run this command again with `CONFIRM` to rebuild every reaction.")
            return
        records = await self.config.guild(ctx.guild).react_roles()
        data = records.get(str(message.id))
        if not data:
            await ctx.send("That message has no configured reaction roles.")
            return
        await message.clear_reactions()
        failed = 0
        for bind in data.get("binds", {}).values():
            try:
                await message.add_reaction(bind.get("emoji"))
            except (discord.HTTPException, TypeError):
                failed += 1
        await ctx.send(f"Rebuilt the reaction panel. Failed emoji: {failed}.")

    @reactrole_group.command(name="sync")
    @commands.bot_has_permissions(manage_roles=True, read_message_history=True)
    async def reactrole_sync(
        self,
        ctx: commands.Context,
        mode: str = "add",
        confirmation: str = "",
    ) -> None:
        """Reconcile configured roles with live reactions (`add` or `sync`)."""
        mode = mode.lower()
        if mode not in {"add", "sync"}:
            raise commands.BadArgument("Mode must be `add` or `sync`.")
        if mode == "sync" and confirmation.upper() != "CONFIRM":
            await ctx.send("Full sync can remove roles. Run it again as `sync CONFIRM`.")
            return
        stats = await self._reconcile_reaction_roles(ctx.guild, remove_missing=mode == "sync")
        await ctx.send(
            f"Reconciled {stats['messages']} message(s): {stats['added']} added, "
            f"{stats['removed']} removed, {stats['missing']} unavailable.",
        )

    @rolemanager.group(name="button", aliases=["buttons"])
    @commands.admin_or_permissions(manage_roles=True)
    @commands.bot_has_permissions(manage_roles=True)
    async def button_group(self, ctx: commands.Context) -> None:
        """Configure persistent role buttons."""

    @button_group.command(name="create")
    async def button_create(
        self,
        ctx: commands.Context,
        name: str,
        role: discord.Role,
        style: str = "secondary",
        emoji: str | None = None,
        *,
        label: str | None = None,
    ) -> None:
        """Create or update a saved role button."""
        self._check_role_manageable(ctx, role)
        await self.config.role(role).self_assignable.set(True)
        await self.config.role(role).self_removable.set(True)
        clean_name = name.lower().strip()
        if not clean_name or " " in clean_name:
            raise commands.BadArgument("Button name cannot be empty or contain spaces.")
        button_data = {
            "role_id": role.id,
            "label": label or f"@{role.name}",
            "emoji": emoji,
            "style": self._button_style_value(style),
            "messages": [],
        }
        old_role_id = None
        async with self.config.guild(ctx.guild).buttons() as buttons:
            old = buttons.get(clean_name)
            if old:
                button_data["messages"] = list(old.get("messages", []))
                old_role_id = int(old.get("role_id", 0)) or None
                policy = normalize_component_policy(old)
                for key in (
                    "mode",
                    "required_role_ids",
                    "blocked_role_ids",
                    "cooldown_seconds",
                    "max_holders",
                    "temp_seconds",
                ):
                    button_data[key] = policy[key]
            buttons[clean_name] = button_data
        if old_role_id is not None and old_role_id != role.id:
            async with self.config.role_from_id(old_role_id).buttons() as role_buttons:
                if clean_name in role_buttons:
                    role_buttons.remove(clean_name)
        async with self.config.role(role).buttons() as role_buttons:
            if clean_name not in role_buttons:
                role_buttons.append(clean_name)
        await self._load_component_views()
        preview = RoleManagerView(self, timeout=120)
        button = RoleButton(
            name=clean_name,
            role_id=role.id,
            label=button_data["label"],
            emoji=emoji,
            style=button_data["style"],
            guild_id=ctx.guild.id,
        )
        button.refresh_label(ctx.guild)
        preview.add_item(button)
        await ctx.send("Button saved. Preview:", view=preview)

    def _component_policy_role_ids(self, guild: discord.Guild, value: str) -> list[int]:
        if not value or value.strip() in {"-", "none"}:
            return []
        role_ids: list[int] = []
        for role_text in self._parse_name_list(value):
            role = self._find_role(guild, role_text)
            if role is None:
                raise commands.BadArgument(f"I could not find role `{role_text}`.")
            if role.id not in role_ids:
                role_ids.append(role.id)
        return role_ids

    @button_group.command(name="policy")
    async def button_policy(
        self,
        ctx: commands.Context,
        name: str,
        mode: str = "toggle",
        cooldown_seconds: int = 0,
        max_holders: int = 0,
        temp_seconds: int = 0,
        required_roles: str = "-",
        *,
        blocked_roles: str = "-",
    ) -> None:
        """Set button mode, locks, cooldown, capacity, and temporary duration."""
        clean_name = name.lower().strip()
        async with self.config.guild(ctx.guild).buttons() as buttons:
            if clean_name not in buttons:
                raise commands.BadArgument(f"Button `{clean_name}` does not exist.")
            data = normalize_component_policy(
                {
                    **buttons[clean_name],
                    "mode": mode,
                    "cooldown_seconds": cooldown_seconds,
                    "max_holders": max_holders,
                    "temp_seconds": temp_seconds,
                    "required_role_ids": self._component_policy_role_ids(ctx.guild, required_roles),
                    "blocked_role_ids": self._component_policy_role_ids(ctx.guild, blocked_roles),
                },
            )
            if data["mode"] != mode.lower():
                raise commands.BadArgument("Button mode must be `toggle`, `add`, or `remove`.")
            buttons[clean_name] = data
        await self._load_component_views()
        await ctx.send(f"Updated policy for button `{clean_name}`.")

    @button_group.command(name="delete", aliases=["remove", "del"])
    async def button_delete(self, ctx: commands.Context, *, name: str) -> None:
        """Delete a saved role button."""
        clean_name = name.lower().strip()
        async with self.config.guild(ctx.guild).buttons() as buttons:
            data = buttons.pop(clean_name, None)
        if not data:
            await ctx.send("That button does not exist.")
            return
        async with self.config.role_from_id(
            int(data["role_id"]),
        ).buttons() as role_buttons:
            if clean_name in role_buttons:
                role_buttons.remove(clean_name)
        await self._load_component_views()
        await ctx.send(f"Deleted button `{clean_name}`.")

    @button_group.command(name="list", aliases=["view"])
    async def button_list(self, ctx: commands.Context) -> None:
        """List saved role buttons."""
        buttons = await self.config.guild(ctx.guild).buttons()
        if not buttons:
            await ctx.send("No role buttons are configured.")
            return
        lines = []
        for name, data in sorted(buttons.items()):
            role = ctx.guild.get_role(int(data.get("role_id", 0)))
            policy = normalize_component_policy(data)
            lines.append(
                f"`{name}` -> {role.mention if role else 'missing role'} "
                f"mode: {policy['mode']} messages: {len(data.get('messages', [])):,}",
            )
        for page in pagify("\n".join(lines), page_length=1900):
            await ctx.send(page, allowed_mentions=discord.AllowedMentions.none())

    @button_group.command(name="cleanup")
    @commands.bot_has_permissions(read_message_history=True)
    async def button_cleanup(self, ctx: commands.Context) -> None:
        """Remove missing message references from buttons."""
        removed = await self._cleanup_component_messages(ctx.guild, "buttons")
        await ctx.send(f"Removed {removed:,} stale button message reference(s).")

    @rolemanager.group(name="select", aliases=["selects"])
    @commands.admin_or_permissions(manage_roles=True)
    @commands.bot_has_permissions(manage_roles=True)
    async def select_group(self, ctx: commands.Context) -> None:
        """Configure persistent role select menus."""

    @select_group.group(name="option", aliases=["options"])
    async def select_option_group(self, ctx: commands.Context) -> None:
        """Configure saved select options."""

    @select_option_group.command(name="create", aliases=["add"])
    async def select_option_create(
        self,
        ctx: commands.Context,
        name: str,
        role: discord.Role,
        *,
        spec: str = "",
    ) -> None:
        """Create a select option. Spec format: `emoji | label | description`."""
        self._check_role_manageable(ctx, role)
        await self.config.role(role).self_assignable.set(True)
        await self.config.role(role).self_removable.set(True)
        clean_name = name.lower().strip()
        if not clean_name or " " in clean_name:
            raise commands.BadArgument("Option name cannot be empty or contain spaces.")
        parts = [part.strip() for part in spec.split("|")]
        emoji = parts[0] if parts and parts[0] else None
        label = parts[1] if len(parts) > 1 and parts[1] else f"@{role.name}"
        description = parts[2] if len(parts) > 2 and parts[2] else ""
        option_data = {
            "role_id": role.id,
            "emoji": emoji,
            "label": label[:100],
            "description": description[:100],
        }
        old_role_id = None
        async with self.config.guild(ctx.guild).select_options() as options:
            old = options.get(clean_name)
            if old:
                old_role_id = int(old.get("role_id", 0)) or None
            options[clean_name] = option_data
        if old_role_id is not None and old_role_id != role.id:
            async with self.config.role_from_id(
                old_role_id,
            ).select_options() as role_options:
                if clean_name in role_options:
                    role_options.remove(clean_name)
        async with self.config.role(role).select_options() as role_options:
            if clean_name not in role_options:
                role_options.append(clean_name)
        await self._load_component_views()
        await ctx.send(f"Saved select option `{clean_name}` for {role.mention}.")

    @select_option_group.command(name="delete", aliases=["remove", "del"])
    async def select_option_delete(self, ctx: commands.Context, *, name: str) -> None:
        """Delete a saved select option."""
        clean_name = name.lower().strip()
        async with self.config.guild(ctx.guild).select_options() as options:
            data = options.pop(clean_name, None)
        if not data:
            await ctx.send("That select option does not exist.")
            return
        async with self.config.guild(ctx.guild).select_menus() as menus:
            for menu in menus.values():
                if clean_name in menu.get("options", []):
                    menu["options"].remove(clean_name)
        async with self.config.role_from_id(
            int(data["role_id"]),
        ).select_options() as role_options:
            if clean_name in role_options:
                role_options.remove(clean_name)
        await self._load_component_views()
        await ctx.send(f"Deleted select option `{clean_name}`.")

    @select_option_group.command(name="list", aliases=["view"])
    async def select_option_list(self, ctx: commands.Context) -> None:
        """List saved select options."""
        options = await self.config.guild(ctx.guild).select_options()
        if not options:
            await ctx.send("No select options are configured.")
            return
        lines = []
        for name, data in sorted(options.items()):
            role = ctx.guild.get_role(int(data.get("role_id", 0)))
            lines.append(f"`{name}` -> {role.mention if role else 'missing role'}")
        for page in pagify("\n".join(lines), page_length=1900):
            await ctx.send(page, allowed_mentions=discord.AllowedMentions.none())

    @select_group.command(name="create")
    async def select_create(
        self,
        ctx: commands.Context,
        name: str,
        options_csv: str,
        min_values: int = 0,
        max_values: int | None = None,
        *,
        placeholder: str = "Pick roles",
    ) -> None:
        """Create or update a select menu from comma-separated option names."""
        clean_name = name.lower().strip()
        if not clean_name or " " in clean_name:
            raise commands.BadArgument(
                "Select menu name cannot be empty or contain spaces.",
            )
        option_names = self._parse_name_list(options_csv)
        saved_options = await self.config.guild(ctx.guild).select_options()
        missing = [option for option in option_names if option not in saved_options]
        if missing:
            raise commands.BadArgument(
                f"Missing select option(s): {humanize_list(missing)}",
            )
        max_values = max_values or len(option_names)
        max_values = max(1, min(max_values, len(option_names), 25))
        min_values = max(0, min(min_values, max_values))
        menu_data = {
            "options": option_names,
            "min_values": min_values,
            "max_values": max_values,
            "placeholder": placeholder[:100],
            "messages": [],
        }
        async with self.config.guild(ctx.guild).select_menus() as menus:
            old = menus.get(clean_name)
            if old:
                menu_data["messages"] = list(old.get("messages", []))
                policy = normalize_component_policy(old, select=True)
                for key in (
                    "mode",
                    "required_role_ids",
                    "blocked_role_ids",
                    "cooldown_seconds",
                    "max_holders",
                    "temp_seconds",
                ):
                    menu_data[key] = policy[key]
            menus[clean_name] = menu_data
        await self._load_component_views()
        preview_data = await self.config.guild(ctx.guild).all()
        preview_data["select_menus"] = {
            clean_name: {**menu_data, "messages": ["preview-0"]},
        }
        preview = self._build_component_view(
            ctx.guild,
            "preview-0",
            preview_data,
            timeout=120,
        )
        await ctx.send("Select menu saved. Preview:", view=preview)

    @select_group.command(name="policy")
    async def select_policy(
        self,
        ctx: commands.Context,
        name: str,
        mode: str = "toggle",
        cooldown_seconds: int = 0,
        max_holders: int = 0,
        temp_seconds: int = 0,
        required_roles: str = "-",
        *,
        blocked_roles: str = "-",
    ) -> None:
        """Set menu mode, locks, cooldown, capacity, and temporary duration."""
        clean_name = name.lower().strip()
        async with self.config.guild(ctx.guild).select_menus() as menus:
            if clean_name not in menus:
                raise commands.BadArgument(f"Select menu `{clean_name}` does not exist.")
            data = normalize_component_policy(
                {
                    **menus[clean_name],
                    "mode": mode,
                    "cooldown_seconds": cooldown_seconds,
                    "max_holders": max_holders,
                    "temp_seconds": temp_seconds,
                    "required_role_ids": self._component_policy_role_ids(ctx.guild, required_roles),
                    "blocked_role_ids": self._component_policy_role_ids(ctx.guild, blocked_roles),
                },
                select=True,
            )
            if data["mode"] != mode.lower():
                raise commands.BadArgument(
                    "Select mode must be `toggle`, `sync`, `exclusive`, or `add`.",
                )
            menus[clean_name] = data
        await self._load_component_views()
        await ctx.send(f"Updated policy for select menu `{clean_name}`.")

    @select_group.command(name="delete", aliases=["remove", "del"])
    async def select_delete(self, ctx: commands.Context, *, name: str) -> None:
        """Delete a saved select menu."""
        clean_name = name.lower().strip()
        async with self.config.guild(ctx.guild).select_menus() as menus:
            if menus.pop(clean_name, None) is None:
                await ctx.send("That select menu does not exist.")
                return
        await self._load_component_views()
        await ctx.send(f"Deleted select menu `{clean_name}`.")

    @select_group.command(name="list", aliases=["view"])
    async def select_list(self, ctx: commands.Context) -> None:
        """List saved select menus."""
        menus = await self.config.guild(ctx.guild).select_menus()
        if not menus:
            await ctx.send("No select menus are configured.")
            return
        lines = []
        for name, data in sorted(menus.items()):
            policy = normalize_component_policy(data, select=True)
            lines.append(
                f"`{name}` mode: {policy['mode']} options: "
                f"{humanize_list(data.get('options', []))} messages: {len(data.get('messages', [])):,}",
            )
        for page in pagify("\n".join(lines), page_length=1900):
            await ctx.send(page)

    @select_group.command(name="cleanup")
    @commands.bot_has_permissions(read_message_history=True)
    async def select_cleanup(self, ctx: commands.Context) -> None:
        """Remove missing message references from select menus."""
        removed = await self._cleanup_component_messages(ctx.guild, "select_menus")
        await ctx.send(f"Removed {removed:,} stale select-menu message reference(s).")

    @rolemanager.group(name="message")
    @commands.admin_or_permissions(manage_roles=True)
    async def component_message_group(self, ctx: commands.Context) -> None:
        """Send or edit messages with saved buttons/select menus."""

    @component_message_group.command(name="send")
    @commands.bot_has_permissions(send_messages=True)
    async def component_message_send(
        self,
        ctx: commands.Context,
        channel: discord.TextChannel,
        buttons_csv: str,
        selects_csv: str = "-",
        *,
        text: str | None = None,
    ) -> None:
        """Send a message with saved buttons/selects."""
        button_names = self._parse_name_list(buttons_csv)
        select_names = self._parse_name_list(selects_csv)
        view = await self._view_for_component_names(
            ctx.guild,
            button_names,
            select_names,
        )
        message = await channel.send(content=text[:2000] if text else None, view=view)
        await self._save_component_message(
            ctx.guild,
            message,
            button_names,
            select_names,
        )
        await ctx.send(f"Role component message sent: {message.jump_url}")

    @component_message_group.command(name="edit")
    async def component_message_edit(
        self,
        ctx: commands.Context,
        message: discord.Message,
        buttons_csv: str,
        selects_csv: str = "-",
    ) -> None:
        """Edit one of the bot's messages to use saved buttons/selects."""
        if message.author.id != ctx.guild.me.id:
            raise commands.BadArgument("I can only edit my own messages.")
        button_names = self._parse_name_list(buttons_csv)
        select_names = self._parse_name_list(selects_csv)
        view = await self._view_for_component_names(
            ctx.guild,
            button_names,
            select_names,
        )
        await message.edit(view=view)
        await self._save_component_message(
            ctx.guild,
            message,
            button_names,
            select_names,
        )
        await ctx.send(f"Role component message updated: {message.jump_url}")

    async def _view_for_component_names(
        self,
        guild: discord.Guild,
        button_names: Sequence[str],
        select_names: Sequence[str],
    ) -> RoleManagerView:
        data = await self.config.guild(guild).all()
        message_key = "preview-0"
        buttons = {}
        for name in button_names:
            if name not in data.get("buttons", {}):
                raise commands.BadArgument(f"Button `{name}` does not exist.")
            buttons[name] = {**data["buttons"][name], "messages": [message_key]}
        menus = {}
        for name in select_names:
            if name not in data.get("select_menus", {}):
                raise commands.BadArgument(f"Select menu `{name}` does not exist.")
            menus[name] = {**data["select_menus"][name], "messages": [message_key]}
        data["buttons"] = buttons
        data["select_menus"] = menus
        view = self._build_component_view(guild, message_key, data)
        if view is None:
            raise commands.BadArgument(
                "No valid buttons or select menus were provided.",
            )
        return view

    async def _save_component_message(
        self,
        guild: discord.Guild,
        message: discord.Message,
        button_names: Sequence[str],
        select_names: Sequence[str],
    ) -> None:
        message_key = self._component_message_key(message)
        async with self.config.guild(guild).buttons() as buttons:
            for button in buttons.values():
                if message_key in button.get("messages", []):
                    button["messages"].remove(message_key)
            for name in button_names:
                messages = buttons[name].setdefault("messages", [])
                if message_key not in messages:
                    messages.append(message_key)
        async with self.config.guild(guild).select_menus() as menus:
            for menu in menus.values():
                if message_key in menu.get("messages", []):
                    menu["messages"].remove(message_key)
            for name in select_names:
                messages = menus[name].setdefault("messages", [])
                if message_key not in messages:
                    messages.append(message_key)
        data = await self.config.guild(guild).all()
        view = self._build_component_view(guild, message_key, data)
        if view is not None:
            guild_views = self._component_views.setdefault(guild.id, {})
            old_view = guild_views.get(message_key)
            if old_view is not None:
                old_view.stop()
            guild_views[message_key] = view
            try:
                _channel_id, message_id = message_key.split("-", 1)
                self.bot.add_view(view, message_id=int(message_id))
            except (AttributeError, TypeError, ValueError):
                pass

    async def _cleanup_component_messages(self, guild: discord.Guild, key: str) -> int:
        removed = 0
        async with getattr(self.config.guild(guild), key)() as records:
            for record in records.values():
                kept = []
                for message_key in record.get("messages", []):
                    try:
                        channel_id, message_id = message_key.split("-", 1)
                    except ValueError:
                        removed += 1
                        continue
                    channel = guild.get_channel_or_thread(int(channel_id))
                    if channel is None:
                        removed += 1
                        continue
                    try:
                        await channel.fetch_message(int(message_id))
                    except (discord.NotFound, discord.HTTPException):
                        removed += 1
                    else:
                        kept.append(message_key)
                record["messages"] = kept
        await self._load_component_views()
        return removed

    async def _apply_external_role_rules(
        self,
        member: discord.Member,
        added_role_ids: Iterable[int],
        removed_role_ids: Iterable[int],
    ) -> None:
        """Apply role policies and explicit rules to changes made outside this cog."""
        key = (member.guild.id, member.id)
        if key in self._role_rule_processing:
            return
        self._role_rule_processing.add(key)
        try:
            guild = member.guild
            explicit_rules = await self.config.guild(guild).role_rules()
            events = deque(
                [("add", int(role_id)) for role_id in added_role_ids]
                + [("remove", int(role_id)) for role_id in removed_role_ids],
            )
            if not events:
                return

            planned_role_ids = {role.id for role in member.roles}
            to_add: dict[int, discord.Role] = {}
            to_remove: dict[int, discord.Role] = {}
            processed_events: set[tuple[str, int]] = set()

            def schedule(action: str, role_id: int) -> None:
                role = guild.get_role(int(role_id))
                if role is None or not self._bot_can_apply_to_member(member, role):
                    return
                if action == "add":
                    if role.id in planned_role_ids:
                        return
                    planned_role_ids.add(role.id)
                    to_remove.pop(role.id, None)
                    to_add[role.id] = role
                else:
                    if role.id not in planned_role_ids:
                        return
                    planned_role_ids.discard(role.id)
                    to_add.pop(role.id, None)
                    to_remove[role.id] = role
                events.append((action, role.id))

            while events and len(processed_events) < 250:
                event, trigger_role_id = events.popleft()
                event_key = (event, trigger_role_id)
                if event_key in processed_events:
                    continue
                processed_events.add(event_key)
                trigger_role = guild.get_role(trigger_role_id)
                if trigger_role is None:
                    continue

                if event == "add":
                    required = [
                        int(role_id)
                        for role_id in await self.config.role(trigger_role).required()
                        if guild.get_role(int(role_id)) is not None
                    ]
                    require_any = bool(
                        await self.config.role(trigger_role).require_any(),
                    )
                    requirements_met = not required or (
                        any(role_id in planned_role_ids for role_id in required)
                        if require_any
                        else all(role_id in planned_role_ids for role_id in required)
                    )
                    if not requirements_met:
                        schedule("remove", trigger_role.id)
                        continue
                    for role_id in await self.config.role(
                        trigger_role,
                    ).inclusive_with():
                        schedule("add", int(role_id))
                    for role_id in await self.config.role(trigger_role).exclusive_to():
                        schedule("remove", int(role_id))
                else:
                    for role_id in await self.config.role(
                        trigger_role,
                    ).inclusive_with():
                        schedule("remove", int(role_id))

                for rule in explicit_rules.values():
                    if not rule.get("enabled", True):
                        continue
                    if int(rule.get("trigger_role_id", 0)) != trigger_role_id:
                        continue
                    if str(rule.get("trigger_event", "add")).lower() != event:
                        continue
                    for role_id in rule.get("add_role_ids", []):
                        schedule("add", int(role_id))
                    for role_id in rule.get("remove_role_ids", []):
                        schedule("remove", int(role_id))

            if events:
                log.warning(
                    "Stopped role-rule processing at the safety limit for guild %s member %s.",
                    guild.id,
                    member.id,
                )

            removed_roles = list(to_remove.values())
            added_roles = list(to_add.values())
            if removed_roles:
                try:
                    await member.remove_roles(
                        *removed_roles,
                        reason="RoleManager automatic role rule.",
                    )
                except discord.HTTPException:
                    log.exception(
                        "Failed automatic role-rule removals for guild %s member %s.",
                        guild.id,
                        member.id,
                    )
                    removed_roles = []
            if added_roles:
                try:
                    await member.add_roles(
                        *added_roles,
                        reason="RoleManager automatic role rule.",
                    )
                except discord.HTTPException:
                    log.exception(
                        "Failed automatic role-rule additions for guild %s member %s.",
                        guild.id,
                        member.id,
                    )
                    added_roles = []

            for role in removed_roles:
                await self._clear_temp_role(member, role)
            for role in added_roles:
                await self._maybe_track_temp_role(member, role)
            if added_roles or removed_roles:
                await self._record_role_audit(
                    guild,
                    action="automatic_role_rule",
                    member_id=member.id,
                    role_ids=[role.id for role in (*added_roles, *removed_roles)],
                    source="external-role-rule",
                    detail=(f"Added {len(added_roles)} and removed {len(removed_roles)} role(s)."),
                )
        finally:
            self._role_rule_processing.discard(key)

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member) -> None:
        if await self.bot.cog_disabled_in_guild(self, member.guild):
            return
        await self._restore_sticky_roles(member)
        if getattr(member, "pending", False):
            return
        await self._schedule_autoroles(member)

    @commands.Cog.listener()
    async def on_member_update(
        self,
        before: discord.Member,
        after: discord.Member,
    ) -> None:
        if await self.bot.cog_disabled_in_guild(self, after.guild):
            return
        if getattr(before, "pending", False) and not getattr(after, "pending", False):
            await self._schedule_autoroles(after)
        before_role_ids = {role.id for role in before.roles}
        after_role_ids = {role.id for role in after.roles}
        added_role_ids = after_role_ids - before_role_ids
        removed_role_ids = before_role_ids - after_role_ids
        if added_role_ids or removed_role_ids:
            await self._apply_external_role_rules(
                after,
                added_role_ids,
                removed_role_ids,
            )

    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member) -> None:
        if await self.bot.cog_disabled_in_guild(self, member.guild):
            return
        sticky_role_ids = []
        for role in member.roles:
            if role.is_default():
                continue
            if await self.config.role(role).sticky():
                sticky_role_ids.append(role.id)
        if not sticky_role_ids:
            return
        async with self.config.member(member).sticky_roles() as stored:
            for role_id in sticky_role_ids:
                if role_id not in stored:
                    stored.append(role_id)

    async def _restore_sticky_roles(self, member: discord.Member) -> None:
        role_ids = await self.config.member(member).sticky_roles()
        if not role_ids:
            return
        roles = [
            role
            for role_id in role_ids
            if (role := member.guild.get_role(int(role_id))) is not None
            and self._bot_can_apply_to_member(member, role)
            and role not in member.roles
        ]
        if roles:
            await self._give_roles(
                member,
                roles,
                "Restored sticky roles.",
                check_required=False,
                check_exclusive=False,
                check_inclusive=False,
                check_cost=False,
            )

    async def _resume_autorole_queue(self) -> None:
        """Resume delayed autorole assignments which survived a bot restart."""
        for guild_id, data in (await self.config.all_guilds()).items():
            guild = self.bot.get_guild(guild_id)
            if guild is None:
                continue
            pending = [
                (member, item)
                for item in data.get("autorole_queue", [])
                if (member := guild.get_member(int(item.get("member_id", 0) or 0))) is not None
            ]
            await self.config.guild(guild).autorole_queue.set([item for _member, item in pending])
            for member, item in pending:
                key = (guild.id, member.id)
                if key not in self._autorole_tasks:
                    self._autorole_tasks[key] = asyncio.create_task(
                        self._autorole_worker(
                            member,
                            run_at=float(item.get("run_at", self._now_ts())),
                        ),
                    )

    async def _schedule_autoroles(self, member: discord.Member) -> None:
        key = (member.guild.id, member.id)
        previous = self._autorole_tasks.get(key)
        if previous is not None and not previous.done():
            previous.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await previous
        settings = await self.config.guild(member.guild).auto_roles()
        delay = max(0, min(int(settings.get("delay_seconds", 0) or 0), 86_400))
        run_at = self._now_ts() + delay
        async with self.config.guild(member.guild).autorole_queue() as queue:
            queue[:] = [item for item in queue if int(item.get("member_id", 0) or 0) != member.id]
            queue.append({"member_id": member.id, "run_at": run_at})
        self._autorole_tasks[key] = asyncio.create_task(self._autorole_worker(member, run_at=run_at))

    async def _autorole_worker(
        self,
        member: discord.Member,
        *,
        run_at: float,
    ) -> None:
        key = (member.guild.id, member.id)
        try:
            settings = await self.config.guild(member.guild).auto_roles()
            delay = max(0.0, run_at - self._now_ts())
            if delay:
                await asyncio.sleep(delay)
            current = member.guild.get_member(member.id)
            if current is None:
                return
            if await self.bot.cog_disabled_in_guild(self, current.guild):
                return
            minimum_age = max(0, int(settings.get("minimum_account_age_hours", 0) or 0))
            account_age = datetime.now(timezone.utc) - current.created_at
            if account_age < timedelta(hours=minimum_age):
                await self._record_role_audit(
                    current.guild,
                    action="autorole_skipped",
                    member_id=current.id,
                    source="autorole",
                    detail=f"Account younger than {minimum_age} hour(s).",
                )
                return
            retries = max(1, min(int(settings.get("retries", 3) or 3), 10))
            for attempt in range(retries):
                try:
                    if await self._apply_autoroles(current, settings=settings):
                        return
                    if attempt + 1 >= retries:
                        return
                    await asyncio.sleep(min(2 ** (attempt + 1), 30))
                except discord.HTTPException:
                    if attempt + 1 >= retries:
                        raise
                    await asyncio.sleep(min(2 ** (attempt + 1), 30))
        except asyncio.CancelledError:
            raise
        except discord.HTTPException:
            log.exception("Autorole delivery failed for member %s.", member.id)
        finally:
            async with self.config.guild(member.guild).autorole_queue() as queue:
                queue[:] = [item for item in queue if int(item.get("member_id", 0) or 0) != member.id]
            self._autorole_tasks.pop(key, None)

    async def _apply_autoroles(
        self,
        member: discord.Member,
        *,
        settings: dict[str, Any] | None = None,
    ) -> bool:
        settings = settings or await self.config.guild(member.guild).auto_roles()
        if not settings.get("enabled"):
            return True
        await self._wait_for_guild_verification(member)
        role_ids = list(settings.get("all", [])) if settings.get("all_enabled", True) else []
        target = "bots" if member.bot else "humans"
        if settings.get(f"{target}_enabled", True):
            role_ids.extend(settings.get(target, []))
        roles = [
            role
            for role_id in dict.fromkeys(role_ids)
            if (role := member.guild.get_role(int(role_id))) is not None
            and self._bot_can_apply_to_member(member, role)
            and role not in member.roles
        ]
        if not roles:
            return True
        responses, added, _removed = await self._give_roles(
            member,
            roles,
            "RoleManager autorole.",
            check_cost=False,
        )
        await self._record_role_audit(
            member.guild,
            action="autorole",
            member_id=member.id,
            role_ids=[role.id for role in added],
            source="autorole",
            detail=self._response_text(responses) if responses else "Assigned joining roles.",
        )
        return not any("Discord rejected" in response.reason for response in responses)

    @commands.Cog.listener()
    async def on_raw_reaction_add(
        self,
        payload: discord.RawReactionActionEvent,
    ) -> None:
        """Handle a reaction added to a configured role panel."""
        await self._handle_raw_reaction_event(payload, adding=True)

    @commands.Cog.listener()
    async def on_raw_reaction_remove(
        self,
        payload: discord.RawReactionActionEvent,
    ) -> None:
        """Handle a reaction removed from a configured role panel."""
        await self._handle_raw_reaction_event(payload, adding=False)

    async def _handle_raw_reaction_event(
        self,
        payload: discord.RawReactionActionEvent,
        *,
        adding: bool,
    ) -> None:
        if payload.guild_id is None:
            return
        if await self.bot.cog_disabled_in_guild_raw(
            self.qualified_name,
            payload.guild_id,
        ):
            return
        guild = self.bot.get_guild(payload.guild_id)
        if guild is None:
            return

        # Config is authoritative. The cache is only an optimization and may be
        # briefly stale after imports, dashboard writes, or a failed startup
        # repair. Looking up the record here reconnects existing panels without
        # requiring their messages or reactions to be recreated.
        data = await self.config.guild(guild).react_roles()
        message_data = data.get(str(payload.message_id))
        if not message_data:
            self._reaction_message_cache.discard(payload.message_id)
            return
        self._reaction_message_cache.add(payload.message_id)

        emoji_key = self._emoji_key(payload.emoji)
        bind = message_data.get("binds", {}).get(emoji_key)
        if not bind:
            normalized, changes = normalize_reaction_bindings(
                message_data.get("binds", {}),
            )
            bind = normalized.get(emoji_key)
            if changes:
                async with self.config.guild(guild).react_roles() as react_roles:
                    configured = react_roles.get(str(payload.message_id))
                    if configured is not None:
                        configured["binds"] = normalized
            if not bind:
                return

        member = payload.member if adding else guild.get_member(payload.user_id)
        if member is None:
            try:
                member = await guild.fetch_member(payload.user_id)
            except (discord.NotFound, discord.Forbidden, discord.HTTPException):
                log.debug(
                    "Could not resolve member %s for reaction-role event in guild %s.",
                    payload.user_id,
                    guild.id,
                )
                return
        if member.bot:
            return
        role = guild.get_role(int(bind.get("role_id", 0)))
        if role is None:
            async with self.config.guild(guild).react_roles() as react_roles:
                configured = react_roles.get(str(payload.message_id), {})
                binds = configured.get("binds", {})
                binds.pop(emoji_key, None)
                if not binds:
                    react_roles.pop(str(payload.message_id), None)
                    self._reaction_message_cache.discard(payload.message_id)
            return
        if not self._bot_can_apply_to_member(member, role):
            log.info(
                "Reaction-role update for role %s and member %s was blocked because %s.",
                role.id,
                member.id,
                role_assignment_blocker(member, role),
            )
            return

        try:
            if adding and role not in member.roles:
                wait = await self._check_guild_verification(member, guild)
                if wait or getattr(member, "pending", False):
                    return
                failures, added, _removed = await self._give_roles(
                    member,
                    [role],
                    "Reaction role.",
                )
                if failures and not added:
                    log.info(
                        "Reaction-role assignment for role %s and member %s was blocked: %s",
                        role.id,
                        member.id,
                        "; ".join(item.reason for item in failures),
                    )
            elif not adding and bind.get("remove_on_unreact", True) and role in member.roles:
                failures, removed = await self._remove_roles(
                    member,
                    [role],
                    "Reaction role removed.",
                )
                if failures and not removed:
                    log.info(
                        "Reaction-role removal for role %s and member %s was blocked: %s",
                        role.id,
                        member.id,
                        "; ".join(item.reason for item in failures),
                    )
        except discord.HTTPException:
            log.exception(
                "Failed to process reaction role %s for member %s.",
                role.id,
                member.id,
            )

    @app_commands.command(
        name="rolemanager-selfrole",
        description="Add or remove one of this server's self roles.",
    )
    @app_commands.guild_only()
    async def app_selfrole(
        self,
        interaction: discord.Interaction,
        role: discord.Role,
    ) -> None:
        """Slash-command role picker for self-service roles."""
        if interaction.guild is None or not isinstance(interaction.user, discord.Member):
            await interaction.response.send_message("This can only be used in a server.", ephemeral=True)
            return
        if await self.bot.cog_disabled_in_guild(self, interaction.guild):
            await interaction.response.send_message("RoleManager is disabled here.", ephemeral=True)
            return
        await interaction.response.defer(ephemeral=True, thinking=True)
        member = interaction.user
        if role in member.roles:
            if not await self.config.role(role).self_removable():
                message = f"{role.name} is not self-removable."
            else:
                responses, removed = await self._remove_roles(member, [role], "Selfrole app command.")
                message = self._response_text(responses) if responses else f"Removed {self._format_role_names(removed)}."
        elif not await self.config.role(role).self_assignable():
            message = f"{role.name} is not self-assignable."
        elif getattr(member, "pending", False):
            message = "Finish Discord membership screening before taking self roles."
        elif wait := await self._check_guild_verification(member, interaction.guild):
            retry_at = datetime.now(timezone.utc) + timedelta(seconds=int(wait))
            message = f"Spend more time in this server first; try again {discord.utils.format_dt(retry_at, 'R')}."
        else:
            responses, added, _removed = await self._give_roles(member, [role], "Selfrole app command.")
            message = self._response_text(responses) if responses else f"Added {self._format_role_names(added)}."
        await interaction.followup.send(message, ephemeral=True)

    @app_commands.command(
        name="rolemanager-role-info",
        description="Show information about a server role.",
    )
    @app_commands.guild_only()
    async def app_role_info(
        self,
        interaction: discord.Interaction,
        role: discord.Role,
    ) -> None:
        """Slash-command role report with Discord's native role picker."""
        data = await self.config.role(role).all()
        embed = discord.Embed(title=role.name, color=role.color)
        embed.description = (
            f"ID: `{role.id}`\nMembers: `{len(role.members)}`\nPosition: `{role.position}`\n"
            f"Self assignable: `{bool(data.get('self_assignable'))}`\n"
            f"Self removable: `{bool(data.get('self_removable'))}`\nSticky: `{bool(data.get('sticky'))}`"
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @commands.Cog.listener()
    async def on_raw_message_delete(
        self,
        payload: discord.RawMessageDeleteEvent,
    ) -> None:
        if payload.guild_id is None or payload.message_id not in self._reaction_message_cache:
            return
        async with self.config.guild_from_id(
            payload.guild_id,
        ).react_roles() as react_roles:
            react_roles.pop(str(payload.message_id), None)
        self._reaction_message_cache.discard(payload.message_id)

    @commands.Cog.listener()
    async def on_raw_bulk_message_delete(
        self,
        payload: discord.RawBulkMessageDeleteEvent,
    ) -> None:
        if payload.guild_id is None:
            return
        deleted = [message_id for message_id in payload.message_ids if message_id in self._reaction_message_cache]
        if not deleted:
            return
        async with self.config.guild_from_id(
            payload.guild_id,
        ).react_roles() as react_roles:
            for message_id in deleted:
                react_roles.pop(str(message_id), None)
                self._reaction_message_cache.discard(message_id)
