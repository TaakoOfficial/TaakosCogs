# Changelog

## 1.9.0 - 2026-07-13

### Simpler Builder Controls

- Replaced the oversized builder dropdowns with a compact, labeled, evenly aligned control bar.
- Shortened **Add component** to **Add** and grouped it directly with the component-type selector.
- Improved toolbar and delivery-control wrapping for narrow dashboard and mobile layouts.

### Mention Controls

- Added a clear dashboard mention selector for **Users and roles**, **All mentions**, or **No mentions**.
- Allow user and role mentions by default while safely blocking `@everyone` and `@here` unless explicitly enabled.
- Apply the selected mention behavior consistently to normal bot and custom webhook delivery.

## 1.8.1 - 2026-07-13

### Dashboard Reliability

- Fixed dashboard saves, sends, and profile lookups displaying `Unexpected token '<'` when Red-Web-Dashboard returned an HTML session or CSRF error page.
- Automatically refresh an expired dashboard security token once and retry the original operation safely.
- Added clear login-expired, HTTP, malformed-response, and server-error messages while preserving browser-local drafts.
- Corrected generic storage failures to say that the message could not be saved instead of sent.

## 1.8.0 - 2026-07-12

### Discord Asset Toolbox

- Added dashboard previews and full-size CDN links for the current server icon, banner, invite splash, and discovery splash.
- Added user-ID profile lookups for display avatars, global avatars, server-specific avatars, profile banners, and accent colors.
- Added one-click Open, Copy URL, Copy ID, and Copy accent-color controls.
- Kept profile lookups behind the existing guild dashboard permission checks and disabled them in the standalone editor.

## 1.7.0 - 2026-07-12

### Dashboard Redesign

- Reduced visual clutter with calmer cards, clearer spacing, component descriptions, and progressive disclosure for advanced settings.
- Added hover and keyboard-focus hints for component types, technical IDs, limits, colors, timestamps, actions, delivery, and storage options.
- Collapsed persistent actions, legacy author/media/field/footer settings, and saved-message controls until they are needed.
- Improved responsive layouts and visual hierarchy across the editor and utility pages.

### Utility Tools

- Redesigned the timestamp tool to preview all seven Discord timestamp styles side by side with click-to-copy markup.
- Added a Discord snowflake creation-time decoder.
- Added a live text, line, byte, and Discord-limit counter.
- Expanded the JSON tool with validation, formatting, minification, payload type, and byte counts.
- Added a live Discord-style Markdown preview.
- Improved the color converter with a swatch and click-to-copy combined output.

## 1.6.0 - 2026-07-12

### New Features

- Added dashboard delivery through a managed webhook with a custom username and avatar URL.
- Added a dashboard selector for normal bot delivery or webhook delivery.
- Webhook messages support legacy embeds, classic components, Components V2, files, and persistent actions.

### Improvements

- Standardized legacy payload detection across commands, storage, editing, validation, dashboard sending, and webhook sending.
- Correctly identify legacy messages that include classic Action Rows instead of labeling them as Components V2.
- Require dashboard users and the bot to have the appropriate channel and webhook permissions before delivery.

## 1.5.0 - 2026-07-12

### New Features

- Added a dedicated Legacy Embeds mode to the dashboard visual builder.
- Added visual editing for message content, up to 10 embeds, titles, descriptions, colors, authors, images, thumbnails, fields, footers, and timestamps.
- Added classic Action Row buttons and selects to legacy messages, including persistent MessageStudio actions.
- Added legacy embed and classic-component previews, JSON import/export, stored-message loading, and direct dashboard sending.

### Fixes

- Dashboard legacy payloads now send as real Discord content, embeds, and classic components instead of being converted into Components V2.
- Downloading a classic component message now retains its Action Rows.

## 1.4.0 - 2026-07-12

### New Features

- Added persistent button and select actions keyed to the sent Discord message and component custom ID.
- Added `add_role`, `remove_role`, `toggle_role`, `send_message`, and ephemeral/public `reply` actions.
- Added optional select-value filters and action text placeholders.
- Added visual persistent-action cards to custom buttons and selects in the dashboard builder.
- Added `[p]embed actions` inspection and `[p]embed actions clear` management commands.

### Safety and Reliability

- Validate moderator role hierarchy and channel access when actions are configured.
- Recheck bot permissions, managed roles, and bot role hierarchy every time an action runs.
- Persist action bindings in Red Config so controls continue working after cog or bot restarts.
- Remove stored bindings automatically when their Discord messages are deleted.

## 1.3.0 - 2026-07-12

### New Features

- Added every Components V2 component supported in Discord messages.
- Added all button styles and string, user, role, mentionable, and channel selects.
- Added custom-ID fallback interaction responses.
- Added real uploaded File components with multipart Discord sending.
- Added visual editing for select options, selection limits, disabled controls, button emojis, SKU IDs, and Section custom-button accessories.
- Added a ready-to-send Components V2 showcase JSON with interactive controls, media, layouts, and an uploaded file.

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
