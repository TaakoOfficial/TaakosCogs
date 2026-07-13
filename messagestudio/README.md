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
- Direct channel sending with mentions suppressed.

The editor is self-contained. It does not load or communicate with message.style or Merlin's API.

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
- `[p]embed tools color|timestamp|validate ...`
- `[p]embed dashboard` and `[p]embed migratefromphen`

Original aliases such as `fromjson`, `fromyaml`, `gist`, `hastebin`, `storeembed`, `post`, and `webhook` are retained. The group is also available through `[p]embedutils`, `[p]messagestudio`, or `[p]cv2`.

If a payload is omitted from the JSON or YAML commands, attach a UTF-8 `.json`, `.yaml`, `.yml`, or `.txt` file. Native Components V2 and standard Discord `content`, `embed`, and `embeds` payloads are auto-detected.

## Native Example

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

Link and premium buttons are safe because Discord handles their actions. Enabled custom-ID buttons and select menus require application-specific callbacks, so arbitrary versions are rejected rather than sending controls that fail when clicked.

## Credits

The visual editor's component-card workflow and split editor/preview layout are inspired by Merlin Fuchs' MIT-licensed [Embed Generator](https://github.com/merlinfuchs/embed-generator). This cog contains an independent, dependency-free dashboard implementation tailored to Red-Web-Dashboard.
