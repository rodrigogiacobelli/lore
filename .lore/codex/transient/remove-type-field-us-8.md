---
id: remove-type-field-us-8
type: user-story
title: "US-8: Update E2E tests to remove type expectations"
summary: As a developer, I want all E2E tests updated to omit type from document fixtures and assert type is absent from command output, so that the full test suite passes at 100% after the source changes.
status: draft
---

## Metadata

- **ID:** US-8
- **Status:** final
- **Epic:** Test Suite Alignment
- **Author:** Business Analyst
- **Date:** 2026-03-27
- **PRD:** `lore codex show remove-type-field-prd`
- **Tech Spec:** `lore codex show remove-type-field-tech-spec`

---

## Story

As a developer landing the `type:` removal changes, I want the E2E test suite to pass at 100% after the change, so that the full integration layer is green and no E2E test asserts a behaviour from the old contract.

## Context

The PRD (FR-20, FR-21) and the Tech Spec identify specific E2E test files that must be updated:

- `tests/e2e/test_codex.py`: remove `type:` from all inline doc strings; delete type-field tests; update JSON key-set assertions
- `tests/e2e/test_artifact_list.py`: update `SPEC_KEY_ORDER` to `["id", "group", "title", "summary"]`; delete `TYPE` column assertions; delete type-field JSON tests
- `tests/e2e/test_codex_chaos.py`: update `_write_codex_doc()` helper to drop `doc_type` param and `type:` line; update JSON schema assertion to `{"id", "title", "summary"}`
- `tests/e2e/test_codex_map.py`: update `_write_codex_doc()` helpers to drop `doc_type` param and `type:` line; update JSON key-set assertions to `{"id", "title", "summary", "body"}`

This story is about E2E test maintenance. New test scenarios for the `type`-free behaviour are already specified in US-1 through US-6 — this story ensures those new tests exist in the E2E layer and old tests are cleaned up.

---

## Acceptance Criteria

### E2E Scenarios

#### Scenario 1: Full E2E test suite passes at 100% after source changes

**Given** the source changes from US-1 through US-6 are applied
**When** the developer runs `pytest tests/e2e/ -q`
**Then** all tests pass; exit code is 0; no test is skipped; output reads `N passed` with no failures or errors

#### Scenario 2: test_artifact_list.py has no TYPE column assertion

**Given** the updated `tests/e2e/test_artifact_list.py`
**When** the developer searches the file for `"TYPE"`
**Then** no match is found; `SPEC_KEY_ORDER` equals `["id", "group", "title", "summary"]`

#### Scenario 3: test_codex_chaos.py _write_codex_doc no longer passes doc_type

**Given** the updated `tests/e2e/test_codex_chaos.py`
**When** the developer reviews the `_write_codex_doc()` helper
**Then** the helper has no `doc_type` parameter and does not write a `type:` line in the frontmatter it generates

#### Scenario 4: test_codex_map.py JSON key-set assertion matches new contract

**Given** the updated `tests/e2e/test_codex_map.py`
**When** the developer runs `pytest tests/e2e/test_codex_map.py -q`
**Then** all tests pass; assertions check that map record key set equals `{"id", "title", "summary", "body"}` (no `"type"`)

#### Scenario 5: E2E fixtures in conftest.py omit type from seeded documents

**Given** the updated `tests/e2e/conftest.py`
**When** the developer reviews any codex document fixture written by `conftest.py`
**Then** the fixture does not include a `type:` frontmatter line

### Unit Test Scenarios

- [ ] `tests/e2e/test_codex.py`: all inline doc strings used in fixtures do not contain `type:` lines
- [ ] `tests/e2e/test_codex.py`: JSON key-set assertions check `{"id", "title", "summary", "group", "path"}` (no `"type"`)
- [ ] `tests/e2e/test_artifact_list.py`: `SPEC_KEY_ORDER` equals `["id", "group", "title", "summary"]`
- [ ] `tests/e2e/test_artifact_list.py`: no assertion checks for `TYPE` column header
- [ ] `tests/e2e/test_artifact_list.py`: no JSON assertion checks for `"type"` key presence
- [ ] `tests/e2e/test_codex_chaos.py`: `_write_codex_doc()` has no `doc_type` parameter
- [ ] `tests/e2e/test_codex_chaos.py`: JSON schema assertion is `{"id", "title", "summary"}` (no `"type"`)
- [ ] `tests/e2e/test_codex_map.py`: `_write_codex_doc()` helpers have no `doc_type` parameter
- [ ] `tests/e2e/test_codex_map.py`: JSON key-set assertions are `{"id", "title", "summary", "body"}` (no `"type"`)

