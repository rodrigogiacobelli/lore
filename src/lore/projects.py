"""Project topology, export resolution and origin-qualified addressing.

Spec: ``nested-projects-spec``. One authoritative home for three questions a
tree of Lore projects raises, instead of spreading walks across ``root.py``,
table parsing across ``config.py`` and merge loops across seven entity modules
(D-1):

  * **Where are the other projects?** — one upward walk for the ancestors that
    export to this project, one downward walk for the projects beneath it.
  * **May this entity cross a boundary?** — :func:`exported_ids` and
    :func:`exports_glossary`, and nothing else, answer that.
  * **What is this entity called from here?** — the ``<project>:<entity-id>``
    algebra, split on the first colon only, because a codex id may hold one.

Two axes, not one (D-3, A-7). **Inheritance is unconditional**: a project sees
what its ancestors export to it at every scope, with no flag. **Federation is
opt-in**: nothing walks downward unless ``scope`` asks for ``all`` or names a
project. A change that collapses the two onto one ``scope`` value is a breach
of A-7, not a simplification, and SC-6 and SC-7 are what make it visible.

Standards:
  * ``standards-single-responsibility`` — this module owns topology, export
    resolution and qualification, and nothing else. It never reads an entity
    file; :func:`collect` takes a reader callback instead (D-2).
  * ``standards-dependency-inversion`` — it imports :mod:`lore.paths`,
    :mod:`lore.config`, :mod:`lore.validators` and stdlib only, and imports no
    entity module, so the arrow points one way.
  * ``standards-dry`` — one glob matcher for ids, one seeded-default test, one
    merge loop, one read-only rule.
"""

from __future__ import annotations

import fnmatch
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Sequence

from lore.config import Config, DescendantExport, load_config
from lore.paths import (
    codex_dir,
    derive_group,
    is_transient_codex_path,
    lore_dir,
    resolve_beneath,
)
from lore.validators import is_glob_pattern


_SELF = "self"
"""The reserved origin, relation and scope token for "this project"."""

_ANCESTOR = "ancestor"
"""The relation of a project above this one that exports into it."""

_DESCENDANT = "descendant"
"""The relation of a project beneath this one."""

_PRUNED_DIRECTORIES = frozenset({".git", "node_modules", ".venv", "__pycache__"})
"""Directories the downward walk never descends into (N-3).

The project marker directory is pruned too, but its name is read off
:func:`lore.paths.lore_dir` rather than spelled again here.
"""

_SOURCES_LAYER = "sources"
"""The codex layer an export never reaches, beside ``transient/`` (A-2).

``transient/`` is asked through :func:`lore.paths.is_transient_codex_path`,
which ADR-019 constraint 1 makes the single home for that boundary.
"""

_ALL = "all"
"""The scope token for "this project, what it inherits, and everything below"."""


@dataclass(frozen=True)
class ProjectRef:
    """One project in scope: its resolved name, its root, and how it relates.

    ``relation`` is ``"self"``, ``"ancestor"`` or ``"descendant"``. The two
    foreign relations behave differently on purpose: an ancestor's entities are
    export-filtered because inheritance is a curated offer, while a named
    descendant's are not, because an ancestor asking for one wants that
    project's material rather than its own exports reflected back (D-4).
    """

    name: str
    root: Path
    relation: str


@dataclass(frozen=True)
class ExportCandidate:
    """One entity an ancestor might export, with what decides its eligibility.

    ``group`` is the entity's derived group, or ``None`` for records that carry
    no group — no seeded-default filter applies to those. ``path`` is the
    record's file, or ``None`` when the reader does not return one; it is read
    only to answer the codex-layer question (A-2).
    """

    entity_id: str
    group: str | None = None
    path: Path | None = None


class UnknownProjectError(Exception):
    """Raised when ``--project <name>`` names no project in scope."""


class ForeignEntityError(Exception):
    """Raised when a write targets an entity belonging to another project."""


# ---------------------------------------------------------------------------
# The ID algebra
# ---------------------------------------------------------------------------


def qualify(origin: str, entity_id: str) -> str:
    """Return *entity_id* as seen from another project.

    A ``self`` origin leaves the id bare, so a project's own rows read exactly
    as they did before the feature existed (SC-7).
    """
    if origin == _SELF:
        return entity_id
    return f"{origin}:{entity_id}"


