---
id: tech-doctrine-internals
title: Doctrine Module Internals
summary: Technical reference for src/lore/doctrine.py. Covers YAML loading, normalisation pipeline (_normalize), validation pipeline (_validate, _validate_required_fields, _validate_steps, _check_cycles), DoctrineError propagation, and the validate_doctrine_content() entry point.
related: ["conceptual-entities-doctrine", "tech-cli-commands", "tech-arch-source-layout"]
stability: stable
---

# Doctrine Module Internals

**Source module:** `src/lore/doctrine.py`
**Module size:** 206 lines

This module handles all doctrine loading and validation. It is invoked when a doctrine is applied to a quest (`lore doctrine apply`), listed (`lore doctrine list`), or validated during import (`lore doctrine show`).

For conceptual documentation on what a doctrine is and how it is used, see conceptual-entities-doctrine (lore codex show conceptual-entities-doctrine).

## Public Interface

### `load_doctrine(filepath: Path) -> dict`

Loads and validates a doctrine from a `.yaml` file on disk.

**Call chain:** `_parse_yaml` → `_validate` → `_normalize`

Returns the normalised doctrine dict on success. Raises `DoctrineError` on any failure.

### `validate_doctrine_content(text: str, expected_name: str) -> dict`

Validates raw YAML text against schema rules. Used when the CLI receives doctrine content as text (e.g., from stdin or a user-supplied string) rather than from a file.

**Call chain:** `_parse_yaml` → `_validate_required_fields` → name-match check → id-match check (if `id` present, must equal `expected_name`) → `_validate_steps`

Returns the parsed (but **not normalised**) data dict on success. Raises `DoctrineError` on failure.

**Difference from `load_doctrine`:** `validate_doctrine_content` does not call `_normalize` and accepts `expected_name` as a command-line argument rather than deriving it from a filename.

### `list_doctrines(doctrines_dir: Path) -> list[dict]`

Lists doctrine `.yaml` files discoverable from `doctrines_dir`, extracting metadata from each. Returns a list of dicts with fields: `id`, `group`, `title`, `summary`, `name`, `filename`, `description`, `valid`, and (on failure) `errors`. The `id` field falls back to filename stem. `title` falls back to `id`. `summary` falls back to `description` truncated via `textwrap.shorten(desc_str, width=83, placeholder="...")`, or empty string if both are absent. GROUP is derived via `paths.derive_group(filepath, doctrines_dir)`.

The function uses a single `doctrines_dir.rglob("*.yaml")` call to search the full directory tree at all depths. This discovers doctrines in `doctrines/default/` (Lore-seeded), at the flat parent level (user-created), and in any user-created subdirectories at any depth. The result is wrapped in `sorted()` and iterated for parsing. The returned list is a single flat sequence with no source-directory annotation — callers cannot distinguish whether a doctrine came from the flat parent, the `default/` subdirectory, or any other subdirectory.

Invalid doctrines are included in the list with `valid=False`. This allows `lore doctrine list` to surface broken doctrines rather than silently omitting them.

