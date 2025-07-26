# Paranoia

A Red Discord Bot cog for playing the popular social party game **Paranoia** in Discord!

## What is Paranoia?

Paranoia is a fun social party game where players receive secret questions about other players via DM. They answer by naming someone in the group, and then the answers are revealed publicly while keeping the questions secret (unless players choose to reveal them). It's perfect for breaking the ice and creating hilarious moments with friends!

## Features

- **Easy Game Management**: Start and stop games with simple commands
- **Private Questions**: Questions are sent via DM to maintain secrecy
- **Flexible Rounds**: Play multiple rounds with different questions
- **Question Pool**: 15+ built-in questions plus custom question support
- **Optional Question Reveals**: Choose whether to reveal what questions were asked
- **Player Management**: Minimum 3 players, no maximum limit
- **Game Status**: Check current game progress and player participation
- **Tupperbox Integration**: Full support for roleplay communities using Tupperbox

## Commands

### Basic Commands

- `[p]paranoia start @player1 @player2 @player3` - Start a new game (min 3 players)
- `[p]paranoia answer @player` - Submit your answer for the current round
- `[p]paranoia stop` - Stop the current game (host or moderator only)
- `[p]paranoia status` - Check current game status

### Question Management

- `[p]paranoia addquestion <question>` - Add a custom question to the server pool
- `[p]paranoia questions` - List all available questions
### Admin Commands

- `[p]paranoia tupperbox [true/false]` - Enable or disable Tupperbox integration (moderator only)


## How to Play

1. **Start a Game**: Use `[p]paranoia start` and mention at least 3 players
2. **Receive Questions**: Each player gets a random question via DM
3. **Submit Answers**: Use `[p]paranoia answer @player` to answer with another player's name
4. **View Results**: Once everyone answers, results are revealed showing who each player chose
5. **Reveal Questions** (Optional): Vote to reveal what questions everyone answered
6. **Next Round**: Start another round with new questions!

## Example Questions

- "Who would survive the longest in a zombie apocalypse?"
- "Who gives the best hugs?"
- "Who would make the best superhero?"
- "Who is most likely to become famous?"
- "Who would you trust to plan your birthday party?"

## Setup Requirements

- Players must allow DMs from server members for questions to be delivered
- The bot needs permission to send messages and add reactions
- Minimum Red Discord Bot version: 3.4.0
## Tupperbox Integration

This cog includes full support for roleplay communities that use Tupperbox! When Tupperbox integration is enabled:

- **Automatic Detection**: The bot automatically detects when players are using Tupperbox proxies
- **Character Preservation**: Game results show both the character name and real player for clarity
- **Seamless Experience**: Players can participate normally through their proxy characters
- **Easy Toggle**: Server administrators can enable/disable this feature as needed

### How Tupperbox Support Works

1. **Enable Integration**: Use `[p]paranoia tupperbox true` to enable Tupperbox support
2. **Play Normally**: Players can join games and submit answers using their proxy characters
3. **Clear Results**: Game results display both "[Character Name] (Real Player)" for transparency
4. **Automatic Fallback**: If proxy detection fails, the system gracefully falls back to normal operation

### Tupperbox Commands

- `[p]paranoia tupperbox` - Check current Tupperbox integration status
- `[p]paranoia tupperbox true` - Enable Tupperbox integration
- `[p]paranoia tupperbox false` - Disable Tupperbox integration

**Note**: Only server moderators can toggle Tupperbox integration settings.


## Privacy & Data

- Game data is stored temporarily during active sessions only
- Custom questions are stored per server
- Player IDs and answers are only used for game functionality
- No personal data is permanently stored

## Tips for Best Experience

- Make sure all players can receive DMs from the bot
- Start with smaller groups (3-5 players) to learn the game
- Add custom questions relevant to your friend group
- Have fun and don't take answers too seriously!

## Troubleshooting

**"Couldn't send DM" error**: Player needs to allow DMs from server members in their privacy settings.


**Tupperbox issues**: If proxy detection isn't working properly, try disabling and re-enabling Tupperbox integration, or contact your server administrators.

**Character name confusion**: When Tupperbox is enabled, results show both character and real player names for clarity.
**Game stuck**: Use `[p]paranoia stop` to end the current game and start fresh.

**Missing answers**: Use `[p]paranoia status` to see who still needs to submit answers.

## Support

If you encounter any issues or have suggestions for improvement, please report them through your server's support channels.

---

*Have fun and remember - it's just a game! The questions and answers are all in good fun.* 🎭