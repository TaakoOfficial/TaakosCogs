# TicketHub

Ticket panels, configurable modal forms, ticket lifecycle controls, AAA3A Tickets profile imports, and self-contained HTML transcripts for Red-DiscordBot.

[Back to the cog catalog](../README.md)

## Install

```text
[p]repo add taakoscogs https://github.com/TaakoOfficial/TaakosCogs
[p]cog install taakoscogs TicketHub
[p]load TicketHub
```

Enable and publish TicketHub's native application commands with Red's built-in slash manager:

```text
[p]slash enablecog TicketHub
[p]slash sync
```

Discord exposes the main command tree as `/ticket` and the setup tree as
`/ticketset`. Use `/ticket help` for ticket actions and `/ticketset …` for profiles,
panels, forms, roles, automation, imports, and exports. Prefix users can use
`[p]ticket` and `[p]ticketset`; `[p]tickethub`, `[p]thub`, `[p]tickethubset`, and
`[p]thubset` remain aliases.

If AAA3A's `Tickets` cog is still loaded, it already owns `[p]ticket` and
`[p]ticketset`. In that side-by-side migration state, TicketHub loads with
`[p]tickethub` and `[p]tickethubset` so you can run the import before unloading
AAA3A. After AAA3A is unloaded, reload TicketHub if you want it to claim the
standard `[p]ticket` and `[p]ticketset` prefix commands.

## Highlights

- Posts ticket panels with persistent Open Ticket buttons or dropdowns.
- Attaches a ticket panel to an existing embed/message sent by the same bot.
- Builds multi-profile panels with a custom emoji, name, and description per option.
- Supports configurable, independently numbered channel names for each profile.
- Supports configurable and imported modal questions before panel-created tickets open.
- Creates private ticket channels, or private thread tickets under a configured parent channel.
- Supports claim, unclaim, lock, close, reopen, delete, recovery, member management, and list workflows.
- Provides persistent ticket controls for Members, Claim, Lock, Close/Reopen, Transcript, and Delete.
- Supports close-on-leave, configurable close-request timeouts, configurable closed-ticket auto-delete, ticket roles, and control emojis.
- Changes Claim to Unclaim and makes other support members read-only while a ticket is claimed.
- Generates HTML transcripts with DiscordChatExporterPy, plus a built-in fallback renderer and plain-text transcript.
- Sends transcripts to a transcript/log channel and optionally DMs the ticket owner.
- Imports profile settings from AAA3A's `Tickets` cog with dry-run preview before applying.
- Provides native commands under `/ticket` and `/ticketset`.

## How Transcripts Work

When a transcript is generated, TicketHub reads the ticket channel or thread history and creates:

- `ticket-<id>-transcript.html`
- `ticket-<id>-transcript.txt`

The HTML file is generated with DiscordChatExporterPy when `chat-exporter` is available. If that exporter fails or is missing, TicketHub falls back to its built-in self-contained HTML renderer. It does not require a public proxy preview service.

## How Ticket Modals Work

When a profile has form questions configured, clicking that profile's panel button collects the answers before the ticket is created. Current Red installations show text, dropdown, and boolean questions together in a native Discord modal. Older Discord.py versions fall back to the existing ephemeral step form for dropdown and boolean questions. Submitted answers are stored on the ticket record and shown in the ticket channel or thread.

```text
[p]ticketset modal wizard main
[p]ticketset modal add main boolean "Is this urgent?"
[p]ticketset modal add main choice "Department | Billing, Technical, Other"
[p]ticketset modal show main
```

## Thread Tickets

Profiles use normal private ticket channels by default. To create private thread tickets instead, set a parent text channel and switch the profile mode:

```text
[p]ticketset threadparent main #support
[p]ticketset mode main thread
```

Thread tickets add the ticket opener and cached members of configured support roles to the private thread. Discord does not support per-thread role permission overwrites, so claiming a private-thread ticket removes everyone except the opener, claimer, TicketHub bot, and cached members with Manage Server/Administrator permission. Support members and added participants are restored when the ticket is unclaimed. The parent channel must allow the ticket opener to view the channel, send messages in threads, and read message history.

## Claim Locking

Claiming an open ticket changes its **Claim** button to **Unclaim**. For channel tickets,
the opener, claimer, and members with Manage Server or Administrator permission can
continue sending messages; other support members and added participants become
read-only. Unclaiming restores their send permissions and changes the button back to
**Claim**.

