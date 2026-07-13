# Changelog

## 1.2.0 - 2026-07-12

### New Features

- Added saved-message naming, optional locking, and storage directly from the dashboard builder.
- Newly saved Components V2 messages appear in the Stored Messages dashboard section immediately.

## 1.1.0 - 2026-07-12

### New Features

- Made Stored Messages, Commands, and Utility Tools functional dashboard sections.
- Added loading stored Components V2 messages into the visual editor and copying stored JSON.
- Added dashboard color conversion, timestamp generation, and JSON validation tools.
- Added matching bot command-reference, color, timestamp, and validation commands.

## 1.0.0 - 2026-07-12

### New Features

- Renamed the standalone cog to MessageStudio.
- Added the complete EmbedUtils-compatible `[p]embed` command surface alongside Components V2.
- Added legacy embeds, stored messages, webhook posting, message cloning, paste links, and migration support.

## 0.2.0 - 2026-07-12

### New Features

- Replaced the basic dashboard textarea with a standalone visual Components V2 builder inspired by Merlin Fuchs' Embed Generator.
- Added component cards, nested container editing, live Discord-style preview, JSON import/export, duplication, reordering, and browser-local drafts.

### Removals

- Removed the AAA3A EmbedUtils dependency and stored-embed command.

### Improvements

- Reframed legacy `content`/`embed` conversion as standard Discord payload compatibility.

## 0.1.0 - 2026-07-12

### New Features

- Added native Components V2 JSON and YAML parsing.
- Added automatic conversion of EmbedUtils payloads and stored embeds.
- Added Discord send, edit, download, and dashboard-link commands.
- Added a Red-Web-Dashboard editor, approximate preview, and channel sender.
