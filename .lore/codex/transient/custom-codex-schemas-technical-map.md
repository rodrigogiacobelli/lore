---
id: custom-codex-schemas-technical-map
title: Context Map — Custom Codex Frontmatter Schemas (technical lens)
summary: Technical-lens context map for the Custom Codex Frontmatter Schemas feature — the schemas module loader/validator (lore.schemas), the health _check_schemas audit path and its get_validator seam, codex.py create/update validation, the two existing codex frontmatter schemas, and the DRY/dependency-inversion/parity standards the new resolver layer must satisfy. Lens carried in the body because the codex schema rejects a raw lens frontmatter key.
type: context-map
---

# Context Map — Custom Codex Frontmatter Schemas (technical lens)

**Author:** Scout (technical lens)
**Date:** 2026-06-18
**Feature:** _Add a project-aware merged-validator layer in `lore.schemas` that overlays `.lore/custom-schemas/<kind>.yaml` onto the packaged codex schemas, consumed by both `_check_schemas` and `codex.py` create/edit._
**Lens:** _technical_

> Frontmatter note: the codex schema is `additionalProperties: false` and rejects a `lens` key, so this map carries its lens in the title and the `**Lens:**` line. See Scout Notes for the exact validator behaviour.

---

## Relevant Documents

| ID | Title | Why relevant |
|----|-------|-------------|
| `custom-codex-schemas-prd` | Custom Codex Frontmatter Schemas — PRD | The spec. FR-3 (project-aware resolver cache-keyed on overlay mtime), FR-4..FR-7 (add-only merge semantics + collision rejection), FR-8/FR-9 (health + codex create/edit integration), FR-10 (malformed overlay → `scan_failed`). The implementation contract. |
| `tech-arch-schemas` | Schemas Module Internals | THE primary technical doc. Documents `load_schema`, `validate_entity`, `validate_entity_file`, `_validator_for`, the nine schema kinds, the codex-frontmatter field table, and explicitly states "User-extensible / project-local schemas are explicitly post-MVP. There is no runtime override path." — this feature reverses that line. The new resolver lives here. NOTE: the source is now `src/lore/schemas/__init__.py` (a package), with packaged `*.yaml` siblings. |
| `conceptual-workflows-health` | lore health Behaviour | The `_check_schemas` audit path. §"Schema checks (scope: schemas)" lists per-kind coverage, the always-error severity, the `iter_errors` no-short-circuit collection, the `yaml-parse`/`missing-frontmatter`/`read-failed` special rules, and the `scan_failed` fail-loud wrapper a malformed overlay must use (FR-10). The codex kind validates `.lore/codex/**/*.md` against `codex-frontmatter` and sources against `codex-source-frontmatter` via an in-loop override. |
| `tech-arch-frontmatter` | Frontmatter Module Internals | `_check_schemas` and `validate_entity_file` read frontmatter via `parse_frontmatter_raw` / the `---`-split logic in `_load_schema_payload`. The overlay merge does not change how frontmatter is parsed — only which schema it is validated against. Needed to know the exact payload shape the merged validator receives. |
| `standards-dry` | DRY — Don't Repeat Yourself | Names the canonical home for JSON-Schema validation: `lore.schemas` is the single authoritative validation module. The merged-validator resolver MUST live there so health and codex create/edit share one implementation (PRD: "resolver layer is added inside lore.schemas so both consumers share one implementation"). Building the merge in two places is a DRY violation by definition. |
| `standards-dependency-inversion` | Dependency Inversion | `schemas.py` imports only stdlib + yaml + jsonschema + `lore.frontmatter`; `validators.py` has zero `lore.*` imports. The resolver must read `.lore/custom-schemas/` without creating an import cycle and without pulling CLI concerns into the core. Constrains where the overlay-discovery code (which needs `project_root`) can sit. |
| `decisions-011-api-parity-with-cli` | ADR-011: Python API behaviourally equivalent to the CLI | The merged validator must behave identically whether reached via `lore health`/`lore codex` (CLI) or `lore.api`/`lore.schemas` (Realm importing `lore.models`). `validate_entity_file` and `load_schema` are already in the public surface; any new resolver entry point added to the public API must obey this parity. |
| `decisions-010-public-api-stability` | ADR-010: lore.api.__all__ is the stable public API contract | If the resolver exposes a new public name (e.g. a project-aware validate function), it must be re-exported through `lore.api`/`lore.models.__all__` deliberately; otherwise it is internal. Governs whether the new layer is public. |
| `decisions-014-link-direction` | Link direction — the codex is the hub | Enumerates the authoritative core edge fields (`related`, `binds`, `rites`) that an overlay must NOT redefine or weaken (FR-7). The collision-rejection set in the merge includes these plus `id`/`title`/`summary`/`type`. Source of truth for the protected-key list. |
| `tech-arch-source-layout` | Source Layout | One-line map of every `src/lore/` module — `schemas/`, `validators.py` (`validate_chaos_threshold` two-layer precedent), `paths.py` (`glossary_path`, `config_path` — pattern for adding a `custom_schemas_path` helper), `config.py` (`load_config`, `.lore/config.toml`), `root.py` (`find_project_root`). Tells you where overlay discovery, path helpers, and any validator mirror belong. |
| `tech-cli-entity-crud-matrix` | CLI Entity CRUD Matrix | Confirms no new `lore schema` command group ships (Out of Scope) — discovery is convention-driven. Codex has no CLI write path; create/edit live behind the codex create/edit story, the second consumer of the merged validator. |
| `decisions-006-no-seed-content-tests` | Do not test seed default file content | The two packaged schemas are seed/defaults; tests must assert structure and behaviour (merge result, validation outcomes), never the literal byte content of `codex-frontmatter.yaml`. Constrains the test strategy for the new resolver. |

