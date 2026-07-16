# rolemanager

Combined role management tools for Red-DiscordBot.

[Back to the cog catalog](../README.md)

## Install

```text
[p]repo add taakoscogs https://github.com/TaakoOfficial/TaakosCogs
[p]cog install taakoscogs rolemanager
[p]load rolemanager
```

## Highlights

- Member self roles with separate self-add and self-remove settings.
- Role policies: required roles, inclusive roles, exclusive roles, credit costs, and atomic assignment mode.
- Role-change rules that react to roles added or removed manually, by another cog, or by RoleManager.
- Reaction roles that can be attached to existing messages or generated as a panel.
- Persistent button roles and select-menu roles.
- Autoroles for all new members, humans only, or bots only.
- Sticky roles that are restored when a member rejoins.
- Temporary roles with explicit durations or a per-role default duration.
- Bulk role add/remove tools for members, roles, channels, humans, bots, online members, or everyone.
- Dry-run previews, cleanup commands, and RoleTools/RoleUtils import helpers.
- Existing RoleTools/RoleUtils reaction-role messages remain usable after import; RoleManager repairs legacy emoji keys and handles their reactions directly.
- Full Red-Web-Dashboard support for policies, role rules, role/member operations, autoroles, sticky and temporary roles, reaction roles, components, cleanup, and imports.

## Commands

| Command | Description |
| ------- | ----------- |
| `[p]rolemanager selfrole <role>` | Toggle a configured self role for yourself. |
| `[p]rolemanager selfrole allow <role> [removable]` | Make a role self-assignable. |
| `[p]rolemanager selfrole deny <role>` | Remove a role from self-role availability. |
| `[p]rolemanager selfrole list` | List configured self roles. |
| `[p]rolemanager required add <role> <required_roles...>` | Require prerequisite roles before a role can be assigned. |
| `[p]rolemanager required any <role> <true|false>` | Require any prerequisite role instead of all prerequisite roles. |
| `[p]rolemanager include add <role> <roles...>` | Add roles automatically when the main role is assigned. |
| `[p]rolemanager exclude add <role> <roles...>` | Remove conflicting roles when the main role is assigned. |
| `[p]rolemanager rule set <name> <add|remove> <trigger_role> --add role,role --remove role,role` | Create or replace a rule that reacts to any matching role change. |
| `[p]rolemanager rule toggle <name> [true|false]` | Enable, disable, or toggle a role-change rule. |
| `[p]rolemanager rule delete <name>` | Delete a role-change rule. |
| `[p]rolemanager rule list` | List configured role-change rules. |
| `[p]rolemanager cost <amount> <role>` | Set a Red bank credit cost for a self-assigned role. |
| `[p]rolemanager atomic [true|false|clear]` | Configure guild atomic role assignment. |
| `[p]rolemanager role add <member> <role>` | Add a role to one member. |
| `[p]rolemanager role remove <member> <role>` | Remove a role from one member. |
| `[p]rolemanager role toggle <member> <role>` | Add or remove a role depending on current state. |
| `[p]rolemanager role addmulti <role> <members...>` | Add one role to multiple members. |
| `[p]rolemanager role multigive <member> <roles...>` | Add multiple roles to one member. |
| `[p]rolemanager role custom <members...> --add role,role --remove role,role` | Add and remove role sets in one command. |
| `[p]rolemanager role uniquemembers <roles...>` | Count unique members across multiple roles. |
| `[p]rolemanager role create <name>` | Create a role. |
| `[p]rolemanager role name <role> <new_name>` | Rename a role. |
| `[p]rolemanager role color <role> <color>` | Change a role color. |
| `[p]rolemanager role hoist <role> [true|false]` | Toggle whether a role is shown separately. |
| `[p]rolemanager role mentionable <role> [true|false]` | Toggle whether a role can be mentioned by everyone. |
| `[p]rolemanager giverole <role> <targets...>` | Bulk-add a role. Targets can be members, roles, text channels, `everyone`, `here`, `humans`, or `bots`. |
| `[p]rolemanager removerole <role> <targets...>` | Bulk-remove a role from the same target types. |
| `[p]rolemanager dryrun add <role> <targets...>` | Preview a bulk add without changing roles. |
| `[p]rolemanager dryrun remove <role> <targets...>` | Preview a bulk removal without changing roles. |
| `[p]rolemanager autorole add <role> [all|humans|bots]` | Add an autorole target. |
| `[p]rolemanager autorole toggle [true|false]` | Enable, disable, or toggle autoroles. |
| `[p]rolemanager sticky set <role> [true|false]` | Mark a role as sticky for future rejoins. |
| `[p]rolemanager sticky add <member> <role>` | Force a sticky role onto one member. |
| `[p]rolemanager temp give <member> <role> <duration>` | Give a temporary role. |
| `[p]rolemanager temp setduration <role> [duration]` | Set or clear a default temp duration for assignments made by this cog. |
| `[p]rolemanager temp list [member]` | List pending temporary roles. |
| `[p]rolemanager reactrole bind <message> <emoji> <role> [remove_on_unreact]` | Bind an emoji on an existing message. |
| `[p]rolemanager reactrole create [channel] <title> | <emoji>;<role> | ...` | Create a reaction-role panel. |
| `[p]rolemanager reactrole unbind <message> <emoji>` | Remove one emoji binding. |
| `[p]rolemanager reactrole clear <message>` | Remove all bindings for a message. |
| `[p]rolemanager reactrole cleanup` | Remove stale reaction-role records. |
| `[p]rolemanager reactrole list` | List configured reaction roles. |
| `[p]rolemanager button create <name> <role> [style] [emoji] [label]` | Save a persistent role button. |
| `[p]rolemanager select option create <name> <role> [emoji | label | description]` | Save a select-menu option. |
| `[p]rolemanager select create <name> <options_csv> [min] [max] [placeholder]` | Save a select menu. |
| `[p]rolemanager message send <channel> <buttons_csv> [selects_csv] [text]` | Send a component role panel. |
| `[p]rolemanager import roletools` | Import compatible settings from TrustyJAID RoleTools config. |
| `[p]rolemanager import roleutils` | Import compatible settings from Seina RoleUtils config. |

