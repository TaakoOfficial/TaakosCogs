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

- Posts ticket panels with persistent Open Ticket buttons or dropdowns.
- Attaches a ticket panel to an existing embed/message sent by the same bot.
- Builds multi-profile panels with a custom emoji, name, and description per option.
- Supports configurable, independently numbered channel names for each profile.
- Supports configurable and imported modal questions before panel-created tickets open.
- Creates private ticket channels, or private thread tickets under a configured parent channel.
- Supports claim, unclaim, close, reopen, delete, add member, remove member, and list workflows.
- Changes Claim to Unclaim and makes other support members read-only while a ticket is claimed.
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

Thread tickets add the ticket opener and cached members of configured support roles to the private thread. Discord does not support per-thread role permission overwrites, so claiming a private-thread ticket removes everyone except the opener, claimer, TicketHub bot, and cached members with Manage Server/Administrator permission. Support members and added participants are restored when the ticket is unclaimed. The parent channel must allow the ticket opener to view the channel, send messages in threads, and read message history.

## Claim Locking

Claiming an open ticket changes its **Claim** button to **Unclaim**. For channel tickets,
the opener, claimer, and members with Manage Server or Administrator permission can
continue sending messages; other support members and added participants become
read-only. Unclaiming restores their send permissions and changes the button back to
**Claim**.

The `[p]tickethub claim` and `[p]tickethub unclaim` commands apply the same permission
changes as the button. Added members remain read-only while a claim lock is active.

## Locking Tickets

Support staff can press **Lock** to stop the ticket opener and manually added members
from posting while keeping the ticket open for staff. The button changes to **Unlock**,
which restores member access without changing the ticket's claim state.

For channel tickets, locked members remain able to read the channel. Discord does not
support per-member send overrides inside private threads, so TicketHub temporarily
removes those members from a locked private thread and restores them when it is unlocked.

The same behavior is available through `[p]tickethub lock [ticket_id]` and
`[p]tickethub unlock [ticket_id]`.

## Closing Tickets

The ticket **Close** button opens a modal requiring a close reason. Submitting it posts
a red **Close Ticket** confirmation in the ticket channel, mentions the ticket opener,
shows the reason, and provides **Cancel** and **Close** buttons. Cancel keeps the ticket
open; Close completes the normal close/transcript workflow. If nobody responds within
five minutes, TicketHub closes the ticket automatically.

Prefix commands cannot directly open Discord modals, so `[p]tickethub close` sends an
**Enter Close Reason** button that only the command author can use. Supplying a reason
with the command skips that button and posts the confirmation immediately:

```text
[p]tickethub close
[p]tickethub close 42 Duplicate request
```

Pending confirmations and their timeout are restored after a bot restart. The ticket
opener, close requester, and support staff can cancel or confirm the prompt.

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
| `[p]tickethub panel [profile] [channel] [style]`      | Post a button or dropdown ticket panel.            |
| `[p]tickethub attachpanel <profile> <message> [style]` | Attach a panel to an existing bot-authored message. |
| `[p]tickethub multipanel`                             | Show multi-profile panel management commands.      |
| `[p]tickethub multipanel add <message> <profile> <style> <emoji> <name> \| <description>` | Add a profile option. |
| `[p]tickethub multipanel remove <message> <profile>`  | Remove a profile option.                           |
| `[p]tickethub multipanel style <message> <style>`     | Switch a multi-panel between buttons and dropdown. |
| `[p]tickethub multipanel placeholder <message> <text>` | Set its dropdown placeholder.                     |
| `[p]tickethub multipanel show <message>`              | Show its configured profile options.               |
| `[p]tickethub multipanel clear <message>`             | Remove the multi-panel components and configuration. |
| `[p]tickethub profile [profile]`                      | Create a profile if it does not exist.             |
| `[p]tickethub channelname [profile] [template]`       | Show or set a profile's channel-name template.     |
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
| `[p]tickethub lock [ticket_id]`                       | Prevent the opener and added members from posting. |
| `[p]tickethub unlock [ticket_id]`                     | Restore posting access to locked ticket members.   |
| `[p]tickethub close [ticket_id] [reason]`             | Request closure with a reason and confirmation.    |
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
[p]tickethub panel main #support button
```

Use `dropdown` as the final argument to post a dropdown panel instead. TicketHub can
also preserve an existing message's content and embeds while adding its panel:

```text
[p]tickethub attachpanel main https://discord.com/channels/server/channel/message dropdown
```

The existing message must have been sent by the same bot and cannot already contain
unrelated buttons or select menus. Running `attachpanel` again on the same profile and
message can switch its panel style.

## Multi-Profile Panels

A multi-panel attaches several TicketHub profiles to one existing message. Each option
has its own display name, emoji, and brief description. The target message must have
been sent by the same bot and cannot already contain unrelated components.

Add dropdown options one at a time using a message link:

```text
[p]tickethub multipanel add <message-link> billing dropdown 💳 Billing | Payment and invoice help
[p]tickethub multipanel add <message-link> technical dropdown 🛠️ Technical | Product and account problems
[p]tickethub multipanel add <message-link> other dropdown ❓ Other | Anything else
```

Every referenced profile must already exist. Names are limited to 80 characters and
descriptions to 100 characters. Use `none` when an option should not have an emoji.

Switch the same panel to buttons or customize its dropdown placeholder:

```text
[p]tickethub multipanel style <message-link> button
[p]tickethub multipanel style <message-link> dropdown
[p]tickethub multipanel placeholder <message-link> What can we help you with?
```

Discord buttons cannot display descriptions. TicketHub retains them when button mode
is selected so they return if the panel is switched back to a dropdown. Multi-panel
components are persistent across bot restarts.

## Ticket Channel Names

Each profile has its own channel-name template and ticket-number sequence. For example:

```text
[p]tickethub channelname support {id}-support-{owner_name}
[p]tickethub channelname billing {id}-billing-{owner_display_name}
```

For new profiles, `{id}` starts at `1` and increments independently. Upgraded profiles
continue above their highest existing ticket number to avoid reused names. TicketHub
also retains a guild-wide internal ID so commands and stored records remain
unambiguous; use `{global_id}` if that number should appear in the channel name.

Supported placeholders are `{id}`, `{ticket_id}`, `{profile_id}`, `{global_id}`,
`{owner_display_name}`, `{owner_name}`, `{owner_mention}`, `{owner_id}`, `{guild_name}`,
`{guild_id}`, and `{profile}`. The first three all mean the profile-local number. Run
the command without a template to show the current template and next profile ID, or
use `reset` to restore `ticket-{id}-{owner_name}`.

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

TicketHub stores per-guild ticket profiles and their next ticket numbers, panel message IDs and styles, multi-panel option labels/descriptions/emojis, channel/thread/category/role IDs, global and profile-local ticket IDs, ticket records, ticket owner IDs, claimed/locked/unlocked/closed staff IDs, participant IDs, ticket reasons, modal form answers, pending close requester/reason/expiry data, close reasons, timestamps, and ticket lifecycle event metadata.

HTML and text transcripts are generated on demand from Discord message history and sent directly to configured Discord destinations.

Imported modal answers are stored on ticket records and shown in the ticket channel or thread.
