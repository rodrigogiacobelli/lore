---
id: interactive-init-us-021
title: US-021 — lore health audits the installed skills
summary: A skills scope joins lore health, reading the install manifest and the packaged
  catalogue to report a recorded file that is missing, a file edited since install, a
  retired skill still on disk, a SKILL.md with no name in frontmatter, and an
  unparseable manifest — while a project with no manifest reports nothing.
type: user-story
related:
- interactive-init-prd
- interactive-init-tech-spec
- conceptual-workflows-health
- decisions-017-constrained-flags-use-click-choice
- decisions-021-health-reports-are-ephemeral-by-default
---

# US-021 — `lore health` audits the installed skills

## Metadata

- **ID:** US-021
- **Status:** final
- **Epic:** _Adjacent Corrections_
- **Author:** Tech Lead — Tech Planning
- **Date:** 2026-08-25
- **PRD:** `lore codex show interactive-init-prd`
- **Tech Spec:** `lore codex show interactive-init-tech-spec`

---

## Story

As _a maintainer auditing a Lore project_, I want _`lore health` to tell me when an installed skill has gone missing, been edited, or been retired_, so that _the one entity type `lore init` seeds without an audit surface stops being a blind spot_.

## Context

FR-37 closes a gap the PRD counts in its success table: "Entity types seeded by `lore init` with no `lore health` scope — baseline 1 (skills), target 0."

Tech Spec §10 adds `skills` to the `--scope` token set. Adding a token is explicitly non-breaking under ADR-017: the `click.Choice` mechanism, its wording and the exit-2 contract are untouched.

`health._check_skills(project_root)` reads `.lore/.install-manifest.json` and the packaged catalogue, and walks **only the paths the manifest names** — the same never-touch-what-Lore-did-not-install discipline reconciliation follows.

The severity split follows the existing convention: Lore claiming to have installed a file that is gone is a real inconsistency and flips exit 1; a user editing a skill is legitimate and warns.

**A missing manifest emits nothing.** `conceptual-workflows-health` records `scan_failed` for a checker whose directory is missing, but a project that predates the manifest is a legitimate state, exactly as an absent `.lore/custom-schemas/` is the zero-overlay baseline and an absent glossary is a valid empty glossary. Reporting an error would fail CI on every project that has not yet re-initialised.

---

## Acceptance Criteria

### E2E Scenarios

#### Scenario 1: A deleted installed skill is an error and exits 1

**Given** a project whose manifest records `.claude/skills/inquest/SKILL.md` and whose file has been deleted
**When** the caller runs `lore health --scope skills`
**Then** stdout carries `ERROR    skills  .claude/skills/inquest/SKILL.md  missing_skill_file: recorded in the install manifest but missing on disk` and exit is 1

#### Scenario 2: An edited installed skill is a warning

**Given** a project whose manifest records `.claude/skills/start-quest/SKILL.md` and whose bytes have since changed
**When** the caller runs `lore health --scope skills`
**Then** stdout carries `WARNING  skills  .claude/skills/start-quest/SKILL.md  modified_skill_file: edited since install; lore init will ask before overwriting` and, with no error present, exit is 0

#### Scenario 3: A retired skill still on disk is a warning naming its successor

**Given** a project whose manifest records a `new-doctrine` skill path that the current catalogue lists under `retired`
**When** the caller runs `lore health --scope skills`
**Then** stdout carries `WARNING  skills  new-doctrine  retired_skill_present: retired into update-doctrine; run lore init to reconcile`

#### Scenario 4: A `SKILL.md` with no `name` is an error

**Given** a project whose manifest records a `SKILL.md` whose frontmatter has no `name`
**When** the caller runs `lore health --scope skills`
**Then** stdout carries `ERROR    skills  <path>  missing_skill_frontmatter: SKILL.md frontmatter is missing 'name'` and exit is 1

#### Scenario 5: An unparseable manifest is one error

**Given** a project whose `.lore/.install-manifest.json` exists and does not parse
**When** the caller runs `lore health --scope skills`
**Then** exactly one issue is reported — `ERROR    skills  <manifest-path>  skills_scan_failed: <reason>` — and exit is 1

