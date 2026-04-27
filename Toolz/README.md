# Toolz

Toolz is a Red DiscordBot cog with role and user utility commands for servers that have many users and roles.

All commands are hybrid commands. After Red syncs slash commands, each command works as both a normal prefix command and a slash command, such as `[p]roleinfo` and `/roleinfo`.

## Commands

| Command | Description |
| --- | --- |
| `[p]memberinfo [member]` or `/memberinfo` | Show a polished member info embed with copy-friendly user ID, account age, join date, top role, role count, and elevated permission summary. |
| `[p]userroles [member] [limit]` or `/userroles` | List a member's roles with role IDs for quick audits. |
| `[p]userpermissions [member]` or `/userpermissions` | Show a member's important server permissions and the roles that provide them. |
| `[p]roleinfo <role>` or `/roleinfo` | Show a polished role info embed with member count, color, permissions, hierarchy details, and mobile-copyable role ID text. |
| `[p]rolecheck <member> <role>` or `/rolecheck` | Check whether a member has a specific role. |
| `[p]rolecompare <role_one> <role_two> [limit]` or `/rolecompare` | Compare two roles and show overlap, only-in-first, and only-in-second member previews. |
| `[p]roleaudit [mode] [limit]` or `/roleaudit` | Audit roles by `elevated`, `empty`, `managed`, or `mentionable`. Requires Manage Roles or Red admin permission. |
| `[p]rolehierarchy [limit] [include_empty]` or `/rolehierarchy` | Show roles in hierarchy order with position, member count, and copy-friendly IDs. |
| `[p]rolesearch <query>` or `/rolesearch` | Search roles by name or ID and show matching role IDs and member counts. |
| `[p]rolelist [sort] [limit]` or `/rolelist` | List server roles sorted by `members`, `position`, `name`, or `color`. |
| `[p]rolemembers <role> [limit]` or `/rolemembers` | Preview members who have a role. |
| `[p]roleexport <role>` or `/roleexport` | Export role members to a CSV file. Requires Manage Roles or Red admin permission. |
| `[p]noroles [limit] [include_bots]` or `/noroles` | List members with no roles except `@everyone`. Requires Manage Roles or Red admin permission. |
| `[p]bots [limit]` or `/bots` | List bot accounts, top roles, and whether they have elevated permissions. Requires Manage Roles or Red admin permission. |
| `[p]rolemessage` or `/rolemessage` | Manage messages posted when a configured role is given to a member. Requires Manage Roles or Red admin permission. |

For the easiest mobile and desktop copying, `roleinfo` sends role ID and mention string as inline backtick text above the embed.

## Role Messages

Role messages post automatically when a configured role is newly added to a member.

| Command | Description |
| --- | --- |
| `[p]rolemessage setup` | Show setup steps, examples, placeholders, and notes. |
| `[p]rolemessage channel <role> <channel>` | Set where messages for a role should post. |
| `[p]rolemessage add <role> <message>` | Add a message template for a role. Up to 10 templates can be stored per role. |
| `[p]rolemessage remove <role> <index>` | Remove one template by its list number. |
| `[p]rolemessage clear <role>` | Remove all settings for a role. |
| `[p]rolemessage toggle <role> [enabled]` | Enable, disable, or toggle a role's messages. |
| `[p]rolemessage list [role]` | Show all configured roles or detailed settings for one role. |
| `[p]rolemessage test <role> [member]` | Preview the rendered templates. |
| `[p]rolemessage placeholders` | Show available placeholders. |

Useful placeholders include `{user}`, `{display_name}`, `{username}`, `{user_id}`, `{role}`, `{role_name}`, `{role_id}`, `{server}`, and `{server_id}`.

Example:

```text
[p]rolemessage channel @Verified #welcome
[p]rolemessage add @Verified Welcome {user}, you now have {role} in {server}!
```
