---
id: "003"
title: "Soft-delete semantics and FK omission on the dependencies table"
summary: "ADR explaining why soft-delete was chosen over hard-delete for all Lore entities, and why foreign key constraints were deliberately omitted from the dependencies table."
related: ["decisions-009", "tech-db-schema"]
stability: stable
---

# ADR 003 — Soft-Delete Semantics and FK Omission on the Dependencies Table

## Context

When CRUD completeness was added to Lore (spec: `docs/specs/crud-completeness.md`, now archived), all entities required a delete operation. Two design questions arose:

1. **Hard-delete vs soft-delete.** Should `lore delete` remove rows permanently or mark them as deleted while retaining the data?
2. **FK constraints on the dependencies table.** The `dependencies` table has `from_id` and `to_id` columns referencing mission IDs. Should those columns carry `FOREIGN KEY` constraints?

These questions are related: the answer to (2) depends on the answer to (1).

The CRUD completeness spec served agents interacting with Lore via the CLI. Human operators wanted to be able to grant `lore *` permissions in Claude Code without granting broad filesystem or direct database access. Full CRUD support through the CLI was the prerequisite.

## Decision

### Soft-delete for all entities

All delete operations use soft-delete semantics. No rows are removed from the database and no files are permanently deleted.

- **Database entities (quests, missions, dependencies):** A `deleted_at TEXT` column is added to the `quests`, `missions`, and `dependencies` tables. `lore delete` sets `deleted_at` to the current UTC ISO 8601 timestamp. All queries add `WHERE deleted_at IS NULL` so soft-deleted entities are invisible to normal operations.
- **File entities (knights, doctrines):** Soft-deleted by renaming with a `.deleted` suffix (e.g., `.lore/knights/reviewer.md` → `.lore/knights/reviewer.md.deleted`). Existing glob patterns (`*.md`, `*.yaml`) naturally exclude `.deleted` files.

Restore commands are not provided. Manual SQL or file rename can recover soft-deleted entities if needed.

### FK constraints deliberately omitted from the dependencies table

The `dependencies` table does not carry `FOREIGN KEY` constraints on `from_id` / `to_id`. This is an intentional design choice, not an oversight.

With soft-delete semantics, mission rows are never physically removed. The physical row remains; only `deleted_at` is set. This means FK constraints would not be violated by the soft-delete operation itself, so the FK omission does not strictly depend on soft-delete. However, the dependencies table was designed without FKs for a separate reason: simplicity and flexibility.

Application-level filtering (`deleted_at IS NULL` on joined mission rows) is the correct mechanism for excluding soft-deleted dependencies from query results.

## Scope

This ADR governs soft-delete semantics for data entities managed by the `lore` CLI — specifically quests, missions, and dependency rows in the Lore SQLite database, and file entities (knights, doctrines) in the `.lore/` directory. It does **not** govern the development practices of the Lore project's own source code. When Lore source code is modified — for example, removing a CLI command, deleting a Python module, or dropping a function — standard hard-delete (permanent removal) is the correct approach. No soft-delete ceremony applies to source code changes.

## Rationale

**Why soft-delete over hard-delete:**

- **Auditability.** Soft-deleted entities remain in the database. An agent or human operator can inspect what was deleted and when, without needing a separate audit log.
- **Recovery.** Accidental deletes are recoverable via manual SQL or file rename. Hard-delete is irreversible.
- **Reference integrity without FKs.** When a quest is soft-deleted with `--cascade`, all its missions and their dependency rows are also soft-deleted in the same operation. Physical rows remain, so no FK violations occur regardless of constraint presence.
- **Consistency.** A single delete mechanism (soft) covers all entity types. No special cases for "this entity can be hard-deleted."
- **AI safety.** Agents interacting with Lore via the CLI cannot accidentally destroy data permanently. The worst case is a soft-delete, which is recoverable.

**Why no FK constraints on the dependencies table:**

- **SQLite FK enforcement requires `PRAGMA foreign_keys = ON` per connection.** Lore does not enable this pragma, so any FK declarations would be inert. Adding non-enforced FKs would be misleading documentation.
- **Soft-delete preserves physical rows.** Even if FKs were enforced, soft-deleting a mission would not violate a FK constraint because the row still exists. The application layer (not the DB constraint) is responsible for treating soft-deleted missions as absent.
- **Simplicity.** The dependency table's integrity is managed through application-level queries. Adding constraints that duplicate application logic without providing additional safety is unnecessary complexity.

## Alternatives Rejected

**Hard-delete with CASCADE.** Rejected because it is irreversible and destroys the audit trail. In an agent-driven workflow, accidental deletions are more likely than in human-driven workflows. The cost of unrecoverable data loss outweighs the simplicity benefit.

**Hard-delete with application-level referential cleanup.** Rejected because it requires the application to identify and delete all referencing rows before deleting the target — a transaction-heavy operation with more failure modes than soft-delete.

**FK constraints enabled via `PRAGMA foreign_keys = ON`.** Rejected because FK enforcement on the dependencies table would conflict with soft-delete semantics: a `DELETE FROM missions` (which Lore never does) would cascade-delete dependency rows, but a soft-delete (UPDATE `deleted_at`) would not trigger FK cascade actions. The FK mechanism and the soft-delete mechanism would be semantically inconsistent. Application-level filtering is the correct and consistent approach.

**Separate audit/history tables.** Rejected as over-engineering. Soft-delete in the same table provides sufficient history for Lore's scale and use case without the complexity of separate tables or change-data-capture patterns.
