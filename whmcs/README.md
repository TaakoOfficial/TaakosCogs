# whmcs

WHMCS billing, client, and support integration for Red-DiscordBot.

[Back to the cog catalog](../README.md)

## Install

```text
[p]repo add taakoscogs https://github.com/TaakoOfficial/TaakosCogs
[p]cog install taakoscogs whmcs
[p]load whmcs
```

## Dashboard

This cog includes standalone Red-Web-Dashboard integration. Server managers can use the dashboard to view visible commands and the current server configuration when Red-Web-Dashboard is installed.

## Highlights

- Browse, view, and search WHMCS clients.
- View invoices, payment history, balances, and account credit tools.
- View and reply to support tickets from Discord.
- Optional ticket-specific Discord channels with auto-reply integration.
- Role-based access levels for admin, billing, support, and read-only users.
- Private API-secret entry through password fields in Red-Web-Dashboard or slash-command options.

## Command Areas

| Area            | Example Commands                                                                                                                          |
| --------------- | ----------------------------------------------------------------------------------------------------------------------------------------- |
| Admin setup     | `[p]whmcs admin config`, `[p]whmcs admin test`, `[p]whmcs admin permissions`                                                              |
| Ticket channels | `[p]whmcs admin channels view`, `[p]whmcs admin channels set category <id>`, `[p]whmcs admin channels enable`                             |
| Clients         | `[p]whmcs client list`, `[p]whmcs client view <id>`, `[p]whmcs client search <term>`                                                      |
| Billing         | `[p]whmcs billing invoices <client_id>`, `[p]whmcs billing invoice <invoice_id>`, `[p]whmcs billing credit <client_id> <amount> <reason>` |
| Support         | `[p]whmcs support tickets`, `[p]whmcs support ticket <ticket_id>`, `[p]whmcs support reply <ticket_id> <message>`                         |

## Setup Notes

1. Create WHMCS API credentials in WHMCS.
2. Open the WHMCS Dashboard page or use `/whmcs admin config` to enter the API secret and optional access key. Visible prefix messages are deliberately rejected for credentials.
3. Run `[p]whmcs admin test`.
4. Configure role permissions with `[p]whmcs admin permissions`.
5. Optional: configure ticket categories with `[p]whmcs admin channels`.

## Requirements

- Red-DiscordBot 3.0.0 or newer.
- `aiohttp>=3.8.0`.
- A working WHMCS installation with API access.
- HTTPS access to your WHMCS endpoint.
- Discord permissions for any channels/categories the integration manages.

## Data

WHMCS stores guild-specific API configuration, including credentials, in Red's per-guild Config alongside permission settings, rate-limit settings, and optional ticket-channel mappings. It connects to your WHMCS API when commands require external client, billing, or support data. Credentials are redacted from logs.
