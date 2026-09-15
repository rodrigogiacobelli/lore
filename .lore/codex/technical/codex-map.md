---
id: tech-arch-codex-map
title: Codex Map — map_documents Internals
summary: Technical reference for map_documents, the shared _build_adjacency helper,
  and the codex_map CLI handler. Covers the two-budget directional BFS, default body
  short-circuit, the ConflictingDepthFlags exception, scope-resolution before the
  walk, and the relationship to chaos_documents.
binds:
- src/lore/codex.py
- src/lore/cli.py
- tests/unit/test_codex_map.py
- tests/unit/test_codex_build_adjacency.py
- tests/e2e/test_codex_map.py
related:
- tech-arch-frontmatter
- tech-arch-source-layout
- tech-arch-projects-module
- ref-lore_api-core
- conceptual-workflows-codex-map
- conceptual-workflows-nested-projects
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

## `map_documents(project_root, start_id, *, depth_out=1, depth_in=1, full=False, scope=None) -> list[dict] | None`

Public function in `codex.py`. Performs a two-budget directional BFS across the
codex graph reachable at `scope` from `start_id` and returns the neighbour list — never the seed
itself.

### Signature

```python
def map_documents(
    project_root: Path,
    start_id: str,
    *,
    depth: int | None = None,
    depth_out: int | None = None,
    depth_in: int | None = None,
    full: bool = False,
    scope: str | None = None,
) -> list[dict] | None:
    ...
```

Keyword-only parameters (note the `*,`). `depth` sets both axes to the same value; `depth_out`/`depth_in` set one axis independently. `scope` takes the same three forms as `--project` (`None` reads `default-project-scope`, `"self"`/`"all"`, or a project name).

### Return shape

| Mode | Per-record keys |
|------|-----------------|
| `full=False` (default) | `id`, `group`, `title`, `summary`, `origin` |
| `full=True` | `id`, `group`, `title`, `summary`, `related`, `body`, `origin` |

The record list is sorted alphabetically by `id` — BFS visitation order is
discarded, and `id` is the qualified form for a foreign record. `group` comes off the index metadata `list_codex` already attached to each record — the owning project's own path-derived group — rather than being re-derived here.

| Outcome | Return |
|---------|--------|
| `start_id` not found in the resolved scope | `None` |
| Empty neighbourhood | `[]` |
| `depth_out` or `depth_in` negative | raises `ValueError` |
| `scope` names no project in scope | raises `UnknownProjectError` |

`None` is reserved for the unknown-seed case — empty neighbourhoods are `[]`.

### Algorithm

