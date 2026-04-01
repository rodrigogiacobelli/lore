---
id: remove-type-field-tech-spec-draft
title: Remove type Field from Lore Python Codebase and Default Templates — Tech Spec Draft
summary: Concrete technical specification for removing the redundant type frontmatter field, covering all modified modules, exact dict-shape changes, CLI output changes, default template stripping, and full TDD test strategy.
---

# Remove `type:` Field from Lore Python Codebase and Default Templates — Tech Spec Draft

**Author:** Architect
**Date:** 2026-03-27
**Input:** _remove-type-field-prd_

---

## Core Architectural Decisions

| Priority | Decision | Choice | Rationale |
|----------|----------|--------|-----------|
| Critical | Where the change is anchored | `frontmatter.py` is the single source of truth | DRY: all callers inherit the removal automatically. `codex.py` and `artifact.py` have their own `_REQUIRED_FIELDS` copies that must also be removed. |
| Critical | `transient-marker` sentinel removal | Remove `exclude_type` parameter entirely; no replacement | PRD is explicit: transient-marker sentinel removed with no replacement. Documents in `transient/` are regular documents. |
| Critical | `type` removal scope in `models.py` | Remove only `Artifact.type` and `CodexDocument.type` | `Dependency.type` (DB column) and `DoctrineStep.type` (mission pipeline) are unrelated — must not be touched. |
| Critical | Breaking change handling | Clean removal, no shim, no deprecation warning | PRD specifies no backwards-compat shim. CHANGELOG documents the break. Downstream (Realm) updates separately. |
| Important | `codex.py` local `_REQUIRED_FIELDS` | Delete it; delegate entirely to `frontmatter.py` | Eliminates the duplication. `_parse_doc_robust` and all callers use the `frontmatter` module's updated constant. |
| Important | `artifact.py` `required_fields` call | Stop passing `required_fields=("id","title","type","summary")` explicitly; use module default | After `frontmatter._REQUIRED_FIELDS` is updated, the default is correct for artifacts too. |
| Important | CLI columns for `artifact list` | Drop `TYPE`; render `ID \| GROUP \| TITLE \| SUMMARY` | Matches PRD FR-16. Column order confirmed: ID, GROUP, TITLE, SUMMARY. |
| Important | CLI `codex search` text output | Drop `TYPE` column; render `ID \| TITLE \| SUMMARY` or `ID \| GROUP \| TITLE \| SUMMARY` | `search_documents` returns `group` after the fix. Use `ID \| TITLE \| SUMMARY` (search already shows title/summary only). |
| Deferred | Semver bump (minor vs major) | Handled as a release decision; CHANGELOG documents the break | Outside feature scope; version bump decision is made at release time by maintainers. |

---

## Data Architecture

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Database | No change (SQLite, no migration) | `type` field is frontmatter-only; no DB column involved. `SCHEMA_VERSION` stays at current value. |
| ORM / query layer | No change | Raw SQL unchanged. |
| Migration approach | None required | Filesystem/frontmatter change only. Existing documents with `type:` field parse successfully (field ignored). |
| Data validation | Frontmatter required-field list shrinks by one | `_REQUIRED_FIELDS = ("id", "title", "summary")` after change. Extra keys in YAML are silently ignored (existing behaviour). |

---

## API & Communication

| Decision | Choice | Rationale |
|----------|--------|-----------|
| API style | Python functions + CLI (unchanged) | No new endpoints. Existing function signatures preserved except removal of `exclude_type` param. |
| Error response format | Unchanged | Same exit-code and error-message patterns. |
| Breaking change | `Artifact.type` and `CodexDocument.type` removed from `lore.models.__all__` | Documented in CHANGELOG. Realm must remove `.type` access. No fallback. |

---

## Implementation Patterns

### Naming Conventions

**Files:** Snake_case (unchanged). No new files are introduced.
**Frontmatter constants:** `_REQUIRED_FIELDS` stays as module-level tuple constant in `frontmatter.py`.
**Dict keys returned:** After change, codex records use `{"id", "title", "summary", "group", "path"}` (scan) and `{"id", "title", "summary", "group", "body"}` (read). Artifact records match codex records.

### Error Handling

Unchanged. Files missing required fields (`id`, `title`, `summary`) return `None` from parse functions — callers skip `None` results. Documents with a legacy `type:` field in YAML are parsed successfully; the `type` key appears in the raw YAML dict but is not included in the returned record dict (no check, no error).

