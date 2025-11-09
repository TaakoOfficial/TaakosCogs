# WHMCS Integration COG

A comprehensive Red-DiscordBot cog for integrating Discord with WHMCS (Web Host Manager Complete Solution) billing and client management system.

## Features

### 🏢 Client Management
- **List Clients**: Browse clients with pagination support
- **View Client Details**: Comprehensive client information display
- **Search Clients**: Find clients by name, email, or company
- **Client Statistics**: View account status, products, domains, and more

### 💰 Billing Operations
- **Invoice Management**: View and manage client invoices
- **Payment Tracking**: Monitor payment history and status
- **Credit Management**: Add account credits for clients
- **Balance Inquiries**: Check client account balances

### 🎫 Support System
- **Ticket Management**: View and manage support tickets
- **Ticket Replies**: Respond to customer inquiries
- **Support Statistics**: Track support metrics and status
- **🚀 Automatic Discord Channels**: Creates dedicated channels for tickets with auto-reply integration

### 💬 Revolutionary Discord Channel Integration
- **Auto-Channel Creation**: Automatically creates Discord channels for WHMCS tickets
- **Seamless Auto-Reply**: Messages in ticket channels automatically post to WHMCS
- **Team Collaboration**: Multiple team members can collaborate in dedicated ticket channels
- **Smart Organization**: Configurable categories for active and archived tickets
- **Visual Feedback**: Reaction confirmations for successful WHMCS integration
- **Universal Compatibility**: Works with all ticket ID formats (numeric and alphanumeric)

### ⚙️ Administration
- **API Configuration**: Secure credential management
- **Permission Management**: Role-based access control
- **Connection Testing**: Verify WHMCS connectivity
- **Rate Limiting**: Automatic API throttling

## Installation

1. **Install the COG**:
   ```
   [p]repo add taako-cogs https://github.com/TaakoOfficial/TaakosCogs
   [p]cog install taakoscogs WHMCS
   [p]load WHMCS
   ```

2. **Install Dependencies**:
   The cog requires `aiohttp` for async HTTP requests. This is automatically installed with the cog.

## Configuration

### 1. WHMCS API Setup

First, configure your WHMCS API credentials in your WHMCS admin panel:

1. Go to **Setup > General Settings > Security > API Credentials**
2. Create a new API credential pair
3. Note the **Identifier** and **Secret**
4. Optionally configure an **Access Key** for IP bypass

### 2. Bot Configuration

Configure the cog with your WHMCS details:

```
[p]whmcs admin config
```

This will guide you through setting up:
- WHMCS installation URL
- API credentials (identifier/secret)
- Access key (optional)
- Rate limiting settings

### 3. Permission Setup

Configure role-based permissions:

```
[p]whmcs admin permissions
```

Available permission levels:
- **Admin**: Full access to all functions and configuration
- **Billing**: Access to billing and client management
- **Support**: Access to support tickets and read-only client info
- **Readonly**: View-only access to basic information

### 4. 🚀 Automatic Ticket Channel Setup

The revolutionary Discord channel integration creates dedicated channels for each WHMCS ticket with automatic reply synchronization. Here's how to set it up:

#### Step 1: Create Discord Categories

First, create categories in your Discord server to organize ticket channels:

1. **Right-click in your Discord server** → "Create Category"
2. **Create two categories**:
   - `🎫 Active Tickets` - For open/active support tickets
   - `📁 Archived Tickets` - For closed/resolved tickets (optional)

#### Step 2: Get Category IDs

To get the category IDs needed for configuration:

1. **Enable Developer Mode** in Discord:
   - User Settings → Advanced → Developer Mode (ON)
2. **Get Category IDs**:
   - Right-click on the "🎫 Active Tickets" category → "Copy ID"
   - Right-click on the "📁 Archived Tickets" category → "Copy ID"

#### Step 3: Configure Ticket Channels

Use the WHMCS admin commands to set up the channel integration:

```bash
# Set the active tickets category (REQUIRED)
[p]whmcs admin channels set category ACTIVE_CATEGORY_ID

# Set the archive category (OPTIONAL)
[p]whmcs admin channels set archive_category ARCHIVE_CATEGORY_ID

# Customize channel prefix (default: "whmcs-ticket-")
[p]whmcs admin channels set prefix "support-"

# Enable auto-archiving when tickets close (default: true)
[p]whmcs admin channels set auto_archive true

# Enable automatic ticket channel creation
[p]whmcs admin channels enable
```

#### Example Configuration

```bash
# Example setup for a server
[p]whmcs admin channels set category 987654321098765432
[p]whmcs admin channels set archive_category 876543210987654321
[p]whmcs admin channels set prefix "whmcs-ticket-"
[p]whmcs admin channels set auto_archive true
[p]whmcs admin channels enable
```

