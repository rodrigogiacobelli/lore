---
id: conceptual-workflows-codex-chaos
title: "`lore codex chaos` Behaviour"
summary: >
  Random-walk traversal of the codex graph starting from a seed document.
  Follows randomly sampled neighbours via the related frontmatter field and
  terminates when the ratio of discovered documents to the reachable subgraph
  exceeds --threshold / 100, or when no unvisited reachable neighbours remain.
  Output format is identical to lore codex map (ID, TITLE, SUMMARY table).
stability: stable
related:
  - conceptual-workflows-codex
  - conceptual-workflows-codex-map
  - conceptual-workflows-json-output
  - conceptual-workflows-error-handling
  - tech-cli-commands
  - tech-api-surface
  - tech-arch-codex-chaos
---

# `lore codex chaos` Behaviour

`lore codex chaos <id> --threshold <int>` performs a probabilistic random-walk
traversal of the codex document graph, starting from a seed document and following
randomly sampled neighbours via the `related` frontmatter field. The walk terminates
when the ratio of discovered documents to the total reachable subgraph exceeds
`--threshold / 100`, or when no unvisited reachable neighbours remain. Output format
is identical to `lore codex map`: a table with columns ID, TITLE, SUMMARY.

## Preconditions

- The Lore project has been initialised.
- The seed document ID supplied as the `<id>` argument must exist in the codex.

## Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `<id>` | positional argument | required | The seed document ID to start the walk from. |
| `--threshold` | integer, 30–100 inclusive | required | Walk terminates when `(discovered - 1) / (reachable - 1) >= threshold / 100` (seed excluded from numerator). Values below 30 or above 100 are rejected. |
| `--json` | flag | off | Output wrapped in `{"documents": [...]}` envelope. Placed at end per project convention. |

## Steps

### 1. Validate seed document

`chaos_documents` in `lore.codex` loads the full codex index once via `scan_codex`.
If the supplied `start_id` is absent from the index, the function returns `None` and
the CLI handler writes `Document "<id>" not found` to stderr and exits with code 1.

### 2. Build bidirectional adjacency map

A pre-pass over the full codex index reads every document's `related` field via
`_read_related` and registers each declared link in both directions. Consequence:
if document A declares B in its `related` field, then B is a neighbour of A and A
is also a neighbour of B for chaos traversal purposes.

This bidirectional treatment is chaos-only. `map_documents` (used by `lore codex map`)
treats `related` links as directed and is unchanged by this feature.

### 3. Compute reachable subgraph

A BFS from `start_id` over the bidirectional adjacency map produces
`reachable: set[str]` — all document IDs reachable from the seed (including the seed
itself). This set is the denominator for threshold evaluation.

If only the seed document is reachable (no connected neighbours), the seed is returned
immediately and the command exits 0.

### 4. Random walk

Starting at `start_id`, at each step the walk picks one unvisited reachable neighbour
at random. The walk stops when either condition is met:

- `(len(visited) - 1) / (len(reachable) - 1) >= threshold / 100` — the fraction of
  the reachable subgraph discovered (excluding the seed from both numerator and
  denominator) has reached or exceeded the threshold.
- No unvisited reachable neighbours remain.

The seed document is always the first entry in the result. Visited documents are
collected in traversal order.

### 5. Render

**Text mode:** a table with columns ID, TITLE, SUMMARY — identical column layout
to `lore codex list` and `lore codex search`. No `=== <id> ===` body separators.
Seed document is always the first row. Output order is non-deterministic.

**JSON mode** (global `--json` flag via `ctx.obj`):

```json
{
  "documents": [
    {"id": "...", "title": "...", "summary": "..."},
    ...
  ]
}
```

Note: chaos output does not include a `body` field. The JSON envelope matches the
`lore codex list` shape, not the `lore codex show` / `lore codex map` shape.

## Non-Determinism

Output order and subset are explicitly non-deterministic across invocations.
Consumers must not rely on order or on a specific subset being returned. Two runs
with the same seed document on the same graph will generally return different subsets.

The only guarantee is that the seed document is always the first entry in the result.

## Failure Modes

| Failure point | Behaviour | Exit code |
|---|---|---|
| Seed document not found | `Document "<id>" not found` to stderr | 1 |
| Seed not found, JSON mode | `{"error": "Document \"<id>\" not found"}` to stderr | 1 |
| `--threshold` below 30 or above 100 | `--threshold must be between 30 and 100` to stderr | 1 |
| `related` field absent, null, or empty | Seed treated as leaf; only seed returned | 0 |
| Broken `related` link (ID not in codex) | Silently skipped; traversal continues | 0 |

## Out of Scope

- Modifying `lore codex map` behaviour — the map command is unchanged by this feature.
- Persisting walk results to disk or database.
- Multi-root walks — exactly one seed document per invocation.
- Graph visualisation.
- `--seed` flag for reproducible RNG (post-MVP).
- Functional equivalence guarantee between `--threshold 100` and `lore codex map` at
  exhaustive depth — the two commands use different traversal strategies and will
  generally not return identical results even at full coverage.
