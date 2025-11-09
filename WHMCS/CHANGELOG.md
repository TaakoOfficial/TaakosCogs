# Changelog

All notable changes to the WHMCS COG will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.11] - 2025-11-09

### Added
- **NEW DIAGNOSTIC TOOL**: Added `[p]whmcs admin debug <ticket_id>` command for troubleshooting ticket API issues
- Comprehensive API parameter testing (ticketid, ticketnum, tid) to identify WHMCS configuration problems
- Detailed diagnosis and recommendations for common WHMCS API permission and configuration issues
- Helps identify if the problem is with API credentials, IP whitelisting, or WHMCS ticket numbering settings

### Technical Details
- Tests all three possible GetTicket API parameters with detailed success/failure reporting
- Provides specific WHMCS configuration recommendations based on test results
- Helps distinguish between COG bugs and WHMCS configuration issues
- Essential tool for troubleshooting "Ticket not found" errors

## [1.0.10] - 2025-11-09

### Fixed

- **CRITICAL**: Fixed ticket ID categorization issue where alphanumeric ticket numbers were incorrectly labeled as "Internal" IDs
- Improved intelligent ID detection to properly categorize numeric vs alphanumeric ticket identifiers
- Fixed "Ticket not found" errors when WHMCS returns alphanumeric ticket numbers in the `tid` field
- Enhanced display logic to show correct ID type: "Internal: 123" for numeric, "Ticket Number: GLY-907775" for alphanumeric

### Technical Details

- Updated ticket listing display logic to use `str(tid_value).isdigit()` for accurate ID type detection
- Fixed edge case where WHMCS `GetTickets` API returns alphanumeric ticket numbers in `tid` field
- Ensures users see the correct ID category and can successfully use any displayed ID with ticket commands
- Maintains backward compatibility with all existing ticket ID formats

## [1.0.9] - 2025-11-09

### Improved

- **MAJOR**: Enhanced ticket listing to show ALL available ticket ID formats
- Ticket listings now display: Internal ID, Ticket Number, and Mask ID (when available)
- Format: `🆔 IDs: Internal: 123 • Number: GLY-907775 • Mask: #WYI-894412`
- Users can now see exactly which ID format to use with `[p]whmcs support ticket <id>` command
- Resolves confusion about which ticket ID to use when viewing individual tickets

### Technical Details

- Updated ticket listing display logic in both embed and plain text formats
- Enhanced ID display to show `tid`, `ticketnum`, and `maskid` fields from WHMCS API
- Improved user experience by showing all available identifier options
- Maintains backward compatibility with existing ticket ID handling

## [1.0.8] - 2025-11-09

### Fixed

- **CRITICAL**: Fixed ticket ID handling for IDs with `#` prefix (e.g., `#WYI-894412`)
- Fixed inconsistency in channel name creation where old "ticket-" prefix was still being used as fallback
- Updated channel creation logic to properly strip `#` prefix from ticket IDs when creating Discord channel names
- Ensured consistent use of "whmcs-ticket-" prefix throughout the application

### Technical Details

- Enhanced `_get_or_create_ticket_channel()` method to handle `#` prefix in ticket IDs
- API client already supported `#` prefix stripping in `get_ticket()` and `add_ticket_reply()` methods
- All ticket ID formats now properly supported: numeric (123), alphanumeric (GLY-907775), and prefixed (#WYI-894412)
- Fixed channel name creation fallback to use correct "whmcs-ticket-" default prefix

## [1.0.7] - 2025-11-09

### Changed

- **IMPROVEMENT**: Changed default ticket channel prefix from "ticket-" to "whmcs-ticket-"
- Ticket channels now named `#whmcs-ticket-[ticket-id]` for better clarity and organization
- Updated all documentation examples to reflect new default prefix
- Enhanced channel identification for better Discord server organization

### Technical Details

- Updated default `channel_prefix` configuration value
- Updated admin channels view command to show correct default
- All documentation examples now use the new prefix format

## [1.0.6] - 2025-11-09

### Added

- **NEW FEATURE**: Dedicated admin commands for ticket channel configuration
- Added `[p]whmcs admin channels` command group for easy setup
- User-friendly commands: `view`, `enable`, `disable`, `set category`, `set prefix`, etc.
- Comprehensive configuration interface with validation and helpful error messages

### Changed

- Updated README documentation to use correct WHMCS COG commands instead of generic Red-Bot config
- Improved setup instructions with proper command examples
- Enhanced troubleshooting section with accurate command references

### Technical Details

- Added `admin_channels()` command method with full configuration management
- Category validation ensures Discord categories exist and are accessible
- Smart prefix sanitization for Discord channel name compatibility
- Enhanced admin command help to include new channels configuration

## [1.0.5] - 2025-11-09

### Fixed

- **CRITICAL**: Fixed "Ticket ID Not Found" error when using alphanumeric ticket IDs (e.g., GLY-907775)
- API client now correctly uses `ticketnum` parameter for alphanumeric ticket IDs and `ticketid` for numeric IDs
- Both GetTicket and AddTicketReply API calls now handle both ticket ID formats properly
- Automatic channel creation now works with all WHMCS ticket ID formats

### Technical Details

- Updated `get_ticket()` method to detect ticket ID format and use appropriate API parameter
- Updated `add_ticket_reply()` method to use the same format detection logic
- Ticket ID format detection: numeric IDs use `ticketid`, alphanumeric use `ticketnum`

## [1.0.4] - 2025-11-09

### Added

- **🚀 Automatic Discord Channel Integration**: Revolutionary ticket-to-channel system
  - **Auto-Channel Creation**: Automatically creates Discord channels for WHMCS tickets
  - **Message Listener Integration**: Messages sent in ticket channels automatically reply to WHMCS tickets
  - **Smart Channel Management**: Configurable channel categories, prefixes, and archiving
  - **Seamless Workflow**: View ticket → Channel created → Reply in Discord → Updates WHMCS
  - **Permission Integration**: Respects WHMCS role permissions for channel access
  - **Visual Feedback**: ✅ reactions confirm successful WHMCS updates, ❌ for errors

### Technical Implementation

- **Channel Configuration System**: Complete admin interface for channel settings
- **Message Event Listener**: `on_message()` handler for automatic reply processing
- **Channel-Ticket Mapping**: Persistent storage linking Discord channels to WHMCS tickets
- **Auto-Permission Setup**: Automatic channel permissions based on WHMCS roles
- **Error Handling**: Graceful handling of channel creation and API failures
- **Memory Management**: Efficient channel ID caching and cleanup

### Configuration Options

- **Enable/Disable**: Toggle automatic channel creation
- **Category Management**: Set categories for active and archived ticket channels
- **Channel Naming**: Customizable channel name prefixes (default: "ticket-")
- **Auto-Archiving**: Automatically archive channels when tickets are closed
- **Manual Creation**: Admin command to manually create channels for existing tickets

### Usage Workflow

1. **View Ticket**: Use `[p]whmcs support ticket GLY-907775`
2. **Auto-Channel**: System creates `#ticket-gly-907775` channel
3. **Team Collaboration**: Support team discusses in dedicated channel
4. **Auto-Reply**: Type messages in channel → automatically posted to WHMCS
5. **Visual Confirmation**: ✅ reaction confirms message was sent to WHMCS
6. **Seamless Integration**: No need to switch between Discord and WHMCS interface

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
