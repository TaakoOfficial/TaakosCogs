# EmojiPorter

A Red-DiscordBot cog for copying emojis and stickers between Discord servers.

## Installation

To install this cog, use the following command in your Red bot:

```
[p]repo add TaakosCogs https://github.com/TaakoOfficial/TaakosCogs
[p]cog install TaakosCogs EmojiPorter
[p]load EmojiPorter
```

## Features

- **Copy Emojis**: Transfer custom emojis from one server to another that your bot has access to
- **Copy Stickers**: Transfer custom stickers between servers
- **Selective Copying**: Copy specific emojis/stickers by name or copy all at once
- **List Management**: View all emojis and stickers in any server your bot is in
- **Smart Duplicate Detection**: Automatically skips emojis/stickers that already exist
- **Comprehensive Error Handling**: Clear feedback on permissions, limits, and failures
- **Progress Tracking**: Real-time updates during bulk copy operations

## Commands

### Core Commands

- `[p]copyemojis <source_guild_id> [emoji_names]`
  - Copy emojis from another server to the current server
  - `source_guild_id`: The ID of the server to copy emojis from
  - `emoji_names`: Optional comma-separated list of specific emoji names to copy (defaults to all)

- `[p]copystickers <source_guild_id> [sticker_names]`
  - Copy stickers from another server to the current server
  - `source_guild_id`: The ID of the server to copy stickers from
  - `sticker_names`: Optional comma-separated list of specific sticker names to copy (defaults to all)

### Utility Commands

- `[p]listemojis [guild_id]`
  - List all custom emojis in the current server or another server
  - `guild_id`: Optional server ID to list emojis from (defaults to current server)

- `[p]liststickers [guild_id]`
  - List all custom stickers in the current server or another server
  - `guild_id`: Optional server ID to list stickers from (defaults to current server)

## Usage Examples

### Copy All Emojis
```
[p]copyemojis 123456789012345678
```
This copies all emojis from server ID `123456789012345678` to the current server.

### Copy Specific Emojis
```
[p]copyemojis 123456789012345678 thinking,pogchamp,kappa
```
This copies only the emojis named "thinking", "pogchamp", and "kappa" from the source server.

### Copy All Stickers
```
[p]copystickers 123456789012345678
```
This copies all stickers from server ID `123456789012345678` to the current server.

### List Emojis in Current Server
```
[p]listemojis
```
Shows all custom emojis in the current server with their names and previews.

### List Emojis in Another Server
```
[p]listemojis 123456789012345678
```
Shows all custom emojis in the specified server (bot must be in that server).

## Requirements

- **Bot Permissions**: The bot needs `Manage Emojis and Stickers` permission in both the source and destination servers
- **Server Access**: The bot must be present in both the source server and the destination server
- **Discord Limits**: 
  - Regular servers can have up to 50 static emojis and 50 animated emojis
  - Boosted servers have higher limits based on boost level
  - Servers can have up to 5 stickers (with higher limits based on boost level)

## Error Handling

The cog provides comprehensive error handling for common issues:

- **Permission Errors**: Clear messages when the bot lacks necessary permissions
- **Server Limits**: Alerts when emoji/sticker limits are reached
- **File Size Issues**: Notifications when emojis/stickers are too large
- **Missing Access**: Warnings when the bot can't access source servers
- **Rate Limiting**: Built-in delays to prevent Discord API rate limits

## Tips

1. **Finding Server IDs**: Enable Developer Mode in Discord, then right-click on a server name and select "Copy ID"
2. **Bulk Operations**: The cog includes small delays between operations to avoid rate limits
3. **Existing Items**: The cog automatically skips emojis/stickers that already exist with the same name
4. **Progress Updates**: During bulk operations, you'll see real-time progress updates

## Troubleshooting

### "Bot is not in the source server"
- Ensure your bot is a member of both the source and destination servers

### "I need the following permissions: Manage Emojis and Stickers"
- Grant the bot the "Manage Emojis and Stickers" permission in Server Settings > Roles

### "Target server has reached emoji limit"
- The destination server has reached its emoji limit based on its boost level

### "Failed to copy emoji 'name': File too large"
- The emoji file exceeds Discord's size limits (256KB for regular emojis)

## End User Data Statement

This cog does not persistently store any end user data.

## Support

If you encounter any issues or have suggestions, please visit the [GitHub repository](https://github.com/TaakoOfficial/TaakosCogs) and create an issue.

## Changelog

See [CHANGELOG.md](CHANGELOG.md) for version history and updates.