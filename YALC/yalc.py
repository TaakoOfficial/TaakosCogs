from redbot.core import commands, Config, app_commands
import discord
from typing import Optional, Any
from .classic_commands import YALCClassicCommands
from .slash_commands import YALCSlashGroup
from .utils import (
    mention_from_id,
    validate_retention_days,
    set_embed_footer,
    log_exception,
    check_manage_guild,
    safe_send
)

class EventLogGroup(app_commands.Group):
    """Slash command group for event log channel configuration."""
    def __init__(self, cog: commands.Cog):
        super().__init__(name="eventlog", description="Event log channel configuration.")
        self.cog = cog

    @app_commands.command(name="set", description="Set a log channel for a specific event type.")
    async def set_eventlog(self, interaction: discord.Interaction, event: str, channel: discord.TextChannel) -> None:
        """Slash command to set a log channel for an event type."""
        if not interaction.guild or not interaction.user:
            await safe_send(interaction, "❌ This command can only be used in a server.")
            return
        member = interaction.user if isinstance(interaction.user, discord.Member) else None
        if not member or not check_manage_guild(member):
            await safe_send(interaction, "❌ You need Manage Server permission!")
            return
        try:
            valid_events = list((await self.cog.config.guild(interaction.guild).log_events()).keys())
            if event not in valid_events:
                await safe_send(interaction, f"❌ Invalid event type. Valid events: {', '.join(valid_events)}")
                return
            await self.cog.config.guild(interaction.guild).event_channels.set_raw(event, value=channel.id)
            await safe_send(interaction, f"✅ Log channel for `{event}` set to {channel.mention}!")
        except Exception as e:
            log_exception(self.cog, e, context="set_eventlog")
            await safe_send(interaction, "❌ An error occurred while setting the log channel.")

    @app_commands.command(name="clear", description="Clear the log channel for an event type (use default).")
    async def clear_eventlog(self, interaction: discord.Interaction, event: str) -> None:
        """Slash command to clear a specific event log channel (revert to default)."""
        if not interaction.guild or not interaction.user:
            await safe_send(interaction, "❌ This command can only be used in a server.")
            return
        member = interaction.user if isinstance(interaction.user, discord.Member) else None
        if not member or not check_manage_guild(member):
            await safe_send(interaction, "❌ You need Manage Server permission!")
            return
        try:
            valid_events = list((await self.cog.config.guild(interaction.guild).log_events()).keys())
            if event not in valid_events:
                await safe_send(interaction, f"❌ Invalid event type. Valid events: {', '.join(valid_events)}")
                return
            await self.cog.config.guild(interaction.guild).event_channels.clear_raw(event)
            await safe_send(interaction, f"✅ Log channel for `{event}` cleared (will use default log channel).")
        except Exception as e:
            log_exception(self.cog, e, context="clear_eventlog")
            await safe_send(interaction, "❌ An error occurred while clearing the log channel.")

