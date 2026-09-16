"""Doctrine storage — a directory of prose, not a graph Lore parses.

A doctrine is a directory: ``D`` is one iff ``D/<D.name>.design.md`` exists, and
its missions are the ``.md`` files under ``D/missions/``. Lore reads frontmatter
for identity — ``id``, ``title``, ``summary`` — and treats every body as an
opaque string. Step order, step type, phases and dependencies are decided by the
orchestrator from the design prose; nothing here parses them.

Discovery skips any path segment that starts with ``.`` or ends ``.deleted``,
which is what makes a soft-deleted doctrine and the staging directory a create
builds invisible in one rule.

Post nested-projects: ``list_doctrines`` and ``read_doctrine`` take ``scope=``
and every record carries ``origin``; the three write functions refuse an
origin-qualified name outright (FR-17, D-7).
"""

import os
import shutil
from collections.abc import Iterator, Sequence
from pathlib import Path, PurePosixPath, PureWindowsPath

import yaml

from lore import projects, safewrite, scoped
from lore.frontmatter import parse_frontmatter_doc, parse_frontmatter_doc_full
from lore.paths import (
    DESIGN_SUFFIX,
    derive_group,
    doctrine_design_path,
    doctrine_mission_path,
    doctrine_missions_dir,
    entity_location,
    group_matches_filter,
)
from lore.schemas import validate_entity
from lore.validators import validate_group, validate_name

DELETED_SUFFIX = ".deleted"
"""What a soft-deleted doctrine directory, and a removed mission file, end in."""

_STAGING_SUFFIX = ".lore-tmp"

_NAME_PREFIX = "Invalid name: "

_MISSION_KIND = "doctrine-mission-frontmatter"
_DESIGN_KIND = "doctrine-design-frontmatter"


# ---------------------------------------------------------------------------
# Frontmatter
# ---------------------------------------------------------------------------


def _frontmatter_mapping(text: str) -> dict:
    """Every key the frontmatter block of *text* declares, or ``{}``.

    Schema validation needs the mapping exactly as written — ``additionalProperties:
    false`` can only report an unexpected key it can see — so this keeps every key
    rather than the required-field subset ``lore.frontmatter`` returns.
    """
    parts = text.split("---", 2)
    if len(parts) < 3:
        return {}
    try:
        loaded = yaml.safe_load(parts[1])
    except yaml.YAMLError:
        return {}
    return loaded if isinstance(loaded, dict) else {}


def _validate_design_frontmatter(meta: dict | None, name: str) -> None:
    """Validate design frontmatter against its schema and the command argument.

    The id-presence check runs before full validation so an id complaint surfaces
    ahead of any other schema issue; the packaged schema's required set is
    ``[id, title, summary]`` and this ordering is what keeps the id message first.
    """
    data = meta if meta is not None else {}

    if "id" not in data:
        issues = validate_entity(_DESIGN_KIND, data)
        id_issues = [i for i in issues if "'id'" in i.message]
        raise ValueError("\n".join(i.message for i in (id_issues or issues)))
    if str(data["id"]) != name:
        raise ValueError(
            f'Design file id "{data["id"]}" does not match command argument "{name}"'
        )

    issues = validate_entity(_DESIGN_KIND, data)
    if issues:
        raise ValueError("\n".join(i.message for i in issues))


def _validate_design_content(design_content: str, name: str) -> None:
    """Rows 4 and 5 of the create validation table."""
    _validate_design_frontmatter(_frontmatter_mapping(design_content), name)


def _validate_mission_sources(missions: dict[str, str]) -> None:
    """Rows 7, 8 and 9 of the create validation table, in that order.

    Each rule runs across every mission before the next one starts, so the first
    failure a caller sees is the earliest *rule* rather than the earliest file.
    """
    ordered = sorted(missions)

    for mission_id in ordered:
        name_err = validate_name(mission_id)
        if name_err:
            raise ValueError(
                f'Invalid mission id "{mission_id}": '
                f"{name_err.removeprefix(_NAME_PREFIX)}"
            )

    frontmatter = {
        mission_id: _frontmatter_mapping(missions[mission_id])
        for mission_id in ordered
    }

    for mission_id in ordered:
        declared = frontmatter[mission_id].get("id")
        if declared is not None and str(declared) != mission_id:
            raise ValueError(
                f'Mission file id "{declared}" does not match filename stem "{mission_id}"'
            )

    for mission_id in ordered:
        issues = validate_entity(_MISSION_KIND, frontmatter[mission_id])
        if issues:
            joined = "\n".join(i.message for i in issues)
            raise ValueError(f'Mission "{mission_id}": {joined}')


