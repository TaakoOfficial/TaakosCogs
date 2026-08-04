# AccessReview

AccessReview creates auditable certification campaigns for sensitive roles. A campaign snapshots current access, reviewers decide `keep` or `remove`, and a separate confirmed step applies removals.

## Safe workflow

```text
[p]accessreview reviewerrole @SecurityReviewers
[p]accessreview logchannel #access-evidence
[p]accessreview create quarterly-admin @Administrator 14
[p]accessreview decide 1 @Member keep Still on operations team
[p]accessreview decide 1 @FormerStaff remove Offboarded
[p]accessreview show 1
[p]accessreview enforce 1 REMOVE
[p]accessreview export 1
```

Decisions never change roles. Enforcement only removes snapshotted campaign roles from entries marked `remove`, skips unmanageable roles, records errors, and requires the exact `REMOVE` confirmation.

The bot needs Manage Roles and a role above every reviewed role.
