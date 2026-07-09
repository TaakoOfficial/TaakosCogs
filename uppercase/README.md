# uppercase

A small Red-DiscordBot utility cog for creating and renaming text channels with visibly uppercase names.

[Back to the cog catalog](../README.md)

## Install

```text
[p]repo add taakoscogs https://github.com/TaakoOfficial/TaakosCogs
[p]cog install taakoscogs uppercase
[p]load uppercase
```

## Highlights

- Creates text channels in the category you specify.
- Renames existing text channels.
- Converts ASCII letters to bold sans uppercase characters so Discord keeps the channel name visibly uppercase.
- Hybrid command support for prefix and slash usage.
- No external dependencies.

## Commands

| Command                                           | Description                                                 |
| ------------------------------------------------- | ----------------------------------------------------------- |
| `[p]create-channel <category> <name>` or `/create-channel` | Create a text channel in a category with a visibly uppercase name. |
| `[p]rename-channel <channel> <name>` or `/rename-channel` | Rename a text channel with a visibly uppercase name. |

## Requirements

- Red-DiscordBot 3.5.0 or newer.
- Python 3.9 or newer.
- The command user needs `Manage Channels`.
- The bot needs `Manage Channels`.

For prefix commands, `<category>` can be a category mention, ID, or name. If the category name has spaces, use the category ID or quote the name.

Discord lowercases normal ASCII letters in text channel names, so this cog uses uppercase-style Unicode letters.

Example output: `staff loa` becomes `𝗦𝗧𝗔𝗙𝗙-𝗟𝗢𝗔`.

## Data

Uppercase does not persistently store end user data.
