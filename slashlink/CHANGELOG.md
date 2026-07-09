# Changelog

## 1.0.1

- Renamed the repository package folder from `SlashLink` to `slashlink` to match Red cog naming standards.
- New installs should use `[p]cog install taakoscogs slashlink` and `[p]load slashlink`.
- Existing SlashLink settings are preserved because the cog's Config identifier did not change.

## 1.0.0

- Added one generated application-command gateway for each loaded prefix-only cog.
- Integrated generated commands with Red's built-in slash list, enablecog, disablecog, and sync workflow.
- Added permission-aware command autocomplete and original prefix-command invocation.
