---
id: tech-arch-graph
title: Graph Module Internals
summary: >
  Technical reference for src/lore/graph.py. Documents topological_sort_missions —
  the Kahn's algorithm implementation used by _show_quest to sort missions in
  dependency order for display.
related: ["tech-arch-source-layout", "conceptual-workflows-show"]
stability: stable
---

# Graph Module Internals

**Source module:** `src/lore/graph.py`

This module provides graph algorithms on mission dependency sets. It ships as part
of the ADR-012 refactor (REFACTOR-10), extracting the topological sort implementation
from `_show_quest` in `cli.py` into a standalone, testable module.

## Purpose

Before this module existed, the topological sort algorithm was embedded directly in
`_show_quest` in `cli.py`. Inline algorithm implementations in a CLI handler violate
the Single Responsibility principle (ADR-012): the handler's job is to format and
display output, not to implement graph algorithms. REFACTOR-10 separates these concerns.

The algorithm is also non-trivial (Kahn's topological sort with a cycle-safety
fallback), making it a strong candidate for isolated testing and documentation.

## Public Interface

### `topological_sort_missions(missions, edges) -> list[dict]`

Sorts a list of mission dicts into topological order based on a set of dependency edges.

**Signature:**

```python
def topological_sort_missions(
    missions: list[dict],  # each dict must have an "id" key
    edges: list[dict],     # each dict must have "from_id" and "to_id" keys
) -> list[dict]:
```

**Inputs:**

- `missions` — list of mission dicts, each with at minimum an `"id"` key.
- `edges` — list of dependency edge dicts, each with `"from_id"` (the dependent
  mission) and `"to_id"` (the dependency being waited on) keys.

**Output:** The same mission dicts as the input, reordered so that a mission's
dependencies appear before it in the list. Original order is preserved as a tiebreaker
for missions at the same topological level (same in-degree after BFS processing).

## Caller Responsibility

The caller (currently `_show_quest` in `cli.py`) must filter edges to **intra-quest
pairs** before passing them to this function. Specifically:

- Include only edges where both `from_id` and `to_id` belong to the same quest.
- Exclude cross-quest dependency edges.

`topological_sort_missions` does not filter edges itself. Passing cross-quest edges
will include missions from other quests in the sort ordering, which produces incorrect
display output.

## Algorithm

Kahn's topological sort:

1. Build an in-degree map: count how many incoming edges each mission has.
2. Initialise a queue with all missions whose in-degree is zero (no dependencies).
3. Process the queue BFS-style:
   - Pop a mission from the queue and add it to the result list.
   - For each outgoing edge from this mission, decrement the in-degree of the target.
   - If the target's in-degree reaches zero, add it to the queue.
4. Continue until the queue is empty.

Original input order is preserved as the tiebreaker within the same BFS level: missions
with the same in-degree are processed in their original list order.

## Cycle-Safety Fallback

If the sort completes and not all input missions have been visited — which indicates a
cycle in the edge set — the unvisited missions are appended to the result list in their
original input order. The function does not raise an exception on cycles.

This fallback ensures the display is always complete even if dependency data is somehow
inconsistent (e.g., circular dependencies that passed cycle-detection at write time).
Lore's database layer prevents cycles from being created (see tech-db-schema,
lore codex show tech-db-schema), so this fallback is a defensive measure, not expected
behaviour.

## Why Not `priority.py`

`priority.py`'s purpose is the ready-queue SQL query — finding the highest-priority
unblocked missions. Graph algorithms are a separate concern and do not belong there.
Placing topological sort in `priority.py` would violate the Single Responsibility
principle.
