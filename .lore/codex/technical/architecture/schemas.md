---
id: tech-arch-schemas
title: Schemas Module Internals
summary: "Technical reference for src/lore/schemas.py and the packaged src/lore/schemas/*.yaml JSON Schemas. Covers the loader, validate_entity / validate_entity_file, the nine schema kinds (glossary, main-rite, and shared-step are full-YAML kinds; main-rite and shared-step are walked via the rites main and shared subfolders; codex-frontmatter additionally carries the rites field), the special yaml-parse / missing-frontmatter / read-failed rules, and how create-time validators in doctrine/knight/watcher/artifact/rite and the audit-time lore health schema check share a single authoritative contract."
binds:
- src/lore/schemas/__init__.py
- src/lore/schemas/doctrine-yaml.yaml
- src/lore/schemas/doctrine-design-frontmatter.yaml
- src/lore/schemas/knight-frontmatter.yaml
- src/lore/schemas/watcher-yaml.yaml
- src/lore/schemas/codex-frontmatter.yaml
- src/lore/schemas/codex-source-frontmatter.yaml
- src/lore/schemas/artifact-frontmatter.yaml
- src/lore/schemas/glossary.yaml
- src/lore/schemas/main-rite.yaml
- src/lore/schemas/shared-step.yaml
- src/lore/health.py
- tests/unit/test_schemas.py
- tests/unit/test_health_schemas.py
- tests/unit/test_health_schemas_binds.py
- tests/unit/test_health_schemas_us007.py
- tests/unit/test_schema_defaults_regression.py
- tests/e2e/test_health_schemas.py
- tests/e2e/test_health_schemas_binds.py
- tests/e2e/test_health_schemas_us005.py
- tests/e2e/test_health_schemas_us007.py
- tests/e2e/test_health_schemas_us008.py
related: ["tech-arch-source-layout", "tech-arch-frontmatter", "tech-overview", "conceptual-workflows-health", "conceptual-workflows-impacts", "ref-lore_doctrine-module", "standards-dry", "standards-dependency-inversion", "decisions-011-api-parity-with-cli", "conceptual-entities-glossary", "conceptual-workflows-glossary", "decisions-013-toml-for-config-yaml-for-glossary", "conceptual-entities-rite", "conceptual-workflows-rite-crud", "decisions-014-link-direction"]
---

# Schemas Module Internals

**Source module:** `src/lore/schemas/__init__.py` (the module logic; previously a flat `schemas.py`, now a package because the YAML resources live as sibling files in the same directory)
**Resource dir:** `src/lore/schemas/*.yaml` (packaged inside the wheel via hatchling `package-data`)

This module is the single authoritative home for the JSON Schemas that define the shape of every on-disk Lore entity. It is consumed by both the create-time validators in `doctrine.py`, `knight.py`, `watcher.py`, and `artifact.py` **and** by the audit-time `_check_schemas` checker in `health.py`. No schema content is duplicated anywhere else in the codebase — this is the DRY guarantee required by FR-19/FR-20 of the schema validation feature.

## Why This Module Exists

`validators.py` has a hard rule of zero `lore.*` imports. Schema loading needs to read packaged resources via `importlib.resources` and is reused by multiple entity modules, so it cannot live in `validators.py` without breaking dependency inversion. A new module — `schemas.py` — is the only placement that:

1. Keeps `validators.py` pure.
2. Gives create-time validators and the health checker a single authoritative home for schema logic.
3. Reads the packaged YAML schemas once per process.

## Schema Kinds

Nine entity kinds are validated. Each kind is a short slug that appears in `HealthIssue.entity_type`, in the `$id` of the schema (`lore://schemas/<kind>`), and in the schema filename (`src/lore/schemas/<kind>.yaml`):

| Kind | Source pattern | Schema `$id` |
|---|---|---|
| `doctrine-yaml` | `.lore/doctrines/**/*.yaml` | `lore://schemas/doctrine-yaml` |
| `doctrine-design-frontmatter` | Frontmatter of `.lore/doctrines/**/*.design.md` | `lore://schemas/doctrine-design-frontmatter` |
| `knight` | Frontmatter of `.lore/knights/**/*.md` | `lore://schemas/knight-frontmatter` |
| `watcher` | `.lore/watchers/**/*.yaml` | `lore://schemas/watcher-yaml` |
| `codex` | Frontmatter of `.lore/codex/**/*.md` | `lore://schemas/codex-frontmatter` |
| `artifact` | Frontmatter of `.lore/artifacts/**/*.md` | `lore://schemas/artifact-frontmatter` |
| `glossary` | `.lore/codex/glossary.yaml` (single literal file, NOT a `**/*.yaml` walk) | `lore://schemas/glossary` |
| `main-rite` | `.lore/rites/main/*.yaml` (full-YAML) | `lore://schemas/main-rite` |
| `shared-step` | `.lore/rites/shared/*.yaml` (full-YAML) | `lore://schemas/shared-step` |

