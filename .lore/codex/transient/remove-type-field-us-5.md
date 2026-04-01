---
id: remove-type-field-us-5
type: user-story
title: "US-5: Remove TYPE column from CLI output"
summary: As a CLI user or agent, I want lore artifact list and all codex commands to output records without a TYPE column or type key, so that the terminal output and JSON are clean and consistent with the simplified data contract.
status: draft
---

## Metadata

- **ID:** US-5
- **Status:** final
- **Epic:** CLI Output Simplification
- **Author:** Business Analyst
- **Date:** 2026-03-27
- **PRD:** `lore codex show remove-type-field-prd`
- **Tech Spec:** `lore codex show remove-type-field-tech-spec`

---

## Story

As a developer or agent using the Lore CLI, I want `lore artifact list` to display a four-column table (`ID | GROUP | TITLE | SUMMARY`) and all JSON output from codex and artifact commands to omit the `"type"` key, so that the output is minimal and matches the simplified data contract.

## Context

The PRD (FR-16, FR-17, FR-18) requires removing the `TYPE` column from `lore artifact list` text output, removing `type` from `lore artifact list --json` records, and removing `type` from all codex command JSON output (`lore codex list`, `lore codex search`, `lore codex map`, `lore codex chaos`). The Tech Spec confirms `lore codex search` text output drops `TYPE` and keeps three columns: `ID | TITLE | SUMMARY`. The Tech Spec also notes that `test_cli_codex_list.py` type-absence tests are already written and will be promoted to green by this change. This story covers PRD Workflows WF-2 and WF-5.

---

## Acceptance Criteria

### E2E Scenarios

#### Scenario 1: lore artifact list shows four-column header without TYPE

**Given** a project with at least one artifact template
**When** the user runs `lore artifact list`
**Then** the command exits 0; the output header line contains exactly the columns `ID`, `GROUP`, `TITLE`, `SUMMARY` in that order; no `TYPE` column is present anywhere in the output

#### Scenario 2: lore artifact list --json records have no type key

**Given** a project with at least one artifact template
**When** the user runs `lore artifact list --json`
**Then** the command exits 0; each record in the `"artifacts"` array has exactly the keys `{"id", "group", "title", "summary"}` with no `"type"` key

#### Scenario 3: lore codex list --json records have no type key

**Given** a project with at least one codex document
**When** the user runs `lore codex list --json`
**Then** the command exits 0; each record in the `"documents"` array has no `"type"` key; the existing tests in `tests/e2e/test_cli_codex_list.py` that assert `"type" not in record` now pass (promoted from FAILS to green)

#### Scenario 4: lore codex search text output has three columns without TYPE

**Given** a project with a codex document containing the word "frontmatter"
**When** the user runs `lore codex search "frontmatter"`
**Then** the command exits 0; the output header contains exactly `ID`, `TITLE`, `SUMMARY` with no `TYPE` or `GROUP` column

#### Scenario 5: lore codex search --json records have no type key

**Given** a project with a codex document containing the word "frontmatter"
**When** the user runs `lore codex search "frontmatter" --json`
**Then** the command exits 0; running `lore codex search "frontmatter" --json | python3 -c "import sys,json; d=json.load(sys.stdin); assert 'type' not in d['documents'][0]"` exits 0

#### Scenario 6: lore codex map --json records have no type key

**Given** a codex document `doc-a`
**When** the user runs `lore codex map doc-a --json`
**Then** the command exits 0; the root record has exactly the keys `{"id", "title", "summary", "body"}` with no `"type"` key

#### Scenario 7: lore codex chaos --json records have no type key

**Given** a project with multiple codex documents
**When** the user runs `lore codex chaos <id> --threshold 50 --json`
**Then** the command exits 0; each record in the output has exactly the keys `{"id", "title", "summary"}` with no `"type"` key

### Unit Test Scenarios