> Add one row per relevant document. The "why relevant" column must be specific enough that a downstream agent knows exactly why to read it.

---

## How to Use This Map

Every agent that receives this map should:
1. Run `lore codex show <id1> <id2> ...` with all IDs in the table above
2. Read every document listed before starting their mission
3. Do not explore the codex independently — this map is your entry point

---

## Scout Notes

Concrete source-file findings the downstream tech-spec/planning agents need (verified by reading the code, not just docs):

- **Two distinct validation entry points consume the schemas, and BOTH must use the merged validator:**
  - **Health audit** (`src/lore/health.py` `_check_schemas`, ~line 528): iterates `_SCHEMA_KINDS` (line 79), resolves a validator per kind via `get_validator(schema_kind)` (a module-level seam = `lore.schemas._validator_for`, monkeypatchable), and for the codex root does an **in-loop per-file override** to `codex-source-frontmatter` for files under `.lore/codex/sources/` (lines ~568-619). The overlay must hook the `get_validator` seam (or a new project-aware variant) for both the `codex-frontmatter` and `codex-source-frontmatter` kinds. `_resolve_schema_candidates` (line 474) and `_load_schema_payload` (line 487) handle file discovery/parse and are unchanged by the merge.
  - **Create/edit** (`src/lore/codex.py` `create_document` ~line 121 and `update_document` ~line 193): both call `validate_entity(_DOC_TYPE_SCHEMAS[kind], meta)` on **in-memory** parsed frontmatter (NOT `validate_entity_file`). `_DOC_TYPE_SCHEMAS` (codex.py ~line 33) maps `codex`→`codex-frontmatter`, `codex-source`→`codex-source-frontmatter`. So the resolver needs a path that validates in-memory data against the merged schema, project-root aware — `validate_entity(kind, data)` currently takes no `project_root`.
- **`validate_entity` / `_validator_for` are `lru_cache`d and project-blind today.** `_validator_for(kind)` (schemas/__init__.py:55) caches by kind only — there is no `project_root` argument and no overlay awareness. FR-3 requires cache-keyed-on-overlay-mtime resolution, so the new resolver cannot reuse the existing kind-only cache unchanged; it needs a (kind, project_root, overlay_mtime) key. Mind cache invalidation in long-running processes (Realm).
- **`additionalProperties: false` is set on both `codex-frontmatter.yaml` and `codex-source-frontmatter.yaml`** (line 5 of each). After merge it must STAY false (FR-6) — declared overlay keys are added to `properties`, undeclared keys still error. `validate_entity`'s `_unexpected_keys`/`_format_message` (schemas/__init__.py:78-97) compute the "allowed keys" message from `schema.properties`, so the merged schema's `properties` must contain the custom keys for the error message to stay accurate.
- **Protected core keys** (collision-reject set, FR-7): `codex-frontmatter` declares `id, title, summary, type, related, binds, rites`; `codex-source-frontmatter` declares `id, title, summary, type, related`. An overlay property whose key is any of these for the target kind must be rejected before merge.
- **`required` append (FR-5):** packaged `required` is `[id, title, summary]` (codex) / `[id, title, summary, related]` (source). Overlay `required` entries append, and each must name a property declared in the same overlay.
- **Malformed-overlay path (FR-10):** health already has a `scan_failed` emission pattern in the `get_validator` try/except (health.py ~558) and a top-level `scan_failed` wrapper. An unparseable/non-object/rule-breaking overlay should surface through that same mechanism — one clean issue identifying the overlay, other checks continue, no stack trace.
- **`tech-arch-schemas` will need updating after this ships** — its "User-extensible / project-local schemas are explicitly post-MVP. There is no runtime override path." paragraph and the "Dependency Rules" section become stale. Flag for the codex-apply mission.
- **Glossary clean:** no term collisions (only `Constable` defined).
