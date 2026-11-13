---
id: xs-verify
feature: memory
commands: [health --scope codex, health --scope schemas, health --scope voice]
---
## Verify

```
lore health --scope codex schemas voice
```

`voice` skips the `sources/` layer entirely: a snapshot is verbatim upstream text and is exempt. Any voice warning is on
a canonical document you edited, not on the snapshot. A schema error naming the snapshot almost always means `related`
is missing, empty, or names an id that does not exist.
