"""Codex scanning and document listing.

Post G17 / codex-CRUD: adds ``create_document`` / ``update_document`` /
``delete_document`` per ``transient-codex-crud-spec`` Section A.
"""

import collections
import random as _random
from pathlib import Path

import yaml

from lore import frontmatter
from lore import paths as _paths
from lore.schemas import validate_entity
from lore.validators import (
    _validate_content_nonempty,
    validate_group,
    validate_name,
)


class ConflictingDepthFlags(ValueError):
    """Raised when callers combine symmetric `depth` with directional flags."""


# ---------------------------------------------------------------------------
# CRUD constants
# ---------------------------------------------------------------------------


_DOC_TYPE_SCHEMAS: dict[str, str] = {
    "codex": "codex-frontmatter",
    "codex-source": "codex-source-frontmatter",
}

# Per spec §E.1 — refuse to delete a fixed allow-list of seeded ids.
# Today only ``codex`` (the codex.md root index) is seeded by ``lore init``.
_RESERVED_DOC_IDS: frozenset[str] = frozenset({"codex"})


def _resolve_doc_type_from_path(project_root: Path, filepath: Path) -> str:
    """Resolve doc_type from a doc's location on disk (path-derived).

    Per spec §A.2 step 3: ``sources/*`` group → ``codex-source``; else ``codex``.
    """
    codex_dir = _paths.entity_location(project_root, "codex")
    group = _paths.derive_group(filepath, codex_dir)
    if group.startswith("sources/") or group == "sources":
        return "codex-source"
    return "codex"


def _resolve_doc_type(
    *,
    group: str | None,
    explicit: str | None,
) -> str:
    """Resolve the doc_type for create_document per spec §A.2.

    Precedence: explicit kwarg → group-derived → fallback ``codex``.
    Frontmatter ``type:`` is intentionally NOT consulted (free-form label).
    """
    if explicit is not None:
        if explicit not in _DOC_TYPE_SCHEMAS:
            raise ValueError(
                f"Unknown doc_type: {explicit}. Expected: codex, codex-source."
            )
        return explicit
    if group is not None and (group == "sources" or group.startswith("sources/")):
        return "codex-source"
    return "codex"


def _find_document(project_root: Path, name: str) -> Path | None:
    """Locate a codex doc by id via subtree rglob.

    Returns the Path to the ``<name>.md`` file if found, or None.
    Raises ``ValueError`` on path-traversal name OR when >1 match is found
    (ambiguity — per spec §A.3 deliberate divergence from artifact).
    """
    if "/" in name or "\\" in name:
        raise ValueError(f"Invalid codex doc name: {name!r}")
    codex_dir = _paths.entity_location(project_root, "codex")
    if not codex_dir.exists():
        return None
    matches = list(codex_dir.rglob(f"{name}.md"))
    if not matches:
        return None
    if len(matches) > 1:
        rels = ", ".join(
            str(m.relative_to(codex_dir)) for m in sorted(matches)
        )
        raise ValueError(
            f'Codex doc "{name}" is ambiguous — matches: {rels}'
        )
    return matches[0]


def _parse_frontmatter_block(content: str) -> tuple[dict, str]:
    """Parse a codex doc's YAML frontmatter, returning (meta, body).

    ``body`` is bit-identical to ``parts[2]`` from ``content.split("---", 2)``,
    so callers that only want ``meta`` can discard it. Raises ``ValueError``
    if the block is missing, the YAML is invalid, or it is not a mapping.
    """
    parts = content.split("---", 2)
    if len(parts) < 3:
        raise ValueError(
            "Codex doc content missing frontmatter block (id, title, summary required)"
        )
    try:
        meta = yaml.safe_load(parts[1])
    except yaml.YAMLError as exc:
        raise ValueError(f"Invalid frontmatter YAML: {exc}") from exc
    if not isinstance(meta, dict):
        raise ValueError("Frontmatter must be a YAML mapping")
    return meta, parts[2]


def create_document(
    project_root: Path,
    name: str,
    content: str,
    *,
    group: str | None = None,
    doc_type: str | None = None,
) -> dict:
    """Create a new codex markdown file under ``.lore/codex/[group/]<name>.md``.

    Returns ``{id, filename, group, doc_type}`` per spec §A.1.
    Raises ``ValueError`` on any validation / duplicate / schema failure.
    """
    # 1. name
    name_err = validate_name(name)
    if name_err:
        raise ValueError(name_err)
    # 2. group
    group_err = validate_group(group)
    if group_err:
        raise ValueError(group_err)
    # 3. content non-empty
    content_err = _validate_content_nonempty(content)
    if content_err:
        raise ValueError(content_err)
    # 4. resolve doc_type
    resolved_type = _resolve_doc_type(group=group, explicit=doc_type)
    # 5. parse frontmatter (body discarded — create writes raw content verbatim)
    meta, _ = _parse_frontmatter_block(content)
    # 6. schema validate
    issues = validate_entity(
        _DOC_TYPE_SCHEMAS[resolved_type], meta, project_root=project_root
    )
    if issues:
        raise ValueError("\n".join(i.message for i in issues))
    # 7. id ↔ filename invariant
    if meta.get("id") != name:
        raise ValueError(
            f"Frontmatter id '{meta.get('id')}' does not match filename '{name}'."
        )
    # 8. subtree-wide duplicate check
    codex_dir = _paths.entity_location(project_root, "codex")
    if codex_dir.exists():
        existing = next(iter(codex_dir.rglob(f"{name}.md")), None)
        if existing is not None:
            relpath = existing.relative_to(codex_dir)
            raise ValueError(
                f"codex doc '{name}' already exists at {relpath}"
            )
    # 9. write
    target_dir = _paths.entity_location(project_root, "codex", group=group)
    target_dir.mkdir(parents=True, exist_ok=True)
    target_path = target_dir / f"{name}.md"
    target_path.write_text(content)
    # 10. envelope
    return {
        "id": name,
        "filename": f"{name}.md",
        "group": group,
        "doc_type": resolved_type,
    }


