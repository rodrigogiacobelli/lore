---
id: interactive-init-us-007
title: US-007 — The agent instruction text is rendered, not copied
summary: LORE-AGENT.md stops being a file lore init copies verbatim and becomes a
  packaged template whose access-mode blocks resolve and whose skills table is
  generated from the catalogue and the chosen install location, producing one
  rendered text that lands both at .lore/LORE-AGENT.md and inside each agent's file.
type: user-story
related:
- interactive-init-prd
- interactive-init-tech-spec
- tech-arch-agents-md
- tech-arch-initialized-project-structure
- standards-dry
- decisions-006-no-seed-content-tests
- conceptual-workflows-lore-init
---

# US-007 — The agent instruction text is rendered, not copied

## Metadata

- **ID:** US-007
- **Status:** final
- **Epic:** _Rendering the Skills_
- **Author:** Tech Lead — Tech Planning
- **Date:** 2026-08-25
- **PRD:** `lore codex show interactive-init-prd`
- **Tech Spec:** `lore codex show interactive-init-tech-spec`

---

## Story

As _a developer whose project installs five of the ten seeded skills into `.claude/skills/`_, I want _the instruction file my agent reads to list exactly those five and say where they are_, so that _my agent never invokes a skill the project does not have_.

## Context

`src/lore/defaults/docs/LORE-AGENT.md` currently carries a hand-maintained thirteen-row skills table (lines 166–182) naming `new-doctrine`, `new-knight`, `explore-codex`, `update-codex`, `lore-update` and seven others — every one of them retired by US-005 and US-006. Both context maps flagged the table as invalidated by the consolidation.

Tech Spec §7.4 fixes it by generating the table rather than maintaining it: the file becomes a packaged **template** producing one rendered text, with two generated regions — the `<!-- lore:access ... -->` blocks resolved per US-004, and a `<!-- lore:skills-table -->` … `<!-- lore:skills-table end -->` region replaced by a table of exactly the installed skills and their install path. The catalogue becomes the one place a skill's existence is recorded (`standards-dry`).

The rendered text lands in two kinds of place: `.lore/LORE-AGENT.md`, always written and manifest-tracked as `owned` — it is the canonical rendered text and the only artefact when no agent is selected, which is exactly today's behaviour and therefore the FR-9 parity anchor — and each selected agent's instruction file, the same text inside `<!-- lore:begin -->` … `<!-- lore:end -->` markers, manifest-tracked as `section`.

---

## Acceptance Criteria

### E2E Scenarios

#### Scenario 1: The skills table names exactly the installed skills

**Given** a render call for `agents=("claude",)`, `access_mode=native`, `skill_families=("memory", "workflow")`
**When** `init.render_agent_instructions(...)` produces the instruction text
**Then** the text contains a markdown table with one row per installed skill and no more — five rows for that family selection — each row naming the skill id and the path `.claude/skills/<id>/`, and the text contains neither `<!-- lore:skills-table` nor `<!-- lore:access`

#### Scenario 2: The install path follows the target

**Given** the same call with `agents=()` (no agent selected)
**When** the instruction text is produced
**Then** every table row names the path `.lore/skills/<id>/`

#### Scenario 3: The access mode reaches the instruction text

**Given** two render calls differing only in `access_mode`
**When** both texts are produced
**Then** they differ, and neither contains a `<!-- lore:access` marker

#### Scenario 4: A narrowed family selection narrows the table

**Given** a render call with `skill_families=("memory",)`
**When** the instruction text is produced
**Then** the table has exactly two rows, and no row names a skill from the machinery or workflow families

### Unit Test Scenarios

- [ ] `lore.init.render_agent_instructions`: returns `str`; the returned text has no `<!-- lore:skills-table` and no `<!-- lore:access` marker
- [ ] `lore.init._render_skills_table`: given a skill-id tuple and an install root, emits one markdown row per id in sorted order, and an empty selection emits a header-only table rather than raising
- [ ] `lore.init._render_skills_table`: the path column uses POSIX separators regardless of platform
- [ ] `lore.init.render_agent_instructions`: a template whose `<!-- lore:skills-table -->` region is unterminated raises `ValueError` naming the line
- [ ] `lore.init.render_agent_instructions`: called twice with identical arguments returns byte-identical text (determinism — the manifest hashes this)
- [ ] `src/lore/defaults/docs/LORE-AGENT.md`: contains exactly one `<!-- lore:skills-table -->` opener and one `<!-- lore:skills-table end -->` closer; every `<!-- lore:access ... -->` region is terminated (structural assertions only — ADR-006)
- [ ] `src/lore/defaults/docs/LORE-AGENT.md`: no hand-written skills table survives outside the generated region — asserted by the absence of any markdown table row naming a catalogue `retired` key
- [ ] `lore.paths.lore_agent_path`: returns `<root>/.lore/LORE-AGENT.md`

---

## Out of Scope

- Writing the rendered text into an agent's file between markers — US-012.
- Deciding which agents and families are selected — US-014.
- The `GETTING-STARTED.md` copy path, which stays a verbatim copy (Tech Spec §12).
- The repository's own `CLAUDE.md`, which is a project file and not seeded content.

---

## References

- PRD: `lore codex show interactive-init-prd` FR-9, FR-14, FR-15, FR-20
- Tech Spec: `lore codex show interactive-init-tech-spec` §7.4, §6.7, §12
- `lore codex show tech-arch-agents-md` — the rewritten instruction-file contract
- `lore codex show standards-dry`

---

## Tech Notes

### Implementation Approach