class YALC(commands.Cog):
    """📝 Yet Another Logging Cog (YALC)! Logs all the spicy server events with style and fun! 🎉"""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.config = Config.get_conf(self, identifier=2025041601)
        default_guild = {
            "log_channel": None,
            "log_events": {
                "message_delete": False,
                "message_edit": False,
                "member_join": False,
                "member_remove": False,
                "member_ban": False,
                "member_unban": False,
                "channel_create": False,
                "channel_delete": False,
                "channel_update": False,
                "role_create": False,
                "role_delete": False,
                "role_update": False,
                "emoji_create": False,
                "emoji_delete": False,
                "emoji_update": False,
                "voice_state": False,
                "invite_create": False,
                "invite_delete": False,
                "webhook_update": False,
                "thread_create": False,
                "thread_delete": False,
                "thread_update": False,
                "nickname_change": False,
                "command_log": False,
                "guild_update": False,
                "timeout": False,
                "username_change": False
            },
            "event_channels": {},
            "ignored_users": [],
            "ignored_roles": [],
            "ignored_channels": [],
            "retention_days": 30  # Default log retention period in days
        }
        self.config.register_guild(**default_guild)
        self.eventlog_group = EventLogGroup(self)
        self.classic_commands = YALCClassicCommands(self)
        self.slash_group = YALCSlashGroup(self)
        # Register classic commands with the bot
        bot.add_command(self.classic_commands.yalc)
        bot.add_command(self.classic_commands.yalctemplate)
        bot.add_command(self.classic_commands.yalcretention)
        bot.add_command(self.classic_commands.yalcignore)
        bot.add_command(self.classic_commands.yalcfilter)
        # Register slash command group
        bot.tree.add_command(self.slash_group)

    async def cog_unload(self) -> None:
        """
        Cleanup tasks when the cog is unloaded.
        """
        self.bot.tree.remove_command(self.eventlog_group.name)
        self.bot.tree.remove_command(self.slash_group.name)
        # Optionally cancel any scheduled tasks here
        # Unregister classic commands
        self.bot.remove_command("yalc")
        self.bot.remove_command("yalctemplate")
        self.bot.remove_command("yalcretention")
        self.bot.remove_command("yalcignore")
        self.bot.remove_command("yalcfilter")

    # --- Log Retention/Pruning ---
    @commands.group(name="yalcretention")
    async def yalcretention(self, ctx: commands.Context) -> None:
        """Configure log retention for YALC."""
        if ctx.invoked_subcommand is None:
            await ctx.send_help(ctx.command)

    @yalcretention.command(name="set")
    async def set_retention(self, ctx: commands.Context, days: int) -> None:
        """Set the log retention period in days (minimum 1, maximum 365)."""
        if not validate_retention_days(days):
            await ctx.send("❌ Please provide a value between 1 and 365 days.")
            return
        await self.config.guild(ctx.guild).set_raw("retention_days", value=days)
        await ctx.send(f"✅ Log retention set to {days} days.")

    @yalcretention.command(name="show")
    async def show_retention(self, ctx: commands.Context) -> None:
        """Show the current log retention period."""
        days = await self.config.guild(ctx.guild).get_raw("retention_days", default=30)
        await ctx.send(f"Current log retention: {days} days.")

    async def prune_old_logs(self) -> None:
        """Prune old log messages based on retention settings for all guilds."""
        import datetime, asyncio
        for guild in self.bot.guilds:
            try:
                days = await self.config.guild(guild).get_raw("retention_days", default=30)
                cutoff = discord.utils.utcnow() - datetime.timedelta(days=days)
                log_channel_id = await self.config.guild(guild).log_channel()
                if not log_channel_id:
                    continue
                channel = guild.get_channel(log_channel_id)
                if not isinstance(channel, discord.TextChannel):
                    continue
                async for msg in channel.history(limit=1000, before=cutoff):
                    if msg.author == self.bot.user:
                        try:
                            await msg.delete()
                            await asyncio.sleep(1)
                        except Exception as e:
                            log_exception(self, e, context="prune_old_logs:delete")
                            continue
            except Exception as e:
                log_exception(self, e, context="prune_old_logs:outer")
                continue

    # Schedule pruning on cog load
    async def initialize_pruning(self) -> None:
        """Start the background task for log pruning."""
        import asyncio
        async def task():
            while True:
                await self.prune_old_logs()
                await asyncio.sleep(24 * 60 * 60)  # Run daily
        self._prune_task = self.bot.loop.create_task(task())

    # Call this in __init__
    # await self.initialize_pruning()

    # --- Utility for safe mention ---
    def _safe_mention(self, obj: Any) -> str:
        if hasattr(obj, "mention"):
            return obj.mention
        return str(obj) if obj else "unknown channel"

    # --- Example usage in listeners ---
    @commands.Cog.listener()
    async def on_voice_state_update(self, member: discord.Member, before: discord.VoiceState, after: discord.VoiceState) -> None:
        """Log voice state changes (join/leave/mute)."""
        if not member.guild:
            return
        settings = await self.config.guild(member.guild).all()
        if not settings["log_events"].get("voice_state", False):
            return
        log_channel = await self._get_event_channel(member.guild, "voice_state")
        if not log_channel:
            return
        if before.channel != after.channel:
            if before.channel is None and after.channel:
                desc = f"{member.mention} joined voice channel {self._safe_mention(after.channel)}"
            elif before.channel and after.channel is None:
                desc = f"{member.mention} left voice channel {self._safe_mention(before.channel)}"
            elif before.channel and after.channel:
                desc = f"{member.mention} moved from {self._safe_mention(before.channel)} to {self._safe_mention(after.channel)}"
            else:
                return
            embed = discord.Embed(title="🔊 Voice State Update", description=desc, color=discord.Color.blue())
            embed.timestamp = discord.utils.utcnow()
            set_embed_footer(embed, self)
            await log_channel.send(embed=embed)
        elif before.mute != after.mute:
            state = "muted" if after.mute else "unmuted"
            desc = f"{member.mention} was {state} in voice."
            embed = discord.Embed(title="🔇 Voice Mute Update", description=desc, color=discord.Color.purple())
            embed.timestamp = discord.utils.utcnow()
            set_embed_footer(embed, self)
            await log_channel.send(embed=embed)

    @commands.Cog.listener()
    async def on_invite_create(self, invite: discord.Invite) -> None:
        """Log invite creation."""
        guild = invite.guild if isinstance(invite.guild, discord.Guild) else None
        if not guild:
            return
        settings = await self.config.guild(guild).all()
        if not settings["log_events"].get("invite_create", False):
            return
        log_channel = await self._get_event_channel(guild, "invite_create")
        if not log_channel:
            return
        channel = invite.channel if hasattr(invite, "channel") and invite.channel else None
        desc = f"Invite `{invite.code}` created for {self._safe_mention(channel)}"
        embed = discord.Embed(title="🔗 Invite Created", description=desc, color=discord.Color.green())
        embed.timestamp = discord.utils.utcnow()
        set_embed_footer(embed, self)
        await log_channel.send(embed=embed)

    @commands.Cog.listener()
    async def on_invite_delete(self, invite: discord.Invite) -> None:
        """Log invite deletion."""
        guild = invite.guild if isinstance(invite.guild, discord.Guild) else None
        if not guild:
            return
        settings = await self.config.guild(guild).all()
        if not settings["log_events"].get("invite_delete", False):
            return
        log_channel = await self._get_event_channel(guild, "invite_delete")
        if not log_channel:
            return
        channel = invite.channel if hasattr(invite, "channel") and invite.channel else None
        desc = f"Invite `{invite.code}` deleted for {self._safe_mention(channel)}"
        embed = discord.Embed(title="❌ Invite Deleted", description=desc, color=discord.Color.red())
        embed.timestamp = discord.utils.utcnow()
        set_embed_footer(embed, self)
        await log_channel.send(embed=embed)

    @commands.Cog.listener()
    async def on_webhook_update(self, webhook: discord.Webhook) -> None:
        """Log webhook executions and changes."""
        guild = webhook.guild if hasattr(webhook, "guild") else None
        if not guild:
            return
        settings = await self.config.guild(guild).all()
        if not settings["log_events"].get("webhook_update", False):
            return
        log_channel = await self._get_event_channel(guild, "webhook_update")
        if not log_channel:
            return
        desc = f"Webhook `{webhook.name}` (ID: {webhook.id}) was updated in {self._safe_mention(webhook.channel) if hasattr(webhook, 'channel') and webhook.channel else 'unknown channel'} by <@{webhook.user.id}>." if hasattr(webhook, 'user') and webhook.user else f"Webhook `{webhook.name}` (ID: {webhook.id}) was updated."
        embed = discord.Embed(title="🪝 Webhook Updated", description=desc, color=discord.Color.teal())
        embed.timestamp = discord.utils.utcnow()
        set_embed_footer(embed, self)
        await log_channel.send(embed=embed)

    @commands.Cog.listener()
    async def on_webhook_send(self, message: discord.Message) -> None:
        """Log webhook message sends (if supported by your Redbot/discord.py version)."""
        if not message.guild or not message.webhook_id:
            return
        settings = await self.config.guild(message.guild).all()
        if not settings["log_events"].get("webhook_update", False):
            return
        log_channel = await self._get_event_channel(message.guild, "webhook_update")
        if not log_channel:
            return
        desc = f"Webhook message sent in {self._safe_mention(message.channel)} by webhook ID `{message.webhook_id}`."
        embed = discord.Embed(title="🪝 Webhook Message Sent", description=desc, color=discord.Color.teal())
        embed.timestamp = discord.utils.utcnow()
        set_embed_footer(embed, self)
        await log_channel.send(embed=embed)

    @commands.Cog.listener()
    async def on_thread_create(self, thread: discord.Thread) -> None:
        """Log thread creation."""
        if not thread.guild:
            return
        settings = await self.config.guild(thread.guild).all()
        if not settings["log_events"].get("thread_create", False):
            return
        log_channel = await self._get_event_channel(thread.guild, "thread_create")
        if not log_channel:
            return
        parent = thread.parent if hasattr(thread, "parent") and thread.parent else None
        desc = f"Thread `{thread.name}` created in {self._safe_mention(parent)}"
        embed = discord.Embed(title="🧵 Thread Created", description=desc, color=discord.Color.green())
        embed.timestamp = discord.utils.utcnow()
        set_embed_footer(embed, self)
        await log_channel.send(embed=embed)

    @commands.Cog.listener()
    async def on_thread_delete(self, thread: discord.Thread) -> None:
        """Log thread deletion."""
        if not thread.guild:
            return
        settings = await self.config.guild(thread.guild).all()
        if not settings["log_events"].get("thread_delete", False):
            return
        log_channel = await self._get_event_channel(thread.guild, "thread_delete")
        if not log_channel:
            return
        parent = thread.parent if hasattr(thread, "parent") and thread.parent else None
        desc = f"Thread `{thread.name}` deleted from {self._safe_mention(parent)}"
        embed = discord.Embed(title="🧵 Thread Deleted", description=desc, color=discord.Color.red())
        embed.timestamp = discord.utils.utcnow()
        set_embed_footer(embed, self)
        await log_channel.send(embed=embed)

    @commands.Cog.listener()
    async def on_user_update(self, before: discord.User, after: discord.User) -> None:
        """Log username changes."""
        # Only log for members in guilds
        for guild in self.bot.guilds:
            member = guild.get_member(after.id)
            if not member:
                continue
            settings = await self.config.guild(guild).all()
            if not settings["log_events"].get("nickname_change", False):
                continue
            log_channel = await self._get_event_channel(guild, "nickname_change")
            if not log_channel:
                continue
            if before.name != after.name:
                desc = f"User `{before.name}` changed username to `{after.name}`"
                embed = discord.Embed(title="📝 Username Changed", description=desc, color=discord.Color.blurple())
                embed.timestamp = discord.utils.utcnow()
                set_embed_footer(embed, self)
                await log_channel.send(embed=embed)
        # Nickname changes are handled in on_member_update

    @commands.Cog.listener()
    async def on_member_update(self, before: discord.Member, after: discord.Member) -> None:
        """Log nickname and role changes."""
        if not before.guild:
            return
        settings = await self.config.guild(before.guild).all()
        # Nickname change
        if settings["log_events"].get("nickname_change", False):
            log_channel = await self._get_event_channel(before.guild, "nickname_change")
            if log_channel and before.nick != after.nick:
                desc = f"{after.mention} changed nickname: `{before.nick or before.name}` ➔ `{after.nick or after.name}`"
                embed = discord.Embed(
                    title="📝 Nickname Changed",
                    description=desc,
                    color=discord.Color.blurple()
                )
                embed.set_author(name=str(after), icon_url=self._get_avatar_url(after))
                embed.timestamp = discord.utils.utcnow()
                set_embed_footer(embed, self)
                await log_channel.send(embed=embed)
        # Role change
        if settings["log_events"].get("role_update", False):
            log_channel = await self._get_event_channel(before.guild, "role_update")
            if log_channel and set(before.roles) != set(after.roles):
                before_roles = ', '.join([r.mention for r in before.roles if r.name != '@everyone']) or 'None'
                after_roles = ', '.join([r.mention for r in after.roles if r.name != '@everyone']) or 'None'
                embed = discord.Embed(
                    title="🎭 Roles Updated",
                    description=f"{after.mention} roles changed.",
                    color=discord.Color.gold()
                )
                embed.add_field(name="Before", value=before_roles, inline=False)
                embed.add_field(name="After", value=after_roles, inline=False)
                embed.set_author(name=str(after), icon_url=self._get_avatar_url(after))
                embed.timestamp = discord.utils.utcnow()
                set_embed_footer(embed, self)
                await log_channel.send(embed=embed)

    @commands.Cog.listener()
    async def on_guild_update(self, before: discord.Guild, after: discord.Guild) -> None:
        """Log server setting changes (name, icon, etc)."""
        settings = await self.config.guild(after).all()
        if not settings["log_events"].get("guild_update", False):
            return
        log_channel = await self._get_event_channel(after, "guild_update")
        if not log_channel:
            return
        changes = []
        if before.name != after.name:
            changes.append(f"**Name:** `{before.name}` ➔ `{after.name}`")
        if before.icon != after.icon:
            changes.append("**Icon changed**")
        if not changes:
            return
        embed = discord.Embed(
            title="🏛️ Server Updated",
            description='\n'.join(changes),
            color=discord.Color.teal()
        )
        embed.timestamp = discord.utils.utcnow()
        set_embed_footer(embed, self)
        await log_channel.send(embed=embed)

    @commands.Cog.listener()
    async def on_member_timeout(self, member: discord.Member) -> None:
        """Log when a member is timed out (if supported by your Redbot/discord.py version)."""
        if not member.guild:
            return
        settings = await self.config.guild(member.guild).all()
        if not settings["log_events"].get("timeout", False):
            return
        log_channel = await self._get_event_channel(member.guild, "timeout")
        if not log_channel:
            return
        embed = discord.Embed(
            title="⏳ Member Timed Out",
            description=f"{member.mention} was timed out.",
            color=discord.Color.dark_purple()
        )
        embed.set_author(name=str(member), icon_url=self._get_avatar_url(member))
        embed.timestamp = discord.utils.utcnow()
        set_embed_footer(embed, self)
        await log_channel.send(embed=embed)

    @commands.Cog.listener()
    async def on_bulk_message_delete(self, messages: list[discord.Message]) -> None:
        """Log bulk message deletions (purges)."""
        if not messages:
            return
        guild = messages[0].guild if messages[0].guild else None
        if not guild:
            return
        settings = await self.config.guild(guild).all()
        if not settings["log_events"].get("message_delete", False):
            return
        log_channel = await self._get_event_channel(guild, "message_delete")
        if not log_channel:
            return
        channel = messages[0].channel
        count = len(messages)
        # Try to correlate with audit log (purge)
        entry = await self.get_audit_log_entry(guild, discord.AuditLogAction.message_bulk_delete, channel.id)
        moderator = entry.user.mention if entry and entry.user else "Unknown"
        reason = entry.reason if entry and entry.reason else "No reason provided."
        embed = discord.Embed(
            title="🧹 Bulk Message Delete",
            description=f"{count} messages were deleted in {self._safe_mention(channel)}",
            color=discord.Color.red()
        )
        embed.add_field(name="Moderator", value=moderator)
        embed.add_field(name="Reason", value=reason)
        embed.timestamp = discord.utils.utcnow()
        set_embed_footer(embed, self)
        await log_channel.send(embed=embed)

    # --- Ignore Lists ---
    @commands.group(name="yalcignore")
    async def yalcignore(self, ctx: commands.Context) -> None:
        """Manage ignore lists for YALC logging."""
        if ctx.invoked_subcommand is None:
            await ctx.send_help(ctx.command)

    @yalcignore.command(name="adduser")
    async def ignore_user(self, ctx: commands.Context, user: discord.User) -> None:
        """Ignore a user from being logged."""
        ignored = await self.config.guild(ctx.guild).get_raw("ignored_users", default=[])
        if user.id in ignored:
            await ctx.send(f"{user.mention} is already ignored.")
            return
        ignored.append(user.id)
        await self.config.guild(ctx.guild).set_raw("ignored_users", value=ignored)
        await ctx.send(f"{user.mention} will now be ignored in logs.")

    @yalcignore.command(name="removeuser")
    async def unignore_user(self, ctx: commands.Context, user: discord.User) -> None:
        """Remove a user from the ignore list."""
        ignored = await self.config.guild(ctx.guild).get_raw("ignored_users", default=[])
        if user.id not in ignored:
            await ctx.send(f"{user.mention} is not ignored.")
            return
        ignored.remove(user.id)
        await self.config.guild(ctx.guild).set_raw("ignored_users", value=ignored)
        await ctx.send(f"{user.mention} will no longer be ignored in logs.")

    @yalcignore.command(name="addrole")
    async def ignore_role(self, ctx: commands.Context, role: discord.Role) -> None:
        """Ignore a role from being logged."""
        ignored = await self.config.guild(ctx.guild).get_raw("ignored_roles", default=[])
        if role.id in ignored:
            await ctx.send(f"{role.mention} is already ignored.")
            return
        ignored.append(role.id)
        await self.config.guild(ctx.guild).set_raw("ignored_roles", value=ignored)
        await ctx.send(f"{role.mention} will now be ignored in logs.")

    @yalcignore.command(name="removerole")
    async def unignore_role(self, ctx: commands.Context, role: discord.Role) -> None:
        """Remove a role from the ignore list."""
        ignored = await self.config.guild(ctx.guild).get_raw("ignored_roles", default=[])
        if role.id not in ignored:
            await ctx.send(f"{role.mention} is not ignored.")
            return
        ignored.remove(role.id)
        await self.config.guild(ctx.guild).set_raw("ignored_roles", value=ignored)
        await ctx.send(f"{role.mention} will no longer be ignored in logs.")

    @yalcignore.command(name="addchannel")
    async def ignore_channel(self, ctx: commands.Context, channel: discord.TextChannel) -> None:
        """Ignore a channel from being logged."""
        ignored = await self.config.guild(ctx.guild).get_raw("ignored_channels", default=[])
        if channel.id in ignored:
            await ctx.send(f"{channel.mention} is already ignored.")
            return
        ignored.append(channel.id)
        await self.config.guild(ctx.guild).set_raw("ignored_channels", value=ignored)
        await ctx.send(f"{channel.mention} will now be ignored in logs.")

    @yalcignore.command(name="removechannel")
    async def unignore_channel(self, ctx: commands.Context, channel: discord.TextChannel) -> None:
        """Remove a channel from the ignore list."""
        ignored = await self.config.guild(ctx.guild).get_raw("ignored_channels", default=[])
        if channel.id not in ignored:
            await ctx.send(f"{channel.mention} is not ignored.")
            return
        ignored.remove(channel.id)
        await self.config.guild(ctx.guild).set_raw("ignored_channels", value=ignored)
        await ctx.send(f"{channel.mention} will no longer be ignored in logs.")

    @yalcignore.command(name="list")
    async def list_ignores(self, ctx: commands.Context) -> None:
        """List all ignored users, roles, and channels."""
        users = await self.config.guild(ctx.guild).get_raw("ignored_users", default=[])
        roles = await self.config.guild(ctx.guild).get_raw("ignored_roles", default=[])
        channels = await self.config.guild(ctx.guild).get_raw("ignored_channels", default=[])
        user_mentions = [f"<@{uid}>" for uid in users]
        role_mentions = [f"<@&{rid}>" for rid in roles]
        channel_mentions = [f"<#{cid}>" for cid in channels]
        embed = discord.Embed(
            title="YALC Ignore Lists",
            color=discord.Color.blurple()
        )
        embed.add_field(name="Users", value=", ".join(user_mentions) or "None", inline=False)
        embed.add_field(name="Roles", value=", ".join(role_mentions) or "None", inline=False)
        embed.add_field(name="Channels", value=", ".join(channel_mentions) or "None", inline=False)
        await ctx.send(embed=embed)

    def is_ignored(self, guild: discord.Guild, user: Optional[discord.abc.User] = None, channel: Optional[discord.abc.GuildChannel] = None) -> Any:
        """Check if a user or channel should be ignored for logging."""
        async def check() -> bool:
            if not guild:
                return False
            users = await self.config.guild(guild).get_raw("ignored_users", default=[])
            roles = await self.config.guild(guild).get_raw("ignored_roles", default=[])
            channels = await self.config.guild(guild).get_raw("ignored_channels", default=[])
            if user and user.id in users:
                return True
            if hasattr(user, "roles"):
                if any(r.id in roles for r in getattr(user, "roles", [])):
                    return True
            if channel and channel.id in channels:
                return True
            return False
        return check

    # --- Advanced Filtering ---
    @commands.group(name="yalcfilter")
    async def yalcfilter(self, ctx: commands.Context) -> None:
        """Manage advanced filters for YALC logging."""
        if ctx.invoked_subcommand is None:
            await ctx.send_help(ctx.command)

    @yalcfilter.command(name="add")
    async def add_filter(self, ctx: commands.Context, event: str, *, filter_str: str) -> None:
        """Add a filter for an event (e.g. only log if user/role/channel/keyword matches)."""
        valid_events = list((await self.config.guild(ctx.guild).log_events()).keys())
        if event not in valid_events:
            await ctx.send(f"❌ Invalid event type. Valid events: {', '.join(valid_events)}")
            return
        filters = await self.config.guild(ctx.guild).get_raw(f"filters_{event}", default=[])
        if filter_str in filters:
            await ctx.send("This filter already exists for this event.")
            return
        filters.append(filter_str)
        await self.config.guild(ctx.guild).set_raw(f"filters_{event}", value=filters)
        await ctx.send(f"✅ Filter added for `{event}`.")

    @yalcfilter.command(name="remove")
    async def remove_filter(self, ctx: commands.Context, event: str, *, filter_str: str) -> None:
        """Remove a filter from an event."""
        valid_events = list((await self.config.guild(ctx.guild).log_events()).keys())
        if event not in valid_events:
            await ctx.send(f"❌ Invalid event type. Valid events: {', '.join(valid_events)}")
            return
        filters = await self.config.guild(ctx.guild).get_raw(f"filters_{event}", default=[])
        if filter_str not in filters:
            await ctx.send("This filter does not exist for this event.")
            return
        filters.remove(filter_str)
        await self.config.guild(ctx.guild).set_raw(f"filters_{event}", value=filters)
        await ctx.send(f"✅ Filter removed for `{event}`.")

    @yalcfilter.command(name="list")
    async def list_filters(self, ctx: commands.Context, event: str) -> None:
        """List all filters for an event."""
        valid_events = list((await self.config.guild(ctx.guild).log_events()).keys())
        if event not in valid_events:
            await ctx.send(f"❌ Invalid event type. Valid events: {', '.join(valid_events)}")
            return
        filters = await self.config.guild(ctx.guild).get_raw(f"filters_{event}", default=[])
        embed = discord.Embed(
            title=f"Filters for {event}",
            description="\n".join(filters) or "No filters set.",
            color=discord.Color.blurple()
        )
        await ctx.send(embed=embed)

    async def passes_filters(self, guild: discord.Guild, event: str, user: Optional[discord.abc.User] = None, channel: Optional[discord.abc.GuildChannel] = None, content: Optional[str] = None) -> bool:
        """Check if an event passes advanced filters (user/role/channel/keyword)."""
        filters = await self.config.guild(guild).get_raw(f"filters_{event}", default=[])
        if not filters:
            return True
        for f in filters:
            if f.startswith("user:") and user and str(user.id) == f[5:]:
                return True
            if f.startswith("role:") and user and hasattr(user, "roles") and any(str(r.id) == f[5:] for r in getattr(user, "roles", [])):
                return True
            if f.startswith("channel:") and channel and str(channel.id) == f[8:]:
                return True
            if f.startswith("keyword:") and content and f[8:].lower() in content.lower():
                return True
        return False

async def setup(bot: commands.Bot):
    cog = YALC(bot)
    await bot.add_cog(cog)
    bot.tree.add_command(cog.eventlog_group)
