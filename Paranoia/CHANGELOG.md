# Changelog

All notable changes to the Paranoia cog will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.0] - 2025-01-26

### Added
- Initial release of the Paranoia cog
- Core game functionality for the social party game Paranoia
- Game session management (start/stop games)
- Private question delivery via DM system
- Answer submission and collection system
- Round-based gameplay with automatic progression
- Results revelation with optional question disclosure
- Built-in question pool with 15 default questions
- Custom question system for server-specific content
- Game status tracking and progress monitoring
- Player validation and error handling
- Reaction-based game flow control
- Multi-round support with question randomization
- Host permissions and game moderation controls
- Comprehensive help documentation and examples

### Features
- **Game Management**: Start games with 3+ players, stop games, check status
- **Question System**: 15 built-in questions + custom question support
- **Privacy Controls**: Questions sent via DM, optional question reveals
- **User Experience**: Clear instructions, progress tracking, error messages
- **Moderation**: Host controls, permission checks, game session isolation
- **Customization**: Server-specific custom questions, flexible round system

### Commands
- `[p]paranoia start @players` - Start a new game session
- `[p]paranoia answer @player` - Submit answer for current round
- `[p]paranoia stop` - End current game (host/moderator only)
- `[p]paranoia status` - Check current game progress
- `[p]paranoia addquestion <question>` - Add custom question to server pool
- `[p]paranoia questions` - List all available questions

### Requirements
- Red Discord Bot 3.4.0+
- Python 3.8+
- Players must allow DMs from server members

### Known Limitations
- Requires DM permissions for question delivery
- One game per channel at a time
- Questions limited to 200 characters
- Minimum 3 players required

## [Unreleased]

### Planned Features
- Question categories and filtering
- Game statistics and leaderboards
- Timed rounds with automatic progression
- Team-based gameplay modes
- Integration with other party game cogs