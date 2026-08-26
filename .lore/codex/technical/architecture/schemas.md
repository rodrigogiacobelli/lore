---
id: tech-arch-schemas
title: Schemas Module Internals
summary: "Technical reference for src/lore/schemas.py and the packaged src/lore/schemas/*.yaml JSON Schemas. Covers the loader, validate_entity / validate_entity_file, the nine project schema kinds plus the two packaged-data kinds agents and skill-catalogue (glossary, main-rite, and shared-step are full-YAML kinds; main-rite and shared-step are walked via the rites main and shared subfolders; codex-frontmatter additionally carries the rites field), the special yaml-parse / missing-frontmatter / read-failed rules, and how create-time validators in doctrine/knight/watcher/artifact/rite and the audit-time lore health schema check share a single authoritative contract."
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
- src/lore/schemas/agents.yaml
- src/lore/schemas/skill-catalogue.yaml
- src/lore/health.py
- src/lore/paths.py
- src/lore/codex.py
- src/lore/frontmatter_edit.py
- src/lore/api.py
- tests/unit/test_schemas.py
- tests/unit/test_frontmatter_edit_overlay.py
- tests/unit/test_health_schemas.py
- tests/unit/test_health_schemas_binds.py
- tests/unit/test_health_schemas_us007.py
- tests/unit/test_schema_defaults_regression.py
- tests/e2e/test_health_schemas.py
- tests/e2e/test_health_schemas_binds.py
- tests/e2e/test_health_schemas_us005.py
- tests/e2e/test_health_schemas_us007.py
- tests/e2e/test_health_schemas_us008.py
related: ["tech-arch-source-layout", "tech-arch-frontmatter", "tech-overview", "conceptual-workflows-health", "conceptual-workflows-impacts", "ref-lore_doctrine-module", "standards-dry", "standards-dependency-inversion", "decisions-011-api-parity-with-cli", "conceptual-entities-glossary", "conceptual-workflows-glossary", "decisions-013-toml-for-config-yaml-for-glossary", "conceptual-entities-rite", "conceptual-workflows-rite-crud", "decisions-014-link-direction", "decisions-010-public-api-stability", "decisions-018-overlays-are-path-discovered-config", "decisions-019-overlay-scope-stops-at-transient", "tech-arch-agents-md", "tech-arch-skill-catalogue"]
---

# Schemas Module Internals

**Source module:** `src/lore/schemas/__init__.py` (the module logic; a package rather than a flat module because the YAML resources live as sibling files in the same directory)
**Resource dir:** `src/lore/schemas/*.yaml` (packaged inside the wheel via hatchling `package-data`)

This module is the single authoritative home for the JSON Schemas that define the shape of every on-disk Lore entity. It is consumed by both the create-time validators in `doctrine.py`, `knight.py`, `watcher.py`, and `artifact.py` **and** by the audit-time `_check_schemas` checker in `health.py`. No schema content is duplicated anywhere else in the codebase — this is the DRY guarantee required by FR-19/FR-20 of the schema validation feature.

## Why This Module Exists

`validators.py` has a hard rule of zero `lore.*` imports. Schema loading needs to read packaged resources via `importlib.resources` and is reused by multiple entity modules, so it cannot live in `validators.py` without breaking dependency inversion. A new module — `schemas.py` — is the only placement that:

1. Keeps `validators.py` pure.
2. Gives create-time validators and the health checker a single authoritative home for schema logic.
3. Reads the packaged YAML schemas once per process.

## Schema Kinds

Nine entity kinds are validated in a project. Each kind is a short slug that appears in `HealthIssue.entity_type`, in the `$id` of the schema (`lore://schemas/<kind>`), and in the schema filename (`src/lore/schemas/<kind>.yaml`):

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

### Packaged-data schema kinds — `agents` and `skill-catalogue`

