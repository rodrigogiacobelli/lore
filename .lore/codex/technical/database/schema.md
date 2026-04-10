---
id: tech-db-schema
title: Database Schema
summary: Full SQLite database reference for Lore — DDL for all tables, indexes, pragmas, ID generation algorithm, cascade algorithm, cycle detection, soft-delete filtering, quest status derivation, priority queue SQL, and schema migrations (v1–v6).
related: ["decisions-003-soft-delete-semantics", "decisions-005-auto-close-toggle", "tech-api-surface", "tech-cli-commands", "conceptual-workflows-concurrent-access", "conceptual-workflows-schema-migrations"]
stability: stable
---

# Database Schema

## Connection Setup

Every CLI invocation opens a fresh SQLite connection with the following pragmas executed immediately:

```sql
PRAGMA journal_mode = WAL;
PRAGMA busy_timeout = 5000;
PRAGMA foreign_keys = ON;
```

The database file is always at `.lore/lore.db` relative to the project root. `db.get_connection` obtains this path via `paths.db_path(project_root)` from `src/lore/paths.py` rather than constructing it inline. See tech-arch-project-root-detection (lore codex show tech-arch-project-root-detection) for how the project root is located.

## Data Model

All timestamp fields (`created_at`, `updated_at`, `closed_at`, `deleted_at`) are managed automatically by the application. AI agents never set or modify these fields.

All timestamps are stored as ISO 8601 strings in UTC with `Z` suffix (e.g., `2025-01-15T09:30:00Z`). Generated via `datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")`.

### Quest

| Field | Type | Description |
|-------|------|-------------|
| id | string | Unique hash-based ID (e.g., `q-a1b2`) |
| title | string | Quest title |
| description | string | Optional detailed description |
| status | enum | `open`, `in_progress`, `closed` |
| priority | int | 0 (critical) through 4 (backlog) |
| auto_close | int | `0` (disabled, default for new quests) or `1` (enabled). Controls whether the quest auto-closes when all missions are closed. |
| created_at | datetime | Auto-set on creation |
| updated_at | datetime | Auto-set on any modification |
| closed_at | datetime | Auto-set when status becomes `closed` |
| deleted_at | datetime | Soft-delete timestamp (NULL = active, ISO 8601 = soft-deleted) |

