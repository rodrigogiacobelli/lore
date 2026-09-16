---
id: conceptual-workflows-schema-migrations
title: Schema Migrations
summary: 'What the system does internally when schema migrations run — version detection,
  sequential application, rollback on failure, and specific migration contracts.

  '
binds:
- src/lore/migrations/__init__.py
- src/lore/migrations/v1_to_v2.py
- src/lore/migrations/v2_to_v3.py
- src/lore/migrations/v3_to_v4.py
- src/lore/migrations/v4_to_v5.py
- src/lore/migrations/v5_to_v6.py
- src/lore/migrations/v6_to_v7.py
- src/lore/db.py
related:
- ref-lore_db-core
- tech-arch-source-layout
---

# Schema Migrations

Lore stores a `schema_version` key in the `lore_meta` table. Every time a connection is opened via `get_connection`, the version is checked and any pending migrations are applied before the connection is returned to the caller.

## Current Schema Version

`SCHEMA_VERSION = 7` (defined in `lore.db`).

## Migration Contracts

| Step | What it does |
|---|---|
| v1→v2 | Adds `deleted_at` columns (soft-delete). |
| v2→v3 | Adds `auto_close` to `quests`. |
| v3→v4 | Adds `mission_type` to `missions`. |
| v4→v5 | Removes the `mission_type` enum: drops `NOT NULL`, the `CHECK` constraint, and the `DEFAULT 'knight'`. |
| v5→v6 | Adds the `board_messages` table and the `idx_board_entity` index. |
| v6→v7 | Drops `missions.knight`, adds `missions.doctrine_mission TEXT`, and rewrites `mission_type` `knight` to `agent`. |

### The v6→v7 contract

`ALTER TABLE ... DROP COLUMN` needs SQLite >= 3.35 and would leave the column order disagreeing with `schema.sql`, so v6→v7 uses the rename-create-copy-drop pattern v4→v5 established: `missions` is renamed to `missions_old`, the new table is created with `doctrine_mission` where `knight` was, every row is copied with `NULL` in that position, `missions_old` is dropped, and both indexes are recreated.

**`doctrine_mission` starts empty on every migrated row.** A stored knight value is a bare file name such as `tech-writer` or `feature-implementation/scout.md`, which is not a valid `<doctrine-id>/<mission-id>` reference and can never resolve. Carrying those across would put every upgraded project into `lore health --scope doctrines` errors on missions its maintainer never touched. The audit trail of which persona a historical mission ran under lives on disk instead: `lore init` names retired and orphaned knight files in its report.

One `UPDATE` rewrites the `mission_type` token `knight` to `agent`. That statement is the only code anywhere that reads the token — `mission_type` is stored and exposed, never interpreted (`decisions-004-mission-type-dumb-storage`).

A migration module is a historical record of DDL that ran. `missions.knight` existed, so the migration chain keeps naming it; editing that out would falsify the schema history and break the upgrade path off an older database.

## Steps — Version Detection

### 1. Read current version

On every `get_connection` call, `_run_migrations` executes:

```sql
SELECT value FROM lore_meta WHERE key = 'schema_version'
```

If the row is missing, a `RuntimeError` is raised immediately: the database is considered corrupt.

### 2. Compare versions

- **Equal to `SCHEMA_VERSION`:** No migration needed; return immediately.
- **Greater than `SCHEMA_VERSION`:** A newer database is connected to an older Lore installation. `RuntimeError` is raised: `Database schema version <N> is newer than supported version <M>. Upgrade Lore.`
- **Less than `SCHEMA_VERSION`:** Migrations are needed; proceed to sequential application.

## Steps — Sequential Migration

### 1. Acquire an exclusive write lock

`BEGIN IMMEDIATE` is executed to prevent concurrent migration by another process.

### 2. Re-check version under lock

Another connection may have run the migration between the initial read and lock acquisition. The version is re-read. If it is now `>= SCHEMA_VERSION`, the lock is released and the function returns.

### 3. Run each step in sequence

For each step from `current` to `SCHEMA_VERSION - 1`:

1. The migration module `lore.migrations.v{from_ver}_to_v{to_ver}` is imported via `importlib.import_module`.
2. If the module does not exist, `RuntimeError` is raised: `Migration module ... not found`.
3. If the module has no `migrate` function, `RuntimeError` is raised.
4. `mod.migrate(conn)` is called with the open connection. The migration performs its DDL/DML changes within the existing transaction.
5. `lore_meta` is updated: `schema_version` is set to `to_ver`.

### 4. Commit or rollback

If all steps succeed, `conn.commit()` is called. If any step raises an exception, `conn.rollback()` is called and the exception re-raises. This guarantees that schema_version is only incremented for successfully applied steps.

## Migration Module Contract

Each migration module at `src/lore/migrations/v{N}_to_v{N+1}.py` must expose a single `migrate(conn: sqlite3.Connection)` function. The function receives an open connection with an active `BEGIN IMMEDIATE` transaction. It must not commit or rollback — the caller manages the transaction boundary.

## Initialisation vs Migration

`init_database` (called by `lore init`) creates a fresh schema at the current `SCHEMA_VERSION` from `schema.sql`. It does not run migrations. Migrations only apply to existing databases that were created at an earlier version.

If `lore init` is called on an existing DB that has the `lore_meta` table, it returns `"existing"` without touching the schema. If the `lore_meta` table is missing (corruption), it deletes and recreates the database, returning `"reinitialized"`.

## Failure Modes

| Failure point | Behaviour | Exit code |
|---|---|---|
| `lore_meta` missing | `RuntimeError` propagates | 1 |
| DB version newer than code | `RuntimeError: ... Upgrade Lore.` | 1 |
| Migration module not found | `RuntimeError` propagates | 1 |
| Migration module missing `migrate` | `RuntimeError` propagates | 1 |
| Migration step raises exception | Full rollback; exception propagates | 1 |

## Out of Scope

- Downgrade migrations — there is no rollback to an earlier schema version.
- Dry-run migration preview.
