# 🌦️ RandomWeather Changelog

## [v2.1.0] - 2025-04-15

### ✨ New Features

- Enhanced weather generation with realistic seasonal patterns
- Added smart condition-based calculations for humidity and visibility
- Improved wind speed variation based on weather conditions
- Added beautiful weather condition icons from Flaticon
- Added proper heat index and wind chill calculations

### 🛠️ Improvements

- Weather conditions now reflect realistic seasonal probabilities
- Temperature ranges now adapt to each season
- Weather elements (temp, humidity, wind) now properly influence each other
- Embeds now show more organized and detailed information
- Footer now includes attribution for Flaticon icons

## [v2.0.1] - 2025-04-14

### 🛠️ Improvements

- Improved scheduled weather update logic: updates now always respect the configured interval or set time, even after restarts or delays.
- Fixed issue where weather updates could drift or jump a day if the bot was restarted or delayed.

## v1.2.0

### Added

- Added `[p]rweather force` command to immediately post a weather update to the configured channel.

## v1.1.0

### Added

- Added the ability to set a custom embed color using `[p]rweather setcolor <color>`.
- Added a toggle for the footer in the weather embed using `[p]rweather togglefooter`.

### Updated

- Enhanced the `info` command to display all current settings, including:
  - Refresh Mode
  - Time Until Next Refresh
  - Time Zone
  - Update Channel
  - Role Tagging
  - Embed Color
  - Footer Status
  - Current Season

---

## v1.0.0

### Added

- Initial release of the `RandomWeather` cog.
- Features include:
  - Seasonal weather generation based on the user's time zone.
  - Customizable updates with role tagging and channel configuration.
  - Automatic weather refresh with user-defined intervals or specific times.
  - Persistent settings across bot restarts.
