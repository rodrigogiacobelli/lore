---
id: remove-type-field-us-1
type: user-story
title: "US-1: Remove type from frontmatter parsing"
summary: As a developer, I want the frontmatter parser to accept documents without a type field, so that type is no longer a contract requirement and exclude_type logic is eliminated.
status: draft
---

## Metadata

- **ID:** US-1
- **Status:** final
- **Epic:** Frontmatter Contract Simplification
- **Author:** Business Analyst
- **Date:** 2026-03-27
- **PRD:** `lore codex show remove-type-field-prd`
- **Tech Spec:** `lore codex show remove-type-field-tech-spec`

---

## Story

As a Realm agent or CLI user, I want the frontmatter parser to parse documents without a `type:` field without raising a validation error, so that I no longer need to include `type:` in any document frontmatter.

## Context

The PRD (FR-1 through FR-4) requires removing `"type"` from `_REQUIRED_FIELDS` in `frontmatter.py` and removing the `exclude_type` parameter entirely. This is the foundational change: all other modules depend on `frontmatter.py` to enforce the field contract. Once `type` is removed here, documents that omit `type:` will parse successfully throughout the system. Documents with a legacy `type:` field must continue to parse without error — the field is silently ignored. This story covers PRD Workflows WF-1 (agent writes a new codex document without `type:`) and the critical decision point that legacy documents parse cleanly.

---

## Acceptance Criteria

### E2E Scenarios

#### Scenario 1: Document without type field parses successfully

**Given** a `.md` file in `.lore/codex/transient/` with frontmatter containing only `id`, `title`, and `summary` (no `type:` line)
**When** the user runs `lore codex show <id>`
**Then** the command exits 0 and returns the document body; no error message is printed

#### Scenario 2: Document with legacy type field is silently accepted

**Given** a `.md` file with frontmatter containing `id`, `title`, `summary`, and `type: conceptual`
**When** the user runs `lore codex list --json`
**Then** the command exits 0, the record for that document appears in the output, and the record does not contain a `"type"` key

#### Scenario 3: exclude_type parameter is gone — callers use no special argument

**Given** the `frontmatter.py` module
**When** a caller invokes `parse_frontmatter_doc(path, required_fields=("id","title","summary"))` without any `exclude_type` argument
**Then** no `TypeError` is raised (the parameter no longer exists); the returned dict has keys `{"id", "title", "summary"}` and no `"type"` key

### Unit Test Scenarios

- [ ] `frontmatter.parse_frontmatter_doc`: document without `type:` field → returns dict with keys `{"id", "title", "summary"}` and no `"type"` key
- [ ] `frontmatter.parse_frontmatter_doc`: document with legacy `type: entity` → returns dict with keys `{"id", "title", "summary"}` and no `"type"` key (silently ignored)
- [ ] `frontmatter.parse_frontmatter_doc`: document missing `id` → returns `None`
- [ ] `frontmatter.parse_frontmatter_doc`: document missing `title` → returns `None`
- [ ] `frontmatter.parse_frontmatter_doc`: document missing `summary` → returns `None`
- [ ] `frontmatter.parse_frontmatter_doc`: `extra_fields=("related",)` still works — `"related"` appears in returned dict
- [ ] `frontmatter.parse_frontmatter_doc_full`: document without `type:` → returns dict with `body` key and no `"type"` key
- [ ] `frontmatter.parse_frontmatter_doc_full`: document with legacy `type:` → `"type"` absent from returned dict
- [ ] `frontmatter.parse_frontmatter_doc`: calling with `exclude_type` keyword argument raises `TypeError` (parameter removed)

---

## Out of Scope

- Changes to `codex.py`, `artifact.py`, `models.py`, or `cli.py` — covered by US-2 through US-5
- Migrating live `.lore/codex/` documents (parallel quest q-bbbf)
- Stripping `type:` from default templates in `src/lore/defaults/` — covered by US-6

---

## References

- PRD: `lore codex show remove-type-field-prd` (FR-1, FR-2, FR-3, FR-4; WF-1)
- Tech Spec: `lore codex show remove-type-field-tech-spec`
- `lore codex show tech-arch-frontmatter`

---

## Tech Notes

_(Filled by Tech Lead in tech-notes-draft and tech-notes-final phases — BA must not edit this section)_

### Implementation Approach

- **Files to create:** None
- **Files to modify:**
  - `src/lore/frontmatter.py` — Remove `"type"` from `_REQUIRED_FIELDS` (line 12: change to `("id", "title", "summary")`); remove `exclude_type` parameter from `parse_frontmatter_doc()` and `parse_frontmatter_doc_full()`; remove `type` key from all returned dicts in `parse_frontmatter_doc_full` (lines 93–99); remove `exclude_type` guard logic (lines 49–50, 88–89)
- **Schema changes:** None — frontmatter-only change, no DB migration required (see `tech-arch-frontmatter`)
- **Dependencies:** None — this is the foundational story; all others (US-2 through US-5) depend on it being complete first

**TDD cycle:** Red mission (write failing tests in `test_frontmatter.py`) → Green mission (update `frontmatter.py`) → Commit mission

### Test File Locations

| Type | Path | Notes |
|------|------|-------|
| E2E | `tests/e2e/test_codex.py` | codex show without type field; legacy type field silently ignored |
| Unit | `tests/unit/test_frontmatter.py` | frontmatter module coverage — update `_make_doc` helper, add type-absence assertions, add exclude_type TypeError test |

### Test Stubs

