---
id: ref-lore_db-core
title: Lore DB — core cluster
summary: Reference doc for the Lore SQLite database — the intent, history, and non-enforced
  rules around the five tables (quests, missions, dependencies, board_messages, lore_meta).
  Schema source of truth is `src/lore/defaults/schema.sql`; algorithms live in `src/lore/db.py`
  and `src/lore/migrations/`.
related:
- decisions-003-soft-delete-semantics
- decisions-005-auto-close-toggle
- conceptual-workflows-concurrent-access
- conceptual-workflows-schema-migrations
- ref-lore_api-core
- ref-lore_cli-commands
---

# Lore DB — core cluster

**Covers:** `quests`, `missions`, `dependencies`, `board_messages`, `lore_meta`
**Source of truth:** `src/lore/defaults/schema.sql` (DDL, indexes, current schema version), `src/lore/db.py` (queries, derivation, cascade, cycle detection), `src/lore/migrations/` (one `v{N}_to_v{N+1}.py` per version bump).

## Why this exists

Lore is a single-file SQLite database that holds all task state for a project. Two consumers depend on it: the CLI (`lore.cli`) and Realm via the Python API (`lore.db`, `lore.models`). Every entity in the system either lives here (quests, missions, dependencies, board messages) or in a sibling file-based store (knights, doctrines, watchers, artifacts, codex, glossary).

This doc captures the design choices that the schema cannot express and the rules every query must follow.

## Gotchas

- **Soft-delete is universal.** `quests`, `missions`, `dependencies`, and `board_messages` all carry a `deleted_at` column (NULL = active, ISO 8601 UTC = tombstoned). Every read query MUST filter `WHERE deleted_at IS NULL`. Soft-delete tombstones are why FK constraints are absent — see decisions-003-soft-delete-semantics.

- **No FK on `dependencies` or `board_messages`.** Both tables reference quest/mission IDs without FK constraints. Application code validates existence inside the same `BEGIN IMMEDIATE` transaction as the insert. FK would not protect anything once soft-delete is the default — physical rows never disappear.

- **Quest `status` is materialized derived.** The column exists for query efficiency but is recomputed from child mission statuses on every mission change (`db.derive_quest_status`). The only direct write is `lore done q-xxxx`, which is required for quests with `auto_close=0`. Adding a mission to a closed quest re-derives and effectively reopens the quest.

- **`auto_close` default differs new vs migrated.** Fresh `schema.sql` ships `DEFAULT 0` (off — explicit close required). The v2→v3 migration uses `DEFAULT 1` to preserve existing-project behaviour. Same column, two answers depending on origin. See decisions-005-auto-close-toggle.

- **Empty quests derive to `open`, not `closed`.** A quest with zero active missions stays open even when `auto_close=1`. Soft-deleted-only quests behave the same. The fallback prevents accidentally-closed empty quests from drifting silently.

- **`blocked` missions never close a quest.** Quest status has no `blocked` state. A quest where every mission is `blocked` derives to `open`, not `blocked`.

- **Cascade only auto-unblocks `open` missions.** When a mission closes, dependents transition from "waiting" to "ready" only if their status is `open`. Manually `blocked` missions (set via `lore block`) are never auto-unblocked — the orchestrator must `lore unblock` them explicitly. This protects deliberate human/orchestrator pauses from being trampled by an unrelated dependency clearing.

- **Mission `mission_type` is free-form (post-v5).** The column has no `CHECK` constraint and no `NOT NULL`. Pre-v5 it was an enum (`knight | constable | human`); the v4→v5 migration removed the constraint so consuming layers can interpret types without a schema bump per type. Existing values were preserved as plain strings.

- **Dependency direction reads "FROM depends on TO".** `from_id` is the blocked mission; `to_id` is what it depends on. The `lore needs A:B` syntax matches: A = `from_id`, B = `to_id`. Read left-to-right: "FROM depends on TO." This is the single mnemonic that keeps cycle detection and cascade logic legible.

- **Cycle detection is a forward-edge DFS from `to_id`.** Adding `from_id → to_id` is rejected if `from_id` is reachable from `to_id` by following outgoing dependency edges (filtered by `deleted_at IS NULL`). The check runs inside the same transaction as the insert.

- **`board_messages` uses `INTEGER PK`; all other entities use `TEXT PK`.** First soft-deletable table with an integer key. The soft-delete SQL pattern is identical — only the PK type differs.

- **`delete_board_message` collapses "never existed" with "already deleted".** Returns not-found in both cases. Deliberate divergence from `delete_mission` / `delete_quest`, which return `{"already_deleted": True}` as a success case. Board messages are ephemeral runtime context; the distinction has no value.

- **Connection pragmas are per-process.** Every CLI invocation opens a fresh connection and applies `journal_mode=WAL`, `busy_timeout=5000`, `foreign_keys=ON`. Never call `sqlite3.connect()` directly — always go through `db.get_connection()` so the pragmas are guaranteed.

- **All timestamps are ISO 8601 UTC with `Z` suffix.** Generated via `datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")`. Application-managed only — agents never set `created_at`, `updated_at`, `closed_at`, `deleted_at`.

- **ID generation: 4→5→6 hex with collision retry.** IDs come from `uuid4().hex[:4]` with retry to length 5 then 6 on collision. Six-char collision raises. Mission IDs are hierarchical (`q-a1b2/m-f3c1`); standalone missions use just `m-<hash>`. Generation and insert run in the same `BEGIN IMMEDIATE` transaction.

## Shape

| Table | ~Cols | Purpose |
|-------|-------|---------|
| `quests` | 10 | Bodies of work (feature, fix, refactor) |
| `missions` | 13 | Unit of work an agent claims and closes |
| `dependencies` | 5 | `blocks` edges between missions (DAG) |
| `board_messages` | 6 | Ephemeral runtime notes from one agent to the next |
| `lore_meta` | 2 | `schema_version` and other metadata |

Indexes (see `schema.sql` for definitions): `idx_quests_status`, `idx_missions_quest_id`, `idx_missions_status_priority`, `idx_deps_from`, `idx_deps_to`, `idx_board_entity`.

## Migrations

Each version bump lives at `src/lore/migrations/v{N}_to_v{N+1}.py` and exports `migrate(conn)`. Migrations run on connection open in version order, each in its own transaction, with `schema_version` updated in the same transaction. Failure rolls back and exits with an error. Fresh databases skip migrations — `schema.sql` always reflects the current shape.

When adding a migration: bump `SCHEMA_VERSION` in `db.py`, update the `INSERT INTO lore_meta` line in `schema.sql` to the new value, and add the migration module. The intent of any non-trivial migration (e.g. v4→v5 removing the `mission_type` enum via rename-create-copy-drop) belongs in this doc's Gotchas above or in an ADR — not duplicated in the migration source.

## Read-side contracts

Typed Python models in `lore.models` (`Quest`, `Mission`, `Dependency`, `BoardMessage`) are constructed via `from_row` / `from_dict` classmethods. `db.py` itself returns `sqlite3.Row` and dict shapes — the typed layer is a presentation concern. Two notable points:

- `Quest.from_row()` calls `bool(row["auto_close"])` explicitly; the column is `INTEGER` but the model field is `bool`.
- `BoardMessage` does not include `deleted_at` — `get_board_messages` filters at the SQL layer, so the typed model reflects the read-side contract, not the storage shape.
