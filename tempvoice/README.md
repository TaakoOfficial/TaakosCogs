# tempvoice

Temporary voice channels with embedded owner controls for Red-DiscordBot.

[Back to the cog catalog](../README.md)

## Install

```text
[p]repo add taakoscogs https://github.com/TaakoOfficial/TaakosCogs
[p]cog install taakoscogs tempvoice
[p]load tempvoice
```

## Highlights

- Join-to-create voice channel setup.
- Automatic deletion of empty temporary voice channels.
- Embedded control panel for each temporary channel.
- Buttons for rename, lock/unlock, user limit, ownership transfer, permitted users, user removal, and claiming abandoned channels.
- Optional text channel for control panels when you do not want to use voice channel chat.

## Quick Start

Create a new `Join to Create` voice channel and enable the cog:

```text
[p]tempvoice setup
```

Use an existing voice channel instead:

```text
[p]tempvoice setup "Join to Create"
```

Post control panels in a text channel instead of the temporary voice channel chat:

```text
[p]tempvoice panelchannel #voice-controls
```

## Commands

| Command | Description |
| --- | --- |
| `[p]tempvoice` | Show the TempVoice help menu. |
| `[p]tempvoice settings` | Show current settings. |
| `[p]tempvoice setup [voice_channel] [category]` | Configure or create the join-to-create voice channel. |
| `[p]tempvoice enable` | Enable temporary voice creation. |
| `[p]tempvoice disable` | Disable new temporary voice creation. |
| `[p]tempvoice joinchannel <voice_channel>` | Set the trigger voice channel. |
| `[p]tempvoice category [category]` | Set the category for temporary channels, or clear it. |
| `[p]tempvoice panelchannel [text_channel]` | Set the control panel text channel, or clear it to use voice channel chat. |
| `[p]tempvoice defaultlimit <0-99>` | Set the default user limit for new channels. |
| `[p]tempvoice template <template>` | Set the channel name template. Supports `{owner}`, `{username}`, `{user}`, and `{guild}`. |
| `[p]tempvoice autodelete <0-300>` | Set the empty-channel deletion delay in seconds. |
| `[p]tempvoice list` | List active temporary channels. |
| `[p]tempvoice claim` | Claim your current temporary channel if the owner is gone. |
| `[p]tempvoice cleanup` | Delete empty temporary channels and remove stale records. |

## Requirements

- Red-DiscordBot 3.5.0 or newer.
- Bot permissions: `Manage Channels`, `Move Members`, `Send Messages`, and `Embed Links`.
- Discord server members must be able to join the configured join-to-create voice channel.

## Data

tempvoice stores per-guild settings, active temporary voice channel IDs, owner user IDs, permitted user IDs, control panel message/channel IDs, creation timestamps, channel names, lock state, and user limits.
