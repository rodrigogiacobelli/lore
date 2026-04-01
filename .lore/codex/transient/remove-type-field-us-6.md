---
id: remove-type-field-us-6
type: user-story
title: "US-6: Strip type from default artifact templates"
summary: As a developer initializing a new project, I want lore init to seed artifact templates without a type frontmatter line, so that new projects start with the simplified field contract from the beginning.
status: draft
---

## Metadata

- **ID:** US-6
- **Status:** final
- **Epic:** Default Template Cleanup
- **Author:** Business Analyst
- **Date:** 2026-03-27
- **PRD:** `lore codex show remove-type-field-prd`
- **Tech Spec:** `lore codex show remove-type-field-tech-spec`

---

## Story

As a developer or agent running `lore init` on a fresh directory, I want none of the seeded artifact templates to contain a `type:` frontmatter line, so that new projects are clean and agents do not need to strip the field before using templates as scaffolds.

## Context

The PRD (FR-19) requires removing the `type:` frontmatter line from all ~39 files under `src/lore/defaults/artifacts/`. The PRD Workflow WF-3 describes this end-to-end: after `lore init`, `grep -r "^type:" .lore/artifacts/` must return zero results. Additionally, the `transient-marker` sentinel exclusion (previously managed by `exclude_type`) is removed entirely — any file that was previously excluded via that sentinel is now a regular document. This is a data change (file content) not a code change.

---

## Acceptance Criteria

### E2E Scenarios

#### Scenario 1: lore init seeds templates without type line

**Given** an empty directory with no existing `.lore/` folder
**When** the user runs `lore init` followed by `grep -r "^type:" .lore/artifacts/`
**Then** `lore init` exits 0; `grep` returns no output (exit code 1, meaning zero matches)

#### Scenario 2: Each seeded artifact template passes lore artifact list

**Given** a project initialized with `lore init`
**When** the user runs `lore artifact list --json`
**Then** the command exits 0; no record in the `"artifacts"` array contains a `"type"` key; the count of records matches the number of files seeded by `lore init`

#### Scenario 3: Seeded templates contain id, title, summary in frontmatter

**Given** a project initialized with `lore init`
**When** the user opens any artifact template file (e.g. `.lore/artifacts/codex/conceptual/entity.md`)
**Then** the YAML frontmatter block contains `id:`, `title:`, and `summary:` lines; there is no `type:` line

### Unit Test Scenarios

- [ ] All files under `src/lore/defaults/artifacts/`: none contain a line matching `^type:` — this can be validated with a test that reads all default artifact files and asserts no `type:` line
- [ ] `lore init` integration: after init, zero artifact files in `.lore/artifacts/` contain `^type:`

---

## Out of Scope

- Changes to Python source code (`frontmatter.py`, `codex.py`, etc.) — covered by US-1 through US-5
- Live `.lore/codex/` document migration — handled by parallel quest q-bbbf
- Any template file content other than the `type:` frontmatter line (body, other fields unchanged)

---

## References

- PRD: `lore codex show remove-type-field-prd` (FR-19; WF-3)
- Tech Spec: `lore codex show remove-type-field-tech-spec`
- `lore codex show tech-arch-source-layout`
- `lore codex show conceptual-workflows-lore-init`
- `lore codex show tech-arch-initialized-project-structure`

---

## Tech Notes

_(Filled by Tech Lead in tech-notes-draft and tech-notes-final phases — BA must not edit this section)_

### Implementation Approach

- **Files to create:** None
- **Files to modify:** All `*.md` files under `src/lore/defaults/artifacts/` (~39 files) — remove the `type:` frontmatter line from each file's YAML block. The files are in two directories:
  - `src/lore/defaults/artifacts/codex/` (~29 `.md` files across subdirectories)
  - `src/lore/defaults/artifacts/feature-implementation/` (~10 `.md` files)
  - Glob: `src/lore/defaults/artifacts/**/*.md` (excluding any `README.md` files that are not artifact templates)
