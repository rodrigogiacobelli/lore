---
id: interactive-init-us-011
title: US-011 — Skills install only where the selected agent reads them
summary: The desired-file set is enumerated from the answers — every selected skill
  rendered in the chosen access mode and placed in each selected agent's native skills
  directory, or in .lore/skills/ for an agent that has none, with each copy tracked
  independently so deselecting one agent removes only its files.
type: user-story
related:
- interactive-init-prd
- interactive-init-tech-spec
- tech-arch-skill-catalogue
- tech-arch-initialized-project-structure
- conceptual-workflows-init-interactive
---

# US-011 — Skills install only where the selected agent reads them

## Metadata

- **ID:** US-011
- **Status:** final
- **Epic:** _Plan and Apply Core_
- **Author:** Tech Lead — Tech Planning
- **Date:** 2026-08-25
- **PRD:** `lore codex show interactive-init-prd`
- **Tech Spec:** `lore codex show interactive-init-tech-spec`

---

## Story

As _a developer working in Claude Code_, I want _the seeded skills to land in `.claude/skills/`_, so that _my agent finds them without my having to copy a directory_.

## Context

This is the manual step the PRD's headline metric removes: "Manual steps between `lore init` and a usable skill in Claude Code — baseline 1 (copy `.lore/skills/` into `.claude/skills/`), target 0."

FR-14 states the rule in two halves: an agent with a native skills directory receives the skills there; an agent with none receives them in `.lore/skills/` plus an instruction-file pointer to that directory. Tech Spec §7.5 turns it into a four-row table:

| Selection | Skills land at |
|---|---|
| An agent with a `skills_dir` (today: Claude Code) | that directory |
| An agent with `skills_dir: null` | `.lore/skills/` |
| Several agents, at least one with a `skills_dir` | each such directory, plus `.lore/skills/` when at least one selected agent lacks one |
| `none`, or no agent at all | `.lore/skills/` |

Installing into two directories for a project using both Claude Code and an `AGENTS.md` agent costs duplicated bytes and buys a working setup for both; the manifest tracks each copy independently, so deselecting one agent removes only its copy.

This story produces the `desired` set that US-009's reconciliation consumes: a mapping from repo-root-relative POSIX path to the rendered bytes the installed Lore release would write, given the answers.

---

## Acceptance Criteria

### E2E Scenarios

_This story has no CLI surface of its own: every scenario below calls a `lore.*` function directly, so all of them are written in `tests/unit/` (`technical-test-guidelines` §2, §8). See Test File Locations._

#### Scenario 1: A Claude Code project gets its skills under `.claude/skills/`

**Given** answers with `agents=("claude",)`, `access_mode=native`, `skill_families=("memory", "workflow")`
**When** the desired set is enumerated
**Then** it contains `.claude/skills/<id>/SKILL.md` for each of the five selected skills, plus `.claude/skills/store-memory/references/{codex-doc,rite,source}.md`, and contains no path under `.lore/skills/`

#### Scenario 2: An agent with no native skills directory gets `.lore/skills/`

**Given** answers with `agents=("agents-md",)`
**When** the desired set is enumerated
**Then** every skill path sits under `.lore/skills/`, and no path sits under any agent-specific directory

#### Scenario 3: Two agents, two copies

**Given** answers with `agents=("claude", "agents-md")`
**When** the desired set is enumerated
**Then** each selected skill appears twice — once under `.claude/skills/` and once under `.lore/skills/` — with identical rendered bytes, and each path is a separate entry

#### Scenario 4: `none` and no-agent both land in `.lore/skills/`

**Given** answers with `agents=("none",)`, and separately with `agents=()`
**When** the desired set is enumerated for each
**Then** both produce skill paths under `.lore/skills/` only, and neither produces an instruction-file entry outside `.lore/`

#### Scenario 5: The access mode reaches every rendered file

**Given** two enumerations differing only in `access_mode`
**When** both desired sets are produced
**Then** the path sets are identical, the rendered bytes for each `SKILL.md` differ between the two, and no rendered file contains the substring `<!-- lore:access`

#### Scenario 6: An empty family selection installs no skill

**Given** answers with `skill_families=()`
**When** the desired set is enumerated
**Then** it contains no skill path at all, while `.lore/LORE-AGENT.md` is still present in the set

### Unit Test Scenarios

- [ ] `lore.skills.desired_files`: returns a mapping keyed by repo-root-relative POSIX path; values carry the rendered bytes, the `kind` (`"owned"`), and the `source` token `skill:<id>`
- [ ] `lore.skills.desired_files`: `store-memory`'s three declared reference files are included and carry the same `source` token as its `SKILL.md`
- [ ] `lore.skills.desired_files`: reference files are **not** passed through the access-mode renderer only if they contain no blocks — the implementer asserts that every packaged file goes through `render` exactly once, blocks or not
- [ ] `lore.skills.install_roots`: given the selected `AgentTarget` tuple, returns the directories skills install into, per Tech Spec §7.5's four rows, deduplicated and sorted
- [ ] `lore.skills.install_roots`: `("claude",)` → `(".claude/skills",)`; `("agents-md",)` → `(".lore/skills",)`; `("claude", "agents-md")` → both; `("none",)` and `()` → `(".lore/skills",)`
- [ ] `lore.skills.desired_files`: deterministic — two calls with the same answers produce identical bytes for every path
- [ ] `lore.skills.desired_files`: paths use `/` on every platform
- [ ] `lore.paths.skills_dir`: returns `<root>/.lore/skills`

---

## Out of Scope

- The instruction-file and gitignore entries in the desired set — US-012.
- Classifying desired against recorded — US-009.
- Writing anything to disk — US-015.
- Resolving which agents and families were chosen — US-014.

