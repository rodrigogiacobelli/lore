"""Rite module — reads rite definitions from .lore/rites/.

Rites are pure-YAML files (parsed via ``yaml.safe_load``), modelled on
``watcher.py`` rather than the frontmatter-based ``codex.py``. Two subfolders
live under ``.lore/rites/``: ``main/`` (full node-graph rites) and ``shared/``
(reusable pure-procedure steps). Each subfolder is scanned RECURSIVELY: a
rite may live in any nested subdirectory, and its path relative to
``main/``/``shared/`` derives a cosmetic ``group`` used for display and
filtering only — never for identity. A rite's identity is its ``id:`` field,
which is globally unique across the entire ``main/`` + ``shared/`` tree (the
codex model). ``use:`` references a bare id and resolves by scanning the whole
``shared/`` tree.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import yaml

from lore.paths import derive_group
from lore.schemas import validate_entity
from lore.validators import validate_group, validate_rite_id


class RiteError(ValueError):
    """Raised when a rite cannot be resolved or has a dangling ``use:``."""


def _check_name(name: str) -> None:
    """Validate a rite name, re-raising the validator's ValueError as RiteError."""
    try:
        validate_rite_id(name)
    except ValueError as exc:
        raise RiteError(str(exc)) from exc


def _check_group(group: str | None) -> None:
    """Validate a ``--group`` path, raising ``RiteError`` on a bad value."""
    err = validate_group(group)
    if err:
        raise RiteError(err)


def _validate_body(content: str, *, shared: bool) -> dict:
    """Parse and schema-validate a rite body, raising ``RiteError`` on failure.

    ``shared=False`` validates against ``main-rite``; ``shared=True`` against
    ``shared-step``. The error message names the first violation:
    ``Invalid rite: <rule> at <pointer> — <message>`` (or ``Invalid shared
    step: ...``). An ``additionalProperties`` violation reports ``unknown key``.
    """
    label = "shared step" if shared else "rite"
    kind = "shared-step" if shared else "main-rite"
    try:
        data = yaml.safe_load(content)
    except yaml.YAMLError as exc:
        raise RiteError(f"Invalid {label}: {exc}") from exc
    if not isinstance(data, dict):
        raise RiteError(f"Invalid {label}: body must be a mapping")
    issues = validate_entity(kind, data)
    if issues:
        first = issues[0]
        message = "unknown key" if first.rule == "additionalProperties" else first.message
        raise RiteError(
            f"Invalid {label}: {first.rule} at {first.pointer} — {message}"
        )
    return data


def _iter_rite_files(subdir: Path):
    """Yield non-deleted ``*.yaml`` files under ``subdir`` recursively."""
    if not subdir.is_dir():
        return
    for filepath in subdir.rglob("*.yaml"):
        if filepath.is_file():
            yield filepath


def _id_of(filepath: Path) -> str:
    """Return the ``id:`` of a rite file, falling back to its stem."""
    data = yaml.safe_load(filepath.read_text(encoding="utf-8")) or {}
    return str(data.get("id", filepath.stem))


def _find_rite_file(rites_dir: Path, rite_id: str) -> tuple[Path | None, bool]:
    """Locate the file whose ``id:`` matches ``rite_id`` across the whole tree.

    Searches ``main/`` first, then ``shared/`` (both recursive). Returns
    ``(path, is_shared)``; ``(None, False)`` on miss.
    """
    for sub, is_shared in (("main", False), ("shared", True)):
        for filepath in _iter_rite_files(rites_dir / sub):
            if _id_of(filepath) == rite_id:
                return filepath, is_shared
    return None, False


def _existing_ids(rites_dir: Path) -> dict[str, Path]:
    """Map every existing rite id (main + shared) to its file path."""
    ids: dict[str, Path] = {}
    for sub in ("main", "shared"):
        for filepath in _iter_rite_files(rites_dir / sub):
            ids.setdefault(_id_of(filepath), filepath)
    return ids


def create_rite(
    rites_dir: Path,
    name: str,
    content: str,
    *,
    shared: bool = False,
    group: str | None = None,
) -> dict:
    """Validate name + schema, dup-detect across the whole tree, then write.

    Validates the name (``validate_rite_id``) and the ``group`` path
    (``validate_group``), then the YAML body against the relevant schema
    BEFORE any write. The id must be unique across the ENTIRE ``main/`` +
    ``shared/`` tree (every subfolder); any collision is rejected. Writes to
    ``main/[group/]`` (default) or ``shared/[group/]`` (``shared=True``).
    Returns ``{id, kind, group, filename, path}``.
    """
    _check_name(name)
    _check_group(group)
    _validate_body(content, shared=shared)

    if name in _existing_ids(rites_dir):
        raise RiteError(f'Rite "{name}" already exists.')

    kind = "shared" if shared else "main"
    target_dir = rites_dir / kind
    if group:
        target_dir = target_dir.joinpath(*group.split("/"))
    target_dir.mkdir(parents=True, exist_ok=True)
    (target_dir / f"{name}.yaml").write_text(content, encoding="utf-8")

    rel_parts = [kind]
    if group:
        rel_parts.extend(group.split("/"))
    rel_parts.append(f"{name}.yaml")
    return {
        "id": name,
        "kind": kind,
        "group": group,
        "filename": f"{name}.yaml",
        "path": ".lore/rites/" + "/".join(rel_parts),
    }


