---
id: remove-type-field-prd-draft
title: Remove type Field from Lore Python Codebase and Default Templates — PRD Draft
summary: PRD Draft for removing the redundant type frontmatter field from frontmatter.py, codex.py, artifact.py, models.py, cli.py, default artifact templates (~39 files), and all associated tests.
---

# Remove `type:` Field from Lore Python Codebase and Default Templates — PRD Draft

**Author:** Product Manager
**Date:** 2026-03-27
**Input:** _Remove the redundant `type:` frontmatter field from the Lore Python codebase and default artifact templates. Every codex document and artifact currently requires a `type:` field (e.g. `type: entity`, `type: workflow`). This is being removed because directory path already provides grouping via the GROUP mechanism. A parallel quest (q-bbbf) handles the live .lore/codex/ document migration. This quest covers Python source (frontmatter.py, codex.py, artifact.py, models.py, cli.py), src/lore/defaults/ templates, and tests._

---

## Executive Summary

Lore currently requires every codex document and artifact to carry a `type:` frontmatter field (e.g. `type: entity`, `type: workflow`, `type: conceptual`). This field is redundant: directory path already encodes grouping via the GROUP mechanism, so `type` carries no information that the filesystem does not already provide. The `type:` field is being removed from the Python source layer — the frontmatter parser, codex and artifact modules, dataclass models, CLI output, and all default shipped templates — to eliminate the maintenance burden and contract mismatch that the field introduces. A parallel quest (q-bbbf) handles the live `.lore/codex/` document migration. This quest is purely a source-code and template change. Realm is the primary Python API consumer and will receive a breaking change notice.

### What Makes This Special

This is a contract simplification. Removing `type:` does not add a feature — it removes a requirement that was never needed. The measure of success is that nothing breaks, the output is cleaner, and the codebase enforces fewer rules than before.

---

## Project Classification

| Attribute | Value |
|-----------|-------|
| Project type | CLI tool / Python library |
| Primary users | Agents (Realm) consuming `lore.models`; humans using the `lore` CLI |
| Scale | Single-project installation; no network traffic; I/O-bound file operations |

---

## Success Criteria

### User Success

- Agents and humans can use every `lore codex` and `lore artifact` command without supplying a `type:` field in any document or artifact file.
- `lore artifact list` no longer shows a `TYPE` column — output is unambiguously narrower and cleaner.
- `lore codex list`, `lore codex search`, `lore codex map`, and `lore codex chaos` return records without a `type` key in JSON output.
- All default artifact templates shipped by `lore init` do not contain a `type:` frontmatter line.
- Existing projects that do not re-init are unaffected: documents with a `type:` field are still parsed (field is ignored, not rejected).

### Technical Success

- All existing tests pass after the change. No new test failures introduced.
- The `Artifact` and `CodexDocument` dataclasses in `lore.models` no longer carry a `type` field.
- `frontmatter.py` no longer lists `"type"` in `_REQUIRED_FIELDS` and does not return `"type"` in parsed dicts.
- The `exclude_type` parameter in `frontmatter.py` is removed or marked dead (its only consumer was the `transient-marker` sentinel pattern).
- `Dependency.type` and `DoctrineStep.type` in `models.py` are untouched.
- `CHANGELOG.md` documents the breaking API change; `pyproject.toml` version reflects semver policy (major bump if `Artifact.type` removal is classified as breaking).

| Metric | Baseline | Target | Timeline |
|--------|----------|--------|----------|
| Test suite pass rate | 100% | 100% | At merge |
| `lore artifact list` column count | 5 (ID, TYPE, GROUP, TITLE, SUMMARY) | 4 (ID, GROUP, TITLE, SUMMARY) | At merge |
| Default templates with `type:` field | 39 files | 0 files | At merge |
| `type` key in `scan_codex` dict | Present | Absent | At merge |
| `type` key in `scan_artifacts` dict | Present | Absent | At merge |

---

## Product Scope

### MVP

