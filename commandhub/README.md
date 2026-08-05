# CommandHub

CommandHub turns configured groups of loaded bot commands into guild slash commands such as `/games`, `/admin`, and `/utility`. Opening a hub displays an interactive command browser with categories, 25-command pages, partial-match search, modal argument entry, confirmation gates, and optional repeat-last-command behavior.

The cog targets Red-DiscordBot 3.5, Python 3.11+, and modern Discord components. Hub commands are guild scoped by default, so changes propagate quickly and do not consume global command updates.

## Installation

From Red's Downloader:

```text
[p]repo add taakoscogs https://github.com/TaakoOfficial/TaakosCogs
[p]cog install taakoscogs commandhub
[p]load commandhub
```

The bot needs `applications.commands`, Send Messages, Embed Links, and Use Application Commands in the target guild. Administrators need Manage Server for normal management; registry refresh and explicit network sync are owner-only.

## Let CommandHub make the first draft

If you already know which loaded cogs belong together, `bootstrap` is the quickest starting point. This example makes one `/utility` hub and gives Toolz and RoleKit their own categories:

```text
[p]commandhub bootstrap utility Toolz RoleKit
```

CommandHub refreshes its command registry and sends a preview showing every supported command it found. It reports unsupported commands separately. Nothing is saved until the administrator who requested the preview clicks **Apply plan**. Applying the plan adds missing assignments to an existing `/utility` hub or creates it and schedules a guild command sync.

If you are not sure how to divide the loaded cogs, ask for a full suggestion:

```text
[p]commandhub suggest
```

The suggestion reads each loaded cog's runtime name and description, plus its local `info.json` name, description, and tags when that file is available. It combines that with command names, descriptions, and required permissions to draft `/admin`, `/community`, `/fun`, `/music`, `/utility`, and `/other` hubs. Permission-gated commands lean toward `/admin`; uncertain matches go to `/other` for review.

The rules are local and repeatable—there is no network classifier or AI call. Treat the result as a first draft: check `/other`, move anything that landed in the wrong place, and review confirmation settings before members use the hubs. Existing assignments in the target hub are not duplicated, common destructive command names start with confirmation enabled, and commands CommandHub cannot represent are skipped. If a suggested slash name is already taken, CommandHub previews a `-hub` name when one is available.

## Your first hub: Toolz lookups

Start small. Categories, custom titles, permission rules, and confirmation settings can wait until the first hub works.

This example uses the real `roleinfo` and `memberinfo` commands from the repository's [Toolz cog](../toolz/README.md). Load Toolz and CommandHub, then run four management commands:

```text
[p]commandhub create utility
[p]commandhub add utility "roleinfo"
[p]commandhub add utility "memberinfo"
[p]commandhub sync
```

That's enough to create `/utility`.

When a member runs it, CommandHub opens a private menu containing the two Toolz commands. Choosing `roleinfo` opens a text field for the role; the member can enter a role mention, its Discord ID, or its exact name. Choosing `memberinfo` opens an optional member field, which can be left blank to inspect yourself. Toolz's original server, channel, bot-permission, and command checks still decide whether the command runs.

Want a nicer name and description? These settings are optional:

```text
[p]commandhub set utility title Server Utilities
[p]commandhub set utility description Look up members and inspect server roles.
```

### Add categories after the hub works

Suppose the utility hub grows and you want a separate section for staff role checks. Toolz also provides `roleaudit` and `rolecompare`:

```text
[p]commandhub category create utility "Role Checks"
[p]commandhub add utility "roleaudit"
[p]commandhub add utility "rolecompare"
[p]commandhub category move utility "Role Checks" "roleaudit"
[p]commandhub category move utility "Role Checks" "rolecompare"
[p]commandhub commands utility
```

Open `/utility` again and the new category appears. You don't need another Discord command-tree sync when adding, removing, or recategorizing commands because the hub reads those assignments when it opens. Run `[p]commandhub sync` after creating, renaming, enabling, disabling, or changing the description of a hub.

Hub responses are private by default. Use `[p]commandhub set utility ephemeral false` if you want one shared public browser; private sessions only accept clicks from the member who opened them.

## Administrator commands

- `[p]commandhub bootstrap <hub> <cog names...>` previews one hub with a category for each selected loaded cog.
- `[p]commandhub suggest` previews a multi-hub layout derived from all loaded cog and command metadata.
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

For internals and extension boundaries, see [ARCHITECTURE.md](./ARCHITECTURE.md).

## Testing

From the repository root with development dependencies installed:

```text
uv run pytest tests/test_commandhub.py
uv run ruff check commandhub tests/test_commandhub.py
```
