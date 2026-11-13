---
id: rm-enter-cli
feature: memory
route: cli
commands: [codex show, codex list, glossary list, glossary show]
---
| Goal | Command |
|---|---|
| Read one or more documents | `lore codex show <id1> <id2> ...` |
| See the whole taxonomy | `lore codex list` |
| List project vocabulary | `lore glossary list` |
| Read vocabulary entries | `lore glossary show <kw1> <kw2> ...` |

Batch ids into one `lore codex show` call: it deduplicates and appends the glossary terms it matched, so an unfamiliar
term arrives with its definition attached.
