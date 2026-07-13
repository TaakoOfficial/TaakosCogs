"""Standalone Discord Components V2 builder."""

from __future__ import annotations

import json
from typing import Literal

import discord
from redbot.core import commands
from redbot.core.utils.chat_formatting import text_to_file

from .components import load_payload, payload_to_view, view_to_payload
from .dashboard_integration import DashboardIntegration


class ComponentsV2Builder(DashboardIntegration, commands.Cog):
    """Build and send Discord Components V2 layouts."""

    def __init__(self, bot):
        self.bot = bot

    async def cog_load(self) -> None:
        if not hasattr(discord.ui, "LayoutView"):
            raise RuntimeError("ComponentsV2Builder requires discord.py 2.6 or newer.")

    @commands.guild_only()
    @commands.mod_or_permissions(manage_messages=True)
    @commands.bot_has_permissions(send_messages=True)
    @commands.hybrid_group(name="componentsv2", aliases=["cv2", "embedv2"], invoke_without_command=True)
    async def components_v2(self, ctx: commands.Context) -> None:
        """Build and send Discord Components V2 messages."""
        await ctx.send_help()

    @components_v2.command(name="json")
    @commands.cooldown(2, 5, commands.BucketType.user)
    async def components_v2_json(
        self,
        ctx: commands.Context,
        channel: discord.TextChannel | None = None,
        *,
        data: str = "",
    ) -> None:
        """Send Components V2 JSON or convert a legacy Discord embed payload."""
        if not data:
            data = await self._attachment_text(ctx, ("json", "txt"))
        await self._send_payload(ctx, load_payload(data, "json"), channel)

    @components_v2.command(name="yaml")
    @commands.cooldown(2, 5, commands.BucketType.user)
    async def components_v2_yaml(
        self,
        ctx: commands.Context,
        channel: discord.TextChannel | None = None,
        *,
        data: str = "",
    ) -> None:
        """Send Components V2 YAML or convert a legacy Discord embed payload."""
        if not data:
            data = await self._attachment_text(ctx, ("yaml", "yml", "txt"))
        await self._send_payload(ctx, load_payload(data, "yaml"), channel)

    @components_v2.command(name="edit")
    @commands.cooldown(2, 5, commands.BucketType.user)
    async def components_v2_edit(
        self,
        ctx: commands.Context,
        message: discord.Message,
        conversion_type: Literal["json", "yaml"] = "json",
        *,
        data: str = "",
    ) -> None:
        """Replace a bot-authored message with a Components V2 payload.

        Converting an existing message to Components V2 removes its legacy content,
        embeds, and attachments. Discord does not allow the V2 flag to be removed later.
        """
        if message.guild is None or message.guild.id != ctx.guild.id:
            raise commands.UserFeedbackCheckFailure("The message must be in this server.")
        if not message.channel.permissions_for(ctx.author).manage_messages:
            raise commands.UserFeedbackCheckFailure(
                "You need Manage Messages in the message's channel.",
            )
        if message.author.id != ctx.me.id:
            raise commands.UserFeedbackCheckFailure("I can only edit messages sent by me.")
        if not data:
            data = await self._attachment_text(ctx, (conversion_type, "txt"))
        view = payload_to_view(load_payload(data, conversion_type))
        try:
            await message.edit(content=None, embeds=[], attachments=[], view=view)
        except discord.HTTPException as error:
            raise commands.UserFeedbackCheckFailure(f"Discord rejected the layout: {error}") from error
        await ctx.tick()

    @components_v2.command(name="download")
    async def components_v2_download(
        self,
        ctx: commands.Context,
        message: discord.Message,
    ) -> None:
        """Download a Components V2 message as reusable JSON."""
        if message.guild is None or message.guild.id != ctx.guild.id:
            raise commands.UserFeedbackCheckFailure("The message must be in this server.")
        if not message.channel.permissions_for(ctx.author).view_channel:
            raise commands.UserFeedbackCheckFailure("You cannot view that message's channel.")
        if not message.flags.components_v2:
            raise commands.UserFeedbackCheckFailure("That message does not use Components V2.")
        view = discord.ui.LayoutView.from_message(message, timeout=None)
        payload = json.dumps(view_to_payload(view), indent=2, ensure_ascii=False)
        await ctx.send(file=text_to_file(payload, filename="components-v2.json"))

    @components_v2.command(name="dashboard")
    async def components_v2_dashboard(self, ctx: commands.Context) -> None:
        """Open this cog's Components V2 dashboard editor."""
        dashboard_url = getattr(self.bot, "dashboard_url", None)
        dashboard = self.bot.get_cog("Dashboard")
        if dashboard_url is None or dashboard is None:
            raise commands.UserFeedbackCheckFailure("Red-Web-Dashboard is not installed and running.")
        if not dashboard_url[1] and ctx.author.id not in self.bot.owner_ids:
            raise commands.UserFeedbackCheckFailure("You cannot access the dashboard.")
        url = f"{dashboard_url[0]}/dashboard/{ctx.guild.id}/third-party/{self.qualified_name}"
        view = discord.ui.View()
        view.add_item(discord.ui.Button(label="Open Components V2 editor", url=url))
        await ctx.send("Build and send Components V2 messages from the dashboard:", view=view)

    async def _send_payload(
        self,
        ctx: commands.Context,
        payload: object,
        channel: discord.TextChannel | None,
    ) -> None:
        view = payload_to_view(payload)
        destination = channel or ctx.channel
        if channel is not None and not channel.permissions_for(ctx.author).send_messages:
            raise commands.UserFeedbackCheckFailure("You cannot send messages in that channel.")
        if not destination.permissions_for(ctx.me).send_messages:
            raise commands.BotMissingPermissions(["send_messages"])
        author_permissions = destination.permissions_for(ctx.author)
        allowed_mentions = discord.AllowedMentions(
            everyone=author_permissions.mention_everyone,
            users=True,
            roles=True,
            replied_user=False,
        )
        try:
            if channel is None:
                await ctx.send(view=view, allowed_mentions=allowed_mentions)
            else:
                message = await channel.send(view=view, allowed_mentions=allowed_mentions)
                await ctx.send(f"Sent Components V2 message: {message.jump_url}", ephemeral=True)
        except discord.HTTPException as error:
            raise commands.UserFeedbackCheckFailure(f"Discord rejected the layout: {error}") from error

    @staticmethod
    async def _attachment_text(ctx: commands.Context, extensions: tuple[str, ...]) -> str:
        attachments = getattr(ctx.message, "attachments", [])
        if not attachments:
            raise commands.UserInputError("Provide a payload or attach a JSON/YAML text file.")
        attachment = attachments[0]
        extension = attachment.filename.rsplit(".", 1)[-1].lower()
        if extension not in extensions:
            raise commands.UserInputError(f"Expected one of these file types: {', '.join(extensions)}.")
        if attachment.size > 256_000:
            raise commands.UserInputError("Payload files are limited to 256 KB.")
        try:
            return (await attachment.read()).decode("utf-8")
        except UnicodeDecodeError as error:
            raise commands.UserInputError("The attached payload must be UTF-8 text.") from error
