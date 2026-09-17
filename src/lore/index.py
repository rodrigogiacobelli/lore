"""The codex index — one job: route a cold read into the codex by cluster.

A codex is a graph of documents joined by ``related``. This module partitions
that graph into clusters of densely linked documents, names each cluster's hub,
and answers a keyword with the clusters it lives in, so an agent opening a
codex cold starts at a named group of documents instead of at the whole corpus.

Two files, both under ``.lore/index/`` and both reached through ``paths``:

``authored.yaml``
    Committed, hand-written, one entry per cluster keyed by that cluster's hub.
    **Nothing here writes it.** It is the only file in the feature a rebuild
    cannot recover, and repair is an authoring act performed by the
    ``update-index`` skill or by a person.
``codex.json``
    Generated, git-ignored, a pure cache. Deleting it loses nothing: the next
    command rebuilds it. It is a function of the codex alone and carries no
    slug, name, summary or status, so two projects with identical codexes and
    different authoring render identically.

The render is refreshed before a search whenever a stat-level fingerprint of
the codex has moved, and written whole through ``safewrite`` so a concurrent
reader sees the old file or the new one and never half of either.

Nothing here prints, and nothing here reaches the surface above it: every rule
a Python caller would otherwise have to reimplement lives in this module and
not in the command that wraps it.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import yaml

from lore import codex as _codex
from lore import graph as _graph
from lore import paths as _paths
from lore import projects as _projects
from lore import safewrite as _safewrite
from lore.schemas import SchemaIssue, SchemaValidationError, validate_entity_file

_RENDER_VERSION = 1
"""The render's own schema version. A payload carrying any other value is a
render this Lore does not understand, and is treated as absent."""

_AUTHORED_KIND = "index-authored"
"""The packaged schema kind for the authored file, in raise-mode."""

_NOT_AUTHORED_MESSAGE = (
    "no index authored for this project. Run the update-index skill to author it."
)
"""R8's refusal, composed once here so one failure carries one wording wherever
a caller meets it."""

_STATUS_RANK = {"ok": 0, "unauthored": 1, "drifted": 2}
"""Display order for the build table: what is fine, what is missing, what moved."""


class CodexIndexError(ValueError):
    """The authored index file is present but cannot be used.

    ``issues`` carries the schema failures behind the message when the file
    reached a shape a rule could apply to, so ``lore health`` reports one row
    per failure with its rule and pointer rather than validating the file a
    second time. A parser failure carries the one issue that describes it.
    """

    def __init__(
        self, message: str, issues: list[SchemaIssue] | None = None
    ) -> None:
        super().__init__(message)
        self.issues = issues or []


class CodexIndexNotAuthoredError(CodexIndexError):
    """No authored index file exists for this project."""


def _authored_label(project_root: Path) -> str:
    """The authored file's path as a message names it, relative to the project."""
    path = _paths.index_authored_path(project_root)
    return path.relative_to(project_root).as_posix()


# ---------------------------------------------------------------------------
# What the index covers, and how its documents are joined
# ---------------------------------------------------------------------------


def _indexed_documents(project_root: Path) -> list[dict]:
    """This project's own canonical codex records, by ascending id.

    Local rather than merged: the render carries a path relative to *this*
    codex root, an ancestor's document has no such path, and an ancestor
    editing its export set must not drift entries in a project whose own files
    nobody touched.

    ``transient/`` and ``sources/`` are dropped through the one predicate that
    already answers "is this document in a layer a governance surface never
    reaches". ``lore health`` writes into the transient subtree on every run
    under two of the three retention policies, so indexing it would let the
    index invalidate itself on a schedule an unrelated command sets.
    """
    return [
        document
        for document in _codex._list_codex_local(project_root)
        if not _projects._is_unexportable_codex_layer(project_root, document["path"])
    ]


def _adjacency(documents: list[dict]) -> dict[str, set[str]]:
    """The undirected ``related`` graph over ``documents``, without self-loops.

    ``related`` is the one stored, bidirectionally-traversed codex-to-codex
    edge, and the reader that turns it into edges is not copied here. Both
    directions are unioned because the stable side owns the link, so which end
    of a pair stores it says nothing about the pair. The self-discard is
    required rather than defensive: a document listing its own id in
    ``related`` reaches the outbound and the inbound map alike, and
    ``partition_graph``'s stated precondition is that a node never neighbours
    itself.
    """
    index = {document["id"]: document for document in documents}
    outbound, inbound = _codex._build_adjacency(index, documents)
    return {
        doc_id: (outbound[doc_id] | inbound[doc_id]) - {doc_id} for doc_id in index
    }


