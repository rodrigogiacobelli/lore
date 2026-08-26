---
id: interactive-init-us-006
title: US-006 — The machinery and workflow families
summary: Five new-* scaffolding skills become update-* skills that create or edit as
  the request requires, lore-update becomes sync-codex-guide with its scope narrowed
  to the codex guide, and start-quest and inquest gain access-mode blocks — eight
  skills, all six retired directories removed from the package.
type: user-story
related:
- interactive-init-prd
- interactive-init-tech-spec
- tech-arch-skill-catalogue
- decisions-006-no-seed-content-tests
- decisions-018-overlays-are-path-discovered-config
- conceptual-workflows-init-interactive
---

# US-006 — The machinery and workflow families

## Metadata

- **ID:** US-006
- **Status:** final
- **Epic:** _Rendering the Skills_
- **Author:** Tech Lead — Tech Planning
- **Date:** 2026-08-25
- **PRD:** `lore codex show interactive-init-prd`
- **Tech Spec:** `lore codex show interactive-init-tech-spec`

---

## Story

As _an AI coding agent asked to change an existing doctrine_, I want _one skill that creates or edits a doctrine depending on what I ask for_, so that _a skill named `new-doctrine` stops being the only route to an edit_.

## Context

FR-24 states the machinery family's rule: "an agent authors a doctrine, knight, watcher, artifact, or custom schema through the corresponding `update-` skill, which creates or edits as the request requires." Today those five skills are named `new-*` and read as create-only, which is why an edit request routes badly.

The workflow family keeps `start-quest` and `inquest` and gains `sync-codex-guide`, renamed from `lore-update` with its scope narrowed. Tech Spec §7.1's ledger gives the reason verbatim: "renamed; agent-file half replaced by the CLAUDE.md marker block". The old `lore-update` skill reconciled both `.lore/codex/CODEX.md` and the project's agent instruction file against freshly seeded templates; the instruction file is now written by Lore between markers (FR-15), so only the codex-guide half remains a skill's job.

`start-quest` and `inquest` are not renamed but are not untouched either: both are rewritten with `<!-- lore:access ... -->` blocks so the access mode reaches them like every other skill (FR-19).

One name correction rides along: `decisions-018-overlays-are-path-discovered-config` names `new-custom-schema` twice as the authoring path for an overlay. That is a codex edit owned by the phase-5 codex-apply mission, not by this story — it is named here so the rename is not shipped with a dangling reference.

---

## Acceptance Criteria

### E2E Scenarios

_This story has no CLI surface of its own: every scenario below calls a `lore.*` function directly, so all of them are written in `tests/unit/` (`technical-test-guidelines` §2, §8). See Test File Locations._

#### Scenario 1: The shipped tree holds exactly ten skills

**Given** the shipped tree at `src/lore/defaults/skills/`
**When** a test lists its directories
**Then** there are exactly ten, each holds a `SKILL.md`, and the set equals the catalogue's `skills[].id` set in both directions

#### Scenario 2: The five machinery skills carry their new names

**Given** the shipped tree
**When** a test lists the directories whose catalogue family is `machinery`
**Then** the set is exactly `update-doctrine`, `update-knight`, `update-watcher`, `update-artifact`, `update-custom-schema`, none of `new-doctrine`, `new-knight`, `new-watcher`, `new-artifact`, `new-custom-schema` exists, and each of those five ids appears in the catalogue's `retired` map with the matching `update-` successor as `into`

#### Scenario 3: The workflow family is start-quest, inquest and sync-codex-guide

**Given** the shipped tree
**When** a test lists the directories whose catalogue family is `workflow`
**Then** the set is exactly `start-quest`, `inquest`, `sync-codex-guide`; `lore-update/` no longer exists; and `retired["lore-update"].into` is `sync-codex-guide`

#### Scenario 4: Every machinery and workflow skill renders in both access modes

**Given** the eight `SKILL.md` files in these two families
**When** each is passed through `skills.render` once per `AccessMode`
**Then** no call raises, neither rendering contains `<!-- lore:access`, and for each file the two renderings differ

### Unit Test Scenarios

- [ ] `src/lore/defaults/skills/`: exactly ten directories; each holds a `SKILL.md`
- [ ] each of the eight `SKILL.md` files in these families: frontmatter parses; `name` equals its directory name; `description` is non-empty
- [ ] catalogue cross-check: `skills_in_families(("machinery",))` returns the five `update-*` ids sorted; `skills_in_families(("workflow",))` returns `("inquest", "start-quest", "sync-codex-guide")`
- [ ] catalogue cross-check: every `retired` key resolves to an `into` that is a current skill id, for all thirteen rows
- [ ] `lore.skills.render`: each of the eight files is block-well-formed — every region terminated and naming `cli` or `native`
- [ ] `src/lore/defaults/skills/`: no directory named `new-doctrine`, `new-knight`, `new-watcher`, `new-artifact`, `new-custom-schema` or `lore-update` exists

---

## Out of Scope

- The memory family — US-005.
- The renderer — US-004.
- Correcting the two `new-custom-schema` references in `decisions-018-overlays-are-path-discovered-config` — owned by the phase-5 codex-apply mission (`lore show q-3c9c/m-d053`), which amends the ADR body in place with no Status History row, because a name correction is not a decision change.
- Removing retired skills from a *user's* project — US-009 and US-010.
- Any assertion about the wording of the authored prose (ADR-006).

---

## References

- PRD: `lore codex show interactive-init-prd` FR-20, FR-24
- Tech Spec: `lore codex show interactive-init-tech-spec` §7.1, §12, §13, §14.3
- `lore codex show decisions-006-no-seed-content-tests`
- `lore codex show decisions-018-overlays-are-path-discovered-config`

