---
id: decisions-030-knight-entity-removed
title: "ADR-030: The Knight entity is removed; a doctrine mission file is the only home for a reusable instruction"
summary: >
  ADR recording that the Knight entity is removed outright — module, CLI group,
  the five API callables and the Knight type, the packaged schema, the health
  scope, the paths helper, the entity_location row, the frontmatter_edit kind
  and the seeded tree. Lore has six entity types, and the one place a reusable
  instruction lives is the doctrine mission file that uses it.
binds:
  - src/lore/doctrine.py
  - src/lore/paths.py
  - src/lore/health.py
related:
  - decisions-029-doctrine-is-prose-not-a-graph
  - decisions-001-dumb-infrastructure
  - decisions-010-public-api-stability
  - conceptual-entities-doctrine
  - conceptual-entities-mission
---

# ADR-030: The Knight entity is removed; a doctrine mission file is the only home for a reusable instruction

## Context

A Knight held "how to be" and a doctrine step's `notes:` held "what to do", and
every doctrine author decided afresh which of the two an instruction belonged
in. The same guidance routinely landed in both. The `missions.knight` column,
the `lore knight` command group, five public API names, a packaged schema, a
health scope, a seeded tree and a `.gitignore` triad all existed to keep the
second copy addressable.

## Decision

The Knight entity is removed outright — module, CLI group, the five API
callables and the `Knight` type, `knight-frontmatter.yaml`,
`lore health --scope knights`, `paths.knights_dir`, the `knight`
`entity_location` row, the `knight` kind in `frontmatter_edit`, and
`src/lore/defaults/knights/**`.

Lore has six entity types. The one place a reusable instruction lives is the
doctrine mission file that uses it, and a Lore mission reaches it through
`missions.doctrine_mission`. No shim, no deprecation window, no alias.

## Rationale

- **Two homes for one instruction produce two copies and no rule for
  choosing.** The split between "how to be" and "what to do" was never
  decidable at the point of authoring, so authors duplicated rather than chose.
- **The second entity paid for itself only in addressability.** Every piece of
  machinery Knight required — a column, a command group, a schema, a health
  scope, a seeded tree — existed to make the second copy reachable, not to make
  it better.
- **A mission file already has a reader and a delivery path.**
  `lore show <mission-id>` splices the referenced body into the worker's brief,
  so the instruction arrives where it is used with no second lookup.

## Alternatives Considered

| Option | Why rejected |
|--------|-------------|
| **Deprecate `lore knight` for one release** | A deprecated command is a second addressable copy for exactly as long as it exists, and no compatibility shim ships. |
| **Keep Knight as a standalone persona a mission file can `include`** | An include is a template engine, which ADR-001 forbids, and it restores the two-places-to-put-an-instruction problem under a new name. |
| **Auto-migrate authored knights into doctrine missions** | Lore cannot know which doctrine a project's knight belongs to, and a wrong guess writes into a file the project owns. |

## Consequences

**Easier:**
- A doctrine author has exactly one file to write per mission and no rule to
  apply about which half of an instruction goes where.
- A worker receives its description and its reusable instructions in one call,
  with no second entity to resolve.

**Harder:**
- A project that authored its own knights must fold them into mission files by
  hand. `lore init` names the orphaned files once and leaves them on disk; the
  editorial work is the project's.
- Two workers that genuinely share a paragraph each carry their own copy. There
  is no include, so the duplication is visible and manual.

## Constraints Imposed

1. **No code, schema, seeded file or document names Knight as a live entity.**
   The only permitted survivals are the migration chain, which records DDL that
   ran, and `init.RETIRED_SEED_TREES`, which is the mechanism that removes the
   seeded tree.
2. **A reusable instruction lives in exactly one doctrine mission file.** No
   include, no import, no shared-fragment mechanism.
3. **Lore has six entity types.** Any document enumerating them says six.

## Status History

| Date | Status | Note |
|------|--------|------|
| 2026-09-16 | accepted | Recorded alongside the removal of `src/lore/knight.py`, the `lore knight` group, and the five `lore.api.__all__` names. |
