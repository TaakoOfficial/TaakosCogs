# ForumFlow

ForumFlow turns Discord forum channels into managed support or knowledge workflows. New posts receive persistent controls, can be claimed by staff, moved through lifecycle states, marked stale, and closed with an accepted answer.

## Setup

```text
[p]forumflow addforum #help-forum
[p]forumflow staffrole @Support
[p]forumflow logchannel #support-logs
```

Create forum tags named `Open`, `Claimed`, `Waiting`, `Solved`, and `Stale` if you want automatic tag changes. ForumFlow preserves unrelated tags.

## Main commands

- `[p]forumflow claim` — claim the current post.
- `[p]forumflow state <state>` — change its lifecycle state.
- `[p]forumflow accept <message>` — accept an answer and solve the post.
- `[p]forumflow queue [state]` — inspect a queue.
- `[p]forumflow markstale` — apply the configured stale threshold.
- `[p]forumflow export` — export lifecycle records.

The bot needs Send Messages and Manage Threads in configured forums. The dashboard configures staff/log policy and shows queue totals.

ForumFlow stores IDs and workflow metadata described in `info.json`; it does not copy full thread contents into Config.
