---
id: conceptual-workflows-codex-map
title: lore codex map Behaviour
summary: 'What the system does internally when lore codex map <id> runs — directional
  bidirectional BFS over the related frontmatter field, list-shape default output
  mirroring lore codex list, optional full-body output via --full, the --depth/--depth-in/--depth-out
  flag matrix with mutual-exclusion enforcement, and traversal across a project boundary
  under --project.

  '
binds:
- src/lore/codex.py
- src/lore/cli.py
- tests/e2e/test_codex_map.py
- tests/unit/test_codex_map.py
related:
- conceptual-workflows-codex
- conceptual-workflows-codex-chaos
- conceptual-workflows-filter-list
- conceptual-workflows-json-output
- conceptual-workflows-nested-projects
- tech-arch-codex-map
- tech-arch-frontmatter
- ref-lore_cli-commands
- decisions-011-api-parity-with-cli
- codex
---
# `lore codex map` Behaviour

`lore codex map <id>` is a graph-shaped index over the codex. It walks the
`related` frontmatter field from a seed document — outbound edges and inbound
backlinks — and renders the resulting neighbourhood as a list-shape table whose
columns match `lore codex list`. The seed itself is never present in the
output. `--full` switches the renderer to the legacy full-body markdown blocks.

The default mode is a cheap discovery primitive: agents call it first, scan IDs
and one-line summaries, then run `lore codex show <id1> <id2>` on the rows they
care about. It is not a body dump.

## Preconditions

- The Lore project has been initialised.
- The seed document ID supplied as the `<id>` argument must exist in the codex reachable at the resolved scope.

## Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `<id>` | positional argument | required | The seed document ID to start traversal from. May be origin-qualified. |
| `--depth` | integer (min 0) | `1` (symmetric) | Sets both inbound and outbound depth to the same value. Mutually exclusive with `--depth-in` and `--depth-out`. |
| `--depth-out` | integer (min 0) | `1` if used or unspecified; `0` when `--depth-in` is the only directional flag passed | Outbound traversal depth (follows `related` links). Not allowed with `--depth`. |
| `--depth-in` | integer (min 0) | `1` if used or unspecified; `0` when `--depth-out` is the only directional flag passed | Inbound traversal depth (follows backlinks from other documents whose `related` lists name the current node). Not allowed with `--depth`. |
| `--full` | flag | off | Print full document bodies instead of the default neighbour table. Composes with directional flags. |
| `--project` (global) | name \| `all` \| `self` | `default-project-scope` | Which project(s) the codex index is built from before the walk runs. See "Traversal across a project boundary" below. |
| `--json` (global) | flag | off | Emit a JSON envelope instead of text. Envelope key depends on `--full`. |

## Steps

### 1. Validate flag combination

Before any I/O, the CLI handler rejects `--depth` combined with either `--depth-in`
or `--depth-out`. The rejection is a Click `UsageError`, exit code `2`, with the
exact message:

```
--depth cannot be combined with --depth-in or --depth-out. Use --depth for symmetric traversal, or --depth-in and/or --depth-out for directional traversal.
```

In `--json` mode the same message is written to stderr inside the standard
`{"error": "..."}` envelope, exit code `2`. The check runs before the seed lookup,
so an invalid invocation never partially executes.

`--depth-in` and `--depth-out` together are valid and combine. Only `--depth` is
mutually exclusive with the directional pair.

### 2. Resolve effective budgets

The CLI handler folds the three flags into two integers — outbound depth and
inbound depth — using this rule:

| Flags passed | Outbound budget | Inbound budget |
|--------------|-----------------|----------------|
| none | `1` | `1` |
| `--depth N` | `N` | `N` |
| `--depth-out N` only | `N` | `0` |
| `--depth-in N` only | `0` | `N` |
| `--depth-out A --depth-in B` | `A` | `B` |

### 3. Build the scoped index and validate the seed

