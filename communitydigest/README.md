# CommunityDigest

CommunityDigest produces scheduled, link-rich recaps without requiring an AI API. It summarizes message volume, contributor counts, active forum posts, high-reaction discussions, and commonly shared links.

## Setup

```text
[p]communitydigest source add #general
[p]communitydigest source add #help-forum
[p]communitydigest destination #weekly-recap
[p]communitydigest schedule 168 168
[p]communitydigest preview
```

`schedule <interval-hours> [lookback-hours]` enables automatic posting. Use `disable` to pause it and `run` to publish immediately.

The cog reads recent source messages while building a recap but stores neither message content nor author IDs. Contributor IDs exist only in temporary in-memory sets used to count unique contributors.

The bot needs View Channel, Read Message History, Send Messages, and Embed Links in the relevant channels.
