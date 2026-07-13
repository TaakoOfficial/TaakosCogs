# MessageStudio

MessageStudio is a standalone EmbedUtils-compatible command suite for legacy embeds and Components V2 messages. It does not require EmbedUtils or any external web service.

Red 3.5.21 or newer is required because that release moved to discord.py 2.6, which introduced `LayoutView` and Components V2 support.

## Visual Dashboard Builder

Open the builder with `[p]embed dashboard` (the `[p]cv2` alias also works). Its interface is inspired by [Merlin Fuchs' Embed Generator](https://github.com/merlinfuchs/embed-generator) and runs entirely inside Red-Web-Dashboard.

The builder provides:

- Visual component cards with duplication, deletion, and reordering.
- Text Displays with Discord Markdown.
- Containers with accent colors, spoilers, and nested components.
- Sections with multiple text blocks and a thumbnail or link-button accessory.
- Media Galleries, Separators, and Action Rows containing link buttons.
- A live Discord-style preview and component/text limit counters.
- JSON import, editing, copying, and downloading.
- Browser-local draft recovery without server-side storage.
- Direct channel sending with a clear mention policy selector.
- Guild saved-message creation with optional moderator locking directly from the builder.
- Every message-side Components V2 type: Action Rows, every button style, all five select families, Sections, Text Displays, Thumbnails, Media Galleries, uploaded Files, Separators, and Containers.
- Persistent role, channel-post, and interaction-reply actions for custom buttons and selects.
- A separate Legacy Embeds mode with content, up to 10 embeds, fields, authors, footers, media, timestamps, and classic Action Row controls.
- Dashboard delivery as either the MessageStudio bot or a managed webhook with a custom username and avatar.
- Compact, labeled message-type and component controls that wrap cleanly on smaller screens.
- Progressive advanced sections and hover/focus hints that explain component types and technical fields without crowding the editor.
- Utility cards for profile/server image assets, colors, all Discord timestamp styles, snowflake dates, text limits, JSON formatting, and Markdown previews.

The editor is self-contained. It does not load or communicate with message.style or Merlin's API.

### Profile and Server Asset Tools

The dashboard **Utility Tools** page shows the current server's icon, banner, invite splash, and discovery splash with full-size Open and Copy URL controls. Enter a Discord user ID to retrieve the latest display avatar, global avatar, server-specific avatar, profile banner, and accent color that Discord makes available to the bot.

Profile lookups are available only from a server dashboard page and use the same Manage Server, Red admin, or bot-owner permission gate as the message builder. Missing optional assets are shown as **Not set** instead of falling back to a misleading image.

### Legacy Embed Mode

Choose **Legacy embeds** from the message-type selector to build a traditional Discord message. Legacy mode sends real `content` and `embeds` and can also include classic Action Rows containing buttons or any supported select menu. Those custom-ID controls use the same persistent action system as V2 controls.

Legacy JSON can use standard Discord `content`, `embed`, and `embeds` keys. When classic controls are included, place their Action Rows in `components`; MessageStudio detects the payload as legacy when it also contains content/embeds, or when `"legacy": true` is present for a components-only message.

A ready-to-send example is available at [`examples/legacy_components_showcase.json`](./examples/legacy_components_showcase.json).

### Dashboard Webhook Delivery

Use the **Send as** selector below the editor to choose **Custom webhook identity**. Enter a username and optional HTTP(S) avatar URL, choose the destination channel, and send normally. The dashboard reuses a bot-owned MessageStudio webhook in that channel or creates one when needed.

Webhook delivery requires the dashboard user and bot to have **Manage Webhooks** in the selected text channel. The **Mentions** selector applies to both bot and webhook delivery, and persistent button/select actions are retained on the resulting message.

The mention selector defaults to **Users and roles**, which allows normal member and role pings but blocks `@everyone` and `@here`. Choose **All mentions** when those broadcast mentions are intentional, or **No mentions** for a silent message.

All command input paths—JSON, YAML, attached files, stored messages, message copying, editing, and webhook posting—accept traditional legacy embeds as well as Components V2 payloads.

## EmbedUtils-Compatible Commands

- `[p]embed [channel_or_message] [color] <title> <description>`
- `[p]embed json|yaml [channel_or_message] [payload]`
- `[p]embed fromfile|yamlfile [channel_or_message]`
- `[p]embed pastebin [channel_or_message] <url>`
- `[p]embed message [channel_or_message] [message] [index] [include_content]`
- `[p]embed download [message] [index] [include_content]`
- `[p]embed edit <message> <json|yaml|jsonfile|yamlfile|pastebin|message> [data]`
- `[p]embed store|unstore|list|info|downloadstored ...`
- `[p]embed poststored ...` and `[p]embed postwebhook ...`
- `[p]embed commands`
- `[p]embed actions [message]` and `[p]embed actions clear <message>`
- `[p]embed tools color|timestamp|validate ...`
- `[p]embed dashboard` and `[p]embed migratefromphen`

Original aliases such as `fromjson`, `fromyaml`, `gist`, `hastebin`, `storeembed`, `post`, and `webhook` are retained. The group is also available through `[p]embedutils`, `[p]messagestudio`, or `[p]cv2`.

If a payload is omitted from the JSON or YAML commands, attach a UTF-8 `.json`, `.yaml`, `.yml`, or `.txt` file. Native Components V2 and standard Discord `content`, `embed`, and `embeds` payloads are auto-detected.

## Native Example

A complete ready-to-send example is available at [`examples/components_v2_showcase.json`](./examples/components_v2_showcase.json). It demonstrates every portable message-side component, interactive controls, media, and a real uploaded file.

```json
{
  "flags": 32768,
  "components": [
    {
      "type": 17,
      "accent_color": 5793266,
      "components": [
        {"type": 10, "content": "## Components V2"},
        {"type": 10, "content": "A native Components V2 message."},
        {"type": 14, "divider": true, "spacing": 1},
        {
          "type": 1,
          "components": [
            {
              "type": 2,
              "style": 5,
              "label": "Discord documentation",
              "url": "https://discord.com/developers/docs/components/reference"
            }
          ]
        }
      ]
    }
  ]
}
```

Discord permanently marks a message as Components V2. A V2 message cannot use legacy `content` or `embeds`; MessageStudio preserves legacy behavior while using `LayoutView` for native V2 payloads.

## Supported Interactive Components

MessageStudio supports link, premium, primary, secondary, success, and danger buttons plus string, user, role, mentionable, and channel selects. Custom-ID controls can use persistent actions; controls without actions accept a configurable fallback response so users never receive an interaction failure.

Add an `actions` array to a custom-ID button or select. The dashboard exposes the same settings as visual **Persistent actions** cards:

```json
{
  "type": 2,
  "style": 1,
  "label": "Get announcements",
  "custom_id": "toggle_announcements",
  "actions": [
    {"type": "toggle_role", "role_id": "123456789012345678"},
    {
      "type": "send_message",
      "channel_id": "234567890123456789",
      "content": "{user} updated their announcement role."
    },
    {"type": "reply", "content": "Your role was updated.", "ephemeral": true}
  ]
}
```

Available action types are:

- `add_role`, `remove_role`, and `toggle_role`, each with a fixed `role_id`.
- `send_message`, with a destination `channel_id` and `content`.
- `reply`, with `content` and an optional `ephemeral` boolean (defaults to `true`).

Any action may include `"values": ["option_1"]` so it only runs when a string-select value matches. Text supports `{user}`, `{user_id}`, `{server}`, `{channel}`, `{value}`, and `{values}` placeholders. Allowed mentions are disabled for action output.

Role actions are self-role controls: the member clicking the component is the member changed. The moderator configuring the action must have Manage Roles and be above the configured role; MessageStudio also requires the bot to have Manage Roles and remain above that role when clicked. Managed roles and `@everyone` are rejected. Action bindings are stored against the sent message ID and restored from Red Config after restarts. Deleting the Discord message removes its binding; moderators can also disable it with `[p]embed actions clear <message>`.

Discord's Label, File Upload input, Radio Group, Checkbox Group, and Checkbox components are modal-only. They cannot be included in a Components V2 message and are therefore outside the message builder.

## Credits

The visual editor's component-card workflow and split editor/preview layout are inspired by Merlin Fuchs' MIT-licensed [Embed Generator](https://github.com/merlinfuchs/embed-generator). This cog contains an independent, dependency-free dashboard implementation tailored to Red-Web-Dashboard.
