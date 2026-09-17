"""Unit tests for the codex index's document selection, edges and clusters.

Spec: codex-index-spec (``lore codex show codex-index-spec``) — Part 4, the
``_indexed_documents``, ``_adjacency`` and ``_build_clusters`` rows.

Every fixture writes real files under ``tmp_path`` through the ``tree``
fixture; the filesystem is never mocked (`technical-test-guidelines`).
"""

from __future__ import annotations

from pathlib import Path

from lore.codex import list_codex
from lore.index import _adjacency, _build_clusters, _indexed_documents

# The Part 4 fixture codex: three five-document themes joined by one edge
# apiece, plus one document with no ``related`` entry at all. The partition it
# produces is four clusters — ``alpha``, ``beta``, ``gamma`` and the isolated
# ``solo``, which is kept because it has no edge to be absorbed along (R12).
_FIXTURE_RELATED: dict[str, tuple[str, ...]] = {
    "alpha-hub": ("alpha-a", "alpha-b", "alpha-c", "alpha-d"),
    "alpha-a": ("alpha-b",),
    "alpha-b": (),
    "alpha-c": ("alpha-d",),
    "alpha-d": ("beta-d",),
    "beta-hub": ("beta-a", "beta-b", "beta-c", "beta-d"),
    "beta-a": ("beta-b",),
    "beta-b": (),
    "beta-c": ("beta-d",),
    "beta-d": ("gamma-d",),
    "gamma-hub": ("gamma-a", "gamma-b", "gamma-c", "gamma-d"),
    "gamma-a": ("gamma-b",),
    "gamma-b": (),
    "gamma-c": ("gamma-d",),
    "gamma-d": (),
    "solo": (),
}


def _write_fixture_codex(tree, project: Path) -> None:
    """Write the sixteen Part 4 fixture documents into ``project``."""
    for doc_id, related in _FIXTURE_RELATED.items():
        tree.doc(project, doc_id, related=related)


def _ids(documents: list[dict]) -> list[str]:
    return [doc["id"] for doc in documents]


# ---------------------------------------------------------------------------
# _indexed_documents — which documents the index covers
# ---------------------------------------------------------------------------


def test_only_this_projects_own_documents_are_indexed(tree):
    """ADR-028 governs a read; the render is committed, so it stays local (D5)."""
    tree.configure(tree.camelot, '[shared]\nexports = ["*"]\n')
    tree.doc(tree.camelot, "ancestor-doc")
    tree.doc(tree.lore, "own-doc")

    assert _ids(_indexed_documents(tree.lore)) == ["own-doc"]
    # The exclusion is real rather than vacuous: the merged reader does see it.
    assert "camelot:ancestor-doc" in _ids(list_codex(tree.lore))


def test_a_transient_document_is_excluded(tree):
    """`lore health` writes into this subtree on every run under two policies."""
    tree.doc(tree.lore, "canonical")
    tree.doc(tree.lore, "in-flight", group="transient")

    assert _ids(_indexed_documents(tree.lore)) == ["canonical"]


def test_a_sources_document_is_excluded(tree):
    """A source is disposable raw input (`decisions-023`)."""
    tree.doc(tree.lore, "canonical")
    tree.doc(tree.lore, "raw-input", group="sources")

    assert _ids(_indexed_documents(tree.lore)) == ["canonical"]


def test_a_nested_transient_document_is_excluded(tree):
    """The boundary is the subtree, not the immediate directory."""
    tree.doc(tree.lore, "canonical")
    tree.doc(tree.lore, "buried", group="transient/nested")

    assert _ids(_indexed_documents(tree.lore)) == ["canonical"]


def test_a_group_merely_starting_with_the_letters_source_is_included(tree):
    """The test is on the first path segment, not on a prefix of it."""
    tree.doc(tree.lore, "sourcebook-entry", group="sourcebook")

    assert _ids(_indexed_documents(tree.lore)) == ["sourcebook-entry"]


def test_a_file_with_no_frontmatter_is_skipped_rather_than_raised_on(tree):
    """A stray markdown file in the codex tree is not a document."""
    tree.doc(tree.lore, "canonical")
    tree.write(tree.lore, "codex/stray.md", "Just prose, no frontmatter.\n")

    assert _ids(_indexed_documents(tree.lore)) == ["canonical"]


def test_an_absent_codex_directory_returns_nothing(tmp_path):
    """A directory that is not a project answers the question with silence."""
    assert _indexed_documents(tmp_path) == []


