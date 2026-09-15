"""Read-side helpers shared by every entity module serving a scoped read.

Spec: ``nested-projects-spec`` — units C1..C7.

:mod:`lore.projects` owns topology, export resolution and qualification, and
it never reads an entity file. What is left over once :func:`lore.projects.collect`
has merged the rows are two questions every entity module asks in the same
words, so they get one home here rather than seven copies (``standards-dry``):

  * **Which row does this id address?** — D-8's resolution rule: a bare id
    resolves locally first, and a qualified id never resolves locally.
  * **Where does this row live?** — the origin a row carries, turned back into
    the project root and the bare id its owner knows it by, so a ``read_*``
    function can open the file the listing found.

This module sits between :mod:`lore.projects` and the entity modules: it
imports the former and none of the latter.
"""

from __future__ import annotations

from pathlib import Path
from typing import Callable

from lore import projects


SELF = "self"
"""The reserved token for "this project".

Both a :class:`lore.projects.ProjectRef` relation and the ``origin`` a
project's own rows carry — they are the same token because they answer the
same question from the two ends.
"""

ANCESTOR = "ancestor"
"""The relation of a project above this one that exports into it."""


def select(
    records: list[dict],
    entity_id: str,
    *,
    alias: Callable[[dict], str] | None = None,
) -> dict | None:
    """Return the row *entity_id* addresses, or ``None`` for a miss.

    ``records`` is a merged listing, so a project's own rows come first and a
    bare id therefore resolves locally before an inherited one of the same
    name. A qualified id is refused a local row outright: entity ids are
    free-form enough to hold a colon, and a local document called
    ``camelot:x`` is still not the ``camelot`` project's document (D-8).

    ``alias`` names a second local address a module has always accepted —
    a knight's file stem, say, which its frontmatter ``id`` is free to
    disagree with. It is consulted only for this project's own rows and only
    once every id has missed, so nothing that resolved before this feature
    stops resolving, and a foreign entity stays reachable by qualified id
    alone.
    """
    qualified = projects.is_qualified(entity_id)
    for record in records:
        if record["id"] != entity_id:
            continue
        if qualified and record["origin"] == SELF:
            continue
        return record
    if alias is None or qualified:
        return None
    for record in records:
        if record["origin"] == SELF and alias(record) == entity_id:
            return record
    return None


def locate(project_root: Path, scope: str | None, record: dict) -> tuple[Path, str]:
    """Return the root of the project owning *record*, and its bare id.

    For the modules whose listing carries no path — doctrines, knights,
    watchers and rites — this is how a scoped ``read_*`` reaches the file:
    the row names its origin, and the origin names one project in the scope
    the row was read from. The topology is resolved again rather than cached,
    which is D-26's own trade: a cache keyed on a path would have to be
    invalidated in tests and would make SC-6's call counts order-dependent.
    """
    origin = record["origin"]
    if origin == SELF:
        return project_root, record["id"]
    # The row came out of this scope, so its origin names a ref in it.
    refs = {ref.name: ref for ref in projects.resolve_scope(project_root, scope)}
    return refs[origin].root, projects.split_qualified(record["id"])[1]