#### Scenario 6: A project with no manifest reports nothing

**Given** a project with no `.lore/.install-manifest.json`
**When** the caller runs `lore health --scope skills`
**Then** zero issues are reported for the skills scope and exit is 0

#### Scenario 7: The scope is a first-class token everywhere

**Given** any initialised project
**When** the caller runs `lore health --scope skills`, then `lore health --scope codex skills`, then `lore health` with no scope, then `lore health --scope bogus`, then `lore health --help`
**Then** the token is accepted alone and space-separated, the full-scan path includes it, `bogus` exits 2 with Click's wording naming `skills` among the valid choices, and `--help` lists it

#### Scenario 8: The Python surface reports the same issues

**Given** the project from Scenario 1
**When** a caller runs `health_check(project_root, scope=["skills"])`
**Then** the returned `HealthReport` carries one `HealthIssue` with `severity="error"`, `entity_type="skills"`, `check="missing_skill_file"`, and `schema_id`, `rule` and `pointer` all `None`

### Unit Test Scenarios

- [ ] `lore.health._ALL_SCOPES`: contains `"skills"`
- [ ] `lore.cli._VALID_SCOPES`: contains `"skills"` and matches `health._ALL_SCOPES` as a set
- [ ] `lore.health._check_skills`: each of the five checks in isolation, one test per check
- [ ] `lore.health._check_skills`: an absent manifest returns an empty list, not a `scan_failed`
- [ ] `lore.health._check_skills`: an unparseable manifest returns exactly one `skills_scan_failed` and no other issue
- [ ] `lore.health._check_skills`: walks only the paths the manifest names — a broken `SKILL.md` planted at an unrecorded path produces no issue
- [ ] `lore.health._check_skills`: every issue carries `entity_type="skills"` and `schema_id`, `rule`, `pointer` all `None`
- [ ] `lore.health._check_skills`: severity mapping — `missing_skill_file` and `missing_skill_frontmatter` and `skills_scan_failed` are errors; `modified_skill_file` and `retired_skill_present` are warnings
- [ ] `lore.health._check_skills`: a `section`-kind manifest entry is not checked for `SKILL.md` frontmatter

---

## Out of Scope

- A `lore skill` CLI command group — Tech Spec §1 rejects it; this scope is the audit surface instead.
- Fixing anything the audit finds — that is `lore init`.
- The `conceptual-workflows-health` doc update adding the scope and correcting its stale `lore.models` sentence — owned by the phase-5 codex-apply mission.

---

## References

- PRD: `lore codex show interactive-init-prd` FR-37
- Tech Spec: `lore codex show interactive-init-tech-spec` §10, §16
- `lore codex show conceptual-workflows-health`
- `lore codex show decisions-017-constrained-flags-use-click-choice` — adding a token is non-breaking

---

## Tech Notes

### Implementation Approach

- **Files to modify:**
  - `src/lore/health.py` — add `"skills"` to `_ALL_SCOPES` at `src/lore/health.py:78`, add `_check_skills(project_root) -> list[HealthIssue]`, and register it in the `checkers` dict at `src/lore/health.py:1663-1674`.
  - `src/lore/cli.py` — add `"skills"` to `_VALID_SCOPES` at `src/lore/cli.py:4093`.
- **Files to create:** none.
- **Schema changes:** none — `entity_type="skills"` with `schema_id`, `rule` and `pointer` all `None`, matching every non-schema check.
- **Dependencies:** US-003 (the retirement ledger for `retired_skill_present`), US-008 (`manifest.load` and `file_digest`).

The generic `except Exception` wrapper already around every checker at `src/lore/health.py:1680-1690` produces a `scan_failed` check name; `_check_skills` must catch the unparseable-manifest case itself and emit `skills_scan_failed`, so the specific detail survives rather than being flattened by the generic handler.

Output format follows the existing `_render_issues_table` at `src/lore/health.py:1505` with no change — the scenarios above quote what that renderer already produces for a new `entity_type`.

### Test File Locations