- [ ] `cli.py` artifact list rendering: text output header is `ID  GROUP  TITLE  SUMMARY` with no `TYPE` column
- [ ] `cli.py` artifact list JSON: each record dict has no `"type"` key
- [ ] `cli.py` codex list JSON: each record dict has no `"type"` key
- [ ] `cli.py` codex search text: header is `ID  TITLE  SUMMARY` (three columns, no `TYPE`)
- [ ] `cli.py` codex search JSON: each record dict has no `"type"` key
- [ ] `cli.py` codex map JSON: root record dict key set is `{"id", "title", "summary", "body"}`
- [ ] `cli.py` codex chaos JSON: each record dict key set is `{"id", "title", "summary"}`

---

## Out of Scope

- Changes to `codex.py`, `artifact.py`, `models.py`, or `frontmatter.py` data shapes — covered by US-1 through US-4
- `lore artifact show` (single artifact display) — not listed in PRD scope
- Any Citadel UI changes

---

## References

- PRD: `lore codex show remove-type-field-prd` (FR-16, FR-17, FR-18; WF-2, WF-5)
- Tech Spec: `lore codex show remove-type-field-tech-spec`
- `lore codex show conceptual-workflows-artifact-list`
- `lore codex show conceptual-workflows-codex`

---

## Tech Notes

_(Filled by Tech Lead in tech-notes-draft and tech-notes-final phases — BA must not edit this section)_

### Implementation Approach

- **Files to create:** None
- **Files to modify:**
  - `src/lore/cli.py`:
    - `artifact_list()` (~line 2456): remove `"type": a["type"]` from JSON dict (lines 2471–2475); change text rows to `[a["id"], a["group"], a["title"], a["summary"]]` (line 2486); change headers to `["ID", "GROUP", "TITLE", "SUMMARY"]` (line 2487)
    - `codex_search()` (~line 2272): remove `"type": d["type"]` from JSON dict (lines 2286–2290); remove `col_type` variable and `TYPE` column from text output (lines 2302–2311); change text header to `ID | TITLE | SUMMARY` (three columns)
    - `codex_chaos()` (~line 2406): change `headers` to `["ID", "TITLE", "SUMMARY"]` and `rows` to omit `doc["type"]` (lines 2437–2441)
    - No changes needed to `codex_list()` (covered by separate quest codex-list-group), `codex_map()`, or `codex_show()` — the map and show JSON output already passes through the dicts from `codex.py` which will have no `"type"` after US-2
- **Schema changes:** None
- **Dependencies:** US-1 through US-4 must be complete so the underlying dict shapes no longer contain `"type"` before the CLI removes its references

**TDD cycle:** Red mission (write failing tests in `test_artifact_list.py`, `test_codex.py`, `test_codex_chaos.py`) → Green mission (update `cli.py`) → Commit mission

Note: `tests/unit/test_cli_codex_list.py` already contains tests asserting `"type" not in record` (marked FAILS). These are promoted to green by this story and require no new stubs — they will pass once US-2 and this story's CLI changes are applied.

### Test File Locations

| Type | Path | Notes |
|------|------|-------|
| E2E | `tests/e2e/test_artifact_list.py` | artifact list text (no TYPE col) and JSON (no type key) |
| E2E | `tests/e2e/test_codex.py` | codex list, search JSON — no "type" key |
| E2E | `tests/e2e/test_codex_map.py` | codex map JSON key-set assertion |
| E2E | `tests/e2e/test_codex_chaos.py` | codex chaos text (no TYPE col) and JSON (no type key) |
| Unit | `tests/unit/test_cli_codex_list.py` | promoted from FAILS to green — no new stubs needed |

### Test Stubs

