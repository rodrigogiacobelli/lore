"""Graph algorithms over mission dependency sets and adjacency mappings."""

from collections import Counter, defaultdict, deque


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


MIN_CLUSTER_SIZE = 3
"""Clusters smaller than this are absorbed into the cluster they link to most."""

_MAX_SWEEPS = 100
"""Guard on the local-moving loop. Convergence is reached in single digits on
every graph measured; the guard makes the function total on a pathological one."""

_GAIN_EPSILON = 1e-12
"""Two gains within this of each other are a tie, resolved by label order."""


def partition_graph(
    adjacency: dict[str, set[str]], *, min_size: int = MIN_CLUSTER_SIZE
) -> list[list[str]]:
    """Partition an undirected graph into clusters, deterministically.

    ``adjacency`` maps every node to its neighbour set and must be symmetric:
    ``b in adjacency[a]`` iff ``a in adjacency[b]``. A node never neighbours
    itself. Returns one sorted list of node ids per cluster, the outer list
    sorted by descending size then by ascending first member. Every key of
    ``adjacency`` appears in exactly one cluster.

    A cluster smaller than ``min_size`` is absorbed into the cluster it shares
    the most edges with; one with no edge leaving it is kept whatever its size,
    so an isolated node survives as a cluster of one rather than disappearing.

    The algorithm is the local-moving phase of Louvain modularity optimisation,
    run to convergence, followed by a minimum-size absorption pass. It needs no
    seed because nothing in it is random: the sweep order is ascending degree
    then ascending id, candidate labels are scanned in sorted order and a tie
    between two of them resolves to the lexicographically smaller label, and
    every value the gain is computed from is an integer, so the only
    floating-point operation is a single division per candidate.
    """
    # 1. The sweep order. Ascending degree, then ascending id — a total order
    #    derived from the adjacency alone, so it does not depend on dict order.
    nodes = sorted(adjacency, key=lambda n: (len(adjacency[n]), n))
    label = {n: n for n in nodes}          # node -> community label
    degree = {n: len(adjacency[n]) for n in nodes}
    two_m = sum(degree.values())           # 2 * edge count, an int

    if two_m == 0:                         # no edges: every node stands alone
        return [[n] for n in nodes]

    total = Counter(degree)                # community label -> sum of degrees

    # 2. Local moving. Sweep the fixed order, moving each node to the
    #    neighbouring community with the greatest modularity gain, until a
    #    whole sweep moves nothing.
    changed, sweeps = True, 0
    while changed and sweeps < _MAX_SWEEPS:
        changed, sweeps = False, sweeps + 1
        for n in nodes:
            home = label[n]
            total[home] -= degree[n]       # lift n out of its community
            links = Counter(label[nb] for nb in adjacency[n])
            best = home
            best_gain = links[home] - total[home] * degree[n] / two_m
            for candidate in sorted(links):
                gain = links[candidate] - total[candidate] * degree[n] / two_m
                if gain > best_gain + _GAIN_EPSILON or (
                    abs(gain - best_gain) <= _GAIN_EPSILON and candidate < best
                ):
                    best, best_gain = candidate, gain
            label[n] = best
            total[best] += degree[n]
            if best != home:
                changed = True

    members: dict[str, set[str]] = defaultdict(set)
    for n, community in label.items():
        members[community].add(n)

    # 3. Minimum-size absorption. Repeatedly take the smallest under-size
    #    cluster — ties by its lowest member id — and merge it into the
    #    cluster it shares the most edges with, ties by that cluster's lowest
    #    member id. A cluster with no edge leaving it is skipped and kept.
    while True:
        absorbed = False
        under = sorted(
            (c for c, m in members.items() if len(m) < min_size),
            key=lambda c: (len(members[c]), min(members[c])),
        )
        for community in under:
            links = Counter()
            for n in members[community]:
                for nb in adjacency[n]:
                    if label[nb] != community:
                        links[label[nb]] += 1
            if not links:
                continue                    # nothing to merge into: keep it
            target = min(sorted(links), key=lambda o: (-links[o], min(members[o])))
            for n in members[community]:
                label[n] = target
            members[target] |= members[community]
            del members[community]
            absorbed = True
            break
        if not absorbed:
            break

    clusters = [sorted(m) for m in members.values()]
    clusters.sort(key=lambda m: (-len(m), m[0]))
    return clusters


def cluster_hub(members: list[str], adjacency: dict[str, set[str]]) -> str:
    """The member most linked to the rest of its own cluster; ties by id.

    Neighbours outside ``members`` do not count: the hub is the member the
    cluster itself is organised around, which is what makes it a stable key
    for an authored entry as membership shifts. An empty ``members`` raises
    ``ValueError``.
    """
    inside = set(members)
    return min(sorted(members), key=lambda n: (-len(adjacency[n] & inside), n))
