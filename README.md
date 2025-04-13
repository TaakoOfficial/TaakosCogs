# 🛠️ Taako's Cogs

Welcome to **Taako's Cogs**, a collection of high-quality cogs for [Red-DiscordBot](https://github.com/Cog-Creators/Red-DiscordBot/tree/V3/develop). These cogs are designed to enhance your Discord bot with unique and useful features.

---

## 📦 Available Cogs

### 1. 🌦️ RandomWeather

- **Description**: A cog for generating random daily weather updates.
- **Features**:
  - Realistic weather generation (temperature, conditions, wind, etc.).
  - Customizable updates with role tagging and channel configuration.
  - Automatic weather refresh with user-defined intervals or specific times.
  - Supports text commands for interaction.
  - Time zone support with a list of available time zones.

---

## 📚 Commands

### Text Commands

| Command                             | Description                                                               |
| ----------------------------------- | ------------------------------------------------------------------------- |
| `[p]rweather`                       | View the current weather.                                                 |
| `[p]rweather refresh`               | Refresh the weather for the day.                                          |
| `[p]rweather role <id>`             | Set a role to be tagged for weather updates.                              |
| `[p]rweather toggle`                | Toggle tagging the role in weather updates.                               |
| `[p]rweather channel <id>`          | Set the channel for weather updates.                                      |
| `[p]rweather load`                  | Manually load the current weather.                                        |
| `[p]rweather setrefresh <interval>` | Set how often the weather should refresh (e.g., `10s`, `5m`, `1h`, `1d`). |
| `[p]rweather settimezone <zone>`    | Set the time zone for weather updates (e.g., `UTC`, `America/New_York`).  |
| `[p]rweather listtimezones`         | List available time zones or provide a link to the full list.             |

---

## 🌟 Example Output

Here's an example of what the weather update looks like:

```
🌤️ Today's Weather:
- Temperature: 75°F
- Feels Like: 77°F
- Conditions: Partly Cloudy
- Wind: 5 mph NE
- Humidity: 60%
- Visibility: 5.5 miles
```

---

## 🔗 Additional Resources

- Learn more about [Red-DiscordBot](https://github.com/Cog-Creators/Red-DiscordBot/tree/V3/develop).
- Explore the cogs in this repository: [TaakosCogs](https://github.com/TaakoOfficial/TaakosCogs).
- View the full list of time zones: [Wikipedia Time Zones](https://en.wikipedia.org/wiki/List_of_tz_database_time_zones).

---
