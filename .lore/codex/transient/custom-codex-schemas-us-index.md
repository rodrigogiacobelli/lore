---
id: custom-codex-schemas-us-index
title: Custom Codex Frontmatter Schemas — User Story Index
summary: >
  Index and coverage map for the seven user stories carving the Custom Codex
  Frontmatter Schemas Tech Spec into sized, testable deliverables. Maps every
  Tech Spec Critical/Important decision and every PRD FR (FR-1..FR-13) to at
  least one story across three epics — Resolver core, Validation integration,
  and Authoring experience. Sizes: US-1 M, US-2 S, US-3 S, US-4 M, US-5 S,
  US-6 S, US-7 S.
type: user-story-index
related:
  - custom-codex-schemas-tech-spec
  - custom-codex-schemas-prd
  - custom-codex-schemas-us-1
  - custom-codex-schemas-us-2
  - custom-codex-schemas-us-3
  - custom-codex-schemas-us-4
  - custom-codex-schemas-us-5
  - custom-codex-schemas-us-6
  - custom-codex-schemas-us-7
---

# Custom Codex Frontmatter Schemas — User Story Index

**Author:** Tech Lead — Tech Planning
**Date:** 2026-06-18
**Status:** final
**PRD:** `lore codex show custom-codex-schemas-prd`
**Tech Spec:** `lore codex show custom-codex-schemas-tech-spec`

---

## Stories by Epic

### Resolver core

The single add-only merge home in `lore.schemas` plus its mtime-keyed cache and the `validate_entity` keyword — the foundation both consumers share (`standards-dry`).

| ID | Title | Status | Codex ID | Size |
|----|-------|--------|----------|------|
| US-1 | Overlay discovery + pure add-only merge core | final | `custom-codex-schemas-us-1` | M |
| US-2 | Project-aware validator with mtime-keyed cache | final | `custom-codex-schemas-us-2` | S |
| US-3 | `validate_entity` gains `project_root` keyword | final | `custom-codex-schemas-us-3` | S |

### Validation integration

Wiring the merged validator into the two consumers (health audit, codex create/edit) and exposing the resolver as deliberate public API.

| ID | Title | Status | Codex ID | Size |
|----|-------|--------|----------|------|
| US-4 | `lore health` honors overlays for both codex kinds | final | `custom-codex-schemas-us-4` | M |
| US-5 | `lore codex` create/edit accept declared custom keys | final | `custom-codex-schemas-us-5` | S |
| US-6 | Public API re-export of resolver names | final | `custom-codex-schemas-us-6` | S |

### Authoring experience

The scaffolding skill that drafts a valid overlay so authors never hand-write JSON-Schema.

| ID | Title | Status | Codex ID | Size |
|----|-------|--------|----------|------|
| US-7 | `new-custom-schema` scaffolding skill | final | `custom-codex-schemas-us-7` | S |

---

## PRD / Tech-Spec Coverage Map

Every PRD functional requirement and every Tech Spec Critical/Important decision maps to at least one story. Deferred rows are intentionally unmapped (no story builds a deferral).

### PRD Functional Requirements

| PRD Requirement | Story IDs |
|-----------------|-----------|
| FR-1: discover overlay at `.lore/custom-schemas/<kind>.yaml` (codex-frontmatter, codex-source-frontmatter) | US-1 |
| FR-2: no overlay → behaviour exactly as today | US-1, US-3, US-4, US-5 |
| FR-3: project-aware, cache-keyed on overlay mtime | US-2 |
| FR-4: overlay `properties` merged into packaged `properties` | US-1 |
| FR-5: overlay `required` appended; each names a property the overlay declares | US-1 |
| FR-6: merged schema keeps `additionalProperties: false`; undeclared key still errors | US-1, US-3, US-5 |
| FR-7: overlay property colliding with a packaged key rejected | US-1 |
| FR-8: `lore health` validates canonical vs source docs against the merged schemas | US-4 |
| FR-9: `lore codex` create/edit validate against the merged schema | US-3, US-5 |
| FR-10: malformed overlay → one clean `scan_failed`, audit never raises | US-1, US-4, US-5 |
| FR-11: skill collects kind + field names/types/required, writes valid overlay | US-7 |
| FR-12: skill enforces add-only rules (collision + undeclared-required) before writing | US-7 |
| FR-13: skill validates the result (`lore health`) after writing | US-7 |
| Workflow: "Add a custom frontmatter field — Codex maintainer" | US-4, US-5, US-7 |
| Workflow: "Health audit honors the overlay — Agent or CI" | US-4 |
| NFR Compatibility/Parity: every behaviour reachable from CLI and `lore.api`; resolver shared | US-3, US-5, US-6 |
| NFR Reliability: malformed → reported, no crash; no-overlay byte-identical | US-1, US-4 |
| NFR Security: `yaml.safe_load`, add-only bounds blast radius | US-1 |

