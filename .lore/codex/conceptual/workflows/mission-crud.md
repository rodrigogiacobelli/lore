---
id: conceptual-workflows-mission-crud
title: Mission CRUD Operations
summary: 'What the system does internally when creating, listing, editing, deleting,
  and viewing mission detail via the CLI, including active-status filtering and soft-delete
  behaviour.

  '
related:
- conceptual-entities-mission
- conceptual-workflows-quest-crud
---

# Mission CRUD Operations

This document covers `lore new mission`, `lore missions`, `lore edit <mission-id>`, `lore delete <mission-id>`, and the mission detail view via `lore show <mission-id>`.

## Preconditions

- The Lore project has been initialised.
- For scoped missions: the parent quest ID (`-q <quest-id>`) must exist.
- For edit and delete: the mission ID must match `q-<hex>/m-<hex>` or `m-<hex>`.

## Steps — Create (`lore new mission <title>`)

### 1. Validate priority

The `--priority` option (default `2`) is validated against `[0, 4]` before any database access.

### 2. Infer parent quest (optional)

If `-q / --quest` is not supplied, the system queries all non-closed quests. If exactly one exists, that quest is used as the parent automatically. If zero or more than one non-closed quest exist, the mission is created standalone (no parent quest).

### 3. Generate mission ID

`create_mission` in `lore.db` opens a `BEGIN IMMEDIATE` transaction. For a quest-scoped mission the ID is `<quest-id>/m-<4-6 hex>`. For standalone the ID is `m-<4-6 hex>`.

### 4. Reopen a closed parent quest

If the specified parent quest has `status = 'closed'`, it is automatically set back to `'open'` before the mission is inserted.

### 5. Insert the mission row

Inserted with status `open`, the supplied fields (`title`, `description`, `priority`, `knight`, `mission_type`), and UTC timestamps.

### 6. Commit and report

Text: `Created mission <id>`. JSON: `{"id": "<id>"}`.

## Steps — List (`lore missions [<quest-id>]`)

### 1. Validate quest (if specified)

If a `<quest-id>` argument is supplied, the quest is looked up. If not found, an error is returned.

### 2. Fetch missions

`list_missions` queries `missions WHERE deleted_at IS NULL`. Without `--all`, only `open`, `in_progress`, and `blocked` missions are returned (closed missions are excluded by default). Results are grouped by `quest_id`.

### 3. Render

Quest-bound missions are displayed under a `Quest: <title> (<quest-id>)` header. Standalone missions are grouped under `Standalone:`. Each line:

```
  <id>  P<priority>  [<status>]  [<mission_type>]  <title>  [<knight>]
```

`mission_type` and `knight` brackets are omitted when null. In JSON mode: `{"missions": [{id, quest_id, title, status, priority, mission_type, knight, created_at}, ...]}`.

### 4. Active-status filtering

By default, only missions in `open`, `in_progress`, or `blocked` status are shown. Pass `--all` to include `closed` missions. Soft-deleted missions (`deleted_at IS NOT NULL`) are never shown.

## Steps — Edit (`lore edit <mission-id>`)

### 1. ID routing

IDs containing `m-` are routed to `_edit_mission`. At least one of `--title`, `--description`, `--priority`, `--knight`, `--no-knight`, or `--type` must be provided.

### 2. Mutual exclusion

`--knight` and `--no-knight` cannot both be supplied.

### 3. Apply changes

`edit_mission` in `lore.db` updates only the supplied fields and sets `updated_at`. Passing `--no-knight` sets the knight field to `NULL`.

### 4. Report

Text: `Updated mission <id>`. JSON: full mission object including `dependencies.needs` and `dependencies.blocks`.

## Steps — Delete (`lore delete <mission-id>`)

Deletion is a **soft-delete**: sets `deleted_at` on the mission row.

### 1. Idempotent warning

If already deleted, prints `Warning: Mission <id> was already deleted on <timestamp>` and exits with code 0.

### 2. Soft-delete

Sets `deleted_at` and `updated_at` in a transaction. Dependencies whose `from_id` or `to_id` is this mission are NOT automatically deleted — they remain with `deleted_at` handling at the caller level.

### 3. Report

Text: `Deleted mission <id>`. JSON: `{"id": "<id>", "deleted_at": "..."}`.

## Failure Modes

| Failure point | Behaviour | Exit code |
|---|---|---|
| Priority out of range | `ClickException` to stderr | 1 |
| Parent quest not found | `ValueError` message to stderr | 1 |
| Invalid mission ID format | Error to stderr | 1 |
| Mission not found on edit | Error with optional `deleted_at` to stderr | 1 |
| Mission not found on delete | Error to stderr | 1 |
| Already deleted (delete) | Warning printed; exit 0 | 0 |
| Quest not found (missions listing) | Error to stderr | 1 |

## Out of Scope

- Bulk creation of multiple missions in one command.
- Restoring (undeleting) a soft-deleted mission via the CLI.
