---
id: conceptual-workflows-show
title: Show Command — lore show
summary: >
  What the system does internally when lore show <id> runs — quest inline mission list (topological sort), mission detail view, ID routing, quest inference for mission IDs, and not-found error paths.
related: ["tech-arch-graph", "conceptual-workflows-board"]
stability: stable
---

# Show Command — `lore show`

`lore show <entity-id>` displays the full detail view of a quest or mission. The command routes by ID shape: `q-<hex>` (no `/`) is treated as a quest; any ID containing `m-` is treated as a mission.

## Preconditions

- The Lore project has been initialised.
- The entity ID must pass format validation.

## ID Routing

1. If the ID starts with `q-` and contains no `/`: attempt quest display.
2. If the ID contains `m-`: attempt mission display.
3. Anything else: `Invalid ID format: "<id>"` to stderr; exit code 1.

**Loose validation for quests:** the show command uses `validate_quest_id_loose` (accepting non-strict hex characters used by test fixtures) rather than the strict validator. If even the loose pattern fails, the command rejects the ID immediately. If loose passes but strict fails, the system proceeds to a DB lookup; a missing record produces a format error rather than a not-found error.

## Steps — Quest Display (`lore show <quest-id>`)

### 1. Fetch quest

`get_quest` is called. If `None` is returned, `_emit_not_found` is called.

### 2. Fetch missions and dependencies

`get_missions_for_quest` returns all missions for the quest (including soft-deleted ones are excluded by the query — only `deleted_at IS NULL` rows). `get_all_dependencies_for_quest` returns all dependency edges. `get_board_messages` returns board messages for the quest.

### 3. Topological sort

The inline mission list is sorted topologically using `graph.topological_sort_missions`. Only intra-quest edges (both `from_id` and `to_id` belong to this quest's mission set) are passed to the sort. Cross-quest edges are excluded from the sort but still rendered in individual mission views.

### 4. Render

Text output shows quest metadata, then a `Missions:` section with one line per mission:

```
● m-yyyy  Mission Title [coding]  ← m-zzzz
```

- Status symbol: `●` closed, `◕` in_progress/blocked, `○` open.
- Short `m-xxxx` form is used for intra-quest IDs; fully-qualified for cross-quest.
- The `← <parent-id>` column is right-aligned when any mission has parents.
- Board messages appear below missions if any exist.

### 5. JSON mode

The full quest object is emitted including `missions` array (each with nested `dependencies.needs` and `dependencies.blocks`), `board` array, and all scalar fields.

## Steps — Mission Display (`lore show <mission-id>`)

### 1. Fetch mission

`get_mission` is called. If `None`, `_emit_not_found` is called. `_emit_not_found` checks `get_deleted_at`; if the entity was soft-deleted, the error message includes the deletion timestamp.

### 2. Check quest soft-deletion

If the mission belongs to a quest, that quest's `deleted_at` is checked. A `(quest deleted)` annotation is added to the mission header when the parent quest has been soft-deleted.

### 3. Fetch dependencies and board messages

`get_mission_depends_on_details` and `get_mission_blocks_details` return rich dependency objects (including `deleted_at` and `status`). `get_board_messages` returns board messages.

### 4. Render

Text output:

```
Mission: q-xxxx/m-yyyy
Title: My Task
Status: open
Priority: 2
Type: coding
Description: ...
Knight: dev.md
Block Reason: ...  (only when blocked)
Created: ...
Updated: ...
Closed: ...  (only when closed)

Dependencies:
  Needs:
    ○ m-zzzz  Prerequisite Task
  Blocks:
    ○ m-aaaa  Downstream Task

Board:
  [2026-03-24T12:00:00Z] (m-prev) Handoff note

--- Knight Contents ---
<full knight markdown>
```

`Type`, `Description`, `Knight`, `Block Reason`, `Closed`, `Dependencies`, `Board`, and knight contents sections are omitted when empty/null.

### 5. JSON mode

Full mission object including `knight_contents` (raw markdown string or null), `dependencies.needs`, `dependencies.blocks`, and `board` array.

## Not-Found Error Paths

When an entity is not found, `_emit_not_found` checks whether it was soft-deleted:

- Soft-deleted: `<Label> "<id>" not found (deleted on <timestamp>)`
- Never existed: `<Label> "<id>" not found`

In JSON mode: `{"error": "...", "deleted_at": "..."}` or `{"error": "..."}` to stderr.

## Failure Modes

| Failure point | Behaviour | Exit code |
|---|---|---|
| Invalid ID format | Error to stderr | 1 |
| Quest not found (not deleted) | `Quest "<id>" not found` to stderr | 1 |
| Quest soft-deleted | Error with `deleted_at` annotation | 1 |
| Mission not found (not deleted) | `Mission "<id>" not found` to stderr | 1 |
| Mission soft-deleted | Error with `deleted_at` annotation | 1 |

## Out of Scope

- Showing a mission without its knight contents by default — use `--no-knight` to suppress.
- Paginated output for quests with many missions.
