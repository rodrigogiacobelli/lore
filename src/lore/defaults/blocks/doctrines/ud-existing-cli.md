---
id: ud-existing-cli
feature: doctrines
requires: [route=cli]
commands: [doctrine show, doctrine list]
---
Read doctrines through the CLI rather than off disk: the doctrine tree hides a `default/` versus flat split and slash-derived
groups, and `lore doctrine show` assembles the mission index.

```
lore doctrine list
lore doctrine show <existing-id> [--mission <mission-id>]
```
