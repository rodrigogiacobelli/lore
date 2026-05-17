"""Codex scanning and document listing."""

import collections
import random as _random
from pathlib import Path

from lore import frontmatter
from lore import paths as _paths


class ConflictingDepthFlags(ValueError):
    """Raised when callers combine symmetric `depth` with directional flags."""


def scan_codex(codex_dir: Path, filter_groups: list[str] | None = None) -> list[dict]:
    """Walk codex_dir recursively, parse frontmatter, return document records.

    Returns a list of dicts with keys: id, title, summary, path.
    Files without valid frontmatter or missing required fields are skipped.
    Results are sorted alphabetically by id.

    If filter_groups is a non-empty list, only documents whose group is in
    filter_groups or whose group is root-level (empty string) are returned.
    If filter_groups is None or an empty list, all documents are returned.
    """
    if not codex_dir.exists():
        return []

    results = []
    for filepath in codex_dir.rglob("*.md"):
        record = frontmatter.parse_frontmatter_doc(filepath, required_fields=("id", "title", "summary"))
        if record is not None:
            results.append(record)

    if filter_groups:
        results = [
            d for d in results
            if _paths.group_matches_filter(_paths.derive_group(d["path"], codex_dir), filter_groups)
        ]

    return sorted(results, key=lambda d: d["id"])


def search_documents(codex_dir: Path, keyword: str) -> list[dict]:
    """Return documents whose title or summary contains the keyword (case-insensitive).

    Returns a list of dicts with keys: id, title, summary (no path).
    Results are sorted alphabetically by id.
    """
    docs = scan_codex(codex_dir)
    kw = keyword.lower()
    results = []
    for doc in docs:
        title_match = kw in doc["title"].lower()
        summary_match = kw in doc["summary"].lower()
        if title_match or summary_match:
            results.append({
                "id": doc["id"],
                "title": doc["title"],
                "summary": doc["summary"],
            })
    return results


def read_document(codex_dir: Path, doc_id: str) -> dict | None:
    """Return a full document record for the given ID, or None if not found.

    The returned dict has keys: id, title, summary, body.
    The body is the content below the YAML frontmatter block, with leading
    newlines stripped.
    """
    docs = scan_codex(codex_dir)
    for doc in docs:
        if doc["id"] == doc_id:
            filepath = doc["path"]
            record = frontmatter.parse_frontmatter_doc_full(filepath, required_fields=("id", "title", "summary"))
            if record is None:
                return None
            return {
                "id": record["id"],
                "title": record["title"],
                "summary": record["summary"],
                "body": record["body"],
            }
    return None


def _read_related(filepath: Path, index: dict) -> list[str]:
    """Return sorted list of related IDs present in the index.

    Reads the ``related`` field from the document frontmatter at ``filepath``,
    filters to only IDs present in ``index``, casts non-string entries to str,
    strips whitespace, drops null entries, and returns a sorted list for
    determinism.
    """
    record = frontmatter.parse_frontmatter_doc(filepath, extra_fields=("related",))
    if record is None:
        return []

    raw = record.get("related")
    if not raw:
        return []

    result = []
    for entry in raw:
        if entry is None:
            continue
        candidate = str(entry).strip()
        if candidate in index:
            result.append(candidate)

    return sorted(result)


def _build_adjacency(
    index: dict[str, dict],
    docs: list[dict],
) -> tuple[dict[str, set[str]], dict[str, set[str]]]:
    """Build outbound/inbound adjacency maps from related links.

    Iterates ``docs`` once, calling ``_read_related`` per doc. Both result
    dicts are initialised with empty sets for every key in ``index``.
    """
    outbound: dict[str, set[str]] = {doc_id: set() for doc_id in index}
    inbound: dict[str, set[str]] = {doc_id: set() for doc_id in index}
    for doc in docs:
        neighbours = _read_related(doc["path"], index)
        for neighbour_id in neighbours:
            outbound[doc["id"]].add(neighbour_id)
            inbound[neighbour_id].add(doc["id"])
    return outbound, inbound


def _bfs_neighbour_ids(
    start_id: str,
    outbound: dict[str, set[str]],
    inbound: dict[str, set[str]],
    depth_out: int,
    depth_in: int,
) -> list[str]:
    """BFS from start_id honouring separate outbound/inbound depth budgets.

    Returns the sorted list of discovered ids excluding the seed. Each id
    appears at most once (visited-set dedupe across both directions).
    """
    visited: set[str] = {start_id}
    queue: collections.deque = collections.deque([(start_id, 0, 0)])
    result_ids: list[str] = []
    while queue:
        doc_id, out_used, in_used = queue.popleft()
        if doc_id != start_id:
            result_ids.append(doc_id)
        if out_used < depth_out:
            for nb in outbound[doc_id]:
                if nb not in visited:
                    visited.add(nb)
                    queue.append((nb, out_used + 1, in_used))
        if in_used < depth_in:
            for nb in inbound[doc_id]:
                if nb not in visited:
                    visited.add(nb)
                    queue.append((nb, out_used, in_used + 1))
    result_ids.sort()
    return result_ids


