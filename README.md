# Taako's Cogs

A growing collection of cogs for [Red-DiscordBot](https://github.com/Cog-Creators/Red-DiscordBot), focused on practical server tools, roleplay immersion, community feedback, reputation, support tickets, events, invite tracking, and admin workflows.

This repo includes everything from role/user audits, invite tracking, suggestions, reputation, tickets, and logging to RP world tracking, Cfx.re service checks, weather simulation, giveaways, welcome automation, emoji migration, party games, and WHMCS support tooling.

## Quick Install

Run these commands in Discord with your Red bot prefix:

```text
[p]load downloader
[p]repo add taakoscogs https://github.com/TaakoOfficial/TaakosCogs
[p]cog install taakoscogs <cogname>
[p]load <cogname>
```

Example:

```text
[p]cog install taakoscogs toolz
[p]load toolz
```

To update installed cogs:

```text
[p]cog update
```

## Dashboard Support

Every configurable cog includes its own purpose-built Red-Web-Dashboard page with labeled fields, Discord channel and role selectors, validation, and cog-specific actions. Stateless utilities use focused operation or live-status pages instead of showing an empty settings editor. No cog relies on the generic JSON configuration fallback.

## Cog Catalog

| Cog                                    | Best For                 | Highlights                                                                                                                                  |
| -------------------------------------- | ------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------- |
| [messagestudio](./messagestudio)         | Rich message building   | EmbedUtils-compatible commands, embeds and Components V2, stored messages, webhooks, JSON/YAML, and a standalone visual dashboard builder. |
| [toolz](./toolz)                       | Role and user utilities  | Role/user info, role audits, role comparison, CSV exports, bot/no-role audits, role-triggered messages with `{user}` placeholders.          |
| [rolemanager](./rolemanager)           | Role management          | Self roles, external role-change rules, policies, role panels, autoroles, sticky/temp roles, dashboard operations, imports, and bulk tools. |
| [yalc](./yalc)                         | Server logging           | Strict audit attribution, raw message coverage, complete event routing, fail-closed delivery, advanced filters, and an optional journal.   |
| [applications](./applications)         | Staff applications       | Configurable forms, application panels, DM questionnaires, review buttons, role actions, CSV exports, polls, and dashboard setup.            |
| [welcome](./welcome)                   | Join messages            | Configurable welcome messages, placeholders, JSON embeds, cached welcome images, avatar overlays, and dashboard setup.                       |
| [captcha](./captcha)                   | Member verification      | Persistent verification buttons, per-click random modal codes, existing-message attachment, configurable success roles, and dashboard setup. |
| [invitetracker](./invitetracker)       | Invite tracking          | Invite-use detection, join sources, fake joins, leaver counts, leaderboards, log embeds, CSV exports, and dashboard controls.               |
| [suggestionbox](./suggestionbox)       | Community feedback       | Suggestions with persistent voting buttons, discussion threads, review states, comments, review logs, CSV exports, and dashboard controls.  |
| [repboard](./repboard)                 | Community reputation     | Member kudos, public rep board posts, cooldowns, daily limits, profiles, leaderboards, moderation removal, and CSV exports.                 |
| [reviewhub](./reviewhub)               | Reviews and vouches      | reviewhub-style reviews, vouches, review requests, stats, leaderboards, reports, useful votes, templates, and CSV exports.                  |
| [tickethub](./tickethub)               | Support tickets          | Ticket panels, private channels, claim/close controls, AAA3A Tickets profile imports, HTML transcripts, and owner transcript DMs.           |
| [slashlink](./slashlink)               | Prefix/slash compatibility | Red-managed application-command gateways for loaded prefix-only cogs, with permission-aware autocomplete and normal `[p]slash` controls. |
| [tempvoice](./tempvoice)               | Voice channel automation | Join-to-create temporary voice channels, embedded owner controls, rename/lock/limit/transfer buttons, claiming, cleanup, and dashboard setup. |
| [giveaway](./giveaway)                 | Community events         | Timed giveaways, reaction entry, rerolls, cancellation, attached giveaways, prefix/slash commands, and dashboard controls.                  |
| [uppercase](./uppercase)               | Channel setup            | Create and rename text channels with uppercase-style names using `/create-channel` and `/rename-channel`.                                  |
| [emojiporter](./emojiporter)           | Server migration         | Copy emojis and stickers between servers, list emoji/sticker inventory, skip duplicates automatically.                                      |
| [rolekit](./rolekit)                   | Community roles & levels | Curated identity/interest role packs, cooldown-limited activity XP, rank cards, leaderboards, milestone roles, and dashboard setup.         |
| [fivemstatus](./fivemstatus)           | FiveM communities        | Live server status panel with player counts, Join Server button, restart countdowns, uptime tracking, images, and link buttons.             |
| [cfxstatus](./cfxstatus)               | Cfx.re service checks    | Auto-updating panel that checks the official Cfx.re Statuspage API, with Rockstar's service-status page as a fallback.                     |
| [randomweather](./randomweather)       | RP atmosphere            | Seasonal weather simulation, extreme weather events, automatic updates, role notifications, timezone-aware generation.                      |
| [rpcalander](./rpcalander)             | RP timekeeping           | Daily RP calendar posts, custom timelines, moon phases, blood moon events, separate moon channels.                                          |
| [fable](./fable)                       | RP worldbuilding         | Character profiles, relationships, locations, timelines, visualizations, lore tracking, export tools.                                       |
| [paranoia](./paranoia)                 | Social games             | Discord version of paranoia with secret DM questions, custom questions, status tracking, and Tupperbox support.                             |
| [flipper](./flipper)                   | Simple fun               | Lightweight coin flip command with embeds.                                                                                                  |
| [whmcs](./whmcs)                       | Hosting/business support | WHMCS clients, billing, support tickets, role permissions, API configuration, and Discord ticket channels.                                  |

## Recommended Sets

### Staff and Server Management

Install these if you want better moderation visibility, invite attribution, feedback workflows, community reputation, support tickets, and role operations:

```text
[p]cog install taakoscogs toolz rolemanager yalc applications welcome captcha invitetracker suggestionbox repboard reviewhub tickethub tempvoice giveaway
```

- `toolz` gives staff role/user lookup, audit, export, and role-triggered message tools.
- `rolemanager` handles self roles, automatic role-change rules, role policies, reaction/button/select role panels, autoroles, sticky roles, temporary roles, dashboard operations, dry-runs, imports, and bulk role updates.
- `YALC` gives detailed server logging.
- `applications` handles staff applications, review workflows, and approval roles.
- `welcome` handles onboarding messages.
- `captcha` verifies new members with randomized modal codes and assigns a configured role.
- `invitetracker` tracks invite joins, fake joins, leavers, join sources, and leaderboards.
- `suggestionbox` collects community suggestions with voting, optional discussion threads, staff review states, comments, and exports.
- `repboard` gives members a lightweight kudos and reputation leaderboard system.
- `reviewhub` collects structured reviews and vouches with request buttons, reports, useful votes, stats, and leaderboards.
- `tickethub` handles support tickets with panels, private channels, staff controls, imports, and transcripts.
- `tempvoice` gives members self-managed temporary voice channels with embedded controls.
- `giveaway` supports events and community rewards.

### Roleplay Servers

Install these for immersive RP communities:

```text
[p]cog install taakoscogs fivemstatus cfxstatus fable randomweather rpcalander paranoia
```

- `fivemstatus` posts a live FiveM status panel with player counts, connect command, restarts, and buttons.
- `cfxstatus` posts an auto-updating panel for the official Cfx.re service status.
- `fable` tracks characters, relationships, locations, and lore.
- `randomweather` adds seasonal weather and extreme events.
- `rpcalander` keeps your in-world calendar and moons moving.
- `paranoia` gives players an easy social game between scenes.

### Server Setup and Migration

Install these when building or moving a server:

```text
[p]cog install taakoscogs emojiporter rolekit toolz rolemanager uppercase tempvoice
```

- `emojiporter` copies emojis and stickers from another server the bot can access.
- `rolekit` creates curated community role packs and can run lightweight activity ranks with automatic milestone roles.
- `toolz` helps audit role counts, hierarchy, empty roles, bots, and permissions.
- `rolemanager` turns those roles into self roles, reaction/button/select roles, autoroles, sticky roles, temporary roles, or policy-linked role sets.
- `uppercase` creates and renames text channels with uppercase-style names.
- `tempvoice` sets up join-to-create voice channels for member-managed voice spaces.

### Hosting and Support Teams

Install this if your Discord supports a WHMCS-powered hosting or billing operation:

```text
[p]cog install taakoscogs whmcs
```

`whmcs` connects Discord staff workflows to clients, invoices, support tickets, and optional per-ticket Discord channels.

## Featured Cog: toolz

`toolz` is the general-purpose staff utility cog for larger servers.

Key commands:

| Command                                   | Purpose                                                                      |
| ----------------------------------------- | ---------------------------------------------------------------------------- |
| `[p]roleinfo <role>` or `/roleinfo`       | Show role info with mobile-copyable role ID and mention text.                |
| `[p]memberinfo [member]` or `/memberinfo` | Show user/member details, join date, roles, and elevated permission summary. |
| `[p]rolecompare <role_a> <role_b>`        | Compare role overlap and member differences.                                 |
| `[p]roleaudit [mode]`                     | Audit elevated, empty, managed, or mentionable roles.                        |
| `[p]rolehierarchy`                        | Review role order, counts, and IDs.                                          |
| `[p]rolemessage setup`                    | Show setup help for messages posted when a role is given.                    |

Role message example:

```text
[p]rolemessage channel @Verified #welcome
[p]rolemessage add @Verified Welcome {user}, you now have {role} in {server}!
[p]rolemessage mode @Verified random
```

## Requirements

Most cogs require:

- Red-DiscordBot V3.
- Discord permissions appropriate to the cog, usually `Send Messages` and `Embed Links`.
- Extra permissions for specific features, such as `Manage Roles`, `Manage Channels`, `Manage Emojis and Stickers`, or `Attach Files`.

Some cogs have Python package requirements that Red's downloader installs automatically:

| Cog           | Requirements     |
| ------------- | ---------------- |
| messagestudio | `PyYAML>=6.0` and Red 3.5.21+ |
| randomweather | `pytz`           |
| rpcalander    | `pytz`           |
| welcome       | `aiohttp`        |
| emojiporter   | `aiohttp`        |
| fivemstatus   | `aiohttp`        |
| cfxstatus     | `aiohttp`        |
| whmcs         | `aiohttp>=3.8.0` |

Some features also need Discord privileged intents:

- Invite join and leave tracking in `invitetracker` needs Server Members intent.
- Role-triggered messages in `toolz` need Server Members intent.
- External role-change rules in `rolemanager` require Server Members intent; autoroles, sticky roles, and bulk member targeting also use it.
- Member logging and member update features in logging cogs may also need Server Members intent.
- Role assignment features in `applications` need Manage Roles and a bot role above the target roles.
- Captcha role assignment needs Manage Roles and a bot role above the verification role.
- Temporary voice creation in `tempvoice` needs Manage Channels and Move Members.

## Data and Privacy

Each cog includes its own data statement in `info.json`. In short:

- `flipper`, `randomweather`, `emojiporter`, `uppercase`, and `slashlink` do not persistently store end user data.
- `rolekit` stores per-server XP and counted-message totals when activity leveling is enabled; it never stores message content.
- `messagestudio` stores saved message payloads, author IDs, lock settings, and usage counts when its storage commands are used.
- `toolz` stores per-guild role-message settings such as role IDs, channel IDs, and message templates.
- `rolemanager` stores role configuration, role-policy and role-change-rule settings, role costs, reaction/button/select message/channel IDs, emoji keys, temporary-role expiry timestamps, and Discord user IDs for sticky and temporary role assignment.
- `captcha` stores panel message/channel IDs, role IDs, and button labels; verification challenges are transient in memory.
- `yalc` stores logging settings, routes, filters, ignore-rule user IDs, and limited voice history. Its optional retained event journal stores event metadata and only stores message content when explicitly enabled.
- `applications`, `welcome`, `invitetracker`, `suggestionbox`, `repboard`, `reviewhub`, `tickethub`, `tempvoice`, `giveaway`, `fivemstatus`, `fable`, `paranoia`, `rpcalander`, and `whmcs` store the settings or records needed for their features.
- `invitetracker` stores invite cache metadata, inviter stats, tracked member join-source records, Discord user IDs, invite codes, timestamps, fake-join flags, and unknown join counts.
- `suggestionbox` stores suggestion text, author IDs, voter IDs, staff reviewer IDs, message/channel/thread IDs, votes, statuses, staff notes, review reasons, and timestamps.
- `repboard` stores reputation settings, giver/receiver/moderator IDs, reasons, message/channel IDs, timestamps, active/removed state, cooldown metadata, daily limit metadata, and aggregate reputation statistics.
- `reviewhub` stores review settings, request records, review/vouch records, reviewer/reviewed/reporter/useful-voter/moderator IDs, review text, ratings, message/channel IDs, timestamps, and deletion metadata.
- `tickethub` stores ticket profiles, panel IDs, channel/category/role IDs, ticket records, owner/staff/participant IDs, reasons, timestamps, and lifecycle events. Transcripts are generated on demand from channel history.
- `tempvoice` stores temporary voice settings, active temporary channel IDs, owner IDs, permitted user IDs, control panel message/channel IDs, creation timestamps, lock state, and user limits.
- `cfxstatus` stores Cfx.re status panel settings, including enabled state, channel IDs, message IDs, polling interval, and last poll timestamp.
- `rpcalander` also uses a local `post_tracker.json` file to prevent duplicate daily posts.

No cog is intended to share stored data with external services unless the feature explicitly requires an external integration, such as WHMCS API access or optional fable export workflows.

## Support and Docs

Start with each cog's README:

- [toolz README](./toolz/README.md)
- [messagestudio README](./messagestudio/README.md)
- [rolemanager README](./rolemanager/README.md)
- [yalc README](./yalc/README.md)
- [applications README](./applications/README.md)
- [welcome README](./welcome/README.md)
- [captcha README](./captcha/README.md)
- [invitetracker README](./invitetracker/README.md)
- [suggestionbox README](./suggestionbox/README.md)
- [repboard README](./repboard/README.md)
- [reviewhub README](./reviewhub/README.md)
- [tickethub README](./tickethub/README.md)
- [slashlink README](./slashlink/README.md)
- [giveaway README](./giveaway/README.md)
- [uppercase README](./uppercase/README.md)
- [emojiporter README](./emojiporter/README.md)
- [rolekit README](./rolekit/README.md)
- [fivemstatus README](./fivemstatus/README.md)
- [cfxstatus README](./cfxstatus/README.md)
- [randomweather README](./randomweather/README.md)
- [rpcalander README](./rpcalander/README.md)
- [fable README](./fable/README.md)
- [paranoia README](./paranoia/README.md)
- [flipper README](./flipper/README.md)
- [whmcs README](./whmcs/README.md)

For command help inside Discord, use:

```text
[p]help <cogname>
```

## Contributing

Before opening a pull request, run [Ruff](https://docs.astral.sh/ruff/) to lint and format your changes:

```bash
ruff check --fix .
ruff format .
```

If you have [pre-commit](https://pre-commit.com/) installed, you can also just run:

```bash
pre-commit install
```

once, and it will run these checks automatically on every commit.

## License

This repository is licensed under the GNU AGPLv3 unless an individual cog states otherwise. See [LICENSE](./LICENSE) for details.
