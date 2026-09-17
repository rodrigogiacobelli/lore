---
id: decisions-038-partition-is-deterministic-modularity-local-moving
title: "ADR-038: The codex index partition is deterministic modularity local-moving, with no graph dependency"
summary: >
  ADR recording that the codex index partition is the local-moving phase of
  Louvain modularity optimisation run to convergence, followed by a
  minimum-size absorption pass at MIN_CLUSTER_SIZE = 3. Determinism needs no
  seed because the sweep order, the candidate scan and the tie-break are all
  derived from the adjacency. No graph library joins pyproject.toml.
binds:
  - src/lore/graph.py
  - tests/unit/test_graph_partition.py
related:
  - tech-arch-graph
  - tech-arch-codex-index
  - decisions-041-render-is-a-cache-invalidated-by-a-stat-fingerprint
  - standards-dry
---

# ADR-038: The codex index partition is deterministic modularity local-moving, with no graph dependency

## Context

The index has to produce the same partition on every machine, with no model and
no seed, over a graph of up to a few thousand documents, in a project whose
declared dependencies are `click`, `pyyaml`, `jsonschema` and `questionary`.

## Decision

The partition is the local-moving phase of Louvain modularity optimisation, run
to convergence over a sweep order of ascending degree then ascending id, with
candidate labels scanned in sorted order and ties broken on the label string,
followed by a minimum-size absorption pass at `MIN_CLUSTER_SIZE = 3`.

All state is integer, so the only floating-point operation is a single division
per candidate and determinism needs no seed. A cluster with no edge leaving it
is kept whatever its size, so an isolated document survives as a cluster of one
rather than disappearing.

The functions live in `lore/graph.py` and take a plain adjacency mapping. No
graph library joins `pyproject.toml`.

## Rationale

- **The same codex must produce the same clusters on every machine.** Anything
  seeded, randomised or ordered by dict insertion breaks the byte-identical
  render the cache depends on.
- **A dependency for one sixty-line function is a bad trade** on a package whose
  four dependencies are all load-bearing. The dependency-free alternative costs
  about sixty lines and one determinism test.
- **Resolution matters more than sophistication here.** An algorithm that
  returns a handful of very large groups is not an index, whatever its
  modularity score.

## Alternatives Considered

| Option | Why rejected |
|--------|-------------|
| **`networkx`** | A dependency for one sixty-line function, on a package whose four dependencies are all load-bearing. |
| **Greedy modularity agglomeration (CNM)** | Measured on the Lore codex it returns a handful of clusters of 13 to 38 members — the resolution limit, which is not an index. |
| **Label propagation** | Cheaper and markedly less stable under a single added document. |
| **Connected components** | The Lore codex is one component with an average degree near 10. |
| **A warm start from the previous render** | Makes the partition a function of history rather than of the codex, and breaks the byte-identical-render property on a second machine. |

## Consequences

**Easier:**
- Two machines with the same codex produce byte-identical renders, so the
  fingerprint cache and the drift digests mean the same thing everywhere.
- The partition is testable without a fixture that pins a random seed.

**Harder:**
- `MIN_CLUSTER_SIZE` is a tuning constant with no principled derivation; moving
  it re-partitions every project's codex and re-keys authored entries.
- A codex whose `related` graph is sparse partitions into groups the absorption
  pass merges by edge count, which is not always the grouping a reader would
  have chosen.

## Constraints Imposed

1. **`partition_graph` is deterministic with no seed parameter.** Any change
   that makes its output depend on dict order, randomness or prior state is a
   defect.
2. **No graph library joins `pyproject.toml`** for this code path.
3. **`partition_graph` and `cluster_hub` take a plain adjacency mapping**
   (`dict[str, set[str]]`, symmetric, no self-loops) and know nothing about
   codex documents.

## Status History

| Date | Status | Note |
|------|--------|------|
| 2026-09-16 | accepted | Recorded with the `lore index` command group, whose partition this is. |