#### Step 4: Set Channel Permissions

The system automatically manages channel permissions, but you may want to ensure:

1. **Support/Admin roles** have access to the ticket categories
2. **WHMCS bot** has permission to create channels in the categories
3. **@everyone** role cannot see the ticket categories (for privacy)

#### How It Works

Once configured, the magic happens automatically:

1. **View any ticket**: `[p]whmcs support ticket GLY-907775`
2. **Auto-channel creation**: Creates `#whmcs-ticket-gly-907775` in the Active Tickets category
3. **Team collaboration**: Support team can discuss in the dedicated channel
4. **Auto-reply to WHMCS**: Any message typed in the channel automatically posts to the WHMCS ticket
5. **Visual confirmation**: ✅ reaction on messages confirms successful WHMCS posting
6. **Auto-archiving**: When tickets close, channels move to the Archived category (if configured)

#### Configuration Options

| Setting | Description | Default | Required |
|---------|-------------|---------|----------|
| `enabled` | Enable/disable automatic channel creation | `False` | Yes |
| `category_id` | Discord category ID for active ticket channels | `None` | Yes |
| `archive_category_id` | Discord category ID for archived channels | `None` | No |
| `channel_prefix` | Prefix for ticket channel names | `"whmcs-ticket-"` | No |
| `auto_archive` | Automatically move channels when tickets close | `True` | No |

## Usage Examples

### Client Management

```
# List clients (paginated)
[p]whmcs client list
[p]whmcs client list 2

# View specific client
[p]whmcs client view 12345

# Search for clients
[p]whmcs client search john@example.com
[p]whmcs client search "Acme Corporation"
```

### Billing Operations

```
# View client invoices
[p]whmcs billing invoices 12345

# View specific invoice
[p]whmcs billing invoice 67890

# Add account credit (admin only)
[p]whmcs billing credit 12345 25.00 "Promotional credit"
```

### Support System

```
# List all support tickets
[p]whmcs support tickets

# List tickets for specific client
[p]whmcs support tickets 12345

# View specific ticket (creates auto-channel if enabled)
[p]whmcs support ticket 98765
[p]whmcs support ticket GLY-907775

# Reply to ticket (support+ role)
[p]whmcs support reply 98765 "Thank you for contacting us..."

# Filter tickets by status
[p]whmcs support open      # Open tickets only
[p]whmcs support closed    # Closed tickets only
```

### 🚀 Automatic Discord Channel Integration

Once ticket channels are configured, the system works seamlessly:

```
# Step 1: View any ticket to create its channel
[p]whmcs support ticket GLY-907775

# Step 2: System automatically creates #whmcs-ticket-gly-907775 channel
# Step 3: Team members join the channel to collaborate
# Step 4: Type messages directly in the channel - they auto-post to WHMCS!

# Example workflow:
User types in #whmcs-ticket-gly-907775: "I've identified the issue and am working on a fix."
→ Message automatically appears in WHMCS ticket GLY-907775
→ ✅ reaction confirms successful posting
→ Customer receives update in WHMCS
```

#### Channel Features

- **Automatic Creation**: Channels created when viewing tickets
- **Smart Naming**: Channels named `whmcs-ticket-[ticket-id]` (configurable)
- **Permission Sync**: Channels inherit support role permissions
- **Auto-Reply**: Messages in channel automatically post to WHMCS
- **Visual Feedback**: ✅/❌ reactions confirm WHMCS integration
- **Rich Information**: Channel topic includes ticket details
- **Team Collaboration**: Multiple team members can work together
- **Archive Management**: Closed tickets move to archive category

### Administration

```
# Test API connection
[p]whmcs admin test

# View current configuration
[p]whmcs admin config view

# Configure WHMCS URL
[p]whmcs admin config url https://your-whmcs.com

# Configure API credentials
[p]whmcs admin config identifier your_api_identifier
[p]whmcs admin config secret your_api_secret

# Set rate limit
[p]whmcs admin config ratelimit 120

# Manage permissions
[p]whmcs admin permissions add billing @Billing Role
[p]whmcs admin permissions remove support @Old Role

# Configure ticket channels
[p]whmcs admin channels view
[p]whmcs admin channels set category 123456789012345678
[p]whmcs admin channels enable
```

## Security Features

### 🔐 Secure Credential Storage
- API credentials are encrypted using Red-Bot's secure config system
- No sensitive data stored in plaintext
- Automatic credential validation

### 🛡️ Role-Based Permissions
- Granular permission system with four access levels
- Guild owner and bot owner always have full access
- Configurable role assignments per permission level

