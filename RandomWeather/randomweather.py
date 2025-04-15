from typing import Dict, Any, Optional, cast
import discord
from discord.ext import tasks
import pytz
from datetime import datetime
import logging

from redbot.core import Config, commands
from redbot.core.bot import Red
from .weather_utils import generate_weather, create_weather_embed
from .time_utils import calculate_next_refresh_time, should_post_now, validate_timezone
from .file_utils import write_last_posted

class WeatherCog(commands.Cog):
    """A cog for generating random daily weather updates."""

    def __init__(self, bot: Red) -> None:
        self.bot = bot
        self.config = Config.get_conf(
            self, 
            identifier=1234567890,
            force_registration=True
        )
        
        default_guild: Dict[str, Any] = {
            "role_id": None,
            "channel_id": None,
            "tag_role": False,
            "refresh_interval": None,
            "refresh_time": None,
            "show_footer": True,
            "embed_color": 0xFF0000,
            "last_refresh": 0,
            "time_zone": "UTC"
        }
        self.config.register_guild(**default_guild)
        self._task = self.weather_update_loop.start()

    def cog_unload(self) -> None:
        """Clean up when cog shuts down."""
        if self._task:
            self._task.cancel()

    @tasks.loop(minutes=1)
    async def weather_update_loop(self) -> None:
        """Check and post weather updates."""
        await self.bot.wait_until_ready()
        
        try:
            all_guilds = await self.config.all_guilds()
            for guild_id, guild_settings in all_guilds.items():
                try:
                    channel_id = guild_settings.get("channel_id")
                    if not channel_id:
                        continue
                        
                    time_zone = cast(str, guild_settings.get("time_zone", "UTC"))
                    tz = pytz.timezone(time_zone)
                    now = datetime.now().astimezone(tz)
                    
                    refresh_time = guild_settings.get("refresh_time")
                    if refresh_time and isinstance(refresh_time, str):
                        target_hour = int(refresh_time[:2])
                        target_minute = int(refresh_time[2:])
                        if should_post_now(now, target_hour, target_minute):
                            await self._post_weather_update(guild_id, guild_settings, is_forced=True)
                            continue
                    
                    # Calculate next refresh based on interval or scheduled time
                    last_refresh = cast(int, guild_settings.get("last_refresh", 0))
                    refresh_interval = cast(Optional[int], guild_settings.get("refresh_interval"))
                    
                    next_post_time = calculate_next_refresh_time(
                        last_refresh,
                        refresh_interval,
                        refresh_time,
                        time_zone
                    )
                    
                    if next_post_time and now >= next_post_time:
                        await self._post_weather_update(
                            guild_id,
                            guild_settings,
                            scheduled_time=next_post_time.timestamp()
                        )
                except Exception as e:
                    logging.error(f"Error processing guild {guild_id}: {e}")
                    
        except Exception as e:
            logging.error(f"Error in weather update loop: {e}")

    async def _post_weather_update(
        self,
        guild_id: int,
        guild_settings: Dict[str, Any],
        scheduled_time: Optional[float] = None,
        is_forced: bool = False
    ) -> None:
        """Post a weather update."""
        try:
            time_zone = cast(str, guild_settings.get("time_zone", "UTC"))
            weather_data = generate_weather(time_zone)
            embed = create_weather_embed(weather_data, guild_settings)
            
            channel = self.bot.get_channel(guild_settings["channel_id"])
            if not isinstance(channel, discord.TextChannel):
                return
                
            content = None
            if guild_settings.get("tag_role"):
                role_id = guild_settings.get("role_id")
                if role_id:
                    content = f"<@&{role_id}>"
                    
            await channel.send(content=content, embed=embed)
            current_time = datetime.now(pytz.timezone(time_zone))
            guild = self.bot.get_guild(guild_id)
            if guild:
                await self.config.guild(guild).last_refresh.set(current_time.timestamp())
            write_last_posted()
            
        except Exception as e:
            logging.error(f"Error posting weather update for guild {guild_id}: {e}")

    @commands.group(name="rweather", invoke_without_command=True)
    @commands.guild_only()
    @commands.admin_or_permissions(administrator=True)
    async def rweather(self, ctx: commands.Context) -> None:
        """Weather management commands."""
        if ctx.invoked_subcommand is None:
            await ctx.send_help()

    @rweather.command(name="settimezone")
    @commands.guild_only()
    @commands.admin_or_permissions(administrator=True)
    async def set_timezone(self, ctx: commands.Context, timezone: str) -> None:
        """Set the timezone for weather updates."""
        if timezone in pytz.all_timezones:
            await self.config.guild(ctx.guild).time_zone.set(timezone)
            await ctx.send(f"Timezone set to: {timezone}")
        else:
            await ctx.send("Invalid timezone. See: https://en.wikipedia.org/wiki/List_of_tz_database_time_zones")

    @rweather.command(name="refresh")
    @commands.guild_only()
    @commands.admin_or_permissions(administrator=True)
    async def set_refresh(self, ctx: commands.Context, value: str) -> None:
        """Set refresh interval (10m, 1h) or time (1830)."""
        time_units = {"s": 1, "m": 60, "h": 3600, "d": 86400}
        
        # Handle military time
        if value.isdigit() and len(value) == 4:
            try:
                hour = int(value[:2])
                minute = int(value[2:])
                if hour > 23 or minute > 59:
                    await ctx.send("Invalid time format. Hours must be 00-23, minutes must be 00-59")
                    return
                
                await self.config.guild(ctx.guild).refresh_time.set(value)
                await self.config.guild(ctx.guild).refresh_interval.set(None)
                
                # Get current settings and check if we should post now
                guild_settings = await self.config.guild(ctx.guild).all()
                time_zone = guild_settings.get("time_zone") or "UTC"
                now = datetime.now(pytz.timezone(time_zone))
                
                if should_post_now(now, hour, minute):
                    await self._post_weather_update(ctx.guild.id, guild_settings, is_forced=True)
                    await ctx.send(f"Weather will refresh daily at {value}. Posted initial update since it's that time now.")
                else:
                    await ctx.send(f"Weather will refresh daily at {value}")
                return
            except ValueError:
                await ctx.send("Invalid time format. Use HHMM (e.g., 1830 for 6:30 PM)")
                return
        
        # Handle intervals
        if not value[-1] in time_units:
            await ctx.send("Invalid format. Use time (1830) or interval (10m, 1h)")
            return
            
        try:
            unit = value[-1]
            interval = int(value[:-1])
            refresh_interval = interval * time_units[unit]
            await self.config.guild(ctx.guild).refresh_interval.set(refresh_interval)
            await self.config.guild(ctx.guild).refresh_time.set(None)
            await ctx.send(f"Weather will refresh every {value}")
        except ValueError:
            await ctx.send("Invalid format. Use a number with s, m, h, or d")

    @rweather.command(name="channel")
    @commands.guild_only()
    @commands.admin_or_permissions(administrator=True)
    async def set_channel(self, ctx: commands.Context, channel: discord.TextChannel) -> None:
        """Set the channel for weather updates."""
        await self.config.guild(ctx.guild).channel_id.set(channel.id)
        await ctx.send(f"Weather updates will now be sent to {channel.mention}")

    @rweather.command(name="role")
    @commands.guild_only()
    @commands.admin_or_permissions(administrator=True)
    async def set_role(self, ctx: commands.Context, role: discord.Role) -> None:
        """Set the role to tag in weather updates."""
        await self.config.guild(ctx.guild).role_id.set(role.id)
        await ctx.send(f"Weather updates will now tag {role.name}")

    @rweather.command(name="toggle")
    @commands.guild_only()
    @commands.admin_or_permissions(administrator=True)
    async def toggle_role(self, ctx: commands.Context) -> None:
        """Toggle whether to tag the set role in weather updates."""
        current = await self.config.guild(ctx.guild).tag_role()
        await self.config.guild(ctx.guild).tag_role.set(not current)
        state = "disabled" if current else "enabled"
        await ctx.send(f"Role tagging has been {state}")

    @rweather.command(name="color")
    @commands.guild_only()
    @commands.admin_or_permissions(administrator=True)
    async def set_color(self, ctx: commands.Context, color: discord.Color) -> None:
        """Set the color for weather embed messages."""
        await self.config.guild(ctx.guild).embed_color.set(color.value)
        await ctx.send(f"Embed color set to: {str(color)}")

    @rweather.command(name="footer")
    @commands.guild_only()
    @commands.admin_or_permissions(administrator=True)
    async def toggle_footer(self, ctx: commands.Context) -> None:
        """Toggle whether to show the footer in weather updates."""
        current = await self.config.guild(ctx.guild).show_footer()
        await self.config.guild(ctx.guild).show_footer.set(not current)
        state = "disabled" if current else "enabled"
        await ctx.send(f"Footer has been {state}")

    @rweather.command(name="info")
    @commands.guild_only()
    async def info(self, ctx: commands.Context) -> None:
        """Show current weather settings."""
        guild_settings = await self.config.guild(ctx.guild).all()
        
        embed_color = discord.Color(guild_settings.get("embed_color", 0xFF0000))
        refresh_interval = guild_settings.get("refresh_interval")
        refresh_time = guild_settings.get("refresh_time")
        last_refresh = guild_settings.get("last_refresh", 0)
        time_zone = guild_settings.get("time_zone") or "UTC"
        tz = pytz.timezone(time_zone)
        
        embed = discord.Embed(
            title="🌦️ RandomWeather Settings",
            color=embed_color
        )
        
        # Get channel and role info
        channel = self.bot.get_channel(guild_settings.get("channel_id")) if guild_settings.get("channel_id") else None
        role = ctx.guild.get_role(guild_settings.get("role_id")) if guild_settings.get("role_id") else None
        
        # Add basic fields
        embed.add_field(name="📢 Channel:", value=channel.mention if channel else "❌ Not set", inline=True)
        embed.add_field(name="🔖 Tag Role:", value=role.name if role else "❌ Not set", inline=True)
        embed.add_field(name="🌍 Timezone:", value=time_zone, inline=True)
        
        # Add timing fields
        if refresh_time:
            embed.add_field(name="⏰ Update Time:", value=f"{refresh_time[:2]}:{refresh_time[2:]}", inline=True)
        elif refresh_interval:
            minutes = refresh_interval // 60
            if minutes < 60:
                timing = f"Every {minutes}m"
            else:
                hours = minutes // 60
                timing = f"Every {hours}h"
            embed.add_field(name="⏰ Update Interval:", value=timing, inline=True)
        else:
            embed.add_field(name="⏰ Updates:", value="Not configured", inline=True)
            
        # Calculate next post time
        if last_refresh or refresh_interval or refresh_time:
            next_post_time = calculate_next_refresh_time(last_refresh, refresh_interval, refresh_time, time_zone)
            if next_post_time is not None and hasattr(next_post_time, 'tzinfo') and next_post_time.tzinfo is not None:
                embed.add_field(name="📅 Next Update:", value=discord.utils.format_dt(next_post_time), inline=True)
        
        # Add toggle states
        embed.add_field(name="🏷️ Role Tagging:", value="✅ Enabled" if guild_settings.get("tag_role") else "❌ Disabled", inline=True)
        embed.add_field(name="📜 Footer:", value="✅ Enabled" if guild_settings.get("show_footer") else "❌ Disabled", inline=True)
        
        await ctx.send(embed=embed)

    @rweather.command(name="force")
    @commands.guild_only()
    @commands.admin_or_permissions(administrator=True)
    async def force_post(self, ctx: commands.Context) -> None:
        """Force a weather update to post now."""
        try:
            guild_settings = await self.config.guild(ctx.guild).all()
            channel_id = guild_settings.get("channel_id")
            
            if not channel_id:
                await ctx.send("No channel configured for weather updates.")
                return
            
            await self._post_weather_update(ctx.guild.id, guild_settings, is_forced=True)
            await ctx.send("Weather update posted.")
        except Exception as e:
            await ctx.send(f"Failed to post weather update: {e}")
            
async def setup(bot: Red) -> None:
    """Load WeatherCog."""
    await bot.add_cog(WeatherCog(bot))