The `glossary` kind is the first full-YAML kind whose source pattern is a literal single-file path rather than a directory glob. `_check_schemas` treats glob entries with no `*` characters as literal filenames and validates only when `(project_root / ".lore" / root_name / glob).is_file()`. The remaining directory-glob kinds use `rglob(glob)` (frontmatter/`**` kinds) or a flat `*.yaml` walk over their entity directory (`main-rite`, `shared-step`). This isolates the single-file behaviour without changing existing wiring.

### Rite schema kinds — `main-rite` and `shared-step`

Both are full-YAML kinds (parsed via `yaml.safe_load`, like `watcher`/`glossary`), `additionalProperties: false`, shipped from `src/lore/schemas/`. They validate the Rite entity's *shape* only (see `conceptual-entities-rite`); graph-level rules (reachability, single entry, dangling `then`/`goto`/`use`, conclusion reachability) are NOT expressible in JSON Schema and live in runtime checks in `rite.py`/`health.py` (see `conceptual-workflows-health`).

- **`main-rite`** — required `id, title, summary, trigger, nodes, conclusions`. `nodes` is a non-empty array of node objects; each node requires `id`, carries optional `do`/`use`/`then`, and enforces `not: {required: [do, use]}` plus `anyOf: [{required: [do]}, {required: [use]}]` (a node is a do-node XOR a use-node, never both, never neither). `then` is `oneOf` a string (straight edge / conclusion key) or an array of `{if, goto}` branch objects (fork). `conclusions` is a non-empty mapping of `{audience, response}` objects. Because the root is `additionalProperties: false`, an outbound `related`/`binds` key is rejected automatically — satisfying ADR-014's "the rite schema rejects both" with no extra rules.
- **`shared-step`** — required `id, title, summary, do` (in that field order) and nothing else; each is a `string` with `minLength: 1`, like every other entity field. `summary` is the one-line "what it does" — the universal cross-entity summary convention (`tech-arch-frontmatter`), NOT a retrieval cue; `trigger` stays MAIN-rite-only, so adding `summary` keeps the pure single-exit shape intact. `additionalProperties: false` is exactly the design-doc "shared step with branching/conclusions" check: any `nodes`/`then`/`conclusions`/`use`/`goto`/`trigger` key is rejected as an unknown property, declaratively enforcing the pure-step / single-exit rule.

Create-time enforcement lives in `rite.py` (`create_rite`/`update_rite` call `validate_entity("main-rite"|"shared-step", data)` before write); audit-time enforcement is the standard `_check_schemas` path. One schema, two enforcement points (DRY).

Schemas are authored as YAML (not JSON) because they were drafted as fenced YAML blocks and the YAML-at-rest form stays diff-friendly and self-documenting. PyYAML is already a dependency.

## Public Interface

### `load_schema(kind: str) -> dict`

Loads the packaged schema for the given kind via `importlib.resources.files("lore.schemas") / f"{kind}.yaml"` and parses it with `yaml.safe_load`. Cached for the lifetime of the process. Raises `FileNotFoundError` with a clear message for an unknown kind.

### `validate_entity(kind: str, data: dict) -> list[tuple[str, str, str]]`

Pure-data validator. Given a kind and a parsed mapping, returns a list of `(rule, pointer, message)` tuples — one per validation failure. Empty list means valid. Uses a cached `jsonschema.Draft202012Validator(load_schema(kind))` and collects every violation via `iter_errors` (no short-circuit on the first error — FR-9).

The validator is compiled once per kind and reused across all files of that kind within a `health_check()` invocation. This keeps the PRD's ≤200 ms overhead budget on a typical project intact.

### `validate_entity_file(path: Path, kind: str) -> list[HealthIssueTuple]`

Full file-level validator. Dispatches by kind:

- **Full-YAML kinds** (`doctrine-yaml`, `watcher`, `glossary`, `main-rite`, `shared-step`): calls `yaml.safe_load` on the file contents.
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

The existing private create-time validators in `doctrine.py`, `knight.py`, `watcher.py`, `artifact.py`, and `rite.py` keep their current signatures and exception types (callers outside the module see no change), but internally delegate to `lore.schemas.validate_entity(kind, data)`:

| Callsite | Delegates to |
|---|---|
| `doctrine._validate_yaml_schema(data, name)` | `validate_entity("doctrine-yaml", data)` |
| `doctrine._validate_design_frontmatter(meta, name)` | `validate_entity("doctrine-design-frontmatter", meta)` |
| `knight.create_knight` frontmatter check | `validate_entity("knight", meta)` |
| `watcher.create_watcher` YAML shape check | `validate_entity("watcher", data)` |
| `artifact.create_artifact` frontmatter re-check | `validate_entity("artifact", meta)` |
| `rite.create_rite`/`update_rite` body check | `validate_entity("main-rite", data)` / `validate_entity("shared-step", data)` |

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

