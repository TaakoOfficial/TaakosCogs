"""WHMCS COG - Main cog implementation for WHMCS integration."""

import asyncio
import discord
import logging
from redbot.core import commands, Config, app_commands
from redbot.core.bot import Red
from typing import Optional, Dict, Any, List, Union

from .whmcs_api import WHMCSAPIClient, WHMCSAPIError, WHMCSAuthenticationError, WHMCSRateLimitError
from .validation_utils import (
    validate_client_id, validate_email, validate_amount, validate_url,
    validate_api_identifier, validate_api_secret, ValidationError
)

__red_end_user_data_statement__ = (
    "This cog stores WHMCS API credentials and configuration data. "
    "No end user data is persistently stored beyond what is necessary for WHMCS integration."
)

log = logging.getLogger("red.WHMCS")


class WHMCS(commands.Cog):
    """WHMCS Integration for Red-Bot.
    
    Provides Discord integration with WHMCS billing and client management system.
    Supports client management, billing operations, support tickets, and system administration.
    """

    def __init__(self, bot: Red):
        self.bot = bot
        self.config = Config.get_conf(self, identifier=2025110901)
        
        # Configuration schema
        default_guild = {
            "api_config": {
                "url": None,           # WHMCS installation URL
                "identifier": None,    # API identifier
                "secret": None,        # API secret (encrypted)
                "access_key": None     # Alternative auth method
            },
            "permissions": {
                "admin_roles": [],     # Roles with full access
                "billing_roles": [],   # Roles with billing access
                "support_roles": [],   # Roles with support access
                "readonly_roles": []   # Roles with read-only access
            },
            "settings": {
                "rate_limit": 60,      # API calls per minute
                "embed_color": 0x7289DA,
                "show_sensitive": False,
                "auto_sync": False
            }
        }
        
        self.config.register_guild(**default_guild)
        
        # Cache for API clients per guild
        self._api_clients: Dict[int, WHMCSAPIClient] = {}
    
    async def cog_unload(self):
        """Clean up when cog is unloaded."""
        # Close all API client sessions
        for client in self._api_clients.values():
            if hasattr(client, 'session') and client.session:
                await client.session.close()
    
    async def _get_api_client(self, guild: discord.Guild) -> Optional[WHMCSAPIClient]:
        """Get or create an API client for the guild.
        
        Args:
            guild: The Discord guild
            
        Returns:
            Configured API client or None if not configured
        """
        guild_id = guild.id
        
        if guild_id not in self._api_clients:
            config = await self.config.guild(guild).api_config()
            
            if not config.get("url") or not (config.get("identifier") or config.get("username")):
                return None
            
            client = WHMCSAPIClient(config["url"])
            
            if config.get("identifier") and config.get("secret"):
                client.set_api_credentials(
                    config["identifier"],
                    config["secret"],
                    config.get("access_key")
                )
            
            settings = await self.config.guild(guild).settings()
            client.rate_limit = settings.get("rate_limit", 60)
            
            self._api_clients[guild_id] = client
        
        return self._api_clients[guild_id]
    
    async def _check_permissions(self, ctx: commands.Context, required_level: str) -> bool:
        """Check if user has required permission level.
        
        Args:
            ctx: The command context
            required_level: Required permission level (readonly, support, billing, admin)
            
        Returns:
            True if user has permission, False otherwise
        """
        if not ctx.guild:
            return False
        
        # Bot owner always has permission
        if await self.bot.is_owner(ctx.author):
            return True
        
        # Guild owner always has permission
        if ctx.author.id == ctx.guild.owner_id:
            return True
        
        user_roles = [role.id for role in ctx.author.roles]
        permissions = await self.config.guild(ctx.guild).permissions()
        
        # Check permission hierarchy (admin > billing > support > readonly)
        permission_hierarchy = ["readonly", "support", "billing", "admin"]
        required_index = permission_hierarchy.index(required_level)
        
        for i in range(required_index, len(permission_hierarchy)):
            level = permission_hierarchy[i]
            if any(role in permissions.get(f"{level}_roles", []) for role in user_roles):
                return True
        
        return False
    
    def _create_embed(self, title: str, description: str = "", color: Optional[int] = None) -> discord.Embed:
        """Create a standardized embed.
        
        Args:
            title: The embed title
            description: The embed description
            color: Optional color override
            
        Returns:
            Configured Discord embed
        """
        if color is None:
            color = 0x7289DA  # Default Discord blue
        
        embed = discord.Embed(
            title=title,
            description=description,
            color=color
        )
        embed.set_footer(text="WHMCS Integration")
        return embed
    
    async def _send_error(self, ctx: commands.Context, message: str):
        """Send an error message.
        
        Args:
            ctx: The command context
            message: Error message to send
        """
        embed = self._create_embed("❌ Error", message, color=0xFF0000)
        await ctx.send(embed=embed, ephemeral=True if ctx.interaction else False)
    
    async def _send_success(self, ctx: commands.Context, message: str):
        """Send a success message.
        
        Args:
            ctx: The command context
            message: Success message to send
        """
        embed = self._create_embed("✅ Success", message, color=0x00FF00)
        await ctx.send(embed=embed, ephemeral=True if ctx.interaction else False)
    
    # Main command group
    @commands.hybrid_group(name="whmcs", description="WHMCS management commands")
    async def whmcs(self, ctx: commands.Context):
        """WHMCS integration commands."""
        if not ctx.invoked_subcommand:
            embed = self._create_embed(
                "🏢 WHMCS Integration",
                "Use subcommands to interact with your WHMCS installation.\n\n"
                "**Available Groups:**\n"
                "• `client` - Client management\n"
                "• `billing` - Billing operations\n"
                "• `support` - Support tickets\n"
                "• `admin` - Administration\n\n"
                "Use `[p]help whmcs <group>` for more information."
            )
            await ctx.send(embed=embed)
    
    # Client management group
    @whmcs.group(name="client", description="Client management commands")
    async def whmcs_client(self, ctx: commands.Context):
        """Client management commands."""
        if not ctx.invoked_subcommand:
            embed = self._create_embed(
                "👤 Client Management",
                "**Available Commands:**\n"
                "• `list` - List clients\n"
                "• `view <id>` - View client details\n"
                "• `search <term>` - Search clients\n"
                "\n*Requires: Support role or higher*"
            )
            await ctx.send(embed=embed)
    
    @whmcs_client.hybrid_command(name="list")
    async def client_list(self, ctx: commands.Context, page: int = 1):
        """List clients with pagination.
        
        Args:
            page: Page number (default: 1)
        """
        if not await self._check_permissions(ctx, "support"):
            await self._send_error(ctx, "You don't have permission to view clients.")
            return
        
        api_client = await self._get_api_client(ctx.guild)
        if not api_client:
            await self._send_error(ctx, "WHMCS is not configured. Use `[p]whmcs admin config` to set up.")
            return
        
        try:
            async with api_client:
                limit = 10
                offset = (page - 1) * limit
                response = await api_client.get_clients(limit=limit, offset=offset)
                
                if not response.get("clients"):
                    await self._send_error(ctx, "No clients found.")
                    return
                
                embed = self._create_embed(f"👥 Clients (Page {page})")
                
                for client in response["clients"]["client"]:
                    client_info = (
                        f"**ID:** {client.get('id')}\n"
                        f"**Email:** {client.get('email')}\n"
                        f"**Status:** {client.get('status')}"
                    )
                    embed.add_field(
                        name=f"{client.get('firstname')} {client.get('lastname')}",
                        value=client_info,
                        inline=True
                    )
                
                total = response.get("totalresults", 0)
                total_pages = (total + limit - 1) // limit
                embed.set_footer(text=f"WHMCS Integration • Page {page}/{total_pages} • {total} total clients")
                
                await ctx.send(embed=embed)
                
        except WHMCSAuthenticationError:
            await self._send_error(ctx, "WHMCS authentication failed. Check your API credentials.")
        except WHMCSRateLimitError:
            await self._send_error(ctx, "Rate limit exceeded. Please try again later.")
        except WHMCSAPIError as e:
            await self._send_error(ctx, f"WHMCS API error: {e}")
        except Exception as e:
            log.exception("Error in client_list command")
            await self._send_error(ctx, f"An unexpected error occurred: {e}")
    
    @whmcs_client.command(name="view")
    async def client_view(self, ctx: commands.Context, client_id: int):
        """View detailed information for a specific client.
        
        Args:
            client_id: The client ID to view
        """
        if not await self._check_permissions(ctx, "support"):
            await self._send_error(ctx, "You don't have permission to view client details.")
            return
        
        # Validate client ID
        try:
            validated_client_id = validate_client_id(client_id)
        except ValidationError as e:
            await self._send_error(ctx, f"Invalid client ID: {e}")
            return
        
        api_client = await self._get_api_client(ctx.guild)
        if not api_client:
            await self._send_error(ctx, "WHMCS is not configured. Use `[p]whmcs admin config` to set up.")
            return
        
        try:
            async with api_client:
                response = await api_client.get_client(validated_client_id)
                
                if not response.get("client"):
                    await self._send_error(ctx, f"Client {client_id} not found.")
                    return
                
                client = response["client"]
                
                embed = self._create_embed(f"👤 Client Details: {client.get('firstname')} {client.get('lastname')}")
                
                # Basic information
                embed.add_field(
                    name="📧 Contact Information",
                    value=(
                        f"**Email:** {client.get('email')}\n"
                        f"**Phone:** {client.get('phonenumber', 'N/A')}\n"
                        f"**Company:** {client.get('companyname', 'N/A')}"
                    ),
                    inline=False
                )
                
                # Address
                address_parts = []
                if client.get('address1'):
                    address_parts.append(client['address1'])
                if client.get('address2'):
                    address_parts.append(client['address2'])
                if client.get('city'):
                    address_parts.append(client['city'])
                if client.get('state'):
                    address_parts.append(client['state'])
                if client.get('postcode'):
                    address_parts.append(client['postcode'])
                if client.get('country'):
                    address_parts.append(client['country'])
                
                if address_parts:
                    embed.add_field(
                        name="🏠 Address",
                        value=", ".join(address_parts),
                        inline=False
                    )
                
                # Account information
                embed.add_field(
                    name="💼 Account Status",
                    value=(
                        f"**Status:** {client.get('status')}\n"
                        f"**Credit:** ${client.get('credit', '0.00')}\n"
                        f"**Currency:** {client.get('currency_code', 'USD')}"
                    ),
                    inline=True
                )
                
                # Statistics
                embed.add_field(
                    name="📊 Statistics",
                    value=(
                        f"**Products:** {client.get('numproducts', '0')}\n"
                        f"**Domains:** {client.get('numdomains', '0')}\n"
                        f"**Invoices:** {client.get('numinvoices', '0')}\n"
                        f"**Tickets:** {client.get('numtickets', '0')}"
                    ),
                    inline=True
                )
                
                # Dates
                if client.get('datecreated'):
                    embed.add_field(
                        name="📅 Important Dates",
                        value=f"**Created:** {client.get('datecreated')}",
                        inline=True
                    )
                
                embed.set_footer(text=f"WHMCS Integration • Client ID: {client_id}")
                
                await ctx.send(embed=embed)
                
        except WHMCSAuthenticationError:
            await self._send_error(ctx, "WHMCS authentication failed. Check your API credentials.")
        except WHMCSRateLimitError:
            await self._send_error(ctx, "Rate limit exceeded. Please try again later.")
        except WHMCSAPIError as e:
            await self._send_error(ctx, f"WHMCS API error: {e}")
        except Exception as e:
            log.exception("Error in client_view command")
            await self._send_error(ctx, f"An unexpected error occurred: {e}")
    
    @whmcs_client.command(name="search")
    async def client_search(self, ctx: commands.Context, *, search_term: str):
        """Search for clients by name, email, or company.
        
        Args:
            search_term: The term to search for
        """
        if not await self._check_permissions(ctx, "support"):
            await self._send_error(ctx, "You don't have permission to search clients.")
            return
        
        api_client = await self._get_api_client(ctx.guild)
        if not api_client:
            await self._send_error(ctx, "WHMCS is not configured. Use `[p]whmcs admin config` to set up.")
            return
        
        try:
            async with api_client:
                response = await api_client.get_clients(search=search_term, limit=20)
                
                if not response.get("clients") or not response["clients"].get("client"):
                    await self._send_error(ctx, f"No clients found matching '{search_term}'.")
                    return
                
                embed = self._create_embed(f"🔍 Search Results: '{search_term}'")
                
                clients = response["clients"]["client"]
                if not isinstance(clients, list):
                    clients = [clients]
                
                for client in clients[:10]:  # Limit to first 10 results
                    client_info = (
                        f"**ID:** {client.get('id')}\n"
                        f"**Email:** {client.get('email')}\n"
                        f"**Status:** {client.get('status')}"
                    )
                    
                    name = f"{client.get('firstname', '')} {client.get('lastname', '')}".strip()
                    if not name:
                        name = client.get('email', f"Client {client.get('id')}")
                    
                    embed.add_field(
                        name=name,
                        value=client_info,
                        inline=True
                    )
                
                total = response.get("totalresults", len(clients))
                embed.set_footer(text=f"WHMCS Integration • {total} results found")
                
                await ctx.send(embed=embed)
                
        except WHMCSAuthenticationError:
            await self._send_error(ctx, "WHMCS authentication failed. Check your API credentials.")
        except WHMCSRateLimitError:
            await self._send_error(ctx, "Rate limit exceeded. Please try again later.")
        except WHMCSAPIError as e:
            await self._send_error(ctx, f"WHMCS API error: {e}")
        except Exception as e:
            log.exception("Error in client_search command")
            await self._send_error(ctx, f"An unexpected error occurred: {e}")
    
    # Administration group
    @whmcs.group(name="admin", description="Administration commands")
    async def whmcs_admin(self, ctx: commands.Context):
        """Administration commands."""
        if not ctx.invoked_subcommand:
            embed = self._create_embed(
                "⚙️ Administration",
                "**Available Commands:**\n"
                "• `config` - Configure WHMCS settings\n"
                "• `test` - Test API connectivity\n"
                "• `permissions` - Manage role permissions\n"
                "\n*Requires: Admin role*"
            )
            await ctx.send(embed=embed)
    
    @whmcs_admin.command(name="config")
    async def admin_config(self, ctx: commands.Context, action: Optional[str] = None, *, value: Optional[str] = None):
        """Configure WHMCS settings.
        
        Args:
            action: Configuration action (view, set, url, identifier, secret, accesskey)
            value: Value to set (required for set actions)
        """
        if not await self._check_permissions(ctx, "admin"):
            await self._send_error(ctx, "You don't have permission to configure WHMCS settings.")
            return
        
        if not action:
            # Show configuration help
            embed = self._create_embed(
                "⚙️ WHMCS Configuration",
                "**Available Actions:**\n"
                "• `view` - View current configuration\n"
                "• `url <whmcs_url>` - Set WHMCS URL\n"
                "• `identifier <api_id>` - Set API identifier\n"
                "• `secret <api_secret>` - Set API secret\n"
                "• `accesskey <access_key>` - Set access key (optional)\n"
                "• `ratelimit <number>` - Set rate limit (requests per minute)\n\n"
                "**Example:**\n"
                "`[p]whmcs admin config url https://your-whmcs.com`"
            )
            await ctx.send(embed=embed)
            return
        
        action = action.lower()
        
        if action == "view":
            # Show current configuration (without secrets)
            config = await self.config.guild(ctx.guild).api_config()
            settings = await self.config.guild(ctx.guild).settings()
            
            embed = self._create_embed("📋 Current WHMCS Configuration")
            
            # API Configuration
            embed.add_field(
                name="🔗 API Configuration",
                value=(
                    f"**URL:** {config.get('url', 'Not set')}\n"
                    f"**Identifier:** {'Set' if config.get('identifier') else 'Not set'}\n"
                    f"**Secret:** {'Set' if config.get('secret') else 'Not set'}\n"
                    f"**Access Key:** {'Set' if config.get('access_key') else 'Not set'}"
                ),
                inline=False
            )
            
            # Settings
            embed.add_field(
                name="⚙️ Settings",
                value=(
                    f"**Rate Limit:** {settings.get('rate_limit', 60)} requests/minute\n"
                    f"**Embed Color:** #{settings.get('embed_color', 0x7289DA):06x}\n"
                    f"**Show Sensitive:** {settings.get('show_sensitive', False)}"
                ),
                inline=False
            )
            
            await ctx.send(embed=embed)
            
        elif action in ["url", "identifier", "secret", "accesskey"]:
            if not value:
                await self._send_error(ctx, f"Please provide a value for {action}.")
                return
            
            # Validate inputs
            try:
                if action == "url":
                    from .validation_utils import validate_url
                    validated_value = validate_url(value)
                elif action == "identifier":
                    from .validation_utils import validate_api_identifier
                    validated_value = validate_api_identifier(value)
                elif action == "secret":
                    from .validation_utils import validate_api_secret
                    validated_value = validate_api_secret(value)
                else:  # accesskey
                    validated_value = value.strip()
                
                # Store the configuration
                if action == "accesskey":
                    async with self.config.guild(ctx.guild).api_config() as config:
                        config["access_key"] = validated_value
                else:
                    async with self.config.guild(ctx.guild).api_config() as config:
                        config[action] = validated_value
                
                # Clear cached API client to force recreation with new config
                if ctx.guild.id in self._api_clients:
                    del self._api_clients[ctx.guild.id]
                
                await self._send_success(ctx, f"✅ {action.title()} has been configured successfully.")
                
                # If we now have URL and credentials, suggest testing
                config = await self.config.guild(ctx.guild).api_config()
                if (config.get("url") and config.get("identifier") and config.get("secret")):
                    embed = self._create_embed(
                        "💡 Suggestion",
                        "Configuration appears complete! Test the connection with:\n"
                        "`[p]whmcs admin test`",
                        color=0x00BFFF
                    )
                    await ctx.send(embed=embed)
                
            except Exception as e:
                await self._send_error(ctx, f"Validation error: {e}")
                
        elif action == "ratelimit":
            if not value:
                await self._send_error(ctx, "Please provide a rate limit value (requests per minute).")
                return
            
            try:
                rate_limit = int(value)
                if rate_limit < 1 or rate_limit > 300:
                    await self._send_error(ctx, "Rate limit must be between 1 and 300 requests per minute.")
                    return
                
                async with self.config.guild(ctx.guild).settings() as settings:
                    settings["rate_limit"] = rate_limit
                
                # Update existing API client if present
                if ctx.guild.id in self._api_clients:
                    self._api_clients[ctx.guild.id].rate_limit = rate_limit
                
                await self._send_success(ctx, f"✅ Rate limit set to {rate_limit} requests per minute.")
                
            except ValueError:
                await self._send_error(ctx, "Rate limit must be a valid number.")
        
        else:
            await self._send_error(ctx, f"Unknown configuration action: {action}")

    @whmcs_admin.command(name="permissions")
    async def admin_permissions(self, ctx: commands.Context, action: Optional[str] = None,
                              level: Optional[str] = None, role: Optional[discord.Role] = None):
        """Manage role permissions for WHMCS commands.
        
        Args:
            action: Action to perform (view, add, remove)
            level: Permission level (admin, billing, support, readonly)
            role: Discord role to modify
        """
        if not await self._check_permissions(ctx, "admin"):
            await self._send_error(ctx, "You don't have permission to manage WHMCS permissions.")
            return
        
        valid_levels = ["admin", "billing", "support", "readonly"]
        
        if not action:
            # Show permission help
            embed = self._create_embed(
                "🔐 Permission Management",
                "**Available Actions:**\n"
                "• `view` - View current role permissions\n"
                "• `add <level> <role>` - Add role to permission level\n"
                "• `remove <level> <role>` - Remove role from permission level\n\n"
                "**Permission Levels:**\n"
                "• `admin` - Full access to all functions\n"
                "• `billing` - Access to billing and client management\n"
                "• `support` - Access to support tickets and read-only client info\n"
                "• `readonly` - View-only access to basic information\n\n"
                "**Example:**\n"
                "`[p]whmcs admin permissions add billing @Billing Team`"
            )
            await ctx.send(embed=embed)
            return
        
        action = action.lower()
        
        if action == "view":
            # Show current permissions
            permissions = await self.config.guild(ctx.guild).permissions()
            
            embed = self._create_embed("🔐 Current Role Permissions")
            
            for level in valid_levels:
                role_ids = permissions.get(f"{level}_roles", [])
                if role_ids:
                    roles = []
                    for role_id in role_ids:
                        role_obj = ctx.guild.get_role(role_id)
                        if role_obj:
                            roles.append(role_obj.mention)
                        else:
                            roles.append(f"Unknown Role ({role_id})")
                    
                    embed.add_field(
                        name=f"{level.title()} Roles",
                        value="\n".join(roles) if roles else "None",
                        inline=True
                    )
                else:
                    embed.add_field(
                        name=f"{level.title()} Roles",
                        value="None",
                        inline=True
                    )
            
            await ctx.send(embed=embed)
            
        elif action in ["add", "remove"]:
            if not level or level.lower() not in valid_levels:
                await self._send_error(ctx, f"Please specify a valid permission level: {', '.join(valid_levels)}")
                return
            
            if not role:
                await self._send_error(ctx, "Please specify a Discord role.")
                return
            
            level = level.lower()
            permissions_key = f"{level}_roles"
            
            async with self.config.guild(ctx.guild).permissions() as permissions:
                current_roles = permissions.get(permissions_key, [])
                
                if action == "add":
                    if role.id not in current_roles:
                        current_roles.append(role.id)
                        permissions[permissions_key] = current_roles
                        await self._send_success(ctx, f"✅ Added {role.mention} to {level} permission level.")
                    else:
                        await self._send_error(ctx, f"{role.mention} already has {level} permissions.")
                        
                else:  # remove
                    if role.id in current_roles:
                        current_roles.remove(role.id)
                        permissions[permissions_key] = current_roles
                        await self._send_success(ctx, f"✅ Removed {role.mention} from {level} permission level.")
                    else:
                        await self._send_error(ctx, f"{role.mention} doesn't have {level} permissions.")
        
        else:
            await self._send_error(ctx, f"Unknown action: {action}. Use 'view', 'add', or 'remove'.")

    @whmcs_admin.command(name="test")
    async def admin_test(self, ctx: commands.Context):
        """Test WHMCS API connectivity."""
        if not await self._check_permissions(ctx, "admin"):
            await self._send_error(ctx, "You don't have permission to test the API connection.")
            return
        
        api_client = await self._get_api_client(ctx.guild)
        if not api_client:
            await self._send_error(ctx, "WHMCS is not configured. Use `[p]whmcs admin config` to set up.")
            return
        
        try:
            async with api_client:
                response = await api_client.test_connection()
                
                embed = self._create_embed("✅ Connection Test Successful", color=0x00FF00)
                
                whmcs_info = response.get("whmcs", {})
                embed.add_field(
                    name="📊 WHMCS Information",
                    value=(
                        f"**Version:** {whmcs_info.get('version', 'Unknown')}\n"
                        f"**URL:** {whmcs_info.get('url', 'Unknown')}\n"
                        f"**Time:** {whmcs_info.get('time', 'Unknown')}"
                    ),
                    inline=False
                )
                
                await ctx.send(embed=embed)
                
        except WHMCSAuthenticationError:
            await self._send_error(ctx, "❌ Authentication failed. Check your API credentials.")
        except WHMCSRateLimitError:
            await self._send_error(ctx, "❌ Rate limit exceeded. Please try again later.")
        except WHMCSAPIError as e:
            await self._send_error(ctx, f"❌ API connection failed: {e}")
        except Exception as e:
            log.exception("Error in admin_test command")
            await self._send_error(ctx, f"❌ Connection test failed: {e}")
    
    # Billing management group
    @whmcs.group(name="billing", description="Billing management commands")
    async def whmcs_billing(self, ctx: commands.Context):
        """Billing management commands."""
        if not ctx.invoked_subcommand:
            embed = self._create_embed(
                "💰 Billing Management",
                "**Available Commands:**\n"
                "• `invoices <client_id>` - List client invoices\n"
                "• `invoice <invoice_id>` - View invoice details\n"
                "• `balance <client_id>` - View account balance\n"
                "• `credit <client_id> <amount> <description>` - Add credit (admin only)\n"
                "\n*Requires: Billing role or higher*"
            )
            await ctx.send(embed=embed)

    @whmcs_billing.command(name="invoices")
    async def billing_invoices(self, ctx: commands.Context, client_id: int, page: int = 1):
        """List invoices for a specific client.
        
        Args:
            client_id: The client ID
            page: Page number (default: 1)
        """
        if not await self._check_permissions(ctx, "billing"):
            await self._send_error(ctx, "You don't have permission to view billing information.")
            return
        
        api_client = await self._get_api_client(ctx.guild)
        if not api_client:
            await self._send_error(ctx, "WHMCS is not configured. Use `[p]whmcs admin config` to set up.")
            return
        
        try:
            async with api_client:
                limit = 10
                offset = (page - 1) * limit
                response = await api_client.get_invoices(client_id=client_id, limit=limit, offset=offset)
                
                if not response.get("invoices"):
                    await self._send_error(ctx, f"No invoices found for client {client_id}.")
                    return
                
                embed = self._create_embed(f"📄 Invoices for Client {client_id} (Page {page})")
                
                invoices = response["invoices"]["invoice"]
                if not isinstance(invoices, list):
                    invoices = [invoices]
                
                for invoice in invoices:
                    status_emoji = {
                        "Paid": "✅",
                        "Unpaid": "❌",
                        "Cancelled": "🚫",
                        "Refunded": "↩️",
                        "Draft": "📝"
                    }.get(invoice.get("status"), "❓")
                    
                    invoice_info = (
                        f"**Status:** {status_emoji} {invoice.get('status')}\n"
                        f"**Total:** ${invoice.get('total', '0.00')}\n"
                        f"**Due Date:** {invoice.get('duedate', 'N/A')}"
                    )
                    embed.add_field(
                        name=f"Invoice #{invoice.get('invoicenum')} (ID: {invoice.get('id')})",
                        value=invoice_info,
                        inline=True
                    )
                
                total = response.get("totalresults", 0)
                total_pages = (total + limit - 1) // limit
                embed.set_footer(text=f"WHMCS Integration • Page {page}/{total_pages} • {total} total invoices")
                
                await ctx.send(embed=embed)
                
        except WHMCSAuthenticationError:
            await self._send_error(ctx, "WHMCS authentication failed. Check your API credentials.")
        except WHMCSRateLimitError:
            await self._send_error(ctx, "Rate limit exceeded. Please try again later.")
        except WHMCSAPIError as e:
            await self._send_error(ctx, f"WHMCS API error: {e}")
        except Exception as e:
            log.exception("Error in billing_invoices command")
            await self._send_error(ctx, f"An unexpected error occurred: {e}")

    @whmcs_billing.command(name="invoice")
    async def billing_invoice(self, ctx: commands.Context, invoice_id: int):
        """View detailed information for a specific invoice.
        
        Args:
            invoice_id: The invoice ID to view
        """
        if not await self._check_permissions(ctx, "billing"):
            await self._send_error(ctx, "You don't have permission to view billing information.")
            return
        
        api_client = await self._get_api_client(ctx.guild)
        if not api_client:
            await self._send_error(ctx, "WHMCS is not configured. Use `[p]whmcs admin config` to set up.")
            return
        
        try:
            async with api_client:
                response = await api_client.get_invoice(invoice_id)
                
                if not response.get("invoice"):
                    await self._send_error(ctx, f"Invoice {invoice_id} not found.")
                    return
                
                invoice = response["invoice"]
                
                status_emoji = {
                    "Paid": "✅",
                    "Unpaid": "❌",
                    "Cancelled": "🚫",
                    "Refunded": "↩️",
                    "Draft": "📝"
                }.get(invoice.get("status"), "❓")
                
                embed = self._create_embed(
                    f"📄 Invoice #{invoice.get('invoicenum')} Details",
                    f"**Status:** {status_emoji} {invoice.get('status')}"
                )
                
                # Basic invoice information
                embed.add_field(
                    name="💰 Financial Details",
                    value=(
                        f"**Subtotal:** ${invoice.get('subtotal', '0.00')}\n"
                        f"**Tax:** ${invoice.get('tax', '0.00')}\n"
                        f"**Total:** ${invoice.get('total', '0.00')}\n"
                        f"**Balance:** ${invoice.get('balance', '0.00')}"
                    ),
                    inline=True
                )
                
                # Dates
                embed.add_field(
                    name="📅 Important Dates",
                    value=(
                        f"**Created:** {invoice.get('date', 'N/A')}\n"
                        f"**Due Date:** {invoice.get('duedate', 'N/A')}\n"
                        f"**Date Paid:** {invoice.get('datepaid', 'N/A') if invoice.get('datepaid') else 'Not paid'}"
                    ),
                    inline=True
                )
                
                # Client information
                if invoice.get("userid"):
                    embed.add_field(
                        name="👤 Client Information",
                        value=(
                            f"**Client ID:** {invoice.get('userid')}\n"
                            f"**Name:** {invoice.get('firstname', '')} {invoice.get('lastname', '')}\n"
                            f"**Company:** {invoice.get('companyname', 'N/A')}"
                        ),
                        inline=False
                    )
                
                # Payment method
                if invoice.get("paymentmethod"):
                    embed.add_field(
                        name="💳 Payment Details",
                        value=f"**Method:** {invoice.get('paymentmethod')}",
                        inline=True
                    )
                
                embed.set_footer(text=f"WHMCS Integration • Invoice ID: {invoice_id}")
                
                await ctx.send(embed=embed)
                
        except WHMCSAuthenticationError:
            await self._send_error(ctx, "WHMCS authentication failed. Check your API credentials.")
        except WHMCSRateLimitError:
            await self._send_error(ctx, "Rate limit exceeded. Please try again later.")
        except WHMCSAPIError as e:
            await self._send_error(ctx, f"WHMCS API error: {e}")
        except Exception as e:
            log.exception("Error in billing_invoice command")
            await self._send_error(ctx, f"An unexpected error occurred: {e}")

    @whmcs_billing.command(name="credit")
    async def billing_credit(self, ctx: commands.Context, client_id: int, amount: float, *, description: str):
        """Add credit to a client account (admin only).
        
        Args:
            client_id: The client ID
            amount: Credit amount to add
            description: Description for the credit
        """
        if not await self._check_permissions(ctx, "admin"):
            await self._send_error(ctx, "You don't have permission to add account credits.")
            return
        
        if amount <= 0:
            await self._send_error(ctx, "Credit amount must be greater than 0.")
            return
        
        api_client = await self._get_api_client(ctx.guild)
        if not api_client:
            await self._send_error(ctx, "WHMCS is not configured. Use `[p]whmcs admin config` to set up.")
            return
        
        try:
            async with api_client:
                response = await api_client.add_credit(client_id, amount, description)
                
                if response.get("result") == "success":
                    embed = self._create_embed(
                        "✅ Credit Added Successfully",
                        f"Added ${amount:.2f} credit to client {client_id}",
                        color=0x00FF00
                    )
                    embed.add_field(
                        name="📝 Details",
                        value=(
                            f"**Client ID:** {client_id}\n"
                            f"**Amount:** ${amount:.2f}\n"
                            f"**Description:** {description}"
                        ),
                        inline=False
                    )
                    await ctx.send(embed=embed)
                else:
                    await self._send_error(ctx, f"Failed to add credit: {response.get('message', 'Unknown error')}")
                
        except WHMCSAuthenticationError:
            await self._send_error(ctx, "WHMCS authentication failed. Check your API credentials.")
        except WHMCSRateLimitError:
            await self._send_error(ctx, "Rate limit exceeded. Please try again later.")
        except WHMCSAPIError as e:
            await self._send_error(ctx, f"WHMCS API error: {e}")
        except Exception as e:
            log.exception("Error in billing_credit command")
            await self._send_error(ctx, f"An unexpected error occurred: {e}")

    # Support management group
    @whmcs.group(name="support", description="Support ticket management commands")
    async def whmcs_support(self, ctx: commands.Context):
        """Support ticket management commands."""
        if not ctx.invoked_subcommand:
            embed = self._create_embed(
                "🎫 Support Management",
                "**Available Commands:**\n"
                "• `tickets <client_id>` - List client tickets\n"
                "• `ticket <ticket_id>` - View ticket details\n"
                "• `reply <ticket_id> <message>` - Reply to ticket\n"
                "\n*Requires: Support role or higher*"
            )
            await ctx.send(embed=embed)

    @whmcs_support.command(name="tickets")
    async def support_tickets(self, ctx: commands.Context, client_id: Optional[int] = None, page: int = 1):
        """List support tickets, optionally filtered by client.
        
        Args:
            client_id: Optional client ID to filter tickets
            page: Page number (default: 1)
        """
        if not await self._check_permissions(ctx, "support"):
            await self._send_error(ctx, "You don't have permission to view support tickets.")
            return
        
        api_client = await self._get_api_client(ctx.guild)
        if not api_client:
            await self._send_error(ctx, "WHMCS is not configured. Use `[p]whmcs admin config` to set up.")
            return
        
        try:
            async with api_client:
                limit = 10
                offset = (page - 1) * limit
                response = await api_client.get_tickets(client_id=client_id, limit=limit, offset=offset)
                
                if not response.get("tickets"):
                    filter_text = f" for client {client_id}" if client_id else ""
                    await self._send_error(ctx, f"No tickets found{filter_text}.")
                    return
                
                filter_text = f" for Client {client_id}" if client_id else ""
                embed = self._create_embed(f"🎫 Support Tickets{filter_text} (Page {page})")
                
                tickets = response["tickets"]["ticket"]
                if not isinstance(tickets, list):
                    tickets = [tickets]
                
                for ticket in tickets:
                    status_emoji = {
                        "Open": "🟢",
                        "Answered": "🔵",
                        "Customer-Reply": "🟡",
                        "Closed": "🔴"
                    }.get(ticket.get("status"), "❓")
                    
                    priority_emoji = {
                        "Low": "🔽",
                        "Medium": "➡️",
                        "High": "🔼"
                    }.get(ticket.get("priority"), "➡️")
                    
                    ticket_info = (
                        f"**Status:** {status_emoji} {ticket.get('status')}\n"
                        f"**Priority:** {priority_emoji} {ticket.get('priority')}\n"
                        f"**Department:** {ticket.get('department', 'N/A')}\n"
                        f"**Last Reply:** {ticket.get('lastreply', 'N/A')}"
                    )
                    
                    subject = ticket.get('subject', 'No Subject')
                    if len(subject) > 50:
                        subject = subject[:47] + "..."
                    
                    embed.add_field(
                        name=f"#{ticket.get('tid')} - {subject}",
                        value=ticket_info,
                        inline=True
                    )
                
                total = response.get("totalresults", 0)
                total_pages = (total + limit - 1) // limit
                embed.set_footer(text=f"WHMCS Integration • Page {page}/{total_pages} • {total} total tickets")
                
                await ctx.send(embed=embed)
                
        except WHMCSAuthenticationError:
            await self._send_error(ctx, "WHMCS authentication failed. Check your API credentials.")
        except WHMCSRateLimitError:
            await self._send_error(ctx, "Rate limit exceeded. Please try again later.")
        except WHMCSAPIError as e:
            await self._send_error(ctx, f"WHMCS API error: {e}")
        except Exception as e:
            log.exception("Error in support_tickets command")
            await self._send_error(ctx, f"An unexpected error occurred: {e}")

    @whmcs_support.command(name="ticket")
    async def support_ticket(self, ctx: commands.Context, ticket_id: int):
        """View detailed information for a specific support ticket.
        
        Args:
            ticket_id: The ticket ID to view
        """
        if not await self._check_permissions(ctx, "support"):
            await self._send_error(ctx, "You don't have permission to view support tickets.")
            return
        
        api_client = await self._get_api_client(ctx.guild)
        if not api_client:
            await self._send_error(ctx, "WHMCS is not configured. Use `[p]whmcs admin config` to set up.")
            return
        
        try:
            async with api_client:
                response = await api_client.get_ticket(ticket_id)
                
                if not response.get("ticket"):
                    await self._send_error(ctx, f"Ticket {ticket_id} not found.")
                    return
                
                ticket = response["ticket"]
                
                status_emoji = {
                    "Open": "🟢",
                    "Answered": "🔵",
                    "Customer-Reply": "🟡",
                    "Closed": "🔴"
                }.get(ticket.get("status"), "❓")
                
                priority_emoji = {
                    "Low": "🔽",
                    "Medium": "➡️",
                    "High": "🔼"
                }.get(ticket.get("priority"), "➡️")
                
                embed = self._create_embed(
                    f"🎫 Ticket #{ticket.get('tid')} - {ticket.get('subject', 'No Subject')}"
                )
                
                # Status and priority
                embed.add_field(
                    name="📊 Status Information",
                    value=(
                        f"**Status:** {status_emoji} {ticket.get('status')}\n"
                        f"**Priority:** {priority_emoji} {ticket.get('priority')}\n"
                        f"**Department:** {ticket.get('department', 'N/A')}"
                    ),
                    inline=True
                )
                
                # Client information
                embed.add_field(
                    name="👤 Client Information",
                    value=(
                        f"**Client ID:** {ticket.get('userid', 'N/A')}\n"
                        f"**Name:** {ticket.get('name', 'N/A')}\n"
                        f"**Email:** {ticket.get('email', 'N/A')}"
                    ),
                    inline=True
                )
                
                # Timing information
                embed.add_field(
                    name="📅 Timing",
                    value=(
                        f"**Created:** {ticket.get('date', 'N/A')}\n"
                        f"**Last Reply:** {ticket.get('lastreply', 'N/A')}"
                    ),
                    inline=True
                )
                
                # Message content (truncated)
                message = ticket.get('message', '')
                if message:
                    if len(message) > 500:
                        message = message[:497] + "..."
                    embed.add_field(
                        name="💬 Initial Message",
                        value=f"```{message}```",
                        inline=False
                    )
                
                # Reply count
                if ticket.get("replies"):
                    reply_count = len(ticket["replies"]) if isinstance(ticket["replies"], list) else 1
                    embed.add_field(
                        name="💬 Replies",
                        value=f"{reply_count} reply(s)",
                        inline=True
                    )
                
                embed.set_footer(text=f"WHMCS Integration • Ticket ID: {ticket_id}")
                
                await ctx.send(embed=embed)
                
        except WHMCSAuthenticationError:
            await self._send_error(ctx, "WHMCS authentication failed. Check your API credentials.")
        except WHMCSRateLimitError:
            await self._send_error(ctx, "Rate limit exceeded. Please try again later.")
        except WHMCSAPIError as e:
            await self._send_error(ctx, f"WHMCS API error: {e}")
        except Exception as e:
            log.exception("Error in support_ticket command")
            await self._send_error(ctx, f"An unexpected error occurred: {e}")

    @whmcs_support.command(name="reply")
    async def support_reply(self, ctx: commands.Context, ticket_id: int, *, message: str):
        """Reply to a support ticket.
        
        Args:
            ticket_id: The ticket ID to reply to
            message: The reply message
        """
        if not await self._check_permissions(ctx, "support"):
            await self._send_error(ctx, "You don't have permission to reply to support tickets.")
            return
        
        if len(message) < 10:
            await self._send_error(ctx, "Reply message must be at least 10 characters long.")
            return
        
        api_client = await self._get_api_client(ctx.guild)
        if not api_client:
            await self._send_error(ctx, "WHMCS is not configured. Use `[p]whmcs admin config` to set up.")
            return
        
        try:
            async with api_client:
                # Add the reply with the Discord user's name as admin username
                admin_username = f"Discord-{ctx.author.display_name}"
                response = await api_client.add_ticket_reply(ticket_id, message, admin_username)
                
                if response.get("result") == "success":
                    embed = self._create_embed(
                        "✅ Reply Added Successfully",
                        f"Your reply has been added to ticket #{ticket_id}",
                        color=0x00FF00
                    )
                    embed.add_field(
                        name="📝 Reply Details",
                        value=(
                            f"**Ticket ID:** {ticket_id}\n"
                            f"**Replied by:** {ctx.author.display_name}\n"
                            f"**Message length:** {len(message)} characters"
                        ),
                        inline=False
                    )
                    
                    # Show preview of message (truncated)
                    preview = message if len(message) <= 200 else message[:197] + "..."
                    embed.add_field(
                        name="💬 Message Preview",
                        value=f"```{preview}```",
                        inline=False
                    )
                    
                    await ctx.send(embed=embed)
                else:
                    await self._send_error(ctx, f"Failed to add reply: {response.get('message', 'Unknown error')}")
                
        except WHMCSAuthenticationError:
            await self._send_error(ctx, "WHMCS authentication failed. Check your API credentials.")
        except WHMCSRateLimitError:
            await self._send_error(ctx, "Rate limit exceeded. Please try again later.")
        except WHMCSAPIError as e:
            await self._send_error(ctx, f"WHMCS API error: {e}")
        except Exception as e:
            log.exception("Error in support_reply command")
            await self._send_error(ctx, f"An unexpected error occurred: {e}")

    # Error handler for the cog
    async def cog_command_error(self, ctx: commands.Context, error: commands.CommandError):
        """Handle cog-specific command errors."""
        if isinstance(error, commands.MissingPermissions):
            await self._send_error(ctx, "You don't have the required permissions to use this command.")
        elif isinstance(error, commands.BadArgument):
            await self._send_error(ctx, f"Invalid argument: {error}")
        elif isinstance(error, commands.CommandOnCooldown):
            await self._send_error(ctx, f"Command is on cooldown. Try again in {error.retry_after:.1f} seconds.")
        else:
            log.exception(f"Unhandled error in WHMCS command: {error}")
            await self._send_error(ctx, "An unexpected error occurred. Please try again later.")