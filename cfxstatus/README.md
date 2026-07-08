# cfxstatus

Check the official Cfx.re service status in Discord, either on demand or as an
auto-updating status panel.

[Back to the cog catalog](../README.md)

## Install

```text
[p]repo add taakoscogs https://github.com/TaakoOfficial/TaakosCogs
[p]cog install taakoscogs cfxstatus
[p]load cfxstatus
```

## Highlights

- Fetches the official Cfx.re Statuspage API, with Rockstar Games' service-status page as a fallback.
- Shows the Cfx.re statuses for Authentication, FiveM, RedM, Community Servers, and Marketplace.
- Posts a polished embed panel in a channel you choose.
- Polls automatically and edits the existing panel on a configurable interval.
- Uses color-coded embeds for operational, degraded, outage, and unknown states.
- Stores only guild-level panel settings.

## Commands

| Command                                  | Description                                                                  |
| ---------------------------------------- | ---------------------------------------------------------------------------- |
| `[p]cfxstatus`, `[p]cfx`, or `[p]cfxre`   | Check the current official Cfx.re status once.                               |
| `[p]cfxstatus setup [channel]`           | Pick a channel, post the status panel, and enable automatic updates.         |
| `[p]cfxstatus channel [channel]`         | Change the channel used for the auto-updating panel.                         |
| `[p]cfxstatus post`                      | Post a fresh status panel in the configured channel.                         |
| `[p]cfxstatus refresh`                   | Refresh the configured status panel immediately.                             |
| `[p]cfxstatus enable <true_or_false>`    | Enable or disable automatic updates.                                         |
| `[p]cfxstatus interval <minutes>`        | Set the polling interval, from 1 to 60 minutes.                              |
| `[p]cfxstatus settings`                  | Show the current panel configuration.                                        |

## Example Setup

```text
[p]cfxstatus setup #server-status
[p]cfxstatus interval 5
```

## Requirements

- Red-DiscordBot 3.5.0 or newer.
- Python 3.8 or newer.
- `aiohttp`.
- Bot permissions to `View Channel`, `Send Messages`, and `Embed Links` in the chosen status channel.
- The bot host must be able to reach `https://status.cfx.re/`.
- Rockstar's service-status page is used as a fallback when reachable:
  `https://support.rockstargames.com/servicestatus`.

## Data

cfxstatus stores per-guild panel settings, including enabled state, channel IDs,
message IDs, polling interval, and the last poll timestamp. It does not store
Discord end user data.
