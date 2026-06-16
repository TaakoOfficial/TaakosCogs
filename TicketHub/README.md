# TicketHub

Ticket panels, configurable modal forms, ticket lifecycle controls, AAA3A Tickets profile imports, and self-contained HTML transcripts for Red-DiscordBot.

[Back to the cog catalog](../README.md)

## Install

```text
[p]repo add taakoscogs https://github.com/TaakoOfficial/TaakosCogs
[p]cog install taakoscogs TicketHub
[p]load TicketHub
```

## Highlights

- Posts ticket panels with persistent Open Ticket buttons.
- Supports configurable and imported modal questions before panel-created tickets open.
- Creates private ticket channels, or private thread tickets under a configured parent channel.
- Supports claim, unclaim, close, reopen, delete, add member, remove member, and list workflows.
- Generates HTML transcripts with DiscordChatExporterPy, plus a built-in fallback renderer and plain-text transcript.
- Sends transcripts to a transcript/log channel and optionally DMs the ticket owner.
- Imports profile settings from AAA3A's `Tickets` cog with dry-run preview before applying.
- Keeps commands under `[p]tickethub` so it can coexist with another `[p]ticket` cog during migration.

## How Transcripts Work

When a transcript is generated, TicketHub reads the ticket channel or thread history and creates:

- `ticket-<id>-transcript.html`
- `ticket-<id>-transcript.txt`

The HTML file is generated with DiscordChatExporterPy when `chat-exporter` is available. If that exporter fails or is missing, TicketHub falls back to its built-in self-contained HTML renderer. It does not require a public proxy preview service.

## How Ticket Modals Work

When a profile has form questions configured, clicking that profile's panel button collects the answers before the ticket is created. Current Red installations show text, dropdown, and boolean questions together in a native Discord modal. Older Discord.py versions fall back to the existing ephemeral step form for dropdown and boolean questions. Submitted answers are stored on the ticket record and shown in the ticket channel or thread.

```text
[p]tickethub modal wizard main
[p]tickethub modal add main boolean "Is this urgent?"
[p]tickethub modal add main choice "Department | Billing, Technical, Other"
[p]tickethub modal show main
```

## Thread Tickets

Profiles use normal private ticket channels by default. To create private thread tickets instead, set a parent text channel and switch the profile mode:

```text
[p]tickethub threadparent main #support
[p]tickethub mode main thread
```

Thread tickets add the ticket opener and cached members of configured support roles to the private thread. Discord does not support per-thread role permission overwrites, so support-role and viewer-role behavior is stricter and more configurable in channel mode. The parent channel must allow the ticket opener to view the channel, send messages in threads, and read message history.

## AAA3A Import

TicketHub can read settings from AAA3A's loaded `Tickets` cog and map one profile into TicketHub:

```text
[p]tickethub import aaa3a main
[p]tickethub import aaa3a main confirm
```

The first command is a dry-run preview. The second applies the import.

Mapped settings include:

- enabled state
- max open tickets per member
- channel name template
- welcome and custom messages
- modal form questions, including AAA3A's default reason modal behavior
- transcript setting
- owner close/reopen settings
- support, view, ping, whitelist, and blacklist roles
- open and closed categories
- log channel

Existing open ticket records, modlog cases, forum tags, and panel buttons are not imported.

## Commands

