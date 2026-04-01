---
id: remove-type-field-us-2
type: user-story
title: "US-2: Remove type from codex scanning and traversal"
summary: As a developer or agent, I want all codex scan, search, map, and chaos functions to return dicts without a type key, so that downstream consumers receive a clean, minimal record shape.
status: draft
---

## Metadata

- **ID:** US-2
- **Status:** final
- **Epic:** Codex Module Cleanup
- **Author:** Business Analyst
- **Date:** 2026-03-27
- **PRD:** `lore codex show remove-type-field-prd`
- **Tech Spec:** `lore codex show remove-type-field-tech-spec`

---

## Story

As a Realm agent or CLI user, I want `scan_codex`, `read_document`, `search_documents`, `map_documents`, and `chaos_documents` to return records without a `"type"` key, so that the data contract is minimal and no downstream code needs to handle a redundant field.

## Context

The PRD (FR-5 through FR-8) requires removing `type` from all dict shapes returned by `codex.py`. Additionally, the `exclude_type` parameter and all `exclude_type="transient-marker"` call sites must be removed — documents in `transient/` are regular documents going forward. The Tech Spec notes that `codex.py`'s local `_REQUIRED_FIELDS` copy should also be deleted in favour of delegating to `frontmatter.py`. This story covers PRD Workflow WF-1 (agent writes a codex doc and sees no `type` key in the result) and WF-5 (codex commands return JSON without `type`).

---

## Acceptance Criteria

### E2E Scenarios

#### Scenario 1: lore codex list --json records have no type key

**Given** a project with at least one codex document (with or without a legacy `type:` field)
**When** the user runs `lore codex list --json`
**Then** the command exits 0; each record in the `"documents"` array has no `"type"` key; each record has exactly the keys `{"id", "title", "summary", "group", "path"}`

#### Scenario 2: lore codex search --json records have no type key

**Given** a project with a codex document containing the word "frontmatter" in its summary
**When** the user runs `lore codex search "frontmatter" --json`
**Then** the command exits 0; each record in the `"documents"` array has no `"type"` key; running `lore codex search "frontmatter" --json | python3 -c "import sys,json; d=json.load(sys.stdin); assert 'type' not in d['documents'][0]"` exits 0

#### Scenario 3: lore codex map --json record has no type key

**Given** a codex document `doc-a` that links to `doc-b` in a `related:` frontmatter field
**When** the user runs `lore codex map doc-a --json`
**Then** the command exits 0; the root document record has exactly the keys `{"id", "title", "summary", "body"}` and no `"type"` key; related document records also have no `"type"` key

#### Scenario 4: lore codex chaos --json records have no type key

**Given** a project with multiple codex documents
**When** the user runs `lore codex chaos <id> --threshold 50 --json`
**Then** the command exits 0; each record in the output has exactly the keys `{"id", "title", "summary"}` and no `"type"` key

#### Scenario 5: Previously transient-marker excluded document is now included in scans

**Given** a document in `.lore/codex/transient/` that previously had `type: transient-marker` in its frontmatter
**When** the user runs `lore codex list --json`
**Then** the document appears in the results (it is no longer excluded); the record has no `"type"` key

### Unit Test Scenarios

- [ ] `codex.scan_codex`: returns dicts with keys `{"id", "title", "summary", "group", "path"}` — no `"type"`
- [ ] `codex.scan_codex`: a document previously excluded via `exclude_type="transient-marker"` is now included
- [ ] `codex.scan_codex`: files missing `id`, `title`, or `summary` are still skipped (returns empty list)
- [ ] `codex.read_document`: returns dict with keys `{"id", "title", "summary", "group", "body"}` — no `"type"`
- [ ] `codex.search_documents`: returns dicts with keys `{"id", "title", "summary"}` — no `"type"`
- [ ] `codex.map_documents`: returned root record key set is `{"id", "title", "summary", "body"}` — no `"type"`
- [ ] `codex.map_documents`: a previously-transient-marker doc is now traversable as a related document
- [ ] `codex.chaos_documents`: returned dict key set is `{"id", "title", "summary"}` — no `"type"`
- [ ] `codex.chaos_documents`: test `test_chaos_documents_excludes_transient_marker_type` is deleted (sentinel gone)
- [ ] `codex.map_documents`: test `test_map_documents_transient_marker_excluded` is deleted (sentinel gone)

