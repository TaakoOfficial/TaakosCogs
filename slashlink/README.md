# slashlink

SlashLink gives loaded prefix-only cogs an application-command gateway while leaving
registration, enablement, disablement, and syncing under Red's built-in `[p]slash`
commands.

It does not replace Red's slash manager and does not modify other cogs. Cogs that
already provide native or hybrid application commands are ignored.

## Install

```text
[p]cog install taakoscogs slashlink
[p]load slashlink
```

Then use Red's normal workflow:

```text
[p]slash list
[p]slash enablecog SomeCog
[p]slash sync
```

For a prefix-only cog named `SomeCog`, SlashLink generates a command similar to:

```text
/somecog command:<autocomplete> arguments:<optional raw arguments> attachment:<optional file>
```

The `command` option only suggests commands belonging to that cog and filters them
through Red's normal visibility and permission checks. Invocation still runs the
original command converters, checks, cooldowns, and hooks.

## Limits

- Discord permits at most 100 enabled global chat-input commands.
- Prefix commands that depend on editing, deleting, or reacting to the original
  invoking message may not work because application commands do not have a real
  source message.
- Interactive commands that wait for later text messages still require those replies
  in the channel.
- Generated proxies are compatibility gateways. Native hybrid commands remain the
  preferred option for precise typed slash parameters.
