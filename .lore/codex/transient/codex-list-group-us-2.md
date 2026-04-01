---
id: codex-list-group-us-2
feature: codex-list-group
status: final
title: Include group field and codex envelope key in lore codex list --json output
summary: As an automation script, I want lore codex list --json to include a group field and use codex as the envelope key so I can filter documents by category without parsing file paths.
---

## Metadata

- **ID:** US-2
- **Status:** final
- **Epic:** codex-list-group
- **Author:** Business Analyst
- **Date:** 2026-03-27
- **PRD:** `lore codex show codex-list-group-prd`
- **Tech Spec:** `lore codex show codex-list-group-tech-spec`

---

## Story

As an automation script, I want `lore codex list --json` to include a `group` field and use `"codex"` as the envelope key so that I can filter documents by category without parsing file paths manually.

## Context

This story fulfills the PRD workflow "Consuming codex list output programmatically — Automation script". The current `lore codex list --json` output wraps documents under the key `"documents"` and omits a `group` field, making it non-standard compared to every other entity list JSON output (e.g. `{"knights": [...]}`, `{"doctrines": [...]}`, `{"watchers": [...]}`). Scripts consuming this output cannot group or filter documents by directory category without string-parsing the file path. This story adds the `group` field to each record, renames the envelope key from `"documents"` to `"codex"`, and removes the `"type"` field from records — aligning the JSON schema with the established pattern.

---

## Acceptance Criteria

Every criterion is testable by running `lore codex list --json` and parsing the output with `jq` or Python's `json.loads`.

### E2E Scenarios

#### Scenario 1: JSON envelope key is `"codex"`

**Given** a lore project with one or more codex documents
**When** the automation script runs `lore codex list --json`
**Then** the output is valid JSON with a single top-level key `"codex"` whose value is an array — for example `{"codex": [...]}` — and the key `"documents"` is not present anywhere in the output

#### Scenario 2: Each record includes a `group` field

**Given** a lore project containing codex documents in one or more subdirectories of `.lore/codex/`
**When** the automation script runs `lore codex list --json`
**Then** every object in the `"codex"` array contains a `"group"` key; running `lore codex list --json | jq '.codex[].group'` returns one value per document without error

#### Scenario 3: `group` value matches subdirectory name for a categorised document

**Given** a lore project containing a document at `.lore/codex/tech-arch/source-layout.md`
**When** the automation script runs `lore codex list --json`
**Then** the record for that document has `"group": "tech-arch"` in the JSON output

#### Scenario 4: `group` is an empty string for a root-level document

**Given** a lore project containing a document stored directly under `.lore/codex/` (no subdirectory)
**When** the automation script runs `lore codex list --json`
**Then** the record for that document has `"group": ""` in the JSON output — not null, not absent, not an error

#### Scenario 5: `type` field is absent from JSON records

**Given** a lore project with one or more codex documents
**When** the automation script runs `lore codex list --json`
**Then** no record in the `"codex"` array contains a `"type"` key; running `lore codex list --json | jq '.codex[] | has("type")'` returns `false` for every record

#### Scenario 6: Each record contains exactly `id`, `group`, `title`, `summary` fields

**Given** a lore project with one or more codex documents
**When** the automation script runs `lore codex list --json`
**Then** each record in the `"codex"` array has exactly the keys `"id"`, `"group"`, `"title"`, and `"summary"` with string values

#### Scenario 7: Global `--json` flag also produces correct output

**Given** a lore project with one or more codex documents
**When** the automation script runs `lore --json codex list`
**Then** the output is identical in structure and content to `lore codex list --json`: top-level key `"codex"`, each record includes `"group"`, no `"type"` key

### Unit Test Scenarios

- [ ] `codex_list` handler: JSON output top-level key is `"codex"`, not `"documents"`
- [ ] `codex_list` handler: each JSON record contains `"group"` derived from `derive_group(d["path"], codex_dir)`
- [ ] `codex_list` handler: `"group"` is `""` for a document at the root of `.lore/codex/` — no exception raised
- [ ] `codex_list` handler: JSON records do not contain a `"type"` key
- [ ] `codex_list` handler: `--json` local flag activates JSON output mode
- [ ] `codex_list` handler: global `ctx.obj["json"] = True` also activates JSON output mode
- [ ] `codex_list` handler: JSON output for empty codex is `{"codex": []}` or follows the established empty pattern

---

## Out of Scope

- Changes to tabular output of `lore codex list` (covered by US-1)
- Changes to `derive_group` in `paths.py`
- Changes to `_format_table` in `cli.py`
- Changes to `scan_codex` in `codex.py`
- Changes to `lore codex map` or any other codex subcommand
- Adding filtering, sorting, or pagination to `lore codex list --json`
- Updating the `conceptual-workflows-codex` documentation (post-MVP)

---

## References

- PRD: `lore codex show codex-list-group-prd`
- Tech Spec: `lore codex show codex-list-group-tech-spec`
- JSON pattern reference: `lore codex show conceptual-workflows-knight-list`
- Current behaviour: `lore codex show conceptual-workflows-codex`

