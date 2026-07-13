# ComponentsV2Bridge

ComponentsV2Bridge is a companion cog for [AAA3A's EmbedUtils](https://github.com/AAA3A-AAA3A/AAA3A-cogs/tree/master/embedutils). It keeps EmbedUtils updateable while adding Discord Components V2 posting and a Red-Web-Dashboard editor.

Red 3.5.21 or newer is required because that release moved to discord.py 2.6, which introduced `LayoutView` and Components V2 support.

## Features

- Accepts native Discord Components V2 JSON or YAML.
- Converts EmbedUtils `content`, `embed`, and `embeds` payloads to V2 text displays, containers, media galleries, separators, and link buttons.
- Posts existing EmbedUtils stored embeds with `[p]cv2 stored`.
- Sends, edits, and downloads V2 messages from Discord.
- Builds, previews, converts, and sends layouts from Red-Web-Dashboard.
- Rejects enabled custom-ID buttons and selects because they require application-specific callbacks. Link and premium buttons work.

## Commands

- `[p]cv2 json [channel] <payload>`
- `[p]cv2 yaml [channel] <payload>`
- `[p]cv2 edit <message> [json|yaml] <payload>`
- `[p]cv2 download <message>`
- `[p]cv2 stored <name> [channel] [global_level]`
- `[p]cv2 dashboard`

If the payload is omitted from the JSON or YAML commands, attach a UTF-8 `.json`, `.yaml`, `.yml`, or `.txt` file.

## Native example

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

Discord permanently marks a message as Components V2. Components V2 messages cannot use legacy `content` or `embeds`; this bridge translates them into V2 components instead.
