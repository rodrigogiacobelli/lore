---
id: custom-codex-schemas-us-3
title: US-3 — validate_entity gains project_root keyword
summary: >
  validate_entity(kind, data, project_root=None) — additive keyword. When a
  project_root is given for the two overlay-eligible codex kinds it validates
  against project_validator_for(kind, project_root); when None (or kind not
  overlay-eligible) it falls through to today's packaged _validator_for, byte
  for byte. A declared custom key passes; an undeclared key still errors with
  Unknown property listing the custom key among allowed; OverlayError propagates.
type: user-story
related:
  - custom-codex-schemas-tech-spec
  - custom-codex-schemas-us-2
---

## Metadata

- **ID:** US-3
- **Status:** final
- **Epic:** Resolver core
- **Author:** Tech Lead — Tech Planning
- **Date:** 2026-06-18
- **PRD:** `lore codex show custom-codex-schemas-prd`
- **Tech Spec:** `lore codex show custom-codex-schemas-tech-spec`

---

## Story

As a **codex create/edit caller (and any `lore.api` consumer)**, I want **`validate_entity` to optionally take a `project_root` and validate in-memory frontmatter against the merged schema**, so that **custom keys are accepted at write time exactly as the health audit accepts them, with no second merge implementation**.

## Context

FR-9 needs create/edit to validate **in-memory** parsed frontmatter (codex.py calls `validate_entity`, not `validate_entity_file`) against the merged schema. `validate_entity(kind, data)` is project-blind today (`schemas/__init__.py:113`). The Tech Spec's Codex-create/edit-wiring Critical decision adds keyword `project_root: Path | None = None`: provided → `project_validator_for(kind, project_root)` for the two codex kinds; `None` or non-overlay kind → today's `_validator_for(kind)`. Per ADR-010 this is an additive minor bump to an already-public function (`validate_entity` is in `schemas.__all__` and `lore.api.__all__` today — verified `schemas/__init__.py:18`, `api.py:311`). The `_unexpected_keys`/`_format_message` helpers (`schemas/__init__.py:78-97`) read `schema.properties`, so a declared overlay key must appear in the merged `properties` for the "allowed keys" message to stay accurate (FR-6).

---

## Acceptance Criteria

### E2E Scenarios

E2E for this keyword is exercised end-to-end via US-5 (codex create/edit). This story's surface is the function, covered by Unit Scenarios.

### Unit Test Scenarios

- [ ] `schemas.validate_entity(kind, data, project_root=root)`: with an overlay declaring `owner`, a doc dict carrying `owner` returns `[]` (no issues) (FR-9).
- [ ] `schemas.validate_entity(..., project_root=root)`: an undeclared key (`onwer`) returns one `SchemaIssue` whose message is `Unknown property 'onwer' — allowed keys are ... owner.` (the custom key appears among allowed; FR-6).
- [ ] `schemas.validate_entity(..., project_root=root)`: a doc missing an overlay-required `owner` returns a `Missing required property 'owner'` issue (FR-5).
- [ ] `schemas.validate_entity(kind, data, project_root=None)`: identical result to `validate_entity(kind, data)` today — packaged behaviour, no overlay read (FR-2).
- [ ] `schemas.validate_entity(..., project_root=root)` for a non-overlay-eligible kind (e.g. `glossary`): uses the packaged validator, ignores `project_root`.
- [ ] `schemas.validate_entity(..., project_root=root)`: a malformed (collision) overlay → `OverlayError` raised during validator construction, before any `SchemaIssue` list is returned (FR-10).

---

## Out of Scope

- Cache mechanics (US-2) and merge rules (US-1).
- `lore health` wiring (US-4) and codex create/edit call sites (US-5).
- Public re-export of the new resolver names (US-6) — this story only changes an existing public signature.

---

## References

- PRD: `lore codex show custom-codex-schemas-prd`
- Tech Spec: `lore codex show custom-codex-schemas-tech-spec`
- `lore codex show decisions-010-public-api-stability` — additive-keyword minor bump
- `lore codex show decisions-011-api-parity-with-cli` — same merged result CLI ≡ API

