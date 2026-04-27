# Taako's Cogs

A growing collection of cogs for [Red-DiscordBot](https://github.com/Cog-Creators/Red-DiscordBot), focused on practical server tools, roleplay immersion, community events, and admin workflows.

This repo includes everything from role/user audits and logging to RP world tracking, weather simulation, giveaways, welcome automation, emoji migration, party games, and WHMCS support tooling.

## Quick Install

Run these commands in Discord with your Red bot prefix:

```text
[p]load downloader
[p]repo add TaakosCogs https://github.com/TaakoOfficial/TaakosCogs
[p]cog install TaakosCogs <CogName>
[p]load <CogName>
```

Example:

```text
[p]cog install TaakosCogs Toolz
[p]load Toolz
```

To update installed cogs:

```text
[p]cog update
```

## Cog Catalog

| Cog | Best For | Highlights |
| --- | --- | --- |
| [Toolz](./Toolz) | Role and user utilities | Role/user info, role audits, role comparison, CSV exports, bot/no-role audits, role-triggered messages with `{user}` placeholders. |
| [YALC](./YALC) | Server logging | Message/member/channel/role logging, event filters, retention settings, ignore lists, Tupperbox/PluralKit-aware filtering. |
| [Welcome](./Welcome) | Join messages | Configurable welcome messages, placeholders, JSON embeds, and cached welcome images. |
| [Giveaway](./Giveaway) | Community events | Timed giveaways, reaction entry, rerolls, cancellation, attached giveaways, prefix and slash command support. |
| [EmojiPorter](./EmojiPorter) | Server migration | Copy emojis and stickers between servers, list emoji/sticker inventory, skip duplicates automatically. |
| [ZodiacColorRoles](./ZodiacColorRoles) | Role setup | Bulk-create zodiac, color, pronoun, and ping preference roles with hybrid command support. |
| [RandomWeather](./RandomWeather) | RP atmosphere | Seasonal weather simulation, extreme weather events, automatic updates, role notifications, timezone-aware generation. |
| [RPCalander](./RPCalander) | RP timekeeping | Daily RP calendar posts, custom timelines, moon phases, blood moon events, separate moon channels. |
| [Fable](./Fable) | RP worldbuilding | Character profiles, relationships, locations, timelines, visualizations, lore tracking, export tools. |
| [Paranoia](./Paranoia) | Social games | Discord version of Paranoia with secret DM questions, custom questions, status tracking, and Tupperbox support. |
| [Flipper](./Flipper) | Simple fun | Lightweight coin flip command with embeds. |
| [WHMCS](./WHMCS) | Hosting/business support | WHMCS clients, billing, support tickets, role permissions, API configuration, and Discord ticket channels. |

## Recommended Sets

### Staff and Server Management

Install these if you want better moderation visibility and role operations:

```text
[p]cog install TaakosCogs Toolz YALC Welcome Giveaway
```

- `Toolz` gives staff role/user lookup, audit, export, and role-triggered message tools.
- `YALC` gives detailed server logging.
- `Welcome` handles onboarding messages.
- `Giveaway` supports events and community rewards.

### Roleplay Servers

Install these for immersive RP communities:

```text
[p]cog install TaakosCogs Fable RandomWeather RPCalander Paranoia
```

- `Fable` tracks characters, relationships, locations, and lore.
- `RandomWeather` adds seasonal weather and extreme events.
- `RPCalander` keeps your in-world calendar and moons moving.
- `Paranoia` gives players an easy social game between scenes.

### Server Setup and Migration

Install these when building or moving a server:

```text
[p]cog install TaakosCogs EmojiPorter ZodiacColorRoles Toolz
```

- `EmojiPorter` copies emojis and stickers from another server the bot can access.
- `ZodiacColorRoles` creates common self-role sets quickly.
- `Toolz` helps audit role counts, hierarchy, empty roles, bots, and permissions.

### Hosting and Support Teams

Install this if your Discord supports a WHMCS-powered hosting or billing operation:

```text
[p]cog install TaakosCogs WHMCS
```

`WHMCS` connects Discord staff workflows to clients, invoices, support tickets, and optional per-ticket Discord channels.

## Featured Cog: Toolz

`Toolz` is the general-purpose staff utility cog for larger servers.

Key commands:

| Command | Purpose |
| --- | --- |
| `[p]roleinfo <role>` or `/roleinfo` | Show role info with mobile-copyable role ID and mention text. |
| `[p]memberinfo [member]` or `/memberinfo` | Show user/member details, join date, roles, and elevated permission summary. |
| `[p]rolecompare <role_a> <role_b>` | Compare role overlap and member differences. |
| `[p]roleaudit [mode]` | Audit elevated, empty, managed, or mentionable roles. |
| `[p]rolehierarchy` | Review role order, counts, and IDs. |
| `[p]rolemessage setup` | Show setup help for messages posted when a role is given. |

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

| Cog | Requirements |
| --- | --- |
| RandomWeather | `pytz` |
| RPCalander | `pytz` |
| Welcome | `aiohttp` |
| EmojiPorter | `aiohttp` |
| WHMCS | `aiohttp>=3.8.0` |

Some features also need Discord privileged intents:

- Role-triggered messages in `Toolz` need Server Members intent.
- Member logging and member update features in logging cogs may also need Server Members intent.

## Data and Privacy

Each cog includes its own data statement in `info.json`. In short:

- `Flipper`, `RandomWeather`, `EmojiPorter`, and `ZodiacColorRoles` do not persistently store end user data.
- `Toolz` stores per-guild role-message settings such as role IDs, channel IDs, and message templates.
- `YALC`, `Welcome`, `Giveaway`, `Fable`, `Paranoia`, `RPCalander`, and `WHMCS` store the settings or records needed for their features.
- `RPCalander` also uses a local `post_tracker.json` file to prevent duplicate daily posts.

No cog is intended to share stored data with external services unless the feature explicitly requires an external integration, such as WHMCS API access or optional Fable export workflows.

## Support and Docs

Start with each cog's README:

- [Toolz README](./Toolz/README.md)
- [YALC README](./YALC/README.md)
- [Welcome README](./Welcome/README.md)
- [Giveaway README](./Giveaway/README.md)
- [EmojiPorter README](./EmojiPorter/README.md)
- [ZodiacColorRoles README](./ZodiacColorRoles/README.md)
- [RandomWeather README](./RandomWeather/README.md)
- [RPCalander README](./RPCalander/README.md)
- [Fable README](./Fable/README.md)
- [Paranoia README](./Paranoia/README.md)
- [Flipper README](./Flipper/README.md)
- [WHMCS README](./WHMCS/README.md)

For command help inside Discord, use:

```text
[p]help <CogName>
```

## License

This repository is licensed under the GNU AGPLv3 unless an individual cog states otherwise. See [LICENSE](./LICENSE) for details.
