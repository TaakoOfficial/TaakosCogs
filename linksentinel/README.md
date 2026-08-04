# LinkSentinel

LinkSentinel checks important community links before members discover they are broken. It records HTTP results, redirects, response time, TLS certificate expiry, failures, and recoveries.

## Setup

```text
[p]linksentinel alertchannel #resource-alerts
[p]linksentinel interval 24
[p]linksentinel add https://example.com/docs Documentation
[p]linksentinel discover #resources 200
[p]linksentinel scan
```

## Commands

- `add`, `remove`, and `discover` manage the inventory.
- `scan` checks immediately; scheduled checks use the configured interval.
- `list [all|healthy|failed]` shows health.
- `export` generates CSV results.

Checks use bounded timeouts, at most four concurrent requests per guild, and a dedicated user agent. URLs containing credentials are rejected. The cog follows up to eight redirects and does not download full response bodies for analysis.

The bot needs Read Message History for discovery and Send Messages/Embed Links for alerts.

## Requirements

- Red-DiscordBot 3.5.0 or newer.
- Python 3.9 or newer.
- `aiohttp>=3.8.0`; Red's Downloader installs it automatically from the cog metadata.
- The bot host must be able to make outbound HTTP(S) requests to monitored URLs.