---

## References

- PRD: `lore codex show interactive-init-prd` FR-14, FR-16, FR-17, FR-19
- Tech Spec: `lore codex show interactive-init-tech-spec` §7.5, §7.2, §6.4
- `lore codex show tech-arch-skill-catalogue`
- `lore codex show tech-arch-initialized-project-structure`

---

## Tech Notes

### Implementation Approach

- **Files to modify:**
  - `src/lore/skills.py` — add `install_roots(targets: tuple[AgentTarget, ...]) -> tuple[str, ...]` implementing Tech Spec §7.5, and `desired_files(*, targets, skill_families, access_mode) -> dict[str, DesiredFile]` reading each selected skill's packaged files through `importlib.resources`, passing each through `render` (US-004), and keying by repo-root-relative POSIX path.
  - `src/lore/paths.py` — add `skills_dir(root: Path) -> Path` returning `root / ".lore" / "skills"`, beside `rites_dir` at `src/lore/paths.py:40`.
- **Files to create:** none.
- **Schema changes:** none.
- **Dependencies:** US-002 (`AgentTarget` rows carry `skills_dir`), US-003 (`skills_in_families`), US-004 (`render`), US-005 and US-006 (the packaged files being read).

`DesiredFile` is a small internal record (path, bytes, kind, source) local to `skills.py`; it is not a public API type and does not belong in `initplan.py`, which holds only what `lore.api` re-exports. The reconciler receives the mapping and produces `PlannedFile` values from it.

`_copy_defaults_tree("skills", lore_dir / "skills", label="skills")` at `src/lore/init.py:192` is the current unconditional copy of the whole skills tree into `.lore/skills/`. It is replaced by this enumeration; the removal itself lands in US-015 where `apply_init` takes over the write sequence.

### Test File Locations

| Type | Path | Notes |
|------|------|-------|
| Unit | `tests/unit/test_skills.py` — extended | **Every scenario above is a unit test.** All six call `skills.desired_files` / `skills.install_roots` directly and write nothing (`technical-test-guidelines` §2, §8). Placement as a user sees it — skills present under `.claude/skills/` after a run — is asserted in US-019 Scenario 1 |
| Unit | `tests/unit/test_skills.py` — extended | `install_roots` and `desired_files` |
| Unit | `tests/unit/test_paths.py` — extended | `skills_dir` |

### Test Stubs

```python
# E2E — Scenario 1: A Claude Code project gets its skills under .claude/skills/
# Exercises: lore codex show conceptual-workflows-init-interactive — The Prompts, prompt 1 (agents)
def test_claude_selection_places_skills_under_claude_skills():
    pass


# E2E — Scenario 2: An agent with no native skills directory gets .lore/skills/
# Exercises: lore codex show conceptual-workflows-init-interactive — The Prompts, prompt 1 (agents)
def test_agents_md_selection_places_skills_under_dot_lore_skills():
    pass


# E2E — Scenario 3: Two agents, two copies
# Exercises: lore codex show conceptual-workflows-init-interactive — The Prompts, prompt 1 (agents)
def test_two_agents_produce_two_independently_tracked_copies():
    pass


# E2E — Scenario 4: `none` and no-agent both land in .lore/skills/
# Exercises: lore codex show conceptual-workflows-init-interactive — The Prompts, prompt 1 (agents)
def test_none_and_no_agent_both_use_dot_lore_skills():
    pass


# E2E — Scenario 5: The access mode reaches every rendered file
# Exercises: lore codex show conceptual-workflows-init-interactive — The Prompts, prompt 2 (access mode)
def test_access_mode_changes_bytes_not_paths():
    pass


# E2E — Scenario 6: An empty family selection installs no skill
# Exercises: lore codex show conceptual-workflows-init-interactive — The Prompts, prompt 3 (skill families)
def test_empty_family_selection_yields_no_skill_paths():
    pass


# Unit — desired_files key shape and source token
# Exercises: lore codex show conceptual-workflows-init-interactive — The Prompts, prompt 1 (agents)
def test_desired_files_keys_are_posix_and_carry_skill_source_tokens():
    pass


# Unit — reference files ride along
# Exercises: lore codex show conceptual-workflows-init-interactive — The Prompts, prompt 1 (agents)
def test_store_memory_reference_files_included():
    pass


# Unit — every packaged file goes through render exactly once
# Exercises: lore codex show conceptual-workflows-init-interactive — The Prompts, prompt 2 (access mode)
def test_every_packaged_file_is_rendered_once():
    pass


# Unit — install_roots, four rows
# Exercises: lore codex show conceptual-workflows-init-interactive — The Prompts, prompt 1 (agents)
def test_install_roots_covers_the_four_placement_rows():
    pass


# Unit — determinism
# Exercises: lore codex show conceptual-workflows-init-interactive — The Prompts, prompt 1 (agents)
def test_desired_files_is_deterministic():
    pass


# Unit — POSIX keys on every platform
# Exercises: lore codex show conceptual-workflows-init-interactive — The Prompts, prompt 1 (agents)
def test_desired_file_keys_use_forward_slashes():
    pass


# Unit — paths.skills_dir
# Exercises: lore codex show conceptual-workflows-init-interactive — The Prompts, prompt 1 (agents)
def test_skills_dir_points_into_dot_lore():
    pass
```

### Complexity Estimate

**M** — a four-row placement table plus a package-data walk that renders each file; no I/O against the project and no branching beyond the table.

### Standards References

- `lore codex show tech-arch-skill-catalogue`
- `lore codex show standards-single-responsibility` — enumeration decides *what*, `apply_init` decides *when*
- `lore codex show technical-test-guidelines`