---

## Out of Scope

- Unit test updates — covered by US-7
- Writing new E2E tests beyond what is specified in US-1 through US-6 acceptance criteria
- `conftest.py` changes beyond removing `type:` from seeded document fixtures

---

## References

- PRD: `lore codex show remove-type-field-prd` (FR-20, FR-21; WF-1, WF-2, WF-5)
- Tech Spec: `lore codex show remove-type-field-tech-spec`

---

## Tech Notes

_(Filled by Tech Lead in tech-notes-draft and tech-notes-final phases — BA must not edit this section)_

### Implementation Approach

- **Files to create:** None
- **Files to modify:**
  - `tests/e2e/test_codex.py` — Remove `type:` lines from all inline document strings used as fixtures; update JSON key-set assertions from `{"id","type","title","summary","group","path"}` to `{"id","title","summary","group","path"}`; delete any test that asserts `result["type"] == "conceptual"` or similar
  - `tests/e2e/test_artifact_list.py` — Update `SPEC_KEY_ORDER` (line 179) from `["id","type","group","title","summary"]` to `["id","group","title","summary"]`; delete `test_output_contains_type`, `test_table_has_type_column_header`, `test_column_order_id_type_group_title_summary` tests; delete `test_json_artifact_has_type_field` tests; delete `test_file_missing_required_type_field_skipped` (that test fixture will now parse successfully); update `VALID_ARTIFACT` inline string to remove `type: template` line
  - `tests/e2e/test_codex_chaos.py` — Remove `doc_type` parameter from `_write_codex_doc()` helper (line 16) and remove `type: {doc_type}` line from the written frontmatter (line 29); update JSON schema assertion at line 352 from `{"id","type","title","summary"}` to `{"id","title","summary"}`
  - `tests/e2e/test_codex_map.py` — Remove `doc_type` parameter from `_write_codex_doc()` helper (line 17) and remove `type: {doc_type}` line from frontmatter (line 30); update JSON key-set assertions at lines 776 and 850 from `{"id","type","title","summary","body"}` to `{"id","title","summary","body"}`; delete `test_bfs_transient_marker_excluded_from_output` (sentinel gone — marker doc will now be included)
  - `tests/e2e/conftest.py` — Review and remove `type:` from any codex document fixtures seeded into the project
- **Schema changes:** None
- **Dependencies:** US-1 through US-6 source changes must all be applied before these E2E test updates will pass

**TDD cycle:** Test mission (update E2E tests to match new source behaviour) → Commit mission

### Test File Locations

| Type | Path | Notes |
|------|------|-------|
| E2E | `tests/e2e/test_codex.py` | inline doc fixture cleanup, key-set assertion updates |
| E2E | `tests/e2e/test_artifact_list.py` | SPEC_KEY_ORDER update, TYPE-related test deletions |
| E2E | `tests/e2e/test_codex_chaos.py` | `_write_codex_doc` helper update, JSON schema assertion |
| E2E | `tests/e2e/test_codex_map.py` | `_write_codex_doc` helper update, JSON key-set assertions |
| E2E | `tests/e2e/conftest.py` | remove type: from seeded doc fixtures if present |

### Test Stubs

