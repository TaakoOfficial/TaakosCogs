"""Scheduled, provider-free community activity digests."""

from __future__ import annotations

import re
import time
from collections import Counter
from contextlib import suppress
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any

import discord
from discord.ext import tasks
from redbot.core import Config, commands

from .dashboard_integration import DashboardIntegration

if TYPE_CHECKING:
    from redbot.core.bot import Red


URL_RE = re.compile(r"https?://[^\s<>\])}\"']+", re.IGNORECASE)


class CommunityDigest(DashboardIntegration, commands.Cog):
    """Turn busy channels into a compact, link-rich recap."""

    CONFIG_IDENTIFIER = 2026080305
    COLOR = 0x9B59B6

    def __init__(self, bot: Red) -> None:
        self.bot = bot
        self.config = Config.get_conf(self, identifier=self.CONFIG_IDENTIFIER, force_registration=True)
        self.config.register_guild(
            source_ids=[],
            destination_id=None,
            enabled=False,
            interval_hours=168,
            lookback_hours=168,
            include_bots=False,
            min_messages=1,
            last_run_at=0,
            last_message_id=None,
            run_count=0,
        )

    async def cog_load(self) -> None:
        self.digest_loop.start()

    def cog_unload(self) -> None:
        self.digest_loop.cancel()

    async def red_delete_data_for_user(self, *, requester: str, user_id: int) -> None:
        return

    @staticmethod
    def _now() -> int:
        return int(time.time())

    async def _text_activity(
        self,
        channel: discord.TextChannel,
        after: datetime,
        include_bots: bool,
    ) -> dict[str, Any]:
        message_count = 0
        contributors: set[int] = set()
        links: Counter[str] = Counter()
        highlights: list[tuple[int, int, str, str]] = []
        async for message in channel.history(after=after, limit=2000, oldest_first=False):
            if message.author.bot and not include_bots:
                continue
            message_count += 1
            contributors.add(message.author.id)
            for url in URL_RE.findall(message.content):
                links[url.rstrip(".,;:!?")] += 1
            score = sum(reaction.count for reaction in message.reactions)
            if score or message.reference or len(message.content) >= 120:
                excerpt = " ".join(message.clean_content.split())[:180]
                highlights.append((score, message.id, excerpt or "Attachment or embed", message.jump_url))
        highlights.sort(key=lambda item: (item[0], item[1]), reverse=True)
        return {
            "name": channel.name,
            "mention": channel.mention,
            "messages": message_count,
            "contributors": len(contributors),
            "links": links,
            "highlights": highlights[:3],
            "kind": "text",
        }

    async def _forum_activity(self, channel: discord.ForumChannel, after: datetime) -> dict[str, Any]:
        threads: dict[int, discord.Thread] = {thread.id: thread for thread in channel.threads}
        try:
            async for thread in channel.archived_threads(limit=100):
                threads[thread.id] = thread
        except (discord.Forbidden, discord.HTTPException):
            pass
        recent = [thread for thread in threads.values() if thread.created_at and thread.created_at >= after]
        recent.sort(key=lambda thread: thread.created_at, reverse=True)
        return {
            "name": channel.name,
            "mention": channel.mention,
            "messages": len(recent),
            "contributors": len({thread.owner_id for thread in recent if thread.owner_id}),
            "links": Counter(),
            "highlights": [(0, thread.id, thread.name[:180], thread.jump_url) for thread in recent[:3]],
            "kind": "forum",
        }

    async def _build(self, guild: discord.Guild) -> tuple[list[discord.Embed], int]:
        settings = await self.config.guild(guild).all()
        after_ts = self._now() - int(settings["lookback_hours"]) * 3600
        after = datetime.fromtimestamp(after_ts, tz=timezone.utc)
        activities = []
        for channel_id in settings["source_ids"]:
            channel = guild.get_channel(channel_id)
            try:
                if isinstance(channel, discord.TextChannel):
                    activity = await self._text_activity(channel, after, bool(settings["include_bots"]))
                elif isinstance(channel, discord.ForumChannel):
                    activity = await self._forum_activity(channel, after)
                else:
                    continue
            except (discord.Forbidden, discord.HTTPException):
                continue
            if activity["messages"] >= int(settings["min_messages"]):
                activities.append(activity)
        total = sum(activity["messages"] for activity in activities)
        overview = discord.Embed(
            title=f"{guild.name} Community Digest",
            description=f"Activity from <t:{after_ts}:F> through <t:{self._now()}:F>.",
            color=self.COLOR,
            timestamp=discord.utils.utcnow(),
        )
        if not activities:
            overview.add_field(
                name="Quiet period", value="No configured source met the minimum activity threshold.", inline=False
            )
            return [overview], 0
        for activity in activities[:12]:
            unit = "new posts" if activity["kind"] == "forum" else "messages"
            overview.add_field(
                name=f"#{activity['name']}",
                value=f"**{activity['messages']:,}** {unit}\n**{activity['contributors']:,}** contributors",
            )
        highlights = discord.Embed(title="Discussions worth revisiting", color=self.COLOR)
        ranked = []
        link_counts: Counter[str] = Counter()
        for activity in activities:
            for score, message_id, excerpt, url in activity["highlights"]:
                ranked.append((score, message_id, activity["name"], excerpt, url))
            link_counts.update(activity["links"])
        ranked.sort(key=lambda item: (item[0], item[1]), reverse=True)
        for score, _message_id, channel_name, excerpt, url in ranked[:8]:
            suffix = f" · {score} reaction(s)" if score else ""
            highlights.add_field(name=f"#{channel_name}{suffix}", value=f"[{excerpt}]({url})", inline=False)
        if link_counts:
            popular = "\n".join(
                f"• [{urlparse_label(url)}](<{url}>) — {count} mention(s)" for url, count in link_counts.most_common(8)
            )
            highlights.add_field(name="Popular links", value=popular[:1024], inline=False)
        return [overview, highlights] if highlights.fields else [overview], total

    async def _send_digest(self, guild: discord.Guild, destination: discord.TextChannel) -> tuple[int, int | None]:
        embeds, total = await self._build(guild)
        last_message_id = None
        for embed in embeds:
            message = await destination.send(embed=embed)
            last_message_id = message.id
        conf = self.config.guild(guild)
        await conf.last_run_at.set(self._now())
        await conf.last_message_id.set(last_message_id)
        await conf.run_count.set((await conf.run_count()) + 1)
        return total, last_message_id

    @tasks.loop(minutes=30)
    async def digest_loop(self) -> None:
        now = self._now()
        for guild in self.bot.guilds:
            settings = await self.config.guild(guild).all()
            if not settings["enabled"] or not settings["destination_id"]:
                continue
            if now - settings["last_run_at"] < int(settings["interval_hours"]) * 3600:
                continue
            destination = guild.get_channel(settings["destination_id"])
            if isinstance(destination, discord.TextChannel):
                with suppress(discord.Forbidden, discord.HTTPException):
                    await self._send_digest(guild, destination)

    @digest_loop.before_loop
    async def before_digest_loop(self) -> None:
        await self.bot.wait_until_red_ready()

    @commands.hybrid_group(name="communitydigest", aliases=["digest"], invoke_without_command=True)
    @commands.guild_only()
    async def community_digest(self, ctx: commands.Context) -> None:
        """Configure and publish community activity recaps."""
        await ctx.send_help()

    @community_digest.group(name="source", invoke_without_command=True)
    @commands.admin_or_permissions(manage_guild=True)
    async def source(self, ctx: commands.Context) -> None:
        """Manage digest source channels."""
        source_ids = await self.config.guild(ctx.guild).source_ids()
        await ctx.send("Sources: " + (", ".join(f"<#{channel_id}>" for channel_id in source_ids) or "none"))

    @source.command(name="add")
    async def source_add(self, ctx: commands.Context, channel: discord.TextChannel | discord.ForumChannel) -> None:
        """Add a text or forum source."""
        async with self.config.guild(ctx.guild).source_ids() as source_ids:
            if channel.id not in source_ids:
                source_ids.append(channel.id)
        await ctx.send(f"Added {channel.mention} to the digest.")

    @source.command(name="remove")
    async def source_remove(self, ctx: commands.Context, channel: discord.TextChannel | discord.ForumChannel) -> None:
        """Remove a digest source."""
        async with self.config.guild(ctx.guild).source_ids() as source_ids:
            if channel.id in source_ids:
                source_ids.remove(channel.id)
        await ctx.send(f"Removed {channel.mention} from the digest.")

    @community_digest.command(name="destination")
    @commands.admin_or_permissions(manage_guild=True)
    async def destination(self, ctx: commands.Context, channel: discord.TextChannel | None = None) -> None:
        """Set the channel where automatic digests are posted."""
        await self.config.guild(ctx.guild).destination_id.set(channel.id if channel else None)
        await ctx.send(f"Digests will post in {channel.mention}." if channel else "Digest destination cleared.")

    @community_digest.command(name="schedule")
    @commands.admin_or_permissions(manage_guild=True)
    async def schedule(
        self,
        ctx: commands.Context,
        interval_hours: commands.Range[int, 1, 720],
        lookback_hours: commands.Range[int, 1, 720] | None = None,
    ) -> None:
        """Enable automatic posting and set interval/lookback hours."""
        conf = self.config.guild(ctx.guild)
        await conf.interval_hours.set(int(interval_hours))
        await conf.lookback_hours.set(int(lookback_hours or interval_hours))
        await conf.enabled.set(True)
        await ctx.send(f"Automatic digests enabled every **{interval_hours}h**.")

    @community_digest.command(name="disable")
    @commands.admin_or_permissions(manage_guild=True)
    async def disable(self, ctx: commands.Context) -> None:
        """Disable automatic posting without removing settings."""
        await self.config.guild(ctx.guild).enabled.set(False)
        await ctx.send("Automatic digests disabled.")

    @community_digest.command(name="preview")
    @commands.admin_or_permissions(manage_guild=True)
    async def preview(self, ctx: commands.Context) -> None:
        """Preview a digest in the current channel without updating its schedule."""
        async with ctx.typing():
            embeds, _total = await self._build(ctx.guild)
        for embed in embeds:
            await ctx.send(embed=embed)

    @community_digest.command(name="run")
    @commands.admin_or_permissions(manage_guild=True)
    async def run(self, ctx: commands.Context) -> None:
        """Publish a digest now to the configured destination."""
        destination_id = await self.config.guild(ctx.guild).destination_id()
        destination = ctx.guild.get_channel(destination_id) if destination_id else None
        if not isinstance(destination, discord.TextChannel):
            raise commands.BadArgument("Configure a destination channel first.")
        async with ctx.typing():
            total, _message_id = await self._send_digest(ctx.guild, destination)
        await ctx.send(f"Digest published with **{total:,}** qualifying activity item(s).")

    @community_digest.command(name="settings")
    async def settings(self, ctx: commands.Context) -> None:
        """Show digest configuration."""
        data = await self.config.guild(ctx.guild).all()
        embed = discord.Embed(title="CommunityDigest Settings", color=self.COLOR)
        embed.add_field(name="Enabled", value="Yes" if data["enabled"] else "No")
        embed.add_field(name="Interval", value=f"{data['interval_hours']} hours")
        embed.add_field(name="Lookback", value=f"{data['lookback_hours']} hours")
        embed.add_field(name="Destination", value=f"<#{data['destination_id']}>" if data["destination_id"] else "Not set")
        embed.add_field(name="Sources", value=", ".join(f"<#{item}>" for item in data["source_ids"]) or "None", inline=False)
        embed.add_field(name="Last run", value=f"<t:{data['last_run_at']}:R>" if data["last_run_at"] else "Never")
        await ctx.send(embed=embed)


def urlparse_label(url: str) -> str:
    """Return a compact human label without adding a urllib dependency to output code."""
    return url.split("//", 1)[-1].split("/", 1)[0][:80]
