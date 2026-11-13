---
id: ud-write-cli
feature: doctrines
route: cli
commands: [doctrine new, doctrine edit, doctrine delete]
---
### 4. Write the doctrine

```
lore doctrine new <name> -d <design-file> -m <mission-1> <mission-2> <mission-3>
```

Pass `--group <subdir>` to nest it; the whole directory is created or nothing is. `lore doctrine edit` replaces only the
files you pass, so a mission nobody names stays byte-identical:

```
lore doctrine edit <name> -d <design-file>               # replace the design
lore doctrine edit <name> -m <mission-file> ...          # replace or add missions
lore doctrine edit <name> --remove-mission <id> ...      # soft-delete missions
lore doctrine edit <name> --set summary="..."            # edit one design frontmatter field
```

A doctrine keeps at least one mission. `lore doctrine delete <name>` retires one by a soft delete: the directory is renamed.