- **Files to modify:**
  - `src/lore/defaults/docs/LORE-AGENT.md` — replace the hand-maintained table at lines 166–182 with a `<!-- lore:skills-table -->` … `<!-- lore:skills-table end -->` region, and wrap the "Lore CLI commands" material in `<!-- lore:access cli -->` / `<!-- lore:access native -->` blocks. The business map identified this section as an access-mode layer like any other.
  - `src/lore/init.py` — `_copy_defaults_tree("docs", lore_dir, label="docs")` at `src/lore/init.py:180` currently copies both docs verbatim. Split it: `GETTING-STARTED.md` keeps the verbatim copy; `LORE-AGENT.md` goes through the new renderer. Add `render_agent_instructions(*, skill_ids, install_root, access_mode) -> str` and the private `_render_skills_table(skill_ids, install_root) -> str`.
  - `src/lore/paths.py` — add `lore_agent_path(root: Path) -> Path` returning `root / ".lore" / "LORE-AGENT.md"`, beside the existing `codex_md_path` at `src/lore/paths.py:60`.
- **Files to create:** none.
- **Schema changes:** none.
- **Dependencies:** US-003 (catalogue, for the skill ids and their descriptions), US-004 (`skills.render` for the access blocks), US-005 and US-006 (the ten skills whose frontmatter `description` fills the table's middle column).

The table's "What it does" column comes from each skill's own `SKILL.md` frontmatter `description`, read from the package — that is the single authored home for the description (`standards-dry`, Tech Spec §7.1). Tests assert the column is *populated*, never what it says (ADR-006).

Determinism matters: the manifest hashes this rendered text as a `section` entry, so two calls with the same inputs must produce the same bytes. Sort the skill ids.

### Test File Locations

| Type | Path | Notes |
|------|------|-------|
| E2E | `tests/e2e/test_lore_init.py` — extended | Anchor `conceptual-workflows-lore-init`; `.lore/LORE-AGENT.md` is written on every run, agent or no agent |
| Unit | `tests/unit/test_lore_init.py` — extended | The renderer and the table builder |
| Unit | `tests/unit/test_paths.py` — extended | `lore_agent_path` |

### Test Stubs

```python
# E2E — Scenario 1: The skills table names exactly the installed skills
# Exercises: lore codex show conceptual-workflows-lore-init — LORE-AGENT.md rendering
def test_skills_table_rows_match_the_installed_selection():
    # Given: agents=("claude",), families=("memory","workflow")
    # When: render the instruction text
    # Then: five rows, each naming .claude/skills/<id>/; no generated-region markers survive
    pass


# E2E — Scenario 2: The install path follows the target
# Exercises: lore codex show conceptual-workflows-lore-init — LORE-AGENT.md rendering
def test_no_agent_selected_points_the_table_at_dot_lore_skills():
    pass


# E2E — Scenario 3: The access mode reaches the instruction text
# Exercises: lore codex show conceptual-workflows-lore-init — LORE-AGENT.md rendering
def test_instruction_text_differs_between_access_modes():
    pass


# E2E — Scenario 4: A narrowed family selection narrows the table
# Exercises: lore codex show conceptual-workflows-lore-init — LORE-AGENT.md rendering
def test_memory_only_selection_yields_a_two_row_table():
    pass


# Unit — render_agent_instructions leaves no markers
# Exercises: lore codex show conceptual-workflows-lore-init — LORE-AGENT.md rendering
def test_rendered_text_carries_no_generated_region_markers():
    pass


# Unit — _render_skills_table row shape and ordering
# Exercises: lore codex show conceptual-workflows-lore-init — LORE-AGENT.md rendering
def test_skills_table_rows_sorted_and_one_per_id():
    pass


# Unit — empty selection is a header-only table
# Exercises: lore codex show conceptual-workflows-lore-init — LORE-AGENT.md rendering
def test_empty_selection_renders_header_only():
    pass


# Unit — POSIX separators in the path column
# Exercises: lore codex show conceptual-workflows-lore-init — LORE-AGENT.md rendering
def test_table_paths_use_posix_separators():
    pass


# Unit — unterminated table region raises
# Exercises: lore codex show conceptual-workflows-lore-init — LORE-AGENT.md rendering
def test_unterminated_skills_table_region_raises_naming_the_line():
    pass


# Unit — determinism
# Exercises: lore codex show conceptual-workflows-lore-init — LORE-AGENT.md rendering
def test_two_identical_render_calls_are_byte_identical():
    pass


# Unit — the shipped template is structurally correct (ADR-006)
# Exercises: lore codex show conceptual-workflows-lore-init — LORE-AGENT.md rendering
def test_shipped_template_has_one_skills_table_region_and_terminated_access_blocks():
    pass


# Unit — no stale hand-written table survives
# Exercises: lore codex show conceptual-workflows-lore-init — LORE-AGENT.md rendering
def test_template_has_no_table_row_naming_a_retired_skill():
    pass


# Unit — paths.lore_agent_path
# Exercises: lore codex show conceptual-workflows-lore-init — project structure
def test_lore_agent_path_points_into_dot_lore():
    pass
```

### Complexity Estimate

**M** — one template rewrite plus a small deterministic table generator, wired into an `init.py` copy path that currently treats both docs identically.

### Standards References

- `lore codex show standards-dry` — the catalogue is the one record of a skill's existence
- `lore codex show decisions-006-no-seed-content-tests` — the table's content is never asserted, only its shape
- `lore codex show tech-arch-initialized-project-structure` — where `.lore/LORE-AGENT.md` sits
- `lore codex show technical-test-guidelines`
