---
id: remove-type-field-technical-map
title: "Remove type: Field — Technical Context Map"
type: context-map
lens: technical
summary: >
  Technical context map for the "Remove type: frontmatter field" feature. Identifies
  every codex document relevant from architecture, implementation, and testing
  perspectives. Covers frontmatter.py, codex.py, artifact.py, models.py, cli.py,
  default artifact templates, and test files.
stability: transient
---

# Context Map — Remove `type:` Field (Technical)

**Author:** Scout (technical lens)
**Date:** 2026-03-27
**Feature:** _Remove the redundant `type:` frontmatter field from the Lore Python codebase and default artifact templates_
**Lens:** _technical_

---

## Relevant Documents

| ID | Title | Why relevant |
|----|-------|-------------|
| `tech-arch-frontmatter` | Frontmatter Module Internals | Central to the change: `_REQUIRED_FIELDS` currently includes `"type"`, `exclude_type` param, and returned dicts all include `"type"`. This is the primary module to modify — removing `"type"` from defaults and returned dict keys. |
| `tech-arch-source-layout` | Source Layout | Authoritative map of every module in `src/lore/` and `tests/`. Identifies all files that need to change: `frontmatter.py`, `codex.py`, `artifact.py`, `models.py`, `cli.py`, and default artifacts. Also documents `Artifact` and `CodexDocument` dataclass field contracts. |
| `tech-arch-codex-map` | Codex Map — map_documents and _read_related Internals | `map_documents` and `chaos_documents` return dicts with `"type"` key (same contract as `read_document`). Both functions and the `codex_map` CLI handler need updating when `"type"` is removed from returned dicts. |
| `tech-arch-codex-chaos` | Codex Chaos — chaos_documents and Bidirectional Adjacency Internals | `chaos_documents` return dict shape currently includes `"type"`. The algorithm pre-pass iterates `scan_codex` results which include `"type"`. Both need updating to drop `"type"` from returned dicts. |
| `tech-overview` | Technical Overview | Documents the module layering diagram (`cli.py → codex.py → frontmatter.py`, `cli.py → artifact.py → frontmatter.py`). Confirms `frontmatter.py` is imported by `codex.py`, `artifact.py`, and `knight.py` — the correct change radius. |
| `tech-api-surface` | Python API Entity CRUD Matrix | Documents the return dict shape for `scan_codex`, `read_document`, `search_documents`, `map_documents`, `chaos_documents`, `scan_artifacts`, `read_artifact`. All currently include `"type"`. Also documents `Artifact.from_dict` and `CodexDocument.from_dict` hydration — both map `type=d["type"]` and will need updating. Note: `chaos_documents` return shape currently listed as `id, type, title, summary, body`. |
| `tech-cli-commands` | CLI Command Reference | Documents `lore codex list`, `lore codex search`, `lore codex map`, `lore codex chaos`, and `lore artifact list` CLI commands. `artifact list` renders a `TYPE` column which is sourced from the `type` field in scan results — must be dropped or replaced. |
| `tech-db-schema` | Database Schema | Documents the `Dependency.type` field (`type TEXT NOT NULL DEFAULT 'blocks'`) — this is a different `type` field (DB column, not frontmatter). Must NOT be modified. Confirms scope boundary. |
| `technical-test-guidelines` | Test Authorship Guidelines | Governs how tests must be written (unit vs E2E, codex anchoring, prohibited patterns). All type-related assertions in `tests/unit/test_codex.py`, `tests/unit/test_cli_codex_list.py`, `tests/unit/test_models.py`, `tests/unit/test_frontmatter.py`, `tests/e2e/test_codex.py`, `tests/e2e/test_codex_map.py`, `tests/e2e/test_artifact_list.py` must be updated. |
| `standards-dry` | DRY — Don't Repeat Yourself | `frontmatter.py` is the single authoritative home for frontmatter parsing. The change must remain centralized there — not scattered across `codex.py` and `artifact.py` separately. |
| `standards-public-api-stability` | Public API Stability | Removing `type` from `Artifact` and `CodexDocument` dataclasses in `models.py` is a breaking change to `lore.models.__all__`. Semver policy: removal → major bump or explicit breaking-change notice in `CHANGELOG.md`. |
| `decisions-011-api-parity-with-cli` | ADR 011 — API Parity with CLI | Governs that Python API and CLI must behave consistently. Removing `type` from the Python API (scan/read dict shapes) must be mirrored in CLI output (no `TYPE` column in `artifact list`, no `type` key in JSON output). |