| Type | Path | Notes |
|------|------|-------|
| E2E | `tests/e2e/test_health_skills.py` — NEW | Anchor `conceptual-workflows-health`, following the `test_health_bindings.py` / `test_health_rites.py` / `test_health_voice.py` precedent, all of which cite the same doc |
| Unit | `tests/unit/test_health.py` — extended | `_check_skills` per check |
| Unit | `tests/unit/test_cli_health.py` — extended | The scope-token surface |

### Test Stubs

```python
# E2E — Scenario 1: A deleted installed skill is an error and exits 1
# Exercises: lore codex show conceptual-workflows-health — the skills scope
def test_missing_installed_skill_is_an_error(project_dir, runner):
    pass


# E2E — Scenario 2: An edited installed skill is a warning
# Exercises: lore codex show conceptual-workflows-health — the skills scope
def test_edited_installed_skill_is_a_warning(project_dir, runner):
    pass


# E2E — Scenario 3: A retired skill still on disk is a warning naming its successor
# Exercises: lore codex show conceptual-workflows-health — the skills scope
def test_retired_skill_present_names_its_successor(project_dir, runner):
    pass


# E2E — Scenario 4: A SKILL.md with no `name` is an error
# Exercises: lore codex show conceptual-workflows-health — the skills scope
def test_skill_without_name_frontmatter_is_an_error(project_dir, runner):
    pass


# E2E — Scenario 5: An unparseable manifest is one error
# Exercises: lore codex show conceptual-workflows-health — the skills scope
def test_unparseable_manifest_is_one_scan_failure(project_dir, runner):
    pass


# E2E — Scenario 6: A project with no manifest reports nothing
# Exercises: lore codex show conceptual-workflows-health — the skills scope
def test_project_without_a_manifest_reports_nothing(project_dir, runner):
    pass


# E2E — Scenario 7: The scope is a first-class token everywhere
# Exercises: lore codex show conceptual-workflows-health — scope vocabulary
def test_skills_scope_alone_combined_default_invalid_and_in_help(project_dir, runner):
    pass


# E2E — Scenario 8: The Python surface reports the same issues
# Exercises: lore codex show conceptual-workflows-health — Python API parity
def test_health_check_scope_skills_returns_the_same_issue(project_dir):
    pass


# Unit — scope registration on both sides
# Exercises: lore codex show conceptual-workflows-health — scope vocabulary
def test_skills_registered_in_all_scopes_and_valid_scopes():
    pass


# Unit — the five checks in isolation
# Exercises: lore codex show conceptual-workflows-health — the skills scope
def test_check_missing_skill_file(tmp_path):
    pass


def test_check_modified_skill_file(tmp_path):
    pass


def test_check_retired_skill_present(tmp_path):
    pass


def test_check_missing_skill_frontmatter(tmp_path):
    pass


def test_check_skills_scan_failed(tmp_path):
    pass


# Unit — absent manifest is silent
# Exercises: lore codex show conceptual-workflows-health — the skills scope
def test_absent_manifest_yields_no_issues(tmp_path):
    pass


# Unit — only manifest-named paths are walked
# Exercises: lore codex show conceptual-workflows-health — the skills scope
def test_unrecorded_broken_skill_is_ignored(tmp_path):
    pass


# Unit — issue field shape
# Exercises: lore codex show conceptual-workflows-health — issue contracts
def test_every_skills_issue_has_null_schema_fields(tmp_path):
    pass


# Unit — severity mapping
# Exercises: lore codex show conceptual-workflows-health — issue contracts
def test_severity_mapping_for_the_five_checks(tmp_path):
    pass


# Unit — section entries are not frontmatter-checked
# Exercises: lore codex show conceptual-workflows-health — the skills scope
def test_section_kind_entries_skip_the_frontmatter_check(tmp_path):
    pass
```

### Complexity Estimate

**M** — five checks in one new checker plus a two-place scope registration; the pattern is well established by `_check_rites` and `_check_bindings`, and the only subtlety is the deliberate silence on a missing manifest.

### Standards References

- `lore codex show conceptual-workflows-health` — issue shape, severity convention, exit codes
- `lore codex show decisions-017-constrained-flags-use-click-choice`
- `lore codex show technical-test-guidelines` — the `test_health_<scope>.py` precedent