# ---------------------------------------------------------------------------
# Discovery
# ---------------------------------------------------------------------------


def _reference_path(ref: str) -> PurePosixPath:
    """A stored reference as a POSIX path, whichever separator wrote it.

    ``PureWindowsPath`` reads both separators and ``as_posix`` emits one, so a
    reference a Windows-side author stored resolves the same way here.
    """
    return PurePosixPath(PureWindowsPath(ref).as_posix())


def _split_doctrine_mission_ref(ref: str) -> tuple[str, str] | None:
    """The ``(doctrine id, mission id)`` a stored reference names, or ``None``.

    The permissive half of the resolver pair's guard, on its own so ``health.py``
    asks the same question this module answers rather than re-deriving it: one
    separator is accepted, and an absolute path, a ``..`` segment or any other
    shape is refused.
    """
    relative = _reference_path(ref)
    if relative.is_absolute() or ".." in relative.parts:
        return None
    if len(relative.parts) != 2:
        return None
    return relative.parts[0], relative.parts[1]


def _is_skipped(segment: str) -> bool:
    """Whether a path segment hides everything at and below it (D1)."""
    return segment.startswith(".") or segment.endswith(DELETED_SUFFIX)


def _doctrine_dirs(doctrines_dir: Path) -> Iterator[Path]:
    """Every doctrine directory under *doctrines_dir*, in path order."""
    if not doctrines_dir.exists():
        return
    for design_file in sorted(doctrines_dir.rglob(f"*{DESIGN_SUFFIX}")):
        directory = design_file.parent
        if design_file.name != f"{directory.name}{DESIGN_SUFFIX}":
            continue
        relative = directory.relative_to(doctrines_dir)
        if not relative.parts or any(_is_skipped(part) for part in relative.parts):
            continue
        yield directory


def _is_single_segment(name: str) -> bool:
    """Whether *name* addresses one path segment and nothing else.

    The strict half of the guard, asked through ``pathlib`` rather than through a
    separator character, so it answers the same way for the separator the other
    platform writes.
    """
    relative = _reference_path(name)
    return len(relative.parts) <= 1 and not relative.is_absolute()


def _reject_traversal(name: str) -> None:
    """Refuse a user-supplied name that could address a directory outside the tree.

    A doctrine name is one path segment and nothing else. One home for the
    guard, so a scoped read enforces it as early as the locator always has — a
    doctrine is addressed by id, never by path (``decisions-006-id-references``).
    """
    if not _is_single_segment(name):
        raise ValueError("Invalid doctrine name: path separators not allowed")


def _find_doctrine_dir(project_root: Path, stem: str) -> Path | None:
    """Resolve a doctrine name to its directory, shallowest match first.

    Strict: the name comes from a user, so a path separator is refused outright
    rather than resolved. ``_resolve_doctrine_mission`` is the permissive half of
    the pair, for the reference a mission row stores.
    """
    _reject_traversal(stem)

    doctrines_dir = entity_location(project_root, "doctrine")
    matches = sorted(
        (d for d in _doctrine_dirs(doctrines_dir) if d.name == stem),
        key=lambda d: (len(d.relative_to(doctrines_dir).parts), str(d)),
    )
    return matches[0] if matches else None


def _doctrine_mission_stem(ref: str) -> str:
    """The bare mission id of a stored reference.

    ``tdd-feature-lite/recon`` -> ``recon``.
    """
    return _reference_path(ref).stem


def _resolve_doctrine_mission(project_root: Path, ref: str) -> Path | None:
    """Resolve a *stored* ``<doctrine-id>/<mission-id>`` reference to its file.

    Permissive where ``_find_doctrine_dir`` is strict: a stored reference
    legitimately carries the one separator between the doctrine and the mission,
    so that separator is accepted and everything that could climb out of
    ``.lore/doctrines/`` is refused — an absolute path, any ``..`` segment, and
    any shape that is not exactly two segments.

    Returns ``None`` whenever the reference does not name a live mission file; a
    read never raises on a reference that simply does not resolve.
    """
    split = _split_doctrine_mission_ref(ref)
    if split is None:
        return None

    doctrine_stem, mission_id = split
    directory = _find_doctrine_dir(project_root, doctrine_stem)
    if directory is None:
        return None

    path = doctrine_mission_path(directory, mission_id)
    return path if path.is_file() else None


