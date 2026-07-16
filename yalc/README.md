# yalc

Yet Another Logging Cog: configurable server logging for Red-DiscordBot.

[Back to the cog catalog](../README.md)

## Install

```text
[p]repo add taakoscogs https://github.com/TaakoOfficial/TaakosCogs
[p]cog install taakoscogs yalc
[p]load yalc
```

## Highlights

- Logs message, member, moderation, channel, overwrite, thread/forum, role, guild, voice, stage, sticker, soundboard, AutoMod, webhook, invite, command, integration, emoji, and other server events.
- Correlates Discord audit entries by action, target, channel, and time so unrelated moderators are never shown as a fallback.
- Covers cached and uncached message edits/deletes, bulk deletes, bot additions, member prunes, permission-overwrite changes, and webhook lifecycle actions.
- Routes every event independently, with per-event enable switches and colors.
- Filters users, roles, channels, categories, bots, webhooks, applications, prefixes, and proxy systems, plus precise event/user/channel ignore rules.
- Fails closed when a destination is unavailable unless an administrator explicitly selects a safe fallback channel.
- Offers an optional searchable SQLite event journal with automatic retention, CSV/JSON export, and message content disabled by default.
- Includes a fully standalone dashboard—no JSON editor, generic fallback, WTForms, or shared form component.

## Commands

| Command                                            | Description                                       |
| -------------------------------------------------- | ------------------------------------------------- |
| `[p]yalc` or `[p]logger`                           | Show the YALC command group help.                 |
| `[p]yalc setup`                                    | Run the setup workflow.                           |
| `[p]yalc autodetect`                               | Try smart setup/autodetection.                    |
| `[p]yalc settings`                                 | Show current logging settings.                    |
| `[p]yalc enable [event_type]`                      | Enable an event or list available event types.    |
| `[p]yalc disable <event_type>`                     | Disable an event type.                            |
| `[p]yalc setchannel <event_type_or_all> [channel]` | Set where logs should post.                       |
| `[p]yalc bulk_enable`                              | Enable multiple event types.                      |
| `[p]yalc bulk_disable`                             | Disable multiple event types.                     |
| `[p]yalc validate`                                 | Validate configuration and permissions.           |
| `[p]yalc test`                                     | Run diagnostics. Aliases: `diagnostics`, `debug`. |
| `[p]yalc reset`                                    | Reset YALC settings for the server.               |
| `[p]yalc dashboard`                                | Show dashboard integration details.               |
| `[p]yalc journal`                                  | Show optional local journal status.                |
| `[p]yalc journal search [event] [query]`           | Search up to 25 recent matching journal records.   |
| `[p]yalc journal export [csv/json] [event]`        | Export up to 500 recent journal records.           |
| `[p]yalc journal prune`                            | Apply configured retention immediately.            |
| `[p]yalc journal clear CONFIRM`                    | Permanently clear this server's journal.            |

## Setup Channels

`[p]yalc setup CONFIRM` creates a private `YALC Logs` category with these channels and routes supported event types to the closest match:

`🤖 | application-logs`, `🤖 | channel-logs`, `🤖 | discord-automod-logs`, `🤖 | emoji-logs`, `🤖 | event-logs`, `🤖 | invite-logs`, `🤖 | message-logs`, `🤖 | role-logs`, `🤖 | stage-logs`, `🤖 | server-logs`, `🤖 | sticker-logs`, `🤖 | soundboard-logs`, `🤖 | thread-logs`, `🤖 | user-logs`, `🤖 | voice-logs`, `🤖 | webhook-logs`, and `🤖 | moderation-logs`.

## Dashboard

YALC registers a standalone Red-Web-Dashboard third-party page when the AAA3A `Dashboard` cog is loaded. The page appears under the guild dashboard's Third Parties tab for users with Manage Server, Red admin, or bot owner access.

The dashboard controls core behavior and privacy, explicit fallback delivery, command-log policy, local journal retention/content policy, every event toggle, every event channel, every event color, broad ignore filters, precise ignore rules, audit readiness, journal statistics, and test deliveries. One-click controls enable or disable every event, while smart routing previews the best matching existing `log`, `logs`, or `logging` channel for each unset route and can apply those suggestions without overwriting configured routes. It does not use the repository's reusable dashboard form component.

## Audit Attribution and Coverage

Give the bot `View Audit Log` to attribute moderation and administrative actions. YALC first consumes Discord's live audit-entry gateway event, deduplicates entries by audit ID, then performs a short bounded lookup when a gateway event needs attribution. A match must have the expected action and, where Discord supplies them, the exact target and channel. If YALC cannot establish that match, it reports attribution as unavailable instead of guessing.

Enable the Guild Moderation intent for the live audit-entry stream, bans, and related moderation events. Enable Message Content if deleted or edited text should be available while Discord still has the message cached. Uncached gateway events contain IDs and any partial data Discord supplied, but cannot recover content Discord did not send.

## Optional Event Journal

The local journal is disabled by default. When enabled, it records delivered-event metadata in YALC's cog data directory only. Message content remains excluded unless `Include message content in journal` is explicitly enabled in the dashboard. Retention is enforced automatically each day and can also be applied immediately. Administrators can search, export, prune, or permanently clear the journal with the commands above.

## Requirements

- Red-DiscordBot 3.5.0 or newer.
- Python 3.10 or newer.
- `Send Messages`, `Embed Links`, and permission to view the events being logged.
- `View Audit Log` for moderator, reason, and audit-only event attribution.
- Manage Server permission, Red admin, or equivalent for configuration commands.
- Guild Moderation intent is required for the live audit stream and moderation coverage.
- Server Members intent is recommended for member update logging.
- Message Content intent is required when message text should be logged.

## Data and Privacy

YALC stores guild-specific routes, enabled events, colors, filters, ignore rules, and limited voice-session state. Ignore rules may contain Discord user IDs. If the optional journal is enabled, YALC also stores delivered-event metadata such as actor/target IDs, channel IDs, timestamps, summaries, confidence, and audit IDs for the configured retention period. Message text is opt-in and off by default. Red data-deletion requests remove stored references to that user.
