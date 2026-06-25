---
id: custom-codex-schemas-us-1
title: US-1 — Overlay discovery + pure add-only merge core
summary: >
  Path helpers custom_schemas_dir / custom_schema_path in paths.py and the pure
  merge core in lore.schemas — merge_overlay, resolve_merged_schema, and the new
  OverlayError(ValueError). Implements add-only/strict/defaults-authoritative
  merge: overlay properties injected, required appended, additionalProperties
  pinned false, collision and undeclared-required rejected with OverlayError,
  packaged base never mutated, no-overlay returns packaged schema unchanged.
type: user-story
related:
  - custom-codex-schemas-tech-spec
  - custom-codex-schemas-prd
---

## Metadata

- **ID:** US-1
- **Status:** final
- **Epic:** Resolver core
- **Author:** Tech Lead — Tech Planning
- **Date:** 2026-06-18
- **PRD:** `lore codex show custom-codex-schemas-prd`
- **Tech Spec:** `lore codex show custom-codex-schemas-tech-spec`

---

## Story

As a **Lore developer wiring custom-schema support**, I want a **pure, project-aware merge function in `lore.schemas` plus the path helpers that locate overlay files**, so that **both the health audit and codex create/edit reach one add-only, defaults-authoritative merged schema with no second copy**.

## Context

This is the foundation story. The Tech Spec's first Critical decision puts the merge logic in one resolver module-region inside `lore.schemas` (`standards-dry` — `lore.schemas` is the single authoritative validation home). Everything downstream (cache, `validate_entity` keyword, health, codex) consumes the functions this story builds. It implements the locked merge semantics: add-only (FR-4 properties, FR-5 required), strict (FR-6 `additionalProperties` stays `false`), defaults-authoritative (FR-7 collision rejection), zero-overlay baseline (FR-2), and the malformed-overlay error type (FR-10 via `OverlayError`). The overlay-discovery contract (FR-1) is the two path helpers that mirror the existing `glossary_path` / `config_path` shape (`tech-arch-source-layout`).

---

## Acceptance Criteria

### E2E Scenarios

E2E behaviour for this story is exercised through the downstream health/codex stories (US-4, US-5); this story's user-facing surface is the Python API, covered by Unit Scenarios below. No standalone CLI E2E — the resolver has no command.

### Unit Test Scenarios

- [ ] `paths.custom_schemas_dir(root)`: returns `root / ".lore" / "custom-schemas"`.
- [ ] `paths.custom_schema_path(root, kind)`: returns `<root>/.lore/custom-schemas/<kind>.yaml` for both `codex-frontmatter` and `codex-source-frontmatter`.
- [ ] `schemas.merge_overlay(base, overlay, kind)`: overlay `properties` keys appear in the merged `properties` (FR-4).
- [ ] `schemas.merge_overlay`: overlay `required` entries appended onto packaged `required`, packaged entries preserved and first (FR-5).
- [ ] `schemas.merge_overlay`: merged schema's `additionalProperties` is `False` even if the overlay omits or sets it (FR-6).
- [ ] `schemas.merge_overlay`: merged `$id` equals the packaged `$id` (overlay `$id` ignored).
- [ ] `schemas.merge_overlay`: an overlay property whose key is any packaged codex key (`id`, `title`, `summary`, `type`, `related`, `binds`, `rites`) → raises `OverlayError` (FR-7).
- [ ] `schemas.merge_overlay`: for `codex-source-frontmatter`, collision set is `id`, `title`, `summary`, `type`, `related` → each collision raises `OverlayError` (FR-7).
- [ ] `schemas.merge_overlay`: a `required` entry naming a property NOT declared in the overlay `properties` → raises `OverlayError` (FR-5).
- [ ] `schemas.merge_overlay`: the packaged `base` dict passed in is not mutated (identity-stable across two merges; cache integrity).
- [ ] `schemas.resolve_merged_schema(kind, root)`: no overlay file present → returns the packaged `load_schema(kind)` content unchanged (FR-2).
- [ ] `schemas.resolve_merged_schema`: unparseable YAML overlay → `OverlayError` with message `<path>: invalid YAML: ...` (FR-10).
- [ ] `schemas.resolve_merged_schema`: top-level non-mapping overlay → `OverlayError` `<path>: overlay must be a mapping` (FR-10).
- [ ] `schemas.resolve_merged_schema`: overlay missing `properties` or `properties` not a mapping → `OverlayError` `<path>: overlay 'properties' must be a mapping` (FR-10).
- [ ] `schemas.OverlayError`: is a subclass of `ValueError`.

---

## Out of Scope

- The mtime-keyed validator cache and `project_validator_for` (US-2).
- The `validate_entity(project_root=...)` keyword (US-3).
- `lore health` wiring (US-4) and codex create/edit wiring (US-5).
- Public re-export through `lore.api` (US-6).
- The scaffolding skill (US-7).

---

## References

- PRD: `lore codex show custom-codex-schemas-prd`
- Tech Spec: `lore codex show custom-codex-schemas-tech-spec`
- `lore codex show tech-arch-schemas` — schemas module internals; resolver home
- `lore codex show standards-dry` — single validation home
- `lore codex show tech-arch-source-layout` — `glossary_path`/`config_path` helper pattern
- `lore codex show decisions-014-link-direction` — protected core edge fields (`related`/`binds`/`rites`)

---

## Tech Notes

### Implementation Approach

