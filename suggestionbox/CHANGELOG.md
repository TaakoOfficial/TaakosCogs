# Changelog

## 1.3.0 - 2026-07-16

- Reorganized the dashboard into responsive Suggestions, Settings, Actions, and Maintenance tabs that remain selected after form submissions.

## 1.2.1

- Renamed the repository package folder from `SuggestionBox` to `suggestionbox` to match Red cog naming standards.
- New installs should use `[p]cog install taakoscogs suggestionbox` and `[p]load suggestionbox`.
- Existing suggestion settings and records are preserved because the cog's Config identifier did not change.

## 1.2.0

- Added Red-Web-Dashboard third-party integration for SuggestionBox.
- Added dashboard controls for settings, manual suggestion submission, review statuses, staff comments, thread creation, deletion, message refresh, and record reset.

## 1.1.0

- Added native `/suggest`, `/suggestionbox`, and `/suggestions` commands.

## 1.0.0

- Initial SuggestionBox cog.
- Added suggestion submission, persistent button voting, anonymous display, staff statuses, staff comments, review logs, lists, stats, deletion, reset, and CSV export.
