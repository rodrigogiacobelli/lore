---
id: conceptual-workflows-ready
title: Ready Queue — lore ready
summary: >
  What the system does internally when lore ready runs — priority ordering, exclusion of blocked and closed missions, dependency-gating, and multi-result output.
related: ["conceptual-entities-mission", "conceptual-workflows-claim"]
stability: stable
---

# Ready Queue — `lore ready`

`lore ready [<count>]` returns the highest-priority unblocked open mission(s). It is the primary dispatch mechanism for the orchestrator when selecting what to work on next.

## Preconditions

- The Lore project has been initialised.
- At least one mission in `open` status must exist with no unresolved blocking dependencies for output to be non-empty.

## Steps

### 1. Query the ready queue

`get_ready_missions` in `lore.priority` executes a single SQL query:

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
      AND dep.deleted_at IS NULL
  )
ORDER BY m.priority ASC, m.created_at ASC
LIMIT ?
```

This means:
- Only `open` (not `in_progress`, `blocked`, or `closed`) missions are candidates.
- Soft-deleted missions are excluded.
- A mission is excluded if it has any non-deleted `blocks` dependency whose blocking mission is not yet `closed`.
- Results are sorted by `priority ASC` (lower number = higher priority) then `created_at ASC` (oldest first as a tiebreaker).
- The optional `count` argument controls the `LIMIT` (default `1`).

### 2. Render results

For each mission in the result set:

```
  <id>  P<priority>  [<status>]  [<mission_type>]  <title>  [<knight>]
```

`mission_type` and `knight` brackets are omitted when null.

If the result set is empty, the output is `No missions are ready.`

### 3. JSON mode

```json
{
  "missions": [
    {
      "id": "q-xxxx/m-yyyy",
      "quest_id": "q-xxxx",
      "title": "...",
      "status": "open",
      "priority": 1,
      "mission_type": "coding",
      "knight": "dev.md",
      "created_at": "2026-03-24T12:00:00Z"
    }
  ]
}
```

An empty `missions` array is returned when nothing is ready.

## Priority Ordering

Priority values run `0` (highest) to `4` (lowest). The default priority is `2`. Lower numeric value means the mission surfaces earlier. Within the same priority, older missions are returned first (by `created_at`).

## Dependency Gating

A mission is dependency-gated (absent from the ready queue) when it has a `blocks`-type dependency row pointing to another mission that is still `open`, `in_progress`, or `blocked`. Once all blocking missions reach `closed` status, the dependency constraint is satisfied and the mission re-enters the ready queue.

## Failure Modes

| Failure point | Behaviour | Exit code |
|---|---|---|
| No ready missions | `No missions are ready.` printed | 0 |
| Project not initialised | Error to stderr | 1 |

## Out of Scope

- Filtering by quest — `lore ready` scans all quests.
- Reserving or claiming a mission as part of the `ready` call — the orchestrator must follow up with `lore claim`.