The `[p]ticket claim` and `[p]ticket unclaim` commands apply the same permission
changes as the button. Added members remain read-only while a claim lock is active.

## Locking Tickets

Support staff can press **Lock** to stop the ticket opener and manually added members
from posting while keeping the ticket open for staff. The button changes to **Unlock**,
which restores member access without changing the ticket's claim state.

For channel tickets, locked members remain able to read the channel. Discord does not
support per-member send overrides inside private threads, so TicketHub temporarily
removes those members from a locked private thread and restores them when it is unlocked.

The same behavior is available through `[p]ticket lock [ticket_id]` and
`[p]ticket unlock [ticket_id]`.

## Managing Members

The **Members** button opens Discord member pickers for adding or removing ticket
participants. Support staff can always use them. Profile settings can also allow the
ticket opener to add or remove members with `[p]ticketset behavior ownerpermission`.

When a ticket closes, its control changes to **Reopen** with an optional reopen reason.
Closed tickets also expose a support-only **Delete** control. The same operations are
available through commands.

## Closing Tickets

The ticket **Close** button opens a modal with an optional close reason. Submitting it posts
a red **Close Ticket** confirmation in the ticket channel, mentions the ticket opener,
shows the reason, and provides **Cancel** and **Close** buttons. Cancel keeps the ticket
open; Close closes the ticket without generating a transcript. If nobody responds within
the configured timeout, TicketHub closes the ticket automatically.

`[p]ticket close` posts the same confirmation immediately. Supplying a reason with the
command shows it in the confirmation prompt:

```text
[p]ticket close
[p]ticket close 42 Duplicate request
```

Pending confirmations and their timeout are restored after a bot restart. New close
requests use the profile's close timeout, which defaults to five minutes:

```text
[p]ticketset behavior closetimeout main 10
[p]ticketset behavior closetimeout main default
```

The ticket opener, close requester, and support staff can cancel or confirm the prompt.

## Lifecycle Automation

Profiles close an owner's open tickets when they leave by default. Configure this with:

```text
[p]ticketset behavior closeonleave main true
[p]ticketset behavior closetimeout main 10
[p]ticketset behavior autodelete main 24
[p]ticketset behavior autodelete main off
```

Auto-delete timers survive cog and bot restarts. Setting the value to `0` deletes a
closed ticket after a five-second grace period.

## AAA3A Import

TicketHub can read settings from AAA3A's loaded `Tickets` cog and map one profile into TicketHub:

```text
[p]tickethubset data import-aaa3a main
[p]tickethubset data import-aaa3a main confirm
```

To import every AAA3A profile at once:

```text
[p]tickethubset data import-aaa3a-all
[p]tickethubset data import-aaa3a-all confirm
```

The first command is a dry-run preview. The second applies the import. Import-all
will create or overwrite TicketHub profiles using the cleaned AAA3A profile names.

Mapped settings include:

- enabled state
- max open tickets per member
- channel name template
- welcome and custom messages
- modal form questions, including AAA3A's default reason modal behavior
- transcript setting
- owner close/reopen/member-management settings and close-on-leave
- support, speak, view, ping, whitelist, and blacklist roles
- ticket role, control emojis, and closed-ticket auto-delete
- open and closed categories
- log channel
- existing AAA3A panel button/dropdown routing, so old panel messages can open TicketHub tickets without being rebuilt

Existing open ticket records, modlog cases, and forum tags are not imported.

## Commands

