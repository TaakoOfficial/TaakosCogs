# spinwheel

Animated, colorful decision wheels for Red-DiscordBot.

[Back to the cog catalog](../README.md)

## Install

```text
[p]repo add taakoscogs https://github.com/TaakoOfficial/TaakosCogs
[p]cog install taakoscogs spinwheel
[p]load spinwheel
```

## Highlights

- Turn comma-, line-, or `|`-separated choices into a wheel that visibly spins in the Discord channel, lands on a winner, and settles into a crisp final image.
- Select every result with Python's cryptographically secure random generator before rendering the animation.
- Use eight built-in palettes: Rainbow, Ocean, Sunset, Forest, Candy, Pastel, Neon, and Midnight.
- Build custom palettes from standard six-digit hex colors.
- Save reusable server wheels and choose a default wheel.
- Optionally remove a winner after each saved-wheel spin without allowing the wheel to drop below two choices.
- Spin with prefix commands, `/wheel` slash commands, or the standalone Red-Web-Dashboard page.
- Limit instant spins to server managers and set a per-server entry limit.

## Quick Start

Spin choices immediately:

```text
[p]wheel spin Pizza, Tacos, Sushi, Burgers
```

The shorter form does the same thing:

```text
[p]wheel Pizza | Tacos | Sushi | Burgers
```

Save and spin a reusable wheel:

```text
[p]wheel create movie-night Dune, The Princess Bride, Knives Out
[p]wheel saved movie-night
```

## Commands

| Command | Description |
| --- | --- |
| `[p]wheel <entries>` | Create and spin an instant wheel. |
| `[p]wheel spin [entries]` | Spin provided entries, or the default saved wheel when no entries are provided. |
| `[p]wheel colorful <theme> <entries>` | Spin an instant wheel with a built-in theme. |
| `[p]wheel saved <name>` | Spin a saved server wheel. |
| `[p]wheel create <name> <entries>` | Create or replace a saved wheel. Requires Manage Server. |
| `[p]wheel theme <name> <theme> [custom_colors]` | Change a wheel's theme or custom palette. |
| `[p]wheel removeonwin <true_or_false> <name>` | Enable or disable automatic winner removal. |
| `[p]wheel default <name>` | Set the wheel used by `[p]wheel spin` with no entries. |
| `[p]wheel list` | List saved wheels, entry totals, themes, and spin counts. |
| `[p]wheel show <name>` | Show a static preview and numbered entry list. |
| `[p]wheel delete CONFIRM <name>` | Permanently delete a saved wheel. |
| `[p]wheel settings [allow_member_spins] [max_entries] [default_theme]` | View or update server defaults. |
| `/wheel spin` | Spin an instant wheel with slash commands. |
| `/wheel saved` | Spin a saved wheel with slash commands. |

`spinwheel` is also accepted as a prefix-command alias for `wheel`.

## Dashboard

The purpose-built dashboard is available when Red-Web-Dashboard is loaded. Members with Manage Server, Red admins, and bot owners can:

- Visually create and edit saved wheels.
- Choose built-in themes or enter custom hex colors.
- Spin saved wheels in the browser with an animated result.
- Enable automatic winner removal.
- Pick the default wheel and configure who can spin.
- Review entry totals, spin counts, and the last selected winner.

## Requirements and Permissions

- Red-DiscordBot 3.5.0 or newer.
- Python 3.9 or newer.
- Pillow 10.0.0 or newer; Red's downloader installs it automatically.
- `Send Messages`, `Embed Links`, and `Attach Files` in channels where wheels are used.
- Manage Server for saved-wheel and server-setting commands.

Discord's upload limit still applies. SpinWheel automatically retries an oversized animation at a Discord-friendly size before using a static result as a last resort.

## Data

SpinWheel stores server-created wheel names, entry labels, color settings, winner-removal preferences, the last winner, and aggregate spin counts. It does not store Discord user IDs.