# ---------------------------------------------------------------------------
# Reading
# ---------------------------------------------------------------------------


def _mission_record(path: Path, *, body: bool = False) -> dict:
    """One mission's index entry, keyed on the filename stem it is addressed by."""
    parsed = parse_frontmatter_doc_full(
        path, required_fields=(), extra_fields=("title", "summary")
    )
    if parsed is None:
        parsed = {"body": path.read_text()}

    record = {
        "id": path.stem,
        "title": str(parsed.get("title") or path.stem),
        "summary": str(parsed.get("summary") or ""),
    }
    if body:
        record["body"] = parsed["body"]
    return record


def _mission_index(directory: Path) -> list[dict]:
    """Every live mission of *directory*, sorted by id."""
    missions_dir = doctrine_missions_dir(directory)
    if not missions_dir.is_dir():
        return []
    return sorted(
        (
            _mission_record(path)
            for path in missions_dir.glob("*.md")
            if not path.name.startswith(".")
        ),
        key=lambda record: record["id"],
    )


def read_doctrine(
    project_root: Path,
    doctrine_id: str,
    *,
    scope: str | None = None,
    mission: str | None = None,
) -> dict | None:
    """Return a doctrine's design document and mission index, or ``None`` on miss.

    ``{id, title, summary, design, missions, origin}``, plus ``mission`` —
    ``{id, title, summary, body}`` or ``None`` — when *mission* is given.
    ``design`` is the whole design file, frontmatter included; a mission ``body``
    is frontmatter-stripped.

    A bare ``None`` means **the doctrine** missed and only that: when the
    doctrine resolves and the named mission does not, the returned dict carries
    ``"mission": None``, which is what lets a caller tell the two misses apart
    from the return value alone.

    Raises ``ValueError`` when *mission* carries a path separator.
    """
    if mission is not None and not _is_single_segment(mission):
        raise ValueError("Invalid mission id: path separators not allowed")

    row = scoped.select(
        list_doctrines(project_root, scope=scope), doctrine_id, alias=_doctrine_stem
    )
    if row is None:
        return None
    owner_root = scoped.locate(project_root, scope, row)[0]
    # A doctrine is found on disk by its directory name, which is the stem the
    # listing carries; a hand-written design file's frontmatter id is free to
    # disagree with it, and the locator globs for the stem.
    record = _read_doctrine_local(owner_root, _doctrine_stem(row), mission=mission)
    if record is None:
        return None
    return {**record, "id": row["id"], "origin": row["origin"]}


def _doctrine_stem(record: dict) -> str:
    """The directory name a doctrine is found on disk by."""
    return record["filename"].removesuffix(DESIGN_SUFFIX)


def _read_doctrine_local(
    project_root: Path, stem: str, *, mission: str | None = None
) -> dict | None:
    """Read one doctrine from the project that owns it."""
    directory = _find_doctrine_dir(project_root, stem)
    if directory is None:
        return None

    design_file = doctrine_design_path(directory)
    meta = parse_frontmatter_doc(
        design_file, required_fields=("id",), extra_fields=("title", "summary")
    )

    record: dict[str, object] = {
        "id": stem,
        "title": str((meta.get("title") if meta else None) or stem),
        "summary": str((meta.get("summary") if meta else None) or ""),
        "design": design_file.read_text(),
        "missions": _mission_index(directory),
    }
    if mission is not None:
        path = doctrine_mission_path(directory, mission)
        record["mission"] = (
            _mission_record(path, body=True) if path.is_file() else None
        )
    return record


def list_doctrines(
    project_root: Path,
    filter_groups: list[str] | None = None,
    *,
    scope: str | None = None,
) -> list[dict]:
    """List valid doctrines across every project in scope.

    Returns a list of dicts with keys: id, group, title, summary, valid,
    filename, origin. A foreign record's ``id`` is origin-qualified.

    Ordering is unchanged (D-16): this module has never sorted by id — it walks
    the doctrines tree in path order — so the merged list concatenates each
    project's own order rather than inventing a sort key the single-project
    listing does not have.

    Raises ``UnknownProjectError`` when ``scope`` names no project in scope.
    """
    return projects.collect(
        project_root,
        scope,
        read=lambda root: _list_doctrines_local(root, filter_groups),
    )