# Field-preservation merge set (spec §A.6 step 4).
_PRESERVED_UPDATE_FIELDS: tuple[str, ...] = (
    "id",
    "title",
    "summary",
    "related",
    "binds",
    "type",
)


def update_document(
    project_root: Path,
    name: str,
    content: str,
) -> dict:
    """Overwrite an existing codex doc with new content (frontmatter + body).

    Returns ``{id, filename, group, doc_type, updated_at}`` per spec §A.1.
    Raises ``ValueError`` on not-found / schema failure / parse failure.
    """
    # 1. locate
    filepath = _find_document(project_root, name)
    if filepath is None:
        raise ValueError(f'Codex doc "{name}" not found.')
    # 2. content non-empty
    content_err = _validate_content_nonempty(content)
    if content_err:
        raise ValueError(content_err)
    # 3. parse new frontmatter
    new_meta, new_body = _parse_frontmatter_block(content)
    # 4. field-preservation merge: load on-disk meta, preserve fields not in new
    existing_meta, _ = _parse_frontmatter_block(filepath.read_text())
    merged = dict(new_meta)
    for field in _PRESERVED_UPDATE_FIELDS:
        if field not in merged and field in existing_meta:
            merged[field] = existing_meta[field]
    # 5. re-resolve doc_type from path (sources stay sources)
    doc_type = _resolve_doc_type_from_path(project_root, filepath)
    # 6. schema validate
    issues = validate_entity(
        _DOC_TYPE_SCHEMAS[doc_type], merged, project_root=project_root
    )
    if issues:
        raise ValueError("\n".join(i.message for i in issues))
    # 7. id invariant
    if merged.get("id") != name:
        raise ValueError(
            f"Frontmatter id '{merged.get('id')}' does not match filename '{name}'."
        )
    # 8. serialize + write
    fm_text = yaml.dump(
        merged, default_flow_style=False, allow_unicode=True, sort_keys=False
    )
    filepath.write_text("---\n" + fm_text + "---" + new_body)
    # group from path
    codex_dir = _paths.entity_location(project_root, "codex")
    group_str = _paths.derive_group(filepath, codex_dir)
    group: str | None = group_str if group_str else None
    return {
        "id": name,
        "filename": filepath.name,
        "group": group,
        "doc_type": doc_type,
        "updated_at": None,
    }


def delete_document(
    project_root: Path,
    name: str,
) -> dict:
    """Hard-delete a codex doc (rename to ``<name>.md.deleted``).

    Returns ``{id, deleted, deleted_at, group, doc_type}`` per spec §A.1.
    Raises ``ValueError`` on not-found OR if ``name`` is a reserved seeded
    doc id. Idempotent on already-deleted docs.
    """
    if "/" in name or "\\" in name:
        raise ValueError(f"Invalid codex doc name: {name!r}")

    # Reserved-id check (spec §E.1) — runs BEFORE locator so that seeded docs
    # (e.g. codex.md whose id is "codex") are protected.
    if name in _RESERVED_DOC_IDS:
        raise ValueError(
            f"Cannot delete seeded codex doc '{name}' — protected. Edit instead."
        )

    codex_dir = _paths.entity_location(project_root, "codex")
    filepath = _find_document(project_root, name)

    if filepath is None:
        # idempotent path: if a sibling .deleted exists, return envelope w/o raise
        if codex_dir.exists():
            deleted_match = next(
                iter(codex_dir.rglob(f"{name}.md.deleted")), None
            )
            if deleted_match is not None:
                group_str = _paths.derive_group(deleted_match, codex_dir)
                doc_type = _resolve_doc_type_from_path(project_root, deleted_match)
                return {
                    "id": name,
                    "deleted": True,
                    "deleted_at": None,
                    "group": group_str if group_str else None,
                    "doc_type": doc_type,
                }
        raise ValueError(f'Codex doc "{name}" not found in .lore/codex/')

    group_str = _paths.derive_group(filepath, codex_dir)
    doc_type = _resolve_doc_type_from_path(project_root, filepath)

    deleted_path = filepath.parent / f"{name}.md.deleted"
    filepath.rename(deleted_path)
    return {
        "id": name,
        "deleted": True,
        "deleted_at": None,
        "group": group_str if group_str else None,
        "doc_type": doc_type,
    }


