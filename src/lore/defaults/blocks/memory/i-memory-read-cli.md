---
id: i-memory-read-cli
feature: memory
route: cli
commands: [codex show, codex list, rite list, rite show, glossary list]
mentions: [retrieve-memory]
---
- **Read** with the Lore CLI, batching ids into one `show` call (it deduplicates and appends matched glossary terms):
  `lore codex show <id1> <id2>`, `lore codex list`, `lore rite list`, `lore rite show <id>` (inlines the shared steps),
  `lore glossary list`. The `retrieve-memory` skill walks codex and rites in one pass.