| Command                                               | Description                                        |
| ----------------------------------------------------- | -------------------------------------------------- |
| `[p]ticket` or `[p]thub`                           | Show the TicketHub help menu.                      |
| `[p]ticket status`                                 | Show settings, profiles, and setup hints.          |
| `[p]ticketset walkthrough [profile]`                  | Walk through basic setup.                          |
| `[p]ticketset enable [true_or_false]`                 | Enable or disable TicketHub.                       |
| `[p]ticketset panel [profile] [channel] [style]`      | Post a button or dropdown ticket panel.            |
| `[p]ticketset attachpanel <profile> <message> [style]` | Attach a panel to an existing bot-authored message. |
| `[p]ticketset clearpanel <message>`                    | Remove tracked TicketHub controls from a message.  |
| `[p]ticketset multipanel`                             | Show multi-profile panel management commands.      |
| `[p]ticketset multipanel add <message> <profile> <style> <emoji> <name> \| <description>` | Add a profile option. |
| `[p]ticketset multipanel remove <message> <profile>`  | Remove a profile option.                           |
| `[p]ticketset multipanel style <message> <style>`     | Switch a multi-panel between buttons and dropdown. |
| `[p]ticketset multipanel placeholder <message> <text>` | Set its dropdown placeholder.                     |
| `[p]ticketset multipanel show <message>`              | Show its configured profile options.               |
| `[p]ticketset multipanel clear <message>`             | Remove the multi-panel components and configuration. |
| `[p]ticketset profile [profile]` or `[p]ticketset profile show [profile]` | Show an existing profile's settings. |
| `[p]ticketset profile list`                           | List configured profiles and their ticket counts.  |
| `[p]ticketset profile create <profile>`               | Create a new profile.                              |
| `[p]ticketset profile delete <profile> confirm`       | Delete an unused profile.                          |
| `[p]ticketset channelname [profile] [template]`       | Show or set a profile's channel-name template.     |
| `[p]ticket open [profile] [reason]`                | Open a ticket by command.                          |
| `[p]ticket createfor <member> [profile] [reason]`  | Create a ticket for another member.                |
| `[p]ticketset modal [profile]`                        | Show modal questions for a profile.                |
| `[p]ticketset modal wizard [profile]`                 | Walk through creating a custom ticket modal.       |
| `[p]ticketset modal add <profile> [type] <label>`     | Add a text, boolean, or choice form question.       |
| `[p]ticketset modal remove <profile> <index>`         | Remove a modal question.                           |
| `[p]ticketset modal defaultreason [profile]`          | Use the default Reason modal.                      |
| `[p]ticketset modal clear [profile]`                  | Disable modal questions.                           |
| `[p]ticketset category <profile> [category]`          | Set the open-ticket category.                      |
| `[p]ticketset closedcategory <profile> [category]`    | Set the closed-ticket category.                    |
| `[p]ticketset mode <profile> <channel\|thread>`       | Choose channel or private-thread tickets.          |
| `[p]ticketset threadparent <profile> [channel]`       | Set the parent channel for thread tickets.         |
| `[p]ticketset logchannel <profile> [channel]`         | Set the ticket log channel.                        |
| `[p]ticketset transcriptchannel <profile> [channel]`  | Set the transcript channel.                        |
| `[p]ticketset roles support-add <profile> <role>`       | Add a support role.                                |
| `[p]ticketset roles support-remove <profile> <role>`    | Remove a support role.                             |
| `[p]ticketset roles add <profile> <type> <role>`      | Add a support/speak/view/ping/access role.         |
| `[p]ticketset roles remove <profile> <type> <role>`   | Remove a configured profile role.                  |
| `[p]ticketset roles ticketrole <profile> [role]`            | Set or clear the role assigned to ticket openers.  |
| `[p]ticketset behavior ownerpermission <profile> <action> <bool>` | Configure owner close/reopen/member permissions. |
| `[p]ticketset behavior closeonleave <profile> <bool>` | Toggle automatic closing when an owner leaves.     |
| `[p]ticketset behavior closetimeout <profile> <minutes>` | Configure unanswered close-request timing.      |
| `[p]ticketset behavior autodelete <profile> <hours\|off>` | Configure closed-ticket deletion.               |
| `[p]ticketset behavior emoji <profile> <action> <emoji>` | Configure a ticket-control emoji.                |
| `[p]ticketset behavior maxopen <profile> <amount>`    | Set max open tickets per member.                   |
| `[p]ticketset behavior transcripts <profile> <true_or_false>` | Enable or disable transcripts on ticket delete. |
| `[p]ticketset behavior dmtranscript <profile> <true_or_false>` | Enable or disable transcript DMs to ticket owners. |
| `[p]ticket claim [ticket_id]`                      | Claim a ticket.                                    |
| `[p]ticket unclaim [ticket_id]`                    | Unclaim a ticket.                                  |
| `[p]ticket lock [ticket_id]`                       | Prevent the opener and added members from posting. |
| `[p]ticket unlock [ticket_id]`                     | Restore posting access to locked ticket members.   |
| `[p]ticket close [ticket_id] [reason]`             | Request closure with an optional reason.           |
| `[p]ticket reopen [ticket_id] [reason]`            | Reopen a ticket with an optional reason.           |
| `[p]ticket delete [ticket_id] [reason]`            | Delete a ticket channel/thread after transcript.   |
| `[p]ticket recover [channel]`                      | Recover a record from its TicketHub control embed. |
| `[p]ticket transcript [ticket_id]`                 | Generate and send a transcript.                    |
| `[p]ticket addmember <member> [ticket_id]`         | Add a member to a ticket.                          |
| `[p]ticket removemember <member> [ticket_id]`      | Remove a member from a ticket.                     |
| `[p]ticket list [status] [owner]`                  | List open/claimed/unclaimed/closed/all tickets.     |
| `[p]ticket show [ticket_id]`                       | Show a ticket's stored details.                    |
| `[p]ticketset data import-aaa3a [profile] [confirm]`       | Preview or apply an AAA3A Tickets profile import.  |
| `[p]ticketset data import-aaa3a-all [confirm]`       | Preview or apply all AAA3A Tickets profile imports. |
| `[p]ticketset data export`                                 | Export TicketHub ticket records as CSV.            |

