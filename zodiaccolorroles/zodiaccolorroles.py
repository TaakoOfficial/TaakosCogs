import discord
from redbot.core import commands

__red_end_user_data_statement__ = "This cog does not persistently store any end user data."

class ZodiacColorRoles(commands.Cog):
    """Cog for easy creation of zodiac and color roles."""
    PRONOUN_ROLES = [
        "he/him",
        "she/her",
        "they/them",
        "any pronouns",
        "ask me",
        "xe/xem",
        "ze/zir"
    ]

    COMMON_PING_ROLES = [
        "Common Ping",
        "No Pings",
        "Ping on Important",
        "Ping for Events"
    ]

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

    async def _check_permissions(self, ctx: commands.Context) -> bool:
        """Check if the bot has permission to manage roles."""
        if not ctx.guild.me.guild_permissions.manage_roles:
            await ctx.send("I need the 'Manage Roles' permission to create roles.", ephemeral=True if ctx.interaction else False)
            return False
        return True

    async def _create_role_safely(self, guild: discord.Guild, name: str, color: discord.Color = None) -> discord.Role:
        """Safely create a role with error handling."""
        try:
            if color:
                return await guild.create_role(name=name, color=color)
            else:
                return await guild.create_role(name=name)
        except discord.Forbidden:
            raise commands.BotMissingPermissions(["manage_roles"])
        except discord.HTTPException as e:
            raise commands.CommandError(f"Failed to create role due to Discord API error: {e}")

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
        if not await self._check_permissions(ctx):
            return
            
        guild = ctx.guild
        zodiac = zodiac.title()
        
        if zodiac.lower() == "all":
            added_roles = []
            failed_roles = []
            for sign in self.ZODIAC_SIGNS:
                role_name = f"{sign}"
                role = discord.utils.get(guild.roles, name=role_name)
                if not role:
                    try:
                        role = await self._create_role_safely(guild, role_name)
                        added_roles.append(role_name)
                    except (commands.BotMissingPermissions, commands.CommandError) as e:
                        failed_roles.append(role_name)
                else:
                    added_roles.append(role_name)
            
            if added_roles:
                await ctx.send(
                    f"Added zodiac roles: {', '.join(added_roles)}", ephemeral=True if ctx.interaction else False
                )
            if failed_roles:
                await ctx.send(
                    f"Failed to create: {', '.join(failed_roles)}", ephemeral=True if ctx.interaction else False
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
            try:
                role = await self._create_role_safely(guild, role_name)
                await ctx.send(f"Added zodiac role: {role_name}", ephemeral=True if ctx.interaction else False)
            except (commands.BotMissingPermissions, commands.CommandError) as e:
                await ctx.send(f"Failed to create role: {e}", ephemeral=True if ctx.interaction else False)
        else:
            await ctx.send(f"Zodiac role already exists: {role_name}", ephemeral=True if ctx.interaction else False)

    @commands.hybrid_command(name="addcolorrole", description="Create a color role for a user, or all color roles.")
    async def addcolorrole(self, ctx: commands.Context, color: str):
        """Add a color role or all color roles to the server."""
        if not await self._check_permissions(ctx):
            return
            
        guild = ctx.guild
        color_name = color.title()
        
        if color_name.lower() == "all":
            added_roles = []
            failed_roles = []
            for name, hex_code in self.COLOR_CHOICES.items():
                role_name = f"Color {name}"
                role = discord.utils.get(guild.roles, name=role_name)
                if not role:
                    try:
                        discord_color = discord.Color(int(hex_code.lstrip("#"), 16))
                        role = await self._create_role_safely(guild, role_name, discord_color)
                        added_roles.append(role_name)
                    except (commands.BotMissingPermissions, commands.CommandError) as e:
                        failed_roles.append(role_name)
                else:
                    added_roles.append(role_name)
            
            if added_roles:
                await ctx.send(
                    f"Added color roles: {', '.join(added_roles)}", ephemeral=True if ctx.interaction else False
                )
            if failed_roles:
                await ctx.send(
                    f"Failed to create: {', '.join(failed_roles)}", ephemeral=True if ctx.interaction else False
                )
            return
        
        if color_name not in self.COLOR_CHOICES:
            await ctx.send(
                f"Invalid color. Use `/listcolorroles` to see valid options.", ephemeral=True if ctx.interaction else False
            )
            return
        
        role_name = f"Color {color_name}"
        role = discord.utils.get(guild.roles, name=role_name)
        if not role:
            try:
                hex_code = self.COLOR_CHOICES[color_name]
                discord_color = discord.Color(int(hex_code.lstrip("#"), 16))
                role = await self._create_role_safely(guild, role_name, discord_color)
                await ctx.send(f"Added color role: {role_name}", ephemeral=True if ctx.interaction else False)
            except (commands.BotMissingPermissions, commands.CommandError) as e:
                await ctx.send(f"Failed to create role: {e}", ephemeral=True if ctx.interaction else False)
        else:
            await ctx.send(f"Color role already exists: {role_name}", ephemeral=True if ctx.interaction else False)

    @commands.hybrid_command(name="addpronounrole", description="Create a pronoun role or all pronoun roles on the server.")
    async def addpronounrole(self, ctx: commands.Context, pronoun: str):
        """Add a pronoun role or all pronoun roles to the server."""
        if not await self._check_permissions(ctx):
            return
            
        guild = ctx.guild
        pronoun_name = pronoun.strip().lower()
        
        if pronoun_name == "all":
            added_roles = []
            failed_roles = []
            for role_name in self.PRONOUN_ROLES:
                role = discord.utils.get(guild.roles, name=role_name)
                if not role:
                    try:
                        role = await self._create_role_safely(guild, role_name)
                        added_roles.append(role_name)
                    except (commands.BotMissingPermissions, commands.CommandError) as e:
                        failed_roles.append(role_name)
                else:
                    added_roles.append(role_name)
            
            if added_roles:
                await ctx.send(
                    f"Added pronoun roles: {', '.join(added_roles)}", ephemeral=True if ctx.interaction else False
                )
            if failed_roles:
                await ctx.send(
                    f"Failed to create: {', '.join(failed_roles)}", ephemeral=True if ctx.interaction else False
                )
            return
            
        valid_names = [r.lower() for r in self.PRONOUN_ROLES]
        if pronoun_name not in valid_names:
            await ctx.send(
                f"Invalid pronoun. Valid options: {', '.join(self.PRONOUN_ROLES)}", ephemeral=True if ctx.interaction else False
            )
            return
            
        role_name = self.PRONOUN_ROLES[valid_names.index(pronoun_name)]
        role = discord.utils.get(guild.roles, name=role_name)
        if not role:
            try:
                role = await self._create_role_safely(guild, role_name)
                await ctx.send(f"Added pronoun role: {role_name}", ephemeral=True if ctx.interaction else False)
            except (commands.BotMissingPermissions, commands.CommandError) as e:
                await ctx.send(f"Failed to create role: {e}", ephemeral=True if ctx.interaction else False)
        else:
            await ctx.send(f"Pronoun role already exists: {role_name}", ephemeral=True if ctx.interaction else False)

    @commands.hybrid_command(name="addcommonpingrole", description="Create a common ping role or all common ping roles on the server.")
    async def addcommonpingrole(self, ctx: commands.Context, pingrole: str):
        """Add a common ping role or all common ping roles to the server."""
        if not await self._check_permissions(ctx):
            return
            
        guild = ctx.guild
        pingrole_name = pingrole.strip().lower()
        
        if pingrole_name == "all":
            added_roles = []
            failed_roles = []
            for role_name in self.COMMON_PING_ROLES:
                role = discord.utils.get(guild.roles, name=role_name)
                if not role:
                    try:
                        role = await self._create_role_safely(guild, role_name)
                        added_roles.append(role_name)
                    except (commands.BotMissingPermissions, commands.CommandError) as e:
                        failed_roles.append(role_name)
                else:
                    added_roles.append(role_name)
            
            if added_roles:
                await ctx.send(
                    f"Added common ping roles: {', '.join(added_roles)}", ephemeral=True if ctx.interaction else False
                )
            if failed_roles:
                await ctx.send(
                    f"Failed to create: {', '.join(failed_roles)}", ephemeral=True if ctx.interaction else False
                )
            return
            
        valid_names = [r.lower() for r in self.COMMON_PING_ROLES]
        if pingrole_name not in valid_names:
            await ctx.send(
                f"Invalid common ping role. Valid options: {', '.join(self.COMMON_PING_ROLES)}", ephemeral=True if ctx.interaction else False
            )
            return
            
        role_name = self.COMMON_PING_ROLES[valid_names.index(pingrole_name)]
        role = discord.utils.get(guild.roles, name=role_name)
        if not role:
            try:
                role = await self._create_role_safely(guild, role_name)
                await ctx.send(f"Added common ping role: {role_name}", ephemeral=True if ctx.interaction else False)
            except (commands.BotMissingPermissions, commands.CommandError) as e:
                await ctx.send(f"Failed to create role: {e}", ephemeral=True if ctx.interaction else False)
        else:
            await ctx.send(f"Common ping role already exists: {role_name}", ephemeral=True if ctx.interaction else False)