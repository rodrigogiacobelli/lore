"""Tests for lore.graph.topological_sort_missions."""

from lore.graph import topological_sort_missions


def make_mission(mid: str) -> dict:
    return {"id": mid, "title": f"Mission {mid}"}


def make_edge(from_id: str, to_id: str) -> dict:
    """Create a dependency edge where from_id depends on to_id."""
    return {"from_id": from_id, "to_id": to_id}


class TestEmptyGraph:
    """Empty input returns empty output."""

    def test_empty_missions_empty_edges_returns_empty_list(self):
        result = topological_sort_missions([], [])
        assert result == []

    def test_empty_missions_with_edges_returns_empty_list(self):
        # Edges referencing non-existent missions are ignored
        result = topological_sort_missions([], [make_edge("m-a", "m-b")])
        assert result == []


class TestNoDependencies:
    """Missions with no edges are returned in original input order."""

    def test_single_mission_no_edges(self):
        missions = [make_mission("m-a")]
        result = topological_sort_missions(missions, [])
        assert [m["id"] for m in result] == ["m-a"]

    def test_multiple_missions_no_edges_preserves_order(self):
        missions = [make_mission("m-a"), make_mission("m-b"), make_mission("m-c")]
        result = topological_sort_missions(missions, [])
        assert [m["id"] for m in result] == ["m-a", "m-b", "m-c"]


class TestLinearChain:
    """A linear dependency chain is sorted in dependency-first order."""

    def test_two_missions_dependency_comes_first(self):
        # m-b depends on m-a (m-b "from", m-a "to")
        missions = [make_mission("m-a"), make_mission("m-b")]
        edges = [make_edge("m-b", "m-a")]
        result = topological_sort_missions(missions, edges)
        ids = [m["id"] for m in result]
        assert ids.index("m-a") < ids.index("m-b")

    def test_three_mission_chain_sorted_correctly(self):
        # m-c depends on m-b, m-b depends on m-a
        missions = [make_mission("m-a"), make_mission("m-b"), make_mission("m-c")]
        edges = [make_edge("m-b", "m-a"), make_edge("m-c", "m-b")]
        result = topological_sort_missions(missions, edges)
        ids = [m["id"] for m in result]
        assert ids == ["m-a", "m-b", "m-c"]

    def test_reversed_input_order_still_sorted_by_dependency(self):
        # Input: m-c, m-b, m-a but chain is a→b→c
        missions = [make_mission("m-c"), make_mission("m-b"), make_mission("m-a")]
        edges = [make_edge("m-b", "m-a"), make_edge("m-c", "m-b")]
        result = topological_sort_missions(missions, edges)
        ids = [m["id"] for m in result]
        assert ids.index("m-a") < ids.index("m-b")
        assert ids.index("m-b") < ids.index("m-c")


class TestDiamondDependency:
    """Diamond dependency shape: m-d depends on m-b and m-c, both depend on m-a."""

    def test_root_comes_before_middle_nodes(self):
        missions = [
            make_mission("m-a"),
            make_mission("m-b"),
            make_mission("m-c"),
            make_mission("m-d"),
        ]
        edges = [
            make_edge("m-b", "m-a"),
            make_edge("m-c", "m-a"),
            make_edge("m-d", "m-b"),
            make_edge("m-d", "m-c"),
        ]
        result = topological_sort_missions(missions, edges)
        ids = [m["id"] for m in result]
        assert ids.index("m-a") < ids.index("m-b")
        assert ids.index("m-a") < ids.index("m-c")
        assert ids.index("m-b") < ids.index("m-d")
        assert ids.index("m-c") < ids.index("m-d")


class TestCircularDependency:
    """Circular dependencies are handled gracefully — no exception raised."""

    def test_two_node_cycle_returns_all_missions(self):
        # m-a depends on m-b, m-b depends on m-a (cycle)
        missions = [make_mission("m-a"), make_mission("m-b")]
        edges = [make_edge("m-a", "m-b"), make_edge("m-b", "m-a")]
        result = topological_sort_missions(missions, edges)
        # All missions should be present (cycle safety appends unvisited)
        assert len(result) == 2
        assert {m["id"] for m in result} == {"m-a", "m-b"}

    def test_three_node_cycle_returns_all_missions(self):
        missions = [make_mission("m-a"), make_mission("m-b"), make_mission("m-c")]
        edges = [
            make_edge("m-a", "m-b"),
            make_edge("m-b", "m-c"),
            make_edge("m-c", "m-a"),
        ]
        result = topological_sort_missions(missions, edges)
        assert len(result) == 3
        assert {m["id"] for m in result} == {"m-a", "m-b", "m-c"}

    def test_cycle_does_not_raise_exception(self):
        missions = [make_mission("m-x"), make_mission("m-y")]
        edges = [make_edge("m-x", "m-y"), make_edge("m-y", "m-x")]
        # Must not raise
        result = topological_sort_missions(missions, edges)
        assert isinstance(result, list)


class TestEdgesOutsideQuestIgnored:
    """Edges referencing missions not in the input list are silently ignored."""

    def test_external_edge_ignored(self):
        missions = [make_mission("m-a"), make_mission("m-b")]
        # Edge referencing m-z which is not in missions list
        edges = [make_edge("m-b", "m-z")]
        result = topological_sort_missions(missions, edges)
        # Both missions are returned, external edge has no effect
        assert len(result) == 2
        assert {m["id"] for m in result} == {"m-a", "m-b"}

    def test_all_external_edges_ignored(self):
        missions = [make_mission("m-a")]
        edges = [make_edge("m-x", "m-y"), make_edge("m-z", "m-a")]
        result = topological_sort_missions(missions, edges)
        assert len(result) == 1
        assert result[0]["id"] == "m-a"


class TestReturnsSameMissionDicts:
    """The returned list contains the same dict objects, not copies."""

    def test_identity_preserved(self):
        m_a = make_mission("m-a")
        m_b = make_mission("m-b")
        missions = [m_a, m_b]
        edges = [make_edge("m-b", "m-a")]
        result = topological_sort_missions(missions, edges)
        # Check object identity
        assert result[0] is m_a
        assert result[1] is m_b
