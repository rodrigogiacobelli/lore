"""Unit tests for codex.map_documents and codex._read_related.

Spec: codex-map-us-1 (lore codex show codex-map-us-1)
Tech arch: tech-arch-codex-map (lore codex show tech-arch-codex-map)
"""

import random
import textwrap
from pathlib import Path

import pytest

from lore.codex import map_documents, _read_related
from lore.codex import chaos_documents


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _write_doc(
    codex_dir: Path,
    doc_id: str,
    *,
    related: list[str] | None = None,
    omit_related: bool = False,
) -> Path:
    """Write a minimal valid codex document into codex_dir and return the path."""
    related_line = ""
    if not omit_related:
        if related is None:
            related_line = "related: []"
        else:
            items = "\n".join(f"  - {r}" for r in related)
            related_line = f"related:\n{items}"
    content = textwrap.dedent(f"""\
        ---
        id: {doc_id}
        title: {doc_id.replace("-", " ").title()}
        summary: Summary for {doc_id}.
        {related_line}
        ---

        Body of {doc_id}.
    """)
    filepath = codex_dir / f"{doc_id}.md"
    filepath.write_text(content)
    return filepath


def _make_codex_dir(tmp_path: Path) -> Path:
    codex_dir = tmp_path / ".lore" / "codex"
    codex_dir.mkdir(parents=True)
    return codex_dir


# ---------------------------------------------------------------------------
# map_documents — depth 1
# ---------------------------------------------------------------------------


# conceptual-workflows-codex-map step 2 (depth 1 BFS)
def test_map_documents_depth_1_returns_root_and_direct_neighbours(tmp_path):
    """depth=1 returns root dict followed by all direct neighbours in related-list order."""
    codex_dir = _make_codex_dir(tmp_path)
    _write_doc(codex_dir, "root", related=["child-a", "child-b"])
    _write_doc(codex_dir, "child-a")
    _write_doc(codex_dir, "child-b")

    result = map_documents(codex_dir, "root", depth=1)

    assert result is not None
    ids = [d["id"] for d in result]
    assert ids[0] == "root"
    assert "child-a" in ids
    assert "child-b" in ids
    assert len(ids) == 3


# ---------------------------------------------------------------------------
# map_documents — depth 2
# ---------------------------------------------------------------------------


# conceptual-workflows-codex-map step 2 (depth 2 BFS)
def test_map_documents_depth_2_returns_root_depth1_depth2(tmp_path):
    """depth=2 returns root + depth-1 + depth-2 in BFS order (depth-1 before depth-2)."""
    codex_dir = _make_codex_dir(tmp_path)
    _write_doc(codex_dir, "root", related=["child-a"])
    _write_doc(codex_dir, "child-a", related=["grandchild-x"])
    _write_doc(codex_dir, "grandchild-x")

    result = map_documents(codex_dir, "root", depth=2)

    assert result is not None
    ids = [d["id"] for d in result]
    assert ids[0] == "root"
    assert ids.index("child-a") < ids.index("grandchild-x")
    assert set(ids) == {"root", "child-a", "grandchild-x"}


# ---------------------------------------------------------------------------
# map_documents — deduplication
# ---------------------------------------------------------------------------


# conceptual-workflows-codex-map step 2 (visited set deduplication)
def test_map_documents_deduplication(tmp_path):
    """Document reachable via two paths appears exactly once in result."""
    codex_dir = _make_codex_dir(tmp_path)
    _write_doc(codex_dir, "root", related=["child-a", "child-b"])
    _write_doc(codex_dir, "child-a", related=["shared"])
    _write_doc(codex_dir, "child-b", related=["shared"])
    _write_doc(codex_dir, "shared")

    result = map_documents(codex_dir, "root", depth=2)

    assert result is not None
    ids = [d["id"] for d in result]
    assert ids.count("shared") == 1


# ---------------------------------------------------------------------------
# map_documents — cycle safety
# ---------------------------------------------------------------------------


# conceptual-workflows-codex-map step 2 (cycle safety)
def test_map_documents_cycle_both_docs_appear_once(tmp_path):
    """Cycle A → B → A: both documents appear exactly once and function terminates."""
    codex_dir = _make_codex_dir(tmp_path)
    _write_doc(codex_dir, "cycle-a", related=["cycle-b"])
    _write_doc(codex_dir, "cycle-b", related=["cycle-a"])

    result = map_documents(codex_dir, "cycle-a", depth=3)

    assert result is not None
    ids = [d["id"] for d in result]
    assert ids.count("cycle-a") == 1
    assert ids.count("cycle-b") == 1


# ---------------------------------------------------------------------------
# map_documents — start_id not found
# ---------------------------------------------------------------------------


# conceptual-workflows-codex-map step 1 (validate root — returns None)
def test_map_documents_returns_none_when_start_id_missing(tmp_path):
    """Returns None when start_id is not in the codex index."""
    codex_dir = _make_codex_dir(tmp_path)

    result = map_documents(codex_dir, "nonexistent-id", depth=1)

    assert result is None


# ---------------------------------------------------------------------------
# map_documents — broken related link
# ---------------------------------------------------------------------------


# conceptual-workflows-codex-map step 3 (dead link skip)
def test_map_documents_broken_related_link_skipped(tmp_path):
    """Broken related link (ID not in index) is silently skipped; valid neighbours still traversed."""
    codex_dir = _make_codex_dir(tmp_path)
    _write_doc(codex_dir, "root", related=["existing-child", "nonexistent-id"])
    _write_doc(codex_dir, "existing-child")

    result = map_documents(codex_dir, "root", depth=1)

    assert result is not None
    ids = [d["id"] for d in result]
    assert "root" in ids
    assert "existing-child" in ids
    assert "nonexistent-id" not in ids


