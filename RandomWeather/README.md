# RandomWeather

Seasonal weather simulation for Red-DiscordBot servers.

[Back to the cog catalog](../README.md)

## Install

```text
[p]repo add TaakosCogs https://github.com/TaakoOfficial/TaakosCogs
[p]cog install TaakosCogs RandomWeather
[p]load RandomWeather
```

## Highlights

- Realistic seasonal weather generation.
- Temperature, feels-like temperature, humidity, wind, visibility, and conditions.
- Timezone-aware seasons.
- Automatic weather updates on an interval or scheduled time.
- Optional role notifications.
- Extreme weather events for dramatic RP or community flavor.
- Prefix command group and slash-command support.

## Commands

| Command | Description |
| --- | --- |
| `[p]rweather` | Show current weather. |
| `[p]rweather info` | Show current settings. |
| `[p]rweather settimezone <timezone>` | Set server timezone. |
| `[p]rweather setrefresh <interval_or_time>` | Set refresh interval or daily time. |
| `[p]rweather channel <channel>` | Set the update channel. |
| `[p]rweather role <role>` | Set the role to notify. |
| `[p]rweather toggle` | Toggle role notification on or off. |
| `[p]rweather color <color>` | Set embed color. |
| `[p]rweather footer` | Toggle embed footer. |
| `[p]rweather force` | Force a weather update post. |
| `[p]rweather extreme` | Force an extreme weather event. |

Slash command equivalents are available for the same core weather actions.

## Requirements

- Red-DiscordBot 3.5.0 or newer.
- `pytz`.
- `Send Messages` and `Embed Links` in the weather channel.
- Administrator or equivalent permission for configuration commands.

## Data

RandomWeather does not persistently store or share end user data. Weather is generated for server use and settings are stored per guild.