---

## Tech Notes

### Implementation Approach

- **Files to create (by renaming and rewriting the existing body):**
  - `src/lore/defaults/skills/update-doctrine/SKILL.md` — from `new-doctrine/`
  - `src/lore/defaults/skills/update-knight/SKILL.md` — from `new-knight/`
  - `src/lore/defaults/skills/update-watcher/SKILL.md` — from `new-watcher/`
  - `src/lore/defaults/skills/update-artifact/SKILL.md` — from `new-artifact/`
  - `src/lore/defaults/skills/update-custom-schema/SKILL.md` — from `new-custom-schema/`
  - `src/lore/defaults/skills/sync-codex-guide/SKILL.md` — from `lore-update/`, scope narrowed to reconciling `.lore/codex/CODEX.md` against the freshly seeded template; the agent-instruction-file half is dropped because Lore now writes that file's Lore section between markers (US-012).
- **Files to modify:**
  - `src/lore/defaults/skills/start-quest/SKILL.md` — add `<!-- lore:access ... -->` blocks around its local-file command layer.
  - `src/lore/defaults/skills/inquest/SKILL.md` — same.
- **Files to delete:** `new-doctrine/`, `new-knight/`, `new-watcher/`, `new-artifact/`, `new-custom-schema/`, `lore-update/`.
- **Schema changes:** none.
- **Dependencies:** US-003 (catalogue rows), US-004 (renderer), US-005 (the other half of the ten-directory assertion — Scenario 1 goes green only when both ship).

Each `update-*` body must state, in its opening lines, that it creates **or** edits depending on the request — that is the behaviour FR-24 buys and the reason for the rename. Frontmatter `name` must match the new directory name, because `lore health --scope skills` (US-021) reports a `SKILL.md` whose frontmatter has no `name`.

Every `update-*` skill still reaches its entity through the Lore CLI in **both** access modes: Tech Spec §7.3 keeps artifacts, knights, doctrines and watchers CLI-only, because `lore doctrine show` runs normalisation, step validation and cycle detection, and every one of the four hides a `default/`-versus-flat split, slash-derived groups and `.deleted` soft-delete naming. Their access blocks therefore cover only codex, rite and glossary reads the skill performs along the way.

### Test File Locations

| Type | Path | Notes |
|------|------|-------|
| Unit | `tests/unit/test_skills.py` — extended | **Every scenario above is a unit test.** All four read the shipped package tree and invoke no CLI (`technical-test-guidelines` §2, §8) |
| Unit | `tests/unit/test_skills.py` — extended | Per-file frontmatter and family-membership checks |

### Test Stubs

```python
# E2E — Scenario 1: The shipped tree holds exactly ten skills
# Exercises: lore codex show conceptual-workflows-init-interactive — The Prompts, prompt 3 (skill families)
def test_shipped_tree_holds_exactly_ten_skills_matching_the_catalogue():
    pass


# E2E — Scenario 2: The five machinery skills carry their new names
# Exercises: lore codex show conceptual-workflows-init-reconcile — Removals (the ledger reason); ledger format in tech-arch-skill-catalogue — The Catalogue
def test_machinery_family_renamed_and_old_names_retired():
    pass


# E2E — Scenario 3: The workflow family is start-quest, inquest and sync-codex-guide
# Exercises: lore codex show conceptual-workflows-init-reconcile — Removals (the ledger reason); ledger format in tech-arch-skill-catalogue — The Catalogue
def test_workflow_family_membership_and_lore_update_retired():
    pass


# E2E — Scenario 4: Every machinery and workflow skill renders in both access modes
# Exercises: lore codex show conceptual-workflows-init-interactive — The Prompts, prompt 2 (access mode)
def test_machinery_and_workflow_skills_render_in_both_modes():
    pass


# Unit — ten directories, each with a SKILL.md
# Exercises: lore codex show conceptual-workflows-init-interactive — The Prompts, prompt 3 (skill families)
def test_ten_directories_each_with_skill_md():
    pass


# Unit — frontmatter name matches directory
# Exercises: lore codex show conceptual-workflows-init-interactive — The Prompts, prompt 3 (skill families)
def test_frontmatter_name_matches_directory_for_every_skill():
    pass


# Unit — family membership for machinery and workflow
# Exercises: lore codex show conceptual-workflows-init-interactive — The Prompts, prompt 3 (skill families)
def test_machinery_and_workflow_membership():
    pass


# Unit — every retired row resolves to a current successor
# Exercises: lore codex show conceptual-workflows-init-reconcile — Removals (the ledger reason); ledger format in tech-arch-skill-catalogue — The Catalogue
def test_all_thirteen_retired_rows_resolve_to_current_ids():
    pass


# Unit — block well-formedness across the eight files
# Exercises: lore codex show conceptual-workflows-init-interactive — The Prompts, prompt 2 (access mode)
def test_machinery_and_workflow_access_blocks_well_formed():
    pass


# Unit — the six old directories are gone
# Exercises: lore codex show conceptual-workflows-init-reconcile — Removals (the ledger reason); ledger format in tech-arch-skill-catalogue — The Catalogue
def test_renamed_directories_no_longer_shipped():
    pass
```

### Complexity Estimate

**M** — six renames with a real behavioural rewrite each (create-or-edit rather than create), one scope narrowing, and two files gaining access blocks; substantial authoring, but every file starts from an existing body.

### Standards References

- `lore codex show decisions-006-no-seed-content-tests`
- `lore codex show decisions-006-id-references` — why `update-*` skills stay on the CLI in both modes
- `lore codex show technical-test-guidelines`
