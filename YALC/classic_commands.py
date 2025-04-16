"""
YALC Classic Commands for Redbot.
"""
from redbot.core import commands
import discord
from typing import Optional

class YALCClassicCommands:
    """Classic command group for YALC logging configuration."""
    def __init__(self, cog: commands.Cog):
        self.cog = cog

    @commands.group(name="yalc")
    async def yalc(self, ctx: commands.Context) -> None:
        """YALC logging configuration commands."""
        if ctx.invoked_subcommand is None:
            await ctx.send_help(ctx.command)

    @yalc.command(name="info")
    async def yalc_info(self, ctx: commands.Context) -> None:
        """Show enabled events and their log channels."""
        settings = await self.cog.config.guild(ctx.guild).all()
        log_events = settings["log_events"]
        event_channels = settings["event_channels"]
        log_channel_id = settings["log_channel"]
        log_channel = ctx.guild.get_channel(log_channel_id) if log_channel_id else None
        lines = []
        for event, enabled in log_events.items():
            channel_id = event_channels.get(event, log_channel_id)
            channel = ctx.guild.get_channel(channel_id) if channel_id else None
            emoji = "✅" if enabled else "❌"
            channel_str = channel.mention if channel else "*Not set*"
            lines.append(f"{emoji} `{event}` → {channel_str}")
        embed = discord.Embed(
            title="📝 YALC Logging Status",
            description="\n".join(lines) or "No events configured.",
            color=discord.Color.blurple()
        )
        self.cog._set_embed_footer(embed)
        await ctx.send(embed=embed)

    @yalc.command(name="listevents")
    async def yalc_listevents(self, ctx: commands.Context) -> None:
        """List all available log event types."""
        event_types = list((await self.cog.config.guild(ctx.guild).log_events()).keys())
        embed = discord.Embed(
            title="Available Log Event Types",
            description="\n".join(f"`{e}`" for e in event_types),
            color=discord.Color.blurple()
        )
        await ctx.send(embed=embed)

    @commands.group(name="yalctemplate")
    async def yalctemplate(self, ctx: commands.Context) -> None:
        """Manage log message templates for YALC events."""
        if ctx.invoked_subcommand is None:
            await ctx.send_help(ctx.command)

    @yalctemplate.command(name="set")
    async def set_template(self, ctx: commands.Context, event: str, *, template: str) -> None:
        """Set a custom log message template for an event. Use placeholders like {user}, {moderator}, {reason}."""
        valid_events = list((await self.cog.config.guild(ctx.guild).log_events()).keys())
        if event not in valid_events:
            await ctx.send(f"❌ Invalid event type. Valid events: {', '.join(valid_events)}")
            return
        await self.cog.config.guild(ctx.guild).set_raw(f"template_{event}", value=template)
        await ctx.send(f"✅ Template for `{event}` set!")

    @yalctemplate.command(name="clear")
    async def clear_template(self, ctx: commands.Context, event: str) -> None:
        """Clear the custom template for an event (revert to default)."""
        valid_events = list((await self.cog.config.guild(ctx.guild).log_events()).keys())
        if event not in valid_events:
            await ctx.send(f"❌ Invalid event type. Valid events: {', '.join(valid_events)}")
            return
        await self.cog.config.guild(ctx.guild).clear_raw(f"template_{event}")
        await ctx.send(f"✅ Template for `{event}` cleared (using default).")

    @commands.group(name="yalcretention")
    async def yalcretention(self, ctx: commands.Context) -> None:
        """Configure log retention for YALC."""
        if ctx.invoked_subcommand is None:
            await ctx.send_help(ctx.command)

    @yalcretention.command(name="set")
    async def set_retention(self, ctx: commands.Context, days: int) -> None:
        """Set the log retention period in days (minimum 1, maximum 365)."""
        if days < 1 or days > 365:
            await ctx.send("❌ Please provide a value between 1 and 365 days.")
            return
        await self.cog.config.guild(ctx.guild).set_raw("retention_days", value=days)
        await ctx.send(f"✅ Log retention set to {days} days.")

    @yalcretention.command(name="show")
    async def show_retention(self, ctx: commands.Context) -> None:
        """Show the current log retention period."""
        days = await self.cog.config.guild(ctx.guild).get_raw("retention_days", default=30)
        await ctx.send(f"Current log retention: {days} days.")

    @commands.group(name="yalcignore")
    async def yalcignore(self, ctx: commands.Context) -> None:
        """Manage ignore lists for YALC logging."""
        if ctx.invoked_subcommand is None:
            await ctx.send_help(ctx.command)

    @yalcignore.command(name="adduser")
    async def ignore_user(self, ctx: commands.Context, user: discord.User) -> None:
        """Ignore a user from being logged."""
        ignored = await self.cog.config.guild(ctx.guild).get_raw("ignored_users", default=[])
        if user.id in ignored:
            await ctx.send(f"{user.mention} is already ignored.")
            return
        ignored.append(user.id)
        await self.cog.config.guild(ctx.guild).set_raw("ignored_users", value=ignored)
        await ctx.send(f"{user.mention} will now be ignored in logs.")

    @yalcignore.command(name="removeuser")
    async def unignore_user(self, ctx: commands.Context, user: discord.User) -> None:
        """Remove a user from the ignore list."""
        ignored = await self.cog.config.guild(ctx.guild).get_raw("ignored_users", default=[])
        if user.id not in ignored:
            await ctx.send(f"{user.mention} is not ignored.")
            return
        ignored.remove(user.id)
        await self.cog.config.guild(ctx.guild).set_raw("ignored_users", value=ignored)
        await ctx.send(f"{user.mention} will no longer be ignored in logs.")

    @yalcignore.command(name="addrole")
    async def ignore_role(self, ctx: commands.Context, role: discord.Role) -> None:
        """Ignore a role from being logged."""
        ignored = await self.cog.config.guild(ctx.guild).get_raw("ignored_roles", default=[])
        if role.id in ignored:
            await ctx.send(f"{role.mention} is already ignored.")
            return
        ignored.append(role.id)
        await self.cog.config.guild(ctx.guild).set_raw("ignored_roles", value=ignored)
        await ctx.send(f"{role.mention} will now be ignored in logs.")

    @yalcignore.command(name="removerole")
    async def unignore_role(self, ctx: commands.Context, role: discord.Role) -> None:
        """Remove a role from the ignore list."""
        ignored = await self.cog.config.guild(ctx.guild).get_raw("ignored_roles", default=[])
        if role.id not in ignored:
            await ctx.send(f"{role.mention} is not ignored.")
            return
        ignored.remove(role.id)
        await self.cog.config.guild(ctx.guild).set_raw("ignored_roles", value=ignored)
        await ctx.send(f"{role.mention} will no longer be ignored in logs.")

    @yalcignore.command(name="addchannel")
    async def ignore_channel(self, ctx: commands.Context, channel: discord.TextChannel) -> None:
        """Ignore a channel from being logged."""
        ignored = await self.cog.config.guild(ctx.guild).get_raw("ignored_channels", default=[])
        if channel.id in ignored:
            await ctx.send(f"{channel.mention} is already ignored.")
            return
        ignored.append(channel.id)
        await self.cog.config.guild(ctx.guild).set_raw("ignored_channels", value=ignored)
        await ctx.send(f"{channel.mention} will now be ignored in logs.")

    @yalcignore.command(name="removechannel")
    async def unignore_channel(self, ctx: commands.Context, channel: discord.TextChannel) -> None:
        """Remove a channel from the ignore list."""
        ignored = await self.cog.config.guild(ctx.guild).get_raw("ignored_channels", default=[])
        if channel.id not in ignored:
            await ctx.send(f"{channel.mention} is not ignored.")
            return
        ignored.remove(channel.id)
        await self.cog.config.guild(ctx.guild).set_raw("ignored_channels", value=ignored)
        await ctx.send(f"{channel.mention} will no longer be ignored in logs.")

    @yalcignore.command(name="list")
    async def list_ignores(self, ctx: commands.Context) -> None:
        """List all ignored users, roles, and channels."""
        users = await self.cog.config.guild(ctx.guild).get_raw("ignored_users", default=[])
        roles = await self.cog.config.guild(ctx.guild).get_raw("ignored_roles", default=[])
        channels = await self.cog.config.guild(ctx.guild).get_raw("ignored_channels", default=[])
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

    @commands.group(name="yalcfilter")
    async def yalcfilter(self, ctx: commands.Context) -> None:
        """Manage advanced filters for YALC logging."""
        if ctx.invoked_subcommand is None:
            await ctx.send_help(ctx.command)

    @yalcfilter.command(name="add")
    async def add_filter(self, ctx: commands.Context, event: str, *, filter_str: str) -> None:
        """Add a filter for an event (e.g. only log if user/role/channel/keyword matches)."""
        valid_events = list((await self.cog.config.guild(ctx.guild).log_events()).keys())
        if event not in valid_events:
            await ctx.send(f"❌ Invalid event type. Valid events: {', '.join(valid_events)}")
            return
        filters = await self.cog.config.guild(ctx.guild).get_raw(f"filters_{event}", default=[])
        if filter_str in filters:
            await ctx.send("This filter already exists for this event.")
            return
        filters.append(filter_str)
        await self.cog.config.guild(ctx.guild).set_raw(f"filters_{event}", value=filters)
        await ctx.send(f"✅ Filter added for `{event}`.")

    @yalcfilter.command(name="remove")
    async def remove_filter(self, ctx: commands.Context, event: str, *, filter_str: str) -> None:
        """Remove a filter from an event."""
        valid_events = list((await self.cog.config.guild(ctx.guild).log_events()).keys())
        if event not in valid_events:
            await ctx.send(f"❌ Invalid event type. Valid events: {', '.join(valid_events)}")
            return
        filters = await self.cog.config.guild(ctx.guild).get_raw(f"filters_{event}", default=[])
        if filter_str not in filters:
            await ctx.send("This filter does not exist for this event.")
            return
        filters.remove(filter_str)
        await self.cog.config.guild(ctx.guild).set_raw(f"filters_{event}", value=filters)
        await ctx.send(f"✅ Filter removed for `{event}`.")

    @yalcfilter.command(name="list")
    async def list_filters(self, ctx: commands.Context, event: str) -> None:
        """List all filters for an event."""
        valid_events = list((await self.cog.config.guild(ctx.guild).log_events()).keys())
        if event not in valid_events:
            await ctx.send(f"❌ Invalid event type. Valid events: {', '.join(valid_events)}")
            return
        filters = await self.cog.config.guild(ctx.guild).get_raw(f"filters_{event}", default=[])
        embed = discord.Embed(
            title=f"Filters for {event}",
            description="\n".join(filters) or "No filters set.",
            color=discord.Color.blurple()
        )
        await ctx.send(embed=embed)
