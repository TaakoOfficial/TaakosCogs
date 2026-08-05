# CommandHub

CommandHub turns configured groups of loaded bot commands into guild slash commands such as `/games`, `/admin`, and `/utility`. Opening a hub displays an interactive command browser with categories, 25-command pages, partial-match search, modal argument entry, confirmation gates, and optional repeat-last-command behavior.

The cog targets Red-DiscordBot 3.5, Python 3.11+, and modern Discord components. Hub commands are guild scoped by default, so changes propagate quickly and do not consume global command updates.

## Installation

From Red's Downloader:

```text
[p]repo add TaakosCogs https://github.com/TaakoOfficial/TaakosCogs
[p]cog install TaakosCogs commandhub
[p]load commandhub
```

The bot needs `applications.commands`, Send Messages, Embed Links, and Use Application Commands in the target guild. Administrators need Manage Server for normal management; registry refresh and explicit network sync are owner-only.

## Quick setup

```text
[p]commandhub create games
[p]commandhub category create games Trivia
[p]commandhub add games "trivia start"
[p]commandhub add games "trivia leaderboard"
[p]commandhub category move games Trivia "trivia start"
[p]commandhub category move games Trivia "trivia leaderboard"
[p]commandhub sync
```

Users can then run `/games`. Hub responses are ephemeral by default. Use `[p]commandhub set games ephemeral false` for a shared public browser; public browsers accept component interactions from other users, while ephemeral sessions remain bound to the opener.

## Administrator commands

- `[p]commandhub create <name>` validates and creates a hub.
- `[p]commandhub delete <name>` removes it.
- `[p]commandhub rename <old> <new>` renames its guild slash command.
- `[p]commandhub list` and `info <name>` inspect configuration.
- `[p]commandhub enable|disable <name>` controls registration.
- `[p]commandhub set <hub> <field> <value>` edits title, description, emoji, response mode, search, or repeat behavior.
- `[p]commandhub add <hub> "<qualified command>"` assigns a command.
- `[p]commandhub remove <hub> "<qualified command>"` removes an assignment.
- `[p]commandhub move <source hub> <destination hub> "<qualified command>"` moves it between hubs.
- `[p]commandhub commands <hub>` lists assignments, including unloaded ones.
- `[p]commandhub commandset <hub> <confirmation_required|hidden|disabled> <true|false> "<qualified command>"` applies a safety policy to one assignment.
- `[p]commandhub category create|delete <hub> <category>` manages categories. Non-empty categories cannot be deleted.
- `[p]commandhub category move <hub> <category> "<qualified command>"` recategorizes an assignment.
- `[p]commandhub registry`, `unsupported`, `syncstatus`, and owner-only `diagnose` report health.
- `[p]commandhub refresh` refreshes discovery; `[p]commandhub sync` immediately synchronizes the guild tree. Both are owner-only.

If the same qualified name exists in more than one source, prefix it with `prefix:`, `hybrid:`, `application:`, or `slashlink:` when assigning it.

## User workflow

Choose a category and page, select a command, then complete any argument modal. A command with more than five parameters opens sequential modals and shows progress. Search ranks exact names first, then name prefixes, name substrings, descriptions, and category/cog metadata. Configuration can hide unavailable commands or show their reason. Checks are repeated immediately before invocation.

Commands whose qualified names contain common destructive actions (ban, kick, purge, delete, reset, clear, or transfer) default to confirmation required. This is only a conservative initial hint: administrators explicitly mark an assignment safe with `commandset ... confirmation_required false`, or require confirmation for any other command. Confirmation views last 60 seconds, redact sensitive-looking argument names, and are required again when repeating.

## Permissions and invocation safety

Hub role, channel, user-permission, and bot-permission gates run when a hub opens and again before invocation. Original command visibility/check logic runs before display where the framework supports it and always runs again before execution. Disabled or unloaded commands are not silently removed from configuration.

Prefix and hybrid commands are invoked with a real `Context.from_interaction` and Red's normal `bot.invoke` pipeline. This retains global/cog/command checks, cooldowns, max concurrency, hooks, converters, and error dispatch. No fake Discord message is sent. Commands that require real message attachments, replies, references, or rely on original prefix text may be incompatible and should remain disabled in CommandHub.

