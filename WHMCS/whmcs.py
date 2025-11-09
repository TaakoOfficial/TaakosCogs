"""WHMCS COG - Main cog implementation for WHMCS integration."""

import asyncio
import discord
import logging
from redbot.core import commands, Config, app_commands
from redbot.core.bot import Red
from redbot.core.utils.menus import menu, DEFAULT_CONTROLS
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
            },
            "ticket_channels": {
                "enabled": False,      # Enable automatic channel creation
                "category_id": None,   # Category for ticket channels
                "archive_category_id": None,  # Category for closed tickets
                "channel_prefix": "whmcs-ticket-",  # Prefix for channel names
                "auto_archive": True   # Archive channels when tickets are closed
            },
            "ticket_mappings": {}      # Map ticket IDs to channel IDs
        }
        
        self.config.register_guild(**default_guild)
        
        # Cache for API clients per guild
        self._api_clients: Dict[int, WHMCSAPIClient] = {}
        
        # Cache for ticket channels per guild
        self._ticket_channels: Dict[int, Dict[str, int]] = {}  # {guild_id: {ticket_id: channel_id}}
    
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
        if await ctx.embed_requested():
            embed = self._create_embed("❌ Error", message, color=0xFF0000)
            await ctx.send(embed=embed, ephemeral=True if ctx.interaction else False)
        else:
            await ctx.send(f"❌ **Error:** {message}", ephemeral=True if ctx.interaction else False)
    
    async def _send_success(self, ctx: commands.Context, message: str):
        """Send a success message.
        
        Args:
            ctx: The command context
            message: Success message to send
        """
        if await ctx.embed_requested():
            embed = self._create_embed("✅ Success", message, color=0x00FF00)
            await ctx.send(embed=embed, ephemeral=True if ctx.interaction else False)
        else:
            await ctx.send(f"✅ **Success:** {message}", ephemeral=True if ctx.interaction else False)
    
    async def _prev_page(self, ctx: commands.Context, pages: List[discord.Embed], controls: Dict, message: discord.Message, page: int, timeout: float, emoji: str):
        """Navigate to previous page."""
        # This would need to be implemented with actual page data
        # For now, just acknowledge the reaction
        return page
    
    async def _next_page(self, ctx: commands.Context, pages: List[discord.Embed], controls: Dict, message: discord.Message, page: int, timeout: float, emoji: str):
        """Navigate to next page."""
        # This would need to be implemented with actual page data
        # For now, just acknowledge the reaction
        return page
    
    async def _get_or_create_ticket_channel(self, guild: discord.Guild, ticket_id: str, ticket_data: Dict[str, Any]) -> Optional[discord.TextChannel]:
        """Get existing ticket channel or create a new one.
        
        Args:
            guild: Discord guild
            ticket_id: WHMCS ticket ID
            ticket_data: Ticket information from WHMCS
            
        Returns:
            Discord text channel for the ticket or None if disabled/failed
        """
        config = await self.config.guild(guild).ticket_channels()
        if not config.get("enabled", False):
            return None
        
        # Check if channel already exists
        if guild.id not in self._ticket_channels:
            self._ticket_channels[guild.id] = {}
        
        # Load existing mappings from config
        ticket_mappings = await self.config.guild(guild).ticket_mappings()
        
        if ticket_id in ticket_mappings:
            channel = guild.get_channel(ticket_mappings[ticket_id])
            if channel:
                return channel
            else:
                # Channel was deleted, remove from mappings
                async with self.config.guild(guild).ticket_mappings() as mappings:
                    if ticket_id in mappings:
                        del mappings[ticket_id]
        
        # Create new channel
        try:
            category = None
            if config.get("category_id"):
                category = guild.get_channel(config["category_id"])
            
            # Create channel name
            prefix = config.get("channel_prefix", "whmcs-ticket-")
            
            # Clean ticket ID for channel name (remove # prefix if present)
            clean_ticket_id = ticket_id.lstrip('#').strip()
            channel_name = f"{prefix}{clean_ticket_id.lower()}"
            
            # Ensure channel name is valid (alphanumeric and hyphens only)
            import re
            channel_name = re.sub(r'[^a-z0-9\-]', '-', channel_name.lower())
            
            # Create the channel
            overwrites = {
                guild.default_role: discord.PermissionOverwrite(read_messages=False),
                guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True, manage_messages=True)
            }
            
            # Add permissions for support roles
            permissions = await self.config.guild(guild).permissions()
            for role_level in ["admin_roles", "support_roles"]:
                for role_id in permissions.get(role_level, []):
                    role = guild.get_role(role_id)
                    if role:
                        overwrites[role] = discord.PermissionOverwrite(read_messages=True, send_messages=True)
            
            channel = await guild.create_text_channel(
                name=channel_name,
                category=category,
                overwrites=overwrites,
                topic=f"WHMCS Support Ticket {ticket_id} - {ticket_data.get('subject', 'No Subject')}"
            )
            
            # Store mapping
            async with self.config.guild(guild).ticket_mappings() as mappings:
                mappings[ticket_id] = channel.id
            
            self._ticket_channels[guild.id][ticket_id] = channel.id
            
            # Send initial ticket information to channel
            await self._send_ticket_info_to_channel(channel, ticket_id, ticket_data)
            
            return channel
            
        except Exception as e:
            log.exception(f"Failed to create ticket channel for {ticket_id}")
            return None
    
    async def _send_ticket_info_to_channel(self, channel: discord.TextChannel, ticket_id: str, ticket_data: Dict[str, Any]):
        """Send ticket information to the newly created channel.
        
        Args:
            channel: Discord channel
            ticket_id: WHMCS ticket ID
            ticket_data: Ticket information
        """
        try:
            status = ticket_data.get("status", "Unknown")
            status_emoji = {
                "Open": "🟢",
                "Answered": "🔵",
                "Customer-Reply": "🟡",
                "Closed": "🔴"
            }.get(status, "❓")
            
            priority = ticket_data.get("priority", "Medium")
            priority_emoji = {
                "Low": "🔽",
                "Medium": "➡️",
                "High": "🔼"
            }.get(priority, "➡️")
            
            embed = self._create_embed(f"🎫 Ticket {ticket_id} Channel Created")
            embed.description = f"**{ticket_data.get('subject', 'No Subject')}**"
            
            embed.add_field(
                name="📊 Ticket Information",
                value=(
                    f"🆔 **ID:** {ticket_id}\n"
                    f"📊 **Status:** {status_emoji} {status}\n"
                    f"⚡ **Priority:** {priority_emoji} {priority}\n"
                    f"🏢 **Department:** {ticket_data.get('department', 'N/A')}\n"
                    f"👤 **Client:** {ticket_data.get('name', 'N/A')}\n"
                    f"📧 **Email:** {ticket_data.get('email', 'N/A')}"
                ),
                inline=False
            )
            
            if ticket_data.get('message'):
                message = ticket_data['message']
                if len(message) > 1000:
                    message = message[:997] + "..."
                embed.add_field(
                    name="💬 Original Message",
                    value=f"```{message}```",
                    inline=False
                )
            
            embed.add_field(
                name="🔧 Channel Usage",
                value=(
                    "**Messages sent in this channel will automatically be added as replies to the WHMCS ticket.**\n\n"
                    "📝 Simply type your response and it will be posted to WHMCS\n"
                    "🎫 Use `/whmcs support ticket " + ticket_id + "` to view full ticket details\n"
                    "🔒 Channel will be archived when ticket is closed"
                ),
                inline=False
            )
            
            await channel.send(embed=embed)
            
        except Exception as e:
            log.exception(f"Failed to send ticket info to channel {channel.id}")
    
    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        """Listen for messages in ticket channels and auto-reply to WHMCS tickets."""
        # Ignore bot messages and DMs
        if not message.guild or message.author.bot:
            return
        
        # Check if this is a ticket channel
        ticket_mappings = await self.config.guild(message.guild).ticket_mappings()
        ticket_id = None
        
        for tid, channel_id in ticket_mappings.items():
            if channel_id == message.channel.id:
                ticket_id = tid
                break
        
        if not ticket_id:
            return
        
        # Check if user has permission to reply to tickets
        ctx = await self.bot.get_context(message)
        if not await self._check_permissions(ctx, "support"):
            return
        
        # Get API client
        api_client = await self._get_api_client(message.guild)
        if not api_client:
            return
        
        try:
            # Add reply to WHMCS ticket
            async with api_client:
                admin_username = f"Discord-{message.author.display_name}"
                response = await api_client.add_ticket_reply(ticket_id, message.content, admin_username)
                
                if response.get("result") == "success":
                    # Add reaction to confirm the message was sent to WHMCS
                    await message.add_reaction("✅")
                else:
                    # Add error reaction
                    await message.add_reaction("❌")
                    
        except Exception as e:
            log.exception(f"Failed to auto-reply to ticket {ticket_id}")
            try:
                await message.add_reaction("❌")
            except:
                pass
    
    # Main command group
    @commands.hybrid_group(name="whmcs", description="WHMCS management commands")
    async def whmcs(self, ctx: commands.Context):
        """WHMCS integration commands."""
        pass
    
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
    
    @whmcs_client.command(name="list")
    @app_commands.describe(page="Page number (default: 1)")
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
                limit = 5  # Reduced from 10 to make less crowded
                offset = (page - 1) * limit
                response = await api_client.get_clients(limit=limit, offset=offset)
                
                if not response.get("clients"):
                    await self._send_error(ctx, "No clients found.")
                    return
                
                total = response.get("totalresults", 0)
                total_pages = (total + limit - 1) // limit
                
                if await ctx.embed_requested():
                    embed = self._create_embed(f"👥 Client Directory")
                    embed.description = f"**Page {page} of {total_pages}** • {total} total clients"
                    
                    clients = response["clients"]["client"]
                    if not isinstance(clients, list):
                        clients = [clients]
                    
                    for client in clients:
                        name = f"{client.get('firstname', '')} {client.get('lastname', '')}".strip()
                        if not name:
                            name = f"Client {client.get('id')}"
                        
                        # Less crowded formatting with better spacing and emojis
                        client_info = (
                            f"🆔 **ID:** {client.get('id')}\n"
                            f"📧 **Email:** {client.get('email')}\n"
                            f"📊 **Status:** {client.get('status')}"
                        )
                        
                        embed.add_field(
                            name=f"👤 {name}",
                            value=client_info,
                            inline=False  # Full width for better readability
                        )
                    
                    # Add navigation hints in footer if multiple pages
                    if total_pages > 1:
                        navigation_text = f"WHMCS Integration • Page {page}/{total_pages}"
                        if page > 1:
                            navigation_text += f" • Use `{ctx.prefix}whmcs client list {page-1}` for previous"
                        if page < total_pages:
                            navigation_text += f" • Use `{ctx.prefix}whmcs client list {page+1}` for next"
                        embed.set_footer(text=navigation_text)
                    else:
                        embed.set_footer(text=f"WHMCS Integration • {total} total clients")
                    
                    await ctx.send(embed=embed)
                else:
                    # Plain text format for when embeds are disabled
                    output = [f"👥 **Client Directory - Page {page} of {total_pages}**"]
                    output.append(f"📊 {total} total clients\n")
                    
                    clients = response["clients"]["client"]
                    if not isinstance(clients, list):
                        clients = [clients]
                    
                    for client in clients:
                        name = f"{client.get('firstname', '')} {client.get('lastname', '')}".strip()
                        if not name:
                            name = f"Client {client.get('id')}"
                        
                        output.append(f"👤 **{name}**")
                        output.append(f"   🆔 ID: {client.get('id')}")
                        output.append(f"   📧 Email: {client.get('email')}")
                        output.append(f"   📊 Status: {client.get('status')}")
                        output.append("")  # Empty line for spacing
                    
                    # Add navigation hints for text format too
                    if total_pages > 1:
                        output.append("📄 **Navigation:**")
                        if page > 1:
                            output.append(f"   ⬅️ Previous: `{ctx.prefix}whmcs client list {page-1}`")
                        if page < total_pages:
                            output.append(f"   ➡️ Next: `{ctx.prefix}whmcs client list {page+1}`")
                    
                    await ctx.send("\n".join(output))
                
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
                
                client_name = f"{client.get('firstname', '')} {client.get('lastname', '')}".strip()
                if not client_name:
                    client_name = f"Client {client_id}"
                
                embed = self._create_embed(f"👤 Client Details")
                embed.description = f"**{client_name}** • ID: {client_id}"
                
                # Basic information with consistent emoji formatting
                embed.add_field(
                    name="📧 Contact Information",
                    value=(
                        f"📧 **Email:** {client.get('email')}\n"
                        f"📞 **Phone:** {client.get('phonenumber', 'N/A')}\n"
                        f"🏢 **Company:** {client.get('companyname', 'N/A')}"
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
                        f"📊 **Status:** {client.get('status')}\n"
                        f"💰 **Credit:** ${client.get('credit', '0.00')}\n"
                        f"💱 **Currency:** {client.get('currency_code', 'USD')}"
                    ),
                    inline=False
                )
                
                # Statistics
                embed.add_field(
                    name="📊 Account Statistics",
                    value=(
                        f"🛍️ **Products:** {client.get('numproducts', '0')}\n"
                        f"🌐 **Domains:** {client.get('numdomains', '0')}\n"
                        f"📄 **Invoices:** {client.get('numinvoices', '0')}\n"
                        f"🎫 **Tickets:** {client.get('numtickets', '0')}"
                    ),
                    inline=False
                )
                
                # Dates
                if client.get('datecreated'):
                    embed.add_field(
                        name="📅 Important Dates",
                        value=f"📅 **Account Created:** {client.get('datecreated')}",
                        inline=False
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
                
                clients = response["clients"]["client"]
                if not isinstance(clients, list):
                    clients = [clients]
                
                embed = self._create_embed(f"🔍 Search Results")
                embed.description = f"**Search term:** '{search_term}' • {response.get('totalresults', len(clients))} results found"
                
                for client in clients[:5]:  # Limit to first 5 results for better display
                    name = f"{client.get('firstname', '')} {client.get('lastname', '')}".strip()
                    if not name:
                        name = client.get('email', f"Client {client.get('id')}")
                    
                    # Consistent formatting with emoji indicators
                    client_info = (
                        f"🆔 **ID:** {client.get('id')}\n"
                        f"📧 **Email:** {client.get('email')}\n"
                        f"📊 **Status:** {client.get('status')}"
                    )
                    
                    embed.add_field(
                        name=f"👤 {name}",
                        value=client_info,
                        inline=False  # Full width for better readability
                    )
                
                total = response.get("totalresults", len(clients))
                if total > 5:
                    embed.set_footer(text=f"WHMCS Integration • Showing first 5 of {total} results")
                else:
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
                "• `debug <ticket_id>` - Debug ticket API issues\n"
                "• `findticket <search>` - Search for tickets by email/ID\n"
                "• `permissions` - Manage role permissions\n"
                "• `channels` - Configure automatic ticket channels\n"
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

    @whmcs_admin.command(name="channels")
    async def admin_channels(self, ctx: commands.Context, action: Optional[str] = None, setting: Optional[str] = None, *, value: Optional[str] = None):
        """Configure automatic ticket channel settings.
        
        Args:
            action: Action to perform (view, enable, disable, set)
            setting: Setting to configure (category, archive_category, prefix, auto_archive)
            value: Value to set (required for set actions)
        """
        if not await self._check_permissions(ctx, "admin"):
            await self._send_error(ctx, "You don't have permission to configure ticket channel settings.")
            return
        
        if not action:
            # Show configuration help
            embed = self._create_embed(
                "🎫 Ticket Channel Configuration",
                "**Available Actions:**\n"
                "• `view` - View current ticket channel settings\n"
                "• `enable` - Enable automatic ticket channel creation\n"
                "• `disable` - Disable automatic ticket channel creation\n"
                "• `set category <category_id>` - Set active tickets category\n"
                "• `set archive_category <category_id>` - Set archive category (optional)\n"
                "• `set prefix <prefix>` - Set channel name prefix\n"
                "• `set auto_archive <true/false>` - Enable/disable auto-archiving\n\n"
                "**Examples:**\n"
                "`[p]whmcs admin channels enable`\n"
                "`[p]whmcs admin channels set category 123456789012345678`\n"
                "`[p]whmcs admin channels set prefix support-`"
            )
            await ctx.send(embed=embed)
            return
        
        action = action.lower()
        
        if action == "view":
            # Show current configuration
            config = await self.config.guild(ctx.guild).ticket_channels()
            
            embed = self._create_embed("🎫 Current Ticket Channel Settings")
            
            # Channel Configuration
            enabled_status = "🟢 Enabled" if config.get("enabled", False) else "🔴 Disabled"
            
            category_info = "Not set"
            if config.get("category_id"):
                category = ctx.guild.get_channel(config["category_id"])
                if category:
                    category_info = f"{category.name} ({config['category_id']})"
                else:
                    category_info = f"Unknown Category ({config['category_id']})"
            
            archive_category_info = "Not set"
            if config.get("archive_category_id"):
                archive_category = ctx.guild.get_channel(config["archive_category_id"])
                if archive_category:
                    archive_category_info = f"{archive_category.name} ({config['archive_category_id']})"
                else:
                    archive_category_info = f"Unknown Category ({config['archive_category_id']})"
            
            embed.add_field(
                name="🎫 Channel Settings",
                value=(
                    f"**Status:** {enabled_status}\n"
                    f"**Active Category:** {category_info}\n"
                    f"**Archive Category:** {archive_category_info}\n"
                    f"**Channel Prefix:** {config.get('channel_prefix', 'whmcs-ticket-')}\n"
                    f"**Auto-Archive:** {'Yes' if config.get('auto_archive', True) else 'No'}"
                ),
                inline=False
            )
            
            if not config.get("enabled", False):
                embed.add_field(
                    name="💡 Getting Started",
                    value=(
                        "To enable ticket channels:\n"
                        f"1. `{ctx.prefix}whmcs admin channels set category <category_id>`\n"
                        f"2. `{ctx.prefix}whmcs admin channels enable`"
                    ),
                    inline=False
                )
            
            await ctx.send(embed=embed)
            
        elif action == "enable":
            config = await self.config.guild(ctx.guild).ticket_channels()
            if not config.get("category_id"):
                await self._send_error(ctx, "Please set a category ID first with `[p]whmcs admin channels set category <category_id>`")
                return
            
            async with self.config.guild(ctx.guild).ticket_channels() as channels_config:
                channels_config["enabled"] = True
            
            await self._send_success(ctx, "✅ Automatic ticket channel creation has been enabled!")
            
        elif action == "disable":
            async with self.config.guild(ctx.guild).ticket_channels() as channels_config:
                channels_config["enabled"] = False
            
            await self._send_success(ctx, "✅ Automatic ticket channel creation has been disabled.")
            
        elif action == "set":
            if not setting:
                await self._send_error(ctx, "Please specify a setting to configure.")
                return
            
            setting = setting.lower()
            valid_settings = ["category", "archive_category", "prefix", "auto_archive"]
            
            if setting not in valid_settings:
                await self._send_error(ctx, f"Invalid setting. Valid settings: {', '.join(valid_settings)}")
                return
            
            if not value:
                await self._send_error(ctx, f"Please provide a value for {setting}.")
                return
            
            async with self.config.guild(ctx.guild).ticket_channels() as channels_config:
                if setting == "category":
                    try:
                        category_id = int(value)
                        category = ctx.guild.get_channel(category_id)
                        if not category:
                            await self._send_error(ctx, f"Category with ID {category_id} not found in this server.")
                            return
                        if not isinstance(category, discord.CategoryChannel):
                            await self._send_error(ctx, f"Channel {category.name} is not a category.")
                            return
                        
                        channels_config["category_id"] = category_id
                        await self._send_success(ctx, f"✅ Active tickets category set to: {category.name}")
                        
                    except ValueError:
                        await self._send_error(ctx, "Category ID must be a number.")
                        
                elif setting == "archive_category":
                    if value.lower() in ["none", "null", "remove"]:
                        channels_config["archive_category_id"] = None
                        await self._send_success(ctx, "✅ Archive category has been removed.")
                    else:
                        try:
                            category_id = int(value)
                            category = ctx.guild.get_channel(category_id)
                            if not category:
                                await self._send_error(ctx, f"Category with ID {category_id} not found in this server.")
                                return
                            if not isinstance(category, discord.CategoryChannel):
                                await self._send_error(ctx, f"Channel {category.name} is not a category.")
                                return
                            
                            channels_config["archive_category_id"] = category_id
                            await self._send_success(ctx, f"✅ Archive category set to: {category.name}")
                            
                        except ValueError:
                            await self._send_error(ctx, "Archive category ID must be a number.")
                            
                elif setting == "prefix":
                    if len(value) > 20:
                        await self._send_error(ctx, "Channel prefix must be 20 characters or less.")
                        return
                    
                    # Sanitize prefix for Discord channel names
                    import re
                    sanitized_prefix = re.sub(r'[^a-z0-9\-]', '-', value.lower())
                    if not sanitized_prefix.endswith('-'):
                        sanitized_prefix += '-'
                    
                    channels_config["channel_prefix"] = sanitized_prefix
                    await self._send_success(ctx, f"✅ Channel prefix set to: {sanitized_prefix}")
                    
                elif setting == "auto_archive":
                    if value.lower() in ["true", "yes", "1", "on", "enable"]:
                        channels_config["auto_archive"] = True
                        await self._send_success(ctx, "✅ Auto-archiving enabled.")
                    elif value.lower() in ["false", "no", "0", "off", "disable"]:
                        channels_config["auto_archive"] = False
                        await self._send_success(ctx, "✅ Auto-archiving disabled.")
                    else:
                        await self._send_error(ctx, "Auto-archive value must be true or false.")
        
        else:
            await self._send_error(ctx, f"Unknown action: {action}. Use 'view', 'enable', 'disable', or 'set'.")

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

    @whmcs_admin.command(name="debug")
    async def admin_debug(self, ctx: commands.Context, ticket_id: str):
        """Debug ticket API calls to identify WHMCS configuration issues.
        
        Args:
            ticket_id: The ticket ID to debug (e.g., GLY-907775)
        """
        if not await self._check_permissions(ctx, "admin"):
            await self._send_error(ctx, "You don't have permission to debug API calls.")
            return
        
        api_client = await self._get_api_client(ctx.guild)
        if not api_client:
            await self._send_error(ctx, "WHMCS is not configured. Use `[p]whmcs admin config` to set up.")
            return
        
        embed = self._create_embed("🔍 WHMCS API Debug Report", f"Debugging ticket ID: **{ticket_id}**")
        
        try:
            async with api_client:
                # Clean up ticket ID - remove # prefix if present
                clean_ticket_id = ticket_id.lstrip('#').strip()
                
                debug_info = []
                debug_info.append(f"**Original ID:** {ticket_id}")
                debug_info.append(f"**Cleaned ID:** {clean_ticket_id}")
                debug_info.append(f"**Is Numeric:** {clean_ticket_id.isdigit()}")
                
                # Try both API parameter methods
                success_count = 0
                
                # Test 1: Try with ticketid parameter (for numeric IDs)
                try:
                    response1 = await api_client._make_request('GetTicket', {'ticketid': clean_ticket_id})
                    if response1.get("ticket"):
                        debug_info.append("✅ **ticketid parameter:** SUCCESS")
                        success_count += 1
                    else:
                        debug_info.append("❌ **ticketid parameter:** No ticket returned")
                except Exception as e:
                    debug_info.append(f"❌ **ticketid parameter:** Error - {e}")
                
                # Test 2: Try with ticketnum parameter (for alphanumeric IDs)
                try:
                    response2 = await api_client._make_request('GetTicket', {'ticketnum': clean_ticket_id})
                    if response2.get("ticket"):
                        debug_info.append("✅ **ticketnum parameter:** SUCCESS")
                        success_count += 1
                    else:
                        debug_info.append("❌ **ticketnum parameter:** No ticket returned")
                except Exception as e:
                    debug_info.append(f"❌ **ticketnum parameter:** Error - {e}")
                
                # Test 3: Try with tid parameter (some WHMCS versions)
                try:
                    response3 = await api_client._make_request('GetTicket', {'tid': clean_ticket_id})
                    if response3.get("ticket"):
                        debug_info.append("✅ **tid parameter:** SUCCESS")
                        success_count += 1
                    else:
                        debug_info.append("❌ **tid parameter:** No ticket returned")
                except Exception as e:
                    debug_info.append(f"❌ **tid parameter:** Error - {e}")
                
                embed.add_field(
                    name="🧪 API Parameter Tests",
                    value="\n".join(debug_info),
                    inline=False
                )
                
                # Diagnosis and recommendations
                if success_count == 0:
                    diagnosis = [
                        "🚨 **No API methods worked!**",
                        "",
                        "**Advanced WHMCS Troubleshooting:**",
                        "",
                        "**1. Department Restriction Issues:**",
                        "• Check if API credentials are restricted to specific departments",
                        "• Go to: Admin → API Credentials → Edit → Department Access",
                        "• Try setting 'All Departments' or add the ticket's department",
                        "",
                        "**2. Ticket Numbering Format Mismatch:**",
                        "• Check: Admin → Support → Settings → General",
                        "• Look for 'Ticket Number Format' settings",
                        "• Verify ticket numbering sequence configuration",
                        "",
                        "**3. Database/API Synchronization:**",
                        "• The ticket may exist in interface but not accessible via API",
                        "• Check if ticket was imported from another system",
                        "• Verify ticket exists in tbltickets database table",
                        "",
                        "**4. WHMCS Version-Specific Issues:**",
                        "• Some WHMCS versions have API inconsistencies",
                        "• Try: Admin → Support → Tickets → Search for GLY-907775",
                        "• Note the exact Ticket ID shown in WHMCS interface",
                        "",
                        "**5. Alternative Identification Methods:**",
                        "• Try searching by client email in ticket listing",
                        "• Use mask ID if different from ticket number",
                        "• Check if ticket has been merged or moved"
                    ]
                elif success_count == 1:
                    diagnosis = [
                        "⚠️ **Partial Success - Configuration Issue**",
                        "",
                        "One method worked, but the COG is using the wrong one.",
                        "This suggests a WHMCS configuration inconsistency.",
                        "",
                        "**Next Steps:**",
                        "• Note which parameter worked above",
                        "• Check WHMCS ticket numbering format settings",
                        "• Verify 'Support → Settings → General' configuration"
                    ]
                else:
                    diagnosis = [
                        "✅ **Multiple Methods Work**",
                        "",
                        "The API is working correctly with multiple parameters.",
                        "The issue might be in the COG's detection logic.",
                        "",
                        "**This is useful debugging info - please share these results!**"
                    ]
                
                embed.add_field(
                    name="💡 Diagnosis & Recommendations",
                    value="\n".join(diagnosis),
                    inline=False
                )
                
                await ctx.send(embed=embed)
                
        except WHMCSAuthenticationError:
            await self._send_error(ctx, "❌ Authentication failed. Check your API credentials.")
        except WHMCSRateLimitError:
            await self._send_error(ctx, "❌ Rate limit exceeded. Please try again later.")
        except WHMCSAPIError as e:
            await self._send_error(ctx, f"❌ API debug failed: {e}")
        except Exception as e:
            log.exception("Error in admin_debug command")
            await self._send_error(ctx, f"❌ Debug test failed: {e}")

    @whmcs_admin.command(name="findticket")
    async def admin_find_ticket(self, ctx: commands.Context, search_term: str):
        """Find tickets by searching client email or partial ticket number.
        
        This helps locate tickets when direct ID lookup fails.
        
        Args:
            search_term: Email address or partial ticket identifier to search for
        """
        if not await self._check_permissions(ctx, "admin"):
            await self._send_error(ctx, "You don't have permission to search tickets.")
            return
        
        api_client = await self._get_api_client(ctx.guild)
        if not api_client:
            await self._send_error(ctx, "WHMCS is not configured. Use `[p]whmcs admin config` to set up.")
            return
        
        try:
            async with api_client:
                # Get recent tickets and filter for matches
                response = await api_client.get_tickets(limit=50)
                
                if not response.get("tickets") or not response["tickets"].get("ticket"):
                    await self._send_error(ctx, f"No tickets found matching '{search_term}'.")
                    return
                
                tickets = response["tickets"]["ticket"]
                if not isinstance(tickets, list):
                    tickets = [tickets]
                
                # Filter tickets that match the search term
                search_lower = search_term.lower()
                matching_tickets = []
                
                for ticket in tickets:
                    # Check if search term matches email, subject, ticket IDs, or client name
                    matches = []
                    
                    # Check email
                    if ticket.get('email') and search_lower in ticket['email'].lower():
                        matches.append(f"email: {ticket['email']}")
                    
                    # Check subject
                    if ticket.get('subject') and search_lower in ticket['subject'].lower():
                        matches.append(f"subject: {ticket['subject']}")
                    
                    # Check ticket IDs
                    for id_field in ['tid', 'ticketnum', 'maskid']:
                        if ticket.get(id_field) and search_lower in str(ticket[id_field]).lower():
                            matches.append(f"{id_field}: {ticket[id_field]}")
                    
                    # Check client name
                    if ticket.get('name') and search_lower in ticket['name'].lower():
                        matches.append(f"name: {ticket['name']}")
                    
                    if matches:
                        matching_tickets.append((ticket, matches))
                
                if not matching_tickets:
                    await self._send_error(ctx, f"No tickets found matching '{search_term}' in recent tickets.")
                    return
                
                embed = self._create_embed("🔍 Ticket Search Results", f"Search term: **{search_term}** • Found {len(matching_tickets)} matches")
                
                for ticket_data, matches in matching_tickets[:5]:  # Limit to first 5 results
                    ticket = ticket_data
                    # Show ALL possible ID fields to help identify the correct one
                    id_info = []
                    
                    if ticket.get('tid'):
                        id_info.append(f"**tid:** {ticket['tid']}")
                    if ticket.get('ticketnum'):
                        id_info.append(f"**ticketnum:** {ticket['ticketnum']}")
                    if ticket.get('maskid'):
                        id_info.append(f"**maskid:** {ticket['maskid']}")
                    if ticket.get('id'):
                        id_info.append(f"**id:** {ticket['id']}")
                    
                    status_emoji = {
                        "Open": "🟢",
                        "Answered": "🔵",
                        "Customer-Reply": "🟡",
                        "Closed": "🔴"
                    }.get(ticket.get("status"), "❓")
                    
                    ticket_info = (
                        f"📊 **Status:** {status_emoji} {ticket.get('status')}\n"
                        f"🏢 **Department:** {ticket.get('department', 'N/A')}\n"
                        f"📧 **Email:** {ticket.get('email', 'N/A')}\n"
                        f"📅 **Date:** {ticket.get('date', 'N/A')}"
                    )
                    
                    if id_info:
                        ticket_info = "\n".join(id_info) + "\n" + ticket_info
                    
                    subject = ticket.get('subject', 'No Subject')
                    if len(subject) > 40:
                        subject = subject[:37] + "..."
                    
                    embed.add_field(
                        name=f"🎫 {subject}",
                        value=ticket_info,
                        inline=False
                    )
                
                embed.set_footer(text="WHMCS Integration • Use any of the ID values with ticket commands")
                await ctx.send(embed=embed)
                
        except WHMCSAuthenticationError:
            await self._send_error(ctx, "❌ Authentication failed. Check your API credentials.")
        except WHMCSRateLimitError:
            await self._send_error(ctx, "❌ Rate limit exceeded. Please try again later.")
        except WHMCSAPIError as e:
            await self._send_error(ctx, f"❌ API search failed: {e}")
        except Exception as e:
            log.exception("Error in admin_find_ticket command")
            await self._send_error(ctx, f"❌ Ticket search failed: {e}")
    
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
                        f"📊 **Status:** {status_emoji} {invoice.get('status')}\n"
                        f"💰 **Total:** ${invoice.get('total', '0.00')}\n"
                        f"📅 **Due Date:** {invoice.get('duedate', 'N/A')}"
                    )
                    embed.add_field(
                        name=f"📄 Invoice #{invoice.get('invoicenum')} (ID: {invoice.get('id')})",
                        value=invoice_info,
                        inline=False  # Full width for better readability
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
                
                embed = self._create_embed(f"📄 Invoice Details")
                embed.description = f"**Invoice #{invoice.get('invoicenum')}** • {status_emoji} {invoice.get('status')}"
                
                # Basic invoice information with consistent emoji formatting
                embed.add_field(
                    name="💰 Financial Details",
                    value=(
                        f"💵 **Subtotal:** ${invoice.get('subtotal', '0.00')}\n"
                        f"🏛️ **Tax:** ${invoice.get('tax', '0.00')}\n"
                        f"💰 **Total:** ${invoice.get('total', '0.00')}\n"
                        f"⚖️ **Balance:** ${invoice.get('balance', '0.00')}"
                    ),
                    inline=False
                )
                
                # Dates
                embed.add_field(
                    name="📅 Important Dates",
                    value=(
                        f"📅 **Created:** {invoice.get('date', 'N/A')}\n"
                        f"⏰ **Due Date:** {invoice.get('duedate', 'N/A')}\n"
                        f"✅ **Date Paid:** {invoice.get('datepaid', 'Not paid') if invoice.get('datepaid') else 'Not paid'}"
                    ),
                    inline=False
                )
                
                # Client information
                if invoice.get("userid"):
                    client_name = f"{invoice.get('firstname', '')} {invoice.get('lastname', '')}".strip()
                    embed.add_field(
                        name="👤 Client Information",
                        value=(
                            f"🆔 **Client ID:** {invoice.get('userid')}\n"
                            f"👤 **Name:** {client_name or 'N/A'}\n"
                            f"🏢 **Company:** {invoice.get('companyname', 'N/A')}"
                        ),
                        inline=False
                    )
                
                # Payment method
                if invoice.get("paymentmethod"):
                    embed.add_field(
                        name="💳 Payment Details",
                        value=f"💳 **Method:** {invoice.get('paymentmethod')}",
                        inline=False
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
                "• `tickets [client_id] [page]` - List all tickets\n"
                "• `open [client_id] [page]` - List open tickets only\n"
                "• `closed [client_id] [page]` - List closed tickets only\n"
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
        await self._list_tickets_with_status(ctx, client_id, page, None)
    
    @whmcs_support.command(name="open")
    async def support_open_tickets(self, ctx: commands.Context, client_id: Optional[int] = None, page: int = 1):
        """List open support tickets only, optionally filtered by client.
        
        Args:
            client_id: Optional client ID to filter tickets
            page: Page number (default: 1)
        """
        await self._list_tickets_with_status(ctx, client_id, page, "Open")
    
    @whmcs_support.command(name="closed")
    async def support_closed_tickets(self, ctx: commands.Context, client_id: Optional[int] = None, page: int = 1):
        """List closed support tickets only, optionally filtered by client.
    
        @whmcs_support.command(name="channel")
        async def support_ticket_channel(self, ctx: commands.Context, ticket_id: str):
            """Explicitly create a Discord channel for a WHMCS ticket.
    
            Example:
                [p]whmcs support channel GLY-907775
            """
            if not await self._check_permissions(ctx, "support"):
                await self._send_error(ctx, "You don't have permission to create ticket channels.")
                return
            api_client = await self._get_api_client(ctx.guild)
            if not api_client:
                await self._send_error(ctx, "WHMCS is not configured. Use `[p]whmcs admin config` to set up.")
                return
            try:
                async with api_client:
                    # Use the same robust lookup logic as support_ticket
                    response = await api_client.get_ticket(ticket_id)
                    found_ticket = None
                    if not response.get("ticket"):
                        tickets_response = await api_client.get_tickets(limit=50)
                        if tickets_response.get("tickets") and tickets_response["tickets"].get("ticket"):
                            tickets = tickets_response["tickets"]["ticket"]
                            if not isinstance(tickets, list):
                                tickets = [tickets]
                            search_lower = ticket_id.lower().lstrip('#').strip()
                            for ticket in tickets:
                                for id_field in ['tid', 'ticketnum', 'maskid']:
                                    if ticket.get(id_field) and search_lower == str(ticket[id_field]).lower().lstrip('#').strip():
                                        found_ticket = ticket
                                        break
                                if found_ticket:
                                    break
                    else:
                        found_ticket = response["ticket"]
                    if not found_ticket:
                        await self._send_error(ctx, f"Ticket {ticket_id} not found.")
                        return
                    # Attempt to create the channel
                    channel = await self._get_or_create_ticket_channel(ctx.guild, str(found_ticket.get("tid") or found_ticket.get("ticketnum") or found_ticket.get("maskid")), found_ticket)
                    if channel:
                        await self._send_success(ctx, f"Channel <#{channel.id}> created for ticket {ticket_id}.")
                    else:
                        await self._send_error(ctx, "Failed to create ticket channel. Check category and permissions.")
            except Exception as e:
                import logging
                logging.getLogger("red.WHMCS").exception("Error in support_ticket_channel command")
                await self._send_error(ctx, f"An unexpected error occurred: {e}")
        Args:
            client_id: Optional client ID to filter tickets
            page: Page number (default: 1)
        """
        await self._list_tickets_with_status(ctx, client_id, page, "Closed")
    
    async def _list_tickets_with_status(self, ctx: commands.Context, client_id: Optional[int], page: int, status_filter: Optional[str]):
        """Internal method to list tickets with optional status filtering.
        
        Args:
            ctx: The command context
            client_id: Optional client ID to filter tickets
            page: Page number
            status_filter: Optional status to filter by (Open, Closed, etc.)
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
                limit = 5  # Reduced from 10 to match client list formatting
                offset = (page - 1) * limit
                
                # Get tickets (status filtering will be done client-side)
                response = await api_client.get_tickets(client_id=client_id, limit=limit, offset=offset)
                
                if not response.get("tickets"):
                    filter_parts = []
                    if client_id:
                        filter_parts.append(f"client {client_id}")
                    if status_filter:
                        filter_parts.append(f"status '{status_filter}'")
                    filter_text = f" for {' and '.join(filter_parts)}" if filter_parts else ""
                    await self._send_error(ctx, f"No tickets found{filter_text}.")
                    return
                
                # Handle both single ticket and list response
                tickets = response["tickets"]["ticket"]
                if not isinstance(tickets, list):
                    tickets = [tickets]
                
                # Filter tickets by status if specified (client-side filtering as backup)
                if status_filter:
                    tickets = [ticket for ticket in tickets if ticket.get("status") == status_filter]
                
                total = len(tickets)  # Use filtered count for more accurate pagination
                total_pages = (total + limit - 1) // limit if total > 0 else 1
                
                # Build filter description
                filter_parts = []
                if client_id:
                    filter_parts.append(f"Client {client_id}")
                if status_filter:
                    filter_parts.append(f"{status_filter} Status")
                filter_text = f" • {' & '.join(filter_parts)}" if filter_parts else ""
                
                if await ctx.embed_requested():
                    status_icon = "🎫"
                    if status_filter == "Open":
                        status_icon = "🟢"
                    elif status_filter == "Closed":
                        status_icon = "🔴"
                    
                    embed = self._create_embed(f"{status_icon} Support Tickets Directory")
                    embed.description = f"**Page {page} of {total_pages}**{filter_text} • {total} total tickets"
                    
                    # Show tickets for current page
                    start_idx = (page - 1) * limit
                    end_idx = start_idx + limit
                    page_tickets = tickets[start_idx:end_idx]
                    
                    for ticket in page_tickets:
                        # Auto-create ticket channel if enabled and not already created
                        if ctx.guild and await self.config.guild(ctx.guild).ticket_channels.enabled():
                            await self._get_or_create_ticket_channel(ctx.guild, str(ticket.get("tid") or ticket.get("ticketnum") or ticket.get("maskid")), ticket)
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
                        
                        # Build ticket ID display - intelligently categorize the IDs
                        id_display_parts = []
                        tid_value = ticket.get('tid')
                        
                        if tid_value:
                            # Determine if tid is actually numeric (internal) or alphanumeric (ticket number)
                            if str(tid_value).isdigit():
                                id_display_parts.append(f"Internal: {tid_value}")
                            else:
                                id_display_parts.append(f"Ticket Number: {tid_value}")
                        
                        if ticket.get('ticketnum') and ticket.get('ticketnum') != str(tid_value):
                            id_display_parts.append(f"Number: {ticket.get('ticketnum')}")
                        if ticket.get('maskid'):
                            id_display_parts.append(f"Mask: {ticket.get('maskid')}")
                        
                        id_display = " • ".join(id_display_parts) if id_display_parts else str(tid_value) if tid_value else 'N/A'
                        
                        ticket_info = (
                            f"🆔 **IDs:** {id_display}\n"
                            f"📊 **Status:** {status_emoji} {ticket.get('status')}\n"
                            f"⚡ **Priority:** {priority_emoji} {ticket.get('priority')}\n"
                            f"🏢 **Department:** {ticket.get('department', 'N/A')}\n"
                            f"💬 **Last Reply:** {ticket.get('lastreply', 'N/A')}"
                        )
                        
                        subject = ticket.get('subject', 'No Subject')
                        if len(subject) > 35:  # Shorter for full-width display
                            subject = subject[:32] + "..."
                        
                        embed.add_field(
                            name=f"🎫 {subject}",
                            value=ticket_info,
                            inline=False  # Full width for better readability
                        )

                        # Show initial message and up to 2 most recent replies for each ticket
                        if ticket.get("message"):
                            message = ticket["message"]
                            if len(message) > 300:
                                message = message[:297] + "..."
                            embed.add_field(
                                name="💬 Initial Message",
                                value=f"```{message}```",
                                inline=False
                            )
                        if ticket.get("replies"):
                            replies = ticket["replies"]
                            if isinstance(replies, dict) and "reply" in replies:
                                replies = replies["reply"]
                            if not isinstance(replies, list):
                                replies = [replies]
                            for reply in replies[-2:]:
                                author = reply.get("admin", reply.get("name", "Unknown"))
                                date = reply.get("date", "N/A")
                                rmsg = reply.get("message", "")
                                if len(rmsg) > 200:
                                    rmsg = rmsg[:197] + "..."
                                embed.add_field(
                                    name=f"💬 Reply by {author} on {date}",
                                    value=f"```{rmsg}```",
                                    inline=False
                                )
                    
                    # Add navigation hints in footer if multiple pages
                    if total_pages > 1:
                        # Determine which command was used for navigation hints
                        cmd_name = "tickets"
                        if status_filter == "Open":
                            cmd_name = "open"
                        elif status_filter == "Closed":
                            cmd_name = "closed"
                        
                        navigation_text = f"WHMCS Integration • Page {page}/{total_pages}"
                        if page > 1:
                            navigation_text += f" • Use `{ctx.prefix}whmcs support {cmd_name}"
                            if client_id:
                                navigation_text += f" {client_id}"
                            navigation_text += f" {page-1}` for previous"
                        if page < total_pages:
                            navigation_text += f" • Use `{ctx.prefix}whmcs support {cmd_name}"
                            if client_id:
                                navigation_text += f" {client_id}"
                            navigation_text += f" {page+1}` for next"
                        embed.set_footer(text=navigation_text)
                    else:
                        embed.set_footer(text=f"WHMCS Integration • {total} total tickets")
                    
                    await ctx.send(embed=embed)
                else:
                    # Plain text format for when embeds are disabled
                    output = [f"🎫 **Support Tickets Directory - Page {page} of {total_pages}**"]
                    if filter_text:
                        output[0] += filter_text
                    output.append(f"📊 {total} total tickets\n")
                    
                    # Show tickets for current page
                    start_idx = (page - 1) * limit
                    end_idx = start_idx + limit
                    page_tickets = tickets[start_idx:end_idx]
                    
                    for ticket in page_tickets:
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
                        
                        # Build ticket ID display - intelligently categorize the IDs
                        id_display_parts = []
                        tid_value = ticket.get('tid')
                        
                        if tid_value:
                            # Determine if tid is actually numeric (internal) or alphanumeric (ticket number)
                            if str(tid_value).isdigit():
                                id_display_parts.append(f"Internal: {tid_value}")
                            else:
                                id_display_parts.append(f"Ticket Number: {tid_value}")
                        
                        if ticket.get('ticketnum') and ticket.get('ticketnum') != str(tid_value):
                            id_display_parts.append(f"Number: {ticket.get('ticketnum')}")
                        if ticket.get('maskid'):
                            id_display_parts.append(f"Mask: {ticket.get('maskid')}")
                        
                        id_display = " • ".join(id_display_parts) if id_display_parts else str(tid_value) if tid_value else 'N/A'
                        
                        subject = ticket.get('subject', 'No Subject')
                        output.append(f"🎫 **{subject}**")
                        output.append(f"   🆔 IDs: {id_display}")
                        output.append(f"   📊 Status: {status_emoji} {ticket.get('status')}")
                        output.append(f"   ⚡ Priority: {priority_emoji} {ticket.get('priority')}")
                        output.append(f"   🏢 Department: {ticket.get('department', 'N/A')}")
                        output.append(f"   💬 Last Reply: {ticket.get('lastreply', 'N/A')}")
                        output.append("")  # Empty line for spacing
                    
                    # Add navigation hints for text format too
                    if total_pages > 1:
                        # Determine which command was used for navigation hints
                        cmd_name = "tickets"
                        if status_filter == "Open":
                            cmd_name = "open"
                        elif status_filter == "Closed":
                            cmd_name = "closed"
                        
                        output.append("📄 **Navigation:**")
                        if page > 1:
                            cmd = f"{ctx.prefix}whmcs support {cmd_name}"
                            if client_id:
                                cmd += f" {client_id}"
                            cmd += f" {page-1}"
                            output.append(f"   ⬅️ Previous: `{cmd}`")
                        if page < total_pages:
                            cmd = f"{ctx.prefix}whmcs support {cmd_name}"
                            if client_id:
                                cmd += f" {client_id}"
                            cmd += f" {page+1}"
                            output.append(f"   ➡️ Next: `{cmd}`")
                    
                    await ctx.send("\n".join(output))
                
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
    async def support_ticket(self, ctx: commands.Context, ticket_id: str):
        """View detailed information for a specific support ticket.
        
        Args:
            ticket_id: The ticket ID to view (e.g., GLY-907775 or 123456)
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
                
                # Fallback: If not found, search recent tickets for a match (admin_find_ticket logic)
                if not response.get("ticket"):
                    # Try to find in recent tickets
                    tickets_response = await api_client.get_tickets(limit=50)
                    found_ticket = None
                    if tickets_response.get("tickets") and tickets_response["tickets"].get("ticket"):
                        tickets = tickets_response["tickets"]["ticket"]
                        if not isinstance(tickets, list):
                            tickets = [tickets]
                        search_lower = ticket_id.lower().lstrip('#').strip()
                        for ticket in tickets:
                            for id_field in ['tid', 'ticketnum', 'maskid']:
                                if ticket.get(id_field) and search_lower == str(ticket[id_field]).lower().lstrip('#').strip():
                                    found_ticket = ticket
                                    break
                            if found_ticket:
                                break
                    if found_ticket:
                        ticket = found_ticket
                    else:
                        await self._send_error(ctx, f"Ticket {ticket_id} not found.")
                        return
                else:
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
                
                subject = ticket.get('subject', 'No Subject')
                embed = self._create_embed(f"🎫 Ticket Details")
                embed.description = f"**#{ticket.get('tid')} - {subject}**"
                
                # Status and priority with consistent emoji formatting
                embed.add_field(
                    name="📊 Status Information",
                    value=(
                        f"📊 **Status:** {status_emoji} {ticket.get('status')}\n"
                        f"⚡ **Priority:** {priority_emoji} {ticket.get('priority')}\n"
                        f"🏢 **Department:** {ticket.get('department', 'N/A')}"
                    ),
                    inline=False
                )
                
                # Client information
                embed.add_field(
                    name="👤 Client Information",
                    value=(
                        f"🆔 **Client ID:** {ticket.get('userid', 'N/A')}\n"
                        f"👤 **Name:** {ticket.get('name', 'N/A')}\n"
                        f"📧 **Email:** {ticket.get('email', 'N/A')}"
                    ),
                    inline=False
                )
                
                # Timing information
                embed.add_field(
                    name="📅 Timing Information",
                    value=(
                        f"📅 **Created:** {ticket.get('date', 'N/A')}\n"
                        f"💬 **Last Reply:** {ticket.get('lastreply', 'N/A')}"
                    ),
                    inline=False
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
                
                # Reply count and reply details
                if ticket.get("replies"):
                    replies = ticket["replies"]
                    if isinstance(replies, dict) and "reply" in replies:
                        replies = replies["reply"]
                    if not isinstance(replies, list):
                        replies = [replies]
                    reply_count = len(replies)
                    embed.add_field(
                        name="💬 Replies",
                        value=f"{reply_count} reply(s)",
                        inline=True
                    )
                    # Show up to 3 most recent replies
                    for reply in replies[-3:]:
                        author = reply.get("admin", reply.get("name", "Unknown"))
                        date = reply.get("date", "N/A")
                        message = reply.get("message", "")
                        if len(message) > 300:
                            message = message[:297] + "..."
                        embed.add_field(
                            name=f"💬 Reply by {author} on {date}",
                            value=f"```{message}```",
                            inline=False
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
    async def support_reply(self, ctx: commands.Context, ticket_id: str, *, message: str):
        """Reply to a support ticket.
        
        Args:
            ticket_id: The ticket ID to reply to (e.g., GLY-907775 or 123456)
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