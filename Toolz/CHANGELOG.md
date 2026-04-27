# Changelog

## 0.4.3

- Added `rolemessage mode <role> all|random`.
- Role messages now support posting all configured messages or one random configured message.

## 0.4.2

- Added `rolemessage setup` with setup steps, examples, placeholders, and notes.

## 0.4.1

- Changed `roleinfo` copy values from code blocks to inline backtick text for easier mobile copying.

## 0.4.0

- Added role-triggered messages with the `rolemessage` command group.
- Added persistent per-guild settings for role message channels, templates, and enabled status.
- Added template placeholders including `{user}`, `{role}`, `{display_name}`, and `{server}`.
- Added automatic posting when a configured role is newly given to a member.

## 0.3.2

- Moved `roleinfo` copy values into normal message text for better mobile copying.
- Removed the member preview section from `roleinfo`.

## 0.3.1

- Renamed `userinfo` to `memberinfo` to avoid conflicts with existing cogs.
- Replaced common aliases `uinfo` and `whois` with `minfo` and `memberlookup`.

## 0.3.0

- Added `rolecompare` for role overlap checks.
- Added `userpermissions` for effective permission source audits.
- Added `noroles` for finding members with no assigned roles.
- Added `bots` for auditing bot accounts and elevated access.
- Added `rolehierarchy` for hierarchy-ordered role review.

## 0.2.0

- Added `memberinfo` for polished member info embeds.
- Added `userroles` for member role audits.
- Added `rolecheck` to check if a member has a role.
- Added `roleaudit` for elevated, empty, managed, and mentionable role audits.
- Documented that all commands are hybrid prefix and slash commands.

## 0.1.0

- Added role info embeds with copy-friendly role IDs.
- Added role search, role list, role member preview, and CSV export commands.
