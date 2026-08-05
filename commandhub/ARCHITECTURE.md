# CommandHub architecture

CommandHub separates persistent configuration, command discovery, conversion, invocation, UI sessions, and optional integrations. `CommandHub` is the orchestration and service layer; both chat commands and dashboard code call those services so validation is not duplicated.

## Data and control flow

1. `HubConfigStore` migrates and loads guild configuration through Red Config.
2. `CommandRegistry` walks Red prefix/hybrid commands and the Discord application-command tree once, normalizing leaves into `HubCommand` records. Full nested names are retained.
3. Enabled hubs are represented by guild-scoped `app_commands.Command` objects. Configuration edits update the local tree and enter a per-guild debouncer; only the sync worker performs network synchronization.
4. A hub callback creates one bounded `HubView`. It resolves assignments against the cache, evaluates visibility, and paginates to Discord's 25-option limit.
5. `ArgumentModal` collects at most five inputs per step. The converter resolves and validates values against the real guild.
6. `InvocationEngine` rechecks hub and command gates. Prefix and hybrid commands use `Context.from_interaction` plus normal `bot.invoke`; application commands use the public callback with its real cog binding after Discord's check adapter, then dispatch through local, cog, parent, and tree error handlers. Unsupported schemas remain visible only when configured and are never invoked by bypassing checks.

## Lifecycle and concurrency

Registry refreshes and guild syncs use locks. Sync debounce tasks are unique per guild. Cog unload cancels pending work, removes only owned local tree entries, and stops active views. Views expire after ten minutes, disable controls when possible, and are not registered as persistent views.

Repeat history is capped at 1,000 in-memory user/guild records. Persistence is off by default and only scalar records are written. Parameters whose names indicate secrets are neither displayed nor persisted/repeated.

## Extension points

The SlashLink adapter is duck typed and requires three explicit public methods; an incompatible SlashLink disables only that adapter. Dashboard integrations should call `list_hubs_service`, `create_hub_service`, `update_hub_service`, `delete_hub_service`, `discoverable_commands_service`, `assign_command_service`, and `sync_guild`.
