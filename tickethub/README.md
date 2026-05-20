# tickethub

Ticket panels, configurable modal forms, ticket lifecycle controls, AAA3A Tickets profile imports, and self-contained HTML transcripts for Red-DiscordBot.

[Back to the cog catalog](../README.md)

## Install

```text
[p]repo add taakoscogs https://github.com/TaakoOfficial/TaakosCogs
[p]cog install taakoscogs tickethub
[p]load tickethub
```

## Highlights

- Posts ticket panels with persistent Open Ticket buttons.
- Supports configurable and imported modal questions before panel-created tickets open.
- Creates private ticket channels with owner, support role, and viewer role permissions.
- Supports claim, unclaim, close, reopen, delete, add member, remove member, and list workflows.
- Generates self-contained HTML transcripts with a dark viewer, message search, attachments, embeds, and ticket events.
- Sends transcripts to a transcript/log channel and optionally DMs the ticket owner.
- Imports profile settings from AAA3A's `Tickets` cog with dry-run preview before applying.
- Keeps commands under `[p]tickethub` so it can coexist with another `[p]ticket` cog during migration.

## How Transcripts Work

When a transcript is generated, TicketHub reads the ticket channel history and creates:

- `ticket-<id>-transcript.html`
- `ticket-<id>-transcript.txt`

The HTML file is self-contained and can be opened directly in a browser. It does not require a public proxy preview service.

## How Ticket Modals Work

When a profile has modal questions configured, clicking that profile's panel button opens a Discord modal before the ticket channel is created. Submitted answers are stored on the ticket record and shown in the ticket channel.

```text
[p]tickethub modal wizard main
[p]tickethub modal show main
```

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
| `[p]tickethub modal add <profile> <label>`            | Add a required paragraph modal question.           |
| `[p]tickethub modal remove <profile> <index>`         | Remove a modal question.                           |
| `[p]tickethub modal defaultreason [profile]`          | Use the default Reason modal.                      |
| `[p]tickethub modal clear [profile]`                  | Disable modal questions.                           |
| `[p]tickethub category <profile> [category]`          | Set the open-ticket category.                      |
| `[p]tickethub closedcategory <profile> [category]`    | Set the closed-ticket category.                    |
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
| `[p]tickethub delete [ticket_id] [reason]`            | Delete a ticket channel after saving a transcript. |
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

## Requirements

- Red-DiscordBot 3.5.0 or newer.
- Python 3.9 or newer.
- Bot permission to `Manage Channels` for ticket channel creation and permission updates.
- Bot permissions to `Send Messages`, `Embed Links`, `Attach Files`, and `Read Message History` in ticket and log channels.
- Manage Server permission, Red admin, or equivalent for configuration and staff management commands.

## Data

TicketHub stores per-guild ticket profiles, panel message IDs, channel/category/role IDs, ticket records, ticket owner IDs, claimed/closed staff IDs, participant IDs, ticket reasons, modal form answers, close reasons, timestamps, and ticket lifecycle event metadata.

HTML and text transcripts are generated on demand from Discord message history and sent directly to configured Discord destinations.

Imported modal answers are stored on ticket records and shown in the ticket channel.
