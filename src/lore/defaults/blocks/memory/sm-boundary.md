---
id: sm-boundary
feature: memory
---
## Step 2: Apply the ingestion boundary

Write a source snapshot **only when the knowledge arrives as an artifact authored outside the project and outside the
conversation, and identifiable well enough to be re-fetched and compared later.** All three conditions hold, or there is
no snapshot:

- **Authored outside the project**: a Jira ticket, a meeting transcript, a vendor's API doc, not a note you just wrote.
- **Authored outside the conversation**: the user pasting their own reasoning is conversation, however long the paste.
- **Re-fetchable and comparable**: you can name the system and the id (`jira`/`KONE-23335`) well enough that a later
  refresh finds the same item and diffs it.

Fail any one and the knowledge still lands, as a codex document or a rite distilled in your own words.
