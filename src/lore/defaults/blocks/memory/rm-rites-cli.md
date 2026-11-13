---
id: rm-rites-cli
feature: memory
route: cli
commands: [rite list, rite show]
---
## Step 4: Cross to the rites for the *how*

| Goal | Command |
|---|---|
| Browse main rites: id, group, trigger, summary | `lore rite list` (`--shared` for shared steps, `--filter <a/b>` for a group) |
| Read rites in full, shared steps inlined | `lore rite show <id1> <id2> ...` |

`lore rite show` inlines every shared step a main rite pulls in with `use:`, so one call gives you the complete,
follow-it-now procedure.
