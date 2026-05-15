# Uppercase

A small Red-DiscordBot utility cog for creating and renaming text channels with uppercase-style names.

[Back to the cog catalog](../README.md)

## Install

```text
[p]repo add taakoscogs https://github.com/TaakoOfficial/TaakosCogs
[p]cog install taakoscogs Uppercase
[p]load Uppercase
```

## Highlights

- Creates text channels in the category you specify.
- Renames existing text channels.
- Converts ASCII letters to bold sans uppercase letters so channel names stay visibly uppercase.
- Hybrid command support for prefix and slash usage.
- No external dependencies.

## Commands

| Command                                           | Description                                                 |
| ------------------------------------------------- | ----------------------------------------------------------- |
| `[p]create-channel <category> <name>` or `/create-channel` | Create a text channel in a category with an uppercase-style name. |
| `[p]rename-channel <channel> <name>` or `/rename-channel` | Rename a text channel with an uppercase-style name. |

## Requirements

- Red-DiscordBot 3.5.0 or newer.
- Python 3.9 or newer.
- The command user needs `Manage Channels`.
- The bot needs `Manage Channels`.

For prefix commands, `<category>` can be a category mention, ID, or name. If the category name has spaces, use the category ID or quote the name.

Example output: `staff loa` becomes `𝗦𝗧𝗔𝗙𝗙-𝗟𝗢𝗔`.

## Data

Uppercase does not persistently store end user data.
