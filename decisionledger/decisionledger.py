"""Auditable decisions with ownership, evidence, and outcomes."""

from __future__ import annotations

import asyncio
import csv
import io
import time
from contextlib import suppress
from typing import TYPE_CHECKING, Any

import discord
from discord.ext import tasks
from redbot.core import Config, commands

from .dashboard_integration import DashboardIntegration
from .models import VALID_STATUSES, compact_title, validate_transition

if TYPE_CHECKING:
    from redbot.core.bot import Red


class DecisionLedger(DashboardIntegration, commands.Cog):
    """Remember what was decided, why, by whom, and what happened next."""

    CONFIG_IDENTIFIER = 2026081803
    SCHEMA_VERSION = 2

    def __init__(self, bot: Red) -> None:
        self.bot = bot
        self.config = Config.get_conf(self, identifier=self.CONFIG_IDENTIFIER, force_registration=True)
        self.config.register_guild(
            schema_version=self.SCHEMA_VERSION,
            next_id=1,
            require_separate_approver=True,
            approval_quorum=1,
            required_evidence=0,
            auto_import_suggestions=False,
            auto_import_incident_actions=False,
            reminder_channel_id=None,
            reminder_interval_hours=24,
            last_reminder_run_at=0,
            templates={},
            decisions={},
        )
        self._locks: dict[int, asyncio.Lock] = {}

    def _lock(self, guild_id: int) -> asyncio.Lock:
        if not hasattr(self, "_locks"):
            self._locks = {}
        return self._locks.setdefault(guild_id, asyncio.Lock())

    async def cog_load(self) -> None:
        for guild_id in await self.config.all_guilds():
            conf = self.config.guild_from_id(guild_id)
            decisions = await conf.decisions()
            changed = False
            for item in decisions.values():
                defaults = {
                    "source_type": "manual",
                    "source_key": "",
                    "source_url": "",
                    "review_event_id": None,
                    "review_due_at": None,
                    "review_interval_days": 0,
                    "last_reminded_at": 0,
                    "risk": "normal",
                    "dependencies": [],
                    "supersedes_id": None,
                    "approval_ids": [item["approved_by"]] if item.get("approved_by") else [],
                }
                for key, value in defaults.items():
                    if key not in item:
                        item[key] = value
                        changed = True
            if changed:
                await conf.decisions.set(decisions)
            await conf.schema_version.set(self.SCHEMA_VERSION)
        self.reminder_loop.start()

    def cog_unload(self) -> None:
        self.reminder_loop.cancel()

    @staticmethod
    def _now() -> int:
        return int(time.time())

    async def _decision(self, guild: discord.Guild, decision_id: int) -> tuple[dict[str, Any], dict[str, Any]]:
        decisions = await self.config.guild(guild).decisions()
        decision = decisions.get(str(decision_id))
        if not decision:
            raise commands.BadArgument("Decision not found.")
        return decisions, decision

    async def _save(self, guild: discord.Guild, decisions: dict[str, Any], decision: dict[str, Any]) -> None:
        decision["updated_at"] = self._now()
        decisions[str(decision["decision_id"])] = decision
        await self.config.guild(guild).decisions.set(decisions)

    async def _audit(self, guild: discord.Guild, action: str, status: str, detail: str = "") -> None:
        operations = self.bot.get_cog("OperationsCenter")
        if operations and hasattr(operations, "record_audit"):
            await operations.record_audit(guild, "DecisionLedger", action, status, detail)

    @staticmethod
    def _embed(decision: dict[str, Any]) -> discord.Embed:
        colors = {
            "proposed": 0xFEE75C,
            "accepted": 0x5865F2,
            "rejected": 0xED4245,
            "implemented": 0x57F287,
            "superseded": 0x95A5A6,
        }
        embed = discord.Embed(
            title=f"Decision #{decision['decision_id']}: {decision['title']}",
            description=decision.get("rationale") or "No rationale recorded.",
            color=colors[decision["status"]],
        )
        embed.add_field(name="Status", value=decision["status"].title())
        if decision.get("approval_ids"):
            embed.add_field(name="Approvals", value=str(len(decision["approval_ids"])))
        embed.add_field(name="Owner", value=f"<@{decision['owner_id']}>" if decision.get("owner_id") else "Unassigned")
        embed.add_field(name="Due", value=f"<t:{decision['due_at']}:F>" if decision.get("due_at") else "Not set")
        if decision.get("outcome"):
            embed.add_field(name="Outcome", value=decision["outcome"][:1024], inline=False)
        if decision.get("review_due_at"):
            embed.add_field(name="Next review", value=f"<t:{decision['review_due_at']}:F>")
        if decision.get("risk") and decision["risk"] != "normal":
            embed.add_field(name="Risk", value=decision["risk"].title())
        if decision.get("dependencies"):
            embed.add_field(
                name="Depends on",
                value=", ".join(f"#{item}" for item in decision["dependencies"][:20]),
            )
        if decision.get("supersedes_id"):
            embed.add_field(name="Supersedes", value=f"Decision #{decision['supersedes_id']}")
        if decision.get("source_url"):
            embed.add_field(
                name="Imported source",
                value=f"[{decision.get('source_type', 'source').title()}]({decision['source_url']})",
                inline=False,
            )
        evidence = decision.get("evidence", [])
        if evidence:
            embed.add_field(
                name="Evidence",
                value="\n".join(f"[{item['label']}]({item['url']})" for item in evidence[-10:])[:1024],
                inline=False,
            )
        embed.set_footer(text=f"Proposed by {decision.get('created_by') or 'deleted user'}")
        return embed

    async def _create_imported(
        self,
        guild: discord.Guild,
        *,
        title: str,
        rationale: str,
        actor_id: int,
        source_type: str,
        source_key: str,
        source_url: str,
        status: str = "accepted",
        owner_id: int | None = None,
    ) -> dict[str, Any]:
        """Create one source-linked decision while preventing duplicate imports."""
        conf = self.config.guild(guild)
        async with self._lock(getattr(guild, "id", 0)):
            existing = await conf.decisions()
            duplicate = next((item for item in existing.values() if item.get("source_key") == source_key), None)
            if duplicate:
                raise commands.BadArgument(f"That source is already Decision #{duplicate['decision_id']}.")
            decision_id = int(await conf.next_id())
            now = self._now()
            item = {
                "decision_id": decision_id,
                "title": compact_title(title),
                "rationale": rationale[:4000],
                "status": status,
                "created_by": actor_id,
                "approved_by": actor_id if status != "proposed" else None,
                "owner_id": owner_id,
                "due_at": None,
                "outcome": "",
                "evidence": [],
                "history": [{"from": None, "to": status, "actor_id": actor_id, "at": now, "note": source_type}],
                "created_at": now,
                "updated_at": now,
                "source_type": source_type,
                "source_key": source_key,
                "source_url": source_url[:1000],
                "review_event_id": None,
                "review_due_at": None,
                "review_interval_days": 0,
                "last_reminded_at": 0,
                "risk": "normal",
                "dependencies": [],
                "supersedes_id": None,
                "approval_ids": [actor_id] if status != "proposed" else [],
            }
            existing[str(decision_id)] = item
            await conf.decisions.set(existing)
            await conf.next_id.set(decision_id + 1)
        return item

    async def _create_proposal(
        self,
        guild: discord.Guild,
        actor_id: int,
        title: str,
        rationale: str,
    ) -> dict[str, Any]:
        try:
            title = compact_title(title)
        except ValueError as error:
            raise commands.BadArgument(str(error)) from error
        conf = self.config.guild(guild)
        async with self._lock(getattr(guild, "id", 0)):
            decision_id = int(await conf.next_id())
            now = self._now()
            item = {
                "decision_id": decision_id,
                "title": title,
                "rationale": rationale[:4000],
                "status": "proposed",
                "created_by": actor_id,
                "approved_by": None,
                "owner_id": None,
                "due_at": None,
                "outcome": "",
                "evidence": [],
                "history": [{"from": None, "to": "proposed", "actor_id": actor_id, "at": now, "note": ""}],
                "created_at": now,
                "updated_at": now,
                "source_type": "manual",
                "source_key": "",
                "source_url": "",
                "review_event_id": None,
                "review_due_at": None,
                "review_interval_days": 0,
                "last_reminded_at": 0,
                "risk": "normal",
                "dependencies": [],
                "supersedes_id": None,
                "approval_ids": [],
            }
            decisions = await conf.decisions()
            decisions[str(decision_id)] = item
            await conf.decisions.set(decisions)
            await conf.next_id.set(decision_id + 1)
        return item

    async def import_suggestion_service(
        self,
        guild: discord.Guild,
        suggestion_id: int,
        actor_id: int,
        owner_id: int | None = None,
    ) -> dict[str, Any]:
        suggestionbox = self.bot.get_cog("SuggestionBox")
        if suggestionbox is None or not hasattr(suggestionbox, "get_suggestion_for_integration"):
            raise commands.BadArgument("SuggestionBox is not loaded or needs an update.")
        record = await suggestionbox.get_suggestion_for_integration(guild, suggestion_id)
        if not record:
            raise commands.BadArgument("Suggestion not found.")
        source_url = (
            f"https://discord.com/channels/{guild.id}/{record['channel_id']}/{record['message_id']}"
            if record.get("channel_id") and record.get("message_id")
            else ""
        )
        current = str(record.get("status") or "open")
        status = "implemented" if current == "implemented" else "accepted" if current == "approved" else "proposed"
        score = len(record.get("upvotes", [])) - len(record.get("downvotes", []))
        rationale = f"Imported from Suggestion #{suggestion_id} with score {score}."
        if record.get("decision_reason"):
            rationale += f"\n\nReview reason: {record['decision_reason']}"
        item = await self._create_imported(
            guild,
            title=str(record.get("text") or f"Suggestion #{suggestion_id}"),
            rationale=rationale,
            actor_id=actor_id,
            source_type="suggestionbox",
            source_key=f"suggestionbox:{suggestion_id}",
            source_url=source_url,
            status=status,
            owner_id=owner_id,
        )
        linker = getattr(suggestionbox, "set_suggestion_integration_link", None)
        if linker:
            await linker(guild, suggestion_id, item["decision_id"])
        return item

    async def import_incident_actions_service(
        self,
        guild: discord.Guild,
        incident_id: int,
        actor_id: int,
        *,
        action_id: int = 0,
        owner_id: int | None = None,
    ) -> list[dict[str, Any]]:
        opsroom = self.bot.get_cog("OpsRoom")
        if opsroom is None or not hasattr(opsroom, "get_incident_for_integration"):
            raise commands.BadArgument("OpsRoom is not loaded or needs an update.")
        incident = await opsroom.get_incident_for_integration(guild, incident_id)
        if not incident:
            raise commands.BadArgument("Incident not found.")
        actions = [
            action
            for action in incident.get("actions", [])
            if not action.get("completed_at") and (not action_id or action.get("action_id") == action_id)
        ]
        if not actions:
            raise commands.BadArgument("No matching incomplete incident actions were found.")
        source_url = f"https://discord.com/channels/{guild.id}/{incident['channel_id']}"
        imported = []
        for action in actions:
            try:
                item = await self._create_imported(
                    guild,
                    title=f"INC-{incident_id:04d} follow-up: {action['task']}",
                    rationale=incident.get("summary") or f"Follow-up from {incident.get('title', 'incident')}",
                    actor_id=actor_id,
                    source_type="opsroom",
                    source_key=f"opsroom:{incident_id}:{action['action_id']}",
                    source_url=source_url,
                    status="accepted",
                    owner_id=owner_id or action.get("owner_id"),
                )
                linker = getattr(opsroom, "set_action_integration_link", None)
                if linker:
                    await linker(guild, incident_id, action["action_id"], item["decision_id"])
            except commands.BadArgument as error:
                if "already Decision" in str(error):
                    continue
                raise
            imported.append(item)
        if not imported:
            raise commands.BadArgument("All matching incident actions were already imported.")
        return imported

    @tasks.loop(hours=1)
    async def reminder_loop(self) -> None:
        now = self._now()
        for guild in self.bot.guilds:
            conf = self.config.guild(guild)
            settings = await conf.all()
            channel = guild.get_channel(settings["reminder_channel_id"])
            if not isinstance(channel, discord.TextChannel):
                continue
            interval = max(1, int(settings["reminder_interval_hours"])) * 3600
            if now - int(settings["last_reminder_run_at"]) < interval:
                continue
            due = []
            decisions = settings["decisions"]
            for item in decisions.values():
                overdue = item.get("due_at") and item["due_at"] <= now and item["status"] == "accepted"
                review = item.get("review_due_at") and item["review_due_at"] <= now and item["status"] != "superseded"
                if (overdue or review) and now - int(item.get("last_reminded_at", 0)) >= interval:
                    due.append((item, "review due" if review else "implementation overdue"))
                    item["last_reminded_at"] = now
            if due:
                lines = [
                    f"`#{item['decision_id']}` **{item['title']}** — {reason}"
                    + (f" · owner <@{item['owner_id']}>" if item.get("owner_id") else "")
                    for item, reason in due[:20]
                ]
                try:
                    await channel.send(
                        embed=discord.Embed(title="DecisionLedger reminders", description="\n".join(lines), color=0xFEE75C),
                        allowed_mentions=discord.AllowedMentions.none(),
                    )
                except (discord.Forbidden, discord.HTTPException) as error:
                    await self._audit(guild, "reminders", "failed", str(error))
                else:
                    await conf.decisions.set(decisions)
                    await self._audit(guild, "reminders", "completed", f"{len(due)} decision(s)")
            await conf.last_reminder_run_at.set(now)

    @reminder_loop.before_loop
    async def before_reminder_loop(self) -> None:
        await self.bot.wait_until_red_ready()

    @commands.Cog.listener()
    async def on_taakoscogs_suggestion_decided(
        self,
        guild_id: int,
        suggestion_id: int,
        status: str,
        actor_id: int,
    ) -> None:
        guild = self.bot.get_guild(guild_id)
        if not guild:
            return
        decisions = await self.config.guild(guild).decisions()
        existing = next(
            (item for item in decisions.values() if item.get("source_key") == f"suggestionbox:{suggestion_id}"),
            None,
        )
        if existing:
            if status == "implemented" and existing.get("status") == "accepted":
                existing["status"] = "implemented"
                existing["outcome"] = "SuggestionBox marked the source suggestion as implemented."
                existing.setdefault("history", []).append(
                    {
                        "from": "accepted",
                        "to": "implemented",
                        "actor_id": actor_id,
                        "at": self._now(),
                        "note": "SuggestionBox sync",
                    }
                )
                await self._save(guild, decisions, existing)
                await self._audit(guild, "SuggestionBox status sync", "completed", f"Decision #{existing['decision_id']}")
            return
        if not await self.config.guild(guild).auto_import_suggestions():
            return
        try:
            item = await self.import_suggestion_service(guild, suggestion_id, actor_id)
        except commands.BadArgument as error:
            await self._audit(guild, "SuggestionBox import", "skipped", str(error))
            return
        await self._audit(guild, "SuggestionBox import", "completed", f"Decision #{item['decision_id']}")
        suggestionbox = self.bot.get_cog("SuggestionBox")
        record = await suggestionbox.get_suggestion_for_integration(guild, suggestion_id)
        channel = guild.get_channel(record.get("thread_id") or record.get("channel_id")) if record else None
        if isinstance(channel, (discord.TextChannel, discord.Thread)):
            with suppress(discord.HTTPException):
                await channel.send(
                    f"DecisionLedger created **Decision #{item['decision_id']}** from this suggestion.",
                    allowed_mentions=discord.AllowedMentions.none(),
                )

    @commands.Cog.listener()
    async def on_taakoscogs_incident_resolved(self, guild_id: int, incident_id: int, actor_id: int) -> None:
        guild = self.bot.get_guild(guild_id)
        if not guild or not await self.config.guild(guild).auto_import_incident_actions():
            return
        try:
            items = await self.import_incident_actions_service(guild, incident_id, actor_id)
        except commands.BadArgument as error:
            await self._audit(guild, "OpsRoom action import", "skipped", str(error))
            return
        await self._audit(guild, "OpsRoom action import", "completed", f"{len(items)} decision(s)")
        opsroom = self.bot.get_cog("OpsRoom")
        incident = await opsroom.get_incident_for_integration(guild, incident_id)
        channel = guild.get_channel(incident.get("channel_id")) if incident else None
        if isinstance(channel, discord.TextChannel):
            with suppress(discord.HTTPException):
                await channel.send(
                    f"DecisionLedger imported {len(items)} incomplete action(s): "
                    + ", ".join(f"Decision #{item['decision_id']}" for item in items),
                    allowed_mentions=discord.AllowedMentions.none(),
                )

    @commands.Cog.listener()
    async def on_taakoscogs_incident_action_completed(
        self,
        guild_id: int,
        incident_id: int,
        action_id: int,
        actor_id: int,
    ) -> None:
        guild = self.bot.get_guild(guild_id)
        if not guild:
            return
        decisions = await self.config.guild(guild).decisions()
        item = next(
            (entry for entry in decisions.values() if entry.get("source_key") == f"opsroom:{incident_id}:{action_id}"),
            None,
        )
        if not item or item.get("status") != "accepted":
            return
        item["status"] = "implemented"
        item["outcome"] = "OpsRoom marked the linked incident action complete."
        item.setdefault("history", []).append(
            {"from": "accepted", "to": "implemented", "actor_id": actor_id, "at": self._now(), "note": "OpsRoom sync"}
        )
        await self._save(guild, decisions, item)
        await self._audit(guild, "OpsRoom action sync", "completed", f"Decision #{item['decision_id']}")

    async def red_delete_data_for_user(self, *, requester: str, user_id: int) -> None:
        for guild_id in await self.config.all_guilds():
            conf = self.config.guild_from_id(guild_id)
            decisions = await conf.decisions()
            changed = False
            for decision in decisions.values():
                for key in ("created_by", "approved_by", "owner_id"):
                    if decision.get(key) == user_id:
                        decision[key] = None
                        changed = True
                for entry in decision.get("history", []):
                    if entry.get("actor_id") == user_id:
                        entry["actor_id"] = None
                        changed = True
                for evidence in decision.get("evidence", []):
                    if evidence.get("added_by") == user_id:
                        evidence["added_by"] = None
                        changed = True
                if user_id in decision.get("approval_ids", []):
                    decision["approval_ids"] = [item for item in decision["approval_ids"] if item != user_id]
                    changed = True
            if changed:
                await conf.decisions.set(decisions)

    @commands.hybrid_group(name="decision", aliases=["decisionledger"], invoke_without_command=True)
    @commands.guild_only()
    async def decision(self, ctx: commands.Context) -> None:
        """Record and review staff decisions."""
        await ctx.send_help()

    @decision.command(name="setup")
    @commands.admin_or_permissions(manage_guild=True)
    async def setup_command(self, ctx: commands.Context, channel: discord.TextChannel | None = None) -> None:
        """Configure safe reminder defaults in one command."""
        destination = channel or ctx.channel
        if not isinstance(destination, discord.TextChannel):
            raise commands.BadArgument("Choose a text channel for decision reminders.")
        permissions = destination.permissions_for(ctx.guild.me)
        if not permissions.send_messages or not permissions.embed_links:
            raise commands.BadArgument("I need Send Messages and Embed Links in that channel.")
        conf = self.config.guild(ctx.guild)
        await conf.reminder_channel_id.set(destination.id)
        await conf.reminder_interval_hours.set(24)
        await conf.last_reminder_run_at.set(self._now())
        await ctx.send(
            f"DecisionLedger reminders are configured in {destination.mention} every 24 hours. "
            f"Approval quorum remains 1 with no required evidence; customize it with "
            f"`{ctx.clean_prefix}decision governance <approvals> <evidence>`."
        )

    @decision.command(name="propose")
    @commands.admin_or_permissions(manage_guild=True)
    async def propose(self, ctx: commands.Context, title: str, *, rationale: str = "") -> None:
        """Create a proposed decision."""
        decision = await self._create_proposal(ctx.guild, ctx.author.id, title, rationale)
        await ctx.send(embed=self._embed(decision))

    @decision.group(name="template", invoke_without_command=True)
    @commands.admin_or_permissions(manage_guild=True)
    async def template(self, ctx: commands.Context) -> None:
        """Manage reusable decision proposal templates."""
        templates = await self.config.guild(ctx.guild).templates()
        await ctx.send(", ".join(f"`{name}`" for name in sorted(templates)) or "No decision templates are configured.")

    @template.command(name="save")
    async def template_save(self, ctx: commands.Context, name: str, title: str, *, rationale: str = "") -> None:
        """Save or replace a named proposal template."""
        key = name.casefold()[:50]
        if not key:
            raise commands.BadArgument("A template name is required.")
        try:
            title = compact_title(title)
        except ValueError as error:
            raise commands.BadArgument(str(error)) from error
        async with self.config.guild(ctx.guild).templates() as templates:
            if key not in templates and len(templates) >= 25:
                raise commands.BadArgument("A guild can retain at most 25 decision templates.")
            templates[key] = {"title": title, "rationale": rationale[:4000]}
        await ctx.send(f"Saved decision template `{key}`.")

    @template.command(name="remove")
    async def template_remove(self, ctx: commands.Context, name: str) -> None:
        """Remove a named decision template."""
        async with self.config.guild(ctx.guild).templates() as templates:
            removed = templates.pop(name.casefold(), None)
        await ctx.send("Template removed." if removed else "Template not found.")

    @decision.command(name="fromtemplate")
    @commands.admin_or_permissions(manage_guild=True)
    async def from_template(self, ctx: commands.Context, name: str) -> None:
        """Create a proposal from a saved template."""
        template = (await self.config.guild(ctx.guild).templates()).get(name.casefold())
        if not template:
            raise commands.BadArgument("Template not found.")
        item = await self._create_proposal(ctx.guild, ctx.author.id, template["title"], template["rationale"])
        await ctx.send(embed=self._embed(item))

    @decision.command(name="show")
    async def show(self, ctx: commands.Context, decision_id: int) -> None:
        """Show one decision."""
        _decisions, decision = await self._decision(ctx.guild, decision_id)
        await ctx.send(embed=self._embed(decision))

    @decision.command(name="list")
    async def list_decisions(self, ctx: commands.Context, status: str = "accepted") -> None:
        """List decisions by status, or use all."""
        status = status.casefold()
        if status != "all" and status not in VALID_STATUSES:
            raise commands.BadArgument("Unknown status.")
        decisions = (await self.config.guild(ctx.guild).decisions()).values()
        selected = [item for item in decisions if status == "all" or item["status"] == status]
        selected.sort(key=lambda item: item["updated_at"], reverse=True)
        lines = [f"`#{item['decision_id']}` [{item['status']}] {item['title']}" for item in selected[:30]]
        await ctx.send("\n".join(lines) if lines else "No matching decisions.")

    @decision.command(name="fromsuggestion")
    @commands.admin_or_permissions(manage_guild=True)
    async def from_suggestion(
        self,
        ctx: commands.Context,
        suggestion_id: int,
        owner: discord.Member | None = None,
    ) -> None:
        """Import a SuggestionBox record with a backlink and duplicate guard."""
        item = await self.import_suggestion_service(
            ctx.guild,
            suggestion_id,
            ctx.author.id,
            owner.id if owner else None,
        )
        await ctx.send(embed=self._embed(item))

    @decision.command(name="fromincident")
    @commands.admin_or_permissions(manage_guild=True)
    async def from_incident(
        self,
        ctx: commands.Context,
        incident_id: int,
        action_id: int = 0,
        owner: discord.Member | None = None,
    ) -> None:
        """Import one incomplete OpsRoom action, or zero for every incomplete action."""
        items = await self.import_incident_actions_service(
            ctx.guild,
            incident_id,
            ctx.author.id,
            action_id=action_id,
            owner_id=owner.id if owner else None,
        )
        await ctx.send(f"Imported {len(items)} decision(s): " + ", ".join(f"#{item['decision_id']}" for item in items))

    @decision.command(name="integrations")
    @commands.admin_or_permissions(manage_guild=True)
    async def integrations(self, ctx: commands.Context) -> None:
        """Show optional integration availability and automation settings."""
        settings = await self.config.guild(ctx.guild).all()
        lines = [
            (
                f"SuggestionBox: **{'loaded' if self.bot.get_cog('SuggestionBox') else 'not loaded'}** · auto-import "
                f"**{'on' if settings['auto_import_suggestions'] else 'off'}**"
            ),
            (
                f"OpsRoom: **{'loaded' if self.bot.get_cog('OpsRoom') else 'not loaded'}** · "
                f"resolved-action auto-import **{'on' if settings['auto_import_incident_actions'] else 'off'}**"
            ),
            f"StaffOps: **{'loaded' if self.bot.get_cog('StaffOps') else 'not loaded'}** · owner context available",
            f"EventCheckin: **{'loaded' if self.bot.get_cog('EventCheckin') else 'not loaded'}** · review events available",
        ]
        await ctx.send("\n".join(lines))

    @decision.command(name="autolink")
    @commands.admin_or_permissions(manage_guild=True)
    async def auto_link(self, ctx: commands.Context, source: str, enabled: bool) -> None:
        """Toggle automatic imports from suggestionbox or opsroom."""
        source = source.casefold()
        conf = self.config.guild(ctx.guild)
        if source in {"suggestion", "suggestions", "suggestionbox"}:
            await conf.auto_import_suggestions.set(enabled)
            label = "SuggestionBox approvals"
        elif source in {"incident", "incidents", "opsroom"}:
            await conf.auto_import_incident_actions.set(enabled)
            label = "resolved OpsRoom actions"
        else:
            raise commands.BadArgument("Source must be `suggestionbox` or `opsroom`.")
        await ctx.send(f"Automatic imports for {label} are now {'enabled' if enabled else 'disabled'}.")

    async def _staffops_context(self, guild: discord.Guild, owner_id: int | None) -> str | None:
        staffops = self.bot.get_cog("StaffOps")
        if not owner_id or staffops is None or not hasattr(staffops, "get_member_context"):
            return None
        context = await staffops.get_member_context(guild, owner_id)
        if not context:
            return "StaffOps: the owner is not in the configured staff team."
        details = ["active shift" if context["active_shift"] else "off shift"]
        if context.get("on_call_position"):
            details.append(f"on-call #{context['on_call_position']}")
        if context.get("approved_leave"):
            details.append(f"leave until {context['approved_leave']}")
        if context.get("availability"):
            details.append(context["availability"])
        return "StaffOps: " + " · ".join(details)

    @decision.command(name="accept")
    @commands.admin_or_permissions(manage_guild=True)
    async def accept(self, ctx: commands.Context, decision_id: int, owner: discord.Member | None = None) -> None:
        """Accept a proposal and optionally assign its owner."""
        decisions, item = await self._decision(ctx.guild, decision_id)
        if await self.config.guild(ctx.guild).require_separate_approver() and item.get("created_by") == ctx.author.id:
            raise commands.BadArgument("A different staff member must accept this proposal.")
        try:
            validate_transition(item["status"], "accepted")
        except ValueError as error:
            raise commands.BadArgument(str(error)) from error
        settings = await self.config.guild(ctx.guild).all()
        if len(item.get("evidence", [])) < int(settings["required_evidence"]):
            raise commands.BadArgument(f"This guild requires {settings['required_evidence']} evidence link(s) before acceptance.")
        approvals = item.setdefault("approval_ids", [])
        if ctx.author.id not in approvals:
            approvals.append(ctx.author.id)
        quorum = max(1, int(settings["approval_quorum"]))
        if len(approvals) < quorum:
            await self._save(ctx.guild, decisions, item)
            await ctx.send(f"Approval recorded for Decision #{decision_id}: **{len(approvals)}/{quorum}** required.")
            return
        previous = item["status"]
        item["status"] = "accepted"
        item["approved_by"] = ctx.author.id
        item["owner_id"] = owner.id if owner else item.get("owner_id")
        item["history"].append({"from": previous, "to": "accepted", "actor_id": ctx.author.id, "at": self._now(), "note": ""})
        await self._save(ctx.guild, decisions, item)
        await ctx.send(content=await self._staffops_context(ctx.guild, item.get("owner_id")), embed=self._embed(item))

    @decision.command(name="status")
    @commands.admin_or_permissions(manage_guild=True)
    async def status(self, ctx: commands.Context, decision_id: int, status: str, *, note: str = "") -> None:
        """Move a decision through its allowed lifecycle."""
        decisions, item = await self._decision(ctx.guild, decision_id)
        target = status.casefold()
        if target == "accepted":
            raise commands.BadArgument("Use `decision accept` so quorum and evidence rules are enforced.")
        try:
            validate_transition(item["status"], target)
        except ValueError as error:
            raise commands.BadArgument(str(error)) from error
        previous = item["status"]
        item["status"] = target
        if target in {"rejected", "proposed"}:
            item["approval_ids"] = []
            item["approved_by"] = None
        if target in {"rejected", "implemented", "superseded"}:
            item["outcome"] = note[:4000]
        item["history"].append(
            {"from": previous, "to": target, "actor_id": ctx.author.id, "at": self._now(), "note": note[:1000]}
        )
        await self._save(ctx.guild, decisions, item)
        await ctx.send(embed=self._embed(item))

    @decision.command(name="governance")
    @commands.admin_or_permissions(manage_guild=True)
    async def governance(
        self,
        ctx: commands.Context,
        approval_quorum: commands.Range[int, 1, 20],
        required_evidence: commands.Range[int, 0, 25] = 0,
    ) -> None:
        """Set required distinct approvals and evidence links for manual proposals."""
        conf = self.config.guild(ctx.guild)
        await conf.approval_quorum.set(int(approval_quorum))
        await conf.required_evidence.set(int(required_evidence))
        await ctx.send(
            f"Manual proposals now require **{int(approval_quorum)}** approval(s) and "
            f"**{int(required_evidence)}** evidence link(s)."
        )

    @decision.command(name="risk")
    @commands.admin_or_permissions(manage_guild=True)
    async def risk(self, ctx: commands.Context, decision_id: int, level: str) -> None:
        """Set a decision's low, normal, high, or critical risk level."""
        level = level.casefold()
        if level not in {"low", "normal", "high", "critical"}:
            raise commands.BadArgument("Risk must be `low`, `normal`, `high`, or `critical`.")
        decisions, item = await self._decision(ctx.guild, decision_id)
        item["risk"] = level
        await self._save(ctx.guild, decisions, item)
        await ctx.send(embed=self._embed(item))

    @decision.command(name="depends")
    @commands.admin_or_permissions(manage_guild=True)
    async def depends(self, ctx: commands.Context, decision_id: int, dependency_id: int) -> None:
        """Toggle a dependency on another retained decision."""
        if decision_id == dependency_id:
            raise commands.BadArgument("A decision cannot depend on itself.")
        decisions, item = await self._decision(ctx.guild, decision_id)
        if str(dependency_id) not in decisions:
            raise commands.BadArgument("Dependency decision not found.")
        dependencies = item.setdefault("dependencies", [])
        if dependency_id in dependencies:
            dependencies.remove(dependency_id)
        elif len(dependencies) < 20:
            dependencies.append(dependency_id)
        else:
            raise commands.BadArgument("A decision can retain at most 20 dependencies.")
        await self._save(ctx.guild, decisions, item)
        await ctx.send(embed=self._embed(item))

    @decision.command(name="supersedes")
    @commands.admin_or_permissions(manage_guild=True)
    async def supersedes(self, ctx: commands.Context, decision_id: int, old_decision_id: int) -> None:
        """Link a replacement decision and supersede the previous accepted decision."""
        if decision_id == old_decision_id:
            raise commands.BadArgument("A decision cannot supersede itself.")
        decisions, item = await self._decision(ctx.guild, decision_id)
        old = decisions.get(str(old_decision_id))
        if not old:
            raise commands.BadArgument("Previous decision not found.")
        try:
            validate_transition(old["status"], "superseded")
        except ValueError as error:
            raise commands.BadArgument(str(error)) from error
        previous = old["status"]
        old["status"] = "superseded"
        old["outcome"] = f"Superseded by Decision #{decision_id}."
        old["history"].append(
            {
                "from": previous,
                "to": "superseded",
                "actor_id": ctx.author.id,
                "at": self._now(),
                "note": f"Decision #{decision_id}",
            }
        )
        item["supersedes_id"] = old_decision_id
        decisions[str(old_decision_id)] = old
        await self._save(ctx.guild, decisions, item)
        await ctx.send(embed=self._embed(item))

    @decision.command(name="assign")
    @commands.admin_or_permissions(manage_guild=True)
    async def assign(self, ctx: commands.Context, decision_id: int, owner: discord.Member | None = None) -> None:
        """Assign or clear the implementation owner."""
        decisions, item = await self._decision(ctx.guild, decision_id)
        item["owner_id"] = owner.id if owner else None
        await self._save(ctx.guild, decisions, item)
        await ctx.send(content=await self._staffops_context(ctx.guild, item.get("owner_id")), embed=self._embed(item))

    @decision.command(name="reviewevent")
    @commands.admin_or_permissions(manage_guild=True)
    async def review_event(
        self,
        ctx: commands.Context,
        decision_id: int,
        starts_at: int,
        duration_minutes: commands.Range[int, 1, 10080] = 60,
    ) -> None:
        """Create an EventCheckin draft for reviewing a decision."""
        eventcheckin = self.bot.get_cog("EventCheckin")
        if eventcheckin is None or not hasattr(eventcheckin, "create_draft_service"):
            raise commands.BadArgument("EventCheckin is not loaded or needs an update.")
        decisions, item = await self._decision(ctx.guild, decision_id)
        if item.get("review_event_id"):
            raise commands.BadArgument(f"This decision already links EventCheckin event #{item['review_event_id']}.")
        event = await eventcheckin.create_draft_service(
            ctx.guild,
            actor_id=ctx.author.id,
            starts_at=starts_at,
            capacity=0,
            title=f"Decision review #{decision_id}: {item['title']}",
            description=f"Review Decision #{decision_id}.\n\n{item.get('rationale') or ''}",
            duration_minutes=int(duration_minutes),
            source_type="decisionledger",
            source_id=decision_id,
        )
        item["review_event_id"] = event["event_id"]
        await self._save(ctx.guild, decisions, item)
        await ctx.send(
            f"Created EventCheckin draft **#{event['event_id']}**. Post it with "
            f"`{ctx.clean_prefix}eventcheckin post {event['event_id']}`."
        )

    @decision.command(name="due")
    @commands.admin_or_permissions(manage_guild=True)
    async def due(self, ctx: commands.Context, decision_id: int, unix_timestamp: int = 0) -> None:
        """Set a Unix due timestamp, or zero to clear it."""
        if unix_timestamp and unix_timestamp <= self._now():
            raise commands.BadArgument("The due timestamp must be in the future.")
        decisions, item = await self._decision(ctx.guild, decision_id)
        item["due_at"] = unix_timestamp or None
        await self._save(ctx.guild, decisions, item)
        await ctx.send(embed=self._embed(item))

    @decision.command(name="reviewcycle")
    @commands.admin_or_permissions(manage_guild=True)
    async def review_cycle(self, ctx: commands.Context, decision_id: int, days: commands.Range[int, 0, 3650]) -> None:
        """Set a recurring review interval in days, or zero to disable it."""
        decisions, item = await self._decision(ctx.guild, decision_id)
        item["review_interval_days"] = int(days)
        item["review_due_at"] = self._now() + int(days) * 86400 if days else None
        item["last_reminded_at"] = 0
        await self._save(ctx.guild, decisions, item)
        await ctx.send(embed=self._embed(item))

    @decision.command(name="reviewed")
    @commands.admin_or_permissions(manage_guild=True)
    async def reviewed(self, ctx: commands.Context, decision_id: int, *, note: str = "") -> None:
        """Record a completed review and schedule the next cycle."""
        decisions, item = await self._decision(ctx.guild, decision_id)
        days = int(item.get("review_interval_days", 0))
        if not days:
            raise commands.BadArgument("This decision has no review cycle.")
        item["review_due_at"] = self._now() + days * 86400
        item["last_reminded_at"] = 0
        item["history"].append(
            {
                "from": item["status"],
                "to": item["status"],
                "actor_id": ctx.author.id,
                "at": self._now(),
                "note": f"Review: {note[:900]}",
            }
        )
        await self._save(ctx.guild, decisions, item)
        await ctx.send(embed=self._embed(item))

    @decision.command(name="reminders")
    @commands.admin_or_permissions(manage_guild=True)
    async def reminders(
        self,
        ctx: commands.Context,
        channel: discord.TextChannel | None = None,
        interval_hours: commands.Range[int, 0, 168] = 24,
    ) -> None:
        """Configure overdue and review reminders; use zero hours to disable them."""
        conf = self.config.guild(ctx.guild)
        if int(interval_hours) == 0:
            await conf.reminder_channel_id.set(None)
            await ctx.send("Decision reminders disabled.")
            return
        destination = channel or ctx.channel
        if not isinstance(destination, discord.TextChannel):
            raise commands.BadArgument("Choose a text channel for reminders.")
        permissions = destination.permissions_for(ctx.guild.me)
        if not permissions.send_messages or not permissions.embed_links:
            raise commands.BadArgument("I need Send Messages and Embed Links in the reminder channel.")
        await conf.reminder_channel_id.set(destination.id)
        await conf.reminder_interval_hours.set(int(interval_hours))
        await conf.last_reminder_run_at.set(self._now())
        await ctx.send(f"Decision reminders will run every {int(interval_hours)} hour(s) in {destination.mention}.")

    @decision.command(name="evidence")
    @commands.admin_or_permissions(manage_guild=True)
    async def evidence(self, ctx: commands.Context, decision_id: int, url: str, *, label: str = "Source") -> None:
        """Attach an HTTPS evidence link without fetching it."""
        if not url.startswith("https://") or len(url) > 1000:
            raise commands.BadArgument("Evidence must be an HTTPS URL up to 1,000 characters.")
        decisions, item = await self._decision(ctx.guild, decision_id)
        if len(item["evidence"]) >= 25:
            raise commands.BadArgument("A decision can retain at most 25 evidence links.")
        item["evidence"].append({"url": url, "label": label[:100], "added_by": ctx.author.id, "added_at": self._now()})
        await self._save(ctx.guild, decisions, item)
        await ctx.send(embed=self._embed(item))

    @decision.command(name="export")
    @commands.admin_or_permissions(manage_guild=True)
    async def export(self, ctx: commands.Context) -> None:
        """Export the decision register as CSV."""
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(
            [
                "decision_id",
                "title",
                "status",
                "created_by",
                "approved_by",
                "owner_id",
                "due_at",
                "created_at",
                "updated_at",
                "outcome",
            ]
        )
        for item in (await self.config.guild(ctx.guild).decisions()).values():
            writer.writerow(
                [
                    item.get(key)
                    for key in (
                        "decision_id",
                        "title",
                        "status",
                        "created_by",
                        "approved_by",
                        "owner_id",
                        "due_at",
                        "created_at",
                        "updated_at",
                        "outcome",
                    )
                ]
            )
        await ctx.send(file=discord.File(io.BytesIO(output.getvalue().encode()), filename="decision-ledger.csv"))
