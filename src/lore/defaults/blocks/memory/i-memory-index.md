---
id: i-memory-index
feature: memory
capabilities: [memory-index]
commands: [index search, index build]
mentions: [update-index]
glue: tight
---
- `lore index search <kw>` is the cheapest first call on a codex you have not read: it answers with a named cluster
  of related documents and their paths. It stays on the CLI whichever way you read the rest, because it rebuilds from
  the codex before it matches. `lore index build` reports clusters still to be named by the `update-index` skill.
