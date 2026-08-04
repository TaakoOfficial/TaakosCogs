"""Provider-neutral subscription ledger and Discord role reconciliation."""

from __future__ import annotations

import csv
import io
import time
from contextlib import suppress
from typing import TYPE_CHECKING

import discord
from discord.ext import tasks
from redbot.core import Config, commands

from .dashboard_integration import DashboardIntegration

if TYPE_CHECKING:
    from redbot.core.bot import Red


class SponsorSync(DashboardIntegration, commands.Cog):
    """Map any membership source to audited, expiring Discord roles."""

    CONFIG_IDENTIFIER = 2026080306
    COLOR = 0xF96854

    def __init__(self, bot: Red) -> None:
        self.bot = bot
        self.config = Config.get_conf(self, identifier=self.CONFIG_IDENTIFIER, force_registration=True)
        self.config.register_guild(
            tiers={},
            subscribers={},
            grace_days=3,
            alert_channel_id=None,
            last_sync_at=0,
            sync_count=0,
        )

    async def cog_load(self) -> None:
        self.sync_loop.start()

    def cog_unload(self) -> None:
        self.sync_loop.cancel()

    @staticmethod
    def _now() -> int:
        return int(time.time())

    @staticmethod
    def _tier_key(name: str) -> str:
        key = "-".join(name.casefold().split())
        if not key or len(key) > 50:
            raise commands.BadArgument("Tier names must contain 1–50 useful characters.")
        return key

    async def _alert(self, guild: discord.Guild, text: str, color: int | None = None) -> None:
        channel_id = await self.config.guild(guild).alert_channel_id()
        channel = guild.get_channel(channel_id) if channel_id else None
        if isinstance(channel, discord.TextChannel):
            with suppress(discord.HTTPException):
                await channel.send(
                    embed=discord.Embed(description=text, color=color or self.COLOR, timestamp=discord.utils.utcnow())
                )

    async def _reconcile(self, guild: discord.Guild) -> tuple[int, int, int]:
        conf = self.config.guild(guild)
        data = await conf.all()
        now = self._now()
        grace_seconds = int(data["grace_days"]) * 86400
        added = removed = errors = 0
        for user_key, record in data["subscribers"].items():
            try:
                user_id = int(user_key)
            except ValueError:
                continue
            member = guild.get_member(user_id)
            tier = data["tiers"].get(record.get("tier"))
            if not member or not tier:
                continue
            role = guild.get_role(tier["role_id"])
            if not role or role.managed or role >= guild.me.top_role:
                errors += 1
                continue
            expires_at = record.get("expires_at")
            active = record.get("status") == "active" and (expires_at is None or now <= int(expires_at) + grace_seconds)
            desired_role_id = role.id if active else None
            obsolete_roles = []
            for configured_tier in data["tiers"].values():
                configured_role = guild.get_role(configured_tier["role_id"])
                if (
                    configured_role
                    and configured_role.id != desired_role_id
                    and configured_role in member.roles
                    and not configured_role.managed
                    and configured_role < guild.me.top_role
                ):
                    obsolete_roles.append(configured_role)
            try:
                if obsolete_roles:
                    await member.remove_roles(*obsolete_roles, reason="SponsorSync obsolete membership tier")
                    removed += len(obsolete_roles)
                if active and role not in member.roles:
                    await member.add_roles(role, reason="SponsorSync active membership")
                    added += 1
                    record["last_role_change_at"] = now
                    await self._alert(
                        guild, f"✅ Added {role.mention} to {member.mention} for tier **{record['tier']}**.", 0x57F287
                    )
                elif not active and role in member.roles:
                    await member.remove_roles(role, reason="SponsorSync membership expired or revoked")
                    removed += 1
                    record["last_role_change_at"] = now
                    await self._alert(
                        guild, f"➖ Removed {role.mention} from {member.mention}; membership is inactive.", 0xED4245
                    )
            except discord.HTTPException:
                errors += 1
        await conf.subscribers.set(data["subscribers"])
        await conf.last_sync_at.set(now)
        await conf.sync_count.set(int(data["sync_count"]) + 1)
        return added, removed, errors

    async def red_delete_data_for_user(self, *, requester: str, user_id: int) -> None:
        for guild_id in await self.config.all_guilds():
            conf = self.config.guild_from_id(guild_id)
            async with conf.subscribers() as subscribers:
                subscribers.pop(str(user_id), None)

    @tasks.loop(hours=1)
    async def sync_loop(self) -> None:
        for guild in self.bot.guilds:
            with suppress(discord.HTTPException, RuntimeError):
                await self._reconcile(guild)

    @sync_loop.before_loop
    async def before_sync_loop(self) -> None:
        await self.bot.wait_until_red_ready()

    @commands.hybrid_group(name="sponsorsync", aliases=["sponsor"], invoke_without_command=True)
    @commands.guild_only()
    async def sponsor_sync(self, ctx: commands.Context) -> None:
        """Manage sponsor tiers and reconcile membership roles."""
        await ctx.send_help()

    @sponsor_sync.group(name="tier", invoke_without_command=True)
    @commands.admin_or_permissions(manage_roles=True)
    async def tier(self, ctx: commands.Context) -> None:
        """Manage sponsor tier-to-role mappings."""
        tiers = await self.config.guild(ctx.guild).tiers()
        lines = [f"• **{key}** → <@&{record['role_id']}>" for key, record in tiers.items()]
        await ctx.send("\n".join(lines) or "No tiers configured.")

    @tier.command(name="add")
    async def tier_add(self, ctx: commands.Context, name: str, role: discord.Role) -> None:
        """Map a provider-neutral tier name to a Discord role."""
        if role.managed or role >= ctx.guild.me.top_role:
            raise commands.BadArgument("Choose a role the bot can manage.")
        key = self._tier_key(name)
        async with self.config.guild(ctx.guild).tiers() as tiers:
            tiers[key] = {"name": name[:50], "role_id": role.id, "created_at": self._now()}
        await ctx.send(f"Tier **{key}** mapped to {role.mention}.")

    @tier.command(name="remove")
    async def tier_remove(self, ctx: commands.Context, name: str) -> None:
        """Remove a tier mapping without deleting subscriber records."""
        key = self._tier_key(name)
        async with self.config.guild(ctx.guild).tiers() as tiers:
            removed = tiers.pop(key, None)
        if not removed:
            raise commands.BadArgument("Tier not found.")
        await ctx.send(f"Tier **{key}** removed.")

    @sponsor_sync.command(name="grant")
    @commands.admin_or_permissions(manage_roles=True)
    async def grant(
        self,
        ctx: commands.Context,
        member: discord.Member,
        tier: str,
        days: commands.Range[int, 0, 3650] = 30,
        provider: str = "manual",
        *,
        reference: str = "",
    ) -> None:
        """Grant or replace a membership. Use 0 days for no expiration."""
        key = self._tier_key(tier)
        tiers = await self.config.guild(ctx.guild).tiers()
        if key not in tiers:
            raise commands.BadArgument("Configure that tier first.")
        now = self._now()
        expires_at = now + int(days) * 86400 if days else None
        record = {
            "user_id": member.id,
            "tier": key,
            "provider": provider[:50],
            "external_ref": reference[:200],
            "started_at": now,
            "expires_at": expires_at,
            "status": "active",
            "updated_at": now,
            "updated_by": ctx.author.id,
            "last_role_change_at": None,
        }
        async with self.config.guild(ctx.guild).subscribers() as subscribers:
            subscribers[str(member.id)] = record
        added, _removed, errors = await self._reconcile(ctx.guild)
        expiry = f"until <t:{expires_at}:F>" if expires_at else "without expiration"
        await ctx.send(f"Granted **{key}** to {member.mention} {expiry}. Role changes: {added}; errors: {errors}.")

    @sponsor_sync.command(name="renew")
    @commands.admin_or_permissions(manage_roles=True)
    async def renew(self, ctx: commands.Context, member: discord.Member, days: commands.Range[int, 1, 3650] = 30) -> None:
        """Extend a subscriber from their current expiration or from now."""
        async with self.config.guild(ctx.guild).subscribers() as subscribers:
            record = subscribers.get(str(member.id))
            if not record:
                raise commands.BadArgument("That member has no subscription record.")
            base = max(self._now(), int(record.get("expires_at") or 0))
            record["expires_at"] = base + int(days) * 86400
            record["status"] = "active"
            record["updated_at"] = self._now()
            record["updated_by"] = ctx.author.id
        await self._reconcile(ctx.guild)
        await ctx.send(f"Renewed {member.mention} through <t:{record['expires_at']}:F>.")

    @sponsor_sync.command(name="revoke")
    @commands.admin_or_permissions(manage_roles=True)
    async def revoke(self, ctx: commands.Context, member: discord.Member, *, reason: str = "") -> None:
        """Revoke a membership and reconcile its role."""
        async with self.config.guild(ctx.guild).subscribers() as subscribers:
            record = subscribers.get(str(member.id))
            if not record:
                raise commands.BadArgument("That member has no subscription record.")
            record.update(status="revoked", updated_at=self._now(), updated_by=ctx.author.id, revoke_reason=reason[:300])
        await self._reconcile(ctx.guild)
        await ctx.send(f"Revoked sponsor access for {member.mention}.")

    @sponsor_sync.command(name="status")
    async def status(self, ctx: commands.Context, member: discord.Member | None = None) -> None:
        """Show a member's sponsor status."""
        target = member or ctx.author
        record = (await self.config.guild(ctx.guild).subscribers()).get(str(target.id))
        if not record:
            await ctx.send(f"{target.mention} has no sponsor record.")
            return
        expiry = f"<t:{record['expires_at']}:F>" if record.get("expires_at") else "No expiration"
        embed = discord.Embed(title=f"Sponsor status · {target}", color=self.COLOR)
        embed.add_field(name="Tier", value=record["tier"])
        embed.add_field(name="Status", value=record["status"].title())
        embed.add_field(name="Provider", value=record.get("provider") or "manual")
        embed.add_field(name="Expiration", value=expiry, inline=False)
        await ctx.send(embed=embed)

    @sponsor_sync.command(name="grace")
    @commands.admin_or_permissions(manage_guild=True)
    async def grace(self, ctx: commands.Context, days: commands.Range[int, 0, 90]) -> None:
        """Set the post-expiration role grace period."""
        await self.config.guild(ctx.guild).grace_days.set(int(days))
        await ctx.send(f"Grace period set to **{days} day(s)**.")

    @sponsor_sync.command(name="alertchannel")
    @commands.admin_or_permissions(manage_guild=True)
    async def alert_channel(self, ctx: commands.Context, channel: discord.TextChannel | None = None) -> None:
        """Set the private role reconciliation audit channel."""
        await self.config.guild(ctx.guild).alert_channel_id.set(channel.id if channel else None)
        await ctx.send(f"SponsorSync alerts will go to {channel.mention}." if channel else "SponsorSync alerts disabled.")

    @sponsor_sync.command(name="sync")
    @commands.admin_or_permissions(manage_roles=True)
    async def sync(self, ctx: commands.Context) -> None:
        """Reconcile all subscriber records to Discord roles immediately."""
        added, removed, errors = await self._reconcile(ctx.guild)
        await ctx.send(f"Sync complete: **{added}** added, **{removed}** removed, **{errors}** error(s).")

    @sponsor_sync.command(name="expiring")
    @commands.admin_or_permissions(manage_roles=True)
    async def expiring(self, ctx: commands.Context, days: commands.Range[int, 1, 365] = 30) -> None:
        """List active memberships expiring within a number of days."""
        cutoff = self._now() + int(days) * 86400
        subscribers = await self.config.guild(ctx.guild).subscribers()
        rows = [
            f"• <@{record['user_id']}> · **{record['tier']}** · <t:{record['expires_at']}:R>"
            for record in subscribers.values()
            if record.get("status") == "active" and record.get("expires_at") and int(record["expires_at"]) <= cutoff
        ]
        await ctx.send(
            embed=discord.Embed(
                title=f"Expiring within {days} days", description="\n".join(rows[:25]) or "No memberships.", color=self.COLOR
            )
        )

    @sponsor_sync.command(name="importcsv")
    @commands.admin_or_permissions(manage_roles=True)
    async def import_csv(self, ctx: commands.Context) -> None:
        """Import attached CSV columns: user_id,tier,provider,external_ref,expires_at."""
        if not ctx.message.attachments:
            raise commands.BadArgument("Attach a UTF-8 CSV file.")
        payload = await ctx.message.attachments[0].read()
        reader = csv.DictReader(io.StringIO(payload.decode("utf-8-sig")))
        tiers = await self.config.guild(ctx.guild).tiers()
        imported = skipped = 0
        async with self.config.guild(ctx.guild).subscribers() as subscribers:
            for row in reader:
                try:
                    user_id = int(row.get("user_id", ""))
                    tier_key = self._tier_key(row.get("tier", ""))
                    expires_at = int(row["expires_at"]) if row.get("expires_at") else None
                except (ValueError, commands.BadArgument):
                    skipped += 1
                    continue
                if tier_key not in tiers:
                    skipped += 1
                    continue
                now = self._now()
                subscribers[str(user_id)] = {
                    "user_id": user_id,
                    "tier": tier_key,
                    "provider": (row.get("provider") or "csv")[:50],
                    "external_ref": (row.get("external_ref") or "")[:200],
                    "started_at": now,
                    "expires_at": expires_at,
                    "status": "active",
                    "updated_at": now,
                    "updated_by": ctx.author.id,
                    "last_role_change_at": None,
                }
                imported += 1
        await ctx.send(
            f"Imported **{imported}** subscriber(s); skipped **{skipped}** row(s). "
            f"Run `{ctx.clean_prefix}sponsorsync sync` to reconcile roles."
        )

    @sponsor_sync.command(name="export")
    @commands.admin_or_permissions(manage_guild=True)
    async def export(self, ctx: commands.Context) -> None:
        """Export the subscription ledger as CSV."""
        subscribers = await self.config.guild(ctx.guild).subscribers()
        output = io.StringIO()
        fields = ["user_id", "tier", "provider", "external_ref", "started_at", "expires_at", "status", "updated_at"]
        writer = csv.DictWriter(output, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(subscribers.values())
        await ctx.send(file=discord.File(io.BytesIO(output.getvalue().encode()), filename="sponsorsync.csv"))