```python
# =============================================================================
# tests/e2e/test_artifact_list.py — changes for US-8
# =============================================================================

# Update: SPEC_KEY_ORDER constant
# remove-type-field-us-8 Unit Test Scenarios — SPEC_KEY_ORDER equals ["id","group","title","summary"]
SPEC_KEY_ORDER = ["id", "group", "title", "summary"]  # updated — was ["id","type","group","title","summary"]


# Update: VALID_ARTIFACT fixture — remove type: template line
# remove-type-field-us-8 Unit Test Scenarios — inline doc strings have no type: lines
VALID_ARTIFACT = """\
---
id: transient-business-spec
title: Business Spec Template
summary: Template for writing a business spec.
---

# Business Spec Template

Body content here.
"""


# DELETE: test_output_contains_type
# remove-type-field-us-8 Unit Test Scenarios — TYPE column assertions deleted

# DELETE: test_table_has_type_column_header
# remove-type-field-us-8 Unit Test Scenarios — TYPE column assertions deleted

# DELETE: test_column_order_id_type_group_title_summary
# remove-type-field-us-8 Unit Test Scenarios — TYPE column assertions deleted

# DELETE: test_json_artifact_has_type_field (both occurrences)
# remove-type-field-us-8 Unit Test Scenarios — JSON type key assertions deleted

# DELETE: test_file_missing_required_type_field_skipped
# remove-type-field-us-8 — that fixture will now parse successfully; delete this test


# =============================================================================
# tests/e2e/test_codex_chaos.py — changes for US-8
# =============================================================================

# Update: _write_codex_doc helper — remove doc_type param and type: line
# remove-type-field-us-8 Unit Test Scenarios — _write_codex_doc has no doc_type parameter
def _write_codex_doc(project_dir, doc_id, *, related=None, omit_related=False):
    # No doc_type parameter; no type: line in written frontmatter
    # conceptual-workflows-codex-chaos step: helper creates minimal valid codex doc
    pass


# Update: JSON schema assertion in test_chaos_json_output_valid_structure
# remove-type-field-us-8 Unit Test Scenarios — JSON schema assertion is {"id","title","summary"}
# Change line ~352: assert set(doc.keys()) == {"id", "type", "title", "summary"}
# To:              assert set(doc.keys()) == {"id", "title", "summary"}


# =============================================================================
# tests/e2e/test_codex_map.py — changes for US-8
# =============================================================================

# Update: _write_codex_doc helper — remove doc_type param and type: line
# remove-type-field-us-8 Unit Test Scenarios — _write_codex_doc helpers have no doc_type param
def _write_codex_doc(project_dir, doc_id, *, related=None, omit_related=False):
    # No doc_type parameter; no type: line in written frontmatter
    # conceptual-workflows-codex-map step: helper creates minimal valid codex doc
    pass


# Update: JSON key-set assertions in test_json_document_object_has_exactly_five_required_keys (~line 762)
# remove-type-field-us-8 Unit Test Scenarios — JSON key-set assertions are {"id","title","summary","body"}
# Change: assert set(doc.keys()) == {"id", "type", "title", "summary", "body"}
# To:     assert set(doc.keys()) == {"id", "title", "summary", "body"}

# Update: same assertion in test_cli_codex_map_json_mode_document_has_five_keys (~line 840)
# Change: assert set(doc.keys()) == {"id", "type", "title", "summary", "body"}
# To:     assert set(doc.keys()) == {"id", "title", "summary", "body"}

# DELETE: test_bfs_transient_marker_excluded_from_output
# remove-type-field-us-8 — sentinel is gone; this test no longer applies
# (The transient-marker doc will now be included, not excluded)


# =============================================================================
# tests/e2e/test_codex.py — changes for US-8
# =============================================================================

# Update: all inline document strings used in fixtures — remove type: lines
# remove-type-field-us-8 Unit Test Scenarios — all inline doc strings have no type: lines
# (Scan the file for strings containing "type: " in YAML frontmatter blocks and remove those lines)

# Update: JSON key-set assertions — remove "type" from expected key sets
# remove-type-field-us-8 Unit Test Scenarios — JSON key-set assertions check {"id","title","summary","group","path"}
# Change any: assert set(record.keys()) == {"id","type","title","summary"}
# To:         assert set(record.keys()) == {"id","title","summary"} (search results)
# Or:         assert set(record.keys()) == {"id","title","summary","group","path"} (scan results)

# DELETE: any test asserting result[0]["type"] == "conceptual" or similar
# remove-type-field-us-8 Unit Test Scenarios — type-field assertions deleted


# =============================================================================
# tests/e2e/conftest.py — changes for US-8
# =============================================================================

# Update: any codex document fixture written in conftest.py — remove type: line
# remove-type-field-us-8 E2E Scenario 5 — conftest fixtures omit type: from seeded documents
# (Review conftest.py and remove type: from any .md content strings)
```

### Complexity Estimate

M — Four E2E test files plus `conftest.py`. Changes are mechanical: remove `type:` from fixture strings, update `_write_codex_doc` helpers in two files, delete several type-assertion tests, update two JSON key-set assertions in `test_codex_map.py`, update `SPEC_KEY_ORDER` in `test_artifact_list.py`. No new test logic is introduced.