Two kinds validate **package** data rather than project files: `lore://schemas/agents` covers `src/lore/defaults/agents.yaml` (the agent registry) and `lore://schemas/skill-catalogue` covers `src/lore/defaults/skills-catalogue.yaml` (the skill catalogue). Both are full-YAML kinds shipped from `src/lore/schemas/` like every other kind.

They differ from the nine project kinds in three ways:

- **No source pattern under `.lore/`.** Nothing in a project matches them, so `_check_schemas` never walks them and they never appear in `HealthIssue.entity_type`.
- **Loaded through `load_schema(kind)` only, never through `resolve_merged_schema`.** `.lore/custom-schemas/agents.yaml` is not a recognised overlay path, and the v1 overlay kinds stay exactly as `decisions-018-overlays-are-path-discovered-config` lists them: `codex-frontmatter` and `codex-source-frontmatter`. A project cannot extend either packaged file, because neither is the project's to extend.
- **A failure is a build defect, not a user error.** `agents.load_registry()` and the catalogue loader raise `RuntimeError` naming the packaged file when it is unparseable or schema-invalid, rather than emitting a health issue.

See `tech-arch-agents-md` and `tech-arch-skill-catalogue` for the two file formats.

### Rite schema kinds — `main-rite` and `shared-step`

Both are full-YAML kinds (parsed via `yaml.safe_load`, like `watcher`/`glossary`), `additionalProperties: false`, shipped from `src/lore/schemas/`. They validate the Rite entity's *shape* only (see `conceptual-entities-rite`); graph-level rules (reachability, single entry, dangling `then`/`goto`/`use`, conclusion reachability) are NOT expressible in JSON Schema and live in runtime checks in `rite.py`/`health.py` (see `conceptual-workflows-health`).

- **`main-rite`** — required `id, title, summary, trigger, nodes, conclusions`. `nodes` is a non-empty array of node objects; each node requires `id`, carries optional `do`/`use`/`then`, and enforces `not: {required: [do, use]}` plus `anyOf: [{required: [do]}, {required: [use]}]` (a node is a do-node XOR a use-node, never both, never neither). `then` is `oneOf` a string (straight edge / conclusion key) or an array of `{if, goto}` branch objects (fork). `conclusions` is a non-empty mapping of `{audience, response}` objects. Because the root is `additionalProperties: false`, an outbound `related`/`binds` key is rejected automatically — satisfying ADR-014's "the rite schema rejects both" with no extra rules.
- **`shared-step`** — required `id, title, summary, do` (in that field order) and nothing else; each is a `string` with `minLength: 1`, like every other entity field. `summary` is the one-line "what it does" — the universal cross-entity summary convention (`tech-arch-frontmatter`), NOT a retrieval cue; `trigger` stays MAIN-rite-only, so adding `summary` keeps the pure single-exit shape intact. `additionalProperties: false` is exactly the design-doc "shared step with branching/conclusions" check: any `nodes`/`then`/`conclusions`/`use`/`goto`/`trigger` key is rejected as an unknown property, declaratively enforcing the pure-step / single-exit rule.

Create-time enforcement lives in `rite.py` (`create_rite`/`update_rite` call `validate_entity("main-rite"|"shared-step", data)` before write); audit-time enforcement is the standard `_check_schemas` path. One schema, two enforcement points (DRY).

Schemas are authored as YAML (not JSON) because they were drafted as fenced YAML blocks and the YAML-at-rest form stays diff-friendly and self-documenting. PyYAML is already a dependency.

## Public Interface

### `load_schema(kind: str) -> dict`

Loads the packaged schema for the given kind via `importlib.resources.files("lore.schemas") / f"{kind}.yaml"` and parses it with `yaml.safe_load`. Cached for the lifetime of the process. Raises `FileNotFoundError` with a clear message for an unknown kind.

### `validate_entity(kind: str, data: dict, *, project_root: Path | None = None) -> list[tuple[str, str, str]]`

