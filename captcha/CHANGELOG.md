# Changelog

## 1.3.1

- Renamed the repository package folder from `Captcha` to `captcha` to match Red cog naming standards.
- New installs should use `[p]cog install taakoscogs captcha` and `[p]load captcha`.
- Existing captcha panels, roles, labels, and setup data are preserved because the cog's Config identifier did not change.

## 1.3.0

- Added Red-Web-Dashboard integration for posting, attaching, removing, and reviewing captcha panels.

## 1.2.0

- Added native `/captcha` commands, including slash-safe role options for posting and attaching panels.

## 1.1.0

- Added support for assigning up to ten roles from one captcha panel.
- Preserved compatibility with existing single-role panel records.
- Changed verification to assign only roles the member is missing.

## 1.0.0

- Added persistent captcha buttons for predefined and existing bot-authored messages.
- Added per-click random codes displayed in Discord modal titles.
- Added role assignment after successful verification.
- Added panel listing/removal and role safety checks.
