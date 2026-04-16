---
id: conceptual-workflows-codex-map
title: lore codex map Behaviour
summary: What the system does internally when lore codex map <id> --depth <n> runs
  — BFS traversal of the related frontmatter field, deduplication via visited set,
  and JSON output.
related:
- conceptual-workflows-codex
- tech-arch-codex-map
- tech-arch-frontmatter
- tech-cli-commands
- codex
---
# `lore codex map` Behaviour

`lore codex map <id> --depth <n>` performs a breadth-first search across the codex
document graph, starting from a root document and following `related` frontmatter links
up to the requested depth. It returns every discovered document exactly once, in BFS
traversal order, in the same format as `lore codex show`.

## Preconditions

- The Lore project has been initialised.
- The root document ID supplied as the `<id>` argument must exist in the codex.

## Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `<id>` | positional argument | required | The root document ID to start BFS from. |
| `--depth` | integer (min 0) | `1` | Maximum number of `related` hops to traverse. |

## Steps

### 1. Validate root document

`map_documents` in `lore.codex` loads the full codex index once via `scan_codex`.
If the supplied `start_id` is not present in the index, the function returns `None`
and the CLI handler prints `Document "<id>" not found` to stderr and exits with
code 1.

### 2. BFS traversal

The algorithm uses a `collections.deque` of `(doc_id, current_depth)` tuples and
a `visited: set[str]` to prevent duplicate processing.

- **Depth 0:** Only the root document is included. No `related` links are followed.
- **Depth N:** All documents reachable within N hops from the root (inclusive of root).

At each node:
1. Mark the current document ID as visited.
2. Fetch the full document body via `read_document`.
3. If `current_depth < depth`, call `_read_related` to get the sorted, validated
   list of neighbour IDs, and enqueue any not yet visited at `current_depth + 1`.

`related` links are treated as **directed**: A declaring B in its `related` field
does not cause B's `related` list to be traversed back toward A unless B also
declares A.

### 3. Neighbour resolution via `_read_related`

`_read_related(filepath, index)` reads the `related` field from a document's
frontmatter using `parse_frontmatter_doc` with `extra_fields=("related",)`. It:
- Applies defensive parsing: nulls, non-strings, and whitespace-only entries are
  dropped.
- Filters to IDs present in the codex index (dead links are silently skipped).
- Sorts the result alphabetically to ensure deterministic BFS output.

### 4. Render

Documents are output in BFS traversal order — root first, then depth-1 neighbours
in sorted `related`-list order, then depth-2, etc.

**Text mode:**
```
=== <id> ===
<document body>

=== <next-id> ===
<document body>
```

Format matches `lore codex show` exactly — `=== <id> ===` separator followed by
the body, one block per document.

**JSON mode** (global `--json` flag via `ctx.obj`):
```json
{
  "documents": [
    {"id": "...", "title": "...", "summary": "...", "body": "..."},
    ...
  ]
}
```

Array preserves BFS traversal order.

## Failure Modes

| Failure point | Behaviour | Exit code |
|---|---|---|
| Root document not found | `Document "<id>" not found` to stderr | 1 |
| Root not found, JSON mode | `{"error": "Document \"<id>\" not found"}` to stderr | 1 |
| Broken `related` link (ID not in codex) | Silently skipped; traversal continues | 0 |
| `related` field absent, null, or empty | Document treated as leaf node; no error | 0 |
| `related` field contains nulls or non-strings | Defensive parsing drops them; no error | 0 |

## Out of Scope

- Writing or modifying any codex document — `lore codex map` is read-only.
- Traversal of Artifact IDs — `related` values are codex IDs only.
- Multi-root BFS (multiple seed IDs in one invocation).
- Reverse traversal (who references a given ID) — Post-MVP `--reverse` flag.
- Output of graph structure (which document linked to which) — output is a flat
  document list in BFS order.