# ---------------------------------------------------------------------------
# map_documents — leaf node with empty related list
# ---------------------------------------------------------------------------


# conceptual-workflows-codex-map step 3 (_read_related returns [] for empty list)
def test_map_documents_empty_related_list_is_leaf(tmp_path):
    """Document with related: [] returns list containing only root, no error raised."""
    codex_dir = _make_codex_dir(tmp_path)
    _write_doc(codex_dir, "leaf-doc", related=[])

    result = map_documents(codex_dir, "leaf-doc", depth=2)

    assert result is not None
    assert len(result) == 1
    assert result[0]["id"] == "leaf-doc"


# ---------------------------------------------------------------------------
# map_documents — absent related field treated as leaf
# ---------------------------------------------------------------------------


# conceptual-workflows-codex-map step 3 (_read_related returns [] for absent field)
def test_map_documents_absent_related_field_is_leaf(tmp_path):
    """Document with no related field in frontmatter is treated as leaf node."""
    codex_dir = _make_codex_dir(tmp_path)
    _write_doc(codex_dir, "leaf-doc", omit_related=True)

    result = map_documents(codex_dir, "leaf-doc", depth=2)

    assert result is not None
    assert len(result) == 1
    assert result[0]["id"] == "leaf-doc"


# ---------------------------------------------------------------------------
# map_documents — determinism
# ---------------------------------------------------------------------------


# conceptual-workflows-codex-map step 2 (determinism via alphabetical sort in _read_related)
def test_map_documents_output_is_deterministic(tmp_path):
    """Two calls with same input produce identical result list."""
    codex_dir = _make_codex_dir(tmp_path)
    _write_doc(codex_dir, "root", related=["alpha", "beta", "gamma"])
    _write_doc(codex_dir, "alpha")
    _write_doc(codex_dir, "beta")
    _write_doc(codex_dir, "gamma")

    result_1 = map_documents(codex_dir, "root", depth=1)
    result_2 = map_documents(codex_dir, "root", depth=1)

    assert result_1 is not None
    assert result_2 is not None
    assert [d["id"] for d in result_1] == [d["id"] for d in result_2]


# ---------------------------------------------------------------------------
# _read_related — core contract
# ---------------------------------------------------------------------------


# conceptual-workflows-codex-map step 3 (_read_related core contract)
def test_read_related_returns_sorted_valid_ids(tmp_path):
    """_read_related returns sorted list of valid IDs present in the index."""
    codex_dir = _make_codex_dir(tmp_path)
    doc_path = _write_doc(codex_dir, "doc-a", related=["doc-c", "doc-b"])
    _write_doc(codex_dir, "doc-b")
    _write_doc(codex_dir, "doc-c")

    # Build a minimal index as map_documents would
    index = {
        "doc-a": {"id": "doc-a", "path": doc_path},
        "doc-b": {"id": "doc-b", "path": codex_dir / "doc-b.md"},
        "doc-c": {"id": "doc-c", "path": codex_dir / "doc-c.md"},
    }

    result = _read_related(doc_path, index)

    assert result == sorted(result)
    assert set(result) == {"doc-b", "doc-c"}


# ---------------------------------------------------------------------------
# _read_related — filters dead links
# ---------------------------------------------------------------------------


# conceptual-workflows-codex-map step 3 (dead link filter)
def test_read_related_filters_ids_not_in_index(tmp_path):
    """_read_related filters out IDs not present in the index."""
    codex_dir = _make_codex_dir(tmp_path)
    doc_path = _write_doc(codex_dir, "doc-a", related=["doc-b", "ghost-id"])
    _write_doc(codex_dir, "doc-b")

    index = {
        "doc-a": {"id": "doc-a", "path": doc_path},
        "doc-b": {"id": "doc-b", "path": codex_dir / "doc-b.md"},
    }

    result = _read_related(doc_path, index)

    assert "ghost-id" not in result
    assert "doc-b" in result


# ---------------------------------------------------------------------------
# _read_related — absent field
# ---------------------------------------------------------------------------


# conceptual-workflows-codex-map step 3 (absent field)
def test_read_related_returns_empty_for_absent_field(tmp_path):
    """_read_related returns [] when related field is absent from frontmatter."""
    codex_dir = _make_codex_dir(tmp_path)
    doc_path = _write_doc(codex_dir, "doc-a", omit_related=True)
    index = {"doc-a": {"id": "doc-a", "path": doc_path}}

    result = _read_related(doc_path, index)

    assert result == []


# ---------------------------------------------------------------------------
# _read_related — null field
# ---------------------------------------------------------------------------


# conceptual-workflows-codex-map step 3 (null field)
def test_read_related_returns_empty_for_null_related(tmp_path):
    """_read_related returns [] when related field is explicitly null."""
    codex_dir = _make_codex_dir(tmp_path)
    content = textwrap.dedent("""\
        ---
        id: doc-a
        title: Doc A
        summary: summary.
        related: null
        ---

        Body.
    """)
    doc_path = codex_dir / "doc-a.md"
    doc_path.write_text(content)
    index = {"doc-a": {"id": "doc-a", "path": doc_path}}

    result = _read_related(doc_path, index)

    assert result == []


# ---------------------------------------------------------------------------
# _read_related — empty list
# ---------------------------------------------------------------------------