### ⚡ Rate Limiting
- Configurable API rate limiting (default: 60 requests/minute)
- Automatic backoff on rate limit exceeded
- Per-guild rate limiting configuration

### 🔍 Audit Logging
- All administrative actions are logged
- API call logging with error tracking
- User action audit trails

## Error Handling

The cog includes comprehensive error handling:

- **Authentication Errors**: Clear messaging for credential issues
- **Rate Limiting**: Automatic handling with user feedback
- **Network Issues**: Retry logic with exponential backoff
- **Invalid Input**: Validation with helpful error messages
- **Permission Denied**: Clear permission requirement messaging

## Troubleshooting

### Common Issues

**"WHMCS is not configured"**
- Run `[p]whmcs admin config` to set up your API credentials
- Ensure your WHMCS URL is accessible from the bot's location

**"Authentication failed"**
- Verify your API identifier and secret in WHMCS admin panel
- Check that the API credentials have proper permissions
- Ensure IP restrictions are configured correctly (use access key if needed)

**"Rate limit exceeded"**
- Wait for the rate limit window to reset
- Consider increasing the rate limit in settings if you have many users
- Check for any automated processes hitting the API

**"Permission denied"**
- Verify you have the required role for the command
- Check role configuration with `[p]whmcs admin permissions`
- Contact a server admin to adjust your permissions

**"Ticket channels not working"**
- Check current settings: `[p]whmcs admin channels view`
- Verify channels are enabled and category is set
- Ensure the bot has "Manage Channels" permission in the category
- Verify the category exists and is accessible to the bot
- Test with a simple ticket: `[p]whmcs support ticket [ticket_id]`

**"Auto-replies not working"**
- Check that the user has Support+ permissions for WHMCS commands
- Verify the ticket ID matches between Discord channel and WHMCS
- Look for ❌ reactions indicating WHMCS API errors
- Test manual reply: `[p]whmcs support reply [ticket_id] "test message"`

### Debug Mode

Enable debug logging to troubleshoot issues:

```python
# In Red's console
[p]set api
[p]debug WHMCS
```

This will provide detailed logging of API calls and errors.

## API Compatibility

This cog is compatible with:
- **WHMCS Version**: 7.0+ (tested with 8.x)
- **API Version**: All current WHMCS API versions
- **Authentication**: Both API credentials and admin username/password
- **SSL**: Requires HTTPS for secure communication

## Support

For support with this cog:

1. **Check the troubleshooting section above**
2. **Review Red-Bot logs** for error details
3. **Verify WHMCS API functionality** outside of Discord
4. **Check WHMCS system logs** for API-related errors

## Contributing

Contributions are welcome! Please:

1. Fork the repository
2. Create a feature branch
3. Add tests for new functionality
4. Ensure code follows project standards
5. Submit a pull request

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Changelog

### Version 1.0.7
- **IMPROVEMENT**: Changed default ticket channel prefix to "whmcs-ticket-"
- Better channel organization and identification in Discord servers
- Updated all documentation examples with new prefix format

### Version 1.0.6
- **NEW FEATURE**: Dedicated admin commands for ticket channel configuration
- Added user-friendly `[p]whmcs admin channels` command group
- Updated documentation with correct WHMCS COG commands
- Enhanced setup process with proper command validation

### Version 1.0.5
- **CRITICAL FIX**: Resolved "Ticket ID Not Found" error for alphanumeric ticket IDs
- Enhanced API client to handle both numeric and alphanumeric ticket formats
- Improved automatic channel creation compatibility with all WHMCS installations

### Version 1.0.4
- **REVOLUTIONARY FEATURE**: Automatic Discord channel creation for WHMCS tickets
- Auto-reply integration: Messages in Discord channels automatically post to WHMCS
- Team collaboration features with dedicated ticket channels
- Smart channel management with configurable categories
- Visual feedback system with reaction confirmations

### Version 1.0.3
- Fixed ticket ID parameter handling for alphanumeric formats
- Enhanced support for mixed ticket ID formats (GLY-907775, ABC-123, etc.)

### Version 1.0.2
- Added ticket status filtering (open/closed commands)
- Improved pagination and navigation for ticket lists
- Enhanced UI consistency across all ticket commands

### Version 1.0.1
- Applied consistent embed formatting across all commands
- Enhanced visual indicators and emoji usage
- Improved user experience with full-width field displays

### Version 1.0.0
- Initial release
- Client management functionality
- Basic billing operations
- Support ticket integration
- Admin configuration system
- Role-based permissions
- Rate limiting and error handling

---

**Note**: This cog requires a valid WHMCS installation and API access. WHMCS is a commercial product - please ensure you have proper licensing for your WHMCS installation.