### Output Formats

**`lore artifact list` (text) — after change:**
```
  ID                 GROUP                     TITLE                         SUMMARY
  fi-tech-spec       feature-implementation    Tech Spec Template            Template for producing a Tech Spec.
  fi-tech-spec-draft feature-implementation    Tech Spec Draft Template      Template for producing a Tech Spec Draft.
```

**`lore artifact list --json` — after change:**
```json
{
  "artifacts": [
    {"id": "fi-tech-spec", "group": "feature-implementation", "title": "Tech Spec Template", "summary": "..."}
  ]
}
```

**`lore codex search <kw>` (text) — after change:**
```
  ID                  TITLE                         SUMMARY
  tech-arch-codex-map Codex Map Internals           Covers map_documents and _read_related.
```

**`lore codex search <kw> --json` — after change:**
```json
{"documents": [{"id": "tech-arch-codex-map", "title": "Codex Map Internals", "summary": "..."}]}
```

**`lore codex chaos <id> --threshold 50` (text) — after change:**
```
  ID                  TITLE                         SUMMARY
  tech-arch-codex-map Codex Map Internals           Covers map_documents and _read_related.
```

**Error (example):**
```
Document "missing-id" not found
```

---

## Project Structure

_Every file that changes, to file-name level. No new files are introduced (except the CHANGELOG entry and this spec document)._

```
src/lore/
  frontmatter.py            # Remove "type" from _REQUIRED_FIELDS; remove exclude_type param from both parse functions; remove type from returned dicts
  codex.py                  # Delete module-level _REQUIRED_FIELDS; remove exclude_type from _parse_doc_robust and all callers; remove type from all returned dict shapes; remove exclude_type="transient-marker" calls
  artifact.py               # Remove type from scan_artifacts/read_artifact returned dicts; stop passing required_fields tuple (use module default)
  models.py                 # Remove type: str from Artifact and CodexDocument dataclasses; update from_dict classmethods
  cli.py                    # Remove TYPE column from artifact_list text+JSON output; remove type from codex_search text+JSON output; remove type from codex_chaos text+JSON output
  defaults/artifacts/
    codex/
      (all ~29 .md files)   # Strip type: line from YAML frontmatter
    feature-implementation/
      (all ~10 .md files)   # Strip type: line from YAML frontmatter

CHANGELOG.md                # Document Artifact.type and CodexDocument.type removal as breaking change

tests/
  unit/
    test_frontmatter.py     # Update _make_doc helper to omit type:; update assertions — type not in result
    test_codex.py           # _write_doc() helper loses doc_type param; delete test_chaos_documents_excludes_transient_marker_type(); delete test_map_documents_transient_marker_excluded(); update key-set assertions
    test_models.py          # Remove type from Artifact/CodexDocument fixture dicts; delete test_type_field tests for both; update from_dict calls
    test_cli_codex_list.py  # No changes needed — type-absence tests already written (promoted from FAILS to green)
  e2e/
    test_codex.py           # Remove type: from all inline doc strings; delete type-field tests; update JSON key-set assertions
    test_artifact_list.py   # Update SPEC_KEY_ORDER to ["id", "group", "title", "summary"]; delete TYPE column assertions; delete type-field JSON tests
    test_codex_chaos.py     # Update _write_codex_doc() helper to drop doc_type param and type: line; update JSON schema assertion to {"id","title","summary"}
    test_codex_map.py       # Update _write_codex_doc() helpers to drop doc_type param and type: line; update JSON key-set assertions to {"id","title","summary","body"}
```

---

## Test Strategy

### TDD Order (Red before Green)

The implementation follows strict Red-Green cycles per user story:
1. Write failing tests first (Red phase).
2. Implement the source change to make them pass (Green phase).
3. Do not touch implementation code before the Red phase tests exist.

Story grouping drives implementation order:
- US-1: `frontmatter.py` changes (type removed from _REQUIRED_FIELDS, exclude_type removed)
- US-2: `codex.py` changes (all returned dict shapes)
- US-3: `artifact.py` changes (returned dict shapes)
- US-4: `models.py` changes (Artifact and CodexDocument dataclasses)
- US-5: `cli.py` changes (TYPE column dropped everywhere)
- US-6: Default templates stripping (~39 files)

### E2E Coverage

Each row maps one PRD user workflow to one E2E test scenario.