A Quest's status is derived: if any Mission is `in_progress`, the Quest is `in_progress`. If `auto_close` is enabled (`1`) and all Missions are `closed`, the Quest is automatically `closed`. If `auto_close` is disabled (`0`), the Quest never auto-closes and must be manually closed via `lore done q-xxxx`. Otherwise it's `open`. See [Quest Status Derivation](#quest-status-derivation) for the full algorithm.

### Mission

| Field | Type | Description |
|-------|------|-------------|
| id | string | Unique hierarchical ID (e.g., `q-a1b2/m-f3c1`) |
| quest_id | string | Parent quest ID (nullable for standalone missions) |
| title | string | Mission title |
| description | string | Detailed description of what needs to be done |
| status | enum | `open`, `in_progress`, `blocked`, `closed` |
| mission_type | string | Free-form type label. Nullable — NULL means no type assigned. |
| priority | int | 0 (critical) through 4 (backlog) |
| knight | string | Filename of the Knight in `.lore/knights/` (optional) |
| block_reason | string | Why it's blocked (when status is `blocked`) |
| created_at | datetime | Auto-set on creation |
| updated_at | datetime | Auto-set on any modification |
| closed_at | datetime | Auto-set when status becomes `closed` |
| deleted_at | datetime | Soft-delete timestamp (NULL = active, ISO 8601 = soft-deleted) |

### Dependency

| Field | Type | Description |
|-------|------|-------------|
| id | int | Auto-increment |
| from_id | string | The mission that is blocked |
| to_id | string | The mission it depends on |
| type | enum | `blocks` |
| deleted_at | datetime | Soft-delete timestamp (NULL = active, ISO 8601 = soft-deleted) |

### Board Message

| Field | Type | Description |
|-------|------|-------------|
| id | int | Auto-increment integer primary key |
| entity_id | string | Quest or mission ID this message belongs to (`q-xxxx` or `q-xxxx/m-yyyy`) — no FK constraint |
| sender | string | Optional. Lore ID of the posting agent (`q-xxxx` or `q-xxxx/m-yyyy` format). NULL when not provided. |
| message | string | The operational note. NOT NULL. |
| created_at | datetime | Auto-set on creation. ISO 8601 UTC string. |
| deleted_at | datetime | Soft-delete timestamp (NULL = active, ISO 8601 = soft-deleted) |

Board messages carry lightweight runtime operational notes posted by agents to guide successor missions. They are distinct from artifact instances (ADR-007), which carry structured work output.

## DDL

```sql
CREATE TABLE quests (
    id          TEXT PRIMARY KEY,
    title       TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    status      TEXT NOT NULL DEFAULT 'open' CHECK (status IN ('open', 'in_progress', 'closed')),
    priority    INTEGER NOT NULL DEFAULT 2 CHECK (priority BETWEEN 0 AND 4),
    auto_close  INTEGER NOT NULL DEFAULT 0 CHECK (auto_close IN (0, 1)),
    created_at  TEXT NOT NULL,
    updated_at  TEXT NOT NULL,
    closed_at   TEXT,
    deleted_at  TEXT  -- NULL = active, ISO 8601 timestamp = soft-deleted
);

CREATE TABLE missions (
    id           TEXT PRIMARY KEY,
    quest_id     TEXT REFERENCES quests(id), -- nullable: NULL = standalone mission
    -- No ON DELETE CASCADE. Quests use soft-delete (rows remain). RESTRICT (the default) catches bugs.
    title        TEXT NOT NULL,
    description  TEXT NOT NULL DEFAULT '',
    status       TEXT NOT NULL DEFAULT 'open' CHECK (status IN ('open', 'in_progress', 'blocked', 'closed')),
    mission_type TEXT,                           -- nullable; free-form string; NULL = no type assigned
    priority     INTEGER NOT NULL DEFAULT 2 CHECK (priority BETWEEN 0 AND 4),
    knight       TEXT,
    block_reason TEXT,
    created_at   TEXT NOT NULL,
    updated_at   TEXT NOT NULL,
    closed_at    TEXT,
    deleted_at   TEXT  -- NULL = active, ISO 8601 timestamp = soft-deleted
);

-- CHECK constraints enforce valid status values. The application enforces valid status *transitions*.
-- These are complementary layers of validation.

CREATE TABLE dependencies (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    from_id    TEXT NOT NULL,
    to_id      TEXT NOT NULL,
    type       TEXT NOT NULL DEFAULT 'blocks' CHECK (type IN ('blocks')),
    deleted_at TEXT,  -- NULL = active, ISO 8601 timestamp = soft-deleted
    UNIQUE(from_id, to_id, type)
);
```

```sql
CREATE TABLE board_messages (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    entity_id  TEXT NOT NULL,
    sender     TEXT,
    message    TEXT NOT NULL,
    created_at TEXT NOT NULL,
    deleted_at TEXT
);
```

**Design notes:**
- No FK constraint on `entity_id` — deliberate, consistent with the `dependencies` table and ADR-003. Since entities use soft-delete (physical rows remain), FK constraints would not provide meaningful protection. Application-level validation (`AND deleted_at IS NULL` check before insert) is the enforcement layer.
- No UNIQUE constraint — multiple messages per entity are expected and normal.
- `message TEXT NOT NULL` — an empty board message is meaningless; the DB-layer constraint guards against it.
- `sender` nullable — sender is optional; NULL when not provided.
- `id INTEGER PRIMARY KEY AUTOINCREMENT` — integer PK, matching the `dependencies` table. This is the first soft-deletable table with an integer PK (all other soft-deletable tables use text PKs). The soft-delete SQL pattern is identical.

See also: [`lore_meta`](#schema-version) for the metadata table used in schema versioning.

### Dependency Semantics

The dependency direction uses `from_id` and `to_id` with type `blocks`: `from_id` is the **blocked mission** (the one that depends on something), and `to_id` is the **dependency** (the mission it depends on). Read it as: "`from_id` depends on `to_id`", or equivalently "`to_id` blocks `from_id`." This matches the `lore needs A:B` syntax where A = `from_id`, B = `to_id`.

Memory aid: `from_id` needs `to_id` — read left-to-right as "FROM depends on TO."

### Foreign Keys on Dependencies

The `dependencies` table does **not** have foreign key constraints on `from_id` / `to_id`. Since missions use soft-delete (physical rows remain in the database), dependency rows never become orphaned. The application validates mission existence before inserting dependencies, making FK constraints redundant. All queries that read dependencies must filter by `deleted_at IS NULL` to exclude soft-deleted dependencies.

### Indexes

```sql
-- Quest lookups by status (dashboard, list commands)
CREATE INDEX idx_quests_status ON quests(status);

-- Mission lookups by quest (show quest, missions command)
CREATE INDEX idx_missions_quest_id ON missions(quest_id);

-- Mission filtering by status and priority (ready queue)
CREATE INDEX idx_missions_status_priority ON missions(status, priority, created_at);

-- Dependency lookups in both directions
CREATE INDEX idx_deps_from ON dependencies(from_id);
CREATE INDEX idx_deps_to ON dependencies(to_id);

-- Board message lookups by entity (lore show performance)
CREATE INDEX idx_board_entity ON board_messages(entity_id);
```

### Schema Version

The schema includes a metadata table to support migrations:

```sql
CREATE TABLE lore_meta (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

INSERT INTO lore_meta (key, value) VALUES ('schema_version', '4');
```

**Current state note:** As of this writing, source code is at schema v4 (`SCHEMA_VERSION = 4` in `db.py`; `schema_version = '4'` in `schema.sql`). Two pending migrations are documented below:
- v4→v5: free-form mission type (see `spec-free-form-mission-type`) — removes enum constraint from `mission_type`
- v5→v6: board messages (this spec) — adds `board_messages` table

The `schema.sql` insert will be updated to `'6'` (and `SCHEMA_VERSION` bumped to `6`) once both migrations ship. The `schema.sql` file must always reflect the current deployed schema.

On connection open, the application reads `schema_version` and runs any pending migrations sequentially. Migrations are Python functions in `src/lore/migrations/`, named `v{N}_to_v{N+1}.py`, each exporting a `migrate(conn)` function that receives an open SQLite connection. They execute in version order. After each successful migration, `schema_version` is updated within the same transaction. If a migration fails, the transaction is rolled back and the application exits with an error.

Fresh databases created from `schema.sql` are initialized at the latest schema version and do not need to run migrations. The `schema.sql` file always reflects the current schema with all columns.

### Migration: v1 to v2

Adds `deleted_at` columns to support soft-delete semantics:

```sql
ALTER TABLE quests ADD COLUMN deleted_at TEXT;
ALTER TABLE missions ADD COLUMN deleted_at TEXT;
ALTER TABLE dependencies ADD COLUMN deleted_at TEXT;
```

### Migration: v2 to v3

Adds the `auto_close` column to the quests table:

```sql
ALTER TABLE quests ADD COLUMN auto_close INTEGER NOT NULL DEFAULT 1 CHECK (auto_close IN (0, 1));
```

**Note:** The migration uses `DEFAULT 1` so existing quests retain the auto-close-enabled behavior they had before this feature existed. The fresh `schema.sql` uses `DEFAULT 0` for new quests (auto-close disabled by default). This intentional difference prevents surprising existing users while establishing the new default for new projects.

### Migration: v3 to v4

Adds the `mission_type` column to the missions table:

```sql
ALTER TABLE missions ADD COLUMN mission_type TEXT NOT NULL DEFAULT 'knight' CHECK (mission_type IN ('knight', 'constable', 'human'));
```

All existing missions receive `'knight'` as their type via the DEFAULT clause. No data backfill is needed.

### Migration: v4 to v5

Removes the `mission_type` enum constraint. SQLite does not support `ALTER TABLE ... DROP CONSTRAINT` or `ALTER COLUMN`, so removing the `CHECK` constraint, `NOT NULL`, and `DEFAULT 'knight'` from an existing column requires recreating the table using the rename-create-copy-drop pattern.

**Steps:**

1. Rename `missions` to `missions_old`
2. Create new `missions` table with `mission_type TEXT` — nullable, no DEFAULT, no CHECK; all other columns and constraints unchanged
3. Copy all rows: `INSERT INTO missions SELECT id, quest_id, title, description, status, mission_type, priority, knight, block_reason, created_at, updated_at, closed_at, deleted_at FROM missions_old`
4. Drop `missions_old`
5. Recreate `idx_missions_quest_id` and `idx_missions_status_priority` (these were dropped with the old table)

**Data preservation:** Existing `knight`, `constable`, and `human` values are preserved as-is. They remain valid free-form strings; no data transformation is performed.

### Migration: v5 to v6

**Prerequisite:** v4→v5 (free-form mission type) must ship first. Before implementing this migration, verify that `schema.sql` shows `mission_type TEXT` (no CHECK, no NOT NULL, no DEFAULT) and that `SCHEMA_VERSION` in `db.py` is `5`.

Adds the `board_messages` table and its index. No table recreation is needed — `board_messages` is a new table, so this is a pure addition.

```sql
CREATE TABLE board_messages (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    entity_id  TEXT NOT NULL,
    sender     TEXT,
    message    TEXT NOT NULL,
    created_at TEXT NOT NULL,
    deleted_at TEXT
);

CREATE INDEX idx_board_entity ON board_messages(entity_id);
```

The migration module (`src/lore/migrations/v5_to_v6.py`) runs these two statements. The migration runner in `db.py` handles updating `schema_version` to `6` within the same transaction. After this migration ships, `SCHEMA_VERSION` in `db.py` must be bumped to `6`.

## Typed Model Hydration

Lore exposes typed Python dataclasses in `lore.models` for all four DB-backed entity types.
`db.py` return type annotations are **not changed** — internal functions continue to return
`sqlite3.Row` and `list[sqlite3.Row]`. Typed models are a presentation layer constructed
via classmethods.

| DB Type | Python Model | Hydration Method | Source Function |
|---------|-------------|------------------|-----------------|
| `quests` row | `Quest` | `Quest.from_row(row)` | `db.get_quest()`, `db.list_quests()` |
| `missions` row | `Mission` | `Mission.from_row(row)` | `db.get_mission()`, `db.get_missions_for_quest()`, `db.get_ready_missions()` |
| `dependencies` row | `Dependency` | `Dependency.from_row(row)` | No current public caller — see note |
| `board_messages` dict | `BoardMessage` | `BoardMessage.from_dict(d)` | `db.get_board_messages()` returns `list[dict]` |

**`auto_close` coercion:** `Quest.from_row()` must call `bool(row["auto_close"])` explicitly.
The schema stores `auto_close` as `INTEGER` (0 or 1). The `Quest.auto_close` Python field is
`bool`. Passing the raw `int` would satisfy Python's runtime (no annotation enforcement in
dataclasses), but mypy would flag it. The coercion is in `from_row()`, not in the schema.

**`Dependency` DB gap:** No public `db.py` function currently returns a full `dependencies`
row as a `sqlite3.Row`. The detail functions (`get_mission_depends_on_details`,
`get_mission_blocks_details`) return joined dicts with `id`, `title`, `status`, `deleted_at`
— not the full dep row shape (`id`, `from_id`, `to_id`, `type`, `deleted_at`). A
`get_dependency()` function must be added to `db.py` before `Dependency` typed objects are
constructible via the public API.

**`BoardMessage` read-side contract:** The `board_messages` table has a `deleted_at` column,
but the `BoardMessage` Python model does not include it. This is intentional: `get_board_messages()`
filters soft-deleted rows at the SQL layer (`WHERE deleted_at IS NULL`), so Realm never
receives deleted messages. The typed model reflects the actual read-side contract. See the
`get_board_messages` query contract below and ADR-003 for soft-delete semantics.

## Query Contracts

### `get_board_messages(project_root, entity_id)`

Returns all active board messages for a quest or mission, ordered by creation time:

```sql
SELECT id, sender, message, created_at
FROM board_messages
WHERE entity_id = ? AND deleted_at IS NULL
ORDER BY created_at ASC
```

Returns a list of dicts with keys `id`, `sender`, `message`, `created_at`. `deleted_at` is not included — soft-deleted rows are filtered at the query layer.

### `add_board_message(project_root, entity_id, message, sender=None)`

Validates entity existence before inserting (runs inside the same `BEGIN IMMEDIATE` transaction as the insert):

- If `entity_id` matches `q-xxxx` format: `SELECT id FROM quests WHERE id = ? AND deleted_at IS NULL`
- If `entity_id` matches `q-xxxx/m-yyyy` format: `SELECT id FROM missions WHERE id = ? AND deleted_at IS NULL`
- Not found → `{"ok": False, "error": "Quest/Mission \"<id>\" not found"}`

Note: this is stricter than `add_dependency()`, which validates existence but does not filter by `deleted_at IS NULL`. The board feature prevents posting to soft-deleted entities. The direct precedents are `get_quest()` and `get_mission()` in `db.py`, both of which filter by `AND deleted_at IS NULL`.

On success returns `{"ok": True, "id": <N>, "entity_id": "<id>", "sender": "<sender or None>", "created_at": "<timestamp>"}`.

### `get_mission_depends_on_details(project_root, mission_id)`

Returns rich dependency detail for missions that the given mission depends on (its "needs"):

```sql
SELECT d.to_id, m.id, m.title, m.status, m.deleted_at FROM dependencies d
LEFT JOIN missions m ON d.to_id = m.id
WHERE d.from_id = ?
  AND d.deleted_at IS NULL
```

Returns a list of dicts. `d.deleted_at IS NULL` filters soft-deleted dependency rows at the query layer. Missions joined via LEFT JOIN that are themselves soft-deleted may return NULL title/status; callers handle NULL gracefully (e.g., render `[unknown]` for title).

### `get_mission_blocks_details(project_root, mission_id)`

Returns rich dependency detail for missions that depend on the given mission (missions it "blocks"):

```sql
SELECT d.from_id, m.id, m.title, m.status, m.deleted_at FROM dependencies d
LEFT JOIN missions m ON d.from_id = m.id
WHERE d.to_id = ?
  AND d.deleted_at IS NULL
```

Returns a list of dicts. `d.deleted_at IS NULL` filters soft-deleted dependency rows at the query layer.

### `get_all_dependencies_for_quest(project_root, quest_id)`

Returns all active dependency rows where the blocked mission (`from_id`) belongs to the given quest. Used by `_show_quest()` to build the topologically-sorted mission list in a single query (no N+1 per mission).

```sql
SELECT d.from_id, d.to_id
FROM dependencies d
JOIN missions m ON m.id = d.from_id
WHERE m.quest_id = ?
  AND m.deleted_at IS NULL
  AND d.deleted_at IS NULL
```

Returns a list of `{"from_id": ..., "to_id": ...}` dicts. Cross-quest upstream nodes (`to_id` belonging to a different quest) are included naturally — they appear as root-level ancestors in the tree rendering. Both the mission filter (`m.deleted_at IS NULL`) and the dependency filter (`d.deleted_at IS NULL`) are required.

### `delete_board_message(project_root, message_id: int)`

Soft-deletes a board message by integer ID:

```python
cursor = conn.execute(
    "UPDATE board_messages SET deleted_at = ? WHERE id = ? AND deleted_at IS NULL",
    (now, message_id)
)
if cursor.rowcount == 0:
    return {"ok": False, "error": f"Board message {message_id} not found."}
return {"ok": True, "deleted_at": now}
```

**Idempotency note:** This intentionally does not distinguish "never existed" from "already deleted" — both return not-found. This diverges from `delete_mission()`/`delete_quest()` (which return `"already_deleted": True` as a success case). Board message IDs are ephemeral runtime context, not tracked entities; the distinction has no meaningful value. This is the first soft-delete in the codebase on an integer-keyed row; the SQL pattern is identical to string-keyed soft-deletes.

## Quest Status Derivation

Quest status is a **materialized derived field**. It is stored in the `status` column for query efficiency, but its value is always recomputed from child mission statuses whenever a mission changes status. The only CLI command that sets Quest status directly is `lore done q-xxxx`, which manually closes a quest (required for quests with `auto_close=0`). The derivation logic:

```python
def derive_quest_status(quest_id: str) -> str:
    # Only considers missions where deleted_at IS NULL
    quest = get_quest(quest_id)
    missions = get_active_missions_for_quest(quest_id)
    if not missions:
        return "open"  # empty quest (or all missions soft-deleted) stays open
    statuses = {m.status for m in missions}
    if all(s == "closed" for s in statuses):
        if quest.auto_close:
            return "closed"
        # auto_close disabled: never auto-derive to closed
        if "in_progress" in statuses:
            return "in_progress"
        return "open"
    if "in_progress" in statuses:
        return "in_progress"
    return "open"
```

When `auto_close` is `0` (disabled), the derivation never transitions the quest to `closed`. The quest remains `open` even when all missions are closed, until the user explicitly closes it via `lore done q-xxxx`.

**Soft-deleted missions are excluded from status derivation.** The `get_active_missions_for_quest` query adds `AND deleted_at IS NULL`. If all missions in a quest are soft-deleted, the quest derives to `open` (empty quest behavior).

This runs inside the same transaction as the mission status change. Quest `closed_at` is set when the derived status transitions to `closed`, and cleared (`NULL`) if it transitions away from `closed`. Adding a new mission to a closed quest triggers re-derivation, which returns `open`, effectively reopening the quest.

**Note on `blocked` missions:** If all missions in a quest are `blocked`, the derivation returns `open` (the fallback). The quest status does not have a `blocked` state.

## Priority Queue

The `lore ready` command returns unblocked Missions sorted by priority level:

1. Filter: only missions with status `open`
2. Filter: only missions with no open/in_progress dependencies (all `blocks` dependencies are `closed`)
3. Sort: by priority ascending (P0 first, P4 last)
4. Tiebreak: by `created_at` ascending (older tasks first)

The SQL query:

```sql
SELECT m.* FROM missions m
WHERE m.status = 'open'
  AND m.deleted_at IS NULL
  AND NOT EXISTS (
    SELECT 1 FROM dependencies d
    JOIN missions dep ON dep.id = d.to_id
    WHERE d.from_id = m.id
      AND d.type = 'blocks'
      AND d.deleted_at IS NULL
      AND dep.status != 'closed'
  )
ORDER BY m.priority ASC, m.created_at ASC
LIMIT ?;
```

The `m.deleted_at IS NULL` filter excludes soft-deleted missions. The `d.deleted_at IS NULL` filter ensures soft-deleted dependencies do not block missions. The `LIMIT` parameter comes from the optional count argument to `lore ready` (default 1).

## ID Generation

IDs are generated from `uuid4()`, hex-encoded, and truncated to a short hash:

- Take the first 4 hex characters of a new `uuid4().hex`
- Query the relevant table for a collision
- If a collision exists, try 5 characters, then 6
- If 6 characters still collide (astronomically unlikely), raise an error
- Prefix indicates type: `q-` for quests, `m-` for missions

```python
import uuid

def generate_id(prefix: str, existing_ids: set[str]) -> str:
    hex_str = uuid.uuid4().hex
    for length in (4, 5, 6):
        candidate = f"{prefix}-{hex_str[:length]}"
        if candidate not in existing_ids:
            return candidate
    raise RuntimeError(f"ID collision after 6 chars for prefix {prefix}")
```

Mission IDs are hierarchical: `q-a1b2/m-f3c1`. Standalone missions (no quest) use just `m-[hash]`.

**Uniqueness check scope:** For quest-bound missions, check against all mission IDs in the same quest. For standalone missions, check against all standalone mission IDs. For quests, check against all IDs in the quests table. The PRIMARY KEY constraint provides a final safety net.

**Concurrency:** ID generation and insertion must occur within the same `BEGIN IMMEDIATE` transaction.

## Cascade Behavior

When a Mission is closed via `lore done`:

1. Set the mission's `status` to `closed` and `closed_at` to the current timestamp.
2. Find all active missions that depend on this mission (`SELECT from_id FROM dependencies WHERE to_id = ? AND type = 'blocks' AND deleted_at IS NULL`).
3. For each dependent mission, check if **all** its `blocks` dependencies are now `closed`. The cascade behavior depends on the dependent mission's current status:
   - **`open`**: The dependency is satisfied. If all other `blocks` dependencies are also `closed`, the mission will appear in `lore ready` results. No status change occurs.
   - **`in_progress`**: No change. The mission is already being worked on.
   - **`blocked`**: No change. The `blocked` status was set manually via `lore block` with a reason. The dependency system does not auto-unblock manually blocked missions — the orchestrator must explicitly `lore unblock` the mission.
   - **`closed`**: No change.
4. Recompute and persist the parent quest's status. For standalone missions (`quest_id IS NULL`), this step is skipped.

All steps happen inside a single `BEGIN IMMEDIATE` transaction.

## Dependency Cycle Detection

When adding a dependency via `lore needs A:B` (A depends on B, i.e., `from_id=A`, `to_id=B`), the application checks for cycles before inserting. The check is a depth-first traversal from B through forward dependency edges: starting from B, follow what B depends on, then what those depend on, etc. If A is reachable from B by following forward edges, inserting the edge A->B would create a cycle.

```python
def would_create_cycle(from_id: str, to_id: str) -> bool:
    """Return True if adding from_id->to_id would create a cycle.

    Traverses forward edges from to_id: finds what to_id depends on,
    then what those depend on, etc. If from_id is reachable,
    adding the edge would close a cycle.
    """
    visited = set()
    stack = [to_id]
    while stack:
        current = stack.pop()
        if current == from_id:
            return True
        if current in visited:
            continue
        visited.add(current)
        # Follow FORWARD edges: find what current depends on
        # SQL: SELECT to_id FROM dependencies WHERE from_id = current AND deleted_at IS NULL
        for dep in get_dependencies_of(current):
            stack.append(dep)
    return False
```

The traversal filters by `deleted_at IS NULL` to exclude soft-deleted dependencies.

## Soft-Delete Query Filtering

All queries must add `deleted_at IS NULL` filters to exclude soft-deleted entities from normal operations. Soft-deleted rows remain in the database for historical record but are invisible to standard CLI output.

### Affected Queries

- **Ready queue:** `AND m.deleted_at IS NULL` on the outer WHERE clause. `AND d.deleted_at IS NULL` in the dependency subquery.
- **Quest status derivation:** `AND deleted_at IS NULL` on the `SELECT status FROM missions WHERE quest_id = ?` query.
- **List/dashboard/stats:** `AND deleted_at IS NULL` on `list_quests`, `list_missions`, `get_dashboard_quests`, and `get_aggregate_stats` queries.
- **Show:** `lore show` on a soft-deleted entity returns `<Entity> "<id>" not found (deleted on <timestamp>)` with exit code 1. In `--json` mode: `{"error": "<Entity> \"<id>\" not found", "deleted_at": "<timestamp>"}`.
- **Dependencies display:** `lore show <mission>` renders a `Dependencies:` section with flat `Needs:` and `Blocks:` sub-sections showing direct upstream and downstream missions. Both `get_mission_depends_on_details` and `get_mission_blocks_details` filter by `AND d.deleted_at IS NULL` — soft-deleted dependency rows are excluded at the query layer. Missions joined via LEFT JOIN that are themselves soft-deleted may return NULL title/status; rendering code handles NULL gracefully (e.g., `[unknown]` for title).
- **Dependency cycle detection:** `AND deleted_at IS NULL` in the traversal query so soft-deleted dependencies are not considered.
- **Board messages display:** `AND deleted_at IS NULL` in `get_board_messages()`. Soft-deleted messages are invisible in `lore show` output. The `add_board_message()` validation also uses `AND deleted_at IS NULL` to prevent posting to soft-deleted entities.
