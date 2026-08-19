# EventCheckin

EventCheckin adds persistent RSVP, automatic waitlists, reminders, attendance check-ins, no-show finalization, recurring drafts, calendar exports, native Discord scheduled events, and optional reward roles.

Use `[p]eventcheckin setup #event-logs America/Chicago` to configure the log channel and calendar timezone together.

Discord timestamp generators such as `<t:...>` use Unix seconds; pass that numeric timestamp to `create`:

```text
[p]eventcheckin create 1786003200 25 Community Workshop Details go here
[p]eventcheckin location 1 Voice channel: Workshop
[p]eventcheckin rewardrole 1 @AttendedWorkshop
[p]eventcheckin post 1 #events
[p]eventcheckin duration 1 90
[p]eventcheckin repeat 1 7 5
[p]eventcheckin calendar all
[p]eventcheckin discordevent 1
[p]eventcheckin template save 1 workshop
[p]eventcheckin template use workshop 1786608000
[p]eventcheckin stats 90
```

When capacity is reached, later RSVPs enter a FIFO waitlist. Withdrawing a confirmed RSVP promotes the first waiting member. Check-in is time-bounded; staff can also use `[p]eventcheckin checkin`.

`finalize` marks remaining confirmed RSVPs as no-shows and awards the configured role to checked-in attendees. `export` creates an attendance CSV.

`repeat` creates a bounded series of draft copies. `calendar` exports retained events as an RFC 5545 `.ics` file for Apple Calendar, Google Calendar, Outlook, and other calendar clients. Set a guild display timezone with `eventcheckin timezone America/Chicago`. `discordevent` creates an external native Discord scheduled event after a location and duration have been set.

Templates preserve reusable event fields without attendees. `series` lists related occurrences and `seriescancel` closes future occurrences. Cancelling a single event updates its panel, posts a cancellation notice, and privately notifies up to 100 reachable registered members. `stats` reports aggregate registration, check-in, and no-show counts.

When DecisionLedger is loaded, `decision reviewevent` creates a linked EventCheckin draft for a scheduled decision review. EventCheckin remains independent when DecisionLedger is absent.

The bot needs Send Messages and Embed Links for panels, plus Manage Roles when rewards are configured.