---

## Tech Notes

### Implementation Approach

- **Files to modify:**
  - `src/lore/schemas/__init__.py` — change signature to `validate_entity(kind: str, data: Any, project_root: Path | None = None) -> list[SchemaIssue]`. At the top, choose the validator: if `project_root is not None` and `kind` is one of the two overlay-eligible kinds (`codex-frontmatter`, `codex-source-frontmatter`), `validator = project_validator_for(kind, project_root)`; else `validator = _validator_for(kind)` (today's line `validator = _validator_for(kind)` at `schemas/__init__.py:119`). The rest of the body (`iter_errors`, `_issue_from_error`, required-pointer aggregation) is unchanged. Define the overlay-eligible kind set once (reuse health's `codex-frontmatter`/`codex-source-frontmatter` notion; a module-level frozenset in schemas).
- **Schema changes:** none.
- **Dependencies:** US-2 (`project_validator_for`).

### Test File Locations

| Type | Path | Notes |
|------|------|-------|
| Unit | `tests/unit/test_schema_overlay_resolver.py` | extend with `validate_entity(project_root=...)` cases |

### Test Stubs

```python
# Unit — declared custom key passes (FR-9)
# Exercises: lore codex show conceptual-workflows-health (merged validator on in-memory data)
def test_validate_entity_project_root_accepts_custom_key(tmp_path):
    # Given: overlay adds owner; data has owner
    # When: validate_entity("codex-frontmatter", data, project_root=tmp_path)
    # Then: returns []
    pass


# Unit — undeclared key errors, custom key listed among allowed (FR-6)
# Exercises: lore codex show conceptual-workflows-health
def test_validate_entity_project_root_rejects_typo(tmp_path):
    # Given: overlay adds owner; data has onwer
    # When: validate_entity(..., project_root=tmp_path)
    # Then: one issue, message contains "Unknown property 'onwer'" and "owner" in allowed keys
    pass


# Unit — missing overlay-required key flagged (FR-5)
# Exercises: lore codex show conceptual-workflows-health
def test_validate_entity_project_root_missing_required(tmp_path):
    # Given: overlay marks owner required; data lacks owner
    # When: validate_entity(..., project_root=tmp_path)
    # Then: issue "Missing required property 'owner'"
    pass


# Unit — project_root=None is packaged behaviour (FR-2)
# Exercises: lore codex show conceptual-workflows-health
def test_validate_entity_none_root_is_packaged(tmp_path):
    # Given: same data
    # When: validate_entity(kind, data) vs validate_entity(kind, data, project_root=None)
    # Then: identical issues; no overlay file read
    pass


# Unit — non-overlay kind ignores project_root
# Exercises: lore codex show conceptual-workflows-health
def test_validate_entity_non_overlay_kind_ignores_root(tmp_path):
    # Given: kind="glossary", project_root=tmp_path
    # When: validate_entity
    # Then: uses packaged validator (no custom-schemas read)
    pass


# Unit — malformed overlay raises OverlayError before returning (FR-10)
# Exercises: lore codex show conceptual-workflows-health
def test_validate_entity_project_root_propagates_overlay_error(tmp_path):
    # Given: collision overlay
    # When: validate_entity(..., project_root=tmp_path)
    # Then: raises OverlayError (subclass of ValueError)
    pass
```

### Complexity Estimate

**S** — A two-line validator-selection branch on an existing function plus the kind-eligibility frozenset; behaviour reuses the untouched validation body.

### Standards References

**Tester (Red):**
- `lore codex show decisions-006-no-seed-content-tests` — assert validation outcomes, not packaged byte content.

**Implementer (Green):**
- `lore codex show decisions-010-public-api-stability` — additive keyword with default is a minor bump; do not break the no-`project_root` call.
- `lore codex show decisions-011-api-parity-with-cli` — the merged result must match what health reaches.
