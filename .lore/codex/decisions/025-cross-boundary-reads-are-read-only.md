---
id: decisions-025-cross-boundary-reads-are-read-only
title: "ADR-025: Cross-boundary reads are read-only, and the rule lives in the core"
summary: >
  ADR making every origin-qualified entity id permanently unwritable.
  projects.reject_foreign raises ForeignEntityError as the first statement of
  every externally callable write function on a file-backed entity, including
  frontmatter_edit.update_frontmatter_fields; --project is a read selector
  and is rejected at exit 2 on every write, quest and mission command. No
  Lore process writes outside the .lore/ of the project it runs in.
binds:
  - src/lore/projects.py
  - src/lore/frontmatter_edit.py
related:
  - decisions-011-api-parity-with-cli
  - decisions-006-id-references
  - conceptual-workflows-nested-projects
  - tech-arch-projects-module
---

# ADR-025: Cross-boundary reads are read-only, and the rule lives in the core

## Context

Nested Projects gives one project a read path into another's files, both
upward (inheritance) and downward (`--project`). Nothing before this feature
distinguished "an entity this project owns" from "an entity this project can
see", so nothing prevented a write from following a read once addressing
crossed a project boundary.

## Decision

An origin-qualified entity id is **never** writable. `projects.reject_foreign`
raises `ForeignEntityError` when `projects.is_qualified` is true of the id
passed to it, and is the first statement of every externally callable write
function on a file-backed entity — every `new`, every `-f` edit, every
field-edit (`--set`/`--unset`/`--add`/`--remove`, routed through
`frontmatter_edit.update_frontmatter_fields`), and every `delete`.

`--project` is a read selector: it is rejected at exit 2 on every write, quest
and mission command. No Lore process writes outside the `.lore/` of the
project it runs in — there is no push, no copy, and no sync between projects.

## Rationale

- **The check belongs in the core, not the CLI, because ADR-011 exists to
  close exactly the gap a CLI-only check would leave open.** A Python caller
  reaching a write function directly must get the identical refusal a CLI
  invocation gets, with no second implementation to keep in step.
- **One call, first statement, covers every write path by construction.** A
  function that calls `reject_foreign` before doing anything else cannot
  partially apply a write before discovering the id was foreign.
- **Read-only is the only answer consistent with "exactly one authoritative
  copy".** Any path that lets a write follow a read creates a second place an
  entity's truth can be edited, which the whole inheritance and federation
  model depends on not existing.

## Alternatives Considered

| Option | Why rejected |
|--------|-------------|
| **Enforce read-only at the CLI only** | A Python caller reaching a write function directly (e.g. `lore.api.update_document`) would bypass it entirely — precisely the class of gap ADR-011 exists to close. |
| **Allow writes with an explicit `--force`** | Makes one repository's history depend on an agent running inside a different repository, with no way for a reviewer of the written-to repository to see why the change happened. |
| **Copy the entity down on read** | Produces two authoritative copies and a synchronisation problem the feature's own model — exactly one authoritative copy, in the project that authored it — rules out. |

## Consequences

**Easier:**
- A write path never needs its own boundary check: one function, called
  first, answers the question for every externally callable write function on
  a file-backed entity.
- A Python caller and a CLI invocation get the identical refusal, because both
  reach the same first statement.

**Harder:**
- Every new write function on a file-backed entity must remember to call
  `reject_foreign` as its first statement — the rule does not propagate
  automatically to a function that omits it.
- `--project` being rejected on every write command means a write against a
  known-foreign id fails with a usage error before the write function's own
  `ForeignEntityError` message is ever reached, so the two failure surfaces
  (a rejected flag vs. a rejected id) must both read as read-only to an agent
  encountering either.

## Constraints Imposed

1. **`projects.reject_foreign(entity_id)` is the first statement of every
   externally callable write function on a file-backed entity.** A write
   function that reaches its body before calling it is a defect.
2. **`--project` is accepted on read commands only.** A write, quest, or
   mission command rejects it at exit 2, regardless of the value passed.
3. **No process this ADR governs writes outside its own project's `.lore/`
   directory.** Introducing a push, copy, or sync between projects requires
   amending this ADR, not adding an exception beside it.

## Status History

| Date | Status | Note |
|------|--------|------|
| 2026-09-02 | accepted | Recorded alongside `projects.reject_foreign`, called as the first statement of every write function on a file-backed entity, `frontmatter_edit.update_frontmatter_fields` included. |
