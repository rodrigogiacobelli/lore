---
id: tech-arch-project-root-detection
title: Project Root Detection
summary: The .lore/ upward directory traversal algorithm implemented in src/lore/root.py — find_project_root() function, ProjectNotFoundError exception type and message, and lore init special-case behaviour.
related: ["tech-arch-source-layout"]
stability: stable
---

# Project Root Detection

## Module

The project root detection algorithm is implemented in `src/lore/root.py`. The module exports:

- `find_project_root(start: Path | None = None) -> Path` — locates the project root
- `ProjectNotFoundError` — raised when no `.lore/` directory is found in the directory hierarchy

## Algorithm

Lore needs to find the project root to locate `.lore/lore.db` and related files. The search strategy in `find_project_root()`:

1. Start from the current working directory (or the `start` parameter if provided). Resolve to an absolute path.
2. Look for a `.lore/` directory in the current directory. If found, return the current directory as the project root.
3. If not found, move to the parent directory and repeat.
4. If the filesystem root is reached (i.e., `current.parent == current`) without finding `.lore/`, raise `ProjectNotFoundError`.

## Error Message

When no `.lore/` is found anywhere in the hierarchy, commands that require the database fail with:

```
Not a lore project (no .lore/ directory found). Run "lore init" to initialize.
```

Exit code 1.

This is the exact message raised by `ProjectNotFoundError` in `src/lore/root.py`.

## `lore init` Special Case

`lore init` does not use `find_project_root()`. It always creates `.lore/` in the current working directory, regardless of whether a parent directory already contains a `.lore/`. Every other command (everything except `lore init` and `--help`) requires a `.lore/` directory to be present and calls `find_project_root()` to locate it.

## Path Helpers (`paths.py`)

`root.py` is responsible for *finding* the project root. Constructing paths inside
`.lore/` is the responsibility of a separate module: `src/lore/paths.py`.

`paths.py` exports seven functions, all accepting `root: Path` (the value returned by
`find_project_root()`):

| Function | Returns |
|----------|---------|
| `lore_dir(root)` | `root / ".lore"` |
| `knights_dir(root)` | `root / ".lore" / "knights"` |
| `doctrines_dir(root)` | `root / ".lore" / "doctrines"` |
| `codex_dir(root)` | `root / ".lore" / "codex"` |
| `artifacts_dir(root)` | `root / ".lore" / "artifacts"` |
| `reports_dir(root)` | `root / ".lore" / "reports"` |
| `db_path(root)` | `root / ".lore" / "lore.db"` |

Every handler in `cli.py`, `oracle.py`, and `db.get_connection()` calls these functions
rather than constructing paths inline. The magic string `".lore"` appears exactly once
in the codebase — in `paths.py`.

**`root.py` retains its existing responsibilities** — detection only — and is not
modified by the refactor. `paths.py` is a companion, not a replacement.
