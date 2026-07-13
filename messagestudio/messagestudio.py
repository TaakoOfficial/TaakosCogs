"""Standalone rich-message and Components V2 studio."""

from __future__ import annotations

import json
from typing import Literal
from urllib.parse import urlparse

import aiohttp
import discord
from redbot.core import Config, commands
from redbot.core.utils.chat_formatting import pagify, text_to_file

from .components import load_payload, payload_to_view, view_to_payload
from .dashboard_integration import DashboardIntegration

FORMATS = Literal["json", "yaml", "jsonfile", "yamlfile", "pastebin", "message"]


class MessageableOrMessage(commands.Converter):
    """Resolve a bot message or a text-capable guild channel."""

    async def convert(self, ctx, argument):
        for converter in (
            commands.MessageConverter,
            commands.TextChannelConverter,
            commands.VoiceChannelConverter,
            commands.ThreadConverter,
        ):
            try:
                return await converter().convert(ctx, argument)
            except commands.BadArgument:
                continue
        raise commands.BadArgument("That is not a message or text-capable channel.")


class StoredName(commands.Converter):
    """Consume one stored-message name for Greedy conversion."""

    async def convert(self, ctx, argument):
        return argument


class MessageStudio(DashboardIntegration, commands.Cog):
    """Create, send, store, and edit embeds and Components V2 messages."""

    CONFIG_IDENTIFIER = 205192943327321000143939875896557571751

    def __init__(self, bot):
        self.bot = bot
        self.config = Config.get_conf(self, identifier=self.CONFIG_IDENTIFIER, force_registration=True)
        self.config.register_global(stored_messages={})
        self.config.register_guild(stored_messages={})
        self.session: aiohttp.ClientSession | None = None

    async def cog_load(self) -> None:
        if not hasattr(discord.ui, "LayoutView"):
            raise RuntimeError("MessageStudio requires discord.py 2.6 or newer.")
        self.session = aiohttp.ClientSession()

    async def cog_unload(self) -> None:
        if self.session is not None:
            await self.session.close()

    @commands.guild_only()
    @commands.mod_or_permissions(manage_messages=True)
    @commands.bot_has_permissions(send_messages=True)
    @commands.hybrid_group(name="embed", aliases=["embedutils", "messagestudio", "cv2"], invoke_without_command=True)
    async def embed(
        self,
        ctx: commands.Context,
        channel_or_message: MessageableOrMessage | None = None,
        color: discord.Color | None = None,
        title: str | None = None,
        *,
        description: str | None = None,
    ) -> None:
        """Post a simple rich embed, or show help when no title is supplied."""
        if title is None:
            await ctx.send_help()
            return
        payload = {"embed": {"color": (color or await ctx.embed_color()).value, "title": title, "description": description}}
        await self._send(ctx, payload, channel_or_message)

    @embed.command(name="json", aliases=["fromjson", "fromdata"])
    async def embed_json(self, ctx, channel_or_message: MessageableOrMessage | None = None, *, data: str = ""):
        """Post embeds or Components V2 from JSON."""
        data = data or await self._attachment(ctx, ("json", "txt"))
        await self._send(ctx, load_payload(data, "json"), channel_or_message)

    @embed.command(name="yaml", aliases=["fromyaml"])
    async def embed_yaml(self, ctx, channel_or_message: MessageableOrMessage | None = None, *, data: str = ""):
        """Post embeds or Components V2 from YAML."""
        data = data or await self._attachment(ctx, ("yaml", "yml", "txt"))
        await self._send(ctx, load_payload(data, "yaml"), channel_or_message)

    @embed.command(name="fromfile", aliases=["jsonfile", "fromjsonfile", "fromdatafile"])
    async def embed_fromfile(self, ctx, channel_or_message: MessageableOrMessage | None = None):
        """Post a JSON message from an attached file."""
        await self._send(ctx, load_payload(await self._attachment(ctx, ("json", "txt")), "json"), channel_or_message)

    @embed.command(name="yamlfile", aliases=["fromyamlfile"])
    async def embed_yamlfile(self, ctx, channel_or_message: MessageableOrMessage | None = None):
        """Post a YAML message from an attached file."""
        await self._send(ctx, load_payload(await self._attachment(ctx, ("yaml", "yml", "txt")), "yaml"), channel_or_message)

    @embed.command(name="pastebin", aliases=["frompastebin", "gist", "fromgist", "hastebin", "fromhastebin"])
    async def embed_pastebin(self, ctx, channel_or_message: MessageableOrMessage | None = None, *, data: str):
        """Post JSON from a GitHub Gist, Pastebin, Hastebin, or raw URL."""
        await self._send(ctx, load_payload(await self._fetch_text(data), "json"), channel_or_message)

    @embed.command(name="message", aliases=["frommessage", "msg", "frommsg"])
    async def embed_message(
        self,
        ctx,
        channel_or_message: MessageableOrMessage | None = None,
        message: discord.Message | None = None,
        index: int | None = None,
        include_content: bool | None = None,
    ):
        """Copy an existing embed or Components V2 message."""
        message = message or self._referenced(ctx)
        payload = self._message_payload(message, index, include_content)
        await self._send(ctx, payload, channel_or_message)

    @embed.command(name="download")
    async def embed_download(
        self,
        ctx,
        message: discord.Message | None = None,
        index: int | None = None,
        include_content: bool | None = None,
    ):
        """Download a message as reusable JSON."""
        message = message or self._referenced(ctx)
        payload = self._message_payload(message, index, include_content)
        await ctx.send(file=text_to_file(json.dumps(payload, indent=2), filename="message.json"))

    @embed.command(name="edit")
    async def embed_edit(self, ctx, message: discord.Message, conversion_type: FORMATS, *, data: str = ""):
        """Edit a bot-authored message from JSON, YAML, file, URL, or message data."""
        if message.author.id != ctx.me.id:
            raise commands.UserFeedbackCheckFailure("I can only edit my own messages.")
        payload = await self._conversion(ctx, conversion_type, data)
        await self._send(ctx, payload, message)
        await ctx.tick()

    @commands.mod_or_permissions(manage_guild=True)
    @embed.command(name="store", aliases=["storeembed"])
    async def embed_store(
        self,
        ctx,
        global_level: bool = False,
        locked: bool = False,
        name: str = "",
        conversion_type: FORMATS = "json",
        *,
        data: str = "",
    ):
        """Store an embed or Components V2 message."""
        self._check_global(ctx, global_level)
        payload = await self._conversion(ctx, conversion_type, data)
        self._validate(payload)
        group = self.config if global_level else self.config.guild(ctx.guild)
        async with group.stored_messages() as stored:
            if name not in stored and not global_level and len(stored) >= 100:
                raise commands.UserFeedbackCheckFailure("This server has reached the 100-message limit.")
            stored[name] = {"author": ctx.author.id, "payload": payload, "locked": locked, "uses": 0}
        await ctx.tick()

    @commands.mod_or_permissions(manage_guild=True)
    @embed.command(name="unstore", aliases=["unstoreembed"])
    async def embed_unstore(self, ctx, global_level: bool = False, *, name: str):
        """Remove a stored message."""
        self._check_global(ctx, global_level)
        group = self.config if global_level else self.config.guild(ctx.guild)
        async with group.stored_messages() as stored:
            if name not in stored:
                raise commands.UserFeedbackCheckFailure("No stored message has that name.")
            del stored[name]
        await ctx.tick()

    @commands.mod_or_permissions(manage_guild=True)
    @embed.command(name="list", aliases=["liststored", "liststoredembeds"])
    async def embed_list(self, ctx, global_level: bool = False):
        """List stored messages."""
        self._check_global(ctx, global_level)
        stored = await (self.config if global_level else self.config.guild(ctx.guild)).stored_messages()
        if not stored:
            raise commands.UserFeedbackCheckFailure("No messages are stored at this level.")
        for page in pagify("\n".join(f"- `{name}`" for name in stored)):
            await ctx.send(embed=discord.Embed(title="Stored Messages", description=page, color=await ctx.embed_color()))

    @commands.mod_or_permissions(manage_guild=True)
    @embed.command(name="info", aliases=["infostored", "infostoredembed"])
    async def embed_info(self, ctx, global_level: bool = False, *, name: str):
        """Show metadata for a stored message."""
        item = await self._stored(ctx, global_level, name, increment=False)
        kind = "Components V2" if isinstance(item["payload"], dict) and "components" in item["payload"] else "Legacy embed"
        await ctx.send(
            embed=discord.Embed(
                title=f"Stored message: {name}",
                description=f"Author: <@{item['author']}>\nUses: {item['uses']}\nLocked: {item['locked']}\nType: {kind}",
                color=await ctx.embed_color(),
            ),
            allowed_mentions=discord.AllowedMentions.none(),
        )

    @commands.mod_or_permissions(manage_guild=True)
    @embed.command(name="downloadstored", aliases=["downloadstoredembed"])
    async def embed_downloadstored(self, ctx, global_level: bool = False, *, name: str):
        """Download a stored message."""
        item = await self._stored(ctx, global_level, name, increment=False)
        await ctx.send(file=text_to_file(json.dumps(item["payload"], indent=2), filename="stored-message.json"))

    @embed.command(name="poststored", aliases=["poststoredembed", "post"])
    async def embed_poststored(
        self,
        ctx,
        channel_or_message: MessageableOrMessage | None = None,
        global_level: bool = False,
        names: commands.Greedy[StoredName] = None,
    ):
        """Post one or more stored messages."""
        for name in names or []:
            await self._send(ctx, (await self._stored(ctx, global_level, name))["payload"], channel_or_message)

    @commands.mod_or_permissions(manage_webhooks=True)
    @commands.bot_has_permissions(manage_webhooks=True)
    @embed.command(name="postwebhook", aliases=["webhook"])
    async def embed_postwebhook(
        self,
        ctx,
        channel: discord.TextChannel | None,
        username: commands.Range[str, 1, 80],
        avatar_url: str,
        global_level: bool = False,
        names: commands.Greedy[StoredName] = None,
    ):
        """Post stored messages through a webhook with a custom identity."""
        channel = channel or ctx.channel
        hooks = await channel.webhooks()
        hook = next((h for h in hooks if h.user == ctx.me), None) or await channel.create_webhook(name="MessageStudio")
        for name in names or []:
            payload = (await self._stored(ctx, global_level, name))["payload"]
            kwargs = self._send_kwargs(payload)
            await hook.send(**kwargs, username=username, avatar_url=avatar_url, wait=True)

    @embed.command(name="dashboard")
    async def dashboard(self, ctx):
        """Open the visual MessageStudio dashboard builder."""
        dashboard_url = getattr(self.bot, "dashboard_url", None)
        if dashboard_url is None:
            raise commands.UserFeedbackCheckFailure("Red-Web-Dashboard is not running.")
        url = f"{dashboard_url[0]}/dashboard/{ctx.guild.id}/third-party/{self.qualified_name}/guild"
        view = discord.ui.View()
        view.add_item(discord.ui.Button(label="Open MessageStudio", url=url))
        await ctx.send("Open the visual message builder:", view=view)

    @embed.command(name="commands")
    async def embed_commands(self, ctx):
        """Show the MessageStudio command reference."""
        lines = [
            "`embed json|yaml [channel] <payload>` — send message data",
            "`embed fromfile|yamlfile [channel]` — send an attached payload",
            "`embed pastebin [channel] <url>` — send remote JSON",
            "`embed message|download|edit ...` — copy, export, or edit messages",
            "`embed store|unstore|list|info ...` — manage saved messages",
            "`embed poststored|postwebhook ...` — post saved messages",
            "`embed dashboard` — open the visual editor",
            "`embed tools color|timestamp|validate ...` — message utilities",
        ]
        await ctx.send(
            embed=discord.Embed(
                title="MessageStudio Commands",
                description="\n".join(lines),
                color=await ctx.embed_color(),
            ),
        )

    @embed.group(name="tools", invoke_without_command=True)
    async def embed_tools(self, ctx):
        """Color, timestamp, and payload validation utilities."""
        await ctx.send_help()

    @embed_tools.command(name="color")
    async def embed_tools_color(self, ctx, color: discord.Color):
        """Convert a Discord color to hex, decimal, and RGB."""
        red, green, blue = color.to_rgb()
        await ctx.send(
            f"Hex: `#{color.value:06X}`\nDecimal: `{color.value}`\nRGB: `{red}, {green}, {blue}`",
        )

    @embed_tools.command(name="timestamp")
    async def embed_tools_timestamp(self, ctx, unix: int | None = None):
        """Generate Discord timestamp markup from a Unix timestamp."""
        unix = unix if unix is not None else int(discord.utils.utcnow().timestamp())
        await ctx.send(
            f"`<t:{unix}:F>` → <t:{unix}:F>\n`<t:{unix}:R>` → <t:{unix}:R>\n`<t:{unix}:d>` → <t:{unix}:d>",
        )

    @embed_tools.command(name="validate")
    async def embed_tools_validate(
        self,
        ctx,
        conversion_type: Literal["json", "yaml"],
        *,
        data: str,
    ):
        """Validate a legacy embed or Components V2 payload."""
        payload = load_payload(data, conversion_type)
        self._validate(payload)
        kind = "Components V2" if isinstance(payload, dict) and "components" in payload else "legacy message"
        await ctx.send(f"Valid {kind} payload.")

    @commands.is_owner()
    @embed.command(name="migratefromphen", aliases=["migratefromembedutils"])
    async def migratefromphen(self, ctx):
        """Migrate stored embeds from Phen's historical EmbedUtils config."""
        old = Config.get_conf("EmbedUtils", identifier=43248937299564234735284, force_registration=True, cog_name="EmbedUtils")
        count = 0
        async with self.config.stored_messages() as stored:
            for name, item in (await old.all()).get("embeds", {}).items():
                stored.setdefault(
                    name,
                    {
                        "author": item["author"],
                        "payload": {"embed": item["embed"]},
                        "locked": item.get("locked", False),
                        "uses": item.get("uses", 0),
                    },
                )
                count += 1
        for guild_id, data in (await old.all_guilds()).items():
            embeds = data.get("embeds", {})
            if not embeds:
                continue
            async with self.config.guild_from_id(int(guild_id)).stored_messages() as stored:
                for name, item in embeds.items():
                    stored.setdefault(
                        name,
                        {
                            "author": item["author"],
                            "payload": {"embed": item["embed"]},
                            "locked": item.get("locked", False),
                            "uses": item.get("uses", 0),
                        },
                    )
                    count += 1
        await ctx.send(f"Migrated {count} stored embeds.")

    async def _conversion(self, ctx, kind, data):
        if kind in {"json", "fromjson", "fromdata"}:
            return load_payload(data, "json")
        if kind in {"yaml", "fromyaml"}:
            return load_payload(data, "yaml")
        if kind in {"jsonfile", "fromfile", "fromjsonfile", "fromdatafile"}:
            return load_payload(await self._attachment(ctx, ("json", "txt")), "json")
        if kind in {"yamlfile", "fromyamlfile"}:
            return load_payload(await self._attachment(ctx, ("yaml", "yml", "txt")), "yaml")
        if kind in {"pastebin", "gist", "hastebin"}:
            return load_payload(await self._fetch_text(data), "json")
        source = await commands.MessageConverter().convert(ctx, data) if data else self._referenced(ctx)
        return self._message_payload(source)

    def _send_kwargs(self, payload):
        if isinstance(payload, dict) and "components" in payload:
            return {"view": payload_to_view(payload)}
        content = payload.get("content") if isinstance(payload, dict) else None
        raw = payload if isinstance(payload, list) else payload.get("embeds", payload.get("embed", payload))
        raw = raw if isinstance(raw, list) else [raw]
        embeds = [discord.Embed.from_dict(x) for x in raw if isinstance(x, dict) and x]
        if not content and not embeds:
            raise commands.BadArgument("The payload contains no message content.")
        return {"content": content, "embeds": embeds}

    async def _send(self, ctx, payload, target=None):
        kwargs = self._send_kwargs(payload)
        try:
            if isinstance(target, discord.Message):
                if target.author.id != ctx.me.id:
                    raise commands.UserFeedbackCheckFailure("I can only edit my own messages.")
                if "view" in kwargs:
                    await target.edit(content=None, embeds=[], attachments=[], **kwargs)
                else:
                    await target.edit(content=kwargs["content"], embeds=kwargs["embeds"], view=None)
            else:
                await (target or ctx).send(**kwargs)
        except discord.HTTPException as error:
            raise commands.UserFeedbackCheckFailure(f"Discord rejected the message: {error}") from error

    def _message_payload(self, message, index=None, include_content=None):
        if message.flags.components_v2:
            return view_to_payload(discord.ui.LayoutView.from_message(message, timeout=None))
        embeds = [e.to_dict() for e in message.embeds]
        if index is not None:
            try:
                embeds = [embeds[index]]
            except IndexError as error:
                raise commands.BadArgument("That embed index does not exist.") from error
        result = {"embeds": embeds}
        if (include_content is True or (include_content is None and index is None)) and message.content:
            result["content"] = message.content
        return result

    @staticmethod
    def _referenced(ctx):
        message = getattr(getattr(ctx.message, "reference", None), "resolved", None)
        if not isinstance(message, discord.Message):
            raise commands.UserInputError("Reply to a message or provide one.")
        return message

    async def _attachment(self, ctx, extensions):
        attachments = getattr(ctx.message, "attachments", [])
        if not attachments:
            raise commands.UserInputError("Attach a JSON or YAML text file.")
        item = attachments[0]
        if item.size > 256_000 or item.filename.rsplit(".", 1)[-1].lower() not in extensions:
            raise commands.UserInputError("The attachment type or size is invalid.")
        try:
            return (await item.read()).decode()
        except UnicodeDecodeError as error:
            raise commands.UserInputError("The attachment must be UTF-8.") from error

    async def _fetch_text(self, url):
        parsed = urlparse(url)
        if parsed.scheme not in {"http", "https"}:
            raise commands.BadArgument("Only HTTP(S) links are supported.")
        if "pastebin.com" in parsed.netloc and "/raw/" not in parsed.path:
            url = url.replace("pastebin.com/", "pastebin.com/raw/")
        if "gist.github.com" in parsed.netloc and not parsed.path.endswith("/raw"):
            url = url.rstrip("/") + "/raw"
        assert self.session is not None
        async with self.session.get(url, timeout=aiohttp.ClientTimeout(total=15)) as response:
            if response.status != 200:
                raise commands.BadArgument(f"The URL returned HTTP {response.status}.")
            data = await response.content.read(256_001)
        if len(data) > 256_000:
            raise commands.BadArgument("Remote payloads are limited to 256 KB.")
        return data.decode()

    def _validate(self, payload):
        self._send_kwargs(payload)

    def _check_global(self, ctx, value):
        if value and ctx.author.id not in ctx.bot.owner_ids:
            raise commands.UserFeedbackCheckFailure("Only bot owners can manage global messages.")

    async def _stored(self, ctx, global_level, name, increment=True):
        group = self.config if global_level else self.config.guild(ctx.guild)
        async with group.stored_messages() as stored:
            if name not in stored:
                raise commands.UserFeedbackCheckFailure(f"No stored message named `{name}` exists.")
            item = stored[name]
            if item.get("locked") and (
                (global_level and ctx.author.id not in ctx.bot.owner_ids)
                or (not global_level and not await ctx.bot.is_mod(ctx.author))
            ):
                raise commands.UserFeedbackCheckFailure("That stored message is locked.")
            if increment:
                item["uses"] = item.get("uses", 0) + 1
            return dict(item)
