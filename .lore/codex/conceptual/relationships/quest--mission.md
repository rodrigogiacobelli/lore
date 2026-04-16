---
id: conceptual-relationships-quest--mission
title: Quest to Mission
related:
- conceptual-entities-quest
- conceptual-entities-mission
- tech-db-schema
summary: A Quest optionally groups one or more Missions. Missions can exist without
  a Quest (standalone). Quest status is derived entirely from its Missions' statuses;
  there is no independent status field on Quest.
---

# Quest to Mission

A Quest is a live grouping of Missions representing a body of work. The relationship is optional on the Mission side: every Mission may belong to at most one Quest, but Missions can also be standalone (no Quest). The cardinality is one Quest to many Missions.

## Named Roles

### Parent Quest (optional, set at mission creation)

The Quest that owns this Mission. Set at mission creation via the `quest_id` field. Cannot be reassigned after creation — a Mission belongs to the Quest it was created under for its entire lifetime. Retained as a historical reference even after the Quest is soft-deleted.

### Missions (collection, mutable membership)

The ordered set of Missions that belong to a Quest. Membership grows when new Missions are created under the Quest. A Mission is never moved between Quests.

## Data on the Connection

The relationship is stored as a foreign key column on the `missions` table.

| Column | Role | Mutable |
|--------|------|---------|
| `missions.quest_id` | References the owning Quest | No |

There is no separate join table. A `NULL` `quest_id` means the Mission is standalone.

## Business Rules

- **One Quest per Mission:** A Mission belongs to at most one Quest; the `quest_id` FK is nullable but not reassignable.
- **Status derivation:** Quest status is computed from its Missions. A Quest with all Missions `done` is `closed`. A Quest with any Mission `blocked` is `blocked`. A Quest with at least one Mission `in_progress` is `in_progress`. See the Quest entity doc for the full derivation table.
- **Reopening:** Adding a new Mission to a `closed` Quest causes the Quest to re-derive its status; it reopens automatically if the new Mission is not `done`.
- **Soft-delete cascade:** Soft-deleting a Quest without explicit cascade does NOT soft-delete its Missions. Those Missions become orphaned — they retain their `quest_id` FK pointing at a deleted Quest, and the `lore show` command displays a warning.
- **Explicit cascade:** When a Quest is soft-deleted with the cascade option, all of its Missions are also soft-deleted in the same operation.
- **Orphaned Missions:** An orphaned Mission (quest soft-deleted, Mission not) remains fully functional. It can be claimed, progressed, and closed. The orphaned state is informational only.
- **Standalone Missions:** A Mission with `quest_id = NULL` is valid and permanent. It will never be associated with a Quest after creation.

## Concrete Examples

### Quest status derived from Missions

```
$ lore quest show q-1234
Status: in_progress
Missions:
  m-001 [done]     Write schema migration
  m-002 [in_progress] Implement CLI command
  m-003 [open]     Write E2E tests
```

→ Quest status = `in_progress` (at least one Mission in progress)

### Reopening a closed Quest

```
$ lore quest show q-1234
Status: closed

$ lore mission new --quest q-1234 "Add observability"
Mission m-004 created.

$ lore quest show q-1234
Status: in_progress
```

→ Quest status re-derives to `in_progress` when the new open Mission is added.

### Orphaned Mission after Quest soft-delete

```
$ lore quest delete q-1234   # no cascade
Quest q-1234 soft-deleted. 3 missions orphaned.

$ lore show m-002
Warning: quest q-1234 has been deleted.
Status: in_progress
```
