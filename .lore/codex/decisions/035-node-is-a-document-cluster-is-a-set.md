---
id: decisions-035-node-is-a-document-cluster-is-a-set
title: "ADR-035: A node is one codex document; a cluster is a set of them"
summary: >
  ADR fixing the two graph nouns the codex index introduced. In Lore, node
  means one codex document as a vertex of the related graph, and cluster means
  a set of nodes the index partition groups together. The codex-map documents
  keep node; the codex index uses cluster in every identifier, JSON key, help
  string, health check name and document.
binds:
  - src/lore/index.py
  - src/lore/graph.py
related:
  - conceptual-workflows-codex-map
  - tech-arch-codex-map
  - conceptual-workflows-index
  - tech-arch-codex-index
  - decisions-036-index-partitions-the-local-canonical-codex
---

# ADR-035: A node is one codex document; a cluster is a set of them

## Context

The `related` graph has vertices, and with the codex index it also has groups
of vertices. `conceptual-workflows-codex-map` and `tech-arch-codex-map` call a
vertex a node. `codex-index-prd` called a group of vertices a node. Every
document written after the codex index uses one of the two meanings, and a
reader has no way to tell which.

## Decision

In Lore, **node** means one codex document as a vertex of the `related` graph,
and **cluster** means a set of nodes the index partition groups together.

The published `codex-map` documents keep their word. The codex index uses
`cluster` in every identifier, JSON key, help string, health check name and
document.

## Rationale

- **One feature does not rename a word two canonical documents already use.**
  The vertex meaning is published and load-bearing in `lore codex map`.
- **The two meanings live in the same graph**, in commands an agent runs in
  sequence, which is where ambiguity costs the most.
- **`cluster` says what the partition produces** without implying a
  subject-matter classification the partition does not perform.

## Alternatives Considered

| Option | Why rejected |
|--------|-------------|
| **Rename the vertex** | Edits two canonical documents to suit one feature, and leaves every reader of a graph meeting a non-standard word first. |
| **Overload `node` to mean both** | The two meanings live in the same graph and in adjacent commands; an agent cannot resolve which is meant. |
| **`region` / `topic` / `neighbourhood`** | Each is either vaguer than `cluster` or suggests a subject-matter classification the partition does not perform. |

## Consequences

**Easier:**
- A reader meeting `node` in any Lore document knows it is one codex document.
- An agent composing `lore codex map` and `lore index search` in sequence reads
  one vocabulary across both.

**Harder:**
- A contributor arriving from graph-clustering literature, where "node" is
  sometimes a merged super-vertex, has to learn Lore's narrower meaning.

## Constraints Imposed

1. **`node` names one codex document.** A document, help string or identifier
   that uses it for a set of documents is a defect.
2. **`cluster` names a set of nodes the index partition groups together.** The
   codex index uses it in every identifier, JSON key, help string, health check
   name and document.

## Status History

| Date | Status | Note |
|------|--------|------|
| 2026-09-16 | accepted | Recorded with the `lore index` command group, which introduced the second graph noun. |