```python
# =============================================================================
# tests/e2e/test_artifact_list.py — new stubs for US-5
# =============================================================================

# E2E Scenario 1: lore artifact list header has four columns without TYPE
# conceptual-workflows-artifact-list step: CLI renders artifact table via _format_table
def test_artifact_list_text_header_no_type_column(runner, project_dir):
    # Given: project with at least one artifact template
    # When: lore artifact list
    # Then: exit 0; header contains ID, GROUP, TITLE, SUMMARY; no TYPE column present
    pass


# E2E Scenario 2: lore artifact list --json records have no type key
# conceptual-workflows-artifact-list step: CLI artifact_list JSON path omits type key
def test_artifact_list_json_records_no_type_key(runner, project_dir):
    # Given: project with at least one artifact template
    # When: lore artifact list --json
    # Then: exit 0; set(record.keys()) == {"id","group","title","summary"} for each record
    pass


# =============================================================================
# tests/e2e/test_codex.py — new stubs for US-5
# =============================================================================

# E2E Scenario 3: lore codex list --json records have no type key (promoted FAILS test)
# conceptual-workflows-codex step: codex_list JSON path emits scan_codex results
# Note: test_cli_codex_list.py already has this — new E2E stub aligns coverage
def test_codex_list_json_no_type_key_e2e(runner, project_dir):
    # Given: project with codex doc
    # When: lore codex list --json
    # Then: exit 0; no record in "documents" has "type" key
    pass


# E2E Scenario 4: lore codex search text output has three columns without TYPE
# conceptual-workflows-codex step: codex_search renders text table with ID/TITLE/SUMMARY
def test_codex_search_text_header_no_type_column(runner, project_dir):
    # Given: codex doc containing "frontmatter" in summary
    # When: lore codex search "frontmatter"
    # Then: exit 0; header contains ID, TITLE, SUMMARY; no TYPE or GROUP column
    pass


# E2E Scenario 5: lore codex search --json records have no type key
# conceptual-workflows-codex step: codex_search JSON path omits type key
def test_codex_search_json_no_type_key(runner, project_dir):
    # Given: codex doc containing "frontmatter" in summary
    # When: lore codex search "frontmatter" --json
    # Then: exit 0; no record in "documents" has "type" key
    pass


# =============================================================================
# tests/e2e/test_codex_map.py — new stubs for US-5
# =============================================================================

# E2E Scenario 6: lore codex map --json root record has no type key
# conceptual-workflows-codex-map step: codex_map JSON path passes map_documents results directly
def test_codex_map_json_root_record_no_type_key(project_dir, runner):
    # Given: codex doc doc-a
    # When: lore codex map doc-a --json
    # Then: exit 0; root record key set == {"id","title","summary","body"}; no "type" key
    pass


# =============================================================================
# tests/e2e/test_codex_chaos.py — new stubs for US-5
# =============================================================================

# E2E Scenario 7: lore codex chaos --json records have no type key
# conceptual-workflows-codex-chaos step: codex_chaos JSON path passes chaos_documents results
def test_codex_chaos_json_records_no_type_key(runner, project_dir):
    # Given: project with multiple codex docs
    # When: lore codex chaos <id> --threshold 50 --json
    # Then: exit 0; set(record.keys()) == {"id","title","summary"} for each record
    pass


# Unit (cli.py) — artifact list text header is ID GROUP TITLE SUMMARY
# conceptual-workflows-artifact-list step: _format_table called with four-column headers
def test_artifact_list_text_uses_four_column_header(runner, project_dir):
    # Given: project with one known artifact
    # When: lore artifact list
    # Then: output matches _format_table(["ID","GROUP","TITLE","SUMMARY"], rows) exactly
    pass


# Unit (cli.py) — codex search text header is ID TITLE SUMMARY (three columns)
# conceptual-workflows-codex step: codex_search text output uses three-column header
def test_codex_search_text_three_column_header(runner, project_dir):
    # Given: codex doc with "frontmatter" in summary
    # When: lore codex search "frontmatter"
    # Then: header line contains ID, TITLE, SUMMARY; no TYPE; no GROUP
    pass


# Unit (cli.py) — codex chaos text uses ID TITLE SUMMARY (three columns)
# conceptual-workflows-codex-chaos step: chaos text output _format_table with three-column headers
def test_codex_chaos_text_three_column_header(runner, project_dir):
    # Given: seed doc with no related docs
    # When: lore codex chaos <id> --threshold 100
    # Then: header contains ID, TITLE, SUMMARY; no TYPE
    pass
```

### Complexity Estimate

M — Three CLI functions in `src/lore/cli.py` (`artifact_list`, `codex_search`, `codex_chaos`). Each function has both a JSON path and a text path to update. The `codex_list` JSON change is already handled by the `codex-list-group` quest's existing `test_cli_codex_list.py` tests which are promoted to green here.
