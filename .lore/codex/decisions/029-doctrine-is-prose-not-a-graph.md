---
id: decisions-029-doctrine-is-prose-not-a-graph
title: "ADR-029: A doctrine is prose for an orchestrator, not a graph Lore parses"
summary: >
  ADR recording that a doctrine carries no machine-readable workflow structure.
  Lore reads a design document's frontmatter for identity and a mission file's
  frontmatter for its index entry, and treats every body as an opaque string.
  Step ordering, step type, phases and dependencies are decided by the
  orchestrator from the design prose.
binds:
  - src/lore/doctrine.py
related:
  - decisions-001-dumb-infrastructure
  - decisions-030-knight-entity-removed
  - conceptual-entities-doctrine
  - ref-lore_doctrine-module
---

# ADR-029: A doctrine is prose for an orchestrator, not a graph Lore parses

## Context

A doctrine carried a machine-readable step graph in `<name>.yaml` — step ids,
`type`, `priority`, `knight`, `needs`, `notes` — and `doctrine.py` validated it,
detected cycles in it and normalised it, while ADR-001 said Lore does not
orchestrate. Nothing consumed the graph: `lore doctrine show` printed the YAML
verbatim and an orchestrator read the prose to decide the order anyway. The
validation machinery was a contract Lore enforced on a structure Lore never
used.

## Decision

A doctrine carries no machine-readable workflow structure. Lore reads a
doctrine's frontmatter for identity (`id`, `title`, `summary`) and a mission
file's frontmatter for its index entry, and treats every body as an opaque
string. Step ordering, step type, phases and dependencies are decided by the
orchestrator from the design prose.

`_validate_steps`, `_check_cycles`, `_normalize`, `load_doctrine`,
`validate_doctrine_content`, `scaffold_doctrine`, `Doctrine`, `DoctrineStep`
and the `doctrine-yaml` schema are deleted.

## Rationale

- **Validating a structure nothing reads is enforcement without a consumer.**
  Cycle detection over a graph no code traverses buys a guarantee no caller
  depends on, and charges every doctrine author for it.
- **ADR-001 already draws the line.** Lore stores and answers queries; it does
  not interpret or orchestrate. A parsed step graph is the shape of a thing
  Lore would have to interpret to justify parsing.
- **An orchestrator that can read prose can read an ordered list in prose.**
  The reader of a doctrine is an agent. Handing it a table it can read costs
  nothing a parsed structure would have bought.

## Alternatives Considered

| Option | Why rejected |
|--------|-------------|
| **Keep a reduced YAML carrying ordering only** | Any parsed structure re-opens "what does Lore do with it", and an orchestrator that can read prose can read an ordered list in prose. |
| **Move cycle detection into `lore health`** | There is no graph left to have a cycle in; relocating the code would preserve a concept this decision exists to delete. |
| **Keep `Doctrine`/`DoctrineStep` in `models.__all__` as deprecated shells** | A dataclass describing a structure that cannot be produced is a trap for Realm, and no compatibility shim ships. |

## Consequences

**Easier:**
- A doctrine author writes one design document and one file per mission, with
  no second machine-readable representation to keep in step.
- `doctrine.py` has no validation pipeline over workflow structure to maintain,
  and no normalisation pass whose output a caller must anticipate.

**Harder:**
- Nothing checks that the design table and the `missions/` directory agree. A
  mission listed in the table with no file, or a file with no row, is found by
  reading, not by `lore health`.
- An orchestrator that wants ordering must read and understand prose rather
  than sort a list, which makes the design document's table a load-bearing
  convention rather than a validated schema.

## Constraints Imposed

1. **Nothing in `doctrine.py` parses, interprets or executes a mission body.**
   `read_doctrine` reads frontmatter for the index and returns each body as an
   opaque string.
2. **No file in a doctrine carries step order, step type, phase or
   dependencies as a machine-readable field.** Reintroducing one requires
   amending this ADR.
3. **`lore doctrine show` stays a single call returning design *and* mission
   index.** No second command lists a doctrine's missions.

## Status History

| Date | Status | Note |
|------|--------|------|
| 2026-09-16 | accepted | Recorded alongside the rewrite of `doctrine.py` onto the directory model. |
