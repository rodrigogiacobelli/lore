---
id: conceptual-workflows-dependencies
title: Dependency Declaration and Removal
summary: >
  What the system does internally when declaring and removing dependencies between missions, including lore needs / lore unneed and dependency display in lore show.
related: ["conceptual-entities-mission", "conceptual-workflows-show"]
stability: stable
---

# Dependency Declaration and Removal

Dependencies model "mission A cannot start until mission B is closed". `lore needs <from>:<to>` declares the dependency; `lore unneed <from>:<to>` removes it. Both commands accept multiple colon-pair arguments in a single invocation.

## Preconditions

- The Lore project has been initialised.
- Both mission IDs in each pair must match the valid mission ID format.
- The missions must exist and not be soft-deleted.
- The dependency must not create a cycle.

## Steps — Declare (`lore needs <from>:<to> [...]`)

### 1. Parse pair format

Each argument is split on `:`. Exactly one colon must be present and both sides must be non-empty. Invalid pairs produce an error to stderr and the pair is skipped.

### 2. Validate mission IDs

Both `from_id` and `to_id` are validated with `validate_mission_id`. Invalid formats produce an error and the pair is skipped.

### 3. Check for duplicates

`add_dependency` in `lore.db` checks whether the dependency row already exists (non-deleted). If it does, the command reports `Dependency already exists: <from> -> <to>` without treating it as an error (idempotent).

### 4. Cycle detection

Before inserting, `_would_create_cycle` performs a depth-first reachability check in the `dependencies` table. If adding the edge would create a cycle (A→B→...→A), the operation is rejected with an error.

### 5. Insert and auto-block

The dependency row is inserted with `type = 'blocks'` and `deleted_at = NULL`. If `to_id` (the blocking mission) is not yet closed, the `from_id` mission's status is set to `blocked` and its `block_reason` is set to indicate the dependency. If `to_id` is already closed, no blocking occurs and a note is printed.

### 6. Report

On success: `Dependency created: <from> -> <to>`.

In JSON mode:

```json
{
  "created": [{"from": "<id>", "to": "<id>"}],
  "existing": [],
  "errors": []
}
```

## Steps — Remove (`lore unneed <from>:<to> [...]`)

### 1. Parse and validate pairs

Same pair-format and mission-ID validation as `lore needs`. Invalid pairs produce an error; processing continues for remaining pairs.

### 2. Remove the dependency row

`remove_dependency` in `lore.db` soft-deletes the dependency row (sets `deleted_at`). If no matching non-deleted row is found, `removed = False` is returned.

### 3. Auto-unblock

After removing the dependency, the system re-evaluates whether `from_id` still has any open blocking dependencies. If not, `from_id` is transitioned from `blocked` back to `open`.

### 4. Report

Removed: `Dependency removed: <from> -> <to>`. Not found: `Warning: no dependency found: <from> -> <to>` (exit code 0 for not-found; exit code 1 only for format/validation errors).

In JSON mode:

```json
{
  "removed": [{"from": "<id>", "to": "<id>"}],
  "not_found": [],
  "errors": []
}
```

## Dependency Display in `lore show`

### Mission view

`lore show <mission-id>` queries `get_mission_depends_on_details` and `get_mission_blocks_details`. Each dependency is rendered with a status symbol:

- `●` closed
- `◕` in_progress or blocked
- `○` open or unknown

Intra-quest dependencies use the short `m-xxxx` form; cross-quest dependencies use the fully-qualified `q-xxxx/m-xxxx` form.

### Quest view

`lore show <quest-id>` loads all dependency edges for the quest and produces a topologically sorted mission list. Parent missions are shown with a `←` annotation listing their blockers.

## Failure Modes

| Failure point | Behaviour | Exit code |
|---|---|---|
| Invalid pair format | Error to stderr; pair skipped | 1 |
| Invalid mission ID format | Error to stderr; pair skipped | 1 |
| Mission not found | Error to stderr; pair skipped | 1 |
| Cycle detected | Error to stderr; pair skipped | 1 |
| Dependency already exists (needs) | Informational note; not an error | 0 |
| Dependency not found (unneed) | Warning to stderr; not an error | 0 |

## Out of Scope

- Cross-quest dependencies via the CLI — both missions must be reachable by their full IDs, but the system does not restrict cross-quest edges.
- Bulk removal of all dependencies for a mission in one command.
