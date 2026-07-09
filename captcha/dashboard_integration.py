"""Red-Web-Dashboard integration for Captcha."""

from __future__ import annotations

import html
import logging
import typing

import discord
from redbot.core import commands

log = logging.getLogger("red.taakoscogs.captcha.dashboard")


def dashboard_page(*args, **kwargs):
    """Dashboard page decorator compatible with Red-Web-Dashboard."""

    def decorator(func: typing.Callable):
        func.__dashboard_decorator_params__ = (args, kwargs)
        return func

    return decorator


class DashboardIntegration:
    """Dashboard integration mixin for Captcha."""

    @commands.Cog.listener()
    async def on_dashboard_cog_add(self, dashboard_cog: commands.Cog) -> None:
        """Register Captcha as a Red-Web-Dashboard third party."""
        handler = dashboard_cog.rpc.third_parties_handler
        try:
            handler.add_third_party(self, overwrite=True)
        except TypeError:
            handler.add_third_party(self)

    @dashboard_page(
        name=None,
        description="Post, attach, remove, and inspect captcha verification panels.",
        methods=("GET", "POST"),
    )
    async def dashboard_page(
        self,
        user: discord.User,
        guild: discord.Guild,
        **kwargs,
    ) -> typing.Dict[str, typing.Any]:
        """Render and process the Captcha dashboard page."""
        _member, can_manage = await self._dashboard_member_can_manage(user, guild)
        if not can_manage:
            return {
                "status": 1,
                "error_title": "Insufficient Permissions",
                "error_message": "You need Manage Server, Red admin, or bot owner access.",
            }

        notifications = []
        form_data = self._dashboard_form_data(kwargs)

        if kwargs.get("method", "GET") == "POST":
            action = self._dash_value(form_data, "action")
            try:
                messages = await self._dashboard_handle_action(guild, action, form_data)
            except commands.CommandError as error:
                notifications.append({"message": str(error), "category": "error"})
            except Exception as error:
                log.exception("Captcha dashboard action failed.")
                notifications.append(
                    {
                        "message": f"Captcha dashboard action failed: {error}",
                        "category": "error",
                    }
                )
            else:
                notifications.extend(messages)

        source = await self._dashboard_source(guild, kwargs)
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
        action: str,
        form_data: typing.Any,
    ) -> typing.List[typing.Dict[str, str]]:
        if action == "post_panel":
            message = await self._dashboard_post_panel(guild, form_data)
            return [
                {
                    "message": f"Captcha panel posted: {message.jump_url}",
                    "category": "success",
                }
            ]

        if action == "attach_panel":
            message = await self._dashboard_attach_panel(guild, form_data)
            return [
                {
                    "message": f"Captcha button attached: {message.jump_url}",
                    "category": "success",
                }
            ]

        if action == "remove_panel":
            message_id = await self._dashboard_remove_panel(guild, form_data)
            return [
                {
                    "message": f"Captcha panel `{message_id}` removed.",
                    "category": "success",
                }
            ]

        if action:
            raise commands.BadArgument("Unknown Captcha dashboard action.")
        return []

    async def _dashboard_post_panel(
        self,
        guild: discord.Guild,
        form_data: typing.Any,
    ) -> discord.Message:
        channel_id = self._dash_required_id(form_data, "channel_id")
        channel = guild.get_channel(channel_id)
        if not isinstance(channel, discord.TextChannel):
            raise commands.BadArgument("Choose a text channel for the captcha panel.")

        me = guild.me
        if me is None:
            raise commands.CommandError("I could not check my channel permissions.")
        permissions = channel.permissions_for(me)
        if not permissions.send_messages or not permissions.embed_links:
            raise commands.CommandError(
                f"I need Send Messages and Embed Links in #{channel.name}."
            )

        roles = self._dashboard_roles(guild, form_data)
        label = self._dash_value(form_data, "label", "Verify").strip()[:80] or "Verify"
        embed = discord.Embed(
            title=self.DEFAULT_TITLE,
            description=self.DEFAULT_DESCRIPTION,
            color=self.DEFAULT_COLOR,
        )
        embed.set_footer(text="Each verification attempt uses a new code.")
        message = None
        try:
            message = await channel.send(embed=embed)
            await self._install_panel(guild, message, roles, label)
        except (commands.CommandError, discord.HTTPException):
            if message is not None:
                try:
                    await message.delete()
                except discord.HTTPException:
                    pass
            raise
        return message

    async def _dashboard_attach_panel(
        self,
        guild: discord.Guild,
        form_data: typing.Any,
    ) -> discord.Message:
        channel_id = self._dash_required_id(form_data, "attach_channel_id")
        message_id = self._dash_required_id(form_data, "attach_message_id")
        channel = guild.get_channel(channel_id)
        if not isinstance(channel, discord.TextChannel):
            raise commands.BadArgument("Choose the text channel containing the message.")

        try:
            message = await channel.fetch_message(message_id)
        except discord.NotFound as exc:
            raise commands.BadArgument("I could not find that message.") from exc
        except discord.Forbidden as exc:
            raise commands.CommandError("I cannot read messages in that channel.") from exc
        except discord.HTTPException as exc:
            raise commands.CommandError("Discord did not return that message.") from exc

        me = guild.me
        if me is None or message.author.id != me.id:
            raise commands.BadArgument("I can only attach buttons to messages sent by this bot.")

        panels = await self.config.guild(guild).panels()
        if message.components and str(message.id) not in panels:
            raise commands.BadArgument("That message already has components I do not manage.")

        roles = self._dashboard_roles(guild, form_data)
        label = self._dash_value(form_data, "attach_label", "Verify").strip()[:80] or "Verify"
        await self._install_panel(guild, message, roles, label)
        return message

    async def _dashboard_remove_panel(
        self,
        guild: discord.Guild,
        form_data: typing.Any,
    ) -> int:
        message_id = self._dash_required_id(form_data, "remove_message_id")
        panels = await self.config.guild(guild).panels()
        record = panels.get(str(message_id))
        if not isinstance(record, dict):
            raise commands.BadArgument("That message is not a configured captcha panel.")

        channel = guild.get_channel(int(record.get("channel_id") or 0))
        if isinstance(channel, discord.TextChannel):
            try:
                message = await channel.fetch_message(message_id)
                await message.edit(view=None)
            except discord.NotFound:
                pass
            except discord.Forbidden as exc:
                raise commands.CommandError("I cannot edit that panel message.") from exc
            except discord.HTTPException as exc:
                raise commands.CommandError(f"I could not remove the button: {exc}") from exc

        await self._remove_panel_record(guild.id, message_id)
        return message_id

    def _dashboard_roles(
        self,
        guild: discord.Guild,
        form_data: typing.Any,
    ) -> typing.List[discord.Role]:
        role_ids = []
        for raw_role_id in self._dash_values(form_data, "role_ids"):
            try:
                role_id = int(raw_role_id)
            except (TypeError, ValueError):
                continue
            if role_id not in role_ids:
                role_ids.append(role_id)
        roles = [guild.get_role(role_id) for role_id in role_ids]
        if any(role is None for role in roles):
            raise commands.BadArgument("One or more selected roles no longer exist.")
        return self._validate_roles(guild, typing.cast(typing.List[discord.Role], roles))

    async def _dashboard_source(
        self,
        guild: discord.Guild,
        kwargs: typing.Dict[str, typing.Any],
    ) -> str:
        panels = await self.config.guild(guild).panels()
        csrf = self._dash_csrf(kwargs)
        text_channel_options = self._text_channel_options(guild)
        role_options = self._role_options(guild)
        panel_rows = self._panel_rows(guild, panels, csrf)

        return f"""
<style>
.captcha-dash {{
  --bg: #101318; --panel: #171b22; --line: #2a303a; --text: #eef1f5;
  --muted: #aab2bf; --accent: #57f287; --warn: #fee75c;
  color: var(--text); display: grid; gap: 16px;
}}
.captcha-dash * {{ box-sizing: border-box; }}
.captcha-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 16px; }}
.captcha-card {{ background: var(--panel); border: 1px solid var(--line); border-radius: 8px; padding: 16px; }}
.captcha-card h2 {{ margin: 0 0 12px; font-size: 18px; }}
.captcha-card h3 {{ margin: 18px 0 10px; font-size: 15px; }}
.captcha-stats {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(140px, 1fr)); gap: 10px; }}
.captcha-stat {{ border: 1px solid var(--line); border-radius: 8px; padding: 12px; }}
.captcha-stat strong {{ display: block; font-size: 22px; }}
.captcha-stat span, .captcha-muted {{ color: var(--muted); }}
.captcha-field {{ display: grid; gap: 6px; margin-bottom: 10px; }}
.captcha-field label {{ color: var(--muted); font-size: 13px; }}
.captcha-field input, .captcha-field select {{
  width: 100%; background: #0c0f14; color: var(--text); border: 1px solid var(--line);
  border-radius: 6px; padding: 9px 10px;
}}
.captcha-field select[multiple] {{ min-height: 145px; }}
.captcha-actions {{ display: flex; flex-wrap: wrap; gap: 8px; margin-top: 12px; }}
.captcha-actions button {{
  background: var(--accent); color: #102014; border: 0; border-radius: 6px;
  padding: 9px 12px; font-weight: 700; cursor: pointer;
}}
.captcha-actions button.warn {{ background: var(--warn); color: #1f1b00; }}
.captcha-table {{ width: 100%; border-collapse: collapse; font-size: 14px; }}
.captcha-table th, .captcha-table td {{ border-bottom: 1px solid var(--line); padding: 8px; text-align: left; vertical-align: top; }}
.captcha-table th {{ color: var(--muted); font-weight: 600; }}
.captcha-link {{ color: #8ab4ff; }}
</style>
<div class="captcha-dash">
  <div class="captcha-stats">
    <div class="captcha-stat"><strong>{len(panels)}</strong><span>configured panels</span></div>
    <div class="captcha-stat"><strong>{len(self._panel_views)}</strong><span>registered views</span></div>
  </div>
  <div class="captcha-grid">
    <form class="captcha-card" method="post">
      {csrf}
      <input type="hidden" name="action" value="post_panel">
      <h2>Post Panel</h2>
      {self._select("channel_id", "Target text channel", text_channel_options)}
      {self._role_select(role_options)}
      {self._input("label", "Button label", "Verify")}
      <div class="captcha-actions"><button type="submit">Post captcha panel</button></div>
    </form>
    <form class="captcha-card" method="post">
      {csrf}
      <input type="hidden" name="action" value="attach_panel">
      <h2>Attach To Bot Message</h2>
      {self._select("attach_channel_id", "Message text channel", text_channel_options)}
      {self._input("attach_message_id", "Message ID", "", "number")}
      {self._role_select(role_options)}
      {self._input("attach_label", "Button label", "Verify")}
      <div class="captcha-actions"><button type="submit">Attach button</button></div>
    </form>
  </div>
  <div class="captcha-card">
    <h2>Configured Panels</h2>
    {panel_rows}
  </div>
</div>
"""

    def _panel_rows(
        self,
        guild: discord.Guild,
        panels: typing.Dict[str, typing.Any],
        csrf: str,
    ) -> str:
        if not panels:
            return '<p class="captcha-muted">No captcha panels are configured.</p>'

        rows = []
        for message_id, record in sorted(panels.items()):
            channel_id = record.get("channel_id") if isinstance(record, dict) else None
            channel = guild.get_channel(int(channel_id or 0))
            role_ids = record.get("role_ids") if isinstance(record, dict) else []
            if not isinstance(role_ids, list):
                role_ids = [record.get("role_id")] if isinstance(record, dict) else []
            role_names = []
            for role_id in role_ids:
                role = guild.get_role(int(role_id or 0))
                role_names.append(role.name if role else f"Missing role {role_id}")
            label = record.get("button_label") if isinstance(record, dict) else "Verify"
            jump_url = self._jump_url(guild.id, channel_id, message_id)
            rows.append(
                "<tr>"
                f"<td><a class=\"captcha-link\" href=\"{self._h(jump_url)}\">{self._h(message_id)}</a></td>"
                f"<td>{self._h('#' + channel.name if channel else 'Missing channel')}</td>"
                f"<td>{self._h(', '.join(role_names) or 'No roles')}</td>"
                f"<td>{self._h(label or 'Verify')}</td>"
                "<td>"
                '<form method="post">'
                f"{csrf}"
                '<input type="hidden" name="action" value="remove_panel">'
                f'<input type="hidden" name="remove_message_id" value="{self._h(message_id)}">'
                '<button class="warn" type="submit">Remove</button>'
                "</form>"
                "</td>"
                "</tr>"
            )
        return (
            '<table class="captcha-table"><thead><tr><th>Message</th><th>Channel</th>'
            "<th>Roles</th><th>Button</th><th></th></tr></thead><tbody>"
            + "".join(rows)
            + "</tbody></table>"
        )

    def _text_channel_options(self, guild: discord.Guild) -> typing.List[typing.Tuple[int, str]]:
        return [(channel.id, f"#{channel.name}") for channel in guild.text_channels]

    def _role_options(self, guild: discord.Guild) -> typing.List[typing.Tuple[int, str]]:
        roles = [
            role
            for role in guild.roles
            if not role.is_default() and not role.managed
        ]
        roles.sort(key=lambda role: role.position, reverse=True)
        return [(role.id, role.name) for role in roles]

    def _select(
        self,
        name: str,
        label: str,
        options: typing.List[typing.Tuple[typing.Any, str]],
        selected: typing.Any = "",
    ) -> str:
        option_html = ['<option value="">Select...</option>']
        for value, text in options:
            option_html.append(
                f'<option value="{self._h(value)}" {self._selected(value, selected)}>'
                f"{self._h(text)}</option>"
            )
        return (
            f'<div class="captcha-field"><label>{self._h(label)}</label>'
            f'<select name="{self._h(name)}">{"".join(option_html)}</select></div>'
        )

    def _role_select(self, options: typing.List[typing.Tuple[typing.Any, str]]) -> str:
        option_html = [
            f'<option value="{self._h(value)}">{self._h(text)}</option>'
            for value, text in options
        ]
        return (
            '<div class="captcha-field"><label>Verification roles</label>'
            f'<select name="role_ids" multiple size="8">{"".join(option_html)}</select></div>'
        )

    def _input(
        self,
        name: str,
        label: str,
        value: typing.Any,
        input_type: str = "text",
    ) -> str:
        return (
            f'<div class="captcha-field"><label>{self._h(label)}</label>'
            f'<input type="{self._h(input_type)}" name="{self._h(name)}" '
            f'value="{self._h(value)}"></div>'
        )

    def _selected(self, value: typing.Any, selected: typing.Any) -> str:
        return "selected" if str(value) == str(selected) else ""

    def _jump_url(
        self,
        guild_id: typing.Any,
        channel_id: typing.Any,
        message_id: typing.Any,
    ) -> str:
        return f"https://discord.com/channels/{guild_id}/{channel_id}/{message_id}"

    def _h(self, value: typing.Any) -> str:
        return html.escape("" if value is None else str(value), quote=True)
