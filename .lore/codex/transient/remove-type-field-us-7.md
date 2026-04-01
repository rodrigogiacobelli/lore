---
id: remove-type-field-us-7
type: user-story
title: "US-7: Update unit tests to remove type expectations"
summary: As a developer, I want all unit tests updated to omit type from fixture dicts and assert type is absent from results, so that the test suite passes at 100% after the source changes in US-1 through US-6.
status: draft
---

## Metadata

- **ID:** US-7
- **Status:** final
- **Epic:** Test Suite Alignment
- **Author:** Business Analyst
- **Date:** 2026-03-27
- **PRD:** `lore codex show remove-type-field-prd`
- **Tech Spec:** `lore codex show remove-type-field-tech-spec`

---

## Story

As a developer landing the `type:` removal changes, I want the unit test suite to pass at 100% after the change, so that the CI gate is green and no test asserts a behaviour that no longer exists.

## Context

The PRD (FR-20, FR-21) and the Tech Spec identify specific unit test files that must be updated:

- `tests/unit/test_frontmatter.py`: update `_make_doc` helper to omit `type:`; update assertions to check `"type" not in result`
- `tests/unit/test_codex.py`: `_write_doc()` helper loses `doc_type` param; delete `test_chaos_documents_excludes_transient_marker_type()`; delete `test_map_documents_transient_marker_excluded()`; update key-set assertions
- `tests/unit/test_models.py`: remove `type` from `Artifact`/`CodexDocument` fixture dicts; delete type-field tests; update `from_dict` calls
- `tests/unit/test_cli_codex_list.py`: no changes needed — type-absence tests already written (promoted from FAILS to green by the source changes)

This story is about test maintenance, not new test authoring. Tests must reflect the new source behaviour, not the old one.

---

## Acceptance Criteria

### E2E Scenarios

#### Scenario 1: Unit test suite passes at 100% after source changes

**Given** the source changes from US-1 through US-6 are applied
**When** the developer runs `pytest tests/unit/ -q`
**Then** all tests pass; exit code is 0; no test is skipped; output reads `N passed` with no failures or errors

#### Scenario 2: Deleted transient-marker tests do not appear in test output

**Given** the source changes from US-2 are applied (transient-marker sentinel removed)
**When** the developer runs `pytest tests/unit/test_codex.py -q`
**Then** `test_chaos_documents_excludes_transient_marker_type` and `test_map_documents_transient_marker_excluded` do not appear in the output (they are deleted, not skipped)

#### Scenario 3: test_cli_codex_list.py type-absence tests pass

**Given** the source changes from US-5 are applied
**When** the developer runs `pytest tests/unit/test_cli_codex_list.py -q`
**Then** all tests pass (including any test asserting `"type" not in record`); exit code is 0

### Unit Test Scenarios

- [ ] `tests/unit/test_frontmatter.py` `_make_doc` helper: does not include `type:` in written frontmatter
- [ ] `tests/unit/test_frontmatter.py`: all assertions check `"type" not in result` rather than `result["type"] == ...`
- [ ] `tests/unit/test_codex.py` `_write_doc()` helper: `doc_type` parameter removed
- [ ] `tests/unit/test_codex.py`: `test_chaos_documents_excludes_transient_marker_type` deleted
- [ ] `tests/unit/test_codex.py`: `test_map_documents_transient_marker_excluded` deleted
- [ ] `tests/unit/test_codex.py`: key-set assertions use `{"id", "title", "summary", "group", "path"}` (no `"type"`)
- [ ] `tests/unit/test_models.py`: fixture dicts for `Artifact` and `CodexDocument` do not contain `"type"` key
- [ ] `tests/unit/test_models.py`: tests asserting `artifact.type` or `doc.type` raises `AttributeError` are added (not deleted)
- [ ] `tests/unit/test_cli_codex_list.py`: no modifications required; existing type-absence assertions now pass

---

## Out of Scope

- E2E test updates — covered by US-8
- Writing new test behaviour not already specified in US-1 through US-6
- Adding tests for Realm behaviour (Realm updates are out of scope for this quest)

---

## References

- PRD: `lore codex show remove-type-field-prd` (FR-20, FR-21, FR-22)
- Tech Spec: `lore codex show remove-type-field-tech-spec`

---

## Tech Notes

_(Filled by Tech Lead in tech-notes-draft and tech-notes-final phases — BA must not edit this section)_

### Implementation Approach

- **Files to create:** None
- **Files to modify:**
  - `tests/unit/test_frontmatter.py` — Update `_make_doc` helper to remove `type: technical` from the base frontmatter string; add assertions checking `"type" not in result` where tests previously checked `result["type"]`
  - `tests/unit/test_codex.py` — Remove `doc_type` parameter from `_write_doc()` helper (and remove the `type: {doc_type}` line from the written content); delete `test_chaos_documents_excludes_transient_marker_type` function entirely; delete `test_map_documents_transient_marker_excluded` function entirely; update any key-set assertions from `{"id","type","title","summary"}` to `{"id","title","summary"}`
  - `tests/unit/test_models.py` — Remove `"type"` key from all `Artifact.from_dict(...)` and `CodexDocument.from_dict(...)` fixture dicts; delete any test asserting `artifact.type == "..."` or `doc.type == "..."`; add tests asserting `artifact.type` raises `AttributeError` and `doc.type` raises `AttributeError`
  - `tests/unit/test_cli_codex_list.py` — No changes needed; type-absence assertions already written (will turn green when US-2 and US-5 source changes are applied)