def list_codex(project_root: Path, filter_groups: list[str] | None = None) -> list[dict]:
    """Walk ``project_root/.lore/codex/`` recursively and return document records.

    Returns a list of dicts with keys: id, title, summary, path.
    Files without valid frontmatter or missing required fields are skipped.
    Results are sorted alphabetically by id.

    If filter_groups is a non-empty list, only documents whose group is in
    filter_groups or whose group is root-level (empty string) are returned.
    If filter_groups is None or an empty list, all documents are returned.
    """
    codex_dir = _paths.entity_location(project_root, "codex")
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


def search_documents(project_root: Path, keyword: str) -> list[dict]:
    """Return documents whose title or summary contains the keyword (case-insensitive).

    Returns a list of dicts with keys: id, title, summary (no path).
    Results are sorted alphabetically by id.
    """
    docs = list_codex(project_root)
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


def read_document(project_root: Path, doc_id: str) -> dict | None:
    """Return a full document record for the given ID, or None if not found.

    The returned dict has keys: id, title, summary, body.
    The body is the content below the YAML frontmatter block, with leading
    newlines stripped.
    """
    docs = list_codex(project_root)
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
    project_root: Path,
    start_id: str,
    *,
    depth: int | None = None,
    depth_out: int | None = None,
    depth_in: int | None = None,
    full: bool = False,
) -> list[dict] | None:
    """BFS the codex graph from start_id with separate outbound/inbound budgets.

    Returns a list of records (one per neighbour, alphabetically by id):
      - default (full=False): {"id", "group", "title", "summary"}
      - full mode (full=True): {"id", "group", "title", "summary", "related", "body"}

    The seed is never present in the result. Records are deduplicated by id.

    Returns None iff start_id is not in the codex index. An empty
    neighbourhood is the empty list [], not None.

    Depth controls:
      - ``depth=N`` — symmetric budget of ``N`` for both directions.
      - ``depth_out=N`` / ``depth_in=N`` — explicit directional budgets.
      - Combining ``depth`` with either directional flag raises
        :class:`ConflictingDepthFlags` BEFORE any disk I/O.
      - When neither is set, both budgets default to 1.
    """
    # Conflict gate — fire BEFORE disk I/O.
    if depth is not None and (depth_out is not None or depth_in is not None):
        raise ConflictingDepthFlags(
            "depth cannot be combined with depth_in or depth_out"
        )

    if depth is not None:
        eff_out = depth
        eff_in = depth
    else:
        eff_out = depth_out if depth_out is not None else 1
        eff_in = depth_in if depth_in is not None else 1

    if eff_out < 0 or eff_in < 0:
        raise ValueError("depth_out and depth_in must be non-negative")

    codex_dir = _paths.entity_location(project_root, "codex")
    docs = list_codex(project_root)
    index = {doc["id"]: doc for doc in docs}
    if start_id not in index:
        return None

    outbound, inbound = _build_adjacency(index, docs)
    neighbour_ids = _bfs_neighbour_ids(
        start_id, outbound, inbound, eff_out, eff_in
    )

    records: list[dict] = []
    for doc_id in neighbour_ids:
        record = _build_neighbour_record(index[doc_id], codex_dir, full=full)
        if record is not None:
            records.append(record)
    return records


def read_documents_with_glossary(
    project_root: Path,
    doc_ids: list[str],
    *,
    skip_glossary: bool = False,
) -> dict:
    """Compose a {documents, glossary} envelope for one-or-more codex docs.

    Absorbs the orchestration previously performed inline in
    ``cli.codex_show`` via ``_collect_codex_glossary``. The envelope
    carries RAW items only — never pre-rendered markdown — so consumers
    (CLI text mode, JSON mode, Realm) format as they see fit.

    Parameters
    ----------
    project_root:
        Project root (the directory containing ``.lore/``).
    doc_ids:
        Ordered list of codex doc IDs to load. Output order matches input.
    skip_glossary:
        When True, returns ``glossary == []`` and does NOT consult the
        glossary file.

    Returns a dict with EXACTLY the keys ``{"documents", "glossary"}``.
    Missing doc ids fail soft: a record carrying ``{"id": "<id>", "not_found": True}``
    is appended in place rather than raising.
    """
    from lore import glossary as _glossary  # deferred to keep monkeypatch surface clean

    documents: list[dict] = []
    for doc_id in doc_ids:
        doc = read_document(project_root, doc_id)
        if doc is None:
            documents.append({"id": doc_id, "not_found": True})
        else:
            documents.append(doc)

    if skip_glossary:
        glossary_items: list = []
    else:
        bodies = [d["body"] for d in documents if "body" in d]
        glossary_items = list(
            _glossary.match_glossary(bodies, root=project_root)
        )

    return {"documents": documents, "glossary": glossary_items}


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

    docs = list_codex(project_root)
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
