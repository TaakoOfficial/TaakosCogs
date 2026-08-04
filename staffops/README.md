# StaffOps

StaffOps coordinates volunteer or staff coverage directly in Discord: clocked shifts, availability, leave review, an ordered on-call rotation, handoffs, and hour reports.

## Setup

```text
[p]staffops staffrole @Staff
[p]staffops logchannel #staff-operations
```

## Main commands

- `[p]staffops clockin [note]` / `[p]staffops clockout [note]`
- `[p]staffops active` and `[p]staffops report [days]`
- `[p]staffops availability <text>` and `[p]staffops roster`
- `[p]staffops leave <until> [reason]` and `[p]staffops reviewleave <id> <approve|deny>`
- `[p]staffops oncall add|remove|rotate`
- `[p]staffops handoff [member] <note>`
- `[p]staffops export`

Staff need the configured role; reviewers need Manage Server. The bot needs Send Messages, Embed Links, and Attach Files for exports.

Availability is intentionally free-form so teams can use their own timezone and rota conventions.
