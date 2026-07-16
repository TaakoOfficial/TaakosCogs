# Changelog

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
