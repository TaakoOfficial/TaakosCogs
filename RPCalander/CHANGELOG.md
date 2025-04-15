# 📅 rpcalander Changelog

## [v1.2.2] - 2025-04-15

### 🛠️ Improvements

- Switched license to AGPLv3 for stronger copyleft and attribution.
- Improved input validation and error handling for all commands.
- Added type hints to all methods and commands.
- Cleaned up code and removed unnecessary comments.

### 📚 Documentation

- Updated LICENSE file to AGPLv3.

## [v1.2.1] - 2025-04-15

### 🛠️ Improvements

- Added automatic installation for the `pytz` dependency. Now the cog handles its time zone magic seamlessly! ✨

## v1.2.0

### Added

- Added `[p]rpca force` command to immediately post a calendar update to the configured channel.

## v1.1.0

### Added

- Standardized the date format to `Day of the Week MM-DD-YYYY` across the cog.
- Added the ability to set a custom title for the main embed using `[p]rpca settitle <title>`.
- Added the ability to set a custom description for the main embed using `[p]rpca setdescription <description>`.
- Added a toggle for the footer in the main embed using `[p]rpca togglefooter`.
- Added the ability to set a custom embed color using `[p]rpca setcolor <color>`.

### Updated

- Enhanced the `info` command to display all current settings, including:
  - Start Date
  - Current Date
  - Update Channel
  - Time Zone
  - Embed Color
  - Embed Title
  - Embed Description

---

## v1.0.0

### Added

- Initial release of the `rpcalander` cog.
- Features include:
  - Daily calendar updates with the current date and day of the week.
  - Customizable start date and time zone.
  - Persistent settings across bot restarts.
