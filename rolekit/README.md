# RoleKit

Curated community role packs plus optional, cooldown-limited activity leveling.

[Back to the cog catalog](../README.md)

## Install

```text
[p]repo add taakoscogs https://github.com/TaakoOfficial/TaakosCogs
[p]cog install taakoscogs rolekit
[p]load rolekit
```

Upgrading from the old cog name:

```text
[p]unload zodiaccolorroles
[p]cog uninstall zodiaccolorroles
[p]cog install taakoscogs rolekit
[p]load rolekit
```

RoleKit uses the legacy internal Config namespace, so existing leveling settings and XP records are retained.

## Dashboard

The purpose-built dashboard lets server managers create missing roles from any pack, enable and tune message XP, choose ignored and announcement channels, customize level-up messages, and map milestone levels to roles.

## Highlights

- Eight reusable packs: zodiac, colors, pronouns, notification preferences, gaming platforms, regions, interests, and level milestones.
- Cooldown-limited XP for real conversation; bot commands and ignored channels do not award XP.
- Automatic milestone roles with stacked or highest-only reward modes.
- Member rank cards and a top-ten server leaderboard.
- Dashboard controls for every leveling setting and reward mapping.
- Use `rolepack createall` to build every pack, or create only the packs that fit the server.
- Hybrid command support for prefix and slash usage.

## Commands

| Command                                                      | Description                                      |
| ------------------------------------------------------------ | ------------------------------------------------ |
| `[p]rolepack list`                                           | Show every curated role pack and its contents.   |
| `[p]rolepack create <pack>`                                  | Create the missing roles in one pack.             |
| `[p]rolepack createall`                                      | Create all available role packs.                  |
| `[p]addlevelrole <level>`                                    | Create and register a custom milestone role.      |
| `[p]rank [member]`                                           | Show activity XP, level, and progress.             |
| `[p]levelboard`                                              | Show the server's top ten activity ranks.          |
| `[p]leveling enable|disable`                                 | Turn message XP on or off without deleting ranks. |
| `[p]leveling xprange <minimum> <maximum>`                    | Configure XP earned per eligible message.         |
| `[p]leveling cooldown <seconds>`                             | Configure the per-member XP cooldown.              |
| `[p]leveling reward <level> <role>`                          | Map an existing role to a milestone.               |
| `[p]leveling removereward <level>`                           | Remove a milestone mapping without deleting it.   |
| `[p]leveling ignorechannel <channel>`                        | Toggle whether a channel awards XP.               |
| `[p]leveling sync [member]`                                  | Reapply the correct milestone roles.               |
| `[p]leveling reset <member>`                                 | Reset one member's XP and milestone roles.         |
| `[p]addzodiacrole <zodiac_or_all>`                           | Backward-compatible zodiac role creation.         |
| `[p]addcolorrole <color_or_all>`                             | Backward-compatible color role creation.          |
| `[p]addpronounrole <pronoun_or_all>`                         | Backward-compatible pronoun role creation.        |
| `[p]addcommonpingrole <role_or_all>`                         | Backward-compatible notification role creation.   |

## Requirements

- Red-DiscordBot 3.5.0 or newer.
- `Manage Roles`.
- The bot's top role must be above the roles it creates.
- The server must have room under Discord's role limit.
- Message Content intent is required for prefix commands and message-based XP.

## Data

When leveling is enabled, the cog stores each member's XP and counted-message total in that server. It never stores message content. Data is removed when a member leaves and is supported by Red's data-deletion API.
