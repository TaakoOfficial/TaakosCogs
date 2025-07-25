# Flipper

A Red-DiscordBot cog for flipping coins with embedded result display and color coding.

## Installation

To install this cog, use the following command in your Red bot:

```
[p]repo add TaakosCogs https://github.com/TaakoOfficial/TaakosCogs
[p]cog install TaakosCogs Flipper
[p]load Flipper
```

## Features

- **Coin Flip**: Simple coin flip command with visual results
- **Embedded Display**: Results shown in attractive Discord embeds
- **Color Coding**: Gold for Heads, Blue for Tails
- **Hybrid Commands**: Works with both prefix commands and slash commands

## Commands

### Core Commands

- `[p]coinflip` / `/coinflip`
  - Flip a coin and get either Heads or Tails
  - Results are displayed in a color-coded embed

## Usage Examples

### Basic Coin Flip
```
[p]coinflip
```
or
```
/coinflip
```

This will flip a coin and display the result in an embed with:
- 🪙 Coin Flip title
- Gold color for Heads result
- Blue color for Tails result
- "Flipper • Coin Toss" footer

## Requirements

- **Bot Permissions**: No special permissions required
- **Red-DiscordBot**: Version 3.0.0 or higher

## Error Handling

The cog is designed to be simple and reliable with minimal error conditions:

- Uses Python's built-in `random.choice()` for fair coin flips
- Embedded display ensures consistent formatting
- No external dependencies or complex operations

## Tips

1. **Fair Results**: Uses Python's cryptographically secure random number generation
2. **Visual Appeal**: Embedded results are more visually appealing than plain text
3. **Accessibility**: Works in both text channels and slash command contexts

## Troubleshooting

### Command not working
- Ensure the cog is loaded with `[p]load Flipper`
- Check that the bot has permission to send messages in the channel

### Embed not displaying
- Verify the bot has "Embed Links" permission in the channel

## End User Data Statement

This cog does not persistently store any end user data.

## Support

If you encounter any issues or have suggestions, please visit the [GitHub repository](https://github.com/TaakoOfficial/TaakosCogs) and create an issue.

## Changelog

See [CHANGELOG.md](CHANGELOG.md) for version history and updates.