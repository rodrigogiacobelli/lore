---
id: conceptual-relationships-knight--mission
title: Knight to Mission
related:
- conceptual-entities-knight
- conceptual-entities-mission
- tech-db-schema
- tech-arch-knight-module
summary: A Mission may optionally name one Knight by filename stem. The Knight is
  not stored by database ID; it is referenced by name and resolved from disk at show-time.
  At most one Knight per Mission.
---

# Knight to Mission

A Mission can be assigned a Knight persona to guide the worker agent executing it. The assignment is optional: a Mission without a Knight is fully valid and can be claimed and executed. The cardinality is at most one Knight per Mission; a Knight can be assigned to many Missions.

## Named Roles

### Assigned Knight (optional, mutable)

The Knight persona assigned to the Mission. Stored as the Knight's filename stem (e.g. `architect`), not as a database row ID. Resolved at show-time by reading the corresponding file from `.lore/knights/<stem>.md`. Can be set at creation or updated later via mission edit.

### Mission (many, mutable assignment)

A Mission that has been assigned a Knight. A single Knight can be the assigned persona for many Missions simultaneously and across time.

## Data on the Connection

The reference is stored as a text column on the `missions` table.

| Column | Role | Mutable |
|--------|------|---------|
| `missions.knight` | Filename stem of the assigned Knight | Yes |

There is no foreign key constraint. The column holds a plain string that the application resolves at read time.

## Business Rules

- **Optional assignment:** `missions.knight` is nullable. A `NULL` value means no Knight is assigned; the Mission is still fully functional.
- **Resolved by name, not by ID:** The knight field stores the filename stem. `lore show <mission-id>` reads the Knight file from `.lore/knights/<stem>.md` and appends its contents to the output. See the Knight entity doc for details on Knight resolution.
- **Missing Knight warning:** If the Knight file cannot be found on disk at show-time (e.g. it was hard-deleted or renamed), Lore emits a warning but the Mission remains fully functional. The `knight` field is not cleared automatically.
- **Soft-delete does not clear missions:** Soft-deleting a Knight does NOT update the `knight` field on any existing Mission. The reference is retained as a historical record. A soft-deleted Knight's file may still be resolved if it has not been physically removed.
- **One Knight per Mission:** A Mission can have at most one Knight assigned at a time. To change the Knight, update the `knight` field; the previous value is overwritten.

## Concrete Examples

### Knight resolved at show-time

```
$ lore show q-4082/m-7f6e
Mission: q-4082/m-7f6e
Title: Build the auth module
Knight: architect
...
--- Knight Contents ---
# Architect
You are the Architect. You run two missions...
```

→ Lore reads `.lore/knights/architect.md` and appends it to the output.

### Missing Knight warning

```
$ lore show m-100
Warning: knight file 'wizard.md' not found. Knight field retained.
Title: Write the spell registry
Knight: wizard
Status: open
```

→ Mission is fully usable; only the Knight contents section is missing.

### Soft-deleted Knight reference retained

```
$ lore knight delete architect
Knight 'architect' soft-deleted.

$ lore show m-200
Warning: knight 'architect' is soft-deleted.
Knight field is retained for historical record.
```