Native application commands use the real component/modal interaction, Discord.py's public callback with its real cog binding, and application-command check/error machinery. Parameter shapes that cannot be safely represented are marked unsupported. CommandHub never fabricates an interaction or calls a callback while skipping checks.

## Supported parameters

String/remainder text, integer, float, boolean, member/user, role, guild channel, text channel, voice channel, mentionable, choices, and optional parameters are normalized. Entity inputs accept a mention, raw Discord ID, or an exact unambiguous name. Greedy collection metadata is retained but currently reported as unsupported because a modal text field cannot reproduce Red's token-by-token conversion safely. Unusual custom converters, attachments, unions that are not optional, and framework-specific transforms are likewise reported rather than discarded.

Discord modals allow five inputs. Commands with more parameters use multiple steps. A validation error is ephemeral and leaves the original browser usable so the user can select the command and retry.

## SlashLink integration

SlashLink is optional and is found only through `bot.get_cog("SlashLink")`. A compatible version must expose:

```python
async def get_linked_commands() -> list[Any]: ...
async def get_command_schema(qualified_name: str) -> Any: ...
async def invoke_linked_command(interaction, qualified_name: str, arguments: dict[str, Any]) -> None: ...
```

If those methods are absent, CommandHub logs one warning and disables only SlashLink discovery/invocation. The current standalone SlashLink cog in this repository does not expose that API; its ordinary gateway behavior is unaffected.

## Dashboard and developer API

Dashboard support is optional. The included page presents a safe inventory and intentionally delegates mutations to the same service layer used by Discord commands. Integrations can call:

```python
await cog.list_hubs_service(guild_id)
await cog.create_hub_service(guild_id, name, title="Game Commands")
await cog.update_hub_service(guild_id, name, {"allowed_roles": [role_id]})
await cog.delete_hub_service(guild_id, name)
await cog.discoverable_commands_service()
await cog.assign_command_service(guild_id, hub, "trivia start", "Trivia")
await cog.update_assignment_service(guild_id, hub, "trivia start", {"confirmation_required": True})
await cog.reorder_commands_service(guild_id, hub, "Trivia", ["prefix:trivia start"])
await cog.reorder_categories_service(guild_id, hub, ["Trivia", "General"])
await cog.update_permissions_service(
    guild_id,
    hub,
    allowed_roles=[role_id],
    blocked_roles=[],
    allowed_channels=[],
    blocked_channels=[],
    required_user_permissions=0,
    required_bot_permissions=0,
)
await cog.sync_guild(guild_id)
state = await cog.sync_status_service(guild_id)
```

Dashboard callers must enforce Manage Server/owner authorization and treat `ValidationError` as user input feedback. The reorder services require a complete, duplicate-free ordering so partial dashboard writes cannot silently drop assignments.

## Synchronization and troubleshooting

Configuration changes update the in-memory command tree and schedule one debounced guild sync (10 seconds by default). Repeated edits replace the pending task. Use `syncstatus` to see pending state, the last successful UTC timestamp, and the last sanitized exception summary.

- A hub missing from Discord: run `syncstatus`, check for a name conflict, then run owner-only `sync`.
- A command missing from a hub: run `refresh`, then `registry`; unloaded assignments remain listed by `commands`.
- An argument is unsupported: run `unsupported`. Do not loosen checks or coerce an unsafe type.
- An invocation shows an error ID: search bot logs for that six-character ID. Internal paths and argument values are not returned to Discord.
- Components expired: reopen the hub. Sessions time out after ten minutes and are not persistent.

## Configuration and migrations

Red Config stores schema version 2 globally, hubs/settings/sync state per guild, and optional last-command records per member. Migrations preserve unknown hub data, add new permission bitfields and unavailable behavior, and never delete assignments solely because discovery failed. Repeat persistence is disabled by default; in-memory history is bounded and only serializable, non-sensitive arguments may be persisted.

For internals and extension boundaries, see [ARCHITECTURE.md](ARCHITECTURE.md).

## Testing

From the repository root with development dependencies installed:

```text
uv run pytest tests/test_commandhub.py
uv run ruff check commandhub tests/test_commandhub.py
```
