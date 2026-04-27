"""Toolz Cog - Role and user utility commands for Red DiscordBot."""

import asyncio
import csv
import io
import random
from typing import List, Optional, Sequence, Tuple

import discord
from redbot.core import Config, commands

__red_end_user_data_statement__ = (
    "This cog stores per-guild role message settings, including role IDs, channel IDs, "
    "and configured message templates. Role member exports are generated on demand and "
    "sent directly to Discord without being saved locally."
)


class SafeFormatDict(dict):
    """Keep unknown template placeholders intact."""

    def __missing__(self, key: str) -> str:
        return "{" + key + "}"


class Toolz(commands.Cog):
    """Role and user utility tools for larger servers."""

    CONFIG_IDENTIFIER = 8273649150

    IMPORTANT_PERMISSIONS: Tuple[Tuple[str, str], ...] = (
        ("administrator", "Administrator"),
        ("manage_guild", "Manage Server"),
        ("manage_roles", "Manage Roles"),
        ("manage_channels", "Manage Channels"),
        ("manage_messages", "Manage Messages"),
        ("manage_webhooks", "Manage Webhooks"),
        ("manage_emojis_and_stickers", "Manage Emojis and Stickers"),
        ("kick_members", "Kick Members"),
        ("ban_members", "Ban Members"),
        ("moderate_members", "Timeout Members"),
        ("mention_everyone", "Mention Everyone"),
        ("view_audit_log", "View Audit Log"),
    )

    VALID_ROLE_SORTS = {"members", "position", "name", "color"}

    def __init__(self, bot):
        self.bot = bot
        self.config = Config.get_conf(
            self,
            identifier=self.CONFIG_IDENTIFIER,
            force_registration=True,
        )
        self.config.register_guild(role_messages={})

    async def _defer_if_needed(self, ctx: commands.Context) -> None:
        """Defer slash command responses before member cache work."""
        if not getattr(ctx, "interaction", None):
            return

        defer = getattr(ctx, "defer", None)
        if defer is None:
            return

        try:
            await defer()
        except (discord.HTTPException, RuntimeError):
            pass

    async def _prepare_member_cache(self, ctx: commands.Context) -> bool:
        """Try to load members so role counts are useful on large guilds."""
        guild = ctx.guild
        if guild is None:
            return False

        if getattr(guild, "chunked", False):
            return True

        intents = getattr(self.bot, "intents", None)
        if not getattr(intents, "members", False):
            return False

        await self._defer_if_needed(ctx)

        try:
            await asyncio.wait_for(guild.chunk(cache=True), timeout=20)
        except (asyncio.TimeoutError, discord.HTTPException):
            return False

        return getattr(guild, "chunked", False)

    async def _get_cache_status(self, ctx: commands.Context) -> bool:
        if getattr(ctx, "interaction", None):
            return await self._prepare_member_cache(ctx)

        async with ctx.typing():
            return await self._prepare_member_cache(ctx)

    @staticmethod
    def _copy_block(value: object) -> str:
        return f"```\n{value}\n```"

    @staticmethod
    def _line_chunks(lines: Sequence[str], max_chars: int = 1000) -> List[str]:
        chunks: List[str] = []
        current: List[str] = []
        current_length = 0

        for line in lines:
            if len(line) > max_chars:
                line = f"{line[: max_chars - 3]}..."

            addition = len(line) + (1 if current else 0)
            if current and current_length + addition > max_chars:
                chunks.append("\n".join(current))
                current = [line]
                current_length = len(line)
            else:
                current.append(line)
                current_length += addition

        if current:
            chunks.append("\n".join(current))

        return chunks

    @staticmethod
    def _yes_no(value: bool) -> str:
        return "Yes" if value else "No"

    @staticmethod
    def _member_is_timed_out(member: discord.Member) -> bool:
        is_timed_out = getattr(member, "is_timed_out", None)
        if callable(is_timed_out):
            return is_timed_out()
        return getattr(member, "timed_out_until", None) is not None

    @staticmethod
    def _count(value: int) -> str:
        return f"{value:,}"

    @staticmethod
    def _format_timestamp(dt) -> str:
        timestamp = int(dt.timestamp())
        return f"<t:{timestamp}:F>\n<t:{timestamp}:R>"

    @staticmethod
    def _role_color(role: discord.Role) -> discord.Color:
        if role.color.value:
            return role.color
        return discord.Color.blurple()

    @staticmethod
    def _member_color(member: discord.Member) -> discord.Color:
        if member.color.value:
            return member.color
        return discord.Color.blurple()

    @staticmethod
    def _safe_role_name(role: discord.Role) -> str:
        if role.is_default():
            return "@everyone"
        return role.name

    @staticmethod
    def _role_reference(role: discord.Role) -> str:
        if role.is_default():
            return "@everyone"
        return role.mention

    @staticmethod
    def _role_mention_string(role: discord.Role) -> str:
        if role.is_default():
            return "@everyone"
        return f"<@&{role.id}>"

    def _role_copy_content(self, role: discord.Role) -> str:
        return (
            "Copy values:\n"
            f"Role ID: `{role.id}`\n"
            f"Mention String: `{self._role_mention_string(role)}`"
        )

    @staticmethod
    def _assignable_by_bot(role: discord.Role) -> bool:
        try:
            return role.is_assignable()
        except AttributeError:
            me = role.guild.me
            return me is not None and not role.managed and me.top_role > role

    @staticmethod
    def _guild_total_members(guild: discord.Guild) -> int:
        return guild.member_count or len(guild.members)

    def _role_members(self, role: discord.Role) -> List[discord.Member]:
        if role.is_default():
            return list(role.guild.members)
        return list(role.members)

    def _role_member_count(self, role: discord.Role) -> int:
        if role.is_default():
            return self._guild_total_members(role.guild)
        return len(role.members)

    @staticmethod
    def _member_roles(member: discord.Member) -> List[discord.Role]:
        return sorted(
            [role for role in member.roles if not role.is_default()],
            key=lambda role: role.position,
            reverse=True,
        )

    def _member_count_text(self, role: discord.Role) -> str:
        count = self._role_member_count(role)
        total = self._guild_total_members(role.guild)
        if total:
            percent = (count / total) * 100
            return f"{self._count(count)} / {self._count(total)} ({percent:.1f}%)"
        return self._count(count)

    def _important_permissions_text(self, role: discord.Role) -> str:
        permissions = role.permissions
        enabled = [
            label
            for attr, label in self.IMPORTANT_PERMISSIONS
            if getattr(permissions, attr, False)
        ]
        if permissions.administrator:
            return "Administrator"
        if not enabled:
            return "No elevated permissions detected"
        return ", ".join(enabled[:8])

    def _display_flags_text(self, role: discord.Role) -> str:
        return "\n".join(
            (
                f"Hoisted: {self._yes_no(role.hoist)}",
                f"Mentionable: {self._yes_no(role.mentionable)}",
                f"Managed: {self._yes_no(role.managed)}",
                f"Default role: {self._yes_no(role.is_default())}",
            )
        )

    def _hierarchy_text(self, role: discord.Role) -> str:
        role_count = len(role.guild.roles)
        return "\n".join(
            (
                f"Position: {role.position} of {role_count - 1}",
                f"Assignable by bot: {self._yes_no(self._assignable_by_bot(role))}",
            )
        )

    def _member_preview_text(self, role: discord.Role, limit: int = 8) -> str:
        members = self._role_members(role)
        if not members:
            return "No cached members have this role."

        members = sorted(members, key=lambda member: member.display_name.casefold())
        lines = [
            f"{member.display_name} (`{member.id}`)"
            for member in members[:limit]
        ]

        remaining = len(members) - len(lines)
        if remaining > 0:
            lines.append(f"...and {self._count(remaining)} more")

        return "\n".join(lines)

    async def _send_embed(self, ctx: commands.Context, embed: discord.Embed, **kwargs) -> None:
        await ctx.send(
            embed=embed,
            allowed_mentions=discord.AllowedMentions.none(),
            **kwargs,
        )

    def _base_role_embed(self, role: discord.Role, title: str) -> discord.Embed:
        embed = discord.Embed(
            title=title,
            description=self._role_reference(role),
            color=self._role_color(role),
        )

        guild = role.guild
        if guild.icon:
            embed.set_author(name=guild.name, icon_url=guild.icon.url)
        else:
            embed.set_author(name=guild.name)

        display_icon = getattr(role, "display_icon", None)
        icon_url = getattr(display_icon, "url", None)
        if icon_url:
            embed.set_thumbnail(url=str(icon_url))

        return embed

    def _cache_footer(self, cache_ready: bool) -> str:
        if cache_ready:
            return "Toolz role tools"
        return "Toolz role tools - counts may be limited by the bot member cache"

    @staticmethod
    def _user_footer() -> str:
        return "Toolz user tools"

    @staticmethod
    def _default_role_message_settings() -> dict:
        return {"channel_id": None, "messages": [], "enabled": True, "mode": "all"}

    @staticmethod
    def _role_message_mode(entry: dict) -> str:
        mode = entry.get("mode", "all")
        if mode not in {"all", "random"}:
            return "all"
        return mode

    @staticmethod
    def _role_message_key(role: discord.Role) -> str:
        return str(role.id)

    def _role_message_placeholders(
        self,
        member: discord.Member,
        role: discord.Role,
    ) -> SafeFormatDict:
        return SafeFormatDict(
            user=member.mention,
            username=str(member),
            display_name=member.display_name,
            user_id=str(member.id),
            role=self._role_reference(role),
            role_name=self._safe_role_name(role),
            role_id=str(role.id),
            server=member.guild.name,
            server_id=str(member.guild.id),
        )

    def _render_role_message(
        self,
        template: str,
        member: discord.Member,
        role: discord.Role,
    ) -> str:
        message = template.format_map(self._role_message_placeholders(member, role))
        if len(message) > 2000:
            return f"{message[:1997]}..."
        return message

    def _role_message_entry_summary(
        self,
        guild: discord.Guild,
        role_id: str,
        entry: dict,
    ) -> str:
        role = guild.get_role(int(role_id))
        role_text = self._role_reference(role) if role else f"Deleted role `{role_id}`"
        channel = guild.get_channel(entry.get("channel_id") or 0)
        channel_text = channel.mention if channel else "No channel set"
        messages = entry.get("messages", [])
        enabled = self._yes_no(entry.get("enabled", True))
        mode = self._role_message_mode(entry)
        return (
            f"{role_text} - {self._count(len(messages))} messages - "
            f"{channel_text} - mode: {mode} - enabled: {enabled}"
        )

    async def _send_configured_role_messages(
        self,
        member: discord.Member,
        role: discord.Role,
        entry: dict,
    ) -> None:
        if not entry.get("enabled", True):
            return

        messages = entry.get("messages") or []
        channel_id = entry.get("channel_id")
        if not messages or not channel_id:
            return

        if self._role_message_mode(entry) == "random":
            messages = [random.choice(messages)]

        channel = member.guild.get_channel(channel_id)
        if channel is None:
            return

        me = member.guild.me
        if me is None:
            return

        permissions = channel.permissions_for(me)
        if not permissions.send_messages:
            return

        allowed_mentions = discord.AllowedMentions(
            users=True,
            roles=False,
            everyone=False,
        )
        for template in messages:
            content = self._render_role_message(template, member, role)
            try:
                await channel.send(content, allowed_mentions=allowed_mentions)
            except discord.HTTPException:
                return

    async def _send_role_message_settings(
        self,
        ctx: commands.Context,
        role: Optional[discord.Role] = None,
    ) -> None:
        role_messages = await self.config.guild(ctx.guild).role_messages()
        embed = discord.Embed(
            title="Role Messages",
            color=discord.Color.blurple(),
        )

        if role is not None:
            entry = role_messages.get(self._role_message_key(role))
            if not entry:
                embed.description = f"No role messages are configured for {self._role_reference(role)}."
                await self._send_embed(ctx, embed)
                return

            channel = ctx.guild.get_channel(entry.get("channel_id") or 0)
            channel_text = channel.mention if channel else "No channel set"
            messages = entry.get("messages", [])
            embed.description = self._role_reference(role)
            embed.add_field(name="Channel", value=channel_text, inline=True)
            embed.add_field(
                name="Enabled",
                value=self._yes_no(entry.get("enabled", True)),
                inline=True,
            )
            embed.add_field(name="Mode", value=self._role_message_mode(entry), inline=True)
            embed.add_field(name="Role ID", value=self._copy_block(role.id), inline=False)

            if messages:
                lines = [
                    f"`{index}.` {message}"
                    for index, message in enumerate(messages, start=1)
                ]
                for index, chunk in enumerate(self._line_chunks(lines), start=1):
                    field_name = "Messages" if index == 1 else "Messages continued"
                    embed.add_field(name=field_name, value=chunk, inline=False)
            else:
                embed.add_field(name="Messages", value="No messages set.", inline=False)

            await self._send_embed(ctx, embed)
            return

        if not role_messages:
            embed.description = "No role messages are configured."
            await self._send_embed(ctx, embed)
            return

        lines = [
            self._role_message_entry_summary(ctx.guild, role_id, entry)
            for role_id, entry in role_messages.items()
        ]
        for index, chunk in enumerate(self._line_chunks(lines), start=1):
            field_name = "Configured Roles" if index == 1 else "Configured Roles continued"
            embed.add_field(name=field_name, value=chunk, inline=False)

        await self._send_embed(ctx, embed)

    def _has_important_permissions(self, role: discord.Role) -> bool:
        return any(
            getattr(role.permissions, attr, False)
            for attr, _label in self.IMPORTANT_PERMISSIONS
        )

    def _member_important_permissions_text(self, member: discord.Member) -> str:
        permissions = member.guild_permissions
        if permissions.administrator:
            return "Administrator"

        enabled = [
            label
            for attr, label in self.IMPORTANT_PERMISSIONS
            if getattr(permissions, attr, False)
        ]
        if not enabled:
            return "No elevated permissions detected"
        return ", ".join(enabled[:8])

    def _member_role_preview_text(self, member: discord.Member, limit: int = 10) -> str:
        roles = self._member_roles(member)
        if not roles:
            return "No roles."

        lines = [
            f"{self._role_reference(role)} (`{role.id}`)"
            for role in roles[:limit]
        ]
        remaining = len(roles) - len(lines)
        if remaining > 0:
            lines.append(f"...and {self._count(remaining)} more")

        return "\n".join(lines)

    def _permission_source_text(self, member: discord.Member, attr: str) -> str:
        roles = self._member_roles(member)
        sources = [
            self._role_reference(role)
            for role in roles
            if getattr(role.permissions, attr, False)
        ]

        if attr != "administrator" and not sources:
            sources = [
                f"{self._role_reference(role)} (Administrator)"
                for role in roles
                if role.permissions.administrator
            ]

        if not sources and getattr(member.guild.default_role.permissions, attr, False):
            sources.append("@everyone")

        if not sources:
            return "Unknown source"

        shown_sources = sources[:4]
        remaining = len(sources) - len(shown_sources)
        source_text = ", ".join(shown_sources)
        if remaining > 0:
            source_text = f"{source_text}, +{self._count(remaining)} more"

        return source_text

    def _member_summary_lines(
        self,
        members: Sequence[discord.Member],
        limit: int,
    ) -> List[str]:
        lines = [
            f"`{index:>2}.` {member.mention} - `{member.id}`"
            for index, member in enumerate(members[:limit], start=1)
        ]

        remaining = len(members) - len(lines)
        if remaining > 0:
            lines.append(f"...and {self._count(remaining)} more")

        return lines

    @staticmethod
    def _joined_sort_key(member: discord.Member):
        return member.joined_at or member.created_at

    def _base_member_embed(self, member: discord.Member, title: str) -> discord.Embed:
        embed = discord.Embed(
            title=title,
            description=member.mention,
            color=self._member_color(member),
        )

        guild = member.guild
        if guild.icon:
            embed.set_author(name=guild.name, icon_url=guild.icon.url)
        else:
            embed.set_author(name=guild.name)

        embed.set_thumbnail(url=member.display_avatar.url)
        return embed

    @commands.Cog.listener()
    async def on_member_update(
        self,
        before: discord.Member,
        after: discord.Member,
    ) -> None:
        before_role_ids = {role.id for role in before.roles}
        added_roles = [
            role
            for role in after.roles
            if role.id not in before_role_ids and not role.is_default()
        ]
        if not added_roles:
            return

        role_messages = await self.config.guild(after.guild).role_messages()
        if not role_messages:
            return

        for role in added_roles:
            entry = role_messages.get(self._role_message_key(role))
            if entry:
                await self._send_configured_role_messages(after, role, entry)

    @commands.hybrid_command(
        name="roleinfo",
        aliases=["rinfo"],
        description="Show detailed information about a server role.",
    )
    @commands.guild_only()
    @commands.bot_has_permissions(embed_links=True)
    async def roleinfo(self, ctx: commands.Context, *, role: discord.Role):
        """Show detailed information about a role."""
        cache_ready = await self._get_cache_status(ctx)

        embed = self._base_role_embed(role, f"Role Info: {self._safe_role_name(role)}")
        embed.add_field(name="Members", value=self._member_count_text(role), inline=True)

        color_text = f"#{role.color.value:06X}" if role.color.value else "Default"
        embed.add_field(name="Color", value=color_text, inline=True)
        embed.add_field(name="Created", value=self._format_timestamp(role.created_at), inline=True)
        embed.add_field(name="Hierarchy", value=self._hierarchy_text(role), inline=True)
        embed.add_field(name="Display", value=self._display_flags_text(role), inline=True)
        embed.add_field(
            name="Important Permissions",
            value=self._important_permissions_text(role),
            inline=True,
        )
        embed.set_footer(text=self._cache_footer(cache_ready))

        await self._send_embed(ctx, embed, content=self._role_copy_content(role))

    @commands.hybrid_command(
        name="memberinfo",
        aliases=["minfo", "memberlookup"],
        description="Show detailed information about a server member.",
    )
    @commands.guild_only()
    @commands.bot_has_permissions(embed_links=True)
    async def memberinfo(
        self,
        ctx: commands.Context,
        member: Optional[discord.Member] = None,
    ):
        """Show detailed information about a server member."""
        member = member or ctx.author
        roles = self._member_roles(member)

        embed = self._base_member_embed(member, f"User Info: {member.display_name}")
        embed.add_field(name="User ID", value=self._copy_block(member.id), inline=True)
        embed.add_field(name="Username", value=f"`{member}`", inline=True)

        account_created = self._format_timestamp(member.created_at)
        joined_server = (
            self._format_timestamp(member.joined_at)
            if member.joined_at
            else "Unknown"
        )
        embed.add_field(name="Account Created", value=account_created, inline=True)
        embed.add_field(name="Joined Server", value=joined_server, inline=True)

        role_count = len(roles)
        top_role = self._role_reference(member.top_role) if roles else "None"
        embed.add_field(
            name="Roles",
            value=f"{self._count(role_count)} roles\nTop: {top_role}",
            inline=True,
        )
        embed.add_field(
            name="Important Permissions",
            value=self._member_important_permissions_text(member),
            inline=True,
        )
        embed.add_field(
            name="Profile",
            value=(
                f"Bot: {self._yes_no(member.bot)}\n"
                f"Timed out: {self._yes_no(self._member_is_timed_out(member))}"
            ),
            inline=True,
        )
        embed.add_field(
            name="Role Preview",
            value=self._member_role_preview_text(member),
            inline=False,
        )
        embed.set_footer(text=self._user_footer())

        await self._send_embed(ctx, embed)

    @commands.hybrid_command(
        name="userroles",
        aliases=["memberroles"],
        description="List roles assigned to a server member.",
    )
    @commands.guild_only()
    @commands.bot_has_permissions(embed_links=True)
    async def userroles(
        self,
        ctx: commands.Context,
        member: Optional[discord.Member] = None,
        limit: int = 25,
    ):
        """List roles assigned to a server member."""
        member = member or ctx.author
        limit = max(1, min(limit, 50))
        roles = self._member_roles(member)

        embed = self._base_member_embed(member, f"Roles: {member.display_name}")
        embed.description = (
            f"{member.mention} has {self._count(len(roles))} roles. "
            f"Showing up to {self._count(min(limit, len(roles)))}."
        )

        if roles:
            lines = [
                f"`{index:>2}.` {self._role_reference(role)} - `{role.id}`"
                for index, role in enumerate(roles[:limit], start=1)
            ]
            remaining = len(roles) - len(lines)
            if remaining > 0:
                lines.append(f"...and {self._count(remaining)} more")

            for index, chunk in enumerate(self._line_chunks(lines), start=1):
                field_name = "Roles" if index == 1 else "Roles continued"
                embed.add_field(name=field_name, value=chunk, inline=False)
        else:
            embed.add_field(name="Roles", value="No roles.", inline=False)

        embed.add_field(name="User ID", value=self._copy_block(member.id), inline=False)
        embed.set_footer(text=self._user_footer())

        await self._send_embed(ctx, embed)

    @commands.hybrid_command(
        name="rolecheck",
        aliases=["hasrole"],
        description="Check whether a member has a specific role.",
    )
    @commands.guild_only()
    @commands.bot_has_permissions(embed_links=True)
    async def rolecheck(
        self,
        ctx: commands.Context,
        member: discord.Member,
        role: discord.Role,
    ):
        """Check whether a member has a specific role."""
        has_role = role.is_default() or role in member.roles
        color = discord.Color.green() if has_role else discord.Color.red()
        result = "Has role" if has_role else "Does not have role"

        embed = discord.Embed(
            title="Role Check",
            description=result,
            color=color,
        )
        embed.add_field(name="Member", value=member.mention, inline=True)
        embed.add_field(name="Role", value=self._role_reference(role), inline=True)
        embed.add_field(name="User ID", value=self._copy_block(member.id), inline=True)
        embed.add_field(name="Role ID", value=self._copy_block(role.id), inline=True)

        await self._send_embed(ctx, embed)

    @commands.hybrid_group(
        name="rolemessage",
        aliases=["rolemsg"],
        invoke_without_command=True,
        description="Manage messages posted when roles are given.",
    )
    @commands.guild_only()
    @commands.admin_or_permissions(manage_roles=True)
    @commands.bot_has_permissions(embed_links=True)
    async def rolemessage(self, ctx: commands.Context):
        """Manage messages posted when roles are given."""
        await self._send_role_message_settings(ctx)

    @rolemessage.command(name="list", description="List configured role messages.")
    @commands.guild_only()
    @commands.admin_or_permissions(manage_roles=True)
    @commands.bot_has_permissions(embed_links=True)
    async def rolemessage_list(
        self,
        ctx: commands.Context,
        role: Optional[discord.Role] = None,
    ):
        """List configured role messages."""
        await self._send_role_message_settings(ctx, role)

    @rolemessage.command(name="channel", description="Set where a role's messages post.")
    @commands.guild_only()
    @commands.admin_or_permissions(manage_roles=True)
    async def rolemessage_channel(
        self,
        ctx: commands.Context,
        role: discord.Role,
        channel: discord.TextChannel,
    ):
        """Set where a role's messages post."""
        me = ctx.guild.me
        if me is None or not channel.permissions_for(me).send_messages:
            await ctx.send(
                f"I cannot send messages in {channel.mention}.",
                allowed_mentions=discord.AllowedMentions.none(),
            )
            return

        async with self.config.guild(ctx.guild).role_messages() as role_messages:
            entry = role_messages.setdefault(
                self._role_message_key(role),
                self._default_role_message_settings(),
            )
            entry["channel_id"] = channel.id

        await ctx.send(
            f"Role messages for {self._role_reference(role)} will post in {channel.mention}.",
            allowed_mentions=discord.AllowedMentions.none(),
        )

    @rolemessage.command(name="add", description="Add a message template for a role.")
    @commands.guild_only()
    @commands.admin_or_permissions(manage_roles=True)
    async def rolemessage_add(
        self,
        ctx: commands.Context,
        role: discord.Role,
        *,
        message: str,
    ):
        """Add a message template for a role."""
        message = message.strip()
        if not message:
            await ctx.send("Message cannot be empty.")
            return
        if len(message) > 1800:
            await ctx.send("Message templates must be 1,800 characters or shorter.")
            return

        async with self.config.guild(ctx.guild).role_messages() as role_messages:
            entry = role_messages.setdefault(
                self._role_message_key(role),
                self._default_role_message_settings(),
            )
            messages = entry.setdefault("messages", [])
            if len(messages) >= 10:
                await ctx.send("That role already has the maximum of 10 messages.")
                return
            messages.append(message)
            has_channel = bool(entry.get("channel_id"))

        channel_note = "" if has_channel else " Set a channel with `rolemessage channel` before it can post."
        await ctx.send(
            f"Added message {len(messages)} for {self._role_reference(role)}.{channel_note}",
            allowed_mentions=discord.AllowedMentions.none(),
        )

    @rolemessage.command(name="remove", description="Remove one message template from a role.")
    @commands.guild_only()
    @commands.admin_or_permissions(manage_roles=True)
    async def rolemessage_remove(
        self,
        ctx: commands.Context,
        role: discord.Role,
        index: int,
    ):
        """Remove one message template from a role."""
        async with self.config.guild(ctx.guild).role_messages() as role_messages:
            entry = role_messages.get(self._role_message_key(role))
            if not entry or not entry.get("messages"):
                await ctx.send("That role has no messages configured.")
                return

            messages = entry["messages"]
            if index < 1 or index > len(messages):
                await ctx.send(f"Index must be between 1 and {len(messages)}.")
                return

            removed = messages.pop(index - 1)

        await ctx.send(
            f"Removed message {index} for {self._role_reference(role)}: `{removed[:120]}`",
            allowed_mentions=discord.AllowedMentions.none(),
        )

    @rolemessage.command(name="clear", description="Remove all role message settings for a role.")
    @commands.guild_only()
    @commands.admin_or_permissions(manage_roles=True)
    async def rolemessage_clear(
        self,
        ctx: commands.Context,
        role: discord.Role,
    ):
        """Remove all role message settings for a role."""
        async with self.config.guild(ctx.guild).role_messages() as role_messages:
            removed = role_messages.pop(self._role_message_key(role), None)

        if removed:
            await ctx.send(
                f"Cleared role messages for {self._role_reference(role)}.",
                allowed_mentions=discord.AllowedMentions.none(),
            )
        else:
            await ctx.send("That role had no role messages configured.")

    @rolemessage.command(name="toggle", description="Enable or disable role messages for a role.")
    @commands.guild_only()
    @commands.admin_or_permissions(manage_roles=True)
    async def rolemessage_toggle(
        self,
        ctx: commands.Context,
        role: discord.Role,
        enabled: Optional[bool] = None,
    ):
        """Enable or disable role messages for a role."""
        async with self.config.guild(ctx.guild).role_messages() as role_messages:
            entry = role_messages.setdefault(
                self._role_message_key(role),
                self._default_role_message_settings(),
            )
            entry["enabled"] = not entry.get("enabled", True) if enabled is None else enabled
            enabled_text = self._yes_no(entry["enabled"])

        await ctx.send(
            f"Role messages for {self._role_reference(role)} enabled: {enabled_text}.",
            allowed_mentions=discord.AllowedMentions.none(),
        )

    @rolemessage.command(name="mode", description="Set whether role messages post all or one random message.")
    @commands.guild_only()
    @commands.admin_or_permissions(manage_roles=True)
    async def rolemessage_mode(
        self,
        ctx: commands.Context,
        role: discord.Role,
        mode: str,
    ):
        """Set whether role messages post all or one random message."""
        mode = mode.casefold()
        if mode not in {"all", "random"}:
            await ctx.send("Mode must be `all` or `random`.")
            return

        async with self.config.guild(ctx.guild).role_messages() as role_messages:
            entry = role_messages.setdefault(
                self._role_message_key(role),
                self._default_role_message_settings(),
            )
            entry["mode"] = mode

        await ctx.send(
            f"Role messages for {self._role_reference(role)} will use `{mode}` mode.",
            allowed_mentions=discord.AllowedMentions.none(),
        )

    @rolemessage.command(name="test", description="Preview the configured messages for a role.")
    @commands.guild_only()
    @commands.admin_or_permissions(manage_roles=True)
    async def rolemessage_test(
        self,
        ctx: commands.Context,
        role: discord.Role,
        member: Optional[discord.Member] = None,
    ):
        """Preview the configured messages for a role."""
        member = member or ctx.author
        role_messages = await self.config.guild(ctx.guild).role_messages()
        entry = role_messages.get(self._role_message_key(role))
        if not entry or not entry.get("messages"):
            await ctx.send("That role has no messages configured.")
            return

        allowed_mentions = discord.AllowedMentions(
            users=True,
            roles=False,
            everyone=False,
        )
        messages = entry["messages"]
        if self._role_message_mode(entry) == "random":
            messages = [random.choice(messages)]

        for template in messages:
            await ctx.send(
                self._render_role_message(template, member, role),
                allowed_mentions=allowed_mentions,
            )

    @rolemessage.command(name="placeholders", description="Show role message placeholders.")
    @commands.guild_only()
    @commands.admin_or_permissions(manage_roles=True)
    @commands.bot_has_permissions(embed_links=True)
    async def rolemessage_placeholders(self, ctx: commands.Context):
        """Show role message placeholders."""
        placeholders = (
            "`{user}` - member mention\n"
            "`{username}` - username and discriminator/global name\n"
            "`{display_name}` - server display name\n"
            "`{user_id}` - member ID\n"
            "`{role}` - role mention\n"
            "`{role_name}` - role name\n"
            "`{role_id}` - role ID\n"
            "`{server}` - server name\n"
            "`{server_id}` - server ID"
        )
        embed = discord.Embed(
            title="Role Message Placeholders",
            description=placeholders,
            color=discord.Color.blurple(),
        )
        await self._send_embed(ctx, embed)

    @rolemessage.command(
        name="setup",
        aliases=["guide", "help"],
        description="Show role message setup steps and examples.",
    )
    @commands.guild_only()
    @commands.admin_or_permissions(manage_roles=True)
    @commands.bot_has_permissions(embed_links=True)
    async def rolemessage_setup(self, ctx: commands.Context):
        """Show role message setup steps and examples."""
        prefix = getattr(ctx, "clean_prefix", "[p]")
        embed = discord.Embed(
            title="Role Message Setup",
            description="Post one or more messages when a configured role is given to a member.",
            color=discord.Color.blurple(),
        )
        embed.add_field(
            name="Setup Steps",
            value=(
                f"`{prefix}rolemessage channel @Role #channel`\n"
                f"`{prefix}rolemessage add @Role Welcome {{user}}, you now have {{role}}!`\n"
                f"`{prefix}rolemessage test @Role @Member`"
            ),
            inline=False,
        )
        embed.add_field(
            name="Manage",
            value=(
                f"`{prefix}rolemessage list [role]`\n"
                f"`{prefix}rolemessage remove <role> <index>`\n"
                f"`{prefix}rolemessage mode <role> all_or_random`\n"
                f"`{prefix}rolemessage toggle <role> [true_or_false]`\n"
                f"`{prefix}rolemessage clear <role>`"
            ),
            inline=False,
        )
        embed.add_field(
            name="Placeholders",
            value=(
                "`{user}` mention, `{display_name}`, `{username}`, `{user_id}`\n"
                "`{role}` mention, `{role_name}`, `{role_id}`\n"
                "`{server}`, `{server_id}`"
            ),
            inline=False,
        )
        embed.add_field(
            name="Notes",
            value=(
                "The bot needs permission to send messages in the target channel. "
                "Automatic posting also needs the Server Members intent."
            ),
            inline=False,
        )
        await self._send_embed(ctx, embed)

    @commands.hybrid_command(
        name="roleaudit",
        aliases=["auditroles"],
        description="Audit roles by elevated permissions, empty roles, managed roles, or mentionable roles.",
    )
    @commands.guild_only()
    @commands.admin_or_permissions(manage_roles=True)
    @commands.bot_has_permissions(embed_links=True)
    async def roleaudit(
        self,
        ctx: commands.Context,
        mode: str = "elevated",
        limit: int = 25,
    ):
        """Audit roles by elevated, empty, managed, or mentionable status."""
        valid_modes = {"elevated", "empty", "managed", "mentionable"}
        mode = mode.casefold()
        if mode not in valid_modes:
            await ctx.send("Mode must be one of: elevated, empty, managed, mentionable.")
            return

        cache_ready = await self._get_cache_status(ctx)
        limit = max(1, min(limit, 50))

        roles = list(ctx.guild.roles)
        if mode == "elevated":
            matched_roles = [
                role for role in roles if self._has_important_permissions(role)
            ]
        elif mode == "empty":
            matched_roles = [
                role
                for role in roles
                if not role.is_default() and self._role_member_count(role) == 0
            ]
        elif mode == "managed":
            matched_roles = [
                role for role in roles if not role.is_default() and role.managed
            ]
        else:
            matched_roles = [
                role
                for role in roles
                if not role.is_default() and role.mentionable
            ]

        matched_roles = sorted(
            matched_roles,
            key=lambda role: role.position,
            reverse=True,
        )

        title = f"Role Audit: {mode.title()}"
        embed = discord.Embed(
            title=title,
            description=(
                f"Found {self._count(len(matched_roles))} matching roles. "
                f"Showing up to {self._count(min(limit, len(matched_roles)))}."
            ),
            color=discord.Color.orange(),
        )

        if matched_roles:
            lines = []
            for index, role in enumerate(matched_roles[:limit], start=1):
                details = f"{self._count(self._role_member_count(role))} members"
                if mode == "elevated":
                    details = self._important_permissions_text(role)
                lines.append(
                    f"`{index:>2}.` {self._role_reference(role)} - {details} - `{role.id}`"
                )

            remaining = len(matched_roles) - len(lines)
            if remaining > 0:
                lines.append(f"...and {self._count(remaining)} more")

            for index, chunk in enumerate(self._line_chunks(lines), start=1):
                field_name = "Roles" if index == 1 else "Roles continued"
                embed.add_field(name=field_name, value=chunk, inline=False)
        else:
            embed.add_field(name="Roles", value=f"No `{mode}` roles found.", inline=False)

        embed.set_footer(text=self._cache_footer(cache_ready))
        await self._send_embed(ctx, embed)

    @commands.hybrid_command(
        name="rolecompare",
        aliases=["compareroles"],
        description="Compare two roles and show member overlap.",
    )
    @commands.guild_only()
    @commands.bot_has_permissions(embed_links=True)
    async def rolecompare(
        self,
        ctx: commands.Context,
        role_one: discord.Role,
        role_two: discord.Role,
        limit: int = 10,
    ):
        """Compare two roles and show member overlap."""
        cache_ready = await self._get_cache_status(ctx)
        limit = max(1, min(limit, 25))

        role_one_members = {
            member.id: member for member in self._role_members(role_one)
        }
        role_two_members = {
            member.id: member for member in self._role_members(role_two)
        }
        role_one_ids = set(role_one_members)
        role_two_ids = set(role_two_members)

        both_ids = role_one_ids & role_two_ids
        only_one_ids = role_one_ids - role_two_ids
        only_two_ids = role_two_ids - role_one_ids

        both_members = sorted(
            [role_one_members[member_id] for member_id in both_ids],
            key=lambda member: member.display_name.casefold(),
        )
        only_one_members = sorted(
            [role_one_members[member_id] for member_id in only_one_ids],
            key=lambda member: member.display_name.casefold(),
        )
        only_two_members = sorted(
            [role_two_members[member_id] for member_id in only_two_ids],
            key=lambda member: member.display_name.casefold(),
        )

        embed = discord.Embed(
            title="Role Compare",
            description=f"{self._role_reference(role_one)} vs {self._role_reference(role_two)}",
            color=discord.Color.blurple(),
        )
        embed.add_field(
            name="Summary",
            value=(
                f"{self._safe_role_name(role_one)}: {self._count(len(role_one_ids))}\n"
                f"{self._safe_role_name(role_two)}: {self._count(len(role_two_ids))}\n"
                f"Both: {self._count(len(both_ids))}"
            ),
            inline=False,
        )
        embed.add_field(name="First Role ID", value=self._copy_block(role_one.id), inline=True)
        embed.add_field(name="Second Role ID", value=self._copy_block(role_two.id), inline=True)

        sections = (
            ("In Both", both_members),
            (f"Only {self._safe_role_name(role_one)}", only_one_members),
            (f"Only {self._safe_role_name(role_two)}", only_two_members),
        )
        for section_name, members in sections:
            lines = self._member_summary_lines(members, limit) if members else ["None"]
            for index, chunk in enumerate(self._line_chunks(lines), start=1):
                field_name = section_name if index == 1 else f"{section_name} continued"
                embed.add_field(name=field_name, value=chunk, inline=False)

        embed.set_footer(text=self._cache_footer(cache_ready))
        await self._send_embed(ctx, embed)

    @commands.hybrid_command(
        name="userpermissions",
        aliases=["uperms", "memberpermissions"],
        description="Show a member's important server permissions and source roles.",
    )
    @commands.guild_only()
    @commands.bot_has_permissions(embed_links=True)
    async def userpermissions(
        self,
        ctx: commands.Context,
        member: Optional[discord.Member] = None,
    ):
        """Show a member's important server permissions and source roles."""
        member = member or ctx.author
        permissions = member.guild_permissions

        lines = []
        for attr, label in self.IMPORTANT_PERMISSIONS:
            if getattr(permissions, attr, False):
                lines.append(f"{label}: {self._permission_source_text(member, attr)}")

        embed = self._base_member_embed(member, f"Permissions: {member.display_name}")
        embed.add_field(name="User ID", value=self._copy_block(member.id), inline=True)
        embed.add_field(
            name="Top Role",
            value=self._role_reference(member.top_role)
            if self._member_roles(member)
            else "None",
            inline=True,
        )

        if lines:
            for index, chunk in enumerate(self._line_chunks(lines), start=1):
                field_name = "Important Permissions" if index == 1 else "Permissions continued"
                embed.add_field(name=field_name, value=chunk, inline=False)
        else:
            embed.add_field(
                name="Important Permissions",
                value="No elevated permissions detected.",
                inline=False,
            )

        embed.set_footer(text=self._user_footer())
        await self._send_embed(ctx, embed)

    @commands.hybrid_command(
        name="noroles",
        aliases=["noroleusers", "unroled"],
        description="List members with no roles except @everyone.",
    )
    @commands.guild_only()
    @commands.admin_or_permissions(manage_roles=True)
    @commands.bot_has_permissions(embed_links=True)
    async def noroles(
        self,
        ctx: commands.Context,
        limit: int = 25,
        include_bots: bool = False,
    ):
        """List members with no roles except @everyone."""
        cache_ready = await self._get_cache_status(ctx)
        limit = max(1, min(limit, 50))

        members = [
            member
            for member in ctx.guild.members
            if len(self._member_roles(member)) == 0 and (include_bots or not member.bot)
        ]
        members = sorted(members, key=self._joined_sort_key)

        embed = discord.Embed(
            title="Members With No Roles",
            description=(
                f"Found {self._count(len(members))} members with no roles. "
                f"Bots included: {self._yes_no(include_bots)}."
            ),
            color=discord.Color.orange(),
        )

        if members:
            lines = self._member_summary_lines(members, limit)
            for index, chunk in enumerate(self._line_chunks(lines), start=1):
                field_name = "Members" if index == 1 else "Members continued"
                embed.add_field(name=field_name, value=chunk, inline=False)
        else:
            embed.add_field(name="Members", value="No matching members found.", inline=False)

        embed.set_footer(text=self._cache_footer(cache_ready))
        await self._send_embed(ctx, embed)

    @commands.hybrid_command(
        name="bots",
        aliases=["botlist"],
        description="List bot accounts in the server.",
    )
    @commands.guild_only()
    @commands.admin_or_permissions(manage_roles=True)
    @commands.bot_has_permissions(embed_links=True)
    async def bots(
        self,
        ctx: commands.Context,
        limit: int = 25,
    ):
        """List bot accounts in the server."""
        cache_ready = await self._get_cache_status(ctx)
        limit = max(1, min(limit, 50))

        members = sorted(
            [member for member in ctx.guild.members if member.bot],
            key=lambda member: member.display_name.casefold(),
        )

        embed = discord.Embed(
            title="Server Bots",
            description=f"Found {self._count(len(members))} bot accounts.",
            color=discord.Color.blurple(),
        )

        if members:
            lines = []
            for index, member in enumerate(members[:limit], start=1):
                elevated = (
                    self._member_important_permissions_text(member)
                    != "No elevated permissions detected"
                )
                status = "elevated" if elevated else "standard"
                top_role = (
                    self._role_reference(member.top_role)
                    if self._member_roles(member)
                    else "None"
                )
                lines.append(
                    f"`{index:>2}.` {member.mention} - {top_role} - {status} - `{member.id}`"
                )

            remaining = len(members) - len(lines)
            if remaining > 0:
                lines.append(f"...and {self._count(remaining)} more")

            for index, chunk in enumerate(self._line_chunks(lines), start=1):
                field_name = "Bots" if index == 1 else "Bots continued"
                embed.add_field(name=field_name, value=chunk, inline=False)
        else:
            embed.add_field(name="Bots", value="No bot accounts found.", inline=False)

        embed.set_footer(text=self._cache_footer(cache_ready))
        await self._send_embed(ctx, embed)

    @commands.hybrid_command(
        name="rolehierarchy",
        aliases=["roleorder"],
        description="Show server roles in hierarchy order.",
    )
    @commands.guild_only()
    @commands.bot_has_permissions(embed_links=True)
    async def rolehierarchy(
        self,
        ctx: commands.Context,
        limit: int = 30,
        include_empty: bool = True,
    ):
        """Show server roles in hierarchy order."""
        cache_ready = await self._get_cache_status(ctx)
        limit = max(1, min(limit, 50))

        roles = [
            role
            for role in ctx.guild.roles
            if not role.is_default()
            and (include_empty or self._role_member_count(role) > 0)
        ]
        roles = sorted(roles, key=lambda role: role.position, reverse=True)

        embed = discord.Embed(
            title="Role Hierarchy",
            description=(
                f"Showing {self._count(min(limit, len(roles)))} of "
                f"{self._count(len(roles))} roles. "
                f"Empty roles included: {self._yes_no(include_empty)}."
            ),
            color=discord.Color.blurple(),
        )

        if roles:
            lines = [
                f"`{index:>2}.` pos {role.position} - {self._role_reference(role)} - "
                f"{self._count(self._role_member_count(role))} members - `{role.id}`"
                for index, role in enumerate(roles[:limit], start=1)
            ]

            remaining = len(roles) - len(lines)
            if remaining > 0:
                lines.append(f"...and {self._count(remaining)} more")

            for index, chunk in enumerate(self._line_chunks(lines), start=1):
                field_name = "Roles" if index == 1 else "Roles continued"
                embed.add_field(name=field_name, value=chunk, inline=False)
        else:
            embed.add_field(name="Roles", value="No matching roles found.", inline=False)

        embed.set_footer(text=self._cache_footer(cache_ready))
        await self._send_embed(ctx, embed)

    @commands.hybrid_command(
        name="rolesearch",
        aliases=["findrole"],
        description="Search server roles by name or ID.",
    )
    @commands.guild_only()
    @commands.bot_has_permissions(embed_links=True)
    async def rolesearch(self, ctx: commands.Context, *, query: str):
        """Search roles by name or ID."""
        query = query.strip()
        if not query:
            await ctx.send("Give me a role name or ID to search for.")
            return

        cache_ready = await self._get_cache_status(ctx)
        lowered = query.casefold()

        matches = [
            role
            for role in ctx.guild.roles
            if lowered in role.name.casefold() or query in str(role.id)
        ]
        matches = sorted(matches, key=lambda role: role.position, reverse=True)

        embed = discord.Embed(
            title="Role Search",
            description=f"Query: `{query}`",
            color=discord.Color.blurple(),
        )

        if not matches:
            embed.description = f"No roles matched `{query}`."
            embed.set_footer(text=self._cache_footer(cache_ready))
            await self._send_embed(ctx, embed)
            return

        lines = []
        for index, role in enumerate(matches[:20], start=1):
            lines.append(
                f"`{index:>2}.` {self._role_reference(role)} - "
                f"{self._count(self._role_member_count(role))} members - `{role.id}`"
            )

        if len(matches) > 20:
            lines.append(f"...and {self._count(len(matches) - 20)} more matches")

        for index, chunk in enumerate(self._line_chunks(lines), start=1):
            field_name = f"Matches ({self._count(len(matches))})" if index == 1 else "Matches continued"
            embed.add_field(name=field_name, value=chunk, inline=False)

        embed.set_footer(text=self._cache_footer(cache_ready))
        await self._send_embed(ctx, embed)

    @commands.hybrid_command(
        name="rolelist",
        aliases=["serverroles"],
        description="List server roles sorted by members, position, name, or color.",
    )
    @commands.guild_only()
    @commands.bot_has_permissions(embed_links=True)
    async def rolelist(
        self,
        ctx: commands.Context,
        sort: str = "members",
        limit: int = 20,
    ):
        """List roles sorted by members, position, name, or color."""
        sort = sort.casefold()
        if sort not in self.VALID_ROLE_SORTS:
            await ctx.send("Sort must be one of: members, position, name, color.")
            return

        limit = max(1, min(limit, 50))
        cache_ready = await self._get_cache_status(ctx)

        roles: Sequence[discord.Role] = [
            role for role in ctx.guild.roles if not role.is_default()
        ]

        if sort == "members":
            roles = sorted(roles, key=self._role_member_count, reverse=True)
        elif sort == "position":
            roles = sorted(roles, key=lambda role: role.position, reverse=True)
        elif sort == "name":
            roles = sorted(roles, key=lambda role: role.name.casefold())
        elif sort == "color":
            roles = sorted(roles, key=lambda role: role.color.value, reverse=True)

        shown_roles = roles[:limit]
        lines = []
        for index, role in enumerate(shown_roles, start=1):
            lines.append(
                f"`{index:>2}.` {self._role_reference(role)} - "
                f"{self._count(self._role_member_count(role))} members - `{role.id}`"
            )

        embed = discord.Embed(
            title="Server Roles",
            description=(
                f"Sorted by `{sort}`. Showing {self._count(len(shown_roles))} "
                f"of {self._count(len(roles))} roles."
            ),
            color=discord.Color.blurple(),
        )
        if lines:
            for index, chunk in enumerate(self._line_chunks(lines), start=1):
                field_name = "Roles" if index == 1 else "Roles continued"
                embed.add_field(name=field_name, value=chunk, inline=False)
        else:
            embed.add_field(name="Roles", value="This server has no roles to list.", inline=False)

        embed.set_footer(text=self._cache_footer(cache_ready))

        await self._send_embed(ctx, embed)

    @commands.hybrid_command(
        name="rolemembers",
        aliases=["roleusers"],
        description="Preview members who have a role.",
    )
    @commands.guild_only()
    @commands.bot_has_permissions(embed_links=True)
    async def rolemembers(
        self,
        ctx: commands.Context,
        role: discord.Role,
        limit: int = 25,
    ):
        """Preview members who have a role."""
        limit = max(1, min(limit, 50))
        cache_ready = await self._get_cache_status(ctx)
        members = sorted(
            self._role_members(role),
            key=lambda member: member.display_name.casefold(),
        )

        embed = self._base_role_embed(role, f"Members: {self._safe_role_name(role)}")
        embed.description = (
            f"{self._role_reference(role)} has {self._member_count_text(role)} members."
        )

        if not members:
            embed.add_field(name="Members", value="No cached members have this role.", inline=False)
        else:
            lines = [
                f"`{index:>3}.` {member.display_name} (`{member.id}`)"
                for index, member in enumerate(members[:limit], start=1)
            ]
            remaining = len(members) - len(lines)
            if remaining > 0:
                lines.append(f"...and {self._count(remaining)} more")

            for index, chunk in enumerate(self._line_chunks(lines), start=1):
                field_name = (
                    f"Showing {self._count(min(limit, len(members)))} members"
                    if index == 1
                    else "Members continued"
                )
                embed.add_field(name=field_name, value=chunk, inline=False)

        embed.add_field(name="Role ID", value=self._copy_block(role.id), inline=False)
        embed.set_footer(text=self._cache_footer(cache_ready))

        await self._send_embed(ctx, embed)

    @commands.hybrid_command(
        name="roleexport",
        aliases=["rolecsv"],
        description="Export role members to a CSV file.",
    )
    @commands.guild_only()
    @commands.admin_or_permissions(manage_roles=True)
    @commands.bot_has_permissions(embed_links=True, attach_files=True)
    async def roleexport(self, ctx: commands.Context, role: discord.Role):
        """Export role members to a CSV file."""
        cache_ready = await self._get_cache_status(ctx)
        members = sorted(
            self._role_members(role),
            key=lambda member: member.display_name.casefold(),
        )

        buffer = io.StringIO()
        writer = csv.writer(buffer)
        writer.writerow(("user_id", "username", "display_name", "is_bot"))
        for member in members:
            writer.writerow((member.id, str(member), member.display_name, member.bot))

        data = io.BytesIO(buffer.getvalue().encode("utf-8"))
        filename = self._export_filename(role)
        file = discord.File(data, filename=filename)

        embed = self._base_role_embed(role, f"Role Export: {self._safe_role_name(role)}")
        embed.description = (
            f"Exported {self._count(len(members))} cached members for "
            f"{self._role_reference(role)}."
        )
        embed.add_field(name="Role ID", value=self._copy_block(role.id), inline=True)
        embed.add_field(name="File", value=f"`{filename}`", inline=True)
        embed.set_footer(text=self._cache_footer(cache_ready))

        await self._send_embed(ctx, embed, file=file)

    @staticmethod
    def _export_filename(role: discord.Role) -> str:
        safe_name = "".join(
            char if char.isascii() and (char.isalnum() or char in {"-", "_"}) else "_"
            for char in role.name
        ).strip("_")
        safe_name = safe_name[:50] or "role"
        return f"{safe_name}_{role.id}_members.csv"
