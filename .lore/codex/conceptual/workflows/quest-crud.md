---
id: conceptual-workflows-quest-crud
title: Quest CRUD Operations
summary: >
  What the system does internally when creating, listing, editing, and deleting quests via the CLI.
related: ["conceptual-entities-quest", "conceptual-workflows-mission-crud"]
stability: stable
---

# Quest CRUD Operations

This document covers the four lifecycle operations on quests: `lore new quest`, `lore list`, `lore edit <quest-id>`, and `lore delete <quest-id>`.

## Preconditions

- The Lore project has been initialised (`lore init`).
- For edit and delete: the quest ID must match the pattern `q-<4-6 hex>`.
- For delete with `--cascade`: all child missions and their dependencies are also removed.

## Steps — Create (`lore new quest <title>`)

### 1. Validate priority

The `--priority` option (default `2`) is validated against the range `[0, 4]`. Out-of-range values raise a `ClickException` before any database access.

### 2. Generate a quest ID

`create_quest` in `lore.db` opens a `BEGIN IMMEDIATE` transaction, reads all existing quest IDs, and calls `generate_id("q", existing_ids)` to produce a unique `q-<4-6 hex>` ID. A `RuntimeError` is raised (and surfaced as an error message) on extremely unlikely ID collision.

### 3. Insert the quest row

The quest is inserted with status `open`, the supplied title, description (default `""`), priority, `auto_close` flag (default `0`), and UTC `created_at` / `updated_at` timestamps.

### 4. Commit and report

The transaction is committed. Output is:

```
Created quest q-xxxx
```

In JSON mode: `{"id": "q-xxxx"}`.

## Steps — List (`lore list`)

### 1. Fetch quests

`list_quests` queries all quests where `deleted_at IS NULL`. Without `--all`, closed quests are excluded (`status != 'closed'`). Results are ordered by `priority ASC, created_at ASC`.

### 2. Render

Each quest is displayed as one line:

```
  q-xxxx  P<priority>  [<status>]  <title>
```

In JSON mode: `{"quests": [{id, title, status, priority, created_at}, ...]}`.

"No quests found." is printed if the result is empty.

## Steps — Edit (`lore edit <quest-id>`)

### 1. Validate ID format

The entity ID is validated with `validate_entity_id`. If the ID starts with `q-` and has no `/`, it is routed to `_edit_quest`.

### 2. Require at least one field

If none of `--title`, `--description`, `--priority`, `--auto-close`, or `--no-auto-close` are provided, a `UsageError` is raised.

### 3. Mutual exclusion check

`--auto-close` and `--no-auto-close` cannot be supplied together.

### 4. Apply the edit

`edit_quest` in `lore.db` updates only the supplied fields, sets `updated_at` to the current UTC timestamp, and returns `{"ok": True}` on success or `{"ok": False, "error": ...}` on failure (quest not found or soft-deleted).

### 5. Report

Text mode: `Updated quest q-xxxx`. JSON mode: the full updated quest object including its missions list.

## Steps — Delete (`lore delete <quest-id>`)

Deletion is a **soft-delete**: the quest's `deleted_at` field is set rather than the row being removed.

### 1. Validate ID format

Loose validation (`validate_quest_id_loose`) is applied for delete, which accepts non-strict hex in test environments.

### 2. Check if already deleted

If `deleted_at` is already set, the command reports the existing timestamp and exits with code 0 (idempotent warning).

### 3. Soft-delete the quest

Within a `BEGIN IMMEDIATE` transaction, `deleted_at` and `updated_at` are set to the current UTC timestamp.

### 4. Cascade (optional)

With `--cascade`, all non-deleted missions belonging to the quest are also soft-deleted, and their dependency edges are soft-deleted. The list of cascaded mission IDs is returned.

### 5. Report

Text mode: `Deleted quest q-xxxx` (plus cascade list if applicable). JSON mode: `{"id": "q-xxxx", "deleted_at": "...", "cascade": [...]}`.

## Failure Modes

| Failure point | Behaviour | Exit code |
|---|---|---|
| Priority out of range [0,4] | `ClickException` — message to stderr | 1 |
| ID collision on create | Error message to stderr | 1 |
| Invalid quest ID format | Error message to stderr | 1 |
| Quest not found on edit | `{"ok": False, "error": ...}` → error to stderr | 1 |
| Quest already deleted on edit | Error with `deleted_at` annotation to stderr | 1 |
| Quest not found on delete | Error to stderr | 1 |
| Quest already deleted on delete | Warning with existing timestamp; exit 0 | 0 |

## Out of Scope

- Re-opening a closed quest directly — use `lore new mission -q <quest-id>` (adding a mission to a closed quest automatically reopens it).
- Permanently removing a quest from the database.
