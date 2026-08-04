"""Auditable periodic access certification for Discord roles."""

from __future__ import annotations

import csv
import io
import time
from contextlib import suppress
from typing import TYPE_CHECKING, Any

import discord
from redbot.core import Config, commands

from .dashboard_integration import DashboardIntegration

if TYPE_CHECKING:
    from redbot.core.bot import Red


class AccessReview(DashboardIntegration, commands.Cog):
    """Prove who reviewed sensitive access and apply removals separately."""

    CONFIG_IDENTIFIER = 2026080308
    COLOR = 0x2C3E50

    def __init__(self, bot: Red) -> None:
        self.bot = bot
        self.config = Config.get_conf(self, identifier=self.CONFIG_IDENTIFIER, force_registration=True)
        self.config.register_guild(
            reviewer_role_id=None,
            log_channel_id=None,
            next_campaign_id=1,
            campaigns={},
        )

    @staticmethod
    def _now() -> int:
        return int(time.time())

    async def _can_review(self, member: discord.Member) -> bool:
        if member.id in getattr(self.bot, "owner_ids", set()) or member.guild_permissions.manage_roles:
            return True
        role_id = await self.config.guild(member.guild).reviewer_role_id()
        return bool(role_id and member.get_role(role_id))

    async def _campaign(self, guild: discord.Guild, campaign_id: int) -> tuple[dict[str, Any], dict[str, Any]]:
        campaigns = await self.config.guild(guild).campaigns()
        campaign = campaigns.get(str(campaign_id))
        if not campaign:
            raise commands.BadArgument("Campaign not found.")
        return campaigns, campaign

    async def _save(self, guild: discord.Guild, campaigns: dict[str, Any], campaign: dict[str, Any]) -> None:
        campaign["updated_at"] = self._now()
        campaigns[str(campaign["campaign_id"])] = campaign
        await self.config.guild(guild).campaigns.set(campaigns)

    async def _log(self, guild: discord.Guild, text: str) -> None:
        channel_id = await self.config.guild(guild).log_channel_id()
        channel = guild.get_channel(channel_id) if channel_id else None
        if isinstance(channel, discord.TextChannel):
            with suppress(discord.HTTPException):
                await channel.send(embed=discord.Embed(description=text, color=self.COLOR, timestamp=discord.utils.utcnow()))

    async def red_delete_data_for_user(self, *, requester: str, user_id: int) -> None:
        key = str(user_id)
        for guild_id in await self.config.all_guilds():
            conf = self.config.guild_from_id(guild_id)
            campaigns = await conf.campaigns()
            changed = False
            for campaign in campaigns.values():
                if campaign.get("entries", {}).pop(key, None):
                    changed = True
                for entry in campaign.get("entries", {}).values():
                    if entry.get("reviewer_id") == user_id:
                        entry["reviewer_id"] = None
                        changed = True
                if campaign.get("created_by") == user_id:
                    campaign["created_by"] = None
                    changed = True
                if campaign.get("enforced_by") == user_id:
                    campaign["enforced_by"] = None
                    changed = True
            if changed:
                await conf.campaigns.set(campaigns)

    @commands.hybrid_group(name="accessreview", aliases=["accesscert"], invoke_without_command=True)
    @commands.guild_only()
    async def access_review(self, ctx: commands.Context) -> None:
        """Run periodic role-access certification campaigns."""
        await ctx.send_help()

    @access_review.command(name="reviewerrole")
    @commands.admin_or_permissions(manage_roles=True)
    async def reviewer_role(self, ctx: commands.Context, role: discord.Role | None = None) -> None:
        """Set the role allowed to submit review decisions."""
        await self.config.guild(ctx.guild).reviewer_role_id.set(role.id if role else None)
        await ctx.send(f"Reviewer role set to {role.mention}." if role else "Reviewer role cleared.")

    @access_review.command(name="logchannel")
    @commands.admin_or_permissions(manage_guild=True)
    async def log_channel(self, ctx: commands.Context, channel: discord.TextChannel | None = None) -> None:
        """Set the evidence log channel."""
        await self.config.guild(ctx.guild).log_channel_id.set(channel.id if channel else None)
        await ctx.send(f"Access review logs will go to {channel.mention}." if channel else "Access review logs disabled.")

    @access_review.command(name="create")
    @commands.admin_or_permissions(manage_roles=True)
    async def create(
        self, ctx: commands.Context, name: str, role: discord.Role, deadline_days: commands.Range[int, 1, 365] = 14
    ) -> None:
        """Create a campaign by snapshotting everyone with a sensitive role."""
        if role.is_default() or role.managed:
            raise commands.BadArgument("Choose a normal assignable role.")
        conf = self.config.guild(ctx.guild)
        campaign_id = await conf.next_campaign_id()
        now = self._now()
        entries = {
            str(member.id): {
                "user_id": member.id,
                "role_ids": [role.id],
                "decision": "pending",
                "reviewer_id": None,
                "reviewed_at": None,
                "note": "",
                "enforced_at": None,
                "enforcement_error": None,
            }
            for member in role.members
        }
        campaign = {
            "campaign_id": campaign_id,
            "name": name[:100],
            "role_ids": [role.id],
            "status": "open",
            "created_by": ctx.author.id,
            "created_at": now,
            "updated_at": now,
            "deadline_at": now + int(deadline_days) * 86400,
            "entries": entries,
            "enforced_by": None,
            "enforced_at": None,
        }
        async with conf.campaigns() as campaigns:
            campaigns[str(campaign_id)] = campaign
        await conf.next_campaign_id.set(campaign_id + 1)
        await self._log(
            ctx.guild, f"📋 **Access review #{campaign_id}** created for {role.mention} with {len(entries)} member(s)."
        )
        await ctx.send(f"Created campaign **#{campaign_id} {name}** with **{len(entries)}** access record(s).")

    @access_review.command(name="addrole")
    @commands.admin_or_permissions(manage_roles=True)
    async def add_role(self, ctx: commands.Context, campaign_id: int, role: discord.Role) -> None:
        """Add another role and snapshot its current members into an open campaign."""
        campaigns, campaign = await self._campaign(ctx.guild, campaign_id)
        if campaign["status"] != "open":
            raise commands.BadArgument("Only open campaigns can be expanded.")
        if role.id not in campaign["role_ids"]:
            campaign["role_ids"].append(role.id)
        for member in role.members:
            entry = campaign["entries"].setdefault(
                str(member.id),
                {
                    "user_id": member.id,
                    "role_ids": [],
                    "decision": "pending",
                    "reviewer_id": None,
                    "reviewed_at": None,
                    "note": "",
                    "enforced_at": None,
                    "enforcement_error": None,
                },
            )
            if role.id not in entry["role_ids"]:
                entry["role_ids"].append(role.id)
        await self._save(ctx.guild, campaigns, campaign)
        await ctx.send(f"Added {role.mention}; campaign now covers **{len(campaign['entries'])}** member(s).")

    @access_review.command(name="decide")
    async def decide(
        self, ctx: commands.Context, campaign_id: int, member: discord.Member, decision: str, *, note: str = ""
    ) -> None:
        """Mark a snapshotted member keep or remove. This does not alter roles yet."""
        if not await self._can_review(ctx.author):
            raise commands.CheckFailure("You are not an access reviewer.")
        decision = decision.casefold()
        if decision not in {"keep", "remove"}:
            raise commands.BadArgument("Decision must be keep or remove.")
        campaigns, campaign = await self._campaign(ctx.guild, campaign_id)
        if campaign["status"] != "open":
            raise commands.BadArgument("That campaign is no longer open.")
        entry = campaign["entries"].get(str(member.id))
        if not entry:
            raise commands.BadArgument("That member was not in this campaign snapshot.")
        entry.update(decision=decision, reviewer_id=ctx.author.id, reviewed_at=self._now(), note=note[:500])
        await self._save(ctx.guild, campaigns, campaign)
        await self._log(
            ctx.guild, f"Access review **#{campaign_id}**: {ctx.author.mention} marked {member.mention} **{decision}**."
        )
        await ctx.send(f"Recorded **{decision}** for {member.mention}. No roles were changed.")

    @access_review.command(name="queue")
    async def queue(self, ctx: commands.Context, campaign_id: int, decision: str = "pending") -> None:
        """List campaign entries by decision."""
        _campaigns, campaign = await self._campaign(ctx.guild, campaign_id)
        rows = [entry for entry in campaign["entries"].values() if entry.get("decision") == decision]
        lines = [
            f"• <@{entry['user_id']}> · roles " + ", ".join(f"<@&{role_id}>" for role_id in entry["role_ids"])
            for entry in rows[:50]
            if entry.get("user_id")
        ]
        await ctx.send(
            embed=discord.Embed(
                title=f"Campaign #{campaign_id} · {decision}", description="\n".join(lines) or "No entries.", color=self.COLOR
            )
        )

    @access_review.command(name="show")
    async def show(self, ctx: commands.Context, campaign_id: int) -> None:
        """Show campaign completion and enforcement status."""
        _campaigns, campaign = await self._campaign(ctx.guild, campaign_id)
        counts = {"pending": 0, "keep": 0, "remove": 0}
        for entry in campaign["entries"].values():
            counts[entry.get("decision", "pending")] += 1
        total = len(campaign["entries"])
        embed = discord.Embed(title=f"Access Review #{campaign_id} · {campaign['name']}", color=self.COLOR)
        embed.add_field(name="Status", value=campaign["status"].title())
        embed.add_field(name="Deadline", value=f"<t:{campaign['deadline_at']}:R>")
        embed.add_field(name="Completion", value=f"{total - counts['pending']}/{total}")
        embed.add_field(name="Keep", value=str(counts["keep"]))
        embed.add_field(name="Remove", value=str(counts["remove"]))
        embed.add_field(name="Pending", value=str(counts["pending"]))
        embed.add_field(name="Roles", value=", ".join(f"<@&{role_id}>" for role_id in campaign["role_ids"]), inline=False)
        await ctx.send(embed=embed)

    @access_review.command(name="enforce")
    @commands.admin_or_permissions(manage_roles=True)
    async def enforce(self, ctx: commands.Context, campaign_id: int, confirmation: str) -> None:
        """Apply reviewed removals. Confirmation must be `REMOVE` exactly."""
        if confirmation != "REMOVE":
            raise commands.BadArgument("Re-run with the exact confirmation word `REMOVE`.")
        campaigns, campaign = await self._campaign(ctx.guild, campaign_id)
        removed = errors = 0
        for entry in campaign["entries"].values():
            if entry.get("decision") != "remove" or entry.get("enforced_at"):
                continue
            member = ctx.guild.get_member(entry.get("user_id")) if entry.get("user_id") else None
            if not member:
                entry["enforcement_error"] = "Member not present"
                errors += 1
                continue
            roles = [ctx.guild.get_role(role_id) for role_id in entry["role_ids"]]
            manageable = [
                role for role in roles if role and not role.managed and role < ctx.guild.me.top_role and role in member.roles
            ]
            try:
                if manageable:
                    await member.remove_roles(*manageable, reason=f"AccessReview campaign #{campaign_id}")
                entry["enforced_at"] = self._now()
                entry["enforcement_error"] = None
                removed += len(manageable)
            except discord.HTTPException as exc:
                entry["enforcement_error"] = str(exc)[:300]
                errors += 1
        campaign["enforced_by"] = ctx.author.id
        campaign["enforced_at"] = self._now()
        campaign["status"] = "enforced" if errors == 0 else "enforced-with-errors"
        await self._save(ctx.guild, campaigns, campaign)
        await self._log(
            ctx.guild,
            f"🔐 Access review **#{campaign_id}** enforced by {ctx.author.mention}: "
            f"{removed} role removal(s), {errors} error(s).",
        )
        await ctx.send(f"Enforcement complete: **{removed}** role removal(s), **{errors}** error(s).")

    @access_review.command(name="close")
    @commands.admin_or_permissions(manage_roles=True)
    async def close(self, ctx: commands.Context, campaign_id: int, force: bool = False) -> None:
        """Close decisions without enforcing. Pending entries require `force=true`."""
        campaigns, campaign = await self._campaign(ctx.guild, campaign_id)
        pending = sum(entry.get("decision") == "pending" for entry in campaign["entries"].values())
        if pending and not force:
            raise commands.BadArgument(f"{pending} decision(s) are still pending. Pass `true` to force close.")
        campaign["status"] = "closed"
        await self._save(ctx.guild, campaigns, campaign)
        await ctx.send(f"Campaign **#{campaign_id}** closed without changing roles.")

    @access_review.command(name="list")
    async def list_campaigns(self, ctx: commands.Context) -> None:
        """List recent access review campaigns."""
        campaigns = await self.config.guild(ctx.guild).campaigns()
        rows = sorted(campaigns.values(), key=lambda item: item["campaign_id"], reverse=True)
        lines = [
            f"• **#{item['campaign_id']} {item['name']}** · {item['status']} · {len(item['entries'])} entries"
            for item in rows[:25]
        ]
        await ctx.send(
            embed=discord.Embed(title="Access Reviews", description="\n".join(lines) or "No campaigns.", color=self.COLOR)
        )

    @access_review.command(name="export")
    @commands.admin_or_permissions(manage_guild=True)
    async def export(self, ctx: commands.Context, campaign_id: int) -> None:
        """Export campaign evidence as CSV."""
        _campaigns, campaign = await self._campaign(ctx.guild, campaign_id)
        output = io.StringIO()
        fields = [
            "campaign_id",
            "campaign_name",
            "user_id",
            "role_ids",
            "decision",
            "reviewer_id",
            "reviewed_at",
            "note",
            "enforced_at",
            "enforcement_error",
        ]
        writer = csv.DictWriter(output, fieldnames=fields)
        writer.writeheader()
        for entry in campaign["entries"].values():
            writer.writerow(
                {
                    "campaign_id": campaign_id,
                    "campaign_name": campaign["name"],
                    "user_id": entry.get("user_id"),
                    "role_ids": "|".join(str(role_id) for role_id in entry["role_ids"]),
                    "decision": entry["decision"],
                    "reviewer_id": entry.get("reviewer_id"),
                    "reviewed_at": entry.get("reviewed_at"),
                    "note": entry.get("note"),
                    "enforced_at": entry.get("enforced_at"),
                    "enforcement_error": entry.get("enforcement_error"),
                },
            )
        await ctx.send(file=discord.File(io.BytesIO(output.getvalue().encode()), filename=f"access-review-{campaign_id}.csv"))
