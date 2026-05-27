"""Unit tests for `lore.codex._build_adjacency`.

Spec: codex-map-tech-spec § Algorithm Specification (`_build_adjacency`).

Helper signature (new — does not yet exist in production):

    _build_adjacency(index, docs) -> tuple[
        dict[str, set[str]],   # outbound:  doc_id -> set of ids it cites
        dict[str, set[str]],   # inbound:   doc_id -> set of ids that cite it
    ]

Both dicts are initialised with empty sets for every key in `index`.
Broken `related` ids (not in index) are filtered upstream by `_read_related`.

Import failures are expected Red behaviour — the helper does not yet exist.
"""

import textwrap
from pathlib import Path

# Imports the NEW helper — does not yet exist.
from lore.codex import _build_adjacency, list_codex


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
    related_line = ""
    if not omit_related:
        if related is None or related == []:
            related_line = "related: []"
        else:
            related_line = "related: [" + ", ".join(related) + "]"
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


def _index_and_docs(codex_dir: Path) -> tuple[dict, list[dict]]:
    """Build (index, docs) the same way `map_documents` does internally."""
    docs = list_codex(codex_dir.parent.parent)
    index = {d["id"]: d for d in docs}
    return index, docs


# ---------------------------------------------------------------------------
# Adjacency core
# ---------------------------------------------------------------------------


def test_build_adjacency_returns_empty_sets_for_isolated_doc(tmp_path):
    """Single doc with no related — outbound[id] and inbound[id] both empty sets."""
    codex_dir = _make_codex_dir(tmp_path)
    _write_doc(codex_dir, "lone-doc", related=[])

    index, docs = _index_and_docs(codex_dir)
    outbound, inbound = _build_adjacency(index, docs)

    assert outbound["lone-doc"] == set()
    assert inbound["lone-doc"] == set()


def test_build_adjacency_outbound_mirrors_related(tmp_path):
    """a -> b. outbound["a"] == {"b"}."""
    codex_dir = _make_codex_dir(tmp_path)
    _write_doc(codex_dir, "a", related=["b"])
    _write_doc(codex_dir, "b", related=[])

    index, docs = _index_and_docs(codex_dir)
    outbound, _inbound = _build_adjacency(index, docs)

    assert outbound["a"] == {"b"}


def test_build_adjacency_inbound_is_reverse_of_outbound(tmp_path):
    """a -> b. inbound["b"] == {"a"}."""
    codex_dir = _make_codex_dir(tmp_path)
    _write_doc(codex_dir, "a", related=["b"])
    _write_doc(codex_dir, "b", related=[])

    index, docs = _index_and_docs(codex_dir)
    _outbound, inbound = _build_adjacency(index, docs)

    assert inbound["b"] == {"a"}


def test_build_adjacency_handles_multiple_edges(tmp_path):
    """Triangle a -> b, b -> c, c -> a.

    Each node's outbound is the single successor; inbound is the single
    predecessor.
    """
    codex_dir = _make_codex_dir(tmp_path)
    _write_doc(codex_dir, "a", related=["b"])
    _write_doc(codex_dir, "b", related=["c"])
    _write_doc(codex_dir, "c", related=["a"])

    index, docs = _index_and_docs(codex_dir)
    outbound, inbound = _build_adjacency(index, docs)

    assert outbound["a"] == {"b"}
    assert outbound["b"] == {"c"}
    assert outbound["c"] == {"a"}
    assert inbound["a"] == {"c"}
    assert inbound["b"] == {"a"}
    assert inbound["c"] == {"b"}


def test_build_adjacency_skips_broken_related_ids(tmp_path):
    """a -> ghost (ghost not in index) — outbound["a"] is empty set."""
    codex_dir = _make_codex_dir(tmp_path)
    _write_doc(codex_dir, "a", related=["ghost"])
    # ghost intentionally absent from the codex

    index, docs = _index_and_docs(codex_dir)
    outbound, inbound = _build_adjacency(index, docs)

    assert outbound["a"] == set()
    # ghost was never in index — must not be a key
    assert "ghost" not in outbound
    assert "ghost" not in inbound
