# SecretSentinel

SecretSentinel watches server messages for supported credential formats. It can delete the source message, notify a private staff channel, and DM the author with rotation advice. Alerts identify the credential type but never copy the matched value or surrounding message text.

```text
[p]secretsentinel setup #security-alerts
[p]secretsentinel status
[p]secretsentinel selftest
[p]secretsentinel cooldown 60
[p]secretsentinel detector Stripe live key
[p]secretsentinel scanbot @WebhookRelay
[p]secretsentinel opsroom true
```

Small UTF-8 text attachments are scanned when attachment scanning is enabled. Files larger than 64 KiB and binary formats are skipped. Supported patterns include Discord bot tokens and webhooks, GitHub tokens, AWS access keys, Google API keys, Stripe live keys, and common private-key headers.

Detection is intentionally disabled after installation. Give the bot Manage Messages if deletion mode is used. Use `ignorechannel` and `ignorerole` for tightly controlled exceptions.

`setup` selects delete mode when the bot has Manage Messages and falls back to report-only mode otherwise. The default role and Administrator roles cannot be excluded. The self-test creates synthetic patterns internally, so staff never need to paste a real credential into Discord.

Duplicate staff alerts from the same author and detector types can be rate-limited without skipping deletion/report actions. Bot messages remain ignored unless a specific bot is opted in with `scanbot`. Individual detector categories can be disabled. With OpsRoom loaded, `opsroom true` opens at most one credential-response incident per 15 minutes and never includes the matched value.

No matched value, excerpt, message body, author ID, or finding history is stored by the cog.
