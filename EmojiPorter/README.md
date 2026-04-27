# EmojiPorter

Copy custom emojis and stickers between Discord servers.

[Back to the cog catalog](../README.md)

## Install

```text
[p]repo add TaakosCogs https://github.com/TaakoOfficial/TaakosCogs
[p]cog install TaakosCogs EmojiPorter
[p]load EmojiPorter
```

## Highlights

- Copy all emojis or selected emojis from another server.
- Copy all stickers or selected stickers from another server.
- List emojis and stickers in the current server or another server the bot can access.
- Duplicate names are skipped automatically.
- Progress updates and clear permission/limit errors.

## Commands

| Command | Description |
| --- | --- |
| `[p]copyemojis <source_guild_id> [emoji_names]` or `/copyemojis` | Copy emojis into the current server. |
| `[p]copystickers <source_guild_id> [sticker_names]` or `/copystickers` | Copy stickers into the current server. |
| `[p]listemojis [guild_id]` or `/listemojis` | List custom emojis. |
| `[p]liststickers [guild_id]` or `/liststickers` | List custom stickers. |

For selected copies, pass comma-separated names such as `blobwave,blobheart`.

## Requirements

- Red-DiscordBot 3.0.0 or newer.
- `aiohttp`.
- Bot must be in the source and destination servers.
- `Manage Emojis and Stickers` in the destination server.
- Source assets must fit Discord's emoji and sticker limits.

## Data

EmojiPorter does not persistently store end user data.