- Remove `"type"` from `_REQUIRED_FIELDS` in `frontmatter.py`; remove `type` from all parsed dict return values; remove or retire `exclude_type` parameter.
- Remove `type: str` from `Artifact` and `CodexDocument` dataclasses in `models.py`; update `from_dict` classmethods.
- Remove `type` from all dict shapes returned by `codex.py` (`scan_codex`, `read_document`, `search_documents`, `map_documents`, `chaos_documents`) and `artifact.py` (`scan_artifacts`, `read_artifact`).
- Remove `TYPE` column from `lore artifact list` text output; remove `type` key from all JSON output paths in `cli.py`.
- Remove `type:` frontmatter line from all default artifact templates in `src/lore/defaults/artifacts/`.
- Update all affected tests to reflect the removed field.
- Document the breaking change in `CHANGELOG.md`.

### Post-MVP

- Remove the `transient-marker` sentinel mechanism entirely and replace with a filename-convention-based exclusion (e.g. files named `CODEX.md` or `INDEX.md` are excluded without consulting any frontmatter field). This is out of scope for this quest but noted as the natural follow-on.

### Out of Scope

- Live `.lore/codex/` document migration — handled by parallel quest q-bbbf.
- Any UI changes in Citadel.
- Changes to `Dependency.type` (DB column) or `DoctrineStep.type` (model field).
- Adding any new frontmatter field as a replacement for `type`.
- Validation that rejects documents that still carry a `type:` field (old documents with `type:` should parse successfully; the field is simply ignored).

---

## User Workflows

### Workflow 1 — Agent writes a new codex document without a `type:` field

**Persona:** Realm agent (e.g. a Scout knight), generating a new codex document file programmatically.
**Situation:** The agent is writing a context map document to `.lore/codex/transient/`. Under the current system, it must include `type: context-map` in the frontmatter or the document fails validation.
**Goal:** Create and persist a valid codex document without specifying `type:`.

**Steps:**
1. Agent writes a `.md` file with frontmatter: `id`, `title`, `summary` — no `type:` field.
2. Agent calls `lore codex show <id>` (or `scan_codex` via Python API).
3. System parses the document through `frontmatter.py`. Validation checks for `id`, `title`, `summary` only — no `type:` check.
4. System returns the document dict with keys `{"id", "title", "summary", "group", "body"}` — no `"type"` key.
5. Agent confirms the document is visible and usable.

**Critical decision points:** If the file carries a legacy `type:` field, the system must still parse it without error (graceful ignore, not rejection).
**Success signal:** `lore codex show <id>` returns without error; the returned dict has no `"type"` key.
**Requirements revealed:** `frontmatter.py` must not fail on presence of `type:`; it must not return `type` in parsed output; `required_fields` validation must omit `type`.

---

### Workflow 2 — Human runs `lore artifact list` and sees clean output

**Persona:** Developer or agent running the CLI interactively.
**Situation:** The developer runs `lore artifact list` to discover available artifact templates. Currently the output table has five columns: `ID`, `TYPE`, `GROUP`, `TITLE`, `SUMMARY`.
**Goal:** See a clean, compact table without the redundant `TYPE` column.

**Steps:**
1. User runs `lore artifact list` in a terminal.
2. System calls `scan_artifacts()` → returns list of dicts with keys `{"id", "group", "title", "summary", "path"}` (no `"type"`).
3. CLI renders a four-column table: `ID | GROUP | TITLE | SUMMARY`.
4. User sees the output; no `TYPE` column is present.

**Critical decision points:** JSON output (`lore artifact list --json`) must also omit the `type` key from each record.
**Success signal:** Table header contains exactly `ID`, `GROUP`, `TITLE`, `SUMMARY`. JSON records have no `"type"` key.
**Requirements revealed:** `cli.py` must drop the `TYPE` column from text output and JSON serialization; `scan_artifacts()` must not return a `type` key.

---

### Workflow 3 — Developer initializes a new project and uses a default template

**Persona:** Developer or agent running `lore init` on a fresh directory.
**Situation:** `lore init` seeds the project with default artifact templates from `src/lore/defaults/artifacts/`. Currently those templates contain `type:` frontmatter.
**Goal:** The seeded templates do not contain `type:` so new projects start clean.

