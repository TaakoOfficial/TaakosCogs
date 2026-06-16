# Applications

Configurable application forms for Red-DiscordBot servers.

[Back to the cog catalog](../README.md)

## Install

```text
[p]repo add taakoscogs https://github.com/TaakoOfficial/TaakosCogs
[p]cog install taakoscogs Applications
[p]load Applications
```

## Highlights

- Create multiple named application forms per server.
- Post application panels with buttons or a dropdown menu.
- Let users apply with `[p]apply <name>` or by clicking a panel.
- Ask questions in DMs with text, yes/no, choice, and attachment prompts.
- Optionally collect up to five non-attachment questions in a native Discord modal.
- Log submitted responses with accept and deny buttons, plus optional voting.
- Give or remove roles when users apply, submit, get accepted, or get denied.
- Restrict applications by whitelist and blacklist roles.
- Configure manager roles, cooldowns, duplicate-pending behavior, threads, and notifications.
- Export responses to CSV or back up all application data to JSON.
- Create simple button polls with `[p]apppoll`.

## Quick Setup

```text
[p]application create staff "Staff Application" #applications
[p]application question add staff "Why do you want to join staff?" text true
[p]application question add staff "Are you 18 or older?" boolean true
[p]application question add staff "Pick your timezone" choice true EST, CST, MST, PST, other
[p]application config form staff modal
[p]application panel #apply buttons staff
```

Give a role when the application is approved:

```text
[p]application role set accept add staff @Staff
```

Remove a role when the application is approved:

```text
[p]application role set acceptremove add staff @Applicant
```

## Main Commands

| Command                                                      | Description                                                             |
| ------------------------------------------------------------ | ----------------------------------------------------------------------- |
| `[p]apply <name>`                                            | Start an application from chat.                                         |
| `[p]application create <name> <description> <channel>`       | Create a new application form.                                          |
| `[p]application delete <name>`                               | Delete an application and its stored responses.                         |
| `[p]application list`                                        | List configured applications.                                           |
| `[p]application view <name>`                                 | Show settings and questions for one application.                        |
| `[p]application panel <channel> [buttons_or_select] [names]` | Post an application panel. Use comma-separated names for multiple apps. |
| `[p]application send <name> <member>`                        | Send an application directly to a member, bypassing role restrictions.  |
| `[p]application responses <name> [status] [member]`          | List response IDs and statuses.                                         |
| `[p]application response <name> <response_id>`               | Show one response.                                                      |
| `[p]application export <name> [status]`                      | Export responses to CSV.                                                |
| `[p]application backup`                                      | Export all application, panel, and poll data to JSON.                   |

Valid response statuses are `all`, `pending`, `accepted`, and `denied`.

## Question Commands

| Command                                                                     | Description                        |
| --------------------------------------------------------------------------- | ---------------------------------- |
| `[p]application question add <name> <question> [type] [required] [choices]` | Add a question.                    |
| `[p]application question remove <name> <position>`                          | Remove a question by position.     |
| `[p]application question list <name>`                                       | List questions for an application. |

Question types:

| Type         | Behavior                                    |
| ------------ | ------------------------------------------- |
| `text`       | Applicant replies with a normal DM message. |
| `boolean`    | Applicant clicks Yes or No.                 |
| `choice`     | Applicant picks one configured choice.      |
| `attachment` | Applicant sends an attachment or link.      |

Choice questions use comma-separated choices. Add `other` to allow a custom typed answer.

```text
[p]application question add staff "Pick your platform" choice true PC, Xbox, PlayStation, other
```

Applications use the DM flow by default. Modal mode supports up to five `text`, `boolean`,
or `choice` questions. Boolean questions and fixed choices use native modal dropdowns on
current Red installations. Choice questions with `other` retain a text field so applicants
can enter a custom answer. Attachment questions require DM mode.

## Config Commands

| Command                                                                 | Description                                                          |
| ----------------------------------------------------------------------- | -------------------------------------------------------------------- |
| `[p]application config channel <name> <channel>`                        | Set the response logging channel.                                    |
| `[p]application config status <name> <open_or_close>`                   | Open or close an application.                                        |
| `[p]application config color <name> <color>`                            | Set the embed color, such as `#5865F2`.                              |
| `[p]application config cooldown <name> <minutes>`                       | Set the cooldown before a user can apply again.                      |
| `[p]application config multiple <name> <true_or_false>`                 | Allow or block multiple pending responses from one user.             |
| `[p]application config form <name> <dm_or_modal>`                       | Choose the DM questionnaire or native modal flow.                    |
| `[p]application config thread <name> <true_or_false> [template]`        | Enable response threads and set the thread name template.            |
| `[p]application config notifications <name> <true_or_false>`            | Enable or disable notifications.                                     |
| `[p]application config notifychannels <name> <channels>`                | Set extra notification channels by mention or ID.                    |
| `[p]application config notifyroles <name> <roles>`                      | Set notification ping roles by mention or ID.                        |
| `[p]application config notifytarget <name> <channel\|thread\|both>`     | Choose where notification roles are pinged.                          |
| `[p]application config voting <name> <true_or_false> [threshold]`       | Enable or disable reviewer voting.                                   |
| `[p]application config button <name> <label_or_emoji_or_style> <value>` | Configure the panel button.                                          |
| `[p]application config message <name> <type> <message>`                 | Configure panel, notification, completion, accept, or deny messages. |

