# DecisionLedger

DecisionLedger records staff proposals and preserves the reason, approval, implementation owner, evidence, due date, outcome, and lifecycle history.

Start with `[p]decision setup #staff-operations` to configure safe daily reminder defaults.

```text
[p]decision propose "Adopt weekly office hours" Reduce unanswered support requests
[p]decision accept 1 @StaffMember
[p]decision evidence 1 https://discord.com/channels/... Discussion
[p]decision due 1 1798761600
[p]decision status 1 implemented Attendance improved after four weeks
[p]decision reviewcycle 1 90
[p]decision reminders #staff-operations 24
```

By default, a proposal's author cannot accept their own proposal. Decisions follow bounded state changes: proposed decisions can be accepted or rejected; accepted decisions can be implemented or superseded. Rejected decisions may be proposed again.

## Optional integrations

```text
[p]decision integrations
[p]decision fromsuggestion 12 @Owner
[p]decision fromincident 4 0
[p]decision autolink suggestionbox true
[p]decision autolink opsroom true
[p]decision reviewevent 7 1798761600 60
```

Suggestion and incident imports retain backlinks and reject duplicate sources. StaffOps adds shift, availability, on-call, and leave context when assigning an owner. EventCheckin can create a linked decision-review draft. None of these cogs are required for DecisionLedger to load.

## Templates and reviews

```text
[p]decision template save policy "Review moderation policy" Check whether the policy still matches practice.
[p]decision fromtemplate policy
[p]decision reviewcycle 3 90
[p]decision reviewed 3 No changes required
```

Review cycles and implementation due dates can produce bounded reminders in a configured staff channel. Templates retain at most 25 reusable proposal starters.

Governance and relationship controls are optional:

```text
[p]decision governance 2 1
[p]decision risk 3 high
[p]decision depends 3 1
[p]decision supersedes 3 2
```

`governance` requires distinct staff approvals and a minimum number of evidence links before manual proposals can be accepted. Decisions can also carry risk, dependency, and supersession relationships.
