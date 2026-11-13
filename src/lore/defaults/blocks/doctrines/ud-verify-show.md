---
id: ud-verify-show
feature: doctrines
requires: [route=cli]
commands: [doctrine show]
---
```
lore doctrine show <name>
lore doctrine show <name> --mission <mission-id>
```

`lore doctrine show <name>` prints the design document and a `--- Missions ---` index. Check that every mission in the
design table appears in that index and that no mission appears in the index without a row in the table.
