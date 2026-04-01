---
id: conceptual-workflows-concurrent-access
title: Concurrent Access Safety
summary: >
  What the system does to ensure safe concurrent access — WAL mode, busy timeout, FK enforcement, and reader/writer isolation.
related: ["tech-db-schema", "tech-overview"]
stability: stable
---

# Concurrent Access Safety

Lore uses SQLite with three pragmas set on every connection to ensure correctness under concurrent agent access.

## Pragmas Applied on Every Connection

`get_connection` in `lore.db` executes these three pragmas before returning the connection to the caller:

```sql
PRAGMA journal_mode = WAL;
PRAGMA busy_timeout = 5000;
PRAGMA foreign_keys = ON;
```

### WAL Mode (`journal_mode = WAL`)

Write-Ahead Logging decouples readers from writers. In WAL mode:

- Multiple concurrent readers never block each other.
- One writer can proceed while readers continue reading a consistent snapshot.
- Readers do not block writers (unlike the default journal mode where a single writer blocks all readers).

This is the correct mode for agent workloads where several orchestrators or workers may read simultaneously while one is writing.

### Busy Timeout (`busy_timeout = 5000`)

When a write operation cannot acquire the database lock immediately (because another writer holds it), SQLite will retry for up to 5000 milliseconds before returning `SQLITE_BUSY`. This avoids immediate `OperationalError: database is locked` failures under brief contention. After 5 seconds of contention, the operation fails.

### Foreign Key Enforcement (`foreign_keys = ON`)

SQLite's foreign key constraints are disabled by default. This pragma enables them for the connection, ensuring that:

- A mission cannot be inserted with a `quest_id` that does not exist in `quests`.
- A dependency row cannot reference a `from_id` or `to_id` that does not exist in `missions`.
- Cascading behaviour defined in the schema is applied correctly.

## Write Isolation via `BEGIN IMMEDIATE`

All mutating operations in `lore.db` open explicit `BEGIN IMMEDIATE` transactions. This acquires a write lock at the start of the transaction rather than at the first write, preventing the following race:

1. Two connections both read the same state.
2. Both attempt to write based on that read.
3. The second write sees stale data.

With `BEGIN IMMEDIATE`, the second connection blocks at transaction start until the first commits or rolls back.

## Migration Double-Check Pattern

The migration path performs a re-read of `schema_version` after acquiring the `BEGIN IMMEDIATE` lock. This handles the case where another connection migrated the schema in the window between the initial version read and lock acquisition.

## Failure Modes

| Failure point | Behaviour | Exit code |
|---|---|---|
| Write contention > 5 seconds | `OperationalError: database is locked` propagates | 1 |
| FK violation on insert | `IntegrityError` propagates | 1 |
| Concurrent migration (race) | Double-check prevents duplicate migration | — |

## Out of Scope

- Multi-process write throughput optimisation — the 5-second timeout is sufficient for agent workloads.
- Network filesystem access — SQLite WAL mode has known issues on NFS; local filesystem is assumed.