# conceptual-workflows-codex-map step 3 (empty list)
def test_read_related_returns_empty_for_empty_list(tmp_path):
    """_read_related returns [] when related is an empty list."""
    codex_dir = _make_codex_dir(tmp_path)
    doc_path = _write_doc(codex_dir, "doc-a", related=[])
    index = {"doc-a": {"id": "doc-a", "path": doc_path}}

    result = _read_related(doc_path, index)

    assert result == []


# ---------------------------------------------------------------------------
# _read_related — defensive: null entries dropped
# ---------------------------------------------------------------------------


# conceptual-workflows-codex-map step 3 (defensive parsing — null entries dropped)
def test_read_related_drops_null_entries(tmp_path):
    """_read_related drops null entries in the related list."""
    codex_dir = _make_codex_dir(tmp_path)
    content = textwrap.dedent("""\
        ---
        id: doc-a
        title: Doc A
        summary: summary.
        related:
          - doc-b
          - null
          - doc-c
        ---

        Body.
    """)
    doc_path = codex_dir / "doc-a.md"
    doc_path.write_text(content)
    _write_doc(codex_dir, "doc-b")
    _write_doc(codex_dir, "doc-c")
    index = {
        "doc-a": {"id": "doc-a", "path": doc_path},
        "doc-b": {"id": "doc-b", "path": codex_dir / "doc-b.md"},
        "doc-c": {"id": "doc-c", "path": codex_dir / "doc-c.md"},
    }

    result = _read_related(doc_path, index)

    assert None not in result
    assert "doc-b" in result
    assert "doc-c" in result


# ---------------------------------------------------------------------------
# _read_related — defensive: non-string entries cast and trimmed
# ---------------------------------------------------------------------------


# conceptual-workflows-codex-map step 3 (defensive parsing — non-string cast and trimmed)
def test_read_related_casts_non_string_entries(tmp_path):
    """_read_related casts non-string entries (e.g. integers) to str and strips whitespace."""
    codex_dir = _make_codex_dir(tmp_path)
    # Write a doc whose related list has an integer entry that, when cast, matches an index key
    content = textwrap.dedent("""\
        ---
        id: doc-a
        title: Doc A
        summary: summary.
        related:
          - 42
        ---

        Body.
    """)
    doc_path = codex_dir / "doc-a.md"
    doc_path.write_text(content)
    _write_doc(codex_dir, "42")
    index = {
        "doc-a": {"id": "doc-a", "path": doc_path},
        "42": {"id": "42", "path": codex_dir / "42.md"},
    }

    result = _read_related(doc_path, index)

    # The integer 42 should be cast to "42" and matched in the index
    assert "42" in result


# ---------------------------------------------------------------------------
# US-2: map_documents — depth boundary unit tests
# ---------------------------------------------------------------------------


# conceptual-workflows-codex-map parameters table (depth 0)
def test_map_documents_depth_0_returns_root_only(tmp_path):
    """depth=0 returns a list containing only the root document dict, with no neighbours."""
    codex_dir = _make_codex_dir(tmp_path)
    _write_doc(codex_dir, "root", related=["child-a"])
    _write_doc(codex_dir, "child-a")

    result = map_documents(codex_dir, "root", depth=0)

    assert result is not None
    ids = [d["id"] for d in result]
    assert ids == ["root"]
    assert "child-a" not in ids


# conceptual-workflows-codex-map step 2 (depth 1 cutoff)
def test_map_documents_depth_1_excludes_grandchildren(tmp_path):
    """depth=1 returns root plus direct neighbours; grandchildren not included."""
    codex_dir = _make_codex_dir(tmp_path)
    _write_doc(codex_dir, "root", related=["child-a"])
    _write_doc(codex_dir, "child-a", related=["grandchild-x"])
    _write_doc(codex_dir, "grandchild-x")

    result = map_documents(codex_dir, "root", depth=1)

    assert result is not None
    ids = [d["id"] for d in result]
    assert "root" in ids
    assert "child-a" in ids
    assert "grandchild-x" not in ids


# conceptual-workflows-codex-map step 2 (depth 2)
def test_map_documents_depth_2_includes_grandchildren(tmp_path):
    """depth=2 returns root plus depth-1 plus depth-2 documents."""
    codex_dir = _make_codex_dir(tmp_path)
    _write_doc(codex_dir, "root", related=["child-a"])
    _write_doc(codex_dir, "child-a", related=["grandchild-x"])
    _write_doc(codex_dir, "grandchild-x")

    result = map_documents(codex_dir, "root", depth=2)

    assert result is not None
    ids = [d["id"] for d in result]
    assert "root" in ids
    assert "child-a" in ids
    assert "grandchild-x" in ids
    assert ids.index("child-a") < ids.index("grandchild-x")


# ---------------------------------------------------------------------------
# US-3: CLI command registration unit checks
# ---------------------------------------------------------------------------


# conceptual-workflows-codex-map (command registered as "map" under codex group)
def test_codex_map_command_registered_in_codex_group():
    """Inspect the codex Click group's commands dict.

    Assert "map" is a key in codex.commands.
    """
    from lore.cli import codex

    assert "map" in codex.commands


# conceptual-workflows-codex-map (doc_id is a required positional argument)
def test_codex_map_doc_id_is_required_argument():
    """The 'map' command must have a required positional param named 'doc_id'."""
    from lore.cli import codex_map
    import click

    param_names = [p.name for p in codex_map.params]
    assert "doc_id" in param_names

    doc_id_param = next(p for p in codex_map.params if p.name == "doc_id")
    assert isinstance(doc_id_param, click.Argument)
    assert doc_id_param.required


