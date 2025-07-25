# ZodiacColorRoles Cog

A Redbot Cog to help server owners easily create zodiac and color roles for users using slash commands.

## Features

- `/addzodiacrole zodiac:<sign>` — Adds a zodiac role to the user.
- `/addcolorrole color:<#hex>` — Adds a color role to the user.

## Usage

1. Load the Cog with Redbot.
2. Use the slash commands to assign roles.

## Requirements

- Redbot 3.5.0+
- Discord bot with permissions to manage roles

## Installation

Copy the `ZodiacColorRoles` folder to your cogs directory and load with:

```
[p]load ZodiacColorRoles
```

## Commands

- `/addzodiacrole <zodiac>` — Create a zodiac role (e.g., Aries, Taurus)
- `/addcolorrole <color>` — Create a color role (e.g., Red, Blue)
- `/addpronounrole <pronoun>` — Create a pronoun role (e.g., he/him, they/them)
- `/addcommonpingrole <role>` — Create a common ping role (e.g., Common Ping, No Pings)
- `/listzodiacroles` — List all available zodiac roles
- `/listcolorroles` — List all available color roles

Use "all" as the parameter to create all roles of that type at once.

## License

MIT