- **Files to modify:**
  - `src/lore/paths.py` — add `custom_schemas_dir(root: Path) -> Path` (returns `root / ".lore" / "custom-schemas"`) and `custom_schema_path(root: Path, kind: str) -> Path` (returns `custom_schemas_dir(root) / f"{kind}.yaml"`), mirroring `glossary_path` (`paths.py:56`) and `config_path` (`paths.py:64`).
  - `src/lore/schemas/__init__.py` — add `class OverlayError(ValueError)` (precedent: `ImpactsError(ValueError)` at `impacts.py:24`); add pure `merge_overlay(base: dict, overlay: dict, kind: str) -> dict` (deep-copies `base`, injects overlay `properties`, appends overlay `required`, pins `additionalProperties = False`, leaves `$id`); add `resolve_merged_schema(kind: str, project_root: Path) -> dict` (stat the overlay via `paths.custom_schema_path`; absent → `load_schema(kind)`; present → `yaml.safe_load`, validate shape, call `merge_overlay`). Imports needed: `copy`, `os`/`pathlib`, `yaml` (already used by `load_schema`), `lore.paths`. `validators.py` stays untouched (`standards-dependency-inversion`).
- **Schema changes:** none to packaged `*.yaml`; the merge synthesises everything from `load_schema(kind)`.
- **Dependencies:** none — this is the base story.

### Test File Locations

| Type | Path | Notes |
|------|------|-------|
| Unit | `tests/unit/test_schema_overlay_resolver.py` | NEW — merge + resolve + paths helpers |

### Test Stubs

```python
# Unit — custom_schema_path resolves both kinds
# Exercises: lore codex show conceptual-workflows-health (schemas scope path discovery)
def test_custom_schema_path_resolves_both_kinds(tmp_path):
    # Given: a project root
    # When: custom_schema_path(root, "codex-frontmatter")
    # Then: == root/.lore/custom-schemas/codex-frontmatter.yaml; same for codex-source-frontmatter
    pass


# Unit — merge injects overlay properties (FR-4)
# Exercises: lore codex show conceptual-workflows-health (schema checks use merged validator)
def test_merge_overlay_adds_properties():
    # Given: packaged codex-frontmatter base, overlay with properties.owner
    # When: merge_overlay(base, overlay, "codex-frontmatter")
    # Then: merged["properties"]["owner"] present; packaged keys still present
    pass


# Unit — merge appends required (FR-5)
# Exercises: lore codex show conceptual-workflows-health
def test_merge_overlay_appends_required():
    # Given: overlay required=[owner] with owner in properties
    # When: merge
    # Then: merged["required"] == packaged_required + ["owner"]; packaged entries first
    pass


# Unit — additionalProperties stays false (FR-6)
# Exercises: lore codex show conceptual-workflows-health
def test_merge_overlay_keeps_additional_properties_false():
    # Given: overlay with no additionalProperties (and one that sets it true)
    # When: merge
    # Then: merged["additionalProperties"] is False
    pass


# Unit — collision with packaged key rejected (FR-7)
# Exercises: lore codex show conceptual-workflows-health
def test_merge_overlay_rejects_packaged_collision():
    # Given: overlay declaring properties.title for codex-frontmatter
    # When: merge
    # Then: raises OverlayError naming 'title'; parametrize over id,title,summary,type,related,binds,rites
    pass


# Unit — undeclared required rejected (FR-5)
# Exercises: lore codex show conceptual-workflows-health
def test_merge_overlay_rejects_undeclared_required():
    # Given: overlay required=[ghost] but properties has no ghost
    # When: merge
    # Then: raises OverlayError naming 'ghost'
    pass


# Unit — packaged base not mutated (cache integrity)
# Exercises: lore codex show conceptual-workflows-health
def test_merge_overlay_does_not_mutate_base():
    # Given: a base dict
    # When: merge twice
    # Then: base["properties"] unchanged, base["required"] unchanged
    pass


# Unit — no overlay returns packaged schema unchanged (FR-2)
# Exercises: lore codex show conceptual-workflows-health
def test_resolve_no_overlay_returns_packaged(tmp_path):
    # Given: project root with no .lore/custom-schemas/codex-frontmatter.yaml
    # When: resolve_merged_schema("codex-frontmatter", tmp_path)
    # Then: == load_schema("codex-frontmatter")
    pass


# Unit — unparseable YAML overlay raises OverlayError (FR-10)
# Exercises: lore codex show conceptual-workflows-health (scan_failed fail-loud wrapper)
def test_resolve_unparseable_yaml_raises(tmp_path):
    # Given: overlay file with broken YAML
    # When: resolve_merged_schema
    # Then: raises OverlayError, message contains "invalid YAML"
    pass


# Unit — non-mapping / missing-properties overlay raises OverlayError (FR-10)
# Exercises: lore codex show conceptual-workflows-health
def test_resolve_malformed_shape_raises(tmp_path):
    # Given: overlay that is a list (non-mapping) / a mapping lacking properties
    # When: resolve_merged_schema
    # Then: raises OverlayError with the matching message
    pass


# Unit — OverlayError subclasses ValueError
# Exercises: lore codex show conceptual-workflows-health
def test_overlay_error_is_value_error():
    assert issubclass(OverlayError, ValueError)
```

### Complexity Estimate

**M** — Pure functions and path helpers, but the full add-only rule matrix (collision sets per kind, required-declared check, mutation safety, malformed-shape branches) is the densest test surface in the feature.

### Standards References

**Tester (Red):**
- `lore codex show decisions-006-no-seed-content-tests` — assert merge structure/behaviour, never the byte content of packaged `codex-frontmatter.yaml` / `codex-source-frontmatter.yaml`.
- `lore codex show decisions-014-link-direction` — protected key set the collision tests must cover.

**Implementer (Green):**
- `lore codex show standards-dry` — the merge lives only in `lore.schemas`.
- `lore codex show standards-dependency-inversion` — resolver imports stdlib + yaml + jsonschema + `lore.paths` only; `validators.py` untouched.
- `lore codex show tech-arch-source-layout` — `glossary_path`/`config_path` shape for the new path helpers.
