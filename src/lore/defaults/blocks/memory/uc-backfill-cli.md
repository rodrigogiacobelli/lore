---
id: uc-backfill-cli
feature: memory
route: cli
commands: [codex edit]
---
Backfill one doc at a time; field-edit mode resolves the same merged schema, so it is the safe way to add a newly required
field:

```
lore codex edit <doc-id> --set owner=alice
lore codex edit <doc-id> --set tags=a,b          # array fields comma-split
lore codex edit <doc-id> --unset <field>         # drop a custom field again
```

To drop a field, also remove it from the overlay's `properties` and `required`: a doc holding an undeclared field fails
with `Unknown property`.