- **Schema changes:** None — this is a data change only (file content), no Python code changes
- **Dependencies:** US-1 must be complete so `frontmatter._REQUIRED_FIELDS` no longer includes `"type"` — the stripped templates will still parse correctly after US-1 is applied. If US-1 is not yet applied, stripping `type:` from templates would cause them to fail parsing against the old required-fields check.

**TDD cycle:** Update mission (strip `type:` from all ~39 template files) → Commit mission (no Red/Green cycle needed — this is a data-only change)

### Test File Locations

| Type | Path | Notes |
|------|------|-------|
| E2E | `tests/e2e/test_lore_init.py` | lore init seeds templates without type: line; grep passes |
| Unit | `tests/unit/test_defaults.py` | static file check: no default artifact file contains a `^type:` line (new test file) |

### Test Stubs

```python
# =============================================================================
# tests/e2e/test_lore_init.py — new stubs for US-6
# =============================================================================

# E2E Scenario 1: lore init seeds templates without type: line
# conceptual-workflows-lore-init step: lore init copies defaults/artifacts/ to .lore/artifacts/
def test_lore_init_seeded_templates_have_no_type_line(runner, tmp_path, monkeypatch):
    # Given: empty directory with no existing .lore/ folder
    # When: lore init
    # Then: lore init exits 0; no file under .lore/artifacts/ contains a line matching ^type:
    import re
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(main, ["init"])
    assert result.exit_code == 0
    artifacts_dir = tmp_path / ".lore" / "artifacts"
    type_lines = []
    for md_file in artifacts_dir.rglob("*.md"):
        for line in md_file.read_text().splitlines():
            if re.match(r"^type:", line):
                type_lines.append((md_file, line))
    assert type_lines == [], f"Found type: lines in seeded templates: {type_lines}"


# E2E Scenario 2: lore artifact list --json after init — no type key in any record
# conceptual-workflows-artifact-list step: scan_artifacts of seeded templates returns no type field
def test_lore_init_artifact_list_json_no_type_key(runner, tmp_path, monkeypatch):
    # Given: empty directory
    # When: lore init; lore artifact list --json
    # Then: exit 0; no record in "artifacts" array contains "type" key
    pass


# E2E Scenario 3: seeded templates contain id, title, summary — no type: line
# conceptual-workflows-lore-init step: each copied template file has valid frontmatter without type
def test_lore_init_seeded_template_frontmatter_has_no_type(runner, tmp_path, monkeypatch):
    # Given: lore init run in empty directory
    # When: read any artifact template file
    # Then: frontmatter contains id:/title:/summary: lines; no type: line
    pass


# =============================================================================
# tests/unit/test_defaults.py — new file, stubs for US-6
# =============================================================================

# Unit: all files under src/lore/defaults/artifacts/ have no line matching ^type:
# remove-type-field-us-6 Unit Test Scenarios — static check of default artifact files
def test_default_artifact_files_have_no_type_line():
    # Given: all .md files under src/lore/defaults/artifacts/ (exclude README.md)
    # When: read each file and check for lines matching ^type:
    # Then: no such lines found
    import re
    import lore as _lore_pkg
    from pathlib import Path
    defaults_dir = Path(_lore_pkg.__file__).parent / "defaults" / "artifacts"
    violations = []
    for md_file in defaults_dir.rglob("*.md"):
        if md_file.name == "README.md":
            continue
        for line in md_file.read_text().splitlines():
            if re.match(r"^type:", line):
                violations.append((str(md_file), line))
    assert violations == [], f"Default artifact files contain type: lines: {violations}"


# Unit: lore init integration — seeded .lore/artifacts/ has zero ^type: lines
# conceptual-workflows-lore-init step: init copies defaults/ to .lore/artifacts/
def test_lore_init_integration_no_type_in_artifacts(tmp_path, monkeypatch):
    # Given: empty tmp_path
    # When: invoke main(["init"]); scan all *.md under .lore/artifacts/
    # Then: zero files contain a line matching ^type:
    pass
```

### Complexity Estimate

L — ~39 files to edit, but each edit is mechanical (remove one `type:` line from YAML frontmatter). No logic changes. The new `tests/unit/test_defaults.py` is a small static file check. The E2E stubs in `test_lore_init.py` exercise the full `lore init` command.
