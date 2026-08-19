"""Reviewed, searchable community knowledge without an external provider."""

from __future__ import annotations

import asyncio
import io
import json
import time
from contextlib import suppress
from typing import TYPE_CHECKING, Any

import discord
from discord.ext import tasks
from redbot.core import Config, commands

from .dashboard_integration import DashboardIntegration
from .search import rank_entries

if TYPE_CHECKING:
    from redbot.core.bot import Red


class KnowledgeGarden(DashboardIntegration, commands.Cog):
    """Turn solved discussions into reviewed, searchable answers."""

    CONFIG_IDENTIFIER = 2026081804
    SCHEMA_VERSION = 2

    def __init__(self, bot: Red) -> None:
        self.bot = bot
        self.config = Config.get_conf(self, identifier=self.CONFIG_IDENTIFIER, force_registration=True)
        self.config.register_guild(
            schema_version=self.SCHEMA_VERSION,
            next_id=1,
            require_separate_publisher=True,
            auto_capture_forumflow=False,
            review_channel_id=None,
            stale_days=90,
            last_review_notice_at=0,
            missed_searches={},
            entries={},
        )
        self._locks: dict[int, asyncio.Lock] = {}

    def _lock(self, guild_id: int) -> asyncio.Lock:
        if not hasattr(self, "_locks"):
            self._locks = {}
        return self._locks.setdefault(guild_id, asyncio.Lock())

    async def cog_load(self) -> None:
        for guild_id in await self.config.all_guilds():
            conf = self.config.guild_from_id(guild_id)
            entries = await conf.entries()
            changed = False
            for item in entries.values():
                defaults = {
                    "source_type": "manual",
                    "source_key": "",
                    "aliases": [],
                    "feedback": {},
                    "last_reviewed_at": item.get("updated_at", 0),
                    "last_reviewed_by": None,
                }
                for key, value in defaults.items():
                    if key not in item:
                        item[key] = value
                        changed = True
            if changed:
                await conf.entries.set(entries)
            await conf.schema_version.set(self.SCHEMA_VERSION)
        self.review_loop.start()

    def cog_unload(self) -> None:
        self.review_loop.cancel()

    @staticmethod
    def _now() -> int:
        return int(time.time())

    async def _entry(self, guild: discord.Guild, entry_id: int) -> tuple[dict[str, Any], dict[str, Any]]:
        entries = await self.config.guild(guild).entries()
        entry = entries.get(str(entry_id))
        if not entry:
            raise commands.BadArgument("Knowledge entry not found.")
        return entries, entry

    async def _save(self, guild: discord.Guild, entries: dict[str, Any], entry: dict[str, Any]) -> None:
        entry["updated_at"] = self._now()
        entries[str(entry["entry_id"])] = entry
        await self.config.guild(guild).entries.set(entries)

    async def _audit(self, guild: discord.Guild, action: str, status: str, detail: str = "") -> None:
        operations = self.bot.get_cog("OperationsCenter")
        if operations and hasattr(operations, "record_audit"):
            await operations.record_audit(guild, "KnowledgeGarden", action, status, detail)

    @staticmethod
    def _embed(entry: dict[str, Any]) -> discord.Embed:
        colors = {"draft": 0xFEE75C, "published": 0x57F287, "retired": 0x95A5A6}
        embed = discord.Embed(
            title=f"Knowledge #{entry['entry_id']}: {entry['title']}",
            description=entry["body"][:4000],
            color=colors[entry["status"]],
        )
        embed.add_field(name="Status", value=entry["status"].title())
        embed.add_field(name="Owner", value=f"<@{entry['owner_id']}>" if entry.get("owner_id") else "Unassigned")
        embed.add_field(name="Tags", value=", ".join(entry.get("tags", [])) or "None")
        feedback = list(entry.get("feedback", {}).values())
        if feedback:
            embed.add_field(
                name="Feedback",
                value=(
                    f"Helpful: {feedback.count('helpful')} · Outdated: {feedback.count('outdated')} · "
                    f"Unclear: {feedback.count('unclear')}"
                ),
                inline=False,
            )
        if entry.get("source_url"):
            embed.add_field(name="Source", value=f"[Open original discussion]({entry['source_url']})", inline=False)
        embed.set_footer(text=f"Revision {len(entry.get('revisions', [])) + 1} · updated {entry['updated_at']}")
        return embed

    async def _create(
        self,
        guild: discord.Guild,
        author_id: int,
        title: str,
        body: str,
        source_url: str = "",
        *,
        source_type: str = "manual",
        source_key: str = "",
    ) -> dict[str, Any]:
        title = " ".join(title.split())[:200]
        if not title or not body.strip():
            raise commands.BadArgument("A title and answer body are required.")
        conf = self.config.guild(guild)
        async with self._lock(getattr(guild, "id", 0)):
            existing = await conf.entries()
            if source_key:
                duplicate = next((item for item in existing.values() if item.get("source_key") == source_key), None)
                if duplicate:
                    raise commands.BadArgument(f"That source is already Knowledge entry #{duplicate['entry_id']}.")
            entry_id = int(await conf.next_id())
            now = self._now()
            entry = {
                "entry_id": entry_id,
                "title": title,
                "body": body.strip()[:12000],
                "tags": [],
                "source_url": source_url[:1000],
                "source_type": source_type[:50],
                "source_key": source_key[:200],
                "status": "draft",
                "created_by": author_id,
                "published_by": None,
                "owner_id": author_id,
                "created_at": now,
                "updated_at": now,
                "published_at": None,
                "revisions": [],
                "aliases": [],
                "feedback": {},
                "last_reviewed_at": now,
                "last_reviewed_by": None,
            }
            existing[str(entry_id)] = entry
            await conf.entries.set(existing)
            await conf.next_id.set(entry_id + 1)
        return entry

    @tasks.loop(hours=6)
    async def review_loop(self) -> None:
        now = self._now()
        for guild in self.bot.guilds:
            conf = self.config.guild(guild)
            settings = await conf.all()
            channel = guild.get_channel(settings["review_channel_id"])
            if not isinstance(channel, discord.TextChannel) or now - int(settings["last_review_notice_at"]) < 86400:
                continue
            cutoff = now - int(settings["stale_days"]) * 86400
            stale = [
                item
                for item in settings["entries"].values()
                if item.get("status") == "published" and int(item.get("last_reviewed_at") or item.get("updated_at", 0)) <= cutoff
            ]
            flagged = [
                item
                for item in settings["entries"].values()
                if item.get("status") == "published"
                and any(value in {"outdated", "unclear"} for value in item.get("feedback", {}).values())
            ]
            selected = {item["entry_id"]: item for item in (*flagged, *stale)}
            if selected:
                lines = [f"`#{item['entry_id']}` **{item['title']}**" for item in list(selected.values())[:20]]
                try:
                    await channel.send(
                        embed=discord.Embed(title="KnowledgeGarden review queue", description="\n".join(lines), color=0xFEE75C),
                        allowed_mentions=discord.AllowedMentions.none(),
                    )
                except (discord.Forbidden, discord.HTTPException) as error:
                    await self._audit(guild, "stale review notice", "failed", str(error))
                else:
                    await self._audit(guild, "stale review notice", "completed", f"{len(selected)} entries")
            await conf.last_review_notice_at.set(now)

    @review_loop.before_loop
    async def before_review_loop(self) -> None:
        await self.bot.wait_until_red_ready()

    async def create_from_forum_service(
        self,
        guild: discord.Guild,
        thread_id: int,
        message_id: int,
        actor_id: int,
    ) -> dict[str, Any]:
        """Create one draft from a ForumFlow accepted answer."""
        channel = guild.get_channel_or_thread(thread_id)
        if not isinstance(channel, discord.Thread):
            try:
                channel = await guild.fetch_channel(thread_id)
            except (discord.NotFound, discord.Forbidden, discord.HTTPException) as error:
                raise commands.BadArgument("The ForumFlow thread is unavailable.") from error
        if not isinstance(channel, discord.Thread):
            raise commands.BadArgument("The ForumFlow source is not a thread.")
        try:
            message = await channel.fetch_message(message_id)
        except (discord.NotFound, discord.Forbidden, discord.HTTPException) as error:
            raise commands.BadArgument("The accepted answer is unavailable.") from error
        body = message.content
        if message.attachments:
            body += "\n\nAttachments:\n" + "\n".join(item.url for item in message.attachments[:10])
        entry = await self._create(
            guild,
            actor_id,
            channel.name,
            body,
            message.jump_url,
            source_type="forumflow",
            source_key=f"forumflow:{thread_id}:{message_id}",
        )
        forumflow = self.bot.get_cog("ForumFlow")
        linker = getattr(forumflow, "set_knowledge_integration_link", None) if forumflow else None
        if linker:
            await linker(guild, thread_id, entry["entry_id"])
        return entry

    @commands.Cog.listener()
    async def on_taakoscogs_forum_solved(
        self,
        guild_id: int,
        thread_id: int,
        message_id: int,
        actor_id: int,
    ) -> None:
        guild = self.bot.get_guild(guild_id)
        if not guild or not await self.config.guild(guild).auto_capture_forumflow():
            return
        try:
            entry = await self.create_from_forum_service(guild, thread_id, message_id, actor_id)
        except commands.BadArgument as error:
            await self._audit(guild, "ForumFlow accepted answer", "skipped", str(error))
            return
        await self._audit(guild, "ForumFlow accepted answer", "completed", f"Knowledge #{entry['entry_id']}")
        channel = guild.get_channel_or_thread(thread_id)
        if isinstance(channel, discord.Thread):
            with suppress(discord.HTTPException):
                await channel.send(
                    f"KnowledgeGarden created review draft **#{entry['entry_id']}** from the accepted answer.",
                    allowed_mentions=discord.AllowedMentions.none(),
                )

    async def red_delete_data_for_user(self, *, requester: str, user_id: int) -> None:
        for guild_id in await self.config.all_guilds():
            conf = self.config.guild_from_id(guild_id)
            entries = await conf.entries()
            changed = False
            for entry in entries.values():
                for key in ("created_by", "published_by", "owner_id"):
                    if entry.get(key) == user_id:
                        entry[key] = None
                        changed = True
                for revision in entry.get("revisions", []):
                    if revision.get("actor_id") == user_id:
                        revision["actor_id"] = None
                        changed = True
                if str(user_id) in entry.get("feedback", {}):
                    entry["feedback"].pop(str(user_id), None)
                    changed = True
            if changed:
                await conf.entries.set(entries)

    @commands.hybrid_group(name="knowledgegarden", aliases=["kgarden"], invoke_without_command=True)
    @commands.guild_only()
    async def knowledge_garden(self, ctx: commands.Context) -> None:
        """Create, review, and search community knowledge."""
        await ctx.send_help()

    @knowledge_garden.command(name="setup")
    @commands.admin_or_permissions(manage_guild=True)
    async def setup_command(self, ctx: commands.Context, channel: discord.TextChannel | None = None) -> None:
        """Configure safe 90-day knowledge review defaults."""
        destination = channel or ctx.channel
        if not isinstance(destination, discord.TextChannel):
            raise commands.BadArgument("Choose a text channel for knowledge reviews.")
        permissions = destination.permissions_for(ctx.guild.me)
        if not permissions.send_messages or not permissions.embed_links:
            raise commands.BadArgument("I need Send Messages and Embed Links in that channel.")
        conf = self.config.guild(ctx.guild)
        await conf.review_channel_id.set(destination.id)
        await conf.stale_days.set(90)
        await conf.last_review_notice_at.set(self._now())
        await ctx.send(
            f"KnowledgeGarden reviews are configured in {destination.mention} with a 90-day stale threshold. "
            "ForumFlow auto-capture remains off until explicitly enabled."
        )

    @knowledge_garden.command(name="draft")
    @commands.mod_or_permissions(manage_messages=True)
    async def draft(self, ctx: commands.Context, title: str, *, answer: str) -> None:
        """Create a draft knowledge entry."""
        existing = await self.config.guild(ctx.guild).entries()
        similar = rank_entries(existing.values(), title, published_only=False)[:3]
        entry = await self._create(ctx.guild, ctx.author.id, title, answer)
        suffix = ""
        if similar:
            suffix = "\nPossible related entries: " + ", ".join(f"#{item['entry_id']}" for _score, item in similar)
        await ctx.send(embed=self._embed(entry), content=suffix or None)

    @knowledge_garden.command(name="capture")
    @commands.mod_or_permissions(manage_messages=True)
    async def capture(self, ctx: commands.Context, *, title: str) -> None:
        """Capture the message you replied to as a draft answer."""
        reference = ctx.message.reference
        if not reference or not reference.message_id:
            raise commands.BadArgument("Reply to the answer message you want to capture.")
        try:
            source = await ctx.channel.fetch_message(reference.message_id)
        except (discord.NotFound, discord.Forbidden, discord.HTTPException) as error:
            raise commands.BadArgument("I could not read the referenced message.") from error
        body = source.content
        if source.attachments:
            body += "\n\nAttachments:\n" + "\n".join(item.url for item in source.attachments[:10])
        entry = await self._create(ctx.guild, ctx.author.id, title, body, source.jump_url)
        await ctx.send(embed=self._embed(entry))

    @knowledge_garden.command(name="fromforum")
    @commands.mod_or_permissions(manage_messages=True)
    async def from_forum(self, ctx: commands.Context, thread: discord.Thread | None = None) -> None:
        """Create a draft from a ForumFlow post's accepted answer."""
        forumflow = self.bot.get_cog("ForumFlow")
        if forumflow is None:
            raise commands.BadArgument("ForumFlow is not loaded.")
        selected = thread or (ctx.channel if isinstance(ctx.channel, discord.Thread) else None)
        if not isinstance(selected, discord.Thread):
            raise commands.BadArgument("Run this in a tracked forum post or provide a thread.")
        records = await forumflow.config.guild(ctx.guild).records()
        record = records.get(str(selected.id))
        if not record or not record.get("accepted_message_id"):
            raise commands.BadArgument("That ForumFlow post has no accepted answer.")
        entry = await self.create_from_forum_service(
            ctx.guild,
            selected.id,
            int(record["accepted_message_id"]),
            ctx.author.id,
        )
        await ctx.send(embed=self._embed(entry))

    @knowledge_garden.command(name="integrations")
    @commands.mod_or_permissions(manage_messages=True)
    async def integrations(self, ctx: commands.Context, forumflow_auto: bool | None = None) -> None:
        """Show optional integration status or toggle ForumFlow auto-drafts."""
        conf = self.config.guild(ctx.guild)
        if forumflow_auto is not None:
            await conf.auto_capture_forumflow.set(forumflow_auto)
        enabled = await conf.auto_capture_forumflow()
        loaded = self.bot.get_cog("ForumFlow") is not None
        await ctx.send(
            f"ForumFlow: **{'loaded' if loaded else 'not loaded'}**\n"
            f"Automatic accepted-answer drafts: **{'enabled' if enabled else 'disabled'}**\n"
            "Manual capture remains available with `knowledgegarden fromforum`."
        )

    @knowledge_garden.command(name="publish")
    @commands.mod_or_permissions(manage_messages=True)
    async def publish(self, ctx: commands.Context, entry_id: int) -> None:
        """Publish a reviewed draft."""
        entries, entry = await self._entry(ctx.guild, entry_id)
        if entry["status"] != "draft":
            raise commands.BadArgument("Only draft entries can be published.")
        if await self.config.guild(ctx.guild).require_separate_publisher() and entry.get("created_by") == ctx.author.id:
            raise commands.BadArgument("A different staff member must publish this draft.")
        entry["status"] = "published"
        entry["published_by"] = ctx.author.id
        entry["published_at"] = self._now()
        entry["last_reviewed_at"] = self._now()
        entry["last_reviewed_by"] = ctx.author.id
        await self._save(ctx.guild, entries, entry)
        await ctx.send(embed=self._embed(entry))

    @knowledge_garden.command(name="edit")
    @commands.mod_or_permissions(manage_messages=True)
    async def edit(self, ctx: commands.Context, entry_id: int, *, answer: str) -> None:
        """Replace an answer while retaining a bounded revision."""
        entries, entry = await self._entry(ctx.guild, entry_id)
        entry.setdefault("revisions", []).append({"body": entry["body"], "actor_id": ctx.author.id, "at": self._now()})
        entry["revisions"] = entry["revisions"][-20:]
        entry["body"] = answer.strip()[:12000]
        if not entry["body"]:
            raise commands.BadArgument("The answer cannot be empty.")
        entry["last_reviewed_at"] = self._now()
        entry["last_reviewed_by"] = ctx.author.id
        await self._save(ctx.guild, entries, entry)
        await ctx.send(embed=self._embed(entry))

    @knowledge_garden.command(name="tags")
    @commands.mod_or_permissions(manage_messages=True)
    async def tags(self, ctx: commands.Context, entry_id: int, *, tags: str) -> None:
        """Set comma-separated search tags."""
        values = list(dict.fromkeys(part.strip().casefold()[:40] for part in tags.split(",") if part.strip()))[:15]
        entries, entry = await self._entry(ctx.guild, entry_id)
        entry["tags"] = values
        await self._save(ctx.guild, entries, entry)
        await ctx.send(embed=self._embed(entry))

    @knowledge_garden.command(name="aliases")
    @commands.mod_or_permissions(manage_messages=True)
    async def aliases(self, ctx: commands.Context, entry_id: int, *, aliases: str) -> None:
        """Set comma-separated alternate search phrases."""
        values = list(dict.fromkeys(part.strip().casefold()[:80] for part in aliases.split(",") if part.strip()))[:15]
        entries, entry = await self._entry(ctx.guild, entry_id)
        entry["aliases"] = values
        await self._save(ctx.guild, entries, entry)
        await ctx.send(embed=self._embed(entry))

    @knowledge_garden.command(name="retire")
    @commands.mod_or_permissions(manage_messages=True)
    async def retire(self, ctx: commands.Context, entry_id: int) -> None:
        """Remove an entry from public search without deleting its record."""
        entries, entry = await self._entry(ctx.guild, entry_id)
        entry["status"] = "retired"
        await self._save(ctx.guild, entries, entry)
        await ctx.send(embed=self._embed(entry))

    @knowledge_garden.command(name="search")
    async def search(self, ctx: commands.Context, *, query: str) -> None:
        """Search published answers locally."""
        ranked = rank_entries((await self.config.guild(ctx.guild).entries()).values(), query)[:10]
        if not ranked:
            normalized = " ".join(query.casefold().split())[:100]
            if normalized:
                async with self.config.guild(ctx.guild).missed_searches() as misses:
                    misses[normalized] = int(misses.get(normalized, 0)) + 1
                    if len(misses) > 100:
                        for key, _count in sorted(misses.items(), key=lambda item: (item[1], item[0]))[: len(misses) - 100]:
                            misses.pop(key, None)
            await ctx.send("No published answer matched that search.")
            return
        lines = [f"`#{entry['entry_id']}` **{entry['title']}** · score {score}" for score, entry in ranked]
        await ctx.send(
            embed=discord.Embed(title=f"Knowledge results for {query[:100]}", description="\n".join(lines), color=0x57F287)
        )

    @knowledge_garden.command(name="feedback")
    async def feedback(self, ctx: commands.Context, entry_id: int, rating: str) -> None:
        """Rate a published answer as helpful, outdated, or unclear."""
        rating = rating.casefold()
        if rating not in {"helpful", "outdated", "unclear", "clear"}:
            raise commands.BadArgument("Feedback must be `helpful`, `outdated`, `unclear`, or `clear`.")
        entries, entry = await self._entry(ctx.guild, entry_id)
        if entry["status"] != "published":
            raise commands.BadArgument("Only published entries accept feedback.")
        if rating == "clear":
            entry.setdefault("feedback", {}).pop(str(ctx.author.id), None)
            message = "Your feedback was cleared."
        else:
            entry.setdefault("feedback", {})[str(ctx.author.id)] = rating
            message = f"Recorded `{rating}` feedback for Knowledge #{entry_id}."
        await self._save(ctx.guild, entries, entry)
        await ctx.send(message)

    @knowledge_garden.command(name="reviewed")
    @commands.mod_or_permissions(manage_messages=True)
    async def reviewed(self, ctx: commands.Context, entry_id: int) -> None:
        """Mark an entry reviewed and clear outdated/unclear feedback."""
        entries, entry = await self._entry(ctx.guild, entry_id)
        entry["last_reviewed_at"] = self._now()
        entry["last_reviewed_by"] = ctx.author.id
        entry["feedback"] = {user_id: value for user_id, value in entry.get("feedback", {}).items() if value == "helpful"}
        await self._save(ctx.guild, entries, entry)
        await ctx.send(embed=self._embed(entry))

    @knowledge_garden.command(name="reviews")
    @commands.mod_or_permissions(manage_messages=True)
    async def reviews(
        self,
        ctx: commands.Context,
        channel: discord.TextChannel | None = None,
        stale_days: commands.Range[int, 0, 3650] = 90,
    ) -> None:
        """Configure the stale/flagged review queue; use zero days to disable notices."""
        conf = self.config.guild(ctx.guild)
        if int(stale_days) == 0:
            await conf.review_channel_id.set(None)
            await ctx.send("Knowledge review notices disabled.")
            return
        destination = channel or ctx.channel
        if not isinstance(destination, discord.TextChannel):
            raise commands.BadArgument("Choose a text channel for review notices.")
        permissions = destination.permissions_for(ctx.guild.me)
        if not permissions.send_messages or not permissions.embed_links:
            raise commands.BadArgument("I need Send Messages and Embed Links in the review channel.")
        await conf.review_channel_id.set(destination.id)
        await conf.stale_days.set(int(stale_days))
        await conf.last_review_notice_at.set(self._now())
        await ctx.send(f"Knowledge entries will be considered stale after {int(stale_days)} days.")

    @knowledge_garden.command(name="misses")
    @commands.mod_or_permissions(manage_messages=True)
    async def misses(self, ctx: commands.Context, clear: bool = False) -> None:
        """Show bounded unanswered search phrases, optionally clearing the report."""
        conf = self.config.guild(ctx.guild)
        misses = await conf.missed_searches()
        ranked = sorted(misses.items(), key=lambda item: (-item[1], item[0]))[:25]
        await ctx.send(
            "\n".join(f"**{count}×** {query}" for query, count in ranked)[:1900]
            if ranked
            else "No unanswered searches are retained."
        )
        if clear:
            await conf.missed_searches.set({})

    @knowledge_garden.command(name="show")
    async def show(self, ctx: commands.Context, entry_id: int) -> None:
        """Show a published answer; staff may also inspect drafts."""
        _entries, entry = await self._entry(ctx.guild, entry_id)
        if entry["status"] != "published" and not ctx.author.guild_permissions.manage_messages:
            raise commands.BadArgument("That entry is not published.")
        await ctx.send(embed=self._embed(entry))

    @knowledge_garden.command(name="export")
    @commands.admin_or_permissions(manage_guild=True)
    async def export(self, ctx: commands.Context) -> None:
        """Export the retained knowledge collection as JSON."""
        payload = json.dumps(await self.config.guild(ctx.guild).entries(), ensure_ascii=False, indent=2).encode()
        await ctx.send(file=discord.File(io.BytesIO(payload), filename="knowledge-garden.json"))