**Steps:**
1. Developer runs `lore init` in an empty directory.
2. System copies all files from `src/lore/defaults/artifacts/` into `.lore/artifacts/`.
3. Developer opens any seeded template file (e.g. `.lore/artifacts/codex/conceptual/entity.md`).
4. Frontmatter contains `id`, `title`, `summary` — no `type:` line.

**Critical decision points:** Templates that were previously filtered by `exclude_type="transient-marker"` need an alternative exclusion mechanism or must be handled differently.
**Success signal:** `grep -r "^type:" .lore/artifacts/` returns zero results after `lore init`.
**Requirements revealed:** All ~39 default template files in `src/lore/defaults/artifacts/` must have their `type:` line removed.

---

### Workflow 4 — Realm imports `Artifact` and processes scan results

**Persona:** Realm (Python orchestrator) using `from lore.models import Artifact` and calling `scan_artifacts()`.
**Situation:** Realm iterates over scan results and constructs `Artifact` objects. It currently accesses `.type` on each `Artifact` instance.
**Goal:** After the change, `Artifact` has no `.type` attribute; Realm must be updated separately (out of scope for this quest, but the contract change must be clearly communicated).

**Steps:**
1. Realm calls `scan_artifacts()` from `lore.artifact`.
2. `scan_artifacts()` returns list of dicts with keys `{"id", "group", "title", "summary", "path"}`.
3. Realm passes each dict to `Artifact.from_dict(d)`.
4. `Artifact.from_dict` constructs an `Artifact` with fields `id`, `group`, `title`, `summary` — no `type` field.
5. Any Realm code that accessed `artifact.type` raises `AttributeError` — Realm must be updated.

**Critical decision points:** This is a breaking API change. The CHANGELOG must document it with the version it ships in.
**Success signal:** `Artifact.from_dict({"id": "x", "title": "X", "summary": "s", "group": "g"})` succeeds without `type` key. Attempting `artifact.type` raises `AttributeError`.
**Requirements revealed:** `models.py` `Artifact` dataclass removes `type: str`; `from_dict` does not attempt `d["type"]`; `CHANGELOG.md` records the breaking change.

---

### Workflow 5 — Developer runs `lore codex search` and receives JSON without `type`

**Persona:** Developer or agent calling `lore codex search <keyword> --json`.
**Situation:** The developer pipes JSON output from `lore codex search` into a downstream tool that parses the records.
**Goal:** JSON records do not contain a `"type"` key — the contract is cleaner and smaller.

**Steps:**
1. User runs `lore codex search "frontmatter" --json`.
2. System calls `search_documents("frontmatter")` → returns list of dicts with keys `{"id", "title", "summary", "group", "path"}`.
3. CLI serializes to JSON and prints.
4. Each record in the JSON array has no `"type"` key.

**Critical decision points:** `lore codex list --json`, `lore codex map <id> --json`, and `lore codex chaos <id> --json` all share the same requirement.
**Success signal:** `lore codex search "frontmatter" --json | python3 -c "import sys, json; d=json.load(sys.stdin); assert 'type' not in d[0]"` exits 0.
**Requirements revealed:** `codex.py` search, map, and chaos functions must not include `type` in returned dicts; JSON serialization in `cli.py` must not add it.

---

## Functional Requirements

### Frontmatter Parsing (`frontmatter.py`)

- **FR-1:** The system parses a codex document that lacks a `type:` frontmatter field without raising a validation error.
- **FR-2:** The system parses a codex document that carries a legacy `type:` frontmatter field without raising an error (field is silently ignored).
- **FR-3:** The dict returned by `parse_frontmatter_doc` does not contain a `"type"` key.
- **FR-4:** The `exclude_type` parameter is removed from `parse_frontmatter_doc` and `scan_docs`; callers are updated accordingly.

### Codex Module (`codex.py`)

- **FR-5:** `scan_codex()` returns dicts with keys `{"id", "title", "summary", "group", "path"}` — no `"type"`.
- **FR-6:** `read_document()` returns a dict with keys `{"id", "title", "summary", "group", "body"}` — no `"type"`.
- **FR-7:** `search_documents()`, `map_documents()`, and `chaos_documents()` return dicts without a `"type"` key.
- **FR-8:** Any call using `exclude_type="transient-marker"` is removed or replaced with an alternative exclusion mechanism.

