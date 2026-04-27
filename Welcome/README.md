# Welcome

Custom welcome messages for Red-DiscordBot servers.

[Back to the cog catalog](../README.md)

## Install

```text
[p]repo add TaakosCogs https://github.com/TaakoOfficial/TaakosCogs
[p]cog install TaakosCogs Welcome
[p]load Welcome
```

## Highlights

- Configurable welcome channel and enable/disable state.
- Plain text welcome templates with member and guild placeholders.
- Optional custom embed JSON.
- Optional cached welcome image used inside the embed or as an attachment.
- Preview command for testing before enabling.

## Commands

| Command | Description |
| --- | --- |
| `[p]welcome enable <true_or_false>` | Enable or disable welcome messages. |
| `[p]welcome channel [channel]` | Set or clear the welcome channel. |
| `[p]welcome message <template>` | Set the plain welcome message template. |
| `[p]welcome clearmessage` | Clear the plain welcome message. |
| `[p]welcome embedjson [json]` | Set a custom embed from text or an attached JSON file. |
| `[p]welcome clearembed` | Clear the custom embed. |
| `[p]welcome image <url>` | Download and cache a welcome image. |
| `[p]welcome clearimage` | Remove the cached image. |
| `[p]welcome imagemode <embed_or_attachment>` | Choose how the cached image is used. |
| `[p]welcome bots <true_or_false>` | Choose whether bot accounts trigger welcomes. |
| `[p]welcome placeholders` | Show available placeholders. |
| `[p]welcome samplejson` | Show a sample embed JSON payload. |
| `[p]welcome settings` | Show current settings. |
| `[p]welcome test [member]` | Preview the welcome output. |

## Requirements

- Red-DiscordBot 3.0.0 or newer.
- `aiohttp`.
- `Send Messages`, `Embed Links`, and `Attach Files` permissions in the welcome channel.
- Manage Server permission, Red admin, or equivalent for configuration commands.

## Data

Welcome stores per-guild welcome settings, including channel IDs, message and embed templates, image mode, and optionally one cached welcome image per guild.