`map_documents` in `lore.codex` loads the codex index for the resolved `--project` scope — this project's own documents plus what it inherits, and (under `all` or a named project) every discovered project's own documents, exactly as `codex list` builds its listing. If the supplied seed is not present in that index, the function
returns `None` and the CLI handler prints `Document "<id>" not found` to stderr
and exits with code 1 (same JSON envelope shape as today under `--json`).

### 4. Build bidirectional adjacency

A single pre-pass over the index reads every document's `related` field via
`_read_related` and registers each declared edge in two maps:

- `outbound[doc_id]` — set of IDs the document points at via its own `related`.
- `inbound[doc_id]` — set of IDs whose `related` field contains the document.

Every id in these maps is in the index's own key space — bare for this project's own documents, origin-qualified for a foreign one. Each `related` entry is normalised into that key space before matching: an entry is qualified by the project that wrote it (a bare entry written inside `lore` is `lore`'s own document), then reduced to a bare id if that qualifier equals this project's own name (`lore.projects.index_key`) — the mechanism that lets an ancestor's document backlink to something the reading project already owns. This is the same helper used by `lore codex chaos` (`_build_adjacency`), so both commands see the same adjacency view of the resolved scope.

### 5. Two-budget BFS

The traversal uses a single queue of `(doc_id, out_used, in_used)` entries
seeded with the start ID at `(0, 0)`. While the queue is non-empty:

- Outbound neighbours of the current document are enqueued iff
  `out_used < depth_out`.
- Inbound neighbours are enqueued iff `in_used < depth_in`.
- A `visited` set keyed by document ID prevents revisits. A node reachable via
  both directions is enqueued and reported at most once.
- The seed is added to `visited` immediately but never appears in the result
  set.

**`out_used` and `in_used` are independent per-node budgets, not one combined hop count from the seed.** A node reached by one outbound hop still has an unused inbound budget, so its own backlinks expand too, and the frontier compounds. `--depth 1` therefore does not mean "direct neighbours only" — it can return most of a large, densely-linked codex. `--depth-out 1 --depth-in 0` is the form that means exactly "direct outbound neighbours", and is the one to reach for when triaging a specific hop distance, in one project or across `--project all`.

### 6. Sort and render

Results are sorted alphabetically by ID for deterministic output — the qualified ID for a foreign document. Rendering
depends on `--full`:

**Default text mode** — uses the shared `_origin_table` helper (which wraps `_format_table`) that powers
`lore codex list`, `lore knight list`, `lore doctrine list`, and
`lore artifact list`. Columns are ID, GROUP, TITLE, SUMMARY, with a leading ORIGIN column when the result set holds a foreign row. GROUP is derived
from the document's directory path via `paths.derive_group`, read off the index metadata for both self and foreign rows. Empty
neighbourhood prints `No related documents.` and exits 0.

```
  ID                                GROUP                 TITLE                                     SUMMARY
  conceptual-workflows-codex        conceptual/workflows  Codex Commands — `lore codex`             ...
  conceptual-workflows-codex-chaos  conceptual/workflows  `lore codex chaos` Behaviour              ...
  tech-arch-codex-map               tech/arch             Codex Map — `map_documents` Internals     ...
```

**Default JSON mode** — same envelope key as `lore codex list --json`, every row carrying `origin`:

```json
{"codex": [
  {"id": "...", "group": "conceptual/workflows", "title": "...", "summary": "...", "origin": "self"}
]}
```

Empty neighbourhood is `{"codex": []}`, not an error.

**`--full` text mode** — preserves today's full-body output. Each surviving
neighbour is rendered as `=== <id> ===` followed by the document body. The
seed is excluded; directional flags still apply.  Block order is alphabetical
by ID.

**`--full` JSON mode** — keeps the `documents` envelope for backward
compatibility, with `group`, `related` and `origin` keys added per entry. A `related` id inside a `--full` record is normalised into the same key space as the record's own `id` — an id the reader can address directly:

```json
{"documents": [
  {"id": "...", "title": "...", "summary": "...", "group": "...", "related": ["..."], "body": "...full markdown...", "origin": "self"}
]}
```

## Traversal across a project boundary

A cross-project `related` edge is legal in one direction only, by authoring convention: an ancestor document may name an origin-qualified descendant document; a descendant document must not name an ancestor's (`decisions-014-link-direction`). Nothing in the walk itself enforces the direction — the BFS has no forbidden edge — so a document that breaks the convention still traverses; `lore health` never reads another project and so cannot flag it (`conceptual-workflows-nested-projects`).

`--project all --depth-out 1 --depth-in 0` from an ancestor's coordination document is the answer to "which projects does this document touch", in one call: each participating project's document is a direct outbound neighbour, and it comes back origin-qualified.

## When to use which mode

| Goal | Invocation |
|------|------------|
| Discovery — scan neighbours and pick IDs to read | `lore codex map <id>` (default) |
| Outbound transitive dependencies up to depth N | `lore codex map <id> --depth-out N` |
| Who references this doc | `lore codex map <id> --depth-in 1` |
| Read every neighbour body end-to-end | `lore codex map <id> --full --depth N` |
| Structured neighbour list for scripts | `lore --json codex map <id>` |
| Which projects a coordination document touches | `lore --project all codex map <id> --depth-out 1 --depth-in 0` |

The default mode is the right answer for scout knights and any agent that
needs to triage the codex before reading anything. `--full` is for human
maintainers and tooling that genuinely needs the bodies.

## Python API parity

Per ADR-011, the public function `lore.codex.map_documents` exposes the same
behaviour as keyword-only arguments:

```python
map_documents(project_root, start_id, *, depth_out=1, depth_in=1, full=False, scope=None)
```

The CLI flag `--depth N` translates to `depth_out=N, depth_in=N` at the
handler level — the Python API exposes the two axes directly. `scope` takes the same three forms as `--project`. Return shape is
a list of dicts with `id`, `group`, `title`, `summary`, `origin` (default) or those keys
plus `related` and `body` (`full=True`). Returns `None` if the seed is not in
the resolved index; an empty neighbourhood returns `[]`. See `tech-arch-codex-map` for
the algorithm details and `_build_adjacency` contract.

## Failure Modes

| Failure point | Behaviour | Exit code |
|---|---|---|
| `--depth` combined with `--depth-in` or `--depth-out` | Click `UsageError` with the pinned conflict message; in `--json` mode the same message is emitted as `{"error": "..."}` to stderr | 2 |
| Negative depth value (any flag) | Click `IntRange(min=0)` rejection | 2 |
| Seed document not found in the resolved scope | `Document "<id>" not found` to stderr (or JSON `{"error": "..."}`) | 1 |
| `--project` names no project in scope | `Unknown project "<name>". Projects in scope: <a, b, c>.` to stderr | 1 |
| Empty neighbourhood (default) | `No related documents.` to stdout; JSON `{"codex": []}` | 0 |
| Empty neighbourhood (`--full`) | Nothing printed; JSON `{"documents": []}` | 0 |
| Broken `related` link (ID not in the resolved index) | Silently skipped; traversal continues | 0 |
| `related` field absent, null, or empty | Node treated as leaf; no error | 0 |
| `related` field contains nulls or non-strings | Defensive parsing in `_read_related` drops them; no error | 0 |
| A descendant document names an ancestor document in `related` | Edge still traverses (not authoring-checked at read time); `lore health` never flags it, because flagging it would require reading another project | 0 |

## Out of Scope

- Writing or modifying any codex document — `lore codex map` is read-only.
- Multi-seed traversal in a single invocation.
- New frontmatter fields or edge types — `related` is the only edge read.
- Glossary auto-surface under `--full` — `lore codex map` does not invoke
  the glossary block under any flag combination (handled separately).
- Graph structure output (which document linked to which) — output is a flat
  list, sorted by ID.
- Fixing `--depth`'s independent-budget behaviour into a single combined hop count — that is a change to a shipped command's output, tracked separately from this traversal's cross-project reach.
