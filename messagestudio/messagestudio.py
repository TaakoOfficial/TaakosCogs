"""Standalone rich-message and Components V2 studio."""

from __future__ import annotations

import json
import logging
from typing import Any, Literal
from urllib.parse import urlparse

import aiohttp
import discord
from redbot.core import Config, commands
from redbot.core.utils.chat_formatting import pagify, text_to_file

from .components import (
    ComponentsV2Error,
    load_payload,
    payload_to_files,
    payload_to_legacy_view,
    payload_to_view,
    view_to_payload,
)
from .dashboard_integration import DashboardIntegration

FORMATS = Literal["json", "yaml", "jsonfile", "yamlfile", "pastebin", "message"]
log = logging.getLogger("red.taakoscogs.messagestudio")


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
        self.config.register_guild(stored_messages={}, component_actions={})
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
        kind = self._payload_kind(item["payload"])
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
            actions = await self._prepare_actions(payload, ctx.guild, ctx.author)
            kwargs = self._send_kwargs(payload)
            message = await hook.send(
                **kwargs,
                username=username,
                avatar_url=avatar_url,
                wait=True,
                allowed_mentions=discord.AllowedMentions.none(),
            )
            await self._register_message_actions(message, actions, ctx.author, guild=ctx.guild)

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
            "`embed actions [message]` — inspect or clear persistent interactions",
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
        kind = self._payload_kind(payload)
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

    @commands.mod_or_permissions(manage_guild=True)
    @embed.group(name="actions", invoke_without_command=True)
    async def embed_actions(self, ctx, message: discord.Message | None = None):
        """Show persistent component actions attached to a message."""
        message = message or self._referenced(ctx)
        record = (await self.config.guild(ctx.guild).component_actions()).get(str(message.id))
        if not record:
            raise commands.UserFeedbackCheckFailure("That message has no registered component actions.")
        controls = record.get("controls", {})
        lines = [f"- `{custom_id}`: {', '.join(action['type'] for action in actions)}" for custom_id, actions in controls.items()]
        await ctx.send(
            embed=discord.Embed(
                title="MessageStudio Actions",
                description="\n".join(lines) or "No actions.",
                color=await ctx.embed_color(),
            ),
        )

    @commands.mod_or_permissions(manage_guild=True)
    @embed_actions.command(name="clear")
    async def embed_actions_clear(self, ctx, message: discord.Message):
        """Disable all persistent component actions for a message."""
        async with self.config.guild(ctx.guild).component_actions() as records:
            if records.pop(str(message.id), None) is None:
                raise commands.UserFeedbackCheckFailure("That message has no registered component actions.")
        await ctx.tick()

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
            if payload.get("legacy") is True or any(key in payload for key in ("content", "embed", "embeds")):
                content, embeds = self._legacy_message_parts(payload)
                return {"content": content, "embeds": embeds, "view": payload_to_legacy_view(payload)}
            return {"view": payload_to_view(payload), "files": payload_to_files(payload)}
        content, embeds = self._legacy_message_parts(payload)
        if not content and not embeds:
            raise commands.BadArgument("The payload contains no message content.")
        return {"content": content, "embeds": embeds}

    @staticmethod
    def _payload_kind(payload) -> str:
        if isinstance(payload, dict) and "components" in payload and not (
            payload.get("legacy") is True or any(key in payload for key in ("content", "embed", "embeds"))
        ):
            return "Components V2"
        return "legacy message"

    @staticmethod
    def _legacy_message_parts(payload):
        if not isinstance(payload, (dict, list)):
            raise ComponentsV2Error("A legacy message payload must be an object or a list of embeds.")
        content = payload.get("content") if isinstance(payload, dict) else None
        if isinstance(payload, list):
            raw = payload
        elif "embeds" in payload:
            raw = payload["embeds"]
        elif "embed" in payload:
            raw = payload["embed"]
        elif "components" in payload:
            raw = []
        else:
            embed_keys = {
                "title",
                "description",
                "color",
                "colour",
                "fields",
                "author",
                "footer",
                "image",
                "thumbnail",
                "timestamp",
                "url",
            }
            raw = payload if embed_keys.intersection(payload) else []
        raw = raw if isinstance(raw, list) else [raw]
        embeds = [discord.Embed.from_dict(x) for x in raw if isinstance(x, dict) and x]
        return content, embeds

    async def _send(self, ctx, payload, target=None):
        guild = target.guild if isinstance(target, discord.Message) else ctx.guild
        actions = await self._prepare_actions(payload, guild, ctx.author)
        kwargs = self._send_kwargs(payload)
        try:
            if isinstance(target, discord.Message):
                if target.author.id != ctx.me.id:
                    raise commands.UserFeedbackCheckFailure("I can only edit my own messages.")
                if "files" in kwargs:
                    files = kwargs.pop("files", [])
                    message = await target.edit(content=None, embeds=[], attachments=files, **kwargs)
                else:
                    message = await target.edit(
                        content=kwargs["content"],
                        embeds=kwargs["embeds"],
                        view=kwargs.get("view"),
                    )
            else:
                message = await (target or ctx).send(**kwargs)
            await self._register_message_actions(message, actions, ctx.author, guild=guild)
            return message
        except discord.HTTPException as error:
            raise commands.UserFeedbackCheckFailure(f"Discord rejected the message: {error}") from error

    async def _prepare_actions(
        self,
        payload: Any,
        guild: discord.Guild,
        actor: discord.Member | discord.User,
    ) -> dict[str, list[dict[str, Any]]]:
        controls = self._collect_component_actions(payload)
        if not controls:
            return controls
        member = guild.get_member(actor.id)
        if member is None:
            raise ComponentsV2Error("The action configurator must be a member of this server.")
        me = guild.me
        is_owner = member.id == guild.owner_id or member.id in getattr(self.bot, "owner_ids", set())
        for actions in controls.values():
            for action in actions:
                if action["type"] in {"add_role", "remove_role", "toggle_role"}:
                    role = guild.get_role(int(action["role_id"]))
                    if role is None:
                        raise ComponentsV2Error(f"Role `{action['role_id']}` does not exist in this server.")
                    if role.is_default() or role.managed:
                        raise ComponentsV2Error(f"Role `{role.name}` cannot be managed by a component action.")
                    if not is_owner and (not member.guild_permissions.manage_roles or role >= member.top_role):
                        raise ComponentsV2Error(
                            f"You need Manage Roles and a role above `{role.name}` to configure that action.",
                        )
                    if me is None or not me.guild_permissions.manage_roles or role >= me.top_role:
                        raise ComponentsV2Error(
                            f"I need Manage Roles and a role above `{role.name}` before that action can be sent.",
                        )
                elif action["type"] == "send_message":
                    channel = guild.get_channel_or_thread(int(action["channel_id"]))
                    if not isinstance(channel, (discord.TextChannel, discord.VoiceChannel, discord.Thread)):
                        raise ComponentsV2Error(f"Channel `{action['channel_id']}` is not text-capable.")
                    if not is_owner and not channel.permissions_for(member).send_messages:
                        raise ComponentsV2Error(f"You cannot configure posts in #{channel.name}.")
                    if me is None or not channel.permissions_for(me).send_messages:
                        raise ComponentsV2Error(f"I cannot post in #{channel.name}.")
        return controls

    @staticmethod
    def _collect_component_actions(payload: Any) -> dict[str, list[dict[str, Any]]]:
        if not isinstance(payload, dict) or not isinstance(payload.get("components"), list):
            return {}
        result: dict[str, list[dict[str, Any]]] = {}
        seen_custom_ids: set[str] = set()
        duplicate_custom_ids: set[str] = set()
        allowed = {"add_role", "remove_role", "toggle_role", "send_message", "reply"}

        def walk(component: Any) -> None:
            if not isinstance(component, dict):
                return
            try:
                component_type = int(component.get("type"))
                button_style = int(component.get("style", 2))
            except (TypeError, ValueError):
                component_type = 0
                button_style = 0
            custom_id = component.get("custom_id")
            if component_type in {2, 3, 5, 6, 7, 8} and isinstance(custom_id, str) and custom_id:
                if custom_id in seen_custom_ids:
                    duplicate_custom_ids.add(custom_id)
                seen_custom_ids.add(custom_id)
            raw_actions = component.get("actions")
            if raw_actions is not None:
                if component_type not in {2, 3, 5, 6, 7, 8} or (
                    component_type == 2 and button_style not in {1, 2, 3, 4}
                ):
                    raise ComponentsV2Error("Actions can only be attached to custom buttons and select menus.")
                if not isinstance(custom_id, str) or not 1 <= len(custom_id) <= 100:
                    raise ComponentsV2Error("A component with actions requires a 1 to 100 character `custom_id`.")
                if custom_id in result:
                    raise ComponentsV2Error(f"Action custom ID `{custom_id}` is duplicated in this message.")
                if not isinstance(raw_actions, list) or not 1 <= len(raw_actions) <= 10:
                    raise ComponentsV2Error("Component `actions` must contain 1 to 10 action objects.")
                normalized = []
                for raw in raw_actions:
                    if not isinstance(raw, dict) or raw.get("type") not in allowed:
                        raise ComponentsV2Error(
                            "Actions support `add_role`, `remove_role`, `toggle_role`, `send_message`, and `reply`.",
                        )
                    action = dict(raw)
                    action_type = action["type"]
                    if action_type in {"add_role", "remove_role", "toggle_role"}:
                        try:
                            action["role_id"] = str(int(action["role_id"]))
                        except (KeyError, TypeError, ValueError) as error:
                            raise ComponentsV2Error(f"`{action_type}` requires a Discord `role_id`.") from error
                        if int(action["role_id"]) <= 0:
                            raise ComponentsV2Error(f"`{action_type}` requires a positive Discord `role_id`.")
                    elif action_type == "send_message":
                        try:
                            action["channel_id"] = str(int(action["channel_id"]))
                        except (KeyError, TypeError, ValueError) as error:
                            raise ComponentsV2Error("`send_message` requires a Discord `channel_id`.") from error
                        if int(action["channel_id"]) <= 0:
                            raise ComponentsV2Error("`send_message` requires a positive Discord `channel_id`.")
                        if not isinstance(action.get("content"), str) or not 1 <= len(action["content"]) <= 2000:
                            raise ComponentsV2Error("`send_message` content must contain 1 to 2000 characters.")
                    else:
                        if not isinstance(action.get("content"), str) or not 1 <= len(action["content"]) <= 2000:
                            raise ComponentsV2Error("`reply` content must contain 1 to 2000 characters.")
                        if "ephemeral" in action and not isinstance(action["ephemeral"], bool):
                            raise ComponentsV2Error("`reply` ephemeral must be true or false.")
                        action["ephemeral"] = bool(action.get("ephemeral", True))
                    if "values" in action and (
                        not isinstance(action["values"], list)
                        or not 1 <= len(action["values"]) <= 25
                        or not all(isinstance(value, str) and 1 <= len(value) <= 100 for value in action["values"])
                    ):
                        raise ComponentsV2Error("Action `values` must contain 1 to 25 select option strings.")
                    normalized.append(action)
                result[custom_id] = normalized
            for child in component.get("components", []) if isinstance(component.get("components"), list) else []:
                walk(child)
            if isinstance(component.get("accessory"), dict):
                walk(component["accessory"])

        for component in payload["components"]:
            walk(component)
        if result and duplicate_custom_ids:
            duplicates = ", ".join(f"`{custom_id}`" for custom_id in sorted(duplicate_custom_ids))
            raise ComponentsV2Error(
                f"Every interactive custom ID must be unique when actions are used. Duplicates: {duplicates}.",
            )
        if len(result) > 40:
            raise ComponentsV2Error("A message cannot register more than 40 interactive controls.")
        return result

    async def _register_message_actions(
        self,
        message: discord.Message,
        controls: dict[str, list[dict[str, Any]]],
        actor: discord.abc.User,
        *,
        guild: discord.Guild | None = None,
    ) -> None:
        guild = guild or message.guild
        if guild is None:
            return
        async with self.config.guild(guild).component_actions() as records:
            if controls:
                records[str(message.id)] = {
                    "channel_id": message.channel.id,
                    "configured_by": actor.id,
                    "controls": controls,
                }
            else:
                records.pop(str(message.id), None)

    @commands.Cog.listener()
    async def on_interaction(self, interaction: discord.Interaction) -> None:
        if interaction.type is not discord.InteractionType.component or interaction.guild is None or interaction.message is None:
            return
        record = (await self.config.guild(interaction.guild).component_actions()).get(str(interaction.message.id))
        if not record or not isinstance(interaction.data, dict):
            return
        custom_id = interaction.data.get("custom_id")
        actions = record.get("controls", {}).get(custom_id)
        if not actions:
            return
        try:
            await self._execute_component_actions(interaction, actions)
        except (ComponentsV2Error, discord.HTTPException, discord.Forbidden) as error:
            await self._interaction_reply(interaction, f"This action could not be completed: {error}", ephemeral=True)
        except Exception:
            log.exception("Unexpected MessageStudio component action failure")
            await self._interaction_reply(
                interaction,
                "This action could not be completed because of an internal error.",
                ephemeral=True,
            )

    async def _execute_component_actions(
        self,
        interaction: discord.Interaction,
        actions: list[dict[str, Any]],
    ) -> None:
        guild = interaction.guild
        member = interaction.user
        if guild is None or not isinstance(member, discord.Member):
            raise ComponentsV2Error("Component actions can only be used by server members.")
        selected = [str(value) for value in interaction.data.get("values", [])]
        if not interaction.response.is_done():
            public_reply = any(action["type"] == "reply" and not action.get("ephemeral", True) for action in actions)
            await interaction.response.defer(ephemeral=not public_reply)
        summaries: list[str] = []
        replies: list[tuple[str, bool]] = []
        for action in actions:
            required_values = action.get("values")
            if required_values and not set(required_values).intersection(selected):
                continue
            action_type = action["type"]
            if action_type in {"add_role", "remove_role", "toggle_role"}:
                role = guild.get_role(int(action["role_id"]))
                me = guild.me
                if role is None:
                    raise ComponentsV2Error("The configured role no longer exists.")
                if (
                    role.is_default()
                    or role.managed
                    or me is None
                    or not me.guild_permissions.manage_roles
                    or role >= me.top_role
                ):
                    raise ComponentsV2Error(
                        f"I cannot manage the `{role.name}` role. Check my role hierarchy and Manage Roles permission.",
                    )
                has_role = role in member.roles
                if action_type == "add_role" and not has_role:
                    await member.add_roles(role, reason=f"MessageStudio component {interaction.message.id}")
                    summaries.append(f"Added **{role.name}**.")
                elif action_type == "remove_role" and has_role:
                    await member.remove_roles(role, reason=f"MessageStudio component {interaction.message.id}")
                    summaries.append(f"Removed **{role.name}**.")
                elif action_type == "toggle_role":
                    if has_role:
                        await member.remove_roles(role, reason=f"MessageStudio component {interaction.message.id}")
                        summaries.append(f"Removed **{role.name}**.")
                    else:
                        await member.add_roles(role, reason=f"MessageStudio component {interaction.message.id}")
                        summaries.append(f"Added **{role.name}**.")
                else:
                    summaries.append(f"You already {'have' if has_role else 'do not have'} **{role.name}**.")
            elif action_type == "send_message":
                channel = guild.get_channel_or_thread(int(action["channel_id"]))
                if not isinstance(channel, (discord.TextChannel, discord.VoiceChannel, discord.Thread)):
                    raise ComponentsV2Error("The configured destination channel no longer exists.")
                if guild.me is None or not channel.permissions_for(guild.me).send_messages:
                    raise ComponentsV2Error(f"I cannot send messages in #{channel.name}.")
                await channel.send(
                    self._format_action_text(action["content"], interaction, selected),
                    allowed_mentions=discord.AllowedMentions.none(),
                )
                summaries.append(f"Posted in {channel.mention}.")
            else:
                replies.append(
                    (
                        self._format_action_text(action["content"], interaction, selected),
                        bool(action.get("ephemeral", True)),
                    ),
                )
        if replies:
            content = "\n".join(text for text, _ in replies)
            await self._interaction_reply(interaction, content[:2000], ephemeral=all(ephemeral for _, ephemeral in replies))
        else:
            content = "\n".join(summaries) or "No configured action matched this selection."
            await self._interaction_reply(interaction, content[:2000], ephemeral=True)

    @staticmethod
    def _format_action_text(text: str, interaction: discord.Interaction, values: list[str]) -> str:
        replacements = {
            "{user}": interaction.user.mention,
            "{user_id}": str(interaction.user.id),
            "{server}": interaction.guild.name if interaction.guild else "",
            "{channel}": interaction.channel.mention if interaction.channel else "",
            "{value}": values[0] if values else "",
            "{values}": ", ".join(values),
        }
        for marker, value in replacements.items():
            text = text.replace(marker, value)
        return text

    @staticmethod
    async def _interaction_reply(interaction: discord.Interaction, content: str, *, ephemeral: bool) -> None:
        if interaction.response.is_done():
            await interaction.followup.send(content, ephemeral=ephemeral, allowed_mentions=discord.AllowedMentions.none())
        else:
            await interaction.response.send_message(content, ephemeral=ephemeral, allowed_mentions=discord.AllowedMentions.none())

    @commands.Cog.listener()
    async def on_raw_message_delete(self, payload: discord.RawMessageDeleteEvent) -> None:
        if payload.guild_id is None:
            return
        async with self.config.guild_from_id(payload.guild_id).component_actions() as records:
            records.pop(str(payload.message_id), None)

    @commands.Cog.listener()
    async def on_raw_bulk_message_delete(self, payload: discord.RawBulkMessageDeleteEvent) -> None:
        if payload.guild_id is None:
            return
        async with self.config.guild_from_id(payload.guild_id).component_actions() as records:
            for message_id in payload.message_ids:
                records.pop(str(message_id), None)

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
        if message.components:
            result["legacy"] = True
            result["components"] = discord.ui.View.from_message(message, timeout=None).to_components()
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