---

## Out of Scope

- Changes to `frontmatter.py` — covered by US-1
- Changes to `artifact.py` — covered by US-3
- CLI text output changes — covered by US-5
- Live document migration (q-bbbf)

---

## References

- PRD: `lore codex show remove-type-field-prd` (FR-5, FR-6, FR-7, FR-8; WF-1, WF-5)
- Tech Spec: `lore codex show remove-type-field-tech-spec`
- `lore codex show conceptual-workflows-codex`

---

## Tech Notes

_(Filled by Tech Lead in tech-notes-draft and tech-notes-final phases — BA must not edit this section)_

### Implementation Approach

- **Files to create:** None
- **Files to modify:**
  - `src/lore/codex.py` — Delete module-level `_REQUIRED_FIELDS` (line 11); remove `exclude_type` parameter and all `exclude_type="transient-marker"` call sites from `_parse_doc_robust()`, `scan_codex()`, `read_document()`, `_scan_codex_robust()`, `map_documents()`, and `chaos_documents()`; remove `"type"` from all returned dict shapes in `search_documents()` (lines 96–101), `read_document()` (lines 121–127), `map_documents()` (lines 212–218), and `chaos_documents()` (lines 295–300, 327–331); update `_parse_doc_robust()` to use `frontmatter._REQUIRED_FIELDS` instead of the local copy
- **Schema changes:** None
- **Dependencies:** US-1 must be complete (frontmatter `_REQUIRED_FIELDS` updated, `exclude_type` removed from `parse_frontmatter_doc`)

**TDD cycle:** Red mission (write failing tests in `test_codex.py`, `test_codex_map.py`, `test_codex_chaos.py`) → Green mission (update `codex.py`) → Commit mission

### Test File Locations

| Type | Path | Notes |
|------|------|-------|
| E2E | `tests/e2e/test_codex.py` | codex list, search JSON — no "type" key |
| E2E | `tests/e2e/test_codex_map.py` | codex map JSON key-set assertion |
| E2E | `tests/e2e/test_codex_chaos.py` | codex chaos JSON key-set assertion |
| Unit | `tests/unit/test_codex.py` | scan_codex, read_document, search, map, chaos — update `_write_doc` helper, delete transient-marker tests |

### Test Stubs

