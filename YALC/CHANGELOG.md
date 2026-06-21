# 📝 YALC Changelog

## [v3.2.0] - 2026-06-21

- Added native `/yalc` subcommands for the complete classic command hierarchy.

## [v3.1.6] - 2026-05-16

### ✨ New Features

- Added deleted image copying for message deletion logs by re-uploading cached image attachments when Discord still provides them.

## [v3.1.5] - 2026-05-16

### 🐛 Bug Fixes

- Added an audit-log fallback for role creation and deletion logs when Discord's role gateway event is missed.
- Added duplicate protection so role create/delete logs do not post twice when both gateway and audit-log events arrive.

## [v3.1.4] - 2026-05-16

### 🐛 Bug Fixes

- Made role creation and deletion logging tolerate discord.py role metadata differences so deleted-role embeds do not fail before sending.
- Added traceback logging for role create, delete, and update failures.

## [v3.1.3] - 2026-05-16

### 🐛 Bug Fixes

- Fixed additional misnamed Discord.py listeners for webhooks, scheduled events, integration deletion, and application command permission updates.
- Fixed listener signatures for integration updates and AutoMod rule updates.
- Rewired message pin and unpin logging through message edit pin-state changes.

## [v3.1.2] - 2026-05-16

### 🐛 Bug Fixes

- Fixed role creation, deletion, and update listeners so Discord role events are tracked correctly.

## [v3.1.1] - 2025-05-12

### 🐛 Bug Fixes

- Fixed critical error with missing `is_tupperbox_message` method
- Resolved AttributeError in message event processing
- Enhanced method implementation with better debugging information

## [v3.1.0] - 2025-05-12

### ✨ New Features

- Added comprehensive guild scheduled event logging (creation, updates, deletion)
- Added missing command error event logging

### 🛠️ Improvements

- Enhanced Tupperbox message detection with multiple identification methods
- Expanded Tupperbox filtering to handle more proxy bot types
- Enhanced visual formatting of embeds for better readability
- More detailed message deletion and bulk deletion logs
- Extended configuration options for advanced filtering
- Added webhook name filtering capabilities

### 🐛 Bug Fixes

- Fixed potential issue with proxy detection in message events
- Improved handling of Discord system messages

## [v3.0.0] - 2025-04-17

### ✨ New Features

- Added custom log icon in embed footers
- Enhanced setup wizard with improved channel organization
- Separate channels for different event types
- Advanced retention policy management (7/30/90 days)

### 🛠️ Improvements

- Improved embed formatting and visual consistency
- Better error handling and permissions checks
- Enhanced type hints and documentation
- Streamlined command organization

### 🚀 Performance

- Optimized event handling
- Improved channel creation process
- Better memory management for cached events

### 📚 Documentation

- Completely revamped README
- Added detailed command documentation
- Improved inline code comments

## [v2.0.0] - Previous Release

### ✨ Major Features

- Initial slash command support
- Basic logging functionality
- Event filtering system
- Simple setup wizard

For older versions, please check the Git history.