Pure-data validator. Given a kind and a parsed mapping, returns a list of `(rule, pointer, message)` tuples — one per validation failure. Empty list means valid. Uses a cached `jsonschema.Draft202012Validator(load_schema(kind))` and collects every violation via `iter_errors` (no short-circuit on the first error — FR-9).

The validator is compiled once per kind and reused across all files of that kind within a `health_check()` invocation. This keeps the PRD's ≤200 ms overhead budget on a typical project intact.

**`project_root` keyword (overlay-aware path).** When `project_root` is passed and `kind` is overlay-eligible (`codex-frontmatter`, `codex-source-frontmatter`), `validate_entity` validates against the **merged** validator from `project_validator_for(kind, project_root)` (packaged default + the project overlay at `.lore/custom-schemas/<kind>.yaml`) instead of the packaged validator. When `project_root` is `None` (the default) or the kind is not overlay-eligible, it falls through to today's packaged behaviour — byte-for-byte identical. The keyword is additive (a minor bump under ADR-010); existing callers are unaffected. `lore codex` create/edit pass `project_root=_overlay_root(project_root, <path>)` — the private `codex._overlay_root(project_root, filepath)` helper, which returns `project_root` for canonical and `sources/` docs and `None` for anything under `.lore/codex/transient/` — so a declared custom key is accepted at write time consistently with the health audit, while a transient working doc validates against the packaged schema alone (`decisions-019-overlay-scope-stops-at-transient`). `create_document` computes its target path *before* validating precisely so the transient decision can be made pre-write. If overlay construction fails, `validate_entity` raises `OverlayError` (see "Project-local schema overlays" below) rather than returning issues.

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

One schema, one contract, enforced at both write time and audit time. Drift between the two is a DRY violation by definition.

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

**Overlay-aware routing.** For the two codex kinds (`codex-frontmatter`, `codex-source-frontmatter`) `_check_schemas` resolves its validator through the project-aware health seam `project_get_validator(kind, project_root)` (re-exporting `project_validator_for`) so the merged validator is used; every other kind still routes through the kind-only `get_validator(kind)` seam. Both are internal module-level monkeypatch seams (neither is public API), split by kind: project-aware for the two codex kinds, kind-only for the rest. A malformed overlay raises `OverlayError`, which the existing `try/except Exception` around validator construction turns into a single `scan_failed` issue naming the overlay — other kinds and checks continue. See "Project-local schema overlays" below and `conceptual-workflows-health`.

Under the codex entity root the per-file dispatch is **three-way**, decided inside the walk loop (no extra `_SCHEMA_KINDS` row):

| File location | Validator used |
|---|---|
| `.lore/codex/transient/**` | `transient_override` — the **packaged** validator from the kind-only `get_validator(schema_kind)` seam |
| `.lore/codex/sources/**` | `sources_override` — the merged `codex-source-frontmatter` validator |
| everything else | the merged `codex-frontmatter` validator |

`transient_override` is resolved **lazily**: it is built only when the resolved candidate list actually contains a file under `transient/`, so a project with no transient subtree keeps a single validator lookup. Because it comes from the packaged seam, a malformed overlay does not blind the subtree — the transient files still validate while the canonical kind reports its single `scan_failed`. The transient branch is tested first; if a branch's validator is `None` (its construction failed), that file is skipped rather than validated against the wrong schema.

## Project-local schema overlays

A project may extend the two codex frontmatter schemas with its own **add-only overlay** at `.lore/custom-schemas/<kind>.yaml`, where `<kind>` ∈ {`codex-frontmatter`, `codex-source-frontmatter`} for v1. The overlay adds new typed frontmatter properties (and optionally marks them required) while the packaged core fields stay authoritative and untouched. With no overlay file present, behaviour is byte-for-byte identical to the packaged-only path. The classification of an overlay as path-discovered project config (not an ID-addressable entity) is `decisions-018-overlays-are-path-discovered-config`.

