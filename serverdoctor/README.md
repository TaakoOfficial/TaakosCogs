# ServerDoctor

ServerDoctor produces a read-only health report for the current guild. It checks bot permissions and role position, dangerous `@everyone` permissions, Administrator roles, Discord role and channel limits, channels where the bot cannot send, empty unmanaged roles, and duplicate role names.

```text
[p]serverdoctor scan
[p]serverdoctor export
[p]serverdoctor ignore EMPTY_ROLES
[p]serverdoctor ignored
[p]serverdoctor schedule 24 #staff-operations
```

Ignoring a code only hides it from later reports. ServerDoctor never changes permissions, moves roles, deletes channels, or edits configuration outside its own suppression list.

If other Taako cogs are loaded, the same scan checks missing integration sources, alert channels, deletion permissions, suggestion channels, event panels, and ForumFlow forum references. Run `serverdoctor cogs` to see which optional checks are active.

Scheduled scans are change-only: the first scan establishes a baseline, then the selected channel receives only new and resolved finding codes. Use `serverdoctor schedule 0` to disable them.
