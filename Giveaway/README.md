# Giveaway

`Giveaway` is a Red-DiscordBot cog for simple timed giveaways.

It creates a giveaway message, adds the `🎉` reaction automatically, watches active giveaways in the background, and picks winners when the timer expires.

## Features

- Timed giveaways with flexible durations like `30m`, `2h`, `3d`, or `1w2d`
- Automatic ending after bot restarts
- Manual end and cancel commands
- Reroll support for ended giveaways
- Active giveaway listing per guild
- Reaction-based entry, so members do not need extra commands to join

## Commands

- `[p]giveaway start <duration> <winner_count> <prize>`
- `[p]giveaway startin <channel> <duration> <winner_count> <prize>`
- `[p]giveaway end <message_id_or_link>`
- `[p]giveaway cancel <message_id_or_link>`
- `[p]giveaway reroll <message_id_or_link> [winner_count]`
- `[p]giveaway list`

## Examples

```text
[p]giveaway start 2h 1 Discord Nitro
[p]giveaway startin #events 3d 3 Server Booster Bundle
[p]giveaway end 123456789012345678
[p]giveaway reroll https://discord.com/channels/123/456/789
```

## Notes

- The bot needs `View Channel`, `Send Messages`, `Embed Links`, `Add Reactions`, and `Read Message History` in the giveaway channel.
- Entrants join by reacting with `🎉` on the giveaway message.
- Winners are selected from non-bot members who still have access to the guild when the giveaway ends.