# conceptual-workflows-codex-map (--depth defaults to 1)
def test_codex_map_depth_option_defaults_to_1_unit():
    """The '--depth' option on the 'map' command must default to 1."""
    from lore.cli import codex_map

    depth_param = next(p for p in codex_map.params if p.name == "depth")
    assert depth_param.default == 1


# ---------------------------------------------------------------------------
# US-001 / US-002 / US-003 / US-004: chaos_documents unit stubs
# ---------------------------------------------------------------------------


# Unit — seed is first element of returned list
# conceptual-workflows-codex-chaos step 4 (seed document always first entry in result per FR-4)
def test_chaos_documents_seed_is_first(tmp_path):
    codex_dir = _make_codex_dir(tmp_path)
    _write_doc(codex_dir, "seed-doc", related=["neighbour-a", "neighbour-b"])
    _write_doc(codex_dir, "neighbour-a")
    _write_doc(codex_dir, "neighbour-b")

    result = chaos_documents(tmp_path, "seed-doc", threshold=100, rng=random.Random(42))

    assert result is not None
    assert result[0]["id"] == "seed-doc"


# Unit — returns None when start_id not in index
# conceptual-workflows-codex-chaos step 1 (validate seed: absent → return None)
def test_chaos_documents_unknown_seed_returns_none(tmp_path):
    codex_dir = _make_codex_dir(tmp_path)
    _write_doc(codex_dir, "doc-a")
    _write_doc(codex_dir, "doc-b")

    result = chaos_documents(tmp_path, "missing", threshold=50)

    assert result is None


# Unit — leaf seed (no related links) returns list of length 1
# conceptual-workflows-codex-chaos step 3 (reachable set size == 1 → return immediately)
def test_chaos_documents_leaf_seed_returns_only_seed(tmp_path):
    codex_dir = _make_codex_dir(tmp_path)
    _write_doc(codex_dir, "leaf-doc", omit_related=True)

    result = chaos_documents(tmp_path, "leaf-doc", threshold=40)

    assert result is not None
    assert len(result) == 1
    assert result[0]["id"] == "leaf-doc"


# Unit — does not write, create, or modify any file in codex directory
# conceptual-workflows-codex-chaos (chaos traversal is read-only per NFR)
def test_chaos_documents_does_not_modify_codex(tmp_path):
    codex_dir = _make_codex_dir(tmp_path)
    _write_doc(codex_dir, "seed-doc", related=["doc-b", "doc-c"])
    _write_doc(codex_dir, "doc-b", related=["doc-d"])
    _write_doc(codex_dir, "doc-c")
    _write_doc(codex_dir, "doc-d", related=["doc-e"])
    _write_doc(codex_dir, "doc-e")

    files_before = {p: p.stat().st_mtime for p in codex_dir.rglob("*.md")}
    count_before = len(list(codex_dir.rglob("*.md")))

    chaos_documents(tmp_path, "seed-doc", threshold=50)

    files_after = {p: p.stat().st_mtime for p in codex_dir.rglob("*.md")}
    count_after = len(list(codex_dir.rglob("*.md")))

    assert count_after == count_before
    for path, mtime in files_before.items():
        assert files_after[path] == mtime


# Unit — threshold=100 returns full connected component
# conceptual-workflows-codex-chaos step 4 (walk exhausts reachable set when threshold=100)
def test_chaos_documents_threshold_100_returns_all_reachable(tmp_path):
    codex_dir = _make_codex_dir(tmp_path)
    _write_doc(codex_dir, "doc-1", related=["doc-2", "doc-3"])
    _write_doc(codex_dir, "doc-2", related=["doc-4"])
    _write_doc(codex_dir, "doc-3", related=["doc-5"])
    _write_doc(codex_dir, "doc-4")
    _write_doc(codex_dir, "doc-5")

    result = chaos_documents(tmp_path, "doc-1", threshold=100, rng=random.Random(0))

    assert result is not None
    ids = [d["id"] for d in result]
    assert len(ids) == 5
    assert set(ids) == {"doc-1", "doc-2", "doc-3", "doc-4", "doc-5"}
    assert len(ids) == len(set(ids))


# Unit — no duplicate IDs in result (seeded RNG)
# conceptual-workflows-codex-chaos step 4 (visited set prevents revisiting nodes)
def test_chaos_documents_no_duplicate_ids(tmp_path):
    codex_dir = _make_codex_dir(tmp_path)
    _write_doc(codex_dir, "seed-doc", related=["n1", "n2", "n3"])
    for i in range(1, 10):
        prev = f"n{i}"
        nxt = f"n{i + 1}" if i < 9 else None
        _write_doc(codex_dir, prev, related=[nxt] if nxt else [])
    _write_doc(codex_dir, "n9")

    result = chaos_documents(tmp_path, "seed-doc", threshold=50, rng=random.Random(42))

    assert result is not None
    ids = [d["id"] for d in result]
    assert len(ids) == len(set(ids))


# Unit — cyclic related graphs (A→B→A) do not produce duplicate entries
# conceptual-workflows-codex-chaos step 4 (visited set applied before appending to result)
def test_chaos_documents_cyclic_graph_no_duplicates(tmp_path):
    codex_dir = _make_codex_dir(tmp_path)
    _write_doc(codex_dir, "doc-a", related=["doc-b"])
    _write_doc(codex_dir, "doc-b", related=["doc-a"])

    result = chaos_documents(tmp_path, "doc-a", threshold=100, rng=random.Random(0))

    assert result is not None
    ids = [d["id"] for d in result]
    assert len(ids) == 2
    assert len(ids) == len(set(ids))


