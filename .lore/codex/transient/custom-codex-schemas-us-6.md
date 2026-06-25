---
id: custom-codex-schemas-us-6
title: US-6 — Public API re-export of resolver names
summary: >
  Re-export resolve_merged_schema, project_validator_for, and OverlayError
  through the # --- Schemas --- import block in api.py and add them to
  lore.api.__all__, keeping the facade a pure re-export module (zero def/class).
  Verifies CLI ≡ API parity — project_validator_for and validate_entity(
  project_root=...) reach the identical merged validator from both surfaces.
type: user-story
related:
  - custom-codex-schemas-tech-spec
  - custom-codex-schemas-us-2
---

## Metadata

- **ID:** US-6
- **Status:** final
- **Epic:** Validation integration
- **Author:** Tech Lead — Tech Planning
- **Date:** 2026-06-18
- **PRD:** `lore codex show custom-codex-schemas-prd`
- **Tech Spec:** `lore codex show custom-codex-schemas-tech-spec`

---

## Story

As a **Realm developer importing `lore.api`**, I want **the new resolver names exposed as deliberate public API**, so that **the orchestrator reaches the merged validator the same way the CLI does, with the public contract documented in `lore.api.__all__`**.

## Context

ADR-010 (`decisions-010-public-api-stability`): any new public name is deliberate and re-exported through `lore.api.__all__`. The Tech Spec's New-public-names decision (reconciliation R-1) places `resolve_merged_schema`, `project_validator_for`, and `OverlayError` in the existing `# --- Schemas ---` import block (`api.py:128`) and adds them to `lore.api.__all__` (`api.py:170`), keeping `api.py` a pure re-export facade with zero `def`/`class` (`tech-arch-api-facade`). ADR-011 (`decisions-011-api-parity-with-cli`): the merged validator must be reachable identically from CLI and `lore.api`. `validate_entity` is already public (US-3 only widens its signature, no re-export change).

---

## Acceptance Criteria

### E2E Scenarios

#### Scenario 1: New names import from lore.api

**Given** the installed package
**When** a consumer runs `from lore.api import resolve_merged_schema, project_validator_for, OverlayError`
**Then** all three import successfully and each name is present in `lore.api.__all__`.

### Unit Test Scenarios

- [ ] `lore.api.__all__`: contains `resolve_merged_schema`, `project_validator_for`, `OverlayError`.
- [ ] `lore.api`: importing each name yields the same object as `lore.schemas`'s (`lore.api.project_validator_for is lore.schemas.project_validator_for`, etc.).
- [ ] `api.py` facade purity: the module defines zero `def`/`class` statements (re-export only) — guard test or AST scan stays green after the additions.
- [ ] Parity: `lore.api.validate_entity(kind, data, project_root=root)` and `lore.schemas.validate_entity(kind, data, project_root=root)` return identical results for a declared custom key (ADR-011).

---

## Out of Scope

- Resolver/cache/keyword behaviour (US-1, US-2, US-3) — this story only exposes them.
- Health and codex wiring (US-4, US-5).
- The scaffolding skill (US-7).

---

## References

- PRD: `lore codex show custom-codex-schemas-prd`
- Tech Spec: `lore codex show custom-codex-schemas-tech-spec`
- `lore codex show decisions-010-public-api-stability` — `__all__` is the public contract
- `lore codex show decisions-011-api-parity-with-cli` — CLI ≡ API
- `lore codex show tech-arch-api-facade` — `api.py` is a pure re-export facade

---

## Tech Notes

### Implementation Approach

- **Files to modify:**
  - `src/lore/api.py` — extend the `# --- Schemas ---` import line (`api.py:129`, currently `from lore.schemas import load_schema, validate_entity, validate_entity_file`) to also import `resolve_merged_schema, project_validator_for, OverlayError`. Add the three names to `lore.api.__all__` (the block starting `api.py:170`, near the existing `"load_schema"`, `"validate_entity"`, `"validate_entity_file"` entries at `api.py:310-312`). No `def`/`class` added — pure re-export preserved.
  - No `lore.models` edit: `src/lore/models.py` is the dataclass/enum module (verified — `from lore.rite import RiteError`, its own `__all__` at `models.py:454`), not a star re-export of `lore.api`. The resolver's public surface is `lore.api.__all__` only, matching how `load_schema`/`validate_entity`/`validate_entity_file` are exposed.
- **Schema changes:** none.
- **Dependencies:** US-1 (`resolve_merged_schema`, `OverlayError`) and US-2 (`project_validator_for`) must define the names first.

### Test File Locations

| Type | Path | Notes |
|------|------|-------|
| Unit | `tests/unit/test_schema_overlay_resolver.py` | extend with the API-surface assertions, or co-locate with the repo's existing api-`__all__` test if one exists |

### Test Stubs

```python
# E2E / import — new names public from lore.api and lore.models (Scenario 1)
# Exercises: lore codex show conceptual-workflows-health (consumers reach the merged validator)
def test_resolver_names_public():
    import lore.api as api
    for name in ("resolve_merged_schema", "project_validator_for", "OverlayError"):
        assert name in api.__all__
        assert getattr(api, name) is getattr(__import__("lore.schemas", fromlist=[name]), name)
    pass


# Unit — api.py stays a pure re-export facade (no def/class)
# Exercises: lore codex show conceptual-workflows-health
def test_api_facade_has_no_definitions():
    # AST-scan src/lore/api.py: zero FunctionDef / ClassDef nodes
    pass


# Unit — parity: api and schemas validate_entity agree (ADR-011)
# Exercises: lore codex show conceptual-workflows-health
def test_validate_entity_parity_api_vs_schemas(tmp_path):
    # Given: overlay adding owner; data with owner
    # When: lore.api.validate_entity(..., project_root=tmp_path) and lore.schemas.validate_entity(...)
    # Then: identical (both [])
    pass
```

### Complexity Estimate

**S** — One import-line extension plus three `__all__` entries; the only care is preserving facade purity (the existing facade-purity guard covers it).

### Standards References

**Tester (Red):**
- `lore codex show decisions-010-public-api-stability` — the `__all__` membership is the assertion.

**Implementer (Green):**
- `lore codex show tech-arch-api-facade` — keep `api.py` zero-`def`/`class`.
- `lore codex show decisions-011-api-parity-with-cli` — names must be the same objects as `lore.schemas`.