def _list_doctrines_local(
    project_root: Path, filter_groups: list[str] | None = None
) -> list[dict]:
    """List one project's own doctrines — the reader ``collect`` calls.

    A directory whose design file carries no ``id`` frontmatter is silently
    skipped, exactly as an unreadable entity file is in every other module.
    """
    doctrines_dir = entity_location(project_root, "doctrine")

    results = []
    for directory in _doctrine_dirs(doctrines_dir):
        design_file = doctrine_design_path(directory)
        meta = parse_frontmatter_doc(
            design_file, required_fields=("id",), extra_fields=("title", "summary")
        )
        if meta is None:
            continue

        doctrine_id = meta["id"]
        results.append(
            {
                "id": doctrine_id,
                "group": derive_group(directory, doctrines_dir),
                "title": str(meta.get("title") or doctrine_id),
                "summary": str(meta.get("summary") or ""),
                "valid": True,
                "filename": design_file.name,
                "origin": scoped.SELF,
            }
        )

    if filter_groups:
        results = [
            r for r in results if group_matches_filter(r.get("group", ""), filter_groups)
        ]

    return results


# ---------------------------------------------------------------------------
# Writing
# ---------------------------------------------------------------------------


def load_mission_sources(paths: Sequence[Path]) -> dict[str, str]:
    """Turn a list of mission source files into the ``{id: content}`` mapping.

    A ``dict`` cannot hold a duplicate key, so a Python caller passing
    ``missions={...}`` physically cannot express two files sharing a stem — the
    mistake exists only on the path-list side, and so does its check. It lives
    here rather than in ``cli.py`` so no rule has a home only the CLI can reach.

    Raises ``ValueError`` on a missing file or a duplicate stem.
    """
    sources: dict[str, str] = {}
    for path in paths:
        path = Path(path)
        if not path.exists():
            raise ValueError(f"File not found: {path}")
        if path.stem in sources:
            raise ValueError(
                f'Duplicate mission id "{path.stem}": two -m files share a filename stem'
            )
        sources[path.stem] = path.read_text()
    return sources


def _check_duplicate_in_subtree(name: str, doctrines_dir: Path) -> None:
    """Raise when anything under *doctrines_dir* already occupies *name*."""
    if not doctrines_dir.exists():
        return
    for candidate in sorted(doctrines_dir.rglob(name)):
        if not candidate.is_dir():
            continue
        relative = candidate.relative_to(doctrines_dir)
        if any(_is_skipped(part) for part in relative.parts):
            continue
        raise ValueError(f"Error: doctrine '{name}' already exists at {candidate}")


def create_doctrine(
    project_root: Path,
    name: str,
    design_content: str,
    missions: dict[str, str],
    *,
    group: str | None = None,
) -> dict:
    """Create a complete doctrine — design plus one or more missions — atomically.

    Validation order:
    0. Read-only rule (``projects.reject_foreign``)
    1. Name format
    2. Group format
    3. Duplicate anywhere in the subtree
    4. Design frontmatter present and its id matches *name*
    5. Design frontmatter schema
    6. At least one mission
    7. Each mission id is a valid name
    8. Each mission's frontmatter id equals its stem
    9. Each mission's frontmatter schema

    Only then does anything reach disk, and it reaches it whole: the tree is
    built inside a dot-prefixed staging directory — invisible to discovery by
    D1's skip rule — and arrives by one ``os.replace``, so no partial doctrine is
    ever left behind, a crash mid-write included.

    Returns ``{created, group, missions, path}``.
    Raises ``ForeignEntityError`` on another project's doctrine, ``ValueError``
    on every validation failure above.
    """
    projects.reject_foreign(name)
    name_err = validate_name(name)
    if name_err:
        raise ValueError(name_err)

    group_err = validate_group(group)
    if group_err:
        raise ValueError(group_err)

    doctrines_dir = entity_location(project_root, "doctrine")
    _check_duplicate_in_subtree(name, doctrines_dir)
    _validate_design_content(design_content, name)
    if not missions:
        raise ValueError("At least one mission file is required (-m)")
    _validate_mission_sources(missions)

    target_dir = entity_location(project_root, "doctrine", group=group) / name
    staging_root = doctrines_dir / f".{name}{_STAGING_SUFFIX}"
    shutil.rmtree(staging_root, ignore_errors=True)
    staged = staging_root / name
    try:
        safewrite.atomic_write_text(
            doctrine_design_path(staged), design_content, project_root=project_root
        )
        for mission_id, content in sorted(missions.items()):
            safewrite.atomic_write_text(
                doctrine_mission_path(staged, mission_id),
                content,
                project_root=project_root,
            )
        target_dir.parent.mkdir(parents=True, exist_ok=True)
        os.replace(staged, target_dir)
    finally:
        shutil.rmtree(staging_root, ignore_errors=True)

    return {
        "created": name,
        "group": group,
        "missions": sorted(missions),
        "path": f"{target_dir.relative_to(project_root).as_posix()}/",
    }