# Unit — non-determinism: different seeds produce different result sets
# conceptual-workflows-codex-chaos step 4 (rng.choice picks different neighbours per seed)
def test_chaos_documents_different_rng_seeds_produce_different_results(tmp_path):
    codex_dir = _make_codex_dir(tmp_path)
    # Build a 10-node graph where seed-doc connects to n1..n9, each connected to the next
    _write_doc(codex_dir, "seed-doc", related=["n1", "n2", "n3", "n4", "n5"])
    _write_doc(codex_dir, "n1", related=["n6"])
    _write_doc(codex_dir, "n2", related=["n7"])
    _write_doc(codex_dir, "n3", related=["n8"])
    _write_doc(codex_dir, "n4", related=["n9"])
    _write_doc(codex_dir, "n5")
    _write_doc(codex_dir, "n6")
    _write_doc(codex_dir, "n7")
    _write_doc(codex_dir, "n8")
    _write_doc(codex_dir, "n9")

    result_a = chaos_documents(tmp_path, "seed-doc", threshold=50, rng=random.Random(1))
    result_b = chaos_documents(tmp_path, "seed-doc", threshold=50, rng=random.Random(2))

    assert result_a is not None
    assert result_b is not None
    # At least one of these result sets differs — they are non-deterministic across RNG seeds
    assert {d["id"] for d in result_a} != {d["id"] for d in result_b}


# Unit — bidirectional adjacency: inbound-only related link is traversable
# conceptual-workflows-codex-chaos step 2 (bidirectional adjacency pre-pass: A→B registers B as neighbour of A and A as neighbour of B)
def test_chaos_documents_bidirectional_adjacency(tmp_path):
    codex_dir = _make_codex_dir(tmp_path)
    _write_doc(codex_dir, "doc-a", related=["doc-b"])
    _write_doc(codex_dir, "doc-b", omit_related=True)

    result = chaos_documents(tmp_path, "doc-b", threshold=100, rng=random.Random(0))

    assert result is not None
    ids = [d["id"] for d in result]
    assert "doc-a" in ids


# Unit — raises ValueError when threshold below 30
# conceptual-workflows-codex-chaos step 2 (validate_chaos_threshold called before index load)
def test_chaos_documents_raises_for_threshold_below_30(tmp_path):
    codex_dir = _make_codex_dir(tmp_path)
    _write_doc(codex_dir, "any-doc")

    import pytest as _pytest
    with _pytest.raises(ValueError):
        chaos_documents(tmp_path, "any-doc", threshold=29)


# Unit — chaos_documents returns None when start_id absent from non-empty codex index
# conceptual-workflows-codex-chaos step 1 (validate seed: absent from index → return None)
def test_chaos_documents_returns_none_for_unknown_id(tmp_path):
    # Given: codex with "doc-a"; start_id = "missing"
    codex_dir = _make_codex_dir(tmp_path)
    _write_doc(codex_dir, "doc-a")

    # When: chaos_documents(tmp_path, "missing", threshold=50)
    result = chaos_documents(tmp_path, "missing", threshold=50)

    # Then: result is None
    assert result is None, f"Expected None but got {result!r}"


# Unit — chaos_documents returns None even when codex is non-empty
# conceptual-workflows-codex-chaos step 1 (index lookup: only exact match returns non-None)
def test_chaos_documents_returns_none_even_with_non_empty_codex(tmp_path):
    # Given: codex with 5 connected docs none of which has id "ghost"
    codex_dir = _make_codex_dir(tmp_path)
    _write_doc(codex_dir, "doc-1", related=["doc-2"])
    _write_doc(codex_dir, "doc-2", related=["doc-3"])
    _write_doc(codex_dir, "doc-3", related=["doc-4"])
    _write_doc(codex_dir, "doc-4", related=["doc-5"])
    _write_doc(codex_dir, "doc-5")

    # When: chaos_documents(tmp_path, "ghost", threshold=40)
    result = chaos_documents(tmp_path, "ghost", threshold=40)

    # Then: result is None
    assert result is None, f"Expected None but got {result!r}"


# Unit — CLI handler writes correct error to stderr and exits 1 when chaos_documents returns None
# conceptual-workflows-codex-chaos Failure Modes (CLI handler translates None → stderr message + exit 1)
def test_chaos_cli_handler_stderr_on_none_result(runner, tmp_path):
    # Given: project at tmp_path with no "phantom-id" in codex
    # Uses global --json flag (ctx.obj["json"]=True) to test that JSON mode also exits 1
    # and emits JSON error envelope — this fails until the CLI handler checks ctx.obj["json"]
    import json
    import subprocess
    import sys

    lore_dir = tmp_path / ".lore"
    lore_dir.mkdir(parents=True, exist_ok=True)
    codex_dir = lore_dir / "codex"
    codex_dir.mkdir(parents=True, exist_ok=True)
    _write_doc(codex_dir, "other-doc")

    # Plain-text mode: exit 1, correct message on stderr, empty stdout
    proc_plain = subprocess.run(
        [sys.executable, "-c", "from lore.cli import main; main()",
         "codex", "chaos", "phantom-id", "--threshold", "50"],
        capture_output=True,
        text=True,
        cwd=str(tmp_path),
    )
    assert proc_plain.returncode == 1, f"Expected exit code 1 but got {proc_plain.returncode}"
    assert 'Document "phantom-id" not found' in proc_plain.stderr, (
        f"Expected error message in stderr but got: {proc_plain.stderr!r}"
    )
    assert proc_plain.stdout == "", f"Expected empty stdout but got: {proc_plain.stdout!r}"

    # JSON mode via global flag (ctx.obj["json"] = True): must emit JSON error envelope, not plain text
    # This assertion fails until codex_chaos checks ctx.obj.get("json", False)
    proc_json_global = subprocess.run(
        [sys.executable, "-c", "from lore.cli import main; main()",
         "--json", "codex", "chaos", "phantom-id", "--threshold", "50"],
        capture_output=True,
        text=True,
        cwd=str(tmp_path),
    )
    assert proc_json_global.returncode == 1
    error_envelope = json.loads(proc_json_global.stderr)
    assert error_envelope == {"error": 'Document "phantom-id" not found'}, (
        f"Expected JSON envelope on stderr in --json mode; got plain text: {proc_json_global.stderr!r}"
    )