1. Validate `depth_out >= 0` and `depth_in >= 0` (after the CLI's own default-resolution). Raise `ValueError` if either is
   negative.
2. Build the scoped codex index via `list_codex(project_root, scope=scope)` — this project's own documents merged with what it inherits and, under `all` or a named project, every discovered project's own documents (`tech-arch-projects-module`). Build a
   `dict[str, dict]` keyed by `id` (qualified for a foreign record).
3. Resolve the seed through `scoped.select`: a bare `start_id` matches this project's own row first; a qualified `start_id` never matches a `self` row. If nothing resolves, return `None`.
4. Build directional adjacency via `_build_adjacency(index, docs, self_name=...)` —
   one pass, two `dict[str, set[str]]` maps for outbound and inbound edges.
5. Initialise the BFS state:
   - `visited: set[str] = {seed_id}` — the seed is visited but never emitted.
   - `queue: deque[tuple[str, int, int]] = deque([(seed_id, 0, 0)])` — entries
     are `(doc_id, out_used, in_used)`.
   - `result_ids: list[str] = []`.
6. Two-budget BFS. While the queue is non-empty, dequeue `(doc_id, out_used, in_used)`:
   - If `doc_id != seed_id`, append it to `result_ids`. The seed is enqueued so
     its neighbours are explored, but it is filtered out of the output.
   - If `out_used < depth_out`, for each neighbour `nb` in `outbound[doc_id]` not
     in `visited`, add `nb` to `visited` and enqueue `(nb, out_used + 1, in_used)`.
   - If `in_used < depth_in`, for each neighbour `nb` in `inbound[doc_id]` not in
     `visited`, add `nb` to `visited` and enqueue `(nb, out_used, in_used + 1)`.
7. Sort `result_ids` alphabetically.
8. Build the result list. In `full=False` mode this uses the cached metadata
   records only — the file is **not** re-parsed. In `full=True` mode each surviving ID is rehydrated with body and `related`, and each `related` entry is normalised into the index's key space via `projects.index_key` before being returned, so every id the record hands back is one the caller can address directly.

### Key properties

- **Seed-exclusion** is enforced at append-time by `if doc_id != seed_id`.
- **Dedupe-by-ID** is enforced by the `visited` set, checked before enqueueing
  in either direction.
- **Cross-direction visit** — a node reachable via both axes appears exactly
  once. Whichever path enqueues it first wins; subsequent attempts fail the
  `nb not in visited` guard.
- **Asymmetric budgets** — `depth_in=0` makes the inbound expansion a no-op,
  guaranteeing the result contains only outbound-reachable nodes (and vice
  versa). **The two budgets are independent per node, not one combined hop
  count from the seed** — a node reached by one outbound hop still has an
  unused inbound budget, so its own backlinks expand too. `--depth 1` can
  therefore return far more than the seed's direct neighbours on a densely
  linked codex; `--depth-out 1 --depth-in 0` is the form that means exactly
  "direct outbound neighbours". This is existing, unchanged behaviour —
  `conceptual-workflows-codex-map` records it as the form to use for a
  cross-project neighbour query.
- **Default body short-circuit** — `full=False` never reads document bodies.
  `--full` retains the per-node parse cost.
- **Scope-agnostic core** — the two-budget walk itself has no concept of a
  project boundary. A cross-project edge traverses exactly like a local one;
  the direction convention on such an edge (ancestor → descendant only) is an
  authoring rule enforced by `lore health`, never by this BFS
  (`decisions-014-link-direction`).

### Complexity

| Phase | Complexity |
|-------|------------|
| Scoped index build + adjacency build | O(V + E) over the resolved scope |
| Two-budget BFS | O(V + E), bounded by depth budgets |
| Result hydration (`full=True`) | O(R) parses, where R is the result size |
| Total | O(V + E) for `full=False`; O(V + E + R parses) for `full=True` |

V is the number of codex documents reachable at the resolved scope; E is the number of declared `related`
edges among them. Same asymptotic class as `chaos_documents`.

### Determinism

Result order is deterministic for a given codex state: BFS visitation order is
discarded and the final list is alphabetised by ID. The adjacency build itself
visits documents in the order `list_codex` returns them, which is already
deterministic within a scope.

## `_build_adjacency(index, docs, *, self_name="") -> tuple[dict[str, set[str]], dict[str, set[str]]]`

Private helper in `codex.py`. Returns `(outbound, inbound)` adjacency maps over
the resolved codex graph.

```python
def _build_adjacency(
    index: dict[str, dict],
    docs: list[dict],
    *,
    self_name: str = "",
) -> tuple[dict[str, set[str]], dict[str, set[str]]]:
    outbound = {doc_id: set() for doc_id in index}
    inbound  = {doc_id: set() for doc_id in index}
    for doc in docs:
        neighbours = _read_related(doc["path"], index, owner=doc["origin"], self_name=self_name)
        for n in neighbours:
            outbound[doc["id"]].add(n)
            inbound[n].add(doc["id"])
    return outbound, inbound
```

Properties:

- Initialises both maps with an empty set for every key in `index` so callers
  can index into either map without `KeyError`.
- Calls `_read_related` once per document, passing that document's own `origin` and this project's `self_name` — the two values `_related_key` needs to normalise a `related` entry into the index's key space (a bare entry is qualified by the project that wrote it; an entry already qualified with this project's own name reduces to its bare id — `lore.projects.index_key`). Defensive parsing (drop nulls, drop unknown IDs) is
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

