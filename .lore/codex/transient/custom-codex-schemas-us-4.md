---
id: custom-codex-schemas-us-4
title: US-4 — lore health honors overlays for both codex kinds
summary: >
  health.py gains a module-level seam project_get_validator(kind, project_root)
  re-exporting schemas.project_validator_for. _check_schemas routes the two codex
  kinds (codex-frontmatter, codex-source-frontmatter) through it and all other
  kinds through the existing get_validator(kind). A malformed overlay → exactly
  one scan_failed HealthIssue naming the overlay, no traceback, every other check
  still runs. The in-loop sources/* override and the monkeypatch seam are kept.
type: user-story
related:
  - custom-codex-schemas-tech-spec
  - custom-codex-schemas-us-2
---

## Metadata

- **ID:** US-4
- **Status:** final
- **Epic:** Validation integration
- **Author:** Tech Lead — Tech Planning
- **Date:** 2026-06-18
- **PRD:** `lore codex show custom-codex-schemas-prd`
- **Tech Spec:** `lore codex show custom-codex-schemas-tech-spec`

---

## Story

As an **agent or CI job running `lore health`**, I want **the schema audit to validate codex and source docs against the merged (packaged + overlay) schema and report a broken overlay as one clean issue**, so that **declared custom keys pass, defaults stay enforced, and a malformed overlay never crashes the audit or silently disables a kind**.

## Context

FR-8 (health validates canonical docs against merged `codex-frontmatter`, source docs against merged `codex-source-frontmatter`) and FR-10 (malformed overlay → one `scan_failed`, audit continues). The Tech Spec's Health-wiring Critical decision keeps the existing `get_validator` seam (`health.py:12`, monkeypatchable per Scout note) and adds a new module-level seam `project_get_validator(kind, project_root)` re-exporting `schemas.project_validator_for`. `_check_schemas` (`health.py:528`) calls `project_get_validator` for the two codex kinds and `get_validator` for the rest; the in-loop `sources/*` → `codex-source-frontmatter` override (`health.py:573-615`) keeps its shape but its source validator now comes from `project_get_validator`. The existing `try/except Exception` around validator resolution (`health.py:556-566`, emits `scan_failed`) catches `OverlayError` → one issue per affected kind, `validator is None` skips that kind's per-file loop, other kinds and checks run.

---

## Acceptance Criteria

### E2E Scenarios

#### Scenario 1: Source overlay honored, canonical unaffected (happy path)

**Given** an initialised project with `.lore/custom-schemas/codex-source-frontmatter.yaml` adding optional `ingested_at: {type: string}`, a source doc under `.lore/codex/sources/` carrying `ingested_at`, and a clean canonical doc
**When** the user runs `lore health --scope schemas`
**Then** exit code is `0` and the schemas line reports OK — the source doc's `ingested_at` validates against the merged source schema and the canonical doc validates against the (unmodified) merged canonical schema (FR-8).

#### Scenario 2: Malformed (collision) overlay → one scan_failed, audit continues

**Given** a project with `.lore/custom-schemas/codex-frontmatter.yaml` whose `properties` declares `title` (collides with a packaged key)
**When** the user runs `lore health --scope schemas`
**Then** exit code is non-zero, there is exactly one `scan_failed` issue with `detail` `.lore/custom-schemas/codex-frontmatter.yaml: property 'title' collides with a packaged field and cannot be overridden` and `schema_id=lore://schemas/codex-frontmatter`, no Python traceback is printed, and the other schema kinds (artifacts, doctrines, source, etc.) are still scanned (FR-10).

#### Scenario 3: No-overlay baseline identical to pre-feature

**Given** a project with no `.lore/custom-schemas/` directory
**When** the user runs `lore health --scope schemas`
**Then** output and exit code are identical to pre-feature behaviour; a doc with an undeclared custom key still fails as `Unknown property` (FR-2).

### Unit Test Scenarios

- [ ] `health.project_get_validator(kind, root)`: re-exports / returns the same validator as `schemas.project_validator_for(kind, root)`.
- [ ] `health._check_schemas`: the two codex kinds are resolved via `project_get_validator`; all other kinds via `get_validator` (FR-8).
- [ ] `health._check_schemas`: a collision overlay yields exactly one `HealthIssue(check="scan_failed")` naming the overlay path; no exception escapes; other kinds still produce their normal issues (FR-10).
- [ ] `health._check_schemas`: `sources/*` files still route to the merged `codex-source-frontmatter` validator (in-loop override preserved).
- [ ] `health._check_schemas`: monkeypatching `health.project_get_validator` is honored (test seam preserved).

---

## Out of Scope

- Resolver/merge/cache internals (US-1, US-2).
- Codex create/edit (US-5).
- The scaffolding skill (US-7).
- Any change to non-schema health checks (`related`, glossary, bindings, rites).

---

## References

- PRD: `lore codex show custom-codex-schemas-prd`
- Tech Spec: `lore codex show custom-codex-schemas-tech-spec`
- `lore codex show conceptual-workflows-health` — `_check_schemas` audit path, `scan_failed` wrapper, per-kind coverage, the `sources/*` in-loop override

---

## Tech Notes

### Implementation Approach

- **Files to modify:**
  - `src/lore/health.py` — add a module-level `project_get_validator(kind, project_root)` that calls `schemas.project_validator_for` (mirrors the existing `from lore.schemas import _validator_for as get_validator` seam at `health.py:12`, kept monkeypatchable via `sys.modules[__name__]`). In `_check_schemas` (`health.py:528`): for each `_SCHEMA_KINDS` row (`health.py:79`), if `schema_kind` ∈ {`codex-frontmatter`, `codex-source-frontmatter`} resolve `validator = project_get_validator(schema_kind, project_root)`, else `validator = get_validator(schema_kind)` — inside the existing `try/except Exception` (`health.py:556`) that emits `scan_failed` and sets `validator = None`. In the in-loop `sources/*` override (`health.py:573-615`), resolve `src_validator` via `project_get_validator("codex-source-frontmatter", project_root)` instead of `get_validator(...)`. `project_root` is already in `_check_schemas` scope.
- **Schema changes:** none.
- **Dependencies:** US-2 (`project_validator_for`).

### Test File Locations

| Type | Path | Notes |
|------|------|-------|
| E2E | `tests/e2e/test_custom_schema_overlay.py` | NEW — health-audit overlay scenarios (CliRunner) |
| Unit | `tests/unit/test_health_schema_overlay.py` | NEW — `_check_schemas` routing + scan_failed |

### Test Stubs

```python
# E2E — source overlay honored, canonical unaffected (Scenario 1, FR-8)
# Exercises: lore codex show conceptual-workflows-health, step 2 (Codex checks / schemas scope)
def test_health_honors_source_overlay(tmp_path):
    # Given: init project; write codex-source-frontmatter overlay adding ingested_at;
    #        a source doc with ingested_at; a clean canonical doc
    # When: CliRunner invoke ["health", "--scope", "schemas"]
    # Then: exit_code == 0; "schemas" reports OK; assert via result.stdout
    pass


# E2E — malformed collision overlay -> one scan_failed, audit continues (Scenario 2, FR-10)
# Exercises: lore codex show conceptual-workflows-health, step 2 (scan_failed fail-loud wrapper)
def test_health_malformed_overlay_scan_failed(tmp_path):
    # Given: codex-frontmatter overlay declaring title (collision)
    # When: invoke ["health", "--scope", "schemas", "--json"]
    # Then: exit non-zero; exactly one scan_failed issue naming the overlay path;
    #       schema_id == lore://schemas/codex-frontmatter; no traceback; other kinds present
    pass


# E2E — no-overlay baseline identical (Scenario 3, FR-2)
# Exercises: lore codex show conceptual-workflows-health, step 2
def test_health_no_overlay_baseline(tmp_path):
    # Given: project with no .lore/custom-schemas/
    # When: invoke ["health", "--scope", "schemas"]
    # Then: output/exit identical to pre-feature; a doc with custom key still Unknown property
    pass


# Unit — two codex kinds routed through project_get_validator (FR-8)
# Exercises: lore codex show conceptual-workflows-health
def test_check_schemas_routes_codex_kinds_project_aware(tmp_path, monkeypatch):
    # Given: spy/monkeypatch on health.project_get_validator and health.get_validator
    # When: _check_schemas(project_root)
    # Then: project_get_validator called with codex-frontmatter and codex-source-frontmatter;
    #       get_validator called for the other kinds
    pass


# Unit — collision overlay -> one scan_failed HealthIssue, no raise (FR-10)
# Exercises: lore codex show conceptual-workflows-health
def test_check_schemas_overlay_error_scan_failed(tmp_path):
    # Given: collision overlay for codex-frontmatter
    # When: _check_schemas(project_root)
    # Then: exactly one HealthIssue(check="scan_failed") naming the overlay; no exception;
    #       issues for other kinds still present
    pass


# Unit — sources/* still routed to merged source validator
# Exercises: lore codex show conceptual-workflows-health
def test_check_schemas_source_override_preserved(tmp_path):
    # Given: a sources/ doc and a canonical doc, source overlay present
    # When: _check_schemas
    # Then: source doc validated against merged codex-source-frontmatter (in-loop override intact)
    pass


# Unit — monkeypatch seam preserved
# Exercises: lore codex show conceptual-workflows-health
def test_project_get_validator_monkeypatchable(monkeypatch):
    # Given: monkeypatch health.project_get_validator with a stub
    # When: _check_schemas
    # Then: the stub is used (sys.modules[__name__] resolution)
    pass
```

### Complexity Estimate

**M** — Touches the densest function in the audit (`_check_schemas`), must preserve the monkeypatch seam, the `sources/*` in-loop override, and the `scan_failed` try/except shape while adding project-aware routing for exactly two kinds.

### Standards References

**Tester (Red):**
- `lore codex show conceptual-workflows-health` — exact `scan_failed` issue shape, severity-always-error, `--scope schemas` semantics.
- `lore codex show decisions-006-no-seed-content-tests` — assert audit behaviour, not packaged byte content.
- Note for the Tester: Click CLI is tested via `CliRunner` reading `result.stdout`/`result.stderr` separately (no `mix_stderr`).

**Implementer (Green):**
- `lore codex show conceptual-workflows-health` — keep the failure-isolation rule (one checker failing does not abort others).
- `lore codex show standards-dependency-inversion` — health reaches the resolver through the seam, no new cross-layer import.
