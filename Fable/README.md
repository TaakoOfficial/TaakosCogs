# Fable

Living world and character tracker for roleplay-focused Red-DiscordBot servers.

[Back to the cog catalog](../README.md)

## Install

```text
[p]repo add TaakosCogs https://github.com/TaakoOfficial/TaakosCogs
[p]cog install TaakosCogs Fable
[p]load Fable
```

## Highlights

- Character profiles with rich fields and genre templates.
- Character milestones, development timelines, and story arcs.
- Relationship tracking with history and visual graphs.
- Location creation, visits, connections, and maps.
- In-character event logging.
- Optional Google Sheets/Docs sync and export workflows.

## Command Areas

| Area | Example Commands |
| --- | --- |
| Characters | `[p]fable character quickstart`, `[p]fable character view`, `[p]fable character edit`, `[p]fable character timeline` |
| Relationships | `[p]fable relationship set`, `[p]fable relationship view`, `[p]fable relations`, `[p]fable visualize relationships` |
| Events | `[p]fable event log`, `[p]fable event edit`, `[p]fable event delete` |
| Milestones | `[p]fable milestone add`, `[p]fable milestone list`, `[p]fable milestone categories` |
| Locations | `[p]fable location create`, `[p]fable location visit`, `[p]fable location connect`, `[p]fable location info` |
| Visuals | `[p]fable visualize relationships`, `[p]fable visualize locations` |
| Sync | `[p]fable sysetup`, `[p]fable syexport`, `[p]fable syimport`, `[p]fable systatus` |

## Quick Start

```text
[p]fable character quickstart "Aria" fantasy
[p]fable relationship set "Aria" "Bram" rival 4 "Stolen artifact dispute"
[p]fable location create "Silverwood" forest "Ancient magical forest"
[p]fable milestone add "Aria" "Personal Growth" "Mastered ancient magic"
```

## Requirements

- Red-DiscordBot 3.5.0 or newer.
- `Send Messages` and `Embed Links`.
- Additional permissions may be needed for admin settings and export workflows.
- Google API setup is optional and only needed for sync/export features.

## Data

Fable stores character profiles, relationships, locations, events, story arcs, settings, and optional sync configuration as configured by users. Data is not shared externally unless an explicit export or sync workflow is configured.
