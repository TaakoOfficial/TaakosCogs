# SuggestionBox

Community suggestions with persistent voting buttons, staff review states, comments, review logs, and CSV exports for Red-DiscordBot.

[Back to the cog catalog](../README.md)

## Install

```text
[p]repo add TaakosCogs https://github.com/TaakoOfficial/TaakosCogs
[p]cog install TaakosCogs SuggestionBox
[p]load SuggestionBox
```

## Highlights

- Posts suggestions as tracked embeds in a configured channel.
- Adds persistent Upvote and Downvote arrow buttons.
- Prevents duplicate voting and optionally blocks self-voting.
- Can create a discussion thread for each suggestion.
- Supports anonymous suggestion display.
- Lets staff mark suggestions as considering, approved, denied, implemented, closed, or reopened.
- Supports staff comments, review-log embeds, suggestion lookup, lists, stats, and CSV export.

## How It Works

1. Staff runs `[p]suggestionbox walkthrough` and chooses a suggestion channel.
2. Users submit ideas with `[p]suggest <suggestion>`.
3. The bot posts the suggestion as an embed in the suggestion channel.
4. The embed gets Upvote and Downvote arrow buttons.
5. If threads are enabled, the bot creates a discussion thread attached to that suggestion message.
6. Staff reviews suggestions with commands like `[p]suggestions approve <id> [reason]`.

## Commands

| Command | Description |
| --- | --- |
| `[p]suggest <suggestion>` | Submit a suggestion. |
| `[p]suggestionbox` or `[p]suggestionset` | Show current SuggestionBox settings. |
| `[p]suggestionbox setup [suggestion_channel] [review_channel]` | Enable suggestions and configure channels. |
| `[p]suggestionbox walkthrough` or `[p]suggestionbox wizard` | Walk through setup interactively. |
| `[p]suggestionbox enable [true_or_false]` | Enable or disable suggestions and voting. |
| `[p]suggestionbox disable` | Disable suggestions and voting. |
| `[p]suggestionbox channel [channel]` | Set the suggestion channel. |
| `[p]suggestionbox reviewchannel [channel]` | Set the staff review log channel. |
| `[p]suggestionbox clearreview` | Clear the staff review log channel. |
| `[p]suggestionbox anonymous <true_or_false>` | Hide or show authors on suggestion embeds. |
| `[p]suggestionbox downvotes <true_or_false>` | Enable or disable downvotes. |
| `[p]suggestionbox selfvote <true_or_false>` | Allow or block authors voting on their own suggestions. |
| `[p]suggestionbox threads <true_or_false>` | Enable or disable per-suggestion discussion threads. |
| `[p]suggestionbox threadarchive <minutes>` | Set thread auto-archive time: `60`, `1440`, `4320`, or `10080`. |
| `[p]suggestionbox color [hex_or_color]` | Set the open suggestion embed color. Omit to reset. |
| `[p]suggestionbox reset confirm` | Clear all stored suggestion records. |
| `[p]suggestionbox refresh` | Refresh all tracked suggestion messages from stored records. |
| `[p]suggestions info <id>` | Show a suggestion by ID. |
| `[p]suggestions list [status|all] [limit]` | List suggestions by status. |
| `[p]suggestions mine [limit]` | List your submitted suggestions. |
| `[p]suggestions stats` | Show suggestion totals by status. |
| `[p]suggestions approve <id> [reason]` | Mark a suggestion as approved. |
| `[p]suggestions deny <id> [reason]` | Mark a suggestion as denied. |
| `[p]suggestions consider <id> [reason]` | Mark a suggestion as under consideration. |
| `[p]suggestions implement <id> [reason]` | Mark a suggestion as implemented. |
| `[p]suggestions close <id> [reason]` | Close a suggestion. |
| `[p]suggestions reopen <id>` | Reopen a suggestion for voting. |
| `[p]suggestions comment <id> <comment>` | Add a staff note to a suggestion. |
| `[p]suggestions delete <id> [reason]` | Delete a suggestion record and its message when possible. |
| `[p]suggestions thread <id>` | Create a discussion thread for an existing suggestion. |
| `[p]suggestions export` | Export suggestion records as CSV. |

## Example Setup

```text
[p]suggestionbox walkthrough
```

Or configure it directly:

```text
[p]suggestionbox setup #suggestions #suggestion-review
[p]suggestionbox anonymous false
[p]suggestionbox selfvote false
[p]suggestionbox downvotes true
[p]suggestionbox threads true
```

Users can then submit suggestions:

```text
[p]suggest Add a weekly community spotlight event.
```

Staff can review them:

```text
[p]suggestions consider 1 We are discussing this with staff.
[p]suggestions approve 1 Good fit for next month.
[p]suggestions implement 1 Added to the event calendar.
```

## Requirements

- Red-DiscordBot 3.5.0 or newer.
- Python 3.9 or newer.
- Bot permissions to `Send Messages`, `Embed Links`, and `Read Message History` in the suggestion channel.
- Bot permission to `Create Public Threads` in the suggestion channel when per-suggestion threads are enabled.
- Bot permission to `Attach Files` for CSV exports.
- Manage Server permission, Red admin, or equivalent for configuration and review commands.

## Data

SuggestionBox stores per-guild settings, suggestion text, author IDs, voter IDs, staff reviewer IDs, message IDs, channel IDs, thread IDs, vote lists, statuses, staff notes, review reasons, and timestamps.

CSV exports are generated on demand and sent directly to Discord.