def split_qualified(token: str) -> tuple[str | None, str]:
    """Split *token* into ``(origin, entity_id)``, on the **first** colon only.

    A bare token returns ``(None, token)``. Codex ids are free-form non-empty
    strings, so a local id holding a colon must keep working (D-8).

    Performs no resolution: whether the left half names a project in scope is
    the caller's question, not this function's.
    """
    origin, separator, entity_id = token.partition(":")
    if not separator:
        return None, token
    return origin, entity_id


def is_qualified(token: str) -> bool:
    """Whether *token* carries an origin qualifier."""
    return split_qualified(token)[0] is not None


def index_key(entry: str, *, self_name: str) -> str:
    """Normalise a ``related`` entry for a scoped index (D-17).

    An entry whose origin equals this project's own name is a document we own,
    written from the other side of the boundary, and reduces to its bare id.
    That is what lets an ancestor's ``related: [lore:tech-db-schema]``, read
    from inside ``lore``, resolve to the local ``tech-db-schema``. Every other
    entry keeps its form.
    """
    origin, entity_id = split_qualified(entry)
    return entity_id if origin == self_name else entry


def matches_export(entity_id: str, pattern: str) -> bool:
    """Whether *entity_id* matches an export *pattern* (D-9).

    A pattern with no glob character is compared literally — never as a prefix.
    A glob pattern goes to :func:`fnmatch.fnmatchcase`, not ``fnmatch``, so
    matching cannot quietly change between macOS and Linux.
    """
    if not is_glob_pattern(pattern):
        return entity_id == pattern
    return fnmatch.fnmatchcase(entity_id, pattern)


def is_seeded_default(group: str) -> bool:
    """Whether *group* names a subtree ``lore init`` seeds (D-10, A-3).

    The authoritative test wherever code must tell a file Lore installed from
    one a project authored. No seeded default is exportable: a project's own
    copy is the only one that applies to it (FR-10).
    """
    return group == "default" or group.startswith("default/")


def reject_foreign(entity_id: str) -> None:
    """Raise :class:`ForeignEntityError` when *entity_id* belongs elsewhere.

    Called as the first statement of every externally callable write function
    on a file-backed entity, so the rule holds for a Python caller and not only
    at the CLI seam (D-7, ADR-011).
    """
    if is_qualified(entity_id):
        raise ForeignEntityError(
            f'Cannot write "{entity_id}": '
            "an entity from another project is read-only."
        )


# ---------------------------------------------------------------------------
# Topology
# ---------------------------------------------------------------------------


def project_name(project_root: Path) -> str:
    """Return the project's own resolved name (FR-1, A-5).

    Its ``project-name`` config value when set, else its directory's name. A
    project names itself: no ancestor can rename it, and a ``[[descendants]]``
    block's label has no resolving power. Never raises — an unreadable config
    falls back like an absent one.
    """
    return _resolved_name(project_root, load_config(project_root))


def resolve_ancestors(project_root: Path) -> tuple[ProjectRef, ...]:
    """Return the ancestors that export to *project_root*, nearest first.

    Walks from the parent directory to the filesystem root, probing for the
    project marker with :func:`Path.is_dir` and reading a config only where one
    exists — at most one per directory, which is the whole of N-4's budget and
    why SC-6 holds. There is no ``$HOME`` stop and no configuration on this
    side: a project learns what it inherits without declaring anything.

    A directory whose config declares neither ``[shared]`` nor a matching
    ``[[descendants]]`` block exports nothing, so a stray marker above a
    project is inert. Never raises; an unreadable ancestor config yields no
    ref.
    """
    root = project_root.resolve()
    refs: list[ProjectRef] = []
    current = root.parent
    while True:
        if lore_dir(current).is_dir():
            config = load_config(current)
            if _exports_to(current, root, config):
                refs.append(
                    ProjectRef(_resolved_name(current, config), current, _ANCESTOR)
                )
        parent = current.parent
        if parent == current:
            return tuple(refs)
        current = parent


