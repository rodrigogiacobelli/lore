---
id: codex-list-group-prd
feature: codex-list-group
status: draft
title: codex-list-group PRD
summary: PRD for fixing lore codex list to output ID, GROUP, TITLE, SUMMARY using _format_table, consistent with all other entity list commands.
---
# codex-list-group — PRD

**Author:** Product Manager
**Date:** 2026-03-27

---

## Executive Summary

`lore codex list` currently outputs ID, TYPE, TITLE, SUMMARY using manual f-string formatting — inconsistent with every other entity list command in the system. Knights, doctrines, artifacts, and watchers all output ID, GROUP, TITLE, SUMMARY via the shared `_format_table` helper. This feature aligns `lore codex list` with that standard: replacing the TYPE column with GROUP (derived from directory structure under `.lore/codex/`), switching to `_format_table` for rendering, and adding `group` to JSON output.

### What Makes This Special

This is the only list command in the CLI that bypasses `_format_table` and omits GROUP — fixing it makes the interface fully consistent across all entities without introducing any new logic, since both `derive_group` and `_format_table` already exist and are tested.

---

## Project Classification

| Attribute | Value |
|-----------|-------|
| Project type | CLI tool |
| Primary users | Developers and team leads using `lore` to navigate and organise codex documents |
| Scale | Single-user CLI; no throughput targets |

---

## Success Criteria

### User Success

Running `lore codex list` produces a four-column table — ID, GROUP, TITLE, SUMMARY — visually and structurally identical to the output of `lore knight list`, `lore doctrine list`, and `lore watcher list`. Users familiar with any other entity list command immediately know what to expect.

### Technical Success

| Metric | Baseline | Target | Timeline |
|--------|----------|--------|----------|
| Columns rendered by `lore codex list` | ID, TYPE, TITLE, SUMMARY (manual f-string) | ID, GROUP, TITLE, SUMMARY (via `_format_table`) | This feature |
| `group` field in `lore codex list --json` output | Absent | Present, derived from directory path | This feature |
| Renderer used by `codex_list` handler | Manual inline f-string | `_format_table` shared helper | This feature |
| Passing unit tests for `codex_list` | Existing tests | All existing tests pass; group column verified | This feature |

---

## Product Scope

### MVP

- `lore codex list` outputs ID, GROUP, TITLE, SUMMARY as a four-column table using `_format_table`
- GROUP is derived from the directory structure under `.lore/codex/` using the existing `derive_group()` function in `paths.py`
- `lore codex list --json` output includes a `group` field per document
- TYPE is removed from the default tabular view (remains available via `--json` if retained in scan output)

### Post-MVP

- Update `conceptual-workflows-codex` codex document to reflect the new column layout and JSON schema

### Out of Scope

- Changes to `scan_codex` in `codex.py` beyond what is necessary to surface `path` for group derivation (path is already returned)
- Changes to `derive_group` in `paths.py`
- Changes to `_format_table` in `cli.py`
- Any new filtering or sorting options for `lore codex list`
- Changes to `lore codex map` or any other codex subcommand

---

## User Workflows

### Listing codex documents — Developer

**Persona:** A developer using `lore` daily to reference architecture documents, workflow specs, and technical notes stored in the codex.
**Situation:** The developer runs `lore codex list` expecting the same four-column layout they see from `lore knight list` and `lore doctrine list`, but receives a TYPE column instead of GROUP, formatted differently from every other list command.
**Goal:** View a consistent, scannable list of codex documents with their group (directory-based category) clearly shown.

**Steps:**
1. Developer opens a terminal in the project root.
2. Developer runs `lore codex list`.
3. System outputs a four-column table with headers ID, GROUP, TITLE, SUMMARY. Each row shows the document's codex ID, its group derived from its subdirectory path under `.lore/codex/`, its title, and a truncated summary. Column widths are padded consistently using `_format_table`.
4. Developer immediately identifies which group a document belongs to and can decide which documents to inspect further.

**Critical decision points:** Documents stored directly under `.lore/codex/` (no subdirectory) must render with a sensible fallback group value (empty string or a default, consistent with how `derive_group` handles flat files).
**Success signal:** Output is visually identical in structure to `lore knight list` output — same four columns, same column-width padding behaviour.