def update_doctrine(
    project_root: Path,
    name: str,
    design_content: str | None = None,
    missions: dict[str, str] | None = None,
    remove_missions: list[str] | None = None,
) -> dict:
    """Replace the design, replace or add missions, and remove missions in one call.

    Merges by stem: a mission the caller does not name is left byte-identical, so
    editing one file never requires re-supplying the rest. A removal is a
    ``.md.deleted`` rename (``decisions-003``), never an unlink, and a doctrine
    always keeps at least one live mission.

    Everything is validated before anything is written, so a validation failure
    leaves the tree exactly as it was.

    Returns ``{updated, design_replaced, missions_replaced, missions_removed}``.
    Raises ``ForeignEntityError`` on another project's doctrine, ``ValueError``
    on every validation failure.
    """
    projects.reject_foreign(name)
    name_err = validate_name(name)
    if name_err:
        raise ValueError(name_err)

    # Subtree-wide, shallowest match first — the same resolver ``read_doctrine``
    # and ``delete_doctrine`` use, so every seeded doctrine under ``default/`` is
    # reachable (``standards-dry``).
    directory = _find_doctrine_dir(project_root, name)
    if directory is None:
        raise ValueError(f'Doctrine "{name}" not found.')

    replacements = dict(missions or {})
    removals = sorted(set(remove_missions or []))

    if design_content is not None:
        _validate_design_content(design_content, name)
    _validate_mission_sources(replacements)

    live = {record["id"] for record in _mission_index(directory)}
    for mission_id in removals:
        if mission_id not in live:
            raise ValueError(f'Mission "{mission_id}" not found in doctrine "{name}"')
    if not (live - set(removals)) | set(replacements):
        raise ValueError(
            "Cannot remove every mission: a doctrine keeps at least one mission."
        )

    if design_content is not None:
        safewrite.atomic_write_text(
            doctrine_design_path(directory), design_content, project_root=project_root
        )
    for mission_id, content in sorted(replacements.items()):
        safewrite.atomic_write_text(
            doctrine_mission_path(directory, mission_id),
            content,
            project_root=project_root,
        )
    for mission_id in removals:
        path = doctrine_mission_path(directory, mission_id)
        path.rename(path.with_name(path.name + DELETED_SUFFIX))

    return {
        "updated": name,
        "design_replaced": design_content is not None,
        "missions_replaced": sorted(replacements),
        "missions_removed": removals,
    }


def delete_doctrine(project_root: Path, name: str) -> dict:
    """Soft-delete a doctrine by renaming its directory to ``<name>.deleted``.

    The directory is the entity now, so the ``.deleted`` rename
    ``decisions-003`` requires lands on it; D1's skip rule then makes the renamed
    directory invisible to discovery, to reads and to health without a second
    rule.

    Returns ``{"id": name, "deleted": True, "deleted_at": None}``.
    Raises ``ForeignEntityError`` on another project's doctrine, ``ValueError``
    on a miss.
    """
    projects.reject_foreign(name)
    name_err = validate_name(name)
    if name_err:
        raise ValueError(name_err)

    directory = _find_doctrine_dir(project_root, name)
    if directory is None:
        raise ValueError(f'Doctrine "{name}" not found')

    directory.rename(directory.with_name(f"{name}{DELETED_SUFFIX}"))
    return {"id": name, "deleted": True, "deleted_at": None}
