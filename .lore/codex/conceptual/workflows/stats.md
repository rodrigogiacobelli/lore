---
id: conceptual-workflows-stats
title: Aggregate Statistics — lore stats
summary: >
  What the system does internally when lore stats runs — aggregate counts by status across quests and missions, zero-state output, and JSON envelope.
related: ["tech-cli-commands"]
stability: stable
---

# Aggregate Statistics — `lore stats`

`lore stats` prints a summary of how many quests and missions exist in each status. It is a read-only operation with no side effects.

## Preconditions

- The Lore project has been initialised.

## Steps

### 1. Query aggregate counts

`get_aggregate_stats` in `lore.db` executes two `GROUP BY status` queries:

```sql
SELECT status, COUNT(*) as cnt
FROM quests
WHERE deleted_at IS NULL
GROUP BY status
```

```sql
SELECT status, COUNT(*) as cnt
FROM missions
WHERE deleted_at IS NULL
GROUP BY status
```

Soft-deleted rows (`deleted_at IS NOT NULL`) are excluded from all counts. Statuses with no rows default to `0`.

### 2. Build the result dict

The returned structure is:

```python
{
    "quests":   {"open": N, "in_progress": N, "closed": N},
    "missions": {"open": N, "in_progress": N, "blocked": N, "closed": N}
}
```

### 3. Render

Text output:

```
Quests:
  open: <N>
  in_progress: <N>
  closed: <N>

Missions:
  open: <N>
  in_progress: <N>
  blocked: <N>
  closed: <N>
```

All four mission statuses and all three quest statuses are always printed, even when their count is `0`.

### 4. JSON mode

The dict returned by `get_aggregate_stats` is emitted directly:

```json
{
  "quests":   {"open": 0, "in_progress": 0, "closed": 0},
  "missions": {"open": 0, "in_progress": 0, "blocked": 0, "closed": 0}
}
```

## Failure Modes

| Failure point | Behaviour | Exit code |
|---|---|---|
| Project not initialised | Error to stderr | 1 |

## Out of Scope

- Per-quest breakdown — use `lore show <quest-id>` for a single quest.
- Historical trend data — stats reflect the current database state only.
