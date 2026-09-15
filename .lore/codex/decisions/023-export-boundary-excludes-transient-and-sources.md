---
id: decisions-023-export-boundary-excludes-transient-and-sources
title: 'ADR-023: An export, and a cross-project related edge, never reach transient/
  or sources/'
summary: 'ADR excluding .lore/codex/transient/ and .lore/codex/sources/ documents
  from every export an ancestor offers a descendant. exported_ids checks each candidate''s
  path through paths.is_transient_codex_path and paths.derive_group before any export
  pattern is matched; a related entry naming an excluded document resolves to nothing,
  and no health check reports it because lore health never reads another project.

  '
binds:
- src/lore/projects.py
related:
- decisions-019-overlay-scope-stops-at-transient
- decisions-014-link-direction
- conceptual-workflows-nested-projects
- tech-arch-projects-module
---

# ADR-023: An export, and a cross-project related edge, never reach transient/ or sources/

## Context

ADR-019 fixed the blast radius of project-authored config at "canonical codex
documents and `sources/`, never `transient/`", because `transient/` holds
scratch artefacts of an in-flight feature that are deleted once it ships.
Nested Projects opens two new paths that can point at a document outside its
own project — an ancestor's `[shared].exports` / `[[descendants]]` export list,
and a `related` entry inside an exported document — and neither path
previously obeyed any boundary, because neither previously existed.

## Decision

A codex document under `.lore/codex/transient/` is never exportable, and
neither is one under `.lore/codex/sources/`. `exported_ids` accepts
`ExportCandidate` records that carry each candidate's file path, and excludes
any candidate whose path answers true to `paths.is_transient_codex_path`
(ADR-019's single home for that boundary) or whose derived group
(`paths.derive_group`) is the `sources` layer — before any export pattern is
even matched.

A `related` entry inside an exported document that names an excluded document
has nothing to resolve to: the excluded document never enters the merged index
a descendant reads, so the entry produces no traversal edge and no error.
Nothing enforces the exclusion by inspecting the other side after the fact —
`lore health` never reads another project, so no check can detect that a
document an ancestor exported was, or later became, a `transient/` or
`sources/` document.

## Rationale

- **A transient document is deleted when its feature ships.** Exporting one
  guarantees a future dangling reference, and the one place that reference
  would surface is a different repository the document's owner cannot see.
- **A source is disposable by design (ADR-014).** Its whole point is that
  deleting it dangles nothing; exporting one would create exactly the dangling
  reference ADR-014 exists to rule out.
- **Excluding at read time, rather than warning after the fact, is the only
  version that helps.** A warning that fires only once the document is already
  deleted arrives too late for the descendant that already saw it.

## Alternatives Considered

| Option | Why rejected |
|--------|-------------|
| **Allow transient exports** | Every export of a `transient/` document is a guaranteed future dangling reference, in a repository its owner cannot see once the document is deleted. |
| **Warn instead of excluding** | A warning that only fires after the document is deleted arrives too late to prevent the descendant from having already seen it. |
| **Let each project configure the boundary** | ADR-019 already rejected a project-configurable boundary for overlays; the transient/canonical line is fixed, not a per-project setting. |

## Consequences

**Easier:**
- An ancestor's in-flight scratch work never leaks into a descendant's index,
  the same guarantee ADR-014 already gives a source's provenance never leaking
  into canon.
- The exclusion is checked through the two existing single homes for these
  questions (`paths.is_transient_codex_path`, `paths.derive_group`) — no second
  copy of either check exists in `projects.py`.

**Harder:**
- An author who wants to share a transient note with a descendant has no
  per-document override — the document must be promoted to a stable layer
  first, the same as it would need to be for any other stable reader.
- A `related` entry that once resolved, then stopped resolving because its
  target moved into `transient/` or was deleted from `sources/`, produces no
  signal anywhere; the descendant stops seeing a neighbour it once saw.

## Constraints Imposed

1. **`exported_ids` excludes a `transient/` or `sources/` candidate before
   matching any export pattern**, for every reader that supplies a path on its
   candidates.
2. **The exclusion is checked through `paths.is_transient_codex_path` and
   `paths.derive_group`** — the existing single homes for those questions.
   `projects.py` holds no second implementation of either.
3. **No health check validates this boundary, from either project.**
   Enforcement is confined to what `exported_ids` excludes at read time; adding
   a cross-project check requires reading another project's files, which this
   feature does not do.

## Status History

| Date | Status | Note |
|------|--------|------|
| 2026-09-02 | accepted | Recorded alongside `exported_ids`' path-based exclusion of `transient/` and `sources/` candidates. |
