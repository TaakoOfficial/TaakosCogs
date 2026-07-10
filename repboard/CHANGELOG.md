# Changelog

## Unreleased

- Added standalone Red-Web-Dashboard integration for viewing visible commands and current server configuration.


## 1.1.1

- Renamed the repository package folder from `RepBoard` to `repboard` to match Red cog naming standards.
- New installs should use `[p]cog install taakoscogs repboard` and `[p]load repboard`.
- Existing reputation settings and records are preserved because the cog's Config identifier did not change.

## 1.1.0

- Added native `/repboard` subcommands for all reputation management commands.

## 1.0.0

- Initial RepBoard cog.
- Added reputation giving, public rep board posts, logs, profile cards, leaderboards, history, moderation removal, setup walkthrough, configurable cooldowns/daily limits, reason settings, and CSV exports.