---

## Tech Notes

_(Filled by Tech Lead in tech-notes-draft and tech-notes-final phases — BA must not edit this section)_

### Implementation Approach

**File to change:** `src/lore/cli.py` — this is the only file that changes.

**Function to modify:** `codex_list` (line 2228)

**Changes:**
1. Add `@click.option("--json", "json_flag", is_flag=True, help="Output as JSON.")` decorator to the `codex_list` handler (before `@click.pass_context`), matching the pattern in `knight_list`, `doctrine_list`, and `watcher_list`.
2. Add `json_flag` parameter to the function signature.
3. Change `json_mode` assignment to `json_mode = json_flag or ctx.obj.get("json", False)` so both the local flag and the global `ctx.obj["json"]` activate JSON mode.
4. In the JSON branch: replace the `"documents"` envelope key with `"codex"`, remove `"type"` from each record, and add `"group"` computed via `paths.derive_group(d["path"], codex_dir)`.
5. JSON record shape: `{"id": d["id"], "group": paths.derive_group(d["path"], codex_dir), "title": d["title"], "summary": d["summary"]}`.

No changes to `src/lore/paths.py`, `src/lore/codex.py`, or `_format_table`. `scan_codex` already returns `path` in every record.

### Test File Locations

| Type | Path | Notes |
|------|------|-------|
| E2E | `tests/e2e/test_codex_list_group_e2e.py` | New file; existing codex list E2E tests live in `tests/e2e/test_codex.py` |
| Unit | `tests/unit/test_cli_codex_list.py` | New file; no existing unit file covers `codex_list` handler |

### Test Stubs

```python
# tests/e2e/test_codex_list_group_e2e.py


def test_codex_list_json_envelope_key_is_codex_not_documents(runner, project_dir):
    # Source: conceptual-workflows-codex (Steps — List, step 3: JSON mode envelope is {"codex": [...]})
    pass


def test_codex_list_json_every_record_has_group_key(runner, project_dir):
    # Source: conceptual-workflows-codex (Steps — List, step 3: each record has id, group, title, summary)
    pass


def test_codex_list_json_group_matches_subdirectory_name(runner, project_dir):
    # Source: conceptual-workflows-codex (Steps — List, step 3: group derived from directory path under .lore/codex/)
    pass


def test_codex_list_json_group_is_empty_string_for_root_level_doc(runner, project_dir):
    # Source: conceptual-workflows-codex (Steps — List, step 2: "Documents at the root of .lore/codex/ render with an empty GROUP")
    pass


def test_codex_list_json_records_do_not_contain_type_key(runner, project_dir):
    # Source: conceptual-workflows-codex (Steps — List, step 3: record fields are id, group, title, summary — type is absent)
    pass


def test_codex_list_json_each_record_has_exactly_four_fields(runner, project_dir):
    # Source: conceptual-workflows-codex (Steps — List, step 3: record schema is id, group, title, summary)
    pass


def test_codex_list_global_json_flag_produces_same_output_as_local_flag(runner, project_dir):
    # Source: conceptual-workflows-codex (Steps — List, step 3: JSON mode activated by global --json or local --json)
    pass


# tests/unit/test_cli_codex_list.py


def test_codex_list_json_top_level_key_is_codex(runner, tmp_path):
    # Source: conceptual-workflows-codex (Steps — List, step 3: {"codex": [...]})
    pass


def test_codex_list_json_record_contains_group_field(runner, tmp_path):
    # Source: conceptual-workflows-codex (Steps — List, step 3: each record includes group derived from derive_group)
    pass


def test_codex_list_json_group_is_empty_string_for_root_document(runner, tmp_path):
    # Source: conceptual-workflows-codex (Steps — List, step 2: empty GROUP for root-level documents)
    pass


def test_codex_list_json_records_have_no_type_key(runner, tmp_path):
    # Source: conceptual-workflows-codex (Steps — List, step 3: record schema excludes type)
    pass


def test_codex_list_local_json_flag_activates_json_mode(runner, tmp_path):
    # Source: conceptual-workflows-codex (Steps — List, step 3: --json flag triggers JSON output)
    pass


def test_codex_list_global_ctx_json_activates_json_mode(runner, tmp_path):
    # Source: conceptual-workflows-codex (Steps — List, step 3: global ctx.obj["json"] also triggers JSON output)
    pass


def test_codex_list_json_empty_codex_returns_codex_empty_array(runner, tmp_path):
    # Source: conceptual-workflows-codex (Steps — List, step 3: empty result follows established empty pattern)
    pass
```

### Complexity Estimate

**Simple.** Only the `codex_list` handler in `src/lore/cli.py` changes. Adding a local `--json` flag and updating the JSON branch to use the `"codex"` envelope key, add `"group"`, and remove `"type"` are all mechanical substitutions following the established `knight_list` pattern. `derive_group` and the JSON `json.dumps` path already exist.
