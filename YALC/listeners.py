"""YALC listeners module - Contains all event listeners for logging."""
import discord
from discord import app_commands
from redbot.core import commands
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
        
    @commands.Cog.listener()
    async def on_message_delete(self, message: discord.Message) -> None:
        """Handle message deletion events."""
        if not message.guild or not await self.cog.should_log_event(message.guild, "message_delete"):
            return

        channel = await self.cog.get_log_channel(message.guild, "message_delete")
        if not channel:
            return

        embed = self.cog.create_embed(
            "message_delete",
            f"🗑️ Message deleted in {self._get_channel_str(message.channel)}",
            user=f"{message.author} ({message.author.id})",
            content=message.content,
            attachments=[a.url for a in message.attachments],
            embeds=message.embeds
        )

        await self.cog.safe_send(channel, embed=embed)

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

        await self.cog.safe_send(channel, embed=embed)

    def _get_channel_str(self, channel: Optional[Union[discord.abc.GuildChannel, discord.abc.PrivateChannel, discord.Thread, discord.ForumChannel]]) -> str:
        """Get a string representation of a channel.
        
        Parameters
        ----------
        channel: Optional[Union[discord.abc.GuildChannel, discord.abc.PrivateChannel, discord.Thread, discord.ForumChannel]]
            The channel to get a string for
            
        Returns
        -------
        str
            A string representation of the channel
        """
        if channel is None:
            return "Unknown Channel"
            
        # Handle guild channels with mentions
        if isinstance(channel, (discord.TextChannel, discord.VoiceChannel, discord.Thread)):
            return channel.mention
            
        # Handle forum channels
        if isinstance(channel, discord.ForumChannel):
            return f"#{channel.name}"
            
        # Handle private channels and others
        if isinstance(channel, discord.abc.PrivateChannel):
            return "DM Channel"
            
        # Fallback for any other types
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

        await self.cog.safe_send(channel, embed=embed)

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

        await self.cog.safe_send(channel, embed=embed)

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

        await self.cog.safe_send(channel, embed=embed)

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

        await self.cog.safe_send(channel, embed=embed)

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

        await self.cog.safe_send(channel, embed=embed)

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

        await self.cog.safe_send(channel, embed=embed)

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

        await self.cog.safe_send(channel, embed=embed)
