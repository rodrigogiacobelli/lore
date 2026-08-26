---
id: interactive-init-us-005
title: US-005 — The memory family — one skill to store knowledge, one to retrieve it
summary: Seven seeded skills collapse into two — store-memory (with three reference
  files, covering codex docs, rites, and outside-authored sources) and retrieve-memory
  (consulting both the codex and the rites) — each authored once with access-mode
  blocks and each declared in the catalogue.
type: user-story
related:
- interactive-init-prd
- interactive-init-tech-spec
- tech-arch-skill-catalogue
- decisions-006-id-references
- decisions-006-no-seed-content-tests
- conceptual-workflows-init-interactive
---

# US-005 — The memory family — one skill to store knowledge, one to retrieve it

## Metadata

- **ID:** US-005
- **Status:** final
- **Epic:** _Rendering the Skills_
- **Author:** Tech Lead — Tech Planning
- **Date:** 2026-08-25
- **PRD:** `lore codex show interactive-init-prd`
- **Tech Spec:** `lore codex show interactive-init-tech-spec`

---

## Story

As _an AI coding agent working in a Lore project_, I want _one skill for recording knowledge into project memory and one for answering a question from it_, so that _I stop having to choose between four near-identical authoring skills and three near-identical exploration skills before I can do either job_.

## Context

FR-21 through FR-23 define the memory family. `store-memory` records knowledge "whether that knowledge comes from the conversation or from an upstream artifact, and whether it creates, edits, or deletes" — absorbing `update-codex`, `new-rite`, `ingest-source` and `refresh-source`. `retrieve-memory` answers a question from project memory, "which consults both the codex and the rites" — absorbing `explore-codex`, `explore-rite` and `explore-codex-rite`.

FR-22 is the boundary that keeps `store-memory` from becoming an ingestion pipeline for everything an agent reads: a source snapshot is written **only** when the knowledge arrives as an artifact authored outside the project and outside the conversation, and identifiable well enough to be re-fetched and compared later. Tech Spec §7.1 puts that rule in `store-memory/SKILL.md` rather than in the catalogue, because a rule an agent must apply lives where the agent reads it.

`store-memory` carries three reference files — `references/codex-doc.md`, `references/rite.md`, `references/source.md` — declared in the catalogue's `references:` list, so the enumerator installs them alongside the skill.

`decisions-006-no-seed-content-tests` decides how this story is proved: existence, parseability and structural completeness. No test may assert a sentence of the authored prose.

---

## Acceptance Criteria

### E2E Scenarios

_This story has no CLI surface of its own: every scenario below calls a `lore.*` function directly, so all of them are written in `tests/unit/` (`technical-test-guidelines` §2, §8). See Test File Locations._

#### Scenario 1: The memory family exists on disk exactly as the catalogue declares it

**Given** the shipped tree at `src/lore/defaults/skills/`
**When** a test lists its directories
**Then** `store-memory/` and `retrieve-memory/` are present, each holds a `SKILL.md` that parses with a `name` and a non-empty `description` in frontmatter, and `store-memory/references/` holds exactly the three files the catalogue declares — `codex-doc.md`, `rite.md`, `source.md`

#### Scenario 2: The seven absorbed skills are gone

**Given** the shipped tree at `src/lore/defaults/skills/`
**When** a test lists its directories
**Then** none of `update-codex/`, `new-rite/`, `ingest-source/`, `refresh-source/`, `explore-codex/`, `explore-rite/`, `explore-codex-rite/` exists, and each of those seven ids appears in the catalogue's `retired` map with an `into` of `store-memory` or `retrieve-memory`

#### Scenario 3: Both skills render cleanly in both access modes

**Given** `store-memory/SKILL.md`, `retrieve-memory/SKILL.md` and the three reference files
**When** each is passed through `skills.render` once with `AccessMode.CLI` and once with `AccessMode.NATIVE`
**Then** no call raises, both renderings differ from each other for `SKILL.md`, and neither rendering contains the substring `<!-- lore:access`

