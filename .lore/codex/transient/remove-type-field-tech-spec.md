---
id: remove-type-field-tech-spec
title: Remove type Field from Lore Python Codebase and Default Templates — Tech Spec
summary: Final technical specification for removing the redundant type frontmatter field from frontmatter.py, codex.py, artifact.py, models.py, cli.py, and all default artifact templates. Covers all architectural decisions, exact dict shapes, CLI output changes, and complete TDD test strategy mapping every PRD workflow to an E2E scenario.
---

# Remove `type:` Field from Lore Python Codebase and Default Templates — Tech Spec

**Author:** Architect
**Date:** 2026-03-27
**Supersedes:** _remove-type-field-tech-spec-draft_
**Input:** _remove-type-field-prd_

---

## Core Architectural Decisions

| Priority | Decision | Choice | Rationale |
|----------|----------|--------|-----------|
| Critical | Single source of truth for required fields | `frontmatter.py` owns `_REQUIRED_FIELDS = ("id", "title", "summary")` | DRY: all callers inherit the removal automatically. Eliminates divergent copies in `codex.py` and `artifact.py`. |
| Critical | `transient-marker` sentinel and `exclude_type` parameter | Remove entirely; no replacement | PRD FR-4 and FR-8 are explicit: sentinel removed with no replacement. Documents in `transient/` are regular documents. |
| Critical | `type` removal scope in `models.py` | Remove only `Artifact.type` and `CodexDocument.type` | `Dependency.type` (DB column) and `DoctrineStep.type` (mission pipeline) are unrelated fields — not touched. |
| Critical | Breaking change handling | Clean removal, no shim, no deprecation warning | PRD specifies no backwards-compat shim. CHANGELOG documents the break. Downstream (Realm) updates separately. |
| Important | `codex.py` local `_REQUIRED_FIELDS` copy | Delete it; delegate entirely to `frontmatter.py` | Eliminates duplication. `_parse_doc_robust` and all callers use the frontmatter module constant. |
| Important | `artifact.py` `required_fields` argument | Stop passing explicit tuple; use module default | After `frontmatter._REQUIRED_FIELDS` is updated, the default is correct for artifacts. |
| Important | `lore artifact list` column order | `ID \| GROUP \| TITLE \| SUMMARY` (four columns) | PRD FR-16 and success criteria. `TYPE` column dropped. |
| Important | `lore codex search` text output | `ID \| TITLE \| SUMMARY` (three columns) | `search_documents()` does not return `group`; adding it is out of scope. Drop `TYPE`; do not add `GROUP`. |
| Deferred | Semver bump (minor vs major) | Release decision; CHANGELOG documents the break | Outside feature scope. Maintainers decide at release time. |

---

## Data Architecture

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Database | No change (SQLite, no migration) | `type` is frontmatter-only. No DB column exists for it. `SCHEMA_VERSION` unchanged. |
| ORM / query layer | No change | Raw SQL unchanged. |
| Migration approach | None required | Filesystem/frontmatter change only. Existing documents with a legacy `type:` field parse successfully — the field is silently ignored. |
| Data validation | `_REQUIRED_FIELDS` shrinks from four to three | `_REQUIRED_FIELDS = ("id", "title", "summary")`. Extra YAML keys are silently ignored (existing behaviour). |

---

## API & Communication

| Decision | Choice | Rationale |
|----------|--------|-----------|
| API style | Python functions + CLI (unchanged) | No new endpoints. Existing function signatures preserved except removal of `exclude_type` param. |
| Error response format | Unchanged | Same exit-code and error-message patterns. |
| Versioning strategy | Breaking change documented in CHANGELOG; semver bump deferred | PRD NFR: no shim. CHANGELOG entry is mandatory. Semver policy is a release decision. |

---

## Implementation Patterns

### Naming Conventions

**Files:** Snake_case (unchanged). No new files are introduced.
**Frontmatter constants:** `_REQUIRED_FIELDS` stays as a module-level tuple constant in `frontmatter.py`.
**Dict keys returned by scan functions:** `{"id", "title", "summary", "group", "path"}` — no `"type"`.
**Dict keys returned by read functions:** `{"id", "title", "summary", "group", "body"}` — no `"type"`.
**Dict keys returned by search/chaos functions:** `{"id", "title", "summary"}` — no `"type"`.

### Error Handling

