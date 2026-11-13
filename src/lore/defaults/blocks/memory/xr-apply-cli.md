---
id: xr-apply-cli
feature: memory
route: cli
commands: [rite new, rite edit, rite delete]
---
## Applying the change

Group small steps by platform or system (`portal/`, `backoffice/`, `db/`) so the tree stays browsable. The group is
optional; omit it for the root.

**Create**: `new` scaffolds, `edit --from` puts the body in:

```
lore rite new <id> [--shared] [--group <path>]
lore rite edit <id> [--shared] --from <temp-file>
```

**Edit**: `edit` resolves a bare id across the whole tree:

```
lore rite edit <id> [--shared] --from <temp-file>
```

**Delete:**

```
lore rite delete <id>
```

`--shared` selects the shared-step schema and subfolder on `new` and `edit`. `delete` resolves a bare id across both
trees, so it accepts the flag for parity and ignores it.
