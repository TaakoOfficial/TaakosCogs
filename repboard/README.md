# repboard

Community reputation, kudos, public rep boards, leaderboards, moderation, and exports for Red-DiscordBot.

[Back to the cog catalog](../README.md)

## Install

```text
[p]repo add taakoscogs https://github.com/TaakoOfficial/TaakosCogs
[p]cog install taakoscogs repboard
[p]load repboard
```

## Dashboard

This cog includes standalone Red-Web-Dashboard integration. Server managers can use the dashboard to view visible commands and the current server configuration when Red-Web-Dashboard is installed.

## Highlights

- Lets members give reputation to other members with an optional or required reason.
- Posts reputation entries to a public board channel, or falls back to the command channel.
- Tracks received rep, given rep, profile cards, recent history, and server leaderboards.
- Supports configurable cooldowns and daily giving limits to reduce spam.
- Blocks self-rep and bot-rep by default.
- Lets staff remove bad reputation entries without deleting the audit trail.
- Exports reputation records to CSV.
- Uses `[p]repboard` commands only, avoiding short global aliases that often conflict with other cogs.

## Quick Setup

Run this in the channel where public reputation posts should go:

```text
[p]repboard setup
```

Or set both channels directly:

```text
[p]repboard setup #rep-board #staff-logs
```

For a guided setup:

```text
[p]repboard walkthrough
```

## How Members Use It

```text
[p]repboard give @Member thanks for helping me fix my load order
[p]repboard profile @Member
[p]repboard leaderboard
[p]repboard history @Member
```

`kudos`, `thank`, and `thanks` are aliases for the `give` subcommand:

```text
[p]repboard kudos @Member great event planning
```

## Commands

| Command                                           | Description                                                             |
| ------------------------------------------------- | ----------------------------------------------------------------------- |
| `[p]repboard`                                     | Show current settings and setup hints.                                  |
| `[p]repboard setup [board_channel] [log_channel]` | Quick setup and enable RepBoard.                                        |
| `[p]repboard walkthrough`                         | Guided setup flow.                                                      |
| `[p]repboard enable [true_or_false]`              | Enable or disable reputation giving.                                    |
| `[p]repboard boardchannel [channel]`              | Set or clear the public rep board channel.                              |
| `[p]repboard logchannel [channel]`                | Set or clear the staff log channel.                                     |
| `[p]repboard cooldown <minutes>`                  | Set the time a member must wait between giving rep.                     |
| `[p]repboard dailylimit <amount>`                 | Set how many reps a member can give per UTC day. Use `0` for unlimited. |
| `[p]repboard requirereason <true_or_false>`       | Require a reason when giving rep.                                       |
| `[p]repboard minreason <length>`                  | Set a minimum reason length.                                            |
| `[p]repboard allowbots <true_or_false>`           | Allow or block reputation for bots.                                     |
| `[p]repboard allowself <true_or_false>`           | Allow or block self-reputation.                                         |
| `[p]repboard give <member> [reason]`              | Give a member reputation.                                               |
| `[p]repboard profile [member]`                    | Show a reputation profile.                                              |
| `[p]repboard leaderboard [received/given] [limit]` | Show the top reputation members.                                        |
| `[p]repboard history [member] [limit]`            | Show recent reputation received by a member.                            |
| `[p]repboard remove <rep_id> [reason]`            | Staff-only removal for bad reputation entries.                          |
| `[p]repboard export`                              | Export reputation records as CSV.                                       |

## Requirements

- Red-DiscordBot 3.5.0 or newer.
- Python 3.9 or newer.
- Bot permissions to `Send Messages` and `Embed Links`.
- Bot permission to `Attach Files` for CSV exports.
- Manage Server or Red admin permissions for configuration.
- Manage Messages, Manage Server, or Red admin permissions for removing entries.

## Data

RepBoard stores per-guild reputation settings, reputation records, giver IDs, receiver IDs, moderator IDs for removed entries, reasons, message/channel IDs, timestamps, active/removed state, cooldown metadata, daily limit metadata, and aggregate reputation statistics.

CSV exports are generated on demand and sent directly to Discord.
