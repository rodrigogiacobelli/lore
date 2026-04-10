---
id: tech-doctrine-internals
title: Doctrine Module Internals
summary: Technical reference for src/lore/doctrine.py. Covers two-file doctrine model (design.md + yaml), list_doctrines() scanning .design.md files, show_doctrine() returning both raw content and normalized steps, create_doctrine() atomic two-file write, _validate_yaml_schema(), _validate_design_frontmatter(), _validate_steps(), _normalize(), _check_cycles(), and DoctrineError propagation.
related: ["conceptual-entities-doctrine", "tech-cli-commands", "tech-arch-source-layout", "decisions-006-id-references"]
---

# Doctrine Module Internals

**Source module:** `src/lore/doctrine.py`

This module handles all doctrine discovery, loading, validation, and creation. It is invoked when a doctrine is listed (`lore doctrine list`), shown (`lore doctrine show`), or created (`lore doctrine new`).

For conceptual documentation on what a doctrine is and how it is used, see conceptual-entities-doctrine (lore codex show conceptual-entities-doctrine).

## Public Interface

### `list_doctrines(doctrines_dir: Path, filter_groups: list[str] | None = None) -> list[dict]`

Scans `doctrines_dir` recursively for `*.design.md` files. For each design file found, checks for a matching `<stem>.yaml` in the **same directory**. Only complete, valid pairs are returned. Orphaned design files (no YAML) and YAML-only files are silently skipped.

Frontmatter parsing delegates to `frontmatter.parse_frontmatter_doc(filepath, required_fields=("id",), extra_fields=("title", "summary"))`. If parsing fails or `id` is absent, the file is skipped.

Return value per entry:
```python
{
    "id": str,        # from design frontmatter
    "group": str,     # from paths.derive_group()
    "title": str,     # from design frontmatter; fallback to id
    "summary": str,   # from design frontmatter; fallback to ""
    "filename": str,  # design file name (e.g. "my-workflow.design.md")
    "valid": True,    # always True — invalid/orphaned entries are skipped
}
```

No `name`, `description`, or `errors` keys in output.

**`list_doctrines()` output is NOT valid input for `Doctrine.from_dict()`.** The listing dict does not contain `steps`. Use `show_doctrine()` to get the full doctrine dict.

### `show_doctrine(doctrine_id: str, doctrines_dir: Path) -> dict`

Searches recursively for `<doctrine_id>.design.md` and `<doctrine_id>.yaml` under `doctrines_dir`.

Error cases:
- Design file not found → `DoctrineError(f"Doctrine '{doctrine_id}' not found: design file missing")`
- YAML file not found → `DoctrineError(f"Doctrine '{doctrine_id}' not found: YAML file missing")`
- Both missing → `DoctrineError(f"Doctrine '{doctrine_id}' not found")`
- YAML parse failure → `DoctrineError(f"YAML parsing error: {details}")`
- YAML validation failure → per schema error messages

On success, returns:
```python
{
    "id": str,          # from design frontmatter
    "title": str,       # from design frontmatter; fallback to id
    "summary": str,     # from design frontmatter; fallback to ""
    "design": str,      # raw file content of .design.md (including frontmatter block)
    "raw_yaml": str,    # raw file content of .yaml (for CLI verbatim dump; excluded from --json output)
    "steps": list[dict] # normalized step dicts from _normalize()
}
```

### `create_doctrine(name: str, yaml_source_path: Path, design_source_path: Path, doctrines_dir: Path) -> dict`

Validates both source files, then writes `<name>.yaml` and `<name>.design.md` to `doctrines_dir` (flat, not subdirectory).

Validation order (all before any write):
1. `validate_name(name)` from `validators.py` — raises `DoctrineError` on failure
2. Duplicate check — `doctrines_dir.rglob(f"{name}.yaml")` or `doctrines_dir.rglob(f"{name}.design.md")` — raises `DoctrineError(f"Error: doctrine '{name}' already exists.")`
3. YAML source file exists — raises `DoctrineError(f"File not found: {yaml_source_path}")`
4. Design source file exists — raises `DoctrineError(f"File not found: {design_source_path}")`
5. `_validate_yaml_schema(yaml_data, name)` — validates YAML content
6. `_validate_design_frontmatter(design_meta, name)` — validates design frontmatter

Returns:
```python
{"name": name, "yaml_filename": f"{name}.yaml", "design_filename": f"{name}.design.md"}
```

## Exception: `DoctrineError`

`DoctrineError` is a plain subclass of `Exception`. It is raised on any validation or parsing failure and propagates to the CLI layer, which catches it and prints the message to stderr.

All internal functions raise `DoctrineError` directly; there is no intermediate wrapping.

## Internal Pipeline

### `_parse_yaml(text: str) -> dict`

Parses YAML text using `yaml.safe_load`. Raises `DoctrineError` if:
- The YAML is syntactically invalid (`yaml.YAMLError`)
- The parsed result is not a dict (`"Doctrine must be a YAML mapping"`)

### `_validate_yaml_schema(data: dict, name: str) -> None`

Checks the new YAML schema (`id` and `steps` only):
1. `id` present → raises `DoctrineError("Missing required field: id")`
2. `steps` present → raises `DoctrineError("Missing required field: steps")`
3. `id` matches `name` → raises `DoctrineError(f'Doctrine id "{data["id"]}" does not match command argument "{name}"')`
4. `name` key in data → raises `DoctrineError("Unexpected field in YAML: name")`
5. `description` key in data → raises `DoctrineError("Unexpected field in YAML: description")`
6. Calls `_validate_steps(data["steps"])`

