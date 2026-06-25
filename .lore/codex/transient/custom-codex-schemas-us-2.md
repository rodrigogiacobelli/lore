---
id: custom-codex-schemas-us-2
title: US-2 — Project-aware validator with mtime-keyed cache
summary: >
  project_validator_for(kind, project_root) builds a Draft202012Validator from
  resolve_merged_schema and caches it on key (kind, str(project_root),
  overlay_mtime_ns), where overlay_mtime_ns is os.stat(overlay).st_mtime_ns or
  sentinel -1 when no overlay exists. An edited overlay bumps mtime → new key →
  re-read within a long-running process (Realm). Cannot reuse the kind-only
  lru_cache on _validator_for (project-blind and mtime-blind).
type: user-story
related:
  - custom-codex-schemas-tech-spec
  - custom-codex-schemas-us-1
---

## Metadata

- **ID:** US-2
- **Status:** final
- **Epic:** Resolver core
- **Author:** Tech Lead — Tech Planning
- **Date:** 2026-06-18
- **PRD:** `lore codex show custom-codex-schemas-prd`
- **Tech Spec:** `lore codex show custom-codex-schemas-tech-spec`

---

## Story

As a **long-running consumer of `lore.schemas` (Realm importing `lore.models`)**, I want **the merged validator to be cached on the overlay's mtime**, so that **repeated validation is cheap but an edited overlay is re-read mid-process without restarting**.

## Context

FR-3 requires project-aware resolution cache-keyed on the overlay file's mtime. The Tech Spec's Cache-strategy Critical decision pins the key to `(kind, str(project_root), overlay_mtime_ns)` with `overlay_mtime_ns = os.stat(overlay).st_mtime_ns` or sentinel `-1` when absent. The existing kind-only `lru_cache` on `_validator_for` (`schemas/__init__.py:56`) is project-blind and mtime-blind and is explicitly rejected for reuse (Crazy-Findings table). This story builds `project_validator_for` on top of US-1's `resolve_merged_schema`.

---

## Acceptance Criteria

### E2E Scenarios

E2E cache behaviour surfaces through US-4 (health re-reads an edited overlay). This story's surface is the Python API, covered by Unit Scenarios.

### Unit Test Scenarios

- [ ] `schemas.project_validator_for(kind, root)`: returns a `jsonschema.Draft202012Validator` whose schema is `resolve_merged_schema(kind, root)`.
- [ ] `schemas.project_validator_for`: two calls with an unchanged overlay return the same cached validator object (identity).
- [ ] `schemas.project_validator_for`: after the overlay file is rewritten so its `st_mtime_ns` changes (`os.utime`), the next call returns a different validator reflecting the new overlay (FR-3).
- [ ] `schemas.project_validator_for`: with no overlay file, the cache key uses sentinel `-1` and does not collide with the same kind once an overlay is added.
- [ ] `schemas.project_validator_for`: an `OverlayError` from `resolve_merged_schema` (malformed overlay) propagates to the caller, not swallowed.

---

## Out of Scope

- The merge rules themselves (US-1).
- `validate_entity(project_root=...)` (US-3).
- Health / codex wiring (US-4, US-5).
- Public re-export (US-6).

---

## References

- PRD: `lore codex show custom-codex-schemas-prd`
- Tech Spec: `lore codex show custom-codex-schemas-tech-spec`
- `lore codex show tech-arch-schemas` — `_validator_for` lru_cache it must NOT reuse

---

## Tech Notes

### Implementation Approach

- **Files to modify:**
  - `src/lore/schemas/__init__.py` — add `project_validator_for(kind: str, project_root: Path) -> jsonschema.Draft202012Validator`. Implement an explicit dict cache keyed on `(kind, str(project_root), overlay_mtime_ns)` (NOT `functools.lru_cache`, which can't key on a live mtime). Compute `overlay_mtime_ns` via `os.stat(paths.custom_schema_path(root, kind)).st_mtime_ns`, catching `FileNotFoundError` → sentinel `-1`. On cache miss build `Draft202012Validator(resolve_merged_schema(kind, root))`. Add `project_validator_for` to `schemas.__all__` (line 17) alongside the new names.
- **Schema changes:** none.
- **Dependencies:** US-1 (`resolve_merged_schema`, `custom_schema_path`, `OverlayError`).

### Test File Locations

| Type | Path | Notes |
|------|------|-------|
| Unit | `tests/unit/test_schema_overlay_resolver.py` | extend US-1 file with cache cases |

### Test Stubs

```python
# Unit — validator built from merged schema
# Exercises: lore codex show conceptual-workflows-health (per-kind validator resolution)
def test_project_validator_uses_merged_schema(tmp_path):
    # Given: overlay adding owner
    # When: project_validator_for("codex-frontmatter", tmp_path)
    # Then: validator.schema["properties"] contains owner
    pass


# Unit — same validator cached for unchanged overlay
# Exercises: lore codex show conceptual-workflows-health
def test_project_validator_cache_hit_unchanged_overlay(tmp_path):
    # Given: an overlay
    # When: project_validator_for called twice
    # Then: the two returned objects are identical (is)
    pass


# Unit — mtime bump busts cache (FR-3)
# Exercises: lore codex show conceptual-workflows-health
def test_project_validator_rereads_on_mtime_change(tmp_path):
    # Given: overlay adding owner -> validator A
    # When: rewrite overlay to add reviewed, os.utime to bump st_mtime_ns
    # Then: next call returns validator B != A, schema has reviewed
    pass


# Unit — no-overlay sentinel key distinct from overlay key
# Exercises: lore codex show conceptual-workflows-health
def test_project_validator_sentinel_key_no_collision(tmp_path):
    # Given: no overlay -> validator (sentinel -1)
    # When: add an overlay later
    # Then: new call returns a different validator reflecting the overlay
    pass


# Unit — OverlayError propagates through the cache layer
# Exercises: lore codex show conceptual-workflows-health (scan_failed fail-loud relies on propagation)
def test_project_validator_propagates_overlay_error(tmp_path):
    # Given: a malformed (collision) overlay
    # When: project_validator_for
    # Then: raises OverlayError
    pass
```

### Complexity Estimate

**S** — One cached function over US-1's resolver; the only subtlety is the explicit mtime-keyed cache (not `lru_cache`) and the absent-file sentinel.

### Standards References

**Tester (Red):**
- `lore codex show decisions-006-no-seed-content-tests` — assert validator behaviour, bump mtime via `os.utime` in `tmp_path`.

**Implementer (Green):**
- `lore codex show tech-arch-schemas` — why the kind-only `_validator_for` lru_cache cannot be reused; FR-3 needs the `(kind, project_root, mtime_ns)` key.
- `lore codex show standards-dry` — single resolver home.
