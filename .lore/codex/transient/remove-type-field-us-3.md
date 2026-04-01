---
id: remove-type-field-us-3
type: user-story
title: "US-3: Remove type from artifact scanning"
summary: As a developer or agent, I want scan_artifacts and read_artifact to return dicts without a type key, so that artifact records are clean and consistent with codex records.
status: draft
---

## Metadata

- **ID:** US-3
- **Status:** final
- **Epic:** Artifact Module Cleanup
- **Author:** Business Analyst
- **Date:** 2026-03-27
- **PRD:** `lore codex show remove-type-field-prd`
- **Tech Spec:** `lore codex show remove-type-field-tech-spec`

---

## Story

As a Realm agent or CLI user, I want `scan_artifacts()` and `read_artifact()` to return records without a `"type"` key, so that artifact data matches the simplified field contract and no consumer needs to handle the redundant field.

## Context

The PRD (FR-9, FR-10, FR-11) requires removing `type` from all dict shapes returned by `artifact.py`. The `required_fields` argument passed to `parse_frontmatter_doc` for artifacts must also omit `"type"` — after US-1, the module default is correct and explicit passing is unnecessary. This story covers the Python API side of PRD Workflow WF-4 (Realm hydrates `Artifact` from `scan_artifacts` dict) and the data that feeds into WF-2 (human runs `lore artifact list`).

---

## Acceptance Criteria

### E2E Scenarios

#### Scenario 1: scan_artifacts returns dicts without type key

**Given** a project with artifact templates in `.lore/artifacts/`
**When** a Python caller runs `from lore.artifact import scan_artifacts; results = scan_artifacts()`
**Then** each dict in `results` has exactly the keys `{"id", "group", "title", "summary", "path"}` with no `"type"` key

#### Scenario 2: read_artifact returns dict without type key

**Given** an artifact template file with frontmatter `id`, `title`, `summary` (and optionally a legacy `type:` field)
**When** a Python caller runs `from lore.artifact import read_artifact; doc = read_artifact("some-id")`
**Then** `doc` has no `"type"` key; `doc` has keys `{"id", "title", "summary", "group", "body"}`

#### Scenario 3: lore artifact list --json records have no type key

**Given** a project with at least one artifact template
**When** the user runs `lore artifact list --json`
**Then** the command exits 0; each record in the `"artifacts"` array has no `"type"` key; each record has exactly `{"id", "group", "title", "summary"}`

### Unit Test Scenarios

- [ ] `artifact.scan_artifacts`: returns dicts with keys `{"id", "group", "title", "summary", "path"}` — no `"type"`
- [ ] `artifact.read_artifact`: returns dict with keys `{"id", "title", "summary", "group", "body"}` — no `"type"`
- [ ] `artifact.scan_artifacts`: artifact file with legacy `type: workflow` in frontmatter — `"type"` absent from returned dict

---

## Out of Scope

- CLI text output changes (TYPE column removal) — covered by US-5
- `models.py` Artifact dataclass changes — covered by US-4
- Default template file changes — covered by US-6

---

## References

- PRD: `lore codex show remove-type-field-prd` (FR-9, FR-10, FR-11; WF-4)
- Tech Spec: `lore codex show remove-type-field-tech-spec`
- `lore codex show conceptual-entities-artifact`
- `lore codex show tech-arch-frontmatter`

---

## Tech Notes

_(Filled by Tech Lead in tech-notes-draft and tech-notes-final phases — BA must not edit this section)_

### Implementation Approach

- **Files to create:** None
- **Files to modify:**
  - `src/lore/artifact.py` — In `scan_artifacts()`, stop passing explicit `required_fields` to `parse_frontmatter_doc` (use module default from US-1); remove `"type"` from `read_artifact()` returned dict (lines 44–50: remove `"type": record["type"]`); update docstring to reflect new key set
- **Schema changes:** None
- **Dependencies:** US-1 must be complete so `frontmatter._REQUIRED_FIELDS` already excludes `"type"` and is the correct default for artifact parsing

**TDD cycle:** Red mission (write failing tests in `test_artifact_list.py` and unit artifact tests) → Green mission (update `artifact.py`) → Commit mission

Note: There is no `tests/unit/test_artifact.py` in the current test suite. The unit coverage for `artifact.py` lives in `tests/e2e/test_artifact_list.py` (class-based unit-style tests at the top). The Red mission should add stubs to `tests/e2e/test_artifact_list.py` (unit-style section) and to a new `tests/unit/test_artifact.py` if the Tech Spec calls for it; otherwise use the existing E2E file.

### Test File Locations

| Type | Path | Notes |
|------|------|-------|
| E2E | `tests/e2e/test_artifact_list.py` | scan_artifacts and read_artifact dict shape; artifact list JSON records |
| Unit | `tests/e2e/test_artifact_list.py` (unit-style class) | scan_artifacts key-set assertion; legacy type field silently ignored |

### Test Stubs

```python
# =============================================================================
# tests/e2e/test_artifact_list.py — new stubs for US-3
# =============================================================================

# E2E Scenario 1: scan_artifacts returns dicts without "type" key
# conceptual-workflows-artifact-list step: scan_artifacts walks artifacts_dir
def test_scan_artifacts_no_type_key(tmp_path):
    # Given: artifact file with frontmatter id/title/summary (no type: line)
    # When: scan_artifacts(artifacts_dir)
    # Then: each dict key set == {"id","group","title","summary","path"}; no "type" key
    pass


# E2E Scenario 1 (legacy): artifact file with legacy type: workflow returns no "type" key
# conceptual-workflows-artifact-list step: scan_artifacts silently ignores extra frontmatter keys
def test_scan_artifacts_legacy_type_field_absent_from_result(tmp_path):
    # Given: artifact file with id/title/summary/type: workflow in frontmatter
    # When: scan_artifacts(artifacts_dir)
    # Then: dict has no "type" key; id/title/summary/group/path are present
    pass


# E2E Scenario 2: read_artifact returns dict without "type" key
# conceptual-workflows-artifact-list step: read_artifact returns full record with body
def test_read_artifact_no_type_key(tmp_path):
    # Given: artifact template file with frontmatter id/title/summary (optionally legacy type:)
    # When: read_artifact(artifacts_dir, "some-id")
    # Then: returned dict key set == {"id","title","summary","group","body"}; no "type" key
    pass


# E2E Scenario 3: lore artifact list --json records have no type key
# conceptual-workflows-artifact-list step: CLI artifact_list handler serialises scan_artifacts results
def test_artifact_list_json_no_type_key(runner, bare_project_dir):
    # Given: project with at least one artifact template
    # When: lore artifact list --json
    # Then: exit 0; each record in "artifacts" array has no "type" key;
    #       set(record.keys()) == {"id","group","title","summary"}
    pass
```

### Complexity Estimate

S — One module (`src/lore/artifact.py`), two functions (`scan_artifacts`, `read_artifact`), straightforward dict shape change. The `scan_artifacts` change is a one-line deletion (stop passing explicit `required_fields`). The `read_artifact` change removes one key from the returned dict.
