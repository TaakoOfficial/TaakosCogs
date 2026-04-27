# RPCalander

Roleplay calendar, moon phase, and celestial event tracking for Red-DiscordBot.

[Back to the cog catalog](../README.md)

## Install

```text
[p]repo add TaakosCogs https://github.com/TaakoOfficial/TaakosCogs
[p]cog install TaakosCogs RPCalander
[p]load RPCalander
```

## Highlights

- Daily in-world calendar updates.
- Custom starting date and current RP date controls.
- Timezone-aware posting.
- Custom embed title, color, and footer controls.
- Moon phase tracking based on the RP calendar.
- Optional blood moon events and separate moon update channels.
- Prefix command group and slash-command support.

## Commands

| Command | Description |
| --- | --- |
| `[p]rpca` | Show base command help. |
| `[p]rpca info` | Show current calendar settings. |
| `[p]rpca force` | Force a calendar update post. |
| `[p]rpca setdate <month> <day> <year>` | Set the current RP date. |
| `[p]rpca settitle <title>` | Set the calendar embed title. |
| `[p]rpca setcolor <color>` | Set embed color. |
| `[p]rpca settimezone <timezone>` | Set posting timezone. |
| `[p]rpca setchannel <channel>` | Set calendar update channel. |
| `[p]rpca togglefooter` | Toggle embed footer. |
| `[p]rpca moonphase` | Show current moon phase. |
| `[p]rpca forcemoonupdate` | Force a moon phase update. |
| `[p]rpca moonconfig enable` | Enable moon phase tracking. |
| `[p]rpca moonconfig disable` | Disable moon phase tracking. |
| `[p]rpca moonconfig bloodmoon` | Toggle blood moon events. |
| `[p]rpca moonconfig setchannel <channel>` | Set moon phase channel. |
| `[p]rpca resetbloodmoon` | Disable current blood moon mode. |

Slash command equivalents are available for the same core calendar actions.

## Requirements

- Red-DiscordBot 3.5.0 or newer.
- `pytz`.
- `Send Messages` and `Embed Links` in configured channels.
- Administrator or equivalent permission for configuration commands.

## Data

RPCalander stores server calendar settings and uses `post_tracker.json` to prevent duplicate daily posts. It does not persistently store or share end user data.
