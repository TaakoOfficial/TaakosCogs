# Fable - Living World RP Tracker

🎭 **Fable** is a Red-DiscordBot cog designed for character-driven roleplay communities. It helps you keep your world alive by tracking character profiles, relationships, in-character (IC) events, and collaboratively building lore—all in beautiful Discord embeds. No more lost lore in chat or forgotten character connections! Fable is built for pure storytelling, with zero D&D mechanics or dice—just your creativity and your community.

Fable also offers optional Google Sheets sync, so your world’s data can be shared, backed up, or visualized outside Discord.

## ✨ Features

- 🎭 **Character Profiles**: Create and view rich character sheets with names, bios, and relationship links
- 🔗 **Relationship Tracking**: Connect characters with custom relationship types
- 📝 **Event Logging**: Log IC events with timestamps and involved characters
- 🌍 **Collaborative Lore**: GMs and players can add and search world lore entries
- 📅 **Timeline View**: See all events in chronological order
- 📤 **Google Sheets Sync**: (Optional) Export and sync your data for backup or sharing
- 🖼️ **Beautiful Embeds**: All info is presented in visually appealing, color-coded Discord embeds

## 📜 Command Examples

```ini
[p]fable profile create "Aria" "Elven spy from the Silverwood"
[p]fable profile link @Aria @Bram "Rival"
[p]fable profile view "Aria"
[p]fable log "Aria stole the artifact from Bram" @Aria @Bram
[p]fable timeline
[p]fable lore add "Silverwood" "Ancient elven forest, home to Aria's kin."
[p]fable lore search "Elven"
```

## 🖼️ Embed Examples

- **Character Profile Embed**: Shows the character's name as the title, a thumbnail (user avatar or custom image), a field for bio, and a field listing all relationships (e.g., "Rival: Bram"). The embed color is coded by faction or character theme for easy visual sorting.
- **Event Log Embed**: Displays the event description, involved characters (with mentions), and a timestamp in the footer.
- **Lore Entry Embed**: Title is the lore name, description is the lore text, and a subtle color to distinguish lore from other embeds.

## 🚀 Installation

1. **Red-DiscordBot V3+ Required**
   - Make sure your bot is running Red V3.5.0 or higher.
2. **Install Fable**
   - Place the `Fable` folder in your cogs directory.
   - Load with `[p]cog load Fable`.
3. **(Optional) Google Sheets Sync**
   - Set up a Google Cloud project and enable Sheets API
   - Place your credentials in the cog's config directory (see documentation for details)

## 🔧 For Developers

- **Tech Stack**: Python 3.10+, Red-DiscordBot V3+, Discord.py, Red's Config system (JSON-backed)
- **Permissions**: Only GMs (admins) can add lore; all users can create/view profiles and log events
- **Code Style**: Follows PEP8, Red-DiscordBot, and Discord.py best practices. Hybrid commands for both text and slash. All outputs use rich embeds.

---

Fable is designed to make your RP world feel alive, organized, and collaborative. Questions, suggestions, or want to contribute? Open an issue or PR on GitHub!
