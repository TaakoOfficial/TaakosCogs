# 📅 rpcalander

Welcome to **rpcalander**, a Discord bot cog that manages an RP calendar with daily updates! This cog is perfect for roleplay servers that want to keep track of in-game days and events.

---

## 📚 Commands

### Text Commands

| Command                                 | Description                                                         |
| --------------------------------------- | ------------------------------------------------------------------- |
| `[p]rpca`                               | View the main command group for the RP calendar.                    |
| `[p]rpca setstart <month> <day> <year>` | Set the starting date for the RP calendar.                          |
| `[p]rpca setchannel <channel>`          | Set the channel for daily calendar updates.                         |
| `[p]rpca settimezone <timezone>`        | Set the time zone for the RP calendar (default: `America/Chicago`). |
| `[p]rpca setcolor <color>`              | Set the embed color for calendar updates.                           |
| `[p]rpca settitle <title>`              | Set a custom title for the main embed.                              |
| `[p]rpca togglefooter`                  | Toggle the footer on or off for the main embed.                     |
| `[p]rpca info`                          | View the current settings for the RP calendar.                      |

---

## ⚙️ Features

- **Daily Updates**: Automatically posts the current date and day of the week in a specified channel.
- **Customizable Start Date**: Set the starting date for your RP calendar.
- **Customizable Embed**: Configure the embed color and title for calendar updates.
- **Time Zone Support**: Configure the time zone for accurate daily updates.
- **Persistent Settings**: All settings are saved and persist across bot restarts.

---

## 🌟 Example Output

Here's an example of what the daily calendar update looks like:

```
📅 RP Calendar Update
Today's date: **Sunday 10-01-2023**
```

---

## 🛠️ Installation

To install the **rpcalander** cog:

1. Add Taako's repository to your bot:

   ```
   [p]repo add TaakosCogs https://github.com/TaakoOfficial/TaakosCogs
   ```

2. Install the rpcalander cog:

   ```
   [p]cog install TaakosCogs RPCalander
   ```

3. Load the cog:

   ```
   [p]load RPCalander
   ```

4. Use `[p]rpca` to start configuring the RP calendar.

---

## 🔗 Additional Resources

- Learn more about [Red-DiscordBot](https://github.com/Cog-Creators/Red-DiscordBot/tree/V3/develop).
- View the full list of time zones: [Wikipedia Time Zones](https://en.wikipedia.org/wiki/List_of_tz_database_time_zones).

---

## 🗂️ Data Storage

This cog saves the following data to your system:

- **`post_tracker.json`**: Stores the timestamp of the last post to ensure the bot does not post multiple times in a single day. This file is located in the cog's directory.

All data is stored locally and is not shared with any external services.
