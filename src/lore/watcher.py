"""Watcher module — reads watcher definitions from .lore/watchers/.

Post-G16: every operational callable takes ``project_root: Path`` first
per amendment Section A1; subdir derivation goes through
``lore.paths.entity_location``. Inline name regex replaced by
``validators.validate_name`` (patterns byte-identical). ``_validate_yaml``
raises ``ValueError`` (no Click leak).
"""

from pathlib import Path

import yaml

from lore import projects, scoped
from lore.paths import derive_group, entity_location, group_matches_filter
from lore.schemas import validate_entity
from lore.validators import (
    _validate_content_nonempty,
    validate_group,
    validate_name,
)


def _validate_yaml(data: dict) -> None:
    """Validate watcher YAML dict by delegating to ``lore.schemas.validate_entity``.

    Raises ``ValueError`` whose message contains every issue's human-readable
    text joined by newlines on any returned issue.
    """
    issues = validate_entity("watcher-yaml", data)
    if issues:
        lines = [f"{i.pointer}: {i.message} ({i.rule})" for i in issues]
        raise ValueError("\n".join(lines))


def _reject_traversal(name: str) -> None:
    """Refuse a name that could address a file outside the watchers tree.

    One home for the guard, so a scoped read enforces it as early as the
    locator always has — a watcher is addressed by name, never by path
    (``decisions-006-id-references``).
    """
    if "/" in name or "\\" in name:
        raise ValueError(f"Invalid watcher name: {name!r}")


def _find_watcher(project_root: Path, name: str) -> Path | None:
    """Return the Path to the watcher YAML file whose stem matches name, or None.

    Raises ValueError if name contains / or \\ (path-traversal guard).
    Internal — amendment C4 reclassification.
    """
    _reject_traversal(name)
    watchers_dir = entity_location(project_root, "watcher")
    if not watchers_dir.exists():
        return None
    for filepath in watchers_dir.rglob("*.yaml"):
        if filepath.stem == name:
            return filepath
    return None


def _load_watcher(filepath: Path, watchers_dir: Path | None = None) -> dict:
    """Return a dict with all 8 keys for the watcher at filepath.

    Keys: id, group, title, summary, filename, watch_target, interval, action.
    Optional fields (watch_target, interval, action) are None when absent.
    Internal — amendment C4 reclassification.
    """
    data = yaml.safe_load(filepath.read_text()) or {}
    stem = filepath.stem
    watcher_id = data.get("id", stem)
    if watchers_dir is not None:
        group = derive_group(filepath, watchers_dir)
    else:
        group = filepath.parent.name
    return {
        "id": watcher_id,
        "group": group,
        "title": data.get("title", watcher_id),
        "summary": data.get("summary", ""),
        "filename": filepath.name,
        "watch_target": data.get("watch_target"),
        "interval": data.get("interval"),
        "action": data.get("action"),
    }


def read_watcher(
    project_root: Path, name: str, *, scope: str | None = None
) -> dict | None:
    """Return the full watcher record dict, or None on miss.

    Shape: ``{id, group, title, summary, filename, watch_target, interval,
    action, origin}`` per amendment B Watcher row plus nested projects. A
    bare name resolves locally before an inherited one of the same name, and
    a qualified name never resolves locally (D-8); an unexported ancestor
    watcher is a miss.
    """
    _reject_traversal(name)
    row = scoped.select(
        list_watchers(project_root, scope=scope), name, alias=_watcher_stem
    )
    if row is None:
        return None
    owner_root = scoped.locate(project_root, scope, row)[0]
    # A watcher is found on disk by file stem; its ``id:`` may disagree.
    record = _read_watcher_local(owner_root, _watcher_stem(row))
    if record is None:
        return None
    return {**record, "id": row["id"], "origin": row["origin"]}


def read_watcher_text(
    project_root: Path, name: str, *, scope: str | None = None
) -> str | None:
    """Return the raw text of a watcher's file, or ``None`` on a miss.

    ``lore watcher show`` prints a watcher's file verbatim, and the record
    :func:`read_watcher` returns holds no text. The text is a second entry
    shape rather than a tenth key on that record, because the record *is* the
    ``watcher show --json`` envelope: a key added there changes shipped output
    (SC-7) and its exact key set is pinned.

    Resolution is :func:`read_watcher`'s own — a bare name locally first, a
    qualified name never locally (D-8) — so the file this returns is always
    the file that record describes, read from the project that owns it.
    """
    _reject_traversal(name)
    row = scoped.select(
        list_watchers(project_root, scope=scope), name, alias=_watcher_stem
    )
    if row is None:
        return None
    owner_root = scoped.locate(project_root, scope, row)[0]
    filepath = _find_watcher(owner_root, _watcher_stem(row))
    if filepath is None:
        return None
    return filepath.read_text()


def _watcher_stem(record: dict) -> str:
    """The file stem a watcher record is found on disk by."""
    return Path(record["filename"]).stem


def _read_watcher_local(project_root: Path, name: str) -> dict | None:
    """Read one watcher from the project that owns it."""
    filepath = _find_watcher(project_root, name)
    if filepath is None:
        return None
    watchers_dir = entity_location(project_root, "watcher")
    return _load_watcher(filepath, watchers_dir)