### Artifact Module (`artifact.py`)

- **FR-9:** `scan_artifacts()` returns dicts with keys `{"id", "title", "summary", "group", "path"}` — no `"type"`.
- **FR-10:** `read_artifact()` returns a dict without a `"type"` key.
- **FR-11:** The `required_fields` argument passed to `parse_frontmatter_doc` for artifacts omits `"type"`.

### Data Models (`models.py`)

- **FR-12:** The `Artifact` dataclass does not contain a `type` field.
- **FR-13:** The `CodexDocument` dataclass does not contain a `type` field.
- **FR-14:** `Artifact.from_dict` and `CodexDocument.from_dict` do not read `d["type"]`.
- **FR-15:** `Dependency.type` and `DoctrineStep.type` are not modified.

### CLI (`cli.py`)

- **FR-16:** `lore artifact list` text output renders columns `ID | GROUP | TITLE | SUMMARY` (four columns, no `TYPE`).
- **FR-17:** `lore artifact list --json` records do not contain a `"type"` key.
- **FR-18:** `lore codex list --json`, `lore codex search --json`, `lore codex map --json`, and `lore codex chaos --json` records do not contain a `"type"` key.

### Default Templates (`src/lore/defaults/artifacts/`)

- **FR-19:** No file under `src/lore/defaults/artifacts/` contains a `type:` frontmatter line after the change (~39 files to update).

### Tests

- **FR-20:** All unit and E2E tests pass after the change.
- **FR-21:** Tests that previously asserted `type` is present in returned dicts are updated to assert `type` is absent.
- **FR-22:** `tests/unit/test_cli_codex_list.py` assertions that `"type" not in record` continue to pass (these were already written for the expected post-change state).

### Documentation

- **FR-23:** `CHANGELOG.md` documents the removal of `Artifact.type` and `CodexDocument.type` as a breaking change, with the version it ships in.

---

## Non-Functional Requirements

### Performance

- Removing one parsed field reduces allocation slightly. No performance regressions expected; no new I/O paths introduced.

### Security

- No security surface changes. Frontmatter parsing is filesystem-local and unchanged in security posture.

### Reliability

- The change must not break parsing of existing documents that carry a legacy `type:` field. Graceful ignore is required (no crash, no warning).
- Test suite must remain at 100% pass rate.

### Backward Compatibility

- `Artifact.type` removal is a breaking change to `lore.models.__all__`. This must be version-bumped per semver and documented in `CHANGELOG.md`. Realm (the primary consumer) must update any access to `artifact.type` in a coordinated release.

---

## Open Questions

| # | Question | Owner | Priority |
|---|----------|-------|----------|
| 1 | What replaces the `transient-marker` sentinel pattern for excluding index/CODEX files from scan results? Filename convention (`CODEX.md`, `INDEX.md`) is the natural candidate, but it must be decided before `exclude_type` is removed. | Architect | High |
| 2 | Does removing `Artifact.type` require a semver major bump (0.3.x → 0.4.0 or 1.0.0), or is a minor bump with a breaking-change notice in CHANGELOG sufficient? The `standards-public-api-stability` codex doc governs this, but the policy must be applied explicitly. | PM / User | High |
| 3 | Should `lore artifact list` output keep the `GROUP` column now that `TYPE` is removed, or should the column order change? Current proposal is `ID | GROUP | TITLE | SUMMARY`. | PM / User | Medium |
| 4 | After `type` is removed from `scan_artifacts` returned dicts, do any other callers in `cli.py` or external code access `record["type"]` for artifacts? A grep of the full codebase should confirm before merge. | Tech Lead | Medium |
| 5 | The `tests/unit/test_cli_codex_list.py` currently has tests asserting `"type" not in record` that are documented as failing (current code emits `type`). Should these tests be promoted to green as part of this change, or are they gating a different ticket? | Tech Lead | Low |
