---
id: tech-arch-graph
title: Graph Module Internals
summary: 'Technical reference for src/lore/graph.py — graph algorithms over mission
  dependency sets and adjacency mappings. Documents topological_sort_missions (Kahn''s
  algorithm, used by _show_quest to sort missions in dependency order for display)
  and the codex-index pair partition_graph / cluster_hub (deterministic Louvain
  local-moving with a minimum-size absorption pass at MIN_CLUSTER_SIZE = 3).

  '
binds:
- src/lore/graph.py
- tests/unit/test_graph.py
- tests/unit/test_graph_partition.py
related:
- tech-arch-source-layout
- tech-arch-codex-index
- conceptual-workflows-show
- conceptual-workflows-index
- decisions-038-partition-is-deterministic-modularity-local-moving
- standards-single-responsibility
---

# Graph Module Internals

**Source module:** `src/lore/graph.py`

This module holds graph algorithms over mission dependency sets and adjacency
mappings. The two shapes are separate: `topological_sort_missions` takes mission
dicts and edge dicts, while `partition_graph` and `cluster_hub` take a plain
adjacency mapping. Neither knows what its nodes mean.

The module exists so that no CLI handler carries an algorithm. A handler's job
is to format and display output; a non-trivial graph algorithm is a second
responsibility and belongs here, where it is isolated and testable
(`standards-single-responsibility`).

Everything in the module is internal. No name reaches `lore.api.__all__`.

## Mission dependency sets

### `topological_sort_missions(missions, edges) -> list[dict]`

Sorts a list of mission dicts into topological order based on a set of
dependency edges.

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
dependencies appear before it in the list. Original order is preserved as a
tiebreaker for missions at the same topological level (same in-degree after BFS
processing).

#### Caller responsibility

The caller — `_show_quest` in `cli.py` — must filter edges to **intra-quest
pairs** before passing them to this function:

- Include only edges where both `from_id` and `to_id` belong to the same quest.
- Exclude cross-quest dependency edges.

`topological_sort_missions` does not filter edges itself. Passing cross-quest
edges includes missions from other quests in the sort ordering, which produces
incorrect display output.

#### Algorithm

Kahn's topological sort:

1. Build an in-degree map: count how many incoming edges each mission has.
2. Initialise a queue with all missions whose in-degree is zero (no
   dependencies).
3. Process the queue BFS-style:
   - Pop a mission from the queue and add it to the result list.
   - For each outgoing edge from this mission, decrement the in-degree of the
     target.
   - If the target's in-degree reaches zero, add it to the queue.
4. Continue until the queue is empty.

Original input order is the tiebreaker within the same BFS level.

#### Cycle-safety fallback

If the sort completes and not all input missions have been visited — which
indicates a cycle in the edge set — the unvisited missions are appended to the
result list in their original input order. The function raises no exception on
cycles.

The fallback keeps the display complete even if dependency data is inconsistent.
Lore's database layer prevents cycles from being created (`ref-lore_db-core`),
so this is a defensive measure rather than an expected path.

## Adjacency mappings

Both functions below take `adjacency: dict[str, set[str]]`, which must be
symmetric — `b in adjacency[a]` iff `a in adjacency[b]` — and in which a node
never neighbours itself. `index.py` is the caller; the mapping it passes is the
undirected codex `related` graph (`tech-arch-codex-index`).

### `partition_graph(adjacency, *, min_size=MIN_CLUSTER_SIZE) -> list[list[str]]`

Partitions an undirected graph into clusters, deterministically. Returns one
sorted list of node ids per cluster, the outer list sorted by descending size
then by ascending first member. Every key of `adjacency` appears in exactly one
cluster.

**The algorithm** is the local-moving phase of Louvain modularity optimisation,
run to convergence, followed by a minimum-size absorption pass
(`decisions-038-partition-is-deterministic-modularity-local-moving`):

1. **Sweep order** — ascending degree, then ascending id. A total order derived
   from the adjacency alone, so it does not depend on dict order.
2. **Local moving** — sweep that fixed order, lifting each node out of its
   community and moving it to the neighbouring community with the greatest
   modularity gain, until a whole sweep moves nothing. Candidate labels are
   scanned in sorted order; a tie resolves to the lexicographically smaller
   label. `_MAX_SWEEPS` caps the loop at 100, which makes the function total on
   a pathological graph; convergence is reached in single digits on every graph
   measured.
3. **Minimum-size absorption** — repeatedly take the smallest cluster below
   `min_size` (ties by its lowest member id) and merge it into the cluster it
   shares the most edges with (ties by that cluster's lowest member id). A
   cluster with no edge leaving it is skipped and kept, so an isolated node
   survives as a cluster of one rather than disappearing.

**Determinism needs no seed.** Every value the gain is computed from is an
integer, so the only floating-point operation is a single division per
candidate, and `_GAIN_EPSILON` (`1e-12`) decides what counts as a tie.

A graph with no edges returns one cluster per node.

**Module constants:** `MIN_CLUSTER_SIZE = 3` is public on the module and is the
default `min_size`. `_MAX_SWEEPS` and `_GAIN_EPSILON` are private.

### `cluster_hub(members, adjacency) -> str`

The member most linked to the rest of its own cluster, ties by ascending id.

Neighbours outside `members` do not count: the hub is the member the cluster
itself is organised around, which is what makes it a stable key for an authored
index entry as membership shifts. An empty `members` raises `ValueError`.

## Why not `priority.py`

`priority.py`'s purpose is the ready-queue SQL query — finding the
highest-priority unblocked missions. Graph algorithms are a separate concern.
Placing either family there would violate `standards-single-responsibility`.