## Example Setup

```text
[p]ticketset walkthrough
```

Or configure directly:

```text
[p]ticketset category main "Open Tickets"
[p]ticketset closedcategory main "Closed Tickets"
[p]ticketset logchannel main #ticket-logs
[p]ticketset transcriptchannel main #ticket-transcripts
[p]ticketset roles support-add main @Support
[p]ticketset panel main #support button
```

Use `dropdown` as the final argument to post a dropdown panel instead. TicketHub can
also preserve an existing message's content and embeds while adding its panel:

```text
[p]ticketset attachpanel main https://discord.com/channels/server/channel/message dropdown
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
[p]ticketset multipanel add <message-link> billing dropdown 💳 Billing | Payment and invoice help
[p]ticketset multipanel add <message-link> technical dropdown 🛠️ Technical | Product and account problems
[p]ticketset multipanel add <message-link> other dropdown ❓ Other | Anything else
```

Every referenced profile must already exist. Names are limited to 80 characters and
descriptions to 100 characters. Use `none` when an option should not have an emoji.

Switch the same panel to buttons or customize its dropdown placeholder:

```text
[p]ticketset multipanel style <message-link> button
[p]ticketset multipanel style <message-link> dropdown
[p]ticketset multipanel placeholder <message-link> What can we help you with?
```

Discord buttons cannot display descriptions. TicketHub retains them when button mode
is selected so they return if the panel is switched back to a dropdown. Multi-panel
components are persistent across bot restarts.

## Ticket Channel Names

Each profile has its own channel-name template and ticket-number sequence. For example:

```text
[p]ticketset channelname support {id}-support-{owner_name}
[p]ticketset channelname billing {id}-billing-{owner_display_name}
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
[p]ticketset threadparent main #support
[p]ticketset mode main thread
```

## Requirements

- Red-DiscordBot 3.5.0 or newer.
- Python 3.9 or newer.
- `chat-exporter` for DiscordChatExporterPy-based HTML transcripts. Red installs this from the cog metadata.
- Bot permission to `Manage Channels` for ticket channel creation and permission updates.
- Bot permission to `Manage Roles` when a profile ticket role is configured.
- For thread mode, bot permissions to `Create Private Threads`, `Send Messages in Threads`, `Manage Threads`, `Embed Links`, and `Read Message History` in the parent channel.
- For thread mode, ticket openers need `View Channel`, `Send Messages in Threads`, and `Read Message History` in the parent channel.
- Bot permissions to `Send Messages`, `Embed Links`, `Attach Files`, and `Read Message History` in ticket and log channels.
- Manage Server permission, Red admin, or equivalent for configuration and staff management commands.

## Data

TicketHub stores per-guild ticket profiles and their next ticket numbers, panel message IDs and styles, multi-panel option labels/descriptions/emojis, control emojis, lifecycle settings, channel/thread/category/role IDs, global and profile-local ticket IDs, ticket records, ticket owner IDs, claimed/locked/unlocked/closed/reopened staff IDs, participant IDs, ticket reasons, modal form answers, pending close requester/reason/expiry data, close and reopen reasons, timestamps, and ticket lifecycle event metadata.

HTML and text transcripts are generated on demand from Discord message history and sent directly to configured Discord destinations.

Imported modal answers are stored on ticket records and shown in the ticket channel or thread.
