---
id: tech-arch-knight-module
title: Knight Module Internals
summary: >
  Technical reference for src/lore/knight.py. Covers list_knights and find_knight
  function signatures, the path-traversal guard, and how cli.py uses these functions
  in knight_list, knight_show, and _show_mission.
related: ["conceptual-entities-knight", "tech-arch-source-layout"]
stability: stable
---

# Knight Module Internals

**Source module:** `src/lore/knight.py`

This module provides filesystem operations for knight files. It mirrors `doctrine.py`
in structure: a dedicated module for file-based entity operations, imported by `cli.py`
only. It ships as part of the ADR-012 refactor (REFACTOR-2), replacing inline file
operations that were previously embedded directly in `cli.py`.

## Purpose

Before this module existed, knight file operations — globbing the directory, reading
files, resolving knight names to paths — were implemented inline in `cli.py` at multiple
call sites. REFACTOR-2 extracts these operations into a single authoritative location,
following the Single Responsibility principle (ADR-012).

## Public Interface

### `list_knights(knights_dir: Path) -> list[dict]`

Returns a sorted list of knight records from the given directory tree.

- **Input:** `knights_dir` — the `.lore/knights/` directory (typically obtained via
  `paths.knights_dir(root)`).
- **Output:** `list[{"id": str, "group": str, "title": str, "summary": str, "name": str, "filename": str}]` sorted by `id`.
- **Frontmatter parsing:** Uses `frontmatter.parse_frontmatter_doc(filepath, required_fields=("id", "title", "summary"))`. If frontmatter is absent or incomplete, falls back to: `id` = filename stem, `title` = filename stem, `summary` = `""`.
- **GROUP derivation:** Uses `paths.derive_group(filepath, knights_dir)` to compute the GROUP from intermediate directory components joined with `-`.
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
  such as `"../sensitive"` could escape the knights directory. The guard previously
  lived inline in `cli.py`; it now lives here so that any Python caller (not just
  the CLI) gets the same protection.
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
| `cli.py` — `knight_list` command | `list_knights` | Display all available knights |
| `cli.py` — `knight_show` command | `find_knight` | Show one knight's content |
| `cli.py` — `_show_mission` | `find_knight` | Embed knight content in mission display |

Four call sites in `cli.py` that previously inlined knight resolution logic were
replaced by `knight.find_knight` calls in REFACTOR-2.

## Module Imports / Dependencies

`list_knights` imports `derive_group` from `lore.paths` and `parse_frontmatter_doc` from `lore.frontmatter`.

## Relationship to `doctrine.py`

`knight.py` intentionally mirrors the structure of `doctrine.py`:

- Both modules provide filesystem operations on a file-based entity type.
- Both are imported by `cli.py` only (no other `lore.*` module imports them).
- Both follow the Single Responsibility principle (ADR-012): one module, one concern.

The doctrine module handles YAML loading and validation. The knight module handles
markdown file discovery and resolution. Neither bleeds into the other's concern.