Button styles are `green`, `red`, `gray`, and `blurple`.

Message types are:

| Type           | Used For                                     |
| -------------- | -------------------------------------------- |
| `panel`        | Text shown on a one-application panel.       |
| `notification` | Message posted when a response is submitted. |
| `completion`   | DM sent to the applicant after submission.   |
| `accept`       | DM sent when staff accepts a response.       |
| `deny`         | DM sent when staff denies a response.        |

## Role Commands

Use this command shape for all application role settings:

```text
[p]application role set <role_type> <add_or_remove> <application> <roles>
```

Role types:

| Role Type      | Behavior                                                  |
| -------------- | --------------------------------------------------------- |
| `manager`      | Allows a role to review responses and use response tools. |
| `whitelist`    | Only members with one of these roles can apply.           |
| `blacklist`    | Members with one of these roles cannot apply.             |
| `apply`        | Role given when a member starts an application.           |
| `submit`       | Role given when a member submits an application.          |
| `accept`       | Role given when a response is approved.                   |
| `acceptremove` | Role removed when a response is approved.                 |
| `deny`         | Role given when a response is denied.                     |
| `denyremove`   | Role removed when a response is denied.                   |

Examples:

```text
[p]application role set manager add staff @HR
[p]application role set whitelist add staff @Verified
[p]application role set blacklist add staff @Muted
[p]application role set apply add staff @Applicant
[p]application role set accept add staff @Staff
[p]application role set acceptremove add staff @Applicant
```

View configured role lists:

```text
[p]application role view staff
```

## Review Workflow

When a user submits an application, the cog posts a response embed in the configured response channel.

Staff with Manage Server or an application manager role can:

- Click `Accept` to approve the response and optionally enter a reason.
- Click `Deny` to reject the response and optionally enter a reason.
- Click `Upvote`, `Neutral`, or `Downvote` when review voting is enabled.

Accepting or denying a response updates the response embed, stores the reviewer and reason, DMs the applicant, and runs the configured role actions.
Disabling review voting removes the voting buttons from existing and future response messages.

## Poll Commands

| Command                                                                | Description                              |
| ---------------------------------------------------------------------- | ---------------------------------------- |
| `[p]apppoll create <channel> <question> \| <option one>, <option two>` | Create a button poll.                    |
| `[p]apppoll close <poll_id>`                                           | Close a poll and disable voting buttons. |

Example:

```text
[p]apppoll create #staff Should we open helper apps? | Yes, No, Wait
```

## Placeholders

The cog supports these placeholders in panel, notification, completion, accept, deny, and thread templates:

| Placeholder             | Value                                   |
| ----------------------- | --------------------------------------- |
| `{application}`         | Application display name.               |
| `{application_key}`     | Stored application key.                 |
| `{description}`         | Application description.                |
| `{server}` or `{guild}` | Server name.                            |
| `{user}`                | Applicant username.                     |
| `{user_name}`           | Applicant server display name.          |
| `{user_mention}`        | Applicant mention.                      |
| `{user_id}`             | Applicant user ID.                      |
| `{response_id}`         | Response ID.                            |
| `{status}`              | Response status.                        |
| `{reviewer}`            | Reviewer username.                      |
| `{reviewer_mention}`    | Reviewer mention.                       |
| `{reason}`              | Review reason, or `No reason provided.` |

## Requirements

- Red-DiscordBot 3.5.0 or newer.
- `Send Messages`, `Embed Links`, and `Read Message History` in application channels.
- `Create Public Threads` and `Send Messages in Threads` if response threads or thread notification pings are enabled.
- `Manage Roles` if the cog should give or remove roles.
- The bot role must be higher than any role it gives or removes.
- Users need open DMs with the bot for DM-mode applications. If the initial DM fails, the cog tells the applicant to enable DMs instead of reporting that the form was sent.
- Manage Server permission, Red admin, bot owner, or a configured manager role for review and management actions.

## Data

Applications stores per-guild application configuration, panel message IDs, poll records, applicant user IDs, application answers, reviewer user IDs, vote records, and role/channel IDs needed to operate the configured workflows.
