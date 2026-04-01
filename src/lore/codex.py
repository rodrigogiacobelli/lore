"""Codex scanning and document listing."""

import collections
import random as _random
from pathlib import Path

import yaml

from lore import frontmatter

def _parse_doc_robust(
    filepath: Path,
    *,
    extra_fields: tuple[str, ...] = (),
    include_body: bool = False,
) -> dict | None:
    """Parse a codex markdown file tolerantly.

    Unlike ``frontmatter.parse_frontmatter_doc_full``, this function strips
    leading/trailing whitespace from each line of the frontmatter block before
    YAML parsing. This makes it resilient to frontmatter that has been
    inadvertently indented (e.g. in test fixtures produced by ``textwrap.dedent``
    on a string with inconsistent indentation).

    Returns a dict with keys for each required field plus ``path`` (and
    optionally ``body`` and each name in ``extra_fields``), or ``None`` if
    parsing fails.
    """
    try:
        text = filepath.read_text()
        parts = text.split("---", 2)
        if len(parts) < 3:
            return None
        # Normalise each line of the frontmatter block so that indented
        # frontmatter (a common test-fixture artefact) is still parseable.
        fm_lines = parts[1].split("\n")
        fm_normalised = "\n".join(line.strip() for line in fm_lines)
        fm = yaml.safe_load(fm_normalised)
    except Exception:
        return None

    if not isinstance(fm, dict):
        return None
    if any(field not in fm or fm[field] is None for field in frontmatter._REQUIRED_FIELDS):
        return None

    result: dict = {field: str(fm[field]) for field in frontmatter._REQUIRED_FIELDS}
    result["path"] = filepath
    for field in extra_fields:
        if field in fm:
            result[field] = fm[field]
    if include_body:
        result["body"] = parts[2].lstrip("\n")
    return result


def scan_codex(codex_dir: Path) -> list[dict]:
    """Walk codex_dir recursively, parse frontmatter, return document records.

    Returns a list of dicts with keys: id, title, summary, group, path.
    Files without valid frontmatter or missing required fields are skipped.
    Results are sorted alphabetically by id.
    """
    if not codex_dir.exists():
        return []

    results = []
    for filepath in codex_dir.rglob("*.md"):
        record = frontmatter.parse_frontmatter_doc(filepath, required_fields=("id", "title", "summary"))
        if record is not None:
            results.append(record)

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
    record = _parse_doc_robust(filepath, extra_fields=("related",))
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


def _scan_codex_robust(codex_dir: Path) -> list[dict]:
    """Like ``scan_codex`` but uses ``_parse_doc_robust`` for tolerant parsing.

    Used internally by ``map_documents`` so that test fixtures with indented
    frontmatter are still discovered.
    """
    if not codex_dir.exists():
        return []

    results = []
    for filepath in codex_dir.rglob("*.md"):
        record = _parse_doc_robust(filepath)
        if record is not None:
            results.append(record)

    return sorted(results, key=lambda d: d["id"])


def map_documents(codex_dir: Path, start_id: str, depth: int) -> list[dict] | None:
    """BFS traversal of the codex document graph starting from ``start_id``.

    Returns a list of full document dicts (id, title, summary, body) in
    BFS order up to ``depth`` hops from the root. Each document appears at most
    once. Returns ``None`` if ``start_id`` is not in the codex index.

    Broken ``related`` links (IDs not in the index) are silently skipped.
    """
    docs = _scan_codex_robust(codex_dir)
    index = {doc["id"]: doc for doc in docs}

    if start_id not in index:
        return None

    visited: set[str] = set()
    result: list[dict] = []

    # Queue items: (doc_id, current_depth)
    queue: collections.deque = collections.deque()
    queue.append((start_id, 0))
    visited.add(start_id)

    while queue:
        current_id, current_depth = queue.popleft()
        doc_meta = index[current_id]
        full_record = _parse_doc_robust(
            doc_meta["path"],
            include_body=True,
        )
        if full_record is None:
            continue

        result.append({
            "id": full_record["id"],
            "title": full_record["title"],
            "summary": full_record["summary"],
            "body": full_record["body"],
        })

        if current_depth < depth:
            neighbours = _read_related(doc_meta["path"], index)
            for neighbour_id in neighbours:
                if neighbour_id not in visited:
                    visited.add(neighbour_id)
                    queue.append((neighbour_id, current_depth + 1))

    return result


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
    docs = _scan_codex_robust(codex_dir)
    index = {doc["id"]: doc for doc in docs}

    if start_id not in index:
        return None

    if rng is None:
        rng = _random.Random()

    # Build bidirectional adjacency from related links
    adjacency: dict[str, set[str]] = {doc_id: set() for doc_id in index}
    for doc in docs:
        neighbours = _read_related(doc["path"], index)
        for neighbour_id in neighbours:
            adjacency[doc["id"]].add(neighbour_id)
            adjacency[neighbour_id].add(doc["id"])

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
    seed_record = _parse_doc_robust(seed_doc["path"])
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
        record = _parse_doc_robust(doc_meta["path"])
        if record is not None:
            result.append({
                "id": record["id"],
                "title": record["title"],
                "summary": record["summary"],
            })

    return result
