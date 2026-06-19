# Captcha

Button-and-modal role verification for Red-DiscordBot.

[Back to the cog catalog](../README.md)

## Install

```text
[p]repo add taakoscogs https://github.com/TaakoOfficial/TaakosCogs
[p]cog install taakoscogs Captcha
[p]load Captcha
```

## How It Works

1. A member presses **Verify**.
2. Captcha generates a new six-character code for that click.
3. Discord opens a modal with the code in its title.
4. The member enters the code.
5. Captcha gives them every role configured for that panel that they do not already have.

Only the latest active code is accepted. Incorrect and expired challenges require a
new button click, which always generates a different code from the member's previous
click on that panel.

## Post the Predefined Panel

```text
[p]captcha post #verification @Verified
[p]captcha post #verification @Verified @Member
```

Optionally provide a custom button label:

```text
[p]captcha post #verification @Verified @Member Complete Verification
```

Mention between one and ten roles first. Any remaining text becomes the button label.

## Attach to an Existing Message

The message must have been sent by the same bot and cannot contain unrelated buttons
or dropdowns.

```text
[p]captcha attach <message-link> @Verified
[p]captcha attach <message-link> @Verified @Member Verify Me
```

Message content and embeds are preserved; Captcha adds only its persistent button.

## Commands

| Command | Description |
| --- | --- |
| `[p]captcha` | Show setup information and the configured panel count. |
| `[p]captcha post <channel> <roles...> [label]` | Post the predefined verification embed. |
| `[p]captcha attach <message> <roles...> [label]` | Attach verification to an existing bot message. |
| `[p]captcha remove <message>` | Remove a configured verification button. |
| `[p]captcha list` | List configured captcha panels and roles. |

## Security

- Codes use cryptographically secure randomness and exclude ambiguous characters.
- A code is scoped to one server, panel, and member.
- Only the newest active code is accepted.
- Challenges expire after five minutes and are never stored persistently.
- Captcha refuses managed roles, roles above the bot, and roles with administrative or moderation permissions.
- Each panel can assign between one and ten roles.

## Requirements

- Red-DiscordBot 3.5.0 or newer.
- Bot permissions to `Send Messages` and `Embed Links` when posting a panel.
- Bot permission to `Read Message History` when attaching by message link.
- Bot permission to `Manage Roles`.
- The bot's highest role must be above the configured verification role.

## Data

Captcha stores panel message IDs, channel IDs, role IDs, and button labels. Verification
codes and user IDs are held transiently in memory for code rotation and active modal
validation, and are cleared when the cog unloads.
