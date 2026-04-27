# Paranoia

A social party game cog for Red-DiscordBot.

[Back to the cog catalog](../README.md)

## Install

```text
[p]repo add TaakosCogs https://github.com/TaakoOfficial/TaakosCogs
[p]cog install TaakosCogs Paranoia
[p]load Paranoia
```

## Highlights

- Players receive secret questions by DM.
- Players answer by naming another participant.
- Public reveals keep the questions hidden unless the group chooses otherwise.
- Built-in and custom question support.
- Game status and host/moderator stop controls.
- Optional Tupperbox integration for roleplay communities.

## Commands

| Command | Description |
| --- | --- |
| `[p]paranoia start @player1 @player2 @player3` | Start a game with at least 3 players. |
| `[p]paranoia answer @player` | Submit your answer for the current round. |
| `[p]paranoia status` | Show game progress and who still needs to answer. |
| `[p]paranoia stop` | Stop the active game. |
| `[p]paranoia addquestion <question>` | Add a custom server question. |
| `[p]paranoia questions` | List available questions. |
| `[p]paranoia tupperbox [true_or_false]` | View or toggle Tupperbox integration. |

## Requirements

- Red-DiscordBot 3.4.0 or newer.
- `Send Messages` in the game channel.
- Players should allow DMs from server members so they can receive questions.

## Data

Paranoia stores game data temporarily during active sessions, including player IDs, questions, and answers. Custom questions are stored per guild.
