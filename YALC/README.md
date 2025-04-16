# 📝 YALC - Yet Another Logging Cog

A powerful Discord server logging solution for Red-DiscordBot with both classic and slash commands! 🌟

---

## 🚀 Features

- Comprehensive server logging
- Both classic and slash commands
- Per-channel event configuration
- User, role, and channel ignore lists
- Log retention management
- Rich embed formatting
- Fully type-hinted codebase

## 🛠️ Installation

1. Add Taako's repo:

   ```
   [p]repo add TaakosCogs https://github.com/TaakoOfficial/TaakosCogs
   ```

2. Install YALC:

   ```
   [p]cog install TaakosCogs YALC
   ```

3. Load it up:

   ```
   [p]load YALC
   ```

## 🎮 Usage

### Slash Commands

- `/yalc info` - Show enabled events and channels
- `/yalc listevents` - List available event types
- `/yalc setchannel` - Set log channel for events
- `/yalc ignore` - Manage ignore lists
- `/yalc filters` - Manage event filters

### Classic Commands

- `[p]yalc info` - Show current settings
- `[p]yalc setup` - Interactive setup
- `[p]yalc ignore` - Manage ignore lists
- `[p]help yalc` - Show all commands

## 🧩 Example

```bash
/yalc setchannel #server-logs
/yalc enable message_delete message_edit
```

## 📜 License

MIT License. See `LICENSE` file.
