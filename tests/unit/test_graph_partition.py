"""Unit tests for lore.graph.partition_graph and lore.graph.cluster_hub.

Spec: codex-index-spec (lore codex show codex-index-spec) — Part 2 "The
Partition Algorithm", the two Part 4 unit rows, Part 5 unit F1.

Both functions are pure graph algorithms over a symmetric adjacency mapping:
no file, no path, no codex record. Determinism is the first property asserted
here rather than a comment in the module — the partition has no seed because
every intermediate value is an integer, so a shuffled insertion order has to
produce a byte-equal answer.
"""

from __future__ import annotations

import pytest

from lore.graph import MIN_CLUSTER_SIZE, cluster_hub, partition_graph

# ---------------------------------------------------------------------------
# Graph builders. Every graph here is hand-built and symmetric: ``b`` is in
# ``adjacency[a]`` exactly when ``a`` is in ``adjacency[b]``, and no node
# neighbours itself, which is ``partition_graph``'s stated precondition.
# ---------------------------------------------------------------------------


def _symmetric(
    edges: list[tuple[str, str]], isolated: tuple[str, ...] = ()
) -> dict[str, set[str]]:
    """Build a symmetric adjacency mapping from an edge list."""
    adjacency: dict[str, set[str]] = {node: set() for node in isolated}
    for left, right in edges:
        adjacency.setdefault(left, set()).add(right)
        adjacency.setdefault(right, set()).add(left)
    return adjacency


def _clique(*members: str) -> list[tuple[str, str]]:
    """Every unordered pair of *members*, so the nodes form a complete graph."""
    return [
        (left, right)
        for index, left in enumerate(members)
        for right in members[index + 1 :]
    ]


def _bridged_triangles() -> dict[str, set[str]]:
    """Two triangles joined through one node that is equidistant from both.

    The graph is invariant under swapping the ``a`` half with the ``z`` half,
    so nothing in the input distinguishes the two sides and only the label
    tie-break can decide where ``m`` lands.
    """
    return _symmetric(
        _clique("a1", "a2", "a3")
        + _clique("z1", "z2", "z3")
        + [("a1", "m"), ("z1", "m")]
    )


def _clique_with_a_dangling_pair() -> dict[str, set[str]]:
    """Six nodes in a clique, plus a two-node cluster attached by one edge."""
    return _symmetric(
        _clique("c1", "c2", "c3", "c4", "c5", "c6") + [("a", "c1"), ("a", "b")]
    )


def _mixed_graph() -> dict[str, set[str]]:
    """Several shapes at once: two cliques, a bridge, a chain and an isolate."""
    return _symmetric(
        _clique("alpha-a", "alpha-b", "alpha-c", "alpha-d")
        + _clique("beta-a", "beta-b", "beta-c")
        + _clique("gamma-a", "gamma-b", "gamma-c")
        + [("alpha-a", "beta-a"), ("beta-c", "gamma-a")],
        isolated=("solo",),
    )


def _reorderings(adjacency: dict[str, set[str]]) -> list[dict[str, set[str]]]:
    """The same mapping under several deterministic insertion orders."""
    keys = list(adjacency)
    half = len(keys) // 2
    orders = [
        list(reversed(keys)),
        sorted(keys),
        sorted(keys, reverse=True),
        sorted(keys, key=lambda key: (len(key), key[::-1])),
        keys[half:] + keys[:half],
    ]
    return [{key: adjacency[key] for key in order} for order in orders]


# ---------------------------------------------------------------------------
# Determinism — the first test, not a comment (Part 2).
# ---------------------------------------------------------------------------


def test_shuffling_the_insertion_order_leaves_the_partition_identical():
    adjacency = _mixed_graph()
    expected = partition_graph(adjacency)

    for reordered in _reorderings(adjacency):
        assert partition_graph(reordered) == expected


def test_the_same_input_partitions_identically_on_every_run():
    adjacency = _mixed_graph()

    results = [partition_graph(adjacency) for _ in range(5)]

    assert results == [results[0]] * 5


# ---------------------------------------------------------------------------
# partition_graph — shape of the answer.
# ---------------------------------------------------------------------------


def test_an_empty_adjacency_returns_no_clusters():
    assert partition_graph({}) == []


def test_a_graph_with_no_edges_returns_one_singleton_per_node():
    adjacency: dict[str, set[str]] = {"c": set(), "a": set(), "b": set()}

    assert partition_graph(adjacency) == [["a"], ["b"], ["c"]]


def test_two_disjoint_triangles_return_two_clusters_of_three():
    adjacency = _symmetric(_clique("a", "b", "c") + _clique("d", "e", "f"))

    assert partition_graph(adjacency) == [["a", "b", "c"], ["d", "e", "f"]]


def test_a_complete_graph_of_six_is_one_cluster():
    adjacency = _symmetric(_clique("a", "b", "c", "d", "e", "f"))

    assert partition_graph(adjacency) == [["a", "b", "c", "d", "e", "f"]]


