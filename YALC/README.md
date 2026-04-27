# YALC

Yet Another Logging Cog: configurable server logging for Red-DiscordBot.

[Back to the cog catalog](../README.md)

## Install

```text
[p]repo add TaakosCogs https://github.com/TaakoOfficial/TaakosCogs
[p]cog install TaakosCogs YALC
[p]load YALC
```

## Highlights

- Logs message, member, channel, thread, role, guild, voice, emoji, and other server events.
- Configure one log channel or event-specific channels.
- Enable, disable, bulk enable, and bulk disable event types.
- Ignore/filter noisy users, channels, bots, webhooks, and proxy-style messages.
- Setup, validation, diagnostics, autodetect, and dashboard integration commands.

## Commands

| Command | Description |
| --- | --- |
| `[p]yalc` or `[p]logger` | Show the YALC command group help. |
| `[p]yalc setup` | Run the setup workflow. |
| `[p]yalc autodetect` | Try smart setup/autodetection. |
| `[p]yalc settings` | Show current logging settings. |
| `[p]yalc enable [event_type]` | Enable an event or list available event types. |
| `[p]yalc disable <event_type>` | Disable an event type. |
| `[p]yalc setchannel <event_type_or_all> [channel]` | Set where logs should post. |
| `[p]yalc bulk_enable` | Enable multiple event types. |
| `[p]yalc bulk_disable` | Disable multiple event types. |
| `[p]yalc validate` | Validate configuration and permissions. |
| `[p]yalc test` | Run diagnostics. Aliases: `diagnostics`, `debug`. |
| `[p]yalc reset` | Reset YALC settings for the server. |
| `[p]yalc dashboard` | Show dashboard integration details. |

## Requirements

- Red-DiscordBot 3.5.0 or newer.
- Python 3.9 or newer.
- `Send Messages`, `Embed Links`, and permission to view the events being logged.
- Manage Server permission, Red admin, or equivalent for configuration commands.
- Server Members intent is recommended for member update logging.

## Data

YALC stores guild-specific logging settings such as channels, enabled events, event filters, and ignore lists. It does not permanently store personal user data beyond configuration needed for logging behavior.
