# Changelog

## 1.3.0 - 2026-07-16

- Reorganized the dashboard into responsive Reports, Settings, and Maintenance tabs that remain selected after form submissions.
- Made invite and member listeners respect Red's per-guild cog-disable state.

## 1.2.1

- Renamed the repository package folder from `InviteTracker` to `invitetracker` to match Red cog naming standards.
- New installs should use `[p]cog install taakoscogs invitetracker` and `[p]load invitetracker`.
- Existing invite tracking settings and records are preserved because the cog's Config identifier did not change.

## 1.2.0

- Added Red-Web-Dashboard integration for settings, invite cache refresh, stat reset, leaderboards, and recent join-source review.

## 1.1.0

- Added native `/invitetracker` and `/invites` subcommands.

## 1.0.0

- Initial InviteTracker cog.
- Added invite-use tracking, fake join detection, leaver tracking, leaderboards, source lookup, log channel configuration, invite cache refresh, stats reset, and CSV export.
