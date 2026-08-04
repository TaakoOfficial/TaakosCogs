# EventCheckin

EventCheckin adds persistent RSVP, automatic waitlists, reminders, attendance check-ins, no-show finalization, and optional reward roles to Discord events.

Discord timestamp generators such as `<t:...>` use Unix seconds; pass that numeric timestamp to `create`:

```text
[p]eventcheckin create 1786003200 25 Community Workshop Details go here
[p]eventcheckin location 1 Voice channel: Workshop
[p]eventcheckin rewardrole 1 @AttendedWorkshop
[p]eventcheckin post 1 #events
```

When capacity is reached, later RSVPs enter a FIFO waitlist. Withdrawing a confirmed RSVP promotes the first waiting member. Check-in is time-bounded; staff can also use `[p]eventcheckin checkin`.

`finalize` marks remaining confirmed RSVPs as no-shows and awards the configured role to checked-in attendees. `export` creates an attendance CSV.

The bot needs Send Messages and Embed Links for panels, plus Manage Roles when rewards are configured.