# Unit — CLI handler writes JSON error envelope to stderr in JSON mode when chaos_documents returns None
# conceptual-workflows-codex-chaos Failure Modes (JSON mode: {"error": ...} to stderr, exit 1)
def test_chaos_cli_handler_json_error_envelope_on_none_result(runner, tmp_path):
    # Given: project at tmp_path with no "ghost-id"; json mode active via --json flag on codex_chaos
    # --json placed at end of command per memory/feedback_json_flag_placement.md convention
    import json
    import subprocess
    import sys

    lore_dir = tmp_path / ".lore"
    lore_dir.mkdir(parents=True, exist_ok=True)
    codex_dir = lore_dir / "codex"
    codex_dir.mkdir(parents=True, exist_ok=True)
    _write_doc(codex_dir, "other-doc")

    proc = subprocess.run(
        [sys.executable, "-c", "from lore.cli import main; main()",
         "codex", "chaos", "ghost-id", "--threshold", "50", "--json"],
        capture_output=True,
        text=True,
        cwd=str(tmp_path),
    )

    # --json is not yet registered on codex_chaos; exit code will be 2 until implemented
    assert proc.returncode == 1, f"Expected exit code 1 but got {proc.returncode}"
    assert proc.stdout == "", f"Expected empty stdout but got: {proc.stdout!r}"
    error_envelope = json.loads(proc.stderr)
    assert error_envelope == {"error": 'Document "ghost-id" not found'}, (
        f"Unexpected JSON error envelope: {error_envelope!r}"
    )


# Unit — nothing written to stdout in either mode when chaos_documents returns None
# conceptual-workflows-codex-chaos Failure Modes (nothing on stdout on error)
def test_chaos_cli_handler_no_stdout_on_not_found(runner, tmp_path):
    # Given: project at tmp_path with no "gone-id"
    # Verifies that --json flag is accepted (exit 1, not 2) and stdout is empty in both modes
    import subprocess
    import sys

    lore_dir = tmp_path / ".lore"
    lore_dir.mkdir(parents=True, exist_ok=True)
    codex_dir = lore_dir / "codex"
    codex_dir.mkdir(parents=True, exist_ok=True)
    _write_doc(codex_dir, "other-doc")

    # When: invoked without --json flag
    proc_plain = subprocess.run(
        [sys.executable, "-c", "from lore.cli import main; main()",
         "codex", "chaos", "gone-id", "--threshold", "50"],
        capture_output=True,
        text=True,
        cwd=str(tmp_path),
    )

    # When: invoked with --json flag at end (should be accepted, not produce Click option error)
    proc_json = subprocess.run(
        [sys.executable, "-c", "from lore.cli import main; main()",
         "codex", "chaos", "gone-id", "--threshold", "50", "--json"],
        capture_output=True,
        text=True,
        cwd=str(tmp_path),
    )

    # Then: stdout is empty in both cases
    assert proc_plain.stdout == "", (
        f"Expected empty stdout in plain-text mode but got: {proc_plain.stdout!r}"
    )
    # --json must be recognised (exit 1, not 2) for this assertion to be meaningful
    assert proc_json.returncode == 1, (
        f"Expected exit 1 in JSON mode (--json not yet implemented on codex_chaos); "
        f"got {proc_json.returncode}"
    )
    assert proc_json.stdout == "", (
        f"Expected empty stdout in JSON mode but got: {proc_json.stdout!r}"
    )


# Unit — JSON mode: stdout is a parseable JSON string on success
# conceptual-workflows-codex-chaos step 5 (JSON render: output must be valid JSON)
def test_chaos_cli_json_stdout_is_parseable(runner, tmp_path):
    import json
    import subprocess
    import sys

    # Given: project at tmp_path with connected docs
    lore_dir = tmp_path / ".lore"
    lore_dir.mkdir(parents=True, exist_ok=True)
    codex_dir = lore_dir / "codex"
    codex_dir.mkdir(parents=True, exist_ok=True)
    _write_doc(codex_dir, "seed-j1", related=["seed-j2"])
    _write_doc(codex_dir, "seed-j2")

    # When: CLI invoked with --json flag at end
    proc = subprocess.run(
        [sys.executable, "-c", "from lore.cli import main; main()",
         "codex", "chaos", "seed-j1", "--threshold", "50", "--json"],
        capture_output=True,
        text=True,
        cwd=str(tmp_path),
    )

    # Then: exit 0, stdout parses as JSON (no exception)
    assert proc.returncode == 0, f"Expected exit 0; got {proc.returncode}. stderr={proc.stderr!r}"
    parsed = json.loads(proc.stdout)  # raises if not valid JSON
    assert parsed is not None


