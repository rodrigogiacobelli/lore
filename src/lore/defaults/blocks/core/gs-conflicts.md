---
id: gs-conflicts
feature: core
requires: ['pseudo:cli']
commands: [init]
---
A file Lore did not install, sitting at a path Lore wants to write, is the one conflict left. Lore leaves it alone and
reports it on every run unless you pass `--on-conflict overwrite` to `lore init`.
