# Changelog

All notable changes to the WHMCS COG will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.3] - 2025-11-09

### Fixed
- **Ticket ID Parameter Type**: Fixed ticket commands to accept alphanumeric ticket IDs
  - `[p]whmcs support ticket <ticket_id>` now accepts IDs like "GLY-907775"
  - `[p]whmcs support reply <ticket_id> <message>` now accepts alphanumeric ticket IDs
  - Updated API client methods to handle string ticket IDs instead of integers only
  - Resolved "Converting to int failed" error for alphanumeric ticket identifiers

### Technical Details
- Changed `ticket_id` parameter type from `int` to `str` in support commands
- Updated `get_ticket()` and `add_ticket_reply()` API methods to accept string parameters
- Enhanced parameter documentation to clarify alphanumeric ID support
- Maintains backward compatibility with numeric-only ticket IDs

## [1.0.2] - 2025-11-09

### Added
- **Ticket Status Filtering**: New commands to filter tickets by status
  - `[p]whmcs support open [client_id] [page]` - List open tickets only
  - `[p]whmcs support closed [client_id] [page]` - List closed tickets only
  - Enhanced `[p]whmcs support tickets` command with improved filtering display
  - Status-specific icons in embed titles (🟢 for open, 🔴 for closed)
  - Smart navigation hints that preserve status filter in pagination
  - Client-side filtering ensures accurate results across all ticket statuses

### Improved
- **Support Command Help**: Updated help text to show all available ticket filtering options
- **Navigation Consistency**: Pagination commands now maintain status filters
- **Visual Indicators**: Status-specific emoji icons for better visual distinction

### Technical Details
- Refactored ticket listing into shared `_list_tickets_with_status` method
- Added client-side status filtering for precise control
- Enhanced pagination logic to work with filtered results
- Improved command help documentation

## [1.0.1] - 2025-11-09

### Improved
- **Comprehensive Embed Formatting**: Applied consistent formatting improvements across ALL embed displays
  - **Client Commands**: Enhanced client list, search, and detail views
    - Reduced clients per page from 10 to 5 to prevent crowded embeds
    - Changed from inline fields to full-width fields for better spacing
    - Added emoji indicators for better visual organization (🆔, 📧, 📊, 👤)
    - Added navigation hints in footer showing command syntax for previous/next pages
    - Improved plain text format with better spacing and navigation instructions
  - **Billing Commands**: Enhanced invoice list and detail views
    - Applied full-width field formatting for better readability
    - Added consistent emoji indicators (💰, 📄, 📅, 🆔, 👤, 🏢, 💳)
    - Improved visual hierarchy with better organization
  - **Support Commands**: Enhanced ticket list and detail views
    - Applied full-width field formatting for less crowded display
    - Added consistent emoji indicators (🎫, 📊, ⚡, 🏢, 💬, 📅, 🆔)
    - Better status and priority visualization
    - **Fixed ticket ID display**: Now prominently shows ticket ID in embed content
    - **Added pagination navigation**: Navigation hints in footer for multi-page ticket lists
    - Reduced tickets per page from 10 to 5 for better readability
  - **Universal Improvements**:
    - All embeds now use description field for key information
    - Consistent emoji usage across all commands
    - Better visual hierarchy and information organization
    - Enhanced readability on both desktop and mobile Discord clients

### Fixed
- **Ticket List Display**:
  - Ticket ID now properly displayed in embed field content with 🆔 indicator
  - Added pagination navigation hints in footer (similar to client list)
  - Improved command syntax hints for navigating between pages
  - Better visual organization with consistent formatting

### Technical Details
- Modified all embed-generating commands in `whmcs.py`
- Applied consistent `inline=False` for better full-width display
- Standardized emoji indicators across all command categories
- Improved visual hierarchy with better field organization
- Enhanced UX with clearer navigation instructions
- Consistent formatting between embed and plain text modes
- Fixed ticket pagination to match client list behavior

## [1.0.0] - 2025-11-09

### Added
- Initial release of WHMCS integration COG
- Client management functionality
  - List clients with pagination
  - View detailed client information
  - Search clients by name, email, or company
- Basic billing operations
  - View client invoices
  - Check account balances
  - Add account credits (admin only)
- Support ticket integration
  - List and view support tickets
  - Reply to tickets
  - Close tickets
- Administration system
  - Secure API credential configuration
  - Connection testing
  - Role-based permission management
- Security features
  - Encrypted credential storage
  - Role-based access control (Admin, Billing, Support, Readonly)
  - API rate limiting with configurable limits
  - Comprehensive error handling
- User interface
  - Hybrid commands (slash and traditional prefix commands)
  - Rich Discord embeds for all responses
  - Pagination support for large datasets
  - Clear error messaging and user feedback

### Security
- All API credentials stored encrypted using Red-Bot's secure config system
- Role-based permission checks on all commands
- Input validation and sanitization for all user inputs
- Rate limiting to prevent API abuse
- Comprehensive audit logging

### Technical
- Async HTTP client with connection pooling
- Automatic retry logic with exponential backoff
- Memory-efficient pagination for large datasets
- Modular architecture following Red-Bot best practices
- Comprehensive error handling and logging
- Support for both API credentials and admin username/password authentication

## [Unreleased]

### Planned Features
- Advanced billing operations
  - Create invoices
  - Process payments
  - Generate quotes
- Enhanced client management
  - Create new clients
  - Update client information
  - Client suspension/activation
- Product and service management
  - List products and services
  - Manage hosting accounts
  - Domain management
- Advanced support features
  - Create new tickets
  - Automated ticket routing
  - Support statistics and reporting
- Real-time updates
  - Webhook integration for live updates
  - Event notifications in Discord channels
- Dashboard integration
  - Web-based configuration interface
  - Visual analytics and reporting
- Advanced automation
  - Automated billing reminders
  - Service provisioning workflows
  - Custom business rule integration

### Known Issues
- None at this time

### Dependencies
- aiohttp>=3.8.0
- redbot.core (Red-DiscordBot framework)
- discord.py (included with Red-Bot)

### Compatibility
- Red-DiscordBot 3.0.0+
- Python 3.8+
- WHMCS 7.0+ (tested with 8.x)