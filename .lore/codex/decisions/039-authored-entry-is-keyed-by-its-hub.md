---
id: decisions-039-authored-entry-is-keyed-by-its-hub
title: "ADR-039: An authored index entry is keyed by its hub, and Lore never writes the authored file"
summary: >
  ADR recording that an entry in .lore/index/authored.yaml is keyed by its
  cluster's hub — the member most linked to the rest of its own cluster, ties by
  ascending id — and that no Lore command creates, edits or deletes that file.
  A cluster whose hub has no entry is unauthored; an entry left behind by the
  partition is reported, never re-keyed. Repair is an authoring act.
binds:
  - src/lore/index.py
  - src/lore/graph.py
  - src/lore/defaults/skills/update-index/SKILL.md
related:
  - decisions-037-index-is-a-top-level-lore-directory
  - decisions-038-partition-is-deterministic-modularity-local-moving
  - conceptual-workflows-index
  - conceptual-workflows-health
  - tech-arch-codex-index
  - conceptual-entities-skill
---

# ADR-039: An authored index entry is keyed by its hub, and Lore never writes the authored file

## Context

The partition shifts as the codex changes. Measured over seven single-document
perturbations of the Lore codex, 86% of hubs survived unchanged and the
remainder moved, so an entry can outlive the cluster it was written for. The
authored file is the one artefact in the codex index a rebuild cannot recover.

## Decision

An entry is keyed by its cluster's **hub** — the member most linked to the rest
of its own cluster, ties by ascending id.

No Lore command creates, edits or deletes `.lore/index/authored.yaml`.

A cluster whose hub has no entry is `unauthored`. An entry whose hub is an
indexed document that heads no cluster is a `stale_entry` warning. An entry
whose hub is not an indexed document at all is an `unresolvable_hub` error.
Repair is an authoring act, performed by the `update-index` skill or by a
person.

## Rationale

- **The hub is the member the cluster is organised around**, computed from
  edges inside the cluster only, which is what makes it a stable key as
  membership shifts.
- **A hand-written summary attached to a set of documents nobody has checked is
  the failure the `drifted` status exists to prevent.** Automatic re-keying
  performs exactly that, silently.
- **The file is the only thing in the feature not recoverable by rebuilding.**
  A tool that rewrites it can lose it.

## Alternatives Considered

| Option | Why rejected |
|--------|-------------|
| **Re-key an entry automatically to the cluster containing its old hub** | Attaches a human-written summary to a set of documents nobody has checked, silently — the failure the `drifted` warning exists to prevent. |
| **Key by slug and match by membership overlap** | A rule with a threshold in it, which is a second thing to tune and a second thing to get wrong. |
| **Let Lore rewrite the file** | The file is the only thing in the feature that is not recoverable by rebuilding, and a tool that rewrites it can lose it. |

## Consequences

**Easier:**
- "One entry per cluster" is structural rather than a convention: the file is a
  mapping keyed by hub, so a duplicate hub is unrepresentable.
- A summary never describes documents nobody checked — every mismatch surfaces
  as a status or a health row.

**Harder:**
- A partition shift re-keys an entry by hand, and the author has to decide
  whether the old summary still describes the new membership.
- `lore index build` cannot make a project's index green on its own; the
  authoring pass is a separate act with a separate skill.

## Constraints Imposed

1. **No Lore command writes `.lore/index/authored.yaml`.** Adding one requires
   amending this ADR.
2. **An entry's key is its cluster's hub**, computed by `graph.cluster_hub` over
   edges inside the cluster only.
3. **An orphaned entry is reported, never re-attached.** The two reasons carry
   different severities: a hub that is still an indexed document is a warning, a
   hub that is not is an error.

## Status History

| Date | Status | Note |
|------|--------|------|
| 2026-09-16 | accepted | Recorded with the `lore index` command group and the `update-index` skill that authors the file. |
