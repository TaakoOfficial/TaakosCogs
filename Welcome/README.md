# Welcome

Custom welcome messages for Red-DiscordBot servers.

[Back to the cog catalog](../README.md)

## Install

```text
[p]repo add taakoscogs https://github.com/TaakoOfficial/TaakosCogs
[p]cog install taakoscogs Welcome
[p]load Welcome
```

## Highlights

- Configurable welcome channel and enable/disable state.
- Plain text welcome templates with member and guild placeholders.
- Optional custom embed JSON.
- Optional cached welcome image used inside the embed or as an attachment.
- Optional member avatar overlay for cached welcome images.
- Preview command for testing before enabling.
- Red-Web-Dashboard page for visual setup, image caching, embed JSON, avatar overlay, and previews.

## Commands

| Command                                      | Description                                            |
| -------------------------------------------- | ------------------------------------------------------ |
| `[p]welcome enable <true_or_false>`          | Enable or disable welcome messages.                    |
| `[p]welcome channel [channel]`               | Set or clear the welcome channel.                      |
| `[p]welcome message <template>`              | Set the plain welcome message template.                |
| `[p]welcome clearmessage`                    | Clear the plain welcome message.                       |
| `[p]welcome embedjson [json]`                | Set a custom embed from text or an attached JSON file. |
| `[p]welcome clearembed`                      | Clear the custom embed.                                |
| `[p]welcome image <url>`                     | Download and cache a welcome image.                    |
| `[p]welcome clearimage`                      | Remove the cached image.                               |
| `[p]welcome imagemode <embed_or_attachment>` | Choose how the cached image is used.                   |
| `[p]welcome avataroverlay <true_or_false> [x_percent] [y_percent] [size_percent]` | Draw the member avatar on the cached image. |
| `[p]welcome bots <true_or_false>`            | Choose whether bot accounts trigger welcomes.          |
| `[p]welcome placeholders`                    | Show available placeholders.                           |
| `[p]welcome samplejson`                      | Show a sample embed JSON payload.                      |
| `[p]welcome settings`                        | Show current settings.                                 |
| `[p]welcome test [member]`                   | Preview the welcome output.                            |

Avatar overlay coordinates are percentages of the cached image. For a banner like the
example with a circle on the right, start with `[p]welcome avataroverlay true 82 52 17`
and adjust from there.

## Dashboard

Welcome includes a Red-Web-Dashboard third-party page when the Dashboard cog is loaded.

Dashboard users with Manage Server, Red admin, or bot owner access can:

- Enable or disable welcome messages and choose the welcome channel.
- Edit the text template and embed JSON with placeholder validation.
- Download, cache, and clear the welcome image.
- Configure image mode and avatar overlay placement.
- Send a welcome preview to a selected channel.
- Review available member and guild placeholders.

## Requirements

- Red-DiscordBot 3.0.0 or newer.
- `aiohttp`.
- `Pillow`.
- `Send Messages`, `Embed Links`, and `Attach Files` permissions in the welcome channel.
- Manage Server permission, Red admin, or equivalent for configuration commands.

## Data

Welcome stores per-guild welcome settings, including channel IDs, message and embed templates, image mode, avatar overlay settings, and optionally one cached welcome image per guild.
