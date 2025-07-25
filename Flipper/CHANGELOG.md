# Changelog

All notable changes to the Flipper cog will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] - 2025-01-25

### Added
- Initial release of Flipper cog
- **Core Functionality:**
  - `coinflip` hybrid command for flipping coins
  - Support for both prefix commands and slash commands
  - Embedded result display with color coding
- **Features:**
  - Gold color for Heads results
  - Blue color for Tails results
  - 🪙 coin emoji in results
  - "Flipper • Coin Toss" footer branding
- **Technical Implementation:**
  - Uses Python's `random.choice()` for fair coin flips
  - Discord embed integration for visual appeal
  - Hybrid command support for maximum compatibility
- **Safety & Reliability:**
  - No external dependencies
  - Minimal error conditions
  - Simple and reliable operation
  - No persistent data storage

### Dependencies
- Red-DiscordBot 3.0.0+ compatibility
- Discord.py integration through Red's framework
- No external package requirements

### Notes
- Bot requires basic message sending permissions
- "Embed Links" permission recommended for best display
- Fair coin flip results using cryptographically secure random generation
