---
id: sq-missions
feature: quests
commands: [new, show]
---
### 4. Create all missions

For each mission in the doctrine (or the trimmed subset), create one Lore mission:

```
lore new mission -q <quest-id> "<mission title>" -d "<description>" -D <doctrine-id>/<mission-id> -T <type> -p <phase>
```

`-D` stores the reference, which Lore resolves at read time: `lore show <mission-id>` hands the worker the doctrine mission
body under `--- Mission Instructions ---` alongside the description. Set `-T` and `-p` from the design table. The
description carries only what is specific to this run; the next section says what goes in it. Keep a mapping
of `doctrine-mission-id` to the fully qualified `q-xxxx/m-yyyy` id `lore new mission` returns.