def discover_descendants(project_root: Path) -> tuple[ProjectRef, ...]:
    """Return every Lore project beneath *project_root*, sorted by name.

    A filesystem walk with no registration (FR-7), pruning the directories N-3
    names from ``dirnames`` in place so they are never descended into at all.
    ``followlinks=False`` keeps the walk inside the subtree and rules out
    cycles. A directory holding the project marker is a project, and the walk
    continues into it, so a project nested inside a project is still found.

    Runs only when the resolved scope is ``all`` or names a project (D-13): a
    project in no tree never pays for this.
    """
    root = project_root.resolve()
    pruned = _PRUNED_DIRECTORIES | {lore_dir(root).name}
    found: list[ProjectRef] = []
    for dirpath, dirnames, _filenames in os.walk(root, followlinks=False):
        dirnames[:] = sorted(name for name in dirnames if name not in pruned)
        current = Path(dirpath)
        if current != root and lore_dir(current).is_dir():
            found.append(ProjectRef(project_name(current), current, _DESCENDANT))
    return tuple(sorted(found, key=lambda ref: ref.name))


def list_projects(project_root: Path) -> list[ProjectRef]:
    """Return every project in scope: self, then ancestors, then descendants.

    The widest scope there is, which is why it is that scope rather than a
    second assembly of the same three parts.
    """
    return list(resolve_scope(project_root, _ALL))


def resolve_project(project_root: Path, name: str) -> ProjectRef:
    """Return the project called *name*, or raise :class:`UnknownProjectError`.

    Matches a project's **own** resolved name, never a ``[[descendants]]``
    block's label (D-11).
    """
    refs = list_projects(project_root)
    for ref in refs:
        if ref.name == name:
            return ref
    others = sorted(ref.name for ref in refs if ref.relation != _SELF)
    if not others:
        raise UnknownProjectError(
            f'Unknown project "{name}". No other Lore project is in scope.'
        )
    raise UnknownProjectError(
        f'Unknown project "{name}". Projects in scope: {", ".join(others)}.'
    )


def resolve_scope(project_root: Path, scope: str | None) -> tuple[ProjectRef, ...]:
    """Resolve a ``--project`` value into the projects to read.

    ``None`` reads ``default-project-scope``. ``self`` is this project and its
    ancestors; ``all`` adds every descendant; any other value names one
    project and returns it alone. The upward half is in every answer because
    inheritance is unconditional — ``scope`` governs the downward axis only
    (D-3, A-7).
    """
    config = load_config(project_root)
    resolved = config.default_project_scope if scope is None else scope
    if resolved not in (_SELF, _ALL):
        return (resolve_project(project_root, resolved),)

    self_ref = ProjectRef(_resolved_name(project_root, config), project_root, _SELF)
    refs = [self_ref, *resolve_ancestors(project_root)]
    if resolved == _ALL:
        refs.extend(discover_descendants(project_root))
    return tuple(refs)


# ---------------------------------------------------------------------------
# Export resolution
# ---------------------------------------------------------------------------


def exported_ids(
    ancestor_root: Path,
    descendant_root: Path,
    *,
    candidates: Sequence[ExportCandidate],
) -> frozenset[str]:
    """Return the ids *ancestor_root* offers *descendant_root*.

    The union of the ancestor's ``[shared].exports`` and the ``[[descendants]]``
    block whose ``path`` resolves to the descendant (D-11), minus everything
    that may not cross a boundary at all. Both exclusions are resolved here, so
    this stays the single home for "may this entity cross" (``standards-dry``):

      1. a seeded default (D-10), skipped for candidates carrying no group;
      2. a codex document under ``transient/`` or ``sources/`` (A-2).
    """
    config = load_config(ancestor_root)
    block = _descendant_block(ancestor_root, descendant_root, config)
    patterns = config.shared.exports + (block.exports if block else ())
    if not patterns:
        return frozenset()
    return frozenset(
        candidate.entity_id
        for candidate in candidates
        if _may_cross(ancestor_root, candidate)
        and any(matches_export(candidate.entity_id, pattern) for pattern in patterns)
    )


def exports_glossary(ancestor_root: Path, descendant_root: Path) -> bool:
    """Whether *ancestor_root* exports its glossary to *descendant_root*.

    The glossary is exported whole or not at all — a keyword is natural
    language matched against document prose, not an id, so there is no partial
    unit to express (D-22). ``[shared].glossary`` reaches every descendant
    (FR-3), which is why the descendant is named for symmetry with
    :func:`exported_ids` but not consulted.
    """
    return load_config(ancestor_root).shared.glossary


# ---------------------------------------------------------------------------
# The merge
# ---------------------------------------------------------------------------


