"""Knight filesystem operations.

Provides discovery and resolution of knight markdown files stored under
the ``.lore/knights/`` directory. Mirrors ``doctrine.py`` in structure.
"""

from pathlib import Path

import yaml

from lore.paths import derive_group


def _parse_knight_frontmatter(filepath: Path) -> dict:
    """Parse frontmatter from a knight markdown file.

    Returns a dict with whatever fields are present in frontmatter.
    Returns an empty dict if the file has no frontmatter or the YAML is invalid.
    """
    try:
        text = filepath.read_text()
        parts = text.split("---")
        if len(parts) < 3:
            return {}
        frontmatter = yaml.safe_load(parts[1])
        if not isinstance(frontmatter, dict):
            return {}
        return frontmatter
    except Exception:
        return {}


def list_knights(knights_dir: Path) -> list[dict]:
    """Return a sorted list of knight records from the given directory tree.

    Each record is a dict with keys ``id``, ``group``, ``title``, ``summary``,
    ``name`` (file stem), and ``filename`` (full filename). Results are sorted
    by id.

    Fallback behaviour when metadata is missing:
    - ``id``: filename stem
    - ``title``: id value
    - ``summary``: empty string
    - ``group``: derived from subdirectory path

    If ``knights_dir`` does not exist, returns an empty list.
    """
    if not knights_dir.exists():
        return []

    records = []
    for filepath in knights_dir.rglob("*.md"):
        stem = filepath.stem
        fm = _parse_knight_frontmatter(filepath)
        knight_id = str(fm["id"]) if "id" in fm and fm["id"] is not None else stem
        title = str(fm["title"]) if "title" in fm and fm["title"] is not None else knight_id
        summary = str(fm["summary"]) if "summary" in fm and fm["summary"] is not None else ""
        group = derive_group(filepath, knights_dir)
        records.append({
            "id": knight_id,
            "group": group,
            "title": title,
            "summary": summary,
            "name": stem,
            "filename": filepath.name,
        })

    return sorted(records, key=lambda r: r["id"])


def find_knight(knights_dir: Path, name: str) -> Path | None:
    """Resolve a knight name to its file path.

    Returns the Path to the knight file if found, or None if not found.

    Raises ValueError immediately if ``name`` contains ``/`` or ``\\``
    (path-traversal guard).

    Resolution order:
    1. Direct path: ``knights_dir / f"{name}.md"``
    2. Fallback: first result of ``rglob(f"{name}.md")``
    """
    if "/" in name or "\\" in name:
        raise ValueError("Invalid knight name: path separators not allowed")

    if not knights_dir.exists():
        return None

    direct = knights_dir / f"{name}.md"
    if direct.exists():
        return direct

    matches = list(knights_dir.rglob(f"{name}.md"))
    if matches:
        return matches[0]

    return None
