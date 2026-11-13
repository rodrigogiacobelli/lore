---
id: decisions-036-index-partitions-the-local-canonical-codex
title: "ADR-036: The codex index partitions this project's own canonical codex"
summary: >
  ADR recording that the codex index reads codex._list_codex_local(project_root)
  and drops every document under transient/ or sources/ through
  projects._is_unexportable_codex_layer. It never reads another project. Because
  the index is local-only, the render may carry member_paths without meeting the
  reason search_documents drops path from a scoped result.
binds:
  - src/lore/index.py
related:
  - decisions-006-id-references
  - decisions-023-export-boundary-excludes-transient-and-sources
  - decisions-028-inheritance-unconditional-federation-opt-in
  - decisions-035-node-is-a-document-cluster-is-a-set
  - tech-arch-codex-index
  - conceptual-workflows-index
---

# ADR-036: The codex index partitions this project's own canonical codex

## Context

`list_codex()` merges ancestor-exported documents unconditionally (ADR-028), and
`_list_codex_local` includes `transient/` and `sources/` with no filter. The
index renders a path per member relative to this codex root, and commits an
authored file describing what it indexed.

## Decision

The index reads `codex._list_codex_local(project_root)` and drops every document
under `transient/` or `sources/`, through
`projects._is_unexportable_codex_layer`. It never reads another project.

One consequence belongs in this decision rather than beside it: because the
index reads this project alone, the render carries `member_paths` without
meeting the reason `search_documents` drops `path` from a scoped result. That
field was dropped because a merged result can carry a *foreign* path, and this
one cannot. A `member_path` is a convenience emitted beside the id, never a
handle a command accepts — ADR-006's by-id rule is untouched, and its
harness-route carve-out already lifts that rule for codex documents specifically.

A document becomes indexable by graduating out of `transient/`, which is the
same gate ADR-019 and ADR-023 already apply.

## Rationale

- **An ancestor's document has no path relative to this codex root.** The
  render carries one path per member; a merged listing cannot supply it.
- **`authored.yaml` is committed.** Partitioning `list_codex()` would commit a
  description of another repository's documents into this one, and an ancestor
  editing its `[shared].exports` would drift entries in a project whose own
  files nobody touched.
- **`lore health` writes into `transient/` on every run under two of the three
  retention policies.** Indexing that subtree would let the index invalidate
  itself on a schedule an unrelated command sets.
- **An in-flight feature's working documents are authored and then deleted.**
  A cluster of them is a summary with a scheduled expiry.

## Alternatives Considered

| Option | Why rejected |
|--------|-------------|
| **Partition `list_codex()`** | An ancestor's document has no path relative to this codex root, and an ancestor's export-list edit would drift entries in a project that changed nothing. |
| **Index `transient/`** | `lore health` writes there on every run under two of the three retention policies, so the index would invalidate itself on a schedule set by an unrelated command; and a cluster of an in-flight feature's working documents is authored and then deleted. |
| **A config key to choose the scope** | ADR-018 and ADR-019 both refused a configuration surface for a scope question, for the same reason: a rule nobody can predict from the filename is worse than a rule with one answer. |

## Consequences

**Easier:**
- Every member of every cluster has a path relative to this codex root, so a
  caller opens a document without resolving its id first.
- A project's authored index describes only files that project owns, so it
  moves when its own codex moves and at no other time.

**Harder:**
- A descendant project inheriting documents from an ancestor indexes none of
  them; the two projects each carry their own index.
- A document under `transient/` is unreachable through `lore index search`
  until it graduates to a stable layer.

## Constraints Imposed

1. **The index reads `codex._list_codex_local(project_root)` only.** Reading a
   merged listing is a defect.
2. **`transient/` and `sources/` are excluded**, through
   `projects._is_unexportable_codex_layer` rather than a second path test.
3. **`member_paths` is a convenience beside the id, never a handle.** No command
   resolves a cluster or a document by path.

## Status History

| Date | Status | Note |
|------|--------|------|
| 2026-09-16 | accepted | Recorded with the `lore index` command group, which introduced the first committed artefact describing what the codex contains. |
