"""Knight filesystem operations.

Provides discovery and resolution of knight markdown files stored under
the ``.lore/knights/`` directory. Mirrors ``doctrine.py`` in structure.
"""

from pathlib import Path

import click
import yaml

from lore.paths import derive_group, group_matches_filter
from lore.schemas import validate_entity
from lore.validators import validate_group, validate_name


def _validate_frontmatter(data: dict) -> None:
    """Validate knight frontmatter by delegating to ``lore.schemas.validate_entity``.

    Raises ``click.ClickException`` whose ``.message`` contains every issue's
    human-readable text on any returned issue.
    """
    issues = validate_entity("knight-frontmatter", data)
    if issues:
        raise click.ClickException("\n".join(i.message for i in issues))


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


def list_knights(knights_dir: Path, filter_groups: list[str] | None = None) -> list[dict]:
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

    if filter_groups:
        records = [r for r in records if group_matches_filter(r["group"], filter_groups)]

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


def create_knight(
    knights_dir: Path,
    name: str,
    content: str,
    *,
    group: str | None = None,
) -> dict:
    """Create a new knight persona file under ``knights_dir``.

    Validation order:
    1. Name format (``validate_name``)
    2. Group format (``validate_group``)
    3. Subtree-wide duplicate via ``rglob``
    4. Create target dir and write file

    When ``group`` is None, file is written at ``knights_dir/{name}.md``.
    When provided, file is written at ``knights_dir/{group}/{name}.md`` with
    intermediate directories auto-created.

    Returns a dict with keys: ``name``, ``group``, ``filename``, ``path``.
    Raises ``ValueError`` on any validation failure.
    """
    name_err = validate_name(name)
    if name_err:
        raise ValueError(name_err)

    group_err = validate_group(group)
    if group_err:
        raise ValueError(group_err)

    if next(iter(knights_dir.rglob(f"{name}.md")), None) is not None:
        raise ValueError(f'Knight "{name}" already exists.')

    target_dir = knights_dir if group is None else knights_dir / Path(group)
    target_dir.mkdir(parents=True, exist_ok=True)
    target_path = target_dir / f"{name}.md"
    target_path.write_text(content)

    return {
        "name": name,
        "group": group,
        "filename": f"{name}.md",
        "path": str(target_path),
    }
