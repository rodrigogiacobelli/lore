---
id: conceptual-relationships-mission--mission
title: Mission to Mission (Dependencies)
related:
- conceptual-entities-mission
- tech-db-schema
summary: Missions can depend on other Missions via a directed acyclic dependency graph.
  Dependencies are stored in a join table. A Mission with unmet dependencies is blocked
  from being claimed until all its predecessors are done.
---

# Mission to Mission (Dependencies)

Missions express ordering constraints through a dependency graph: a Mission can declare that it `needs` one or more other Missions to be `done` before it can be claimed. This forms a directed acyclic graph (DAG). The cardinality is many-to-many: one Mission can need many predecessors, and one Mission can be needed by many successors.

## Named Roles

### Blocker (predecessor)

The Mission that must reach `done` status before the dependent Mission is eligible. Referenced by ID. The blocker role is established when the dependent Mission is created or edited.

### Dependent (successor)

The Mission that declares the dependency. It will not appear in the `lore ready` queue until all of its blockers are `done`.

## Data on the Connection

Dependencies are stored in a separate join table, not as columns on `missions`.

| Column | Role | Mutable |
|--------|------|---------|
| `mission_dependencies.mission_id` | The dependent Mission | No (row deleted to remove dep) |
| `mission_dependencies.needs_mission_id` | The blocker Mission | No (row deleted to remove dep) |

Dependency rows are immutable once inserted. To remove a dependency, the row is deleted. To change a dependency, the old row is deleted and a new one inserted.

## Business Rules

- **Cross-quest dependencies:** When a dependency spans two Quests, the blocker is referenced by its fully-qualified ID (e.g. `q-1234/m-001`). Within the same Quest, the short Mission ID is sufficient.
- **Intra-quest short IDs:** The CLI resolves short IDs within the current Quest context when the dependency is declared from within a Quest scope.
- **Cycle detection:** Lore rejects any dependency that would create a cycle in the graph. The check is performed at write time; the operation fails with an error if a cycle is detected.
- **Cascade on soft-delete:** When a Mission is soft-deleted, all dependency rows referencing it — as either the dependent or the blocker — are deleted from the join table.
- **Show output:** `lore show <mission-id>` exposes only the direct neighbours: the Missions this Mission directly needs, and the Missions that directly need this Mission. Transitive dependencies are not listed in show output.
- **Ready queue eligibility:** A Mission is only surfaced by `lore ready` when every direct blocker has status `done`.

## Concrete Examples

### Declaring a cross-quest dependency

```
$ lore mission new --quest q-5000 --needs q-4999/m-007 "Deploy new service"
Mission q-5000/m-008 created.
Blocked by: q-4999/m-007
```

→ `mission_dependencies` row: `mission_id=q-5000/m-008`, `needs_mission_id=q-4999/m-007`

### Cycle detection

```
$ lore mission edit m-001 --needs m-003
# m-003 already needs m-001
Error: dependency cycle detected. m-001 → m-003 → m-001.
```

### Cascade on soft-delete

```
$ lore mission delete m-002
Mission m-002 soft-deleted.
Dependency rows removed: m-003 no longer blocked by m-002.
```

→ m-003 may now appear in `lore ready` if all other blockers are done.