| Workflow (from PRD) | PRD codex ID | Test file | Test scenario | Priority |
|---------------------|-------------|-----------|---------------|----------|
| WF-1: Agent writes codex doc without `type:` field | remove-type-field-prd | tests/e2e/test_codex.py | Write a `.md` with frontmatter `id`, `title`, `summary` only; call `scan_codex()` (via `lore codex list --json`); assert returned record has no `type` key | High |
| WF-1: Legacy `type:` field in existing doc is silently ignored | remove-type-field-prd | tests/e2e/test_codex.py | Write a `.md` with `type: conceptual` in frontmatter; call `scan_codex()`; assert record has no `type` key and command exits 0 | High |
| WF-2: Human runs `lore artifact list` and sees clean output | remove-type-field-prd | tests/e2e/test_artifact_list.py | Run `lore artifact list`; assert header is `ID  GROUP  TITLE  SUMMARY` with no `TYPE` column; assert four-column layout | High |
| WF-2: `lore artifact list --json` records have no `type` key | remove-type-field-prd | tests/e2e/test_artifact_list.py | Run `lore artifact list --json`; assert no record in `artifacts` array contains `"type"` key | High |
| WF-3: `lore init` seeds templates without `type:` line | remove-type-field-prd | tests/e2e/test_lore_init.py | Run `lore init`; scan seeded artifact files; assert no file contains `type:` in frontmatter | High |
| WF-4: Realm hydrates `Artifact` from dict without `type` | remove-type-field-prd | tests/e2e/test_python_api.py | Call `scan_artifacts()` then `Artifact.from_dict(d)` for each result; assert no `AttributeError`; assert `hasattr(artifact, "type")` is False | High |
| WF-5: `lore codex search --json` records have no `type` key | remove-type-field-prd | tests/e2e/test_codex.py | Run `lore codex search <kw> --json`; assert no record in `documents` array contains `"type"` key | High |
| WF-5: `lore codex list --json` records have no `type` key | remove-type-field-prd | tests/e2e/test_codex.py (also test_cli_codex_list.py) | Run `lore codex list --json`; assert no record contains `"type"` key — this is the promoted-from-FAILS test in test_cli_codex_list.py | High |
| WF-5: `lore codex map --json` records have no `type` key | remove-type-field-prd | tests/e2e/test_codex_map.py | Run `lore codex map <id> --json`; assert record key set is `{"id","title","summary","body"}` | High |
| WF-5: `lore codex chaos --json` records have no `type` key | remove-type-field-prd | tests/e2e/test_codex_chaos.py | Run `lore codex chaos <id> --threshold 50 --json`; assert record key set is `{"id","title","summary"}` | High |

### Unit Coverage

| Component | Scenarios to cover |
|-----------|---------------------|
| `frontmatter.parse_frontmatter_doc` | (a) doc without `type:` field → returns dict without `type` key; (b) doc with legacy `type: x` field → returns dict without `type` key; (c) doc missing `id` → returns None; (d) doc missing `title` → returns None; (e) doc missing `summary` → returns None; (f) `extra_fields=("related",)` still works |
| `frontmatter.parse_frontmatter_doc_full` | Same cases as above plus: (g) returns `body` key; (h) `extra_fields=("related",)` still works |
| `codex.scan_codex` | (a) returns dicts with keys `{"id","title","summary","path"}` only — no `type`; (b) documents previously excluded via `exclude_type="transient-marker"` are now included; (c) files missing `id`/`title`/`summary` are skipped |
| `codex.map_documents` | (a) returned dict key set is `{"id","title","summary","body"}` — no `type`; (b) previously-transient-marker doc is now traversable (remove test for marker exclusion); (c) broken related links skipped |
| `codex.chaos_documents` | (a) returned dict key set is `{"id","title","summary"}` — no `type`; (b) delete `test_chaos_documents_excludes_transient_marker_type` (sentinel gone) |
| `codex._read_related` | No change in behaviour; `_write_doc` helper loses `doc_type` param |
| `artifact.scan_artifacts` | (a) returns dicts with keys `{"id","title","summary","group","path"}` — no `type` |
| `artifact.read_artifact` | (a) returns dict with keys `{"id","title","summary","body"}` — no `type` |
| `models.Artifact` | (a) `Artifact` dataclass has no `type` field; (b) `Artifact.from_dict({"id":...,"title":...,"summary":...,"group":...,"body":...})` succeeds without `type` key; (c) `artifact.type` raises `AttributeError`; (d) frozen — still immutable |
| `models.CodexDocument` | (a) `CodexDocument` dataclass has no `type` field; (b) `CodexDocument.from_dict({"id":...,"title":...,"summary":...})` succeeds without `type` key; (c) `doc.type` raises `AttributeError`; (d) frozen — still immutable |
| `models.Dependency` | No change — `Dependency.type` remains untouched |
| `models.DoctrineStep` | No change — `DoctrineStep.type` remains untouched |

