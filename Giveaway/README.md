# Giveaway

Timed reaction-based giveaways for Red-DiscordBot.

[Back to the cog catalog](../README.md)

## Install

```text
[p]repo add TaakosCogs https://github.com/TaakoOfficial/TaakosCogs
[p]cog install TaakosCogs Giveaway
[p]load Giveaway
```

## Highlights

- Start giveaways in the current channel or a specific channel.
- Attach a giveaway to an existing message by ID or message link.
- Automatic ending after the timer expires, including after bot restarts.
- Manual end, cancel, reroll, and active giveaway list commands.
- Prefix commands and `/giveaway` slash commands.

## Commands

| Command | Description |
| --- | --- |
| `[p]giveaway start <duration> <winner_count> <prize>` | Start a giveaway in the current channel. |
| `[p]giveaway startin <channel> <duration> <winner_count> <prize>` | Start a giveaway in another channel. |
| `[p]giveaway attach <message_id_or_link> <duration> <winner_count> [prize]` | Use an existing message for entries. |
| `[p]giveaway end <message_id_or_link>` | End an active giveaway immediately. |
| `[p]giveaway cancel <message_id_or_link>` | Cancel an active giveaway. |
| `[p]giveaway reroll <message_id_or_link> [winner_count]` | Pick new winners for an ended giveaway. |
| `[p]giveaway list` | List active giveaways in the server. |

Durations support values like `30m`, `2h`, `3d`, or `1w2d`.

## Requirements

- Red-DiscordBot 3.5.0 or newer.
- `View Channel`, `Send Messages`, `Embed Links`, `Add Reactions`, and `Read Message History`.
- Manage Server permission, Red admin, or equivalent for giveaway management commands.

## Data

Giveaway stores giveaway metadata per guild, including message IDs, channel IDs, host IDs, winner IDs, prize text, and timestamps.
