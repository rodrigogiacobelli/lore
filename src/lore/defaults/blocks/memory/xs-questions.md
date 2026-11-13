---
id: xs-questions
feature: memory
---
# Reference: capturing an upstream artifact as a source snapshot

Read this only when the knowledge passed the ingestion boundary in step 2 of the skill: authored outside the project,
authored outside the conversation, and identifiable well enough to be re-fetched and compared later.

A snapshot is a verbatim copy of one upstream item, stored at `.lore/codex/sources/<system>/<id>.md`, whose `related`
field names every canonical document the item caused to change. The snapshot is the raw record; the canonical documents
are the distilled knowledge. Both land, every time.

## Ask three questions

- **What system is this from?** `jira`, `slack`, `meetings`, `vendor-docs`.
- **What is the id?** `KONE-23335`, `2026-08-24-arch-review`.
- **How should I fetch it?** Pasted text, a local file, or a URL through a tool you have.

The answers set the path and make the later refresh possible. If the user cannot answer the first two, the item failed
the boundary: distil it into a codex document instead and write no snapshot.
