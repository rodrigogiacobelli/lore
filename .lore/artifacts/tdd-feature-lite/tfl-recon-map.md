---
id: tfl-recon-map
title: Recon Map
summary: >
  Template for the single recon document the `tdd-feature-lite` doctrine produces
  before architecture. One map, not two: relevant codex, the binding ADR and
  standards table with each rule stated in one line, the real code surface, the
  lane coverage call, and an explicit split between what the scout verified and
  what it inferred. The architect builds on this; every downstream step trusts it.
---

# Recon Map — {Feature Name}

**Author:** Recon
**Date:** {date}
**Feature:** _{one-line feature description}_
**Upstream PRD:** _{PRD codex ID, or "none — architect writes Part 1"}_

---

## 1. Relevant Codex

| ID | Title | Why relevant |
|----|-------|-------------|
| `{codex-id}` | {title} | _{Specific. "Defines the frontmatter schema this feature extends" is good; "related to this feature" is not.}_ |

> One row per document. Borderline goes in — the architect can ignore a row it
> cannot use, but it cannot find a row that is missing.

---

## 2. Binding Decisions and Standards

Every ADR (`decisions/`), standards doc (`standards/`), and contract doc that
governs a file this feature will touch. **State the rule, not just the id** — the
architect must be able to obey it without opening the ADR.

| ID | The rule, in one line | What it governs here |
|----|----------------------|---------------------|
| `decisions-011-api-parity-with-cli` | _{e.g. "No validation, business logic, or post-processing may live only in the CLI layer — every rule has a core-function home."}_ | _{which file(s) in scope}_ |
| `{decisions-...}` | _{one line}_ | _{scope}_ |
| `{standards-...}` | _{one line}_ | _{scope}_ |

### Apparent Conflicts

Places where the request, as written, looks like it contradicts one of the rows above.
Do not resolve them — name them. The architect writes them into the spec's conflicts
table and the human gate decides.

| Rule id | What the request seems to want | Why that reads as a conflict |
|---------|-------------------------------|------------------------------|
| `{id}` | _{…}_ | _{…}_ |

_None found_ is a valid entry — write it explicitly rather than leaving the table empty.

---

## 3. Code Surface

Real paths, verified against the working tree. For each existing file, run
`lore impacts <path>` and fold what it returns into section 2.

| Path | Lane | What is there now | Expected change |
|------|------|-------------------|-----------------|
| `src/lore/{module}.py` | foundation \| core \| surface | _{current responsibility}_ | new \| modified \| read-only reference |
| `tests/unit/test_{module}.py` | _{lane of the module it tests}_ | _{coverage that exists}_ | _{…}_ |

---

## 4. Lane Coverage

Which of the three dev lanes this feature actually touches. A lane with no row in
section 3 is skipped by the doctrine — say so here rather than leaving the
architect to guess.

| Lane | In scope? | Why |
|------|-----------|-----|
| foundation — leaf modules with zero or near-zero `lore.*` imports | yes \| no | _{…}_ |
| core — storage, entity modules, and the business logic behind every command | yes \| no | _{…}_ |
| surface — `api.py`, `cli.py`, `prompts.py` | yes \| no | _{…}_ |

---

## 5. Verified vs Inferred

The single most important section. A downstream step that builds on an unverified
claim inherits the error silently.

**Verified** — read in a file or observed from a command, with what proved it:

- _{claim}_ — proved by `{command run, or file:line read}`

**Inferred** — believed from naming, convention, or partial reading, not confirmed:

- _{claim}_ — _{what would confirm it}_

**Unknown** — questions recon could not answer and the architect must resolve:

- _{question}_

---

## 6. Notes

_{Gaps in the codex, stale docs found, terminology collisions with
`lore glossary list`. Observations, not instructions.}_
