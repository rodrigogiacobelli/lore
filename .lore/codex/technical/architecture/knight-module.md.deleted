---
id: tech-arch-knight-module
title: Knight Module Internals
summary: 'Technical reference for src/lore/knight.py. Covers list_knights and find_knight
  function signatures, the path-traversal guard, and how cli.py uses these functions
  in knight_list, knight_show, and _show_mission.

  '
binds:
- src/lore/knight.py
- tests/unit/test_knight.py
- tests/e2e/test_knight_crud.py
- tests/e2e/test_knight_list.py
related:
- conceptual-entities-knight
- tech-arch-source-layout
---

# Knight Module Internals

**Source module:** `src/lore/knight.py`

This module provides filesystem operations for knight files. It mirrors `doctrine.py`
in structure: a dedicated module for file-based entity operations, imported by `cli.py`
only.

## Purpose

`knight.py` is the single authoritative location for knight file operations — globbing
the directory, reading files, resolving knight names to paths. `cli.py` holds none of
that logic, following the Single Responsibility principle (ADR-012).

## Public Interface

### `create_knight(knights_dir: Path, name: str, content: str, *, group: str | None = None) -> dict`

Creates a new knight file under `knights_dir`. The CLI handler (`cli.knight_new`) is a thin wrapper over it.

- **Input:** `knights_dir` — the `.lore/knights/` directory; `name` — the knight filename stem; `content` — the full markdown body to write; `group` — an optional slash-delimited subdirectory path, or `None` for the knights root.
- **Validation order (all before any write):**
  1. `validate_name(name)` from `lore.validators` — raises `ValueError` with the name-error message on failure.
  2. `validate_group(group)` from `lore.validators` — raises `ValueError` with `Error: invalid group '<value>': <reason>` on failure. `None` is accepted.
  3. Duplicate check — `knights_dir.rglob(f"{name}.md")`. A knight named `<name>` anywhere under `knights_dir` blocks the create regardless of the supplied group. Raises `ValueError("Knight \"<name>\" already exists.")`.
- **Directory creation:** after validation, the target directory is computed as `knights_dir if group is None else knights_dir / Path(group)` and created with `mkdir(parents=True, exist_ok=True)`. Idempotent — pre-existing group directories never fail.
- **Write:** `content` is written to `target_dir / f"{name}.md"`.
- **Return:** `{"name": name, "group": group, "filename": f"{name}.md", "path": str(target_dir / f"{name}.md")}`. `group` is the slash-joined string or `None`.

This helper is the single authoritative knight write path. Both `cli.knight_new` and any Python API caller go through it — ADR-011 parity.

### `list_knights(knights_dir: Path) -> list[dict]`

Returns a sorted list of knight records from the given directory tree.

- **Input:** `knights_dir` — the `.lore/knights/` directory (typically obtained via
  `paths.knights_dir(root)`).
- **Output:** `list[{"id": str, "group": str, "title": str, "summary": str, "name": str, "filename": str}]` sorted by `id`.
- **Frontmatter parsing:** Uses `frontmatter.parse_frontmatter_doc(filepath, required_fields=("id", "title", "summary"))`. If frontmatter is absent or incomplete, falls back to: `id` = filename stem, `title` = filename stem, `summary` = `""`.
- **GROUP derivation:** Uses `paths.derive_group(filepath, knights_dir)` to compute the GROUP from intermediate directory components joined with `/`. Root-level knights carry `""` which list renderers translate to the empty sentinel in the table and `null` in the JSON envelope.
- **Backward compatibility:** The `name` and `filename` keys are retained so `find_knight` and other consumers continue to work.
- **Discovery:** Uses `rglob("*.md")` on `knights_dir`, discovering all knight files
  regardless of subdirectory depth. This matches the existing CLI behaviour where
  `lore knight list` shows knights from both `.lore/knights/` and
  `.lore/knights/default/`.

### `find_knight(knights_dir: Path, name: str) -> Path | None`

Resolves a knight name to its file path.

- **Input:** `knights_dir` — the `.lore/knights/` directory; `name` — the knight's
  filename stem (e.g., `"developer"` for `developer.md`).
- **Output:** `Path` to the knight file if found; `None` if not found.
- **Path-traversal guard:** If `name` contains `/` or `\\`, raises `ValueError`
  immediately. This guard prevents directory traversal attacks where a crafted name
  such as `"../sensitive"` could escape the knights directory. It lives in this module,
  so every Python caller gets the same protection, not the CLI alone.
- **Legitimate subdirectories:** A knight stored in a subdirectory (e.g.,
  `default/constable.md`) is still resolved correctly — the name `"constable"` (the
  stem) is valid and does not contain path separators. The guard rejects path separators
  in the name itself, not the existence of subdirectories in the tree.

## Security Note

The path-traversal guard on `find_knight` must be preserved in all future modifications.
Do not remove or weaken it. Any caller supplying untrusted input (e.g., a name read from
a CLI argument) is protected by this guard automatically.

## Callers

| Call site | Function used | Purpose |
|---|---|---|
| `cli.py` — `knight_new` command | `create_knight` | Create a new knight file (optionally nested via `--group`) |
| `cli.py` — `knight_list` command | `list_knights` | Display all available knights |
| `cli.py` — `knight_show` command | `find_knight` | Show one knight's content |
| `cli.py` — `_show_mission` | `find_knight` | Embed knight content in mission display |

## Module Imports / Dependencies

`list_knights` imports `derive_group` from `lore.paths` and `parse_frontmatter_doc` from `lore.frontmatter`.

## Relationship to `doctrine.py`

`knight.py` intentionally mirrors the structure of `doctrine.py`:

- Both modules provide filesystem operations on a file-based entity type.
- Both are imported by `cli.py` only (no other `lore.*` module imports them).
- Both follow the Single Responsibility principle (ADR-012): one module, one concern.

The doctrine module handles YAML loading and validation. The knight module handles
markdown file discovery and resolution. Neither bleeds into the other's concern.
