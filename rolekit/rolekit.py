"""Community role packs and lightweight activity leveling."""

from __future__ import annotations

import asyncio
import math
import random
import time
from typing import Any

import discord
from redbot.core import Config, commands

from .dashboard_integration import DashboardIntegration

__red_end_user_data_statement__ = (
    "This cog stores per-server message XP totals and message counts for members while "
    "leveling is enabled. It does not store message content."
)


class RoleKit(DashboardIntegration, commands.Cog):
    """Create useful community role packs and optional activity level rewards."""

    CONFIG_IDENTIFIER = 2026071501
    XP_PER_LEVEL_SQUARED = 100
    MAX_LEVEL = 500

    PRONOUN_ROLES = [
        "he/him",
        "she/her",
        "they/them",
        "any pronouns",
        "ask me",
        "xe/xem",
        "ze/zir",
    ]

    COMMON_PING_ROLES = [
        "Common Ping",
        "No Pings",
        "Ping on Important",
        "Ping for Events",
    ]

    ZODIAC_SIGNS = [
        "Aries",
        "Taurus",
        "Gemini",
        "Cancer",
        "Leo",
        "Virgo",
        "Libra",
        "Scorpio",
        "Sagittarius",
        "Capricorn",
        "Aquarius",
        "Pisces",
    ]

    COLOR_CHOICES = {
        "Red": "#FF0000",
        "Orange": "#FFA500",
        "Yellow": "#FFFF00",
        "Green": "#008000",
        "Blue": "#0000FF",
        "Purple": "#800080",
        "Pink": "#FFC0CB",
        "Black": "#000000",
        "White": "#FFFFFF",
        "Gray": "#808080",
        "Cyan": "#00FFFF",
        "Magenta": "#FF00FF",
        "Brown": "#A52A2A",
        "Teal": "#008080",
        "Lime": "#00FF00",
        "Navy": "#000080",
    }

    PLATFORM_ROLES = [
        "PC",
        "PlayStation",
        "Xbox",
        "Nintendo",
        "Mobile",
        "Tabletop",
    ]

    REGION_ROLES = [
        "North America",
        "South America",
        "Europe",
        "Africa",
        "Asia",
        "Oceania",
    ]

    INTEREST_ROLES = [
        "Gaming",
        "Roleplay",
        "Art",
        "Music",
        "Coding",
        "Movies & TV",
        "Books",
        "Sports",
    ]

    DEFAULT_LEVEL_ROLES = {
        5: 0x95A5A6,
        10: 0x2ECC71,
        20: 0x3498DB,
        30: 0x9B59B6,
        50: 0xF1C40F,
    }

    PACK_LABELS = {
        "zodiac": "Zodiac signs",
        "colors": "Display colors",
        "pronouns": "Pronouns",
        "pings": "Notification preferences",
        "platforms": "Gaming platforms",
        "regions": "World regions",
        "interests": "Community interests",
        "levels": "Activity level rewards",
    }

    PACK_ALIASES = {
        "color": "colors",
        "colour": "colors",
        "colours": "colors",
        "pronoun": "pronouns",
        "ping": "pings",
        "platform": "platforms",
        "region": "regions",
        "interest": "interests",
        "level": "levels",
    }

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.config = Config.get_conf(
            self,
            identifier=self.CONFIG_IDENTIFIER,
            force_registration=True,
            # Keep the original Config namespace so upgrades retain XP/settings.
            cog_name="ZodiacColorRoles",
        )
        self.config.register_guild(
            leveling_enabled=False,
            xp_min=15,
            xp_max=25,
            xp_cooldown=60,
            level_up_channel_id=None,
            level_up_message="🎉 {user} reached **Level {level}**!",
            level_roles={},
            stack_level_roles=True,
            ignored_channel_ids=[],
        )
        self.config.register_member(xp=0, message_count=0)
        self._xp_cooldowns: dict[tuple[int, int], float] = {}
        self._xp_locks: dict[tuple[int, int], asyncio.Lock] = {}

    async def red_delete_data_for_user(self, *, requester: str, user_id: int) -> None:
        """Delete a member's stored XP from every server."""
        for guild_id in await self.config.all_guilds():
            await self.config.member_from_ids(guild_id, user_id).clear()
        for key in [key for key in self._xp_cooldowns if key[1] == user_id]:
            self._xp_cooldowns.pop(key, None)
            self._xp_locks.pop(key, None)

    @staticmethod
    def _ephemeral(ctx: commands.Context) -> bool:
        return bool(ctx.interaction)

    async def _check_permissions(self, ctx: commands.Context) -> bool:
        """Check whether the bot can create and assign roles."""
        if ctx.guild is None or ctx.guild.me is None:
            await ctx.send("This command can only be used in a server.")
            return False
        if not ctx.guild.me.guild_permissions.manage_roles:
            await ctx.send(
                "I need the Manage Roles permission to create or assign roles.",
                ephemeral=self._ephemeral(ctx),
            )
            return False
        return True

    async def _create_role_safely(
        self,
        guild: discord.Guild,
        name: str,
        color: discord.Color | None = None,
        *,
        reason: str = "Community role pack setup",
    ) -> discord.Role:
        """Create a role while translating Discord errors into command errors."""
        try:
            kwargs: dict[str, Any] = {"name": name, "reason": reason}
            if color is not None:
                kwargs["color"] = color
            return await guild.create_role(**kwargs)
        except discord.Forbidden as error:
            raise commands.BotMissingPermissions(["manage_roles"]) from error
        except discord.HTTPException as error:
            raise commands.CommandError(
                f"Discord could not create the role {name!r}: {error}",
            ) from error

    @classmethod
    def _normalize_pack(cls, pack: str) -> str:
        normalized = pack.strip().lower().replace(" ", "_")
        return cls.PACK_ALIASES.get(normalized, normalized)

    @classmethod
    def _pack_definitions(
        cls,
        pack: str,
    ) -> list[tuple[str, discord.Color | None, int | None]]:
        """Return role name, optional color, and optional reward level."""
        if pack == "zodiac":
            return [(name, None, None) for name in cls.ZODIAC_SIGNS]
        if pack == "colors":
            return [
                (f"Color {name}", discord.Color(int(hex_code[1:], 16)), None)
                for name, hex_code in cls.COLOR_CHOICES.items()
            ]
        if pack == "pronouns":
            return [(name, None, None) for name in cls.PRONOUN_ROLES]
        if pack == "pings":
            return [(name, None, None) for name in cls.COMMON_PING_ROLES]
        if pack == "platforms":
            return [(name, None, None) for name in cls.PLATFORM_ROLES]
        if pack == "regions":
            return [(name, None, None) for name in cls.REGION_ROLES]
        if pack == "interests":
            return [(name, None, None) for name in cls.INTEREST_ROLES]
        if pack == "levels":
            return [
                (f"Level {level}", discord.Color(color), level)
                for level, color in cls.DEFAULT_LEVEL_ROLES.items()
            ]
        raise commands.BadArgument(
            f"Unknown role pack. Choose from: {', '.join(cls.PACK_LABELS)}.",
        )

    async def _create_role_pack(
        self,
        guild: discord.Guild,
        pack: str,
    ) -> tuple[list[str], list[str], list[str]]:
        """Create missing roles in a pack and wire level reward roles."""
        pack = self._normalize_pack(pack)
        definitions = self._pack_definitions(pack)
        created: list[str] = []
        existing: list[str] = []
        failed: list[str] = []
        reward_roles = await self.config.guild(guild).level_roles()

        for name, color, reward_level in definitions:
            role = discord.utils.get(guild.roles, name=name)
            if role is None:
                try:
                    role = await self._create_role_safely(guild, name, color)
                except (commands.BotMissingPermissions, commands.CommandError):
                    failed.append(name)
                    continue
                created.append(name)
            else:
                existing.append(name)
            if reward_level is not None:
                reward_roles[str(reward_level)] = role.id

        if pack == "levels":
            await self.config.guild(guild).level_roles.set(reward_roles)
        return created, existing, failed

    async def _send_pack_result(
        self,
        ctx: commands.Context,
        pack: str,
        created: list[str],
        existing: list[str],
        failed: list[str],
    ) -> None:
        label = self.PACK_LABELS[self._normalize_pack(pack)]
        parts = [f"**{label}**"]
        if created:
            parts.append(f"Created ({len(created)}): {', '.join(created)}")
        if existing:
            parts.append(f"Already present ({len(existing)}): {', '.join(existing)}")
        if failed:
            parts.append(f"Failed ({len(failed)}): {', '.join(failed)}")
        await ctx.send("\n".join(parts), ephemeral=self._ephemeral(ctx))

    async def _create_pack_option(
        self,
        ctx: commands.Context,
        pack: str,
        requested: str,
    ) -> None:
        """Backward-compatible helper for the original add-role commands."""
        if not await self._check_permissions(ctx):
            return
        normalized = requested.strip().lower()
        definitions = self._pack_definitions(pack)
        if normalized == "all":
            result = await self._create_role_pack(ctx.guild, pack)
            await self._send_pack_result(ctx, pack, *result)
            return

        match = next(
            (item for item in definitions if item[0].lower() == normalized),
            None,
        )
        if pack == "colors" and match is None:
            match = next(
                (item for item in definitions if item[0].removeprefix("Color ").lower() == normalized),
                None,
            )
        if match is None:
            choices = ", ".join(item[0] for item in definitions)
            await ctx.send(
                f"Invalid option. Choose one of: {choices}, or `all`.",
                ephemeral=self._ephemeral(ctx),
            )
            return

        name, color, reward_level = match
        role = discord.utils.get(ctx.guild.roles, name=name)
        if role is not None:
            await ctx.send(
                f"Role already exists: {name}",
                ephemeral=self._ephemeral(ctx),
            )
            return
        try:
            role = await self._create_role_safely(ctx.guild, name, color)
        except (commands.BotMissingPermissions, commands.CommandError) as error:
            await ctx.send(
                f"Failed to create role: {error}",
                ephemeral=self._ephemeral(ctx),
            )
            return
        if reward_level is not None:
            async with self.config.guild(ctx.guild).level_roles() as rewards:
                rewards[str(reward_level)] = role.id
        await ctx.send(f"Created role: {name}", ephemeral=self._ephemeral(ctx))

    @commands.hybrid_group(name="rolepack", invoke_without_command=True)
    @commands.guild_only()
    async def rolepack(self, ctx: commands.Context) -> None:
        """Create curated community role packs."""
        await ctx.send_help(ctx.command)

    @rolepack.command(name="list")
    @commands.guild_only()
    async def rolepack_list(self, ctx: commands.Context) -> None:
        """List the available role packs and their contents."""
        lines = []
        for key, label in self.PACK_LABELS.items():
            names = ", ".join(item[0] for item in self._pack_definitions(key))
            lines.append(f"**{key} — {label}:** {names}")
        await ctx.send("\n".join(lines), ephemeral=self._ephemeral(ctx))

    @rolepack.command(name="create")
    @commands.guild_only()
    @commands.admin_or_permissions(manage_roles=True)
    async def rolepack_create(self, ctx: commands.Context, pack: str) -> None:
        """Create every role in one curated pack."""
        if not await self._check_permissions(ctx):
            return
        normalized = self._normalize_pack(pack)
        if normalized not in self.PACK_LABELS:
            raise commands.BadArgument(
                f"Choose from: {', '.join(self.PACK_LABELS)}.",
            )
        result = await self._create_role_pack(ctx.guild, normalized)
        await self._send_pack_result(ctx, normalized, *result)

    @rolepack.command(name="createall")
    @commands.guild_only()
    @commands.admin_or_permissions(manage_roles=True)
    async def rolepack_create_all(self, ctx: commands.Context) -> None:
        """Create every curated pack; this may create many server roles."""
        if not await self._check_permissions(ctx):
            return
        summaries = []
        for pack in self.PACK_LABELS:
            created, existing, failed = await self._create_role_pack(ctx.guild, pack)
            summaries.append(
                f"**{self.PACK_LABELS[pack]}:** {len(created)} created, "
                f"{len(existing)} existing, {len(failed)} failed",
            )
        await ctx.send("\n".join(summaries), ephemeral=self._ephemeral(ctx))

    @commands.hybrid_command(name="listzodiacroles")
    @commands.guild_only()
    async def listzodiacroles(self, ctx: commands.Context) -> None:
        """List all available zodiac roles."""
        await ctx.send(
            f"Available zodiac roles: {', '.join(self.ZODIAC_SIGNS)}",
            ephemeral=self._ephemeral(ctx),
        )

    @commands.hybrid_command(name="listcolorroles")
    @commands.guild_only()
    async def listcolorroles(self, ctx: commands.Context) -> None:
        """List all available color roles."""
        choices = ", ".join(
            f"{name} ({hex_code})" for name, hex_code in self.COLOR_CHOICES.items()
        )
        await ctx.send(f"Available color roles: {choices}", ephemeral=self._ephemeral(ctx))

    @commands.hybrid_command(name="addzodiacrole")
    @commands.guild_only()
    @commands.admin_or_permissions(manage_roles=True)
    async def addzodiacrole(self, ctx: commands.Context, zodiac: str) -> None:
        """Create one zodiac role or the full zodiac pack."""
        await self._create_pack_option(ctx, "zodiac", zodiac)

    @commands.hybrid_command(name="addcolorrole")
    @commands.guild_only()
    @commands.admin_or_permissions(manage_roles=True)
    async def addcolorrole(self, ctx: commands.Context, color: str) -> None:
        """Create one color role or the full color pack."""
        await self._create_pack_option(ctx, "colors", color)

    @commands.hybrid_command(name="addpronounrole")
    @commands.guild_only()
    @commands.admin_or_permissions(manage_roles=True)
    async def addpronounrole(self, ctx: commands.Context, pronoun: str) -> None:
        """Create one pronoun role or the full pronoun pack."""
        await self._create_pack_option(ctx, "pronouns", pronoun)

    @commands.hybrid_command(name="addcommonpingrole")
    @commands.guild_only()
    @commands.admin_or_permissions(manage_roles=True)
    async def addcommonpingrole(self, ctx: commands.Context, pingrole: str) -> None:
        """Create one notification role or the full notification pack."""
        await self._create_pack_option(ctx, "pings", pingrole)

    @commands.hybrid_command(name="addlevelrole")
    @commands.guild_only()
    @commands.admin_or_permissions(manage_roles=True)
    async def addlevelrole(
        self,
        ctx: commands.Context,
        level: int,
    ) -> None:
        """Create and register a reward role for an activity level."""
        if not 1 <= level <= self.MAX_LEVEL:
            raise commands.BadArgument(f"Level must be between 1 and {self.MAX_LEVEL}.")
        if not await self._check_permissions(ctx):
            return
        name = f"Level {level}"
        role = discord.utils.get(ctx.guild.roles, name=name)
        created = role is None
        if role is None:
            default_color = self.DEFAULT_LEVEL_ROLES.get(level)
            color = discord.Color(default_color) if default_color is not None else None
            role = await self._create_role_safely(ctx.guild, name, color)
        async with self.config.guild(ctx.guild).level_roles() as rewards:
            rewards[str(level)] = role.id
        verb = "Created" if created else "Registered"
        await ctx.send(
            f"{verb} {role.mention} as the Level {level} reward.",
            ephemeral=self._ephemeral(ctx),
        )

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message) -> None:
        """Award cooldown-limited XP for normal server conversation."""
        if (
            message.guild is None
            or message.author.bot
            or message.webhook_id is not None
            or not isinstance(message.author, discord.Member)
            or (not message.content.strip() and not message.attachments)
        ):
            return
        if await self.bot.cog_disabled_in_guild(self, message.guild):
            return

        settings = await self.config.guild(message.guild).all()
        if not settings["leveling_enabled"]:
            return
        if message.channel.id in settings["ignored_channel_ids"]:
            return
        ctx = await self.bot.get_context(message)
        if ctx.valid:
            return

        key = (message.guild.id, message.author.id)
        now = time.monotonic()
        cooldown = max(5, int(settings["xp_cooldown"]))
        if now - self._xp_cooldowns.get(key, 0.0) < cooldown:
            return
        self._xp_cooldowns[key] = now

        xp_min = max(1, int(settings["xp_min"]))
        xp_max = max(xp_min, int(settings["xp_max"]))
        gained = random.randint(xp_min, xp_max)
        lock = self._xp_locks.setdefault(key, asyncio.Lock())
        async with lock:
            member_conf = self.config.member(message.author)
            data = await member_conf.all()
            old_xp = max(0, int(data["xp"]))
            new_xp = old_xp + gained
            old_level = self.level_for_xp(old_xp)
            new_level = self.level_for_xp(new_xp)
            await member_conf.xp.set(new_xp)
            await member_conf.message_count.set(max(0, int(data["message_count"])) + 1)

        if new_level > old_level:
            await self._handle_level_up(message, new_level, settings)

    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member) -> None:
        """Remove XP data when a member leaves a server."""
        await self.config.member(member).clear()
        key = (member.guild.id, member.id)
        self._xp_cooldowns.pop(key, None)
        self._xp_locks.pop(key, None)

    @classmethod
    def level_for_xp(cls, xp: int) -> int:
        """Convert total XP into a level using a predictable quadratic curve."""
        return min(cls.MAX_LEVEL, math.isqrt(max(0, int(xp)) // cls.XP_PER_LEVEL_SQUARED))

    @classmethod
    def xp_for_level(cls, level: int) -> int:
        """Return the total XP required to reach a level."""
        return cls.XP_PER_LEVEL_SQUARED * max(0, int(level)) ** 2

    async def _handle_level_up(
        self,
        message: discord.Message,
        level: int,
        settings: dict[str, Any],
    ) -> None:
        await self._sync_level_roles(message.author, level, settings)
        channel = None
        channel_id = settings.get("level_up_channel_id")
        if channel_id:
            channel = message.guild.get_channel(int(channel_id))
        channel = channel or message.channel
        if not hasattr(channel, "send"):
            return
        template = str(settings.get("level_up_message") or "{user} reached Level {level}!")
        try:
            text = template.format(
                user=message.author.mention,
                display_name=message.author.display_name,
                level=level,
                server=message.guild.name,
            )
        except (AttributeError, IndexError, KeyError, ValueError):
            text = f"🎉 {message.author.mention} reached **Level {level}**!"
        try:
            await channel.send(
                text[:2000],
                allowed_mentions=discord.AllowedMentions(
                    everyone=False,
                    roles=False,
                    users=[message.author],
                ),
            )
        except discord.HTTPException:
            return

    async def _sync_level_roles(
        self,
        member: discord.Member,
        level: int,
        settings: dict[str, Any] | None = None,
    ) -> tuple[int, int]:
        settings = settings or await self.config.guild(member.guild).all()
        configured = []
        for raw_level, raw_role_id in settings.get("level_roles", {}).items():
            try:
                reward_level = int(raw_level)
                role = member.guild.get_role(int(raw_role_id))
            except (TypeError, ValueError):
                continue
            if role is not None:
                configured.append((reward_level, role))
        configured.sort(key=lambda item: item[0])

        manageable = [
            (reward_level, role)
            for reward_level, role in configured
            if member.guild.me is not None and role < member.guild.me.top_role
        ]
        eligible = [(reward_level, role) for reward_level, role in manageable if reward_level <= level]
        wanted = [role for _, role in eligible]
        if wanted and not settings.get("stack_level_roles", True):
            wanted = [wanted[-1]]
        configured_roles = {role for _, role in manageable}
        wanted_set = set(wanted)
        to_add = [role for role in wanted if role not in member.roles]
        to_remove = [
            role
            for role in member.roles
            if role in configured_roles and role not in wanted_set
        ]
        try:
            if to_add:
                await member.add_roles(*to_add, reason="Activity level rewards")
            if to_remove:
                await member.remove_roles(*to_remove, reason="Activity level reward sync")
        except (discord.Forbidden, discord.HTTPException):
            return 0, 0
        return len(to_add), len(to_remove)

    @commands.hybrid_command(name="rank")
    @commands.guild_only()
    async def rank(
        self,
        ctx: commands.Context,
        member: discord.Member | None = None,
    ) -> None:
        """Show your activity rank or another member's rank."""
        member = member or ctx.author
        data = await self.config.member(member).all()
        xp = max(0, int(data["xp"]))
        level = self.level_for_xp(xp)
        current_floor = self.xp_for_level(level)
        next_floor = self.xp_for_level(min(self.MAX_LEVEL, level + 1))
        needed = max(0, next_floor - xp)
        span = max(1, next_floor - current_floor)
        progress = min(1.0, max(0.0, (xp - current_floor) / span))
        blocks = round(progress * 10)
        bar = "█" * blocks + "░" * (10 - blocks)
        embed = discord.Embed(
            title=f"{member.display_name}'s Activity Rank",
            color=member.color if member.color.value else discord.Color.blurple(),
        )
        embed.set_thumbnail(url=member.display_avatar.url)
        embed.add_field(name="Level", value=f"**{level}**")
        embed.add_field(name="Total XP", value=f"**{xp:,}**")
        embed.add_field(name="Counted messages", value=f"**{int(data['message_count']):,}**")
        if level < self.MAX_LEVEL:
            embed.add_field(
                name="Next level",
                value=f"`{bar}` {needed:,} XP remaining",
                inline=False,
            )
        await ctx.send(embed=embed, ephemeral=self._ephemeral(ctx))

    @commands.hybrid_command(name="levelboard", aliases=["xpleaderboard"])
    @commands.guild_only()
    async def levelboard(self, ctx: commands.Context) -> None:
        """Show the server's most active members."""
        records = await self.config.all_members(ctx.guild)
        ranked = sorted(
            (
                (int(member_id), max(0, int(data.get("xp", 0))))
                for member_id, data in records.items()
                if int(data.get("xp", 0)) > 0
            ),
            key=lambda item: item[1],
            reverse=True,
        )[:10]
        if not ranked:
            await ctx.send("No one has earned activity XP yet.", ephemeral=self._ephemeral(ctx))
            return
        lines = []
        for position, (member_id, xp) in enumerate(ranked, start=1):
            member = ctx.guild.get_member(member_id)
            name = member.mention if member is not None else f"Former member ({member_id})"
            lines.append(f"**{position}.** {name} — Level {self.level_for_xp(xp)} · {xp:,} XP")
        embed = discord.Embed(
            title=f"{ctx.guild.name} Activity Leaderboard",
            description="\n".join(lines),
            color=discord.Color.gold(),
        )
        await ctx.send(embed=embed)

    @commands.hybrid_group(name="leveling", invoke_without_command=True)
    @commands.guild_only()
    @commands.admin_or_permissions(manage_guild=True)
    async def leveling(self, ctx: commands.Context) -> None:
        """Configure activity XP and level rewards."""
        await ctx.send_help(ctx.command)

    @leveling.command(name="enable")
    @commands.guild_only()
    @commands.admin_or_permissions(manage_guild=True)
    async def leveling_enable(self, ctx: commands.Context) -> None:
        """Enable activity XP in this server."""
        await self.config.guild(ctx.guild).leveling_enabled.set(True)
        await ctx.send("Activity leveling is now enabled.", ephemeral=self._ephemeral(ctx))

    @leveling.command(name="disable")
    @commands.guild_only()
    @commands.admin_or_permissions(manage_guild=True)
    async def leveling_disable(self, ctx: commands.Context) -> None:
        """Disable activity XP without deleting existing ranks."""
        await self.config.guild(ctx.guild).leveling_enabled.set(False)
        await ctx.send("Activity leveling is now disabled.", ephemeral=self._ephemeral(ctx))

    @leveling.command(name="xprange")
    @commands.guild_only()
    @commands.admin_or_permissions(manage_guild=True)
    async def leveling_xp_range(
        self,
        ctx: commands.Context,
        minimum: int,
        maximum: int,
    ) -> None:
        """Set the random XP awarded for an eligible message."""
        if minimum < 1 or maximum < minimum or maximum > 1000:
            raise commands.BadArgument("Use an XP range from 1 to 1,000 with minimum ≤ maximum.")
        guild_conf = self.config.guild(ctx.guild)
        await guild_conf.xp_min.set(minimum)
        await guild_conf.xp_max.set(maximum)
        await ctx.send(
            f"Eligible messages now earn {minimum}–{maximum} XP.",
            ephemeral=self._ephemeral(ctx),
        )

    @leveling.command(name="cooldown")
    @commands.guild_only()
    @commands.admin_or_permissions(manage_guild=True)
    async def leveling_cooldown(self, ctx: commands.Context, seconds: int) -> None:
        """Set how often one member can earn message XP."""
        if not 5 <= seconds <= 3600:
            raise commands.BadArgument("Cooldown must be between 5 and 3,600 seconds.")
        await self.config.guild(ctx.guild).xp_cooldown.set(seconds)
        await ctx.send(
            f"The XP cooldown is now {seconds} seconds.",
            ephemeral=self._ephemeral(ctx),
        )

    @leveling.command(name="reward")
    @commands.guild_only()
    @commands.admin_or_permissions(manage_guild=True)
    async def leveling_reward(
        self,
        ctx: commands.Context,
        level: int,
        role: discord.Role,
    ) -> None:
        """Use an existing role as a level reward."""
        if not 1 <= level <= self.MAX_LEVEL:
            raise commands.BadArgument(f"Level must be between 1 and {self.MAX_LEVEL}.")
        if ctx.guild.me is None or role >= ctx.guild.me.top_role:
            raise commands.BadArgument("That role must be below the bot's highest role.")
        async with self.config.guild(ctx.guild).level_roles() as rewards:
            rewards[str(level)] = role.id
        await ctx.send(
            f"{role.mention} is now the Level {level} reward.",
            ephemeral=self._ephemeral(ctx),
        )

    @leveling.command(name="removereward")
    @commands.guild_only()
    @commands.admin_or_permissions(manage_guild=True)
    async def leveling_remove_reward(self, ctx: commands.Context, level: int) -> None:
        """Remove the configured reward for a level without deleting the role."""
        async with self.config.guild(ctx.guild).level_roles() as rewards:
            removed = rewards.pop(str(level), None)
        message = (
            f"Removed the Level {level} reward mapping."
            if removed is not None
            else f"No reward was configured for Level {level}."
        )
        await ctx.send(message, ephemeral=self._ephemeral(ctx))

    @leveling.command(name="ignorechannel")
    @commands.guild_only()
    @commands.admin_or_permissions(manage_guild=True)
    async def leveling_ignore_channel(
        self,
        ctx: commands.Context,
        channel: discord.TextChannel,
    ) -> None:
        """Toggle whether a channel awards message XP."""
        async with self.config.guild(ctx.guild).ignored_channel_ids() as channel_ids:
            if channel.id in channel_ids:
                channel_ids.remove(channel.id)
                message = f"{channel.mention} now awards XP."
            else:
                channel_ids.append(channel.id)
                message = f"{channel.mention} no longer awards XP."
        await ctx.send(message, ephemeral=self._ephemeral(ctx))

    @leveling.command(name="sync")
    @commands.guild_only()
    @commands.admin_or_permissions(manage_guild=True)
    async def leveling_sync(
        self,
        ctx: commands.Context,
        member: discord.Member | None = None,
    ) -> None:
        """Reapply a member's configured level reward roles."""
        member = member or ctx.author
        xp = await self.config.member(member).xp()
        added, removed = await self._sync_level_roles(member, self.level_for_xp(xp))
        await ctx.send(
            f"Synced {member.mention}: {added} role(s) added, {removed} removed.",
            ephemeral=self._ephemeral(ctx),
        )

    @leveling.command(name="reset")
    @commands.guild_only()
    @commands.admin_or_permissions(manage_guild=True)
    async def leveling_reset(
        self,
        ctx: commands.Context,
        member: discord.Member,
    ) -> None:
        """Reset one member's XP and remove configured level roles."""
        await self.config.member(member).clear()
        _added, removed = await self._sync_level_roles(member, 0)
        await ctx.send(
            f"Reset {member.mention}'s XP and removed {removed} level role(s).",
            ephemeral=self._ephemeral(ctx),
        )
