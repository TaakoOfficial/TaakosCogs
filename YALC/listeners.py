"""YALC listeners module - Contains all event listeners for logging."""
import discord
from discord import app_commands
from redbot.core import commands, modlog
from typing import Dict, List, Optional, Union, cast, TYPE_CHECKING
import datetime
import asyncio

if TYPE_CHECKING:
    from .yalc import YALC

class Listeners(commands.Cog):
    """Event listener class for YALC."""

    def __init__(self, cog: "YALC") -> None:
        """Initialize Listeners class."""
        super().__init__()
        self.bot = cog.bot
        self.cog = cog
        self._cached_deletes: Dict[int, discord.Message] = {}
        self._cached_edits: Dict[int, discord.Message] = {}
        
    async def _safe_send(self, channel: Optional[discord.abc.GuildChannel], embed: discord.Embed, guild: discord.Guild, event_type: str) -> None:
        """Safely send an embed to a channel with validation and logging."""
        if not isinstance(channel, discord.TextChannel):
            self.cog.log.warning(f"[YALC] Channel for event '{event_type}' is not a TextChannel: {channel}")
            return
        perms = channel.permissions_for(guild.me)
        if not (perms.send_messages and perms.embed_links):
            self.cog.log.warning(f"[YALC] Missing permissions in channel {channel.id} for event '{event_type}' (send_messages: {perms.send_messages}, embed_links: {perms.embed_links})")
            return
        try:
            await channel.send(embed=embed)
            self.cog.log.debug(f"[YALC] Sent embed to channel {channel.id} for event '{event_type}'")
        except Exception as e:
            self.cog.log.error(f"[YALC] Failed to send embed to channel {channel.id} for event '{event_type}': {e}")

    @commands.Cog.listener()
    async def on_message_delete(self, message: discord.Message) -> None:
        """Handle message deletion events."""
        if not message.guild or not await self.cog.should_log_event(message.guild, "message_delete"):
            return

        channel = await self.cog.get_log_channel(message.guild, "message_delete")
        self.cog.log.debug(f"[YALC] Resolved channel for message_delete: {channel}")

        embed = self.cog.create_embed(
            "message_delete",
            f"🗑️ Message deleted in {self._get_channel_str(message.channel)}",
            user=f"{message.author} ({message.author.id})",
            content=message.content,
            attachments=[a.url for a in message.attachments],
            embeds=message.embeds
        )

        await self._safe_send(channel, embed, message.guild, "message_delete")
        try:
            await modlog.create_case(
                guild=message.guild,
                case_type="message_delete",
                user=message.author,
                moderator=None,
                reason=None,
                until=None,
                extra={
                    "content": message.content,
                    "attachments": [a.url for a in message.attachments],
                    "embeds": message.embeds
                }
            )
        except Exception as e:
            self.cog.log.error(f"Failed to create modlog case for message_delete: {e}")

    @commands.Cog.listener()
    async def on_message_edit(self, before: discord.Message, after: discord.Message) -> None:
        """Handle message edit events."""
        if not before.guild or not await self.cog.should_log_event(before.guild, "message_edit"):
            return

        channel = await self.cog.get_log_channel(before.guild, "message_edit")
        if not channel:
            return

        embed = self.cog.create_embed(
            "message_edit",
            f"✏️ Message edited in {self._get_channel_str(before.channel)}",
            user=f"{before.author} ({before.author.id})",
            content=f"**Before:** {before.content}\n**After:** {after.content}",
            attachments=[a.url for a in after.attachments],
            embeds=after.embeds
        )

        await self._safe_send(channel, embed, before.guild, "message_edit")
        try:
            await modlog.create_case(
                guild=before.guild,
                case_type="message_edit",
                user=before.author,
                moderator=None,
                reason=None,
                until=None,
                extra={
                    "before": before.content,
                    "after": after.content,
                    "attachments": [a.url for a in after.attachments],
                    "embeds": after.embeds
                }
            )
        except Exception as e:
            self.cog.log.error(f"Failed to create modlog case for message_edit: {e}")

    def _get_channel_str(self, channel: object) -> str:
        """Get a string representation of any channel or messageable object."""
        if channel is None:
            return "Unknown Channel"
        if hasattr(channel, "mention"):
            return str(getattr(channel, "mention", str(channel)))
        if hasattr(channel, "name"):
            return f"#{getattr(channel, 'name', str(channel))}"
        return str(channel)

    async def _should_log_event(self, guild: discord.Guild, event_type: str, channel: Optional[discord.abc.GuildChannel] = None) -> bool:
        """Check if an event should be logged."""
        return await self.cog.should_log_event(guild, event_type, channel)

    def _get_command_path(self, command: Optional[Union[discord.app_commands.Command, discord.app_commands.ContextMenu]]) -> str:
        """Get the full path of a command including parent groups.
        
        Parameters
        ----------
        command: Optional[Union[discord.app_commands.Command, discord.app_commands.ContextMenu]]
            The command to get the path for
            
        Returns
        -------
        str
            The full command path
        """
        if not command:
            return "Unknown"
            
        parts = [command.name]
        current = getattr(command, "parent", None)
        while current:
            parts.append(current.name)
            current = getattr(current, "parent", None)
        return "/" + " ".join(reversed(parts))

    @commands.Cog.listener()
    async def on_application_command(self, interaction: discord.Interaction) -> None:
        """Log slash command usage."""
        if not interaction.guild or not await self.cog.should_log_event(interaction.guild, "application_cmd"):
            return

        # Skip if command is in ignore list
        settings = await self.cog.config.guild(interaction.guild).all()
        if interaction.command and interaction.command.name in settings.get("ignored_commands", []):
            return

        channel = await self.cog.get_log_channel(interaction.guild, "application_cmd")
        if not channel:
            return

        # Get command path and options
        cmd_str = self._get_command_path(interaction.command)
        
        # Add options if present
        options = []
        if interaction.data and "options" in interaction.data:
            for option in interaction.data.get("options", []):
                name = option.get("name")
                value = option.get("value")
                if name and value is not None:
                    options.append(f"{name}={value}")
        if options:
            cmd_str += " " + " ".join(options)

        embed = self.cog.create_embed(
            "application_cmd",
            f"Slash command used in {self._get_channel_str(interaction.channel)}",
            user=f"{interaction.user} ({interaction.user.id})",
            command=f"`{cmd_str}`"
        )

        await self._safe_send(channel, embed, interaction.guild, "application_cmd")
        try:
            await modlog.create_case(
                guild=interaction.guild,
                case_type="application_cmd",
                user=interaction.user,
                moderator=None,
                reason=None,
                until=None,
                extra={"command": cmd_str}
            )
        except Exception as e:
            self.cog.log.error(f"Failed to create modlog case for application_cmd: {e}")

    @commands.Cog.listener()
    async def on_application_command_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError) -> None:
        """Log slash command errors."""
        if not interaction.guild or not await self.cog.should_log_event(interaction.guild, "command_error"):
            return

        # Skip if command is in ignore list
        settings = await self.cog.config.guild(interaction.guild).all()
        if interaction.command and interaction.command.name in settings.get("ignored_commands", []):
            return

        channel = await self.cog.get_log_channel(interaction.guild, "command_error")
        if not channel:
            return

        cmd_str = self._get_command_path(interaction.command)

        embed = self.cog.create_embed(
            "command_error",
            f"Slash command error in {self._get_channel_str(interaction.channel)}",
            user=f"{interaction.user} ({interaction.user.id})",
            command=f"`{cmd_str}`",
            error=str(error),
            error_type=error.__class__.__name__
        )

        await self._safe_send(channel, embed, interaction.guild, "command_error")
        try:
            await modlog.create_case(
                guild=interaction.guild,
                case_type="command_error",
                user=interaction.user,
                moderator=None,
                reason=str(error),
                until=None,
                extra={
                    "command": cmd_str,
                    "error_type": error.__class__.__name__
                }
            )
        except Exception as e:
            self.cog.log.error(f"Failed to create modlog case for command_error: {e}")

    @commands.Cog.listener()
    async def on_thread_create(self, thread: discord.Thread) -> None:
        """Log thread creation."""
        if not await self.cog.should_log_event(thread.guild, "thread_create"):
            return

        channel = await self.cog.get_log_channel(thread.guild, "thread_create")
        if not channel:
            return

        embed = self.cog.create_embed(
            "thread_create",
            f"🧵 Thread created in {self._get_channel_str(thread.parent)}",
            thread=thread.mention,
            name=thread.name,
            creator=f"{thread.owner} ({thread.owner_id})" if thread.owner else f"ID: {thread.owner_id}",
            type=str(thread.type),
            slowmode=f"{thread.slowmode_delay}s" if thread.slowmode_delay else "None"
        )

        await self._safe_send(channel, embed, thread.guild, "thread_create")
        try:
            await modlog.create_case(
                guild=thread.guild,
                case_type="thread_create",
                user=thread.owner,
                moderator=None,
                reason=None,
                until=None,
                extra={
                    "thread": thread.name,
                    "type": str(thread.type)
                }
            )
        except Exception as e:
            self.cog.log.error(f"Failed to create modlog case for thread_create: {e}")

    @commands.Cog.listener()
    async def on_thread_delete(self, thread: discord.Thread) -> None:
        """Log thread deletion."""
        if not await self.cog.should_log_event(thread.guild, "thread_delete"):
            return

        channel = await self.cog.get_log_channel(thread.guild, "thread_delete")
        if not channel:
            return

        embed = self.cog.create_embed(
            "thread_delete",
            f"🗑️ Thread deleted from {self._get_channel_str(thread.parent)}",
            name=thread.name,
            archived=thread.archived,
            locked=thread.locked,
            type=str(thread.type)
        )

        await self._safe_send(channel, embed, thread.guild, "thread_delete")
        try:
            await modlog.create_case(
                guild=thread.guild,
                case_type="thread_delete",
                user=None,
                moderator=None,
                reason=None,
                until=None,
                extra={
                    "thread": thread.name,
                    "archived": thread.archived,
                    "locked": thread.locked,
                    "type": str(thread.type)
                }
            )
        except Exception as e:
            self.cog.log.error(f"Failed to create modlog case for thread_delete: {e}")

    @commands.Cog.listener()
    async def on_thread_update(self, before: discord.Thread, after: discord.Thread) -> None:
        """Log thread updates."""
        if not await self.cog.should_log_event(before.guild, "thread_update"):
            return

        channel = await self.cog.get_log_channel(before.guild, "thread_update")
        if not channel:
            return

        changes = []
        
        if before.name != after.name:
            changes.append(f"Name: {before.name} → {after.name}")
        if before.archived != after.archived:
            changes.append(f"Archived: {before.archived} → {after.archived}")
        if before.locked != after.locked:
            changes.append(f"Locked: {before.locked} → {after.locked}")
        if before.slowmode_delay != after.slowmode_delay:
            changes.append(f"Slowmode: {before.slowmode_delay}s → {after.slowmode_delay}s")
        if before.auto_archive_duration != after.auto_archive_duration:
            changes.append(f"Auto Archive: {before.auto_archive_duration} minutes → {after.auto_archive_duration} minutes")

        if not changes:
            return

        embed = self.cog.create_embed(
            "thread_update",
            f"🔄 Thread updated in {self._get_channel_str(after.parent)}",
            thread=after.mention,
            changes="\n".join(changes)
        )

        await self._safe_send(channel, embed, before.guild, "thread_update")
        try:
            await modlog.create_case(
                guild=before.guild,
                case_type="thread_update",
                user=None,
                moderator=None,
                reason=None,
                until=None,
                extra={"changes": changes, "thread": after.name}
            )
        except Exception as e:
            self.cog.log.error(f"Failed to create modlog case for thread_update: {e}")

    @commands.Cog.listener()
    async def on_thread_member_join(self, member: discord.ThreadMember) -> None:
        """Log thread member joins."""
        if not await self.cog.should_log_event(member.thread.guild, "thread_member_join"):
            return

        channel = await self.cog.get_log_channel(member.thread.guild, "thread_member_join")
        if not channel:
            return

        embed = self.cog.create_embed(
            "thread_member_join",
            f"➡️ Member joined thread {member.thread.mention}",
            member=f"{member} ({member.id})",
            thread=member.thread.name
        )

        await self._safe_send(channel, embed, member.thread.guild, "thread_member_join")
        try:
            await modlog.create_case(
                guild=member.thread.guild,
                case_type="thread_member_join",
                user=member,
                moderator=None,
                reason=None,
                until=None,
                extra={"thread": member.thread.name}
            )
        except Exception as e:
            self.cog.log.error(f"Failed to create modlog case for thread_member_join: {e}")

    @commands.Cog.listener()
    async def on_thread_member_remove(self, member: discord.ThreadMember) -> None:
        """Log thread member leaves."""
        if not await self.cog.should_log_event(member.thread.guild, "thread_member_leave"):
            return

        channel = await self.cog.get_log_channel(member.thread.guild, "thread_member_leave")
        if not channel:
            return

        embed = self.cog.create_embed(
            "thread_member_leave",
            f"⬅️ Member left thread {member.thread.mention}",
            member=f"{member} ({member.id})",
            thread=member.thread.name
        )

        await self._safe_send(channel, embed, member.thread.guild, "thread_member_leave")
        try:
            await modlog.create_case(
                guild=member.thread.guild,
                case_type="thread_member_leave",
                user=member,
                moderator=None,
                reason=None,
                until=None,
                extra={"thread": member.thread.name}
            )
        except Exception as e:
            self.cog.log.error(f"Failed to create modlog case for thread_member_leave: {e}")

    @commands.Cog.listener()
    async def on_guild_channel_create(self, channel: discord.abc.GuildChannel) -> None:
        """Log channel creation events."""
        if not channel.guild or not await self.cog.should_log_event(channel.guild, "channel_create", channel):
            return
        log_channel = await self.cog.get_log_channel(channel.guild, "channel_create")
        if not log_channel:
            return
        embed = self.cog.create_embed(
            "channel_create",
            f"📝 Channel created: {self._get_channel_str(channel)}",
            name=channel.name,
            id=channel.id,
            type=type(channel).__name__
        )
        await self._safe_send(log_channel, embed, channel.guild, "channel_create")
        try:
            await modlog.create_case(
                guild=channel.guild,
                case_type="channel_create",
                user=None,
                moderator=None,
                reason=None,
                until=None,
                extra={
                    "name": channel.name,
                    "id": channel.id,
                    "type": type(channel).__name__
                }
            )
        except Exception as e:
            self.cog.log.error(f"Failed to create modlog case for channel_create: {e}")

    @commands.Cog.listener()
    async def on_guild_channel_delete(self, channel: discord.abc.GuildChannel) -> None:
        """Log channel deletion events."""
        if not channel.guild or not await self.cog.should_log_event(channel.guild, "channel_delete", channel):
            return
        log_channel = await self.cog.get_log_channel(channel.guild, "channel_delete")
        if not log_channel:
            return
        embed = self.cog.create_embed(
            "channel_delete",
            f"🗑️ Channel deleted: {self._get_channel_str(channel)}",
            name=channel.name,
            id=channel.id,
            type=type(channel).__name__
        )
        await self._safe_send(log_channel, embed, channel.guild, "channel_delete")
        try:
            await modlog.create_case(
                guild=channel.guild,
                case_type="channel_delete",
                user=None,
                moderator=None,
                reason=None,
                until=None,
                extra={
                    "name": channel.name,
                    "id": channel.id,
                    "type": type(channel).__name__
                }
            )
        except Exception as e:
            self.cog.log.error(f"Failed to create modlog case for channel_delete: {e}")

    @commands.Cog.listener()
    async def on_guild_channel_update(self, before: discord.abc.GuildChannel, after: discord.abc.GuildChannel) -> None:
        """Log channel update events."""
        if not before.guild or not await self.cog.should_log_event(before.guild, "channel_update", after):
            return
        log_channel = await self.cog.get_log_channel(before.guild, "channel_update")
        if not log_channel:
            return
        changes = []
        # Only check attributes that exist for the specific channel type
        if hasattr(before, "name") and before.name != getattr(after, "name", None):
            changes.append(f"Name: {before.name} → {after.name}")
        if isinstance(before, discord.TextChannel) and isinstance(after, discord.TextChannel):
            if before.topic != after.topic:
                changes.append(f"Topic: {before.topic} → {after.topic}")
            if before.nsfw != after.nsfw:
                changes.append(f"NSFW: {before.nsfw} → {after.nsfw}")
            if before.slowmode_delay != after.slowmode_delay:
                changes.append(f"Slowmode: {before.slowmode_delay}s → {after.slowmode_delay}s")
        if isinstance(before, discord.VoiceChannel) and isinstance(after, discord.VoiceChannel):
            if before.bitrate != after.bitrate:
                changes.append(f"Bitrate: {before.bitrate} → {after.bitrate}")
            if before.user_limit != after.user_limit:
                changes.append(f"User limit: {before.user_limit} → {after.user_limit}")
        if not changes:
            return
        embed = self.cog.create_embed(
            "channel_update",
            f"🔄 Channel updated: {self._get_channel_str(after)}",
            changes="\n".join(changes)
        )
        await self._safe_send(log_channel, embed, before.guild, "channel_update")
        try:
            await modlog.create_case(
                guild=before.guild,
                case_type="channel_update",
                user=None,
                moderator=None,
                reason=None,
                until=None,
                extra={"changes": changes}
            )
        except Exception as e:
            self.cog.log.error(f"Failed to create modlog case for channel_update: {e}")

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member) -> None:
        """Log member join events."""
        if not member.guild or not await self.cog.should_log_event(member.guild, "member_join"):
            return
        log_channel = await self.cog.get_log_channel(member.guild, "member_join")
        if not log_channel:
            return
        embed = self.cog.create_embed(
            "member_join",
            f"👋 Member joined: {member.mention}",
            user=f"{member} ({member.id})"
        )
        await self._safe_send(log_channel, embed, member.guild, "member_join")
        try:
            await modlog.create_case(
                guild=member.guild,
                case_type="member_join",
                user=member,
                moderator=None,
                reason=None,
                until=None,
                extra=None
            )
        except Exception as e:
            self.cog.log.error(f"Failed to create modlog case for member_join: {e}")

    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member) -> None:
        """Log member leave events."""
        if not member.guild or not await self.cog.should_log_event(member.guild, "member_leave"):
            return
        log_channel = await self.cog.get_log_channel(member.guild, "member_leave")
        if not log_channel:
            return
        embed = self.cog.create_embed(
            "member_leave",
            f"👋 Member left: {member.mention}",
            user=f"{member} ({member.id})"
        )
        await self._safe_send(log_channel, embed, member.guild, "member_leave")
        try:
            await modlog.create_case(
                guild=member.guild,
                case_type="member_leave",
                user=member,
                moderator=None,
                reason=None,
                until=None,
                extra=None
            )
        except Exception as e:
            self.cog.log.error(f"Failed to create modlog case for member_leave: {e}")

    @commands.Cog.listener()
    async def on_member_update(self, before: discord.Member, after: discord.Member) -> None:
        """Log member update events."""
        if not before.guild or not await self.cog.should_log_event(before.guild, "member_update"):
            return
        log_channel = await self.cog.get_log_channel(before.guild, "member_update")
        if not log_channel:
            return
        changes = []
        if before.nick != after.nick:
            changes.append(f"Nickname: {before.nick} → {after.nick}")
        if before.roles != after.roles:
            before_roles = set(before.roles)
            after_roles = set(after.roles)
            added = after_roles - before_roles
            removed = before_roles - after_roles
            if added:
                changes.append(f"Roles added: {', '.join(r.name for r in added)}")
            if removed:
                changes.append(f"Roles removed: {', '.join(r.name for r in removed)}")
        if not changes:
            return
        embed = self.cog.create_embed(
            "member_update",
            f"👤 Member updated: {after.mention}",
            user=f"{after} ({after.id})",
            changes="\n".join(changes)
        )
        await self._safe_send(log_channel, embed, after.guild, "member_update")
        try:
            await modlog.create_case(
                guild=before.guild,
                case_type="member_update",
                user=after,
                moderator=None,
                reason=None,
                until=None,
                extra={"changes": changes}
            )
        except Exception as e:
            self.cog.log.error(f"Failed to create modlog case for member_update: {e}")

    @commands.Cog.listener()
    async def on_member_ban(self, guild: discord.Guild, user: discord.User) -> None:
        """Log member ban events."""
        if not await self.cog.should_log_event(guild, "member_ban"):
            return
        log_channel = await self.cog.get_log_channel(guild, "member_ban")
        if not log_channel:
            return
        embed = self.cog.create_embed(
            "member_ban",
            f"🔨 Member banned: {user.mention if hasattr(user, 'mention') else user}",
            user=f"{user} ({user.id})"
        )
        await self._safe_send(log_channel, embed, guild, "member_ban")
        try:
            await modlog.create_case(
                guild=guild,
                case_type="member_ban",
                user=user,
                moderator=None,
                reason=None,
                until=None,
                extra=None
            )
        except Exception as e:
            self.cog.log.error(f"Failed to create modlog case for member_ban: {e}")

    @commands.Cog.listener()
    async def on_member_unban(self, guild: discord.Guild, user: discord.User) -> None:
        """Log member unban events."""
        if not await self.cog.should_log_event(guild, "member_unban"):
            return
        log_channel = await self.cog.get_log_channel(guild, "member_unban")
        if not log_channel:
            return
        embed = self.cog.create_embed(
            "member_unban",
            f"🔓 Member unbanned: {user.mention if hasattr(user, 'mention') else user}",
            user=f"{user} ({user.id})"
        )
        await self._safe_send(log_channel, embed, guild, "member_unban")
        try:
            await modlog.create_case(
                guild=guild,
                case_type="member_unban",
                user=user,
                moderator=None,
                reason=None,
                until=None,
                extra=None
            )
        except Exception as e:
            self.cog.log.error(f"Failed to create modlog case for member_unban: {e}")

    @commands.Cog.listener()
    async def on_guild_role_create(self, role: discord.Role) -> None:
        """Log role creation events."""
        if not role.guild or not await self.cog.should_log_event(role.guild, "role_create"):
            return
        log_channel = await self.cog.get_log_channel(role.guild, "role_create")
        if not log_channel:
            return
        embed = self.cog.create_embed(
            "role_create",
            f"✨ Role created: {role.mention}",
            name=role.name,
            id=role.id
        )
        await self._safe_send(log_channel, embed, role.guild, "role_create")
        try:
            await modlog.create_case(
                guild=role.guild,
                case_type="role_create",
                user=None,
                moderator=None,
                reason=None,
                until=None,
                extra={"name": role.name, "id": role.id}
            )
        except Exception as e:
            self.cog.log.error(f"Failed to create modlog case for role_create: {e}")

    @commands.Cog.listener()
    async def on_guild_role_delete(self, role: discord.Role) -> None:
        """Log role deletion events."""
        if not role.guild or not await self.cog.should_log_event(role.guild, "role_delete"):
            return
        log_channel = await self.cog.get_log_channel(role.guild, "role_delete")
        if not log_channel:
            return
        embed = self.cog.create_embed(
            "role_delete",
            f"🗑️ Role deleted: {role.name}",
            name=role.name,
            id=role.id
        )
        await self._safe_send(log_channel, embed, role.guild, "role_delete")
        try:
            await modlog.create_case(
                guild=role.guild,
                case_type="role_delete",
                user=None,
                moderator=None,
                reason=None,
                until=None,
                extra={"name": role.name, "id": role.id}
            )
        except Exception as e:
            self.cog.log.error(f"Failed to create modlog case for role_delete: {e}")

    @commands.Cog.listener()
    async def on_guild_role_update(self, before: discord.Role, after: discord.Role) -> None:
        """Log role update events."""
        if not before.guild or not await self.cog.should_log_event(before.guild, "role_update"):
            return
        log_channel = await self.cog.get_log_channel(before.guild, "role_update")
        if not log_channel:
            return
        changes = []
        if before.name != after.name:
            changes.append(f"Name: {before.name} → {after.name}")
        if before.color != after.color:
            changes.append(f"Color: {before.color} → {after.color}")
        if before.permissions != after.permissions:
            changes.append("Permissions changed")
        if not changes:
            return
        embed = self.cog.create_embed(
            "role_update",
            f"🔄 Role updated: {after.mention}",
            changes="\n".join(changes)
        )
        await self._safe_send(log_channel, embed, before.guild, "role_update")
        try:
            await modlog.create_case(
                guild=before.guild,
                case_type="role_update",
                user=None,
                moderator=None,
                reason=None,
                until=None,
                extra={"changes": changes, "role": after.name}
            )
        except Exception as e:
            self.cog.log.error(f"Failed to create modlog case for role_update: {e}")

    @commands.Cog.listener()
    async def on_guild_emojis_update(self, guild: discord.Guild, before, after) -> None:
        """Log emoji update events."""
        if not await self.cog.should_log_event(guild, "emoji_update"):
            return
        log_channel = await self.cog.get_log_channel(guild, "emoji_update")
        if not log_channel:
            return
        before_set = set(before)
        after_set = set(after)
        added = after_set - before_set
        removed = before_set - after_set
        changes = []
        if added:
            changes.append(f"Added: {', '.join(str(e) for e in added)}")
        if removed:
            changes.append(f"Removed: {', '.join(str(e) for e in removed)}")
        if not changes:
            return
        embed = self.cog.create_embed(
            "emoji_update",
            f"😀 Emoji updated",
            changes="\n".join(changes)
        )
        await self._safe_send(log_channel, embed, guild, "emoji_update")
        try:
            await modlog.create_case(
                guild=guild,
                case_type="emoji_update",
                user=None,
                moderator=None,
                reason=None,
                until=None,
                extra={"changes": changes}
            )
        except Exception as e:
            self.cog.log.error(f"Failed to create modlog case for emoji_update: {e}")

    @commands.Cog.listener()
    async def on_guild_update(self, before: discord.Guild, after: discord.Guild) -> None:
        """Log guild/server update events."""
        if not await self.cog.should_log_event(before, "guild_update"):
            return
        log_channel = await self.cog.get_log_channel(before, "guild_update")
        if not log_channel:
            return
        changes = []
        if before.name != after.name:
            changes.append(f"Name: {before.name} → {after.name}")
        if before.icon != after.icon:
            changes.append("Icon changed")
        if before.owner_id != after.owner_id:
            changes.append(f"Owner: {before.owner_id} → {after.owner_id}")
        if not changes:
            return
        embed = self.cog.create_embed(
            "guild_update",
            f"⚙️ Server updated",
            changes="\n".join(changes)
        )
        await self._safe_send(log_channel, embed, before, "guild_update")
        try:
            await modlog.create_case(
                guild=before,
                case_type="guild_update",
                user=None,
                moderator=None,
                reason=None,
                until=None,
                extra={"changes": changes}
            )
        except Exception as e:
            self.cog.log.error(f"Failed to create modlog case for guild_update: {e}")

    @commands.Cog.listener()
    async def on_voice_state_update(self, member: discord.Member, before: discord.VoiceState, after: discord.VoiceState) -> None:
        """Log voice channel update events."""
        if not member.guild or not await self.cog.should_log_event(member.guild, "voice_update"):
            return
        log_channel = await self.cog.get_log_channel(member.guild, "voice_update")
        if not log_channel:
            return
        changes = []
        if before.channel != after.channel:
            changes.append(f"Channel: {getattr(before.channel, 'mention', None)} → {getattr(after.channel, 'mention', None)}")
        if before.mute != after.mute:
            changes.append(f"Muted: {before.mute} → {after.mute}")
        if before.deaf != after.deaf:
            changes.append(f"Deafened: {before.deaf} → {after.deaf}")
        if before.self_mute != after.self_mute:
            changes.append(f"Self-muted: {before.self_mute} → {after.self_mute}")
        if before.self_deaf != after.self_deaf:
            changes.append(f"Self-deafened: {before.self_deaf} → {after.self_deaf}")
        if not changes:
            return
        embed = self.cog.create_embed(
            "voice_update",
            f"🎤 Voice state updated for {member.mention}",
            changes="\n".join(changes)
        )
        await self._safe_send(log_channel, embed, member.guild, "voice_update")
        try:
            await modlog.create_case(
                guild=member.guild,
                case_type="voice_update",
                user=member,
                moderator=None,
                reason=None,
                until=None,
                extra={"changes": changes}
            )
        except Exception as e:
            self.cog.log.error(f"Failed to create modlog case for voice_update: {e}")

    @commands.Cog.listener()
    async def on_member_kick(self, guild: discord.Guild, user: discord.User) -> None:
        """Log member kick events (custom event, requires manual dispatch)."""
        if not await self.cog.should_log_event(guild, "member_kick"):
            return
        log_channel = await self.cog.get_log_channel(guild, "member_kick")
        if not log_channel:
            return
        embed = self.cog.create_embed(
            "member_kick",
            f"👢 Member kicked: {user.mention if hasattr(user, 'mention') else user}",
            user=f"{user} ({user.id})"
        )
        await self._safe_send(log_channel, embed, guild, "member_kick")
        try:
            await modlog.create_case(
                guild=guild,
                case_type="member_kick",
                user=user,
                moderator=None,
                reason=None,
                until=None,
                extra=None
            )
        except Exception as e:
            self.cog.log.error(f"Failed to create modlog case for member_kick: {e}")

    @commands.Cog.listener()
    async def on_command(self, ctx: commands.Context) -> None:
        """Log classic command usage."""
        if not ctx.guild or not await self.cog.should_log_event(ctx.guild, "command_use"):
            return
        settings = await self.cog.config.guild(ctx.guild).all()
        if ctx.command and ctx.command.qualified_name in settings.get("ignored_commands", []):
            return
        log_channel = await self.cog.get_log_channel(ctx.guild, "command_use")
        if not log_channel:
            return
        embed = self.cog.create_embed(
            "command_use",
            f"⌨️ Command used in {self._get_channel_str(ctx.channel)}",
            user=f"{ctx.author} ({ctx.author.id})",
            command=f"{ctx.command.qualified_name if ctx.command else 'Unknown'} {ctx.view.value}"
        )
        await self._safe_send(log_channel, embed, ctx.guild, "command_use")
        try:
            await modlog.create_case(
                guild=ctx.guild,
                case_type="command_use",
                user=ctx.author,
                moderator=None,
                reason=None,
                until=None,
                extra={"command": ctx.command.qualified_name if ctx.command else 'Unknown'}
            )
        except Exception as e:
            self.cog.log.error(f"Failed to create modlog case for command_use: {e}")

    @commands.Cog.listener()
    async def on_command_error(self, ctx: commands.Context, error: Exception) -> None:
        """Log classic command errors."""
        if not ctx.guild or not await self.cog.should_log_event(ctx.guild, "command_error"):
            return
        settings = await self.cog.config.guild(ctx.guild).all()
        if ctx.command and ctx.command.qualified_name in settings.get("ignored_commands", []):
            return
        log_channel = await self.cog.get_log_channel(ctx.guild, "command_error")
        if not log_channel:
            return
        embed = self.cog.create_embed(
            "command_error",
            f"⚠️ Command error in {self._get_channel_str(ctx.channel)}",
            user=f"{ctx.author} ({ctx.author.id})",
            command=f"{ctx.command.qualified_name if ctx.command else 'Unknown'} {ctx.view.value}",
            error=str(error),
            error_type=error.__class__.__name__
        )
        await self._safe_send(log_channel, embed, ctx.guild, "command_error")
        try:
            await modlog.create_case(
                guild=ctx.guild,
                case_type="command_error",
                user=ctx.author,
                moderator=None,
                reason=str(error),
                until=None,
                extra={
                    "command": ctx.command.qualified_name if ctx.command else 'Unknown',
                    "error_type": error.__class__.__name__
                }
            )
        except Exception as e:
            self.cog.log.error(f"Failed to create modlog case for command_error: {e}")

    @commands.Cog.listener()
    async def on_cog_add(self, cog: commands.Cog) -> None:
        """Log cog load events."""
        for guild in self.bot.guilds:
            if not await self.cog.should_log_event(guild, "cog_load"):
                continue
            log_channel = await self.cog.get_log_channel(guild, "cog_load")
            if not log_channel:
                continue
            embed = self.cog.create_embed(
                "cog_load",
                f"📦 Cog loaded: {getattr(cog, 'qualified_name', str(cog))}"
            )
            await self._safe_send(log_channel, embed, guild, "cog_load")
            try:
                for guild in self.bot.guilds:
                    await modlog.create_case(
                        guild=guild,
                        case_type="cog_load",
                        user=None,
                        moderator=None,
                        reason=None,
                        until=None,
                        extra={"cog": getattr(cog, 'qualified_name', str(cog))}
                    )
            except Exception as e:
                self.cog.log.error(f"Failed to create modlog case for cog_load: {e}")

    @commands.Cog.listener()
    async def on_cog_remove(self, cog: commands.Cog) -> None:
        """Log cog unload events."""
        for guild in self.bot.guilds:
            if not await self.cog.should_log_event(guild, "cog_load"):
                continue
            log_channel = await self.cog.get_log_channel(guild, "cog_load")
            if not log_channel:
                continue
            embed = self.cog.create_embed(
                "cog_load",
                f"📦 Cog unloaded: {getattr(cog, 'qualified_name', str(cog))}"
            )
            await self._safe_send(log_channel, embed, guild, "cog_load")
            try:
                for guild in self.bot.guilds:
                    await modlog.create_case(
                        guild=guild,
                        case_type="cog_load",
                        user=None,
                        moderator=None,
                        reason=None,
                        until=None,
                        extra={"cog": getattr(cog, 'qualified_name', str(cog)), "unloaded": True}
                    )
            except Exception as e:
                self.cog.log.error(f"Failed to create modlog case for cog_unload: {e}")
