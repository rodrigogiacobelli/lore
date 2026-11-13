---
id: i-memory-graph
feature: memory
capabilities: [memory-graph]
commands: [codex map, codex chaos, impacts]
glue: tight
---
- `lore codex map <id>` walks related documents; `lore codex chaos <id> --threshold <30-100>` finds unexpected
  neighbours. `lore impacts <path>` lists the documents governing a file (run it before editing code);
  `lore impacts <codex-id>` lists the files a document binds.
