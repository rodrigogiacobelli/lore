---
id: decisions-041-render-is-a-cache-invalidated-by-a-stat-fingerprint
title: "ADR-041: The rendered index is a cache invalidated by a stat fingerprint"
summary: >
  ADR recording that .lore/index/codex.json stores a codex_fingerprint — a
  sha256 over path, size and mtime_ns for every indexed file — which
  search_index recomputes to decide whether to rebuild. lore index build rebuilds
  unconditionally. A missing, unparseable or wrong-version render is treated as
  absent, and deleting the file loses nothing.
binds:
  - src/lore/index.py
related:
  - decisions-001-dumb-infrastructure
  - decisions-037-index-is-a-top-level-lore-directory
  - decisions-038-partition-is-deterministic-modularity-local-moving
  - decisions-031-staged-multi-file-entity-write
  - tech-arch-codex-index
  - conceptual-workflows-index
---

# ADR-041: The rendered index is a cache invalidated by a stat fingerprint

## Context

`lore index search` refreshes before every match and must not feel like a second
tool call (ADR-001). A full rebuild of an 857-document codex costs 493 ms on the
reference machine; one `stat` per file costs 11 ms.

## Decision

`.lore/index/codex.json` stores a `codex_fingerprint`: `sha256` over
`f"{relpath}\t{size}\t{mtime_ns}\n"` for every indexed file, sorted by relpath.

`search_index` recomputes the fingerprint and rebuilds only when it differs.
`build_index` rebuilds unconditionally and is the answer to any doubt. A
missing, unparseable or wrong-version render is treated as absent. Deleting the
file loses nothing.

The render is written whole through `safewrite`, so a concurrent reader sees the
old file or the new one and never half of either; two processes refreshing at
once write the same bytes.

## Rationale

- **ADR-001 budgets round trips.** A search that makes the caller decide whether
  to build first has spent the budget the index exists to save.
- **A false positive costs one rebuild; a false negative needs a coincidence.**
  A checkout rewriting mtimes rebuilds once and then the fast path returns; a
  miss needs an edit of identical byte length landing in the same nanosecond,
  and `lore index build` is the unconditional answer to it.
- **A cache that can fail a command is not a cache.** Every unusable render
  answers the same way — absent — so no stored state can break a read.

## Alternatives Considered

| Option | Why rejected |
|--------|-------------|
| **Hash every file's content on every search** | 493 ms on every call, which is the cost ADR-001 budgets against. |
| **Trust an mtime alone** | Size and mtime together, hashed with the path, also catch an addition, a deletion and a move. |
| **A `--no-refresh` flag** | `codex-index-prd` rules it out, and `build` already is the unconditional path. |
| **Store the render in SQLite** | A cache in the database needs a migration and a schema version for something a file deletion should fix. |

## Consequences

**Easier:**
- `lore index search` costs one `stat` per document on a warm codex, so a caller
  never has to decide whether to rebuild first.
- The render is disposable: deleting it, or shipping a Lore that does not
  understand its version, costs one rebuild and nothing else.

**Harder:**
- The fingerprint is taken before the partition, so a document edited while a
  build runs leaves a fingerprint the next search disagrees with — correct, and
  it costs that search a rebuild.
- An edit of identical byte length landing in the same nanosecond as the last
  one is invisible to the fingerprint until someone runs `lore index build`.

## Constraints Imposed

1. **The render is a pure function of the codex.** It carries no slug, name,
   summary or status, so two projects with identical codexes and different
   authoring render identically.
2. **Any render that cannot be used is treated as absent** — missing,
   unreadable, unparseable, of another version, or structurally incomplete.
3. **`build_index` never consults the stored render.** It is the unconditional
   rebuild.

## Status History

| Date | Status | Note |
|------|--------|------|
| 2026-09-16 | accepted | Recorded with the `lore index` command group, whose search refreshes before every match. |
