---
id: decisions-028-inheritance-unconditional-federation-opt-in
title: "ADR-028: Inheritance is unconditional, federation is opt-in; scope governs the downward axis only"
summary: >
  ADR fixing Nested Projects' two directions of visibility as independent
  axes. Upward inheritance is always on: resolve_scope includes
  resolve_ancestors in every answer, for every scope value, with no flag to
  disable it. Downward federation is opt-in: discover_descendants runs only
  when scope is "all" or names a project. default-project-scope and
  --project govern the downward axis only; neither ever disables inheritance.
binds:
  - src/lore/projects.py
related:
  - conceptual-workflows-nested-projects
  - tech-arch-projects-module
---

# ADR-028: Inheritance is unconditional, federation is opt-in; scope governs the downward axis only

## Context

Nested Projects has two directions of visibility across a tree: upward, a
project sees what its ancestors export to it; downward, a project reads
projects beneath it. Both answer a version of "how much of the tree do I
see", and a single flag or a single `scope` value could plausibly govern both
at once.

## Decision

The two directions are governed independently, as two axes rather than one.

**Inheritance (upward) is unconditional.** `resolve_scope` includes
`resolve_ancestors(...)` in every answer it returns, for every `scope` value
— there is no flag that turns it off.

**Federation (downward) is opt-in.** `discover_descendants(...)` runs only
when the resolved scope is `"all"` or names a project. A bare command in a
project with no tree beneath it performs zero directory scans.

`default-project-scope` and the `--project` selector govern the downward axis
only. Neither ever disables inheritance, and neither ever turns federation on
beyond what it explicitly names.

## Rationale

- **This is the decision two success criteria depend on.** Zero directory
  scans in a project with no tree above or below it, and byte-identical
  stdout for an untreed project, hold only because the downward axis stays
  off unless a command asks for it.
- **Inheritance exists to let an agent think across a tree it may not even
  know exists.** A flag it would have to remember to pass to see what an
  ancestor exports defeats that purpose; the whole value of inheritance is
  that nothing has to be asked for it to apply.
- **Collapsing the two onto one `scope` value hides a real behaviour
  change as a simplification.** A future change that makes `scope="all"` also
  mean "and export to me" would alter the upward axis while looking like it
  only touched the downward one. Recording the two axes as independent here
  is what makes such a change visible as a breach rather than a tidy-up.

## Alternatives Considered

| Option | Why rejected |
|--------|-------------|
| **One `scope` value governs both axes** | Collapses two independent questions — what do I inherit, what do I federate into — onto one token; a later change to one axis would silently change the other. |
| **Inheritance also opt-in, behind a flag** | Defeats the purpose of inheritance, which is to let an agent think across a tree without first having to know the tree exists. |
| **Federation unconditional, always walking descendants** | Breaks the zero-directory-scan guarantee for every project with a tree beneath it, turning every command into a filesystem walk nobody asked for. |

## Consequences

**Easier:**
- A project with no tree above or below it pays nothing for the feature: one
  `Path.is_dir()` probe per directory up to the filesystem root for
  inheritance, and no descendant walk at all unless `--project` asks for one.
- A descendant needs no configuration of its own to see what it inherits —
  nothing it can set turns inheritance off.

**Harder:**
- Two independent axes are two things to reason about when a tree's visibility
  looks wrong, rather than one `scope` knob to check.

## Constraints Imposed

1. **`resolve_scope` includes the upward walk (`resolve_ancestors`) in every
   answer**, regardless of the `scope` argument's value.
2. **`discover_descendants` runs only when the resolved scope is `"all"` or
   names a project** — never for a bare or `"self"` scope.
3. **A change that lets one `scope` value control both axes is a breach of
   this ADR, not a simplification**, and requires amending this ADR in place.

## Status History

| Date | Status | Note |
|------|--------|------|
| 2026-09-02 | accepted | Recorded alongside `resolve_scope`, `resolve_ancestors` and `discover_descendants` in `lore.projects`. |