### Scope of governance

An overlay governs **canonical codex documents and the `sources/` layer only**. Documents under `.lore/codex/transient/` are out of overlay scope and validate against the **packaged** schema alone — at every seam that validates a codex doc: the `lore health` schema scan, `lore codex new`, `lore codex edit -f`, and `lore codex edit --set/--unset/--add/--remove` (`decisions-019-overlay-scope-stops-at-transient`). The exemption removes the *overlay*, never the *validation*: `id`, `title`, and `summary` are still required and `additionalProperties` is still `false`, so a transient doc missing `summary` is still a health error, and a transient doc that *carries* a declared custom key is rejected as an unknown property. Custom fields are canonical-codex governance. An overlay `required` entry therefore never fires on a transient doc — which is what stops `lore health` from failing on the reports it writes itself into `.lore/codex/transient/health-<timestamp>.md`. Every seam routes through `codex._overlay_root(project_root, filepath)`; no seam open-codes the decision. The path predicates are `paths.codex_transient_dir(root)` and `paths.is_transient_codex_path(root, filepath)`.

### Resolver surface

The merge logic is a single region in this module — no second copy lives in `health.py` or `codex.py` (DRY, `standards-dry`):

- **`resolve_merged_schema(kind, project_root) -> dict`** — returns the packaged `load_schema(kind)` unchanged when no overlay exists; otherwise a deep copy of the packaged base with overlay `properties` injected, overlay `required` appended, and `additionalProperties` pinned `false` (the packaged base is never mutated, preserving cache integrity). Raises `OverlayError` on any rule violation.
- **`merge_overlay(base, overlay, kind) -> dict`** — the pure merge helper. Add-only: it only adds `properties`/`required`; it never reads a value out of the packaged `properties`/`required`.
- **`project_validator_for(kind, project_root) -> Draft202012Validator`** — builds the merged schema via `resolve_merged_schema`, constructs the validator, and caches it on key `(kind, str(project_root), overlay_mtime_ns)`, where `overlay_mtime_ns` is `os.stat(overlay).st_mtime_ns` or sentinel `-1` when absent. An edited overlay yields a new key → re-read within a long-running process (Realm). The kind-only `lru_cache` on `_validator_for` is project-blind and is not reused.
- **`OverlayError(ValueError)`** — the overlay-resolution failure type (see "Failure handling").

`resolve_merged_schema`, `project_validator_for`, and `OverlayError` are public (re-exported in the `# --- Schemas ---` block of `api.py` and in `lore.api.__all__`); `validate_entity` gains the `project_root` keyword. The path helpers `paths.custom_schemas_dir(root)` and `paths.custom_schema_path(root, kind)` follow the `glossary_path`/`config_path` shape. The resolver imports only stdlib (`os`, `pathlib`, `copy`), `yaml`, `jsonschema`, and `lore.paths` — no cycle into the entity modules.

### Merge semantics (add-only, strict)

An overlay is a JSON-Schema fragment: a top-level mapping with `properties` (object, required) and optional `required` (array of strings). All other top-level keys are ignored — the merge synthesizes everything else from the packaged base (`$schema`, `$id`, `type`, `additionalProperties` are never copied from the overlay).

- New `properties` keys are merged in (FR-4).
- `required` entries are appended, and each must name a property declared in the **same** overlay (FR-5).
- `additionalProperties` stays `false` (FR-6): declared custom keys pass; an undeclared key (e.g. a typo `onwer:`) still errors as an unknown property, listing the custom key among allowed keys because the merged `properties` contains it.
- An overlay property whose key collides with a packaged field — for `codex-frontmatter`: `id, title, summary, type, related, binds, rites`; for `codex-source-frontmatter`: `id, title, summary, type, related` — is rejected (FR-7). Defaults can never be redefined or weakened.

### Failure handling

