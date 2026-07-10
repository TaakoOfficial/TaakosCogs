"""Red-Web-Dashboard integration for RoleManager."""

from __future__ import annotations

import html
import logging
import typing
from datetime import datetime, timezone

import discord
from redbot.core import commands

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
        description="Configure self roles, autoroles, sticky roles, temp roles, and reaction roles.",
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
            and member.id != guild.owner_id
            and not member.guild_permissions.administrator
            and role >= member.top_role
        ):
            raise commands.BadArgument(f"Your top role must be above `{role.name}`.")

    async def _dashboard_save_role_flags(
        self,
        guild: discord.Guild,
        member: typing.Optional[discord.Member],
        role: discord.Role,
        form_data: typing.Any,
    ) -> None:
        await self.config.role(role).self_assignable.set(
            self._dash_bool(form_data, "self_assignable")
        )
        await self.config.role(role).self_removable.set(
            self._dash_bool(form_data, "self_removable")
        )
        await self.config.role(role).sticky.set(self._dash_bool(form_data, "sticky"))

        duration = self._dash_value(form_data, "temp_duration").strip()
        if duration:
            await self.config.role(role).temp_duration.set(self._parse_duration(duration))
        else:
            await self.config.role(role).temp_duration.clear()
        cost_value = self._dash_value(form_data, "cost").strip()
        try:
            cost = int(cost_value or 0)
        except ValueError as exc:
            raise commands.BadArgument("Cost must be a whole number.") from exc
        await self.config.role(role).cost.set(max(0, cost))
        await self.config.role(role).require_any.set(self._dash_bool(form_data, "require_any"))
        await self.config.role(role).required.set(
            self._dashboard_valid_role_ids(
                guild,
                member,
                form_data,
                "required_roles",
                check_manageable=False,
            )
        )
        await self.config.role(role).inclusive_with.set(
            self._dashboard_valid_role_ids(guild, member, form_data, "inclusive_roles")
        )
        await self.config.role(role).exclusive_to.set(
            self._dashboard_valid_role_ids(guild, member, form_data, "exclusive_roles")
        )

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
        async with self.config.guild(guild).buttons() as buttons:
            old = buttons.get(name)
            if old:
                data["messages"] = list(old.get("messages", []))
            buttons[name] = data
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
        async with self.config.guild(guild).select_options() as options:
            options[name] = data
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
        csrf = self._dash_csrf(kwargs)

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
            .rmdash-check {{ display: flex; align-items: center; gap: 8px; margin: 6px 0; color: #d1d5db; }}
            .rmdash-check input {{ width: auto; }}
            .rmdash-btn {{ background: #2563eb; color: white; border: 0; border-radius: 6px; padding: 9px 14px; cursor: pointer; font-weight: 700; }}
            .rmdash-btn.secondary {{ background: #4b5563; }}
            .rmdash-btn.danger {{ background: #dc2626; }}
            .rmdash-nav {{ display: flex; gap: 8px; flex-wrap: wrap; margin: 12px 0 16px; }}
            .rmdash-nav a {{ color: #bfdbfe; border: 1px solid #374151; border-radius: 6px; padding: 6px 10px; text-decoration: none; }}
            .rmdash-table {{ width: 100%; border-collapse: collapse; font-size: 0.92rem; }}
            .rmdash-table th, .rmdash-table td {{ border-bottom: 1px solid #374151; padding: 8px; text-align: left; vertical-align: top; }}
            .rmdash-table th {{ color: #d1d5db; }}
            .rmdash-inline {{ display: inline; }}
        </style>
        <div class="rmdash-wrap">
            <div class="rmdash-card">
                <h2>RoleManager Dashboard</h2>
                <div class="rmdash-nav">
                    <a href="#role-settings">Role Settings</a>
                    <a href="#autoroles">Autoroles</a>
                    <a href="#reaction-roles">Reaction Roles</a>
                    <a href="#components">Buttons & Selects</a>
                    <a href="#temporary-roles">Temporary Roles</a>
                </div>
                <div class="rmdash-grid">
                    <div><div class="rmdash-muted">Self Roles</div><div class="rmdash-stat">{role_stats["self_roles"]}</div></div>
                    <div><div class="rmdash-muted">Sticky Roles</div><div class="rmdash-stat">{role_stats["sticky_roles"]}</div></div>
                    <div><div class="rmdash-muted">Default Temp Roles</div><div class="rmdash-stat">{role_stats["temp_roles"]}</div></div>
                    <div><div class="rmdash-muted">Reaction Bindings</div><div class="rmdash-stat">{reaction_bind_count}</div></div>
                    <div><div class="rmdash-muted">Buttons</div><div class="rmdash-stat">{len(buttons)}</div></div>
                    <div><div class="rmdash-muted">Select Menus</div><div class="rmdash-stat">{len(select_menus)}</div></div>
                    <div><div class="rmdash-muted">Pending Temp Roles</div><div class="rmdash-stat">{len(temp_roles)}</div></div>
                </div>
            </div>
            {await self._dashboard_role_settings_section(guild, selected_role, csrf)}
            {self._dashboard_autoroles_section(guild, auto_roles, csrf)}
            {self._dashboard_reaction_roles_section(guild, react_roles, csrf)}
            {self._dashboard_components_section(guild, buttons, select_options, select_menus, csrf)}
            {self._dashboard_temporary_roles_section(guild, temp_roles, csrf)}
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
                <input type="hidden" name="action" value="save_role_flags">
                <input type="hidden" name="role_id" value="{self._h(role_id)}">
                <div class="rmdash-row">
                    {self._input("temp_duration", "Default Temp Duration", duration_text)}
                    {self._input("cost", "Credit Cost", config.get("cost") or 0)}
                </div>
                {self._checkbox("self_assignable", "Members can add this role with selfrole", self_assignable)}
                {self._checkbox("self_removable", "Members can remove this role with selfrole", self_removable)}
                {self._checkbox("sticky", "Restore this role when members rejoin", sticky)}
                {self._checkbox("require_any", "Require any prerequisite instead of all prerequisites", config.get("require_any"))}
                <div class="rmdash-grid">
                    {self._multi_role_select(guild, "required_roles", "Required Roles", config.get("required") or [])}
                    {self._multi_role_select(guild, "inclusive_roles", "Inclusive Roles", config.get("inclusive_with") or [])}
                    {self._multi_role_select(guild, "exclusive_roles", "Exclusive Roles", config.get("exclusive_to") or [])}
                </div>
                <button class="rmdash-btn" type="submit">Save Role Settings</button>
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
            else '<table class="rmdash-table"><thead><tr><th>Message</th><th>Channel</th>'
            '<th>Emoji</th><th>Role</th><th>Remove On Unreact</th><th>Actions</th>'
            f'</tr></thead><tbody>{"".join(rows)}</tbody></table>'
        )
        return f"""
        <div id="reaction-roles" class="rmdash-card">
            <h3>Reaction Roles</h3>
            <form method="POST">
                {csrf}
                <input type="hidden" name="action" value="bind_reaction_role">
                <div class="rmdash-grid">
                    {self._text_channel_select(guild, "rr_channel_id", "Message Channel", None)}
                    {self._input("rr_message_id", "Message ID", "")}
                    {self._input("rr_emoji", "Emoji", "")}
                    {self._role_select(guild, "rr_role_id", "Role", None)}
                </div>
                {self._checkbox("rr_remove_on_unreact", "Remove role when reaction is removed", True)}
                <button class="rmdash-btn" type="submit">Bind Reaction Role</button>
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
        buttons_table = (
            '<p class="rmdash-muted">No buttons configured.</p>'
            if not button_rows
            else '<table class="rmdash-table"><thead><tr><th>Name</th><th>Role</th>'
            f'<th>Label</th><th>Messages</th><th></th></tr></thead><tbody>{"".join(button_rows)}</tbody></table>'
        )

        option_rows = []
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
        options_table = (
            '<p class="rmdash-muted">No select options configured.</p>'
            if not option_rows
            else '<table class="rmdash-table"><thead><tr><th>Name</th><th>Role</th>'
            f'<th>Label</th><th></th></tr></thead><tbody>{"".join(option_rows)}</tbody></table>'
        )

        menu_rows = []
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
                    {self._input("button_style", "Style", "secondary")}
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
            </div>
            <h3>Saved Buttons</h3>
            {buttons_table}
            <h3>Saved Select Options</h3>
            {options_table}
            <h3>Saved Select Menus</h3>
            {menus_table}
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