- **Schema changes:** None
- **Dependencies:** US-1 through US-6 source changes must all be applied before these test updates will pass

**TDD cycle:** Test mission (update unit tests to match new source behaviour) → Commit mission (no Red/Green needed — this is test maintenance aligned with already-implemented source)

### Test File Locations

| Type | Path | Notes |
|------|------|-------|
| Unit | `tests/unit/test_frontmatter.py` | update `_make_doc` helper; add type-absence assertions |
| Unit | `tests/unit/test_codex.py` | update `_write_doc` helper; delete two tests; update key-set assertions |
| Unit | `tests/unit/test_models.py` | update fixture dicts; delete type-value tests; add AttributeError tests |
| Unit | `tests/unit/test_cli_codex_list.py` | no changes — promoted to green by source changes |

### Test Stubs

```python
# =============================================================================
# tests/unit/test_frontmatter.py — changes for US-7
# =============================================================================

# Update: _make_doc helper — omit type: from base frontmatter
# remove-type-field-us-7 Unit Test Scenarios — _make_doc helper does not include type:
def _make_doc(tmp_path, extra_frontmatter: str = "", name: str = "doc.md"):
    # Updated base: id/title/summary only — no type: line
    base = textwrap.dedent("""\
        ---
        id: doc-a
        title: Test Document
        summary: A test document
        {extra}
        ---
        Body text.
    """).format(extra=extra_frontmatter)
    path = tmp_path / name
    path.write_text(base)
    return path


# Update: all existing assertions that check result["type"] must change to assert "type" not in result
# remove-type-field-us-7 Unit Test Scenarios — type not in result assertions
# (Apply to all tests in test_frontmatter.py that previously asserted type presence)


# =============================================================================
# tests/unit/test_codex.py — changes for US-7
# =============================================================================

# Update: _write_doc helper — remove doc_type param and type: line
# remove-type-field-us-7 Unit Test Scenarios — _write_doc() helper loses doc_type param
def _write_doc(codex_dir, doc_id, *, related=None, omit_related=False):
    # No doc_type parameter; no type: line in written content
    related_line = ""
    if not omit_related:
        if related is None:
            related_line = "related: []"
        else:
            items = "\n".join(f"  - {r}" for r in related)
            related_line = f"related:\n{items}"
    content = textwrap.dedent(f"""\
        ---
        id: {doc_id}
        title: {doc_id.replace("-", " ").title()}
        summary: Summary for {doc_id}.
        {related_line}
        ---

        Body of {doc_id}.
    """)
    filepath = codex_dir / f"{doc_id}.md"
    filepath.write_text(content)
    return filepath


# DELETE: test_chaos_documents_excludes_transient_marker_type
# remove-type-field-us-7 Unit Test Scenarios — this test is deleted (sentinel gone)
# (Remove the function body entirely — do not leave a stub)

# DELETE: test_map_documents_transient_marker_excluded
# remove-type-field-us-7 Unit Test Scenarios — this test is deleted (sentinel gone)
# (Remove the function body entirely — do not leave a stub)

# Update: key-set assertions in codex chaos JSON unit test (line ~970)
# remove-type-field-us-7 Unit Test Scenarios — codex chaos key-set updated
# Change: assert set(doc.keys()) == {"id", "type", "title", "summary"}
# To:     assert set(doc.keys()) == {"id", "title", "summary"}


# =============================================================================
# tests/unit/test_models.py — changes for US-7
# =============================================================================

# Update: Artifact fixture dicts — remove "type" key
# remove-type-field-us-7 Unit Test Scenarios — Artifact fixture dicts omit "type"
# Change all:  {"id":"x","title":"T","type":"t","summary":"S","body":"B"}
# To:          {"id":"x","title":"T","summary":"S","body":"B"}

# Update: CodexDocument fixture dicts — remove "type" key
# remove-type-field-us-7 Unit Test Scenarios — CodexDocument fixture dicts omit "type"
# Change all:  {"id":"x","title":"T","type":"t","summary":"S"}
# To:          {"id":"x","title":"T","summary":"S"}

# Add: artifact.type raises AttributeError
# remove-type-field-us-7 Unit Test Scenarios — tests asserting .type raises AttributeError added
def test_artifact_type_attr_raises_attribute_error():
    # remove-type-field-us-7 — AttributeError test added (not deleted)
    from lore.models import Artifact
    import pytest
    a = Artifact.from_dict({"id": "x", "title": "T", "summary": "S", "group": "g", "body": ""})
    with pytest.raises(AttributeError):
        _ = a.type


# Add: doc.type raises AttributeError
# remove-type-field-us-7 Unit Test Scenarios — tests asserting .type raises AttributeError added
def test_codex_document_type_attr_raises_attribute_error():
    # remove-type-field-us-7 — AttributeError test added (not deleted)
    from lore.models import CodexDocument
    import pytest
    doc = CodexDocument.from_dict({"id": "y", "title": "Y", "summary": "s"})
    with pytest.raises(AttributeError):
        _ = doc.type
```

### Complexity Estimate

M — Three test files to update. Changes are mechanical: remove `type` from fixture dicts throughout `test_models.py`, delete two tests in `test_codex.py`, update the `_write_doc` helper, update the `_make_doc` helper, and update key-set assertions. `test_cli_codex_list.py` requires zero edits.