`resolve_merged_schema` raises `OverlayError` (subclass of `ValueError`, mirroring the `GlossaryError` / `ImpactsError` precedent; public in `lore.api.__all__`) on: unparseable YAML, a non-mapping top-level, a missing/non-mapping `properties`, a packaged-field collision (FR-7), or a `required` entry not declared in the overlay (FR-5). The two consumers handle it as follows:

- **Health** catches it in the existing `try/except Exception` around validator construction and emits one `scan_failed` `HealthIssue` naming the overlay; the per-file loop for that kind is skipped, other kinds and checks continue. No stack trace escapes `lore health`.
- **Codex create/edit** let `OverlayError` propagate unchanged out of `create_document` / `update_document` — because it subclasses `ValueError`, it rides their existing "raises `ValueError` on schema failure" contract. Ordinary validation failures (typo, missing required) still return the `list[SchemaIssue]` that create/edit join into a `ValueError`.

Overlays are parsed with `yaml.safe_load` only (NFR Security) and cannot weaken packaged invariants (add-only), bounding blast radius.

### Field-edit mode as an overlay consumer

`frontmatter_edit.update_frontmatter_fields` — behind `lore codex edit --set/--unset/--add/--remove` and `lore.api.update_frontmatter_fields` — is the third overlay consumer alongside health and codex create/edit. It resolves its overlay root the same way every other seam does, `codex._overlay_root(project_root, filepath)`, and passes the result to `validate_entity(schema_kind, mutated, project_root=overlay_root)`. Consequences:

- A field edit that sets a **declared custom key** on a canonical doc validates against the merged schema and succeeds. This is what makes the backfill `lore health` prescribes possible from the CLI: when a project newly marks a custom field `required`, `lore codex edit <doc> --set owner=alice` is the fix. Before this, field-edit mode validated against the packaged schema only and failed with `Unknown property 'owner'` even though the overlay declared it.
- On a transient doc `_overlay_root` returns `None`, so the packaged schema applies and a custom key is rejected — same rule as every other seam.
- `update_frontmatter_fields` can therefore raise `OverlayError` (a `ValueError`, so it rides the function's existing `ValueError` contract) when the project overlay is malformed.

The CLI-side scalar coercion follows the same schema. `frontmatter_edit._coerce_scalar_for_schema(schema_kind, field, raw_str, project_root=None)` takes an optional fourth argument; when a `project_root` is passed it consults `resolve_merged_schema(schema_kind, project_root)` instead of `load_schema(schema_kind)`, so a custom **array**, **integer**, or **boolean** field coerces by its declared type rather than arriving at validation as a raw string. `cli.py` passes it for `kind == "codex"` only — the sole overlay-eligible kind. Net effect: `lore codex edit my-doc --set owner=alice --set tags=a,b` writes `tags` as a list.

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

- `schemas/__init__.py` imports **only** stdlib (`importlib.resources`, `os`, `pathlib`, `copy`), `yaml`, `jsonschema`, `lore.frontmatter`, and `lore.paths` (for the overlay path helpers). It has zero imports from any entity module (`doctrine.py`, `knight.py`, etc.), so the create-time validators can import it without creating a cycle. `lore.paths` has no cycle back into schemas.
- The packaged schema YAML files are static resources. They are never written to and never fetched over the network — `$schema` and `$id` URIs are metadata only.
- **Project-local schema overlays are supported** for the two codex kinds via the resolver above (`.lore/custom-schemas/<kind>.yaml`, add-only, strict). This reverses the previous "no runtime override path" posture. The override is add-only and defaults-authoritative — an overlay can never redefine, relax, or remove a packaged field — so the packaged schemas remain the single source of truth for the core shape. It is also **scope-bounded**: overlays reach canonical codex docs and `sources/` only, never `.lore/codex/transient/**`, where the packaged schema is the whole contract (ADR-019). Overlays for other entity kinds (knight, artifact, doctrine) and per-doc-type overlays remain post-MVP.

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
