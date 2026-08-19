# OpsRoom

OpsRoom provides a Discord-native incident-response workflow for hosting teams, game communities, and internal operations.

When DecisionLedger is loaded, unresolved incident actions can be imported manually or after incident resolution. Configure the handoff from DecisionLedger; OpsRoom has no hard dependency on it.

SecretSentinel can optionally open a rate-limited credential-response incident through OpsRoom. The incident contains detector types and Discord location IDs, never the matched credential value.

## Setup

```text
[p]opsroom category "Active Incidents"
[p]opsroom archivecategory "Incident Archive"
[p]opsroom responserole @Responders
[p]opsroom updatechannel #service-updates
```

## Incident flow

```text
[p]opsroom create sev2 API unavailable
[p]opsroom commander @Member
[p]opsroom note Investigating upstream timeouts
[p]opsroom status identified Database connection pool exhausted
[p]opsroom action @Member Increase pool monitoring coverage
[p]opsroom status resolved Service is stable
[p]opsroom postmortem
[p]opsroom archive
```

Severity values are `sev1` through `sev4`; statuses are `investigating`, `identified`, `monitoring`, and `resolved`. Stakeholder summaries can be published separately from internal timeline notes.

The bot needs Manage Channels for incident creation/archive and Attach Files for Markdown postmortems.
