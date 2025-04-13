import discord  # Edited by Taako
from redbot.core import commands, Config  # Edited by Taako
from datetime import datetime, timedelta  # Edited by Taako
import pytz  # Edited by Taako
from discord.ext import tasks  # Edited by Taako

class RPCalander(commands.Cog):
    """A cog for managing an RP calendar with daily updates."""  # Edited by Taako

    def __init__(self, bot):
        self._bot = bot  # Edited by Taako
        self.config = Config.get_conf(self, identifier=9876543210, force_registration=True)  # Edited by Taako
        default_guild = {
            "start_date": None,  # Starting date (MM-DD-YYYY)  # Edited by Taako
            "channel_id": None,  # Channel ID for updates
            "current_date": None,  # Current date in the calendar
            "time_zone": "America/Chicago",  # Default time zone  # Edited by Taako
            "embed_color": 0x0000FF,  # Default embed color (blue)  # Edited by Taako
            "show_footer": True,  # Whether to show the footer in the main embed  # Edited by Taako
        }
        self.config.register_guild(**default_guild)
        self._daily_update_loop.start()  # Start the daily update loop

    @tasks.loop(hours=24)
    async def _daily_update_loop(self):
        """Task loop to post daily calendar updates."""  # Edited by Taako
        all_guilds = await self.config.all_guilds()
        for guild_id, guild_settings in all_guilds.items():
            channel_id = guild_settings["channel_id"]
            if not channel_id:
                continue

            current_date = guild_settings["current_date"]
            time_zone = guild_settings["time_zone"] or "America/Chicago"  # Edited by Taako
            embed_color = guild_settings["embed_color"] or 0x0000FF  # Default to blue  # Edited by Taako
            show_footer = guild_settings["show_footer"]  # Edited by Taako
            if not current_date:
                continue

            # Increment the current date
            tz = pytz.timezone(time_zone)  # Edited by Taako
            current_date_obj = datetime.strptime(current_date, "%m-%d-%Y").astimezone(tz)  # Edited by Taako
            next_date_obj = current_date_obj + timedelta(days=1)
            next_date_str = next_date_obj.strftime("%m-%d-%Y")  # Edited by Taako
            day_of_week = next_date_obj.strftime("%A")

            # Update the stored current date
            await self.config.guild_from_id(guild_id).current_date.set(next_date_str)

            # Create and send the embed
            embed = discord.Embed(
                title="📅 RP Calendar Update",
                description=f"Today's date: **{next_date_str} ({day_of_week})**",
                color=discord.Color(embed_color)  # Use the configured embed color  # Edited by Taako
            )
            if show_footer:  # Add footer if enabled  # Edited by Taako
                embed.set_footer(text="RP Calendar by Taako", icon_url="https://cdn-icons-png.flaticon.com/512/869/869869.png")
            channel = self._bot.get_channel(channel_id)
            if channel:
                await channel.send(embed=embed)

    @rpcalander.command(name="togglefooter")
    async def toggle_footer(self, ctx):
        """Toggle the footer on or off for the main embed."""  # Edited by Taako
        show_footer = await self.config.guild(ctx.guild).show_footer()
        new_state = not show_footer
        await self.config.guild(ctx.guild).show_footer.set(new_state)
        status = "enabled" if new_state else "disabled"
        await ctx.send(f"The footer has been {status} for the main embed.")  # Edited by Taako

    @rpcalander.command(name="info")
    async def info(self, ctx):
        """View the current settings for the RP calendar."""  # Edited by Taako
        guild_settings = await self.config.guild(ctx.guild).all()
        start_date = guild_settings["start_date"] or "Not set"
        current_date = guild_settings["current_date"] or "Not set"
        channel_id = guild_settings["channel_id"]
        channel = f"<#{channel_id}>" if channel_id else "Not set"
        time_zone = guild_settings["time_zone"] or "America/Chicago"  # Edited by Taako
        embed_color = discord.Color(guild_settings["embed_color"])  # Edited by Taako

        embed = discord.Embed(
            title="📅 RP Calendar Settings",
            color=embed_color  # Use the configured embed color  # Edited by Taako
        )
        embed.add_field(name="Start Date", value=start_date, inline=False)
        embed.add_field(name="Current Date", value=current_date, inline=False)
        embed.add_field(name="Update Channel", value=channel, inline=False)
        embed.add_field(name="Time Zone", value=time_zone, inline=False)
        embed.add_field(name="Embed Color", value=str(embed_color), inline=False)  # Edited by Taako
        embed.set_footer(text="RP Calendar by Taako", icon_url="https://cdn-icons-png.flaticon.com/512/869/869869.png")  # Always show footer in info embed  # Edited by Taako
        await ctx.send(embed=embed)