Unchanged. Files missing required fields (`id`, `title`, `summary`) return `None` from parse functions — callers skip `None` results. Documents with a legacy `type:` field in YAML are parsed successfully; the `type` key appears in the raw YAML dict but is not included in the returned record dict (no check, no error, no warning).

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
    {"id": "fi-tech-spec", "group": "feature-implementation", "title": "Tech Spec Template", "summary": "Template for producing a Tech Spec."}
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
{"documents": [{"id": "tech-arch-codex-map", "title": "Codex Map Internals", "summary": "Covers map_documents and _read_related."}]}
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
  frontmatter.py            # Remove "type" from _REQUIRED_FIELDS; remove exclude_type param from both parse functions; type key absent from returned dicts
  codex.py                  # Delete module-level _REQUIRED_FIELDS; remove exclude_type from _parse_doc_robust and all callers; remove type from all returned dict shapes; remove exclude_type="transient-marker" call sites
  artifact.py               # Remove type from scan_artifacts/read_artifact returned dicts; stop passing required_fields tuple explicitly (use module default)
  models.py                 # Remove type: str from Artifact and CodexDocument dataclasses; update from_dict classmethods
  cli.py                    # Remove TYPE column from artifact list text+JSON output; remove type from codex search/list/map/chaos text+JSON output
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
    test_models.py          # Remove type from Artifact/CodexDocument fixture dicts; delete type-field tests; update from_dict calls
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
- US-1: `frontmatter.py` changes (type removed from `_REQUIRED_FIELDS`, `exclude_type` removed)
- US-2: `codex.py` changes (all returned dict shapes, `exclude_type` call sites removed)
- US-3: `artifact.py` changes (returned dict shapes, `required_fields` default used)
- US-4: `models.py` changes (`Artifact` and `CodexDocument` dataclasses)
- US-5: `cli.py` changes (`TYPE` column dropped from all output paths)
- US-6: Default templates stripping (~39 files in `src/lore/defaults/artifacts/`)

### E2E Coverage

Each row maps one PRD user workflow to one E2E test scenario.

| Workflow (from PRD) | PRD codex ID | Test file | Test scenario | Priority |
|---------------------|--------------|-----------|---------------|----------|
| WF-1: Agent writes codex doc without `type:` field | remove-type-field-prd | tests/e2e/test_codex.py | Write a `.md` with frontmatter `id`, `title`, `summary` only; call `lore codex list --json`; assert returned record has no `"type"` key and exit code is 0 | High |
| WF-1: Legacy `type:` field in existing doc is silently ignored | remove-type-field-prd | tests/e2e/test_codex.py | Write a `.md` with `type: conceptual` in frontmatter; call `lore codex list --json`; assert record has no `"type"` key and command exits 0 | High |
| WF-2: Human runs `lore artifact list` and sees clean output | remove-type-field-prd | tests/e2e/test_artifact_list.py | Run `lore artifact list`; assert header is `ID  GROUP  TITLE  SUMMARY` with no `TYPE` column; assert exactly four columns in header | High |
| WF-2: `lore artifact list --json` records have no `type` key | remove-type-field-prd | tests/e2e/test_artifact_list.py | Run `lore artifact list --json`; assert no record in `artifacts` array contains `"type"` key; assert key set is `{"id", "group", "title", "summary"}` | High |
| WF-3: `lore init` seeds templates without `type:` line | remove-type-field-prd | tests/e2e/test_lore_init.py | Run `lore init`; scan all seeded artifact files; assert no file contains a line matching `^type:` in frontmatter | High |
| WF-4: Realm hydrates `Artifact` from dict without `type` | remove-type-field-prd | tests/e2e/test_python_api.py | Call `scan_artifacts()` then `Artifact.from_dict(d)` for each result; assert no `AttributeError`; assert `hasattr(artifact, "type")` is `False` | High |
| WF-5: `lore codex search --json` records have no `type` key | remove-type-field-prd | tests/e2e/test_codex.py | Run `lore codex search <kw> --json`; assert no record in `documents` array contains `"type"` key | High |
| WF-5: `lore codex list --json` records have no `type` key | remove-type-field-prd | tests/e2e/test_codex.py and tests/e2e/test_cli_codex_list.py | Run `lore codex list --json`; assert no record contains `"type"` key — this promotes the existing FAILS test in `test_cli_codex_list.py` to green | High |
| WF-5: `lore codex map --json` records have no `type` key | remove-type-field-prd | tests/e2e/test_codex_map.py | Run `lore codex map <id> --json`; assert record key set is exactly `{"id", "title", "summary", "body"}` | High |
| WF-5: `lore codex chaos --json` records have no `type` key | remove-type-field-prd | tests/e2e/test_codex_chaos.py | Run `lore codex chaos <id> --threshold 50 --json`; assert record key set is exactly `{"id", "title", "summary"}` | High |

### Unit Coverage