# Unit — JSON mode: parsed JSON has key "documents" whose value is a list
# conceptual-workflows-codex-chaos step 5 (JSON envelope shape: {"documents": [...]})
def test_chaos_cli_json_has_documents_key(runner, tmp_path):
    import json
    import subprocess
    import sys

    # Given: project at tmp_path with connected docs
    lore_dir = tmp_path / ".lore"
    lore_dir.mkdir(parents=True, exist_ok=True)
    codex_dir = lore_dir / "codex"
    codex_dir.mkdir(parents=True, exist_ok=True)
    _write_doc(codex_dir, "seed-j3", related=["seed-j4"])
    _write_doc(codex_dir, "seed-j4")

    # When: CLI invoked with --json flag at end
    proc = subprocess.run(
        [sys.executable, "-c", "from lore.cli import main; main()",
         "codex", "chaos", "seed-j3", "--threshold", "50", "--json"],
        capture_output=True,
        text=True,
        cwd=str(tmp_path),
    )

    assert proc.returncode == 0, f"Expected exit 0; got {proc.returncode}. stderr={proc.stderr!r}"
    data = json.loads(proc.stdout)
    # Then: parsed JSON has key "documents" whose value is a list
    assert "documents" in data, f"Expected 'documents' key; got {set(data.keys())}"
    assert isinstance(data["documents"], list), f"Expected list; got {type(data['documents'])}"


# Unit — JSON mode: each document dict has exactly the keys id, title, summary (no other keys)
# conceptual-workflows-codex-chaos step 5 (JSON output: metadata-only, document has exactly 3 keys)
def test_chaos_cli_json_document_fields_exact_keys(runner, tmp_path):
    import json
    import subprocess
    import sys

    # Given: project at tmp_path with connected docs
    lore_dir = tmp_path / ".lore"
    lore_dir.mkdir(parents=True, exist_ok=True)
    codex_dir = lore_dir / "codex"
    codex_dir.mkdir(parents=True, exist_ok=True)
    _write_doc(codex_dir, "seed-j5", related=["seed-j6"])
    _write_doc(codex_dir, "seed-j6")

    # When: CLI invoked with --json flag at end
    proc = subprocess.run(
        [sys.executable, "-c", "from lore.cli import main; main()",
         "codex", "chaos", "seed-j5", "--threshold", "50", "--json"],
        capture_output=True,
        text=True,
        cwd=str(tmp_path),
    )

    assert proc.returncode == 0, f"Expected exit 0; got {proc.returncode}. stderr={proc.stderr!r}"
    data = json.loads(proc.stdout)
    # Then: for each doc in result["documents"]: set(doc.keys()) == {"id", "title", "summary"}
    for doc in data["documents"]:
        assert set(doc.keys()) == {"id", "title", "summary"}, (
            f"Document has unexpected keys: {set(doc.keys())}"
        )


# Unit — JSON mode: no "body" key appears in any document dict
# conceptual-workflows-codex-chaos step 5 (JSON output: metadata-only, no body field per spec — body excluded)
def test_chaos_cli_json_document_fields_no_body(runner, tmp_path):
    import json
    import subprocess
    import sys

    # Given: project at tmp_path with connected docs
    lore_dir = tmp_path / ".lore"
    lore_dir.mkdir(parents=True, exist_ok=True)
    codex_dir = lore_dir / "codex"
    codex_dir.mkdir(parents=True, exist_ok=True)
    _write_doc(codex_dir, "seed-j7", related=["seed-j8"])
    _write_doc(codex_dir, "seed-j8")

    # When: CLI invoked with --json flag at end
    proc = subprocess.run(
        [sys.executable, "-c", "from lore.cli import main; main()",
         "codex", "chaos", "seed-j7", "--threshold", "50", "--json"],
        capture_output=True,
        text=True,
        cwd=str(tmp_path),
    )

    assert proc.returncode == 0, f"Expected exit 0; got {proc.returncode}. stderr={proc.stderr!r}"
    data = json.loads(proc.stdout)
    # Then: for each doc in result["documents"]: "body" not in doc
    for doc in data["documents"]:
        assert "body" not in doc, f"Unexpected 'body' key in document: {doc!r}"


# Unit — JSON mode: document id values match the IDs returned by chaos_documents
# conceptual-workflows-codex-chaos step 5 (JSON render maps chaos_documents result to envelope)
def test_chaos_cli_json_ids_match_chaos_documents_output(runner, tmp_path):
    import json
    import subprocess
    import sys

    # Given: project at tmp_path with connected docs
    lore_dir = tmp_path / ".lore"
    lore_dir.mkdir(parents=True, exist_ok=True)
    codex_dir = lore_dir / "codex"
    codex_dir.mkdir(parents=True, exist_ok=True)
    _write_doc(codex_dir, "seed-j9", related=["seed-j10", "seed-j11"])
    _write_doc(codex_dir, "seed-j10")
    _write_doc(codex_dir, "seed-j11")

    # When: CLI invoked with --json flag at end (threshold 100 to exhaust all reachable)
    proc = subprocess.run(
        [sys.executable, "-c", "from lore.cli import main; main()",
         "codex", "chaos", "seed-j9", "--threshold", "100", "--json"],
        capture_output=True,
        text=True,
        cwd=str(tmp_path),
    )

    assert proc.returncode == 0, f"Expected exit 0; got {proc.returncode}. stderr={proc.stderr!r}"
    data = json.loads(proc.stdout)
    # Then: all IDs in the JSON output exist in the codex and match what chaos_documents would return
    expected_ids = {"seed-j9", "seed-j10", "seed-j11"}
    actual_ids = {d["id"] for d in data["documents"]}
    assert actual_ids == expected_ids, (
        f"Expected IDs {expected_ids}; got {actual_ids}"
    )


