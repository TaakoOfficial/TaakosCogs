# 🌦️ RandomWeather Changelog

## [v2.2.2] - 2025-05-12

### ✨ New Features

- Added "Flash Freeze 🥶" extreme weather event for winter
- Added "Light Snow ❄️" normal weather condition to increase winter snow variety
- Enhanced winter weather diversity with more snow-related conditions

### 🎨 Visual Improvements

- Updated all extreme weather icons with higher quality versions
- Added distinct icon for Light Snow
- Improved visual distinction between weather types

## [v2.2.1] - 2025-05-12

### 🛠️ Improvements

- Enhanced extreme weather with seasonal patterns:
  - Tornadoes occur more frequently in spring
  - Hurricanes and typhoons peak in summer and early fall
  - Lightning storms more common in spring and summer
  - Ice storms appear primarily in winter
- Renamed "Colored Fog" to "Heavy Smog" for clarity
- Base extreme events (Acid Rain, Heavy Smog, Blood Fog, Noxious Gas) can appear in any season

## [v2.2.0] - 2025-05-12

### ✨ New Features

- Added 10 rare extreme weather events:
  - Typhoon 🌀
  - Flash Flooding 🌊
  - Acid Rain ☢️
  - Hurricane 🌀
  - Tornado 🌪️
  - Ice Storm 🧊
  - Heavy Smog 🟣
  - Blood Fog 🔴
  - Lightning Storm ⚡
  - Noxious Gas ☁️
- Customized wind speeds and visibility for extreme conditions
- Added unique icons for all new weather types

## [v2.1.1] - 2025-04-15

### 🛠️ Improvements

- Switched license to AGPLv3 for stronger copyleft and attribution.
- Improved input validation and error handling for all commands.
- Added type hints to all methods and commands.
- Cleaned up code and removed unnecessary comments.

### 📚 Documentation

- Updated LICENSE file to AGPLv3.

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