## Codex Frontmatter Fields

The `codex-frontmatter` schema (`src/lore/schemas/codex-frontmatter.yaml`) is `additionalProperties: false`, so every accepted field is named explicitly. The full list:

| Field | Required | Type | Notes |
|---|---|---|---|
| `id` | yes | string (minLength 1) | Globally unique across the codex. |
| `title` | yes | string (minLength 1) | Human-readable title. |
| `summary` | yes | string (minLength 1) | Scannable one-paragraph summary. |
| `related` | no | array of unique strings | Directed edges to other codex ids. Empty list and missing field behave identically. |
| `binds` | no | array of unique strings | Repo-root-relative paths or globs governed by this entry. See "The `binds:` field" below. Empty list and missing field behave identically (FR-4 of `lore-impacts-prd`). |
| `rites` | no | array of unique strings | Rite ids (in `.lore/rites/main/`) governed by this entry — the codex→rite edge. See "The `rites:` field" below. Empty list and missing field behave identically. |

### The `binds:` field

`binds:` is the codex↔code edge consumed by `lore impacts`. Validation rules
declared in the schema:

| Rule | Schema construct | Rejects |
|---|---|---|
| Must be an array | `type: array` | scalars, mappings |
| No duplicates | `uniqueItems: true` | repeated strings |
| Each entry is a non-empty string | `items.type: string`, `items.minLength: 1` | non-strings, `""` |
| No absolute paths | `items.not.anyOf: [{pattern: '^/'}]` | `"/etc/passwd"` |
| No `..` traversal | `items.not.anyOf: [{pattern: '(^\|/)\.\.(/\|$)'}]` | `"../foo"`, `"a/../b"` |

The two regex `not.anyOf` rules are how FR-3 of `lore-impacts-prd` is
expressed declaratively. Filesystem-shape checks beyond strings (file
existence, symlink-outside-repo) are NOT in the schema — they belong to
runtime in `lore.impacts._normalize_path_input` (`conceptual-workflows-impacts`).

**Absent-vs-empty semantics.** `binds:` absent from frontmatter and `binds: []`
both mean "this entry binds nothing." `lore impacts` returns an empty result
in both cases; the schema validates both identically. Callers must not
distinguish them.

A separate pure validator `lore.validators.validate_binds_entry(s)` mirrors
the regex rules for callers that need to validate a single entry without
loading the JSON Schema (Python API, post-MVP authoring helpers). Two-layer
enforcement matches the `validate_chaos_threshold` precedent (see
`tech-arch-codex-chaos`).

`lore health --scope schemas` surfaces every malformed entry as a HealthIssue
with `entity_type="codex"` and `rule` set to the violated JSON-Schema keyword
(`type`, `pattern`, `minLength`, `uniqueItems`).

### The `rites:` field

`rites:` is the codex→rite edge (ADR-014, `decisions-014-link-direction`): a
codex doc names the rite ids it governs; rites never link back. Because
`codex-frontmatter` is `additionalProperties: false`, `rites:` had to be **added
explicitly** to the schema's `properties` — without that edit, `lore health
--scope schemas` rejects any doc carrying it. The field mirrors `binds:`'s array
shape but **omits** the path-pattern `not.anyOf` rules — rite ids are plain slugs,
not paths:

| Rule | Schema construct | Rejects |
|---|---|---|
| Must be an array | `type: array` | scalars, mappings |
| No duplicates | `uniqueItems: true` | repeated ids |
| Each entry is a non-empty string | `items.type: string`, `items.minLength: 1` | non-strings, `""` |

**Absent-vs-empty semantics.** `rites:` absent and `rites: []` both mean "this
entry governs no rites" and validate identically.

Read-side wiring reuses the bindings-style pattern (`tech-arch-frontmatter`): no
new parse helper — `parse_frontmatter_doc(filepath, extra_fields=("rites",))`,
exactly how `related` and `binds` are read. The codex `rites:` index the health
checker consumes is built with one `scan_codex` walk, mirroring
`impacts._load_codex_binds_index`. Reference integrity (a `rites:` id resolving to
an existing rite) is the `dangling_codex_rite` check under `--scope rites`/`codex`
(`conceptual-workflows-health`), NOT a schema check; the schema validates shape
only.

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
- conceptual-workflows-impacts — the `lore impacts` consumer of the `binds:` field declared on `codex-frontmatter`.
- tech-arch-frontmatter — `parse_frontmatter_raw` is the only parse helper used by schema validation.
- ref-lore_doctrine-module — describes the existing create-time validators that delegate to this module.
- standards-dry — the DRY guarantee this module exists to enforce.
- decisions-011-api-parity-with-cli — why `validate_entity_file` and `load_schema` are in `lore.models.__all__`.
