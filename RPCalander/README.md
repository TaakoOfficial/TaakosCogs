# 📅 RP Calendar Cog

Welcome to **RP Calendar**, your trusty companion for managing in-game time in your roleplay server! 🗓️✨ Never lose track of the date again!

---

## 🚀 Features

- **Automatic Daily Updates**: Posts the current RP date and day of the week automatically in your chosen channel. ☀️
- **Customizable Start Date**: Set the exact starting point for your RP timeline. ⏳
- **Time Zone Savvy**: Supports different time zones for accurate updates, powered by `pytz`! 🌍
- **Pretty Embeds**: Customize the look with embed colors and titles. 🎨
- **Footer Toggle**: Show or hide the cog footer as you like. 👀
- **Persistent Settings**: Remembers your configuration even after bot restarts. 💾
- **Force Post**: Need an immediate update? Use the force command! 💪
- **Moon Phase Tracking** 🌙: Display accurate moon phases based on your RP calendar date!
- **Blood Moon Events** 🔴: Enable special blood moon events that occur randomly during full moons!
- **Simple Blood Moon Toggle**: Admins can easily enable or disable the blood moon feature for special events.

---

## 🛠️ Installation

Getting started is easy peasy!

1.  Add Taako's Cogs repo (if you haven't already):
    ```bash
    [p]repo add TaakosCogs https://github.com/TaakoOfficial/TaakosCogs
    ```
2.  Install the RP Calendar cog:
    ```bash
    [p]cog install TaakosCogs RPCalander
    ```
3.  Load the cog:
    ```bash
    [p]load RPCalander
    ```
4.  Start configuring with `[p]rpca help`! 🎉

---

## 🎮 Usage (Commands)

Here are the commands to control your RP calendar:

| Command                                 | Description                                                   |
| --------------------------------------- | ------------------------------------------------------------- |
| `[p]rpca`                               | Base command group for the RP calendar.                       |
| `[p]rpca setstart <month> <day> <year>` | Set the starting date (e.g., `[p]rpca setstart 1 1 1450`).    |
| `[p]rpca setchannel <channel>`          | Designate the channel for daily updates.                      |
| `[p]rpca settimezone <timezone>`        | Set the time zone (e.g., `America/New_York`). Default: `UTC`. |
| `[p]rpca setcolor <color>`              | Choose a hex color for the embed (e.g., `#FF00FF`).           |
| `[p]rpca settitle <title>`              | Set a custom title for the update embed.                      |
| `[p]rpca togglefooter`                  | Turn the embed footer on or off.                              |
| `[p]rpca info`                          | Show the current calendar settings.                           |
| `[p]rpca force`                         | Manually trigger a calendar update post.                      |
| `[p]rpca moonphase`                     | Display the current moon phase for your RP date.              |
| `[p]rpca forcemoonupdate`               | Manually trigger a moon phase update post. (Admin only)       |
| `[p]rpca moonconfig enable/disable`     | Enable or disable moon phase tracking. (Admin only)           |
| `[p]rpca moonconfig bloodmoon`          | Toggle blood moon mode on/off. (Admin only)                   |
| `[p]rpca moonconfig setchannel`         | Set a separate channel for moon phase updates. (Admin only)   |
| `[p]rpca resetbloodmoon`                | Disable blood moon mode. (Admin only)                         |

---

## ✨ Example Output

Imagine this popping up in your channel every day:

```
📅 RP Calendar Update
Today's date: **Sunday 10-01-1450**
```

And with moon phase tracking enabled:

```
🌙 Full Moon 🌕
The moon is currently in its Full Moon 🌕 phase.

Date: Sunday 10-01-1450
```

Or on special occasions:

```
🌙 Blood Moon 🔴
A rare Blood Moon has appeared in the night sky! Such events are often associated with mystical occurrences and heightened magical energies.

Date: Sunday 10-01-1450
```

_(Date format: DayOfWeek MM-DD-YYYY)_

---

## 🧩 Dependencies

This cog requires the `pytz` library to handle time zones correctly. Don't worry, it tries to install it automatically for you! ✅

---

## 🔗 Additional Resources

- Curious about [Red-DiscordBot](https://github.com/Cog-Creators/Red-DiscordBot/tree/V3/develop)?
- Need a time zone? Check the [List of tz database time zones](https://en.wikipedia.org/wiki/List_of_tz_database_time_zones).

---

## 🗂️ Data Storage

This cog keeps track of the last post time in `post_tracker.json` within its directory to avoid double-posting. No user data is stored or shared. Your secrets are safe! 🔒
