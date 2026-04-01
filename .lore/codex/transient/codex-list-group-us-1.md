---
id: codex-list-group-us-1
feature: codex-list-group
status: final
title: Display GROUP instead of TYPE in lore codex list tabular output
summary: As a developer, I want lore codex list to display GROUP instead of TYPE so I can see which directory category each document belongs to, consistent with all other entity list commands.
---

## Metadata

- **ID:** US-1
- **Status:** final
- **Epic:** codex-list-group
- **Author:** Business Analyst
- **Date:** 2026-03-27
- **PRD:** `lore codex show codex-list-group-prd`
- **Tech Spec:** `lore codex show codex-list-group-tech-spec`

---

## Story

As a developer, I want `lore codex list` to display GROUP instead of TYPE so that I can see which directory category each document belongs to in a layout consistent with all other entity list commands.

## Context

This story fulfills the PRD workflow "Listing codex documents — Developer". Currently `lore codex list` outputs a TYPE column using manual f-string formatting, diverging from every other entity list command (`lore knight list`, `lore doctrine list`, `lore watcher list`) which all output ID, GROUP, TITLE, SUMMARY via the shared `_format_table` helper. A developer who works with multiple entity types expects a uniform four-column table. This story replaces the TYPE column with GROUP, switches the renderer to `_format_table`, and derives GROUP from the document's directory path under `.lore/codex/` using the existing `derive_group()` function.

---

## Acceptance Criteria

Every criterion is testable by running `lore codex list` in a project that contains at least one codex document stored in a subdirectory and one stored at the root of `.lore/codex/`.

### E2E Scenarios

#### Scenario 1: Tabular output displays four columns — ID, GROUP, TITLE, SUMMARY

**Given** a lore project containing at least one codex document stored in a subdirectory of `.lore/codex/` (e.g. `.lore/codex/tech-arch/source-layout.md`)
**When** the developer runs `lore codex list`
**Then** the first output line is a header containing exactly the columns `ID`, `GROUP`, `TITLE`, `SUMMARY` in that order, and each subsequent row displays the document's codex ID, its group (subdirectory name, e.g. `tech-arch`), its title, and a truncated summary — column widths padded consistently via `_format_table`

#### Scenario 2: TYPE column is absent from tabular output

**Given** a lore project with one or more codex documents
**When** the developer runs `lore codex list`
**Then** the output does not contain the word `TYPE` as a column header, and no row contains a raw YAML `type:` field value in the position formerly occupied by the TYPE column

#### Scenario 3: Document stored at root of `.lore/codex/` displays empty GROUP

**Given** a lore project containing a codex document stored directly under `.lore/codex/` (no subdirectory, e.g. `.lore/codex/001.md`)
**When** the developer runs `lore codex list`
**Then** the GROUP column for that document is empty (blank cell) and no error is raised — the command exits with code 0

#### Scenario 4: Output structure matches `lore knight list`

**Given** a lore project with codex documents in subdirectories
**When** the developer runs `lore codex list`
**Then** the tabular structure (four columns, consistent padding, header underline behaviour) is visually identical to the output produced by `lore knight list` on the same project

#### Scenario 5: Empty codex shows fallback message

**Given** a lore project with no codex documents
**When** the developer runs `lore codex list`
**Then** the output is exactly `No codex documents found.` and the command exits with code 0

### Unit Test Scenarios

- [ ] `codex_list` handler: header line output by `_format_table` contains `"GROUP"` and does not contain `"TYPE"`
- [ ] `codex_list` handler: each row is `[d["id"], derive_group(d["path"], codex_dir), d["title"], d["summary"]]`
- [ ] `codex_list` handler: GROUP is an empty string for a document at the root of `.lore/codex/` — no exception raised
- [ ] `codex_list` handler: GROUP is the subdirectory name for a document one level deep (e.g. `tech-arch`)
- [ ] `codex_list` handler: output is produced via `_format_table` (not manual f-string formatting)
- [ ] `codex_list` handler: prints `"No codex documents found."` when `scan_codex` returns an empty list

---

## Out of Scope

- Changes to `lore codex list --json` output (covered by US-2)
- Changes to `derive_group` in `paths.py`
- Changes to `_format_table` in `cli.py`
- Changes to `scan_codex` in `codex.py`
- Changes to `lore codex map` or any other codex subcommand
- Adding filtering or sorting options to `lore codex list`
- Updating the `conceptual-workflows-codex` documentation (post-MVP)

