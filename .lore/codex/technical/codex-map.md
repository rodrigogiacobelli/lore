---
id: tech-arch-codex-map
title: "Codex Map — map_documents Internals"
summary: "Technical reference for map_documents, the shared _build_adjacency helper, and the codex_map CLI handler. Covers the two-budget directional BFS, default body short-circuit, the ConflictingDepthFlags exception, and the relationship to chaos_documents."
binds:
  - src/lore/codex.py
  - src/lore/cli.py
  - tests/unit/test_codex_map.py
  - tests/unit/test_codex_build_adjacency.py
  - tests/e2e/test_codex_map.py
related:
  - tech-arch-frontmatter
  - tech-arch-source-layout
  - ref-lore_api-core
  - conceptual-workflows-codex-map
  - ref-lore_cli-commands
  - tech-arch-codex-chaos
  - tech-arch-schemas
  - standards-dry
  - decisions-011-api-parity-with-cli
---
# Codex Map — `map_documents` Internals

**Source module:** `src/lore/codex.py`

This document covers `map_documents`, the shared `_build_adjacency` helper, and
the `codex_map` CLI handler in `cli.py`. It is the sibling document to
`tech-arch-codex-chaos`.

## `map_documents(codex_dir, start_id, *, depth_out=1, depth_in=1, full=False) -> list[dict] | None`

Public function in `codex.py`. Performs a two-budget directional BFS across the
codex graph from `start_id` and returns the neighbour list — never the seed
itself.

### Signature

```python
def map_documents(
    codex_dir: Path,
    start_id: str,
    *,
    depth_out: int = 1,
    depth_in: int = 1,
    full: bool = False,
) -> list[dict] | None:
    ...
```

Keyword-only parameters (note the `*,`) match the style established by
`chaos_documents`. There is no `depth` kwarg — symmetric traversal is expressed
as `depth_out=N, depth_in=N` by callers. The CLI flag `--depth N` is folded into
both kwargs at the handler level.

### Return shape

| Mode | Per-record keys |
|------|-----------------|
| `full=False` (default) | `id`, `group`, `title`, `summary` |
| `full=True` | `id`, `group`, `title`, `summary`, `related`, `body` |

The record list is sorted alphabetically by `id` — BFS visitation order is
discarded. `group` is derived from the document's directory path via
`paths.derive_group(meta["path"], codex_dir)`, identical to `lore codex list`.

| Outcome | Return |
|---------|--------|
| `start_id` not in the codex index | `None` |
| Empty neighbourhood | `[]` |
| `depth_out` or `depth_in` negative | raises `ValueError` |

`None` is reserved for the unknown-seed case — empty neighbourhoods are `[]`.

### Algorithm

1. Validate `depth_out >= 0` and `depth_in >= 0`. Raise `ValueError` if either is
   negative.
2. Load the codex index once via `_scan_codex_robust(codex_dir)`. Build a
   `dict[str, dict]` keyed by `id`.
3. If `start_id` is absent from the index, return `None`.
4. Build directional adjacency via `_build_adjacency(index, docs)` (see below) —
   one pass, two `dict[str, set[str]]` maps for outbound and inbound edges.
5. Initialise the BFS state:
   - `visited: set[str] = {start_id}` — the seed is visited but never emitted.
   - `queue: deque[tuple[str, int, int]] = deque([(start_id, 0, 0)])` — entries
     are `(doc_id, out_used, in_used)`.
   - `result_ids: list[str] = []`.
6. Two-budget BFS. While the queue is non-empty, dequeue `(doc_id, out_used, in_used)`:
   - If `doc_id != start_id`, append it to `result_ids`. The seed is enqueued so
     its neighbours are explored, but it is filtered out of the output.
   - If `out_used < depth_out`, for each neighbour `nb` in `outbound[doc_id]` not
     in `visited`, add `nb` to `visited` and enqueue `(nb, out_used + 1, in_used)`.
   - If `in_used < depth_in`, for each neighbour `nb` in `inbound[doc_id]` not in
     `visited`, add `nb` to `visited` and enqueue `(nb, out_used, in_used + 1)`.
7. Sort `result_ids` alphabetically (FR-3 from the PRD).
8. Build the result list. In `full=False` mode this uses the cached metadata
   records only — `_parse_doc_robust(path, include_body=True)` is **not** called.
   In `full=True` mode each surviving ID is rehydrated with body and `related`.

### Key properties

- **Seed-exclusion** is enforced at append-time by `if doc_id != start_id`.
- **Dedupe-by-ID** is enforced by the `visited` set, checked before enqueueing
  in either direction.
- **Cross-direction visit** — a node reachable via both axes appears exactly
  once. Whichever path enqueues it first wins; subsequent attempts fail the
  `nb not in visited` guard.
- **Asymmetric budgets** — `depth_in=0` makes the inbound expansion a no-op,
  guaranteeing the result contains only outbound-reachable nodes (and vice
  versa).
- **Default body short-circuit** — `full=False` never reads document bodies.
  This closes the previously-deferred N+1 `read_document` perf note for the
  default code path. `--full` retains the per-node parse cost.

### Complexity

| Phase | Complexity |
|-------|------------|
| Index load + adjacency build | O(V + E) |
| Two-budget BFS | O(V + E), bounded by depth budgets |
| Result hydration (`full=True`) | O(R) parses, where R is the result size |
| Total | O(V + E) for `full=False`; O(V + E + R parses) for `full=True` |

