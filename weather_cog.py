import random
import discord  # Edited by Taako
from redbot.core import commands
from discord import app_commands  # Edited by Taako

class WeatherCog(commands.Cog):
    """A cog for generating random daily weather."""
    
    # Edited by Taako
    def __init__(self, bot):
        self._bot = bot  # Store the bot instance
        self._current_weather = self._generate_weather()  # Generate initial weather
        self._role_id = None  # Role ID for tagging
        self._channel_id = None  # Channel ID for sending updates
        self._tag_role = False  # Whether to tag the role

    def _generate_weather(self):
        """Generate realistic random weather."""
        # Edited by Taako
        temperature = random.randint(30, 100)  # Temperature in °F
        feels_like = temperature + random.randint(-3, 3)  # Feels like temperature
        conditions = random.choice(["Clear sky", "Partly cloudy", "Overcast", "Rainy", "Stormy", "Snowy"])
        wind_speed = round(random.uniform(0.5, 20.0), 1)  # Wind speed in mph
        wind_direction = random.choice(["N", "NE", "E", "SE", "S", "SW", "W", "NW"])
        pressure = random.randint(980, 1050)  # Pressure in hPa
        humidity = random.randint(20, 100)  # Humidity in %
        dew_point = round(temperature - ((100 - humidity) / 5), 1)  # Dew point in °F

        # Adjust visibility based on conditions
        if conditions == "Clear sky":
            visibility = round(random.uniform(5.0, 6.2), 1)  # High visibility in miles
        elif conditions in ["Partly cloudy", "Overcast"]:
            visibility = round(random.uniform(3.1, 5.0), 1)  # Moderate visibility in miles
        elif conditions in ["Rainy", "Stormy"]:
            visibility = round(random.uniform(0.6, 3.1), 1)  # Low visibility in miles
        elif conditions == "Snowy":
            visibility = round(random.uniform(0.3, 1.9), 1)  # Very low visibility in miles
        else:
            visibility = round(random.uniform(0.6, 6.2), 1)  # Default fallback in miles

        return {
            "temperature": f"{temperature}°F",
            "feels_like": f"{feels_like}°F",
            "conditions": conditions,
            "wind": f"{wind_speed} mph {wind_direction}",
            "pressure": f"{pressure} hPa",
            "humidity": f"{humidity}%",
            "dew_point": f"{dew_point}°F",
            "visibility": f"{visibility} miles",  # Updated to miles
        }

    def _create_weather_embed(self, weather_data):
        """Create a Discord embed for the weather data."""
        # Edited by Taako
        embed = discord.Embed(title="Today's Weather", color=discord.Color.blue())
        embed.add_field(name="Temperature", value=weather_data["temperature"], inline=True)
        embed.add_field(name="Feels Like", value=weather_data["feels_like"], inline=True)
        embed.add_field(name="Conditions", value=weather_data["conditions"], inline=False)
        embed.add_field(name="Wind", value=weather_data["wind"], inline=True)
        embed.add_field(name="Pressure", value=weather_data["pressure"], inline=True)
        embed.add_field(name="Humidity", value=weather_data["humidity"], inline=True)
        embed.add_field(name="Dew Point", value=weather_data["dew_point"], inline=True)
        embed.add_field(name="Visibility", value=weather_data["visibility"], inline=True)
        return embed

    @commands.group()
    async def weather(self, ctx):
        """Main weather command."""
        # Edited by Taako
        if ctx.invoked_subcommand is None:
            embed = self._create_weather_embed(self._current_weather)
            role_mention = f"<@&{self._role_id}>" if self._role_id and self._tag_role else ""
            if self._channel_id:
                channel = self._bot.get_channel(self._channel_id)
                if channel:
                    await channel.send(content=role_mention, embed=embed)
                    await ctx.send(f"Weather update sent to {channel.mention}.")
                else:
                    await ctx.send("The set channel is invalid. Please set a valid channel.")
            else:
                await ctx.send(embed=embed)

    @weather.command()
    async def refresh(self, ctx):
        """Refresh the weather for the day."""
        # Edited by Taako
        self._current_weather = self._generate_weather()
        embed = self._create_weather_embed(self._current_weather)
        role_mention = f"<@&{self._role_id}>" if self._role_id and self._tag_role else ""
        if self._channel_id:
            channel = self._bot.get_channel(self._channel_id)
            if channel:
                await channel.send(content=role_mention, embed=embed)
                await ctx.send(f"Weather update sent to {channel.mention}.")
            else:
                await ctx.send("The set channel is invalid. Please set a valid channel.")
        else:
            await ctx.send(embed=embed)

    @weather.command()
    async def role(self, ctx, role_id: int):
        """Set the role to be tagged for weather updates."""
        # Edited by Taako
        role = ctx.guild.get_role(role_id)
        if role:
            self._role_id = role_id
            await ctx.send(f"Weather updates will now tag the role: {role.name}")
        else:
            await ctx.send("Invalid role ID. Please provide a valid role ID.")

    @weather.command()
    async def toggle(self, ctx):
        """Toggle whether the role should be tagged in weather updates."""
        # Edited by Taako
        self._tag_role = not self._tag_role
        status = "enabled" if self._tag_role else "disabled"
        await ctx.send(f"Role tagging has been {status}.")

    @weather.command()
    async def channel(self, ctx, channel_id: int):
        """Set the channel for weather updates."""
        # Edited by Taako
        channel = self._bot.get_channel(channel_id)
        if channel:
            self._channel_id = channel_id
            await ctx.send(f"Weather updates will now be sent to: {channel.mention}")
        else:
            await ctx.send("Invalid channel ID. Please provide a valid channel ID.")

    @app_commands.command(name="weather")
    async def slash_weather(self, interaction: discord.Interaction):
        """Slash command to view the current weather."""
        # Edited by Taako
        embed = self._create_weather_embed(self._current_weather)
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="refresh")
    async def slash_refresh(self, interaction: discord.Interaction):
        """Slash command to refresh the weather."""
        # Edited by Taako
        self._current_weather = self._generate_weather()
        embed = self._create_weather_embed(self._current_weather)
        await interaction.response.send_message("Weather refreshed!", embed=embed)

    @app_commands.command(name="role")
    async def slash_role(self, interaction: discord.Interaction, role: discord.Role):
        """Slash command to set the role for weather updates."""
        # Edited by Taako
        self._role_id = role.id
        await interaction.response.send_message(f"Weather updates will now tag the role: {role.name}")

    @app_commands.command(name="toggle")
    async def slash_toggle(self, interaction: discord.Interaction):
        """Slash command to toggle role tagging."""
        # Edited by Taako
        self._tag_role = not self._tag_role
        status = "enabled" if self._tag_role else "disabled"
        await interaction.response.send_message(f"Role tagging has been {status}.")

    @app_commands.command(name="channel")
    async def slash_channel(self, interaction: discord.Interaction, channel: discord.TextChannel):
        """Slash command to set the channel for weather updates."""
        # Edited by Taako
        self._channel_id = channel.id
        await interaction.response.send_message(f"Weather updates will now be sent to: {channel.mention}")

    async def cog_load(self):
        """Register slash commands when the cog is loaded."""
        # Edited by Taako
        guild = discord.Object(id=YOUR_GUILD_ID)  # Replace with your guild ID for testing
        self._bot.tree.add_command(self.slash_weather, guild=guild)
        self._bot.tree.add_command(self.slash_refresh, guild=guild)
        self._bot.tree.add_command(self.slash_role, guild=guild)
        self._bot.tree.add_command(self.slash_toggle, guild=guild)
        self._bot.tree.add_command(self.slash_channel, guild=guild)
        await self._bot.tree.sync(guild=guild)

    async def cog_unload(self):
        """Unregister slash commands when the cog is unloaded."""
        # Edited by Taako
        guild = discord.Object(id=YOUR_GUILD_ID)  # Replace with your guild ID for testing
        self._bot.tree.remove_command("weather", guild=guild)
        self._bot.tree.remove_command("refresh", guild=guild)
        self._bot.tree.remove_command("role", guild=guild)
        self._bot.tree.remove_command("toggle", guild=guild)
        self._bot.tree.remove_command("channel", guild=guild)
        await self._bot.tree.sync(guild=guild)

def setup(bot):
    # Edited by Taako
    bot.add_cog(WeatherCog(bot))