**`list_doctrines()` output is NOT valid input for `Doctrine.from_dict()`.** The listing
dict contains `id`, `group`, `title`, `summary`, `name`, `filename`, `description`, `valid`, and optionally `errors`. The
`Doctrine` typed model requires the normalized dict from `_normalize()` (via `load_doctrine()`),
which has `name`, `description`, and `steps`. Conflating the two shapes will cause a
`KeyError` on `steps`. See [Typed Model: `Doctrine`](#typed-model-doctrine) below.

## Exception: `DoctrineError`

`DoctrineError` is a plain subclass of `Exception`. It is raised on any validation or parsing failure and propagates to the CLI layer, which catches it and prints the message to stderr.

All internal functions raise `DoctrineError` directly; there is no intermediate wrapping.

## Internal Pipeline

### `_parse_yaml(text: str) -> dict`

Parses YAML text using `yaml.safe_load`. Raises `DoctrineError` if:
- The YAML is syntactically invalid (`yaml.YAMLError`)
- The parsed result is not a dict (`"Doctrine must be a YAML mapping"`)

### `_validate(data: dict, filename: str) -> None`

Top-level validation dispatcher for file-based loading. Calls:
1. `_validate_required_fields(data)` — checks top-level fields
2. Name-match check — `data["name"]` must equal `filename` with the `.yaml` suffix stripped
3. `_validate_steps(data["steps"])` — validates the steps list

### `_validate_required_fields(data: dict) -> None`

Checks that `name`, `description`, and `steps` are all present at the top level. Raises `DoctrineError(f"Missing required field: {field}")` for the first missing field found.

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

Detects dependency cycles using iterative DFS with three-colour marking (WHITE / GRAY / BLACK). Raises `DoctrineError(f'Dependency cycle detected involving step "{node}"')` if a back-edge is found (i.e., a GRAY node is encountered during DFS traversal).

### `_normalize(data: dict) -> dict`

Applies defaults and returns a clean normalised dict. Fields and their defaults:

| Field | Default if absent |
|-------|------------------|
| `priority` | `2` (normal) |
| `type` | `None` |
| `needs` | `[]` |
| `knight` | `None` |
| `notes` | `None` |

The `name` and `description` top-level fields are passed through without modification. The optional metadata fields `id`, `title`, and `summary` are passed through if present. Only the `steps` array is normalised; all other top-level fields are preserved verbatim.

## Validation Order and Short-Circuit Behaviour

The validation pipeline short-circuits at the first error. If `_validate_required_fields` raises, `_validate_steps` is never called. This means a doctrine with both a missing required field and a cycle in steps will only report the missing field.

## YAML Schema (Normalised)

```yaml
id: <string>             # optional; must match filename stem if present
title: <string>          # optional; human-readable name
summary: <string>        # optional; one-line description for list output
name: <string>           # required; must match filename stem
description: <string>    # required
steps:                   # required; non-empty list
  - id: <string>         # required; unique within doctrine
    title: <string>      # required
    priority: <0-4>      # optional; default 2
    type: <string>            # optional; default null (free-form, any string accepted)
    needs: [<step-id>]   # optional; default []
    knight: <string>     # optional; default null
    notes: <string>      # optional; default null
```

## Typed Model: `Doctrine`

The `Doctrine` and `DoctrineStep` typed dataclasses are defined in `lore/models.py`, not
in `doctrine.py`. The scan module's dict contracts are unchanged; typed models are a
presentation layer on top of them.

### Constructing a `Doctrine` object

```python
from lore.doctrine import load_doctrine
from lore.models import Doctrine

normalized = load_doctrine(path)          # calls _normalize(); raises DoctrineError on failure
doctrine_obj = Doctrine.from_dict(normalized)
```

`Doctrine.from_dict()` accepts the dict produced by `_normalize()`:

| Field | Type in normalized dict | `Doctrine` field |
|-------|------------------------|------------------|
| `name` | `str` | `name: str` |
| `description` | `str` | `description: str` |
| `steps` | `list[dict]` | `steps: tuple[DoctrineStep, ...]` |

Each step dict from `_normalize()` maps to a `DoctrineStep`:

| Key | Type | `DoctrineStep` field |
|-----|------|----------------------|
| `id` | `str` | `id: str` |
| `title` | `str` | `title: str` |
| `priority` | `int` (default 2) | `priority: int` |
| `type` | `str \| None` | `type: str \| None` |
| `knight` | `str \| None` | `knight: str \| None` |
| `notes` | `str \| None` | `notes: str \| None` |
| `needs` | `list[str]` (default `[]`) | `needs: list[str]` |

`steps` is stored as `tuple[DoctrineStep, ...]` in the frozen dataclass (lists are
mutable and incompatible with `frozen=True`). `from_dict()` converts the source list.

### `list_doctrines()` output is not `Doctrine.from_dict()` input

| Shape | Source | Valid for `Doctrine.from_dict()` |
|-------|--------|----------------------------------|
| `{name, description, steps: [...]}` | `_normalize()` via `load_doctrine()` | Yes |
| `{id, group, title, summary, name, filename, description, valid, errors?}` | `list_doctrines()` | **No** — missing `steps`; will raise `KeyError` |

`list_doctrines()` exists to support the `lore doctrine list` CLI display. Its output
includes validation metadata (`valid`, `errors`), enrichment fields (`id`, `group`, `title`, `summary`), and a `filename` field that have no
place in a clean `Doctrine` model. Realm navigating doctrine listings should use the `DoctrineListEntry` typed model from `lore.models`.

## Related

- conceptual-entities-doctrine (lore codex show conceptual-entities-doctrine) — conceptual overview of doctrines
- tech-cli-commands (lore codex show tech-cli-commands) — `lore doctrine` CLI commands
- tech-arch-source-layout (lore codex show tech-arch-source-layout) — `lore.models` public API reference
