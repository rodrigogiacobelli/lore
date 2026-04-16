---
id: tech-arch-codex-map
title: "Codex Map — map_documents and _read_related Internals"
summary: "Technical reference for the map_documents and _read_related functions added to src/lore/codex.py for the lore codex map command. Covers BFS algorithm, extra_fields usage, defensive related-field parsing, and the codex_map CLI handler."
related:
  - tech-arch-frontmatter
  - tech-arch-source-layout
  - tech-api-surface
  - conceptual-workflows-codex-map
  - tech-cli-commands
  - tech-arch-codex-chaos
  - tech-arch-schemas
---
# Codex Map — `map_documents` and `_read_related` Internals

**Source module:** `src/lore/codex.py`

This document covers the two new functions added to `codex.py` for the
`lore codex map` command and the `codex_map` CLI handler added to `cli.py`.

## `map_documents(codex_dir: Path, start_id: str, depth: int) -> list[dict] | None`

Public function in `codex.py`. Returns `None` if `start_id` is not found in the
codex (signals missing root to the CLI handler). Returns a `list[dict]` on success.
Each dict has keys `id`, `title`, `summary`, `body` — the same contract as
`read_document`.

### Algorithm

1. Load the full codex index once via `scan_codex(codex_dir)`. Build a
   `dict[str, dict]` keyed by `id` for O(1) lookup of document paths during BFS.
2. Validate `start_id` — if not in the index, return `None`.
3. Initialise BFS:
   - `visited: set[str]` — prevents revisiting; implicitly handles cyclic graphs.
   - `queue: collections.deque[tuple[str, int]]` — `(doc_id, current_depth)` pairs.
   - Seed queue with `(start_id, 0)`.
4. While queue is non-empty:
   a. Dequeue `(current_id, current_depth)`.
   b. Skip if `current_id` already in `visited`.
   c. Add `current_id` to `visited`.
   d. Call `read_document(codex_dir, current_id)`. If `None` (parse failure),
      skip without adding to result.
   e. Append the full document dict to `result`.
   f. If `current_depth < depth`, call `_read_related(filepath, index)` and enqueue
      all unvisited neighbours at `current_depth + 1`.
5. Return `result`.

### Complexity

O(V + E) where V is the number of distinct visited documents and E is the number
of `related` links traversed. The codex index is built once in O(N) where N is
the total number of codex documents.

### Determinism

BFS output order is deterministic for the same codex state on any filesystem because
`_read_related` sorts neighbour IDs alphabetically before returning them.

### Performance Note

`read_document` calls `scan_codex` internally on each invocation. For MVP codex
sizes (tens to low hundreds of documents) this satisfies the 2-second NFR.
Refactoring `read_document` to accept a pre-built path index is deferred Post-MVP.

## `_read_related(filepath: Path, index: dict[str, dict]) -> list[str]`

Private helper in `codex.py`.

1. Calls `frontmatter.parse_frontmatter_doc(filepath, extra_fields=("related",))`.
   The `extra_fields` extension to `parse_frontmatter_doc` passes through additional
   YAML fields in the returned dict — see `tech-arch-frontmatter`.
2. Extracts `doc.get("related")`. If `None` or the parse returns `None`, returns `[]`.
3. Applies defensive parsing:
   `[str(x).strip() for x in (raw or []) if x is not None and str(x).strip()]`
   Note: `_read_related` is intentionally permissive (it tolerates mapping-shaped or mixed `related` values at traversal time so a single bad file never breaks the map). The authoritative enforcement point is `lore health --scope schemas`, which rejects any `related` that is not a YAML array of non-empty strings against `lore://schemas/codex-frontmatter`. Health fails loud, map degrades gracefully — by design.
4. Filters: returns only IDs present as keys in `index`.
5. Sorts the result alphabetically.
6. Returns `list[str]`.

The `index` parameter is passed in (not rebuilt per call) so filter lookups are O(1)
without additional filesystem access.

## `codex_map` CLI handler (in `cli.py`)

Registered as `@codex.command("map")` under the `codex` group.

```
lore codex map <doc_id> [--depth <n>]
```

- `doc_id` — positional argument (the root document ID).
- `--depth` — `click.IntRange(min=0)`, default `1`, `show_default=True`.
- Uses `ctx.obj["project_root"]` and `ctx.obj.get("json", False)` — same pattern
  as `codex_show`. No local `--json` flag.

**Error handling (missing root):**
- Text mode: `click.echo(f'Document "{doc_id}" not found', err=True)` then
  `ctx.exit(1); return`.
- JSON mode: `click.echo(json.dumps({"error": f'Document "{doc_id}" not found'}),
  err=True)` then `ctx.exit(1); return`.

## `extra_fields` Extension to `frontmatter.py`

`_read_related` relies on the `extra_fields` parameter added to
`parse_frontmatter_doc` and `parse_frontmatter_doc_full`. See `tech-arch-frontmatter`
for the full parameter specification. In brief:

- `extra_fields=()` is the default; all existing callers are unaffected.
- When `extra_fields=("related",)` is passed, the returned dict includes a `related`
  key with the raw YAML value (a Python `list[str]` or `None`).
- Fields listed in `extra_fields` that are absent in the frontmatter are omitted
  from the returned dict — callers must use `.get()`.

## Sibling: `chaos_documents`

`chaos_documents` in `codex.py` is the sibling traversal function introduced by the
Chaos Search feature. It reuses `_read_related` during its bidirectional adjacency
pre-pass and shares the same index-building pattern, but replaces deterministic BFS
with a bidirectional-adjacency random walk. See `tech-arch-codex-chaos`
(`lore codex show tech-arch-codex-chaos`) for its internals.
