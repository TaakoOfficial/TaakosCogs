# KnowledgeGarden

KnowledgeGarden turns solved discussions into staff-reviewed answers that members can search without an external AI or search provider.

Start with `[p]knowledgegarden setup #staff-operations` to configure a 90-day review queue without enabling optional auto-capture.

```text
[p]knowledgegarden draft "Resetting two-factor authentication" Ask an administrator to verify ownership...
[p]knowledgegarden publish 1
[p]knowledgegarden tags 1 account, security, 2fa
[p]knowledgegarden aliases 1 lost phone, new authenticator
[p]knowledgegarden search lost authenticator
[p]knowledgegarden feedback 1 helpful
```

Reply to a useful answer and run `knowledgegarden capture <title>` to preserve its text, attachments, and Discord jump link as a draft. Draft creation also points staff toward related retained entries. By default, the draft author cannot publish their own entry.

With ForumFlow loaded, run `knowledgegarden fromforum` inside a solved post. Use `knowledgegarden integrations true` to create a draft automatically whenever ForumFlow accepts an answer. Source identifiers prevent duplicate imports.

Edits retain at most 20 previous answer bodies. Retiring an entry removes it from member search without erasing the record or its source.

Use `knowledgegarden reviews #staff-operations 90` to receive a daily change queue when published entries become stale or members flag them as outdated or unclear. Staff can run `knowledgegarden reviewed <id>` after checking an entry. `knowledgegarden misses` reports up to 100 bounded unanswered search phrases without storing who searched for them.
