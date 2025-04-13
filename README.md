# 🌦️ WeatherCog

Welcome to **WeatherCog**, a Discord bot cog that generates random daily weather updates! Whether you're running a roleplay server or just want some fun weather updates, this cog has you covered.

---

## ✨ Features

- **Realistic Weather Generation**: Get temperature, feels-like temperature, conditions, wind, pressure, humidity, dew point, and visibility.
- **Customizable Updates**:
  - Set a specific channel for weather updates.
  - Tag a role for weather notifications.
  - Toggle role tagging on or off.
- **Interactive Commands**: Refresh the weather or view the current weather on demand.

---

## 🛠️ Installation

1. Add the repository to your Red-DiscordBot instance:
   ```
   [p]repo add randomweather https://github.com/TaakoOfficial/randomweather
   ```
2. Install the cog using the following command:
   ```
   [p]cog install WeatherCog
   ```
3. Load the cog:
   ```
   [p]load WeatherCog
   ```

---

## 📚 Commands

| Command                  | Description                                  |
| ------------------------ | -------------------------------------------- |
| `[p]weather`             | View the current weather.                    |
| `[p]refresh_weather`     | Refresh the weather for the day.             |
| `[p]set_weather_role`    | Set a role to be tagged for weather updates. |
| `[p]toggle_role_tagging` | Toggle tagging the role in weather updates.  |
| `[p]set_weather_channel` | Set the channel for weather updates.         |

---

## ⚙️ Configuration

- **Set Weather Role**: Use `[p]set_weather_role <role_id>` to specify a role for tagging.
- **Set Weather Channel**: Use `[p]set_weather_channel <channel_id>` to define where updates are sent.
- **Toggle Role Tagging**: Use `[p]toggle_role_tagging` to enable or disable role mentions.

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
- Visibility: 8.5 km
```

---

## 🧑‍💻 Author

Created with ❤️ by **Taako**.

---

## 📜 License

This project is licensed under the MIT License. See the `LICENSE` file for details.

---

## 🔗 Additional Resources

- Learn more about [Red-DiscordBot](https://github.com/Cog-Creators/Red-DiscordBot/tree/V3/develop).
- Explore this cog's repository: [randomweather](https://github.com/TaakoOfficial/randomweather).

---

Enjoy your daily dose of random weather! 🌈
