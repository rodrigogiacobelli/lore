---
id: tech-arch-schemas
title: Schemas Module Internals
summary: Technical reference for src/lore/schemas.py and the packaged src/lore/schemas/*.yaml JSON Schemas. Covers the loader, validate_entity / validate_entity_file, the six schema kinds, the special yaml-parse / missing-frontmatter / read-failed rules, and how create-time validators in doctrine/knight/watcher/artifact and the audit-time lore health schema check share a single authoritative contract.
related: ["tech-arch-source-layout", "tech-arch-frontmatter", "tech-overview", "conceptual-workflows-health", "tech-doctrine-internals", "standards-dry", "standards-dependency-inversion", "decisions-011-api-parity-with-cli"]
---

# Schemas Module Internals

**Source module:** `src/lore/schemas.py`
**Resource dir:** `src/lore/schemas/*.yaml` (packaged inside the wheel via hatchling `package-data`)

This module is the single authoritative home for the JSON Schemas that define the shape of every on-disk Lore entity. It is consumed by both the create-time validators in `doctrine.py`, `knight.py`, `watcher.py`, and `artifact.py` **and** by the audit-time `_check_schemas` checker in `health.py`. No schema content is duplicated anywhere else in the codebase — this is the DRY guarantee required by FR-19/FR-20 of the schema validation feature.

## Why This Module Exists

`validators.py` has a hard rule of zero `lore.*` imports. Schema loading needs to read packaged resources via `importlib.resources` and is reused by multiple entity modules, so it cannot live in `validators.py` without breaking dependency inversion. A new module — `schemas.py` — is the only placement that:

1. Keeps `validators.py` pure.
2. Gives create-time validators and the health checker a single authoritative home for schema logic.
3. Reads the packaged YAML schemas once per process.

## Schema Kinds

Six entity kinds are validated. Each kind is a short slug that appears in `HealthIssue.entity_type`, in the `$id` of the schema (`lore://schemas/<kind>`), and in the schema filename (`src/lore/schemas/<kind>.yaml`):

| Kind | Source pattern | Schema `$id` |
|---|---|---|
| `doctrine-yaml` | `.lore/doctrines/**/*.yaml` | `lore://schemas/doctrine-yaml` |
| `doctrine-design-frontmatter` | Frontmatter of `.lore/doctrines/**/*.design.md` | `lore://schemas/doctrine-design-frontmatter` |
| `knight` | Frontmatter of `.lore/knights/**/*.md` | `lore://schemas/knight-frontmatter` |
| `watcher` | `.lore/watchers/**/*.yaml` | `lore://schemas/watcher-yaml` |
| `codex` | Frontmatter of `.lore/codex/**/*.md` | `lore://schemas/codex-frontmatter` |
| `artifact` | Frontmatter of `.lore/artifacts/**/*.md` | `lore://schemas/artifact-frontmatter` |

Schemas are authored as YAML (not JSON) because they were drafted as fenced YAML blocks and the YAML-at-rest form stays diff-friendly and self-documenting. PyYAML is already a dependency.

## Public Interface

### `load_schema(kind: str) -> dict`

Loads the packaged schema for the given kind via `importlib.resources.files("lore.schemas") / f"{kind}.yaml"` and parses it with `yaml.safe_load`. Cached for the lifetime of the process. Raises `FileNotFoundError` with a clear message for an unknown kind.

### `validate_entity(kind: str, data: dict) -> list[tuple[str, str, str]]`

Pure-data validator. Given a kind and a parsed mapping, returns a list of `(rule, pointer, message)` tuples — one per validation failure. Empty list means valid. Uses a cached `jsonschema.Draft202012Validator(load_schema(kind))` and collects every violation via `iter_errors` (no short-circuit on the first error — FR-9).

The validator is compiled once per kind and reused across all files of that kind within a `health_check()` invocation. This keeps the PRD's ≤200 ms overhead budget on a typical project intact.

### `validate_entity_file(path: Path, kind: str) -> list[HealthIssueTuple]`

Full file-level validator. Dispatches by kind:

- **Full-YAML kinds** (`doctrine-yaml`, `watcher`): calls `yaml.safe_load` on the file contents.
- **Frontmatter kinds** (`doctrine-design-frontmatter`, `knight`, `codex`, `artifact`): calls `frontmatter.parse_frontmatter_raw(path)` to obtain the raw mapping preserving every key.

Error translation:

