# Changelog

## 0.4.0

- Added verified RoleTools/RoleUtils migrations with automatic pre-import backups, bounded backup history, health checks, JSON exports, rollback, and live reaction reconciliation in add-only or full-sync mode.
- Added button and select policies for toggle/add/remove/sync/exclusive behavior, required and blocked roles, per-member cooldowns, holder limits, temporary assignments, and concurrency locks.
- Added advanced `key=value` member targeting with status, role, channel, voice, thread, join-age, and account-age filters plus reusable target presets.
- Added persistent background bulk jobs with progress, cancellation, recent history, and JSON export.
- Added a bounded role-change audit journal with optional live channel delivery and dashboard controls.
- Added role reports, member/color exports, unused-role discovery, cloning, guarded deletion, hierarchy movement, individual permission editing, and role icons.
- Added restart-safe autorole queueing with independent all/human/bot lists, delivery delay, minimum account age, retry policy, and audit records.
- Added temporary-role reasons, grant metadata, optional expiry notifications, extension, immediate revocation, and expiry auditing.
- Added slash-command role pickers for self roles and role information.
- Expanded the standalone dashboard with every new policy and safety setting, target/job visibility, migration recovery tools, and audit controls.
- Retained backward-compatible toggle behavior for existing select menus while adding the new component policy modes.

## 0.3.2

- Reconnected existing imported reaction-role panels with explicit add/remove event listeners.
- Made saved dashboard/config records authoritative so a stale in-memory message cache can no longer block role updates.
- Added live repair when an older imported emoji binding is encountered during a reaction event.
- Matched Trusty RoleTools role assignment behavior for moderators whose staff role is above the bot while the assigned reaction role remains below it.
- Added per-binding dashboard readiness checks for the Reactions intent, channel access, Manage Roles permission, missing roles, and bot-role hierarchy.

## 0.3.1

- Fixed RoleTools/RoleUtils reaction-role imports so existing messages update members when they react or remove a reaction.
- Made a configured reaction binding authorize its own role assignment/removal instead of incorrectly requiring the separate self-role flags used by the `selfrole` command.
- Added automatic startup repair for previously imported emoji keys, including custom emoji IDs and Unicode variation selectors.
- Added an API member-fetch fallback for reaction removals when the member is not cached.

## 0.3.0

- Added persistent role-change rules with add/remove triggers and chained add/remove actions.
- Enforced required, inclusive, and exclusive policies when roles are changed manually or by another cog.
- Added dashboard controls for atomic settings, mutual policies, policy overview, role rules, role creation/editing, dry-run and live role operations, member sticky roles, temporary-role grants, reaction panel maintenance, component message editing/cleanup, and imports.
- Added prefilled editors for saved buttons, select options, and select menus.
- Reorganized the dashboard into responsive workflow tabs that remain selected after form submissions.
- Matched dashboard role-cost validation to command permissions and bank limits, and blocked conflicting inclusive/exclusive selections.

## 0.2.0

- Added role policy rules: required roles, inclusive roles, exclusive roles, credit costs, and atomic assignment settings.
- Added persistent button roles and select-menu roles with saved component messages.
- Added RoleTools-style aliases, dry-run previews, bulk multi-role/member commands, unique member counts, cleanup commands, and RoleTools/RoleUtils import helpers.
- Expanded Red-Web-Dashboard support to cover policy fields, button roles, select-menu roles, and component message creation.

## 0.1.0

- Added initial `rolemanager` cog.
- Added self roles, reaction roles, autoroles, sticky roles, temporary roles, and bulk role add/remove tools.
- Added Red-Web-Dashboard integration for role settings, autoroles, reaction roles, and temporary role tracking.
- Added README and Red cog metadata.
