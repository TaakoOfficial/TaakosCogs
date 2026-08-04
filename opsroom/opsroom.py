"""Discord-native incident response and postmortem workflows."""

from __future__ import annotations

import io
import re
import time
from contextlib import suppress
from typing import TYPE_CHECKING, Any, ClassVar

import discord
from redbot.core import Config, commands

from .dashboard_integration import DashboardIntegration

if TYPE_CHECKING:
    from redbot.core.bot import Red


SEVERITIES = {"sev1", "sev2", "sev3", "sev4"}
STATUSES = {"investigating", "identified", "monitoring", "resolved"}


class OpsRoom(DashboardIntegration, commands.Cog):
    """Run incidents with a clear owner, timeline, and durable follow-up."""

    CONFIG_IDENTIFIER = 2026080303
    COLORS: ClassVar[dict[str, int]] = {
        "sev1": 0xED4245,
        "sev2": 0xF47B20,
        "sev3": 0xFEE75C,
        "sev4": 0x5865F2,
    }

    def __init__(self, bot: Red) -> None:
        self.bot = bot
        self.config = Config.get_conf(self, identifier=self.CONFIG_IDENTIFIER, force_registration=True)
        self.config.register_guild(
            category_id=None,
            response_role_id=None,
            update_channel_id=None,
            archive_category_id=None,
            next_incident_id=1,
            incidents={},
        )

    @staticmethod
    def _now() -> int:
        return int(time.time())

    @staticmethod
    def _slug(value: str) -> str:
        clean = re.sub(r"[^a-z0-9]+", "-", value.casefold()).strip("-")
        return clean[:60] or "incident"

    async def _is_responder(self, member: discord.Member) -> bool:
        if member.id in getattr(self.bot, "owner_ids", set()) or member.guild_permissions.manage_channels:
            return True
        role_id = await self.config.guild(member.guild).response_role_id()
        return bool(role_id and member.get_role(role_id))

    async def _incident_from_channel(self, channel: discord.abc.GuildChannel) -> tuple[dict[str, Any], dict[str, Any]]:
        incidents = await self.config.guild(channel.guild).incidents()
        record = next((item for item in incidents.values() if item.get("channel_id") == channel.id), None)
        if not record:
            raise commands.BadArgument("Run this command in an OpsRoom incident channel.")
        return incidents, record

    async def _save(self, guild: discord.Guild, incidents: dict[str, Any], record: dict[str, Any]) -> None:
        incidents[str(record["incident_id"])] = record
        await self.config.guild(guild).incidents.set(incidents)

    async def _timeline(
        self, guild: discord.Guild, incidents: dict[str, Any], record: dict[str, Any], kind: str, actor_id: int, text: str
    ) -> None:
        record.setdefault("timeline", []).append(
            {"at": self._now(), "kind": kind, "actor_id": actor_id, "text": text[:1500]},
        )
        record["updated_at"] = self._now()
        await self._save(guild, incidents, record)

    def _embed(self, record: dict[str, Any]) -> discord.Embed:
        embed = discord.Embed(
            title=f"INC-{record['incident_id']:04d} · {record['title']}",
            description=record.get("summary") or "No summary has been posted.",
            color=self.COLORS.get(record.get("severity"), 0x5865F2),
        )
        embed.add_field(name="Severity", value=record.get("severity", "unknown").upper())
        embed.add_field(name="Status", value=record.get("status", "unknown").title())
        commander = record.get("commander_id")
        embed.add_field(name="Commander", value=f"<@{commander}>" if commander else "Unassigned")
        embed.add_field(name="Opened", value=f"<t:{record['created_at']}:F>", inline=False)
        return embed

    async def _publish_update(self, guild: discord.Guild, record: dict[str, Any], text: str) -> None:
        channel_id = await self.config.guild(guild).update_channel_id()
        channel = guild.get_channel(channel_id) if channel_id else None
        if isinstance(channel, discord.TextChannel):
            embed = self._embed(record)
            embed.description = text
            try:
                message = await channel.send(embed=embed)
            except discord.HTTPException:
                return
            record.setdefault("update_message_ids", []).append(message.id)

    async def red_delete_data_for_user(self, *, requester: str, user_id: int) -> None:
        for guild_id in await self.config.all_guilds():
            conf = self.config.guild_from_id(guild_id)
            incidents = await conf.incidents()
            changed = False
            for record in incidents.values():
                if record.get("created_by") == user_id:
                    record["created_by"] = None
                    changed = True
                if record.get("commander_id") == user_id:
                    record["commander_id"] = None
                    changed = True
                for entry in record.get("timeline", []):
                    if entry.get("actor_id") == user_id:
                        entry["actor_id"] = None
                        changed = True
                for action in record.get("actions", []):
                    if action.get("owner_id") == user_id:
                        action["owner_id"] = None
                        changed = True
                    if action.get("created_by") == user_id:
                        action["created_by"] = None
                        changed = True
            if changed:
                await conf.incidents.set(incidents)

    @commands.hybrid_group(name="opsroom", aliases=["incident"], invoke_without_command=True)
    @commands.guild_only()
    async def opsroom(self, ctx: commands.Context) -> None:
        """Create and coordinate operational incidents."""
        await ctx.send_help()

    @opsroom.command(name="category")
    @commands.admin_or_permissions(manage_guild=True)
    async def category(self, ctx: commands.Context, category: discord.CategoryChannel | None = None) -> None:
        """Set the category where incident channels are created."""
        await self.config.guild(ctx.guild).category_id.set(category.id if category else None)
        await ctx.send(f"Incident category set to **{category.name}**." if category else "Incident category cleared.")

    @opsroom.command(name="archivecategory")
    @commands.admin_or_permissions(manage_guild=True)
    async def archive_category(self, ctx: commands.Context, category: discord.CategoryChannel | None = None) -> None:
        """Set the category where resolved incident channels are moved."""
        await self.config.guild(ctx.guild).archive_category_id.set(category.id if category else None)
        await ctx.send(f"Archive category set to **{category.name}**." if category else "Archive category cleared.")

    @opsroom.command(name="responserole")
    @commands.admin_or_permissions(manage_guild=True)
    async def response_role(self, ctx: commands.Context, role: discord.Role | None = None) -> None:
        """Set the role allowed to manage incidents."""
        await self.config.guild(ctx.guild).response_role_id.set(role.id if role else None)
        await ctx.send(f"Response role set to {role.mention}." if role else "Response role cleared.")

    @opsroom.command(name="updatechannel")
    @commands.admin_or_permissions(manage_guild=True)
    async def update_channel(self, ctx: commands.Context, channel: discord.TextChannel | None = None) -> None:
        """Set the public or stakeholder incident update channel."""
        await self.config.guild(ctx.guild).update_channel_id.set(channel.id if channel else None)
        await ctx.send(f"Updates will be published in {channel.mention}." if channel else "Automatic update publishing disabled.")

    @opsroom.command(name="create")
    async def create(self, ctx: commands.Context, severity: str, *, title: str) -> None:
        """Create an incident channel: `[p]opsroom create sev2 API unavailable`."""
        if not isinstance(ctx.author, discord.Member) or not await self._is_responder(ctx.author):
            raise commands.CheckFailure("Only configured responders can create incidents.")
        severity = severity.casefold()
        if severity not in SEVERITIES:
            raise commands.BadArgument("Severity must be sev1, sev2, sev3, or sev4.")
        conf = self.config.guild(ctx.guild)
        incident_id = await conf.next_incident_id()
        category_id = await conf.category_id()
        category = ctx.guild.get_channel(category_id) if category_id else None
        role_id = await conf.response_role_id()
        role = ctx.guild.get_role(role_id) if role_id else None
        overwrites = None
        if role:
            overwrites = {
                ctx.guild.default_role: discord.PermissionOverwrite(view_channel=False),
                role: discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True),
                ctx.guild.me: discord.PermissionOverwrite(view_channel=True, send_messages=True, manage_channels=True),
            }
        channel = await ctx.guild.create_text_channel(
            f"inc-{incident_id:04d}-{self._slug(title)}",
            category=category if isinstance(category, discord.CategoryChannel) else None,
            overwrites=overwrites,
            reason=f"OpsRoom incident created by {ctx.author}",
            topic=f"INC-{incident_id:04d} | {severity.upper()} | investigating | {title[:200]}",
        )
        now = self._now()
        record = {
            "incident_id": incident_id,
            "title": title[:200],
            "severity": severity,
            "status": "investigating",
            "summary": "",
            "channel_id": channel.id,
            "created_by": ctx.author.id,
            "commander_id": ctx.author.id,
            "created_at": now,
            "updated_at": now,
            "resolved_at": None,
            "timeline": [{"at": now, "kind": "opened", "actor_id": ctx.author.id, "text": title[:1500]}],
            "actions": [],
            "update_message_ids": [],
        }
        async with conf.incidents() as incidents:
            incidents[str(incident_id)] = record
        await conf.next_incident_id.set(incident_id + 1)
        await channel.send(content=role.mention if role else None, embed=self._embed(record))
        await ctx.send(f"Created {channel.mention} for **INC-{incident_id:04d}**.")

    @opsroom.command(name="show")
    async def show(self, ctx: commands.Context, incident_id: int | None = None) -> None:
        """Show an incident by ID, or the current channel's incident."""
        incidents = await self.config.guild(ctx.guild).incidents()
        record = (
            incidents.get(str(incident_id))
            if incident_id
            else next(
                (item for item in incidents.values() if item.get("channel_id") == ctx.channel.id),
                None,
            )
        )
        if not record:
            raise commands.BadArgument("Incident not found.")
        await ctx.send(embed=self._embed(record))

    @opsroom.command(name="commander")
    async def commander(self, ctx: commands.Context, member: discord.Member) -> None:
        """Assign the incident commander in the current incident channel."""
        if not await self._is_responder(ctx.author):
            raise commands.CheckFailure("Only responders can assign a commander.")
        incidents, record = await self._incident_from_channel(ctx.channel)
        record["commander_id"] = member.id
        await self._timeline(ctx.guild, incidents, record, "commander", ctx.author.id, f"Commander assigned to {member}.")
        await ctx.send(f"Incident commander: {member.mention}.")

    @opsroom.command(name="note")
    async def note(self, ctx: commands.Context, *, note: str) -> None:
        """Append a timestamped internal timeline note."""
        if not await self._is_responder(ctx.author):
            raise commands.CheckFailure("Only responders can add timeline notes.")
        incidents, record = await self._incident_from_channel(ctx.channel)
        await self._timeline(ctx.guild, incidents, record, "note", ctx.author.id, note)
        await ctx.message.add_reaction("✅")

    @opsroom.command(name="status")
    async def status(self, ctx: commands.Context, status: str, *, summary: str = "") -> None:
        """Change status and optionally publish a stakeholder update."""
        if not await self._is_responder(ctx.author):
            raise commands.CheckFailure("Only responders can change incident status.")
        status = status.casefold()
        if status not in STATUSES:
            raise commands.BadArgument("Status must be investigating, identified, monitoring, or resolved.")
        incidents, record = await self._incident_from_channel(ctx.channel)
        record["status"] = status
        if summary:
            record["summary"] = summary[:1500]
        if status == "resolved":
            record["resolved_at"] = self._now()
        await self._timeline(ctx.guild, incidents, record, "status", ctx.author.id, summary or status)
        if summary:
            await self._publish_update(ctx.guild, record, summary)
            await self._save(ctx.guild, incidents, record)
        with suppress(discord.HTTPException):
            await ctx.channel.edit(
                topic=f"INC-{record['incident_id']:04d} | {record['severity'].upper()} | {status} | {record['title']}"
            )
        await ctx.send(embed=self._embed(record))

    @opsroom.command(name="action")
    async def action(self, ctx: commands.Context, owner: discord.Member | None = None, *, task: str) -> None:
        """Add a post-incident action item."""
        if not await self._is_responder(ctx.author):
            raise commands.CheckFailure("Only responders can add actions.")
        incidents, record = await self._incident_from_channel(ctx.channel)
        action_id = len(record.setdefault("actions", [])) + 1
        record["actions"].append(
            {
                "action_id": action_id,
                "task": task[:1000],
                "owner_id": owner.id if owner else None,
                "created_by": ctx.author.id,
                "created_at": self._now(),
                "completed_at": None,
            },
        )
        await self._timeline(ctx.guild, incidents, record, "action", ctx.author.id, task)
        await ctx.send(f"Action **#{action_id}** added" + (f" for {owner.mention}." if owner else "."))

    @opsroom.command(name="complete")
    async def complete(self, ctx: commands.Context, action_id: int) -> None:
        """Complete an incident action item."""
        if not await self._is_responder(ctx.author):
            raise commands.CheckFailure("Only responders can complete actions.")
        incidents, record = await self._incident_from_channel(ctx.channel)
        action = next((item for item in record.get("actions", []) if item["action_id"] == action_id), None)
        if not action:
            raise commands.BadArgument("Action item not found.")
        action["completed_at"] = self._now()
        await self._timeline(ctx.guild, incidents, record, "action-complete", ctx.author.id, action["task"])
        await ctx.send(f"Action **#{action_id}** completed.")

    @opsroom.command(name="archive")
    async def archive(self, ctx: commands.Context) -> None:
        """Lock and move a resolved incident channel into the archive category."""
        if not await self._is_responder(ctx.author):
            raise commands.CheckFailure("Only responders can archive incidents.")
        _incidents, record = await self._incident_from_channel(ctx.channel)
        if record.get("status") != "resolved":
            raise commands.BadArgument("Resolve the incident before archiving it.")
        category_id = await self.config.guild(ctx.guild).archive_category_id()
        category = ctx.guild.get_channel(category_id) if category_id else None
        overwrites = ctx.channel.overwrites_for(ctx.guild.default_role)
        overwrites.send_messages = False
        await ctx.channel.set_permissions(ctx.guild.default_role, overwrite=overwrites, reason="OpsRoom incident archived")
        if isinstance(category, discord.CategoryChannel):
            await ctx.channel.edit(category=category, sync_permissions=False)
        await ctx.send("Incident archived. This channel is now read-only for the default role.")

    @opsroom.command(name="postmortem")
    async def postmortem(self, ctx: commands.Context, incident_id: int | None = None) -> None:
        """Generate a Markdown incident postmortem."""
        incidents = await self.config.guild(ctx.guild).incidents()
        record = (
            incidents.get(str(incident_id))
            if incident_id
            else next(
                (item for item in incidents.values() if item.get("channel_id") == ctx.channel.id),
                None,
            )
        )
        if not record:
            raise commands.BadArgument("Incident not found.")
        lines = [
            f"# INC-{record['incident_id']:04d}: {record['title']}",
            "",
            f"- Severity: {record['severity'].upper()}",
            f"- Status: {record['status']}",
            f"- Opened: <t:{record['created_at']}:F>",
            f"- Resolved timestamp: {record.get('resolved_at') or 'Not resolved'}",
            f"- Commander ID: {record.get('commander_id') or 'Unassigned'}",
            "",
            "## Summary",
            record.get("summary") or "Not written.",
            "",
            "## Timeline",
        ]
        for entry in record.get("timeline", []):
            lines.append(f"- {entry['at']} [{entry['kind']}] actor={entry.get('actor_id') or 'deleted'} — {entry['text']}")
        lines.extend(["", "## Follow-up actions"])
        for action in record.get("actions", []):
            mark = "x" if action.get("completed_at") else " "
            lines.append(f"- [{mark}] {action['task']} (owner={action.get('owner_id') or 'unassigned'})")
        payload = "\n".join(lines).encode()
        await ctx.send(file=discord.File(io.BytesIO(payload), filename=f"INC-{record['incident_id']:04d}-postmortem.md"))

    @opsroom.command(name="list")
    async def list_incidents(self, ctx: commands.Context, status: str = "active") -> None:
        """List active, resolved, or all incidents."""
        incidents = await self.config.guild(ctx.guild).incidents()
        rows = []
        for record in sorted(incidents.values(), key=lambda item: item["incident_id"], reverse=True):
            if status == "active" and record.get("status") == "resolved":
                continue
            if status == "resolved" and record.get("status") != "resolved":
                continue
            rows.append(
                f"• **INC-{record['incident_id']:04d}** {record['severity'].upper()} · "
                f"{record['status']} · <#{record['channel_id']}> — {record['title']}",
            )
        await ctx.send(
            embed=discord.Embed(title="OpsRoom Incidents", description="\n".join(rows[:25]) or "No incidents.", color=0x5865F2)
        )
