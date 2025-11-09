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

# View specific ticket
[p]whmcs support ticket 98765

# Reply to ticket (support+ role)
[p]whmcs support reply 98765 "Thank you for contacting us..."
```

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