---

## References

- PRD: `lore codex show codex-list-group-prd`
- Tech Spec: `lore codex show codex-list-group-tech-spec`
- Workflow reference (gold standard): `lore codex show conceptual-workflows-knight-list`
- Current behaviour: `lore codex show conceptual-workflows-codex`

---

## Tech Notes

_(Filled by Tech Lead in tech-notes-draft and tech-notes-final phases — BA must not edit this section)_

### Implementation Approach

**File to change:** `src/lore/cli.py` — this is the only file that changes.

**Function to modify:** `codex_list` (line 2228)

**Changes:**
1. Replace the manual f-string column-width table with `_format_table(["ID", "GROUP", "TITLE", "SUMMARY"], rows)` (already implemented at line 74 of `cli.py`).
2. Call `paths.derive_group(d["path"], codex_dir)` per document to compute GROUP — `derive_group` is already implemented at line 44 of `src/lore/paths.py` with signature `derive_group(filepath: Path, base_dir: Path) -> str`.
3. Build `codex_dir` from `paths.codex_dir(project_root)` in the handler.
4. Each table row becomes `[d["id"], paths.derive_group(d["path"], codex_dir), d["title"], d["summary"]]`.

No changes to `src/lore/paths.py`, `src/lore/codex.py`, or `_format_table`. `scan_codex` already returns `path` in every record.

### Test File Locations

| Type | Path | Notes |
|------|------|-------|
| E2E | `tests/e2e/test_codex_list_group_e2e.py` | New file; existing codex list E2E tests live in `tests/e2e/test_codex.py` |
| Unit | `tests/unit/test_cli_codex_list.py` | New file; no existing unit file covers `codex_list` handler |

### Test Stubs

```python
# tests/e2e/test_codex_list_group_e2e.py


def test_codex_list_tabular_header_contains_group_not_type(runner, project_dir):
    # Source: conceptual-workflows-codex (Steps — List, step 2: render table with ID, GROUP, TITLE, SUMMARY)
    pass


def test_codex_list_tabular_row_shows_subdirectory_as_group(runner, project_dir):
    # Source: conceptual-workflows-codex (Steps — List, step 2: GROUP derived via derive_group)
    pass


def test_codex_list_type_column_absent_from_tabular_output(runner, project_dir):
    # Source: conceptual-workflows-codex (Steps — List, step 2: columns are ID, GROUP, TITLE, SUMMARY — TYPE is not listed)
    pass


def test_codex_list_root_level_document_renders_empty_group(runner, project_dir):
    # Source: conceptual-workflows-codex (Steps — List, step 2: "Documents at the root of .lore/codex/ render with an empty GROUP")
    pass


def test_codex_list_empty_codex_shows_fallback_message(runner, tmp_path, monkeypatch):
    # Source: conceptual-workflows-codex (Steps — List, step 2: "If no documents are found, No codex documents found. is printed")
    pass


# tests/unit/test_cli_codex_list.py


def test_codex_list_header_contains_group(runner, tmp_path):
    # Source: conceptual-workflows-codex (Steps — List, step 2: table columns are ID, GROUP, TITLE, SUMMARY)
    pass


def test_codex_list_header_does_not_contain_type(runner, tmp_path):
    # Source: conceptual-workflows-codex (Steps — List, step 2: TYPE is not a column in the rendered table)
    pass


def test_codex_list_row_uses_derive_group_for_subdirectory(runner, tmp_path):
    # Source: conceptual-workflows-codex (Steps — List, step 2: GROUP derived via derive_group from directory path)
    pass


def test_codex_list_group_is_empty_string_for_root_level_doc(runner, tmp_path):
    # Source: conceptual-workflows-codex (Steps — List, step 2: root-level documents render with empty GROUP)
    pass


def test_codex_list_uses_format_table_not_fstring(runner, tmp_path):
    # Source: conceptual-workflows-codex (Steps — List, step 2: shared _format_table helper is used)
    pass


def test_codex_list_empty_scan_prints_no_documents_message(runner, tmp_path):
    # Source: conceptual-workflows-codex (Steps — List, step 2: "If no documents are found, No codex documents found.")
    pass
```

### Complexity Estimate

**Simple.** Only the `codex_list` handler in `src/lore/cli.py` changes. Both `derive_group` and `_format_table` already exist and are tested. The change is a mechanical substitution of one rendering block with the established pattern from `knight_list`.
