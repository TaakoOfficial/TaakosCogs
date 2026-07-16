# 📝 YALC Changelog

## [v4.0.2] - 2026-07-15

- Rebuilt Tupperbox/proxy filtering around normalized application IDs and webhook attribution instead of proxy persona names or message-content guesses.
- Added automatic recognition for the official Tupperbox and PluralKit applications while retaining configurable proxy application IDs.
- Added bounded webhook and message caches so known proxy messages remain filtered from uncached raw edit, delete, and bulk-delete events.
- Removed the false-positive heuristic that treated unrelated bot messages containing pipe characters as proxies.
- Clarified the proxy filtering controls and added focused detection tests.

## [v4.0.1] - 2026-07-15

- Fixed the dashboard smart-route renderer referencing the removed `EVENT_TO_SETUP_GROUP` attribute.
- Fixed the same stale mapping reference in the bulk moderation enable and disable commands.
- Routed dashboard suggestions and bulk categories through YALC's canonical event-to-channel resolver.

## [v4.0.0] - 2026-07-15

- Rebuilt audit attribution around a bounded, deduplicated audit stream with strict action, target, channel, and time matching. YALC no longer substitutes an unrelated newest audit entry.
- Added raw gateway coverage for uncached message edits, deletes, and bulk deletes, including explicit notices when Discord did not provide message content.
- Added direct audit-only logging for bot additions, member prunes, permission-overwrite changes, and webhook creation/deletion.
- Added moderator and reason attribution to ban and unban logs.
- Made fallback delivery fail closed: YALC only retries in an explicitly configured fallback channel and never chooses an arbitrary writable public channel.
- Added reply, sticker, poll, forwarded-message, and attachment context to cached deletion logs.
- Added per-event dashboard color controls and command-log privacy modes for all commands, staff commands only, or disabled command logging.
- Added an optional SQLite event journal with content-off-by-default privacy, retention pruning, search, CSV/JSON export, clear, audit-ID deduplication, and Red user-data deletion support.
- Replaced the old generic form dashboard with a fully standalone YALC control center for core policy, every event toggle/route/color, filters, granular ignores, audit health, journal health, and test delivery.
- Added focused tests for strict audit matching, duplicate handling, journal privacy, journal persistence, searching, and data deletion.
- Fixed log-channel dropdowns collapsing into unreadable vertical text on narrow dashboard panels.
- Added enable/disable controls for all events and for each event category.
- Refined the dashboard's spacing, hierarchy, controls, and responsive layout.
- Reorganized both dashboard renderers into responsive Filtering, Events, and Log Channels tabs that preserve the selected tab while editing settings.

## [v3.2.1] - 2026-07-09

- Renamed the repository package folder from `YALC` to `yalc` to match Red cog naming standards.
- New installs should use `[p]cog install taakoscogs yalc` and `[p]load yalc`.
- Existing guild logging settings are preserved because the cog's Config identifier did not change.

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
