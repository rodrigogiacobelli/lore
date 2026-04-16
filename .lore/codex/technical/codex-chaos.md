---
id: tech-arch-codex-chaos
title: Codex Chaos — `chaos_documents` and Bidirectional Adjacency Internals
summary: 'Internal implementation of chaos_documents in codex.py: bidirectional adjacency
  pre-pass, reachable-set BFS, random walk loop, RNG injection pattern (rng=None default),
  validate_chaos_threshold in validators.py, and the codex_chaos CLI handler in cli.py.
  Sibling to tech-arch-codex-map.

  '
related:
- tech-arch-codex-map
- tech-arch-source-layout
- tech-arch-frontmatter
- conceptual-workflows-codex-chaos
- tech-api-surface
- standards-dry
- decisions-011-api-parity-with-cli
---

# Codex Chaos — `chaos_documents` and Bidirectional Adjacency Internals

**Source module:** `src/lore/codex.py`

This document covers `chaos_documents` and its supporting internals added to
`codex.py` for the `lore codex chaos` command, `validate_chaos_threshold` in
`validators.py`, and the `codex_chaos` CLI handler in `cli.py`. It is the sibling
document to `tech-arch-codex-map` (`lore codex show tech-arch-codex-map`).

## `chaos_documents(codex_dir, start_id, threshold, rng=None) -> list[dict] | None`

Public function in `codex.py`. Returns `None` when `start_id` is absent from the
codex index (signals missing seed to the CLI handler). Returns a `list[dict]` on
success. Each dict has keys `id`, `type`, `title`, `summary`, `body` — the same
contract as `read_document` and `map_documents`.

### Algorithm

The algorithm executes in six steps:

1. **RNG resolution** — if `rng` is `None`, the `random` module is used as the
   default. Any object with a `.choice()` method is accepted, enabling test
   injection without monkeypatching.

2. **Threshold validation** — `validate_chaos_threshold(threshold)` is called; a
   `ValueError` is raised on invalid input (below 30 or above 100). `chaos_documents`
   enforces the rule at the domain layer; `cli.py` also enforces it at the UX layer
   via `click.IntRange(min=30, max=100)`, consistent with ADR-011.

3. **Index load** — `scan_codex(codex_dir)` is called once to build a
   `dict[str, dict]` keyed by document ID. If `start_id` is not in the index,
   return `None`.

4. **Bidirectional adjacency pre-pass** — iterate over every document in the index.
   For each document, call `_read_related(filepath, index)` to get its declared
   neighbour IDs. Register each declared link in both directions in an adjacency
   `dict[str, set[str]]`. This pre-pass runs once; `_read_related` is not called
   again during the walk. This avoids the N+1 `scan_codex` problem that would arise
   from calling `_read_related` per walk step.

5. **Reachable-set BFS** — perform a standard BFS from `start_id` over the
   bidirectional adjacency map to produce `reachable: set[str]`. This is the
   denominator for threshold evaluation. If `len(reachable) == 1` (only the seed),
   return the seed document and exit.

6. **Random walk loop** — start at `start_id`. At each step:
   - Add the current document to `visited`.
   - Fetch the full document dict via `read_document(codex_dir, current_id)` and
     append to `result`.
   - Compute unvisited reachable neighbours: `reachable & adjacency[current_id] - visited`.
   - If none remain, stop.
   - Check termination condition:
     `(len(visited) - 1) / (len(reachable) - 1) >= threshold / 100`. If met, stop.
   - Pick next node: `rng.choice(list(unvisited_neighbours))`.

Return `result`.

## Bidirectional Adjacency Map

The `related` frontmatter field is **directed**: A declaring B does not mean B
declares A. This asymmetry is appropriate for `map_documents` (BFS follows declared
direction) but suboptimal for chaos traversal, where the goal is probabilistic
discovery across the connected neighbourhood regardless of link direction.

`chaos_documents` solves this with a pre-pass that treats all declared edges as
undirected: `A → B` is registered as both A ∈ neighbours(B) and B ∈ neighbours(A).
This ensures that a document reachable via an inbound link is included in the walk
candidate set, not just documents reachable via outbound links.

`map_documents` is unchanged. Its directed-only traversal behaviour is preserved.

## RNG Injection Pattern

`rng=None` defaults to the `random` module, which provides `random.choice()`. The
parameter accepts any object with a `.choice()` method. Pass `random.Random(seed)`
to get a reproducible sequence:

```python
import random
results = chaos_documents(codex_dir, "my-doc", threshold=50, rng=random.Random(42))
```

This pattern enables unit tests to inject a seeded RNG without monkeypatching the
`random` module. It also provides the scaffolding for a future `--seed` CLI flag
(post-MVP) without requiring further API changes.

## `validate_chaos_threshold(value: int) -> tuple[bool, str | None]`

Private validator in `validators.py`. Returns `(True, None)` for values in
30–100 inclusive. Returns `(False, error_message)` for values outside that range,
where `error_message` is `"--threshold must be between 30 and 100"`.

Called by `chaos_documents`, which raises `ValueError(error_message)` on `(False, ...)`.
Also enforced in `cli.py` via `click.IntRange(min=30, max=100)` as the UX layer.
Both layers enforce the same rule, consistent with ADR-011 (API parity with CLI).

## `codex_chaos` CLI Handler (in `cli.py`)

Registered as `@codex.command("chaos")` under the `codex` Click group.

```
lore codex chaos <id> --threshold <int>
```

- `id` — positional argument (the seed document ID).
- `--threshold` — `click.IntRange(min=30, max=100)`, required. No default.
- Uses `ctx.obj["project_root"]` and `ctx.obj.get("json", False)` — same pattern
  as `codex_map`. No local `--json` flag.

**Error handling (missing seed):**
- Text mode: `click.echo(f'Document "{id}" not found', err=True)` then
  `ctx.exit(1); return`.
- JSON mode: `click.echo(json.dumps({"error": f'Document "{id}" not found'}),
  err=True)` then `ctx.exit(1); return`.

Error handling mirrors `codex_map` exactly.

## Complexity

| Phase | Complexity |
|-------|------------|
| Bidirectional adjacency pre-pass | O(V + E) |
| Reachable-set BFS | O(V + E) |
| Random walk (per step) | O(k) where k is local adjacency size |
| Total | O(V + E) |

Same asymptotic class as `map_documents`. V is the number of codex documents; E is
the total number of declared `related` links across all documents.

## Performance

`read_document` calls `scan_codex` internally on each invocation (same note as
`tech-arch-codex-map`). For MVP codex sizes (tens to low hundreds of documents) this
satisfies the 2 s P95 NFR. Refactoring `read_document` to accept a pre-built path
index is deferred Post-MVP.

## Determinism

`chaos_documents` is explicitly non-deterministic by design. Unit tests inject
`rng=random.Random(seed)` to get reproducible sequences. E2E tests must not assert
on output order or on the specific subset returned — they should assert only on
structural properties (seed always first, all returned IDs are valid codex IDs,
result length within expected range for a given threshold).
