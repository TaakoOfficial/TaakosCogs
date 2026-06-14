# ReviewHub

ReviewHub-style reviews, vouches, review requests, stats, leaderboards, reports, useful votes, and configurable review embeds for Red-DiscordBot.

[Back to the cog catalog](../README.md)

## Install

```text
[p]repo add taakoscogs https://github.com/TaakoOfficial/TaakosCogs
[p]cog install taakoscogs ReviewHub
[p]load ReviewHub
```

## Highlights

- Mirrors the public ReviewHub command surface: `/review`, `/vouch`, `/rateme`, `/stats`, `/leaderboard`, `/help`, `/deletereview`, and `/config`.
- Supports review mode and vouch mode.
- Lets admins choose whether regular reviews can target a specific member.
- Posts public review embeds to a configured channel.
- Adds persistent submit, report, and useful buttons.
- Supports `/rateme` request messages with a submit button and modal.
- Uses a native 1–5 star dropdown in review submission modals on current Red installations.
- Includes Classic and Detailed review embed templates.
- Tracks server and user stats, useful votes, and top 10 leaderboards.
- Stores reports and can forward report alerts to a staff channel.
- Can auto-create discussion threads for review posts.
- Provides CSV export through `[p]reviewhub export`.

## Quick Setup

```text
[p]reviewhub setup #reviews #review-reports
```

Then users can submit reviews:

```text
/review rating:5 message:Great experience.
/vouch member:@User rating:5 message:Reliable and helpful.
```

To let users attach a regular review to a specific person, such as a service provider:

```text
[p]reviewhub config reviewtargets true
/review member:@Provider rating:5 message:Great service.
```

Staff can request a review from a member:

```text
/rateme @User
```

## Slash Commands

| Command | Description |
| --- | --- |
| `/review` | Submit a review. If enabled by staff, users can choose a member the review is about. If rating or message is omitted, Discord opens a modal. |
| `/vouch` | Recommend another member. |
| `/rateme @User` | Request a review from a specific user. |
| `/stats [user] [global_stats]` | View server or user statistics. |
| `/leaderboard [mode] [global_stats]` | View the top 10 members by submitted, received, or useful count. |
| `/help` | View ReviewHub commands and reference links. |
| `/deletereview id:<review id>` | Delete a review by ID. |
| `/config server` | Configure review/report channels, threads, titles, command state, request deletion, vouch mode, and targeted reviews. |
| `/config appearance` | Configure buttons, template, color, labels, and emojis. |
| `/config access` | Configure the `/rateme` role and review submission role. |

## Prefix Fallbacks

| Command | Description |
| --- | --- |
| `[p]reviewhub` or `[p]rh` | Show current settings. |
| `[p]reviewhub help` | Show command help. |
| `[p]reviewhub setup [review_channel] [report_channel]` | Quick setup. |
| `[p]reviewhub review [member] <rating> <message>` | Submit a review. |
| `[p]reviewhub vouch <member> <rating> <message>` | Submit a vouch. |
| `[p]reviewhub rateme <member>` | Request a review. |
| `[p]reviewhub stats [member] [global_stats]` | View stats. |
| `[p]reviewhub leaderboard [submitted|received|useful] [global_stats]` | View leaderboard. |
| `[p]reviewhub deletereview <id> [reason]` | Delete a review. |
| `[p]reviewhub config` | Show settings. |
| `[p]reviewhub config reviewchannel [channel]` | Set or clear the review channel. |
| `[p]reviewhub config reportchannel [channel]` | Set or clear the report channel. |
| `[p]reviewhub config template <classic|detailed>` | Set the review template. |
| `[p]reviewhub config color <hex>` | Set the review embed color. |
| `[p]reviewhub config vouchmode <true_or_false>` | Enable or disable vouch mode. |
| `[p]reviewhub config reviewtargets <true_or_false>` | Allow or block users from choosing a reviewed member on regular reviews. |
| `[p]reviewhub config autothread <true_or_false>` | Enable or disable discussion threads. |
| `[p]reviewhub config ratemerole [role]` | Set or clear the `/rateme` role. |
| `[p]reviewhub export` | Export review records as CSV. |

## Notes

This is a local Red cog inspired by the documented ReviewHub workflow. It does not call the external ReviewHub service or control panel.

The self-hosted default daily limit is 5 reviews per server, resetting at midnight UTC+2 to match the documented free-plan behavior. The cog stores everything in Red's Config system.

## Requirements

- Red-DiscordBot 3.5.0 or newer.
- Python 3.9 or newer.
- Bot permissions to `Send Messages` and `Embed Links` in review/request channels.
- Bot permission to `Create Public Threads` if auto-threading is enabled.
- Bot permission to `Attach Files` for CSV exports.
- Manage Server permission for configuration and `/rateme` unless a `/rateme` role is configured.

## Data

ReviewHub stores per-guild settings, review request records, review/vouch records, Discord user IDs for reviewers, reviewed users, reporters, useful votes, moderators, review text, ratings, message/channel IDs, timestamps, and deletion metadata.

CSV exports are generated on demand and sent directly to Discord.
