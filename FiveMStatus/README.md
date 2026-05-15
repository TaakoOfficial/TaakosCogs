# FiveMStatus

Live FiveM server status panels for Red-DiscordBot.

[Back to the cog catalog](../README.md)

## Install

```text
[p]repo add taakoscogs https://github.com/TaakoOfficial/TaakosCogs
[p]cog install taakoscogs FiveMStatus
[p]load FiveMStatus
```

## Highlights

- Posts one Discord embed that updates every minute.
- Reads live player count, max players, hostname, server banner, and player list from FiveM JSON endpoints.
- Supports direct `ip:port` / `hostname:port` servers and `cfx.re/join` codes.
- Shows online/offline status, players, F8 connect command, next restart, uptime, and a Join Server button.
- Supports custom title, message, thumbnail logo, banner image, embed color, restart schedule, timezone, and link buttons.

## Commands

| Command                             | Description                                                                   |
| ----------------------------------- | ----------------------------------------------------------------------------- |
| `[p]fivem` or `[p]fivemstatus`      | Show current settings.                                                        |
| `[p]fivem setup <server> [channel]` | Set the server, choose the channel, enable updates, and post the panel.       |
| `[p]fivem server <server>`          | Change the FiveM endpoint.                                                    |
| `[p]fivem channel [channel]`        | Set the status channel.                                                       |
| `[p]fivem post`                     | Post a fresh status panel.                                                    |
| `[p]fivem refresh`                  | Refresh the panel immediately.                                                |
| `[p]fivem enable <true_or_false>`   | Enable or disable automatic refreshes.                                        |
| `[p]fivem name [name]`              | Set the panel title. Use `clear` to return to the server hostname.            |
| `[p]fivem message [message]`        | Set the short panel message. Use `clear` to remove it.                        |
| `[p]fivem logo [url]`               | Set the thumbnail logo URL. Use `clear` to remove it.                         |
| `[p]fivem image [url]`              | Set the large image URL. Use `clear` to use the server banner when available. |
| `[p]fivem color [hex_or_color]`     | Set the embed color. Omit the color to restore the default.                   |
| `[p]fivem connecturl [url]`         | Set the Join Server button URL. Use `clear` to remove it.                     |
| `[p]fivem joincode [code_or_url]`   | Set the Join Server button from a CFX join code or `cfx.re/join` URL.         |
| `[p]fivem discordurl [url]`         | Set the Discord button URL. Use `clear` to remove it.                         |
| `[p]fivem hostingurl [url]`         | Set the Hosting button URL. Use `clear` to remove it.                         |
| `[p]fivem restart add <HH:MM>`      | Add a daily restart time.                                                     |
| `[p]fivem restart remove <HH:MM>`   | Remove a restart time.                                                        |
| `[p]fivem restart clear`            | Clear restart times.                                                          |
| `[p]fivem timezone <iana_timezone>` | Set the timezone used for restart countdowns.                                 |
| `[p]fivem players`                  | Show the currently listed online players.                                     |
| `[p]fivem settings`                 | Show current settings.                                                        |

## Server Formats

All of these are valid:

```text
[p]fivem setup 123.123.123.123:30120 #server-status
[p]fivem setup play.example.com:30120 #server-status
[p]fivem setup https://cfx.re/join/abc123 #server-status
[p]fivem setup abc123 #server-status
```

If no port is provided for a direct host, the cog uses FiveM's default `30120` port.

## Example Setup

```text
[p]fivem setup 123.123.123.123:30120 #server-status
[p]fivem name Revival of Hope RP
[p]fivem logo https://example.com/logo.png
[p]fivem image https://example.com/banner.png
[p]fivem joincode gmblex
[p]fivem restart add 06:00
[p]fivem restart add 18:00
[p]fivem timezone America/Chicago
[p]fivem discordurl https://discord.gg/example
```

`[p]fivem joincode gmblex` creates a Discord button that links to `https://cfx.re/join/gmblex`. On devices with FiveM/CFX handling configured, that link opens the game and starts the connection flow.

## Requirements

- Red-DiscordBot 3.5.0 or newer.
- Python 3.9 or newer.
- `aiohttp`.
- Bot permissions to `Send Messages`, `Embed Links`, `Read Message History`, and use external emoji/images in the status channel.
- Manage Server permission, Red admin, or equivalent for configuration commands.
- The configured FiveM endpoint must allow the bot host to reach `dynamic.json`, `info.json`, and `players.json`, or the public CFX server listing API for join codes.

## Notes

FiveM does not reliably expose true process uptime through the public JSON endpoints. The uptime field is tracked from the first successful poll after the cog sees the configured server online, and it resets when the server becomes unreachable.

## Data

FiveMStatus stores per-guild status settings such as the server endpoint, channel/message IDs, display text, image URLs, button URLs, restart times, timezone, and observed online-since timestamp. It fetches player names from the FiveM API for display but does not store player records.
