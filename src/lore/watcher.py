"""Watcher module — reads watcher definitions from .lore/watchers/.

Post-G16: every operational callable takes ``project_root: Path`` first
per amendment Section A1; subdir derivation goes through
``lore.paths.entity_location``. Inline name regex replaced by
``validators.validate_name`` (patterns byte-identical). ``_validate_yaml``
raises ``ValueError`` (no Click leak).
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


def _validate_yaml(data: dict) -> None:
    """Validate watcher YAML dict by delegating to ``lore.schemas.validate_entity``.

    Raises ``ValueError`` whose message contains every issue's human-readable
    text joined by newlines on any returned issue.
    """
    issues = validate_entity("watcher-yaml", data)
    if issues:
        lines = [f"{i.pointer}: {i.message} ({i.rule})" for i in issues]
        raise ValueError("\n".join(lines))


def _find_watcher(project_root: Path, name: str) -> Path | None:
    """Return the Path to the watcher YAML file whose stem matches name, or None.

    Raises ValueError if name contains / or \\ (path-traversal guard).
    Internal — amendment C4 reclassification.
    """
    if "/" in name or "\\" in name:
        raise ValueError(f"Invalid watcher name: {name!r}")
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


def read_watcher(project_root: Path, name: str) -> dict | None:
    """Return the full 8-key watcher record dict, or None on miss.

    Shape: ``{id, group, title, summary, filename, watch_target, interval,
    action}`` per amendment B Watcher row.
    """
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
    Raises ValueError for invalid name/group, duplicate, empty content, or invalid YAML.
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
    Raises ValueError for invalid name, not found, empty content, or invalid YAML.
    """
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
    Raises ValueError for path-traversal names or if the watcher is not found.
    """
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
) -> list[dict]:
    """Return a list of watcher dicts under ``project_root/.lore/watchers/``.

    Each dict has keys: id, group, title, summary, and optional fields
    watch_target, interval, action when present in the YAML.
    Results are sorted ascending by id.
    """
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
        }
        for optional_field in ("watch_target", "interval", "action"):
            if optional_field in data:
                record[optional_field] = data[optional_field]
        watchers.append(record)

    if filter_groups:
        watchers = [w for w in watchers if group_matches_filter(w["group"], filter_groups)]

    return sorted(watchers, key=lambda w: w["id"])