def collect(
    project_root: Path,
    scope: str | None,
    *,
    read: Callable[[Path], list[dict]],
    id_key: str = "id",
    group_key: str | None = "group",
    exportable: bool = True,
) -> list[dict]:
    """Read every project in scope through *read* and merge the records.

    One merge loop for every entity kind (D-2). *read* is the caller's own
    single-project reader, so this module never imports an entity module and
    the dependency arrow keeps pointing inward.

    Each record is returned as a tagged copy: ``origin`` is ``"self"`` or the
    originating project's name, and a foreign record's *id_key* is qualified.
    An **ancestor**'s records are filtered to what it exports; a
    **descendant**'s never are (D-4).

    *id_key* names the key holding the entity id — the key that gets qualified
    and the key export patterns match against. *group_key* names the key
    holding the derived group; ``None`` means these records carry no group and
    no seeded-default filter applies to them. A missing group key is not an
    error, and no group is ever fabricated or derived from disk.
    *exportable=False* suppresses the export filter for a caller that resolves
    its own export set.

    Records keep the reader's own order within each project (D-16): the sort
    key belongs to the entity module, which applies it to the returned —
    qualified — id. A project whose reader raises ``OSError`` contributes no
    rows and one stderr line, and never fails the command (N-7).
    """
    rows: list[dict] = []
    for ref in resolve_scope(project_root, scope):
        try:
            records = read(ref.root)
        except OSError as exc:
            print(
                f'lore: project "{ref.name}" is unreadable: {exc}; skipped',
                file=sys.stderr,
            )
            continue
        if ref.relation == _SELF:
            rows.extend({**record, "origin": _SELF} for record in records)
            continue
        allowed: frozenset[str] | None = None
        if exportable and ref.relation == _ANCESTOR:
            allowed = exported_ids(
                ref.root,
                project_root,
                candidates=[
                    _as_candidate(record, id_key, group_key) for record in records
                ],
            )
        for record in records:
            entity_id = record[id_key]
            if allowed is not None and entity_id not in allowed:
                continue
            rows.append(
                {
                    **record,
                    id_key: qualify(ref.name, entity_id),
                    "origin": ref.name,
                }
            )
    return rows


# ---------------------------------------------------------------------------
# Internals
# ---------------------------------------------------------------------------


def _resolved_name(root: Path, config: Config) -> str:
    """A project's name from an already-loaded config, so nothing re-reads it."""
    return config.project_name or root.name


def _exports_to(ancestor_root: Path, descendant_root: Path, config: Config) -> bool:
    """Whether the ancestor's config offers anything to the descendant."""
    if config.shared.exports or config.shared.glossary:
        return True
    return _descendant_block(ancestor_root, descendant_root, config) is not None


def _descendant_block(
    ancestor_root: Path, descendant_root: Path, config: Config
) -> DescendantExport | None:
    """The ``[[descendants]]`` block whose ``path`` resolves to the descendant.

    Identity is the ``path`` and only the ``path``: a block's ``name`` is a
    label, and one that disagrees with its target's real name names nothing and
    breaks nothing (D-11).
    """
    target = descendant_root.resolve()
    for block in config.descendants:
        if resolve_beneath(ancestor_root, block.path) == target:
            return block
    return None


def _may_cross(ancestor_root: Path, candidate: ExportCandidate) -> bool:
    """Whether *candidate* is eligible to cross a boundary at all."""
    if candidate.group is not None and is_seeded_default(candidate.group):
        return False
    return not _is_unexportable_codex_layer(ancestor_root, candidate.path)


def _is_unexportable_codex_layer(ancestor_root: Path, path: Path | None) -> bool:
    """Whether *path* is a codex document an export never reaches (A-2).

    A transient document is deleted when its feature ships, so exporting one
    guarantees a future dangling reference in a repository its owner cannot
    see. A source is disposable raw input whose whole point is that deleting it
    dangles nothing. A path outside the codex tree is not asked the question.
    """
    if path is None:
        return False
    base = codex_dir(ancestor_root)
    if not path.is_relative_to(base):
        return False
    if is_transient_codex_path(ancestor_root, path):
        return True
    layer, _, _ = derive_group(path, base).partition("/")
    return layer == _SOURCES_LAYER


def _as_candidate(
    record: dict, id_key: str, group_key: str | None
) -> ExportCandidate:
    """Build the export candidate for one record read from an ancestor."""
    group = record.get(group_key) if group_key is not None else None
    path = record.get("path")
    return ExportCandidate(
        entity_id=record[id_key],
        group=group if isinstance(group, str) else None,
        path=path if isinstance(path, Path) else None,
    )