# ---------------------------------------------------------------------------
# _adjacency — the undirected `related` graph over the indexed set
# ---------------------------------------------------------------------------


def test_the_adjacency_is_symmetric(tree):
    """``partition_graph``'s stated precondition (D3)."""
    tree.doc(tree.lore, "one", related=("two",))
    tree.doc(tree.lore, "two", related=("three",))
    tree.doc(tree.lore, "three")

    adjacency = _adjacency(_indexed_documents(tree.lore))

    for node, neighbours in adjacency.items():
        for neighbour in neighbours:
            assert node in adjacency[neighbour], (
                f"{node} -> {neighbour} has no matching reverse edge"
            )


def test_an_edge_to_an_excluded_transient_document_produces_no_edge(tree):
    """A document outside the indexed set is outside the graph too."""
    tree.doc(tree.lore, "canonical", related=("in-flight",))
    tree.doc(tree.lore, "in-flight", group="transient")

    adjacency = _adjacency(_indexed_documents(tree.lore))

    assert adjacency == {"canonical": set()}


def test_an_edge_to_a_document_that_does_not_exist_produces_no_edge(tree):
    """A broken `related` link is `lore health`'s business, not the index's."""
    tree.doc(tree.lore, "canonical", related=("no-such-document",))

    adjacency = _adjacency(_indexed_documents(tree.lore))

    assert adjacency == {"canonical": set()}


def test_a_self_reference_produces_no_self_loop(tree):
    """``_read_related`` keeps an id that is in the index, its own included."""
    tree.doc(tree.lore, "narcissus", related=("narcissus", "other"))
    tree.doc(tree.lore, "other")

    adjacency = _adjacency(_indexed_documents(tree.lore))

    assert adjacency["narcissus"] == {"other"}
    assert adjacency["other"] == {"narcissus"}


def test_an_inbound_only_edge_appears_in_both_directions(tree):
    """`related` is one stored, bidirectionally-traversed edge (ADR-014)."""
    tree.doc(tree.lore, "writer", related=("subject",))
    tree.doc(tree.lore, "subject")

    adjacency = _adjacency(_indexed_documents(tree.lore))

    assert adjacency == {"writer": {"subject"}, "subject": {"writer"}}


# ---------------------------------------------------------------------------
# _build_clusters — the partition, rendered
# ---------------------------------------------------------------------------


def test_each_cluster_carries_hub_members_member_paths_and_digest(tree):
    _write_fixture_codex(tree, tree.lore)

    clusters = _build_clusters(tree.lore)

    assert clusters, "the fixture codex must produce at least one cluster"
    for cluster in clusters:
        assert set(cluster) == {"hub", "members", "member_paths", "digest"}
        assert cluster["hub"] in cluster["members"]
        assert cluster["members"] == sorted(cluster["members"])
        assert len(cluster["digest"]) == 64


def test_member_paths_are_posix_relative_to_the_codex_root_and_aligned(tree):
    _write_fixture_codex(tree, tree.lore)

    clusters = _build_clusters(tree.lore)

    for cluster in clusters:
        assert len(cluster["member_paths"]) == len(cluster["members"])
        for member, path in zip(cluster["members"], cluster["member_paths"]):
            assert path == f"{member}.md"
            assert "\\" not in path


def test_a_document_in_a_group_renders_its_group_in_the_member_path(tree):
    tree.doc(tree.lore, "grouped", group="standards")

    clusters = _build_clusters(tree.lore)

    assert len(clusters) == 1
    assert clusters[0]["members"] == ["grouped"]
    assert clusters[0]["member_paths"] == ["standards/grouped.md"]


def test_clusters_arrive_in_partition_order(tree):
    """Descending size, then ascending first member — not display order (D12)."""
    _write_fixture_codex(tree, tree.lore)

    clusters = _build_clusters(tree.lore)

    assert [c["hub"] for c in clusters] == [
        "alpha-hub",
        "beta-hub",
        "gamma-hub",
        "solo",
    ]
    assert [len(c["members"]) for c in clusters] == [5, 5, 5, 1]


def test_every_indexed_document_lands_in_exactly_one_cluster(tree):
    _write_fixture_codex(tree, tree.lore)

    clusters = _build_clusters(tree.lore)

    placed = [member for cluster in clusters for member in cluster["members"]]
    assert sorted(placed) == sorted(_FIXTURE_RELATED)
    assert len(placed) == len(set(placed))
