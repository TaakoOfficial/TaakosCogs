# Toolz

Role and user utility tools for larger Red-DiscordBot servers.

[Back to the cog catalog](../README.md)

## Install

```text
[p]repo add TaakosCogs https://github.com/TaakoOfficial/TaakosCogs
[p]cog install TaakosCogs Toolz
[p]load Toolz
```

All public commands are hybrid commands. After Red syncs application commands, they work as both prefix commands and slash commands.

## Highlights

- Role and member info embeds with mobile-friendly copy text.
- Role search, hierarchy, member counts, exports, and audits.
- Member role and permission inspection.
- Bot, empty-role, no-role, and elevated-permission review tools.
- Role-triggered messages with placeholders like `{user}`, `{role}`, and `{server}`.

## Commands

| Command | Description |
| --- | --- |
| `[p]memberinfo [member]` or `/memberinfo` | Show account age, join date, roles, and elevated permission summary. |
| `[p]userroles [member] [limit]` or `/userroles` | List a member's roles with role IDs. |
| `[p]userpermissions [member]` or `/userpermissions` | Show a member's important server permissions and source roles. |
| `[p]roleinfo <role>` or `/roleinfo` | Show role information with mobile-copyable role ID and mention text. |
| `[p]rolecheck <member> <role>` or `/rolecheck` | Check whether a member has a role. |
| `[p]rolecompare <role_one> <role_two> [limit]` or `/rolecompare` | Compare role overlap and member differences. |
| `[p]roleaudit [mode] [limit]` or `/roleaudit` | Audit `elevated`, `empty`, `managed`, or `mentionable` roles. |
| `[p]rolehierarchy [limit] [include_empty]` or `/rolehierarchy` | Show roles in hierarchy order with IDs and member counts. |
| `[p]rolesearch <query>` or `/rolesearch` | Search roles by name or ID. |
| `[p]rolelist [sort] [limit]` or `/rolelist` | List roles sorted by `members`, `position`, `name`, or `color`. |
| `[p]rolemembers <role> [limit]` or `/rolemembers` | Preview members with a role. |
| `[p]roleexport <role>` or `/roleexport` | Export cached role members to CSV. |
| `[p]noroles [limit] [include_bots]` or `/noroles` | List members with no roles except `@everyone`. |
| `[p]bots [limit]` or `/bots` | List bot accounts and elevated access status. |

## Role Messages

Role messages post automatically when a configured role is newly added to a member.

| Command | Description |
| --- | --- |
| `[p]rolemessage setup` | Show setup steps, examples, placeholders, and notes. |
| `[p]rolemessage channel <role> <channel>` | Set where messages for a role should post. |
| `[p]rolemessage add <role> <message>` | Add a message template. Up to 10 templates can be stored per role. |
| `[p]rolemessage mode <role> <all_or_random>` | Post every configured message or pick one random message. |
| `[p]rolemessage toggle <role> [enabled]` | Enable, disable, or toggle messages for a role. |
| `[p]rolemessage list [role]` | Show all configured roles or one role's settings. |
| `[p]rolemessage test <role> [member]` | Preview rendered templates. |
| `[p]rolemessage remove <role> <index>` | Remove one message by list number. |
| `[p]rolemessage clear <role>` | Remove all settings for a role. |
| `[p]rolemessage placeholders` | Show available placeholders. |

Example:

```text
[p]rolemessage channel @Verified #welcome
[p]rolemessage add @Verified Welcome {user}, you now have {role} in {server}!
[p]rolemessage mode @Verified random
```

## Requirements

- Red-DiscordBot 3.5.0 or newer.
- `Embed Links` for rich command output.
- `Attach Files` for CSV exports.
- `Manage Roles` or Red admin permission for admin-only audits and role-message settings.
- Server Members intent for automatic role-message triggers and the most accurate member cache.

## Data

Toolz stores per-guild role-message settings, including role IDs, channel IDs, enabled status, mode, and message templates. CSV exports are generated on demand and are not saved locally.
