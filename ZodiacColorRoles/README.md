# ZodiacColorRoles

A Red-DiscordBot cog for easily creating zodiac, color, pronoun, and ping roles with hybrid command support.

## Installation

To install this cog, use the following command in your Red bot:

```
[p]repo add TaakosCogs https://github.com/TaakoOfficial/TaakosCogs
[p]cog install TaakosCogs ZodiacColorRoles
[p]load ZodiacColorRoles
```

## Features

- **Zodiac Roles**: Create roles for all 12 zodiac signs
- **Color Roles**: Create colorized roles with 16 predefined colors
- **Pronoun Roles**: Create common pronoun roles for inclusive communities
- **Ping Roles**: Create common notification preference roles
- **Bulk Creation**: Create all roles of a type at once with "all" parameter
- **Smart Duplicate Detection**: Automatically handles existing roles
- **Hybrid Commands**: Works with both prefix commands and slash commands
- **Comprehensive Error Handling**: Clear feedback on permissions and failures

## Commands

### Role Creation Commands

- `[p]addzodiacrole <zodiac>` / `/addzodiacrole`
  - Create zodiac roles (Aries, Taurus, Gemini, Cancer, Leo, Virgo, Libra, Scorpio, Sagittarius, Capricorn, Aquarius, Pisces)
  - Use "all" to create all zodiac roles at once

- `[p]addcolorrole <color>` / `/addcolorrole`
  - Create color roles with proper hex colors
  - Available colors: Red, Orange, Yellow, Green, Blue, Purple, Pink, Black, White, Gray, Cyan, Magenta, Brown, Teal, Lime, Navy
  - Use "all" to create all color roles at once

- `[p]addpronounrole <pronoun>` / `/addpronounrole`
  - Create pronoun roles for inclusive communities
  - Available pronouns: he/him, she/her, they/them, any pronouns, ask me, xe/xem, ze/zir
  - Use "all" to create all pronoun roles at once

- `[p]addcommonpingrole <pingrole>` / `/addcommonpingrole`
  - Create common notification preference roles
  - Available roles: Common Ping, No Pings, Ping on Important, Ping for Events
  - Use "all" to create all ping roles at once

### Utility Commands

- `[p]listzodiacroles` / `/listzodiacroles`
  - List all available zodiac roles that can be created

- `[p]listcolorroles` / `/listcolorroles`
  - List all available color roles with their hex codes

## Usage Examples

### Create Single Roles
```
[p]addzodiacrole Aries
[p]addcolorrole Blue
[p]addpronounrole they/them
[p]addcommonpingrole No Pings
```

### Create All Roles of a Type
```
[p]addzodiacrole all
[p]addcolorrole all
[p]addpronounrole all
[p]addcommonpingrole all
```

### List Available Options
```
[p]listzodiacroles
[p]listcolorroles
```

## Color Roles Available

- **Red** (#FF0000), **Orange** (#FFA500), **Yellow** (#FFFF00)
- **Green** (#008000), **Blue** (#0000FF), **Purple** (#800080)
- **Pink** (#FFC0CB), **Black** (#000000), **White** (#FFFFFF)
- **Gray** (#808080), **Cyan** (#00FFFF), **Magenta** (#FF00FF)
- **Brown** (#A52A2A), **Teal** (#008080), **Lime** (#00FF00), **Navy** (#000080)

## Requirements

- **Bot Permissions**: The bot needs `Manage Roles` permission in the server
- **Red-DiscordBot**: Version 3.0.0 or higher
- **Role Hierarchy**: Bot's role must be higher than the roles it creates

## Error Handling

The cog provides comprehensive error handling for common issues:

- **Permission Errors**: Clear messages when the bot lacks "Manage Roles" permission
- **Invalid Input**: Helpful feedback when invalid zodiac signs, colors, or pronouns are provided
- **Existing Roles**: Automatic detection and notification when roles already exist
- **Bulk Operations**: Detailed reports showing which roles were created vs. skipped vs. failed

## Tips

1. **Role Management**: Created roles can be assigned to users through Discord's native role system
2. **Customization**: All role names follow consistent patterns (e.g., "Color Blue", "Aries")
3. **Bulk Operations**: Use "all" parameter for initial server setup
4. **Case Insensitive**: Commands accept input in any case (e.g., "aries", "ARIES", "Aries")

## Troubleshooting

### "I need the 'Manage Roles' permission to create roles"
- Grant the bot the "Manage Roles" permission in Server Settings > Roles

### "Invalid zodiac sign" or "Invalid color"
- Use the list commands to see valid options: `[p]listzodiacroles` or `[p]listcolorroles`

### "Failed to create role due to Discord API error"
- Check that the bot's role is higher in the hierarchy than the roles it's trying to create
- Ensure the server hasn't reached Discord's role limit (250 roles)

### Roles not appearing with colors
- Verify the bot has permission to manage roles and that role hierarchy is correct
- Color roles are created with "Color " prefix (e.g., "Color Blue")

## End User Data Statement

This cog does not persistently store any end user data.

## Support

If you encounter any issues or have suggestions, please visit the [GitHub repository](https://github.com/TaakoOfficial/TaakosCogs) and create an issue.

## Changelog

See [CHANGELOG.md](CHANGELOG.md) for version history and updates.