# ---------------------------------------------------------------------------
# The two hashes
# ---------------------------------------------------------------------------


def _document_digest(path: Path) -> str:
    """The sha256 of one document's bytes."""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _cluster_digest(members: list[str], paths: dict[str, Path]) -> str:
    """A hash of a cluster's membership and of its members' content.

    Scoped to the cluster, so a document changing elsewhere in the codex cannot
    move it — the precision a drift warning needs to be worth reading. It
    covers what the members are and what they say, and nothing else: a member
    whose file moves without changing refreshes the render and leaves the
    summary alone, which is correct, because the summary describes what the
    documents say rather than where they sit.
    """
    lines = "".join(
        f"{member}\t{_document_digest(paths[member])}\n" for member in sorted(members)
    )
    return hashlib.sha256(lines.encode("utf-8")).hexdigest()


def _codex_fingerprint(project_root: Path) -> str:
    """A hash of every indexed file's path, size and mtime — stats, no reads.

    The question this answers is "has anything at all changed since the
    render", and it has to be cheap enough that a search never has to decide
    whether to rebuild first. One ``stat`` per document and no file read buys
    that; hashing content would cost the search the very rebuild the
    fingerprint exists to skip.

    A false positive — a checkout rewriting mtimes — costs one rebuild and then
    the fast path returns. A false negative needs an edit of identical byte
    length landing in the same nanosecond, and ``lore index build`` is the
    unconditional rebuild that answers it.
    """
    codex_root = _paths.entity_location(project_root, "codex")
    stamped: list[tuple[str, str]] = []
    for filepath in codex_root.rglob("*.md"):
        if _projects._is_unexportable_codex_layer(project_root, filepath):
            continue
        stats = filepath.stat()
        relative = filepath.relative_to(codex_root).as_posix()
        stamped.append((relative, f"{relative}\t{stats.st_size}\t{stats.st_mtime_ns}\n"))
    lines = "".join(line for _, line in sorted(stamped))
    return hashlib.sha256(lines.encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# The partition, rendered
# ---------------------------------------------------------------------------


def _build_clusters(project_root: Path) -> list[dict]:
    """Partition the codex and describe each cluster, in partition order.

    Each cluster carries its hub, its members by ascending id, each member's
    path relative to the codex root so a caller opens a document without
    resolving its id, and the digest its summary is authored against.
    """
    documents = _indexed_documents(project_root)
    adjacency = _adjacency(documents)
    codex_root = _paths.entity_location(project_root, "codex")
    paths = {document["id"]: document["path"] for document in documents}
    return [
        {
            "hub": _graph.cluster_hub(members, adjacency),
            "members": members,
            "member_paths": [
                paths[member].relative_to(codex_root).as_posix() for member in members
            ],
            "digest": _cluster_digest(members, paths),
        }
        for members in _graph.partition_graph(adjacency)
    ]


def _render_payload(project_root: Path) -> dict:
    """The whole render: version, fingerprint, and the clusters as partitioned.

    The fingerprint is taken before the partition, so a document edited while
    the build runs leaves a fingerprint the next search will disagree with
    rather than one it will trust.
    """
    return {
        "version": _RENDER_VERSION,
        "codex_fingerprint": _codex_fingerprint(project_root),
        "clusters": _build_clusters(project_root),
    }


def _write_render(project_root: Path, payload: dict) -> None:
    """Write the render whole, through the gate every Lore write passes."""
    _safewrite.atomic_write_text(
        _paths.index_rendered_path(project_root),
        json.dumps(payload, indent=2, sort_keys=False, ensure_ascii=False) + "\n",
        project_root=project_root,
    )


def _load_render(project_root: Path) -> dict | None:
    """The stored render, or ``None`` when there is no usable one.

    Absent, unreadable, unparseable, of another version or structurally
    incomplete all answer the same way, because the render is a cache and a
    cache that can fail a command is not a cache.
    """
    try:
        payload = json.loads(
            _paths.index_rendered_path(project_root).read_text(encoding="utf-8")
        )
    except (OSError, ValueError):
        return None
    if not isinstance(payload, dict):
        return None
    if payload.get("version") != _RENDER_VERSION:
        return None
    if not isinstance(payload.get("codex_fingerprint"), str):
        return None
    if not isinstance(payload.get("clusters"), list):
        return None
    return payload


def _current_render(project_root: Path) -> dict | None:
    """The stored render when it still describes the codex; ``None`` otherwise."""
    payload = _load_render(project_root)
    if payload is None:
        return None
    if payload["codex_fingerprint"] != _codex_fingerprint(project_root):
        return None
    return payload


def _refresh(project_root: Path) -> dict:
    """The render as it should be now, rebuilt and rewritten only if it moved.

    Two processes refreshing at once is acceptable: each writes the same bytes
    and the write is atomic, so a reader sees one whole file either way.
    """
    payload = _current_render(project_root)
    if payload is not None:
        return payload
    payload = _render_payload(project_root)
    _write_render(project_root, payload)
    return payload


def _current_clusters(project_root: Path) -> list[dict]:
    """The clusters as they are now, computing them in memory if need be.

    The read-only half of :func:`_refresh`, for the audit: same fast path, no
    write, so a health run leaves no file behind that nobody asked for.
    """
    payload = _current_render(project_root)
    if payload is not None:
        return payload["clusters"]
    return _build_clusters(project_root)


# ---------------------------------------------------------------------------
# The authored half, and what it says about the clusters
# ---------------------------------------------------------------------------


def _load_authored(project_root: Path) -> dict[str, dict]:
    """The authored entries, keyed by hub.

    Raises :class:`CodexIndexNotAuthoredError` when the file does not exist and
    :class:`CodexIndexError` when it exists and cannot be used. A mapping keyed
    by hub makes "one entry per cluster" structural rather than a convention,
    and makes a duplicate hub unrepresentable rather than a check.
    """
    path = _paths.index_authored_path(project_root)
    if not path.exists():
        raise CodexIndexNotAuthoredError(_NOT_AUTHORED_MESSAGE)
    try:
        validate_entity_file(str(path), _AUTHORED_KIND)
    except SchemaValidationError as exc:
        issues = exc.issues or [
            SchemaIssue(rule="yaml-parse", pointer="/", message=str(exc))
        ]
        raise CodexIndexError(
            f"{_authored_label(project_root)}: {exc}", issues
        ) from exc
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    return data["entries"]


def _from_entry(entry: dict | None, field: str) -> str | None:
    """One field of an authored entry, or ``None`` when the cluster has none."""
    return None if entry is None else entry[field]


def _cluster_status(cluster: dict, entry: dict | None) -> str:
    """Whether a cluster is ``ok``, ``drifted`` or ``unauthored``.

    A cluster whose hub has an entry carrying the cluster's current digest is
    ``ok``; one whose entry was authored against another digest is ``drifted``,
    because the summary describes documents that have since changed; one with
    no entry at all is ``unauthored``.
    """
    if entry is None:
        return "unauthored"
    if entry["authored_against"] == cluster["digest"]:
        return "ok"
    return "drifted"


def _cluster_rows(clusters: list[dict], entries: dict[str, dict]) -> list[dict]:
    """One row per cluster, in display order: status, then size, then hub."""
    rows = [
        {
            "slug": _from_entry(entries.get(cluster["hub"]), "slug"),
            "name": _from_entry(entries.get(cluster["hub"]), "name"),
            "hub": cluster["hub"],
            "status": _cluster_status(cluster, entries.get(cluster["hub"])),
            "members": cluster["members"],
            "member_paths": cluster["member_paths"],
        }
        for cluster in clusters
    ]
    rows.sort(
        key=lambda row: (
            _STATUS_RANK[row["status"]],
            -len(row["members"]),
            row["hub"],
        )
    )
    return rows


def _stale_rows(clusters: list[dict], entries: dict[str, dict]) -> list[dict]:
    """One row per entry the partition has left behind, by ascending slug.

    Nothing is re-keyed: attaching a hand-written summary to a set of documents
    nobody has checked is the failure the drift status exists to prevent, so an
    orphaned entry is reported instead. The two reasons carry different
    severities downstream because a hub that is still a document in this codex
    is a codex edit needing a re-read, while one that is not is a deleted
    document needing a decision.
    """
    indexed = {member for cluster in clusters for member in cluster["members"]}
    hubs = {cluster["hub"] for cluster in clusters}
    return sorted(
        (
            {
                "slug": entry["slug"],
                "hub": hub,
                "reason": "hub_not_a_hub" if hub in indexed else "hub_not_found",
            }
            for hub, entry in entries.items()
            if hub not in hubs
        ),
        key=lambda row: row["slug"],
    )


def _classify(clusters: list[dict], entries: dict[str, dict]) -> dict:
    """Judge every cluster against the authored file, and every entry against
    the partition.

    The one classification the build table and the health audit both render, so
    there is no second rule to keep in step.
    """
    rows = _cluster_rows(clusters, entries)
    statuses = [row["status"] for row in rows]
    return {
        "clusters": rows,
        "unauthored": statuses.count("unauthored"),
        "drifted": statuses.count("drifted"),
        "stale": _stale_rows(clusters, entries),
    }


def _matches(needle: str, cluster: dict, entry: dict | None) -> bool:
    """Whether a casefolded keyword occurs in anything this cluster is findable by.

    The member ids always, and an authored cluster's name and summary as well.
    The slug is deliberately absent: it is the display key of a row, and no
    command resolves a cluster by it, so matching on it would return a cluster
    for a word that appears nowhere a reader can see.
    """
    haystack = list(cluster["members"])
    if entry is not None:
        haystack += [entry["name"], entry["summary"]]
    return any(needle in field.casefold() for field in haystack)


# ---------------------------------------------------------------------------
# The two callables
# ---------------------------------------------------------------------------


def build_index(project_root: Path) -> dict:
    """Re-partition the codex, write the render, and report what needs writing.

    The unconditional rebuild: it never consults the stored render and never
    reads the authored file to compute one, so the render stays a pure function
    of the codex. A missing authored file is a valid state, reported as every
    cluster ``unauthored`` rather than as a failure — a cluster needing
    attention is a state to report, not an error.

    Raises :class:`CodexIndexError` when the authored file exists and is
    unparseable or fails its schema, and ``ValueError`` from the write gate
    when the render path is a link, escapes the project root, or cannot be
    written.
    """
    payload = _render_payload(project_root)
    _write_render(project_root, payload)
    try:
        entries = _load_authored(project_root)
    except CodexIndexNotAuthoredError:
        entries = {}
    return _classify(payload["clusters"], entries)


def search_index(project_root: Path, keyword: str) -> list[dict]:
    """The clusters a keyword lives in, refreshing the render first if it moved.

    Matching is a case-insensitive substring of ``keyword`` against a cluster's
    name, its summary and each of its member ids. An unauthored cluster has no
    name or summary and matches on member ids alone: once one entry exists,
    hiding the clusters nobody has written up yet would leave documents the
    index knows about unreachable through the command whose job is reaching
    them. A slug is not searched — it is the display key of a row, and no
    command resolves a cluster by it.

    Authored clusters come first by ascending slug, then unauthored ones by
    ascending hub. No match is an empty list, which is an answer rather than a
    failure.

    Raises :class:`CodexIndexNotAuthoredError` when no authored file exists,
    and :class:`CodexIndexError` on the failures ``build_index`` names.
    """
    entries = _load_authored(project_root)
    needle = keyword.casefold()
    authored: list[dict] = []
    unauthored: list[dict] = []
    for cluster in _refresh(project_root)["clusters"]:
        entry = entries.get(cluster["hub"])
        if not _matches(needle, cluster, entry):
            continue
        row = {
            "slug": _from_entry(entry, "slug"),
            "name": _from_entry(entry, "name"),
            "summary": _from_entry(entry, "summary"),
            "hub": cluster["hub"],
            "members": cluster["members"],
            "member_paths": cluster["member_paths"],
        }
        if entry is None:
            unauthored.append(row)
        else:
            authored.append(row)
    authored.sort(key=lambda row: row["slug"])
    unauthored.sort(key=lambda row: row["hub"])
    return authored + unauthored
