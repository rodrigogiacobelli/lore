---
id: decisions-014-link-direction
title: Link direction — the codex is the hub, links live on the stable side
summary: ADR defining the direction of every link edge in Lore — codex↔codex (`related`),
  codex→code (`binds`), codex→rite (`rites`), and source→canonical (`related`, one-way).
  The unifying rule — the stable/authoritative side owns the link; volatile and derived
  entities carry none — and why each edge points the way it does.
related:
- conceptual-workflows-impacts
- conceptual-workflows-nested-projects
- decisions-006-id-references
---

# ADR-014: Link direction — the codex is the hub, links live on the stable side

## Context

Lore has several kinds of cross-reference, and more are arriving as rites land.
Without one place stating who owns each edge and why, authors put links on the
wrong side — on a doc that gets rewritten often, or pointing the wrong way — and
the graph rots. This ADR fixes the direction of every edge in the system.

Key forces:

- **The codex is the single source of truth.** Documentation is authoritative;
  everything else is derived from it or feeds into it.
- **Some entities are volatile or disposable.** Sources are disposable raw input;
  rites are derived how-to that gets redistilled often. A link held on a volatile
  entity is a link that rots.
- **Links should point the way change and dependency flow**, so the graph doubles
  as an impact map.

## Decision

Every link edge in Lore has a fixed owner and direction. **The stable side owns
the link; the codex is the hub.**

| Edge | Field | Owner / direction | Back-link? |
|------|-------|-------------------|------------|
| codex ↔ codex (same project) | `related` | stored on one codex doc; traversal is bidirectional (`lore codex map` surfaces backlinks) | n/a — symmetric |
| codex ↔ codex (cross-project) | `related` | an entry may name an origin-qualified document in a descendant project; the edge points downward, by authoring convention only | **no** — nothing enforces the direction |
| codex → code | `binds` | codex doc names the code paths it governs | no — code has no frontmatter |
| codex → rite | `rites` | codex doc names the rites it governs | **no** — rites never link back |
| source → canonical | `related` | source names the canonical docs it changed | **no** — canonical must never name a source |
| rite → anything | — | rites carry no `related` and no `binds` | n/a — rites link to nothing |

## Rationale

- **The stable side owns the link.** The codex changes far less often than the
  rites built on it or the sources feeding it. Putting the edge on the stable
  side means rewrites of volatile entities don't break links.
- **Direction follows governance and provenance.** `binds` and `rites` point from
  the codex to what it *governs* (code, procedures) — the direction a codex change
  propagates. `source → canonical` points from raw input to what it *produced* —
  the direction provenance flows. In both cases the edge encodes a real dependency,
  so the graph is also an impact map.
- **Volatile/derived entities stay clean.** Rites carry nothing: no `related`
  (the codex holds codex→rite), no `binds` (removing the rite→code edge removes an
  entire stale-reference class, since code paths move under frequently-rewritten
  procedures). Sources carry only their own outbound provenance and are never
  pointed *to* by canon, so disposing of a source never dangles a canonical doc.
- **Links are navigation, not retrieval.** `rites:` enriches "reading this domain
  doc? here are procedures that touch it", but agents still find rites via
  `lore rite list`. No edge is load-bearing for retrieval, so a missing inbound
  link is never a failure to find something.
- **A cross-project `related` edge follows the direction inheritance already
  flows.** An ancestor's exported document may name a descendant's document —
  pointing the edge the same way a project's dependency on what it inherits
  runs. Nothing checks that an author pointed it the intended way: confirming
  the direction would mean reading the descendant's codex from the ancestor's
  side, and `lore health` validates only the project it runs in
  (`conceptual-workflows-nested-projects`). The rule is a documented authoring
  convention, not a checked one.

## Alternatives Considered

| Option | Why rejected |
|--------|-------------|
| **Links on the volatile side (rite→codex, canonical→source)** | Puts the edge where it rots. Every rewrite of a rite, or disposal of a source, risks breaking or dangling the link. The stable side must own it. |
| **Bidirectional stored links everywhere** | Doubles maintenance and staleness surface for no retrieval gain — `lore codex map` already surfaces backlinks from a single stored edge, and agents find rites via `list`. |
| **rite → code via `binds`** | A stale-reference factory: code paths move under a procedure that is itself frequently redistilled. Code linkage already belongs to the codex. |
| **No codex→rite edge at all** | Loses the "this doc governs these procedures" navigation and the change-propagation signal from truth to derived how-to. |

## Consequences

**Easier:**
- Volatile entities (rites) and disposable ones (sources) stay cheap to rewrite
  or delete — no outbound links to maintain on the side that changes.
- The rite→code stale-reference class does not exist.
- The graph doubles as an impact map: codex change → bound code and governed rites.

**Harder:**
- No traversal *from* a rite back to its semantic context; an agent reading a rite
  gets codex context only by having arrived from the codex side.
- Deleting or renaming a rite (or a canonical doc) leaves a dangling pointer on the
  owning side — the standard staleness class that `lore health` must validate for
  every edge that stores ids.

## Constraints Imposed

1. **Rites have no `related` and no `binds`.** The rite schema rejects both.
2. **Canonical docs never name a source** in `related`; sources MUST name every
   canonical doc they changed. `lore health` enforces both directions
   (`canonical_links_to_source` error; empty source `related` is a schema error).
3. **`rites:` is a codex-only field**, a list of rite ids validated for
   resolvability by `lore health`, exactly as `related`/`binds` are.
4. **Orphan asymmetry for rites.** A main rite no codex `rites:` names is NOT an
   error (found via `lore rite list`, like inbound-orphan sources). A `rites:` id
   with no matching rite IS an error.
5. **A cross-project `related` entry is downward-only by authoring convention,
   and no check enforces it.** `lore health` never reads another project, so
   an edge pointed the wrong way — or one that stops resolving because its
   target moved or was excluded from export — raises no error on either side.

## Status History

| Date | Status | Note |
|------|--------|------|
| 2026-06-02 | accepted | Initial decision — generalised from the rite linking model to cover all edges |
| 2026-09-02 | accepted (cross-project edge recorded) | The codex↔codex row splits into same-project (unchanged) and cross-project: a `related` entry may name an origin-qualified document in a descendant project, downward-only by authoring convention, with nothing enforcing the direction — enforcement would require reading another project's codex, which `lore health` does not do. |
