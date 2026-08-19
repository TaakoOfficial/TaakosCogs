# OperationsCenter

OperationsCenter is an optional control plane for the operations cogs. It shows which capabilities are loaded, surfaces ServerDoctor findings, retains a bounded integration audit, and retries supported cross-cog work after temporary failures. Partner cogs remain standalone when OperationsCenter is absent.

```text
[p]operationscenter status
[p]operationscenter setup #staff-operations
[p]operationscenter audit 10
[p]operationscenter retries
[p]operationscenter retry 3
[p]operationscenter route SecretSentinel #security-alerts
[p]operationscenter mute KnowledgeGarden
```

The setup command validates its alert channel and prints setup commands for whichever partner cogs are currently loaded. It does not silently enable those cogs or change their policies.

Each managed cog can route failures to its own channel. Quiet mode suppresses notifications for one source without discarding its audit events.
