---
id: ref-lore_doctrine-module
title: Lore doctrine module — internals
summary: Reference doc for `src/lore/doctrine.py` — the two-file model (design.md +
  yaml), the schema-delegation rule, the cross-field validations the schema cannot
  express, and the cycle-detection algorithm. Source of truth is the module plus its
  two JSON Schemas.
related:
- conceptual-entities-doctrine
- ref-lore_cli-commands
- tech-arch-source-layout
- decisions-006-id-references
- tech-arch-schemas
---

# Lore doctrine module — internals

**Covers:** `lore.doctrine`, `list_doctrines`, `show_doctrine`, `create_doctrine`, `_validate_yaml_schema`, `_validate_design_frontmatter`, `_validate_steps`, `_check_cycles`, `_normalize`, `_parse_yaml`, `DoctrineError`, `Doctrine`, `DoctrineStep`, `DoctrineListEntry`
**Source of truth:** `src/lore/doctrine.py` (logic), `src/lore/schemas/doctrine-yaml.yaml` (YAML schema), `src/lore/schemas/doctrine-design-frontmatter.yaml` (design frontmatter schema), `src/lore/models.py` (typed models).

## Why this exists

Doctrines are stored as a paired `<name>.design.md` + `<name>.yaml` so the design (markdown body for humans/agents) is the discovery entry point and the YAML carries the executable graph. This module owns discovery, loading, validation, and creation. Most of the complexity is in keeping the two files coherent and in delegating shape checks to JSON Schemas (FR-20 DRY) so create-time and audit-time validation never diverge.

## Gotchas

- **Two-file model is mandatory.** `<name>.design.md` and `<name>.yaml` must live in the same directory. `list_doctrines` skips orphans (design-only or yaml-only) silently — they do not surface as errors. `show_doctrine` raises `DoctrineError` if either file is missing.

- **`list_doctrines` output is NOT valid input for `Doctrine.from_dict()`.** The list dict has no `steps`. Use `show_doctrine()` to construct a `Doctrine`. The list dict is for `DoctrineListEntry.from_dict`.

- **Shape validation lives in JSON Schema, not inline.** `_validate_yaml_schema` and `_validate_design_frontmatter` are thin wrappers around `lore.schemas.validate_entity(...)`. Required fields, `additionalProperties: false`, the `if/then/else` conditional that requires a `knight` field when `type == "knight"` — all live in the YAML schema files. Adding inline checks here is a violation of FR-20 and a divergence risk.

- **Cross-field rules stay in code.** Two checks that the schema cannot express:
  1. Doctrine `id` (in YAML and in design frontmatter) must equal the filename stem / `name` argument.
  2. The `meta is None` → `"Design file missing required frontmatter field: id"` error path.
  These remain inline in `_validate_yaml_schema` and `_validate_design_frontmatter`.

- **`DoctrineError` is unwrapped.** Plain `Exception` subclass. Every internal function raises it directly; the CLI catches and prints to stderr. No intermediate wrapping or chaining.

- **Validation order is total.** `create_doctrine` runs all six validations before any disk write: name → group → duplicate (subtree-wide via `rglob`) → YAML source exists → design source exists → YAML schema → design frontmatter schema. Failure at any step leaves the filesystem untouched.

- **Duplicate detection is subtree-wide.** `doctrines_dir.rglob(f"{name}.yaml")` and `.design.md`. A doctrine `foo` cannot coexist anywhere in the tree.

- **Cycle detection is iterative DFS with three-colour marking.** WHITE / GRAY / BLACK. A back-edge into a GRAY node raises `DoctrineError(f'Dependency cycle detected involving step "{node}"')`. Recursive DFS would risk Python's recursion limit on pathological doctrines.

- **Step defaults are applied by `_normalize`, not by the schema.** `priority=2`, `type=None`, `needs=[]`, `knight=None`, `notes=None`. Top-level fields are preserved verbatim — only the `steps` array is normalised. `show_doctrine` applies normalisation; `list_doctrines` does not (it never reads steps).

- **YAML top-level rejects `name`/`description`/`title`/`summary`.** Those fields belong in the design file's frontmatter. Putting them in YAML is a schema error (`additionalProperties: false`).

- **`type` in steps is free-form.** Any string. Schema does NOT enforce a value set. Consuming layers (orchestrators) interpret `type` semantics — Lore does not (mirrors the v4→v5 mission_type policy).

- **`scaffold_doctrine` was removed.** No `lore doctrine new` scaffold path exists. Both `-f` (yaml) and `-d` (design) flags are required.

- **`Doctrine` typed model dropped `name` and `description`.** Realm callers updated in the two-file refactor. `Doctrine.from_dict` accepts `{id, title, summary, steps}`. `DoctrineListEntry` similarly dropped `name`, `description`, and `errors` (orphaned entries are skipped, not surfaced).

## Shape

| Function | Returns | Notes |
|----------|---------|-------|
| `list_doctrines` | `list[dict]` (per-entry: `id`, `group`, `title`, `summary`, `filename`, `valid=True`) | No `steps`. No errors. |
| `show_doctrine` | `dict` (`id`, `title`, `summary`, `design`, `raw_yaml`, `steps`) | `raw_yaml` is for verbatim CLI dump and is excluded from `--json` output. |
| `create_doctrine` | `dict` (`name`, `group`, `yaml_filename`, `design_filename`, `path`) | `path` points at the YAML file. |

`Doctrine` (typed) field-by-field mapping lives in `src/lore/models.py`. `steps` is stored as `tuple[DoctrineStep, ...]` in the frozen dataclass.

## Schemas (pointer)

- `src/lore/schemas/doctrine-yaml.yaml` — top-level `id`, `steps`, per-step shape, the knight-conditional.
- `src/lore/schemas/doctrine-design-frontmatter.yaml` — required `id`, optional `title`/`summary`, `additionalProperties: false`.

Both are loaded once per process via `lore.models.load_schema(kind)`. Audit-time validation in `lore health` runs the same schemas — adding a new constraint means editing the schema file, not the module.
