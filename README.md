# 🛠️ Taako's Cogs

Welcome to **Taako's Cogs**, a collection of high-quality cogs for [Red-DiscordBot](https://github.com/Cog-Creators/Red-DiscordBot/tree/V3/develop). These cogs are designed to enhance your Discord bot with unique and useful features.

---

## 📦 Available Cogs

### 1. 🌦️ RandomWeather

- **Description**: A cog for generating random daily weather updates.
- **Features**:
  - Realistic weather generation (temperature, conditions, wind, etc.).
  - Seasonal weather generation based on the user's time zone and current date.
  - Customizable updates with role tagging and channel configuration.
  - Automatic weather refresh with user-defined intervals or specific times.
  - Supports text commands for interaction.
  - Time zone support with a list of available time zones.

### 2. 📅 rpcalander

- **Description**: A cog for managing an RP calendar with daily updates.
- **Features**:
  - Automatically posts the current date and day of the week in a specified channel.
  - Customizable start date for the RP calendar.
  - Time zone support for accurate daily updates.
  - Persistent settings across bot restarts.

---

## 📚 Commands

### RandomWeather Commands

| Command                             | Description                                                               |
| ----------------------------------- | ------------------------------------------------------------------------- |
| `[p]rweather`                       | View the current weather.                                                 |
| `[p]rweather refresh`               | Refresh the weather for the day.                                          |
| `[p]rweather role <id>`             | Set a role to be tagged for weather updates.                              |
| `[p]rweather toggle`                | Toggle tagging the role in weather updates.                               |
| `[p]rweather channel <id>`          | Set the channel for weather updates.                                      |
| `[p]rweather setrefresh <interval>` | Set how often the weather should refresh (e.g., `10s`, `5m`, `1h`, `1d`). |
| `[p]rweather settimezone <zone>`    | Set the time zone for weather updates (e.g., `UTC`, `America/New_York`).  |
| `[p]rweather setcolor <color>`      | Set the embed color for weather updates.                                  |
| `[p]rweather togglefooter`          | Toggle the footer on or off for the weather embed.                        |
| `[p]rweather info`                  | View the current settings for weather updates.                            |

### rpcalander Commands

| Command                                       | Description                                                         |
| --------------------------------------------- | ------------------------------------------------------------------- |
| `[p]rpcalander`                               | View the main command group for the RP calendar.                    |
| `[p]rpcalander setstart <year> <month> <day>` | Set the starting date for the RP calendar.                          |
| `[p]rpcalander setchannel <channel>`          | Set the channel for daily calendar updates.                         |
| `[p]rpcalander settimezone <timezone>`        | Set the time zone for the RP calendar (default: `America/Chicago`). |
| `[p]rpcalander info`                          | View the current settings for the RP calendar.                      |

---

## 🌟 Example Outputs

### RandomWeather Example

```
🌤️ Today's Weather:
- Temperature: 75°F
- Feels Like: 77°F
- Conditions: Partly Cloudy
- Wind: 5 mph NE
- Humidity: 60%
- Visibility: 5.5 miles
```

### rpcalander Example

```
📅 **RP Calendar Update**
Today's date: 2023-10-01 (Sunday)
```

---

## 🔗 Additional Resources

- Learn more about [Red-DiscordBot](https://github.com/Cog-Creators/Red-DiscordBot/tree/V3/develop).
- Explore the cogs in this repository: [TaakosCogs](https://github.com/TaakoOfficial/TaakosCogs).
- View the full list of time zones: [Wikipedia Time Zones](https://en.wikipedia.org/wiki/List_of_tz_database_time_zones).

---