def test_two_cliques_joined_by_one_edge_stay_two_clusters():
    adjacency = _symmetric(
        _clique("c1", "c2", "c3", "c4", "c5")
        + _clique("d1", "d2", "d3", "d4", "d5")
        + [("c1", "d1")]
    )

    assert partition_graph(adjacency) == [
        ["c1", "c2", "c3", "c4", "c5"],
        ["d1", "d2", "d3", "d4", "d5"],
    ]


def test_every_input_key_appears_in_exactly_one_cluster():
    adjacency = _mixed_graph()

    clusters = partition_graph(adjacency)

    placed = [node for cluster in clusters for node in cluster]
    assert sorted(placed) == sorted(adjacency)
    assert len(placed) == len(set(placed))


# ---------------------------------------------------------------------------
# partition_graph — minimum-size absorption (R12, D7).
# ---------------------------------------------------------------------------


def test_the_minimum_cluster_size_is_three():
    assert MIN_CLUSTER_SIZE == 3


def test_an_undersized_cluster_is_absorbed_into_the_cluster_it_links_to_most():
    adjacency = _clique_with_a_dangling_pair()

    assert partition_graph(adjacency) == [
        ["a", "b", "c1", "c2", "c3", "c4", "c5", "c6"]
    ]


def test_min_size_one_absorbs_nothing():
    adjacency = _clique_with_a_dangling_pair()

    assert partition_graph(adjacency, min_size=1) == [
        ["c1", "c2", "c3", "c4", "c5", "c6"],
        ["a", "b"],
    ]


def test_the_default_min_size_is_the_module_constant():
    adjacency = _clique_with_a_dangling_pair()

    assert partition_graph(adjacency) == partition_graph(
        adjacency, min_size=MIN_CLUSTER_SIZE
    )


def test_a_node_with_no_edges_survives_as_a_cluster_of_one():
    # It has no edge to be absorbed along, so keeping it is what stops an
    # indexed document from being dropped from the index entirely (R12).
    adjacency = _symmetric(_clique("a", "b", "c"), isolated=("z",))

    assert partition_graph(adjacency) == [["a", "b", "c"], ["z"]]


# ---------------------------------------------------------------------------
# partition_graph — ordering and tie-breaking.
# ---------------------------------------------------------------------------


def test_clusters_are_ordered_by_descending_size_then_ascending_first_member():
    # The larger cluster's ids sort last, so only size can put it first.
    adjacency = _symmetric(
        _clique("a1", "a2", "a3") + _clique("z1", "z2", "z3", "z4")
    )

    assert partition_graph(adjacency) == [
        ["z1", "z2", "z3", "z4"],
        ["a1", "a2", "a3"],
    ]


def test_equal_sized_clusters_are_ordered_by_ascending_first_member():
    adjacency = _symmetric(_clique("d", "e", "f") + _clique("a", "b", "c"))

    assert partition_graph(adjacency) == [["a", "b", "c"], ["d", "e", "f"]]


def test_members_within_a_cluster_are_sorted_by_ascending_id():
    adjacency = _symmetric(_clique("c", "b", "a"))

    assert partition_graph(adjacency) == [["a", "b", "c"]]


def test_a_tie_between_two_candidate_labels_resolves_to_the_smaller_label():
    # ``m`` is attached to both triangles by exactly one edge and the graph is
    # symmetric under swapping the halves, so the only thing that can decide
    # where it lands is the tie-break on the candidate label.
    adjacency = _bridged_triangles()

    assert partition_graph(adjacency) == [
        ["a1", "a2", "a3", "m"],
        ["z1", "z2", "z3"],
    ]


# ---------------------------------------------------------------------------
# cluster_hub (D8, R2).
# ---------------------------------------------------------------------------


def test_a_star_returns_its_centre():
    adjacency = _symmetric([("hub", "leaf-a"), ("hub", "leaf-b"), ("hub", "leaf-c")])

    assert cluster_hub(["hub", "leaf-a", "leaf-b", "leaf-c"], adjacency) == "hub"


def test_a_tie_on_intra_cluster_degree_returns_the_smallest_id():
    adjacency = _symmetric([("a", "b")])

    assert cluster_hub(["a", "b"], adjacency) == "a"


def test_neighbours_outside_the_cluster_do_not_count():
    # "a" has four neighbours and one of them inside; "b" has two inside and
    # sorts later, so it can only win on intra-cluster degree.
    adjacency = _symmetric(
        [("a", "b"), ("a", "x"), ("a", "y"), ("a", "z"), ("b", "c")]
    )

    assert cluster_hub(["a", "b", "c"], adjacency) == "b"


def test_a_single_member_cluster_returns_that_member():
    adjacency: dict[str, set[str]] = {"solo": set()}

    assert cluster_hub(["solo"], adjacency) == "solo"


def test_an_empty_members_list_raises_value_error():
    with pytest.raises(ValueError):
        cluster_hub([], {})
