# Changelog

## 1.2.1

- Renamed the repository package folder from `FiveMStatus` to `fivemstatus` to match Red cog naming standards.
- New installs should use `[p]cog install taakoscogs fivemstatus` and `[p]load fivemstatus`.
- Existing server status panel settings are preserved because the cog's Config identifier did not change.

## 1.2.0

- Added native `/fivemstatus` subcommands for the complete prefix command group.

## 1.1.0

- Added `[p]fivem joincode`, with `cfxjoin` and `cfxcode` aliases, to set the Join Server button from a CFX join code or URL.
- Changed the panel's connect button label to `Join Server`.
- Kept automatic `cfx.re/join` buttons available for configured CFX join-code servers, even while the server is offline.

## 1.0.0

- Initial FiveM status panel cog.
- Added live status message refreshes, FiveM endpoint polling, player counts, connect command, restart countdowns, observed uptime, custom images, and link buttons.
