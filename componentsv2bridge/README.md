# ComponentsV2Builder

ComponentsV2Builder is a standalone visual builder and Discord command suite for Components V2 messages. It does not require EmbedUtils or any external web service.

Red 3.5.21 or newer is required because that release moved to discord.py 2.6, which introduced `LayoutView` and Components V2 support.

## Visual Dashboard Builder

Open the builder with `[p]cv2 dashboard`. Its interface is inspired by [Merlin Fuchs' Embed Generator](https://github.com/merlinfuchs/embed-generator) and runs entirely inside Red-Web-Dashboard.

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

## Discord Commands

- `[p]cv2 json [channel] <payload>`
- `[p]cv2 yaml [channel] <payload>`
- `[p]cv2 edit <message> [json|yaml] <payload>`
- `[p]cv2 download <message>`
- `[p]cv2 dashboard`

If a payload is omitted from the JSON or YAML commands, attach a UTF-8 `.json`, `.yaml`, `.yml`, or `.txt` file. Standard legacy Discord `content`, `embed`, and `embeds` payloads can also be converted without requiring another cog.

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

Discord permanently marks a message as Components V2. A V2 message cannot use legacy `content` or `embeds`, so this cog converts legacy fields into Text Displays and Containers.

## Supported Interactive Components

Link and premium buttons are safe because Discord handles their actions. Enabled custom-ID buttons and select menus require application-specific callbacks, so arbitrary versions are rejected rather than sending controls that fail when clicked.

## Credits

The visual editor's component-card workflow and split editor/preview layout are inspired by Merlin Fuchs' MIT-licensed [Embed Generator](https://github.com/merlinfuchs/embed-generator). This cog contains an independent, dependency-free dashboard implementation tailored to Red-Web-Dashboard.
