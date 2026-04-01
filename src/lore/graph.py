"""Graph algorithms on mission dependency sets."""

from collections import deque


def topological_sort_missions(
    missions: list[dict],
    edges: list[dict],
) -> list[dict]:
    """Sort missions into topological order based on dependency edges.

    Uses Kahn's algorithm. Original input order is used as a tiebreaker for
    missions at the same topological level.

    The caller is responsible for filtering edges to intra-quest pairs only
    before calling this function.

    If a cycle is detected (not all missions visited after the BFS completes),
    the unvisited missions are appended in their original input order without
    raising an exception.

    Args:
        missions: List of mission dicts, each with at minimum an ``"id"`` key.
        edges: List of dependency edge dicts, each with ``"from_id"`` (the
            dependent mission) and ``"to_id"`` (the dependency) keys.

    Returns:
        The same mission dicts reordered so that a mission's dependencies
        appear before it in the list.
    """
    mission_ids = {m["id"] for m in missions}

    # Build in_degree and children_of for Kahn's algorithm
    in_degree = {m["id"]: 0 for m in missions}
    children_of: dict[str, list[str]] = {}  # parent_id -> [child_id]

    for edge in edges:
        parent = edge["to_id"]
        child = edge["from_id"]
        if parent in mission_ids and child in mission_ids:
            in_degree[child] += 1
            children_of.setdefault(parent, []).append(child)

    # Seed queue with missions that have no intra-quest parents (in original order)
    queue = deque(m["id"] for m in missions if in_degree[m["id"]] == 0)
    mission_map = {m["id"]: m for m in missions}
    # Track original index for stable ordering within same topological level
    original_index = {m["id"]: i for i, m in enumerate(missions)}

    sorted_missions: list[dict] = []
    visited: set[str] = set()
    while queue:
        mid = queue.popleft()
        if mid in visited:
            continue
        visited.add(mid)
        sorted_missions.append(mission_map[mid])
        # Push children whose in-degree reaches 0, sorted by original index
        children = children_of.get(mid, [])
        ready_children = []
        for child_id in children:
            in_degree[child_id] -= 1
            if in_degree[child_id] == 0:
                ready_children.append(child_id)
        ready_children.sort(key=lambda cid: original_index.get(cid, 0))
        queue.extend(ready_children)

    # Cycle safety: append any unvisited missions in original order
    for m in missions:
        if m["id"] not in visited:
            sorted_missions.append(m)

    return sorted_missions
