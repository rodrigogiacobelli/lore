"""Knight filesystem operations.

Provides discovery and resolution of knight markdown files stored under
the ``.lore/knights/`` directory. Mirrors ``doctrine.py`` in structure.

Post-G16: every operational callable takes ``project_root: Path`` first
per amendment Section A1; subdir derivation goes through
``lore.paths.entity_location``.
"""

from pathlib import Path

import yaml

from lore.paths import derive_group, entity_location, group_matches_filter
from lore.schemas import validate_entity
from lore.validators import (
    _validate_content_nonempty,
    validate_group,
    validate_name,
)


def _validate_frontmatter(data: dict) -> None:
    """Validate knight frontmatter by delegating to ``lore.schemas.validate_entity``.

    Raises ``ValueError`` whose message contains every issue's human-readable
    text joined by newlines on any returned issue. The CLI translator is
    responsible for converting this into the user-visible error envelope.
    """
    issues = validate_entity("knight-frontmatter", data)
    if issues:
        raise ValueError("\n".join(i.message for i in issues))


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


def list_knights(
    project_root: Path,
    filter_groups: list[str] | None = None,
) -> list[dict]:
    """Return a sorted list of knight records under ``project_root/.lore/knights/``.

    Each record is a dict with keys ``id``, ``group``, ``title``, ``summary``,
    ``name`` (file stem), and ``filename`` (full filename). Results are sorted
    by id.

    Fallback behaviour when metadata is missing:
    - ``id``: filename stem
    - ``title``: id value
    - ``summary``: empty string
    - ``group``: derived from subdirectory path

    If the knights directory does not exist, returns an empty list.
    """
    knights_dir = entity_location(project_root, "knight")
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


def _find_knight(project_root: Path, name: str) -> Path | None:
    """Resolve a knight name to its file path (internal).

    Returns the Path to the knight file if found, or None if not found.
    Raises ValueError immediately if ``name`` contains ``/`` or ``\\``
    (path-traversal guard).
    """
    if "/" in name or "\\" in name:
        raise ValueError("Invalid knight name: path separators not allowed")

    knights_dir = entity_location(project_root, "knight")
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
    project_root: Path,
    name: str,
    content: str,
    *,
    group: str | None = None,
) -> dict:
    """Create a new knight persona file under ``project_root/.lore/knights/``.

    Validation order (per amendment A4):
    1. Name format (``validate_name``)
    2. Group format (``validate_group``)
    3. Content non-empty
    4. Frontmatter parse + ``schemas.validate_entity('knight-frontmatter', meta)``
    5. Subtree-wide duplicate via ``rglob``
    6. Create target dir and write file

    Returns ``{id, filename, group}`` (amendment B knight row).
    Raises ``ValueError`` on any validation failure.
    """
    name_err = validate_name(name)
    if name_err:
        raise ValueError(name_err)

    group_err = validate_group(group)
    if group_err:
        raise ValueError(group_err)

    content_err = _validate_content_nonempty(content)
    if content_err:
        raise ValueError(content_err)

    # Inline parse to surface the schema's per-field "Missing required
    # property 'X'." text. (parse_frontmatter_text returns None when fields
    # are absent which loses the per-field detail.)
    parts = content.split("---", 2)
    meta: dict = {}
    if len(parts) >= 3:
        try:
            loaded = yaml.safe_load(parts[1])
            if isinstance(loaded, dict):
                meta = loaded
        except yaml.YAMLError:
            meta = {}
    _validate_frontmatter(meta)

    knights_dir = entity_location(project_root, "knight")
    if knights_dir.exists() and next(iter(knights_dir.rglob(f"{name}.md")), None) is not None:
        raise ValueError(f'Knight "{name}" already exists.')

    target_dir = entity_location(project_root, "knight", group=group)
    target_dir.mkdir(parents=True, exist_ok=True)
    target_path = target_dir / f"{name}.md"
    target_path.write_text(content)

    return {
        "id": name,
        "filename": f"{name}.md",
        "group": group,
    }


