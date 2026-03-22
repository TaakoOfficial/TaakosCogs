"""Welcome cog for Red-DiscordBot."""

import base64
import io
import json
import logging
import os
import re
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

import aiohttp
import discord
from redbot.core import Config, commands
from redbot.core.utils.chat_formatting import box, pagify

log = logging.getLogger("red.taakoscogs.welcome")


class Welcome(commands.Cog):
    """Custom welcome messages with placeholders, JSON embeds, and cached images."""

    IMAGE_SIZE_LIMIT = 8 * 1024 * 1024
    PLACEHOLDER_PATTERN = re.compile(r"\{(member|guild)\.([a-zA-Z0-9_]+)\}")

    MEMBER_PLACEHOLDERS: Dict[str, str] = {
        "mention": "Mentions the joining member.",
        "name": "The member username.",
        "display_name": "The member display name in the server.",
        "global_name": "The member global display name.",
        "nick": "The member nickname in the server.",
        "id": "The member Discord ID.",
        "bot": "Whether the member is a bot.",
        "created_at": "The member account creation time.",
        "joined_at": "The time the member joined the server.",
        "avatar_url": "The member avatar URL.",
        "display_avatar_url": "The member display avatar URL.",
        "top_role": "The member's highest role name.",
        "top_role_mention": "The member's highest role mention.",
        "color": "The member display color as a hex string.",
        "roles": "A comma-separated list of the member's roles.",
        "role_mentions": "All of the member's roles as mentions.",
    }

    GUILD_PLACEHOLDERS: Dict[str, str] = {
        "name": "The server name.",
        "id": "The server ID.",
        "description": "The server description.",
        "member_count": "The current server member count.",
        "created_at": "The server creation time.",
        "owner": "The server owner name.",
        "owner_mention": "The server owner mention.",
        "owner_id": "The server owner ID.",
        "preferred_locale": "The server preferred locale.",
        "verification_level": "The server verification level.",
        "icon_url": "The server icon URL.",
        "banner_url": "The server banner URL.",
        "splash_url": "The server splash URL.",
        "discovery_splash_url": "The discovery splash URL.",
        "rules_channel": "The rules channel mention.",
        "system_channel": "The system channel mention.",
        "text_channels": "The number of text channels.",
        "voice_channels": "The number of voice channels.",
        "categories": "The number of category channels.",
        "roles": "The number of roles.",
        "emojis": "The number of custom emojis.",
        "stickers": "The number of stickers.",
        "premium_tier": "The server boost tier.",
        "premium_subscription_count": "The server boost count.",
    }

    def __init__(self, bot):
        self.bot = bot
        self.config = Config.get_conf(self, identifier=2026032101, force_registration=True)
        self.config.register_guild(
            enabled=False,
            include_bots=False,
            channel_id=None,
            message_template="Welcome {member.mention} to **{guild.name}**!",
            embed_json={},
            image=self._empty_image_data(),
            image_mode="embed",
        )

    @staticmethod
    def _empty_image_data() -> Dict[str, Optional[str]]:
        return {
            "source_url": None,
            "filename": None,
            "content_type": None,
            "data_base64": None,
        }

    @staticmethod
    def _format_datetime(value: Optional[datetime]) -> str:
        if value is None:
            return ""
        return discord.utils.format_dt(value, "F")

    @staticmethod
    def _asset_url(asset: Optional[discord.Asset]) -> str:
        return str(asset.url) if asset else ""

    @staticmethod
    def _sanitize_filename(url: str, content_type: Optional[str]) -> str:
        parsed_name = os.path.basename(url.split("?")[0].strip())
        if not parsed_name:
            parsed_name = "welcome-image"

        name, ext = os.path.splitext(parsed_name)
        if not ext:
            guessed = None
            if content_type:
                guessed = content_type.split(";")[0].strip().lower()
            ext = {
                "image/png": ".png",
                "image/jpeg": ".jpg",
                "image/jpg": ".jpg",
                "image/webp": ".webp",
                "image/gif": ".gif",
            }.get(guessed, ".png")
        safe_name = re.sub(r"[^a-zA-Z0-9._-]", "-", name).strip("-") or "welcome-image"
        return f"{safe_name[:40]}{ext.lower()}"

    @classmethod
    def _valid_placeholder_names(cls) -> set:
        return {
            *(f"member.{key}" for key in cls.MEMBER_PLACEHOLDERS),
            *(f"guild.{key}" for key in cls.GUILD_PLACEHOLDERS),
        }

    @classmethod
    def _find_unknown_placeholders(cls, value: Any) -> List[str]:
        unknown = set()

        def walk(item: Any) -> None:
            if isinstance(item, str):
                for match in cls.PLACEHOLDER_PATTERN.findall(item):
                    placeholder = ".".join(match)
                    if placeholder not in cls._valid_placeholder_names():
                        unknown.add(placeholder)
            elif isinstance(item, dict):
                for sub_value in item.values():
                    walk(sub_value)
            elif isinstance(item, list):
                for sub_value in item:
                    walk(sub_value)

        walk(value)
        return sorted(unknown)

    def _member_context(self, member: discord.Member) -> Dict[str, str]:
        roles = [role for role in member.roles if role != member.guild.default_role]
        top_role = member.top_role if member.top_role != member.guild.default_role else None
        return {
            "mention": member.mention,
            "name": member.name,
            "display_name": member.display_name,
            "global_name": member.global_name or "",
            "nick": member.nick or "",
            "id": str(member.id),
            "bot": "Yes" if member.bot else "No",
            "created_at": self._format_datetime(member.created_at),
            "joined_at": self._format_datetime(member.joined_at),
            "avatar_url": self._asset_url(member.avatar),
            "display_avatar_url": self._asset_url(member.display_avatar),
            "top_role": top_role.name if top_role else "",
            "top_role_mention": top_role.mention if top_role else "",
            "color": str(member.color),
            "roles": ", ".join(role.name for role in roles),
            "role_mentions": " ".join(role.mention for role in roles),
        }

    def _guild_context(self, guild: discord.Guild) -> Dict[str, str]:
        owner = guild.owner
        return {
            "name": guild.name,
            "id": str(guild.id),
            "description": guild.description or "",
            "member_count": str(guild.member_count or 0),
            "created_at": self._format_datetime(guild.created_at),
            "owner": str(owner) if owner else "",
            "owner_mention": owner.mention if owner else "",
            "owner_id": str(guild.owner_id or ""),
            "preferred_locale": str(guild.preferred_locale),
            "verification_level": str(guild.verification_level),
            "icon_url": self._asset_url(guild.icon),
            "banner_url": self._asset_url(guild.banner),
            "splash_url": self._asset_url(guild.splash),
            "discovery_splash_url": self._asset_url(guild.discovery_splash),
            "rules_channel": guild.rules_channel.mention if guild.rules_channel else "",
            "system_channel": guild.system_channel.mention if guild.system_channel else "",
            "text_channels": str(len(guild.text_channels)),
            "voice_channels": str(len(guild.voice_channels)),
            "categories": str(len(guild.categories)),
            "roles": str(len(guild.roles)),
            "emojis": str(len(guild.emojis)),
            "stickers": str(len(guild.stickers)),
            "premium_tier": str(guild.premium_tier),
            "premium_subscription_count": str(guild.premium_subscription_count or 0),
        }

    def _render_string(self, template: str, member: discord.Member) -> str:
        member_context = self._member_context(member)
        guild_context = self._guild_context(member.guild)

        def replacer(match: re.Match) -> str:
            root, name = match.groups()
            if root == "member":
                return member_context.get(name, match.group(0))
            return guild_context.get(name, match.group(0))

        return self.PLACEHOLDER_PATTERN.sub(replacer, template)

    def _render_data(self, value: Any, member: discord.Member) -> Any:
        if isinstance(value, str):
            return self._render_string(value, member)
        if isinstance(value, dict):
            return {key: self._render_data(sub_value, member) for key, sub_value in value.items()}
        if isinstance(value, list):
            return [self._render_data(sub_value, member) for sub_value in value]
        return value

    @staticmethod
    def _normalise_embed_dict(embed_data: Dict[str, Any]) -> Dict[str, Any]:
        cleaned = dict(embed_data)
        color_value = cleaned.get("color")
        if isinstance(color_value, str):
            normalized = color_value.strip().lower().replace("#", "").replace("0x", "")
            try:
                cleaned["color"] = int(normalized, 16)
            except ValueError as exc:
                raise commands.BadArgument(
                    "Embed color must be an integer or a hex string like `#5865F2`."
                ) from exc
        return cleaned

    @staticmethod
    def _clean_embed_media_block(block: Any) -> Optional[Dict[str, Any]]:
        if not isinstance(block, dict):
            return None

        url = block.get("url")
        if not url:
            return None

        return {"url": url}

    @staticmethod
    def _clean_embed_footer_block(block: Any) -> Optional[Dict[str, Any]]:
        if not isinstance(block, dict):
            return None

        cleaned: Dict[str, Any] = {}
        text = block.get("text")
        icon_url = block.get("icon_url")
        if text:
            cleaned["text"] = text
        if icon_url:
            cleaned["icon_url"] = icon_url
        return cleaned or None

    @staticmethod
    def _clean_embed_author_block(block: Any) -> Optional[Dict[str, Any]]:
        if not isinstance(block, dict):
            return None

        cleaned: Dict[str, Any] = {}
        for key in ("name", "url", "icon_url"):
            value = block.get(key)
            if value:
                cleaned[key] = value
        return cleaned or None

    @staticmethod
    def _clean_embed_fields(fields: Any) -> List[Dict[str, Any]]:
        if not isinstance(fields, list):
            return []

        cleaned_fields: List[Dict[str, Any]] = []
        for field in fields:
            if not isinstance(field, dict):
                continue
            name = field.get("name")
            value = field.get("value")
            if name is None or value is None:
                continue

            cleaned_field: Dict[str, Any] = {
                "name": name,
                "value": value,
            }
            if "inline" in field:
                cleaned_field["inline"] = bool(field.get("inline"))
            cleaned_fields.append(cleaned_field)
        return cleaned_fields

    @classmethod
    def _extract_embed_object(cls, payload: Dict[str, Any]) -> Dict[str, Any]:
        if "embeds" in payload:
            embeds = payload.get("embeds")
            if not isinstance(embeds, list) or not embeds:
                raise commands.BadArgument("`embeds` must be a non-empty list.")
            if not isinstance(embeds[0], dict):
                raise commands.BadArgument("The first entry in `embeds` must be an object.")
            return embeds[0]

        embed = payload.get("embed")
        if isinstance(embed, dict):
            return embed

        return payload

    @classmethod
    def _sanitize_embed_dict(cls, embed_data: Dict[str, Any]) -> Dict[str, Any]:
        cleaned: Dict[str, Any] = {}

        for key in ("title", "description", "url", "timestamp"):
            value = embed_data.get(key)
            if value not in (None, ""):
                cleaned[key] = value

        if "color" in embed_data and embed_data.get("color") is not None:
            cleaned["color"] = embed_data.get("color")

        author = cls._clean_embed_author_block(embed_data.get("author"))
        if author:
            cleaned["author"] = author

        footer = cls._clean_embed_footer_block(embed_data.get("footer"))
        if footer:
            cleaned["footer"] = footer

        thumbnail = cls._clean_embed_media_block(embed_data.get("thumbnail"))
        if thumbnail:
            cleaned["thumbnail"] = thumbnail

        image = cls._clean_embed_media_block(embed_data.get("image"))
        if image:
            cleaned["image"] = image

        fields = cls._clean_embed_fields(embed_data.get("fields"))
        if fields:
            cleaned["fields"] = fields

        if not cleaned:
            raise commands.BadArgument("No usable embed data was found in that JSON payload.")

        return cleaned

    async def _read_json_input(
        self, ctx: commands.Context, raw_json: Optional[str]
    ) -> Tuple[Dict[str, Any], str]:
        payload = raw_json
        source = "command input"

        if payload is None and ctx.message and ctx.message.attachments:
            attachment = ctx.message.attachments[0]
            try:
                payload = (await attachment.read()).decode("utf-8")
            except UnicodeDecodeError as exc:
                raise commands.BadArgument(
                    "The attached file could not be decoded as UTF-8 JSON."
                ) from exc
            source = f"attachment `{attachment.filename}`"

        if not payload:
            raise commands.BadArgument("Provide JSON text or attach a `.json` file.")

        payload = payload.strip()
        if payload.startswith("```") and payload.endswith("```"):
            payload = "\n".join(payload.splitlines()[1:-1]).strip()

        try:
            parsed = json.loads(payload)
        except json.JSONDecodeError as exc:
            raise commands.BadArgument(
                f"Invalid JSON near line {exc.lineno}, column {exc.colno}: {exc.msg}"
            ) from exc

        if not isinstance(parsed, dict):
            raise commands.BadArgument("Embed JSON must be a single JSON object.")

        embed_object = self._extract_embed_object(parsed)
        cleaned_embed = self._sanitize_embed_dict(embed_object)
        return self._normalise_embed_dict(cleaned_embed), source

    async def _download_image(self, url: str) -> Dict[str, str]:
        timeout = aiohttp.ClientTimeout(total=30)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(url) as response:
                if response.status != 200:
                    raise commands.CommandError(
                        f"Failed to download the image. HTTP status: {response.status}"
                    )

                content_type = response.headers.get("Content-Type", "").split(";")[0].lower()
                if not content_type.startswith("image/"):
                    raise commands.BadArgument("The provided URL did not return an image.")

                data = await response.read()
                if len(data) > self.IMAGE_SIZE_LIMIT:
                    raise commands.BadArgument(
                        "The downloaded image is larger than 8 MB. Use a smaller image."
                    )

                filename = self._sanitize_filename(url, content_type)
                return {
                    "source_url": url,
                    "filename": filename,
                    "content_type": content_type,
                    "data_base64": base64.b64encode(data).decode("ascii"),
                }

    @staticmethod
    def _build_image_file(image_data: Dict[str, Optional[str]]) -> Optional[discord.File]:
        encoded = image_data.get("data_base64")
        filename = image_data.get("filename")
        if not encoded or not filename:
            return None

        data = base64.b64decode(encoded)
        return discord.File(io.BytesIO(data), filename=filename)

    def _build_embed(
        self,
        embed_json: Optional[Dict[str, Any]],
        member: discord.Member,
        image_data: Dict[str, Optional[str]],
        image_mode: str,
    ) -> Optional[discord.Embed]:
        if not embed_json:
            return None

        rendered = self._normalise_embed_dict(self._render_data(embed_json, member))
        embed = discord.Embed.from_dict(rendered)
        if image_mode == "embed" and image_data.get("filename") and not embed.image.url:
            embed.set_image(url=f"attachment://{image_data['filename']}")
        return embed

    async def _send_welcome_message(
        self,
        channel: discord.TextChannel,
        member: discord.Member,
        settings: Dict[str, Any],
    ) -> None:
        content_template = settings.get("message_template") or ""
        content = self._render_string(content_template, member).strip()
        image_data = settings.get("image") or self._empty_image_data()
        image_mode = settings.get("image_mode") or "embed"
        file = self._build_image_file(image_data)
        embed = self._build_embed(settings.get("embed_json"), member, image_data, image_mode)
        me = channel.guild.me or channel.guild.get_member(self.bot.user.id)
        permissions = channel.permissions_for(me) if me else None
        should_attach_file = False
        if file:
            if image_mode == "attachment" or embed is None:
                should_attach_file = True
            elif embed.image.url and embed.image.url.startswith("attachment://"):
                should_attach_file = True

        kwargs: Dict[str, Any] = {
            "allowed_mentions": discord.AllowedMentions(users=True, roles=True, everyone=False)
        }
        if content:
            kwargs["content"] = content
        if embed and permissions and permissions.embed_links:
            kwargs["embed"] = embed
        if should_attach_file and permissions and permissions.attach_files:
            kwargs["file"] = file

        if not any(key in kwargs for key in ("content", "embed", "file")):
            return

        await channel.send(**kwargs)

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member) -> None:
        settings = await self.config.guild(member.guild).all()
        if not settings.get("enabled"):
            return
        if member.bot and not settings.get("include_bots"):
            return

        channel_id = settings.get("channel_id")
        if not channel_id:
            return

        channel = member.guild.get_channel(channel_id)
        if not isinstance(channel, discord.TextChannel):
            return

        me = member.guild.me
        if me is None:
            return

        permissions = channel.permissions_for(me)
        if not permissions.send_messages:
            return

        try:
            await self._send_welcome_message(channel, member, settings)
        except Exception:
            log.exception(
                "Failed to send welcome message in guild %s for member %s",
                member.guild.id,
                member.id,
            )

    @commands.group(name="welcome", invoke_without_command=True)
    @commands.guild_only()
    @commands.admin_or_permissions(manage_guild=True)
    async def welcome(self, ctx: commands.Context) -> None:
        """Configure welcome messages for this server."""
        await ctx.send_help(ctx.command)

    @welcome.command(name="enable")
    async def welcome_enable(self, ctx: commands.Context, enabled: bool) -> None:
        """Enable or disable the welcome message."""
        await self.config.guild(ctx.guild).enabled.set(enabled)
        state = "enabled" if enabled else "disabled"
        await ctx.send(f"Welcome messages are now {state}.")

    @welcome.command(name="bots")
    async def welcome_bots(self, ctx: commands.Context, include_bots: bool) -> None:
        """Choose whether bot accounts should trigger the welcome message."""
        await self.config.guild(ctx.guild).include_bots.set(include_bots)
        state = "included" if include_bots else "ignored"
        await ctx.send(f"Bot accounts will now be {state} by the welcome listener.")

    @welcome.command(name="channel")
    async def welcome_channel(
        self, ctx: commands.Context, channel: Optional[discord.TextChannel] = None
    ) -> None:
        """Set the channel for welcome messages. Leave blank to clear it."""
        if channel is None:
            await self.config.guild(ctx.guild).channel_id.set(None)
            await ctx.send("The welcome channel has been cleared.")
            return

        await self.config.guild(ctx.guild).channel_id.set(channel.id)
        await ctx.send(f"Welcome messages will be sent in {channel.mention}.")

    @welcome.command(name="message")
    async def welcome_message(self, ctx: commands.Context, *, template: str) -> None:
        """Set the plain welcome message template."""
        unknown = self._find_unknown_placeholders(template)
        if unknown:
            unknown_text = ", ".join(f"`{{{name}}}`" for name in unknown)
            raise commands.BadArgument(f"Unknown placeholders: {unknown_text}")

        await self.config.guild(ctx.guild).message_template.set(template)
        await ctx.send("The welcome message template has been updated.")

    @welcome.command(name="clearmessage")
    async def welcome_clear_message(self, ctx: commands.Context) -> None:
        """Clear the plain welcome message template."""
        await self.config.guild(ctx.guild).message_template.set("")
        await ctx.send("The plain welcome message has been cleared.")

    @welcome.command(name="embedjson")
    async def welcome_embed_json(
        self, ctx: commands.Context, *, raw_json: Optional[str] = None
    ) -> None:
        """Set a custom embed from JSON text or a JSON attachment."""
        embed_json, source = await self._read_json_input(ctx, raw_json)
        unknown = self._find_unknown_placeholders(embed_json)
        if unknown:
            unknown_text = ", ".join(f"`{{{name}}}`" for name in unknown)
            raise commands.BadArgument(f"Unknown placeholders: {unknown_text}")

        preview_member = ctx.author if isinstance(ctx.author, discord.Member) else ctx.guild.me
        if preview_member is None:
            raise commands.CommandError("I could not build a preview for this embed.")

        try:
            self._build_embed(embed_json, preview_member, self._empty_image_data(), "embed")
        except Exception as exc:
            raise commands.BadArgument(f"That JSON could not be converted into a Discord embed: {exc}")

        await self.config.guild(ctx.guild).embed_json.set(embed_json)
        await ctx.send(f"Welcome embed JSON saved from {source}.")

    @welcome.command(name="clearembed")
    async def welcome_clear_embed(self, ctx: commands.Context) -> None:
        """Remove the stored custom embed."""
        await self.config.guild(ctx.guild).embed_json.set({})
        await ctx.send("The stored welcome embed has been cleared.")

    @welcome.command(name="image")
    async def welcome_image(self, ctx: commands.Context, url: str) -> None:
        """Download an image from a URL, save it, and re-upload it on welcome."""
        image_data = await self._download_image(url)
        await self.config.guild(ctx.guild).image.set(image_data)
        await ctx.send(
            "The welcome image has been downloaded and cached. "
            "Use `welcome imagemode attachment` to post it above the embed, or "
            "`welcome imagemode embed` to use it inside the embed."
        )

    @welcome.command(name="clearimage")
    async def welcome_clear_image(self, ctx: commands.Context) -> None:
        """Remove the cached welcome image."""
        await self.config.guild(ctx.guild).image.set(self._empty_image_data())
        await ctx.send("The cached welcome image has been cleared.")

    @welcome.command(name="imagemode")
    async def welcome_image_mode(self, ctx: commands.Context, mode: str) -> None:
        """Set whether the cached image is posted in the embed or as a separate attachment."""
        normalized = mode.strip().lower()
        if normalized not in {"embed", "attachment"}:
            raise commands.BadArgument("Use `embed` or `attachment`.")

        await self.config.guild(ctx.guild).image_mode.set(normalized)
        if normalized == "attachment":
            await ctx.send(
                "The cached image will now be posted as a separate attachment above the embed."
            )
            return

        await ctx.send("The cached image will now be used as the embed image when possible.")

    @welcome.command(name="placeholders")
    async def welcome_placeholders(self, ctx: commands.Context) -> None:
        """Show the available member and guild placeholders."""
        member_lines = [
            f"{{member.{name}}} - {description}"
            for name, description in self.MEMBER_PLACEHOLDERS.items()
        ]
        guild_lines = [
            f"{{guild.{name}}} - {description}"
            for name, description in self.GUILD_PLACEHOLDERS.items()
        ]
        content = "\n".join(
            [
                "Member placeholders:",
                *member_lines,
                "",
                "Guild placeholders:",
                *guild_lines,
            ]
        )
        for page in pagify(content, page_length=1800):
            await ctx.send(box(page, lang="md"))

    @welcome.command(name="samplejson")
    async def welcome_sample_json(self, ctx: commands.Context) -> None:
        """Show a sample embed JSON payload."""
        sample = {
            "title": "Welcome to {guild.name}",
            "description": "Say hello to {member.mention}. You are member #{guild.member_count}.",
            "color": "#5865F2",
            "thumbnail": {"url": "{member.display_avatar_url}"},
            "footer": {"text": "Account created {member.created_at}"},
        }
        text = json.dumps(sample, indent=2)
        for page in pagify(text, page_length=1800):
            await ctx.send(box(page, lang="json"))

    @welcome.command(name="settings")
    async def welcome_settings(self, ctx: commands.Context) -> None:
        """Show the current welcome settings for this server."""
        settings = await self.config.guild(ctx.guild).all()
        channel_id = settings.get("channel_id")
        channel = ctx.guild.get_channel(channel_id) if channel_id else None
        image_data = settings.get("image") or {}

        embed = discord.Embed(title="Welcome Settings", color=discord.Color.blurple())
        embed.add_field(
            name="Enabled",
            value="Yes" if settings.get("enabled") else "No",
            inline=True,
        )
        embed.add_field(
            name="Include Bots",
            value="Yes" if settings.get("include_bots") else "No",
            inline=True,
        )
        embed.add_field(
            name="Channel",
            value=channel.mention if channel else "Not set",
            inline=True,
        )

        message_template = settings.get("message_template") or ""
        if message_template:
            embed.add_field(
                name="Message Template",
                value=message_template[:1024],
                inline=False,
            )
        else:
            embed.add_field(name="Message Template", value="Not set", inline=False)

        embed.add_field(
            name="Custom Embed JSON",
            value="Configured" if settings.get("embed_json") else "Not set",
            inline=True,
        )
        embed.add_field(
            name="Cached Image",
            value=image_data.get("filename") or "Not set",
            inline=True,
        )
        embed.add_field(
            name="Image Mode",
            value=(settings.get("image_mode") or "embed").title(),
            inline=True,
        )
        embed.add_field(
            name="Image Source",
            value=(image_data.get("source_url") or "Not set")[:1024],
            inline=False,
        )
        await ctx.send(embed=embed)

    @welcome.command(name="test")
    async def welcome_test(
        self, ctx: commands.Context, member: Optional[discord.Member] = None
    ) -> None:
        """Preview the welcome message in the current channel."""
        member = member or ctx.author
        if not isinstance(member, discord.Member):
            raise commands.BadArgument("The preview target must be a server member.")

        settings = await self.config.guild(ctx.guild).all()
        await self._send_welcome_message(ctx.channel, member, settings)
        await ctx.send("Welcome preview sent above.")
