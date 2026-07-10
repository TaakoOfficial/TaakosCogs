"""Red-Web-Dashboard integration for RoleManager."""

from __future__ import annotations

import html
import logging
import typing
from datetime import datetime, timezone

import discord
from redbot.core import bank, commands

log = logging.getLogger("red.taakoscogs.rolemanager.dashboard")


def dashboard_page(*args, **kwargs):
    """Dashboard page decorator compatible with Red-Web-Dashboard."""

    def decorator(func: typing.Callable):
        func.__dashboard_decorator_params__ = (args, kwargs)
        return func

    return decorator


class DashboardIntegration:
    """Dashboard integration mixin for RoleManager."""

    @commands.Cog.listener()
    async def on_dashboard_cog_add(self, dashboard_cog: commands.Cog) -> None:
        """Register RoleManager as a Red-Web-Dashboard third party."""
        handler = dashboard_cog.rpc.third_parties_handler
        try:
            handler.add_third_party(self, overwrite=True)
        except TypeError:
            handler.add_third_party(self)

    @dashboard_page(
        name=None,
        description="Configure role policies, automatic rules, member operations, and role panels.",
        methods=("GET", "POST"),
    )
    async def dashboard_page(
        self,
        user: discord.User,
        guild: discord.Guild,
        **kwargs,
    ) -> typing.Dict[str, typing.Any]:
        """Render and process the RoleManager dashboard page."""
        member, can_manage = await self._dashboard_member_can_manage(user, guild)
        if not can_manage:
            return {
                "status": 1,
                "error_title": "Insufficient Permissions",
                "error_message": "You need Manage Server, Red admin, or bot owner access.",
            }

        notifications = []
        form_data = self._dashboard_form_data(kwargs)
        selected_role_id = self._dashboard_selected_role_id(form_data)

        if kwargs.get("method", "GET") == "POST":
            action = self._dash_value(form_data, "action")
            try:
                selected_role_id, messages = await self._dashboard_handle_action(
                    guild,
                    member,
                    action,
                    form_data,
                    selected_role_id,
                )
            except commands.CommandError as error:
                notifications.append({"message": str(error), "category": "error"})
            except Exception as error:
                log.exception("RoleManager dashboard action failed.")
                notifications.append(
                    {
                        "message": f"RoleManager dashboard action failed: {error}",
                        "category": "error",
                    }
                )
            else:
                notifications.extend(messages)

        source = await self._dashboard_source(guild, selected_role_id, kwargs)
        return {
            "status": 0,
            "notifications": notifications,
            "web_content": {
                "source": source,
                "expanded": True,
            },
        }

    async def _dashboard_member_can_manage(
        self,
        user: discord.User,
        guild: discord.Guild,
    ) -> typing.Tuple[typing.Optional[discord.Member], bool]:
        member = guild.get_member(user.id)
        is_owner = user.id in getattr(self.bot, "owner_ids", set())
        is_admin = member is not None and await self.bot.is_admin(member)
        can_manage = (
            is_owner
            or is_admin
            or (member is not None and member.guild_permissions.manage_guild)
        )
        return member, can_manage

    def _dashboard_form_data(self, kwargs: typing.Dict[str, typing.Any]) -> typing.Any:
        data = kwargs.get("data") or {}
        if isinstance(data, dict) and ("form" in data or "json" in data):
            return data.get("form") or data.get("json") or {}
        return data

    def _dashboard_selected_role_id(self, form_data: typing.Any) -> typing.Optional[int]:
        value = (
            self._dash_value(form_data, "selected_role_id")
            or self._dash_value(form_data, "role_id")
        ).strip()
        if not value:
            return None
        try:
            return int(value)
        except (TypeError, ValueError):
            return None

    def _dash_value(
        self,
        form_data: typing.Any,
        key: str,
        default: str = "",
    ) -> str:
        if hasattr(form_data, "get"):
            value = form_data.get(key, default)
        else:
            return default
        if isinstance(value, (list, tuple)):
            value = value[0] if value else default
        if value is None:
            return default
        return str(value)

    def _dash_values(self, form_data: typing.Any, key: str) -> typing.List[str]:
        if hasattr(form_data, "getlist"):
            values = form_data.getlist(key)
        elif hasattr(form_data, "get"):
            value = form_data.get(key, [])
            values = value if isinstance(value, (list, tuple)) else [value]
        else:
            values = []
        return [str(value) for value in values if str(value).strip()]

    def _dash_bool(self, form_data: typing.Any, key: str) -> bool:
        if hasattr(form_data, "__contains__") and key in form_data:
            value = self._dash_value(form_data, key, "1").lower()
            return value not in {"0", "false", "off", "no", ""}
        return False

    def _dashboard_active_tab(self, kwargs: typing.Dict[str, typing.Any]) -> str:
        form_data = self._dashboard_form_data(kwargs)
        selected = self._dash_value(form_data, "active_tab").lower()
        valid_tabs = {"overview", "roles", "members", "panels", "data"}
        if selected in valid_tabs:
            return selected

        action = self._dash_value(form_data, "action").lower()
        action_tabs = {
            "save_guild_settings": "overview",
            "create_role": "overview",
            "select_role": "roles",
            "save_role_flags": "roles",
            "make_inclusive_mutual": "roles",
            "make_exclusive_mutual": "roles",
            "save_role_rule": "roles",
            "delete_role_rule": "roles",
            "save_autoroles": "roles",
            "role_operation": "members",
            "sticky_member_action": "members",
            "give_temp_role": "members",
            "clear_temp_role": "members",
            "bind_reaction_role": "panels",
            "create_reaction_panel": "panels",
            "refresh_reaction_message": "panels",
            "cleanup_reaction_roles": "panels",
            "delete_reaction_bind": "panels",
            "clear_reaction_message": "panels",
            "create_button": "panels",
            "delete_button": "panels",
            "create_select_option": "panels",
            "delete_select_option": "panels",
            "create_select_menu": "panels",
            "delete_select_menu": "panels",
            "send_component_message": "panels",
            "edit_component_message": "panels",
            "cleanup_component_messages": "panels",
            "import_settings": "data",
        }
        return action_tabs.get(action, "overview")

    def _dash_optional_id(self, form_data: typing.Any, key: str) -> typing.Optional[int]:
        value = self._dash_value(form_data, key).strip()
        if not value:
            return None
        try:
            return int(value)
        except (TypeError, ValueError) as exc:
            raise commands.BadArgument(f"`{key}` must be a Discord ID.") from exc

    def _dash_required_id(self, form_data: typing.Any, key: str) -> int:
        value = self._dash_optional_id(form_data, key)
        if value is None:
            raise commands.BadArgument(f"`{key}` is required.")
        return value

    def _dash_csrf(self, kwargs: typing.Dict[str, typing.Any]) -> str:
        csrf_token = kwargs.get("csrf_token")
        if not isinstance(csrf_token, (tuple, list)) or len(csrf_token) != 2:
            return ""
        return (
            '<input type="hidden" name="csrf_token" value="'
            f'{html.escape(str(csrf_token[1]), quote=True)}">'
        )

    async def _dashboard_handle_action(
        self,
        guild: discord.Guild,
        member: typing.Optional[discord.Member],
        action: str,
        form_data: typing.Any,
        selected_role_id: typing.Optional[int],
    ) -> typing.Tuple[typing.Optional[int], typing.List[typing.Dict[str, str]]]:
        messages: typing.List[typing.Dict[str, str]] = []

        if action == "select_role":
            return selected_role_id, messages

        if action == "save_role_flags":
            role = self._dashboard_role_from_form(guild, form_data, "role_id")
            self._dashboard_check_role_manageable(guild, role, member)
            await self._dashboard_save_role_flags(guild, member, role, form_data)
            messages.append(
                {
                    "message": f"Saved role settings for {role.name}.",
                    "category": "success",
                }
            )
            return role.id, messages

        if action == "save_guild_settings":
            atomic = await self._dashboard_save_guild_settings(guild, form_data)
            messages.append(
                {
                    "message": f"Guild atomic assignment set to {atomic}.",
                    "category": "success",
                }
            )
            return selected_role_id, messages

        if action == "create_role":
            role = await self._dashboard_create_role(guild, member, form_data)
            messages.append(
                {"message": f"Created role {role.name}.", "category": "success"}
            )
            return role.id, messages

        if action in {"make_inclusive_mutual", "make_exclusive_mutual"}:
            role = self._dashboard_role_from_form(guild, form_data, "role_id")
            self._dashboard_check_role_manageable(guild, role, member)
            policy = "inclusive" if action == "make_inclusive_mutual" else "exclusive"
            count = await self._dashboard_make_policy_mutual(
                guild,
                member,
                role,
                form_data,
                policy,
            )
            messages.append(
                {
                    "message": f"Updated {count:,} mutual {policy} role link(s).",
                    "category": "success",
                }
            )
            return role.id, messages

        if action == "save_role_rule":
            name = await self._dashboard_save_role_rule(guild, member, form_data)
            messages.append(
                {"message": f"Role rule `{name}` saved.", "category": "success"}
            )
            return selected_role_id, messages

        if action == "delete_role_rule":
            name = await self._dashboard_delete_role_rule(guild, form_data)
            messages.append(
                {"message": f"Role rule `{name}` deleted.", "category": "success"}
            )
            return selected_role_id, messages

        if action == "save_autoroles":
            await self._dashboard_save_autoroles(guild, member, form_data)
            messages.append({"message": "Autorole settings saved.", "category": "success"})
            return selected_role_id, messages

        if action == "bind_reaction_role":
            message = await self._dashboard_bind_reaction_role(guild, member, form_data)
            messages.append(
                {
                    "message": f"Reaction role bound on message {message.id}.",
                    "category": "success",
                }
            )
            return selected_role_id, messages

        if action == "create_reaction_panel":
            message = await self._dashboard_create_reaction_panel(guild, member, form_data)
            messages.append(
                {
                    "message": f"Reaction-role panel created: {message.jump_url}",
                    "category": "success",
                }
            )
            return selected_role_id, messages

        if action == "refresh_reaction_message":
            count = await self._dashboard_refresh_reaction_message(guild, form_data)
            messages.append(
                {
                    "message": f"Refreshed {count:,} reaction(s).",
                    "category": "success",
                }
            )
            return selected_role_id, messages

        if action == "cleanup_reaction_roles":
            count = await self._dashboard_cleanup_reaction_roles(guild)
            messages.append(
                {
                    "message": f"Removed {count:,} stale reaction-role record(s).",
                    "category": "success",
                }
            )
            return selected_role_id, messages

        if action == "delete_reaction_bind":
            message_id = await self._dashboard_delete_reaction_bind(guild, form_data)
            messages.append(
                {
                    "message": f"Reaction-role binding removed from message {message_id}.",
                    "category": "success",
                }
            )
            return selected_role_id, messages

        if action == "clear_reaction_message":
            message_id = await self._dashboard_clear_reaction_message(guild, form_data)
            messages.append(
                {
                    "message": f"Reaction-role message {message_id} cleared.",
                    "category": "success",
                }
            )
            return selected_role_id, messages

        if action == "create_button":
            name = await self._dashboard_create_button(guild, member, form_data)
            messages.append({"message": f"Button `{name}` saved.", "category": "success"})
            return selected_role_id, messages

        if action == "delete_button":
            name = await self._dashboard_delete_button(guild, form_data)
            messages.append({"message": f"Button `{name}` deleted.", "category": "success"})
            return selected_role_id, messages

        if action == "create_select_option":
            name = await self._dashboard_create_select_option(guild, member, form_data)
            messages.append(
                {"message": f"Select option `{name}` saved.", "category": "success"}
            )
            return selected_role_id, messages

        if action == "delete_select_option":
            name = await self._dashboard_delete_select_option(guild, form_data)
            messages.append(
                {"message": f"Select option `{name}` deleted.", "category": "success"}
            )
            return selected_role_id, messages

        if action == "create_select_menu":
            name = await self._dashboard_create_select_menu(guild, form_data)
            messages.append(
                {"message": f"Select menu `{name}` saved.", "category": "success"}
            )
            return selected_role_id, messages

        if action == "delete_select_menu":
            name = await self._dashboard_delete_select_menu(guild, form_data)
            messages.append(
                {"message": f"Select menu `{name}` deleted.", "category": "success"}
            )
            return selected_role_id, messages

        if action == "send_component_message":
            message = await self._dashboard_send_component_message(guild, form_data)
            messages.append(
                {
                    "message": f"Component message sent in #{message.channel.name}.",
                    "category": "success",
                }
            )
            return selected_role_id, messages

        if action == "edit_component_message":
            message = await self._dashboard_edit_component_message(guild, form_data)
            messages.append(
                {
                    "message": f"Component message updated: {message.jump_url}",
                    "category": "success",
                }
            )
            return selected_role_id, messages

        if action == "cleanup_component_messages":
            removed = await self._dashboard_cleanup_component_messages(guild)
            messages.append(
                {
                    "message": f"Removed {removed:,} stale component message reference(s).",
                    "category": "success",
                }
            )
            return selected_role_id, messages

        if action == "sticky_member_action":
            message = await self._dashboard_sticky_member_action(guild, member, form_data)
            messages.append({"message": message, "category": "success"})
            return selected_role_id, messages

        if action == "give_temp_role":
            message = await self._dashboard_give_temp_role(guild, member, form_data)
            messages.append({"message": message, "category": "success"})
            return selected_role_id, messages

        if action == "role_operation":
            message = await self._dashboard_role_operation(guild, member, form_data)
            messages.append({"message": message, "category": "success"})
            return selected_role_id, messages

        if action == "import_settings":
            source, count = await self._dashboard_import_settings(guild, form_data)
            messages.append(
                {
                    "message": f"Imported {source} settings. Records touched: {count:,}.",
                    "category": "success",
                }
            )
            return selected_role_id, messages

        if action == "clear_temp_role":
            member_id, role_id = await self._dashboard_clear_temp_role(guild, form_data)
            messages.append(
                {
                    "message": f"Cleared pending temp role {role_id} for member {member_id}.",
                    "category": "success",
                }
            )
            return selected_role_id, messages

        if action:
            raise commands.BadArgument("Unknown RoleManager dashboard action.")
        return selected_role_id, messages

    def _dashboard_role_from_form(
        self,
        guild: discord.Guild,
        form_data: typing.Any,
        key: str,
    ) -> discord.Role:
        role_id = self._dash_required_id(form_data, key)
        role = guild.get_role(role_id)
        if role is None:
            raise commands.BadArgument(f"Role `{role_id}` was not found.")
        return role

    def _dashboard_check_role_manageable(
        self,
        guild: discord.Guild,
        role: discord.Role,
        member: typing.Optional[discord.Member],
    ) -> None:
        if role.is_default():
            raise commands.BadArgument("The everyone role cannot be managed here.")
        if role.managed:
            raise commands.BadArgument("Integration-managed roles cannot be managed here.")
        me = guild.me
        if me is None or not me.guild_permissions.manage_roles:
            raise commands.BadArgument("The bot needs Manage Roles.")
        if role >= me.top_role:
            raise commands.BadArgument(f"The bot's top role must be above `{role.name}`.")
        if (
            member is not None
            and member.id not in getattr(self.bot, "owner_ids", set())
            and member.id != guild.owner_id
            and not member.guild_permissions.administrator
            and role >= member.top_role
        ):
            raise commands.BadArgument(f"Your top role must be above `{role.name}`.")

    def _dashboard_check_trigger_role(
        self,
        guild: discord.Guild,
        role: discord.Role,
        member: typing.Optional[discord.Member],
    ) -> None:
        if role.is_default():
            raise commands.BadArgument("The everyone role cannot be a rule trigger.")
        if (
            member is not None
            and member.id not in getattr(self.bot, "owner_ids", set())
            and member.id != guild.owner_id
            and not member.guild_permissions.administrator
            and role >= member.top_role
        ):
            raise commands.BadArgument("Your top role must be above the trigger role.")

    @staticmethod
    def _dashboard_color(value: str) -> discord.Color:
        value = value.strip().lower()
        if value.startswith("#"):
            value = value[1:]
        if value.startswith("0x"):
            value = value[2:]
        if not value:
            return discord.Color.default()
        if not all(character in "0123456789abcdef" for character in value) or len(value) > 6:
            raise commands.BadArgument("Role color must be a hex value such as `5865F2`.")
        return discord.Color(int(value, 16))

    async def _dashboard_save_guild_settings(
        self,
        guild: discord.Guild,
        form_data: typing.Any,
    ) -> str:
        atomic = self._dash_value(form_data, "atomic", "inherit").lower()
        if atomic == "inherit":
            await self.config.guild(guild).atomic.clear()
            return "the global default"
        if atomic not in {"true", "false"}:
            raise commands.BadArgument("Atomic assignment must be inherit, true, or false.")
        enabled = atomic == "true"
        await self.config.guild(guild).atomic.set(enabled)
        return str(enabled)

    async def _dashboard_create_role(
        self,
        guild: discord.Guild,
        member: typing.Optional[discord.Member],
        form_data: typing.Any,
    ) -> discord.Role:
        if len(guild.roles) >= 250:
            raise commands.BadArgument("This server is already at Discord's 250 role limit.")
        me = guild.me
        if me is None or not me.guild_permissions.manage_roles:
            raise commands.BadArgument("The bot needs Manage Roles.")
        name = self._dash_value(form_data, "new_role_name").strip()
        if not name or len(name) > 100:
            raise commands.BadArgument("Role name must contain between 1 and 100 characters.")
        color = self._dashboard_color(self._dash_value(form_data, "new_role_color"))
        return await guild.create_role(
            name=name,
            color=color,
            hoist=self._dash_bool(form_data, "new_role_hoist"),
            mentionable=self._dash_bool(form_data, "new_role_mentionable"),
            reason=f"RoleManager dashboard role create by {member or 'bot owner'}.",
        )

    async def _dashboard_make_policy_mutual(
        self,
        guild: discord.Guild,
        member: typing.Optional[discord.Member],
        role: discord.Role,
        form_data: typing.Any,
        policy: str,
    ) -> int:
        if policy not in {"inclusive", "exclusive"}:
            raise commands.BadArgument("Unknown mutual policy type.")
        field = f"{policy}_roles"
        conflict_field = "exclusive_roles" if policy == "inclusive" else "inclusive_roles"
        config_key = "inclusive_with" if policy == "inclusive" else "exclusive_to"
        conflict_key = "exclusive_to" if policy == "inclusive" else "inclusive_with"
        role_ids = self._dashboard_valid_role_ids(guild, member, form_data, field)
        role_ids = [role_id for role_id in role_ids if role_id != role.id]
        if not role_ids:
            raise commands.BadArgument(f"Select at least one {policy} role.")
        current_conflicts = set(
            self._dashboard_valid_role_ids(
                guild,
                member,
                form_data,
                conflict_field,
            )
        )
        overlap = current_conflicts & set(role_ids)
        if overlap:
            raise commands.BadArgument(
                f"A role cannot be both inclusive and exclusive: {self._dashboard_role_names(guild, overlap)}."
            )
        targets = []
        for role_id in role_ids:
            other = guild.get_role(role_id)
            if other is None:
                continue
            other_conflicts = {
                int(item) for item in await getattr(self.config.role(other), conflict_key)()
            }
            if role.id in other_conflicts:
                raise commands.BadArgument(
                    f"{other.name} already has {role.name} configured as a conflicting policy."
                )
            targets.append(other)

        await getattr(self.config.role(role), config_key).set(role_ids)
        changed = 0
        for other in targets:
            async with getattr(self.config.role(other), config_key)() as stored:
                if role.id not in stored:
                    stored.append(role.id)
                    changed += 1
        return changed

    async def _dashboard_save_role_rule(
        self,
        guild: discord.Guild,
        member: typing.Optional[discord.Member],
        form_data: typing.Any,
    ) -> str:
        name = self._normalise_rule_name(self._dash_value(form_data, "rule_name"))
        trigger_event = self._dash_value(form_data, "rule_event", "add").lower()
        if trigger_event not in {"add", "remove"}:
            raise commands.BadArgument("Rule event must be add or remove.")
        trigger = self._dashboard_role_from_form(guild, form_data, "rule_trigger_role_id")
        self._dashboard_check_trigger_role(guild, trigger, member)
        add_ids = self._dashboard_valid_role_ids(
            guild, member, form_data, "rule_add_roles"
        )
        remove_ids = self._dashboard_valid_role_ids(
            guild, member, form_data, "rule_remove_roles"
        )
        if not add_ids and not remove_ids:
            raise commands.BadArgument("A role rule needs at least one add or remove action.")
        if trigger.id in add_ids or trigger.id in remove_ids:
            raise commands.BadArgument("A role rule cannot modify its own trigger role.")
        overlap = set(add_ids) & set(remove_ids)
        if overlap:
            raise commands.BadArgument(
                "A rule cannot add and remove the same role: "
                f"{self._dashboard_role_names(guild, overlap)}."
            )
        async with self.config.guild(guild).role_rules() as rules:
            rules[name] = {
                "trigger_role_id": trigger.id,
                "trigger_event": trigger_event,
                "add_role_ids": add_ids,
                "remove_role_ids": remove_ids,
                "enabled": self._dash_bool(form_data, "rule_enabled"),
            }
        return name

    async def _dashboard_delete_role_rule(
        self,
        guild: discord.Guild,
        form_data: typing.Any,
    ) -> str:
        name = self._normalise_rule_name(self._dash_value(form_data, "rule_name"))
        async with self.config.guild(guild).role_rules() as rules:
            if rules.pop(name, None) is None:
                raise commands.BadArgument(f"Role rule `{name}` was not found.")
        return name

    async def _dashboard_save_role_flags(
        self,
        guild: discord.Guild,
        member: typing.Optional[discord.Member],
        role: discord.Role,
        form_data: typing.Any,
    ) -> None:
        role_name = self._dash_value(form_data, "role_name", role.name).strip()
        if not role_name or len(role_name) > 100:
            raise commands.BadArgument("Role name must contain between 1 and 100 characters.")
        color = self._dashboard_color(self._dash_value(form_data, "role_color"))
        duration = self._dash_value(form_data, "temp_duration").strip()
        temp_duration = self._parse_duration(duration) if duration else None
        cost_value = self._dash_value(form_data, "cost").strip()
        try:
            cost = int(cost_value or 0)
        except ValueError as exc:
            raise commands.BadArgument("Cost must be a whole number.") from exc
        cost = max(0, cost)
        current_cost = int(await self.config.role(role).cost() or 0)
        is_owner = member is None or member.id in getattr(self.bot, "owner_ids", set())
        if cost != current_cost and await bank.is_global() and not is_owner:
            raise commands.BadArgument(
                "Only bot owners can change role costs while the bank is global."
            )
        if cost:
            max_balance = await bank.get_max_balance(guild)
            if cost >= max_balance:
                raise commands.BadArgument("Cost cannot be higher than the bank max balance.")
        required_ids = self._dashboard_valid_role_ids(
            guild,
            member,
            form_data,
            "required_roles",
            check_manageable=False,
        )
        inclusive_ids = self._dashboard_valid_role_ids(
            guild, member, form_data, "inclusive_roles"
        )
        exclusive_ids = self._dashboard_valid_role_ids(
            guild, member, form_data, "exclusive_roles"
        )
        if role.id in required_ids + inclusive_ids + exclusive_ids:
            raise commands.BadArgument("A role cannot require, include, or exclude itself.")
        overlap = set(inclusive_ids) & set(exclusive_ids)
        if overlap:
            raise commands.BadArgument(
                "A role cannot be both inclusive and exclusive: "
                f"{self._dashboard_role_names(guild, overlap)}."
            )

        await role.edit(
            name=role_name,
            color=color,
            hoist=self._dash_bool(form_data, "role_hoist"),
            mentionable=self._dash_bool(form_data, "role_mentionable"),
            reason=f"RoleManager dashboard role edit by {member or 'bot owner'}.",
        )
        await self.config.role(role).self_assignable.set(
            self._dash_bool(form_data, "self_assignable")
        )
        await self.config.role(role).self_removable.set(
            self._dash_bool(form_data, "self_removable")
        )
        await self.config.role(role).sticky.set(self._dash_bool(form_data, "sticky"))
        if temp_duration is None:
            await self.config.role(role).temp_duration.clear()
        else:
            await self.config.role(role).temp_duration.set(temp_duration)
        await self.config.role(role).cost.set(cost)
        await self.config.role(role).require_any.set(self._dash_bool(form_data, "require_any"))
        await self.config.role(role).required.set(required_ids)
        await self.config.role(role).inclusive_with.set(inclusive_ids)
        await self.config.role(role).exclusive_to.set(exclusive_ids)

    async def _dashboard_save_autoroles(
        self,
        guild: discord.Guild,
        member: typing.Optional[discord.Member],
        form_data: typing.Any,
    ) -> None:
        settings = {
            "enabled": self._dash_bool(form_data, "autoroles_enabled"),
            "all": self._dashboard_valid_role_ids(guild, member, form_data, "auto_all"),
            "humans": self._dashboard_valid_role_ids(guild, member, form_data, "auto_humans"),
            "bots": self._dashboard_valid_role_ids(guild, member, form_data, "auto_bots"),
        }
        await self.config.guild(guild).auto_roles.set(settings)

    async def _dashboard_sticky_member_action(
        self,
        guild: discord.Guild,
        actor: typing.Optional[discord.Member],
        form_data: typing.Any,
    ) -> str:
        operation = self._dash_value(form_data, "sticky_operation", "add").lower()
        role = self._dashboard_role_from_form(guild, form_data, "sticky_role_id")
        self._dashboard_check_role_manageable(guild, role, actor)
        user_id = self._dash_required_id(form_data, "sticky_member_id")
        if operation == "forget":
            async with self.config.member_from_ids(guild.id, user_id).sticky_roles() as roles:
                if role.id in roles:
                    roles.remove(role.id)
            return f"Forgot sticky role {role.name} for user ID {user_id}."

        target = guild.get_member(user_id)
        if target is None:
            raise commands.BadArgument(
                "That member is not in the server. Use Forget for departed member IDs."
            )
        if operation == "add":
            async with self.config.member(target).sticky_roles() as roles:
                if role.id not in roles:
                    roles.append(role.id)
            if role not in target.roles:
                responses, added, _removed = await self._give_roles(
                    target,
                    [role],
                    "RoleManager dashboard sticky role add.",
                    check_required=False,
                    check_exclusive=False,
                    check_inclusive=False,
                    check_cost=False,
                )
                if responses and role not in added:
                    raise commands.BadArgument(self._response_text(responses))
            return f"{role.name} is now forced sticky for {target}."
        if operation == "remove":
            async with self.config.member(target).sticky_roles() as roles:
                if role.id in roles:
                    roles.remove(role.id)
            if role in target.roles:
                responses, removed = await self._remove_roles(
                    target,
                    [role],
                    "RoleManager dashboard sticky role remove.",
                    check_inclusive=False,
                )
                if responses and role not in removed:
                    raise commands.BadArgument(self._response_text(responses))
            return f"{role.name} is no longer forced sticky for {target}."
        raise commands.BadArgument("Sticky operation must be add, remove, or forget.")

    async def _dashboard_give_temp_role(
        self,
        guild: discord.Guild,
        actor: typing.Optional[discord.Member],
        form_data: typing.Any,
    ) -> str:
        target_id = self._dash_required_id(form_data, "temp_member_id")
        target = guild.get_member(target_id)
        if target is None:
            raise commands.BadArgument("Temporary-role member was not found in this server.")
        role = self._dashboard_role_from_form(guild, form_data, "temp_role_id")
        self._dashboard_check_role_manageable(guild, role, actor)
        duration = self._parse_duration(self._dash_value(form_data, "temp_give_duration"))
        responses, added, _removed = await self._give_roles(
            target,
            [role],
            "RoleManager dashboard temporary role.",
            check_cost=False,
            duration_overrides={role.id: duration},
        )
        if responses and role not in added:
            raise commands.BadArgument(self._response_text(responses))
        return f"Added {role.name} to {target} for {self._format_duration(duration)}."

    async def _dashboard_role_operation(
        self,
        guild: discord.Guild,
        actor: typing.Optional[discord.Member],
        form_data: typing.Any,
    ) -> str:
        operation = self._dash_value(form_data, "operation", "add").lower()
        if operation not in {"add", "remove"}:
            raise commands.BadArgument("Role operation must be add or remove.")
        dry_run = self._dash_bool(form_data, "operation_dry_run")
        if not dry_run and not self._dash_bool(form_data, "confirm_role_operation"):
            raise commands.BadArgument("Confirm the role operation before applying it.")
        role = self._dashboard_role_from_form(guild, form_data, "operation_role_id")
        self._dashboard_check_role_manageable(guild, role, actor)
        target_type = self._dash_value(form_data, "operation_target_type", "member").lower()
        target_id = self._dash_optional_id(form_data, "operation_target_id")
        await self._ensure_member_cache(guild)

        members: typing.List[discord.Member]
        if target_type == "member":
            target = guild.get_member(target_id or 0)
            if target is None:
                raise commands.BadArgument("Target member was not found.")
            members = [target]
        elif target_type == "role":
            target_role = guild.get_role(target_id or 0)
            if target_role is None:
                raise commands.BadArgument("Target role was not found.")
            members = list(target_role.members)
        elif target_type == "channel":
            channel = guild.get_channel(target_id or 0)
            if not isinstance(channel, discord.TextChannel):
                raise commands.BadArgument("Target text channel was not found.")
            members = list(channel.members)
        elif target_type == "everyone":
            members = list(guild.members)
        elif target_type == "humans":
            members = [target for target in guild.members if not target.bot]
        elif target_type == "bots":
            members = [target for target in guild.members if target.bot]
        else:
            raise commands.BadArgument(
                "Target type must be member, role, channel, everyone, humans, or bots."
            )
        members = list(dict.fromkeys(members))
        if not members:
            raise commands.BadArgument("No members matched that target.")

        eligible = 0
        issues = 0
        policy_added: typing.Set[discord.Role] = set()
        policy_removed: typing.Set[discord.Role] = set()
        for target in members:
            if operation == "add":
                responses, added, removed = await self._give_roles(
                    target,
                    [role],
                    "RoleManager dashboard role operation.",
                    check_cost=False,
                    dry_run=dry_run,
                )
                if role in added:
                    eligible += 1
                policy_added.update(added)
                policy_removed.update(removed)
            else:
                responses, removed = await self._remove_roles(
                    target,
                    [role],
                    "RoleManager dashboard role operation.",
                    dry_run=dry_run,
                )
                if role in removed:
                    eligible += 1
                policy_removed.update(removed)
            if responses:
                issues += 1
        verb = "Would update" if dry_run else "Updated"
        extras = []
        if policy_added - {role}:
            extras.append(
                "also add " + self._dashboard_role_names(guild, [item.id for item in policy_added - {role}])
            )
        if policy_removed - {role}:
            extras.append(
                "also remove "
                + self._dashboard_role_names(guild, [item.id for item in policy_removed - {role}])
            )
        extra_text = f" Policies may {' and '.join(extras)}." if extras else ""
        return (
            f"{verb} {eligible:,} of {len(members):,} matched member(s); "
            f"{issues:,} had policy issues.{extra_text}"
        )

    async def _dashboard_import_settings(
        self,
        guild: discord.Guild,
        form_data: typing.Any,
    ) -> typing.Tuple[str, int]:
        if not self._dash_bool(form_data, "confirm_import"):
            raise commands.BadArgument("Confirm the import before replacing settings.")
        source = self._dash_value(form_data, "import_source").lower()
        if source == "roletools":
            return "RoleTools", await self._import_roletools_settings(guild)
        if source == "roleutils":
            return "RoleUtils", await self._import_roleutils_settings(guild)
        raise commands.BadArgument("Import source must be RoleTools or RoleUtils.")

    def _dashboard_valid_role_ids(
        self,
        guild: discord.Guild,
        member: typing.Optional[discord.Member],
        form_data: typing.Any,
        key: str,
        *,
        check_manageable: bool = True,
    ) -> typing.List[int]:
        role_ids: typing.List[int] = []
        for value in self._dash_values(form_data, key):
            try:
                role_id = int(value)
            except (TypeError, ValueError):
                continue
            role = guild.get_role(role_id)
            if role is None:
                continue
            if check_manageable:
                self._dashboard_check_role_manageable(guild, role, member)
            role_ids.append(role.id)
        return list(dict.fromkeys(role_ids))

    async def _dashboard_create_reaction_panel(
        self,
        guild: discord.Guild,
        member: typing.Optional[discord.Member],
        form_data: typing.Any,
    ) -> discord.Message:
        channel_id = self._dash_required_id(form_data, "panel_channel_id")
        channel = guild.get_channel(channel_id)
        if not isinstance(channel, discord.TextChannel):
            raise commands.BadArgument("Reaction panel channel must be a text channel.")
        title = self._dash_value(form_data, "panel_title").strip()[:256]
        if not title:
            raise commands.BadArgument("Reaction panel title is required.")
        raw_bindings = self._dash_value(form_data, "panel_bindings").strip()
        parts = [part.strip() for part in raw_bindings.replace("\n", "|").split("|") if part.strip()]
        if not parts:
            raise commands.BadArgument("Add at least one `emoji;role` binding.")
        bindings: typing.List[typing.Tuple[str, discord.Role]] = []
        for part in parts:
            if ";" not in part:
                raise commands.BadArgument(f"`{part}` is missing `;` between emoji and role.")
            emoji, role_text = [piece.strip() for piece in part.split(";", 1)]
            role = self._find_role(guild, role_text)
            if not emoji or role is None:
                raise commands.BadArgument(f"Could not resolve reaction binding `{part}`.")
            self._dashboard_check_role_manageable(guild, role, member)
            bindings.append((emoji, role))
        if len(bindings) > 20:
            raise commands.BadArgument("Reaction panels are limited to 20 bindings.")

        embed = discord.Embed(
            title=title,
            description="\n".join(f"{emoji} - {role.mention}" for emoji, role in bindings),
            color=guild.me.color if guild.me else discord.Color.blurple(),
        )
        message = await channel.send(
            embed=embed,
            allowed_mentions=discord.AllowedMentions.none(),
        )
        record: typing.Dict[str, typing.Any] = {
            "channel_id": channel.id,
            "binds": {},
        }
        for emoji, role in bindings:
            try:
                await message.add_reaction(emoji)
            except discord.HTTPException as exc:
                try:
                    await message.delete()
                except discord.HTTPException:
                    pass
                raise commands.BadArgument(f"Discord rejected reaction `{emoji}`.") from exc
            record["binds"][self._emoji_key(emoji)] = {
                "role_id": role.id,
                "remove_on_unreact": True,
                "emoji": emoji,
            }
        async with self.config.guild(guild).react_roles() as react_roles:
            react_roles[str(message.id)] = record
        for role in {role for _emoji, role in bindings}:
            await self.config.role(role).self_assignable.set(True)
            await self.config.role(role).self_removable.set(True)
        self._reaction_message_cache.add(message.id)
        return message

    async def _dashboard_refresh_reaction_message(
        self,
        guild: discord.Guild,
        form_data: typing.Any,
    ) -> int:
        message_id = self._dash_required_id(form_data, "message_id")
        react_roles = await self.config.guild(guild).react_roles()
        data = react_roles.get(str(message_id))
        if not data:
            raise commands.BadArgument("That message has no configured reaction roles.")
        channel = guild.get_channel(int(data.get("channel_id", 0)))
        if not isinstance(channel, discord.TextChannel):
            raise commands.BadArgument("The configured reaction-role channel is missing.")
        try:
            message = await channel.fetch_message(message_id)
        except discord.HTTPException as exc:
            raise commands.BadArgument("The reaction-role message could not be fetched.") from exc
        refreshed = 0
        for bind in data.get("binds", {}).values():
            try:
                await message.add_reaction(bind.get("emoji"))
            except discord.HTTPException:
                continue
            refreshed += 1
        return refreshed

    async def _dashboard_cleanup_reaction_roles(self, guild: discord.Guild) -> int:
        removed = 0
        async with self.config.guild(guild).react_roles() as react_roles:
            for message_id, data in list(react_roles.items()):
                channel = guild.get_channel(int(data.get("channel_id", 0)))
                if not isinstance(channel, discord.TextChannel):
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
                    if guild.get_role(int(bind.get("role_id", 0))) is None:
                        del data["binds"][emoji_key]
                        removed += 1
                if not data.get("binds"):
                    del react_roles[message_id]
                    self._reaction_message_cache.discard(int(message_id))
        return removed

    async def _dashboard_bind_reaction_role(
        self,
        guild: discord.Guild,
        member: typing.Optional[discord.Member],
        form_data: typing.Any,
    ) -> discord.Message:
        channel_id = self._dash_required_id(form_data, "rr_channel_id")
        message_id = self._dash_required_id(form_data, "rr_message_id")
        emoji = self._dash_value(form_data, "rr_emoji").strip()
        if not emoji:
            raise commands.BadArgument("Emoji is required.")
        role = self._dashboard_role_from_form(guild, form_data, "rr_role_id")
        self._dashboard_check_role_manageable(guild, role, member)
        await self.config.role(role).self_assignable.set(True)
        if self._dash_bool(form_data, "rr_remove_on_unreact"):
            await self.config.role(role).self_removable.set(True)

        channel = guild.get_channel(channel_id)
        if not isinstance(channel, discord.TextChannel):
            raise commands.BadArgument("Reaction-role channel must be a text channel.")
        try:
            message = await channel.fetch_message(message_id)
        except discord.HTTPException as exc:
            raise commands.BadArgument("I could not fetch that message.") from exc

        emoji_key = self._emoji_key(emoji)
        async with self.config.guild(guild).react_roles() as react_roles:
            message_data = react_roles.setdefault(
                str(message.id),
                {"channel_id": channel.id, "binds": {}},
            )
            message_data["channel_id"] = channel.id
            message_data.setdefault("binds", {})[emoji_key] = {
                "role_id": role.id,
                "remove_on_unreact": self._dash_bool(form_data, "rr_remove_on_unreact"),
                "emoji": emoji,
            }
        self._reaction_message_cache.add(message.id)
        await message.add_reaction(emoji)
        return message

    async def _dashboard_delete_reaction_bind(
        self,
        guild: discord.Guild,
        form_data: typing.Any,
    ) -> int:
        message_id = self._dash_required_id(form_data, "message_id")
        emoji_key = self._dash_value(form_data, "emoji_key").strip()
        if not emoji_key:
            raise commands.BadArgument("Emoji key is required.")
        async with self.config.guild(guild).react_roles() as react_roles:
            message_data = react_roles.get(str(message_id))
            if not message_data or emoji_key not in message_data.get("binds", {}):
                raise commands.BadArgument("That reaction-role binding was not found.")
            del message_data["binds"][emoji_key]
            if not message_data["binds"]:
                del react_roles[str(message_id)]
                self._reaction_message_cache.discard(message_id)
        return message_id

    async def _dashboard_clear_reaction_message(
        self,
        guild: discord.Guild,
        form_data: typing.Any,
    ) -> int:
        message_id = self._dash_required_id(form_data, "message_id")
        async with self.config.guild(guild).react_roles() as react_roles:
            if str(message_id) not in react_roles:
                raise commands.BadArgument("That reaction-role message was not found.")
            del react_roles[str(message_id)]
        self._reaction_message_cache.discard(message_id)
        return message_id

    async def _dashboard_clear_temp_role(
        self,
        guild: discord.Guild,
        form_data: typing.Any,
    ) -> typing.Tuple[int, int]:
        member_id = self._dash_required_id(form_data, "member_id")
        role_id = self._dash_required_id(form_data, "role_id")
        async with self.config.guild(guild).temporary_roles() as temp_roles:
            temp_roles[:] = [
                item
                for item in temp_roles
                if not (
                    int(item.get("member_id", 0)) == member_id
                    and int(item.get("role_id", 0)) == role_id
                )
            ]
        return member_id, role_id

    async def _dashboard_create_button(
        self,
        guild: discord.Guild,
        member: typing.Optional[discord.Member],
        form_data: typing.Any,
    ) -> str:
        name = self._dash_value(form_data, "button_name").strip().lower()
        if not name or " " in name:
            raise commands.BadArgument("Button name cannot be empty or contain spaces.")
        role = self._dashboard_role_from_form(guild, form_data, "button_role_id")
        self._dashboard_check_role_manageable(guild, role, member)
        await self.config.role(role).self_assignable.set(True)
        await self.config.role(role).self_removable.set(True)
        data = {
            "role_id": role.id,
            "label": self._dash_value(form_data, "button_label", f"@{role.name}")[:80],
            "emoji": self._dash_value(form_data, "button_emoji").strip() or None,
            "style": self._button_style_value(
                self._dash_value(form_data, "button_style", "secondary")
            ),
            "messages": [],
        }
        old_role_id = None
        async with self.config.guild(guild).buttons() as buttons:
            old = buttons.get(name)
            if old:
                data["messages"] = list(old.get("messages", []))
                old_role_id = int(old.get("role_id", 0)) or None
            buttons[name] = data
        if old_role_id is not None and old_role_id != role.id:
            async with self.config.role_from_id(old_role_id).buttons() as role_buttons:
                if name in role_buttons:
                    role_buttons.remove(name)
        async with self.config.role(role).buttons() as role_buttons:
            if name not in role_buttons:
                role_buttons.append(name)
        await self._load_component_views()
        return name

    async def _dashboard_delete_button(
        self,
        guild: discord.Guild,
        form_data: typing.Any,
    ) -> str:
        name = self._dash_value(form_data, "button_name").strip().lower()
        async with self.config.guild(guild).buttons() as buttons:
            data = buttons.pop(name, None)
        if data is None:
            raise commands.BadArgument("Button was not found.")
        async with self.config.role_from_id(int(data["role_id"])).buttons() as role_buttons:
            if name in role_buttons:
                role_buttons.remove(name)
        await self._load_component_views()
        return name

    async def _dashboard_create_select_option(
        self,
        guild: discord.Guild,
        member: typing.Optional[discord.Member],
        form_data: typing.Any,
    ) -> str:
        name = self._dash_value(form_data, "option_name").strip().lower()
        if not name or " " in name:
            raise commands.BadArgument("Option name cannot be empty or contain spaces.")
        role = self._dashboard_role_from_form(guild, form_data, "option_role_id")
        self._dashboard_check_role_manageable(guild, role, member)
        await self.config.role(role).self_assignable.set(True)
        await self.config.role(role).self_removable.set(True)
        data = {
            "role_id": role.id,
            "emoji": self._dash_value(form_data, "option_emoji").strip() or None,
            "label": self._dash_value(form_data, "option_label", f"@{role.name}")[:100],
            "description": self._dash_value(form_data, "option_description")[:100],
        }
        old_role_id = None
        async with self.config.guild(guild).select_options() as options:
            old = options.get(name)
            if old:
                old_role_id = int(old.get("role_id", 0)) or None
            options[name] = data
        if old_role_id is not None and old_role_id != role.id:
            async with self.config.role_from_id(old_role_id).select_options() as role_options:
                if name in role_options:
                    role_options.remove(name)
        async with self.config.role(role).select_options() as role_options:
            if name not in role_options:
                role_options.append(name)
        await self._load_component_views()
        return name

    async def _dashboard_delete_select_option(
        self,
        guild: discord.Guild,
        form_data: typing.Any,
    ) -> str:
        name = self._dash_value(form_data, "option_name").strip().lower()
        async with self.config.guild(guild).select_options() as options:
            data = options.pop(name, None)
        if data is None:
            raise commands.BadArgument("Select option was not found.")
        async with self.config.guild(guild).select_menus() as menus:
            for menu in menus.values():
                if name in menu.get("options", []):
                    menu["options"].remove(name)
        async with self.config.role_from_id(int(data["role_id"])).select_options() as role_options:
            if name in role_options:
                role_options.remove(name)
        await self._load_component_views()
        return name

    async def _dashboard_create_select_menu(
        self,
        guild: discord.Guild,
        form_data: typing.Any,
    ) -> str:
        name = self._dash_value(form_data, "menu_name").strip().lower()
        if not name or " " in name:
            raise commands.BadArgument("Menu name cannot be empty or contain spaces.")
        option_names = self._parse_name_list(self._dash_value(form_data, "menu_options"))
        saved_options = await self.config.guild(guild).select_options()
        missing = [option for option in option_names if option not in saved_options]
        if missing:
            raise commands.BadArgument(f"Missing option(s): {', '.join(missing)}")
        if not option_names:
            raise commands.BadArgument("At least one option is required.")
        try:
            min_values = int(self._dash_value(form_data, "menu_min", "0") or 0)
            max_values = int(
                self._dash_value(form_data, "menu_max", str(len(option_names)))
                or len(option_names)
            )
        except ValueError as exc:
            raise commands.BadArgument("Menu min/max values must be whole numbers.") from exc
        min_values = max(0, min(min_values, 25))
        max_values = max(1, min(max_values, len(option_names), 25))
        min_values = min(min_values, max_values)
        data = {
            "options": option_names,
            "min_values": min_values,
            "max_values": max_values,
            "placeholder": self._dash_value(form_data, "menu_placeholder", "Pick roles")[:100],
            "messages": [],
        }
        async with self.config.guild(guild).select_menus() as menus:
            old = menus.get(name)
            if old:
                data["messages"] = list(old.get("messages", []))
            menus[name] = data
        await self._load_component_views()
        return name

    async def _dashboard_delete_select_menu(
        self,
        guild: discord.Guild,
        form_data: typing.Any,
    ) -> str:
        name = self._dash_value(form_data, "menu_name").strip().lower()
        async with self.config.guild(guild).select_menus() as menus:
            if menus.pop(name, None) is None:
                raise commands.BadArgument("Select menu was not found.")
        await self._load_component_views()
        return name

    async def _dashboard_send_component_message(
        self,
        guild: discord.Guild,
        form_data: typing.Any,
    ) -> discord.Message:
        channel_id = self._dash_required_id(form_data, "component_channel_id")
        channel = guild.get_channel(channel_id)
        if not isinstance(channel, discord.TextChannel):
            raise commands.BadArgument("Component message channel must be a text channel.")
        button_names = self._parse_name_list(self._dash_value(form_data, "component_buttons"))
        select_names = self._parse_name_list(self._dash_value(form_data, "component_selects"))
        view = await self._view_for_component_names(guild, button_names, select_names)
        content = self._dash_value(form_data, "component_text")[:2000] or None
        message = await channel.send(content=content, view=view)
        await self._save_component_message(guild, message, button_names, select_names)
        return message

    async def _dashboard_edit_component_message(
        self,
        guild: discord.Guild,
        form_data: typing.Any,
    ) -> discord.Message:
        channel_id = self._dash_required_id(form_data, "edit_component_channel_id")
        message_id = self._dash_required_id(form_data, "edit_component_message_id")
        channel = guild.get_channel(channel_id)
        if not isinstance(channel, discord.TextChannel):
            raise commands.BadArgument("Component message channel must be a text channel.")
        try:
            message = await channel.fetch_message(message_id)
        except discord.HTTPException as exc:
            raise commands.BadArgument("I could not fetch that component message.") from exc
        if guild.me is None or message.author.id != guild.me.id:
            raise commands.BadArgument("I can only edit my own messages.")
        button_names = self._parse_name_list(
            self._dash_value(form_data, "edit_component_buttons")
        )
        select_names = self._parse_name_list(
            self._dash_value(form_data, "edit_component_selects")
        )
        view = await self._view_for_component_names(guild, button_names, select_names)
        content_value = self._dash_value(form_data, "edit_component_text")
        kwargs: typing.Dict[str, typing.Any] = {"view": view}
        if self._dash_bool(form_data, "edit_component_content"):
            kwargs["content"] = content_value[:2000] or None
        await message.edit(**kwargs)
        await self._save_component_message(guild, message, button_names, select_names)
        return message

    async def _dashboard_cleanup_component_messages(self, guild: discord.Guild) -> int:
        button_count = await self._cleanup_component_messages(guild, "buttons")
        select_count = await self._cleanup_component_messages(guild, "select_menus")
        return button_count + select_count

    async def _dashboard_source(
        self,
        guild: discord.Guild,
        selected_role_id: typing.Optional[int],
        kwargs: typing.Dict[str, typing.Any],
    ) -> str:
        auto_roles = await self.config.guild(guild).auto_roles()
        react_roles = await self.config.guild(guild).react_roles()
        temp_roles = await self.config.guild(guild).temporary_roles()
        buttons = await self.config.guild(guild).buttons()
        select_options = await self.config.guild(guild).select_options()
        select_menus = await self.config.guild(guild).select_menus()
        role_rules = await self.config.guild(guild).role_rules()
        atomic = await self.config.guild(guild).atomic()
        csrf = self._dash_csrf(kwargs)
        active_tab = self._dashboard_active_tab(kwargs)

        role_stats = await self._dashboard_role_stats(guild)
        selected_role = guild.get_role(selected_role_id or 0)
        if selected_role is None:
            selected_role = next(
                (role for role in guild.roles if not role.is_default() and not role.managed),
                None,
            )
        selected_role_id = selected_role.id if selected_role else None
        reaction_bind_count = sum(
            len(message_data.get("binds", {})) for message_data in react_roles.values()
        )

        return f"""
        <style>
            .rmdash-wrap {{ max-width: 1180px; margin: 0 auto; color: #e5e7eb; }}
            .rmdash-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(260px, 1fr)); gap: 16px; }}
            .rmdash-row {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 12px; margin-bottom: 12px; }}
            .rmdash-card {{ background: #1f2937; border: 1px solid #374151; border-radius: 8px; padding: 16px; margin-bottom: 16px; }}
            .rmdash-card h2, .rmdash-card h3 {{ margin: 0 0 12px 0; color: #f9fafb; }}
            .rmdash-muted {{ color: #9ca3af; }}
            .rmdash-stat {{ font-size: 1.5rem; font-weight: 700; color: #f9fafb; }}
            .rmdash-field label {{ display: block; font-weight: 600; margin-bottom: 4px; color: #d1d5db; }}
            .rmdash-field input, .rmdash-field select {{
                width: 100%; box-sizing: border-box; border: 1px solid #4b5563; border-radius: 6px;
                background: #111827; color: #f9fafb; padding: 8px; min-height: 38px;
            }}
            .rmdash-field textarea {{
                width: 100%; box-sizing: border-box; border: 1px solid #4b5563; border-radius: 6px;
                background: #111827; color: #f9fafb; padding: 8px; min-height: 86px; resize: vertical;
            }}
            .rmdash-check {{ display: flex; align-items: center; gap: 8px; margin: 6px 0; color: #d1d5db; }}
            .rmdash-check input {{ width: auto; }}
            .rmdash-btn {{ background: #2563eb; color: white; border: 0; border-radius: 6px; padding: 9px 14px; cursor: pointer; font-weight: 700; }}
            .rmdash-btn.secondary {{ background: #4b5563; }}
            .rmdash-btn.danger {{ background: #dc2626; }}
            .rmdash-tabs {{
                display: flex; gap: 4px; overflow-x: auto; position: sticky; top: 0; z-index: 10;
                margin: 0 0 16px; padding: 5px; background: #111827; border: 1px solid #374151;
                border-radius: 8px; scrollbar-width: thin;
            }}
            .rmdash-tab {{
                flex: 0 0 auto; border: 0; border-radius: 6px; padding: 9px 13px;
                background: transparent; color: #9ca3af; cursor: pointer; font-weight: 700;
                white-space: nowrap;
            }}
            .rmdash-tab:hover {{ background: #1f2937; color: #f9fafb; }}
            .rmdash-tab.active {{ background: #2563eb; color: white; }}
            .rmdash-tab-panel {{ display: none; }}
            .rmdash-tab-panel.active {{ display: block; }}
            .rmdash-table {{ width: 100%; border-collapse: collapse; font-size: 0.92rem; }}
            .rmdash-table th, .rmdash-table td {{ border-bottom: 1px solid #374151; padding: 8px; text-align: left; vertical-align: top; }}
            .rmdash-table th {{ color: #d1d5db; }}
            .rmdash-inline {{ display: inline; }}
            .rmdash-actions {{ display: flex; gap: 8px; flex-wrap: wrap; margin-top: 10px; }}
            .rmdash-scroll {{ overflow-x: auto; }}
            .rmdash-card details {{ margin-top: 8px; }}
        </style>
        <div class="rmdash-wrap" data-rmdash-tabs="1">
            <div class="rmdash-card">
                <h2>RoleManager Dashboard</h2>
                <div class="rmdash-grid">
                    <div><div class="rmdash-muted">Self Roles</div><div class="rmdash-stat">{role_stats["self_roles"]}</div></div>
                    <div><div class="rmdash-muted">Sticky Roles</div><div class="rmdash-stat">{role_stats["sticky_roles"]}</div></div>
                    <div><div class="rmdash-muted">Default Temp Roles</div><div class="rmdash-stat">{role_stats["temp_roles"]}</div></div>
                    <div><div class="rmdash-muted">Reaction Bindings</div><div class="rmdash-stat">{reaction_bind_count}</div></div>
                    <div><div class="rmdash-muted">Buttons</div><div class="rmdash-stat">{len(buttons)}</div></div>
                    <div><div class="rmdash-muted">Select Menus</div><div class="rmdash-stat">{len(select_menus)}</div></div>
                    <div><div class="rmdash-muted">Pending Temp Roles</div><div class="rmdash-stat">{len(temp_roles)}</div></div>
                    <div><div class="rmdash-muted">Role Rules</div><div class="rmdash-stat">{len(role_rules)}</div></div>
                </div>
            </div>
            <div class="rmdash-tabs" role="tablist" aria-label="RoleManager sections">
                {self._dashboard_tab_button("overview", "Overview", active_tab)}
                {self._dashboard_tab_button("roles", "Role Setup", active_tab)}
                {self._dashboard_tab_button("members", "Member Operations", active_tab)}
                {self._dashboard_tab_button("panels", "Role Panels", active_tab)}
                {self._dashboard_tab_button("data", "Data & Imports", active_tab)}
            </div>
            <section class="rmdash-tab-panel{self._dashboard_active_class("overview", active_tab)}" data-tab-panel="overview" id="rmdash-panel-overview" role="tabpanel">
                {self._dashboard_guild_settings_section(guild, atomic, csrf)}
                {await self._dashboard_policy_overview_section(guild)}
            </section>
            <section class="rmdash-tab-panel{self._dashboard_active_class("roles", active_tab)}" data-tab-panel="roles" id="rmdash-panel-roles" role="tabpanel">
                {await self._dashboard_role_settings_section(guild, selected_role, csrf)}
                {self._dashboard_role_rules_section(guild, role_rules, csrf)}
                {self._dashboard_autoroles_section(guild, auto_roles, csrf)}
            </section>
            <section class="rmdash-tab-panel{self._dashboard_active_class("members", active_tab)}" data-tab-panel="members" id="rmdash-panel-members" role="tabpanel">
                {self._dashboard_role_operations_section(guild, csrf)}
                {self._dashboard_sticky_section(guild, csrf)}
                {self._dashboard_temporary_roles_section(guild, temp_roles, csrf)}
            </section>
            <section class="rmdash-tab-panel{self._dashboard_active_class("panels", active_tab)}" data-tab-panel="panels" id="rmdash-panel-panels" role="tabpanel">
                {self._dashboard_reaction_roles_section(guild, react_roles, csrf)}
                {self._dashboard_components_section(guild, buttons, select_options, select_menus, csrf)}
            </section>
            <section class="rmdash-tab-panel{self._dashboard_active_class("data", active_tab)}" data-tab-panel="data" id="rmdash-panel-data" role="tabpanel">
                {self._dashboard_import_section(csrf)}
            </section>
            {self._dashboard_tabs_script()}
        </div>
        """

    @staticmethod
    def _dashboard_active_class(tab: str, active_tab: str) -> str:
        return " active" if tab == active_tab else ""

    def _dashboard_tab_button(self, tab: str, label: str, active_tab: str) -> str:
        active = tab == active_tab
        active_class = " active" if active else ""
        return (
            f'<button type="button" class="rmdash-tab{active_class}" role="tab" '
            f'id="rmdash-tab-{self._h(tab)}" data-tab="{self._h(tab)}" '
            f'aria-controls="rmdash-panel-{self._h(tab)}" '
            f'aria-selected="{str(active).lower()}" tabindex="{0 if active else -1}">'
            f"{self._h(label)}</button>"
        )

    @staticmethod
    def _dashboard_tabs_script() -> str:
        return """
        <script>
        (() => {
            const script = document.currentScript;
            const root = script ? script.closest(".rmdash-wrap") : null;
            if (!root) return;

            const tabs = Array.from(root.querySelectorAll("[data-tab]"));
            const panels = Array.from(root.querySelectorAll("[data-tab-panel]"));
            const validTabs = new Set(tabs.map((tab) => tab.dataset.tab));
            const sectionTabs = {
                "guild-settings": "overview",
                "policy-overview": "overview",
                "role-settings": "roles",
                "role-rules": "roles",
                "autoroles": "roles",
                "role-operations": "members",
                "sticky-roles": "members",
                "temporary-roles": "members",
                "reaction-roles": "panels",
                "components": "panels",
                "imports": "data",
            };

            const activate = (name, updateHash = false) => {
                if (!validTabs.has(name)) return;
                tabs.forEach((tab) => {
                    const selected = tab.dataset.tab === name;
                    tab.classList.toggle("active", selected);
                    tab.setAttribute("aria-selected", selected ? "true" : "false");
                    tab.tabIndex = selected ? 0 : -1;
                });
                panels.forEach((panel) => {
                    const selected = panel.dataset.tabPanel === name;
                    panel.classList.toggle("active", selected);
                    panel.hidden = !selected;
                });
                if (updateHash && window.history && window.history.replaceState) {
                    window.history.replaceState(null, "", `#rm-${name}`);
                }
            };

            const tabFromHash = () => {
                const hash = window.location.hash.slice(1);
                if (hash.startsWith("rm-") && validTabs.has(hash.slice(3))) {
                    return hash.slice(3);
                }
                return sectionTabs[hash] || null;
            };

            tabs.forEach((tab, index) => {
                tab.addEventListener("click", () => activate(tab.dataset.tab, true));
                tab.addEventListener("keydown", (event) => {
                    let nextIndex = null;
                    if (event.key === "ArrowRight") nextIndex = (index + 1) % tabs.length;
                    if (event.key === "ArrowLeft") nextIndex = (index - 1 + tabs.length) % tabs.length;
                    if (event.key === "Home") nextIndex = 0;
                    if (event.key === "End") nextIndex = tabs.length - 1;
                    if (nextIndex === null) return;
                    event.preventDefault();
                    tabs[nextIndex].focus();
                    activate(tabs[nextIndex].dataset.tab, true);
                });
            });

            root.querySelectorAll("form").forEach((form) => {
                form.addEventListener("submit", () => {
                    const active = root.querySelector("[data-tab].active");
                    if (!active) return;
                    let input = form.querySelector('input[name="active_tab"]');
                    if (!input) {
                        input = document.createElement("input");
                        input.type = "hidden";
                        input.name = "active_tab";
                        form.appendChild(input);
                    }
                    input.value = active.dataset.tab;
                });
            });

            const initial = tabFromHash();
            const selected = root.querySelector("[data-tab].active");
            activate(initial || (selected ? selected.dataset.tab : "overview"));
            window.addEventListener("hashchange", () => {
                const requested = tabFromHash();
                if (requested) activate(requested);
            });
        })();
        </script>
        """

    def _dashboard_guild_settings_section(
        self,
        guild: discord.Guild,
        atomic: typing.Optional[bool],
        csrf: str,
    ) -> str:
        selected_atomic = "inherit" if atomic is None else str(bool(atomic)).lower()
        atomic_select = self._select(
            "atomic",
            "Atomic Assignment",
            [
                ("inherit", "Use global default"),
                ("true", "Enabled"),
                ("false", "Disabled"),
            ],
            selected_atomic,
        )
        return f"""
        <div id="guild-settings" class="rmdash-card">
            <h3>Guild Settings & Role Creation</h3>
            <div class="rmdash-grid">
                <form method="POST">
                    {csrf}
                    <input type="hidden" name="action" value="save_guild_settings">
                    {atomic_select}
                    <button class="rmdash-btn" type="submit">Save Guild Settings</button>
                </form>
                <form method="POST">
                    {csrf}
                    <input type="hidden" name="action" value="create_role">
                    {self._input("new_role_name", "Role Name", "")}
                    {self._input("new_role_color", "Role Color (hex)", "5865F2")}
                    {self._checkbox("new_role_hoist", "Display role members separately", False)}
                    {self._checkbox("new_role_mentionable", "Allow everyone to mention role", False)}
                    <button class="rmdash-btn" type="submit">Create Role</button>
                </form>
            </div>
        </div>
        """

    async def _dashboard_policy_overview_section(self, guild: discord.Guild) -> str:
        rows = []
        for role in sorted(guild.roles, key=lambda item: item.position, reverse=True):
            if role.is_default():
                continue
            config = await self.config.role(role).all()
            if not any(
                [
                    config.get("self_assignable"),
                    config.get("self_removable"),
                    config.get("sticky"),
                    config.get("temp_duration"),
                    config.get("required"),
                    config.get("inclusive_with"),
                    config.get("exclusive_to"),
                    config.get("cost"),
                ]
            ):
                continue
            flags = []
            if config.get("self_assignable"):
                flags.append("self-add")
            if config.get("self_removable"):
                flags.append("self-remove")
            if config.get("sticky"):
                flags.append("sticky")
            if config.get("temp_duration"):
                flags.append("temp")
            rows.append(
                "<tr>"
                f"<td>{self._h(role.name)}</td>"
                f"<td>{self._h(', '.join(flags) or 'policy only')}</td>"
                f"<td>{int(config.get('cost') or 0):,}</td>"
                f"<td>{self._h(self._dashboard_role_names(guild, config.get('required') or []))}</td>"
                f"<td>{self._h(self._dashboard_role_names(guild, config.get('inclusive_with') or []))}</td>"
                f"<td>{self._h(self._dashboard_role_names(guild, config.get('exclusive_to') or []))}</td>"
                "</tr>"
            )
        table = (
            '<p class="rmdash-muted">No role policies configured.</p>'
            if not rows
            else '<div class="rmdash-scroll"><table class="rmdash-table"><thead><tr>'
            '<th>Role</th><th>Flags</th><th>Cost</th><th>Required</th><th>Includes</th>'
            f'<th>Excludes</th></tr></thead><tbody>{"".join(rows)}</tbody></table></div>'
        )
        return f"""
        <div id="policy-overview" class="rmdash-card">
            <h3>Configured Role Policies</h3>
            {table}
        </div>
        """

    def _dashboard_role_rules_section(
        self,
        guild: discord.Guild,
        rules: typing.Dict[str, typing.Dict[str, typing.Any]],
        csrf: str,
    ) -> str:
        rows = []
        editors = []
        for name, rule in sorted(rules.items()):
            trigger = guild.get_role(int(rule.get("trigger_role_id", 0)))
            trigger_name = trigger.name if trigger else "Missing role"
            add_names = self._dashboard_role_names(guild, rule.get("add_role_ids", []))
            remove_names = self._dashboard_role_names(guild, rule.get("remove_role_ids", []))
            rows.append(
                "<tr>"
                f"<td>{self._h(name)}</td><td>{self._h(bool(rule.get('enabled', True)))}</td>"
                f"<td>{self._h(rule.get('trigger_event', 'add'))} {self._h(trigger_name)}</td>"
                f"<td>{self._h(add_names)}</td><td>{self._h(remove_names)}</td>"
                "<td>"
                '<form method="POST" class="rmdash-inline">'
                f"{csrf}"
                '<input type="hidden" name="action" value="delete_role_rule">'
                f'<input type="hidden" name="rule_name" value="{self._h(name)}">'
                '<button class="rmdash-btn danger" type="submit">Delete</button>'
                "</form></td></tr>"
            )
            editors.append(
                f"""
                <details>
                    <summary>Edit {self._h(name)}</summary>
                    <form method="POST">
                        {csrf}
                        <input type="hidden" name="action" value="save_role_rule">
                        <input type="hidden" name="rule_name" value="{self._h(name)}">
                        <div class="rmdash-row">
                            {self._select("rule_event", "Trigger Event", [("add", "Role added"), ("remove", "Role removed")], rule.get("trigger_event", "add"))}
                            {self._role_select(guild, "rule_trigger_role_id", "Trigger Role", rule.get("trigger_role_id"))}
                        </div>
                        {self._checkbox("rule_enabled", "Rule enabled", rule.get("enabled", True))}
                        <div class="rmdash-grid">
                            {self._multi_role_select(guild, "rule_add_roles", "Roles To Add", rule.get("add_role_ids", []))}
                            {self._multi_role_select(guild, "rule_remove_roles", "Roles To Remove", rule.get("remove_role_ids", []))}
                        </div>
                        <button class="rmdash-btn" type="submit">Save Rule</button>
                    </form>
                </details>
                """
            )
        table = (
            '<p class="rmdash-muted">No role-change rules configured.</p>'
            if not rows
            else '<div class="rmdash-scroll"><table class="rmdash-table"><thead><tr>'
            '<th>Name</th><th>Enabled</th><th>Trigger</th><th>Add</th><th>Remove</th><th></th>'
            f'</tr></thead><tbody>{"".join(rows)}</tbody></table></div>'
        )
        return f"""
        <div id="role-rules" class="rmdash-card">
            <h3>Role-Change Rules</h3>
            <form method="POST">
                {csrf}
                <input type="hidden" name="action" value="save_role_rule">
                <div class="rmdash-row">
                    {self._input("rule_name", "Rule Name", "")}
                    {self._select("rule_event", "Trigger Event", [("add", "Role added"), ("remove", "Role removed")], "add")}
                    {self._role_select(guild, "rule_trigger_role_id", "Trigger Role", None)}
                </div>
                {self._checkbox("rule_enabled", "Rule enabled", True)}
                <div class="rmdash-grid">
                    {self._multi_role_select(guild, "rule_add_roles", "Roles To Add", [])}
                    {self._multi_role_select(guild, "rule_remove_roles", "Roles To Remove", [])}
                </div>
                <button class="rmdash-btn" type="submit">Save Rule</button>
            </form>
            {table}
            {"".join(editors)}
        </div>
        """

    def _dashboard_role_operations_section(self, guild: discord.Guild, csrf: str) -> str:
        return f"""
        <div id="role-operations" class="rmdash-card">
            <h3>Role Operations</h3>
            <form method="POST">
                {csrf}
                <input type="hidden" name="action" value="role_operation">
                <div class="rmdash-row">
                    {self._select("operation", "Operation", [("add", "Add role"), ("remove", "Remove role")], "add")}
                    {self._role_select(guild, "operation_role_id", "Role", None)}
                    {self._select("operation_target_type", "Target Type", [("member", "Member ID"), ("role", "Members with role ID"), ("channel", "Members in channel ID"), ("everyone", "Everyone"), ("humans", "Humans"), ("bots", "Bots")], "member")}
                    {self._input("operation_target_id", "Target ID (when required)", "")}
                </div>
                {self._checkbox("operation_dry_run", "Preview only", True)}
                {self._checkbox("confirm_role_operation", "Confirm live role changes", False)}
                <button class="rmdash-btn" type="submit">Run Role Operation</button>
            </form>
        </div>
        """

    def _dashboard_sticky_section(self, guild: discord.Guild, csrf: str) -> str:
        return f"""
        <div id="sticky-roles" class="rmdash-card">
            <h3>Member Sticky Roles</h3>
            <form method="POST">
                {csrf}
                <input type="hidden" name="action" value="sticky_member_action">
                <div class="rmdash-row">
                    {self._select("sticky_operation", "Operation", [("add", "Add and remember"), ("remove", "Remove and forget"), ("forget", "Forget departed user")], "add")}
                    {self._input("sticky_member_id", "Member or User ID", "")}
                    {self._role_select(guild, "sticky_role_id", "Sticky Role", None)}
                </div>
                <button class="rmdash-btn" type="submit">Apply Sticky Role Action</button>
            </form>
        </div>
        """

    def _dashboard_import_section(self, csrf: str) -> str:
        return f"""
        <div id="imports" class="rmdash-card">
            <h3>Import Existing Cog Settings</h3>
            <form method="POST">
                {csrf}
                <input type="hidden" name="action" value="import_settings">
                {self._select("import_source", "Source Cog", [("roletools", "Trusty RoleTools"), ("roleutils", "Seina RoleUtils")], "roletools")}
                {self._checkbox("confirm_import", "Confirm replacing compatible RoleManager settings", False)}
                <button class="rmdash-btn danger" type="submit">Import Settings</button>
            </form>
        </div>
        """

    async def _dashboard_role_stats(self, guild: discord.Guild) -> typing.Dict[str, int]:
        stats = {"self_roles": 0, "sticky_roles": 0, "temp_roles": 0}
        for role in guild.roles:
            if role.is_default():
                continue
            if await self.config.role(role).self_assignable():
                stats["self_roles"] += 1
            if await self.config.role(role).sticky():
                stats["sticky_roles"] += 1
            if await self.config.role(role).temp_duration():
                stats["temp_roles"] += 1
        return stats

    async def _dashboard_role_settings_section(
        self,
        guild: discord.Guild,
        selected_role: typing.Optional[discord.Role],
        csrf: str,
    ) -> str:
        role_id = selected_role.id if selected_role else ""
        role_select = self._role_select(guild, "selected_role_id", "Selected Role", role_id)
        if selected_role is None:
            settings = '<p class="rmdash-muted">No editable roles found.</p>'
        else:
            config = await self.config.role(selected_role).all()
            self_assignable = await self.config.role(selected_role).self_assignable()
            self_removable = await self.config.role(selected_role).self_removable()
            sticky = await self.config.role(selected_role).sticky()
            temp_duration = await self.config.role(selected_role).temp_duration()
            duration_text = self._dashboard_duration_value(temp_duration)
            settings = f"""
            <form method="POST">
                {csrf}
                <input type="hidden" name="role_id" value="{self._h(role_id)}">
                <div class="rmdash-row">
                    {self._input("role_name", "Role Name", selected_role.name)}
                    {self._input("role_color", "Role Color (hex)", f"{selected_role.color.value:06X}")}
                    {self._input("temp_duration", "Default Temp Duration", duration_text)}
                    {self._input("cost", "Credit Cost", config.get("cost") or 0)}
                </div>
                {self._checkbox("role_hoist", "Display role members separately", selected_role.hoist)}
                {self._checkbox("role_mentionable", "Allow everyone to mention role", selected_role.mentionable)}
                {self._checkbox("self_assignable", "Members can add this role with selfrole", self_assignable)}
                {self._checkbox("self_removable", "Members can remove this role with selfrole", self_removable)}
                {self._checkbox("sticky", "Restore this role when members rejoin", sticky)}
                {self._checkbox("require_any", "Require any prerequisite instead of all prerequisites", config.get("require_any"))}
                <div class="rmdash-grid">
                    {self._multi_role_select(guild, "required_roles", "Required Roles", config.get("required") or [])}
                    {self._multi_role_select(guild, "inclusive_roles", "Inclusive Roles", config.get("inclusive_with") or [])}
                    {self._multi_role_select(guild, "exclusive_roles", "Exclusive Roles", config.get("exclusive_to") or [])}
                </div>
                <div class="rmdash-actions">
                    <button class="rmdash-btn" name="action" value="save_role_flags" type="submit">Save Role Settings</button>
                    <button class="rmdash-btn secondary" name="action" value="make_inclusive_mutual" type="submit">Make Includes Mutual</button>
                    <button class="rmdash-btn secondary" name="action" value="make_exclusive_mutual" type="submit">Make Excludes Mutual</button>
                </div>
            </form>
            """
        return f"""
        <div id="role-settings" class="rmdash-card">
            <h3>Role Settings</h3>
            <form method="POST">
                {csrf}
                <input type="hidden" name="action" value="select_role">
                {role_select}
                <button class="rmdash-btn secondary" type="submit">Load Role</button>
            </form>
            {settings}
        </div>
        """

    def _dashboard_autoroles_section(
        self,
        guild: discord.Guild,
        settings: typing.Dict[str, typing.Any],
        csrf: str,
    ) -> str:
        return f"""
        <div id="autoroles" class="rmdash-card">
            <h3>Autoroles</h3>
            <form method="POST">
                {csrf}
                <input type="hidden" name="action" value="save_autoroles">
                {self._checkbox("autoroles_enabled", "Enable autoroles", settings.get("enabled"))}
                <div class="rmdash-grid">
                    {self._multi_role_select(guild, "auto_all", "All New Members", settings.get("all", []))}
                    {self._multi_role_select(guild, "auto_humans", "Humans Only", settings.get("humans", []))}
                    {self._multi_role_select(guild, "auto_bots", "Bots Only", settings.get("bots", []))}
                </div>
                <button class="rmdash-btn" type="submit">Save Autoroles</button>
            </form>
        </div>
        """

    def _dashboard_reaction_roles_section(
        self,
        guild: discord.Guild,
        react_roles: typing.Dict[str, typing.Dict[str, typing.Any]],
        csrf: str,
    ) -> str:
        rows = []
        for message_id, message_data in sorted(react_roles.items()):
            channel = guild.get_channel(int(message_data.get("channel_id", 0)))
            channel_label = f"#{channel.name}" if channel else "Missing channel"
            jump_url = (
                f"https://discord.com/channels/{guild.id}/{message_data.get('channel_id')}/{message_id}"
            )
            for emoji_key, bind in sorted(message_data.get("binds", {}).items()):
                role = guild.get_role(int(bind.get("role_id", 0)))
                role_label = role.name if role else f"Missing role {bind.get('role_id')}"
                rows.append(
                    "<tr>"
                    f'<td><a href="{self._h(jump_url)}">{self._h(message_id)}</a></td>'
                    f"<td>{self._h(channel_label)}</td>"
                    f"<td>{self._h(bind.get('emoji') or emoji_key)}</td>"
                    f"<td>{self._h(role_label)}</td>"
                    f"<td>{self._h(bind.get('remove_on_unreact', True))}</td>"
                    "<td>"
                    '<form method="POST" class="rmdash-inline">'
                    f"{csrf}"
                    '<input type="hidden" name="action" value="delete_reaction_bind">'
                    f'<input type="hidden" name="message_id" value="{self._h(message_id)}">'
                    f'<input type="hidden" name="emoji_key" value="{self._h(emoji_key)}">'
                    '<button class="rmdash-btn danger" type="submit">Remove</button>'
                    "</form>"
                    "</td>"
                    "</tr>"
                )
            rows.append(
                "<tr>"
                f"<td colspan=\"5\" class=\"rmdash-muted\">Clear all bindings for message {self._h(message_id)}</td>"
                "<td>"
                '<form method="POST" class="rmdash-inline">'
                f"{csrf}"
                '<input type="hidden" name="action" value="refresh_reaction_message">'
                f'<input type="hidden" name="message_id" value="{self._h(message_id)}">'
                '<button class="rmdash-btn secondary" type="submit">Refresh</button>'
                "</form> "
                '<form method="POST" class="rmdash-inline">'
                f"{csrf}"
                '<input type="hidden" name="action" value="clear_reaction_message">'
                f'<input type="hidden" name="message_id" value="{self._h(message_id)}">'
                '<button class="rmdash-btn danger" type="submit">Clear Message</button>'
                "</form>"
                "</td>"
                "</tr>"
            )
        table = (
            '<p class="rmdash-muted">No reaction roles configured.</p>'
            if not rows
            else '<div class="rmdash-scroll"><table class="rmdash-table"><thead><tr><th>Message</th><th>Channel</th>'
            '<th>Emoji</th><th>Role</th><th>Remove On Unreact</th><th>Actions</th>'
            f'</tr></thead><tbody>{"".join(rows)}</tbody></table></div>'
        )
        return f"""
        <div id="reaction-roles" class="rmdash-card">
            <h3>Reaction Roles</h3>
            <div class="rmdash-grid">
                <form method="POST">
                    {csrf}
                    <input type="hidden" name="action" value="bind_reaction_role">
                    {self._text_channel_select(guild, "rr_channel_id", "Existing Message Channel", None)}
                    {self._input("rr_message_id", "Existing Message ID", "")}
                    {self._input("rr_emoji", "Emoji", "")}
                    {self._role_select(guild, "rr_role_id", "Role", None)}
                    {self._checkbox("rr_remove_on_unreact", "Remove role when reaction is removed", True)}
                    <button class="rmdash-btn" type="submit">Bind Reaction Role</button>
                </form>
                <form method="POST">
                    {csrf}
                    <input type="hidden" name="action" value="create_reaction_panel">
                    {self._text_channel_select(guild, "panel_channel_id", "New Panel Channel", None)}
                    {self._input("panel_title", "Panel Title", "Pick your roles")}
                    {self._textarea("panel_bindings", "Bindings (one emoji;role per line)", "")}
                    <button class="rmdash-btn" type="submit">Create Reaction Panel</button>
                </form>
            </div>
            <form method="POST" class="rmdash-actions">
                {csrf}
                <input type="hidden" name="action" value="cleanup_reaction_roles">
                <button class="rmdash-btn secondary" type="submit">Clean Stale Reaction Records</button>
            </form>
            {table}
        </div>
        """

    def _dashboard_temporary_roles_section(
        self,
        guild: discord.Guild,
        temp_roles: typing.List[typing.Dict[str, typing.Any]],
        csrf: str,
    ) -> str:
        rows = []
        for item in sorted(temp_roles, key=lambda data: float(data.get("expires_at", 0))):
            member_id = int(item.get("member_id", 0))
            role_id = int(item.get("role_id", 0))
            member = guild.get_member(member_id)
            role = guild.get_role(role_id)
            rows.append(
                "<tr>"
                f"<td>{self._h(member.display_name if member else member_id)}</td>"
                f"<td>{self._h(role.name if role else role_id)}</td>"
                f"<td>{self._h(self._dashboard_time(item.get('expires_at')))}</td>"
                "<td>"
                '<form method="POST" class="rmdash-inline">'
                f"{csrf}"
                '<input type="hidden" name="action" value="clear_temp_role">'
                f'<input type="hidden" name="member_id" value="{self._h(member_id)}">'
                f'<input type="hidden" name="role_id" value="{self._h(role_id)}">'
                '<button class="rmdash-btn danger" type="submit">Clear Tracking</button>'
                "</form>"
                "</td>"
                "</tr>"
            )
        table = (
            '<p class="rmdash-muted">No temporary roles are pending.</p>'
            if not rows
            else '<table class="rmdash-table"><thead><tr><th>Member</th><th>Role</th>'
            f'<th>Expires</th><th>Actions</th></tr></thead><tbody>{"".join(rows)}</tbody></table>'
        )
        return f"""
        <div id="temporary-roles" class="rmdash-card">
            <h3>Temporary Roles</h3>
            <form method="POST">
                {csrf}
                <input type="hidden" name="action" value="give_temp_role">
                <div class="rmdash-row">
                    {self._input("temp_member_id", "Member ID", "")}
                    {self._role_select(guild, "temp_role_id", "Role", None)}
                    {self._input("temp_give_duration", "Duration", "7d")}
                </div>
                <button class="rmdash-btn" type="submit">Give Temporary Role</button>
            </form>
            {table}
        </div>
        """

    def _dashboard_components_section(
        self,
        guild: discord.Guild,
        buttons: typing.Dict[str, typing.Dict[str, typing.Any]],
        select_options: typing.Dict[str, typing.Dict[str, typing.Any]],
        select_menus: typing.Dict[str, typing.Dict[str, typing.Any]],
        csrf: str,
    ) -> str:
        button_rows = []
        button_editors = []
        for name, data in sorted(buttons.items()):
            role = guild.get_role(int(data.get("role_id", 0)))
            button_rows.append(
                "<tr>"
                f"<td>{self._h(name)}</td>"
                f"<td>{self._h(role.name if role else 'Missing role')}</td>"
                f"<td>{self._h(data.get('label'))}</td>"
                f"<td>{len(data.get('messages', [])):,}</td>"
                "<td>"
                '<form method="POST" class="rmdash-inline">'
                f"{csrf}"
                '<input type="hidden" name="action" value="delete_button">'
                f'<input type="hidden" name="button_name" value="{self._h(name)}">'
                '<button class="rmdash-btn danger" type="submit">Delete</button>'
                "</form>"
                "</td>"
                "</tr>"
            )
            style_name = {
                discord.ButtonStyle.primary.value: "primary",
                discord.ButtonStyle.secondary.value: "secondary",
                discord.ButtonStyle.success.value: "success",
                discord.ButtonStyle.danger.value: "danger",
            }.get(int(data.get("style") or discord.ButtonStyle.secondary.value), "secondary")
            button_editors.append(
                f"""
                <details><summary>Edit button {self._h(name)}</summary>
                    <form method="POST">
                        {csrf}
                        <input type="hidden" name="action" value="create_button">
                        <input type="hidden" name="button_name" value="{self._h(name)}">
                        <div class="rmdash-row">
                            {self._role_select(guild, "button_role_id", "Button Role", data.get("role_id"))}
                            {self._input("button_label", "Label", data.get("label") or "")}
                            {self._input("button_emoji", "Emoji", data.get("emoji") or "")}
                            {self._select("button_style", "Style", [("primary", "Primary"), ("secondary", "Secondary"), ("success", "Success"), ("danger", "Danger")], style_name)}
                        </div>
                        <button class="rmdash-btn" type="submit">Save Button</button>
                    </form>
                </details>
                """
            )
        buttons_table = (
            '<p class="rmdash-muted">No buttons configured.</p>'
            if not button_rows
            else '<table class="rmdash-table"><thead><tr><th>Name</th><th>Role</th>'
            f'<th>Label</th><th>Messages</th><th></th></tr></thead><tbody>{"".join(button_rows)}</tbody></table>'
        )

        option_rows = []
        option_editors = []
        for name, data in sorted(select_options.items()):
            role = guild.get_role(int(data.get("role_id", 0)))
            option_rows.append(
                "<tr>"
                f"<td>{self._h(name)}</td>"
                f"<td>{self._h(role.name if role else 'Missing role')}</td>"
                f"<td>{self._h(data.get('label'))}</td>"
                "<td>"
                '<form method="POST" class="rmdash-inline">'
                f"{csrf}"
                '<input type="hidden" name="action" value="delete_select_option">'
                f'<input type="hidden" name="option_name" value="{self._h(name)}">'
                '<button class="rmdash-btn danger" type="submit">Delete</button>'
                "</form>"
                "</td>"
                "</tr>"
            )
            option_editors.append(
                f"""
                <details><summary>Edit option {self._h(name)}</summary>
                    <form method="POST">
                        {csrf}
                        <input type="hidden" name="action" value="create_select_option">
                        <input type="hidden" name="option_name" value="{self._h(name)}">
                        <div class="rmdash-row">
                            {self._role_select(guild, "option_role_id", "Option Role", data.get("role_id"))}
                            {self._input("option_emoji", "Emoji", data.get("emoji") or "")}
                            {self._input("option_label", "Label", data.get("label") or "")}
                            {self._input("option_description", "Description", data.get("description") or "")}
                        </div>
                        <button class="rmdash-btn" type="submit">Save Option</button>
                    </form>
                </details>
                """
            )
        options_table = (
            '<p class="rmdash-muted">No select options configured.</p>'
            if not option_rows
            else '<table class="rmdash-table"><thead><tr><th>Name</th><th>Role</th>'
            f'<th>Label</th><th></th></tr></thead><tbody>{"".join(option_rows)}</tbody></table>'
        )

        menu_rows = []
        menu_editors = []
        for name, data in sorted(select_menus.items()):
            menu_rows.append(
                "<tr>"
                f"<td>{self._h(name)}</td>"
                f"<td>{self._h(', '.join(data.get('options', [])))}</td>"
                f"<td>{len(data.get('messages', [])):,}</td>"
                "<td>"
                '<form method="POST" class="rmdash-inline">'
                f"{csrf}"
                '<input type="hidden" name="action" value="delete_select_menu">'
                f'<input type="hidden" name="menu_name" value="{self._h(name)}">'
                '<button class="rmdash-btn danger" type="submit">Delete</button>'
                "</form>"
                "</td>"
                "</tr>"
            )
            menu_editors.append(
                f"""
                <details><summary>Edit menu {self._h(name)}</summary>
                    <form method="POST">
                        {csrf}
                        <input type="hidden" name="action" value="create_select_menu">
                        <input type="hidden" name="menu_name" value="{self._h(name)}">
                        <div class="rmdash-row">
                            {self._input("menu_options", "Option Names, comma separated", ", ".join(data.get("options", [])))}
                            {self._input("menu_min", "Min Values", data.get("min_values", 0))}
                            {self._input("menu_max", "Max Values", data.get("max_values", 1))}
                            {self._input("menu_placeholder", "Placeholder", data.get("placeholder") or "Pick roles")}
                        </div>
                        <button class="rmdash-btn" type="submit">Save Menu</button>
                    </form>
                </details>
                """
            )
        menus_table = (
            '<p class="rmdash-muted">No select menus configured.</p>'
            if not menu_rows
            else '<table class="rmdash-table"><thead><tr><th>Name</th><th>Options</th>'
            f'<th>Messages</th><th></th></tr></thead><tbody>{"".join(menu_rows)}</tbody></table>'
        )

        return f"""
        <div id="components" class="rmdash-card">
            <h3>Buttons & Select Menus</h3>
            <div class="rmdash-grid">
                <form method="POST">
                    {csrf}
                    <input type="hidden" name="action" value="create_button">
                    {self._input("button_name", "Button Name", "")}
                    {self._role_select(guild, "button_role_id", "Button Role", None)}
                    {self._input("button_label", "Label", "")}
                    {self._input("button_emoji", "Emoji", "")}
                    {self._select("button_style", "Style", [("primary", "Primary"), ("secondary", "Secondary"), ("success", "Success"), ("danger", "Danger")], "secondary")}
                    <button class="rmdash-btn" type="submit">Save Button</button>
                </form>
                <form method="POST">
                    {csrf}
                    <input type="hidden" name="action" value="create_select_option">
                    {self._input("option_name", "Option Name", "")}
                    {self._role_select(guild, "option_role_id", "Option Role", None)}
                    {self._input("option_emoji", "Emoji", "")}
                    {self._input("option_label", "Label", "")}
                    {self._input("option_description", "Description", "")}
                    <button class="rmdash-btn" type="submit">Save Option</button>
                </form>
                <form method="POST">
                    {csrf}
                    <input type="hidden" name="action" value="create_select_menu">
                    {self._input("menu_name", "Menu Name", "")}
                    {self._input("menu_options", "Option Names, comma separated", "")}
                    {self._input("menu_min", "Min Values", "0")}
                    {self._input("menu_max", "Max Values", "")}
                    {self._input("menu_placeholder", "Placeholder", "Pick roles")}
                    <button class="rmdash-btn" type="submit">Save Menu</button>
                </form>
                <form method="POST">
                    {csrf}
                    <input type="hidden" name="action" value="send_component_message">
                    {self._text_channel_select(guild, "component_channel_id", "Channel", None)}
                    {self._input("component_buttons", "Button Names, comma separated", "")}
                    {self._input("component_selects", "Select Names, comma separated", "")}
                    {self._input("component_text", "Message Text", "")}
                    <button class="rmdash-btn" type="submit">Send Component Message</button>
                </form>
                <form method="POST">
                    {csrf}
                    <input type="hidden" name="action" value="edit_component_message">
                    {self._text_channel_select(guild, "edit_component_channel_id", "Existing Message Channel", None)}
                    {self._input("edit_component_message_id", "Existing Message ID", "")}
                    {self._input("edit_component_buttons", "Button Names, comma separated", "")}
                    {self._input("edit_component_selects", "Select Names, comma separated", "")}
                    {self._checkbox("edit_component_content", "Replace message text", False)}
                    {self._textarea("edit_component_text", "Replacement Text", "")}
                    <button class="rmdash-btn" type="submit">Edit Component Message</button>
                </form>
            </div>
            <form method="POST" class="rmdash-actions">
                {csrf}
                <input type="hidden" name="action" value="cleanup_component_messages">
                <button class="rmdash-btn secondary" type="submit">Clean Stale Message References</button>
            </form>
            <h3>Saved Buttons</h3>
            {buttons_table}
            {"".join(button_editors)}
            <h3>Saved Select Options</h3>
            {options_table}
            {"".join(option_editors)}
            <h3>Saved Select Menus</h3>
            {menus_table}
            {"".join(menu_editors)}
        </div>
        """

    def _role_options(self, guild: discord.Guild) -> typing.List[typing.Tuple[int, str]]:
        roles = [
            role
            for role in guild.roles
            if not role.is_default() and not role.managed
        ]
        return [
            (role.id, role.name)
            for role in sorted(roles, key=lambda item: item.position, reverse=True)
        ]

    def _dashboard_role_names(
        self,
        guild: discord.Guild,
        role_ids: typing.Iterable[int],
    ) -> str:
        names = [
            role.name
            for role_id in role_ids
            if (role := guild.get_role(int(role_id))) is not None
        ]
        return ", ".join(names) if names else "None"

    def _text_options(self, guild: discord.Guild) -> typing.List[typing.Tuple[int, str]]:
        return [(channel.id, f"#{channel.name}") for channel in guild.text_channels]

    def _role_select(
        self,
        guild: discord.Guild,
        name: str,
        label: str,
        selected: typing.Any,
    ) -> str:
        return self._select(name, label, self._role_options(guild), selected)

    def _text_channel_select(
        self,
        guild: discord.Guild,
        name: str,
        label: str,
        selected: typing.Any,
    ) -> str:
        return self._select(name, label, self._text_options(guild), selected)

    def _multi_role_select(
        self,
        guild: discord.Guild,
        name: str,
        label: str,
        selected: typing.Sequence[int],
    ) -> str:
        selected_ids = {str(role_id) for role_id in selected}
        options = []
        for role_id, role_name in self._role_options(guild):
            selected_attr = "selected" if str(role_id) in selected_ids else ""
            options.append(
                f'<option value="{self._h(role_id)}" {selected_attr}>{self._h(role_name)}</option>'
            )
        return (
            f'<div class="rmdash-field"><label>{self._h(label)}</label>'
            f'<select name="{self._h(name)}" multiple size="8">{"".join(options)}</select></div>'
        )

    def _select(
        self,
        name: str,
        label: str,
        options: typing.List[typing.Tuple[typing.Any, str]],
        selected: typing.Any,
    ) -> str:
        option_html = ['<option value="">Select...</option>']
        for value, text in options:
            option_html.append(
                f'<option value="{self._h(value)}" {self._selected(value, selected)}>'
                f"{self._h(text)}</option>"
            )
        return (
            f'<div class="rmdash-field"><label>{self._h(label)}</label>'
            f'<select name="{self._h(name)}">{"".join(option_html)}</select></div>'
        )

    def _input(self, name: str, label: str, value: typing.Any) -> str:
        return (
            f'<div class="rmdash-field"><label>{self._h(label)}</label>'
            f'<input type="text" name="{self._h(name)}" value="{self._h(value)}"></div>'
        )

    def _textarea(self, name: str, label: str, value: typing.Any) -> str:
        return (
            f'<div class="rmdash-field"><label>{self._h(label)}</label>'
            f'<textarea name="{self._h(name)}">{self._h(value)}</textarea></div>'
        )

    def _checkbox(self, name: str, label: str, checked: typing.Any) -> str:
        checked_attr = "checked" if checked else ""
        return (
            '<label class="rmdash-check">'
            f'<input type="checkbox" name="{self._h(name)}" value="1" {checked_attr}>'
            f"{self._h(label)}</label>"
        )

    def _selected(self, value: typing.Any, selected: typing.Any) -> str:
        return "selected" if str(value) == str(selected) else ""

    def _dashboard_time(self, value: typing.Any) -> str:
        try:
            timestamp = float(value)
        except (TypeError, ValueError):
            return "Unknown"
        return datetime.fromtimestamp(timestamp, tz=timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    def _dashboard_duration_value(self, value: typing.Any) -> str:
        try:
            seconds = int(value)
        except (TypeError, ValueError):
            return ""
        if seconds <= 0:
            return ""
        units = (
            ("y", 365 * 24 * 60 * 60),
            ("mo", 30 * 24 * 60 * 60),
            ("w", 7 * 24 * 60 * 60),
            ("d", 24 * 60 * 60),
            ("h", 60 * 60),
            ("m", 60),
            ("s", 1),
        )
        parts = []
        for suffix, size in units:
            amount, seconds = divmod(seconds, size)
            if amount:
                parts.append(f"{amount}{suffix}")
        return " ".join(parts)

    def _h(self, value: typing.Any) -> str:
        return html.escape("" if value is None else str(value), quote=True)
