"""EmojiPorter Cog - Copy emojis and stickers between Discord servers."""

import asyncio
import aiohttp
import discord
from redbot.core import commands
from typing import Optional, List

__red_end_user_data_statement__ = "This cog does not persistently store any end user data."


class EmojiPorter(commands.Cog):
    """Copy emojis and stickers between Discord servers."""

    def __init__(self, bot):
        self.bot = bot

    async def _check_permissions(self, ctx: commands.Context, manage_emojis: bool = True) -> bool:
        """Check if the bot has necessary permissions."""
        required_perms = []
        
        if manage_emojis and not ctx.guild.me.guild_permissions.manage_emojis_and_stickers:
            required_perms.append("Manage Emojis and Stickers")
            
        if required_perms:
            await ctx.send(
                f"I need the following permissions: {', '.join(required_perms)}", 
                ephemeral=True if ctx.interaction else False
            )
            return False
        return True

    async def _download_asset(self, url: str) -> bytes:
        """Download an asset from a URL."""
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                if response.status == 200:
                    return await response.read()
                else:
                    raise aiohttp.ClientError(f"Failed to download asset: HTTP {response.status}")

    async def _copy_emoji(self, source_emoji: discord.Emoji, target_guild: discord.Guild) -> Optional[discord.Emoji]:
        """Copy a single emoji to the target guild."""
        try:
            # Check if emoji already exists
            existing = discord.utils.get(target_guild.emojis, name=source_emoji.name)
            if existing:
                return existing

            # Download emoji image
            image_data = await self._download_asset(str(source_emoji.url))
            
            # Create emoji in target guild
            new_emoji = await target_guild.create_custom_emoji(
                name=source_emoji.name,
                image=image_data,
                reason="Copied via EmojiPorter"
            )
            return new_emoji
            
        except discord.Forbidden:
            raise commands.BotMissingPermissions(["manage_emojis_and_stickers"])
        except discord.HTTPException as e:
            if e.code == 30008:  # Maximum number of emojis reached
                raise commands.CommandError(f"Target server has reached emoji limit")
            elif e.code == 50045:  # File too large
                raise commands.CommandError(f"Emoji '{source_emoji.name}' is too large")
            else:
                raise commands.CommandError(f"Failed to copy emoji '{source_emoji.name}': {e}")
        except Exception as e:
            raise commands.CommandError(f"Unexpected error copying emoji '{source_emoji.name}': {e}")

    async def _copy_sticker(self, source_sticker: discord.GuildSticker, target_guild: discord.Guild) -> Optional[discord.GuildSticker]:
        """Copy a single sticker to the target guild."""
        try:
            # Check if sticker already exists
            existing = discord.utils.get(target_guild.stickers, name=source_sticker.name)
            if existing:
                return existing

            # Download sticker file
            file_data = await self._download_asset(str(source_sticker.url))
            
            # Create sticker in target guild
            new_sticker = await target_guild.create_sticker(
                name=source_sticker.name,
                description=source_sticker.description or "Imported sticker",
                emoji=source_sticker.emoji,
                file=discord.File(fp=file_data, filename=f"{source_sticker.name}.png"),
                reason="Copied via EmojiPorter"
            )
            return new_sticker
            
        except discord.Forbidden:
            raise commands.BotMissingPermissions(["manage_emojis_and_stickers"])
        except discord.HTTPException as e:
            if e.code == 30039:  # Maximum number of stickers reached
                raise commands.CommandError(f"Target server has reached sticker limit")
            else:
                raise commands.CommandError(f"Failed to copy sticker '{source_sticker.name}': {e}")
        except Exception as e:
            raise commands.CommandError(f"Unexpected error copying sticker '{source_sticker.name}': {e}")

    @commands.hybrid_command(name="copyemojis", description="Copy emojis from source server to current server.")
    @commands.guild_only()
    async def copyemojis(self, ctx: commands.Context, source_guild_id: int, emoji_names: Optional[str] = None):
        """
        Copy emojis from another server to this server.
        
        Parameters:
        - source_guild_id: The ID of the server to copy emojis from
        - emoji_names: Optional comma-separated list of specific emoji names to copy (default: all)
        """
        if not await self._check_permissions(ctx):
            return

        # Get source guild
        source_guild = self.bot.get_guild(source_guild_id)
        if not source_guild:
            await ctx.send("❌ Source server not found or bot is not in that server.", ephemeral=True if ctx.interaction else False)
            return

        target_guild = ctx.guild
        
        # Check if bot is in both guilds
        if not source_guild.get_member(self.bot.user.id):
            await ctx.send("❌ Bot is not in the source server.", ephemeral=True if ctx.interaction else False)
            return

        # Get emojis to copy
        if emoji_names:
            requested_names = [name.strip() for name in emoji_names.split(",")]
            emojis_to_copy = [emoji for emoji in source_guild.emojis if emoji.name in requested_names]
            if len(emojis_to_copy) != len(requested_names):
                found_names = [emoji.name for emoji in emojis_to_copy]
                missing = [name for name in requested_names if name not in found_names]
                await ctx.send(f"⚠️ Could not find emojis: {', '.join(missing)}", ephemeral=True if ctx.interaction else False)
        else:
            emojis_to_copy = source_guild.emojis

        if not emojis_to_copy:
            await ctx.send("❌ No emojis found to copy.", ephemeral=True if ctx.interaction else False)
            return

        # Send initial message
        progress_msg = await ctx.send(f"🔄 Starting to copy {len(emojis_to_copy)} emoji(s)...")

        copied = []
        failed = []
        skipped = []

        for emoji in emojis_to_copy:
            try:
                result = await self._copy_emoji(emoji, target_guild)
                if result:
                    if discord.utils.get(target_guild.emojis, name=emoji.name):
                        if result.created_at == emoji.created_at:
                            copied.append(emoji.name)
                        else:
                            skipped.append(f"{emoji.name} (already exists)")
                    else:
                        copied.append(emoji.name)
                else:
                    skipped.append(f"{emoji.name} (already exists)")
                    
            except (commands.CommandError, commands.BotMissingPermissions) as e:
                failed.append(f"{emoji.name}: {str(e)}")
            
            # Small delay to avoid rate limits
            await asyncio.sleep(0.5)

        # Update final message
        result_parts = []
        if copied:
            result_parts.append(f"✅ **Copied ({len(copied)}):** {', '.join(copied)}")
        if skipped:
            result_parts.append(f"⏭️ **Skipped ({len(skipped)}):** {', '.join(skipped)}")
        if failed:
            result_parts.append(f"❌ **Failed ({len(failed)}):** {', '.join(failed)}")

        final_message = "\n".join(result_parts) if result_parts else "No emojis were processed."
        
        # Discord has a 2000 character limit, so truncate if needed
        if len(final_message) > 1900:
            final_message = final_message[:1900] + "...\n*Message truncated due to length*"
            
        await progress_msg.edit(content=final_message)

    @commands.hybrid_command(name="copystickers", description="Copy stickers from source server to current server.")
    @commands.guild_only()
    async def copystickers(self, ctx: commands.Context, source_guild_id: int, sticker_names: Optional[str] = None):
        """
        Copy stickers from another server to this server.
        
        Parameters:
        - source_guild_id: The ID of the server to copy stickers from
        - sticker_names: Optional comma-separated list of specific sticker names to copy (default: all)
        """
        if not await self._check_permissions(ctx):
            return

        # Get source guild
        source_guild = self.bot.get_guild(source_guild_id)
        if not source_guild:
            await ctx.send("❌ Source server not found or bot is not in that server.", ephemeral=True if ctx.interaction else False)
            return

        target_guild = ctx.guild

        # Check if bot is in both guilds
        if not source_guild.get_member(self.bot.user.id):
            await ctx.send("❌ Bot is not in the source server.", ephemeral=True if ctx.interaction else False)
            return

        # Get stickers to copy
        if sticker_names:
            requested_names = [name.strip() for name in sticker_names.split(",")]
            stickers_to_copy = [sticker for sticker in source_guild.stickers if sticker.name in requested_names]
            if len(stickers_to_copy) != len(requested_names):
                found_names = [sticker.name for sticker in stickers_to_copy]
                missing = [name for name in requested_names if name not in found_names]
                await ctx.send(f"⚠️ Could not find stickers: {', '.join(missing)}", ephemeral=True if ctx.interaction else False)
        else:
            stickers_to_copy = source_guild.stickers

        if not stickers_to_copy:
            await ctx.send("❌ No stickers found to copy.", ephemeral=True if ctx.interaction else False)
            return

        # Send initial message
        progress_msg = await ctx.send(f"🔄 Starting to copy {len(stickers_to_copy)} sticker(s)...")

        copied = []
        failed = []
        skipped = []

        for sticker in stickers_to_copy:
            try:
                result = await self._copy_sticker(sticker, target_guild)
                if result:
                    if discord.utils.get(target_guild.stickers, name=sticker.name):
                        if result.created_at == sticker.created_at:
                            copied.append(sticker.name)
                        else:
                            skipped.append(f"{sticker.name} (already exists)")
                    else:
                        copied.append(sticker.name)
                else:
                    skipped.append(f"{sticker.name} (already exists)")
                    
            except (commands.CommandError, commands.BotMissingPermissions) as e:
                failed.append(f"{sticker.name}: {str(e)}")
            
            # Small delay to avoid rate limits
            await asyncio.sleep(0.5)

        # Update final message
        result_parts = []
        if copied:
            result_parts.append(f"✅ **Copied ({len(copied)}):** {', '.join(copied)}")
        if skipped:
            result_parts.append(f"⏭️ **Skipped ({len(skipped)}):** {', '.join(skipped)}")
        if failed:
            result_parts.append(f"❌ **Failed ({len(failed)}):** {', '.join(failed)}")

        final_message = "\n".join(result_parts) if result_parts else "No stickers were processed."
        
        # Discord has a 2000 character limit, so truncate if needed
        if len(final_message) > 1900:
            final_message = final_message[:1900] + "...\n*Message truncated due to length*"
            
        await progress_msg.edit(content=final_message)

    @commands.hybrid_command(name="listemojis", description="List all emojis in a server.")
    @commands.guild_only()
    async def listemojis(self, ctx: commands.Context, guild_id: Optional[int] = None):
        """List all emojis in the current server or another server."""
        target_guild = ctx.guild if guild_id is None else self.bot.get_guild(guild_id)
        
        if not target_guild:
            await ctx.send("❌ Server not found or bot is not in that server.", ephemeral=True if ctx.interaction else False)
            return

        if not target_guild.emojis:
            await ctx.send(f"📭 No custom emojis found in **{target_guild.name}**.", ephemeral=True if ctx.interaction else False)
            return

        emoji_list = []
        static_count = 0
        animated_count = 0
        
        for emoji in target_guild.emojis:
            if emoji.animated:
                animated_count += 1
                emoji_list.append(f"<a:{emoji.name}:{emoji.id}> `{emoji.name}`")
            else:
                static_count += 1
                emoji_list.append(f"<:{emoji.name}:{emoji.id}> `{emoji.name}`")

        # Create embed
        embed = discord.Embed(
            title=f"📊 Emojis in {target_guild.name}",
            description=f"**Total:** {len(target_guild.emojis)} emojis\n**Static:** {static_count} | **Animated:** {animated_count}",
            color=discord.Color.blue()
        )

        # Split emoji list into chunks to fit Discord's field limits
        chunk_size = 20
        for i in range(0, len(emoji_list), chunk_size):
            chunk = emoji_list[i:i + chunk_size]
            field_name = f"Emojis ({i+1}-{min(i+chunk_size, len(emoji_list))})"
            embed.add_field(
                name=field_name,
                value="\n".join(chunk),
                inline=True
            )

        embed.set_footer(text=f"Server ID: {target_guild.id}")
        await ctx.send(embed=embed, ephemeral=True if ctx.interaction else False)

    @commands.hybrid_command(name="liststickers", description="List all stickers in a server.")
    @commands.guild_only()
    async def liststickers(self, ctx: commands.Context, guild_id: Optional[int] = None):
        """List all stickers in the current server or another server."""
        target_guild = ctx.guild if guild_id is None else self.bot.get_guild(guild_id)
        
        if not target_guild:
            await ctx.send("❌ Server not found or bot is not in that server.", ephemeral=True if ctx.interaction else False)
            return

        if not target_guild.stickers:
            await ctx.send(f"📭 No custom stickers found in **{target_guild.name}**.", ephemeral=True if ctx.interaction else False)
            return

        sticker_info = []
        for sticker in target_guild.stickers:
            sticker_info.append(f"🏷️ **{sticker.name}**\n└ *{sticker.description or 'No description'}*")

        # Create embed
        embed = discord.Embed(
            title=f"🏷️ Stickers in {target_guild.name}",
            description=f"**Total:** {len(target_guild.stickers)} stickers",
            color=discord.Color.green()
        )

        # Split sticker list into chunks to fit Discord's field limits
        chunk_size = 10
        for i in range(0, len(sticker_info), chunk_size):
            chunk = sticker_info[i:i + chunk_size]
            field_name = f"Stickers ({i+1}-{min(i+chunk_size, len(sticker_info))})"
            embed.add_field(
                name=field_name,
                value="\n".join(chunk),
                inline=False
            )

        embed.set_footer(text=f"Server ID: {target_guild.id}")
        await ctx.send(embed=embed, ephemeral=True if ctx.interaction else False)