### `_validate_design_frontmatter(meta: dict | None, name: str) -> None`

`meta` is the result of frontmatter parsing or a pre-parsed dict.

Checks:
- `meta` is None or no `id` → raises `DoctrineError("Design file missing required frontmatter field: id")`
- `meta["id"]` != `name` → raises `DoctrineError(f'Design file id "{meta["id"]}" does not match command argument "{name}"')`

### `_validate_steps(steps) -> None`

Validates the steps list in three passes:

**Pass 1 — structure and field checks (per step):**
- `steps` must be a non-empty list
- Each step must be a dict
- Each step must have `id` and `title`
- Step `id` values must be unique within the doctrine
- If `priority` is present, it must be an integer in 0–4
- If `type` is present, it must be a string (not an integer or other non-string YAML scalar)

**Pass 2 — dependency reference check:**
- For each step, every entry in `needs` must refer to an `id` that exists in the same doctrine

**Pass 3 — cycle detection:**
- Calls `_check_cycles(steps)`

### `_check_cycles(steps: list[dict]) -> None`

Detects dependency cycles using iterative DFS with three-colour marking (WHITE / GRAY / BLACK). Raises `DoctrineError(f'Dependency cycle detected involving step "{node}"')` if a back-edge is found.

### `_normalize(data: dict) -> dict`

Applies defaults and returns a clean normalised dict. Called by `show_doctrine()` on the parsed YAML steps.

Step-level fields and their defaults:

| Field | Default if absent |
|-------|------------------|
| `priority` | `2` (normal) |
| `type` | `None` |
| `needs` | `[]` |
| `knight` | `None` |
| `notes` | `None` |

Only the `steps` array is normalised. Top-level fields (`id`) are preserved verbatim.

## Removed Functions

The following functions were removed in the two-file model refactor:

| Removed | Replacement |
|---------|-------------|
| `load_doctrine(filepath)` | `show_doctrine(id, doctrines_dir)` |
| `validate_doctrine_content(text, expected_name)` | `_validate_yaml_schema()` + `_validate_design_frontmatter()` |
| `scaffold_doctrine(name)` | Removed entirely (scaffold path removed) |
| `_validate(data, filename)` | `_validate_yaml_schema(data, name)` |
| `_validate_required_fields(data)` | Inline in `_validate_yaml_schema()` |
| `_truncate_description(text, width)` | Removed (no description field) |

## YAML Schema (New)

```yaml
id: <string>          # required; must match filename stem
steps:                # required; non-empty list
  - id: <string>      # required; unique within doctrine
    title: <string>   # required
    priority: <0-4>   # optional; default 2
    type: <string>    # optional; default null (free-form, any string accepted)
    needs: [<step-id>] # optional; default []
    knight: <string>  # optional; default null
    notes: <string>   # optional; default null
```

**Rejected fields:** `name`, `description`, `title`, `summary` must NOT appear at the YAML top level. These fields belong in the `.design.md` frontmatter.

## Design File Schema

```markdown
---
id: <string>      # required; must match filename stem
title: <string>   # optional
summary: <string> # optional
---

<free-form markdown body>
```

## Typed Model: `Doctrine`

The `Doctrine` and `DoctrineStep` typed dataclasses are defined in `lore/models.py`.

### Constructing a `Doctrine` object

```python
from pathlib import Path
from lore.doctrine import show_doctrine
from lore.models import Doctrine

doctrines_dir = Path(".lore/doctrines")
result = show_doctrine("my-workflow", doctrines_dir)
doctrine_obj = Doctrine.from_dict(result)
```

`Doctrine.from_dict()` accepts the dict produced by `show_doctrine()`:

| Field | Type in dict | `Doctrine` field |
|-------|-------------|------------------|
| `id` | `str` | `id: str` |
| `title` | `str` | `title: str` |
| `summary` | `str` | `summary: str` |
| `steps` | `list[dict]` | `steps: tuple[DoctrineStep, ...]` |

Each step dict maps to a `DoctrineStep`:

| Key | Type | `DoctrineStep` field |
|-----|------|----------------------|
| `id` | `str` | `id: str` |
| `title` | `str` | `title: str` |
| `priority` | `int` (default 2) | `priority: int` |
| `type` | `str \| None` | `type: str \| None` |
| `knight` | `str \| None` | `knight: str \| None` |
| `notes` | `str \| None` | `notes: str \| None` |
| `needs` | `list[str]` (default `[]`) | `needs: list[str]` |

`steps` is stored as `tuple[DoctrineStep, ...]` in the frozen dataclass.

### Breaking API changes

| Old | New | Notes |
|-----|-----|-------|
| `Doctrine.name: str` | removed | moved to design file |
| `Doctrine.description: str` | removed | moved to design file |
| `Doctrine.from_dict({name, description, steps})` | `Doctrine.from_dict({id, title, summary, steps})` | Shape change — Realm callers must update |
| `DoctrineListEntry.name` | removed | — |
| `DoctrineListEntry.description` | removed | — |
| `DoctrineListEntry.errors` | removed | orphaned entries are skipped, not surfaced |

## Related

- conceptual-entities-doctrine (lore codex show conceptual-entities-doctrine) — conceptual overview of doctrines
- conceptual-workflows-doctrine-show (lore codex show conceptual-workflows-doctrine-show) — show workflow
- tech-cli-commands (lore codex show tech-cli-commands) — `lore doctrine` CLI commands
- tech-arch-source-layout (lore codex show tech-arch-source-layout) — `lore.models` public API reference