```python
# =============================================================================
# tests/e2e/test_codex.py — new stubs for US-2
# =============================================================================

# E2E Scenario 1: lore codex list --json records have no type key
# conceptual-workflows-codex step: lore codex list --json returns scan_codex results with group
def test_codex_list_json_no_type_key(runner, project_dir):
    # Given: project with at least one codex doc (with or without legacy type: field)
    # When: lore codex list --json
    # Then: exit 0; each record in "documents" has no "type" key;
    #       set(record.keys()) == {"id","title","summary","group","path"} (or subset without path)
    pass


# E2E Scenario 2: lore codex search --json records have no type key
# conceptual-workflows-codex step: search_documents returns dicts without "type"
def test_codex_search_json_no_type_key(runner, project_dir):
    # Given: project with codex doc containing "frontmatter" in summary
    # When: lore codex search "frontmatter" --json
    # Then: exit 0; each record in "documents" has no "type" key
    pass


# E2E Scenario 5: Previously transient-marker excluded document is now included in scans
# conceptual-workflows-codex step: scan_codex walks all .md files including transient/
def test_codex_list_transient_marker_doc_now_included(runner, project_dir):
    # Given: doc in .lore/codex/transient/ with legacy type: transient-marker in frontmatter
    # When: lore codex list --json
    # Then: document appears in results (not excluded); record has no "type" key
    pass


# =============================================================================
# tests/e2e/test_codex_map.py — new stubs for US-2
# =============================================================================

# E2E Scenario 3: lore codex map --json record has no type key
# conceptual-workflows-codex-map step: map_documents returns dicts with keys id/title/summary/body
def test_codex_map_json_no_type_key(project_dir, runner):
    # Given: codex doc doc-a that links to doc-b in related: field
    # When: lore codex map doc-a --json
    # Then: exit 0; root record key set == {"id","title","summary","body"}; no "type" key
    pass


# =============================================================================
# tests/e2e/test_codex_chaos.py — new stubs for US-2
# =============================================================================

# E2E Scenario 4: lore codex chaos --json records have no type key
# conceptual-workflows-codex-chaos step: chaos_documents returns dicts with id/title/summary only
def test_codex_chaos_json_no_type_key(runner, project_dir):
    # Given: project with multiple codex docs
    # When: lore codex chaos <id> --threshold 50 --json
    # Then: exit 0; each record key set == {"id","title","summary"}; no "type" key
    pass


# =============================================================================
# tests/unit/test_codex.py — new/updated stubs for US-2
# =============================================================================

# Unit: _write_doc helper — updated to omit doc_type param and type: line
# remove-type-field-us-2 Unit Test Scenarios — _write_doc() helper loses doc_type param
def _write_doc(codex_dir, doc_id, *, related=None, omit_related=False):
    # Updated: no doc_type parameter; no type: line in written frontmatter
    pass


# Unit: scan_codex returns dicts with no "type" key
# conceptual-workflows-codex step: scan_codex walks codex_dir and returns record dicts
def test_scan_codex_no_type_in_result(tmp_path):
    # Given: valid codex doc with id/title/summary (no type:)
    # When: scan_codex(codex_dir)
    # Then: each dict has no "type" key; set(d.keys()) == {"id","title","summary","group","path"}
    pass


# Unit: scan_codex — previously transient-marker excluded doc is now included
# conceptual-workflows-codex step: scan_codex no longer excludes by type value
def test_scan_codex_former_transient_marker_doc_included(tmp_path):
    # Given: doc with type: transient-marker in frontmatter (legacy)
    # When: scan_codex(codex_dir)
    # Then: that document appears in results (not excluded)
    pass


# Unit: scan_codex — files missing id/title/summary are still skipped
# conceptual-workflows-codex step: scan_codex skips files with missing required fields
def test_scan_codex_missing_required_fields_skipped(tmp_path):
    # Given: doc missing summary field
    # When: scan_codex(codex_dir)
    # Then: result is empty list
    pass


# Unit: read_document returns dict with no "type" key
# conceptual-workflows-codex step: read_document returns full record dict
def test_read_document_no_type_in_result(tmp_path):
    # Given: valid codex doc
    # When: read_document(codex_dir, doc_id)
    # Then: result key set == {"id","title","summary","group","body"}; no "type" key
    pass


# Unit: search_documents returns dicts with no "type" key
# conceptual-workflows-codex step: search_documents filters scan_codex results
def test_search_documents_no_type_in_result(tmp_path):
    # Given: codex doc with "frontmatter" in summary
    # When: search_documents(codex_dir, "frontmatter")
    # Then: each dict key set == {"id","title","summary"}; no "type" key
    pass


# Unit: map_documents root record key set has no "type"
# conceptual-workflows-codex-map step: map_documents returns full records in BFS order
def test_map_documents_root_record_no_type(tmp_path):
    # Given: valid codex doc
    # When: map_documents(codex_dir, doc_id, depth=0)
    # Then: root record key set == {"id","title","summary","body"}; no "type" key
    pass


# Unit: map_documents — formerly transient-marker doc is now traversable
# conceptual-workflows-codex-map step: map_documents uses _scan_codex_robust which no longer excludes
def test_map_documents_former_transient_marker_doc_traversable(tmp_path):
    # Given: doc-a related to former-marker-doc (which had type: transient-marker)
    # When: map_documents(codex_dir, "doc-a", depth=1)
    # Then: former-marker-doc appears in result
    pass


# Unit: chaos_documents returned dict key set has no "type"
# conceptual-workflows-codex-chaos step: chaos_documents appends dicts with id/title/summary
def test_chaos_documents_no_type_in_result(tmp_path):
    # Given: valid codex doc as seed
    # When: chaos_documents(project_root, doc_id, threshold=100)
    # Then: each dict key set == {"id","title","summary"}; no "type" key
    pass


# Unit: test_chaos_documents_excludes_transient_marker_type — DELETED (sentinel gone)
# (Remove this test entirely — do not stub it)

# Unit: test_map_documents_transient_marker_excluded — DELETED (sentinel gone)
# (Remove this test entirely — do not stub it)
```

### Complexity Estimate

M — Multiple functions in one module (`src/lore/codex.py`). Requires deleting the local `_REQUIRED_FIELDS`, removing six `exclude_type` call sites across five functions, and stripping `"type"` from four returned dict shapes. Deleting two tests and updating the `_write_doc` helper is mechanical.
