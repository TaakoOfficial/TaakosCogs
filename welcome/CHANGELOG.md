# Changelog

## 1.4.0 - 2026-07-16

- Reorganized the dashboard into responsive Settings, Image, Preview, and Placeholders tabs that remain selected after form submissions.
- Added SSRF-resistant image fetching with public-address DNS filtering, redirect validation, image-type enforcement, and streaming size limits.
- Made member-join automation respect Red's per-guild cog-disable state.

## 1.3.1

- Renamed the repository package folder from `Welcome` to `welcome` to match Red cog naming standards.
- New installs should use `[p]cog install taakoscogs welcome` and `[p]load welcome`.
- Existing welcome settings, templates, cached-image settings, and setup data are preserved because the cog's Config identifier did not change.

## 1.3.0

- Added Red-Web-Dashboard third-party integration for Welcome.
- Added dashboard controls for welcome settings, message templates, embed JSON, cached images, avatar overlays, previews, and placeholder reference.
