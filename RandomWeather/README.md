# 🌦️ RandomWeather

A comprehensive weather simulation system for Discord servers that generates realistic, seasonal weather patterns with beautiful embeds and dramatic extreme weather events. Perfect for roleplay servers or adding atmospheric immersion to any community!

[![Red-DiscordBot](https://img.shields.io/badge/Red--DiscordBot-V3-red.svg)](https://github.com/Cog-Creators/Red-DiscordBot)
[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![License: AGPL v3](https://img.shields.io/badge/License-AGPL%20v3-blue.svg)](https://www.gnu.org/licenses/agpl-3.0)

## 📋 Table of Contents

- [Features](#-features)
- [Installation](#-installation)
- [Commands](#-commands)
- [Configuration](#-configuration)
- [Usage Examples](#-usage-examples)
- [Weather System](#-weather-system)
- [Extreme Weather Events](#-extreme-weather-events)
- [Troubleshooting](#-troubleshooting)
- [Support](#-support)
- [Contributing](#-contributing)
- [License](#-license)

## ✨ Features

### 🌡️ Intelligent Weather Generation
- **Seasonal Accuracy**: Weather patterns that realistically change with the seasons
- **Dynamic Conditions**: Temperature, humidity, wind speed, and visibility that correlate naturally
- **Time-Zone Aware**: Respects your server's timezone for accurate seasonal calculations
- **Smart Calculations**: Includes heat index and wind chill for realistic temperature feelings

### 🌪️ Extreme Weather System
- **Rare Events**: 10 dramatic extreme weather conditions with special alert styling
- **Seasonal Patterns**: Extreme events follow realistic seasonal occurrence patterns
- **Emergency Alerts**: Professional-grade weather alerts with danger levels and safety recommendations
- **Manual Triggers**: Administrators can force extreme weather events when needed

### 🎨 Customization Options
- **Embed Colors**: Set custom colors for weather displays
- **Footer Toggle**: Show or hide embed footers
- **Update Intervals**: Configure automatic weather updates (10s to daily)
- **Channel Selection**: Choose where weather updates appear
- **Role Notifications**: Tag specific roles for weather updates

### 🎭 Roleplay Integration
- **Immersive Experience**: Perfect for roleplay servers needing consistent weather
- **Atmospheric Details**: Comprehensive weather information for storytelling
- **Consistent Updates**: Reliable weather progression for ongoing narratives

## 🚀 Installation

### Prerequisites
- Red-DiscordBot V3.5.0 or higher
- Python 3.8 or higher
- `Manage Roles` permission (for role tagging features)
- `Send Messages` and `Embed Links` permissions in target channels

### Quick Install

1. **Add the repository:**
   ```
   [p]repo add TaakosCogs https://github.com/TaakoOfficial/TaakosCogs
   ```

2. **Install the cog:**
   ```
   [p]cog install TaakosCogs RandomWeather
   ```

3. **Load the cog:**
   ```
   [p]load RandomWeather
   ```

4. **Verify installation:**
   ```
   [p]rweather
   ```

> **Note:** The required `pytz` package is automatically installed during cog installation.

## 📚 Commands

### Basic Commands

| Command | Description | Usage Example |
|---------|-------------|---------------|
| `[p]rweather` | Display current weather conditions | `[p]rweather` |
| `[p]rweather refresh` | Generate fresh weather conditions | `[p]rweather refresh` |
| `[p]rweather info` | View all current settings | `[p]rweather info` |

### Configuration Commands

| Command | Description | Usage Example |
|---------|-------------|---------------|
| `[p]rweather channel <channel>` | Set weather update channel | `[p]rweather channel #weather` |
| `[p]rweather role <role>` | Set role to tag for updates | `[p]rweather role @Weather Updates` |
| `[p]rweather toggle` | Toggle role tagging on/off | `[p]rweather toggle` |
| `[p]rweather settimezone <zone>` | Set server timezone | `[p]rweather settimezone America/New_York` |
| `[p]rweather setrefresh <interval>` | Set update interval | `[p]rweather setrefresh 1h` |

### Customization Commands

| Command | Description | Usage Example |
|---------|-------------|---------------|
| `[p]rweather setcolor <color>` | Set embed color | `[p]rweather setcolor #3498db` |
| `[p]rweather togglefooter` | Toggle embed footer visibility | `[p]rweather togglefooter` |

### Administrative Commands

| Command | Description | Usage Example |
|---------|-------------|---------------|
| `[p]rweather extreme` | Force an extreme weather event | `[p]rweather extreme` |

### Refresh Interval Options
- `10s` - Every 10 seconds (testing only)
- `5m` - Every 5 minutes
- `1h` - Every hour
- `1d` - Daily updates
- `HH:MM` - Specific time daily (e.g., `14:30`)

## ⚙️ Configuration

### Initial Setup

1. **Set your timezone** (required for seasonal accuracy):
   ```
   [p]rweather settimezone America/New_York
   ```

2. **Configure update channel** (optional):
   ```
   [p]rweather channel #weather-updates
   ```

3. **Set update interval** (optional):
   ```
   [p]rweather setrefresh 1h
   ```

4. **Configure role notifications** (optional):
   ```
   [p]rweather role @Weather Updates
   [p]rweather toggle
   ```

### Advanced Configuration

- **Custom Colors**: Use hex codes or color names
- **Footer Control**: Hide attribution if desired
- **Extreme Events**: Can be disabled by not using the force command

## 📖 Usage Examples

### Basic Weather Check
```
User: [p]rweather
Bot: [Weather Embed showing current conditions]
```

### Setting Up Automatic Updates
```
Admin: [p]rweather channel #general
Admin: [p]rweather setrefresh 6h
Admin: [p]rweather role @everyone
Admin: [p]rweather toggle
```

### Customizing Appearance
```
Admin: [p]rweather setcolor #FF6B6B
Admin: [p]rweather togglefooter
```

### Forcing Extreme Weather (RP Events)
```
Admin: [p]rweather extreme
Bot: [EXTREME WEATHER ALERT Embed with dramatic conditions]
```

## 🌦️ Weather System

### Seasonal Patterns

**🌸 Spring (March-May)**
- Temperature: 50-75°F (10-24°C)
- Common: Rain showers, partly cloudy, mild winds
- Extreme: Tornadoes, lightning storms

**☀️ Summer (June-August)**
- Temperature: 70-95°F (21-35°C)
- Common: Sunny, thunderstorms, high humidity
- Extreme: Hurricanes, typhoons, heat waves

**🍂 Fall (September-November)**
- Temperature: 45-70°F (7-21°C)
- Common: Clear skies, light rain, variable conditions
- Extreme: Flash flooding, early ice storms

**❄️ Winter (December-February)**
- Temperature: 20-50°F (-7-10°C)
- Common: Snow, overcast, cold winds
- Extreme: Ice storms, flash freeze, blizzards

### Weather Calculations

- **Heat Index**: Calculated when temperature exceeds 80°F (27°C)
- **Wind Chill**: Applied when temperature drops below 50°F (10°C)
- **Humidity**: Correlates with weather conditions and temperature
- **Visibility**: Reduced by fog, precipitation, and extreme events
- **Wind Speed**: Varies based on weather patterns and conditions

## 🌪️ Extreme Weather Events

### Available Extreme Events

| Event | Icon | Season | Description |
|-------|------|--------|-------------|
| **Typhoon** | 🌀 | Summer/Fall | Massive rotating storm system |
| **Hurricane** | 🌀 | Summer/Fall | Intense tropical cyclone |
| **Tornado** | 🌪️ | Spring/Summer | Violent rotating column of air |
| **Flash Flooding** | 🌊 | Any | Rapid water level rise |
| **Lightning Storm** | ⚡ | Spring/Summer | Intense electrical activity |
| **Ice Storm** | 🧊 | Winter | Freezing rain coating surfaces |
| **Flash Freeze** | 🥶 | Winter | Rapid temperature drop |
| **Acid Rain** | ☢️ | Any | Chemically contaminated precipitation |
| **Heavy Smog** | 🟣 | Any | Dense air pollution |
| **Blood Fog** | 🔴 | Any | Mysterious red-tinted fog |
| **Noxious Gas** | ☁️ | Any | Dangerous atmospheric gases |

### Alert Features

- **Emergency Styling**: Red colors and warning icons
- **Danger Levels**: Risk assessment for each event type
- **Safety Recommendations**: Appropriate actions for each extreme event
- **Dramatic Descriptions**: Immersive text for roleplay scenarios
- **Special Effects**: Modified visibility, wind, and other environmental factors

## 🔧 Troubleshooting

### Common Issues

**Weather not updating automatically:**
- Verify update interval is set: `[p]rweather info`
- Check channel permissions for the bot
- Ensure timezone is configured correctly

**Role tagging not working:**
- Confirm role tagging is enabled: `[p]rweather toggle`
- Verify the bot has permission to mention the role
- Check that the role exists and is configured

**Embed colors not changing:**
- Use valid hex codes (e.g., `#FF6B6B`) or color names
- Restart the bot if changes don't appear immediately

**Timezone issues:**
- Use proper timezone format: [tz database names](https://en.wikipedia.org/wiki/List_of_tz_database_time_zones)
- Example: `America/New_York`, not `EST` or `UTC-5`

### Permission Requirements

- **Basic Operation**: `Send Messages`, `Embed Links`
- **Role Tagging**: `Mention Everyone` (if using @everyone) or role-specific permissions
- **Channel Updates**: `Send Messages` in the configured update channel

### Performance Notes

- Weather generation is lightweight and shouldn't impact bot performance
- Extreme weather events are rare (approximately 1-2% chance)
- Update intervals shorter than 5 minutes are not recommended for production

## 💡 Support

### Getting Help

1. **Check this documentation** for common solutions
2. **Use `[p]rweather info`** to verify your configuration
3. **Visit the support server** for real-time assistance
4. **Report bugs** on the GitHub repository

### Useful Commands for Debugging

```
[p]rweather info          # View all settings
[p]rweather refresh       # Test weather generation
[p]rweather settimezone   # Verify timezone
```

## 🤝 Contributing

We welcome contributions to improve RandomWeather! Here's how you can help:

### Ways to Contribute

- **Bug Reports**: Found an issue? Report it on GitHub
- **Feature Requests**: Have an idea? We'd love to hear it
- **Code Contributions**: Submit pull requests for improvements
- **Documentation**: Help improve this README or add examples

### Development Setup

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test thoroughly
5. Submit a pull request

## 📄 License

This project is licensed under the **GNU Affero General Public License v3.0** (AGPL-3.0).

### Key Points:
- ✅ **Free to use** for any purpose
- ✅ **Modify and distribute** freely
- ✅ **Private use** allowed
- ❗ **Source code must be provided** when distributing
- ❗ **Same license** must be used for derivatives
- ❗ **Network use** requires source disclosure

### Attribution

- Weather icons provided by [Flaticon](https://www.flaticon.com/)
- Seasonal calculations based on astronomical data
- Extreme weather data inspired by meteorological patterns

---

## 🌈 End User Data Statement

This cog does not persistently store or share any end user data. All weather data is generated randomly and not stored permanently.

---

*Enjoy your personal weather system! May your skies be as varied as your adventures!* 🌈✨
