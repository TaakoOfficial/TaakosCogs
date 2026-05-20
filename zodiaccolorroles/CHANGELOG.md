# Changelog

All notable changes to the ZodiacColorRoles cog will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.1.0] - 2025-01-25

### Changed
- **Major Refactor**: Complete overhaul for enhanced Red-DiscordBot compatibility
- **Command System**: Replaced app_commands with hybrid commands for dual support
- **Architecture**: Improved codebase structure and maintainability

### Added
- **Hybrid Commands**: Full support for both slash commands and prefix commands
- **Bulk Creation**: "all" parameter support for creating all roles of a type at once
- **Enhanced Validation**: Comprehensive input validation and error handling
- **Pronoun Roles**: Complete pronoun role system (he/him, she/her, they/them, etc.)
- **Ping Roles**: Common notification preference roles (Common Ping, No Pings, etc.)
- **Smart Logic**: Improved role creation with duplicate detection
- **List Commands**: `listzodiacroles` and `listcolorroles` for viewing available options

### Improved
- **Error Handling**: Clear, user-friendly error messages for all failure scenarios
- **Permission Checks**: Robust permission validation before role operations
- **User Feedback**: Detailed success/failure reporting for bulk operations
- **Documentation**: Complete rewrite of README and changelog for clarity
- **Code Quality**: Enhanced code structure and maintainability

### Technical Details
- **Color System**: 16 predefined colors with proper hex values
- **Zodiac System**: All 12 zodiac signs with consistent naming
- **Pronoun System**: 7 inclusive pronoun options
- **Ping System**: 4 common notification preference roles
- **Safety**: Comprehensive error handling for Discord API limits and permissions

## [1.0.0] - 2024-12-01

### Added
- Initial release of ZodiacColorRoles cog
- **Core Functionality:**
  - Slash commands for zodiac role creation
  - Slash commands for color role creation
  - Basic role management capabilities
- **Role Types:**
  - 12 zodiac sign roles
  - Multiple color roles with hex values
- **Features:**
  - Discord slash command integration
  - Role creation and management
  - Basic error handling

### Dependencies
- Red-DiscordBot 3.5.0+ compatibility
- Discord.py app_commands integration
- Basic Discord permissions for role management

### Notes
- Initial implementation focused on slash commands only
- Limited to zodiac and color roles
- Basic functionality without bulk operations