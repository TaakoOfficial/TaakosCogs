# InviteTracker

Invite tracking, join-source lookup, fake join detection, leaver counts, leaderboards, and CSV exports for Red-DiscordBot.

[Back to the cog catalog](../README.md)

## Install

```text
[p]repo add taakoscogs https://github.com/TaakoOfficial/TaakosCogs
[p]cog install taakoscogs InviteTracker
[p]load InviteTracker
```

## Highlights

- Tracks which invite was used when a member joins.
- Maintains inviter stats for total joins, leavers, fake joins, and net valid joins.
- Detects fake joins using a configurable account-age threshold.
- Logs member joins and leaves with invite source details.
- Shows invite stats, leaderboards, member join sources, and members invited by a user.
- Exports tracked join records as CSV for staff review.
- Keeps an invite cache refreshed at setup, enable, manual refresh, and invite create/delete events.

## Commands

| Command                                        | Description                                                                     |
| ---------------------------------------------- | ------------------------------------------------------------------------------- |
| `[p]invitetracker`                             | Show current settings, quick setup steps, required access, and useful commands. |
| `[p]invitetracker setup [channel]`             | Enable tracking, set the log channel, and cache current invites.                |
| `[p]invitetracker enable [true_or_false]`      | Enable or disable invite tracking.                                              |
| `[p]invitetracker disable`                     | Disable invite tracking.                                                        |
| `[p]invitetracker channel [channel]`           | Set the invite log channel. Omit the channel to use the current channel.        |
| `[p]invitetracker clearchannel`                | Clear the invite log channel.                                                   |
| `[p]invitetracker fakeage <hours>`             | Set the account-age threshold for fake joins. Use `0` to disable fake marking.  |
| `[p]invitetracker includebots <true_or_false>` | Choose whether bot joins should be tracked.                                     |
| `[p]invitetracker refresh`                     | Refresh the cached invite list from Discord.                                    |
| `[p]invitetracker resetstats confirm`          | Clear all tracked invite stats and member records for the server.               |
| `[p]invitetracker settings`                    | Show current settings.                                                          |
| `[p]invites [member]`                          | Show invite stats for yourself or another member.                               |
| `[p]invites top [limit]`                       | Show the invite leaderboard, up to 25 users.                                    |
| `[p]invites source <member>`                   | Show which invite a current member joined with.                                 |
| `[p]invites joinedby <member> [limit]`         | List currently tracked members invited by a user.                               |
| `[p]invites export`                            | Export tracked member invite records as CSV.                                    |

## Example Setup

```text
[p]invitetracker setup #join-logs
[p]invitetracker fakeage 48
[p]invitetracker includebots false
[p]invites top 10
```

## How Tracking Works

Discord does not send the invite code directly with a member join event. InviteTracker keeps a cache of invite use counts. When someone joins, it fetches the current invite list and compares the new use counts against the cached counts.

If the bot cannot read server invites, or an invite disappears before Discord returns the updated list, the join may be counted as unknown.

## Requirements

- Red-DiscordBot 3.5.0 or newer.
- Python 3.9 or newer.
- Bot permission to `Manage Server` so Discord allows reading server invites.
- Bot permissions to `Send Messages` and `Embed Links` in the configured log channel.
- Server Members intent is required for join and leave tracking.
- Manage Server permission, Red admin, or equivalent for configuration commands.

## Data

InviteTracker stores per-guild settings, cached invite metadata, inviter statistics, tracked member join-source records, Discord user IDs, invite codes, timestamps, fake-join flags, and unknown join counts.

CSV exports are generated on demand and sent directly to Discord.