V is the number of codex documents; E is the number of declared `related`
edges. Same asymptotic class as `chaos_documents`.

### Determinism

Result order is deterministic for a given codex state: BFS visitation order is
discarded and the final list is alphabetised by ID. The adjacency build itself
visits documents in the order returned by `_scan_codex_robust`, which is
already deterministic.

## `_build_adjacency(index, docs) -> tuple[dict[str, set[str]], dict[str, set[str]]]`

Private helper in `codex.py`. Returns `(outbound, inbound)` adjacency maps over
the codex graph.

```python
def _build_adjacency(
    index: dict[str, dict],
    docs: list[dict],
) -> tuple[dict[str, set[str]], dict[str, set[str]]]:
    outbound = {doc_id: set() for doc_id in index}
    inbound  = {doc_id: set() for doc_id in index}
    for doc in docs:
        neighbours = _read_related(doc["path"], index)
        for n in neighbours:
            outbound[doc["id"]].add(n)
            inbound[n].add(doc["id"])
    return outbound, inbound
```

Properties:

- Initialises both maps with an empty set for every key in `index` so callers
  can index into either map without `KeyError`.
- Calls `_read_related` once per document — the same per-doc edge parser used
  before this refactor. Defensive parsing (drop nulls, drop unknown IDs) is
  unchanged.
- Cost: one pass over `docs`, one frontmatter parse per doc. No body reads.
- Shared with `chaos_documents`, which unions the two maps into a single
  bidirectional adjacency for its random walk. See `tech-arch-codex-chaos`.

## `ConflictingDepthFlags`

Module-level exception in `lore.codex`, subclass of `ValueError`:

```python
class ConflictingDepthFlags(ValueError):
    """Raised when callers combine symmetric `depth` with directional flags."""
```

Raised by the CLI handler (after translating `--depth` into kwargs), not by
`map_documents` directly. The handler also raises `click.UsageError` with the
PRD-pinned message before propagating, so the user-visible failure is a Click
usage error (exit 2). The Python exception exists for parity-conscious Python
callers building their own conflict logic.

## `_read_related(filepath, index) -> list[str]`

Private helper, unchanged by this refactor. Reads the `related` frontmatter
field from a single document via
`frontmatter.parse_frontmatter_doc(filepath, extra_fields=("related",))`,
applies defensive parsing, filters to IDs present in `index`, and returns the
sorted result. Tolerance is intentional — a single bad file never breaks the
adjacency build. Strict enforcement lives in `lore health --scope schemas`.

## `codex_map` CLI handler (in `cli.py`)

Registered as `@codex.command("map")` under the `codex` group.

```
lore codex map <doc_id> [--depth N] [--depth-out N] [--depth-in N] [--full]
```

Flag types:

- `--depth` / `--depth-out` / `--depth-in` — `click.IntRange(min=0)`,
  `default=None` (so absence is distinguishable from explicit `0`).
- `--full` — `is_flag=True`, `default=False`.

Handler responsibilities, in order:

1. **Mutual-exclusion check (before any I/O).** If `--depth` is set together
   with `--depth-in` or `--depth-out`, raise `click.UsageError` with the exact
   PRD-pinned message. In `--json` mode the same message is emitted as
   `{"error": "..."}` to stderr. Exit code 2.
2. **Resolve effective budgets.** Fold the three flags into `eff_out` and
   `eff_in` via the table in `conceptual-workflows-codex-map` § "Resolve
   effective budgets".
3. **Call `map_documents`** with `depth_out=eff_out, depth_in=eff_in, full=full`.
4. **Unknown seed.** If `map_documents` returns `None`, print
   `Document "<doc_id>" not found` (or the JSON envelope equivalent) to stderr
   and exit 1.
5. **Dispatch output by mode.**
   - `full=True`, text mode — for each record emit `=== {id} ===` then `body`.
   - `full=True`, JSON mode — emit `{"documents": [...]}`.
   - `full=False`, JSON mode — emit `{"codex": [{id, group, title, summary}, ...]}`,
     normalising empty-string `group` to `null` via `_group_for_json` (same
     helper `codex_list` uses).
   - `full=False`, text mode — `_format_table(["ID", "GROUP", "TITLE", "SUMMARY"], rows)`,
     the same renderer used by `codex_list`, `knight_list`, `doctrine_list`,
     and `artifact_list`. Empty neighbourhood prints `No related documents.`.

### Output dispatch reuses existing renderers

| Mode | Renderer | Source |
|------|----------|--------|
| Default text | `_format_table` | `cli.py` (shared with `codex_list`) |
| Default JSON | inline dict literal, envelope key `"codex"` | `cli.py` (same shape as `codex_list --json`) |
| `--full` text | inline `=== {id} ===\n{body}` loop | `cli.py` (unchanged) |
| `--full` JSON | inline `{"documents": [...]}` | `cli.py` (unchanged shape, additive keys per entry) |

The default-mode handler MUST NOT compute column widths or padding locally — it
builds the rows list and delegates entirely to `_format_table`.

## Sibling: `chaos_documents`

`chaos_documents` in `codex.py` is the sibling traversal function. After this
refactor it shares the adjacency build with `map_documents`: it calls
`_build_adjacency(index, docs)` and unions the two maps into a single
undirected adjacency for its random walk. Behaviour is unchanged — only the
helper is shared. See `tech-arch-codex-chaos`.