### Tech Spec Architectural Decisions

| Tech Spec decision | Story IDs |
|--------------------|-----------|
| Critical: merge logic in one `lore.schemas` resolver region (`resolve_merged_schema`, `merge_overlay`, `project_validator_for`) | US-1, US-2 |
| Critical: overlay discovery contract + `paths.custom_schemas_dir`/`custom_schema_path` | US-1 |
| Critical: add-only merge semantics (properties/required/additionalProperties/collision) | US-1 |
| Critical: cache key `(kind, str(project_root), overlay_mtime_ns)`, sentinel -1 | US-2 |
| Critical: health wiring — `project_get_validator` seam, two codex kinds | US-4 |
| Critical: codex create/edit wiring — `validate_entity` gains `project_root` | US-3, US-5 |
| Critical: malformed overlay → `OverlayError(ValueError)` → `scan_failed` / propagating `ValueError` | US-1, US-4, US-5 |
| Important: scaffolding skill `new-custom-schema` (seed + repo copy) | US-7 |
| Important: no new CLI command — only the resolver + the `validate_entity` keyword | US-3, US-6 (and honored as Out of Scope across all stories) |
| API: new public names re-exported via `api.py` `# --- Schemas ---` block + `lore.api.__all__`; facade purity | US-6 |
| ADR & Standards Audit — reconciliations R-1 (public-surface placement) and R-2 (create/edit error path) | US-6 (R-1), US-5 (R-2) |
| Deferred: knight/artifact/doctrine overlays; per-doc-type overlays; `--show` inspect | _none — Post-MVP, intentionally unmapped_ |

### Codex Apply hand-off (not a Tech-Planning story)

The Tech Spec's "Migration & Rollback → Stale-doc flag" and the ADR & Standards Audit route the `tech-arch-schemas` doc update ("User-extensible / project-local schemas are explicitly post-MVP. There is no runtime override path." reversal) and three forward-looking ADR records (overlay-is-path-config classification, the `project_get_validator` health-seam convention, the `OverlayError(ValueError)` convention) to the Codex Apply mission `m-984e`. These are documentation deliverables, not implementation stories, and are deliberately NOT carved here.

---

## Summary

| Total stories | Epics | Draft | Final |
|---------------|-------|-------|-------|
| 7 | 3 | 0 | 7 |

Sizes: US-1 **M**, US-2 **S**, US-3 **S**, US-4 **M**, US-5 **S**, US-6 **S**, US-7 **S**.

## Dev Cycle Groups
- G1: [custom-codex-schemas-us-1, custom-codex-schemas-us-2, custom-codex-schemas-us-3] — Resolver core: merge/path helpers, mtime-keyed validator cache, and the `validate_entity` keyword all live in `lore.schemas` with a strict US-1→US-2→US-3 dependency chain — one coherent module-building session
- G2: [custom-codex-schemas-us-4, custom-codex-schemas-us-5, custom-codex-schemas-us-6] — Validation integration: wires the resolver into both consumers (health `_check_schemas`, codex create/edit) and re-exports the public names; US-4/US-5 share one E2E file (`test_custom_schema_overlay.py`) and US-6 is the one-line `api.py` re-export finalizing that public surface
- G3: [custom-codex-schemas-us-7] — Authoring experience: markdown-only `new-custom-schema` skill (repo copy + seed), no production code or unit tests — separate session whose guard prose mirrors the now-settled G1 merge rules