#### Scenario 4: The graph commands survive both modes

**Given** `retrieve-memory/SKILL.md`
**When** it is rendered in each access mode
**Then** the substrings `lore codex map`, `lore codex chaos` and `lore impacts` appear in both renderings — this is FR-18's structural test, and it is a *presence of a command token*, not an assertion about authored prose

### Unit Test Scenarios

- [ ] `src/lore/defaults/skills/store-memory/SKILL.md`: frontmatter parses; `name` equals the directory name; `description` is a non-empty string
- [ ] `src/lore/defaults/skills/retrieve-memory/SKILL.md`: same three assertions
- [ ] `src/lore/defaults/skills/store-memory/references/`: contains exactly the files listed under the catalogue's `store-memory.references`, in both directions
- [ ] `src/lore/defaults/skills/`: no directory named by a catalogue `retired` key exists
- [ ] catalogue cross-check: every `retired` key whose `into` is `store-memory` or `retrieve-memory` names a directory that no longer exists, and the `into` target does
- [ ] `lore.skills.render`: each of the five memory-family files is well-formed — every `<!-- lore:access ... -->` region terminated and naming `cli` or `native`
- [ ] `lore.skills.skills_in_families(("memory",))`: returns exactly `("retrieve-memory", "store-memory")`

---

## Out of Scope

- The five machinery renames and the three workflow skills — US-006.
- The renderer itself — US-004.
- Where the rendered files land on disk — US-011.
- Removing the retired skills from a *user's* project — US-009 (reconciliation) and US-010 (legacy fallback); this story only removes them from the shipped package.
- Any assertion about the wording of the authored prose (ADR-006).

---

## References

- PRD: `lore codex show interactive-init-prd` FR-20, FR-21, FR-22, FR-23
- Tech Spec: `lore codex show interactive-init-tech-spec` §7.1, §7.2, §12, §14.3
- `lore codex show decisions-006-id-references` — which entity types agent-native mode may reach with its own tools, and which stay CLI-only in both modes
- `lore codex show decisions-006-no-seed-content-tests`

---

## Tech Notes

### Implementation Approach

- **Files to create:**
  - `src/lore/defaults/skills/store-memory/SKILL.md` — frontmatter `name: store-memory` plus a `description`; body covers creating, editing and deleting codex documents and rites, and carries the FR-22 ingestion boundary verbatim in prose. Command layer inside `<!-- lore:access cli -->` / `<!-- lore:access native -->` blocks; `lore codex map`, `lore codex chaos`, `lore impacts` and `lore health` authored **outside** any block.
  - `src/lore/defaults/skills/store-memory/references/codex-doc.md`
  - `src/lore/defaults/skills/store-memory/references/rite.md`
  - `src/lore/defaults/skills/store-memory/references/source.md`
  - `src/lore/defaults/skills/retrieve-memory/SKILL.md` — frontmatter `name: retrieve-memory` plus a `description`; body covers answering a question from the codex **and** the rites in one pass, with the same block convention.
- **Files to delete:** the seven absorbed directories under `src/lore/defaults/skills/` — `update-codex/`, `new-rite/`, `ingest-source/`, `refresh-source/`, `explore-codex/`, `explore-rite/`, `explore-codex-rite/`. Their content is the input for the two new skills; salvage it rather than rewriting from nothing.
- **Files to modify:** none in `src/lore/` code. The catalogue rows for these two skills ship in US-003; this story makes the two-way id/directory cross-check from US-003 pass for the memory half.
- **Schema changes:** none.
- **Dependencies:** US-003 (catalogue rows and the cross-check test), US-004 (the renderer that proves well-formedness).

Authoring guidance from Tech Spec §7.3 — what agent-native mode may cover, and what stays CLI-only in both modes:

