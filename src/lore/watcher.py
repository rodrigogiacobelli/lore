"""Watcher module — reads watcher definitions from .lore/watchers/."""

import re
from pathlib import Path

import yaml

from lore.paths import derive_group


def find_watcher(watchers_dir: Path, name: str) -> Path | None:
    """Return the Path to the watcher YAML file whose stem matches name, or None.

    Raises ValueError if name contains / or \\ (path-traversal guard).
    """
    if "/" in name or "\\" in name:
        raise ValueError(f"Invalid watcher name: {name!r}")
    if not watchers_dir.exists():
        return None
    for filepath in watchers_dir.rglob("*.yaml"):
        if filepath.stem == name:
            return filepath
    return None


def load_watcher(filepath: Path, watchers_dir: Path | None = None) -> dict:
    """Return a dict with all 8 keys for the watcher at filepath.

    Keys: id, group, title, summary, filename, watch_target, interval, action.
    Optional fields (watch_target, interval, action) are None when absent.
    If watchers_dir is provided, group is derived via derive_group; otherwise
    group is derived from the parent directory name of the filepath.
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


def create_watcher(watchers_dir: Path, name: str, content: str) -> dict:
    """Create a new watcher YAML file at watchers_dir/{name}.yaml.

    Validates name (path traversal), checks for duplicates via rglob,
    validates non-empty content and valid YAML, then writes the file.
    Returns {"id": name, "filename": f"{name}.yaml"} on success.

    Raises ValueError for invalid name, duplicate, empty content, or invalid YAML.
    """
    if not re.match(r"^[a-zA-Z0-9][a-zA-Z0-9_-]*$", name):
        raise ValueError(f"Invalid watcher name: {name!r}. Must match ^[a-zA-Z0-9][a-zA-Z0-9_-]*$")

    if not content or not content.strip():
        raise ValueError("Content must not be empty.")

    try:
        yaml.safe_load(content)
    except yaml.YAMLError as exc:
        raise ValueError(f"Invalid YAML content: {exc}") from exc

    if watchers_dir.exists():
        for existing in watchers_dir.rglob("*.yaml"):
            if existing.stem == name:
                raise ValueError(f'Watcher "{name}" already exists.')

    watchers_dir.mkdir(parents=True, exist_ok=True)
    filepath = watchers_dir / f"{name}.yaml"
    filepath.write_text(content)
    return {"id": name, "filename": f"{name}.yaml"}


def update_watcher(watchers_dir: Path, name: str, content: str) -> dict:
    """Overwrite an existing watcher YAML file in place.

    Finds the file via rglob (preserves directory/group), validates content,
    validates YAML, then overwrites the file at its current location.
    Returns {"id": name, "filename": filepath.name} on success.

    Raises ValueError for invalid name, not found, empty content, or invalid YAML.
    """
    if "/" in name or "\\" in name:
        raise ValueError(f"Invalid watcher name: {name!r}")

    if not content or not content.strip():
        raise ValueError("Content must not be empty.")

    try:
        yaml.safe_load(content)
    except yaml.YAMLError as exc:
        raise ValueError(f"Invalid YAML content: {exc}") from exc

    filepath = find_watcher(watchers_dir, name)
    if filepath is None:
        raise ValueError(f'Watcher "{name}" not found.')

    filepath.write_text(content)
    return {"id": name, "filename": filepath.name}


def delete_watcher(watchers_dir: Path, name: str) -> dict:
    """Soft-delete a watcher by renaming {name}.yaml to {name}.yaml.deleted in place.

    Uses rglob to find the file (supports group subdirectories).
    Raises ValueError for path-traversal names or if the watcher is not found.
    Returns {"id": name, "deleted": True} on success.
    """
    if "/" in name or "\\" in name:
        raise ValueError(f"Invalid watcher name: {name!r}")

    filepath = find_watcher(watchers_dir, name)
    if filepath is None:
        raise ValueError(f'Watcher "{name}" not found in .lore/watchers/')

    deleted_path = filepath.parent / f"{name}.yaml.deleted"
    filepath.rename(deleted_path)
    return {"id": name, "deleted": True}


def list_watchers(watchers_dir: Path) -> list[dict]:
    """Return a list of watcher dicts read from *.yaml files under watchers_dir.

    Each dict has keys: id, group, title, summary.
    Results are sorted ascending by id.
    Missing fields fall back to safe defaults.
    """
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
        watchers.append({
            "id": watcher_id,
            "group": derive_group(filepath, watchers_dir),
            "title": data.get("title", watcher_id),
            "summary": data.get("summary", ""),
            "filename": filepath.name,
        })

    return sorted(watchers, key=lambda w: w["id"])
