# 🌦️ RandomWeather

Welcome to **RandomWeather**, a Discord bot cog that generates random daily weather updates! Whether you're running a roleplay server or just want some fun weather updates, this cog has you covered.

---

## ✨ Features

- **Realistic Weather Generation**: Get temperature, feels-like temperature, conditions, wind, pressure, humidity, dew point, and visibility (in miles).
- **Customizable Updates**:
  - Set a specific channel for weather updates.
  - Tag a role for weather notifications.
  - Toggle role tagging on or off.
- **Interactive Commands**: Use text commands or slash commands to interact with the bot.

---

## 🛠️ Installation

1. Add the repository to your Red-DiscordBot instance:
   ```
   [p]repo add TaakosCogs https://github.com/TaakoOfficial/TaakosCogs
   ```
2. Install the cog using the following command:
   ```
   [p]cog install TaakosCogs randomweather
   ```
3. Load the cog:
   ```
   [p]load randomweather
   ```

---

## 📚 Commands

### Text Commands

| Command                   | Description                                  |
| ------------------------- | -------------------------------------------- |
| `[p]weather`              | View the current weather.                    |
| `[p]weather refresh`      | Refresh the weather for the day.             |
| `[p]weather role <id>`    | Set a role to be tagged for weather updates. |
| `[p]weather toggle`       | Toggle tagging the role in weather updates.  |
| `[p]weather channel <id>` | Set the channel for weather updates.         |

### Slash Commands

| Command    | Description                                  |
| ---------- | -------------------------------------------- |
| `/weather` | View the current weather.                    |
| `/refresh` | Refresh the weather for the day.             |
| `/role`    | Set a role to be tagged for weather updates. |
| `/toggle`  | Toggle tagging the role in weather updates.  |
| `/channel` | Set the channel for weather updates.         |

---

## ⚙️ Configuration

- **Set Weather Role**: Use `[p]weather role <role_id>` or `/role` to specify a role for tagging.
- **Set Weather Channel**: Use `[p]weather channel <channel_id>` or `/channel` to define where updates are sent.
- **Toggle Role Tagging**: Use `[p]weather toggle` or `/toggle` to enable or disable role mentions.

---

## 🌟 Example Output

Here's an example of what the weather update looks like:

```
🌤️ Today's Weather:
- Temperature: 75°F
- Feels Like: 77°F
- Conditions: Partly Cloudy
- Wind: 5 mph NE
- Pressure: 1015 hPa
- Humidity: 60%
- Dew Point: 60°F
- Visibility: 5.5 miles
```

---

## 🧑‍💻 Author

Created with ❤️ by [**Taako**](https://github.com/TaakoOfficial).

---

## 📜 License

This project is licensed under the MIT License. See the `LICENSE` file for details.

---

## 🔗 Additional Resources

- Learn more about [Red-DiscordBot](https://github.com/Cog-Creators/Red-DiscordBot/tree/V3/develop).
- Explore this cog's repository: [TaakosCogs](https://github.com/TaakoOfficial/TaakosCogs).

---

Enjoy your daily dose of random weather! 🌈
