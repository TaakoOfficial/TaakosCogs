import discord
from redbot.core import commands

class ZodiacColorRoles(commands.Cog):
    """Cog for easy creation of zodiac and color roles."""

    ZODIAC_SIGNS = [
        "Aries", "Taurus", "Gemini", "Cancer", "Leo", "Virgo",
        "Libra", "Scorpio", "Sagittarius", "Capricorn", "Aquarius", "Pisces"
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
        "Navy": "#000080"
    }

    def __init__(self, bot):
        self.bot = bot

    @commands.hybrid_command(name="listzodiacroles", description="List all available zodiac roles.")
    async def listzodiacroles(self, ctx: commands.Context):
        """List all zodiac roles the bot can create."""
        zodiac_list = ", ".join(self.ZODIAC_SIGNS)
        await ctx.send(f"Available zodiac roles: {zodiac_list}", ephemeral=True if ctx.interaction else False)

    @commands.hybrid_command(name="listcolorroles", description="List all available color roles.")
    async def listcolorroles(self, ctx: commands.Context):
        """List all color roles the bot can create."""
        color_list = ", ".join(f"{name} ({hexcode})" for name, hexcode in self.COLOR_CHOICES.items())
        await ctx.send(f"Available color roles: {color_list}", ephemeral=True if ctx.interaction else False)

    @commands.hybrid_command(name="addzodiacrole", description="Create a zodiac role for a user, or all zodiac roles.")
    async def addzodiacrole(self, ctx: commands.Context, zodiac: str):
        """Add a zodiac role or all zodiac roles to the server."""
        guild = ctx.guild
        member = ctx.author
        zodiac = zodiac.title()
        if zodiac.lower() == "all":
            added_roles = []
            for sign in self.ZODIAC_SIGNS:
                role_name = f"{sign}"
                role = discord.utils.get(guild.roles, name=role_name)
                if not role:
                    role = await guild.create_role(name=role_name)
                added_roles.append(role_name)
            await ctx.send(
                f"Added all zodiac roles: {', '.join(added_roles)}", ephemeral=True if ctx.interaction else False
            )
            return
        if zodiac not in self.ZODIAC_SIGNS:
            await ctx.send(
                f"Invalid zodiac sign. Use `/listzodiacroles` to see valid options.", ephemeral=True if ctx.interaction else False
            )
            return
        role_name = f"{zodiac}"
        role = discord.utils.get(guild.roles, name=role_name)
        if not role:
            role = await guild.create_role(name=role_name)
        await ctx.send(f"Added zodiac role: {role_name}", ephemeral=True if ctx.interaction else False)

    @commands.hybrid_command(name="addcolorrole", description="Create a color role for a user, or all color roles.")
    async def addcolorrole(self, ctx: commands.Context, color: str):
        """Add a color role or all color roles to the server."""
        guild = ctx.guild
        member = ctx.author
        color_name = color.title()
        if color_name.lower() == "all":
            added_roles = []
            for name, hex_code in self.COLOR_CHOICES.items():
                role_name = f"Color {name}"
                role = discord.utils.get(guild.roles, name=role_name)
                if not role:
                    discord_color = discord.Color(int(hex_code.lstrip("#"), 16))
                    role = await guild.create_role(name=role_name, color=discord_color)
                added_roles.append(role_name)
            await ctx.send(
                f"Added all color roles: {', '.join(added_roles)}", ephemeral=True if ctx.interaction else False
            )
            return
        if color_name not in self.COLOR_CHOICES:
            await ctx.send(
                f"Invalid color. Use `/listcolorroles` to see valid options.", ephemeral=True if ctx.interaction else False
            )
            return
        hex_code = self.COLOR_CHOICES[color_name]
        role_name = f"Color {color_name}"
        role = discord.utils.get(guild.roles, name=role_name)
        if not role:
            discord_color = discord.Color(int(hex_code.lstrip("#"), 16))
            role = await guild.create_role(name=role_name, color=discord_color)
        await ctx.send(f"Added color role: {role_name}", ephemeral=True if ctx.interaction else False)