| Condition | Emitted issue |
|---|---|
| Unparseable YAML | single `(rule="yaml-parse", pointer="/", message=<parser msg>)` — validation of that file stops here (FR-10) |
| Frontmatter-validated file with no `---` block | single `(rule="missing-frontmatter", pointer="/", message="File has no YAML frontmatter block")` (FR-11) |
| `OSError` / `UnicodeDecodeError` on read | single `(rule="read-failed", pointer="/", message=str(exc))`; validation continues on the next file |
| Schema validation errors | one tuple per violation, with `rule=<validator keyword>`, `pointer=<JSON Pointer>`, `message=<human-readable>` |

`validate_entity_file` and `load_schema` are both added to `lore.models.__all__` so Realm can call them directly — ADR-011 parity.

## Reuse at Create Time (FR-20)

The existing private create-time validators in `doctrine.py`, `knight.py`, `watcher.py`, and `artifact.py` keep their current signatures and exception types (callers outside the module see no change), but internally delegate to `lore.schemas.validate_entity(kind, data)`:

| Callsite | Delegates to |
|---|---|
| `doctrine._validate_yaml_schema(data, name)` | `validate_entity("doctrine-yaml", data)` |
| `doctrine._validate_design_frontmatter(meta, name)` | `validate_entity("doctrine-design-frontmatter", meta)` |
| `knight.create_knight` frontmatter check | `validate_entity("knight", meta)` |
| `watcher.create_watcher` YAML shape check | `validate_entity("watcher", data)` |
| `artifact.create_artifact` frontmatter re-check | `validate_entity("artifact", meta)` |

One schema, one contract, enforced at both write time and audit time. Any drift in the future is a DRY violation by definition.

## Reuse at Audit Time

`health._check_schemas(project_root)` walks every entity directory using the same glob patterns the existing per-entity checkers and loaders use, invokes `validate_entity_file(path, kind)` per file, and wraps each returned tuple in a `HealthIssue` with:

- `severity="error"` (schema violations are always errors, never warnings)
- `entity_type=kind`
- `id=<path relative to project root>`
- `check="schema"`
- `detail=<message>`
- `schema_id=f"lore://schemas/{kind}"`
- `rule`, `pointer` from the tuple

A catastrophic failure loading the schema resource itself (e.g. the wheel is corrupted) raises out of `_check_schemas` and is caught by `health_check()`'s existing `scan_failed` wrapper — the health check fails loud, never false-greens.

## Dependency Rules

- `schemas.py` imports **only** `importlib.resources`, `yaml`, `jsonschema`, and `lore.frontmatter`. It has zero imports from any entity module (`doctrine.py`, `knight.py`, etc.), so the create-time validators can import `schemas.py` without creating a cycle.
- The packaged schema YAML files are static resources. They are never written to and never fetched over the network — `$schema` and `$id` URIs are metadata only.
- User-extensible / project-local schemas are explicitly post-MVP. There is no runtime override path.

## Packaging

`pyproject.toml` lists `jsonschema>=4.18` in `[project] dependencies` and uses `[tool.hatch.build.targets.wheel]` package-data to ship `src/lore/schemas/*.yaml` inside the wheel. `importlib.resources.files("lore.schemas")` resolves against the installed package on every platform hatchling supports.

## Test Strategy

- Unit tests in `tests/unit/test_schemas.py` cover every schema kind (happy fixture + one fixture per violated keyword: `required`, `additionalProperties`, `type`, `enum`, `minItems`, `uniqueItems`, `minLength`, `oneOf`, and the doctrine-step `if/then/else` `knight` conditional).
- Unit tests in `tests/unit/test_frontmatter_raw.py` cover the five `parse_frontmatter_raw` cases (happy, no-frontmatter, yaml-parse, non-mapping, empty).
- E2E tests in `tests/e2e/test_health_schemas.py` cover all seven PRD workflows end-to-end including `lore init` + `lore health` green run, hallucinated fields, missing required fields, scoped runs, `--json` output, the Python API parity path, and the transient report section.

## See Also

- conceptual-workflows-health — how `_check_schemas` slots into the overall health pipeline and the `schemas` scope semantics.
- tech-arch-frontmatter — `parse_frontmatter_raw` is the only parse helper used by schema validation.
- tech-doctrine-internals — describes the existing create-time validators that delegate to this module.
- standards-dry — the DRY guarantee this module exists to enforce.
- decisions-011-api-parity-with-cli — why `validate_entity_file` and `load_schema` are in `lore.models.__all__`.
