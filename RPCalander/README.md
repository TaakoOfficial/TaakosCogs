# 📅 RPCalander

A comprehensive roleplay calendar system for Discord servers that automatically tracks in-game dates, displays moon phases, and manages special celestial events. Perfect for D&D campaigns, fantasy roleplay servers, and any community that needs immersive time tracking!

[![Red-DiscordBot](https://img.shields.io/badge/Red--DiscordBot-V3-red.svg)](https://github.com/Cog-Creators/Red-DiscordBot)
[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![License: AGPL v3](https://img.shields.io/badge/License-AGPL%20v3-blue.svg)](https://www.gnu.org/licenses/agpl-3.0)

## 📋 Table of Contents

- [Features](#-features)
- [Installation](#-installation)
- [Commands](#-commands)
- [Configuration](#-configuration)
- [Usage Examples](#-usage-examples)
- [Moon Phase System](#-moon-phase-system)
- [Troubleshooting](#-troubleshooting)
- [Support](#-support)
- [Contributing](#-contributing)
- [License](#-license)

## ✨ Features

### 🗓️ Automatic Calendar Management
- **Daily Updates**: Automatically posts the current RP date and day of the week
- **Custom Start Date**: Set any starting point for your RP timeline
- **Time Zone Support**: Accurate updates based on your server's timezone
- **Persistent Settings**: Remembers configuration across bot restarts

### 🌙 Advanced Moon Phase System
- **Accurate Tracking**: Real moon phases calculated based on your RP calendar date
- **Custom Embeds**: Beautiful moon phase displays with appropriate icons
- **Blood Moon Events**: Rare special events during full moons for dramatic storytelling
- **Separate Channels**: Configure different channels for calendar and moon updates

### 🎨 Customization Options
- **Embed Colors**: Set custom colors for calendar displays
- **Custom Titles**: Personalize embed titles for your server's theme
- **Footer Toggle**: Show or hide embed footers
- **Force Updates**: Manual calendar and moon phase updates when needed

### 🎭 Roleplay Integration
- **Immersive Experience**: Perfect for D&D campaigns and fantasy roleplay
- **Consistent Timeline**: Reliable date progression for ongoing stories
- **Special Events**: Blood moon events add mystical atmosphere to your world

## 🚀 Installation

### Prerequisites
- Red-DiscordBot V3.5.0 or higher
- Python 3.8 or higher
- `Send Messages` and `Embed Links` permissions in target channels

### Quick Install

1. **Add the repository:**
   ```
   [p]repo add TaakosCogs https://github.com/TaakoOfficial/TaakosCogs
   ```

2. **Install the cog:**
   ```
   [p]cog install TaakosCogs RPCalander
   ```

3. **Load the cog:**
   ```
   [p]load RPCalander
   ```

4. **Verify installation:**
   ```
   [p]rpca help
   ```

> **Note:** The required `pytz` package is automatically installed during cog installation.

## 📚 Commands

### Basic Commands

| Command | Description | Usage Example |
|---------|-------------|---------------|
| `[p]rpca` | Display help and base command group | `[p]rpca` |
| `[p]rpca info` | View all current calendar settings | `[p]rpca info` |
| `[p]rpca force` | Manually trigger a calendar update post | `[p]rpca force` |

### Calendar Configuration

| Command | Description | Usage Example |
|---------|-------------|---------------|
| `[p]rpca setstart <month> <day> <year>` | Set the RP calendar starting date | `[p]rpca setstart 1 1 1450` |
| `[p]rpca setchannel <channel>` | Set channel for daily calendar updates | `[p]rpca setchannel #rp-calendar` |
| `[p]rpca settimezone <timezone>` | Set server timezone for updates | `[p]rpca settimezone America/New_York` |

### Customization Commands

| Command | Description | Usage Example |
|---------|-------------|---------------|
| `[p]rpca setcolor <color>` | Set embed color (hex or name) | `[p]rpca setcolor #FF6B6B` |
| `[p]rpca settitle <title>` | Set custom title for calendar embed | `[p]rpca settitle "Kingdom Calendar"` |
| `[p]rpca togglefooter` | Toggle embed footer visibility | `[p]rpca togglefooter` |

### Moon Phase Commands

| Command | Description | Usage Example |
|---------|-------------|---------------|
| `[p]rpca moonphase` | Display current moon phase for RP date | `[p]rpca moonphase` |
| `[p]rpca forcemoonupdate` | Manually trigger moon phase update | `[p]rpca forcemoonupdate` |
| `[p]rpca moonconfig enable` | Enable moon phase tracking | `[p]rpca moonconfig enable` |
| `[p]rpca moonconfig disable` | Disable moon phase tracking | `[p]rpca moonconfig disable` |
| `[p]rpca moonconfig bloodmoon` | Toggle blood moon events | `[p]rpca moonconfig bloodmoon` |
| `[p]rpca moonconfig setchannel <channel>` | Set separate moon phase channel | `[p]rpca moonconfig setchannel #moon-phases` |
| `[p]rpca resetbloodmoon` | Disable blood moon mode | `[p]rpca resetbloodmoon` |

## ⚙️ Configuration

### Initial Setup

1. **Set your starting date** (required):
   ```
   [p]rpca setstart 3 15 1450
   ```

2. **Configure update channel**:
   ```
   [p]rpca setchannel #rp-calendar
   ```

3. **Set your timezone** (recommended):
   ```
   [p]rpca settimezone America/New_York
   ```

4. **Enable moon phase tracking** (optional):
   ```
   [p]rpca moonconfig enable
   ```

### Advanced Configuration

#### Custom Appearance
```
[p]rpca setcolor #4B0082
[p]rpca settitle "Realm of Mystara Calendar"
[p]rpca togglefooter
```

#### Moon Phase Setup
```
[p]rpca moonconfig setchannel #celestial-events
[p]rpca moonconfig bloodmoon
```

## 📖 Usage Examples

### Basic Calendar Display
```
User: [p]rpca force
Bot: 📅 RP Calendar Update
     Today's date: **Friday 03-15-1450**
```

### Moon Phase Display
```
User: [p]rpca moonphase
Bot: 🌙 Waxing Crescent 🌒
     The moon is currently in its Waxing Crescent 🌒 phase.
     
     Date: Friday 03-15-1450
```

### Blood Moon Event
```
Bot: 🌙 Blood Moon 🔴
     A rare Blood Moon has appeared in the night sky! Such events are often 
     associated with mystical occurrences and heightened magical energies.
     
     Date: Friday 03-15-1450
```

### Setting Up for D&D Campaign
```
DM: [p]rpca setstart 9 21 1372    # Start of Eleasis in DR
DM: [p]rpca settitle "Forgotten Realms Calendar"
DM: [p]rpca setcolor #8B4513
DM: [p]rpca setchannel #campaign-updates
DM: [p]rpca moonconfig enable
DM: [p]rpca moonconfig bloodmoon
```

## 🌙 Moon Phase System

### Moon Phase Cycle

The moon phase system follows a realistic 29.5-day lunar cycle:

| Phase | Icon | Description |
|-------|------|-------------|
| **New Moon** | 🌑 | Moon is not visible |
| **Waxing Crescent** | 🌒 | Thin crescent appearing |
| **First Quarter** | 🌓 | Half moon waxing |
| **Waxing Gibbous** | 🌔 | More than half illuminated |
| **Full Moon** | 🌕 | Completely illuminated |
| **Waning Gibbous** | 🌖 | More than half waning |
| **Last Quarter** | 🌗 | Half moon waning |
| **Waning Crescent** | 🌘 | Thin crescent disappearing |

### Blood Moon Events

- **Occurrence**: Random chance during full moon phases
- **Rarity**: Approximately 10% chance during full moons
- **Special Features**:
  - Dramatic red-themed embed styling
  - Mystical event descriptions
  - Perfect for magical campaigns and special story events
  - Can be manually toggled on/off by administrators

### Moon Phase Features

- **Accurate Calculations**: Based on your RP calendar date, not real-world dates
- **Customizable Display**: Separate channel configuration for moon updates
- **Roleplay Integration**: Descriptions perfect for fantasy settings
- **Administrative Control**: Enable/disable features as needed

## 🔧 Troubleshooting

### Common Issues

**Calendar not updating daily:**
- Check that the bot has permission to send messages in the configured channel
- Verify timezone is set correctly: `[p]rpca info`
- Ensure the cog is loaded: `[p]load RPCalander`

**Moon phases not showing:**
- Enable moon phase tracking: `[p]rpca moonconfig enable`
- Check moon phase channel permissions
- Verify the starting date is set correctly

**Dates seem incorrect:**
- Confirm timezone setting: `[p]rpca settimezone America/New_York`
- Check starting date: `[p]rpca info`
- Remember that the calendar uses your configured timezone for daily updates

**Blood moon events not appearing:**
- Enable blood moon mode: `[p]rpca moonconfig bloodmoon`
- Blood moons are rare (10% chance during full moons)
- Use `[p]rpca forcemoonupdate` to test moon phase system

### Permission Requirements

- **Basic Operation**: `Send Messages`, `Embed Links`
- **Channel Updates**: `Send Messages` in configured calendar/moon channels
- **Embed Display**: `Embed Links` permission required

### Timezone Format

Use proper [tz database names](https://en.wikipedia.org/wiki/List_of_tz_database_time_zones):
- ✅ `America/New_York`
- ✅ `Europe/London` 
- ✅ `Asia/Tokyo`
- ❌ `EST`, `PST`, `UTC-5`

## 💡 Support

### Getting Help

1. **Check this documentation** for setup instructions
2. **Use `[p]rpca info`** to verify your configuration
3. **Test with force commands** to ensure functionality
4. **Report bugs** on the GitHub repository

### Useful Commands for Debugging

```
[p]rpca info              # View all settings
[p]rpca force             # Test calendar updates
[p]rpca moonphase         # Test moon phase display
[p]rpca forcemoonupdate   # Test moon updates
```

## 🤝 Contributing

We welcome contributions to improve RPCalander! Here's how you can help:

### Ways to Contribute

- **Bug Reports**: Found an issue? Report it on GitHub
- **Feature Requests**: Ideas for new moon events or calendar features
- **Code Contributions**: Submit pull requests for improvements
- **Documentation**: Help improve this README or add examples

### Development Ideas

- Additional celestial events (eclipses, meteor showers)
- Multiple calendar systems (different fantasy worlds)
- Integration with other RP cogs
- Custom moon phase names for different settings

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

- Moon phase calculations based on astronomical algorithms
- Icons and symbols used under fair use for educational/non-commercial purposes
- Time zone handling powered by the `pytz` library

---

## 🌈 End User Data Statement

This cog stores local data in the form of a `post_tracker.json` file to track the last post timestamp. No end user data is persistently stored or shared.

---

*Keep track of time in your fantasy worlds and let the moons guide your adventures!* 🌙✨
