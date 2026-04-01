---
id: remove-type-field-us-index
type: user-story-index
title: Remove type Field — User Story Index
summary: Index of all user stories for the remove-type-field feature, covering frontmatter parsing, codex and artifact scanning, Python models, CLI output, default templates, and test suite alignment.
status: final
---

# Remove `type:` Field — User Story Index

**Author:** Business Analyst
**Date:** 2026-03-27
**Status:** final
**PRD:** `lore codex show remove-type-field-prd`
**Tech Spec:** `lore codex show remove-type-field-tech-spec`

---

## Stories by Epic

### Frontmatter Contract Simplification

Removes `type` from the frontmatter parser and eliminates the `exclude_type` parameter entirely. This is the foundational change that all other epics depend on.

| ID | Title | Status | Codex ID |
|----|-------|--------|----------|
| US-1 | Remove type from frontmatter parsing | final | `remove-type-field-us-1` |

### Codex Module Cleanup

Removes `type` from all dict shapes returned by `codex.py` and eliminates the `transient-marker` sentinel call sites.

| ID | Title | Status | Codex ID |
|----|-------|--------|----------|
| US-2 | Remove type from codex scanning and traversal | final | `remove-type-field-us-2` |

### Artifact Module Cleanup

Removes `type` from all dict shapes returned by `artifact.py`.

| ID | Title | Status | Codex ID |
|----|-------|--------|----------|
| US-3 | Remove type from artifact scanning | final | `remove-type-field-us-3` |

### Public API Contract Change

Removes `type: str` from `Artifact` and `CodexDocument` dataclasses — a breaking change to `lore.models.__all__`.

| ID | Title | Status | Codex ID |
|----|-------|--------|----------|
| US-4 | Remove type from Python models | final | `remove-type-field-us-4` |

### CLI Output Simplification

Removes the `TYPE` column from `lore artifact list` and removes `type` from all JSON output paths for codex and artifact commands.

| ID | Title | Status | Codex ID |
|----|-------|--------|----------|
| US-5 | Remove TYPE column from CLI output | final | `remove-type-field-us-5` |

### Default Template Cleanup

Strips `type:` frontmatter from all ~39 files under `src/lore/defaults/artifacts/` so that new projects start clean.

| ID | Title | Status | Codex ID |
|----|-------|--------|----------|
| US-6 | Strip type from default artifact templates | final | `remove-type-field-us-6` |

### Test Suite Alignment

Updates unit and E2E tests to remove type from fixtures and assert type is absent from results, ensuring 100% pass rate after source changes.

| ID | Title | Status | Codex ID |
|----|-------|--------|----------|
| US-7 | Update unit tests to remove type expectations | final | `remove-type-field-us-7` |
| US-8 | Update E2E tests to remove type expectations | final | `remove-type-field-us-8` |

---

## PRD Coverage Map

| PRD Requirement | Story IDs |
|-----------------|-----------|
| FR-1: System parses codex doc without `type:` without error | US-1 |
| FR-2: System parses legacy `type:` field without error (silently ignored) | US-1 |
| FR-3: `parse_frontmatter_doc` result dict has no `"type"` key | US-1 |
| FR-4: `exclude_type` parameter removed from `parse_frontmatter_doc` and `scan_docs` | US-1 |
| FR-5: `scan_codex()` returns dicts without `"type"` key | US-2 |
| FR-6: `read_document()` returns dict without `"type"` key | US-2 |
| FR-7: `search_documents()`, `map_documents()`, `chaos_documents()` return dicts without `"type"` | US-2 |
| FR-8: All `exclude_type="transient-marker"` call sites removed; no replacement | US-2 |
| FR-9: `scan_artifacts()` returns dicts without `"type"` key | US-3 |
| FR-10: `read_artifact()` returns dict without `"type"` key | US-3 |
| FR-11: `required_fields` argument for artifacts omits `"type"` | US-3 |
| FR-12: `Artifact` dataclass has no `type` field | US-4 |
| FR-13: `CodexDocument` dataclass has no `type` field | US-4 |
| FR-14: `Artifact.from_dict` and `CodexDocument.from_dict` do not read `d["type"]` | US-4 |
| FR-15: `Dependency.type` and `DoctrineStep.type` not modified | US-4 |
| FR-16: `lore artifact list` text output shows `ID \| GROUP \| TITLE \| SUMMARY` (four columns) | US-5 |
| FR-17: `lore artifact list --json` records have no `"type"` key | US-3, US-5 |
| FR-18: `lore codex list/search/map/chaos --json` records have no `"type"` key | US-2, US-5 |
| FR-19: No file under `src/lore/defaults/artifacts/` contains `type:` frontmatter | US-6 |
| FR-20: All unit and E2E tests pass after the change | US-7, US-8 |
| FR-21: Tests asserting `type` present updated to assert `type` absent | US-7, US-8 |
| FR-22: `test_cli_codex_list.py` type-absence tests promoted to green | US-5, US-7 |
| FR-23: `CHANGELOG.md` documents breaking change | US-4 |
| _WF-1: Agent writes codex doc without `type:` field_ | US-1, US-2 |
| _WF-2: Human runs `lore artifact list` and sees clean output_ | US-3, US-5 |
| _WF-3: Developer initializes project and uses default template_ | US-6 |
| _WF-4: Realm imports `Artifact` and processes scan results_ | US-3, US-4 |
| _WF-5: Developer runs `lore codex search` and receives JSON without `type`_ | US-2, US-5 |

---

## Summary

| Total stories | Epics | Draft | Final |
|---------------|-------|-------|-------|
| 8 | 7 | 0 | 8 |