def read_knight(project_root: Path, name: str) -> dict | None:
    """Return the full knight record dict, or None on miss.

    Shape: ``{id, group, title, summary, filename, body}`` per amendment B
    Knight row + A2 read-shape. Supersedes canonical Section 4 text-only
    sketch.

    Path-traversal guard delegated to ``_find_knight`` (raises ``ValueError``
    on ``/`` or ``\\``). Returns None when the directory or file is absent.
    """
    filepath = _find_knight(project_root, name)
    if filepath is None:
        return None

    text = filepath.read_text()
    fm = _parse_knight_frontmatter(filepath)
    knights_dir = entity_location(project_root, "knight")
    group = derive_group(filepath, knights_dir)
    knight_id = str(fm["id"]) if "id" in fm and fm["id"] is not None else filepath.stem
    title = str(fm["title"]) if "title" in fm and fm["title"] is not None else knight_id
    summary = str(fm["summary"]) if "summary" in fm and fm["summary"] is not None else ""

    parts = text.split("---", 2)
    body = parts[2].lstrip("\n") if len(parts) >= 3 else text

    return {
        "id": knight_id,
        "group": group,
        "title": title,
        "summary": summary,
        "filename": filepath.name,
        "body": body,
    }


def update_knight(project_root: Path, name: str, content: str) -> dict:
    """Overwrite an existing knight markdown file in place.

    Returns ``{"id": name, "filename": filepath.name}`` on success
    (watcher-canonical envelope — NO ``path``, NO ``ok`` keys).

    Validation order:
    1. Path-traversal guard on ``name`` (raises ``ValueError``).
    2. Resolve via ``_find_knight``; missing → ``ValueError``.
    3. Content non-empty.
    4. Parse frontmatter inline and validate via ``_validate_frontmatter``;
       invalid → ``ValueError`` BEFORE any disk write.
    5. Overwrite the file at its existing location.
    """
    if "/" in name or "\\" in name:
        raise ValueError(f"Invalid knight name: {name!r}")

    filepath = _find_knight(project_root, name)
    if filepath is None:
        raise ValueError(f'Knight "{name}" not found.')

    content_err = _validate_content_nonempty(content)
    if content_err:
        raise ValueError(content_err)

    parts = content.split("---", 2)
    meta: dict = {}
    if len(parts) >= 3:
        try:
            loaded = yaml.safe_load(parts[1])
            if isinstance(loaded, dict):
                meta = loaded
        except yaml.YAMLError:
            meta = {}
    _validate_frontmatter(meta)

    filepath.write_text(content)
    return {"id": name, "filename": filepath.name, "updated_at": None}


def delete_knight(project_root: Path, name: str) -> dict:
    """Soft-delete a knight by renaming ``{name}.md`` to ``{name}.md.deleted``.

    Returns ``{"id": name, "deleted": True, "deleted_at": None}``
    (amendment A2: file-backed delete envelope gains ``deleted_at: None``).
    Idempotent: if the live file is absent but a ``.md.deleted`` sibling
    exists, returns the same envelope without raising.

    Raises ``ValueError`` on path-traversal names. Raises ``ValueError`` if
    neither the live file nor a ``.md.deleted`` sibling exists.
    """
    if "/" in name or "\\" in name:
        raise ValueError(f"Invalid knight name: {name!r}")

    knights_dir = entity_location(project_root, "knight")
    filepath = _find_knight(project_root, name)
    if filepath is None:
        # Idempotent: if a .md.deleted sibling exists, treat as already done.
        if knights_dir.exists():
            deleted_match = next(iter(knights_dir.rglob(f"{name}.md.deleted")), None)
            if deleted_match is not None:
                return {"id": name, "deleted": True, "deleted_at": None}
        raise ValueError(f'Knight "{name}" not found in .lore/knights/')

    deleted_path = filepath.parent / f"{name}.md.deleted"
    filepath.rename(deleted_path)
    return {"id": name, "deleted": True, "deleted_at": None}
