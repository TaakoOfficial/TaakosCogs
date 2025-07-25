# Changelog

All notable changes to the EmojiPorter cog will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.1] - 2025-07-25

### Fixed
- Fixed a SyntaxError in `_copy_sticker` method (indentation issue).
- Fixed bug where copying certain stickers caused an "embedded null byte" error by properly wrapping sticker bytes in `io.BytesIO`.
## [1.0.0] - 2025-01-25

### Added
- Initial release of EmojiPorter cog
- **Core Functionality:**
  - `copyemojis` command to copy emojis between servers
  - `copystickers` command to copy stickers between servers
  - Support for copying all or specific emojis/stickers by name
  - Smart duplicate detection to skip existing items
- **Utility Commands:**
  - `listemojis` command to view all emojis in a server
  - `liststickers` command to view all stickers in a server
  - Support for listing items from current server or remote servers
- **Features:**
  - Comprehensive error handling for permissions, limits, and API errors
  - Progress tracking with real-time updates during bulk operations
  - Rate limiting protection with built-in delays
  - Support for both static and animated emojis
  - Proper handling of Discord's file size and server limits
- **Safety & Reliability:**
  - Permission checks before operations
  - Graceful handling of Discord API errors
  - Clear user feedback for all operation results
  - Automatic skipping of existing emojis/stickers

### Dependencies
- `aiohttp` for downloading emoji/sticker files
- Red-DiscordBot 3.0.0+ compatibility
- Discord.py integration through Red's framework

### Notes
- Bot requires "Manage Emojis and Stickers" permission in both source and destination servers
- Bot must be present in both source and destination servers
- Respects Discord's emoji and sticker limits based on server boost level
- All operations include detailed logging and user feedback