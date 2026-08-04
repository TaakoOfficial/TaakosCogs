# CommunityPulse

CommunityPulse measures onboarding, activation, retention, churn, role adoption, and inactivity without storing message content.

Tracking starts disabled so administrators can review the data statement first:

```text
[p]communitypulse enable
[p]communitypulse thresholds 5 30
```

## Reports

- `overview` — current totals and activation rate.
- `funnel` — joined → first message → activated → retained.
- `inactive [days]` — staff re-engagement queue.
- `cohorts` — join-month activation and retention.
- `roles` — adoption of non-managed roles.
- `export` — member-level timestamps/counts as CSV.

Message activity is buffered in memory and flushed every five minutes to reduce Config I/O. Only counts, timestamps, user IDs, and current non-managed role IDs are stored. Server Members intent is needed for complete join/leave and role information; Message Content intent is not required for counting messages received by the bot.