def update_rite(
    rites_dir: Path,
    name: str,
    content: str,
    *,
    shared: bool = False,
) -> dict:
    """Re-validate and overwrite an existing rite in place; refuses create-via-edit.

    The rite is located by id via a recursive scan of the whole tree (the
    ``shared`` flag only selects the schema to validate against). Not-found
    raises ``RiteError``. The body is re-validated before write. Returns the
    full parsed entity dict.
    """
    _check_name(name)
    filepath, _ = _find_rite_file(rites_dir, name)
    if filepath is None:
        raise RiteError(f'Rite "{name}" not found')

    data = _validate_body(content, shared=shared)
    filepath.write_text(content, encoding="utf-8")
    return data


def delete_rite(rites_dir: Path, name: str, *, shared: bool = False) -> dict:
    """Soft-delete a rite by renaming ``<name>.yaml`` to ``<name>.yaml.deleted``.

    The rite is located by id via a recursive scan of the whole tree (the
    ``shared`` flag is accepted for parity but does not affect lookup).
    Not-found (absent or already deleted) raises ``RiteError``. Returns
    ``{id, group, deleted_at}``.
    """
    _check_name(name)
    filepath, _ = _find_rite_file(rites_dir, name)
    if filepath is None:
        raise RiteError(f'Rite "{name}" not found')

    kind_dir = rites_dir / ("shared" if filepath.is_relative_to(rites_dir / "shared") else "main")
    group = derive_group(filepath, kind_dir)
    filepath.rename(filepath.with_name(f"{filepath.stem}.yaml.deleted"))
    deleted_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S+00:00")
    return {"id": name, "group": group or None, "deleted_at": deleted_at}


def scan_rites(rites_dir: Path, *, shared: bool = False) -> list[dict]:
    """Return the rite records under ``rites_dir`` (recursive).

    Reads ``main/**/*.yaml`` by default; ``shared=True`` reads
    ``shared/**/*.yaml``. Skips ``*.yaml.deleted`` soft-deleted files. Each
    returned dict is the parsed body with a derived ``group`` key attached
    (root → ``""``). Results are sorted by ``(group, id)``. An empty or missing
    subfolder returns ``[]``.
    """
    kind_dir = rites_dir / ("shared" if shared else "main")
    rites: list[dict] = []
    for filepath in _iter_rite_files(kind_dir):
        data = yaml.safe_load(filepath.read_text(encoding="utf-8")) or {}
        data["group"] = derive_group(filepath, kind_dir)
        rites.append(data)
    rites.sort(key=lambda r: (r.get("group", ""), r.get("id", "")))
    return rites


def search_rites(rites_dir: Path, query: str) -> list[dict]:
    """Return main rites whose id/title/summary/trigger match ``query``.

    Case-insensitive substring browse over main rites only (recursive). No
    match returns ``[]``. This is keyword browse, not the deferred situational
    matcher.
    """
    needle = query.lower()
    return [
        r
        for r in scan_rites(rites_dir)
        if any(
            needle in str(r.get(field, "")).lower()
            for field in ("id", "title", "summary", "trigger")
        )
    ]


def read_rite(rites_dir: Path, rite_id: str) -> dict:
    """Resolve ``rite_id`` by id and return the rite, inlining shared steps.

    Resolution scans ``main/`` then ``shared/`` (both recursive) for the file
    whose ``id:`` matches ``rite_id``. A main rite has each ``use:``-node
    flat-inlined: the shared step is looked up BY ID anywhere under ``shared/``
    and attached as a ``"step"`` key on the node (non-recursive — shared steps
    do not ``use:``). A bare shared-step id resolves to the shared-step object
    alone.

    Raises ``RiteError`` for a not-found id (including soft-deleted) and for a
    dangling ``use:`` whose shared step id is absent from ``shared/``.
    """
    filepath, is_shared = _find_rite_file(rites_dir, rite_id)

    if filepath is not None and not is_shared:
        rite = yaml.safe_load(filepath.read_text(encoding="utf-8")) or {}
        for node in rite.get("nodes", []):
            use_id = node.get("use")
            if use_id is None:
                continue
            step_path, _ = _find_rite_file(rites_dir, str(use_id))
            if step_path is None or not step_path.is_relative_to(rites_dir / "shared"):
                raise RiteError(
                    f'Rite "{rite_id}": shared step "{use_id}" not found'
                )
            node["step"] = yaml.safe_load(step_path.read_text(encoding="utf-8")) or {}
        return rite

    if filepath is not None:
        return yaml.safe_load(filepath.read_text(encoding="utf-8")) or {}

    # Not found among live files — look for a soft-deleted match by stem.
    for sub in ("main", "shared"):
        subdir = rites_dir / sub
        if not subdir.is_dir():
            continue
        for deleted in subdir.rglob(f"{rite_id}.yaml.deleted"):
            ts = (
                datetime.fromtimestamp(deleted.stat().st_mtime, tz=timezone.utc)
                .strftime("%Y-%m-%dT%H:%M:%S+00:00")
            )
            raise RiteError(f'Rite "{rite_id}" not found (deleted on {ts})')

    raise RiteError(f'Rite "{rite_id}" not found')
