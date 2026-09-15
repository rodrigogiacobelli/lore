---
id: decisions-026-project-naming-and-addressing
title: 'ADR-026: A project''s name is its own to set; export lists are a bloat filter,
  not access control'
summary: 'ADR fixing project naming and origin-qualified addressing together. A project''s
  name comes from its own project-name key or its directory name; no ancestor can
  rename it, and a duplicate name is undetected and resolves deterministically (first
  match in self, ancestor, descendant order) because lore health never reads another
  project. Qualification splits an id on the first colon only; a bare id resolves
  locally first, a qualified id never resolves locally. An export list controls what
  an agent sees, never what a human or process with filesystem access can reach.

  '
binds:
- src/lore/projects.py
- src/lore/validators.py
related:
- decisions-006-id-references
- conceptual-workflows-nested-projects
- tech-arch-projects-module
---

# ADR-026: A project's name is its own to set; export lists are a bloat filter, not access control

## Context

A project's name is used both as the `--project` selector value and as the
qualifier in every origin-qualified entity id it exports. Two projects in one
subtree can end up with the same resolved name — including, in the worst case,
an ancestor sharing its own name with the project reading it. Separately, an
export list (`[shared].exports`, a `[[descendants]]` block's `exports`) reads,
at a glance, like a permission system, and will be treated as one unless the
record says otherwise.

## Decision

1. **Naming.** A project's name comes from its own `project-name` config key,
   falling back to its directory name when that key is empty. No ancestor can
   rename a descendant: a `[[descendants]]` block's `name` field is a label
   used only in `lore health` messages and for a human reading the config, and
   has no resolving power.
2. **A duplicate name is undetected, and resolves deterministically.**
   `resolve_project` returns the first project, in `list_projects`' order
   (self, then ancestors nearest-first, then descendants sorted by name),
   whose resolved name matches. A name shared between two projects in scope
   —including an ancestor sharing the reading project's own name — resolves
   silently to whichever ref comes first in that order; the others become
   unreachable by `--project`. Nothing surfaces the collision: `lore health`
   never reads another project, so no check can see it from either side. The
   remedy is the project's own: set `project-name` to something unique.
3. **Addressing.** An entity id originating outside the reading project is
   qualified as `<project-name>:<entity-id>`, split on the **first** colon
   only — a codex id may itself contain a colon, but `project-name`'s grammar
   (`^[a-zA-Z0-9][a-zA-Z0-9_-]*$`) admits none, so the left half of a split is
   unambiguous whenever it names a real project. A bare id always resolves
   locally first; a qualified id never resolves locally, even when a local
   document happens to share its exact text.
4. **Export lists are a bloat filter, not access control.** They are
   documented as controlling what an agent sees in `list`/`show`/`search`
   output, never what a human or process can reach — anyone with filesystem
   access to a descendant already has access to its ancestor's files directly,
   with or without an export list naming anything.

## Rationale

- **A project names itself because nothing above or below it should be able
  to change how it is addressed from outside.** Letting an ancestor's block
  assign a descendant's name would let it silently rename something it does
  not own.
- **Detecting a duplicate name requires reading another project's state**,
  which `lore health` does not do (the project only ever validates its own
  entities). The resolution order is deterministic without a check — it is
  not visible without one.
- **An export list cannot be access control, because filesystem access
  already grants everything an export list could withhold.** Documenting it
  as security would be a false claim, and a false security claim is worse
  than none.

## Alternatives Considered

| Option | Why rejected |
|--------|-------------|
| **Let the ancestor's block name the descendant** | An ancestor's block could then shadow a name the descendant already uses for itself; the fix for a duplicate is to set `project-name` on the project itself, not to let the ancestor override it. |
| **Make a duplicate name an error** | Would break a project's own commands because of a sibling project it does not control and may not even know exists. |
| **Document exports as access control** | False — filesystem access already reaches everything an export list could withhold — and a false security claim is worse than none. |

## Consequences

**Easier:**
- A project's identity is entirely its own to set; nothing above or below it
  in a tree can change how it is addressed.
- Addressing needs no registry: a bare id resolves locally, a qualified id
  never does, and the split is unambiguous by construction.

**Harder:**
- A name collision is silent. Nothing in the running system reports it, and
  the operator who hits one must diagnose "the wrong project answered" from
  behaviour alone, with the fix being to rename the project that collided.

## Constraints Imposed

1. **`project_name(project_root)` is the single source of a project's
   resolved name.** A `[[descendants]]` block's `name` label is never
   consulted for resolution, only for display.
2. **`resolve_project` returns the first name match in self → ancestors
   (nearest first) → descendants (sorted) order.** No check anywhere detects
   or reports a duplicate name.
3. **Qualification splits on the first colon only.** `project-name`'s grammar
   must never admit a colon, or this split becomes ambiguous.
4. **An export list is documented as a visibility filter.** No code path may
   treat it as an access-control boundary.

## Status History

| Date | Status | Note |
|------|--------|------|
| 2026-09-02 | accepted | Recorded alongside `project_name`, `resolve_project`, and the `qualify`/`split_qualified` id algebra in `lore.projects`. |