# Unit — JSON mode: seed document is first element of documents array
# conceptual-workflows-codex-chaos step 5 (seed always first in result per FR-4)
def test_chaos_cli_json_seed_is_first_element(runner, tmp_path):
    import json
    import subprocess
    import sys

    # Given: project at tmp_path with "seed-doc" connected to others
    lore_dir = tmp_path / ".lore"
    lore_dir.mkdir(parents=True, exist_ok=True)
    codex_dir = lore_dir / "codex"
    codex_dir.mkdir(parents=True, exist_ok=True)
    _write_doc(codex_dir, "seed-first", related=["sf-n1", "sf-n2"])
    _write_doc(codex_dir, "sf-n1")
    _write_doc(codex_dir, "sf-n2")

    # When: CLI invoked with --json flag at end
    proc = subprocess.run(
        [sys.executable, "-c", "from lore.cli import main; main()",
         "codex", "chaos", "seed-first", "--threshold", "60", "--json"],
        capture_output=True,
        text=True,
        cwd=str(tmp_path),
    )

    assert proc.returncode == 0, f"Expected exit 0; got {proc.returncode}. stderr={proc.stderr!r}"
    data = json.loads(proc.stdout)
    # Then: first element's id is "seed-first"
    assert data["documents"][0]["id"] == "seed-first", (
        f"Expected first element id 'seed-first'; got {data['documents'][0]['id']!r}"
    )


# Unit — JSON mode: not-found → stderr is JSON error envelope, stdout empty
# conceptual-workflows-codex-chaos Failure Modes (Seed not found, JSON mode)
def test_chaos_cli_json_not_found_stderr_envelope(runner, tmp_path):
    import json
    import subprocess
    import sys

    # Given: project at tmp_path with no "phantom-doc"
    lore_dir = tmp_path / ".lore"
    lore_dir.mkdir(parents=True, exist_ok=True)
    codex_dir = lore_dir / "codex"
    codex_dir.mkdir(parents=True, exist_ok=True)
    _write_doc(codex_dir, "real-doc")

    # When: CLI invoked with --json flag at end and id="phantom-doc"
    proc = subprocess.run(
        [sys.executable, "-c", "from lore.cli import main; main()",
         "codex", "chaos", "phantom-doc", "--threshold", "50", "--json"],
        capture_output=True,
        text=True,
        cwd=str(tmp_path),
    )

    # Then: exit 1, stdout empty, stderr parses as JSON error envelope
    assert proc.returncode == 1, f"Expected exit 1; got {proc.returncode}"
    assert proc.stdout == "", f"Expected empty stdout; got {proc.stdout!r}"
    error_envelope = json.loads(proc.stderr)
    assert error_envelope == {"error": 'Document "phantom-doc" not found'}, (
        f"Unexpected JSON error envelope: {error_envelope!r}"
    )


# Unit — chaos_documents raises ValueError when threshold=29
# conceptual-workflows-codex-chaos step 2 (validate_chaos_threshold called; ValueError on invalid value)
def test_chaos_documents_raises_value_error_for_threshold_29(tmp_path):
    # No codex setup needed — validator fires before any file I/O
    with pytest.raises(ValueError, match="--threshold must be between 30 and 100"):
        chaos_documents(tmp_path, "any-doc", threshold=29)


# Unit — chaos_documents raises ValueError when threshold=101
# conceptual-workflows-codex-chaos step 2 (validate_chaos_threshold called; ValueError on above-ceiling value)
def test_chaos_documents_raises_value_error_for_threshold_101(tmp_path):
    with pytest.raises(ValueError, match="--threshold must be between 30 and 100"):
        chaos_documents(tmp_path, "any-doc", threshold=101)


# Unit — chaos_documents does not raise when threshold=30
# conceptual-workflows-codex-chaos step 2 (validate_chaos_threshold: 30 is valid, no exception)
def test_chaos_documents_no_raise_for_threshold_30(tmp_path):
    # Given: a codex directory with "valid-doc"
    codex_dir = tmp_path / ".lore" / "codex"
    codex_dir.mkdir(parents=True)
    _write_doc(codex_dir, "valid-doc", related=[])

    # When/Then: no ValueError raised for threshold at floor boundary
    try:
        chaos_documents(tmp_path, "valid-doc", threshold=30)
    except ValueError as exc:
        raise AssertionError(
            f"chaos_documents raised ValueError for threshold=30: {exc}"
        ) from exc


# Unit — chaos_documents does not raise when threshold=100
# conceptual-workflows-codex-chaos step 2 (validate_chaos_threshold: 100 is valid, no exception)
def test_chaos_documents_no_raise_for_threshold_100(tmp_path):
    # Given: a codex directory with "valid-doc"
    codex_dir = tmp_path / ".lore" / "codex"
    codex_dir.mkdir(parents=True)
    _write_doc(codex_dir, "valid-doc", related=[])

    # When/Then: no ValueError raised for threshold at ceiling boundary
    try:
        chaos_documents(tmp_path, "valid-doc", threshold=100)
    except ValueError as exc:
        raise AssertionError(
            f"chaos_documents raised ValueError for threshold=100: {exc}"
        ) from exc
