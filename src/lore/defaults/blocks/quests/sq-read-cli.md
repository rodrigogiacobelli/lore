---
id: sq-read-cli
feature: quests
requires: [route=cli]
commands: [doctrine show]
---
```
lore doctrine show <doctrine-id>
```

One call returns the design document and a `--- Missions ---` index of every mission in the doctrine. Read the design in
full. Read a mission body only when you need to know what the worker will be told:

```
lore doctrine show <doctrine-id> --mission <mission-id>
```