| Component | Scenarios to cover |
|-----------|---------------------|
| `frontmatter.parse_frontmatter_doc` | (a) doc without `type:` field → returns dict without `"type"` key; (b) doc with legacy `type: x` field → returns dict without `"type"` key; (c) doc missing `id` → returns `None`; (d) doc missing `title` → returns `None`; (e) doc missing `summary` → returns `None`; (f) `extra_fields=("related",)` still works |
| `frontmatter.parse_frontmatter_doc_full` | Same cases as above plus: (g) returns `body` key; (h) `extra_fields=("related",)` still works |
| `codex.scan_codex` | (a) returns dicts with keys `{"id", "title", "summary", "group", "path"}` — no `"type"`; (b) documents previously excluded via `exclude_type="transient-marker"` are now included; (c) files missing `id`/`title`/`summary` are skipped |
| `codex.map_documents` | (a) returned dict key set is `{"id", "title", "summary", "body"}` — no `"type"`; (b) previously-transient-marker doc is now traversable; (c) broken related links are skipped |
| `codex.chaos_documents` | (a) returned dict key set is `{"id", "title", "summary"}` — no `"type"`; (b) delete `test_chaos_documents_excludes_transient_marker_type` (sentinel gone) |
| `codex._read_related` | No behaviour change; `_write_doc` helper loses `doc_type` param |
| `artifact.scan_artifacts` | (a) returns dicts with keys `{"id", "title", "summary", "group", "path"}` — no `"type"` |
| `artifact.read_artifact` | (a) returns dict with keys `{"id", "title", "summary", "group", "body"}` — no `"type"` |
| `models.Artifact` | (a) `Artifact` dataclass has no `type` field; (b) `Artifact.from_dict({"id": "x", "title": "X", "summary": "s", "group": "g", "body": ""})` succeeds without `type` key; (c) accessing `artifact.type` raises `AttributeError`; (d) frozen — still immutable |
| `models.CodexDocument` | (a) `CodexDocument` dataclass has no `type` field; (b) `CodexDocument.from_dict({"id": "x", "title": "X", "summary": "s"})` succeeds without `type` key; (c) accessing `doc.type` raises `AttributeError`; (d) frozen — still immutable |
| `models.Dependency` | No change — `Dependency.type` remains untouched |
| `models.DoctrineStep` | No change — `DoctrineStep.type` remains untouched |

### Test Conventions

- **File naming:** `tests/unit/test_<module>.py`, `tests/e2e/test_<command>.py` — unchanged.
- **Codex anchoring:** Every test comment cites a codex ID. E2E tests cite the PRD workflow ID (e.g. `# remove-type-field-prd WF-1`). Unit tests cite the relevant codex doc or user story ID.
- **Fixture strategy:** Unit tests use `tmp_path` and write minimal `.md` files inline. Helper functions (`_write_doc`, `_write_codex_doc`) lose the `doc_type` parameter. E2E fixtures in `conftest.py` are updated to remove `type:` from all seeded documents.
- **Assertion style:** Key-set assertions use `assert set(record.keys()) == {"id", "title", "summary", ...}` — explicit and exact, not subset. JSON output assertions check `"type" not in record` after the change.
- **Prohibited:** No `type: ignore` on legitimate code paths. No conditional skipping. No test that writes a `type:` field and then asserts it IS present in the result.

---

## Crazy Tech Spec Findings

_The Crazy Tech Spec was cancelled and no alternative design was produced. This table is included for completeness; no ideas require evaluation._

| Idea | Decision | Rationale |
|------|----------|-----------|
| N/A — Crazy Tech Spec cancelled | N/A | No alternative design was produced. All decisions derive from the Tech Spec Draft and PRD. |

---

## Migration & Rollback

### What changes

- **Frontmatter contract:** `type:` is no longer required. Documents without it now parse and appear in all scan/list/search results. Documents that carry a legacy `type:` field continue to parse — the field is silently ignored (no error, no warning).
- **API contract:** `Artifact` and `CodexDocument` objects no longer have a `.type` attribute. This is a breaking change to `lore.models.__all__`. Realm or any code accessing `.type` must be updated.
- **CLI contract:** `lore artifact list` has four columns (not five). JSON output from all codex and artifact commands no longer includes a `"type"` key.
- **Default templates:** All ~39 files under `src/lore/defaults/artifacts/` have the `type:` line stripped from frontmatter.
- **`transient-marker` sentinel:** Removed entirely. Documents in `transient/` are now regular documents included in all scans.

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

No database migrations involved. To roll back: `git revert` the source file changes. Documents in `.lore/codex/` that previously required `type:` will again be excluded from scan results if the field is absent — that is the correct rollback behaviour.

---

## Change Log

| Version | Change | Reason |
|---------|--------|--------|
| 1.0 | Initial Tech Spec | Incorporates all decisions from Tech Spec Draft. Crazy Tech Spec was cancelled — no ideas to adopt or reject. All decisions are final; no open questions remain. |