def _build_neighbour_record(
    meta: dict,
    codex_dir: Path,
    *,
    full: bool,
) -> dict | None:
    """Build a single map_documents result record for one neighbour id.

    In default mode returns {id, group, title, summary} from index metadata.
    In full mode re-parses the file to attach related + body. Returns None
    only in full mode when the file fails to re-parse (caller skips it).
    """
    group = _paths.derive_group(meta["path"], codex_dir)
    if not full:
        return {
            "id": meta["id"],
            "title": meta["title"],
            "summary": meta["summary"],
            "group": group,
        }
    rec = frontmatter.parse_frontmatter_doc_full(
        meta["path"], extra_fields=("related",)
    )
    if rec is None:
        return None
    return {
        "id": rec["id"],
        "title": rec["title"],
        "summary": rec["summary"],
        "group": group,
        "related": list(rec.get("related") or []),
        "body": rec["body"],
    }


def map_documents(
    codex_dir: Path,
    start_id: str,
    *,
    depth_out: int = 1,
    depth_in: int = 1,
    full: bool = False,
) -> list[dict] | None:
    """BFS the codex graph from start_id with separate outbound/inbound budgets.

    Returns a list of records (one per neighbour, alphabetically by id):
      - default (full=False): {"id", "group", "title", "summary"}
      - full mode (full=True): {"id", "group", "title", "summary", "related", "body"}

    The seed is never present in the result. Records are deduplicated by id.

    Returns None iff start_id is not in the codex index. An empty
    neighbourhood is the empty list [], not None.
    """
    if depth_out < 0 or depth_in < 0:
        raise ValueError("depth_out and depth_in must be non-negative")

    docs = scan_codex(codex_dir)
    index = {doc["id"]: doc for doc in docs}
    if start_id not in index:
        return None

    outbound, inbound = _build_adjacency(index, docs)
    neighbour_ids = _bfs_neighbour_ids(
        start_id, outbound, inbound, depth_out, depth_in
    )

    records: list[dict] = []
    for doc_id in neighbour_ids:
        record = _build_neighbour_record(index[doc_id], codex_dir, full=full)
        if record is not None:
            records.append(record)
    return records


def chaos_documents(
    project_root: Path,
    start_id: str,
    threshold: int,
    *,
    rng: _random.Random | None = None,
) -> list[dict] | None:
    """Random-walk traversal of the codex document graph from ``start_id``.

    Steps:
    1. Validate threshold (raises ValueError if < 30 or > 100).
    2. Build index and bidirectional adjacency map.
    3. BFS from start_id to compute the full reachable subgraph.
    4. Random walk: pick random unvisited reachable nodes.
       Stop when discovered / reachable_others >= threshold / 100 or no unvisited remain.

    Returns None if start_id is not in the index.
    The seed document is always the first entry.
    """
    from lore.validators import validate_chaos_threshold

    valid, err = validate_chaos_threshold(threshold)
    if not valid:
        raise ValueError(err)

    codex_dir = project_root / ".lore" / "codex"
    docs = scan_codex(codex_dir)
    index = {doc["id"]: doc for doc in docs}

    if start_id not in index:
        return None

    if rng is None:
        rng = _random.Random()

    # Build bidirectional adjacency from related links via shared helper.
    outbound, inbound = _build_adjacency(index, docs)
    adjacency: dict[str, set[str]] = {k: outbound[k] | inbound[k] for k in index}

    # BFS to find all reachable nodes from start_id
    reachable: set[str] = set()
    bfs_queue: collections.deque = collections.deque([start_id])
    reachable.add(start_id)
    while bfs_queue:
        current = bfs_queue.popleft()
        for nb in adjacency[current]:
            if nb not in reachable:
                reachable.add(nb)
                bfs_queue.append(nb)

    # reachable_others excludes the seed for threshold ratio calculation
    reachable_others = reachable - {start_id}
    total_reachable = len(reachable_others)

    # Start result with seed document
    result: list[dict] = []
    visited: set[str] = {start_id}

    seed_doc = index[start_id]
    seed_record = frontmatter.parse_frontmatter_doc(seed_doc["path"])
    if seed_record is not None:
        result.append({
            "id": seed_record["id"],
            "title": seed_record["title"],
            "summary": seed_record["summary"],
        })

    # If no reachable others, return immediately
    if total_reachable == 0:
        return result

    # Random walk
    while True:
        # Check stopping condition
        discovered = len(visited) - 1  # exclude seed
        if discovered >= total_reachable:
            break
        if discovered > 0 and (discovered / total_reachable) >= (threshold / 100):
            break

        # Pick a random unvisited reachable node
        candidates = list(reachable_others - visited)
        if not candidates:
            break

        next_id = rng.choice(candidates)
        visited.add(next_id)

        doc_meta = index[next_id]
        record = frontmatter.parse_frontmatter_doc(doc_meta["path"])
        if record is not None:
            result.append({
                "id": record["id"],
                "title": record["title"],
                "summary": record["summary"],
            })

    return result