### Test Conventions

- **File naming:** `tests/unit/test_<module>.py`, `tests/e2e/test_<command>.py` — unchanged.
- **Codex anchoring:** Every test comment cites a codex ID (e.g. `# remove-type-field-prd WF-1`). For unit tests, cite the relevant codex doc or US story ID. For E2E tests, cite the PRD workflow ID.
- **Fixture strategy:** In unit tests, use `tmp_path` and write minimal `.md` files inline. Helper functions (`_write_doc`, `_write_codex_doc`) are updated to remove the `doc_type` parameter. E2E fixtures in `conftest.py` are updated to remove `type:` from all seeded documents.
- **Assertion style:** Key-set assertions use `assert set(record.keys()) == {"id", "title", "summary", ...}` — explicit, not subset. JSON output assertions check `"type" not in record` after the change.
- **Prohibited:** No `type: ignore` on legitimate code paths. No conditional skipping. No test that writes a `type:` field into a doc and then asserts it IS present in the result.

---

## Migration & Rollback

### What changes

- **Frontmatter contract:** `type:` is no longer required. Documents without it now parse and appear in all scan/list/search results. Documents that carry a legacy `type:` field continue to parse — the field is silently ignored.
- **API contract:** `Artifact` and `CodexDocument` objects no longer have a `.type` attribute. This is a breaking change to `lore.models.__all__`. Realm or any code accessing `.type` must be updated.
- **CLI contract:** `lore artifact list` has four columns (not five). JSON output from all codex and artifact commands no longer includes `"type"` key.
- **Default templates:** All ~39 files under `src/lore/defaults/artifacts/` have the `type:` line stripped from frontmatter.

### CHANGELOG entry (to be added to `CHANGELOG.md`)

```
## Unreleased

### Breaking Changes
- `Artifact.type` field removed from `lore.models.Artifact`. Code accessing `artifact.type` will raise `AttributeError`.
- `CodexDocument.type` field removed from `lore.models.CodexDocument`. Code accessing `doc.type` will raise `AttributeError`.
- `lore artifact list` no longer includes a `TYPE` column. Column order is now `ID | GROUP | TITLE | SUMMARY`.
- JSON output from `lore codex list`, `lore codex search`, `lore codex map`, `lore codex chaos`, and `lore artifact list` no longer includes a `"type"` key in each record.
- The `exclude_type` parameter has been removed from `frontmatter.parse_frontmatter_doc` and `frontmatter.parse_frontmatter_doc_full`. Any direct callers must remove this argument.
- `type: transient-marker` sentinel pattern removed. Documents in the `transient/` directory are now included in all scan and list results.
```

### Rollback

No database migrations involved. To roll back: revert the source files via `git revert`. Documents in `.lore/codex/` that previously required `type:` will again be excluded from scan results if the field is absent — that is the correct rollback behaviour.

---

## Open Questions

_None. All decisions are made. Deferred items are explicitly called out above._

| # | Question | Resolution |
|---|----------|------------|
| 1 | Should transient-marker be replaced with a different mechanism (e.g. `sentinel: true` field, or filename convention)? | No replacement. PRD is explicit: removed entirely. Documents in `transient/` are regular documents. |
| 2 | Column order for `lore artifact list` — `ID \| TYPE \| GROUP \| TITLE \| SUMMARY` or `ID \| GROUP \| TITLE \| SUMMARY`? | Confirmed `ID \| GROUP \| TITLE \| SUMMARY` per PRD success criteria. |
| 3 | Should `codex search` text output gain a GROUP column? | No. `search_documents()` does not return `group` today, and adding it is out of scope for this change. Drop TYPE column; render `ID \| TITLE \| SUMMARY`. |
| 4 | Does this require a major version bump? | Deferred to release. CHANGELOG documents the break. Feature can ship; semver decision is separate. |