## `_read_related(filepath, index, *, owner="self", self_name="") -> list[str]`

Private helper. Reads the `related` frontmatter
field from a single document via
`frontmatter.parse_frontmatter_doc(filepath, extra_fields=("related",))`,
normalises each entry into the index's key space via `_related_key(entry, owner=owner, self_name=self_name)`, applies defensive parsing, filters to entries present in `index`, and returns
the sorted result. Tolerance is intentional — a single bad file never breaks the
adjacency build. Strict enforcement lives in `lore health --scope schemas`. `owner` and `self_name` default to describe a single-project index, where every entry is already in its final form.

## `codex_map` CLI handler (in `cli.py`)

Registered as `@codex.command("map")` under the `codex` group.

```
lore codex map <doc_id> [--depth N] [--depth-out N] [--depth-in N] [--full]
```

Flag types:

- `--depth` / `--depth-out` / `--depth-in` — `click.IntRange(min=0)`,
  `default=None` (so absence is distinguishable from explicit `0`).
- `--full` — `is_flag=True`, `default=False`.
- `--project` (global) — threaded through as `scope=_scope(ctx)`.

Handler responsibilities, in order:

1. **Mutual-exclusion check (before any I/O).** If `--depth` is set together
   with `--depth-in` or `--depth-out`, raise `click.UsageError` with the exact
   PRD-pinned message. In `--json` mode the same message is emitted as
   `{"error": "..."}` to stderr. Exit code 2.
2. **Resolve effective budgets.** Fold the three flags into `eff_out` and
   `eff_in` via the table in `conceptual-workflows-codex-map` § "Resolve
   effective budgets".
3. **Call `map_documents`** with `depth_out=eff_out, depth_in=eff_in, full=full, scope=_scope(ctx)`.
4. **Unknown seed.** If `map_documents` returns `None`, print
   `Document "<doc_id>" not found` (or the JSON envelope equivalent) to stderr
   and exit 1.
5. **Dispatch output by mode.**
   - `full=True`, text mode — for each record emit `=== {id} ===` then `body`.
   - `full=True`, JSON mode — emit `{"documents": [...]}`, each row carrying `origin`.
   - `full=False`, JSON mode — emit `{"codex": [{id, group, title, summary, origin}, ...]}`,
     normalising empty-string `group` to `null` via `_group_for_json` (same
     helper `codex_list` uses).
   - `full=False`, text mode — `_origin_table(["ID", "GROUP", "TITLE", "SUMMARY"], rows, origins)`,
     the same renderer used by `codex_list`, `knight_list`, `doctrine_list`,
     and `artifact_list` — an ORIGIN column is prepended only when a row is foreign. Empty neighbourhood prints `No related documents.`.

### Output dispatch reuses existing renderers

| Mode | Renderer | Source |
|------|----------|--------|
| Default text | `_origin_table` (wraps `_format_table`) | `cli.py` (shared with `codex_list`) |
| Default JSON | inline dict literal, envelope key `"codex"` | `cli.py` (same shape as `codex_list --json`) |
| `--full` text | inline `=== {id} ===\n{body}` loop | `cli.py` (unchanged) |
| `--full` JSON | inline `{"documents": [...]}` | `cli.py` (unchanged shape, additive keys per entry) |

The default-mode handler MUST NOT compute column widths or padding locally — it
builds the rows list and delegates entirely to `_origin_table`.

## Sibling: `chaos_documents`

`chaos_documents` in `codex.py` is the sibling traversal function. It shares the adjacency build with `map_documents`: it calls
`_build_adjacency(index, docs)` and unions the two maps into a single
undirected adjacency for its random walk. `lore codex chaos` accepts no `--project` — its termination ratio is defined over one project's own reachable subgraph. See `tech-arch-codex-chaos`.
