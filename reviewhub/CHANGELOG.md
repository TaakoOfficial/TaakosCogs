# Changelog

## 1.2.0 - 2026-07-16

- Added standalone Red-Web-Dashboard integration for viewing visible commands and current server configuration.


## 1.1.1

- Renamed the repository package folder from `ReviewHub` to `reviewhub` to match Red cog naming standards.
- New installs should use `[p]cog install taakoscogs reviewhub` and `[p]load reviewhub`.
- Existing review settings and records are preserved because the cog's Config identifier did not change.

## 1.1.0

- Added a native 1–5 star dropdown to review submission modals.
- Retained the rating text input fallback for older Discord.py versions.

## 1.0.1

- Added an admin-controlled targeted review setting for regular reviews.
- Added a public submit-button target picker when targeted reviews are enabled.

## 1.0.0

- Initial ReviewHub-style cog.
- Added `/review`, `/vouch`, `/rateme`, `/stats`, `/leaderboard`, `/deletereview`, and `/config` slash workflows.
- Added persistent submit, report, and useful buttons.
- Added Classic and Detailed review templates.
- Added review/vouch stats, leaderboards, request modals, report channel alerts, auto-thread support, and CSV export.