---

### Consuming codex list output programmatically — Automation script

**Persona:** An automation agent or script that consumes `lore codex list --json` to build summaries or dashboards.
**Situation:** The JSON output from `lore codex list --json` lacks a `group` field, making it impossible to filter or group documents by category without parsing file paths manually.
**Goal:** Receive structured JSON that includes `group` alongside `id`, `title`, and `summary` for each document.

**Steps:**
1. Script runs `lore codex list --json`.
2. System outputs a JSON object with a `"codex"` key containing an array of document records.
3. Each record includes `"id"`, `"group"`, `"title"`, and `"summary"` fields.
4. Script filters records by `group` to process only the relevant subset of documents.

**Critical decision points:** The `group` field must be present even when it is an empty string (for documents at the root of `.lore/codex/`). The JSON key casing and structure must match the pattern established by `lore knight list --json` (i.e., `{"knights": [{...}]}`), adapted to `{"codex": [{...}]}`.
**Success signal:** `lore codex list --json | jq '.[].group'` returns a value for every document without error.

---

## Functional Requirements

### Tabular output

- **FR-1:** `lore codex list` renders output using `_format_table(["ID", "GROUP", "TITLE", "SUMMARY"], rows)`.
- **FR-2:** GROUP for each document is computed by calling `derive_group(d["path"], codex_dir)` where `codex_dir` is the `.lore/codex/` directory and `d["path"]` is the file path returned by `scan_codex`.
- **FR-3:** The TYPE column is not shown in tabular output.
- **FR-4:** Column widths are determined automatically by `_format_table`, consistent with all other entity list commands.

### JSON output

- **FR-5:** `lore codex list --json` includes a `"group"` field in each document record.
- **FR-6:** The JSON structure follows the same envelope pattern as other entity list commands (e.g., `{"codex": [{"id": ..., "group": ..., "title": ..., "summary": ...}]}`).

### Consistency

- **FR-7:** The behaviour of `lore codex list` with no flags matches the output structure of `lore knight list`, `lore doctrine list`, and `lore watcher list`.
- **FR-8:** No changes are made to `derive_group` in `paths.py` or `_format_table` in `cli.py`.

---

## Non-Functional Requirements

### Performance

- `lore codex list` must complete in the same time envelope as other entity list commands; `derive_group` is a pure string operation and adds no measurable overhead.

### Security

- No new file I/O beyond what `scan_codex` already performs; no new external calls.

### Reliability

- All existing unit tests for `codex_list` must continue to pass after the change.
- The GROUP column must be non-empty for any document stored in a subdirectory of `.lore/codex/`; the empty-string case for flat root documents must not raise an exception.

---

## Change Log

| Version | Change | Reason |
|---------|--------|--------|
| 1.0 | Initial PRD | Established based on business map, technical map, and knight/doctrine/watcher list patterns as the reference implementation |

---

## Pre-Architecture Notes

Make sure all Decisions and Standards are properly followed. We should have 100% adherence to both.

### Decisions

