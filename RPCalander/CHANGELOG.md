# Changelog

All notable changes to the RPCalander cog will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.3.1] - 2025-05-12

### Changed
- **Blood Moon System**: Simplified blood moon functionality to direct toggle instead of admin approvals
- **User Experience**: Improved interface for managing moon phase settings
- **Visual Quality**: Updated moon phase icons with enhanced graphics

### Improved
- **Accessibility**: Streamlined blood moon configuration process
- **Interface**: More intuitive moon phase management commands
- **Visual Appeal**: Higher quality moon phase icons and embeds

## [1.3.0] - 2025-05-10

### Added
- **Moon Phase System**: Complete lunar tracking based on RP calendar dates
- **Blood Moon Events**: Rare special events during full moons for dramatic roleplay
- **Separate Embeds**: Custom styling for moon phase displays distinct from calendar
- **Channel Configuration**: Ability to set separate channels for moon phase updates

### New Commands
- **`[p]rpca moonphase`**: Display current moon phase for RP date
- **`[p]rpca forcemoonupdate`**: Manually trigger moon phase updates
- **`[p]rpca moonconfig`**: Complete moon phase configuration system
  - `enable/disable`: Toggle moon phase tracking on/off
  - `bloodmoon`: Toggle blood moon event mode
  - `setchannel`: Configure separate moon phase update channel
- **`[p]rpca resetbloodmoon`**: Quick disable for blood moon mode

### Enhanced Features
- **Lunar Calculations**: Accurate 29.5-day lunar cycle tracking
- **Visual Elements**: Moon phase icons and themed embed colors
- **Roleplay Integration**: Atmospheric descriptions perfect for fantasy settings
- **Administrative Control**: Full control over moon phase features

### Documentation
- **Help System**: Updated all command documentation
- **Info Display**: Added moon phase settings to `[p]rpca info` command
- **User Guide**: Comprehensive moon phase usage instructions

## [1.2.2] - 2025-04-15

### Changed
- **License**: Switched to AGPLv3 for stronger copyleft protection and attribution requirements
- **Code Quality**: Enhanced input validation and error handling across all commands
- **Type Safety**: Added comprehensive type hints to all methods and commands
- **Code Maintenance**: Cleaned up codebase and removed unnecessary comments

### Documentation
- **License**: Updated LICENSE file to GNU Affero General Public License v3.0
- **Legal**: Enhanced attribution and distribution requirements

## [1.2.1] - 2025-04-15

### Added
- **Automatic Dependencies**: Implemented automatic `pytz` library installation
- **Seamless Setup**: Time zone functionality now works out-of-the-box
- **Error Prevention**: Eliminates dependency-related installation issues

### Improved
- **User Experience**: Streamlined installation process without manual dependency management
- **Reliability**: Consistent time zone handling across all server environments

## [1.2.0] - 2025-04-14

### Added
- **Force Updates**: `[p]rpca force` command for immediate calendar updates
- **Manual Control**: Bypass automatic scheduling when needed
- **Testing Support**: Easy way to verify calendar configuration and appearance

### Enhanced
- **Administrative Tools**: Better control over calendar posting timing
- **Troubleshooting**: Simplified testing of calendar embed formatting

## [1.1.0] - 2025-04-13

### Added
- **Date Standardization**: Consistent `Day of the Week MM-DD-YYYY` format across all displays
- **Custom Titles**: `[p]rpca settitle <title>` for personalized embed headers
- **Custom Descriptions**: `[p]rpca setdescription <description>` for detailed embed content
- **Footer Control**: `[p]rpca togglefooter` to show/hide embed attribution
- **Color Customization**: `[p]rpca setcolor <color>` for themed embed appearance

### Enhanced
- **Info Command**: Comprehensive settings display including:
  - Current RP start date and calculated current date
  - Configured update channel and timezone
  - Visual customization settings (embed color, title, description)
  - Footer visibility status
- **User Interface**: More intuitive configuration management
- **Visual Consistency**: Standardized appearance across all calendar displays

## [1.0.0] - 2025-04-01

### Added
- **Core Functionality**: Initial release of RPCalander cog
- **Daily Updates**: Automatic calendar posting with current RP date and day of week
- **Custom Timeline**: Configurable starting date for any fantasy world or campaign
- **Time Zone Support**: Accurate daily updates based on server timezone
- **Persistent Settings**: Configuration survives bot restarts and updates

### Features
- **Date Calculation**: Smart progression from custom start date
- **Timezone Integration**: Powered by `pytz` library for accurate time handling
- **Channel Configuration**: Designate specific channels for calendar updates
- **Basic Customization**: Foundation for visual and functional enhancements

### Technical Details
- **Dependencies**: `pytz` for timezone calculations
- **Data Storage**: Local configuration persistence
- **Update System**: Daily automated posting mechanism
- **Command Structure**: Intuitive `[p]rpca` command group