| Surface | Native mode |
|---|---|
| Codex read and write, rites read and write, glossary read and write | own tools |
| `lore codex map`, `lore codex chaos`, `lore impacts` | CLI, always |
| Artifacts, knights, doctrines, watchers, quests, missions, board | CLI, always |
| `lore health` | CLI, always |

### Test File Locations

| Type | Path | Notes |
|------|------|-------|
| Unit | `tests/unit/test_skills.py` — extended | **Every scenario above is a unit test.** All four read the shipped package tree and invoke no CLI (`technical-test-guidelines` §2, §8) |
| Unit | `tests/unit/test_skills.py` — extended | Per-file frontmatter and reference-list checks |

### Test Stubs

```python
# E2E — Scenario 1: The memory family exists on disk exactly as the catalogue declares it
# Exercises: lore codex show conceptual-workflows-init-interactive — The Prompts, prompt 3 (skill families)
def test_memory_family_directories_and_references_present():
    # Given: the shipped defaults/skills tree
    # When: list directories and store-memory/references
    # Then: two directories, each with a parseable SKILL.md; exactly three reference files
    pass


# E2E — Scenario 2: The seven absorbed skills are gone
# Exercises: lore codex show conceptual-workflows-init-reconcile — Removals (the ledger reason); ledger format in tech-arch-skill-catalogue — The Catalogue
def test_absorbed_skill_directories_removed_and_recorded_as_retired():
    pass


# E2E — Scenario 3: Both skills render cleanly in both access modes
# Exercises: lore codex show conceptual-workflows-init-interactive — The Prompts, prompt 2 (access mode)
def test_memory_family_renders_in_both_modes_without_markers():
    pass


# E2E — Scenario 4: The graph commands survive both modes
# Exercises: lore codex show conceptual-workflows-init-interactive — The Prompts, prompt 2 (access mode)
def test_graph_commands_present_in_both_renderings():
    # Command tokens only: `lore codex map`, `lore codex chaos`, `lore impacts`
    pass


# Unit — store-memory frontmatter
# Exercises: lore codex show conceptual-workflows-init-interactive — The Prompts, prompt 3 (skill families)
def test_store_memory_frontmatter_has_name_and_description():
    pass


# Unit — retrieve-memory frontmatter
# Exercises: lore codex show conceptual-workflows-init-interactive — The Prompts, prompt 3 (skill families)
def test_retrieve_memory_frontmatter_has_name_and_description():
    pass


# Unit — declared references match disk in both directions
# Exercises: lore codex show conceptual-workflows-init-interactive — The Prompts, prompt 3 (skill families)
def test_store_memory_references_match_catalogue_both_ways():
    pass


# Unit — no retired directory survives in the package
# Exercises: lore codex show conceptual-workflows-init-reconcile — Removals (the ledger reason); ledger format in tech-arch-skill-catalogue — The Catalogue
def test_no_retired_directory_remains_in_the_shipped_tree():
    pass


# Unit — memory-family files are block-well-formed
# Exercises: lore codex show conceptual-workflows-init-interactive — The Prompts, prompt 2 (access mode)
def test_memory_family_access_blocks_well_formed():
    pass


# Unit — family membership
# Exercises: lore codex show conceptual-workflows-init-interactive — The Prompts, prompt 3 (skill families)
def test_memory_family_membership():
    # skills_in_families(("memory",)) == ("retrieve-memory", "store-memory")
    pass
```

### Complexity Estimate

**L** — two skills absorbing seven, three reference files, and the FR-22 ingestion boundary all authored from scratch; the code surface is nil but the authoring judgement is the largest single content deliverable in the feature.

### Standards References

- `lore codex show decisions-006-no-seed-content-tests` — structure only, never prose
- `lore codex show decisions-006-id-references` — the carve-out agent-native mode gets, and what it does not get
- `lore codex show decisions-020-codex-voice-is-enforced` — skills are not codex documents, but the same plainness serves them
- `lore codex show technical-test-guidelines`
