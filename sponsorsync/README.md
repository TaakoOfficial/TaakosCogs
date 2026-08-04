# SponsorSync

SponsorSync is a provider-neutral membership ledger that reconciles subscription tiers to Discord roles. It supports manual grants, renewals, revocations, expiration grace periods, CSV bridges, automatic hourly reconciliation, and audit alerts.

## Setup

```text
[p]sponsorsync tier add gold @GoldSponsor
[p]sponsorsync alertchannel #sponsor-audit
[p]sponsorsync grace 3
[p]sponsorsync grant @Member gold 30 kofi order-123
```

Use `[p]sponsorsync importcsv` with an attached CSV containing `user_id,tier,provider,external_ref,expires_at`. Imports update the ledger; run `sponsorsync sync` to reconcile roles.

Provider labels and external references are opaque metadata. No Patreon, Ko-fi, GitHub, or Stripe secret is required, which keeps the first release usable with exports, webhooks handled elsewhere, or manual administration.

The bot needs Manage Roles, with its highest role above every mapped tier role.
