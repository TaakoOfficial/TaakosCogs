# ZodiacColorRoles

Bulk role creation for zodiac, color, pronoun, and ping preference roles.

[Back to the cog catalog](../README.md)

## Install

```text
[p]repo add TaakosCogs https://github.com/TaakoOfficial/TaakosCogs
[p]cog install TaakosCogs ZodiacColorRoles
[p]load ZodiacColorRoles
```

## Highlights

- Create zodiac sign roles.
- Create color roles with predefined colors.
- Create common pronoun roles.
- Create common notification preference roles.
- Use `all` to create a full category at once.
- Hybrid command support for prefix and slash usage.

## Commands

| Command | Description |
| --- | --- |
| `[p]addzodiacrole <zodiac_or_all>` or `/addzodiacrole` | Create one or all zodiac roles. |
| `[p]addcolorrole <color_or_all>` or `/addcolorrole` | Create one or all color roles. |
| `[p]addpronounrole <pronoun_or_all>` or `/addpronounrole` | Create one or all pronoun roles. |
| `[p]addcommonpingrole <role_or_all>` or `/addcommonpingrole` | Create one or all common ping roles. |
| `[p]listzodiacroles` or `/listzodiacroles` | Show available zodiac options. |
| `[p]listcolorroles` or `/listcolorroles` | Show available color options and hex values. |

## Requirements

- Red-DiscordBot 3.5.0 or newer.
- `Manage Roles`.
- The bot's top role must be above the roles it creates.
- The server must have room under Discord's role limit.

## Data

ZodiacColorRoles does not persistently store end user data.
