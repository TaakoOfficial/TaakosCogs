# 📝 YALC - Yet Another Logging Cog

A modern, modular Redbot cog for logging all the spicy server events with style and fun! 🎉

---

## 🚀 Features

- Per-event logging for nearly every Discord server event
- Classic and slash command support
- Per-event log channel configuration (set each event to a different channel!)
- All logging is opt-in: enable only what you want
- Rich, readable embeds for all logs
- Tracks moderation actions, nickname/username changes, channel/role/thread/emoji events, and more
- Case numbers for moderation actions
- Staff command usage logging
- Follows Red V3+ and Discord best practices

## 🛠️ Installation

1. Ensure you have Redbot 3.5+ installed and running.
2. Install this cog using Redbot's downloader:
   ```bash
   [p]repo add TaakosCogs https://github.com/TaakoOfficial/TaakosCogs
   [p]cog install TaakosCogs  yalc
   [p]load yalc
   ```

## 🎮 Usage

- Enable logging for events you want:
  - `[p]yalc setlog #channel` — Set the default log channel
  - `/eventlog set <event> <#channel>` — Set a log channel for a specific event
  - `/eventlog clear <event>` — Reset an event to use the default log channel
- Enable/disable events in your config (see `[p]help yalc` for all options)
- All logs are sent as rich embeds for clarity

## 🧩 Example

```bash
[p]yalc setlog #mod-logs
/eventlog set member_ban #ban-logs
/eventlog set command_log #staff-commands
```

## ⚙️ Configuration Tips

- All logging is opt-in. Enable only the events you want to log.
- Use `/eventlog set <event> <#channel>` to send each event to a different channel.
- Use `/eventlog clear <event>` to reset an event to the default log channel.
- Enable/disable events using Redbot's config system or with your preferred config editor.
- You can check your current settings with `[p]yamlc` or `[p]yamlc settings` (if implemented).
- For best results, create dedicated channels for moderation, join/leave, and staff command logs.

## ❓ FAQ

**Q: Why aren't any logs showing up?**
- Make sure you've set a log channel and enabled at least one event in your config.
- Check bot permissions: it needs to view and send messages in the log channels.

**Q: Can I log each event to a different channel?**
- Yes! Use `/eventlog set <event> <#channel>` for each event you want to separate.

**Q: How do I enable/disable specific events?**
- Use your config editor or commands to set `log_events.<event>` to true/false.

**Q: Does this support both classic and slash commands?**
- Yes, both are supported and logged if enabled.

**Q: How do I update the cog?**
- Use `[p]cog update yalc` and reload with `[p]reload yalc`.

**Q: Where can I get help?**
- Open an issue on the GitHub repo or ask in the Redbot support server.

## 📜 License

AGPL-3.0 License. See `LICENSE` file.
