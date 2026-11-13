---
id: sq-context-cli
feature: quests
requires: [memory.cli]
commands: [glossary list, codex show]
glue: tight
---
Find them with `lore glossary list` and `lore codex show <id1> <id2>`; batch ids into one `show` call, which deduplicates
and appends the glossary terms it matched.