| Command                                               | Description                                        |
| ----------------------------------------------------- | -------------------------------------------------- |
| `[p]tickethub` or `[p]thub`                           | Show settings, profiles, and setup hints.          |
| `[p]tickethub walkthrough [profile]`                  | Walk through basic setup.                          |
| `[p]tickethub enable [true_or_false]`                 | Enable or disable TicketHub.                       |
| `[p]tickethub panel [profile] [channel]`              | Post a ticket panel.                               |
| `[p]tickethub profile [profile]`                      | Create a profile if it does not exist.             |
| `[p]tickethub open [profile] [reason]`                | Open a ticket by command.                          |
| `[p]tickethub modal [profile]`                        | Show modal questions for a profile.                |
| `[p]tickethub modal wizard [profile]`                 | Walk through creating a custom ticket modal.       |
| `[p]tickethub modal add <profile> [type] <label>`     | Add a text, boolean, or choice form question.       |
| `[p]tickethub modal remove <profile> <index>`         | Remove a modal question.                           |
| `[p]tickethub modal defaultreason [profile]`          | Use the default Reason modal.                      |
| `[p]tickethub modal clear [profile]`                  | Disable modal questions.                           |
| `[p]tickethub category <profile> [category]`          | Set the open-ticket category.                      |
| `[p]tickethub closedcategory <profile> [category]`    | Set the closed-ticket category.                    |
| `[p]tickethub mode <profile> <channel\|thread>`       | Choose channel or private-thread tickets.          |
| `[p]tickethub threadparent <profile> [channel]`       | Set the parent channel for thread tickets.         |
| `[p]tickethub logchannel <profile> [channel]`         | Set the ticket log channel.                        |
| `[p]tickethub transcriptchannel <profile> [channel]`  | Set the transcript channel.                        |
| `[p]tickethub supportrole add <profile> <role>`       | Add a support role.                                |
| `[p]tickethub supportrole remove <profile> <role>`    | Remove a support role.                             |
| `[p]tickethub maxopen <profile> <amount>`             | Set max open tickets per member.                   |
| `[p]tickethub transcripts <profile> <true_or_false>`  | Enable or disable transcripts on close/delete.     |
| `[p]tickethub dmtranscript <profile> <true_or_false>` | Enable or disable transcript DMs to ticket owners. |
| `[p]tickethub claim [ticket_id]`                      | Claim a ticket.                                    |
| `[p]tickethub unclaim [ticket_id]`                    | Unclaim a ticket.                                  |
| `[p]tickethub close [ticket_id] [reason]`             | Close a ticket.                                    |
| `[p]tickethub reopen [ticket_id]`                     | Reopen a ticket.                                   |
| `[p]tickethub delete [ticket_id] [reason]`            | Delete a ticket channel/thread after transcript.   |
| `[p]tickethub transcript [ticket_id]`                 | Generate and send a transcript.                    |
| `[p]tickethub addmember <member> [ticket_id]`         | Add a member to a ticket.                          |
| `[p]tickethub removemember <member> [ticket_id]`      | Remove a member from a ticket.                     |
| `[p]tickethub list [open \| closed \| all] [owner]`   | List tickets.                                      |
| `[p]tickethub import aaa3a [profile] [confirm]`       | Preview or apply an AAA3A Tickets profile import.  |
| `[p]tickethub export`                                 | Export TicketHub ticket records as CSV.            |

## Example Setup

```text
[p]tickethub walkthrough
```

Or configure directly:

```text
[p]tickethub profile main
[p]tickethub category main "Open Tickets"
[p]tickethub closedcategory main "Closed Tickets"
[p]tickethub logchannel main #ticket-logs
[p]tickethub transcriptchannel main #ticket-transcripts
[p]tickethub supportrole add main @Support
[p]tickethub panel main #support
```

Thread-ticket setup:

```text
[p]tickethub threadparent main #support
[p]tickethub mode main thread
```

## Requirements

- Red-DiscordBot 3.5.0 or newer.
- Python 3.9 or newer.
- `chat-exporter` for DiscordChatExporterPy-based HTML transcripts. Red installs this from the cog metadata.
- Bot permission to `Manage Channels` for ticket channel creation and permission updates.
- For thread mode, bot permissions to `Create Private Threads`, `Send Messages in Threads`, `Manage Threads`, `Embed Links`, and `Read Message History` in the parent channel.
- For thread mode, ticket openers need `View Channel`, `Send Messages in Threads`, and `Read Message History` in the parent channel.
- Bot permissions to `Send Messages`, `Embed Links`, `Attach Files`, and `Read Message History` in ticket and log channels.
- Manage Server permission, Red admin, or equivalent for configuration and staff management commands.

## Data

TicketHub stores per-guild ticket profiles, panel message IDs, channel/thread/category/role IDs, ticket records, ticket owner IDs, claimed/closed staff IDs, participant IDs, ticket reasons, modal form answers, close reasons, timestamps, and ticket lifecycle event metadata.

HTML and text transcripts are generated on demand from Discord message history and sent directly to configured Discord destinations.

Imported modal answers are stored on ticket records and shown in the ticket channel or thread.