```python
# =============================================================================
# tests/e2e/test_codex.py — new stubs for US-1
# =============================================================================

# E2E Scenario 1: Document without type field parses and shows successfully
# conceptual-workflows-codex step: lore codex show resolves id via scan_codex → read_document
def test_codex_show_doc_without_type_field_exits_0(runner, project_dir):
    # Given: .md file with frontmatter id/title/summary only (no type: line)
    # When: lore codex show <id>
    # Then: exit code 0; document body is printed; no error message
    pass


# E2E Scenario 2: Document with legacy type: field is silently accepted (no type key in output)
# conceptual-workflows-codex step: lore codex list --json returns scan_codex results
def test_codex_list_json_legacy_type_field_silently_ignored(runner, project_dir):
    # Given: .md file with frontmatter id/title/summary/type: conceptual
    # When: lore codex list --json
    # Then: exit 0; record for that document appears; record has no "type" key
    pass


# E2E Scenario 3: exclude_type parameter removed — callers use no special argument
# conceptual-workflows-codex step: scan_codex uses parse_frontmatter_doc with default args
def test_parse_frontmatter_doc_no_exclude_type_param(tmp_path):
    # Given: a valid doc with id/title/summary; no type: line
    # When: parse_frontmatter_doc(path, required_fields=("id","title","summary")) — no exclude_type
    # Then: no TypeError raised; result has keys {"id","title","summary"} and no "type" key
    pass


# =============================================================================
# tests/unit/test_frontmatter.py — new/updated stubs for US-1
# =============================================================================

# Unit: _make_doc helper — updated to omit type: line
# remove-type-field-us-1 Unit Test Scenarios — _make_doc helper omits type:
def _make_doc(tmp_path, extra_frontmatter: str = "", name: str = "doc.md"):
    # Updated: no type: line in base frontmatter
    # base has id/title/summary only
    pass


# Unit: document without type field returns dict without "type" key
# remove-type-field-us-1 Unit Test Scenarios — parse_frontmatter_doc no type: → no "type" in result
def test_parse_frontmatter_doc_no_type_field_returns_no_type_key(tmp_path):
    # Given: doc with id/title/summary, no type:
    # When: parse_frontmatter_doc(path)
    # Then: result is not None; "type" not in result; set(result.keys()) >= {"id","title","summary"}
    pass


# Unit: document with legacy type: entity returns dict without "type" key (silently ignored)
# remove-type-field-us-1 Unit Test Scenarios — legacy type: entity → "type" absent from result
def test_parse_frontmatter_doc_legacy_type_field_absent_from_result(tmp_path):
    # Given: doc with id/title/summary/type: entity
    # When: parse_frontmatter_doc(path)
    # Then: result is not None; "type" not in result
    pass


# Unit: document missing id returns None
# remove-type-field-us-1 Unit Test Scenarios — missing id → None
def test_parse_frontmatter_doc_missing_id_returns_none(tmp_path):
    # Given: doc with title/summary only (no id)
    # When: parse_frontmatter_doc(path)
    # Then: result is None
    pass


# Unit: document missing title returns None
# remove-type-field-us-1 Unit Test Scenarios — missing title → None
def test_parse_frontmatter_doc_missing_title_returns_none(tmp_path):
    # Given: doc with id/summary only (no title)
    # When: parse_frontmatter_doc(path)
    # Then: result is None
    pass


# Unit: document missing summary returns None
# remove-type-field-us-1 Unit Test Scenarios — missing summary → None
def test_parse_frontmatter_doc_missing_summary_returns_none(tmp_path):
    # Given: doc with id/title only (no summary)
    # When: parse_frontmatter_doc(path)
    # Then: result is None
    pass


# Unit: extra_fields=("related",) still works after type removal
# remove-type-field-us-1 Unit Test Scenarios — extra_fields=("related",) still works
def test_parse_frontmatter_doc_extra_fields_related_still_works(tmp_path):
    # Given: doc with id/title/summary and related: [doc-b]
    # When: parse_frontmatter_doc(path, extra_fields=("related",))
    # Then: result["related"] == ["doc-b"]
    pass


# Unit: parse_frontmatter_doc_full returns body key and no "type" key
# remove-type-field-us-1 Unit Test Scenarios — parse_frontmatter_doc_full no type: → body present, no "type"
def test_parse_frontmatter_doc_full_no_type_returns_body(tmp_path):
    # Given: doc with id/title/summary, no type:
    # When: parse_frontmatter_doc_full(path)
    # Then: result is not None; "body" in result; "type" not in result
    pass


# Unit: parse_frontmatter_doc_full with legacy type: returns no "type" key
# remove-type-field-us-1 Unit Test Scenarios — legacy type: → "type" absent from full result
def test_parse_frontmatter_doc_full_legacy_type_absent(tmp_path):
    # Given: doc with id/title/summary/type: workflow
    # When: parse_frontmatter_doc_full(path)
    # Then: result is not None; "type" not in result
    pass


# Unit: calling parse_frontmatter_doc with exclude_type raises TypeError
# remove-type-field-us-1 Unit Test Scenarios — exclude_type keyword raises TypeError (param removed)
def test_parse_frontmatter_doc_exclude_type_raises_type_error(tmp_path):
    # Given: a valid doc file
    # When: parse_frontmatter_doc(path, exclude_type="transient-marker")
    # Then: TypeError is raised (parameter no longer exists)
    import pytest
    with pytest.raises(TypeError):
        parse_frontmatter_doc(path, exclude_type="transient-marker")
    pass
```

### Complexity Estimate

M — Touches one module (`src/lore/frontmatter.py`) but is the foundational change that all other stories depend on. The `exclude_type` removal touches two function signatures and two internal guard blocks. Test updates add nine new unit stubs and update the `_make_doc` helper.