| ID | TITLE | SUMMARY | ADHERENCE | TO READ |
|----|-------|---------|-----------|---------|
| 001 | Dumb infrastructure design principles | ADR recording the core design principles of Lore: dumb infrastructure, short commands, single-file no-server, and minimise tool calls. The context-aware principle is noted as an unimplemented intention deferred to US-30. | | `lore codex show 001 --json` |
| 002 | PyPI package name: lore-agent-task-manager | The canonical PyPI package name is lore-agent-task-manager. The earlier working name lore-taskman has been retired and all references updated. | | `lore codex show 002 --json` |
| 003 | Soft-delete semantics and FK omission on the dependencies table | ADR explaining why soft-delete was chosen over hard-delete for all Lore entities, and why foreign key constraints were deliberately omitted from the dependencies table. | | `lore codex show 003 --json` |
| 004 | mission_type is stored and exposed, never interpreted | ADR recording the decision that Lore stores and exposes mission_type but does not interpret it or change behaviour based on it. Dispatch semantics belong to the consuming tool, not to Lore. | | `lore codex show 004 --json` |
| 005 | auto_close toggle on quests | ADR recording the decision to add a per-quest auto_close toggle, defaulting to disabled for new quests. Covers the schema design, migration default split, and the mechanism for manually closing quests. | | `lore codex show 005 --json` |
| decisions-006-id-references | Agents reference entities by ID, never by file path | ADR recording the decision that agents must use Lore CLI commands to access artifacts, doctrines, and knights by ID rather than reading file paths directly. This enforces the CLI as the only stable interface and prevents agents from bypassing the abstraction layer. | | `lore codex show decisions-006-id-references --json` |
| 006 | Do not test seed default file content | ADR recording the decision that tests must never assert on the specific content of seed default files (defaults/ directory). Only structure and existence are valid test targets. | | `lore codex show 006 --json` |
| decisions-007-artifact-communication-protocol | Artifact instances are the official communication protocol between pipeline steps | ADR recording the decision that official communication between steps in a multi-step pipeline (human or AI) happens through artifact instances, not through prose in mission descriptions or side channels. Each step declares an input artifact and produces an output artifact. This makes handoffs auditable and forces every step to produce something concrete before the next step can start. | | `lore codex show decisions-007-artifact-communication-protocol --json` |
| decisions-008-help-as-teaching-interface | CLI --help is the primary teaching interface for AI agents | ADR establishing that Lore's --help output must teach agents how the tool works — entities, concepts, and workflow — not just describe syntax. Enrichment is scoped to top-level and command-group levels only. JSON --help is deferred. AGENTS.md is reduced to ~40-50 lines. | | `lore codex show decisions-008-help-as-teaching-interface --json` |
| decisions-009-mission-self-containment | Missions must be self-contained — board messages carry the chain, artifacts carry the content | ADR establishing that a mission must be executable using only its description and its board. Board messages are lightweight operational messages posted by predecessor agents to guide successor missions. They are distinct from artifact instances (ADR-007), which carry structured work output. | | `lore codex show decisions-009-mission-self-containment --json` |
| decisions-011-api-parity-with-cli | ADR-011: Python API must be safe and behaviourally equivalent to the CLI | Establishes that every lore.db function exposed in the public API must be self-contained and safe to call directly — no pre-validation, post-processing, or business logic may live exclusively in the CLI layer. The CLI becomes a thin formatting wrapper. Any gap is a bug. | | `lore codex show decisions-011-api-parity-with-cli --json` |

### Standards

| ID | TITLE | SUMMARY | ADHERENCE | TO READ |
|----|-------|---------|-----------|---------|
| standards-dependency-inversion | Dependency Inversion | Core logic does not depend on the CLI. The dependency arrow always points inward — outer layers (CLI) depend on inner layers (business logic, validators), never the reverse. validators.py has zero lore.* imports. db.py does not import cli.py. | | `lore codex show standards-dependency-inversion --json` |
| standards-dry | DRY — Don't Repeat Yourself | Every piece of logic has one authoritative home. If the same rule, check, or transformation appears in more than one place, one of them is wrong. Covers the canonical module homes for validation, path construction, YAML parsing, and graph algorithms. | | `lore codex show standards-dry --json` |
| standards-facade | Facade | The public surface of a layer is a facade over its internals — simple, stable, and narrow. lore.models.__all__ is the stable public surface for external consumers. Internal modules may change freely without breaking the facade. | | `lore codex show standards-facade --json` |
| standards-public-api-stability | Public API Stability | Everything in lore.models.__all__ is the public API of lore-agent-task-manager. Semver policy for pre-1.0: adding names or fields → minor bump; removals, renames, or type changes → major bump or explicit breaking-change notice in CHANGELOG.md. | | `lore codex show standards-public-api-stability --json` |
| standards-separation-of-concerns | Separation of Concerns | The CLI is a concern. Business logic is a different concern. They live apart. cli.py formats terminal I/O, db.py enforces database rules, validators.py defines validation rules. Mixing these concerns is a structural defect even when tests pass. | | `lore codex show standards-separation-of-concerns --json` |
| standards-single-responsibility | Single Responsibility | A CLI handler does one thing — translate between the terminal and the core. A core function does one thing — business logic. Each module owns exactly one concern. When a unit starts doing two things, one of them belongs somewhere else. | | `lore codex show standards-single-responsibility --json` |