def create_watcher(
    project_root: Path,
    name: str,
    content: str,
    *,
    group: str | None = None,
) -> dict:
    """Create a new watcher YAML file under the project's ``.lore/watchers/``.

    Returns ``{id, filename, group}`` (amendment B Watcher row — drops ``path``).
    Raises ``ForeignEntityError`` on another project's watcher (FR-17, D-7).
    Raises ValueError for invalid name/group, duplicate, empty content, or invalid YAML.
    """
    projects.reject_foreign(name)
    name_err = validate_name(name)
    if name_err:
        raise ValueError(name_err)

    group_err = validate_group(group)
    if group_err:
        raise ValueError(group_err)

    content_err = _validate_content_nonempty(content)
    if content_err:
        raise ValueError(content_err)

    try:
        yaml.safe_load(content)
    except yaml.YAMLError as exc:
        raise ValueError(f"Invalid YAML content: {exc}") from exc

    if _find_watcher(project_root, name) is not None:
        raise ValueError(f'Watcher "{name}" already exists.')

    target_dir = entity_location(project_root, "watcher", group=group)
    target_dir.mkdir(parents=True, exist_ok=True)
    filepath = target_dir / f"{name}.yaml"
    filepath.write_text(content)
    return {
        "id": name,
        "filename": f"{name}.yaml",
        "group": group,
    }


def update_watcher(project_root: Path, name: str, content: str) -> dict:
    """Overwrite an existing watcher YAML file in place.

    Returns {"id": name, "filename": filepath.name} on success.
    Raises ValueError for invalid name, not found, empty content, or invalid
    YAML, and ``ForeignEntityError`` on another project's watcher (FR-17, D-7).
    """
    projects.reject_foreign(name)
    if "/" in name or "\\" in name:
        raise ValueError(f"Invalid watcher name: {name!r}")

    content_err = _validate_content_nonempty(content)
    if content_err:
        raise ValueError(content_err)

    try:
        yaml.safe_load(content)
    except yaml.YAMLError as exc:
        raise ValueError(f"Invalid YAML content: {exc}") from exc

    filepath = _find_watcher(project_root, name)
    if filepath is None:
        raise ValueError(f'Watcher "{name}" not found.')

    filepath.write_text(content)
    return {"id": name, "filename": filepath.name, "updated_at": None}


def delete_watcher(project_root: Path, name: str) -> dict:
    """Soft-delete a watcher by renaming {name}.yaml to {name}.yaml.deleted in place.

    Returns ``{"id": name, "deleted": True, "deleted_at": None}`` (amendment A2).
    Raises ValueError for path-traversal names or if the watcher is not found,
    and ``ForeignEntityError`` on another project's watcher (FR-17, D-7).
    """
    projects.reject_foreign(name)
    if "/" in name or "\\" in name:
        raise ValueError(f"Invalid watcher name: {name!r}")

    filepath = _find_watcher(project_root, name)
    if filepath is None:
        raise ValueError(f'Watcher "{name}" not found in .lore/watchers/')

    deleted_path = filepath.parent / f"{name}.yaml.deleted"
    filepath.rename(deleted_path)
    return {"id": name, "deleted": True, "deleted_at": None}


def list_watchers(
    project_root: Path,
    filter_groups: list[str] | None = None,
    *,
    scope: str | None = None,
) -> list[dict]:
    """Return watcher records for every project in scope.

    Each dict has keys: id, group, title, summary, filename, origin, and the
    optional fields watch_target, interval, action when present in the YAML.
    A foreign record's ``id`` is origin-qualified. Results are sorted
    ascending by id — the qualified id for a foreign record (D-16).

    Raises ``UnknownProjectError`` when ``scope`` names no project in scope.
    """
    records = projects.collect(
        project_root,
        scope,
        read=lambda root: _list_watchers_local(root, filter_groups),
    )
    return sorted(records, key=lambda w: w["id"])


def _list_watchers_local(
    project_root: Path,
    filter_groups: list[str] | None = None,
) -> list[dict]:
    """List one project's own watchers — the reader ``collect`` calls."""
    watchers_dir = entity_location(project_root, "watcher")
    if not watchers_dir.exists():
        return []

    watchers = []
    for filepath in watchers_dir.rglob("*.yaml"):
        try:
            data = yaml.safe_load(filepath.read_text()) or {}
        except Exception:
            data = {}

        stem = filepath.stem
        watcher_id = data.get("id", stem)
        record = {
            "id": watcher_id,
            "group": derive_group(filepath, watchers_dir),
            "title": data.get("title", watcher_id),
            "summary": data.get("summary", ""),
            "filename": filepath.name,
            "origin": scoped.SELF,
        }
        for optional_field in ("watch_target", "interval", "action"):
            if optional_field in data:
                record[optional_field] = data[optional_field]
        watchers.append(record)

    if filter_groups:
        watchers = [w for w in watchers if group_matches_filter(w["group"], filter_groups)]

    return sorted(watchers, key=lambda w: w["id"])
