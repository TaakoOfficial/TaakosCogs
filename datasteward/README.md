# DataSteward

DataSteward provides bounded message-retention policies and a privacy-request workflow. It starts disabled and dry-run-first.

## Retention safety flow

```text
[p]datasteward policy set #temporary-chat 30
[p]datasteward preview
[p]datasteward mode dry-run
```

After reviewing previews, enforcement requires explicit confirmation:

```text
[p]datasteward mode enforce ENFORCE
[p]datasteward run DELETE
```

Scheduled enforcement runs every six hours only while enforce mode is active. Each channel is capped at 250 candidates per run, pinned messages are always preserved, and the dashboard cannot enable enforcement or trigger deletion.

Members can open `access`, `correction`, or `deletion` workflow requests with `[p]datasteward request`. These requests notify configured staff; they do not automatically invoke other cogs' privacy handlers.

The bot needs Read Message History and Manage Messages in policy channels.