Duration examples: `30m`, `2 hours`, `7d`, `1 week 2 days`.

Reaction panel example:

```text
[p]rolemanager reactrole create #roles Pick your pings | <:game:123456789012345678>;Gamer | <:news:123456789012345679>;Announcements
```

Role-change rule example:

```text
[p]rolemanager rule set verified add @Verified --add Member --remove Unverified
```

Existing required, inclusive, and exclusive policies are also enforced when a role is changed manually or by another cog. Removing a role externally removes its configured inclusive roles. RoleManager skips automatic actions it cannot perform because of Discord role hierarchy or managed-role restrictions.

## Dashboard

The Red-Web-Dashboard page is organized into responsive tabs for overview, role setup, member operations, role panels, and data/imports. It supports guild atomic settings, role creation and editing, a complete policy overview, mutual include/exclude links, role-change rule creation and editing, autoroles, single-member and bulk role operations with dry-run previews, member sticky roles, temporary-role grants, reaction panel creation and maintenance, persistent component creation/editing/cleanup, and RoleTools/RoleUtils imports.

Live dashboard role operations require the confirmation checkbox. Imports also require explicit confirmation because compatible destination settings may be replaced.

## Requirements

- Red-DiscordBot 3.5.0 or newer.
- The bot needs `Manage Roles` and its top role must be above any managed role.
- Reaction-role setup also needs `Add Reactions`, `Read Message History`, and access to the target channel.
- Server Members intent is required for external role-change rules and recommended for autoroles, sticky roles, and accurate bulk targeting.

## Data

This cog stores role IDs, channel/message IDs, emoji keys, role-policy and role-change-rule settings, role costs, component definitions, temporary-role expiry timestamps, and Discord user IDs for sticky and temporary role assignment. It does not store message content except optional component panel text sent directly to Discord.