---

## Implementation Scope Summary (Technical Lens)

### Source files to modify

| File | What changes |
|------|-------------|
| `src/lore/frontmatter.py` | Remove `"type"` from `_REQUIRED_FIELDS` default; remove `type` from returned dicts; audit `exclude_type` param (currently only used for `"transient-marker"` sentinel — can be removed or repurposed) |
| `src/lore/codex.py` | Remove `_REQUIRED_FIELDS` (or repoint to `frontmatter`); remove `"type"` from all returned dict shapes in `scan_codex`, `read_document`, `search_documents`, `map_documents`, `chaos_documents`; remove `exclude_type="transient-marker"` calls (transient-marker sentinel no longer needed if type field is gone) |
| `src/lore/artifact.py` | Remove `"type"` from `scan_artifacts` and `read_artifact` return dicts; update `required_fields` passed to `frontmatter.parse_frontmatter_doc` (currently `("id","title","type","summary")`) |
| `src/lore/models.py` | Remove `type: str` field from `Artifact` and `CodexDocument` dataclasses; update `from_dict` classmethods (NOT `DoctrineStep.type` or `Dependency.type` — those are unrelated) |
| `src/lore/cli.py` | Remove `TYPE` column from `artifact list` text output; remove `type` key from `artifact list` JSON output; audit `codex_search` and `codex_chaos` handlers for any `type` references |
| `src/lore/defaults/artifacts/codex/` | Remove `type:` frontmatter line from all ~29 `.md` files that carry it |

### Test files to update

| File | What changes |
|------|-------------|
| `tests/unit/test_frontmatter.py` | Remove assertions that `type` is required; update any test that checks returned dict keys include `type` |
| `tests/unit/test_codex.py` | Update dict key assertions (currently `{"id", "type", "title", "summary"}`) to drop `type` |
| `tests/unit/test_cli_codex_list.py` | Tests explicitly assert `"type" not in record` — these should pass after the change; remove tests asserting type is present |
| `tests/unit/test_models.py` | Update `Artifact.from_dict` and `CodexDocument.from_dict` test fixtures to remove `type` key from input dicts; update field assertions |
| `tests/e2e/test_codex.py` | Update assertions like `result[0]["type"] == "conceptual"` and `result["type"] == "conceptual"` |
| `tests/e2e/test_codex_map.py` | Update key set assertions (`{"id", "type", "title", "summary", "body"}` → `{"id", "title", "summary", "body"}`) |
| `tests/e2e/test_artifact_list.py` | Remove `TYPE` column assertions, `type_pos = header.index("TYPE")` lookups, and JSON `type` field assertions |

---

## How to Use This Map

Every agent that receives this map should:
1. Run `lore codex show tech-arch-frontmatter tech-arch-source-layout tech-arch-codex-map tech-arch-codex-chaos tech-api-surface tech-cli-commands technical-test-guidelines standards-dry standards-public-api-stability decisions-011-api-parity-with-cli tech-overview tech-db-schema`
2. Read every document listed before starting their mission
3. Do not explore the codex independently — this map is your entry point

---

## Scout Notes

- The `transient-marker` sentinel pattern (used to exclude index/README files from codex scan results via `exclude_type="transient-marker"`) is tightly coupled to the `type:` field. When `type` is removed, a new exclusion mechanism must be designed or those marker files must be handled differently (e.g., by filename convention like `INDEX.md` / `CODEX.md`, or by a different frontmatter field like `sentinel: true`).
- `Dependency.type` in the database schema and `DoctrineStep.type` in `models.py` are unrelated to the codex/artifact frontmatter `type` field. These must not be touched.
- The `tests/unit/test_cli_codex_list.py` already contains failing tests asserting that `"type"` must NOT be in JSON output (`FAILS: current code emits {"type": ...} in each record`). This signals that the codex list type removal was already anticipated and partially specced.
- `tech-db-schema` currently notes `SCHEMA_VERSION = 4` with pending migrations to v5 and v6. The type field removal does not require a schema migration (it is a filesystem/frontmatter change only, not a DB change).
